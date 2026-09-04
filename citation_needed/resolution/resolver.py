from __future__ import annotations

import hashlib
import re

from citation_needed.models.citation import CitationRelation, ResolutionStatus
from citation_needed.models.document import ReferenceEntry, StructuredDocument
from citation_needed.models.extraction import ExtractionResult
from citation_needed.models.resolution import CitationResolution, IdentityBasis


def _norm_doi(doi: str) -> str:
    value = doi.strip()
    value = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", value, flags=re.IGNORECASE)
    return value.lower().rstrip(".,;:)]}")


def _paper_id(entry: ReferenceEntry) -> tuple[str | None, IdentityBasis]:
    if entry.doi:
        doi = _norm_doi(entry.doi)
        return f"doi:{doi}", IdentityBasis.DOI
    if entry.url:
        digest = hashlib.sha1(entry.url.strip().encode("utf-8")).hexdigest()[:16]
        return f"url:{digest}", IdentityBasis.URL
    if entry.title and entry.year:
        payload = f"{entry.title.strip().lower()}|{entry.year}"
        digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]
        return f"bib:{digest}", IdentityBasis.BIBLIOGRAPHIC_METADATA
    return None, IdentityBasis.RAW_REFERENCE


def resolve_citation_relation(
    relation: CitationRelation,
    references: list[ReferenceEntry],
) -> CitationResolution:
    matches = [r for r in references if r.reference_number == relation.reference_number]

    if not matches:
        return CitationResolution(
            relation_id=relation.id,
            source_paper_id=relation.source_paper_id,
            reference_number=relation.reference_number,
            status=ResolutionStatus.UNRESOLVED,
            warnings=["No bibliography entry matched the in-text reference number."],
        )

    if len(matches) > 1:
        return CitationResolution(
            relation_id=relation.id,
            source_paper_id=relation.source_paper_id,
            reference_number=relation.reference_number,
            status=ResolutionStatus.UNRESOLVED,
            warnings=["Multiple bibliography entries share the same reference number."],
        )

    entry = matches[0]
    cited_paper_id, basis = _paper_id(entry)
    status = (
        ResolutionStatus.RESOLVED
        if basis in {IdentityBasis.DOI, IdentityBasis.URL, IdentityBasis.BIBLIOGRAPHIC_METADATA}
        else ResolutionStatus.PARTIALLY_RESOLVED
    )

    return CitationResolution(
        relation_id=relation.id,
        source_paper_id=relation.source_paper_id,
        reference_number=relation.reference_number,
        status=status,
        reference_entry=entry,
        cited_paper_id=cited_paper_id,
        identity_basis=basis,
        warnings=[] if status == ResolutionStatus.RESOLVED else [
            "Bibliography entry found, but no canonical source identifier is available yet."
        ],
    )


def resolve_extraction(
    extraction: ExtractionResult,
    document: StructuredDocument,
) -> list[CitationResolution]:
    if extraction.paper_id != document.paper_id:
        raise ValueError("ExtractionResult and StructuredDocument must refer to the same paper_id.")

    return [
        resolve_citation_relation(relation, document.references)
        for relation in extraction.citation_relations
    ]
