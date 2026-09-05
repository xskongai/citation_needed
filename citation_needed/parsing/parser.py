from __future__ import annotations

import html as html_lib
import re
from pathlib import Path
from xml.etree import ElementTree as ET

from citation_needed.models import (
    AcquiredSource,
    AcquisitionStatus,
    ArtifactKind,
    DocumentSection,
    ParseStatus,
    ReferenceEntry,
    SectionType,
    SourceLocation,
    SourceParseResult,
    StructuredDocument,
)
from citation_needed.resolution.reference_parser import parse_reference_section


_HEADING_NUMBER_RE = re.compile(r"^\s*(?:\d+(?:\.\d+){0,3}\.?\s+)(.+?)\s*$")
_BRACKET_REF_RE = re.compile(r"^\s*\[\d+\]")
_DOT_REF_RE = re.compile(r"^\s*\d+\.\s+")


def _norm_ws(text: str) -> str:
    return re.sub(r"[ \t\f\v]+", " ", text.replace("\u00a0", " ")).strip()


def classify_section(heading: str | None) -> SectionType:
    if not heading:
        return SectionType.OTHER
    raw = heading.strip()
    top_match = re.match(r"^\s*(\d+)(?:\.\d+){0,3}\.?\s*", raw)
    top_number = int(top_match.group(1)) if top_match else None
    h = re.sub(r"^\s*\d+(?:\.\d+){0,3}\.?\s*", "", raw).strip().lower()
    if not h:
        return SectionType.OTHER
    if h == "abstract" or h.startswith("abstract "):
        return SectionType.ABSTRACT
    if any(k in h for k in ("reference", "bibliograph")):
        return SectionType.REFERENCES
    if any(k in h for k in ("supplement", "supporting information")):
        return SectionType.SUPPLEMENTARY
    if h == "introduction" or h == "background" or h.startswith("introduction "):
        return SectionType.INTRODUCTION
    if any(k in h for k in ("method", "experimental", "materials", "synthesis", "preparation", "fabrication")):
        return SectionType.METHODS
    if "characterization" in h or "characterisation" in h:
        # In many scientific papers section 2.x is experimental
        # characterization, while 3.x characterization can be results.
        return SectionType.METHODS if top_number == 2 else SectionType.RESULTS
    if "conclusion" in h or "concluding" in h:
        return SectionType.CONCLUSION
    if "discussion" in h and "result" not in h:
        return SectionType.DISCUSSION
    if any(k in h for k in ("result", "performance")):
        return SectionType.RESULTS
    return SectionType.OTHER


def _looks_like_heading(line: str) -> bool:
    line = _norm_ws(line)
    if not line or len(line) > 140:
        return False
    if line.endswith((".", ";", ":", "?", "!")):
        return False

    # Numbered headings are the strongest layout-independent signal.
    m = _HEADING_NUMBER_RE.match(line)
    if m:
        tail = m.group(1).strip()
        if len(tail) <= 100 and 1 <= len(tail.split()) <= 14:
            return True

    # For unnumbered headings, use a narrow scientific-section lexicon rather
    # than substring matching. This avoids treating a wrapped sentence such as
    # "... examined by galvanostatic ... method up to" as a METHODS heading.
    h = line.lower().strip()
    exact = {
        "abstract", "introduction", "background", "methods", "method",
        "materials and methods", "experimental methods", "experimental",
        "results", "results and discussion", "discussion", "conclusion",
        "conclusions", "references", "bibliography", "acknowledgements",
        "acknowledgments", "characterization", "characterisation",
        "experimental section", "supporting information",
    }
    if h in exact:
        return True
    # A few common short variants are still safe.
    safe_prefixes = ("methods for ", "experimental ", "results of ", "discussion of ")
    return h.startswith(safe_prefixes) and len(line.split()) <= 10


def _split_heading_prefix(block_text: str) -> tuple[str | None, str]:
    lines = [_norm_ws(x) for x in block_text.splitlines() if _norm_ws(x)]
    if not lines:
        return None, ""
    if _looks_like_heading(lines[0]):
        return lines[0], "\n".join(lines[1:]).strip()
    return None, "\n".join(lines).strip()


def _make_section_id(page: int | None, section_type: SectionType, paragraph: int, serial: int) -> str:
    p = f"p{page}" if page else "pna"
    return f"sec:{p}:{section_type.value.lower()}:{paragraph}:{serial}"


