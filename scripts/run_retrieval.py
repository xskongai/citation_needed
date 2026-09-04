#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from citation_needed.models import Assertion, CitationRelation, SourceRole, StructuredDocument
from citation_needed.retrieval import retrieve_evidence_openai


def main() -> None:
    parser = argparse.ArgumentParser(description="Retrieve evidence from a supplied cited source document.")
    parser.add_argument("--assertion", required=True)
    parser.add_argument("--citation", required=True)
    parser.add_argument("--source-document", required=True)
    parser.add_argument("--source-role", default="UNKNOWN", choices=[r.value for r in SourceRole])
    parser.add_argument("--source-doi", default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    assertion = Assertion.model_validate_json(Path(args.assertion).read_text())
    relation = CitationRelation.model_validate_json(Path(args.citation).read_text())
    source_document = StructuredDocument.model_validate_json(Path(args.source_document).read_text())

    result = retrieve_evidence_openai(
        assertion,
        relation,
        source_document,
        source_role=SourceRole(args.source_role),
        source_doi=args.source_doi,
        model=args.model,
    )
    output = result.model_dump(mode="json")
    text = json.dumps(output, ensure_ascii=False, indent=2)
    print(text)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n")


if __name__ == "__main__":
    main()
