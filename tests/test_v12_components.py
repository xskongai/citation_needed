from citation_needed.judgement.openai_judge import _project_component_lists
from citation_needed.judgement.semantic_schema import SemanticJudgeOutput
from citation_needed.models import (
    AlignmentAssessment,
    ClaimComponentAssessment,
    ContextMatch,
    ReliabilityFactorRationale,
    ReliabilityFactors,
    RelevanceJudgement,
    SupportJudgement,
)


def _factor_rationale() -> ReliabilityFactorRationale:
    return ReliabilityFactorRationale(
        evidence_directness="x",
        source_originality="x",
        method_completeness="x",
        characterization_quality="x",
        context_match="x",
        reproducibility_evidence="x",
        reporting_clarity="x",
    )


def test_component_projection_preserves_supported_unsupported_contradicted():
    parsed = SemanticJudgeOutput(
        relevance=RelevanceJudgement.RELEVANT,
        support=SupportJudgement.PARTIALLY_SUPPORTED,
        claim_components=[
            ClaimComponentAssessment(
                component="Method X produced particles below 10 nm under the reported condition.",
                status=SupportJudgement.SUPPORTED,
                rationale="8 nm is reported.",
            ),
            ClaimComponentAssessment(
                component="The method does so reliably across reaction conditions.",
                status=SupportJudgement.INSUFFICIENT_EVIDENCE,
                rationale="Only one condition is supplied.",
            ),
            ClaimComponentAssessment(
                component="The effect is a decrease.",
                status=SupportJudgement.CONTRADICTED,
                rationale="Evidence reports an increase.",
            ),
        ],
        alignment=AlignmentAssessment(
            subject_match=ContextMatch.MATCH,
            outcome_match=ContextMatch.MATCH,
            condition_match=ContextMatch.PARTIAL_MATCH,
        ),
        reliability_factors=ReliabilityFactors(),
        factor_rationale=_factor_rationale(),
        rationale="mixed",
    )
    supported, unsupported, contradicted = _project_component_lists(parsed)
    assert len(supported) == 1
    assert len(unsupported) == 1
    assert len(contradicted) == 1
