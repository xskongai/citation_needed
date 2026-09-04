from __future__ import annotations

from pydantic import BaseModel, Field


class SemanticEvidenceSelection(BaseModel):
    selected_candidate_ids: list[str] = Field(default_factory=list, max_length=3)
    rationale: str
