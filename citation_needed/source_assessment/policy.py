from __future__ import annotations

from citation_needed.models import (
    Completeness,
    InternalConsistency,
    MeasurementAppropriateness,
    MeasurementMethodStatus,
    MeasurementTargetLink,
    SourceAssessmentInput,
    SourceContextScope,
    SourceOriginality,
    SourceRole,
)
from .semantic_schema import SemanticSourceAssessmentOutput


def derive_source_originality(role: SourceRole) -> SourceOriginality:
    if role == SourceRole.PRIMARY_STUDY:
        return SourceOriginality.PRIMARY
    if role == SourceRole.SECONDARY_SOURCE:
        return SourceOriginality.SECONDARY
    return SourceOriginality.UNCLEAR


def apply_scope_guards(
    parsed: SemanticSourceAssessmentOutput,
    source_input: SourceAssessmentInput,
) -> SemanticSourceAssessmentOutput:
    """Prevent missing context from being converted into negative source judgements."""

    if source_input.context_scope == SourceContextScope.EXCERPT_ONLY:
        parsed.method_completeness = Completeness.UNKNOWN
        parsed.reporting_completeness = Completeness.UNKNOWN
        parsed.factor_rationale.method_completeness = (
            "Not assessed: only an excerpt was supplied, so source-level method completeness cannot be established."
        )
        parsed.factor_rationale.reporting_completeness = (
            "Not assessed: only an excerpt was supplied, so source-level reporting completeness cannot be established."
        )
        if parsed.internal_consistency == InternalConsistency.CONSISTENT:
            parsed.internal_consistency = InternalConsistency.UNKNOWN
            parsed.factor_rationale.internal_consistency = (
                "Not established: an excerpt cannot demonstrate source-wide internal consistency."
            )

    elif (
        source_input.context_scope == SourceContextScope.RELEVANT_SECTIONS
        and parsed.internal_consistency == InternalConsistency.CONSISTENT
    ):
        parsed.internal_consistency = InternalConsistency.UNKNOWN
        parsed.factor_rationale.internal_consistency = (
            "No conflict was established in the supplied relevant sections, but the full source was not supplied."
        )

    mt = parsed.measurement_traceability

    # If no measurement/characterisation method is identified, there is no basis
    # for claiming a target link or measurement appropriateness.
    if mt.method_status != MeasurementMethodStatus.IDENTIFIED:
        mt.identified_methods = []
        mt.target_link = MeasurementTargetLink.UNKNOWN
        if mt.appropriateness not in {MeasurementAppropriateness.NA, MeasurementAppropriateness.UNKNOWN}:
            mt.appropriateness = MeasurementAppropriateness.UNKNOWN
        if not mt.rationale:
            mt.rationale = "Measurement/characterisation method is not established by the supplied material."

    # Appropriateness requires at least an identified method and a non-unknown
    # link to the target quantity/result. Otherwise UNKNOWN is the only auditable state.
    if mt.target_link == MeasurementTargetLink.UNKNOWN and mt.appropriateness not in {
        MeasurementAppropriateness.NA,
        MeasurementAppropriateness.UNKNOWN,
    }:
        mt.appropriateness = MeasurementAppropriateness.UNKNOWN
        mt.rationale = (
            mt.rationale.rstrip(". ")
            + ". Appropriateness is not assessed because the supplied material does not link the method to the target result."
        ).strip()

    return parsed
