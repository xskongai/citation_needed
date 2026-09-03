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
        method_completeness=enum_or(Completeness.PARTIAL, Completeness, "method_completeness"),
        characterization_quality=enum_or(
            CharacterisationQuality.NA,
            CharacterisationQuality,
            "characterization_quality",
        ),
        context_match=enum_or(ContextMatch.UNKNOWN, ContextMatch, "context_match"),
        reproducibility_evidence=enum_or(Presence.UNKNOWN, Presence, "reproducibility_evidence"),
        reporting_clarity=enum_or(ReportingClarity.PARTIAL, ReportingClarity, "reporting_clarity"),
    )


def _reliability_from_factors(f: ReliabilityFactors, evidence: list[Evidence]) -> ReliabilityJudgement:
    if any(ev.epistemic_state in {EvidenceState.UNRESOLVED, EvidenceState.SOURCE_UNAVAILABLE} for ev in evidence):
        return ReliabilityJudgement.UNRESOLVED

    score = 0
    score += {EvidenceDirectness.DIRECT: 2, EvidenceDirectness.INDIRECT: 0, EvidenceDirectness.UNCLEAR: -1}[f.evidence_directness]
    score += {SourceOriginality.PRIMARY: 1, SourceOriginality.SECONDARY: -1, SourceOriginality.UNCLEAR: 0}[f.source_originality]
    score += {Completeness.SUFFICIENT: 2, Completeness.PARTIAL: 0, Completeness.INSUFFICIENT: -2}[f.method_completeness]
    score += {
        CharacterisationQuality.SUFFICIENT: 2,
        CharacterisationQuality.PARTIAL: 0,
        CharacterisationQuality.INSUFFICIENT: -2,
        CharacterisationQuality.NA: 0,
    }[f.characterization_quality]
    score += {ContextMatch.MATCH: 2, ContextMatch.PARTIAL_MATCH: 0, ContextMatch.MISMATCH: -2, ContextMatch.UNKNOWN: -1}[f.context_match]
    score += {Presence.PRESENT: 1, Presence.ABSENT: -1, Presence.UNKNOWN: 0}[f.reproducibility_evidence]
    score += {ReportingClarity.CLEAR: 1, ReportingClarity.PARTIAL: 0, ReportingClarity.UNCLEAR: -1}[f.reporting_clarity]

    if score >= 7:
        return ReliabilityJudgement.HIGH
    if score >= 2:
        return ReliabilityJudgement.MODERATE
    return ReliabilityJudgement.LOW


def _uncertainties(f: ReliabilityFactors, evidence: list[Evidence]) -> list[str]:
    out: list[str] = []
    if f.evidence_directness != EvidenceDirectness.DIRECT:
        out.append("Evidence is not clearly direct experimental support.")
    if f.source_originality != SourceOriginality.PRIMARY:
        out.append("Primary-source status is not established.")
    if f.method_completeness != Completeness.SUFFICIENT:
        out.append("Method reporting is incomplete or only partially assessed.")
    if f.context_match != ContextMatch.MATCH:
        out.append("Experimental/context match is incomplete or unknown.")
    if f.reproducibility_evidence != Presence.PRESENT:
        out.append("Independent reproducibility evidence is absent or unknown.")
    if any(ev.epistemic_state == EvidenceState.INFERRED for ev in evidence):
        out.append("At least one evidence item is an AI inference rather than explicitly reported information.")
    return out


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
    )
