from __future__ import annotations

from citation_needed.models import (
    CitationAuditResult,
    Completeness,
    ContextMatch,
    Evidence,
    EvidenceState,
    InternalConsistency,
    Judgement,
    MeasurementAppropriateness,
    MeasurementMethodStatus,
    MeasurementTargetLink,
    ReliabilityDecision,
    ReliabilityJudgement,
    RelevanceJudgement,
    SourceAssessment,
    SourceEvidenceBasis,
    SourceOriginality,
    SupportJudgement,
)


_STRONG_BASES = {
    SourceEvidenceBasis.DIRECT_MEASUREMENT,
    SourceEvidenceBasis.DERIVED_RESULT,
}

_ACCEPTABLE_BASES = {
    SourceEvidenceBasis.DIRECT_MEASUREMENT,
    SourceEvidenceBasis.DERIVED_RESULT,
    SourceEvidenceBasis.REPORTED_RESULT,
}


def _append_unique(items: list[str], value: str) -> None:
    if value and value not in items:
        items.append(value)


def decide_reliability(
    relation: Judgement,
    source: SourceAssessment,
    evidence: list[Evidence],
) -> ReliabilityDecision:
    """Combine Relation Judge + Source Assessor with deterministic rules.

    Design principles:
    - No numeric confidence score.
    - SUPPORTED does not imply HIGH, and CONTRADICTED does not imply LOW.
    - UNKNOWN is neutral/cautionary, not negative evidence.
    - Explicit source conflicts, inappropriate measurement, and secondary-only
      evidence are hard reasons to cap the result at LOW.
    - HIGH is intentionally strict and requires a well-traced primary source.
    """

    positive: list[str] = []
    cautions: list[str] = []
    blockers: list[str] = []

    # 1) Unresolved states are terminal.
    unresolved_evidence = any(
        ev.epistemic_state in {EvidenceState.UNRESOLVED, EvidenceState.SOURCE_UNAVAILABLE}
        for ev in evidence
    )
    if relation.judgement_status != "COMPLETE":
        _append_unique(blockers, "Relation judgement is not complete.")
    if source.assessment_status != "COMPLETE":
        _append_unique(blockers, "Source assessment is not complete.")
    if unresolved_evidence:
        _append_unique(blockers, "At least one required evidence item is unresolved or unavailable.")
    if relation.relevance == RelevanceJudgement.UNCLEAR:
        _append_unique(blockers, "Claim-evidence relevance remains unclear.")

    if blockers:
        return ReliabilityDecision(
            level=ReliabilityJudgement.UNRESOLVED,
            positive_signals=positive,
            caution_signals=cautions,
            blocking_signals=blockers,
            rationale="Reliability is unresolved because the audit lacks a complete, evaluable evidence chain.",
        )

    # 2) Relation-level signals. These describe fit, not source quality.
    if relation.relevance == RelevanceJudgement.RELEVANT:
        _append_unique(positive, "Evidence is relevant to the evaluated claim.")
    elif relation.relevance == RelevanceJudgement.PARTIALLY_RELEVANT:
        _append_unique(cautions, "Evidence is only partially relevant to the evaluated claim.")
    elif relation.relevance == RelevanceJudgement.IRRELEVANT:
        _append_unique(cautions, "Evidence is not relevant to the evaluated claim; the support conclusion is therefore limited.")

    if relation.support == SupportJudgement.SUPPORTED:
        _append_unique(positive, "The supplied evidence supports the material claim components.")
    elif relation.support == SupportJudgement.CONTRADICTED:
        _append_unique(positive, "The supplied evidence materially contradicts the claim; contradiction can be reliable when the source is strong.")
    elif relation.support == SupportJudgement.PARTIALLY_SUPPORTED:
        _append_unique(cautions, "Only part of the claim is supported by the supplied evidence.")
    elif relation.support == SupportJudgement.INSUFFICIENT_EVIDENCE:
        _append_unique(cautions, "The supplied evidence is insufficient to establish the claim.")

    # Alignment limits applicability but is not itself evidence of poor source quality.
    a = relation.alignment
    if a.subject_match == ContextMatch.MATCH and a.outcome_match == ContextMatch.MATCH:
        _append_unique(positive, "Claim and evidence align on subject and outcome.")
    else:
        _append_unique(cautions, "Subject/outcome alignment is incomplete or mismatched.")

    if a.condition_match == ContextMatch.MISMATCH:
        _append_unique(cautions, "Experimental conditions materially differ between claim and evidence.")
    elif a.condition_match in {ContextMatch.UNKNOWN, ContextMatch.PARTIAL_MATCH}:
        _append_unique(cautions, "Experimental-condition alignment is incomplete or not fully established.")

    # 3) Source-level hard-low conditions.
    if source.source_originality == SourceOriginality.SECONDARY:
        _append_unique(blockers, "The current support is secondary; the original source has not been audited directly.")
    elif source.source_originality == SourceOriginality.PRIMARY:
        _append_unique(positive, "Evidence comes from a primary study.")
    else:
        _append_unique(cautions, "Primary-vs-secondary source status is not established.")

    if source.evidence_basis == SourceEvidenceBasis.SECONDARY_REPORT:
        _append_unique(blockers, "The evidence basis is a secondary report of another study.")
    elif source.evidence_basis in _STRONG_BASES:
        _append_unique(positive, f"Evidence basis is {source.evidence_basis.value.lower().replace('_', ' ')}.")
    elif source.evidence_basis == SourceEvidenceBasis.REPORTED_RESULT:
        _append_unique(positive, "The source explicitly reports the target result.")
    elif source.evidence_basis == SourceEvidenceBasis.AUTHOR_INTERPRETATION:
        _append_unique(cautions, "The target evidence is primarily author interpretation rather than a direct/derived result.")
    else:
        _append_unique(cautions, "Evidence basis is not established from the supplied source context.")

    if source.internal_consistency == InternalConsistency.CONFLICTED:
        _append_unique(blockers, "The source contains a material internal conflict about the target evidence.")
    elif source.internal_consistency == InternalConsistency.CONSISTENT:
        _append_unique(positive, "No material internal conflict was found in the supplied full source.")
    else:
        _append_unique(cautions, "Source-wide internal consistency is not established from the supplied scope.")

    mt = source.measurement_traceability
    if mt.appropriateness == MeasurementAppropriateness.INAPPROPRIATE:
        _append_unique(blockers, "The identified measurement is inappropriate for the target result.")
    elif mt.appropriateness == MeasurementAppropriateness.APPROPRIATE:
        _append_unique(positive, "The target result is supported by an appropriate identified measurement.")
    elif mt.appropriateness == MeasurementAppropriateness.PARTIAL:
        _append_unique(cautions, "Measurement appropriateness is only partial.")
    elif mt.appropriateness == MeasurementAppropriateness.UNKNOWN:
        _append_unique(cautions, "Measurement appropriateness is not established from the supplied material.")

    if mt.method_status == MeasurementMethodStatus.IDENTIFIED:
        _append_unique(positive, "A measurement/characterisation method is identified.")
    else:
        _append_unique(cautions, "Measurement/characterisation method is not fully identified.")

    if mt.target_link == MeasurementTargetLink.EXPLICIT:
        _append_unique(positive, "The measurement-to-result link is explicit.")
    elif mt.target_link == MeasurementTargetLink.INFERRED:
        _append_unique(cautions, "The measurement-to-result link is inferred rather than explicit.")
    else:
        _append_unique(cautions, "The measurement-to-result link is not established.")

    if source.method_completeness == Completeness.SUFFICIENT:
        _append_unique(positive, "Critical method details are sufficiently reported for the target evidence.")
    elif source.method_completeness == Completeness.PARTIAL:
        _append_unique(cautions, "Critical method details are only partially reported/assessed.")
    elif source.method_completeness == Completeness.INSUFFICIENT:
        _append_unique(cautions, "Critical method details are insufficiently reported.")
    else:
        _append_unique(cautions, "Method completeness is unknown from the supplied scope.")

    if source.reporting_completeness == Completeness.SUFFICIENT:
        _append_unique(positive, "Target-result reporting is sufficiently complete.")
    elif source.reporting_completeness == Completeness.PARTIAL:
        _append_unique(cautions, "Target-result reporting is only partially complete/assessed.")
    elif source.reporting_completeness == Completeness.INSUFFICIENT:
        _append_unique(cautions, "Target-result reporting is insufficiently complete.")
    else:
        _append_unique(cautions, "Reporting completeness is unknown from the supplied scope.")

    # Hard-low conditions are deliberately categorical rather than additive.
    if blockers:
        return ReliabilityDecision(
            level=ReliabilityJudgement.LOW,
            positive_signals=positive,
            caution_signals=cautions,
            blocking_signals=blockers,
            rationale="Reliability is LOW because at least one source-level condition materially weakens the evidential chain.",
        )

    # 4) HIGH is strict: strong primary evidence, explicit traceability, sufficient
    # source context, and no material alignment limitation.
    high_relation = (
        relation.relevance == RelevanceJudgement.RELEVANT
        and relation.support in {
            SupportJudgement.SUPPORTED,
            SupportJudgement.CONTRADICTED,
        }
        and a.subject_match == ContextMatch.MATCH
        and a.outcome_match == ContextMatch.MATCH
        and a.condition_match == ContextMatch.MATCH
    )
    high_source = (
        source.source_originality == SourceOriginality.PRIMARY
        and source.evidence_basis in _STRONG_BASES
        and source.method_completeness == Completeness.SUFFICIENT
        and source.reporting_completeness == Completeness.SUFFICIENT
        and source.internal_consistency == InternalConsistency.CONSISTENT
        and mt.method_status == MeasurementMethodStatus.IDENTIFIED
        and mt.target_link == MeasurementTargetLink.EXPLICIT
        and mt.appropriateness == MeasurementAppropriateness.APPROPRIATE
    )

    if high_relation and high_source:
        return ReliabilityDecision(
            level=ReliabilityJudgement.HIGH,
            positive_signals=positive,
            caution_signals=cautions,
            blocking_signals=[],
            rationale="Reliability is HIGH because the relation is clear and the primary-source evidence is directly traceable, methodologically sufficient, and internally consistent.",
        )

    # 5) Everything evaluable without a hard-low condition is MODERATE. This
    # includes partial support and unknown/partial source factors; UNKNOWN is a
    # reason for caution, not an automatic failure.
    return ReliabilityDecision(
        level=ReliabilityJudgement.MODERATE,
        positive_signals=positive,
        caution_signals=cautions,
        blocking_signals=[],
        rationale="Reliability is MODERATE: the audit is evaluable and has no hard failure, but one or more relation/source factors remain partial, limited, or unknown.",
    )


def build_audit_result(
    relation: Judgement,
    source: SourceAssessment,
    evidence: list[Evidence],
) -> CitationAuditResult:
    decision = decide_reliability(relation, source, evidence)
    status = "UNRESOLVED" if decision.level == ReliabilityJudgement.UNRESOLVED else "COMPLETE"
    return CitationAuditResult(
        assertion_id=relation.assertion_id,
        citation_relation_id=relation.citation_relation_id,
        evidence_ids=[ev.id for ev in evidence],
        relation_judgement=relation,
        source_assessment=source,
        reliability=decision,
        audit_status=status,
    )
