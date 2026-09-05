from __future__ import annotations

from pathlib import Path

import pymupdf

from citation_needed.models import (
    AccessLevel,
    AcquisitionProvider,
    AcquisitionStatus,
    AcquiredArtifact,
    AcquiredMetadata,
    AcquiredSource,
    ArtifactKind,
    ParseStatus,
    SectionType,
)
from citation_needed.parsing import classify_section, parse_acquired_source, parse_artifact


def _write_pdf(path: Path) -> None:
    doc = pymupdf.open()
    p1 = doc.new_page()
    y = 60
    for line in [
        "A Traceable Scientific Paper",
        "Abstract",
        "We report a material with a specific capacitance of 623 F/g.",
        "1. Introduction",
        "Prior work motivates the study [1].",
    ]:
        p1.insert_text((60, y), line, fontsize=12)
        y += 24
    p2 = doc.new_page()
    y = 60
    for line in [
        "2. Experimental Methods",
        "The sample was treated at pH 12 and 145 C for 24 hours.",
        "3. Results and Discussion",
        "The electrode showed 623 F/g at 1 A/g.",
        "4. Conclusion",
        "The composite showed strong electrochemical performance.",
        "References",
        "[1] A. Smith, Example study, Journal 12 (2020) 1-5. https://doi.org/10.1234/example.1",
    ]:
        p2.insert_text((60, y), line, fontsize=11)
        y += 24
    doc.save(path)
    doc.close()


def test_section_classifier():
    assert classify_section("2. Experimental methods") == SectionType.METHODS
    assert classify_section("3. Results and Discussion") == SectionType.RESULTS
    assert classify_section("References") == SectionType.REFERENCES
    assert classify_section("4 Conclusion") == SectionType.CONCLUSION


def test_pdf_parser_preserves_page_and_excludes_references(tmp_path: Path):
    path = tmp_path / "paper.pdf"
    _write_pdf(path)
    doc = parse_artifact(path, kind=ArtifactKind.PDF, paper_id="paper:test")
    assert doc.title == "A Traceable Scientific Paper"
    assert any(s.section_type == SectionType.METHODS and s.location.page == 2 for s in doc.sections)
    assert any("623 F/g" in s.text and s.location.page == 2 for s in doc.sections)
    assert not any(s.section_type == SectionType.REFERENCES for s in doc.sections)
    assert len(doc.references) == 1
    assert doc.references[0].reference_number == "1"
    assert doc.references[0].doi == "10.1234/example.1"


def test_txt_parser_sections_and_references(tmp_path: Path):
    path = tmp_path / "paper.txt"
    path.write_text(
        "Plain Text Scientific Paper\n\n"
        "Abstract\nA compact abstract.\n\n"
        "2. Methods\nThe sample was heated at 145 C.\n\n"
        "3. Results\nThe measured value was 18 nm.\n\n"
        "References\n[7] B. Jones, Source paper, 2021. https://doi.org/10.7777/test.7\n"
    )
    doc = parse_artifact(path, kind=ArtifactKind.TEXT, paper_id="paper:text")
    assert doc.title == "Plain Text Scientific Paper"
    assert [s.section_type for s in doc.sections] == [SectionType.ABSTRACT, SectionType.METHODS, SectionType.RESULTS]
    assert doc.references[0].doi == "10.7777/test.7"


def test_jats_xml_parser(tmp_path: Path):
    path = tmp_path / "paper.xml"
    path.write_text("""<?xml version='1.0'?>
<article><front><article-meta><title-group><article-title>JATS Example</article-title></title-group>
<abstract><p>Abstract evidence.</p></abstract></article-meta></front>
<body><sec><title>2. Experimental Methods</title><p>We used TEM for particle size.</p></sec>
<sec><title>3. Results</title><p>The mean diameter was 18 nm.</p></sec></body>
<back><ref-list><ref id='R3'><label>3</label><mixed-citation>C. Doe. Example. 2022. doi:10.3333/xml.3</mixed-citation></ref></ref-list></back>
</article>""")
    doc = parse_artifact(path, kind=ArtifactKind.XML, paper_id="paper:xml")
    assert doc.title == "JATS Example"
    assert any(s.section_type == SectionType.ABSTRACT for s in doc.sections)
    assert any(s.section_type == SectionType.METHODS for s in doc.sections)
    assert any("18 nm" in s.text for s in doc.sections)
    assert doc.references and doc.references[0].reference_number == "3"
    assert doc.references[0].doi == "10.3333/xml.3"


def test_html_parser(tmp_path: Path):
    path = tmp_path / "paper.html"
    path.write_text("""<html><head><title>HTML Example</title></head><body>
<h1>HTML Example</h1><h2>Methods</h2><p>GCD was used for electrochemical testing.</p>
<h2>Results</h2><p>Specific capacitance was 623 F/g.</p>
<h2>References</h2><p>[2] D. Roe, Web article, 2020. https://doi.org/10.2222/html.2</p>
</body></html>""")
    doc = parse_artifact(path, kind=ArtifactKind.HTML, paper_id="paper:html")
    assert doc.title == "HTML Example"
    assert any(s.section_type == SectionType.METHODS for s in doc.sections)
    assert any(s.section_type == SectionType.RESULTS for s in doc.sections)
    assert len(doc.references) == 1


def test_abstract_only_is_not_promoted_to_full_text():
    source = AcquiredSource(
        relation_id="rel:1",
        cited_paper_id="doi:10.1/x",
        status=AcquisitionStatus.ABSTRACT_ONLY,
        metadata=AcquiredMetadata(title="Abstract only", abstract="Only this abstract is available."),
    )
    result = parse_acquired_source(source)
    assert result.status == ParseStatus.ABSTRACT_ONLY_PARSED
    assert result.document is not None
    assert len(result.document.sections) == 1
    assert result.document.sections[0].section_type == SectionType.ABSTRACT
    assert "not a full-text parse" in result.warnings[0]


def test_unavailable_source_stays_unavailable():
    source = AcquiredSource(
        relation_id="rel:2",
        cited_paper_id="doi:10.1/y",
        status=AcquisitionStatus.ACCESS_RESTRICTED,
    )
    result = parse_acquired_source(source)
    assert result.status == ParseStatus.SOURCE_UNAVAILABLE
    assert result.document is None


def test_parse_acquired_pdf(tmp_path: Path):
    path = tmp_path / "paper.pdf"
    _write_pdf(path)
    source = AcquiredSource(
        relation_id="rel:3",
        cited_paper_id="doi:10.1/z",
        status=AcquisitionStatus.FULL_TEXT_AVAILABLE,
        metadata=AcquiredMetadata(title="Metadata Title"),
        artifacts=[AcquiredArtifact(
            provider=AcquisitionProvider.DIRECT_URL,
            url="https://example.org/paper.pdf",
            kind=ArtifactKind.PDF,
            access_level=AccessLevel.OPEN_ACCESS,
            local_path=str(path),
        )],
    )
    result = parse_acquired_source(source)
    assert result.status == ParseStatus.FULL_TEXT_PARSED
    assert result.document is not None
    assert result.document.title == "Metadata Title"
    assert result.artifact_kind == ArtifactKind.PDF
