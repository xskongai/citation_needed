#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

import fitz

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
from citation_needed.parsing import parse_acquired_source, parse_artifact


def write_pdf(path: Path) -> None:
    doc = fitz.open()
    p1 = doc.new_page()
    y = 60
    for line in [
        "Parser Suite Scientific Paper",
        "Abstract",
        "We report electrochemical measurements.",
        "1. Introduction",
        "Prior work motivates this study [1].",
    ]:
        p1.insert_text((55, y), line, fontsize=12); y += 24
    p2 = doc.new_page(); y = 60
    for line in [
        "2. Experimental Methods",
        "The material was treated at pH 12 and 145 C for 24 hours.",
        "3. Results and Discussion",
        "The electrode showed a specific capacitance of 623 F/g at 1 A/g.",
        "References",
        "[1] A. Smith, Example source, 2020. https://doi.org/10.1234/parser.1",
    ]:
        p2.insert_text((55, y), line, fontsize=11); y += 24
    doc.save(path); doc.close()


def check(name: str, ok: bool, detail: str, report: list[dict]) -> None:
    label = "PASS" if ok else "REVIEW"
    print(f"[{label}] {name}: {detail}")
    report.append({"case": name, "pass": ok, "detail": detail})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    report: list[dict] = []

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        pdf = root / 'paper.pdf'; write_pdf(pdf)
        d = parse_artifact(pdf, kind=ArtifactKind.PDF, paper_id='paper:pdf')
        ok = (
            any(s.section_type == SectionType.METHODS and s.location.page == 2 for s in d.sections)
            and any(s.section_type == SectionType.RESULTS and '623 F/g' in s.text for s in d.sections)
            and len(d.references) == 1
            and not any(s.section_type == SectionType.REFERENCES for s in d.sections)
        )
        check('pdf_sections_page_provenance', ok, f"sections={len(d.sections)} refs={len(d.references)} pages={sorted(set(s.location.page for s in d.sections if s.location.page))}", report)

        txt = root / 'paper.txt'
        txt.write_text('Text Paper\n\nAbstract\nA short abstract.\n\n2. Methods\nTEM was used.\n\n3. Results\nDiameter was 18 nm.\n\nReferences\n[7] B. Jones, Study, 2021. https://doi.org/10.7777/txt.7\n')
        d2 = parse_artifact(txt, kind=ArtifactKind.TEXT, paper_id='paper:txt')
        ok = any(s.section_type == SectionType.METHODS for s in d2.sections) and any('18 nm' in s.text for s in d2.sections) and len(d2.references) == 1
        check('plain_text_structure', ok, f"sections={len(d2.sections)} refs={len(d2.references)}", report)

        xml = root / 'paper.xml'
        xml.write_text("""<article><front><article-meta><title-group><article-title>XML Paper</article-title></title-group><abstract><p>Abstract text.</p></abstract></article-meta></front><body><sec><title>Methods</title><p>GCD was used.</p></sec><sec><title>Results</title><p>Capacitance was 623 F/g.</p></sec></body><back><ref-list><ref id='R4'><label>4</label><mixed-citation>D. Doe, 2022, doi:10.4444/xml.4</mixed-citation></ref></ref-list></back></article>""")
        d3 = parse_artifact(xml, kind=ArtifactKind.XML, paper_id='paper:xml')
        ok = any(s.section_type == SectionType.ABSTRACT for s in d3.sections) and any(s.section_type == SectionType.RESULTS for s in d3.sections) and len(d3.references) == 1
        check('jats_xml_structure', ok, f"title={d3.title!r} sections={len(d3.sections)} refs={len(d3.references)}", report)

        html = root / 'paper.html'
        html.write_text('<html><head><title>HTML Paper</title></head><body><h2>Methods</h2><p>TEM was used.</p><h2>Results</h2><p>Diameter was 18 nm.</p><h2>References</h2><p>[2] Roe, 2020, doi:10.2222/html.2</p></body></html>')
        d4 = parse_artifact(html, kind=ArtifactKind.HTML, paper_id='paper:html')
        ok = any(s.section_type == SectionType.METHODS for s in d4.sections) and len(d4.references) == 1
        check('html_structure', ok, f"title={d4.title!r} sections={len(d4.sections)} refs={len(d4.references)}", report)

        source = AcquiredSource(relation_id='rel:a', cited_paper_id='paper:a', status=AcquisitionStatus.ABSTRACT_ONLY, metadata=AcquiredMetadata(title='Abstract-only', abstract='Only abstract evidence is available.'))
        r = parse_acquired_source(source)
        ok = r.status == ParseStatus.ABSTRACT_ONLY_PARSED and r.document is not None and len(r.document.sections) == 1
        check('abstract_only_not_full_text', ok, f"status={r.status.value} sections={len(r.document.sections) if r.document else 0}", report)

        source2 = AcquiredSource(relation_id='rel:b', cited_paper_id='paper:b', status=AcquisitionStatus.ACCESS_RESTRICTED)
        r2 = parse_acquired_source(source2)
        ok = r2.status == ParseStatus.SOURCE_UNAVAILABLE and r2.document is None
        check('restricted_stays_unavailable', ok, f"status={r2.status.value}", report)

        source3 = AcquiredSource(relation_id='rel:c', cited_paper_id='paper:c', status=AcquisitionStatus.FULL_TEXT_AVAILABLE, metadata=AcquiredMetadata(title='Metadata wins'), artifacts=[AcquiredArtifact(provider=AcquisitionProvider.DIRECT_URL, url='https://example.org/p.pdf', kind=ArtifactKind.PDF, access_level=AccessLevel.OPEN_ACCESS, local_path=str(pdf))])
        r3 = parse_acquired_source(source3)
        ok = r3.status == ParseStatus.FULL_TEXT_PARSED and r3.document is not None and r3.document.title == 'Metadata wins'
        check('acquired_pdf_to_structured_document', ok, f"status={r3.status.value} title={r3.document.title if r3.document else None!r}", report)

        bad = root / 'broken.pdf'; bad.write_bytes(b'not a pdf')
        source4 = AcquiredSource(relation_id='rel:d', cited_paper_id='paper:d', status=AcquisitionStatus.FULL_TEXT_AVAILABLE, artifacts=[AcquiredArtifact(provider=AcquisitionProvider.DIRECT_URL, url='https://example.org/bad.pdf', kind=ArtifactKind.PDF, local_path=str(bad))])
        r4 = parse_acquired_source(source4)
        ok = r4.status == ParseStatus.PARSE_FAILED and r4.document is None
        check('parse_failure_is_explicit', ok, f"status={r4.status.value}", report)

    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2))
    passed = sum(1 for x in report if x['pass'])
    print(f"\n{passed}/{len(report)} cases matched the declared expectations.")
    print(f"Report written to {out}")


if __name__ == '__main__':
    main()
