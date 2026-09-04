from __future__ import annotations

from pydantic import BaseModel, Field

from citation_needed.models import CitationPurpose, ClaimType


class SemanticCitationBinding(BaseModel):
    reference_number: str
    purpose: CitationPurpose
    purpose_reason: str


class SemanticAssertionCandidate(BaseModel):
    section_id: str
    source_text: str
    normalized_claim: str
    claim_type: ClaimType
    citations: list[SemanticCitationBinding] = Field(default_factory=list)


class SemanticExtractionOutput(BaseModel):
    assertions: list[SemanticAssertionCandidate] = Field(default_factory=list)
