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
from citation_needed.models import Assertion, CitationRelation, Evidence


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def check(result: dict, expected: dict) -> tuple[bool, list[str]]:
    failures: list[str] = []
    factor = result.get("reliability_factors", {})
    actuals = {
        "relevance": result.get("relevance"),
        "support": result.get("support"),
        "context_match": factor.get("context_match"),
        "source_originality": factor.get("source_originality"),
    }
    for key, allowed in expected.items():
        actual = actuals.get(key)
        if actual not in allowed:
            failures.append(f"{key}: got {actual!r}, expected one of {allowed}")
    return not failures, failures


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Citation Needed semantic adversarial suite")
    parser.add_argument("--model", default=None, help="Hosted model override")
    parser.add_argument("--suite", type=Path, default=ROOT / "examples" / "adversarial_suite.json")
    parser.add_argument("--out", type=Path, default=None, help="Optional JSON report path")
    args = parser.parse_args()

    suite = load_json(args.suite)
    base = args.suite.parent
    report: list[dict] = []

    for case in suite["cases"]:
        claim_payload = load_json(base / case["claim"])
        evidence_payload = load_json(base / case["evidence"])
        assertion = Assertion.model_validate(claim_payload["assertion"])
        citation = CitationRelation.model_validate(claim_payload["citation_relation"])
        evidence = [Evidence.model_validate(x) for x in evidence_payload["evidence"]]

        result = judge_openai(assertion, citation, evidence, model=args.model)
        dumped = result.model_dump(mode="json")
        passed, failures = check(dumped, case["expected"])
        report.append({
            "case": case["name"],
            "passed": passed,
            "failures": failures,
            "expected": case["expected"],
            "result": dumped,
        })
        status = "PASS" if passed else "REVIEW"
        print(f"[{status}] {case['name']}: relevance={dumped['relevance']} support={dumped['support']} reliability={dumped['reliability']}")
        if failures:
            for failure in failures:
                print(f"  - {failure}")

    passed_count = sum(1 for x in report if x["passed"])
    print(f"\n{passed_count}/{len(report)} cases matched the declared expectations.")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps({"cases": report}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Report written to {args.out}")


if __name__ == "__main__":
    main()
