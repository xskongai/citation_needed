from __future__ import annotations

from pydantic import BaseModel, Field

from .source import SourceLocation


class DocumentSection(BaseModel):
    """A parser-neutral section of a scientific document.

    v1.6 intentionally starts from structured text rather than PDF bytes.  The
    eventual PDF parser only needs to produce this contract.
    """

    id: str
    heading: str | None = None
    text: str = Field(min_length=1)
    location: SourceLocation = Field(default_factory=SourceLocation)


class ReferenceEntry(BaseModel):
    reference_number: str = Field(min_length=1)
    raw_text: str = Field(min_length=1)
    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    year: int | None = Field(default=None, ge=1800, le=2200)
    venue: str | None = None
    doi: str | None = None
    url: str | None = None


class StructuredDocument(BaseModel):
    paper_id: str
    title: str | None = None
    sections: list[DocumentSection] = Field(default_factory=list)
    references: list[ReferenceEntry] = Field(default_factory=list)
