# Manually supplied cited papers

This folder is the human-in-the-loop fallback when Citation Needed can identify a cited paper but cannot automatically retrieve its full text.

For the bundled Gita validation case, place reference **[17]** here using one of these filenames:

```text
papers/cited/reference_17.pdf     # recommended
papers/cited/ref_17.pdf
papers/cited/17.pdf
papers/cited/10.1039_c3ra47681b.pdf
```

The live Gita audit checks this folder **before** Crossref/Unpaywall acquisition. If a matching PDF is present, it is used directly and remote acquisition is skipped.

You can also bypass filename discovery:

```bash
python scripts/run_gita_live_audit.py --cited-pdf /path/to/the/cited-paper.pdf
```

Important: the local file is treated only as a researcher-supplied source artifact. The normal Parser -> Evidence Retriever -> Relation Judge -> Source Assessor -> Reliability Policy still run unchanged.
