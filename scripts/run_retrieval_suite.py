#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from citation_needed.models import Assertion, CitationRelation, SourceRole, StructuredDocument
from citation_needed.retrieval import retrieve_evidence_openai


def main() -> None:
    parser = argparse.ArgumentParser(description="Run hosted evidence-retrieval semantic cases.")
    parser.add_argument("--suite", default="examples/retrieval_suite.json")
    parser.add_argument("--model", default=None)
    parser.add_argument("--out", default="data/retrieval_report.json")
    args = parser.parse_args()

    cases = json.loads(Path(args.suite).read_text())
    report = []
    passed = 0

    for case in cases:
        document = StructuredDocument.model_validate_json(Path(case["source_document"]).read_text())
        assertion = Assertion.model_validate(case["assertion"])
        relation = CitationRelation.model_validate(case["relation"])
        role = SourceRole(case.get("source_role", "UNKNOWN"))

        result = retrieve_evidence_openai(
            assertion,
            relation,
            document,
            source_role=role,
            model=args.model,
        )

        issues: list[str] = []
        if result.status.value != case["expected_status"]:
            issues.append(
                f"status: got {result.status.value!r}, expected {case['expected_status']!r}"
            )

        n = len(result.evidence)
        if "expected_evidence_min" in case and n < case["expected_evidence_min"]:
            issues.append(f"evidence: got {n}, expected >= {case['expected_evidence_min']}")
        if "expected_evidence_max" in case and n > case["expected_evidence_max"]:
            issues.append(f"evidence: got {n}, expected <= {case['expected_evidence_max']}")

        combined = "\n".join(ev.content for ev in result.evidence)
        for required in case.get("must_include_any", []):
            # must_include_any means each listed cue should occur somewhere in the
            # selected evidence. This keeps tests explicit and auditable.
            if required not in combined:
                issues.append(f"selected evidence did not contain required cue {required!r}")

        ok = not issues
        passed += int(ok)
        status = "PASS" if ok else "REVIEW"
        selected = [
            ev.experimental_context.get("_retrieval_candidate_id", "?")
            for ev in result.evidence
        ]
        print(
            f"[{status}] {case['name']}: status={result.status.value} "
            f"candidates={len(result.candidates)} evidence={len(result.evidence)} "
            f"selected={selected or 'none'}"
        )
        for issue in issues:
            print(f"  - {issue}")

        report.append({
            "case": case["name"],
            "passed": ok,
            "issues": issues,
            "result": result.model_dump(mode="json"),
        })

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(f"\n{passed}/{len(cases)} cases matched the declared expectations.")
    print(f"Report written to {out}")


if __name__ == "__main__":
    main()
