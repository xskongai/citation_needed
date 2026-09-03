# Citation Needed v0

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
