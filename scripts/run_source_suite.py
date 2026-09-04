#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from citation_needed.models import Evidence, SourceAssessmentInput
from citation_needed.source_assessment import assess_source_openai


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def get_path(obj: dict, path: str):
    cur = obj
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", type=Path, default=ROOT / "examples" / "source_suite.json")
    ap.add_argument("--model", default=None)
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "source_assessment_report.json")
    a = ap.parse_args()

    suite = load(a.suite)
    report = []
    passed = 0

    for case in suite["cases"]:
        src = SourceAssessmentInput.model_validate(load(ROOT / case["source"]))
        ev = [Evidence.model_validate(x) for x in load(ROOT / case["evidence"])["evidence"]]
        r = assess_source_openai(src, ev, model=a.model)
        d = r.model_dump(mode="json")
        issues = []

        for key, allowed in case["expected"].items():
            allowed = allowed if isinstance(allowed, list) else [allowed]
            got = get_path(d, key)
            if got not in allowed:
                issues.append(f"{key}: got {got!r}, expected one of {allowed!r}")

        status = "PASS" if not issues else "REVIEW"
        passed += status == "PASS"
        mt = d["measurement_traceability"]
        print(
            f"[{status}] {case['id']}: "
            f"basis={d['evidence_basis']} "
            f"method={d['method_completeness']} "
            f"measurement=({mt['method_status']}, {mt['target_link']}, {mt['appropriateness']}) "
            f"reporting={d['reporting_completeness']} "
            f"originality={d['source_originality']} "
            f"consistency={d['internal_consistency']}"
        )
        for issue in issues:
            print("  - " + issue)
        report.append({"case": case["id"], "status": status, "issues": issues, "result": d})

    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n{passed}/{len(suite['cases'])} cases matched the declared expectations.")
    print(f"Report written to {a.out}")


if __name__ == "__main__":
    main()
