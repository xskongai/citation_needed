from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from .acquisition import ArtifactKind
from .document import StructuredDocument


class ParseStatus(str, Enum):
    FULL_TEXT_PARSED = "FULL_TEXT_PARSED"
    ABSTRACT_ONLY_PARSED = "ABSTRACT_ONLY_PARSED"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"
    PARSE_FAILED = "PARSE_FAILED"


class SourceParseResult(BaseModel):
    relation_id: str
    cited_paper_id: str | None = None
    status: ParseStatus
    artifact_kind: ArtifactKind | None = None
    artifact_path: str | None = None
    document: StructuredDocument | None = None
    warnings: list[str] = Field(default_factory=list)
    parser_backend: str = "citation-needed-source-parser-v1"
