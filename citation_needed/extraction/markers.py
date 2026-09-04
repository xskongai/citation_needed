from __future__ import annotations

import re

# v1.6 deliberately supports numeric bracket citations first, e.g. [14], [1,2,3], [10-12,13].
_BRACKET_RE = re.compile(r"\[\s*([0-9][0-9,;\-–—\s]*)\]")


def _expand_token(token: str) -> list[str]:
    token = token.strip()
    if not token:
        return []
    m = re.fullmatch(r"(\d+)\s*[-–—]\s*(\d+)", token)
    if m:
        start, end = int(m.group(1)), int(m.group(2))
        if start <= end and end - start <= 100:
            return [str(i) for i in range(start, end + 1)]
    if token.isdigit():
        return [str(int(token))]
    return []


def extract_numeric_reference_numbers(text: str) -> list[str]:
    refs: list[str] = []
    for m in _BRACKET_RE.finditer(text):
        content = m.group(1).replace(";", ",")
        for token in content.split(","):
            for ref in _expand_token(token):
                if ref not in refs:
                    refs.append(ref)
    return refs
