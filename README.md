# Citation Needed — Manual Cited-PDF Fallback v2.1.3

v2.1.3 keeps the existing real-world single-citation audit and adds the first explicit **human-in-the-loop source recovery path**: when Citation Needed identifies a cited paper but cannot retrieve its full text automatically, the researcher can place the cited PDF inside the project and re-run the same audit.

The bundled Paper A is Gita Singh et al.'s MnFe2O4@PANI paper. The current live case targets reference **[17]**:

```text
Paper A: Nano-flowered manganese doped ferrite@PANI composite...
  |
  | citation [17]
  v
K. V. Sankar & R. K. Selvan (2014)
The preparation of MnFe2O4 decorated flexible graphene wrapped with PANI...
DOI: 10.1039/C3RA47681B
```

## v2.1.3 goal

This version intentionally solves only the source handoff problem:

```text
Automatic source access fails
        ↓
Researcher supplies Paper B PDF
        ↓
Citation Needed detects local PDF
        ↓
Parse Paper B
        ↓
Retrieve evidence
        ↓
Judge claim–citation relation
        ↓
Assess source
        ↓
Reliability decision
```

It does **not** yet redesign online source discovery, and it does **not** yet fix the known claim-granularity issue in the Gita multi-citation sentence. Those are separate changes so this workflow can be validated in isolation.

## Project layout

```text
citation-needed-v2.1.3/
├── papers/
│   ├── MFO-PANI_Gita.pdf          # Paper A, bundled
│   └── cited/
│       ├── README.md
│       └── reference_17.pdf       # Paper B: you place this manually
├── citation_needed/
├── scripts/
├── examples/
├── tests/
└── data/
```

The cited PDF itself is intentionally **not** bundled and is git-ignored. This avoids accidentally redistributing a paper that the researcher obtained separately.

## Manual cited-PDF naming

For the Gita [17] case, the recommended filename is:

```text
papers/cited/reference_17.pdf
```

The acquirer also recognizes:

```text
papers/cited/ref_17.pdf
papers/cited/17.pdf
papers/cited/10.1039_c3ra47681b.pdf
```

Or explicitly provide any local path:

```bash
python scripts/run_gita_live_audit.py \
  --cited-pdf /path/to/paper-b.pdf \
  --out data/gita_live_audit.json
```

## Acquisition priority

When `papers/cited/` is configured, the order is now:

```text
1. Explicit --cited-pdf
2. Matching local PDF in papers/cited/
3. Existing remote Crossref / Unpaywall acquisition
```

A local file is accepted as full text only if it has a PDF header. A random text/HTML file renamed to `.pdf` is not promoted to full-text evidence.

When a local PDF is used, the acquisition trace records:

```text
acquisition=FULL_TEXT_AVAILABLE
provider=LOCAL_FILE
```

Remote acquisition is then skipped, but **all downstream scientific processing remains unchanged**.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

## Tests

```bash
python -m pytest -q
```

Expected baseline:

```text
80 passed
```

The new tests cover:

- explicit local cited PDF;
- automatic `reference_<n>.pdf` discovery;
- DOI-based local filename discovery;
- invalid fake-PDF rejection;
- local PDF -> Source Parser continuation.

## Run the Gita case

### Step 1 — place Paper B

Put the manually obtained [17] paper at:

```text
papers/cited/reference_17.pdf
```

### Step 2 — run

```bash
export OPENAI_API_KEY="your_key"

python scripts/run_gita_live_audit.py \
  --out data/gita_live_audit.json
```

No `CITATION_NEEDED_CONTACT_EMAIL` is required when the local PDF is found because the remote acquisition route is skipped.

The important transition to look for is:

```text
resolution=RESOLVED ... identity_check=PASS
acquisition=FULL_TEXT_AVAILABLE provider=LOCAL_FILE
parse=FULL_TEXT_PARSED
retrieval=FOUND ...
```

After that, inspect the actual `support`, `reliability`, evidence excerpts, and the complete JSON trace.

## Existing v2.1 capabilities retained

- conservative bibliography -> Crossref identity enrichment;
- repeated-citation context disambiguation;
- targeted extraction for an explicit reference number;
- explicit availability and unresolved states;
- PyMuPDF parser using `import pymupdf`;
- deterministic reliability policy.

## Generic single-citation audit with manual Paper B

```bash
python scripts/run_single_audit.py paper_a.pdf \
  --kind PDF \
  --paper-id paper-a \
  --reference-number 17 \
  --cited-pdf /path/to/paper-b.pdf \
  --out data/single_citation_audit.json
```

Or use a reusable directory:

```bash
python scripts/run_single_audit.py paper_a.pdf \
  --kind PDF \
  --paper-id paper-a \
  --reference-number 17 \
  --cited-dir papers/cited \
  --out data/single_citation_audit.json
```

## GitHub summary

Suggested commit message:

```text
Add researcher-supplied cited PDF fallback
```

Short PR description:

> Adds a local cited-PDF acquisition path before remote lookup. Researchers can place inaccessible cited papers in `papers/cited/` or pass `--cited-pdf`; the source is validated, traced as `LOCAL_FILE`, and then passed through the existing parser, evidence retriever, judge, source assessor, and reliability policy. Adds regression tests and git-ignore protection for manually supplied PDFs.


## v2.1.3 test isolation fix

Acquisition tests that explicitly exercise the no-email branch now clear `CITATION_NEEDED_CONTACT_EMAIL` with pytest `monkeypatch`. This prevents a developer's exported shell environment from changing deterministic unit-test expectations. Production behavior is unchanged: when no explicit `contact_email` is passed, the environment variable is still a valid fallback.
