from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from .acquisition import AcquiredSource
from .assertion import Assertion
from .audit import CitationAuditResult
from .citation import CitationRelation
from .extraction import ExtractionResult
from .judgement import Judgement
from .parsing import SourceParseResult
from .resolution import CitationResolution
from .retrieval import EvidenceRetrievalResult
from .source_assessment import SourceAssessment


class EndToEndAuditStatus(str, Enum):
    COMPLETE = "COMPLETE"
    UNRESOLVED = "UNRESOLVED"


class SingleCitationAuditTrace(BaseModel):
    """Trace of one complete citation audit across all pipeline stages.

    Every stage remains visible so an unresolved acquisition/retrieval state is
    never collapsed into a negative scientific judgement.
    """

    source_paper_id: str
    extraction: ExtractionResult
    assertion: Assertion
    citation_relation: CitationRelation
    resolution: CitationResolution
    acquisition: AcquiredSource
    parse_result: SourceParseResult
    retrieval: EvidenceRetrievalResult
    relation_judgement: Judgement
    source_assessment: SourceAssessment
    audit_result: CitationAuditResult
    status: EndToEndAuditStatus
    warnings: list[str] = Field(default_factory=list)
    pipeline_version: str = "single-citation-audit-v1"
