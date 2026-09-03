from __future__ import annotations

import json
import os
import uuid
from typing import Any

from citation_needed.models import (
    AlignmentAssessment,
    Assertion,
    CitationRelation,
    ContextMatch,
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
from .policy import (
    merge_uncertainties,
    overall_context_match,
    policy_uncertainties,
    reliability_from_factors,
)
from .semantic_schema import SemanticJudgeOutput


SYSTEM_INSTRUCTIONS = """You are the relation-level semantic judgement component of Citation Needed, a scientific citation-audit system.

Your task is narrow: evaluate the relation between ONE assertion and the supplied evidence. Do not answer whether the claim is true in the world. Judge only what the supplied material establishes.

A. CLAIM DECOMPOSITION
1. Decompose the normalized claim into the smallest decision-relevant propositions needed to explain support. Do not invent new claims.
2. Put each proposition in claim_components with a status and concise rationale.
3. Use SUPPORTED when the supplied evidence establishes that proposition; CONTRADICTED when it materially opposes it; INSUFFICIENT_EVIDENCE when it does not establish it. PARTIALLY_SUPPORTED should be rare at component level and used only if the component cannot be made meaningfully smaller.
4. Overall SUPPORTED requires all material claim components to be supported.
5. Overall PARTIALLY_SUPPORTED means at least one material component is supported while another material component is unsupported/insufficient (or mixed evidence prevents full support).
6. Overall CONTRADICTED requires evidence that materially opposes the central claim. Mere absence, omission, or a condition mismatch is not by itself contradiction.
7. Overall INSUFFICIENT_EVIDENCE means the supplied evidence does not establish any meaningful part strongly enough to support the claim.

B. RELATION AND ALIGNMENT
8. Separate RELEVANCE from SUPPORT. Evidence can be relevant but fail to support the claim.
9. Compare claim strength with evidence strength. Check scope, quantifiers, causality, numerical values, direction of effect, population/material, method, conditions, and context.
10. Assess alignment as three separate dimensions:
   - subject_match: same material/system/population/intervention/entity?
   - outcome_match: same property/result/measurement or target outcome?
   - condition_match: do material experimental/contextual conditions required by the claim match the evidence?
11. For condition_match, record concrete differences in condition_mismatches, e.g. 'claim: room temperature; evidence: 145 C'.
12. Do not collapse a condition-only mismatch into total irrelevance. If subject and outcome align but conditions differ, condition_match should be MISMATCH while relevance may still be RELEVANT.

C. RELIABILITY FACTORS
13. Assess factors only from information actually supplied. Never infer that a paper itself has poor/incomplete methods merely because the evidence package contains only an excerpt.
14. method_completeness concerns the source paper's method reporting. If the supplied material does not let you assess that source-level property, use UNKNOWN.
15. characterization_quality concerns whether the source's measurement/characterization is appropriate for the claim. If the needed method/data is not supplied, use UNKNOWN. Use NA only when characterization is not relevant.
16. source_originality will be overridden from provenance metadata. If provenance does not establish it, use UNCLEAR rather than guessing.
17. reproducibility_evidence is PRESENT only when independent replication/reproduction evidence is supplied. Use ABSENT only when supplied material explicitly establishes absence. Otherwise use UNKNOWN.
18. context_match inside reliability_factors is a backward-compatible aggregate and will be overridden by code from the alignment dimensions. You may set it to UNKNOWN.
19. Treat REPORTED evidence as source-reported text/data. Treat INFERRED evidence cautiously and explicitly note it.
20. Keep rationales concise, auditable, and decision-relevant.
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
    factors = parsed.reliability_factors

    # Provenance fact, not a semantic guess.
    factors.source_originality = _derive_source_originality(evidence)
    if factors.source_originality == SourceOriginality.PRIMARY:
        parsed.factor_rationale.source_originality = (
            "Provenance metadata marks the supplied evidence source as a primary study."
        )
    elif factors.source_originality == SourceOriginality.SECONDARY:
        parsed.factor_rationale.source_originality = (
            "Provenance metadata marks the supplied evidence source as secondary."
        )
    else:
        parsed.factor_rationale.source_originality = (
            "Provenance metadata does not establish primary-vs-secondary source status."
        )

    # Coarse reliability context is derived from the richer alignment model.
    factors.context_match = overall_context_match(parsed.alignment)
    parsed.factor_rationale.context_match = (
        "Derived from subject/outcome/condition alignment: "
        f"subject={parsed.alignment.subject_match.value}, "
        f"outcome={parsed.alignment.outcome_match.value}, "
        f"condition={parsed.alignment.condition_match.value}."
    )
    return parsed


def _project_component_lists(parsed: SemanticJudgeOutput) -> tuple[list[str], list[str], list[str]]:
    supported: list[str] = []
    unsupported: list[str] = []
    contradicted: list[str] = []
    for item in parsed.claim_components:
        if item.status == SupportJudgement.SUPPORTED:
            supported.append(item.component)
        elif item.status == SupportJudgement.CONTRADICTED:
            contradicted.append(item.component)
        else:
            unsupported.append(item.component)
    return supported, unsupported, contradicted


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
        alignment=AlignmentAssessment(),
        claim_components=[],
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
        policy_uncertainties(parsed.reliability_factors, usable, parsed.alignment),
    )
    supported, unsupported, contradicted = _project_component_lists(parsed)

    return Judgement(
        id=f"j_{uuid.uuid4().hex[:10]}",
        assertion_id=assertion.id,
        citation_relation_id=citation.id,
        evidence_ids=[ev.id for ev in evidence],
        relevance=parsed.relevance,
        support=parsed.support,
        reliability=reliability,
        alignment=parsed.alignment,
        claim_components=parsed.claim_components,
        reliability_factors=parsed.reliability_factors,
        factor_rationale=parsed.factor_rationale,
        supported_components=supported,
        unsupported_components=unsupported,
        contradicted_components=contradicted,
        uncertainty=uncertainty,
        rationale=parsed.rationale,
        judgement_status="COMPLETE",
        judge_backend="openai-responses",
        judge_model=model,
    )
