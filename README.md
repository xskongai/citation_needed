# Citation Needed — Reliability Policy v1

This version keeps **Relation Judge v1.2** and **Source Assessor v1.4**, then combines them with a deterministic final reliability policy.

```text
Claim + Evidence -> Relation Judge
Source context   -> Source Assessor
                         |
                         v
                 Reliability Policy v1
                         |
                         v
               HIGH / MODERATE / LOW / UNRESOLVED
```

## What v1.5 adds

- `ReliabilityDecision` and `CitationAuditResult`
- deterministic `decide_reliability(...)` policy
- no numeric confidence score and no LLM-generated final reliability label
- explicit `positive_signals`, `caution_signals`, and `blocking_signals`
- hard guards for:
  - secondary-only evidence
  - source-internal conflict
  - inappropriate measurement
  - unresolved/unavailable evidence
- strict HIGH criteria requiring strong primary evidence, explicit measurement traceability, sufficient method/reporting context, and no material source conflict
- contradiction can still be HIGH reliability when the contradictory evidence itself is strong
- UNKNOWN remains cautionary/neutral rather than automatically negative

Core rule:

```text
SUPPORTED != HIGH
CONTRADICTED != LOW
UNKNOWN != BAD
```

The final reliability level means:

> How much should the system trust the resulting claim-evidence audit after combining relation fit and source evidence quality?

It is **not** an LLM confidence score.

## Install

```bash
cd citation-needed-v1.5
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

Expected for this package:

```text
27 passed
```

These are local schema/policy tests. They do not imply that hosted semantic-model suites will necessarily pass.

## Run Relation Judge suite

```bash
python scripts/run_adversarial_suite.py \
  --out data/adversarial_report.json
```

## Run Source Assessor suite

```bash
python scripts/run_source_suite.py \
  --out data/source_assessment_report.json
```

## Run integrated Reliability suite

```bash
python scripts/run_reliability_suite.py \
  --out data/reliability_report.json
```

The integrated suite runs both hosted semantic components and then applies the deterministic reliability policy. It currently includes:

1. `strong_primary_realistic` -> expected `MODERATE` because the real source package is strong but still only supplies relevant sections rather than a fully established source-wide assessment.
2. `secondary_only_support` -> expected `LOW`.
3. `internal_source_conflict` -> expected `LOW`.
4. `condition_mismatch_is_limited_not_bad_source` -> expected `MODERATE`.
5. `related_but_insufficient_primary` -> expected `MODERATE` for the audit conclusion without treating missing/unknown source context as poor quality.

## Reliability Policy v1

```text
UNRESOLVED
  when the relation/source/evidence chain cannot be evaluated.

LOW
  when a hard source-level weakness exists, such as:
  - secondary-only support
  - internal source conflict
  - inappropriate measurement

HIGH
  only when:
  - relation is clearly relevant and supported/contradicted
  - subject/outcome/conditions align
  - source is primary
  - evidence is direct or explicitly derived
  - method and reporting are sufficient
  - measurement -> target link is explicit and appropriate
  - full-source internal consistency is established

MODERATE
  for evaluable audits without hard failure when one or more
  relation/source factors remain partial, limited, or unknown.
```

## Architecture

```text
Assertion
  -> Citation Relation
  -> Evidence + Provenance
       |                    |
       v                    v
  Relation Judge       Source Assessor
       |               Evidence Basis
       |               Method Coverage
       |               Measurement Traceability
       |               Reporting
       |               Provenance
       |               Internal Consistency
       +---------+----------+
                 v
        Reliability Policy v1
                 |
                 v
          CitationAuditResult
```

Not yet implemented: PDF parsing, citation/source retrieval, recursive citation traversal, cross-paper reproducibility, cross-source consistency, and calibrated empirical validation of the reliability policy.
