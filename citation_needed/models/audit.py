from __future__ import annotations

from pydantic import BaseModel, Field

from .judgement import Judgement, ReliabilityJudgement
from .source_assessment import SourceAssessment


class ReliabilityDecision(BaseModel):
    """Deterministic final reliability decision for one citation audit.

    The level describes how much the system should trust the resulting
    claim-evidence judgement after combining relation-level reasoning with
    source-level evidence quality. It is not an LLM confidence score.
    """

    level: ReliabilityJudgement
    positive_signals: list[str] = Field(default_factory=list)
    caution_signals: list[str] = Field(default_factory=list)
    blocking_signals: list[str] = Field(default_factory=list)
    rationale: str
    policy_version: str = "reliability-v1"


class CitationAuditResult(BaseModel):
    assertion_id: str
    citation_relation_id: str
    evidence_ids: list[str] = Field(default_factory=list)
    relation_judgement: Judgement
    source_assessment: SourceAssessment
    reliability: ReliabilityDecision
    audit_status: str = "COMPLETE"
