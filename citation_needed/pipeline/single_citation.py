from __future__ import annotations

from pathlib import Path
from typing import Callable

from citation_needed.acquisition.acquirer import acquire_source
from citation_needed.acquisition.http import HttpClient
from citation_needed.extraction.openai_extractor import extract_citation_assertions_openai
from citation_needed.judgement.openai_judge import judge_openai
from citation_needed.models import (
    ArtifactKind,
    Assertion,
    CitationRelation,
    CitationResolution,
    EndToEndAuditStatus,
    EvidenceRetrievalResult,
    ExtractionResult,
    FollowPriority,
    ParseStatus,
    ResolutionStatus,
    SectionType,
    SingleCitationAuditTrace,
    SourceAssessmentInput,
    SourceContextItem,
    SourceContextScope,
    SourceContextType,
    SourceRole,
    StructuredDocument,
)
from citation_needed.parsing.parser import parse_acquired_source, parse_artifact
from citation_needed.reliability.policy import build_audit_result
from citation_needed.resolution.resolver import resolve_citation_relation
from citation_needed.retrieval.openai_retriever import retrieve_evidence_openai
from citation_needed.source_assessment.openai_assessor import assess_source_openai


_PRIORITY = {
    FollowPriority.HIGH: 0,
    FollowPriority.MEDIUM: 1,
    FollowPriority.LOW: 2,
    FollowPriority.STOP: 3,
}

_CONTEXT_TYPE = {
    SectionType.ABSTRACT: SourceContextType.ABSTRACT,
    SectionType.METHODS: SourceContextType.METHOD,
    SectionType.RESULTS: SourceContextType.RESULT,
    SectionType.DISCUSSION: SourceContextType.DISCUSSION,
    SectionType.SUPPLEMENTARY: SourceContextType.SUPPLEMENTARY,
}


def select_citation_relation(
    extraction: ExtractionResult,
    *,
    reference_number: str | None = None,
    relation_id: str | None = None,
) -> tuple[Assertion, CitationRelation, list[str]]:
    """Select exactly one relation for a single-citation audit.

    Explicit selectors win. Without one, the highest follow-priority relation
    is selected deterministically and a warning is emitted when alternatives
    existed.
    """

    warnings: list[str] = []
    relations = list(extraction.citation_relations)
    if relation_id is not None:
        relations = [r for r in relations if r.id == relation_id]
    if reference_number is not None:
        relations = [r for r in relations if r.reference_number == str(reference_number)]

    if not relations:
        selector = relation_id or reference_number or "automatic selection"
        raise ValueError(f"No citation relation matched {selector!r}.")

    if relation_id is None and reference_number is None:
        relations = sorted(relations, key=lambda r: (_PRIORITY[r.follow_priority], r.reference_number, r.id))
        if len(relations) > 1:
            warnings.append(
                "Multiple citation relations were extracted; the highest follow-priority relation was selected automatically."
            )
    elif len(relations) > 1:
        raise ValueError("The supplied selector matched multiple citation relations; use relation_id to disambiguate.")

    relation = relations[0]
    assertion = next((a for a in extraction.assertions if a.id == relation.assertion_id), None)
    if assertion is None:
        raise ValueError("Selected citation relation has no matching assertion in the extraction result.")
    return assertion, relation, warnings


def _section_matches_evidence(section, evidence_locations) -> bool:
    for loc in evidence_locations:
        if loc.section and section.location.section and loc.section.strip().lower() == section.location.section.strip().lower():
            return True
        if loc.page and section.location.page and loc.page == section.location.page:
            if not loc.section or not section.location.section:
                return True
    return False


def build_source_assessment_input(
    source_document: StructuredDocument | None,
    retrieval: EvidenceRetrievalResult,
    *,
    source_role: SourceRole,
    requested_scope: SourceContextScope = SourceContextScope.RELEVANT_SECTIONS,
    fallback_paper_id: str,
) -> SourceAssessmentInput:
    """Build source-assessment context without pretending partial text is full text."""

    if source_document is None:
        return SourceAssessmentInput(
            source_paper_id=fallback_paper_id,
            source_role=source_role,
            context_scope=SourceContextScope.EXCERPT_ONLY,
            evidence_ids=[ev.id for ev in retrieval.evidence],
            context_items=[],
        )

    evidence_locations = [ev.provenance.location for ev in retrieval.evidence]
    non_refs = [s for s in source_document.sections if s.section_type != SectionType.REFERENCES]

    if requested_scope == SourceContextScope.FULL_SOURCE:
        selected = non_refs
        scope = SourceContextScope.FULL_SOURCE
    elif requested_scope == SourceContextScope.EXCERPT_ONLY:
        evidence_sections = [s for s in non_refs if _section_matches_evidence(s, evidence_locations)]
        selected = evidence_sections[:1] or non_refs[:1]
        scope = SourceContextScope.EXCERPT_ONLY
    else:
        evidence_sections = [s for s in non_refs if _section_matches_evidence(s, evidence_locations)]
        supporting = [
            s
            for s in non_refs
            if s.section_type in {SectionType.METHODS, SectionType.RESULTS, SectionType.DISCUSSION}
        ]
        selected = []
        seen: set[str] = set()
        for section in evidence_sections + supporting:
            if section.id not in seen:
                seen.add(section.id)
                selected.append(section)
        if not selected:
            selected = non_refs[:3]
        scope = SourceContextScope.RELEVANT_SECTIONS if selected else SourceContextScope.EXCERPT_ONLY

    items = [
        SourceContextItem(
            content=section.text,
            context_type=_CONTEXT_TYPE.get(section.section_type, SourceContextType.OTHER),
            location=section.location,
        )
        for section in selected
    ]

    return SourceAssessmentInput(
        source_paper_id=source_document.paper_id,
        source_title=source_document.title,
        source_role=source_role,
        context_scope=scope,
        evidence_ids=[ev.id for ev in retrieval.evidence],
        context_items=items,
    )


