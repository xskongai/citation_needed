#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from citation_needed.models import ExtractionResult, StructuredDocument
from citation_needed.resolution import resolve_extraction


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--document', required=True)
    parser.add_argument('--extraction', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()

    document = StructuredDocument.model_validate_json(Path(args.document).read_text())
    extraction = ExtractionResult.model_validate_json(Path(args.extraction).read_text())
    results = resolve_extraction(extraction, document)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps([r.model_dump(mode='json') for r in results], indent=2))

    for r in results:
        print(f"[{r.status.value}] relation={r.relation_id} ref=[{r.reference_number}] basis={r.identity_basis.value} paper_id={r.cited_paper_id}")
        for warning in r.warnings:
            print(f"  - {warning}")
    print(f"Report written to {out}")


if __name__ == '__main__':
    main()
