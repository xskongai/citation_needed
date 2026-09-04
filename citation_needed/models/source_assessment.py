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


class SourceEvidenceBasis(str, Enum):
    """How the source-level evidence is expressed.

    This is deliberately different from claim/evidence support. It describes the
    epistemic basis of the reported source content.
    """

    DIRECT_MEASUREMENT = "DIRECT_MEASUREMENT"
    DERIVED_RESULT = "DERIVED_RESULT"
    REPORTED_RESULT = "REPORTED_RESULT"
    AUTHOR_INTERPRETATION = "AUTHOR_INTERPRETATION"
    SECONDARY_REPORT = "SECONDARY_REPORT"
    UNKNOWN = "UNKNOWN"


# Backward-compatible import alias for v1.3 callers.
SourceEvidenceDirectness = SourceEvidenceBasis


class MeasurementMethodStatus(str, Enum):
    IDENTIFIED = "IDENTIFIED"
    NOT_IDENTIFIED = "NOT_IDENTIFIED"
    UNKNOWN = "UNKNOWN"


class MeasurementTargetLink(str, Enum):
    EXPLICIT = "EXPLICIT"
    INFERRED = "INFERRED"
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


class MeasurementTraceability(BaseModel):
    """Traceability from a target result to the method/measurement that produced it."""

    method_status: MeasurementMethodStatus = MeasurementMethodStatus.UNKNOWN
    identified_methods: list[str] = Field(default_factory=list)
    target_link: MeasurementTargetLink = MeasurementTargetLink.UNKNOWN
    appropriateness: MeasurementAppropriateness = MeasurementAppropriateness.UNKNOWN
    rationale: str = ""


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
    evidence_basis: str
    method_completeness: str
    reporting_completeness: str
    source_originality: str
    internal_consistency: str


class SourceAssessment(BaseModel):
    id: str
    source_paper_id: str
    evidence_ids: list[str] = Field(default_factory=list)
    context_scope: SourceContextScope
    evidence_basis: SourceEvidenceBasis = SourceEvidenceBasis.UNKNOWN
    method_completeness: Completeness = Completeness.UNKNOWN
    measurement_traceability: MeasurementTraceability = Field(default_factory=MeasurementTraceability)
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
