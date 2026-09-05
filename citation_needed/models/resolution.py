from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from .citation import ResolutionStatus
from .document import ReferenceEntry


class IdentityBasis(str, Enum):
    DOI = "DOI"
    URL = "URL"
    BIBLIOGRAPHIC_METADATA = "BIBLIOGRAPHIC_METADATA"
    RAW_REFERENCE = "RAW_REFERENCE"
    UNKNOWN = "UNKNOWN"


class CitationResolution(BaseModel):
    """Resolution of one in-text citation relation to a bibliography entry.

    Local bibliography matching is separated from remote full-text acquisition.
    v2.1 may conservatively enrich a PARTIALLY_RESOLVED bibliography entry via
    Crossref when a unique title/year/author match is strong enough. RESOLVED
    therefore means a canonical identifier is available from either the supplied
    bibliography or verified metadata enrichment.
    """

    relation_id: str
    source_paper_id: str
    reference_number: str = Field(min_length=1)
    status: ResolutionStatus
    reference_entry: ReferenceEntry | None = None
    cited_paper_id: str | None = None
    identity_basis: IdentityBasis = IdentityBasis.UNKNOWN
    warnings: list[str] = Field(default_factory=list)
