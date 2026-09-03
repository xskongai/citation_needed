# Citation Needed v0.3 — Judge v1.1

A minimal, from-scratch scaffold for a **traceable claim–citation–evidence judgement pipeline**.

## What this version proves

This v0 deliberately starts with the system's core information model rather than PDF parsing, search, or multi-agent orchestration:

`Assertion -> CitationRelation -> Evidence -> Judgement`

The current judgement backend is a **deterministic smoke-test baseline only**. It is intentionally conservative and must not be treated as a scientifically valid entailment/reliability model. Its purpose is to make the schemas, provenance requirements, CLI, and reliability-factor policy executable before an evaluated semantic judge is added.

## Core invariants

1. Original assertion text and normalized claim are stored separately.
2. Citation purpose is explicit.
3. Every Evidence object must carry provenance.
4. Reported information and AI inference are different epistemic states.
5. Support and reliability are separate judgements.
6. Reliability is derived from explicit factors, not an unexplained confidence number.
7. Unknown information remains unknown.

## Install

```bash
cd citation-needed-v0
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Run the first judgement

```bash
python scripts/run_judgement.py \
  --claim examples/claim.json \
  --evidence examples/evidence.json
```

Optional output file:

```bash
python scripts/run_judgement.py \
  --claim examples/claim.json \
  --evidence examples/evidence.json \
  --out data/judgement.json
```

## Run tests

```bash
pip install pytest
pytest -q
```

## Next implementation step

Replace the provisional semantic rules inside `citation_needed/judgement/engine.py` with an evaluated judge backend while keeping the same domain models and output contract. Recommended split:

- relevance judge
- support judge
- reliability-factor extractor
- reliability policy

After that, add assertion/citation extraction and evidence retrieval around the stable core.

## Judge v1 — hosted semantic reasoning

v0 keeps the deterministic baseline for smoke tests. v1 adds an optional hosted semantic judge while keeping the final reliability aggregation in application code.

Install/update dependencies:

```bash
pip install -e .
```

Set an API key in your shell:

```bash
export OPENAI_API_KEY="your_key_here"
```

Optional model override:

```bash
export CITATION_NEEDED_MODEL="gpt-5.6-terra"
```

Run the semantic judge:

```bash
python scripts/run_judgement.py \
  --backend openai \
  --claim examples/claim.json \
  --evidence examples/evidence.json
```

Use a stronger model for a demo/evaluation run by passing `--model`:

```bash
python scripts/run_judgement.py \
  --backend openai \
  --model gpt-5.6-sol \
  --claim examples/claim.json \
  --evidence examples/evidence.json
```

The semantic model decides relevance, support, reliability factors, uncertainty, and concise rationale. The final HIGH/MODERATE/LOW reliability label is produced by the deterministic policy in `citation_needed/judgement/policy.py`.

The v0 `_reliability` hints in example evidence are deliberately stripped before calling the semantic model, so they cannot bias Judge v1.

## Judge v1.1 — adversarial semantic checks

v1.1 tightens the boundary between **relation-level semantic judgement** and **source-level facts**.

Key changes:

- Partial support is decomposed into `supported_components`, `unsupported_components`, and `contradicted_components`.
- `UNKNOWN` is now explicit for method completeness and characterization quality when an excerpt does not provide enough source context to assess the paper itself.
- Reproducibility defaults to `UNKNOWN` when it is merely not shown; `ABSENT` is reserved for explicit evidence of absence.
- `source_originality` is overridden from provenance metadata (`PRIMARY_STUDY`, `SECONDARY_SOURCE`, `UNKNOWN`) rather than guessed from prose.
- Five adversarial cases test overclaiming, contradiction, related-but-insufficient evidence, secondary citation, and condition mismatch.

Run one case as before:

```bash
python scripts/run_judgement.py \
  --backend openai \
  --claim examples/claim_contradiction.json \
  --evidence examples/evidence_contradiction.json
```

Run the full semantic adversarial suite:

```bash
python scripts/run_adversarial_suite.py \
  --out data/adversarial_report.json
```

Optional stronger model:

```bash
python scripts/run_adversarial_suite.py \
  --model gpt-5.6-sol \
  --out data/adversarial_report.json
```

The suite is an engineering diagnostic, not a scientific benchmark. A `REVIEW` result means the output fell outside the deliberately narrow expected label set and should be inspected; it does not automatically mean the model is scientifically wrong.
