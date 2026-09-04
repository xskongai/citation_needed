from __future__ import annotations

from pydantic import BaseModel, Field

from .assertion import Assertion
from .citation import CitationRelation


class ExtractionResult(BaseModel):
    paper_id: str
    assertions: list[Assertion] = Field(default_factory=list)
    citation_relations: list[CitationRelation] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    extractor_backend: str = "openai-responses"
    extractor_model: str | None = None
