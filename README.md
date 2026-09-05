# Citation Needed — Real-world Validation v2.1.1

v2.1.1 hardens the single-citation MVP against a real scientific paper and bundles the Gita PDF inside the project for reproducible local validation.

The live validation target is Gita Singh et al.'s MnFe2O4@PANI paper, using its reference **[17]**:

```text
Paper A: Nano-flowered manganese doped ferrite@PANI composite...
  |
  | citation [17]
  v
K. V. Sankar & R. K. Selvan (2014)
The preparation of MnFe2O4 decorated flexible graphene wrapped with PANI...
DOI: 10.1039/C3RA47681B
```

## What v2.1 adds

### 1. Conservative bibliography -> Crossref identity enrichment

Real bibliographies often contain no DOI. v1.7 therefore correctly returned `PARTIALLY_RESOLVED` for Gita reference [17].

v2.1 adds a deterministic Crossref bibliographic lookup:

```text
raw bibliography entry
  -> Crossref candidates
  -> title/year/author agreement checks
  -> strong unique match only
  -> canonical DOI
```

If the match is weak or ambiguous, the state remains `PARTIALLY_RESOLVED`. No LLM is allowed to invent a DOI.

### 2. Repeated-citation disambiguation

The same reference can appear more than once in a real paper. A reference number alone is therefore not always a unique citation relation.

v2.1 adds `citation_context_contains`, so a specific use of `[17]` can be selected by its local citation context.

### 3. Targeted extraction for an explicit reference

When `--reference-number` is supplied, the extractor receives only sections where that numeric citation is actually visible. This reduces token cost and avoids unrelated citation extraction while preserving original provenance.

### 4. PyMuPDF API hardening

Runtime/tests now use:

```python
import pymupdf
```

rather than the deprecated `fitz` alias.

## Architecture

```text
Paper A
  -> Source Parser
  -> Targeted Citation Extraction
  -> Local Reference Resolution
  -> Crossref Identity Enrichment       [new]
  -> Source Acquisition
  -> Parse Paper B
  -> Evidence Retrieval
  -> Relation Judge
  -> Source Assessor
  -> Reliability Policy
  -> SingleCitationAuditTrace
```

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

## Local tests

```bash
python -m pytest -q
```

Expected baseline:

```text
75 passed
```

## Bundled Gita paper

The real validation PDF is stored inside the project at:

```text
papers/MFO-PANI_Gita.pdf
```

This keeps the live validation case self-contained. You do not need to pass a PDF path for the default run.

## Run the Gita live audit

```bash
export OPENAI_API_KEY="your_new_key"
export CITATION_NEEDED_CONTACT_EMAIL="you@example.com"

python scripts/run_gita_live_audit.py \
  --out data/gita_live_audit.json
```

You can still override the bundled paper by passing another path as the optional first argument.

The script targets the specific use of reference [17] in the sentence beginning:

```text
Different composites with different ratios have already been utilized successfully...
```

It independently checks that the resolved DOI is:

```text
10.1039/C3RA47681B
```

Source availability is intentionally not a pass/fail scientific result. A publisher or OA access change may yield full text, abstract/metadata only, or restricted access; those states remain explicit in the audit trace.

## Generic real audit

```bash
python scripts/run_single_audit.py paper_a.pdf \
  --kind PDF \
  --paper-id paper-a \
  --reference-number 17 \
  --context-contains "distinctive citation context" \
  --out data/single_citation_audit.json
```

## GitHub summary

Suggested commit message:

```text
Bundle real Gita paper for reproducible live citation audit
```

Short PR description:

> Bundles the Gita validation PDF under `papers/`, defaults the live audit script to that project-local file, and retains conservative Crossref enrichment, citation-context disambiguation, targeted extraction, and the existing single-citation audit pipeline.
