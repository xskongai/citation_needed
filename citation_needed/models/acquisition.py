from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class AcquisitionStatus(str, Enum):
    """State of remote source acquisition.

    These states describe *availability*, not scientific quality.
    """

    FULL_TEXT_AVAILABLE = "FULL_TEXT_AVAILABLE"
    ABSTRACT_ONLY = "ABSTRACT_ONLY"
    METADATA_ONLY = "METADATA_ONLY"
    ACCESS_RESTRICTED = "ACCESS_RESTRICTED"
    NOT_FOUND = "NOT_FOUND"
    ACQUISITION_FAILED = "ACQUISITION_FAILED"
    UNRESOLVED = "UNRESOLVED"


class AcquisitionProvider(str, Enum):
    CROSSREF = "CROSSREF"
    UNPAYWALL = "UNPAYWALL"
    DIRECT_URL = "DIRECT_URL"
    REPOSITORY = "REPOSITORY"
    PUBLISHER = "PUBLISHER"
    UNKNOWN = "UNKNOWN"


class ArtifactKind(str, Enum):
    PDF = "PDF"
    XML = "XML"
    HTML = "HTML"
    TEXT = "TEXT"
    LANDING_PAGE = "LANDING_PAGE"
    UNKNOWN = "UNKNOWN"


class AccessLevel(str, Enum):
    OPEN_ACCESS = "OPEN_ACCESS"
    RESTRICTED = "RESTRICTED"
    UNKNOWN = "UNKNOWN"


class ProviderAttempt(BaseModel):
    provider: AcquisitionProvider
    url: str
    status_code: int | None = None
    outcome: str
    detail: str | None = None


class AcquiredArtifact(BaseModel):
    provider: AcquisitionProvider
    url: str
    kind: ArtifactKind
    media_type: str | None = None
    access_level: AccessLevel = AccessLevel.UNKNOWN
    local_path: str | None = None
    sha256: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)


class AcquiredMetadata(BaseModel):
    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    year: int | None = Field(default=None, ge=1800, le=2200)
    venue: str | None = None
    publisher: str | None = None
    doi: str | None = None
    abstract: str | None = None
    landing_url: str | None = None


class AcquiredSource(BaseModel):
    relation_id: str
    cited_paper_id: str | None = None
    status: AcquisitionStatus
    metadata: AcquiredMetadata = Field(default_factory=AcquiredMetadata)
    artifacts: list[AcquiredArtifact] = Field(default_factory=list)
    discovered_urls: list[str] = Field(default_factory=list)
    provider_attempts: list[ProviderAttempt] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
