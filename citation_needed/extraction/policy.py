from __future__ import annotations

from citation_needed.models import CitationPurpose, FollowPriority


_HIGH = {
    CitationPurpose.METHOD,
    CitationPurpose.PARAMETER,
    CitationPurpose.CONTRADICTION,
}
_MEDIUM = {
    CitationPurpose.RESULT,
    CitationPurpose.SUPPORT,
    CitationPurpose.COMPARISON,
}
_LOW = {
    CitationPurpose.BACKGROUND,
    CitationPurpose.THEORY,
}


def follow_priority_for_purpose(purpose: CitationPurpose) -> FollowPriority:
    """Deterministic v1 traversal prior.

    This is intentionally not an LLM judgement.  It encodes only a coarse
    first-pass priority; later traversal policy can also use unresolved
    dependencies, information need, domain relevance, and cost.
    """
    if purpose in _HIGH:
        return FollowPriority.HIGH
    if purpose in _MEDIUM:
        return FollowPriority.MEDIUM
    if purpose in _LOW:
        return FollowPriority.LOW
    return FollowPriority.MEDIUM
