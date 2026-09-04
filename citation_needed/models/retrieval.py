from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from .evidence import Evidence, EvidenceType
from .source import SourceLocation


class EvidenceRetrievalStatus(str, Enum):
    FOUND = "FOUND"
    NO_RELEVANT_EVIDENCE = "NO_RELEVANT_EVIDENCE"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    UNRESOLVED = "UNRESOLVED"


class EvidenceCandidate(BaseModel):
    """Exact source passage offered to the semantic selector.

    Candidate text is system-owned and copied from the supplied cited source.
    The model may select candidate IDs but may not rewrite candidate content.
    """

    id: str
    source_paper_id: str
    section_id: str
    passage_index: int = Field(ge=1)
    content: str = Field(min_length=1)
    location: SourceLocation
    evidence_type: EvidenceType = EvidenceType.TEXT
    lexical_score: float = Field(ge=0.0)
    purpose_boost: float = Field(default=0.0, ge=0.0)
    matched_terms: list[str] = Field(default_factory=list)

    @property
    def retrieval_score(self) -> float:
        return self.lexical_score + self.purpose_boost


class EvidenceRetrievalResult(BaseModel):
    assertion_id: str
    citation_relation_id: str
    source_paper_id: str | None = None
    status: EvidenceRetrievalStatus
    candidates: list[EvidenceCandidate] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    rationale: str = ""
    retriever_backend: str = "openai-responses"
    retriever_model: str | None = None
