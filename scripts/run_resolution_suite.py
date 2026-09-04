#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from citation_needed.models import CitationRelation, CitationPurpose, FollowPriority
from citation_needed.resolution import parse_reference_section, resolve_citation_relation


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--suite', default='examples/resolution_suite.json')
    parser.add_argument('--out', default='data/resolution_report.json')
    args = parser.parse_args()

    cases = json.loads(Path(args.suite).read_text())
    report = []
    passed = 0

    for idx, case in enumerate(cases, 1):
        text = Path(case['reference_section']).read_text()
        refs = parse_reference_section(text)
        relation = CitationRelation(
            id=f"relation-{idx}",
            assertion_id=f"assertion-{idx}",
            source_paper_id="paper-a",
            reference_number=case['reference_number'],
            citation_context=f"Synthetic citation [{case['reference_number']}].",
            purpose=CitationPurpose.SUPPORT,
            follow_priority=FollowPriority.MEDIUM,
        )
        result = resolve_citation_relation(relation, refs)

        errors = []
        if result.status.value != case['expected_status']:
            errors.append(f"status: got {result.status.value!r}, expected {case['expected_status']!r}")
        if result.identity_basis.value != case['expected_basis']:
            errors.append(f"basis: got {result.identity_basis.value!r}, expected {case['expected_basis']!r}")
        if 'expected_doi' in case:
            got = result.reference_entry.doi if result.reference_entry else None
            if got != case['expected_doi']:
                errors.append(f"doi: got {got!r}, expected {case['expected_doi']!r}")
        if 'expected_year' in case:
            got = result.reference_entry.year if result.reference_entry else None
            if got != case['expected_year']:
                errors.append(f"year: got {got!r}, expected {case['expected_year']!r}")
        if 'raw_contains' in case:
            raw = result.reference_entry.raw_text if result.reference_entry else ''
            if case['raw_contains'] not in raw:
                errors.append(f"raw reference did not contain {case['raw_contains']!r}")

        ok = not errors
        passed += int(ok)
        print(
            f"[{'PASS' if ok else 'REVIEW'}] {case['name']}: "
            f"ref=[{case['reference_number']}] status={result.status.value} "
            f"basis={result.identity_basis.value} paper_id={result.cited_paper_id}"
        )
        for error in errors:
            print(f"  - {error}")

        report.append({
            'name': case['name'],
            'passed': ok,
            'errors': errors,
            'result': result.model_dump(mode='json'),
        })

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2))
    print(f"\n{passed}/{len(cases)} cases matched the declared expectations.")
    print(f"Report written to {out}")


if __name__ == '__main__':
    main()
