from __future__ import annotations

import json
import os
import re
import uuid
from typing import Any

from citation_needed.models import (
    Assertion,
    CitationRelation,
    ExtractionResult,
    ResolutionStatus,
    StructuredDocument,
)

from .markers import extract_numeric_reference_numbers
from .policy import follow_priority_for_purpose
from .semantic_schema import SemanticExtractionOutput


SYSTEM_INSTRUCTIONS = """You extract citation-bearing scientific assertions from structured scientific text.

Rules:
1. Use ONLY the supplied document sections. Do not add scientific facts from outside knowledge.
2. Extract only assertions that are explicitly attached to numeric bracket citations such as [14], [1,2,3], or [10-12].
3. source_text must be copied from one supplied section and must contain the relevant citation marker(s). Do not paraphrase source_text.
4. normalized_claim should express the smallest decision-relevant scientific proposition supported/qualified by the citation, without citation markers.
5. Do not treat bibliography entries, figure numbers, equation numbers, or uncited statements as citation-bearing assertions.
6. Bind only reference numbers visibly present in source_text. Never invent a reference number.
7. Classify claim_type independently from citation purpose.
8. Citation purpose describes WHY the cited source is used here: METHOD, PARAMETER, RESULT, SUPPORT, BACKGROUND, THEORY, COMPARISON, CONTRADICTION, OTHER.
9. When one sentence contains multiple distinct cited propositions, split only when doing so preserves the exact citation-to-proposition relation. Do not over-split a single proposition.
10. If a citation is merely broad background, label BACKGROUND rather than SUPPORT.
11. Do not resolve cited papers or assess whether the citation is correct. This stage only extracts the relation asserted by the citing paper.
12. Keep reasons short and auditable.
"""


def _norm_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _section_map(document: StructuredDocument) -> dict[str, Any]:
    return {section.id: section for section in document.sections}


def _reference_map(document: StructuredDocument) -> dict[str, Any]:
    return {entry.reference_number.strip(): entry for entry in document.references}


def _payload(document: StructuredDocument) -> dict[str, Any]:
    return {
        "paper_id": document.paper_id,
        "title": document.title,
        "sections": [
            {
                "id": s.id,
                "heading": s.heading,
                "text": s.text,
                "location": s.location.model_dump(mode="json"),
            }
            for s in document.sections
        ],
        "references": [
            {
                "reference_number": r.reference_number,
                "raw_text": r.raw_text,
            }
            for r in document.references
        ],
    }


def materialize_extraction(
    document: StructuredDocument,
    parsed: SemanticExtractionOutput,
    *,
    model: str | None = None,
) -> ExtractionResult:
    sections = _section_map(document)
    refs = _reference_map(document)
    assertions: list[Assertion] = []
    relations: list[CitationRelation] = []
    warnings: list[str] = []

    seen_assertions: set[tuple[str, str]] = set()
    seen_relations: set[tuple[str, str]] = set()

    for candidate in parsed.assertions:
        section = sections.get(candidate.section_id)
        if section is None:
            warnings.append(f"Skipped assertion with unknown section_id={candidate.section_id!r}.")
            continue

        source_text = _norm_ws(candidate.source_text)
        section_text = _norm_ws(section.text)
        if source_text not in section_text:
            warnings.append(
                f"Skipped non-verbatim assertion in section {candidate.section_id!r}: source_text is not present in supplied text."
            )
            continue

        visible_refs = set(extract_numeric_reference_numbers(source_text))
        if not visible_refs:
            warnings.append(
                f"Skipped assertion in section {candidate.section_id!r}: no numeric bracket citation is visible in source_text."
            )
            continue

        valid_bindings = [c for c in candidate.citations if c.reference_number.strip() in visible_refs]
        invalid = [c.reference_number for c in candidate.citations if c.reference_number.strip() not in visible_refs]
        if invalid:
            warnings.append(
                f"Ignored citation bindings not visible in source_text: {', '.join(invalid)}."
            )
        if not valid_bindings:
            warnings.append(
                f"Skipped assertion in section {candidate.section_id!r}: no model citation binding matched the visible citation markers."
            )
            continue

        assertion_key = (candidate.section_id, _norm_ws(candidate.normalized_claim).lower())
        if assertion_key in seen_assertions:
            warnings.append(f"Skipped duplicate normalized assertion in section {candidate.section_id!r}.")
            continue
        seen_assertions.add(assertion_key)

        assertion_id = f"a_{uuid.uuid4().hex[:10]}"
        citation_ids: list[str] = []

        for binding in valid_bindings:
            ref_no = binding.reference_number.strip()
            rel_key = (assertion_id, ref_no)
            if rel_key in seen_relations:
                continue
            seen_relations.add(rel_key)
            relation_id = f"cr_{uuid.uuid4().hex[:10]}"
            citation_ids.append(relation_id)

            reference_known = not refs or ref_no in refs
            if not reference_known:
                warnings.append(
                    f"Reference [{ref_no}] is visible in text but missing from the supplied bibliography; kept as UNRESOLVED."
                )

            relations.append(
                CitationRelation(
                    id=relation_id,
                    assertion_id=assertion_id,
                    source_paper_id=document.paper_id,
                    cited_paper_id=None,
                    reference_number=ref_no,
                    citation_context=source_text,
                    purpose=binding.purpose,
                    purpose_reason=binding.purpose_reason,
                    follow_priority=follow_priority_for_purpose(binding.purpose),
                    resolution_status=ResolutionStatus.UNRESOLVED,
                )
            )

        assertions.append(
            Assertion(
                id=assertion_id,
                text=source_text,
                normalized_claim=_norm_ws(candidate.normalized_claim),
                paper_id=document.paper_id,
                location=section.location,
                claim_type=candidate.claim_type,
                citation_ids=citation_ids,
            )
        )

    return ExtractionResult(
        paper_id=document.paper_id,
        assertions=assertions,
        citation_relations=relations,
        warnings=warnings,
        extractor_backend="openai-responses",
        extractor_model=model,
    )


def extract_citation_assertions_openai(
    document: StructuredDocument,
    *,
    model: str | None = None,
) -> ExtractionResult:
    model = model or os.getenv("CITATION_NEEDED_MODEL", "gpt-5.6-terra")

    from openai import OpenAI

    response = OpenAI().responses.parse(
        model=model,
        instructions=SYSTEM_INSTRUCTIONS,
        input=(
            "Extract citation-bearing scientific assertions from this structured document.\n\n"
            + json.dumps(_payload(document), ensure_ascii=False, indent=2)
        ),
        text_format=SemanticExtractionOutput,
    )
    parsed = response.output_parsed
    if parsed is None:
        raise RuntimeError("The model response could not be parsed into SemanticExtractionOutput.")
    return materialize_extraction(document, parsed, model=model)
