from __future__ import annotations

import re

from citation_needed.models.document import ReferenceEntry

_BRACKET_START = re.compile(r"^\s*\[(\d+)\]\s*(.*)$")
_DOT_START = re.compile(r"^\s*(\d+)\.\s+(.*)$")
_DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)
_URL_RE = re.compile(r"https?://[^\s<>]+", re.IGNORECASE)
_YEAR_RE = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")


def _clean_identifier_tail(value: str) -> str:
    return value.rstrip(".,;:)]}")


def _extract_metadata(raw_text: str) -> tuple[str | None, str | None, int | None]:
    doi_match = _DOI_RE.search(raw_text)
    url_match = _URL_RE.search(raw_text)
    years = [int(m.group(1)) for m in _YEAR_RE.finditer(raw_text)]
    doi = _clean_identifier_tail(doi_match.group(0)) if doi_match else None
    url = _clean_identifier_tail(url_match.group(0)) if url_match else None
    # Conservative heuristic: retain raw text and use the last visible year.
    year = years[-1] if years else None
    return doi, url, year


def parse_reference_section(text: str) -> list[ReferenceEntry]:
    """Parse a numeric bibliography block into reference entries.

    Supported starts:
      [17] Author, Title, Journal ...
      17. Author, Title, Journal ...

    Continuation lines are appended to the active entry. Lines before the first
    numeric entry are ignored. Duplicate reference numbers are intentionally
    preserved as separate entries so downstream resolution can mark them
    ambiguous rather than silently choosing one.
    """

    records: list[tuple[str, list[str]]] = []
    current_chunks: list[str] | None = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        match = _BRACKET_START.match(line) or _DOT_START.match(line)
        if match:
            number, rest = match.group(1), match.group(2).strip()
            current_chunks = []
            records.append((number, current_chunks))
            if rest:
                current_chunks.append(rest)
            continue

        if current_chunks is not None:
            current_chunks.append(line)

    parsed: list[ReferenceEntry] = []
    for number, chunks in records:
        raw_text = " ".join(chunks).strip()
        if not raw_text:
            continue
        doi, url, year = _extract_metadata(raw_text)
        parsed.append(
            ReferenceEntry(
                reference_number=number,
                raw_text=raw_text,
                doi=doi,
                url=url,
                year=year,
            )
        )
    return parsed
