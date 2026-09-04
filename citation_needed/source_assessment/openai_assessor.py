from __future__ import annotations

import json
import os
import uuid
from typing import Any

from citation_needed.models import (
    Evidence,
    SourceAssessment,
    SourceAssessmentInput,
    SourceAssessmentRationale,
    SourceOriginality,
)
from .policy import apply_scope_guards, derive_source_originality
from .semantic_schema import SemanticSourceAssessmentOutput


SYSTEM_INSTRUCTIONS = """You are the source-level evidence assessor for Citation Needed, a scientific citation-audit system.

Do NOT decide whether a claim is true or whether evidence supports a claim. Assess the quality, basis, and traceability of the supplied evidence-bearing SOURCE for the target evidence items.

1. Use only supplied evidence and source context. Do not use outside knowledge.
2. Unknown is not negative evidence. Missing context must not become a poor-source judgement.
3. Respect context_scope: EXCERPT_ONLY, RELEVANT_SECTIONS, FULL_SOURCE.
4. source_originality is system-owned provenance and will be derived in code.
5. evidence_basis categories:
   - DIRECT_MEASUREMENT: the supplied source directly reports an observed measurement/reading/value and the measurement basis is explicit.
   - DERIVED_RESULT: the target result is explicitly calculated, transformed, or derived from measurements/data (for example via an equation).
   - REPORTED_RESULT: the source explicitly reports a result/comparison/finding, but the supplied material does not make it a direct raw measurement or explicit derivation.
   - AUTHOR_INTERPRETATION: causal/mechanistic/explanatory interpretation or inference by the authors rather than the measured/reported result itself.
   - SECONDARY_REPORT: the source reports a result attributed to another study/source.
   - UNKNOWN: the basis cannot be established from supplied material.
6. method_completeness: assess only critical method details needed to interpret or reproduce the target evidence. Use UNKNOWN when supplied scope cannot establish it.
7. measurement_traceability has four parts:
   - method_status: IDENTIFIED only when a measurement/characterisation method is actually named or clearly specified in supplied material; NOT_IDENTIFIED only when the supplied scope is sufficient to establish that it is not identified; otherwise UNKNOWN.
   - identified_methods: list only methods actually supplied; never invent methods.
   - target_link: EXPLICIT when source text directly links a method/measurement/calculation to the target result; INFERRED when linkage is suggested by supplied context but not explicit; UNKNOWN otherwise.
   - appropriateness: APPROPRIATE/PARTIAL/INAPPROPRIATE only when the supplied source gives enough basis to assess fit between the identified method and target result. If method or target link is missing, use UNKNOWN. Do not use outside domain knowledge.
8. reporting_completeness: assess critical values, conditions, units, uncertainty/context and traceable reporting only when supplied scope permits it.
9. internal_consistency: CONFLICTED only when supplied source locations materially disagree about the same target quantity/finding under comparable context. CONSISTENT only when FULL_SOURCE is supplied. Otherwise UNKNOWN.
10. Do not assess cross-paper reproducibility.
11. supporting_locations must be locations actually supplied. Never invent page/figure/table locations.
12. Keep rationales concise and auditable.
"""


def _build_payload(source_input: SourceAssessmentInput, evidence: list[Evidence]) -> dict[str, Any]:
    return {
        "source": {
            "paper_id": source_input.source_paper_id,
            "title": source_input.source_title,
            "context_scope": source_input.context_scope.value,
        },
        "target_evidence": [
            {
                "id": ev.id,
                "content": ev.content,
                "evidence_type": ev.evidence_type.value,
                "epistemic_state": ev.epistemic_state.value,
                "provenance": ev.provenance.model_dump(mode="json"),
                "experimental_context": {
                    k: v
                    for k, v in ev.experimental_context.items()
                    if not str(k).startswith("_")
                },
            }
            for ev in evidence
        ],
        "source_context": [item.model_dump(mode="json") for item in source_input.context_items],
    }


def assess_source_openai(
    source_input: SourceAssessmentInput,
    evidence: list[Evidence],
    *,
    model: str | None = None,
) -> SourceAssessment:
    model = model or os.getenv("CITATION_NEEDED_MODEL", "gpt-5.6-terra")
    originality = derive_source_originality(source_input.source_role)

    if not evidence:
        return SourceAssessment(
            id=f"sa_{uuid.uuid4().hex[:10]}",
            source_paper_id=source_input.source_paper_id,
            evidence_ids=[],
            context_scope=source_input.context_scope,
            source_originality=originality,
            factor_rationale=SourceAssessmentRationale(
                evidence_basis="No target evidence was supplied.",
                method_completeness="Not assessed without target evidence.",
                reporting_completeness="Not assessed without target evidence.",
                source_originality="Derived from provenance metadata.",
                internal_consistency="Not assessed without target evidence.",
            ),
            rationale="Source assessment is unresolved because no target evidence was supplied.",
            assessment_status="UNRESOLVED",
            assessor_model=model,
        )

    from openai import OpenAI

    response = OpenAI().responses.parse(
        model=model,
        instructions=SYSTEM_INSTRUCTIONS,
        input=(
            "Assess this evidence-bearing scientific source. Use only the supplied material.\n\n"
            + json.dumps(_build_payload(source_input, evidence), ensure_ascii=False, indent=2)
        ),
        text_format=SemanticSourceAssessmentOutput,
    )
    parsed = response.output_parsed
    if parsed is None:
        raise RuntimeError("The model response could not be parsed into SemanticSourceAssessmentOutput.")

    parsed = apply_scope_guards(parsed, source_input)

    if originality == SourceOriginality.PRIMARY:
        parsed.factor_rationale.source_originality = (
            "Provenance metadata marks the evidence-bearing source as a primary study."
        )
    elif originality == SourceOriginality.SECONDARY:
        parsed.factor_rationale.source_originality = (
            "Provenance metadata marks the evidence-bearing source as secondary."
        )
    else:
        parsed.factor_rationale.source_originality = (
            "Provenance metadata does not establish primary-vs-secondary source status."
        )

    return SourceAssessment(
        id=f"sa_{uuid.uuid4().hex[:10]}",
        source_paper_id=source_input.source_paper_id,
        evidence_ids=[ev.id for ev in evidence],
        context_scope=source_input.context_scope,
        evidence_basis=parsed.evidence_basis,
        method_completeness=parsed.method_completeness,
        measurement_traceability=parsed.measurement_traceability,
        reporting_completeness=parsed.reporting_completeness,
        source_originality=originality,
        internal_consistency=parsed.internal_consistency,
        missing_information=parsed.missing_information,
        supporting_locations=parsed.supporting_locations,
        factor_rationale=parsed.factor_rationale,
        rationale=parsed.rationale,
        assessor_backend="openai-responses",
        assessor_model=model,
    )