def _append_paragraph(
    sections: list[DocumentSection],
    *,
    text: str,
    page: int | None,
    heading: str | None,
    section_type: SectionType,
    paragraph: int,
    serial: int,
) -> None:
    text = _norm_ws(text.replace("\n", " "))
    if not text:
        return
    sections.append(
        DocumentSection(
            id=_make_section_id(page, section_type, paragraph, serial),
            heading=heading,
            text=text,
            section_type=section_type,
            location=SourceLocation(page=page, section=heading, paragraph=paragraph),
        )
    )


def _parse_pdf(path: Path, *, paper_id: str, title: str | None) -> StructuredDocument:
    try:
        import pymupdf
    except ImportError as exc:  # pragma: no cover - dependency contract
        raise RuntimeError("PyMuPDF is required to parse PDF artifacts.") from exc

    doc = pymupdf.open(path)
    sections: list[DocumentSection] = []
    ref_chunks: list[str] = []
    current_heading: str | None = None
    current_type = SectionType.OTHER
    serial = 0

    metadata_title = _norm_ws(str((doc.metadata or {}).get("title") or "")) or None
    inferred_title = title or metadata_title
    title_candidates: list[str] = []

    # PDF block extraction can yield one block per visual line. We therefore
    # aggregate adjacent blocks under the same heading *within each page*.
    # This preserves page provenance while giving the retriever enough local
    # context to evaluate scientific statements spanning line wraps.
    for page_idx, page in enumerate(doc, start=1):
        segment_parts: list[str] = []
        segment_heading = current_heading
        segment_type = current_type
        paragraph_index = 0

        def flush_segment() -> None:
            nonlocal serial, paragraph_index, segment_parts
            body = _norm_ws(" ".join(segment_parts))
            segment_parts = []
            if not body:
                return
            paragraph_index += 1
            serial += 1
            _append_paragraph(
                sections,
                text=body,
                page=page_idx,
                heading=segment_heading,
                section_type=segment_type,
                paragraph=paragraph_index,
                serial=serial,
            )

        blocks = page.get_text("blocks", sort=True)
        for block in blocks:
            raw = str(block[4] or "").strip()
            if not raw:
                continue

            # Once the bibliography starts, it normally continues to the end
            # of the article. Reference titles can contain words like
            # "performance" or "methods", so do not reclassify them as body
            # section headings.
            if current_type == SectionType.REFERENCES:
                ref_chunks.append(raw)
                continue

            if inferred_title is None and page_idx == 1 and current_heading is None:
                for candidate_line in raw.splitlines():
                    candidate = _norm_ws(candidate_line)
                    low = candidate.lower()
                    if 20 <= len(candidate) <= 240 and not low.startswith((
                        "version of record", "manuscript_", "http", "doi", "©", "email:", "department of"
                    )):
                        title_candidates.append(candidate)

            heading, body = _split_heading_prefix(raw)
            if heading:
                flush_segment()
                current_heading = heading
                current_type = classify_section(heading)
                segment_heading = current_heading
                segment_type = current_type
                paragraph_index = 0
                if current_type == SectionType.REFERENCES:
                    if body:
                        ref_chunks.append(body)
                    continue
                if body:
                    segment_parts.append(body)
                continue

            segment_parts.append(raw)

        flush_segment()

    doc.close()
    if inferred_title is None and title_candidates:
        inferred_title = title_candidates[0]
    refs = parse_reference_section("\n".join(ref_chunks)) if ref_chunks else []
    return StructuredDocument(paper_id=paper_id, title=inferred_title, sections=sections, references=refs)


def _parse_plain_text(text: str, *, paper_id: str, title: str | None) -> StructuredDocument:
    lines = text.splitlines()
    sections: list[DocumentSection] = []
    ref_lines: list[str] = []
    current_heading: str | None = None
    current_type = SectionType.OTHER
    paragraph_lines: list[str] = []
    paragraph_counter = 0
    serial = 0
    inferred_title = title

    def flush() -> None:
        nonlocal paragraph_lines, paragraph_counter, serial
        body = _norm_ws(" ".join(paragraph_lines))
        paragraph_lines = []
        if not body:
            return
        if current_type == SectionType.REFERENCES:
            ref_lines.append(body)
            return
        paragraph_counter += 1
        serial += 1
        _append_paragraph(
            sections,
            text=body,
            page=None,
            heading=current_heading,
            section_type=current_type,
            paragraph=paragraph_counter,
            serial=serial,
        )

    for raw in lines:
        line = _norm_ws(raw)
        if not line:
            flush()
            continue
        if _looks_like_heading(line):
            flush()
            current_heading = line
            current_type = classify_section(line)
            paragraph_counter = 0
            continue
        if current_type == SectionType.REFERENCES:
            # Preserve numeric entry boundaries for the deterministic bibliography parser.
            if _BRACKET_REF_RE.match(line) or _DOT_REF_RE.match(line):
                flush()
                paragraph_lines.append(line)
            else:
                paragraph_lines.append(line)
            continue
        if inferred_title is None and current_heading is None and not sections and not paragraph_lines:
            if 20 <= len(line) <= 240:
                inferred_title = line
                continue
        paragraph_lines.append(line)
    flush()

    refs = parse_reference_section("\n".join(ref_lines)) if ref_lines else []
    return StructuredDocument(paper_id=paper_id, title=inferred_title, sections=sections, references=refs)


