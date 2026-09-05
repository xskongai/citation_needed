from citation_needed.models import (
    Assertion,
    CitationPurpose,
    CitationRelation,
    DocumentSection,
    Evidence,
    EvidenceRetrievalResult,
    EvidenceRetrievalStatus,
    EvidenceState,
    EvidenceType,
    ExtractionResult,
    FollowPriority,
    Provenance,
    ResolutionStatus,
    SectionType,
    SourceLocation,
    SourceRole,
    StructuredDocument,
)
from citation_needed.pipeline import build_source_assessment_input, select_citation_relation


def _extraction():
    a1 = Assertion(
        id="a1", text="Background [1]", normalized_claim="background",
        paper_id="A", location=SourceLocation(section="Intro"), citation_ids=["r1"]
    )
    a2 = Assertion(
        id="a2", text="Method adapted [2]", normalized_claim="method adapted",
        paper_id="A", location=SourceLocation(section="Methods"), citation_ids=["r2"]
    )
    r1 = CitationRelation(
        id="r1", assertion_id="a1", source_paper_id="A", reference_number="1",
        citation_context="Background [1]", purpose=CitationPurpose.BACKGROUND,
        follow_priority=FollowPriority.LOW, resolution_status=ResolutionStatus.UNRESOLVED,
    )
    r2 = CitationRelation(
        id="r2", assertion_id="a2", source_paper_id="A", reference_number="2",
        citation_context="Method adapted [2]", purpose=CitationPurpose.METHOD,
        follow_priority=FollowPriority.HIGH, resolution_status=ResolutionStatus.UNRESOLVED,
    )
    return ExtractionResult(paper_id="A", assertions=[a1, a2], citation_relations=[r1, r2])


def test_selects_highest_priority_without_selector():
    assertion, relation, warnings = select_citation_relation(_extraction())
    assert assertion.id == "a2"
    assert relation.id == "r2"
    assert warnings


def test_selects_explicit_reference_number():
    assertion, relation, warnings = select_citation_relation(_extraction(), reference_number="1")
    assert assertion.id == "a1"
    assert relation.id == "r1"
    assert warnings == []


def test_relevant_source_context_includes_evidence_and_methods_results():
    doc = StructuredDocument(
        paper_id="B",
        sections=[
            DocumentSection(id="m", heading="Methods", text="Measured with GCD.", section_type=SectionType.METHODS, location=SourceLocation(page=1, section="Methods")),
            DocumentSection(id="r", heading="Results", text="Capacitance was 623 F/g.", section_type=SectionType.RESULTS, location=SourceLocation(page=2, section="Results")),
            DocumentSection(id="x", heading="References", text="[1] X", section_type=SectionType.REFERENCES, location=SourceLocation(page=3, section="References")),
        ],
    )
    ev = Evidence(
        id="e1", citation_relation_id="r", source_paper_id="B",
        content="Capacitance was 623 F/g.", evidence_type=EvidenceType.RESULT,
        provenance=Provenance(paper_id="B", source_role=SourceRole.PRIMARY_STUDY, location=SourceLocation(page=2, section="Results")),
        epistemic_state=EvidenceState.REPORTED,
    )
    retrieval = EvidenceRetrievalResult(
        assertion_id="a", citation_relation_id="r", source_paper_id="B",
        status=EvidenceRetrievalStatus.FOUND, evidence=[ev]
    )
    source_input = build_source_assessment_input(
        doc, retrieval, source_role=SourceRole.PRIMARY_STUDY, fallback_paper_id="B"
    )
    assert {i.location.section for i in source_input.context_items} == {"Methods", "Results"}
    assert source_input.context_scope.value == "RELEVANT_SECTIONS"


def test_missing_source_context_is_excerpt_only():
    retrieval = EvidenceRetrievalResult(
        assertion_id="a", citation_relation_id="r",
        status=EvidenceRetrievalStatus.SOURCE_UNAVAILABLE,
    )
    source_input = build_source_assessment_input(
        None, retrieval, source_role=SourceRole.UNKNOWN, fallback_paper_id="unknown:B"
    )
    assert source_input.context_scope.value == "EXCERPT_ONLY"
    assert source_input.context_items == []


