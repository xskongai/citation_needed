from __future__ import annotations

import json
from pathlib import Path

from citation_needed.acquisition import AcquisitionNetworkError, HttpResponse, acquire_source, crossref_url, unpaywall_url
from citation_needed.models import (
    AcquisitionStatus,
    CitationResolution,
    IdentityBasis,
    ReferenceEntry,
    ResolutionStatus,
)


class FakeHttpClient:
    def __init__(self, responses=None, errors=None):
        self.responses = responses or {}
        self.errors = errors or {}
        self.calls = []

    def get(self, url, *, headers=None, timeout=20.0, max_bytes=50_000_000):
        self.calls.append(url)
        if url in self.errors:
            raise AcquisitionNetworkError(self.errors[url])
        if url not in self.responses:
            raise AssertionError(f"Unexpected URL: {url}")
        return self.responses[url]


def response(url, status=200, *, payload=None, body=None, content_type="application/json"):
    if body is None:
        body = json.dumps(payload or {}).encode()
    return HttpResponse(status, url, {"content-type": content_type}, body)


def resolution(*, doi="10.1234/example", url=None, status=ResolutionStatus.RESOLVED):
    entry = ReferenceEntry(
        reference_number="7",
        raw_text="[7] Example reference",
        title="Example paper",
        year=2024,
        doi=doi,
        url=url,
    )
    return CitationResolution(
        relation_id="rel-7",
        source_paper_id="paper-a",
        reference_number="7",
        status=status,
        reference_entry=entry,
        cited_paper_id=f"doi:{doi}" if doi else "url:example",
        identity_basis=IdentityBasis.DOI if doi else IdentityBasis.URL,
    )


def crossref_payload(doi="10.1234/example", *, abstract=None, links=None):
    msg = {
        "DOI": doi,
        "title": ["Remote title"],
        "author": [{"given": "Ada", "family": "Example"}],
        "issued": {"date-parts": [[2024, 1, 1]]},
        "container-title": ["Example Journal"],
        "publisher": "Example Publisher",
        "URL": f"https://doi.org/{doi}",
    }
    if abstract is not None:
        msg["abstract"] = abstract
    if links is not None:
        msg["link"] = links
    return {"status": "ok", "message": msg}


def unpaywall_payload(*, is_oa=True, pdf=None):
    best = None
    if pdf:
        best = {"url_for_pdf": pdf, "url_for_landing_page": "https://repo.example/paper"}
    return {"doi": "10.1234/example", "is_oa": is_oa, "best_oa_location": best, "oa_locations": [best] if best else []}


def test_unresolved_does_not_touch_network(tmp_path):
    res = resolution(status=ResolutionStatus.UNRESOLVED)
    client = FakeHttpClient()
    out = acquire_source(res, output_dir=tmp_path, client=client, contact_email="a@b.example")
    assert out.status == AcquisitionStatus.UNRESOLVED
    assert client.calls == []


def test_open_access_pdf_is_saved_and_marked_full_text(tmp_path):
    doi = "10.1234/example"
    cu = crossref_url(doi)
    uu = unpaywall_url(doi, "a@b.example")
    pdf = "https://repo.example/paper.pdf"
    client = FakeHttpClient({
        cu: response(cu, payload=crossref_payload(doi)),
        uu: response(uu, payload=unpaywall_payload(pdf=pdf)),
        pdf: response(pdf, body=b"%PDF-1.4 fake", content_type="application/pdf"),
    })
    out = acquire_source(resolution(doi=doi), output_dir=tmp_path, client=client, contact_email="a@b.example")
    assert out.status == AcquisitionStatus.FULL_TEXT_AVAILABLE
    assert len(out.artifacts) == 1
    assert out.artifacts[0].local_path
    assert Path(out.artifacts[0].local_path).read_bytes().startswith(b"%PDF")
    assert out.artifacts[0].sha256


