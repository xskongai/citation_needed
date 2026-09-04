# Citation Needed — Relation Judge v1.2 + Source Assessor v1.4

This version keeps the v1.2 relation judge and refines the source-level assessor around two concepts exposed by the v1.3 semantic suite:

1. **Evidence Basis** — a reported scientific result is not automatically an author interpretation.
2. **Measurement Traceability** — identifying a measurement method is separate from proving that it produced the target result and from judging its appropriateness.

```text
Claim + Evidence -> Relation Judge
Evidence-bearing source context -> Source Assessor
```

## v1.4 Source Assessor model

```text
Source Assessment
├── Evidence Basis
│   ├── DIRECT_MEASUREMENT
│   ├── DERIVED_RESULT
│   ├── REPORTED_RESULT
│   ├── AUTHOR_INTERPRETATION
│   ├── SECONDARY_REPORT
│   └── UNKNOWN
├── Method Completeness
├── Measurement Traceability
│   ├── method_status
│   │   ├── IDENTIFIED
│   │   ├── NOT_IDENTIFIED
│   │   └── UNKNOWN
│   ├── identified_methods[]
│   ├── target_link
│   │   ├── EXPLICIT
│   │   ├── INFERRED
│   │   └── UNKNOWN
│   └── appropriateness
│       ├── APPROPRIATE
│       ├── PARTIAL
│       ├── INAPPROPRIATE
│       ├── UNKNOWN
│       └── NA
├── Reporting Completeness
├── Source Originality       # provenance-owned
└── Internal Consistency
```

A core invariant remains:

```text
Not observed != observed absent
Missing source context != poor source quality
```

If a measurement method is not identified, or the method-to-target link is unknown, the policy prevents the system from asserting measurement appropriateness.

## Install

```bash
cd citation-needed-v1.4
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
18 passed
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

The suite now contains five cases:

1. `strong_primary_measurement_traceability` — primary-paper result with explicit GCD/capacitance linkage and calculation context.
2. `reported_comparative_result` — tests the new `REPORTED_RESULT` evidence-basis state.
3. `excerpt_does_not_imply_bad_source` — tests UNKNOWN-vs-negative discipline.
4. `secondary_report` — tests provenance-owned secondary status.
5. `internal_numeric_conflict` — synthetic source-internal conflict stress test.

The hosted suite is an evaluation. `18 passed` refers only to local schema/policy tests and does not imply all hosted semantic cases will pass.

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
        Reliability Policy   # next integration step
```

Not yet implemented: PDF parsing, citation retrieval, cross-paper reproducibility, cross-source consistency, calibrated final reliability policy, traversal policy.
