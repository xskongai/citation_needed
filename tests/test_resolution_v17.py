from citation_needed.models import CitationRelation, CitationPurpose, FollowPriority, ResolutionStatus
from citation_needed.models.resolution import IdentityBasis
from citation_needed.resolution import parse_reference_section, resolve_citation_relation


def relation(number: str) -> CitationRelation:
    return CitationRelation(
        id=f"rel-{number}",
        assertion_id="a1",
        source_paper_id="paper-a",
        reference_number=number,
        citation_context=f"Claim [{number}]",
        purpose=CitationPurpose.SUPPORT,
        follow_priority=FollowPriority.MEDIUM,
    )


def test_parse_multiline_reference_and_year():
    refs = parse_reference_section("""
    References
    [10] A. Author, A long title that continues
         across a second line, Journal 4 (2018) 1-9.
    [11] B. Author, Other title, Journal 5 (2019) 2-8.
    """)
    assert len(refs) == 2
    assert refs[0].reference_number == "10"
    assert "across a second line" in refs[0].raw_text
    assert refs[0].year == 2018


def test_parse_dot_style_numeric_reference():
    refs = parse_reference_section("1. A. Author, Paper, J. 1 (2020) 1-2.\n2. B. Author, Paper, J. 2 (2021) 3-4.")
    assert [r.reference_number for r in refs] == ["1", "2"]


def test_doi_is_extracted_and_normalized_for_identity():
    refs = parse_reference_section("[1] A. Author, Paper, J. (2020). https://doi.org/10.1234/ABC.DEF.")
    result = resolve_citation_relation(relation("1"), refs)
    assert result.status == ResolutionStatus.RESOLVED
    assert result.identity_basis == IdentityBasis.DOI
    assert result.cited_paper_id == "doi:10.1234/abc.def"


def test_url_is_canonical_identity_when_no_doi():
    refs = parse_reference_section("[2] A. Author, Paper, J. (2020). https://example.org/paper/2")
    result = resolve_citation_relation(relation("2"), refs)
    assert result.status == ResolutionStatus.RESOLVED
    assert result.identity_basis == IdentityBasis.URL
    assert result.cited_paper_id.startswith("url:")


def test_raw_bibliography_match_is_partial_not_full_resolution():
    refs = parse_reference_section("[17] K.V. Sankar, R.K. Selvan, The preparation of MnFe2O4 decorated flexible graphene wrapped with PANI, RSC Adv. 4 (2014) 17555–17566.")
    result = resolve_citation_relation(relation("17"), refs)
    assert result.status == ResolutionStatus.PARTIALLY_RESOLVED
    assert result.identity_basis == IdentityBasis.RAW_REFERENCE
    assert result.reference_entry is not None
    assert result.reference_entry.year == 2014
    assert result.cited_paper_id is None


def test_missing_bibliography_entry_remains_unresolved():
    refs = parse_reference_section("[1] A. Author, Paper, J. (2020).")
    result = resolve_citation_relation(relation("99"), refs)
    assert result.status == ResolutionStatus.UNRESOLVED
    assert result.reference_entry is None


def test_unknown_is_not_source_unavailable():
    refs = []
    result = resolve_citation_relation(relation("1"), refs)
    assert result.status == ResolutionStatus.UNRESOLVED
    assert result.status != ResolutionStatus.SOURCE_UNAVAILABLE


def test_duplicate_reference_numbers_are_unresolved_not_silently_chosen():
    refs = parse_reference_section("[5] A. Author, First paper, J. (2018).\n[5] B. Author, Second paper, J. (2019).")
    assert len(refs) == 2
    result = resolve_citation_relation(relation("5"), refs)
    assert result.status == ResolutionStatus.UNRESOLVED
    assert result.reference_entry is None
    assert any("Multiple bibliography entries" in w for w in result.warnings)
