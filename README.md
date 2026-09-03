# Citation Needed — Judge v1.2

From-scratch scaffold for a **traceable scientific claim–citation–evidence judgement pipeline**.

Current core:

```text
Assertion
  -> CitationRelation
  -> Evidence + Provenance
  -> Relation Judge
       -> Relevance
       -> Support
       -> Claim-component coverage
       -> Subject / Outcome / Condition alignment
  -> Reliability factors
  -> deterministic reliability policy
```

## What changed in v1.2

### 1. Claim decomposition

A partially supported claim is no longer just one label. The hosted judge decomposes it into decision-relevant propositions:

```text
Claim: Method X reliably produces <10 nm particles across reaction conditions.

P1: Method X produced <10 nm particles.       -> SUPPORTED
P2: The result is reliable.                   -> INSUFFICIENT_EVIDENCE
P3: It holds across reaction conditions.      -> INSUFFICIENT_EVIDENCE

Overall -> PARTIALLY_SUPPORTED
```

The output includes `claim_components`, and convenience projections remain available as `supported_components`, `unsupported_components`, and `contradicted_components`.

### 2. Structured context alignment

The old coarse `context_match` is split into:

```text
alignment
  subject_match
  outcome_match
  condition_match
  condition_mismatches[]
```

For the adversarial condition case:

```text
Claim:    8 nm at room temperature
Evidence: 8 nm at 145 C

subject_match   = MATCH
outcome_match   = MATCH
condition_match = MISMATCH
```

For backwards compatibility, `reliability_factors.context_match` is still emitted, but code derives it from the richer alignment. A condition-only mismatch therefore produces `PARTIAL_MATCH` overall rather than hiding the actual temperature mismatch.

### 3. System-owned facts stay outside LLM judgement

`source_originality` is derived from provenance metadata (`PRIMARY_STUDY`, `SECONDARY_SOURCE`, `UNKNOWN`) rather than guessed from prose. The final reliability category is also aggregated by transparent application policy rather than directly chosen by the model.

## Install

Requires Python 3.11+.

```bash
cd citation-needed-v1.2
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
pip install pytest
```

Set your API key:

```bash
export OPENAI_API_KEY="your_key_here"
```

Optional default model override:

```bash
export CITATION_NEEDED_MODEL="gpt-5.6-terra"
```

## Run one judgement

Hosted semantic judge:

```bash
python scripts/run_judgement.py \
  --backend openai \
  --claim examples/claim.json \
  --evidence examples/evidence.json
```

Overclaim case:

```bash
python scripts/run_judgement.py \
  --backend openai \
  --claim examples/claim_overreach.json \
  --evidence examples/evidence_overreach.json
```

A deterministic local smoke-test backend is still retained for schema/plumbing tests:

```bash
python scripts/run_judgement.py \
  --claim examples/claim.json \
  --evidence examples/evidence.json
```

## Run adversarial semantic suite

```bash
python scripts/run_adversarial_suite.py \
  --out data/adversarial_report.json
```

The five cases currently test:

- claim overreach / scope expansion
- direct contradiction
- related but insufficient evidence
- secondary-source provenance
- experimental-condition mismatch

The v1.2 suite specifically checks that the condition-mismatch example reports:

```text
subject_match   = MATCH
outcome_match   = MATCH
condition_match = MISMATCH
context_match   = PARTIAL_MATCH   # derived compatibility field
```

It also checks whether claim decomposition contains the expected support states.

## Run unit tests

```bash
pytest -q
```

Expected for the packaged version:

```text
11 passed
```

## Design invariants

1. Original assertion text and normalized claim are separate.
2. Citation purpose is explicit.
3. Every evidence item carries provenance.
4. Reported information and AI inference are distinct epistemic states.
5. Relevance, support, and reliability are different questions.
6. Unknown is not treated as negative evidence.
7. Source-level quality is not inferred merely because an excerpt is incomplete.
8. Condition mismatches stay explicit rather than disappearing into an overall context label.
9. Reliability is derived from explicit factors, not an unexplained confidence score.
10. Every judgement remains traceable back to evidence and source location.

## Next boundary

v1.2 is still primarily a **relation-level judge**. It does not yet constitute a full source-quality or cross-paper reliability assessment. The next distinct layers are intentionally separate:

```text
Full source context
  -> Source Assessor
     method completeness
     characterization quality
     reporting clarity

Multiple independent papers
  -> Cross-source Assessor
     reproducibility
     cross-source consistency
```

Do not collapse those into the relation judge just because an LLM can emit the fields.
