# Citation Needed — Evidence Retriever v1.8

v1.8 adds the missing bridge between a resolved citation and the existing judgement stack: **retrieve exact, auditable evidence passages from a supplied cited paper**.

```text
Paper A
  |
  v
Citation-bearing Assertion Extraction      [v1.6]
  |
  v
Reference Resolution                        [v1.7]
  |
  v
Cited Paper B as StructuredDocument
  |
  v
Evidence Retriever                          [v1.8]
  |-- deterministic candidate generation
  |-- semantic relevance selection
  |-- exact passage materialization
  |-- provenance preserved
  |
  v
Evidence + Provenance
  |
  +------------------+
  v                  v
Relation Judge   Source Assessor
  +--------+---------+
           v
   Reliability Policy
```

## Important boundary

v1.8 assumes **Paper B has already been acquired and parsed into `StructuredDocument`**.

It does **not** yet download papers from DOI/URL, query Crossref/OpenAlex/Unpaywall, or parse PDF bytes. Those belong to the source-acquisition layer.

This separation is deliberate:

```text
Citation resolution != source acquisition != evidence retrieval
```

## What v1.8 adds

### 1. `EvidenceCandidate`

Every retrieval candidate is an exact passage from the supplied cited source and carries:

- source paper ID
- section ID
- retrieval-local passage index
- exact passage text
- source location copied from the parser
- evidence type (`TEXT`, `METHOD`, `RESULT`)
- lexical prefilter score
- matched query terms
- small citation-purpose section boost

The generated passage index is **not written into source provenance as a fake paragraph number**.

### 2. Cheap deterministic candidate generation

`build_evidence_candidates(...)` uses:

```text
normalized claim
+
citation context
+
small purpose-aware section preference
```

to create a short candidate set.

Purpose preference is only a boost, never a hard filter. A result passage is not removed merely because the citation was classified as METHOD, and vice versa.

### 3. Semantic selector with anti-confirmation-bias rule

The hosted selector is explicitly told:

```text
Retrieval != support judgement
```

It may retrieve passages that:

- support the claim
- contradict the claim
- qualify/limit the claim
- expose a condition mismatch
- provide method/parameter context

A contradictory value is therefore **successful retrieval**, not a retrieval failure.

### 4. Candidate-ID-only materialization

The LLM cannot write evidence text.

It returns only candidate IDs:

```text
[cand:results:1, cand:methods:2]
```

Code then copies the exact system-owned candidate text into `Evidence` objects.

Unknown/invented candidate IDs are ignored and recorded as warnings.

### 5. Explicit retrieval states

```text
FOUND
NO_RELEVANT_EVIDENCE
SOURCE_UNAVAILABLE
UNRESOLVED
```

Examples:

- cited paper not supplied -> `SOURCE_UNAVAILABLE`
- supplied paper ID does not match `citation_relation.cited_paper_id` -> `UNRESOLVED`
- paper is supplied but contains no directly relevant evidence -> `NO_RELEVANT_EVIDENCE`

Core rule:

```text
No relevant evidence found != source unavailable
Related topic != relevant evidence
Contradiction != retrieval failure
```

## Install

```bash
cd citation-needed-v1.8
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
pip install pytest
export OPENAI_API_KEY="your_key_here"
```

## Local tests

```bash
pytest -q
```

## Run the hosted retrieval suite

```bash
python scripts/run_retrieval_suite.py \
  --out data/retrieval_report.json
```

The suite covers:

1. real-paper-inspired specific capacitance retrieval
2. method/condition retrieval (`pH 12`, `145 °C`, `24 hours`)
3. contradictory numeric evidence must still be retrieved (`8 nm` claim vs `18 nm` source)
4. condition mismatch must still be retrieved (`5 A/g` claim vs `1 A/g` source)
5. unrelated thermal-conductivity claim -> `NO_RELEVANT_EVIDENCE`

## Run one retrieval

```bash
python scripts/run_retrieval.py \
  --assertion examples/your_assertion.json \
  --citation examples/your_citation.json \
  --source-document examples/your_cited_paper.json \
  --source-role PRIMARY_STUDY \
  --out data/retrieval.json
```

## Current architecture

```text
Structured Paper A
      |
      v
Assertion + CitationRelation Extraction       DONE
      |
      v
Local Bibliography Resolution                 DONE
      |
      v
Remote Metadata / Full-text Acquisition       NOT DONE
      |
      v
Structured Paper B
      |
      v
Evidence Retrieval                            DONE (v1.8 baseline)
      |
      v
Evidence + Provenance
      |                 |
      v                 v
Relation Judge      Source Assessor            DONE
      +--------+--------+
               v
       Reliability Policy                      DONE
```

## Why this is still a baseline

The candidate generator is intentionally simple: lexical overlap + small section-purpose boosts, followed by semantic selection. It is designed to validate the **retrieval contract and safeguards** before introducing embeddings, vector indexes, figure/table retrieval, or domain-specific retrieval strategies.

Next after semantic validation: connect `Reference Resolution -> Source Acquisition -> StructuredDocument -> Evidence Retriever`, then run the first true `Paper A -> Paper B -> Evidence -> Judgement` end-to-end audit.