def _strip_ns(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _node_text(node: ET.Element | None) -> str:
    if node is None:
        return ""
    return _norm_ws(" ".join("".join(node.itertext()).split()))


def _parse_xml(path: Path, *, paper_id: str, title: str | None) -> StructuredDocument:
    root = ET.parse(path).getroot()
    inferred_title = title
    if inferred_title is None:
        for node in root.iter():
            if _strip_ns(node.tag) in {"article-title", "title"}:
                candidate = _node_text(node)
                if candidate:
                    inferred_title = candidate
                    break

    sections: list[DocumentSection] = []
    refs: list[ReferenceEntry] = []
    serial = 0

    # JATS-like sections. Nested sections are intentionally emitted separately.
    for sec in (n for n in root.iter() if _strip_ns(n.tag) == "sec"):
        title_node = next((c for c in list(sec) if _strip_ns(c.tag) == "title"), None)
        heading = _node_text(title_node) or None
        st = classify_section(heading)
        paragraph = 0
        # direct p children only avoids duplicating nested sec paragraphs
        for child in list(sec):
            if _strip_ns(child.tag) != "p":
                continue
            body = _node_text(child)
            if not body:
                continue
            paragraph += 1
            serial += 1
            _append_paragraph(
                sections,
                text=body,
                page=None,
                heading=heading,
                section_type=st,
                paragraph=paragraph,
                serial=serial,
            )

    # Abstract often lives outside <sec>.
    if not any(s.section_type == SectionType.ABSTRACT for s in sections):
        for abstract in (n for n in root.iter() if _strip_ns(n.tag) == "abstract"):
            body = _node_text(abstract)
            if body:
                serial += 1
                _append_paragraph(
                    sections,
                    text=body,
                    page=None,
                    heading="Abstract",
                    section_type=SectionType.ABSTRACT,
                    paragraph=1,
                    serial=serial,
                )
                break

    # Numeric JATS bibliography.
    for ref in (n for n in root.iter() if _strip_ns(n.tag) == "ref"):
        label = next((c for c in list(ref) if _strip_ns(c.tag) == "label"), None)
        number = _node_text(label)
        if not number:
            rid = ref.attrib.get("id", "")
            m = re.search(r"(\d+)$", rid)
            number = m.group(1) if m else ""
        raw = _node_text(ref)
        if number and raw:
            raw_no_label = re.sub(rf"^\s*{re.escape(number)}\s*", "", raw).strip()
            parsed = parse_reference_section(f"[{number}] {raw_no_label}")
            refs.extend(parsed)

    return StructuredDocument(paper_id=paper_id, title=inferred_title, sections=sections, references=refs)


def _parse_html(path: Path, *, paper_id: str, title: str | None) -> StructuredDocument:
    try:
        from bs4 import BeautifulSoup
    except ImportError as exc:  # pragma: no cover - dependency contract
        raise RuntimeError("beautifulsoup4 is required to parse HTML artifacts.") from exc

    soup = BeautifulSoup(path.read_text(errors="replace"), "html.parser")
    inferred_title = title
    if inferred_title is None:
        node = soup.find("h1") or soup.find("title")
        if node:
            inferred_title = _norm_ws(node.get_text(" ", strip=True)) or None

    sections: list[DocumentSection] = []
    refs_text: list[str] = []
    current_heading: str | None = None
    current_type = SectionType.OTHER
    paragraph = 0
    serial = 0

    for node in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li"]):
        text = _norm_ws(html_lib.unescape(node.get_text(" ", strip=True)))
        if not text:
            continue
        if node.name and node.name.startswith("h"):
            if inferred_title and text == inferred_title:
                continue
            current_heading = text
            current_type = classify_section(text)
            paragraph = 0
            continue
        if current_type == SectionType.REFERENCES:
            refs_text.append(text)
            continue
        paragraph += 1
        serial += 1
        _append_paragraph(
            sections,
            text=text,
            page=None,
            heading=current_heading,
            section_type=current_type,
            paragraph=paragraph,
            serial=serial,
        )

    refs = parse_reference_section("\n".join(refs_text)) if refs_text else []
    return StructuredDocument(paper_id=paper_id, title=inferred_title, sections=sections, references=refs)


def parse_artifact(
    path: str | Path,
    *,
    kind: ArtifactKind,
    paper_id: str,
    title: str | None = None,
) -> StructuredDocument:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    if kind == ArtifactKind.PDF:
        return _parse_pdf(path, paper_id=paper_id, title=title)
    if kind == ArtifactKind.XML:
        return _parse_xml(path, paper_id=paper_id, title=title)
    if kind == ArtifactKind.TEXT:
        return _parse_plain_text(path.read_text(errors="replace"), paper_id=paper_id, title=title)
    if kind == ArtifactKind.HTML:
        return _parse_html(path, paper_id=paper_id, title=title)
    raise ValueError(f"Unsupported artifact kind: {kind.value}")


def parse_acquired_source(source: AcquiredSource) -> SourceParseResult:
    """Convert acquisition output into the StructuredDocument contract.

    Availability states remain explicit. An abstract-only source can produce an
    abstract-only document, but it is never promoted to a full-text parse.
    """
    paper_id = source.cited_paper_id or source.metadata.doi or f"relation:{source.relation_id}"

    if source.status == AcquisitionStatus.ABSTRACT_ONLY and source.metadata.abstract:
        doc = StructuredDocument(
            paper_id=paper_id,
            title=source.metadata.title,
            sections=[
                DocumentSection(
                    id="sec:pna:abstract:1:1",
                    heading="Abstract",
                    text=_norm_ws(source.metadata.abstract),
                    section_type=SectionType.ABSTRACT,
                    location=SourceLocation(section="Abstract", paragraph=1),
                )
            ],
            references=[],
        )
        return SourceParseResult(
            relation_id=source.relation_id,
            cited_paper_id=source.cited_paper_id,
            status=ParseStatus.ABSTRACT_ONLY_PARSED,
            document=doc,
            warnings=["Only abstract text was available; this is not a full-text parse."],
        )

    if source.status != AcquisitionStatus.FULL_TEXT_AVAILABLE:
        return SourceParseResult(
            relation_id=source.relation_id,
            cited_paper_id=source.cited_paper_id,
            status=ParseStatus.SOURCE_UNAVAILABLE,
            warnings=[f"Acquisition status {source.status.value} does not provide parseable full text."],
        )

    artifact = next((a for a in source.artifacts if a.local_path), None)
    if artifact is None:
        return SourceParseResult(
            relation_id=source.relation_id,
            cited_paper_id=source.cited_paper_id,
            status=ParseStatus.SOURCE_UNAVAILABLE,
            warnings=["Acquisition reported full text but no local artifact path was supplied."],
        )

    if artifact.kind not in {ArtifactKind.PDF, ArtifactKind.XML, ArtifactKind.HTML, ArtifactKind.TEXT}:
        return SourceParseResult(
            relation_id=source.relation_id,
            cited_paper_id=source.cited_paper_id,
            status=ParseStatus.UNSUPPORTED_FORMAT,
            artifact_kind=artifact.kind,
            artifact_path=artifact.local_path,
            warnings=[f"Unsupported full-text artifact kind: {artifact.kind.value}."],
        )

    try:
        document = parse_artifact(
            artifact.local_path,
            kind=artifact.kind,
            paper_id=paper_id,
            title=source.metadata.title,
        )
    except Exception as exc:
        return SourceParseResult(
            relation_id=source.relation_id,
            cited_paper_id=source.cited_paper_id,
            status=ParseStatus.PARSE_FAILED,
            artifact_kind=artifact.kind,
            artifact_path=artifact.local_path,
            warnings=[f"Parser failed: {type(exc).__name__}: {exc}"],
        )

    warnings: list[str] = []
    if not document.sections:
        warnings.append("Full-text artifact parsed but no evidence-bearing sections were produced.")
    return SourceParseResult(
        relation_id=source.relation_id,
        cited_paper_id=source.cited_paper_id,
        status=ParseStatus.FULL_TEXT_PARSED,
        artifact_kind=artifact.kind,
        artifact_path=artifact.local_path,
        document=document,
        warnings=warnings,
    )
