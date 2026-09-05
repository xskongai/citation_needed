from __future__ import annotations

import html
import re
from dataclasses import dataclass
from urllib.parse import quote, urlencode

from citation_needed.models.acquisition import (
    AccessLevel,
    AcquisitionProvider,
    AcquiredMetadata,
    ArtifactKind,
)

from .http import HttpClient, HttpResponse


@dataclass(frozen=True)
class RemoteCandidate:
    url: str
    provider: AcquisitionProvider
    kind_hint: ArtifactKind = ArtifactKind.UNKNOWN
    access_level: AccessLevel = AccessLevel.UNKNOWN


def normalize_doi(value: str) -> str:
    doi = value.strip()
    doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi, flags=re.I)
    return doi.lower().rstrip(".,;:)]}")


def crossref_url(doi: str) -> str:
    return f"https://api.crossref.org/works/{quote(normalize_doi(doi), safe='')}"


def unpaywall_url(doi: str, email: str) -> str:
    query = urlencode({"email": email})
    return f"https://api.unpaywall.org/v2/{quote(normalize_doi(doi), safe='/')}?{query}"


def _strip_markup(value: str | None) -> str | None:
    if not value:
        return None
    text = re.sub(r"<[^>]+>", " ", value)
    text = html.unescape(re.sub(r"\s+", " ", text)).strip()
    return text or None


def parse_crossref(response: HttpResponse) -> tuple[AcquiredMetadata, list[RemoteCandidate]]:
    payload = response.json()
    if not isinstance(payload, dict) or not isinstance(payload.get("message"), dict):
        raise ValueError("Unexpected Crossref response shape.")
    msg = payload["message"]

    title = None
    if isinstance(msg.get("title"), list) and msg["title"]:
        title = str(msg["title"][0])

    authors: list[str] = []
    if isinstance(msg.get("author"), list):
        for item in msg["author"]:
            if not isinstance(item, dict):
                continue
            full = " ".join(str(item.get(k, "")).strip() for k in ("given", "family")).strip()
            if full:
                authors.append(full)

    year = None
    for key in ("published-print", "published-online", "issued", "created"):
        part = msg.get(key)
        if isinstance(part, dict):
            dp = part.get("date-parts")
            if isinstance(dp, list) and dp and isinstance(dp[0], list) and dp[0]:
                try:
                    year = int(dp[0][0])
                except Exception:
                    pass
                if year:
                    break

    venue = None
    if isinstance(msg.get("container-title"), list) and msg["container-title"]:
        venue = str(msg["container-title"][0])

    landing = msg.get("URL") if isinstance(msg.get("URL"), str) else None
    metadata = AcquiredMetadata(
        title=title,
        authors=authors,
        year=year,
        venue=venue,
        publisher=msg.get("publisher") if isinstance(msg.get("publisher"), str) else None,
        doi=normalize_doi(msg.get("DOI")) if isinstance(msg.get("DOI"), str) else None,
        abstract=_strip_markup(msg.get("abstract") if isinstance(msg.get("abstract"), str) else None),
        landing_url=landing,
    )

    candidates: list[RemoteCandidate] = []
    for link in msg.get("link", []) if isinstance(msg.get("link"), list) else []:
        if not isinstance(link, dict) or not isinstance(link.get("URL"), str):
            continue
        ctype = str(link.get("content-type", "")).lower()
        kind = kind_from_media_type(ctype)
        if kind in {ArtifactKind.PDF, ArtifactKind.XML, ArtifactKind.HTML, ArtifactKind.TEXT}:
            candidates.append(
                RemoteCandidate(
                    url=link["URL"],
                    provider=AcquisitionProvider.CROSSREF,
                    kind_hint=kind,
                    access_level=AccessLevel.UNKNOWN,
                )
            )
    return metadata, candidates


def parse_unpaywall(response: HttpResponse) -> tuple[bool | None, list[RemoteCandidate]]:
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("Unexpected Unpaywall response shape.")
    is_oa = payload.get("is_oa") if isinstance(payload.get("is_oa"), bool) else None

    locations: list[dict] = []
    best = payload.get("best_oa_location")
    if isinstance(best, dict):
        locations.append(best)
    raw = payload.get("oa_locations")
    if isinstance(raw, list):
        locations.extend(item for item in raw if isinstance(item, dict) and item not in locations)

    candidates: list[RemoteCandidate] = []
    seen: set[str] = set()
    for loc in locations:
        pdf = loc.get("url_for_pdf")
        if isinstance(pdf, str) and pdf and pdf not in seen:
            seen.add(pdf)
            candidates.append(
                RemoteCandidate(
                    url=pdf,
                    provider=AcquisitionProvider.UNPAYWALL,
                    kind_hint=ArtifactKind.PDF,
                    access_level=AccessLevel.OPEN_ACCESS,
                )
            )
        landing = loc.get("url_for_landing_page")
        if isinstance(landing, str) and landing and landing not in seen:
            seen.add(landing)
            candidates.append(
                RemoteCandidate(
                    url=landing,
                    provider=AcquisitionProvider.UNPAYWALL,
                    kind_hint=ArtifactKind.LANDING_PAGE,
                    access_level=AccessLevel.OPEN_ACCESS,
                )
            )
    return is_oa, candidates


def kind_from_media_type(media_type: str | None) -> ArtifactKind:
    value = (media_type or "").split(";", 1)[0].strip().lower()
    if value == "application/pdf":
        return ArtifactKind.PDF
    if "xml" in value:
        return ArtifactKind.XML
    if value in {"text/html", "application/xhtml+xml"}:
        return ArtifactKind.HTML
    if value.startswith("text/plain"):
        return ArtifactKind.TEXT
    return ArtifactKind.UNKNOWN


def infer_kind_from_url(url: str) -> ArtifactKind:
    lower = url.lower().split("?", 1)[0]
    if lower.endswith(".pdf"):
        return ArtifactKind.PDF
    if lower.endswith((".xml", ".nxml")):
        return ArtifactKind.XML
    if lower.endswith((".txt", ".text")):
        return ArtifactKind.TEXT
    return ArtifactKind.UNKNOWN


def fetch_crossref(doi: str, client: HttpClient, *, timeout: float, max_bytes: int) -> HttpResponse:
    return client.get(
        crossref_url(doi),
        headers={"Accept": "application/json"},
        timeout=timeout,
        max_bytes=max_bytes,
    )


def fetch_unpaywall(doi: str, email: str, client: HttpClient, *, timeout: float, max_bytes: int) -> HttpResponse:
    return client.get(
        unpaywall_url(doi, email),
        headers={"Accept": "application/json"},
        timeout=timeout,
        max_bytes=max_bytes,
    )
