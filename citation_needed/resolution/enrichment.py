from __future__ import annotations

import re
from urllib.parse import urlencode

from citation_needed.acquisition.http import (
    AcquisitionNetworkError,
    ContentTooLargeError,
    HttpClient,
    UrllibHttpClient,
)
from citation_needed.acquisition.providers import normalize_doi
from citation_needed.models.citation import ResolutionStatus
from citation_needed.models.document import ReferenceEntry
from citation_needed.models.resolution import CitationResolution, IdentityBasis


_TOKEN_RE = re.compile(r"[a-z0-9]+", re.I)


def _norm_tokens(text: str) -> set[str]:
    stop = {
        "the", "a", "an", "and", "of", "for", "in", "on", "to", "with", "its", "by",
        "et", "al", "vol", "pp", "journal", "adv", "rsc",
    }
    return {t.lower() for t in _TOKEN_RE.findall(text) if len(t) > 2 and t.lower() not in stop}


def _candidate_year(item: dict) -> int | None:
    for key in ("published-print", "published-online", "issued", "created"):
        value = item.get(key)
        if isinstance(value, dict):
            parts = value.get("date-parts")
            if isinstance(parts, list) and parts and isinstance(parts[0], list) and parts[0]:
                try:
                    return int(parts[0][0])
                except (TypeError, ValueError):
                    pass
    return None


def _candidate_title(item: dict) -> str | None:
    titles = item.get("title")
    if isinstance(titles, list) and titles:
        value = str(titles[0]).strip()
        return value or None
    return None


def _candidate_authors(item: dict) -> list[str]:
    out: list[str] = []
    authors = item.get("author")
    if not isinstance(authors, list):
        return out
    for author in authors:
        if not isinstance(author, dict):
            continue
        name = " ".join(str(author.get(k, "")).strip() for k in ("given", "family")).strip()
        if name:
            out.append(name)
    return out


def _candidate_venue(item: dict) -> str | None:
    values = item.get("container-title")
    if isinstance(values, list) and values:
        value = str(values[0]).strip()
        return value or None
    return None


def _score_candidate(entry: ReferenceEntry, item: dict) -> float:
    title = _candidate_title(item)
    doi = item.get("DOI")
    if not title or not isinstance(doi, str) or not doi.strip():
        return 0.0

    raw_tokens = _norm_tokens(entry.raw_text)
    title_tokens = _norm_tokens(title)
    if not title_tokens:
        return 0.0

    # Candidate titles should mostly occur in the supplied bibliography text.
    title_coverage = len(raw_tokens & title_tokens) / len(title_tokens)
    score = 0.82 * title_coverage

    cyear = _candidate_year(item)
    if entry.year is not None and cyear is not None:
        score += 0.12 if entry.year == cyear else -0.18

    # Small author-family-name corroboration signal.
    families = []
    for author in item.get("author", []) if isinstance(item.get("author"), list) else []:
        if isinstance(author, dict) and isinstance(author.get("family"), str):
            families.append(author["family"].lower())
    if families:
        raw_lower = entry.raw_text.lower()
        matched = sum(1 for family in families[:3] if family and family in raw_lower)
        score += 0.06 * (matched / min(3, len(families)))

    return max(0.0, min(1.0, score))


def crossref_bibliographic_url(raw_reference: str, rows: int = 5) -> str:
    query = urlencode({"query.bibliographic": raw_reference, "rows": rows})
    return f"https://api.crossref.org/works?{query}"


def enrich_resolution_crossref(
    resolution: CitationResolution,
    *,
    client: HttpClient | None = None,
    timeout: float = 20.0,
    max_bytes: int = 5_000_000,
    min_score: float = 0.78,
    min_margin: float = 0.08,
) -> CitationResolution:
    """Upgrade a local bibliography match using conservative Crossref lookup.

    Only PARTIALLY_RESOLVED references are enriched. The remote candidate must
    match the *supplied bibliography text* strongly enough; otherwise the
    resolution remains partial. This is identity enrichment, not scientific
    judgement, and it never lets an LLM invent a DOI.
    """

    if resolution.status != ResolutionStatus.PARTIALLY_RESOLVED:
        return resolution
    entry = resolution.reference_entry
    if entry is None:
        return resolution

    http = client or UrllibHttpClient(user_agent="CitationNeeded/0.14 (+reference-enrichment)")
    url = crossref_bibliographic_url(entry.raw_text)
    warnings = list(resolution.warnings)

    try:
        response = http.get(url, headers={"Accept": "application/json"}, timeout=timeout, max_bytes=max_bytes)
    except (AcquisitionNetworkError, ContentTooLargeError, OSError) as exc:
        warnings.append(f"Crossref bibliographic enrichment failed: {exc}")
        return resolution.model_copy(update={"warnings": warnings})

    if response.status_code != 200:
        warnings.append(f"Crossref bibliographic enrichment returned HTTP {response.status_code}.")
        return resolution.model_copy(update={"warnings": warnings})

    try:
        payload = response.json()
    except Exception as exc:
        warnings.append(f"Crossref bibliographic enrichment returned invalid JSON: {exc}")
        return resolution.model_copy(update={"warnings": warnings})

    message = payload.get("message") if isinstance(payload, dict) else None
    items = message.get("items") if isinstance(message, dict) else None
    if not isinstance(items, list) or not items:
        warnings.append("Crossref bibliographic enrichment returned no candidates.")
        return resolution.model_copy(update={"warnings": warnings})

    ranked: list[tuple[float, dict]] = []
    for item in items:
        if isinstance(item, dict):
            ranked.append((_score_candidate(entry, item), item))
    ranked.sort(key=lambda x: x[0], reverse=True)
    if not ranked:
        warnings.append("Crossref bibliographic enrichment returned no usable candidates.")
        return resolution.model_copy(update={"warnings": warnings})

    best_score, best = ranked[0]
    second_score = ranked[1][0] if len(ranked) > 1 else 0.0
    if best_score < min_score or (len(ranked) > 1 and best_score - second_score < min_margin):
        warnings.append(
            f"Crossref candidate identity was not strong enough (best={best_score:.3f}, second={second_score:.3f}); kept PARTIALLY_RESOLVED."
        )
        return resolution.model_copy(update={"warnings": warnings})

    doi_raw = best.get("DOI")
    title = _candidate_title(best)
    if not isinstance(doi_raw, str) or not doi_raw.strip() or not title:
        warnings.append("Crossref best candidate lacked a DOI or title; kept PARTIALLY_RESOLVED.")
        return resolution.model_copy(update={"warnings": warnings})

    doi = normalize_doi(doi_raw)
    enriched_entry = entry.model_copy(update={
        "title": title,
        "authors": _candidate_authors(best),
        "year": _candidate_year(best) or entry.year,
        "venue": _candidate_venue(best),
        "doi": doi,
        "url": best.get("URL") if isinstance(best.get("URL"), str) else entry.url,
    })

    warnings = [w for w in warnings if "no canonical source identifier" not in w.lower()]
    warnings.append(f"Resolved bibliography identity via Crossref bibliographic match (score={best_score:.3f}).")
    return resolution.model_copy(update={
        "status": ResolutionStatus.RESOLVED,
        "reference_entry": enriched_entry,
        "cited_paper_id": f"doi:{doi}",
        "identity_basis": IdentityBasis.DOI,
        "warnings": warnings,
    })
