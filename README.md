# Citation Needed — Relation Judge v1.2 + Source Assessor v0

This version keeps the v1.2 relation judge and adds a separate source-level evidence assessor.

```text
Claim + Evidence -> Relation Judge
Evidence-bearing source context -> Source Assessor
```

The Source Assessor emits: evidence directness, method completeness, measurement appropriateness, reporting completeness, source originality, and internal consistency.

A key guard is `context_scope`:

```text
EXCERPT_ONLY
RELEVANT_SECTIONS
FULL_SOURCE
```

Missing source context is not treated as negative evidence. In particular, an excerpt that omits the method does **not** imply that the paper has an incomplete method.

`source_originality` is derived from provenance rather than guessed by the model.

## Install

```bash
cd citation-needed-v1.3
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
pip install pytest
export OPENAI_API_KEY="your_key_here"
```

## Run local tests

```bash
pytest -q
```

## Run one source assessment

```bash
python scripts/run_source_assessment.py \
  --source examples/source_strong.json \
  --evidence examples/evidence_source_strong.json
```

## Run Source Assessor semantic suite

```bash
python scripts/run_source_suite.py \
  --out data/source_assessment_report.json
```

Cases:

1. `strong_primary_relevant_sections` — adapted from the supplied MFO-PANI paper.
2. `excerpt_does_not_imply_bad_source` — tests UNKNOWN-vs-negative discipline.
3. `secondary_report` — tests provenance-owned secondary status.
4. `internal_numeric_conflict` — synthetic stress test with 8 nm vs 18 nm for the same sample.

The hosted suite is an evaluation; local unit tests do not imply the hosted semantic cases will pass.

## Architecture

```text
Assertion
  -> Citation Relation
  -> Evidence + Provenance
       |                    |
       v                    v
  Relation Judge       Source Assessor
       |                    |
       +---------+----------+
                 v
        Reliability Policy   # next integration step
```

Not yet implemented: PDF parsing, citation retrieval, cross-paper reproducibility, cross-source consistency, calibrated final reliability scoring, traversal policy.
