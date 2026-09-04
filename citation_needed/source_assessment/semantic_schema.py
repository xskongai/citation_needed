from __future__ import annotations
from pydantic import BaseModel, Field
from citation_needed.models import Completeness, InternalConsistency, MeasurementAppropriateness, SourceAssessmentRationale, SourceEvidenceDirectness, SourceLocation

class SemanticSourceAssessmentOutput(BaseModel):
    evidence_directness: SourceEvidenceDirectness
    method_completeness: Completeness
    measurement_appropriateness: MeasurementAppropriateness
    reporting_completeness: Completeness
    internal_consistency: InternalConsistency
    missing_information: list[str] = Field(default_factory=list)
    supporting_locations: list[SourceLocation] = Field(default_factory=list)
    factor_rationale: SourceAssessmentRationale
    rationale: str
