from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from .source import Provenance


class EvidenceType(str, Enum):
    TEXT = "TEXT"
    METHOD = "METHOD"
    RESULT = "RESULT"
    TABLE = "TABLE"
    FIGURE = "FIGURE"


class EvidenceState(str, Enum):
    REPORTED = "REPORTED"
    INFERRED = "INFERRED"
    NOT_REPORTED = "NOT_REPORTED"
    UNRESOLVED = "UNRESOLVED"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    CONFLICTED = "CONFLICTED"


class Evidence(BaseModel):
    id: str
    citation_relation_id: str
    source_paper_id: str
    content: str = Field(min_length=1)
    evidence_type: EvidenceType = EvidenceType.TEXT
    provenance: Provenance
    epistemic_state: EvidenceState = EvidenceState.REPORTED
    experimental_context: dict[str, Any] = Field(default_factory=dict)
    extraction_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
