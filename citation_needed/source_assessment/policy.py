from __future__ import annotations
from citation_needed.models import Completeness, InternalConsistency, SourceAssessmentInput, SourceContextScope, SourceOriginality, SourceRole
from .semantic_schema import SemanticSourceAssessmentOutput

def derive_source_originality(role: SourceRole) -> SourceOriginality:
    if role == SourceRole.PRIMARY_STUDY:
        return SourceOriginality.PRIMARY
    if role == SourceRole.SECONDARY_SOURCE:
        return SourceOriginality.SECONDARY
    return SourceOriginality.UNCLEAR

def apply_scope_guards(parsed: SemanticSourceAssessmentOutput, source_input: SourceAssessmentInput) -> SemanticSourceAssessmentOutput:
    if source_input.context_scope == SourceContextScope.EXCERPT_ONLY:
        parsed.method_completeness = Completeness.UNKNOWN
        parsed.reporting_completeness = Completeness.UNKNOWN
        parsed.factor_rationale.method_completeness = "Not assessed: only an excerpt was supplied, so source-level method completeness cannot be established."
        parsed.factor_rationale.reporting_completeness = "Not assessed: only an excerpt was supplied, so source-level reporting completeness cannot be established."
        if parsed.internal_consistency == InternalConsistency.CONSISTENT:
            parsed.internal_consistency = InternalConsistency.UNKNOWN
            parsed.factor_rationale.internal_consistency = "Not established: an excerpt cannot demonstrate source-wide internal consistency."
    elif source_input.context_scope == SourceContextScope.RELEVANT_SECTIONS and parsed.internal_consistency == InternalConsistency.CONSISTENT:
        parsed.internal_consistency = InternalConsistency.UNKNOWN
        parsed.factor_rationale.internal_consistency = "No conflict was established in the supplied relevant sections, but the full source was not supplied."
    return parsed