def audit_single_citation_from_document(
    source_document: StructuredDocument,
    *,
    reference_number: str | None = None,
    relation_id: str | None = None,
    source_role: SourceRole = SourceRole.UNKNOWN,
    context_scope: SourceContextScope = SourceContextScope.RELEVANT_SECTIONS,
    model: str | None = None,
    contact_email: str | None = None,
    acquisition_output_dir: str | Path = "data/acquired",
    http_client: HttpClient | None = None,
    top_k: int = 12,
    extractor: Callable[..., ExtractionResult] = extract_citation_assertions_openai,
    resolver: Callable[..., CitationResolution] = resolve_citation_relation,
    acquirer=acquire_source,
    parser=parse_acquired_source,
    retriever=retrieve_evidence_openai,
    judge=judge_openai,
    assessor=assess_source_openai,
) -> SingleCitationAuditTrace:
    """Run one traceable Paper-A -> cited-source -> evidence -> judgement audit."""

    warnings: list[str] = []
    extraction = extractor(source_document, model=model)
    warnings.extend(extraction.warnings)
    assertion, relation, selection_warnings = select_citation_relation(
        extraction,
        reference_number=reference_number,
        relation_id=relation_id,
    )
    warnings.extend(selection_warnings)

    resolution = resolver(relation, source_document.references)
    warnings.extend(resolution.warnings)

    resolved_relation = relation.model_copy(
        update={
            "cited_paper_id": resolution.cited_paper_id,
            "resolution_status": resolution.status,
        }
    )

    acquisition = acquirer(
        resolution,
        output_dir=acquisition_output_dir,
        contact_email=contact_email,
        client=http_client,
    )
    warnings.extend(acquisition.warnings)

    parse_result = parser(acquisition)
    warnings.extend(parse_result.warnings)
    cited_document = parse_result.document

    doi = acquisition.metadata.doi
    if not doi and resolution.reference_entry is not None:
        doi = resolution.reference_entry.doi

    retrieval = retriever(
        assertion,
        resolved_relation,
        cited_document,
        source_role=source_role,
        source_doi=doi,
        model=model,
        top_k=top_k,
    )
    warnings.extend(retrieval.warnings)

    relation_judgement = judge(
        assertion,
        resolved_relation,
        retrieval.evidence,
        model=model,
    )

    effective_scope = context_scope
    if parse_result.status == ParseStatus.ABSTRACT_ONLY_PARSED:
        effective_scope = SourceContextScope.EXCERPT_ONLY
    source_input = build_source_assessment_input(
        cited_document,
        retrieval,
        source_role=source_role,
        requested_scope=effective_scope,
        fallback_paper_id=resolution.cited_paper_id or f"unresolved:{resolved_relation.reference_number}",
    )
    source_assessment = assessor(source_input, retrieval.evidence, model=model)
    audit_result = build_audit_result(relation_judgement, source_assessment, retrieval.evidence)

    status = (
        EndToEndAuditStatus.UNRESOLVED
        if audit_result.audit_status == "UNRESOLVED"
        else EndToEndAuditStatus.COMPLETE
    )

    return SingleCitationAuditTrace(
        source_paper_id=source_document.paper_id,
        extraction=extraction,
        assertion=assertion,
        citation_relation=resolved_relation,
        resolution=resolution,
        acquisition=acquisition,
        parse_result=parse_result,
        retrieval=retrieval,
        relation_judgement=relation_judgement,
        source_assessment=source_assessment,
        audit_result=audit_result,
        status=status,
        warnings=list(dict.fromkeys(warnings)),
    )


def audit_single_citation_from_artifact(
    paper_a_path: str | Path,
    *,
    paper_a_kind: ArtifactKind,
    paper_a_id: str,
    paper_a_title: str | None = None,
    **kwargs,
) -> SingleCitationAuditTrace:
    source_document = parse_artifact(
        paper_a_path,
        kind=paper_a_kind,
        paper_id=paper_a_id,
        title=paper_a_title,
    )
    return audit_single_citation_from_document(source_document, **kwargs)
