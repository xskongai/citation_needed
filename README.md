# Citation Needed — Reference Resolution v1.7

v1.7 keeps the validated v1.6 extraction + judgement stack and adds the next bridge: **resolve an in-text numeric citation to its bibliography entry and establish as much source identity as the supplied bibliography actually supports**.

```text
Scientific text
    |
    v
Citation-bearing Assertion Extraction        [v1.6]
    |
    v
CitationRelation: reference [17]
    |
    v
Reference Parser + Local Source Resolver      [v1.7]
    |-- bibliography entry found?
    |-- DOI / URL present?
    |-- publication year extracted?
    |-- canonical cited_paper_id when safe
    |
    v
Evidence Retrieval                            [next]
    |
    v
Relation Judge + Source Assessor + Reliability Policy
```

## What v1.7 adds

- deterministic numeric bibliography parsing for `[17] ...` and `17. ...`
- multiline bibliography-entry reconstruction
- conservative DOI / URL / publication-year extraction
- `CitationResolution` and `IdentityBasis`
- explicit resolution states:
  - `RESOLVED`: bibliography entry found **and** a canonical identifier (DOI / URL, or already-structured title+year metadata) is available
  - `PARTIALLY_RESOLVED`: bibliography entry found but canonical source identity is not yet established
  - `UNRESOLVED`: no matching bibliography entry (or ambiguous duplicate)
  - `SOURCE_UNAVAILABLE`: reserved for a later acquisition stage; not used merely because a reference could not be resolved
- deterministic `cited_paper_id` generation from canonical identity
- no LLM guessing of missing titles, DOI, authors, or source identity
- a seven-case resolution suite, including a real Gita-paper bibliography entry

Core rule:

```text
Reference entry found != source fully resolved
UNRESOLVED != source unavailable
Missing DOI != bad source
```

## Why local resolution first?

The citation marker `[17]` is only meaningful inside Paper A. Before querying Crossref, OpenAlex, Unpaywall, or a repository, the system must first establish **which bibliography entry Paper A means**. v1.7 makes that mapping deterministic and auditable.

Remote metadata lookup and full-text acquisition are deliberately deferred. This prevents an external search result from silently replacing the source actually cited by the paper.

## Install

```bash
cd citation-needed-v1.7
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

## Run the resolution suite

```bash
python scripts/run_resolution_suite.py \
  --out data/resolution_report.json
```

The suite covers:

1. DOI-backed canonical resolution
2. URL-backed canonical resolution
3. real Gita bibliography entry without DOI -> `PARTIALLY_RESOLVED`
4. missing bibliography number -> `UNRESOLVED`
5. multiline bibliography reconstruction
6. dot-style numeric references (`17.`)
7. duplicate reference numbers -> `UNRESOLVED` rather than silent selection

## Existing semantic suites

```bash
python scripts/run_extraction_suite.py --out data/extraction_report.json
python scripts/run_adversarial_suite.py --out data/adversarial_report.json
python scripts/run_source_suite.py --out data/source_assessment_report.json
python scripts/run_reliability_suite.py --out data/reliability_report.json
```

## Current architecture

```text
StructuredDocument
      |
      v
Assertion + CitationRelation Extraction       DONE
      |
      v
Reference / Source Resolution                 DONE (local bibliography identity)
      |
      v
Remote Metadata + Full-text Acquisition       NEXT / NOT DONE
      |
      v
Evidence Retrieval                            NOT DONE
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

## Important boundary

v1.7 does **not** claim that a raw bibliography string uniquely identifies a paper. If the entry has no DOI/URL and no pre-structured title+year metadata, the result remains `PARTIALLY_RESOLVED` rather than inventing a canonical identity.

Next: **remote source metadata resolution + evidence retrieval contract** so the pipeline can move from `Paper A -> [17] -> Paper B -> relevant evidence`.
