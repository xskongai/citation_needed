from citation_needed.models import Completeness, InternalConsistency, MeasurementAppropriateness, SourceAssessmentInput, SourceAssessmentRationale, SourceContextScope, SourceEvidenceDirectness, SourceOriginality, SourceRole
from citation_needed.source_assessment.policy import apply_scope_guards, derive_source_originality
from citation_needed.source_assessment.semantic_schema import SemanticSourceAssessmentOutput

def fixture():
    return SemanticSourceAssessmentOutput(evidence_directness=SourceEvidenceDirectness.DIRECT_MEASUREMENT,method_completeness=Completeness.INSUFFICIENT,measurement_appropriateness=MeasurementAppropriateness.UNKNOWN,reporting_completeness=Completeness.INSUFFICIENT,internal_consistency=InternalConsistency.CONSISTENT,factor_rationale=SourceAssessmentRationale(evidence_directness="x",method_completeness="x",measurement_appropriateness="x",reporting_completeness="x",source_originality="x",internal_consistency="x"),rationale="x")
def test_excerpt_scope_forces_unknown_not_negative():
    out=apply_scope_guards(fixture(),SourceAssessmentInput(source_paper_id="p",context_scope=SourceContextScope.EXCERPT_ONLY)); assert out.method_completeness==Completeness.UNKNOWN; assert out.reporting_completeness==Completeness.UNKNOWN; assert out.internal_consistency==InternalConsistency.UNKNOWN
def test_relevant_sections_cannot_claim_global_consistency():
    out=apply_scope_guards(fixture(),SourceAssessmentInput(source_paper_id="p",context_scope=SourceContextScope.RELEVANT_SECTIONS)); assert out.internal_consistency==InternalConsistency.UNKNOWN
def test_relevant_sections_preserve_conflict():
    x=fixture(); x.internal_consistency=InternalConsistency.CONFLICTED; out=apply_scope_guards(x,SourceAssessmentInput(source_paper_id="p",context_scope=SourceContextScope.RELEVANT_SECTIONS)); assert out.internal_consistency==InternalConsistency.CONFLICTED
def test_originality_owned_by_provenance():
    assert derive_source_originality(SourceRole.PRIMARY_STUDY)==SourceOriginality.PRIMARY; assert derive_source_originality(SourceRole.SECONDARY_SOURCE)==SourceOriginality.SECONDARY; assert derive_source_originality(SourceRole.UNKNOWN)==SourceOriginality.UNCLEAR
