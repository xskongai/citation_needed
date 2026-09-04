from __future__ import annotations
from enum import Enum
from pydantic import BaseModel, Field
from .judgement import Completeness, SourceOriginality
from .source import SourceLocation, SourceRole

class SourceContextScope(str, Enum):
    EXCERPT_ONLY = "EXCERPT_ONLY"
    RELEVANT_SECTIONS = "RELEVANT_SECTIONS"
    FULL_SOURCE = "FULL_SOURCE"

class SourceContextType(str, Enum):
    ABSTRACT = "ABSTRACT"
    METHOD = "METHOD"
    RESULT = "RESULT"
    FIGURE = "FIGURE"
    TABLE = "TABLE"
    DISCUSSION = "DISCUSSION"
    SUPPLEMENTARY = "SUPPLEMENTARY"
    OTHER = "OTHER"

class SourceEvidenceDirectness(str, Enum):
    DIRECT_MEASUREMENT = "DIRECT_MEASUREMENT"
    DERIVED_RESULT = "DERIVED_RESULT"
    AUTHOR_INTERPRETATION = "AUTHOR_INTERPRETATION"
    SECONDARY_REPORT = "SECONDARY_REPORT"
    UNKNOWN = "UNKNOWN"

class MeasurementAppropriateness(str, Enum):
    APPROPRIATE = "APPROPRIATE"
    PARTIAL = "PARTIAL"
    INAPPROPRIATE = "INAPPROPRIATE"
    UNKNOWN = "UNKNOWN"
    NA = "NA"

class InternalConsistency(str, Enum):
    CONSISTENT = "CONSISTENT"
    CONFLICTED = "CONFLICTED"
    UNKNOWN = "UNKNOWN"

class SourceContextItem(BaseModel):
    content: str = Field(min_length=1)
    context_type: SourceContextType = SourceContextType.OTHER
    location: SourceLocation

class SourceAssessmentInput(BaseModel):
    source_paper_id: str
    source_title: str | None = None
    source_role: SourceRole = SourceRole.UNKNOWN
    context_scope: SourceContextScope = SourceContextScope.EXCERPT_ONLY
    evidence_ids: list[str] = Field(default_factory=list)
    context_items: list[SourceContextItem] = Field(default_factory=list)

class SourceAssessmentRationale(BaseModel):
    evidence_directness: str
    method_completeness: str
    measurement_appropriateness: str
    reporting_completeness: str
    source_originality: str
    internal_consistency: str

class SourceAssessment(BaseModel):
    id: str
    source_paper_id: str
    evidence_ids: list[str] = Field(default_factory=list)
    context_scope: SourceContextScope
    evidence_directness: SourceEvidenceDirectness = SourceEvidenceDirectness.UNKNOWN
    method_completeness: Completeness = Completeness.UNKNOWN
    measurement_appropriateness: MeasurementAppropriateness = MeasurementAppropriateness.UNKNOWN
    reporting_completeness: Completeness = Completeness.UNKNOWN
    source_originality: SourceOriginality = SourceOriginality.UNCLEAR
    internal_consistency: InternalConsistency = InternalConsistency.UNKNOWN
    missing_information: list[str] = Field(default_factory=list)
    supporting_locations: list[SourceLocation] = Field(default_factory=list)
    factor_rationale: SourceAssessmentRationale
    rationale: str
    assessment_status: str = "COMPLETE"
    assessor_backend: str = "openai-responses"
    assessor_model: str | None = None
