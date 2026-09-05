from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

import pymupdf

from citation_needed.acquisition.http import HttpResponse
from citation_needed.models import ArtifactKind, SourceRole
from citation_needed.pipeline import audit_single_citation_from_artifact


class FakeHttpClient:
    def __init__(self, *, doi: str, pdf_bytes: bytes | None, restricted: bool = False) -> None:
        self.doi = doi
        self.pdf_bytes = pdf_bytes
        self.restricted = restricted
        self.pdf_url = f"https://example.org/{doi.split('/')[-1]}.pdf"

    def get(self, url: str, *, headers=None, timeout: float = 20.0, max_bytes: int = 50_000_000):
        if "api.crossref.org/works/" in url:
            message = {
                "DOI": self.doi,
                "title": ["Synthetic cited study"],
                "author": [{"given": "A.", "family": "Researcher"}],
                "published-online": {"date-parts": [[2025]]},
                "container-title": ["Synthetic Journal"],
                "URL": f"https://doi.org/{self.doi}",
                "link": [] if self.restricted else [{"URL": self.pdf_url, "content-type": "application/pdf"}],
            }
            return HttpResponse(200, url, {"content-type": "application/json"}, json.dumps({"message": message}).encode())

        if "api.unpaywall.org/" in url:
            payload = {
                "is_oa": False if self.restricted else True,
                "best_oa_location": None if self.restricted else {
                    "url_for_pdf": self.pdf_url,
                    "url_for_landing_page": f"https://example.org/{self.doi.split('/')[-1]}",
                },
                "oa_locations": [],
            }
            return HttpResponse(200, url, {"content-type": "application/json"}, json.dumps(payload).encode())

        if url == self.pdf_url and self.pdf_bytes is not None:
            return HttpResponse(200, url, {"content-type": "application/pdf"}, self.pdf_bytes)

        return HttpResponse(404, url, {"content-type": "text/plain"}, b"")


def make_pdf_bytes(result_sentence: str) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    text = (
        "Synthetic cited study\n\n"
        "Methods\n"
        "Catalytic conversion was measured in a fixed-bed reactor at 300 C under identical feed conditions.\n\n"
        "Results\n"
        f"{result_sentence}\n\n"
        "Discussion\n"
        "The reported conversion refers to the stated 300 C test condition.\n"
    )
    page.insert_textbox(pymupdf.Rect(50, 50, 550, 780), text, fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data


def paper_a_text(claim_sentence: str, doi: str) -> str:
    return (
        "Introduction\n"
        f"{claim_sentence} [1]\n\n"
        "References\n"
        f"[1] A. Researcher, Synthetic cited study, Synthetic Journal (2025). https://doi.org/{doi}\n"
    )


def run_case(root: Path, case: dict, model: str | None):
    doi = case["doi"]
    paper_a = root / f"{case['name']}_paper_a.txt"
    paper_a.write_text(paper_a_text(case["claim"], doi))
    pdf = None if case.get("restricted") else make_pdf_bytes(case["source_result"])
    http = FakeHttpClient(doi=doi, pdf_bytes=pdf, restricted=case.get("restricted", False))

    result = audit_single_citation_from_artifact(
        paper_a,
        paper_a_kind=ArtifactKind.TEXT,
        paper_a_id=f"paper-a:{case['name']}",
        reference_number="1",
        source_role=SourceRole.PRIMARY_STUDY,
        model=model,
        contact_email="test@example.com",
        acquisition_output_dir=root / "acquired",
        http_client=http,
    )

    errors = []
    for field, allowed in case["expected"].items():
        if field == "acquisition":
            got = result.acquisition.status.value
        elif field == "retrieval":
            got = result.retrieval.status.value
        elif field == "support":
            got = result.relation_judgement.support.value
        elif field == "reliability":
            got = result.audit_result.reliability.level.value
        elif field == "status":
            got = result.status.value
        else:
            continue
        if got not in allowed:
            errors.append(f"{field}: got {got!r}, expected one of {allowed}")

    return result, errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model")
    parser.add_argument("--out", default="data/e2e_report.json")
    args = parser.parse_args()

    cases = [
        {
            "name": "supported_full_text",
            "doi": "10.1234/cn.support",
            "claim": "The catalyst achieved a conversion of 82% at 300 C",
            "source_result": "The catalyst achieved a measured conversion of 82% at 300 C.",
            "expected": {
                "acquisition": ["FULL_TEXT_AVAILABLE"],
                "retrieval": ["FOUND"],
                "support": ["SUPPORTED"],
                "reliability": ["MODERATE", "HIGH"],
                "status": ["COMPLETE"],
            },
        },
        {
            "name": "contradicted_full_text",
            "doi": "10.1234/cn.contradict",
            "claim": "The catalyst achieved a conversion of 82% at 300 C",
            "source_result": "The catalyst achieved a measured conversion of 61% at 300 C.",
            "expected": {
                "acquisition": ["FULL_TEXT_AVAILABLE"],
                "retrieval": ["FOUND"],
                "support": ["CONTRADICTED"],
                "reliability": ["MODERATE", "HIGH"],
                "status": ["COMPLETE"],
            },
        },
        {
            "name": "restricted_source_propagates_unknown",
            "doi": "10.1234/cn.restricted",
            "claim": "The catalyst achieved a conversion of 82% at 300 C",
            "source_result": "",
            "restricted": True,
            "expected": {
                "acquisition": ["ACCESS_RESTRICTED"],
                "retrieval": ["SOURCE_UNAVAILABLE"],
                "support": ["INSUFFICIENT_EVIDENCE"],
                "reliability": ["UNRESOLVED"],
                "status": ["UNRESOLVED"],
            },
        },
    ]

    records = []
    passed = 0
    with tempfile.TemporaryDirectory(prefix="citation-needed-e2e-") as tmp:
        root = Path(tmp)
        for case in cases:
            result, errors = run_case(root, case, args.model)
            ok = not errors
            passed += int(ok)
            label = "PASS" if ok else "REVIEW"
            print(
                f"[{label}] {case['name']}: acquisition={result.acquisition.status.value} "
                f"parse={result.parse_result.status.value} retrieval={result.retrieval.status.value} "
                f"support={result.relation_judgement.support.value} "
                f"reliability={result.audit_result.reliability.level.value} status={result.status.value}"
            )
            for error in errors:
                print(f"  - {error}")
            records.append({
                "case": case["name"],
                "ok": ok,
                "errors": errors,
                "result": result.model_dump(mode="json"),
            })

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(records, ensure_ascii=False, indent=2))
    print(f"\n{passed}/{len(cases)} cases matched the declared expectations.")
    print(f"Report written to {out}")


if __name__ == "__main__":
    main()
