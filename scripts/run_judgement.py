#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from citation_needed.judgement import judge
from citation_needed.models import Assertion, CitationRelation, Evidence


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    parser = argparse.ArgumentParser(description="Citation Needed v0 judgement smoke test")
    parser.add_argument("--claim", required=True, type=Path, help="JSON containing assertion + citation_relation")
    parser.add_argument("--evidence", required=True, type=Path, help="JSON containing an evidence array")
    parser.add_argument("--out", type=Path, default=None, help="Optional output JSON path")
    args = parser.parse_args()

    claim_payload = load_json(args.claim)
    evidence_payload = load_json(args.evidence)

    assertion = Assertion.model_validate(claim_payload["assertion"])
    citation = CitationRelation.model_validate(claim_payload["citation_relation"])
    evidence = [Evidence.model_validate(item) for item in evidence_payload["evidence"]]

    result = judge(assertion, citation, evidence)
    rendered = result.model_dump_json(indent=2)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
