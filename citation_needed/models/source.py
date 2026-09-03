from __future__ import annotations

from pydantic import BaseModel, Field


class SourceLocation(BaseModel):
    """Traceable location of an assertion or evidence item in a source."""

    page: int | None = Field(default=None, ge=1)
    section: str | None = None
    paragraph: int | None = Field(default=None, ge=1)
    figure: str | None = None
    table: str | None = None
    supplementary: str | None = None


class Provenance(BaseModel):
    """Source identity plus exact location. Every Evidence must have this."""

    paper_id: str
    title: str | None = None
    doi: str | None = None
    location: SourceLocation
