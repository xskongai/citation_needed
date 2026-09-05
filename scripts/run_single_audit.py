from __future__ import annotations

import argparse
import json
from pathlib import Path

from citation_needed.models import ArtifactKind, SourceContextScope, SourceRole
from citation_needed.pipeline import audit_single_citation_from_artifact


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one end-to-end citation audit from a local Paper A artifact.")
    parser.add_argument("paper_a", type=Path)
    parser.add_argument("--kind", choices=[k.value for k in ArtifactKind], default="PDF")
    parser.add_argument("--paper-id", required=True)
    parser.add_argument("--title")
    parser.add_argument("--reference-number")
    parser.add_argument("--relation-id")
    parser.add_argument("--context-contains", help="Substring used to disambiguate repeated uses of the same reference number.")
    parser.add_argument("--source-role", choices=[r.value for r in SourceRole], default=SourceRole.UNKNOWN.value)
    parser.add_argument("--context-scope", choices=[s.value for s in SourceContextScope], default=SourceContextScope.RELEVANT_SECTIONS.value)
    parser.add_argument("--model")
    parser.add_argument("--contact-email")
    parser.add_argument("--acquired-dir", default="data/acquired")
    parser.add_argument("--out", default="data/single_citation_audit.json")
    args = parser.parse_args()

    result = audit_single_citation_from_artifact(
        args.paper_a,
        paper_a_kind=ArtifactKind(args.kind),
        paper_a_id=args.paper_id,
        paper_a_title=args.title,
        reference_number=args.reference_number,
        relation_id=args.relation_id,
        citation_context_contains=args.context_contains,
        source_role=SourceRole(args.source_role),
        context_scope=SourceContextScope(args.context_scope),
        model=args.model,
        contact_email=args.contact_email,
        acquisition_output_dir=args.acquired_dir,
    )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))

    print(
        f"status={result.status.value} ref=[{result.citation_relation.reference_number}] "
        f"acquisition={result.acquisition.status.value} parse={result.parse_result.status.value} "
        f"retrieval={result.retrieval.status.value} support={result.relation_judgement.support.value} "
        f"reliability={result.audit_result.reliability.level.value}"
    )
    print(f"Report written to {out}")


if __name__ == "__main__":
    main()
