#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from citation_needed.acquisition import AcquisitionNetworkError, HttpResponse, acquire_source, crossref_url, unpaywall_url
from citation_needed.models import CitationResolution, IdentityBasis, ReferenceEntry, ResolutionStatus


class FixtureClient:
    def __init__(self, responses=None, errors=None):
        self.responses = responses or {}
        self.errors = errors or {}

    def get(self, url, *, headers=None, timeout=20.0, max_bytes=50_000_000):
        if url in self.errors:
            raise AcquisitionNetworkError(self.errors[url])
        if url not in self.responses:
            raise AssertionError(f"Unexpected fixture URL: {url}")
        return self.responses[url]


def resp(url, status=200, payload=None, body=None, content_type="application/json"):
    return HttpResponse(
        status,
        url,
        {"content-type": content_type},
        body if body is not None else json.dumps(payload or {}).encode(),
    )


def crossref_payload(doi, *, abstract=None):
    msg = {
        "DOI": doi,
        "title": ["Fixture paper"],
        "author": [{"given": "Ada", "family": "Example"}],
        "issued": {"date-parts": [[2024]]},
        "container-title": ["Fixture Journal"],
        "publisher": "Fixture Publisher",
        "URL": f"https://doi.org/{doi}",
    }
    if abstract:
        msg["abstract"] = abstract
    return {"status": "ok", "message": msg}


def up_payload(*, is_oa=True, pdf=None):
    loc = {"url_for_pdf": pdf, "url_for_landing_page": "https://repo.example/article"} if pdf else None
    return {"is_oa": is_oa, "best_oa_location": loc, "oa_locations": [loc] if loc else []}


def make_resolution(doi="10.1234/fixture", url=None):
    entry = ReferenceEntry(
        reference_number="7",
        raw_text="[7] Fixture reference",
        title="Fixture paper",
        year=2024,
        doi=doi,
        url=url,
    )
    return CitationResolution(
        relation_id="rel-7",
        source_paper_id="paper-a",
        reference_number="7",
        status=ResolutionStatus.RESOLVED,
        reference_entry=entry,
        cited_paper_id=f"doi:{doi}" if doi else "url:fixture",
        identity_basis=IdentityBasis.DOI if doi else IdentityBasis.URL,
    )


def fixture(name):
    email = "fixture@example.org"
    doi = "10.1234/fixture"
    cu = crossref_url(doi)
    uu = unpaywall_url(doi, email)
    pdf = "https://repo.example/article.pdf"
    res = make_resolution(doi=doi)

    if name == "open_access_pdf":
        return res, email, FixtureClient({
            cu: resp(cu, payload=crossref_payload(doi)),
            uu: resp(uu, payload=up_payload(pdf=pdf)),
            pdf: resp(pdf, body=b"%PDF-1.4 fixture", content_type="application/pdf"),
        })
    if name == "abstract_only":
        return res, email, FixtureClient({
            cu: resp(cu, payload=crossref_payload(doi, abstract="<p>Fixture abstract.</p>")),
            uu: resp(uu, payload=up_payload(is_oa=False)),
        })
    if name == "metadata_only":
        return res, None, FixtureClient({cu: resp(cu, payload=crossref_payload(doi))})
    if name == "access_restricted":
        return res, email, FixtureClient({
            cu: resp(cu, payload=crossref_payload(doi)),
            uu: resp(uu, payload=up_payload(is_oa=False)),
        })
    if name == "not_found":
        return res, email, FixtureClient({
            cu: resp(cu, status=404, payload={"status": "not-found"}),
            uu: resp(uu, status=404, payload={"error": True}),
        })
    if name == "network_failure":
        return res, email, FixtureClient(errors={cu: "offline", uu: "offline"})
    if name == "html_login_not_full_text":
        return res, email, FixtureClient({
            cu: resp(cu, payload=crossref_payload(doi)),
            uu: resp(uu, payload=up_payload(pdf=pdf)),
            pdf: resp(pdf, body=b"<html>login</html>", content_type="text/html"),
        })
    if name == "direct_pdf":
        direct = "https://repo.example/direct.pdf"
        return make_resolution(doi=None, url=direct), None, FixtureClient({
            direct: resp(direct, body=b"%PDF-1.7 direct", content_type="application/pdf")
        })
    raise KeyError(name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", default="examples/acquisition_suite.json")
    parser.add_argument("--out", default="data/acquisition_report.json")
    args = parser.parse_args()

    cases = json.loads(Path(args.suite).read_text())
    report = []
    passed = 0

    with tempfile.TemporaryDirectory(prefix="citation-needed-acq-") as tmp:
        for case in cases:
            resolution, email, client = fixture(case["fixture"])
            result = acquire_source(
                resolution,
                output_dir=Path(tmp) / case["name"],
                contact_email=email,
                client=client,
            )
            errors = []
            if result.status.value != case["expected_status"]:
                errors.append(f"status: got {result.status.value!r}, expected {case['expected_status']!r}")
            if len(result.artifacts) != case["expected_artifacts"]:
                errors.append(f"artifacts: got {len(result.artifacts)}, expected {case['expected_artifacts']}")
            ok = not errors
            passed += int(ok)
            providers = ",".join(a.provider.value for a in result.provider_attempts) or "none"
            print(
                f"[{'PASS' if ok else 'REVIEW'}] {case['name']}: "
                f"status={result.status.value} artifacts={len(result.artifacts)} providers={providers}"
            )
            for error in errors:
                print(f"  - {error}")
            report.append({
                "name": case["name"],
                "passed": ok,
                "errors": errors,
                "result": result.model_dump(mode="json"),
            })

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2))
    print(f"\n{passed}/{len(cases)} cases matched the declared expectations.")
    print(f"Report written to {out}")


if __name__ == "__main__":
    main()
