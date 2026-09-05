from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

from citation_needed.models.acquisition import (
    AccessLevel,
    AcquisitionProvider,
    AcquisitionStatus,
    AcquiredArtifact,
    AcquiredMetadata,
    AcquiredSource,
    ArtifactKind,
    ProviderAttempt,
)
from citation_needed.models.citation import ResolutionStatus
from citation_needed.models.resolution import CitationResolution, IdentityBasis

from .http import AcquisitionNetworkError, ContentTooLargeError, HttpClient, UrllibHttpClient
from .providers import (
    RemoteCandidate,
    fetch_crossref,
    fetch_unpaywall,
    infer_kind_from_url,
    kind_from_media_type,
    normalize_doi,
    parse_crossref,
    parse_unpaywall,
)


def _merge_metadata(base: AcquiredMetadata, incoming: AcquiredMetadata) -> AcquiredMetadata:
    return AcquiredMetadata(
        title=incoming.title or base.title,
        authors=incoming.authors or base.authors,
        year=incoming.year or base.year,
        venue=incoming.venue or base.venue,
        publisher=incoming.publisher or base.publisher,
        doi=incoming.doi or base.doi,
        abstract=incoming.abstract or base.abstract,
        landing_url=incoming.landing_url or base.landing_url,
    )


def _metadata_from_resolution(resolution: CitationResolution) -> AcquiredMetadata:
    entry = resolution.reference_entry
    if entry is None:
        return AcquiredMetadata()
    return AcquiredMetadata(
        title=entry.title,
        authors=list(entry.authors),
        year=entry.year,
        venue=entry.venue,
        doi=normalize_doi(entry.doi) if entry.doi else None,
        landing_url=entry.url,
    )


def _doi_from_resolution(resolution: CitationResolution) -> str | None:
    if resolution.reference_entry and resolution.reference_entry.doi:
        return normalize_doi(resolution.reference_entry.doi)
    if resolution.cited_paper_id and resolution.cited_paper_id.startswith("doi:"):
        return normalize_doi(resolution.cited_paper_id[4:])
    return None


def _extension(kind: ArtifactKind) -> str:
    return {
        ArtifactKind.PDF: ".pdf",
        ArtifactKind.XML: ".xml",
        ArtifactKind.HTML: ".html",
        ArtifactKind.TEXT: ".txt",
    }.get(kind, ".bin")


def _safe_stem(paper_id: str | None, url: str) -> str:
    seed = paper_id or url
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
    readable = re.sub(r"[^A-Za-z0-9._-]+", "-", seed)[:48].strip("-._") or "source"
    return f"{readable}-{digest}"


def _save_artifact(
    body: bytes,
    *,
    output_dir: Path,
    paper_id: str | None,
    url: str,
    kind: ArtifactKind,
) -> tuple[str, str, int]:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{_safe_stem(paper_id, url)}{_extension(kind)}"
    path.write_bytes(body)
    sha = hashlib.sha256(body).hexdigest()
    return str(path), sha, len(body)


def _dedupe_candidates(candidates: list[RemoteCandidate]) -> list[RemoteCandidate]:
    out: list[RemoteCandidate] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate.url in seen:
            continue
        seen.add(candidate.url)
        out.append(candidate)
    return out


