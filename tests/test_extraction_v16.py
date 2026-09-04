from citation_needed.extraction import (
    extract_numeric_reference_numbers,
    follow_priority_for_purpose,
    materialize_extraction,
)
from citation_needed.extraction.semantic_schema import (
    SemanticAssertionCandidate,
    SemanticCitationBinding,
    SemanticExtractionOutput,
)
from citation_needed.models import (
    CitationPurpose,
    ClaimType,
    DocumentSection,
    FollowPriority,
    ReferenceEntry,
    SourceLocation,
    StructuredDocument,
)


def _doc() -> StructuredDocument:
    return StructuredDocument(
        paper_id="p1",
        sections=[
            DocumentSection(
                id="s1",
                heading="Introduction",
                text="Metal ferrites are promising electrode materials [14].",
                location=SourceLocation(page=2, section="Introduction"),
            )
        ],
        references=[ReferenceEntry(reference_number="14", raw_text="Reference 14")],
    )


def test_numeric_markers_expand_ranges():
    assert extract_numeric_reference_numbers("Prior work [10-12, 14; 17–18].") == ["10", "11", "12", "14", "17", "18"]


def test_follow_priority_is_deterministic():
    assert follow_priority_for_purpose(CitationPurpose.METHOD) == FollowPriority.HIGH
    assert follow_priority_for_purpose(CitationPurpose.CONTRADICTION) == FollowPriority.HIGH
    assert follow_priority_for_purpose(CitationPurpose.BACKGROUND) == FollowPriority.LOW
    assert follow_priority_for_purpose(CitationPurpose.SUPPORT) == FollowPriority.MEDIUM


def test_materialize_valid_candidate_preserves_source_location():
    parsed = SemanticExtractionOutput(
        assertions=[
            SemanticAssertionCandidate(
                section_id="s1",
                source_text="Metal ferrites are promising electrode materials [14].",
                normalized_claim="Metal ferrites are promising electrode materials.",
                claim_type=ClaimType.PROPERTY,
                citations=[
                    SemanticCitationBinding(
                        reference_number="14",
                        purpose=CitationPurpose.SUPPORT,
                        purpose_reason="The citation is used to support the material-property statement.",
                    )
                ],
            )
        ]
    )
    result = materialize_extraction(_doc(), parsed, model="test")
    assert len(result.assertions) == 1
    assert len(result.citation_relations) == 1
    assert result.assertions[0].location.page == 2
    assert result.citation_relations[0].reference_number == "14"
    assert result.citation_relations[0].follow_priority == FollowPriority.MEDIUM


def test_hallucinated_reference_binding_is_rejected():
    parsed = SemanticExtractionOutput(
        assertions=[
            SemanticAssertionCandidate(
                section_id="s1",
                source_text="Metal ferrites are promising electrode materials [14].",
                normalized_claim="Metal ferrites are promising electrode materials.",
                claim_type=ClaimType.PROPERTY,
                citations=[
                    SemanticCitationBinding(
                        reference_number="99",
                        purpose=CitationPurpose.SUPPORT,
                        purpose_reason="invented",
                    )
                ],
            )
        ]
    )
    result = materialize_extraction(_doc(), parsed, model="test")
    assert result.assertions == []
    assert result.citation_relations == []
    assert any("not visible" in w for w in result.warnings)


def test_non_verbatim_source_text_is_rejected():
    parsed = SemanticExtractionOutput(
        assertions=[
            SemanticAssertionCandidate(
                section_id="s1",
                source_text="Ferrites are excellent electrode materials [14].",
                normalized_claim="Ferrites are excellent electrode materials.",
                claim_type=ClaimType.PROPERTY,
                citations=[
                    SemanticCitationBinding(
                        reference_number="14",
                        purpose=CitationPurpose.SUPPORT,
                        purpose_reason="support",
                    )
                ],
            )
        ]
    )
    result = materialize_extraction(_doc(), parsed, model="test")
    assert result.assertions == []
    assert any("non-verbatim" in w for w in result.warnings)
