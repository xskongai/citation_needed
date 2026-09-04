from __future__ import annotations

import json
import os
import uuid

from citation_needed.models import (
    Assertion,
    CitationRelation,
    Evidence,
    EvidenceRetrievalResult,
    EvidenceRetrievalStatus,
    EvidenceState,
    SourceRole,
    StructuredDocument,
    Provenance,
)

from .candidates import build_evidence_candidates
from .semantic_schema import SemanticEvidenceSelection


SYSTEM_INSTRUCTIONS = """You are the evidence retrieval selector for Citation Needed, a scientific citation-audit system.

Your task is retrieval, NOT support judgement.

1. Use only the supplied candidate passages from the cited source.
2. Select up to 3 candidate IDs that are most directly useful for evaluating the target assertion.
3. Relevant evidence may SUPPORT, CONTRADICT, QUALIFY, LIMIT, or provide METHOD/PARAMETER context for the assertion. Do not prefer supportive passages.
4. Prefer passages that match the target scientific subject/entity, outcome/property, and material conditions.
5. A passage can be relevant even when its value/direction disagrees with the assertion. Contradiction is evidence, not a retrieval failure.
6. Broad topical similarity alone is insufficient. If no candidate bears directly enough on the assertion, select no IDs.
7. For METHOD/PARAMETER citation purposes, prioritize passages that state the actual method, setting, material, quantity, or procedure.
8. For SUPPORT/RESULT/COMPARISON/CONTRADICTION purposes, prioritize directly reported findings/data and relevant experimental context.
9. Never invent, rewrite, merge, or quote evidence outside candidate text. Return candidate IDs only.
10. Never use outside scientific knowledge to fill missing evidence.
11. Keep rationale short and auditable.
"""


def _payload(assertion: Assertion, relation: CitationRelation, candidates) -> dict:
    return {
        "assertion": {
            "text": assertion.text,
            "normalized_claim": assertion.normalized_claim,
            "claim_type": assertion.claim_type.value,
        },
        "citation_relation": {
            "reference_number": relation.reference_number,
            "citation_context": relation.citation_context,
            "purpose": relation.purpose.value,
            "purpose_reason": relation.purpose_reason,
        },
        "candidates": [
            {
                "id": c.id,
                "section_id": c.section_id,
                "content": c.content,
                "location": c.location.model_dump(mode="json"),
                "evidence_type": c.evidence_type.value,
                "lexical_score": c.lexical_score,
                "purpose_boost": c.purpose_boost,
            }
            for c in candidates
        ],
    }


def materialize_evidence_selection(
    assertion: Assertion,
    relation: CitationRelation,
    source_document: StructuredDocument,
    candidates,
    selection: SemanticEvidenceSelection,
    *,
    source_role: SourceRole = SourceRole.UNKNOWN,
    source_doi: str | None = None,
    model: str | None = None,
) -> EvidenceRetrievalResult:
    by_id = {c.id: c for c in candidates}
    warnings: list[str] = []
    selected = []
    seen: set[str] = set()

    for candidate_id in selection.selected_candidate_ids[:3]:
        if candidate_id in seen:
            continue
        seen.add(candidate_id)
        candidate = by_id.get(candidate_id)
        if candidate is None:
            warnings.append(f"Ignored unknown candidate id returned by selector: {candidate_id!r}.")
            continue
        selected.append(candidate)

    evidence: list[Evidence] = []
    for candidate in selected:
        evidence.append(
            Evidence(
                id=f"ev_{uuid.uuid4().hex[:10]}",
                citation_relation_id=relation.id,
                source_paper_id=source_document.paper_id,
                content=candidate.content,
                evidence_type=candidate.evidence_type,
                provenance=Provenance(
                    paper_id=source_document.paper_id,
                    title=source_document.title,
                    doi=source_doi,
                    source_role=source_role,
                    location=candidate.location,
                ),
                epistemic_state=EvidenceState.REPORTED,
                experimental_context={
                    "_retrieval_candidate_id": candidate.id,
                    "_retrieval_lexical_score": candidate.lexical_score,
                    "_retrieval_purpose_boost": candidate.purpose_boost,
                },
            )
        )

    status = (
        EvidenceRetrievalStatus.FOUND
        if evidence
        else EvidenceRetrievalStatus.NO_RELEVANT_EVIDENCE
    )

    return EvidenceRetrievalResult(
        assertion_id=assertion.id,
        citation_relation_id=relation.id,
        source_paper_id=source_document.paper_id,
        status=status,
        candidates=list(candidates),
        evidence=evidence,
        warnings=warnings,
        rationale=selection.rationale,
        retriever_backend="openai-responses",
        retriever_model=model,
    )


def retrieve_evidence_openai(
    assertion: Assertion,
    relation: CitationRelation,
    source_document: StructuredDocument | None,
    *,
    source_role: SourceRole = SourceRole.UNKNOWN,
    source_doi: str | None = None,
    model: str | None = None,
    top_k: int = 12,
) -> EvidenceRetrievalResult:
    model = model or os.getenv("CITATION_NEEDED_MODEL", "gpt-5.6-terra")

    if source_document is None:
        return EvidenceRetrievalResult(
            assertion_id=assertion.id,
            citation_relation_id=relation.id,
            status=EvidenceRetrievalStatus.SOURCE_UNAVAILABLE,
            rationale="The cited source document was not supplied to the retrieval stage.",
            retriever_model=model,
        )

    if relation.cited_paper_id and relation.cited_paper_id != source_document.paper_id:
        return EvidenceRetrievalResult(
            assertion_id=assertion.id,
            citation_relation_id=relation.id,
            source_paper_id=source_document.paper_id,
            status=EvidenceRetrievalStatus.UNRESOLVED,
            warnings=[
                "The supplied cited source paper_id does not match citation_relation.cited_paper_id."
            ],
            rationale="Retrieval was blocked to avoid silently searching the wrong cited source.",
            retriever_model=model,
        )

    candidates = build_evidence_candidates(
        assertion,
        relation,
        source_document,
        top_k=top_k,
    )
    if not candidates:
        return EvidenceRetrievalResult(
            assertion_id=assertion.id,
            citation_relation_id=relation.id,
            source_paper_id=source_document.paper_id,
            status=EvidenceRetrievalStatus.NO_RELEVANT_EVIDENCE,
            candidates=[],
            rationale="The supplied cited source contains no retrievable text passages.",
            retriever_model=model,
        )

    from openai import OpenAI

    response = OpenAI().responses.parse(
        model=model,
        instructions=SYSTEM_INSTRUCTIONS,
        input=(
            "Select the cited-source passages most directly relevant to evaluating this assertion. "
            "Do not judge support; retrieve relevant evidence regardless of polarity.\n\n"
            + json.dumps(_payload(assertion, relation, candidates), ensure_ascii=False, indent=2)
        ),
        text_format=SemanticEvidenceSelection,
    )
    parsed = response.output_parsed
    if parsed is None:
        raise RuntimeError("The model response could not be parsed into SemanticEvidenceSelection.")

    return materialize_evidence_selection(
        assertion,
        relation,
        source_document,
        candidates,
        parsed,
        source_role=source_role,
        source_doi=source_doi,
        model=model,
    )