def test_crossref_abstract_is_not_promoted_to_full_text(tmp_path):
    doi = "10.1234/example"
    cu = crossref_url(doi)
    uu = unpaywall_url(doi, "a@b.example")
    client = FakeHttpClient({
        cu: response(cu, payload=crossref_payload(doi, abstract="<jats:p>Abstract only.</jats:p>")),
        uu: response(uu, payload=unpaywall_payload(is_oa=False)),
    })
    out = acquire_source(resolution(doi=doi), output_dir=tmp_path, client=client, contact_email="a@b.example")
    assert out.status == AcquisitionStatus.ABSTRACT_ONLY
    assert out.metadata.abstract == "Abstract only."
    assert not out.artifacts


def test_non_oa_without_abstract_is_access_restricted(tmp_path):
    doi = "10.1234/example"
    cu = crossref_url(doi)
    uu = unpaywall_url(doi, "a@b.example")
    client = FakeHttpClient({
        cu: response(cu, payload=crossref_payload(doi)),
        uu: response(uu, payload=unpaywall_payload(is_oa=False)),
    })
    out = acquire_source(resolution(doi=doi), output_dir=tmp_path, client=client, contact_email="a@b.example")
    assert out.status == AcquisitionStatus.ACCESS_RESTRICTED


def test_crossref_only_metadata_is_metadata_only_without_unpaywall_email(tmp_path):
    doi = "10.1234/example"
    cu = crossref_url(doi)
    client = FakeHttpClient({cu: response(cu, payload=crossref_payload(doi))})
    out = acquire_source(resolution(doi=doi), output_dir=tmp_path, client=client, contact_email=None)
    assert out.status == AcquisitionStatus.METADATA_ONLY
    assert out.metadata.title == "Remote title"
    assert any("Unpaywall" in w for w in out.warnings)


def test_invalid_doi_not_found_when_both_providers_404(tmp_path):
    doi = "10.1234/example"
    cu = crossref_url(doi)
    uu = unpaywall_url(doi, "a@b.example")
    client = FakeHttpClient({
        cu: response(cu, status=404, payload={"status": "not-found"}),
        uu: response(uu, status=404, payload={"error": True}),
    })
    out = acquire_source(resolution(doi=doi), output_dir=tmp_path, client=client, contact_email="a@b.example")
    assert out.status == AcquisitionStatus.NOT_FOUND


def test_network_failure_is_not_mislabelled_not_found(tmp_path):
    doi = "10.1234/example"
    cu = crossref_url(doi)
    uu = unpaywall_url(doi, "a@b.example")
    client = FakeHttpClient(errors={cu: "offline", uu: "offline"})
    out = acquire_source(resolution(doi=doi), output_dir=tmp_path, client=client, contact_email="a@b.example")
    assert out.status == AcquisitionStatus.ACQUISITION_FAILED


def test_html_login_page_returned_for_pdf_candidate_is_not_full_text(tmp_path):
    doi = "10.1234/example"
    cu = crossref_url(doi)
    uu = unpaywall_url(doi, "a@b.example")
    pdf = "https://repo.example/paper.pdf"
    client = FakeHttpClient({
        cu: response(cu, payload=crossref_payload(doi)),
        uu: response(uu, payload=unpaywall_payload(pdf=pdf)),
        pdf: response(pdf, body=b"<html>login</html>", content_type="text/html"),
    })
    out = acquire_source(resolution(doi=doi), output_dir=tmp_path, client=client, contact_email="a@b.example")
    assert out.status != AcquisitionStatus.FULL_TEXT_AVAILABLE
    assert not out.artifacts
    assert any("returned HTML" in w for w in out.warnings)


def test_direct_pdf_url_can_be_acquired_without_doi(tmp_path):
    url = "https://repo.example/direct.pdf"
    res = resolution(doi=None, url=url)
    client = FakeHttpClient({url: response(url, body=b"%PDF-1.7 direct", content_type="application/pdf")})
    out = acquire_source(res, output_dir=tmp_path, client=client)
    assert out.status == AcquisitionStatus.FULL_TEXT_AVAILABLE
    assert out.artifacts[0].url == url
