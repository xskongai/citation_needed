from citation_needed.models import (
    Completeness,
    InternalConsistency,
    MeasurementAppropriateness,
    MeasurementMethodStatus,
    MeasurementTargetLink,
    MeasurementTraceability,
    SourceAssessmentInput,
    SourceAssessmentRationale,
    SourceContextScope,
    SourceEvidenceBasis,
    SourceOriginality,
    SourceRole,
)
from citation_needed.source_assessment.policy import apply_scope_guards, derive_source_originality
from citation_needed.source_assessment.semantic_schema import SemanticSourceAssessmentOutput


def fixture():
    return SemanticSourceAssessmentOutput(
        evidence_basis=SourceEvidenceBasis.DERIVED_RESULT,
        method_completeness=Completeness.INSUFFICIENT,
        measurement_traceability=MeasurementTraceability(
            method_status=MeasurementMethodStatus.IDENTIFIED,
            identified_methods=["GCD"],
            target_link=MeasurementTargetLink.EXPLICIT,
            appropriateness=MeasurementAppropriateness.APPROPRIATE,
            rationale="x",
        ),
        reporting_completeness=Completeness.INSUFFICIENT,
        internal_consistency=InternalConsistency.CONSISTENT,
        factor_rationale=SourceAssessmentRationale(
            evidence_basis="x",
            method_completeness="x",
            reporting_completeness="x",
            source_originality="x",
            internal_consistency="x",
        ),
        rationale="x",
    )


def test_excerpt_scope_forces_unknown_not_negative():
    out = apply_scope_guards(
        fixture(),
        SourceAssessmentInput(source_paper_id="p", context_scope=SourceContextScope.EXCERPT_ONLY),
    )
    assert out.method_completeness == Completeness.UNKNOWN
    assert out.reporting_completeness == Completeness.UNKNOWN
    assert out.internal_consistency == InternalConsistency.UNKNOWN


def test_relevant_sections_cannot_claim_global_consistency():
    out = apply_scope_guards(
        fixture(),
        SourceAssessmentInput(source_paper_id="p", context_scope=SourceContextScope.RELEVANT_SECTIONS),
    )
    assert out.internal_consistency == InternalConsistency.UNKNOWN


def test_relevant_sections_preserve_conflict():
    x = fixture()
    x.internal_consistency = InternalConsistency.CONFLICTED
    out = apply_scope_guards(
        x,
        SourceAssessmentInput(source_paper_id="p", context_scope=SourceContextScope.RELEVANT_SECTIONS),
    )
    assert out.internal_consistency == InternalConsistency.CONFLICTED


def test_originality_owned_by_provenance():
    assert derive_source_originality(SourceRole.PRIMARY_STUDY) == SourceOriginality.PRIMARY
    assert derive_source_originality(SourceRole.SECONDARY_SOURCE) == SourceOriginality.SECONDARY
    assert derive_source_originality(SourceRole.UNKNOWN) == SourceOriginality.UNCLEAR


def test_no_method_forces_unknown_measurement_link_and_appropriateness():
    x = fixture()
    x.measurement_traceability.method_status = MeasurementMethodStatus.UNKNOWN
    x.measurement_traceability.identified_methods = ["invented"]
    x.measurement_traceability.target_link = MeasurementTargetLink.EXPLICIT
    x.measurement_traceability.appropriateness = MeasurementAppropriateness.APPROPRIATE
    out = apply_scope_guards(x, SourceAssessmentInput(source_paper_id="p"))
    assert out.measurement_traceability.identified_methods == []
    assert out.measurement_traceability.target_link == MeasurementTargetLink.UNKNOWN
    assert out.measurement_traceability.appropriateness == MeasurementAppropriateness.UNKNOWN


def test_unknown_target_link_forces_unknown_appropriateness():
    x = fixture()
    x.measurement_traceability.target_link = MeasurementTargetLink.UNKNOWN
    x.measurement_traceability.appropriateness = MeasurementAppropriateness.APPROPRIATE
    out = apply_scope_guards(x, SourceAssessmentInput(source_paper_id="p"))
    assert out.measurement_traceability.appropriateness == MeasurementAppropriateness.UNKNOWN


def test_reported_result_is_distinct_from_author_interpretation():
    assert SourceEvidenceBasis.REPORTED_RESULT != SourceEvidenceBasis.AUTHOR_INTERPRETATION
