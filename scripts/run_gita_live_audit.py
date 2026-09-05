from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from citation_needed.models import ArtifactKind, SourceRole
from citation_needed.pipeline import audit_single_citation_from_artifact


EXPECTED_REF_17_DOI = "10.1039/c3ra47681b"
DEFAULT_CONTEXT = "Different composites with different ratios have already been utilized successfully"
DEFAULT_PAPER_A = Path("papers/MFO-PANI_Gita.pdf")
DEFAULT_CITED_DIR = Path("papers/cited")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a live single-citation audit on Gita Singh et al.'s MnFe2O4@PANI paper, targeting reference [17]."
    )
    parser.add_argument(
        "paper_a",
        nargs="?",
        type=Path,
        default=DEFAULT_PAPER_A,
        help="Path to the Gita paper (default: papers/MFO-PANI_Gita.pdf)",
    )
    parser.add_argument("--model")
    parser.add_argument("--contact-email", default=os.getenv("CITATION_NEEDED_CONTACT_EMAIL"))
    parser.add_argument("--out", default="data/gita_live_audit.json")
    parser.add_argument("--acquired-dir", default="data/gita_acquired")
    parser.add_argument(
        "--cited-dir",
        type=Path,
        default=DEFAULT_CITED_DIR,
        help="Directory containing manually supplied cited PDFs (default: papers/cited).",
    )
    parser.add_argument(
        "--cited-pdf",
        type=Path,
        help="Explicit local PDF for reference [17]; overrides automatic filename discovery.",
    )
    args = parser.parse_args()

    if not args.paper_a.exists():
        raise SystemExit(
            f"Paper A not found: {args.paper_a}. Expected the bundled file at {DEFAULT_PAPER_A}."
        )

    result = audit_single_citation_from_artifact(
        args.paper_a,
        paper_a_kind=ArtifactKind.PDF,
        paper_a_id="gita:mfo-pani",
        paper_a_title="Nano-flowered manganese doped ferrite@PANI composite as energy storage electrode material for supercapacitors",
        reference_number="17",
        citation_context_contains=DEFAULT_CONTEXT,
        source_role=SourceRole.PRIMARY_STUDY,
        model=args.model,
        contact_email=args.contact_email,
        acquisition_output_dir=args.acquired_dir,
        local_cited_pdf=args.cited_pdf,
        local_cited_dir=args.cited_dir,
    )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))

    resolved_doi = None
    if result.resolution.reference_entry is not None:
        resolved_doi = result.resolution.reference_entry.doi
    identity_ok = (resolved_doi or "").lower() == EXPECTED_REF_17_DOI

    print(f"source_claim={result.assertion.normalized_claim}")
    print(f"citation=[{result.citation_relation.reference_number}] purpose={result.citation_relation.purpose.value}")
    print(
        f"resolution={result.resolution.status.value} doi={resolved_doi or 'none'} "
        f"identity_check={'PASS' if identity_ok else 'REVIEW'}"
    )
    provider = (
        result.acquisition.artifacts[0].provider.value
        if result.acquisition.artifacts else "none"
    )
    print(
        f"acquisition={result.acquisition.status.value} provider={provider} "
        f"parse={result.parse_result.status.value} "
        f"retrieval={result.retrieval.status.value} evidence={len(result.retrieval.evidence)}"
    )
    print(
        f"support={result.relation_judgement.support.value} "
        f"reliability={result.audit_result.reliability.level.value} status={result.status.value}"
    )
    for evidence in result.retrieval.evidence:
        loc = evidence.provenance.location
        print(
            f"evidence: page={loc.page or '-'} section={loc.section or '-'} "
            f"text={evidence.content[:260]}"
        )
    if result.warnings:
        print("warnings:")
        for warning in result.warnings:
            print(f"  - {warning}")
    print(f"Report written to {out}")


if __name__ == "__main__":
    main()
