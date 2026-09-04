from citation_needed.models import (
    AlignmentAssessment,
    Completeness,
    ContextMatch,
    Evidence,
    EvidenceState,
    EvidenceType,
    InternalConsistency,
    Judgement,
    MeasurementAppropriateness,
    MeasurementMethodStatus,
    MeasurementTargetLink,
    MeasurementTraceability,
    Provenance,
    RelevanceJudgement,
    ReliabilityFactors,
    ReliabilityJudgement,
    SourceAssessment,
    SourceAssessmentRationale,
    SourceContextScope,
    SourceEvidenceBasis,
    SourceLocation,
    SourceOriginality,
    SourceRole,
    SupportJudgement,
)
from citation_needed.reliability import decide_reliability


def ev(state=EvidenceState.REPORTED):
    return Evidence(
        id="e1",
        citation_relation_id="cr1",
        source_paper_id="p1",
        content="Measured result.",
        evidence_type=EvidenceType.RESULT,
        provenance=Provenance(
            paper_id="p1",
            title="Paper",
            source_role=SourceRole.PRIMARY_STUDY,
            location=SourceLocation(page=1, section="Results"),
        ),
        epistemic_state=state,
        experimental_context={},
    )


def relation(
    *,
    support=SupportJudgement.SUPPORTED,
    relevance=RelevanceJudgement.RELEVANT,
    condition=ContextMatch.MATCH,
    status="COMPLETE",
):
    return Judgement(
        id="j1",
        assertion_id="a1",
        citation_relation_id="cr1",
        evidence_ids=["e1"],
        relevance=relevance,
        support=support,
        reliability=ReliabilityJudgement.MODERATE,
        alignment=AlignmentAssessment(
            subject_match=ContextMatch.MATCH,
            outcome_match=ContextMatch.MATCH,
            condition_match=condition,
        ),
        reliability_factors=ReliabilityFactors(),
        rationale="relation",
        judgement_status=status,
    )


def source(
    *,
    originality=SourceOriginality.PRIMARY,
    basis=SourceEvidenceBasis.DERIVED_RESULT,
    method=Completeness.SUFFICIENT,
    reporting=Completeness.SUFFICIENT,
    consistency=InternalConsistency.CONSISTENT,
    mt_method=MeasurementMethodStatus.IDENTIFIED,
    mt_link=MeasurementTargetLink.EXPLICIT,
    mt_app=MeasurementAppropriateness.APPROPRIATE,
    status="COMPLETE",
):
    return SourceAssessment(
        id="sa1",
        source_paper_id="p1",
        evidence_ids=["e1"],
        context_scope=SourceContextScope.FULL_SOURCE,
        evidence_basis=basis,
        method_completeness=method,
        measurement_traceability=MeasurementTraceability(
            method_status=mt_method,
            identified_methods=["TEM"] if mt_method == MeasurementMethodStatus.IDENTIFIED else [],
            target_link=mt_link,
            appropriateness=mt_app,
            rationale="measurement",
        ),
        reporting_completeness=reporting,
        source_originality=originality,
        internal_consistency=consistency,
        factor_rationale=SourceAssessmentRationale(
            evidence_basis="basis",
            method_completeness="method",
            reporting_completeness="reporting",
            source_originality="provenance",
            internal_consistency="consistency",
        ),
        rationale="source",
        assessment_status=status,
    )


def test_high_for_strong_supported_primary():
    r = decide_reliability(relation(), source(), [ev()])
    assert r.level == ReliabilityJudgement.HIGH


def test_high_can_apply_to_strong_contradiction():
    r = decide_reliability(relation(support=SupportJudgement.CONTRADICTED), source(), [ev()])
    assert r.level == ReliabilityJudgement.HIGH


def test_partial_or_unknown_source_factors_yield_moderate_not_low():
    s = source(
        method=Completeness.PARTIAL,
        reporting=Completeness.PARTIAL,
        consistency=InternalConsistency.UNKNOWN,
        mt_app=MeasurementAppropriateness.UNKNOWN,
    )
    r = decide_reliability(relation(), s, [ev()])
    assert r.level == ReliabilityJudgement.MODERATE
    assert not r.blocking_signals


def test_condition_mismatch_caps_at_moderate_not_low():
    r = decide_reliability(relation(support=SupportJudgement.PARTIALLY_SUPPORTED, condition=ContextMatch.MISMATCH), source(), [ev()])
    assert r.level == ReliabilityJudgement.MODERATE


def test_secondary_only_support_is_low():
    s = source(
        originality=SourceOriginality.SECONDARY,
        basis=SourceEvidenceBasis.SECONDARY_REPORT,
        method=Completeness.UNKNOWN,
        reporting=Completeness.UNKNOWN,
        consistency=InternalConsistency.UNKNOWN,
        mt_method=MeasurementMethodStatus.UNKNOWN,
        mt_link=MeasurementTargetLink.UNKNOWN,
        mt_app=MeasurementAppropriateness.UNKNOWN,
    )
    r = decide_reliability(relation(), s, [ev()])
    assert r.level == ReliabilityJudgement.LOW
    assert any("secondary" in x.lower() for x in r.blocking_signals)


def test_internal_conflict_is_low():
    r = decide_reliability(relation(), source(consistency=InternalConsistency.CONFLICTED), [ev(EvidenceState.CONFLICTED)])
    assert r.level == ReliabilityJudgement.LOW
    assert any("internal conflict" in x.lower() for x in r.blocking_signals)


def test_inappropriate_measurement_is_low():
    r = decide_reliability(relation(), source(mt_app=MeasurementAppropriateness.INAPPROPRIATE), [ev()])
    assert r.level == ReliabilityJudgement.LOW
    assert any("inappropriate" in x.lower() for x in r.blocking_signals)


def test_unavailable_evidence_is_unresolved():
    r = decide_reliability(relation(), source(), [ev(EvidenceState.SOURCE_UNAVAILABLE)])
    assert r.level == ReliabilityJudgement.UNRESOLVED


def test_incomplete_relation_is_unresolved():
    r = decide_reliability(relation(status="UNRESOLVED"), source(), [ev()])
    assert r.level == ReliabilityJudgement.UNRESOLVED
