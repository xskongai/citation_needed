#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from citation_needed.acquisition import acquire_source
from citation_needed.models import CitationResolution


def load_resolution(path: Path) -> CitationResolution:
    payload = json.loads(path.read_text())
    # Accept either a bare resolution or one report item from run_resolution_suite.
    if isinstance(payload, dict) and isinstance(payload.get("result"), dict):
        payload = payload["result"]
    return CitationResolution.model_validate(payload)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--resolution", required=True, help="JSON CitationResolution")
    parser.add_argument("--contact-email", default=None, help="Email used for Unpaywall polite API access")
    parser.add_argument("--artifact-dir", default="data/acquired")
    parser.add_argument("--out", default="data/acquisition.json")
    parser.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args()

    resolution = load_resolution(Path(args.resolution))
    result = acquire_source(
        resolution,
        output_dir=args.artifact_dir,
        contact_email=args.contact_email,
        timeout=args.timeout,
    )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result.model_dump(mode="json"), indent=2))
    print(
        f"status={result.status.value} paper_id={result.cited_paper_id} "
        f"artifacts={len(result.artifacts)} abstract={'yes' if result.metadata.abstract else 'no'}"
    )
    for artifact in result.artifacts:
        print(f"  - {artifact.kind.value}: {artifact.local_path} <- {artifact.url}")
    for warning in result.warnings:
        print(f"  ! {warning}")
    print(f"Result written to {out}")


if __name__ == "__main__":
    main()
