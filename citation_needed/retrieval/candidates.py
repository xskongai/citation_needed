from __future__ import annotations

import math
import re
from dataclasses import dataclass

from citation_needed.models import (
    Assertion,
    CitationPurpose,
    CitationRelation,
    DocumentSection,
    EvidenceCandidate,
    EvidenceType,
    SourceLocation,
    StructuredDocument,
)


_TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:\.[0-9]+)?(?:%|wt%|nm|μm|um|mm|cm|mV|V|A|F|g|kg|Hz|kHz|°C|C)?", re.I)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(])")

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "being", "by", "for", "from",
    "had", "has", "have", "in", "into", "is", "it", "its", "of", "on", "or", "that",
    "the", "their", "this", "to", "was", "were", "with", "than", "then", "which", "using",
    "used", "show", "showed", "shows", "study", "paper", "reported", "report", "result",
}


@dataclass(frozen=True)
class _RawPassage:
    content: str
    passage_index: int


def _norm_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _tokens(text: str) -> list[str]:
    out: list[str] = []
    for token in _TOKEN_RE.findall(text.lower()):
        token = token.strip().lower()
        if len(token) <= 1 or token in _STOPWORDS:
            continue
        out.append(token)
    return out


def _query_terms(assertion: Assertion, relation: CitationRelation) -> set[str]:
    return set(_tokens(f"{assertion.normalized_claim} {relation.citation_context}"))


def _split_section(section: DocumentSection, *, max_chars: int = 900) -> list[_RawPassage]:
    """Split a structured section into auditable text passages.

    We never invent source locations: generated passage_index is retrieval-local;
    SourceLocation is copied from the parent section unchanged.
    """
    text = section.text.strip()
    if not text:
        return []

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n+", text) if p.strip()]
    if len(paragraphs) == 1:
        paragraphs = [text]

    passages: list[str] = []
    for paragraph in paragraphs:
        paragraph = _norm_ws(paragraph)
        if len(paragraph) <= max_chars:
            passages.append(paragraph)
            continue

        sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(paragraph) if s.strip()]
        if len(sentences) <= 1:
            # Hard fallback for parser text with no usable sentence boundaries.
            for start in range(0, len(paragraph), max_chars):
                passages.append(paragraph[start:start + max_chars].strip())
            continue

        current: list[str] = []
        current_len = 0
        for sentence in sentences:
            extra = len(sentence) + (1 if current else 0)
            if current and current_len + extra > max_chars:
                passages.append(" ".join(current))
                current = [sentence]
                current_len = len(sentence)
            else:
                current.append(sentence)
                current_len += extra
        if current:
            passages.append(" ".join(current))

    return [_RawPassage(content=p, passage_index=i + 1) for i, p in enumerate(passages) if p]


def _evidence_type(section: DocumentSection) -> EvidenceType:
    heading = (section.heading or section.location.section or "").lower()
    if any(k in heading for k in ("method", "experimental", "materials", "synthesis", "preparation")):
        return EvidenceType.METHOD
    if any(k in heading for k in ("result", "discussion", "conclusion", "performance")):
        return EvidenceType.RESULT
    return EvidenceType.TEXT


def _purpose_boost(purpose: CitationPurpose, section: DocumentSection) -> float:
    heading = (section.heading or section.location.section or "").lower()
    if not heading:
        return 0.0

    methodish = any(k in heading for k in ("method", "experimental", "materials", "synthesis", "preparation"))
    resultish = any(k in heading for k in ("result", "discussion", "performance", "conclusion"))
    introish = any(k in heading for k in ("introduction", "background", "theory"))

    if purpose in {CitationPurpose.METHOD, CitationPurpose.PARAMETER} and methodish:
        return 0.12
    if purpose in {CitationPurpose.RESULT, CitationPurpose.SUPPORT, CitationPurpose.CONTRADICTION, CitationPurpose.COMPARISON} and resultish:
        return 0.08
    if purpose in {CitationPurpose.BACKGROUND, CitationPurpose.THEORY} and introish:
        return 0.08
    return 0.0


def _lexical_score(query: set[str], content: str) -> tuple[float, list[str]]:
    if not query:
        return 0.0, []
    content_terms = set(_tokens(content))
    matched = sorted(query & content_terms)
    if not matched:
        return 0.0, []
    coverage = len(matched) / len(query)
    precision = len(matched) / max(1, len(content_terms))
    # Coverage matters more than passage density. Log damping prevents very short
    # passages from receiving extreme precision bonuses.
    score = 0.82 * coverage + 0.18 * min(1.0, precision * math.log2(2 + len(content_terms)))
    return round(score, 6), matched


def build_evidence_candidates(
    assertion: Assertion,
    relation: CitationRelation,
    source_document: StructuredDocument,
    *,
    top_k: int = 12,
) -> list[EvidenceCandidate]:
    """Generate a cheap, deterministic candidate set for semantic selection.

    This stage ranks *relevance candidates*, not supportive evidence. It does not
    inspect truth/support polarity and therefore cannot discard contradiction by design.
    """
    query = _query_terms(assertion, relation)
    candidates: list[EvidenceCandidate] = []

    for section in source_document.sections:
        for passage in _split_section(section):
            lexical, matched = _lexical_score(query, passage.content)
            boost = _purpose_boost(relation.purpose, section)
            candidates.append(
                EvidenceCandidate(
                    id=f"cand:{section.id}:{passage.passage_index}",
                    source_paper_id=source_document.paper_id,
                    section_id=section.id,
                    passage_index=passage.passage_index,
                    content=passage.content,
                    location=SourceLocation.model_validate(section.location.model_dump()),
                    evidence_type=_evidence_type(section),
                    lexical_score=lexical,
                    purpose_boost=boost,
                    matched_terms=matched,
                )
            )

    if not candidates:
        return []

    # Small documents are cheap enough to show entirely to the selector, which
    # protects against lexical misses from scientific paraphrase/synonymy.
    if len(candidates) <= top_k:
        return sorted(candidates, key=lambda c: (-c.retrieval_score, c.id))

    ranked = sorted(candidates, key=lambda c: (-c.retrieval_score, c.id))
    selected = ranked[:top_k]

    # Guarantee at least one candidate from a purpose-aligned section when it
    # was not already admitted by lexical ranking.
    aligned = [c for c in ranked[top_k:] if c.purpose_boost > 0]
    if aligned and not any(c.purpose_boost > 0 for c in selected):
        selected[-1] = aligned[0]
        selected = sorted(selected, key=lambda c: (-c.retrieval_score, c.id))

    return selected
