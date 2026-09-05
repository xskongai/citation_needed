# Citation Needed — Source Parser v1.10

v1.10 closes the structural gap between **Source Acquisition** and **Evidence Retrieval**.

```text
Paper A
  |
  v
Citation-bearing Assertion Extraction       [v1.6] DONE
  |
  v
Reference Resolution                        [v1.7] DONE
  |
  v
Source Acquisition                          [v1.9] DONE
  |
  v
PDF / XML / HTML / TXT
  |
  v
Source Parser                               [v1.10] NEW
  |-- section classification
  |-- page/section provenance
  |-- bibliography extraction
  |-- abstract-only boundary
  |-- explicit parse states
  |
  v
StructuredDocument
  |
  v
Evidence Retriever                          [v1.8] DONE
  |
  v
Relation Judge + Source Assessor + Reliability Policy
```

## Core boundary

v1.10 answers:

> **How do we convert the source bytes we actually obtained into a traceable document structure that downstream retrieval can consume?**

It does **not** decide whether a passage supports a claim. That remains the responsibility of the Evidence Retriever and Relation Judge.

```text
parse failure != source absence
abstract-only != full-text parse
reference list != evidence section
page provenance must not be invented
```

## Supported input formats

- PDF via PyMuPDF
- JATS-like XML
- HTML
- plain text

## Structured output

`StructuredDocument` now includes typed sections:

```text
ABSTRACT
INTRODUCTION
METHODS
RESULTS
DISCUSSION
CONCLUSION
SUPPLEMENTARY
OTHER
```

References are parsed separately and are deliberately excluded from evidence-bearing sections.

Each parsed body unit keeps:

- exact source text;
- page when available;
- logical section heading;
- section type;
- local paragraph index.

For PDFs, visual line blocks are aggregated under the same heading within a page. This keeps page provenance while preventing line-wrapped scientific sentences from becoming isolated retrieval fragments.

## Parse states

```text
FULL_TEXT_PARSED
ABSTRACT_ONLY_PARSED
SOURCE_UNAVAILABLE
UNSUPPORTED_FORMAT
PARSE_FAILED
```

The distinction is intentional. For example, a restricted source remains `SOURCE_UNAVAILABLE`; it is not treated as an empty document.

## Install

```bash
cd citation-needed-v1.10
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
pip install pytest
```

No OpenAI key is needed for the parser layer itself.

## Local tests

```bash
pytest -q
```

Expected baseline for this package:

```text
65 passed
```

## Run the deterministic parser suite

```bash
python scripts/run_parser_suite.py \
  --out data/parser_report.json
```

The suite covers:

1. PDF section detection + page provenance
2. reference-list separation from evidence text
3. plain-text parsing
4. JATS-like XML parsing
5. HTML parsing
6. abstract-only source handling
7. restricted source handling
8. explicit parse-failure state

## Parse a v1.9 acquisition result

```bash
python scripts/run_parser.py \
  --source data/acquisition.json \
  --out data/parsed_source.json
```

The output is a `SourceParseResult` containing the downstream `StructuredDocument` contract.

## Current architecture

```text
Paper A
  |
  v
Extraction                                  DONE
  |
  v
Reference Resolution                       DONE
  |
  v
Source Acquisition                         DONE
  |
  v
Source Parser                              DONE (v1.10 baseline)
  |
  v
Evidence Retrieval                         DONE
  |
  v
Relation Judge                             DONE
  |
  v
Source Assessor                            DONE
  |
  v
Reliability Policy                         DONE
```

## Next

The next milestone is no longer another isolated component. It is the first orchestration layer:

```text
Paper A
 -> citation-bearing assertion
 -> resolve citation
 -> acquire Paper B
 -> parse Paper B
 -> retrieve evidence
 -> judge relation
 -> assess source
 -> reliability
```

That will be **v2.0 — Single Citation End-to-End Audit**.
