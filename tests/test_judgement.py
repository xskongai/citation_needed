import json
from pathlib import Path

from citation_needed.judgement import judge
from citation_needed.models import Assertion, CitationRelation, Evidence


ROOT = Path(__file__).resolve().parents[1]


def test_golden_smoke_case():
    claim_payload = json.loads((ROOT / "examples" / "claim.json").read_text())
    evidence_payload = json.loads((ROOT / "examples" / "evidence.json").read_text())

    assertion = Assertion.model_validate(claim_payload["assertion"])
    citation = CitationRelation.model_validate(claim_payload["citation_relation"])
    evidence = [Evidence.model_validate(x) for x in evidence_payload["evidence"]]

    result = judge(assertion, citation, evidence)

    assert result.relevance.value == "RELEVANT"
    assert result.support.value in {"SUPPORTED", "PARTIALLY_SUPPORTED"}
    assert result.reliability.value in {"HIGH", "MODERATE"}
    assert result.evidence_ids == ["e_001"]
