from citation_needed.judgement.openai_judge import _build_payload
from citation_needed.models import Assertion, CitationRelation, Evidence


def test_internal_reliability_hints_are_not_sent_to_semantic_model():
    assertion = Assertion.model_validate({
        "id": "a",
        "text": "X improves Y [1].",
        "normalized_claim": "X improves Y",
        "paper_id": "p1",
        "location": {"page": 1},
        "citation_ids": ["c"],
    })
    citation = CitationRelation.model_validate({
        "id": "c",
        "assertion_id": "a",
        "source_paper_id": "p1",
        "cited_paper_id": "p2",
        "reference_number": "1",
        "citation_context": "X improves Y [1].",
    })
    evidence = Evidence.model_validate({
        "id": "e",
        "citation_relation_id": "c",
        "source_paper_id": "p2",
        "content": "X increased Y in this experiment.",
        "provenance": {"paper_id": "p2", "location": {"page": 2}},
        "experimental_context": {
            "temperature": "25 C",
            "_reliability": {"context_match": "MATCH"},
        },
    })

    payload = _build_payload(assertion, citation, [evidence])
    ctx = payload["evidence"][0]["experimental_context"]
    assert ctx == {"temperature": "25 C"}
