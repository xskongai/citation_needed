from __future__ import annotations

import json
import os
import uuid
from typing import Any

from citation_needed.models import (
    Assertion,
    CitationRelation,
    Evidence,
    EvidenceState,
    Judgement,
    ReliabilityFactorRationale,
    ReliabilityFactors,
    ReliabilityJudgement,
    RelevanceJudgement,
    SourceOriginality,
    SourceRole,
    SupportJudgement,
)
from .policy import merge_uncertainties, policy_uncertainties, reliability_from_factors
from .semantic_schema import SemanticJudgeOutput


SYSTEM_INSTRUCTIONS = """You are the relation-level semantic judgement component of Citation Needed, a scientific citation-audit system.

Your task is narrow: evaluate the relation between ONE assertion and the supplied evidence. Do not answer whether the claim is true in the world. Judge only what the supplied material establishes.

Rules:
1. Separate RELEVANCE from SUPPORT. Evidence can be relevant but fail to support the claim.
2. Compare claim strength with evidence strength. Check scope, quantifiers, causality, numerical values, direction of effect, population/material, method, conditions, and context. A weaker or narrower result does not fully support a stronger or broader claim.
3. Decompose partial support. Populate supported_components with claim parts actually established, unsupported_components with parts not established, and contradicted_components with parts materially opposed by the evidence.
4. CONTRADICTED requires evidence that materially opposes the claim. Mere absence, omission, or a condition mismatch is not by itself contradiction.
5. INSUFFICIENT_EVIDENCE means the supplied evidence does not establish enough to decide support. Use PARTIALLY_SUPPORTED when a meaningful part is established but another material part is not.
6. Assess factors only from information actually supplied. Never infer that a paper itself has poor/incomplete methods merely because the evidence package contains only an excerpt.
7. method_completeness concerns the source paper's method reporting. If the supplied material does not let you assess that source-level property, use UNKNOWN, not PARTIAL or INSUFFICIENT.
8. characterization_quality concerns whether the source's measurement/characterization is appropriate for the claim. If the measurement method/data needed to assess quality is not supplied, use UNKNOWN. Use NA only when scientific characterization is not relevant to the claim.
9. source_originality will be overridden from provenance metadata when available. If provenance does not establish it, use UNCLEAR rather than guessing from writing style.
10. reproducibility_evidence is PRESENT only when independent replication/reproduction evidence is supplied. Use ABSENT only when the supplied material explicitly establishes that independent reproducibility is absent. If it is simply not shown or not mentioned in the evidence package, use UNKNOWN.
11. Treat REPORTED evidence as source-reported text/data. Treat INFERRED evidence cautiously and explicitly note it.
12. Keep rationales concise and auditable. State only decision-relevant reasons.
"""


def _clean_context(value: Any) -> Any:
    """Remove private/internal hint fields so the model cannot copy v0 labels."""
    if isinstance(value, dict):
        return {
            k: _clean_context(v)
            for k, v in value.items()
            if not str(k).startswith("_")
        }
    if isinstance(value, list):
        return [_clean_context(v) for v in value]
    return value


def _build_payload(
    assertion: Assertion,
    citation: CitationRelation,
    evidence: list[Evidence],
) -> dict[str, Any]:
    return {
        "assertion": {
            "text": assertion.text,
            "normalized_claim": assertion.normalized_claim,
            "claim_type": assertion.claim_type.value,
            "location": assertion.location.model_dump(mode="json"),
        },
        "citation_relation": {
            "reference_number": citation.reference_number,
            "citation_context": citation.citation_context,
            "purpose": citation.purpose.value,
            "purpose_reason": citation.purpose_reason,
        },
        "evidence": [
            {
                "id": ev.id,
                "content": ev.content,
                "evidence_type": ev.evidence_type.value,
                "epistemic_state": ev.epistemic_state.value,
                "provenance": ev.provenance.model_dump(mode="json"),
                "experimental_context": _clean_context(ev.experimental_context),
            }
            for ev in evidence
        ],
    }


def _derive_source_originality(evidence: list[Evidence]) -> SourceOriginality:
    """Derive originality from provenance facts rather than semantic guesswork."""
    roles = {ev.provenance.source_role for ev in evidence}
    if roles == {SourceRole.PRIMARY_STUDY}:
        return SourceOriginality.PRIMARY
    if roles == {SourceRole.SECONDARY_SOURCE}:
        return SourceOriginality.SECONDARY
    return SourceOriginality.UNCLEAR


