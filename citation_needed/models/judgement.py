from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class RelevanceJudgement(str, Enum):
    RELEVANT = "RELEVANT"
    PARTIALLY_RELEVANT = "PARTIALLY_RELEVANT"
    IRRELEVANT = "IRRELEVANT"
    UNCLEAR = "UNCLEAR"


class SupportJudgement(str, Enum):
    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class ReliabilityJudgement(str, Enum):
    HIGH = "HIGH"
    MODERATE = "MODERATE"
    LOW = "LOW"
    UNRESOLVED = "UNRESOLVED"


class EvidenceDirectness(str, Enum):
    DIRECT = "DIRECT"
    INDIRECT = "INDIRECT"
    UNCLEAR = "UNCLEAR"


class SourceOriginality(str, Enum):
    PRIMARY = "PRIMARY"
    SECONDARY = "SECONDARY"
    UNCLEAR = "UNCLEAR"


class Completeness(str, Enum):
    SUFFICIENT = "SUFFICIENT"
    PARTIAL = "PARTIAL"
    INSUFFICIENT = "INSUFFICIENT"
    UNKNOWN = "UNKNOWN"


class CharacterisationQuality(str, Enum):
    SUFFICIENT = "SUFFICIENT"
    PARTIAL = "PARTIAL"
    INSUFFICIENT = "INSUFFICIENT"
    UNKNOWN = "UNKNOWN"
    NA = "NA"


class ContextMatch(str, Enum):
    MATCH = "MATCH"
    PARTIAL_MATCH = "PARTIAL_MATCH"
    MISMATCH = "MISMATCH"
    UNKNOWN = "UNKNOWN"


class Presence(str, Enum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    UNKNOWN = "UNKNOWN"


class ReportingClarity(str, Enum):
    CLEAR = "CLEAR"
    PARTIAL = "PARTIAL"
    UNCLEAR = "UNCLEAR"


class AlignmentAssessment(BaseModel):
    """Relation-level alignment. These are intentionally separate dimensions."""

    subject_match: ContextMatch = ContextMatch.UNKNOWN
    outcome_match: ContextMatch = ContextMatch.UNKNOWN
    condition_match: ContextMatch = ContextMatch.UNKNOWN
    condition_mismatches: list[str] = Field(default_factory=list)
    rationale: str = ""


class ClaimComponentAssessment(BaseModel):
    """Evidence coverage for one minimal, decision-relevant proposition in the claim."""

    component: str
    status: SupportJudgement
    rationale: str


class ReliabilityFactors(BaseModel):
    evidence_directness: EvidenceDirectness = EvidenceDirectness.UNCLEAR
    source_originality: SourceOriginality = SourceOriginality.UNCLEAR
    method_completeness: Completeness = Completeness.UNKNOWN
    characterization_quality: CharacterisationQuality = CharacterisationQuality.UNKNOWN
    # Backward-compatible aggregate, now derived from AlignmentAssessment for hosted v1.2.
    context_match: ContextMatch = ContextMatch.UNKNOWN
    reproducibility_evidence: Presence = Presence.UNKNOWN
    reporting_clarity: ReportingClarity = ReportingClarity.PARTIAL


class ReliabilityFactorRationale(BaseModel):
    evidence_directness: str
    source_originality: str
    method_completeness: str
    characterization_quality: str
    context_match: str
    reproducibility_evidence: str
    reporting_clarity: str


class Judgement(BaseModel):
    id: str
    assertion_id: str
    citation_relation_id: str
    evidence_ids: list[str] = Field(default_factory=list)
    relevance: RelevanceJudgement
    support: SupportJudgement
    reliability: ReliabilityJudgement
    alignment: AlignmentAssessment = Field(default_factory=AlignmentAssessment)
    claim_components: list[ClaimComponentAssessment] = Field(default_factory=list)
    reliability_factors: ReliabilityFactors
    factor_rationale: ReliabilityFactorRationale | None = None
    # Convenience projections retained for UI/backward compatibility.
    supported_components: list[str] = Field(default_factory=list)
    unsupported_components: list[str] = Field(default_factory=list)
    contradicted_components: list[str] = Field(default_factory=list)
    uncertainty: list[str] = Field(default_factory=list)
    rationale: str
    judgement_status: str = "COMPLETE"
    judge_backend: str = "deterministic-v0"
    judge_model: str | None = None
