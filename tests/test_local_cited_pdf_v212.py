from __future__ import annotations

from pathlib import Path

import pymupdf

from citation_needed.acquisition import acquire_source
from citation_needed.models import (
    AcquisitionStatus,
    CitationResolution,
    IdentityBasis,
    ParseStatus,
    ReferenceEntry,
    ResolutionStatus,
)
from citation_needed.parsing import parse_acquired_source


def _resolution() -> CitationResolution:
    entry = ReferenceEntry(
        reference_number="17",
        raw_text="[17] Example cited paper",
        title="Example cited paper",
        year=2024,
        doi="10.1000/local-test",
    )
    return CitationResolution(
        relation_id="rel-17",
        source_paper_id="paper-a",
        reference_number="17",
        status=ResolutionStatus.RESOLVED,
        reference_entry=entry,
        cited_paper_id="doi:10.1000/local-test",
        identity_basis=IdentityBasis.DOI,
    )


def test_manual_pdf_continues_into_parser(tmp_path: Path):
    cited = tmp_path / "cited"
    cited.mkdir()
    pdf = cited / "reference_17.pdf"

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Results")
    page.insert_text((72, 100), "The MnFe2O4 graphene PANI composite was successfully prepared and tested.")
    doc.save(pdf)
    doc.close()

    acquired = acquire_source(_resolution(), local_source_dir=cited)
    assert acquired.status == AcquisitionStatus.FULL_TEXT_AVAILABLE
    assert acquired.artifacts[0].provider.value == "LOCAL_FILE"

    parsed = parse_acquired_source(acquired)
    assert parsed.status == ParseStatus.FULL_TEXT_PARSED
    assert parsed.document is not None
    assert any("MnFe2O4" in section.text for section in parsed.document.sections)