def _apply_system_factors(parsed: SemanticJudgeOutput, evidence: list[Evidence]) -> SemanticJudgeOutput:
    parsed.reliability_factors.source_originality = _derive_source_originality(evidence)
    if parsed.reliability_factors.source_originality == SourceOriginality.PRIMARY:
        parsed.factor_rationale.source_originality = "Provenance metadata marks the supplied evidence source as a primary study."
    elif parsed.reliability_factors.source_originality == SourceOriginality.SECONDARY:
        parsed.factor_rationale.source_originality = "Provenance metadata marks the supplied evidence source as secondary."
    else:
        parsed.factor_rationale.source_originality = "Provenance metadata does not establish primary-vs-secondary source status."
    return parsed


def _unresolved_result(
    assertion: Assertion,
    citation: CitationRelation,
    evidence: list[Evidence],
    *,
    backend: str,
    model: str | None,
) -> Judgement:
    return Judgement(
        id=f"j_{uuid.uuid4().hex[:10]}",
        assertion_id=assertion.id,
        citation_relation_id=citation.id,
        evidence_ids=[ev.id for ev in evidence],
        relevance=RelevanceJudgement.UNCLEAR,
        support=SupportJudgement.INSUFFICIENT_EVIDENCE,
        reliability=ReliabilityJudgement.UNRESOLVED,
        reliability_factors=ReliabilityFactors(),
        factor_rationale=ReliabilityFactorRationale(
            evidence_directness="No usable reported/inferred evidence was supplied.",
            source_originality="Cannot establish source originality without usable evidence.",
            method_completeness="Method completeness was not assessed.",
            characterization_quality="Characterization quality was not assessed.",
            context_match="Cannot compare contexts without usable evidence.",
            reproducibility_evidence="Independent reproducibility evidence is unknown.",
            reporting_clarity="Cannot assess reporting clarity without usable evidence.",
        ),
        uncertainty=["No usable evidence is available for semantic evaluation."],
        rationale="The citation relation cannot yet be judged from the supplied evidence.",
        judgement_status="UNRESOLVED",
        judge_backend=backend,
        judge_model=model,
    )


def judge_openai(
    assertion: Assertion,
    citation: CitationRelation,
    evidence: list[Evidence],
    *,
    model: str | None = None,
) -> Judgement:
    """Use a hosted semantic model for relation judgement and code for aggregation."""
    usable = [
        ev
        for ev in evidence
        if ev.epistemic_state in {EvidenceState.REPORTED, EvidenceState.INFERRED, EvidenceState.CONFLICTED}
    ]
    model = model or os.getenv("CITATION_NEEDED_MODEL", "gpt-5.6-terra")

    if not usable:
        return _unresolved_result(
            assertion,
            citation,
            evidence,
            backend="openai-responses",
            model=model,
        )

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "OpenAI backend requested but the 'openai' package is not installed. Run: pip install -e ."
        ) from exc

    client = OpenAI()
    payload = _build_payload(assertion, citation, usable)

    response = client.responses.parse(
        model=model,
        instructions=SYSTEM_INSTRUCTIONS,
        input=(
            "Evaluate this assertion-citation-evidence unit. Use only the supplied material.\n\n"
            + json.dumps(payload, ensure_ascii=False, indent=2)
        ),
        text_format=SemanticJudgeOutput,
    )

    parsed = response.output_parsed
    if parsed is None:
        raise RuntimeError("The model response could not be parsed into SemanticJudgeOutput.")

    parsed = _apply_system_factors(parsed, usable)
    reliability = reliability_from_factors(parsed.reliability_factors, usable)
    uncertainty = merge_uncertainties(
        parsed.uncertainty,
        policy_uncertainties(parsed.reliability_factors, usable),
    )

    return Judgement(
        id=f"j_{uuid.uuid4().hex[:10]}",
        assertion_id=assertion.id,
        citation_relation_id=citation.id,
        evidence_ids=[ev.id for ev in evidence],
        relevance=parsed.relevance,
        support=parsed.support,
        reliability=reliability,
        reliability_factors=parsed.reliability_factors,
        factor_rationale=parsed.factor_rationale,
        supported_components=parsed.supported_components,
        unsupported_components=parsed.unsupported_components,
        contradicted_components=parsed.contradicted_components,
        uncertainty=uncertainty,
        rationale=parsed.rationale,
        judgement_status="COMPLETE",
        judge_backend="openai-responses",
        judge_model=model,
    )
