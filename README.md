# Citation Needed — Source Acquisition v1.9

v1.9 fills the availability gap between **Reference Resolution** and **Evidence Retrieval**.

```text
Paper A
  |
  v
Citation-bearing Assertion Extraction       [v1.6] DONE
  |
  v
Reference Resolution                         [v1.7] DONE
  |
  v
Source Acquisition                           [v1.9] NEW
  |-- Crossref metadata lookup
  |-- optional Unpaywall OA-location lookup
  |-- guarded full-text artifact download
  |-- explicit availability states
  |-- exact artifact provenance + SHA-256
  |
  v
Acquired source artifact
  |
  v
Source Parsing / StructuredDocument          NEXT
  |
  v
Evidence Retriever                           [v1.8] DONE
  |
  v
Relation Judge + Source Assessor + Reliability Policy
```

## Core boundary

v1.9 answers:

> **Where is the cited source, and what content can we actually obtain?**

It does **not** answer:

- whether the source supports the claim;
- whether the source is scientifically good;
- which passage is evidence;
- whether an unavailable paper is negative evidence.

```text
source unavailable != evidence absent
abstract != full text
landing page != full text
metadata-only != bad source
```

## Acquisition states

```text
FULL_TEXT_AVAILABLE
ABSTRACT_ONLY
METADATA_ONLY
ACCESS_RESTRICTED
NOT_FOUND
ACQUISITION_FAILED
UNRESOLVED
```

The distinctions are intentional:

- `ACCESS_RESTRICTED`: a source appears to exist, but usable full text is not openly available through the attempted routes.
- `NOT_FOUND`: the remote identity lookup returned not-found states.
- `ACQUISITION_FAILED`: network/tooling failed, so absence was **not established**.
- `UNRESOLVED`: the citation identity itself was not resolved, so remote acquisition was not attempted.

## Providers in v1.9

### Crossref

Used for DOI metadata and provider-declared full-text links when present.

### Unpaywall

Used optionally for open-access locations. Set either:

```bash
export CITATION_NEEDED_CONTACT_EMAIL="you@example.com"
```

or pass `--contact-email` to the CLI.

### Direct URL

A bibliography URL ending in a clear full-text format such as `.pdf`, `.xml`, or `.txt` can be fetched directly.

## Guardrails

### 1. A landing page is not full text

The acquirer does not mark a generic HTML landing page as `FULL_TEXT_AVAILABLE`.

### 2. PDF candidate returning HTML is rejected as full text

This catches common login / access pages returned from a URL that looked like a PDF.

### 3. Full-text bytes are system-owned

Downloaded artifacts are saved locally with:

- source URL;
- provider;
- detected media type;
- byte size;
- SHA-256 checksum.

### 4. Network failure is not `NOT_FOUND`

A timeout or connection failure becomes `ACQUISITION_FAILED`, preserving epistemic uncertainty.

## Install

```bash
cd citation-needed-v1.9
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
pip install pytest
```

No OpenAI key is needed for the acquisition layer itself.

## Local tests

```bash
pytest -q
```

## Run the deterministic acquisition suite

This suite uses a fake HTTP transport, so it does not depend on external services:

```bash
python scripts/run_acquisition_suite.py \
  --out data/acquisition_report.json
```

It covers:

1. open-access PDF -> `FULL_TEXT_AVAILABLE`
2. abstract without full text -> `ABSTRACT_ONLY`
3. metadata only -> `METADATA_ONLY`
4. known non-OA source -> `ACCESS_RESTRICTED`
5. provider 404s -> `NOT_FOUND`
6. network failure -> `ACQUISITION_FAILED`
7. PDF URL returning login HTML must **not** become full text
8. direct PDF URL acquisition

## Run a real acquisition

First produce or save a single `CitationResolution` JSON, then:

```bash
python scripts/run_acquisition.py \
  --resolution data/resolution.json \
  --contact-email "you@example.com" \
  --artifact-dir data/acquired \
  --out data/acquisition.json
```

Remote behavior depends on source availability, publisher/repository access, and provider uptime. The deterministic suite tests our policy and state transitions; a live run tests external integration.

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
Remote Source Acquisition                  DONE (v1.9 baseline)
  |
  v
Raw PDF/XML/Text artifact
  |
  v
Source Parser -> StructuredDocument        NOT DONE
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

The next missing contract is deliberately small:

```text
AcquiredArtifact
      |
      v
Source Parser
      |
      v
StructuredDocument
```

Once that parser exists, the first true single-citation end-to-end audit can connect:

```text
Paper A -> citation -> Paper B -> acquired full text -> parsed source
        -> evidence -> judgement -> source assessment -> reliability
```
