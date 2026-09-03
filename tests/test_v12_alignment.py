from citation_needed.judgement.policy import overall_context_match
from citation_needed.models import AlignmentAssessment, ContextMatch


def test_condition_only_mismatch_is_partial_overall():
    alignment = AlignmentAssessment(
        subject_match=ContextMatch.MATCH,
        outcome_match=ContextMatch.MATCH,
        condition_match=ContextMatch.MISMATCH,
        condition_mismatches=["claim: room temperature; evidence: 145 C"],
    )
    assert overall_context_match(alignment) == ContextMatch.PARTIAL_MATCH


def test_subject_mismatch_is_overall_mismatch():
    alignment = AlignmentAssessment(
        subject_match=ContextMatch.MISMATCH,
        outcome_match=ContextMatch.MATCH,
        condition_match=ContextMatch.MATCH,
    )
    assert overall_context_match(alignment) == ContextMatch.MISMATCH


def test_all_alignment_dimensions_match():
    alignment = AlignmentAssessment(
        subject_match=ContextMatch.MATCH,
        outcome_match=ContextMatch.MATCH,
        condition_match=ContextMatch.MATCH,
    )
    assert overall_context_match(alignment) == ContextMatch.MATCH
