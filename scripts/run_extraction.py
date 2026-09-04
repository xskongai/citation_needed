from __future__ import annotations

import argparse
import json
from pathlib import Path

from citation_needed.extraction import extract_citation_assertions_openai
from citation_needed.models import StructuredDocument


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract citation-bearing assertions from structured scientific text.")
    parser.add_argument("--document", required=True)
    parser.add_argument("--model", default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    document = StructuredDocument.model_validate_json(Path(args.document).read_text())
    result = extract_citation_assertions_openai(document, model=args.model)
    output = json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2)
    print(output)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(output + "\n")


if __name__ == "__main__":
    main()
