from __future__ import annotations

import re
import uuid
from collections.abc import Iterable

from citation_needed.models import (
    Assertion,
    CharacterisationQuality,
    CitationRelation,
    Completeness,
    ContextMatch,
    Evidence,
    EvidenceDirectness,
    EvidenceState,
    Judgement,
    Presence,
    RelevanceJudgement,
    ReliabilityFactors,
    ReliabilityJudgement,
    ReportingClarity,
    SourceOriginality,
    SupportJudgement,
)
from .policy import policy_uncertainties, reliability_from_factors

# This baseline is intentionally conservative and deterministic. It exists to
# validate the data model + end-to-end plumbing, not to serve as the final
# scientific judge. Replace semantic decisions with an evaluated LLM/backend.

_STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "for", "with",
    "by", "as", "is", "are", "was", "were", "be", "been", "being", "that",
    "this", "these", "those", "it", "its", "from", "at", "than", "due",
    "have", "has", "had", "can", "may", "might", "we", "they", "their",
}

_NEGATION_MARKERS = {"not", "no", "without", "failed", "lower", "decrease", "decreased"}


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-zA-Z0-9]+(?:\.[0-9]+)?", text.lower())
    return {w for w in words if len(w) > 1 and w not in _STOPWORDS}


def _coverage(claim: str, evidence: str) -> float:
    c = _tokens(claim)
    e = _tokens(evidence)
    if not c:
        return 0.0
    return len(c & e) / len(c)


def _has_negation(text: str) -> bool:
    toks = _tokens(text)
    return bool(toks & _NEGATION_MARKERS) or "did not" in text.lower()


def _infer_reliability_factors(evidence: list[Evidence]) -> ReliabilityFactors:
    """Read optional structured hints from experimental_context.

    Evidence may include an internal `_reliability` mapping for the v0 smoke test.
    In the real system, these factors should be independently extracted/judged.
    """
    merged: dict[str, str] = {}
    for ev in evidence:
        hints = ev.experimental_context.get("_reliability")
        if isinstance(hints, dict):
            for key, value in hints.items():
                if isinstance(value, str):
                    merged[key] = value

    def enum_or(default, enum_cls, key):
        raw = merged.get(key)
        if raw is None:
            return default
        try:
            return enum_cls(raw)
        except ValueError:
            return default

    return ReliabilityFactors(
        evidence_directness=enum_or(EvidenceDirectness.UNCLEAR, EvidenceDirectness, "evidence_directness"),
        source_originality=enum_or(SourceOriginality.UNCLEAR, SourceOriginality, "source_originality"),
        method_completeness=enum_or(Completeness.UNKNOWN, Completeness, "method_completeness"),
        characterization_quality=enum_or(
            CharacterisationQuality.UNKNOWN,
            CharacterisationQuality,
            "characterization_quality",
        ),
        context_match=enum_or(ContextMatch.UNKNOWN, ContextMatch, "context_match"),
        reproducibility_evidence=enum_or(Presence.UNKNOWN, Presence, "reproducibility_evidence"),
        reporting_clarity=enum_or(ReportingClarity.PARTIAL, ReportingClarity, "reporting_clarity"),
    )


def _reliability_from_factors(f: ReliabilityFactors, evidence: list[Evidence]) -> ReliabilityJudgement:
    return reliability_from_factors(f, evidence)


def _uncertainties(f: ReliabilityFactors, evidence: list[Evidence]) -> list[str]:
    return policy_uncertainties(f, evidence)


def judge(
    assertion: Assertion,
    citation: CitationRelation,
    evidence: Iterable[Evidence],
) -> Judgement:
    evidence = list(evidence)
    usable = [ev for ev in evidence if ev.epistemic_state == EvidenceState.REPORTED]

    if not evidence or not usable:
        factors = _infer_reliability_factors(evidence)
        return Judgement(
            id=f"j_{uuid.uuid4().hex[:10]}",
            assertion_id=assertion.id,
            citation_relation_id=citation.id,
            evidence_ids=[ev.id for ev in evidence],
            relevance=RelevanceJudgement.UNCLEAR,
            support=SupportJudgement.INSUFFICIENT_EVIDENCE,
            reliability=ReliabilityJudgement.UNRESOLVED,
            reliability_factors=factors,
            uncertainty=["No explicitly reported evidence is available for evaluation."],
            rationale="The evidence chain cannot yet be evaluated because no reported evidence item is available.",
            judgement_status="UNRESOLVED",
            judge_backend="deterministic-v0",
        )

    combined = " ".join(ev.content for ev in usable)
    coverage = _coverage(assertion.normalized_claim, combined)

    if coverage >= 0.55:
        relevance = RelevanceJudgement.RELEVANT
    elif coverage >= 0.25:
        relevance = RelevanceJudgement.PARTIALLY_RELEVANT
    else:
        relevance = RelevanceJudgement.IRRELEVANT

    claim_neg = _has_negation(assertion.normalized_claim)
    evidence_neg = _has_negation(combined)

    if relevance == RelevanceJudgement.IRRELEVANT:
        support = SupportJudgement.INSUFFICIENT_EVIDENCE
    elif claim_neg != evidence_neg and coverage >= 0.45:
        support = SupportJudgement.CONTRADICTED
    elif coverage >= 0.75:
        support = SupportJudgement.SUPPORTED
    elif coverage >= 0.35:
        support = SupportJudgement.PARTIALLY_SUPPORTED
    else:
        support = SupportJudgement.INSUFFICIENT_EVIDENCE

    factors = _infer_reliability_factors(usable)
    reliability = _reliability_from_factors(factors, usable)
    uncertainty = _uncertainties(factors, usable)

    rationale = (
        f"Deterministic v0 baseline: normalized-claim token coverage against reported evidence is "
        f"{coverage:.2f}. Relevance and support are provisional smoke-test outputs; reliability is "
        f"derived from explicit factor states rather than a free-form confidence score."
    )

    return Judgement(
        id=f"j_{uuid.uuid4().hex[:10]}",
        assertion_id=assertion.id,
        citation_relation_id=citation.id,
        evidence_ids=[ev.id for ev in evidence],
        relevance=relevance,
        support=support,
        reliability=reliability,
        reliability_factors=factors,
        uncertainty=uncertainty,
        rationale=rationale,
        judge_backend="deterministic-v0",
    )
