# Citation Needed — Single Citation End-to-End Audit v2.0.1

v2.0 is the first orchestration milestone: the previously tested modules are now connected into one traceable single-citation audit.

```text
Paper A (local PDF/XML/HTML/TXT)
  |
  v
Parse Paper A
  |
  v
Citation-bearing Assertion Extraction       [v1.6]
  |
  v
Reference Resolution                        [v1.7]
  |
  v
Source Acquisition                          [v1.9]
  |
  v
Parse cited Paper B                         [v1.10]
  |
  v
Evidence Retrieval                          [v1.8]
  |
  v
Relation Judge                              [v1.2]
  |
  v
Source Assessor                             [v1.4]
  |
  v
Deterministic Reliability Policy            [v1.5]
  |
  v
SingleCitationAuditTrace                    [v2.0]
```

## What v2.0 adds

The new orchestration layer lives in `citation_needed/pipeline/single_citation.py`.

It produces a `SingleCitationAuditTrace` that preserves every stage rather than collapsing the pipeline into one opaque answer:

```text
extraction
resolution
acquisition
parse_result
retrieval
relation_judgement
source_assessment
audit_result
```

Important boundaries remain explicit:

```text
source unavailable != evidence absent
retrieval failure != contradiction
abstract-only != full source
SUPPORTED != HIGH reliability
CONTRADICTED != LOW reliability
UNKNOWN != bad source
```

## Citation selection

You can explicitly choose a citation by reference number or relation ID. If no selector is supplied, v2.0 deterministically selects the highest follow-priority relation and records a warning when alternatives existed.

## Install

Dependencies are now listed explicitly.

```bash
cd citation-needed-v2.0
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

Equivalent package install:

```bash
python -m pip install -e .
python -m pip install pytest
```

## Local tests

```bash
python -m pytest -q
```

Expected baseline:

```text
71 passed
```

## Hosted end-to-end semantic suite

This suite uses synthetic Paper A + synthetic cited PDFs and a fake acquisition HTTP backend, so it does not depend on Crossref/Unpaywall availability. The semantic stages still use the configured OpenAI model.

```bash
export OPENAI_API_KEY="your_key"

python scripts/run_e2e_suite.py \
  --out data/e2e_report.json
```

The three cases test:

1. exact support through the complete chain;
2. contradiction that must still be retrieved and judged;
3. restricted source propagation to `UNRESOLVED`, rather than false negative evidence.

Expected shape:

```text
[PASS] supported_full_text: ... support=SUPPORTED ...
[PASS] contradicted_full_text: ... support=CONTRADICTED ...
[PASS] restricted_source_propagates_unknown: ... reliability=UNRESOLVED ...

3/3 cases matched the declared expectations.
```

## Run one real single-citation audit

Example with a local Paper A PDF:

```bash
export OPENAI_API_KEY="your_key"
export CITATION_NEEDED_CONTACT_EMAIL="you@example.com"

python scripts/run_single_audit.py paper_a.pdf \
  --kind PDF \
  --paper-id paper-a \
  --reference-number 17 \
  --source-role PRIMARY_STUDY \
  --out data/single_citation_audit.json
```

The contact email is used for Unpaywall. Without it, DOI metadata lookup can still run, but Unpaywall is skipped.

`source-role` defaults to `UNKNOWN`; v2.0 does not guess primary-vs-secondary provenance from prose.

## Scope of this MVP

v2.0 is a **single-citation audit**, not yet a recursive literature-review agent.

Implemented:

```text
Paper A -> citation -> Paper B -> evidence -> judgement -> reliability
```

Still future work:

```text
multi-citation batch audit
recursive citation-chain traversal
cross-paper consistency / replication assessment
human review queue
materials-science domain adapter
figure/table-specific evidence extraction
final researcher-facing audit UI/report
```

## GitHub summary

Suggested commit message:

```text
Add v2.0 single-citation end-to-end audit pipeline
```

Short PR description:

> Connects extraction, reference resolution, guarded source acquisition, source parsing, evidence retrieval, relation judgement, source assessment, and deterministic reliability into one traceable single-citation audit. Adds explicit pipeline-stage outputs, citation selection, dependency files, and end-to-end semantic tests for support, contradiction, and unavailable-source propagation.


## Packaging fix in v2.0.1

Setuptools package discovery is explicitly restricted to `citation_needed*`, so top-level runtime folders such as `data/` are not treated as packages during editable installation.
