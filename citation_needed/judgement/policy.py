from __future__ import annotations

from citation_needed.models import (
    CharacterisationQuality,
    Completeness,
    ContextMatch,
    Evidence,
    EvidenceDirectness,
    EvidenceState,
    Presence,
    ReliabilityFactors,
    ReliabilityJudgement,
    ReportingClarity,
    SourceOriginality,
)


def reliability_from_factors(
    factors: ReliabilityFactors,
    evidence: list[Evidence],
) -> ReliabilityJudgement:
    """Aggregate explicit factors into a categorical reliability judgement.

    Unknown/not-assessed source-level factors are deliberately neutral rather
    than treated as evidence of poor quality. This prevents an excerpt-level
    evidence package from being mistaken for a complete assessment of a paper.
    """
    if any(
        ev.epistemic_state in {EvidenceState.UNRESOLVED, EvidenceState.SOURCE_UNAVAILABLE}
        for ev in evidence
    ):
        return ReliabilityJudgement.UNRESOLVED

    score = 0
    score += {
        EvidenceDirectness.DIRECT: 2,
        EvidenceDirectness.INDIRECT: 0,
        EvidenceDirectness.UNCLEAR: -1,
    }[factors.evidence_directness]
    score += {
        SourceOriginality.PRIMARY: 1,
        SourceOriginality.SECONDARY: -1,
        SourceOriginality.UNCLEAR: 0,
    }[factors.source_originality]
    score += {
        Completeness.SUFFICIENT: 2,
        Completeness.PARTIAL: 0,
        Completeness.INSUFFICIENT: -2,
        Completeness.UNKNOWN: 0,
    }[factors.method_completeness]
    score += {
        CharacterisationQuality.SUFFICIENT: 2,
        CharacterisationQuality.PARTIAL: 0,
        CharacterisationQuality.INSUFFICIENT: -2,
        CharacterisationQuality.UNKNOWN: 0,
        CharacterisationQuality.NA: 0,
    }[factors.characterization_quality]
    score += {
        ContextMatch.MATCH: 2,
        ContextMatch.PARTIAL_MATCH: 0,
        ContextMatch.MISMATCH: -2,
        ContextMatch.UNKNOWN: -1,
    }[factors.context_match]
    score += {
        Presence.PRESENT: 1,
        Presence.ABSENT: -1,
        Presence.UNKNOWN: 0,
    }[factors.reproducibility_evidence]
    score += {
        ReportingClarity.CLEAR: 1,
        ReportingClarity.PARTIAL: 0,
        ReportingClarity.UNCLEAR: -1,
    }[factors.reporting_clarity]

    if score >= 7:
        return ReliabilityJudgement.HIGH
    if score >= 2:
        return ReliabilityJudgement.MODERATE
    return ReliabilityJudgement.LOW


def policy_uncertainties(
    factors: ReliabilityFactors,
    evidence: list[Evidence],
) -> list[str]:
    out: list[str] = []
    if factors.evidence_directness != EvidenceDirectness.DIRECT:
        out.append("Evidence is not clearly direct support for the evaluated claim.")
    if factors.source_originality == SourceOriginality.UNCLEAR:
        out.append("Primary-vs-secondary source status is not established by provenance.")
    elif factors.source_originality == SourceOriginality.SECONDARY:
        out.append("The supplied evidence is secondary; the original source should be followed where possible.")
    if factors.method_completeness == Completeness.UNKNOWN:
        out.append("Method completeness was not assessed from the supplied material.")
    elif factors.method_completeness != Completeness.SUFFICIENT:
        out.append("Method reporting is incomplete or only partially assessed.")
    if factors.characterization_quality == CharacterisationQuality.UNKNOWN:
        out.append("Characterization/measurement quality was not assessed from the supplied material.")
    if factors.context_match != ContextMatch.MATCH:
        out.append("Experimental/context match is incomplete, mismatched, or unknown.")
    if factors.reproducibility_evidence == Presence.UNKNOWN:
        out.append("Independent reproducibility evidence is unknown from the supplied material.")
    elif factors.reproducibility_evidence == Presence.ABSENT:
        out.append("Independent reproducibility is explicitly absent in the supplied evidence.")
    if any(ev.epistemic_state == EvidenceState.INFERRED for ev in evidence):
        out.append(
            "At least one evidence item is an AI inference rather than explicitly reported information."
        )
    return out


def merge_uncertainties(*groups: list[str]) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for group in groups:
        for item in group:
            cleaned = item.strip()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                merged.append(cleaned)
    return merged