def acquire_source(
    resolution: CitationResolution,
    *,
    output_dir: str | Path = "data/acquired",
    contact_email: str | None = None,
    client: HttpClient | None = None,
    timeout: float = 20.0,
    metadata_max_bytes: int = 5_000_000,
    artifact_max_bytes: int = 50_000_000,
) -> AcquiredSource:
    """Acquire the best available source artifact for a resolved citation.

    The acquirer never treats lack of access as negative scientific evidence.
    It also never labels a landing page as full text merely because it is HTML.
    """

    if resolution.status == ResolutionStatus.UNRESOLVED or resolution.reference_entry is None:
        return AcquiredSource(
            relation_id=resolution.relation_id,
            cited_paper_id=resolution.cited_paper_id,
            status=AcquisitionStatus.UNRESOLVED,
            warnings=["Citation identity is unresolved; remote acquisition was not attempted."],
        )

    http = client or UrllibHttpClient()
    email = contact_email or os.getenv("CITATION_NEEDED_CONTACT_EMAIL")
    metadata = _metadata_from_resolution(resolution)
    attempts: list[ProviderAttempt] = []
    warnings: list[str] = []
    candidates: list[RemoteCandidate] = []
    discovered_urls: list[str] = []
    network_failures = 0
    remote_not_found = 0
    access_restricted = False
    doi = _doi_from_resolution(resolution)

    if doi:
        try:
            response = fetch_crossref(doi, http, timeout=timeout, max_bytes=metadata_max_bytes)
            attempts.append(ProviderAttempt(
                provider=AcquisitionProvider.CROSSREF,
                url=response.url,
                status_code=response.status_code,
                outcome="metadata_lookup",
            ))
            if response.status_code == 200:
                crossref_meta, crossref_candidates = parse_crossref(response)
                metadata = _merge_metadata(metadata, crossref_meta)
                candidates.extend(crossref_candidates)
                if crossref_meta.landing_url:
                    discovered_urls.append(crossref_meta.landing_url)
            elif response.status_code == 404:
                remote_not_found += 1
            elif response.status_code in {401, 403}:
                access_restricted = True
            else:
                warnings.append(f"Crossref lookup returned HTTP {response.status_code}.")
        except (AcquisitionNetworkError, ContentTooLargeError, ValueError) as exc:
            network_failures += 1
            attempts.append(ProviderAttempt(
                provider=AcquisitionProvider.CROSSREF,
                url=f"doi:{doi}",
                outcome="failed",
                detail=str(exc),
            ))

        if email:
            try:
                response = fetch_unpaywall(doi, email, http, timeout=timeout, max_bytes=metadata_max_bytes)
                attempts.append(ProviderAttempt(
                    provider=AcquisitionProvider.UNPAYWALL,
                    url=response.url,
                    status_code=response.status_code,
                    outcome="oa_lookup",
                ))
                if response.status_code == 200:
                    is_oa, oa_candidates = parse_unpaywall(response)
                    if is_oa is False:
                        access_restricted = True
                    candidates.extend(oa_candidates)
                    discovered_urls.extend(c.url for c in oa_candidates)
                elif response.status_code == 404:
                    remote_not_found += 1
                elif response.status_code in {401, 403}:
                    access_restricted = True
                else:
                    warnings.append(f"Unpaywall lookup returned HTTP {response.status_code}.")
            except (AcquisitionNetworkError, ContentTooLargeError, ValueError) as exc:
                network_failures += 1
                attempts.append(ProviderAttempt(
                    provider=AcquisitionProvider.UNPAYWALL,
                    url=f"doi:{doi}",
                    outcome="failed",
                    detail=str(exc),
                ))
        else:
            warnings.append(
                "CITATION_NEEDED_CONTACT_EMAIL not set; Unpaywall lookup was skipped."
            )

    entry = resolution.reference_entry
    if entry and entry.url:
        kind = infer_kind_from_url(entry.url)
        candidates.append(RemoteCandidate(
            url=entry.url,
            provider=AcquisitionProvider.DIRECT_URL,
            kind_hint=kind if kind != ArtifactKind.UNKNOWN else ArtifactKind.LANDING_PAGE,
            access_level=AccessLevel.UNKNOWN,
        ))
        discovered_urls.append(entry.url)

    candidates = _dedupe_candidates(candidates)
    discovered_urls = list(dict.fromkeys(discovered_urls + [c.url for c in candidates]))
    artifacts: list[AcquiredArtifact] = []

    # Only download candidates that are plausibly full text. A landing page is
    # useful provenance but is not silently promoted to full-text evidence.
    downloadable = [
        c for c in candidates
        if c.kind_hint in {ArtifactKind.PDF, ArtifactKind.XML, ArtifactKind.HTML, ArtifactKind.TEXT}
    ]
    for candidate in downloadable:
        try:
            response = http.get(
                candidate.url,
                headers={"Accept": "application/pdf, application/xml, text/xml, text/plain, text/html;q=0.8, */*;q=0.1"},
                timeout=timeout,
                max_bytes=artifact_max_bytes,
            )
            attempts.append(ProviderAttempt(
                provider=candidate.provider,
                url=response.url,
                status_code=response.status_code,
                outcome="artifact_fetch",
            ))
            if response.status_code in {401, 403}:
                access_restricted = True
                continue
            if response.status_code == 404:
                remote_not_found += 1
                continue
            if response.status_code != 200:
                warnings.append(f"Artifact fetch returned HTTP {response.status_code}: {candidate.url}")
                continue

            media_type = response.headers.get("content-type")
            actual_kind = kind_from_media_type(media_type)
            if actual_kind == ArtifactKind.UNKNOWN:
                actual_kind = candidate.kind_hint if candidate.kind_hint != ArtifactKind.UNKNOWN else infer_kind_from_url(response.url)

            # HTML returned for a PDF/XML candidate is commonly a login or
            # publisher landing page. Do not treat that downgrade as full text.
            if actual_kind == ArtifactKind.HTML and candidate.kind_hint not in {ArtifactKind.HTML, ArtifactKind.TEXT}:
                warnings.append(f"Candidate returned HTML instead of expected full-text artifact: {candidate.url}")
                continue
            if actual_kind not in {ArtifactKind.PDF, ArtifactKind.XML, ArtifactKind.HTML, ArtifactKind.TEXT}:
                warnings.append(f"Unsupported artifact media type {media_type!r}: {candidate.url}")
                continue

            path, sha, size = _save_artifact(
                response.body,
                output_dir=Path(output_dir),
                paper_id=resolution.cited_paper_id,
                url=response.url,
                kind=actual_kind,
            )
            artifacts.append(AcquiredArtifact(
                provider=candidate.provider,
                url=response.url,
                kind=actual_kind,
                media_type=media_type,
                access_level=candidate.access_level,
                local_path=path,
                sha256=sha,
                size_bytes=size,
            ))
            # One exact full-text artifact is enough for v1.9. Keep provider
            # order deterministic: OA PDF first, then repository/Crossref.
            break
        except (AcquisitionNetworkError, ContentTooLargeError) as exc:
            network_failures += 1
            attempts.append(ProviderAttempt(
                provider=candidate.provider,
                url=candidate.url,
                outcome="failed",
                detail=str(exc),
            ))

    if artifacts:
        status = AcquisitionStatus.FULL_TEXT_AVAILABLE
    elif metadata.abstract:
        status = AcquisitionStatus.ABSTRACT_ONLY
    elif access_restricted:
        status = AcquisitionStatus.ACCESS_RESTRICTED
    elif doi and remote_not_found >= (2 if email else 1):
        status = AcquisitionStatus.NOT_FOUND
    elif network_failures and not any(a.status_code == 200 for a in attempts):
        status = AcquisitionStatus.ACQUISITION_FAILED
    else:
        status = AcquisitionStatus.METADATA_ONLY

    return AcquiredSource(
        relation_id=resolution.relation_id,
        cited_paper_id=resolution.cited_paper_id,
        status=status,
        metadata=metadata,
        artifacts=artifacts,
        discovered_urls=discovered_urls,
        provider_attempts=attempts,
        warnings=warnings,
    )
