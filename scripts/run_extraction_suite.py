from __future__ import annotations

import argparse
import json
from pathlib import Path

from citation_needed.extraction import extract_citation_assertions_openai
from citation_needed.models import StructuredDocument


def main() -> None:
    parser = argparse.ArgumentParser(description="Run hosted citation-extraction semantic cases.")
    parser.add_argument("--suite", default="examples/extraction_suite.json")
    parser.add_argument("--model", default=None)
    parser.add_argument("--out", default="data/extraction_report.json")
    args = parser.parse_args()

    cases = json.loads(Path(args.suite).read_text())
    report = []
    passed = 0

    for case in cases:
        doc = StructuredDocument.model_validate_json(Path(case["document"]).read_text())
        result = extract_citation_assertions_openai(doc, model=args.model)
        issues: list[str] = []

        n = len(result.assertions)
        if "expected_assertions_min" in case and n < case["expected_assertions_min"]:
            issues.append(f"assertions: got {n}, expected >= {case['expected_assertions_min']}")
        if "expected_assertions_max" in case and n > case["expected_assertions_max"]:
            issues.append(f"assertions: got {n}, expected <= {case['expected_assertions_max']}")

        by_ref: dict[str, list] = {}
        for rel in result.citation_relations:
            by_ref.setdefault(rel.reference_number, []).append(rel)

        actual_refs = sorted(by_ref.keys(), key=lambda x: int(x) if x.isdigit() else x)
        expected_refs = sorted(case.get("expected_refs", []), key=lambda x: int(x) if x.isdigit() else x)
        if actual_refs != expected_refs:
            issues.append(f"refs: got {actual_refs}, expected {expected_refs}")

        for ref, allowed in case.get("expected_purpose_by_ref", {}).items():
            vals = {rel.purpose.value for rel in by_ref.get(ref, [])}
            if not vals or vals.isdisjoint(set(allowed)):
                issues.append(f"purpose[{ref}]: got {sorted(vals)}, expected one of {allowed}")

        for ref, allowed in case.get("expected_priority_by_ref", {}).items():
            vals = {rel.follow_priority.value for rel in by_ref.get(ref, [])}
            if not vals or vals.isdisjoint(set(allowed)):
                issues.append(f"priority[{ref}]: got {sorted(vals)}, expected one of {allowed}")

        ok = not issues
        passed += int(ok)
        status = "PASS" if ok else "REVIEW"
        summary = ", ".join(
            f"[{r.reference_number}]={r.purpose.value}/{r.follow_priority.value}"
            for r in result.citation_relations
        ) or "no citation-bearing assertions"
        print(f"[{status}] {case['name']}: assertions={n} relations={len(result.citation_relations)} {summary}")
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
