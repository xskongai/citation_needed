from __future__ import annotations

from pydantic import BaseModel, Field

from citation_needed.models import (
    RelevanceJudgement,
    ReliabilityFactorRationale,
    ReliabilityFactors,
    SupportJudgement,
)


class SemanticJudgeOutput(BaseModel):
    """Structured semantic output before deterministic reliability aggregation."""

    relevance: RelevanceJudgement
    support: SupportJudgement
    supported_components: list[str] = Field(default_factory=list)
    unsupported_components: list[str] = Field(default_factory=list)
    contradicted_components: list[str] = Field(default_factory=list)
    reliability_factors: ReliabilityFactors
    factor_rationale: ReliabilityFactorRationale
    uncertainty: list[str] = Field(default_factory=list)
    rationale: str
