from __future__ import annotations

from pydantic import BaseModel, Field

from citation_needed.models import (
    AlignmentAssessment,
    ClaimComponentAssessment,
    RelevanceJudgement,
    ReliabilityFactorRationale,
    ReliabilityFactors,
    SupportJudgement,
)


class SemanticJudgeOutput(BaseModel):
    """Structured relation-level semantic output before system overrides/policy."""

    relevance: RelevanceJudgement
    support: SupportJudgement
    claim_components: list[ClaimComponentAssessment] = Field(default_factory=list)
    alignment: AlignmentAssessment
    reliability_factors: ReliabilityFactors
    factor_rationale: ReliabilityFactorRationale
    uncertainty: list[str] = Field(default_factory=list)
    rationale: str
