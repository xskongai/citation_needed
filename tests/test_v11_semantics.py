import json
from pathlib import Path

from citation_needed.judgement.openai_judge import _derive_source_originality
from citation_needed.models import Evidence, SourceOriginality

ROOT = Path(__file__).resolve().parents[1]


def _load_evidence(name: str) -> list[Evidence]:
    payload = json.loads((ROOT / "examples" / name).read_text())
    return [Evidence.model_validate(x) for x in payload["evidence"]]


def test_primary_source_is_derived_from_provenance():
    evidence = _load_evidence("evidence_contradiction.json")
    assert _derive_source_originality(evidence) == SourceOriginality.PRIMARY


def test_secondary_source_is_derived_from_provenance():
    evidence = _load_evidence("evidence_secondary.json")
    assert _derive_source_originality(evidence) == SourceOriginality.SECONDARY


def test_adversarial_suite_files_validate():
    suite = json.loads((ROOT / "examples" / "adversarial_suite.json").read_text())
    assert len(suite["cases"]) == 5
    for case in suite["cases"]:
        claim_path = ROOT / "examples" / case["claim"]
        evidence_path = ROOT / "examples" / case["evidence"]
        assert claim_path.exists()
        assert evidence_path.exists()
        evidence = _load_evidence(case["evidence"])
        assert evidence
