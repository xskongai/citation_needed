#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from citation_needed.judgement import judge_openai
from citation_needed.models import Assertion, CitationRelation, Evidence, SourceAssessmentInput
from citation_needed.reliability import build_audit_result
from citation_needed.source_assessment import assess_source_openai


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", type=Path, default=ROOT / "examples" / "reliability_suite.json")
    ap.add_argument("--model", default=None)
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "reliability_report.json")
    a = ap.parse_args()

    suite = load(a.suite)
    report = []
    passed = 0

    for case in suite["cases"]:
        claim_payload = load(ROOT / case["claim"])
        assertion = Assertion.model_validate(claim_payload["assertion"])
        citation = CitationRelation.model_validate(claim_payload["citation_relation"])
        evidence = [Evidence.model_validate(x) for x in load(ROOT / case["evidence"])["evidence"]]
        source_input = SourceAssessmentInput.model_validate(load(ROOT / case["source"]))

        relation = judge_openai(assertion, citation, evidence, model=a.model)
        source = assess_source_openai(source_input, evidence, model=a.model)
        audit = build_audit_result(relation, source, evidence)

        expected = case["expected"]
        issues = []

        checks = {
            "relation_support": relation.support.value,
            "source_originality": source.source_originality.value,
            "source_consistency": source.internal_consistency.value,
            "condition_match": relation.alignment.condition_match.value,
            "reliability": audit.reliability.level.value,
        }

        for key, allowed in expected.items():
            allowed = allowed if isinstance(allowed, list) else [allowed]
            got = checks.get(key)
            if got not in allowed:
                issues.append(f"{key}: got {got!r}, expected one of {allowed!r}")

        status = "PASS" if not issues else "REVIEW"
        passed += status == "PASS"
        print(
            f"[{status}] {case['id']}: "
            f"support={relation.support.value} "
            f"source=({source.evidence_basis.value}, {source.source_originality.value}, {source.internal_consistency.value}) "
            f"reliability={audit.reliability.level.value}"
        )
        for issue in issues:
            print("  - " + issue)

        report.append({
            "case": case["id"],
            "status": status,
            "issues": issues,
            "audit": audit.model_dump(mode="json"),
        })

    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n{passed}/{len(suite['cases'])} cases matched the declared expectations.")
    print(f"Report written to {a.out}")


if __name__ == "__main__":
    main()
