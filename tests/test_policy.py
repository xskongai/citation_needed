from citation_needed.judgement.policy import reliability_from_factors
from citation_needed.models import (
    CharacterisationQuality,
    Completeness,
    ContextMatch,
    Evidence,
    EvidenceDirectness,
    EvidenceState,
    EvidenceType,
    Presence,
    Provenance,
    ReliabilityFactors,
    ReliabilityJudgement,
    ReportingClarity,
    SourceLocation,
    SourceOriginality,
)


def _evidence() -> Evidence:
    return Evidence(
        id="e",
        citation_relation_id="c",
        source_paper_id="p",
        content="reported result",
        evidence_type=EvidenceType.RESULT,
        provenance=Provenance(paper_id="p", location=SourceLocation(page=1)),
        epistemic_state=EvidenceState.REPORTED,
    )


def test_high_reliability_policy():
    factors = ReliabilityFactors(
        evidence_directness=EvidenceDirectness.DIRECT,
        source_originality=SourceOriginality.PRIMARY,
        method_completeness=Completeness.SUFFICIENT,
        characterization_quality=CharacterisationQuality.SUFFICIENT,
        context_match=ContextMatch.MATCH,
        reproducibility_evidence=Presence.UNKNOWN,
        reporting_clarity=ReportingClarity.CLEAR,
    )
    assert reliability_from_factors(factors, [_evidence()]) == ReliabilityJudgement.HIGH


def test_context_mismatch_reduces_reliability():
    factors = ReliabilityFactors(
        evidence_directness=EvidenceDirectness.DIRECT,
        source_originality=SourceOriginality.PRIMARY,
        method_completeness=Completeness.PARTIAL,
        characterization_quality=CharacterisationQuality.PARTIAL,
        context_match=ContextMatch.MISMATCH,
        reproducibility_evidence=Presence.ABSENT,
        reporting_clarity=ReportingClarity.CLEAR,
    )
    assert reliability_from_factors(factors, [_evidence()]) == ReliabilityJudgement.LOW
