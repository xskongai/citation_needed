from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class CitationPurpose(str, Enum):
    METHOD = "METHOD"
    PARAMETER = "PARAMETER"
    RESULT = "RESULT"
    SUPPORT = "SUPPORT"
    BACKGROUND = "BACKGROUND"
    THEORY = "THEORY"
    COMPARISON = "COMPARISON"
    CONTRADICTION = "CONTRADICTION"
    OTHER = "OTHER"


class FollowPriority(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    STOP = "STOP"


class ResolutionStatus(str, Enum):
    RESOLVED = "RESOLVED"
    PARTIALLY_RESOLVED = "PARTIALLY_RESOLVED"
    UNRESOLVED = "UNRESOLVED"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"


class CitationRelation(BaseModel):
    id: str
    assertion_id: str
    source_paper_id: str
    cited_paper_id: str | None = None
    reference_number: str = Field(min_length=1)
    citation_context: str = Field(min_length=1)
    purpose: CitationPurpose = CitationPurpose.OTHER
    purpose_reason: str | None = None
    follow_priority: FollowPriority = FollowPriority.MEDIUM
    resolution_status: ResolutionStatus = ResolutionStatus.UNRESOLVED
