from __future__ import annotations

import json

from citation_needed.acquisition.http import AcquisitionNetworkError, HttpResponse
from citation_needed.models import (
    Assertion,
    CitationPurpose,
    CitationRelation,
    ExtractionResult,
    FollowPriority,
    ReferenceEntry,
    ResolutionStatus,
    SourceLocation,
)
from citation_needed.models.resolution import CitationResolution, IdentityBasis
from citation_needed.pipeline import select_citation_relation
from citation_needed.resolution.enrichment import enrich_resolution_crossref


GITA_REF_17 = (
    "K.V. Sankar, R.K. Selvan, The preparation of MnFe2O4 decorated flexible graphene wrapped with PANI "
    "and its electrochemical performances for hybrid supercapacitors, RSC Adv. 4 (2014) 17555–17566."
)


class FakeCrossrefSearch:
    def __init__(self, *, ambiguous: bool = False, fail: bool = False):
        self.ambiguous = ambiguous
        self.fail = fail

    def get(self, url: str, *, headers=None, timeout=20.0, max_bytes=5_000_000):
        if self.fail:
            raise AcquisitionNetworkError("offline")
        exact = {
            "DOI": "10.1039/C3RA47681B",
            "title": ["The preparation of MnFe2O4 decorated flexible graphene wrapped with PANI and its electrochemical performances for hybrid supercapacitors"],
            "author": [
                {"given": "Kalimuthu Vijaya", "family": "Sankar"},
                {"given": "Ramakrishnan Kalai", "family": "Selvan"},
            ],
            "published-online": {"date-parts": [[2014, 4, 11]]},
            "container-title": ["RSC Advances"],
            "URL": "https://doi.org/10.1039/C3RA47681B",
        }
        items = [exact]
        if self.ambiguous:
            duplicate = dict(exact)
            duplicate["DOI"] = "10.9999/ambiguous"
            items.append(duplicate)
        else:
            items.append({
                "DOI": "10.9999/distractor",
                "title": ["Unrelated manganese ferrite electrode study"],
                "published-online": {"date-parts": [[2014]]},
            })
        body = json.dumps({"message": {"items": items}}).encode()
        return HttpResponse(200, url, {"content-type": "application/json"}, body)


def _partial_resolution() -> CitationResolution:
    return CitationResolution(
        relation_id="cr17",
        source_paper_id="gita",
        reference_number="17",
        status=ResolutionStatus.PARTIALLY_RESOLVED,
        reference_entry=ReferenceEntry(reference_number="17", raw_text=GITA_REF_17, year=2014),
        cited_paper_id=None,
        identity_basis=IdentityBasis.RAW_REFERENCE,
        warnings=["Bibliography entry found, but no canonical source identifier is available yet."],
    )


def test_gita_reference_17_enriches_to_verified_doi():
    result = enrich_resolution_crossref(_partial_resolution(), client=FakeCrossrefSearch())
    assert result.status == ResolutionStatus.RESOLVED
    assert result.identity_basis == IdentityBasis.DOI
    assert result.cited_paper_id == "doi:10.1039/c3ra47681b"
    assert result.reference_entry is not None
    assert result.reference_entry.doi == "10.1039/c3ra47681b"
    assert result.reference_entry.year == 2014
    assert "Sankar" in " ".join(result.reference_entry.authors)


def test_ambiguous_crossref_identity_stays_partial():
    result = enrich_resolution_crossref(_partial_resolution(), client=FakeCrossrefSearch(ambiguous=True))
    assert result.status == ResolutionStatus.PARTIALLY_RESOLVED
    assert result.cited_paper_id is None
    assert any("not strong enough" in w for w in result.warnings)


def test_network_failure_does_not_turn_partial_identity_into_not_found():
    result = enrich_resolution_crossref(_partial_resolution(), client=FakeCrossrefSearch(fail=True))
    assert result.status == ResolutionStatus.PARTIALLY_RESOLVED
    assert any("enrichment failed" in w for w in result.warnings)


def test_repeated_reference_can_be_disambiguated_by_context():
    a1 = Assertion(
        id="a1", text="Limited resistance [17]", normalized_claim="limited resistance",
        paper_id="gita", location=SourceLocation(section="Introduction"), citation_ids=["r1"],
    )
    a2 = Assertion(
        id="a2", text="Different composites have been utilized successfully such as MnFe2O4/Graphene/PANI[17]",
        normalized_claim="MnFe2O4/Graphene/PANI composites have been utilized successfully",
        paper_id="gita", location=SourceLocation(section="Introduction"), citation_ids=["r2"],
    )
    common = dict(
        source_paper_id="gita", reference_number="17", purpose=CitationPurpose.SUPPORT,
        follow_priority=FollowPriority.MEDIUM, resolution_status=ResolutionStatus.UNRESOLVED,
    )
    r1 = CitationRelation(id="r1", assertion_id="a1", citation_context=a1.text, **common)
    r2 = CitationRelation(id="r2", assertion_id="a2", citation_context=a2.text, **common)
    extraction = ExtractionResult(paper_id="gita", assertions=[a1, a2], citation_relations=[r1, r2])

    assertion, relation, _ = select_citation_relation(
        extraction,
        reference_number="17",
        citation_context_contains="Different composites have been utilized",
    )
    assert assertion.id == "a2"
    assert relation.id == "r2"
