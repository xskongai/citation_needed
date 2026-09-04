from citation_needed.models import (
    Assertion,
    CitationPurpose,
    CitationRelation,
    ClaimType,
    DocumentSection,
    EvidenceRetrievalStatus,
    FollowPriority,
    ResolutionStatus,
    SourceLocation,
    SourceRole,
    StructuredDocument,
)
from citation_needed.retrieval import build_evidence_candidates, materialize_evidence_selection, retrieve_evidence_openai
from citation_needed.retrieval.semantic_schema import SemanticEvidenceSelection


def assertion(text="The sample had an average particle diameter of 8 nm.") -> Assertion:
    return Assertion(
        id="a1",
        text=text,
        normalized_claim=text,
        paper_id="paper-a",
        location=SourceLocation(page=1),
        claim_type=ClaimType.PROPERTY,
        citation_ids=["rel1"],
    )


def relation(cited="paper-b") -> CitationRelation:
    return CitationRelation(
        id="rel1",
        assertion_id="a1",
        source_paper_id="paper-a",
        cited_paper_id=cited,
        reference_number="8",
        citation_context="The sample had an average particle diameter of 8 nm [8].",
        purpose=CitationPurpose.SUPPORT,
        follow_priority=FollowPriority.HIGH,
        resolution_status=ResolutionStatus.RESOLVED,
    )


def document(paper_id="paper-b") -> StructuredDocument:
    return StructuredDocument(
        paper_id=paper_id,
        title="Particle study",
        sections=[
            DocumentSection(
                id="methods",
                heading="Methods",
                text="Particle diameter was measured by TEM on the as-prepared sample.",
                location=SourceLocation(page=2, section="Methods"),
            ),
            DocumentSection(
                id="results",
                heading="Results",
                text="TEM analysis showed an average particle diameter of 18 nm for the as-prepared sample.",
                location=SourceLocation(page=5, section="Results"),
            ),
        ],
    )


def test_candidate_generation_keeps_contradictory_value_passage():
    candidates = build_evidence_candidates(assertion(), relation(), document())
    assert any("18 nm" in c.content for c in candidates)


def test_candidates_copy_source_location_without_invented_paragraph():
    candidates = build_evidence_candidates(assertion(), relation(), document())
    result = next(c for c in candidates if "18 nm" in c.content)
    assert result.location.page == 5
    assert result.location.section == "Results"
    assert result.location.paragraph is None


def test_materializer_accepts_candidate_ids_only_and_keeps_exact_text():
    a = assertion()
    r = relation()
    d = document()
    candidates = build_evidence_candidates(a, r, d)
    chosen = next(c for c in candidates if "18 nm" in c.content)
    parsed = SemanticEvidenceSelection(selected_candidate_ids=[chosen.id], rationale="Directly relevant size result.")
    result = materialize_evidence_selection(a, r, d, candidates, parsed, source_role=SourceRole.PRIMARY_STUDY)
    assert result.status == EvidenceRetrievalStatus.FOUND
    assert len(result.evidence) == 1
    assert result.evidence[0].content == chosen.content
    assert result.evidence[0].provenance.source_role == SourceRole.PRIMARY_STUDY


def test_unknown_selector_candidate_is_ignored_not_invented():
    a = assertion()
    r = relation()
    d = document()
    candidates = build_evidence_candidates(a, r, d)
    parsed = SemanticEvidenceSelection(selected_candidate_ids=["cand:invented:99"], rationale="test")
    result = materialize_evidence_selection(a, r, d, candidates, parsed)
    assert result.status == EvidenceRetrievalStatus.NO_RELEVANT_EVIDENCE
    assert result.evidence == []
    assert any("unknown candidate id" in w for w in result.warnings)


def test_source_unavailable_is_explicit_without_api_call():
    result = retrieve_evidence_openai(assertion(), relation(), None)
    assert result.status == EvidenceRetrievalStatus.SOURCE_UNAVAILABLE


def test_wrong_source_document_is_blocked_without_api_call():
    result = retrieve_evidence_openai(assertion(), relation("paper-b"), document("paper-c"))
    assert result.status == EvidenceRetrievalStatus.UNRESOLVED
    assert result.evidence == []
    assert any("does not match" in w for w in result.warnings)


def test_empty_document_is_no_relevant_evidence_without_api_call():
    empty = StructuredDocument(paper_id="paper-b", title="Empty", sections=[])
    result = retrieve_evidence_openai(assertion(), relation(), empty)
    assert result.status == EvidenceRetrievalStatus.NO_RELEVANT_EVIDENCE


def test_method_purpose_gives_small_section_boost_not_hard_filter():
    a = Assertion(
        id="a1",
        text="The synthesis used pH 12.",
        normalized_claim="synthesis pH 12",
        paper_id="paper-a",
        location=SourceLocation(page=1),
        claim_type=ClaimType.METHOD,
        citation_ids=["rel1"],
    )
    r = CitationRelation(
        id="rel1",
        assertion_id="a1",
        source_paper_id="paper-a",
        cited_paper_id="paper-b",
        reference_number="3",
        citation_context="The synthesis used pH 12 [3].",
        purpose=CitationPurpose.METHOD,
        follow_priority=FollowPriority.HIGH,
        resolution_status=ResolutionStatus.RESOLVED,
    )
    d = StructuredDocument(
        paper_id="paper-b",
        sections=[
            DocumentSection(id="m", heading="Experimental methods", text="The pH was adjusted to 12.", location=SourceLocation(page=2)),
            DocumentSection(id="r", heading="Results", text="The pH 12 sample was black.", location=SourceLocation(page=4)),
        ],
    )
    candidates = build_evidence_candidates(a, r, d)
    method = next(c for c in candidates if c.section_id == "m")
    result = next(c for c in candidates if c.section_id == "r")
    assert method.purpose_boost > result.purpose_boost
    assert any(c.section_id == "r" for c in candidates)
