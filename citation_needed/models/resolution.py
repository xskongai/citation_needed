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

    v1.7 deliberately separates *local bibliography resolution* from remote
    full-text acquisition. RESOLVED means that the source identity has a
    canonical identifier (currently DOI or URL) in the supplied bibliography.
    PARTIALLY_RESOLVED means the numbered bibliography entry was found but no
    canonical identifier is present yet.
    """

    relation_id: str
    source_paper_id: str
    reference_number: str = Field(min_length=1)
    status: ResolutionStatus
    reference_entry: ReferenceEntry | None = None
    cited_paper_id: str | None = None
    identity_basis: IdentityBasis = IdentityBasis.UNKNOWN
    warnings: list[str] = Field(default_factory=list)
