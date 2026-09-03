from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from .source import SourceLocation


class ClaimType(str, Enum):
    METHOD = "METHOD"
    PARAMETER = "PARAMETER"
    RESULT = "RESULT"
    PROPERTY = "PROPERTY"
    CAUSAL = "CAUSAL"
    COMPARISON = "COMPARISON"
    GENERAL = "GENERAL"
    OTHER = "OTHER"


class Assertion(BaseModel):
    id: str
    text: str = Field(min_length=1)
    normalized_claim: str = Field(min_length=1)
    paper_id: str
    location: SourceLocation
    claim_type: ClaimType = ClaimType.OTHER
    citation_ids: list[str] = Field(default_factory=list)
