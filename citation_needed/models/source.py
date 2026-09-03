from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class SourceRole(str, Enum):
    """Role of the evidence-bearing source, established by provenance/metadata when known."""

    PRIMARY_STUDY = "PRIMARY_STUDY"
    SECONDARY_SOURCE = "SECONDARY_SOURCE"
    UNKNOWN = "UNKNOWN"


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
    source_role: SourceRole = SourceRole.UNKNOWN
    location: SourceLocation