def test_orchestrator_wires_all_stages_without_network_or_llm(tmp_path):
    from citation_needed.models import (
        AcquisitionStatus, AcquiredSource, AcquiredMetadata, AlignmentAssessment,
        Completeness, ContextMatch, IdentityBasis, InternalConsistency, Judgement,
        MeasurementTraceability, ParseStatus, ReferenceEntry, ReliabilityFactorRationale,
        ReliabilityFactors, ReliabilityJudgement, RelevanceJudgement, SourceAssessment,
        SourceAssessmentRationale, SourceContextScope, SourceEvidenceBasis, SourceOriginality,
        SourceParseResult, SupportJudgement, CitationResolution,
    )
    from citation_needed.pipeline import audit_single_citation_from_document

    source_a = StructuredDocument(
        paper_id="A",
        sections=[DocumentSection(id="s1", heading="Intro", text="Claim [1]", location=SourceLocation(section="Intro"))],
        references=[ReferenceEntry(reference_number="1", raw_text="Ref", title="Cited", year=2025, doi="10.1/x")],
    )
    extraction = ExtractionResult(
        paper_id="A",
        assertions=[Assertion(id="a", text="Claim [1]", normalized_claim="claim", paper_id="A", location=SourceLocation(section="Intro"), citation_ids=["r"])],
        citation_relations=[CitationRelation(id="r", assertion_id="a", source_paper_id="A", reference_number="1", citation_context="Claim [1]", purpose=CitationPurpose.SUPPORT, follow_priority=FollowPriority.HIGH)],
    )
    cited = StructuredDocument(
        paper_id="doi:10.1/x",
        sections=[DocumentSection(id="res", heading="Results", text="Claim was observed.", section_type=SectionType.RESULTS, location=SourceLocation(section="Results"))],
    )
    evidence = Evidence(
        id="e", citation_relation_id="r", source_paper_id="doi:10.1/x", content="Claim was observed.", evidence_type=EvidenceType.RESULT,
        provenance=Provenance(paper_id="doi:10.1/x", source_role=SourceRole.PRIMARY_STUDY, location=SourceLocation(section="Results")),
    )

    def extractor(doc, model=None): return extraction
    def resolver(rel, refs):
        return CitationResolution(relation_id="r", source_paper_id="A", reference_number="1", status=ResolutionStatus.RESOLVED, reference_entry=source_a.references[0], cited_paper_id="doi:10.1/x", identity_basis=IdentityBasis.DOI)
    def acquirer(res, **kwargs):
        return AcquiredSource(relation_id="r", cited_paper_id="doi:10.1/x", status=AcquisitionStatus.FULL_TEXT_AVAILABLE, metadata=AcquiredMetadata(doi="10.1/x"))
    def parser(acq):
        return SourceParseResult(relation_id="r", cited_paper_id="doi:10.1/x", status=ParseStatus.FULL_TEXT_PARSED, document=cited)
    def retriever(assertion, relation, document, **kwargs):
        return EvidenceRetrievalResult(assertion_id="a", citation_relation_id="r", source_paper_id=document.paper_id, status=EvidenceRetrievalStatus.FOUND, evidence=[evidence])
    def judge(assertion, relation, evs, **kwargs):
        return Judgement(
            id="j", assertion_id="a", citation_relation_id="r", evidence_ids=["e"],
            relevance=RelevanceJudgement.RELEVANT, support=SupportJudgement.SUPPORTED,
            reliability=ReliabilityJudgement.MODERATE,
            alignment=AlignmentAssessment(subject_match=ContextMatch.MATCH, outcome_match=ContextMatch.MATCH, condition_match=ContextMatch.UNKNOWN),
            reliability_factors=ReliabilityFactors(source_originality=SourceOriginality.PRIMARY),
            factor_rationale=ReliabilityFactorRationale(
                evidence_directness="x", source_originality="x", method_completeness="x",
                characterization_quality="x", context_match="x", reproducibility_evidence="x", reporting_clarity="x"
            ), rationale="supported",
        )
    def assessor(source_input, evs, **kwargs):
        return SourceAssessment(
            id="sa", source_paper_id="doi:10.1/x", evidence_ids=["e"], context_scope=SourceContextScope.RELEVANT_SECTIONS,
            evidence_basis=SourceEvidenceBasis.REPORTED_RESULT, method_completeness=Completeness.PARTIAL,
            measurement_traceability=MeasurementTraceability(), reporting_completeness=Completeness.PARTIAL,
            source_originality=SourceOriginality.PRIMARY, internal_consistency=InternalConsistency.UNKNOWN,
            factor_rationale=SourceAssessmentRationale(
                evidence_basis="reported", method_completeness="partial", reporting_completeness="partial",
                source_originality="primary", internal_consistency="unknown"
            ), rationale="assessed",
        )

    result = audit_single_citation_from_document(
        source_a, reference_number="1", source_role=SourceRole.PRIMARY_STUDY,
        acquisition_output_dir=tmp_path, extractor=extractor, resolver=resolver, acquirer=acquirer,
        parser=parser, retriever=retriever, judge=judge, assessor=assessor,
    )
    assert result.status.value == "COMPLETE"
    assert result.retrieval.evidence[0].id == "e"
    assert result.audit_result.reliability.level.value == "MODERATE"


def test_requested_excerpt_scope_stays_excerpt_only():
    from citation_needed.models import SourceContextScope
    doc = StructuredDocument(
        paper_id="B",
        sections=[DocumentSection(id="abs", heading="Abstract", text="A result is reported.", section_type=SectionType.ABSTRACT, location=SourceLocation(section="Abstract"))],
    )
    retrieval = EvidenceRetrievalResult(
        assertion_id="a", citation_relation_id="r", source_paper_id="B",
        status=EvidenceRetrievalStatus.NO_RELEVANT_EVIDENCE,
    )
    source_input = build_source_assessment_input(
        doc, retrieval, source_role=SourceRole.UNKNOWN,
        requested_scope=SourceContextScope.EXCERPT_ONLY, fallback_paper_id="B"
    )
    assert source_input.context_scope == SourceContextScope.EXCERPT_ONLY
    assert len(source_input.context_items) == 1
