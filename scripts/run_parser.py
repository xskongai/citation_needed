#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from citation_needed.models import AcquiredSource
from citation_needed.parsing import parse_acquired_source


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True, help='AcquiredSource JSON from v1.9')
    parser.add_argument('--out', required=True)
    args = parser.parse_args()

    source = AcquiredSource.model_validate_json(Path(args.source).read_text())
    result = parse_acquired_source(source)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result.model_dump(mode='json'), indent=2))

    n_sections = len(result.document.sections) if result.document else 0
    n_refs = len(result.document.references) if result.document else 0
    print(f"[{result.status.value}] sections={n_sections} references={n_refs} kind={result.artifact_kind.value if result.artifact_kind else 'none'}")
    for w in result.warnings:
        print(f"  - {w}")
    print(f"Report written to {out}")


if __name__ == '__main__':
    main()
