#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from citation_needed.models import Evidence, SourceAssessmentInput
from citation_needed.source_assessment import assess_source_openai

def load(p: Path): return json.loads(p.read_text(encoding="utf-8"))
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--suite",type=Path,default=ROOT/"examples"/"source_suite.json"); ap.add_argument("--model",default=None); ap.add_argument("--out",type=Path,default=ROOT/"data"/"source_assessment_report.json"); a=ap.parse_args()
    suite=load(a.suite); report=[]; passed=0
    for case in suite["cases"]:
        src=SourceAssessmentInput.model_validate(load(ROOT/case["source"])); ev=[Evidence.model_validate(x) for x in load(ROOT/case["evidence"])["evidence"]]
        r=assess_source_openai(src,ev,model=a.model); d=r.model_dump(mode="json"); issues=[]
        for k,allowed in case["expected"].items():
            allowed=allowed if isinstance(allowed,list) else [allowed]
            if d.get(k) not in allowed: issues.append(f"{k}: got {d.get(k)!r}, expected one of {allowed!r}")
        status="PASS" if not issues else "REVIEW"; passed += (status=="PASS")
        print(f"[{status}] {case['id']}: directness={d['evidence_directness']} method={d['method_completeness']} measurement={d['measurement_appropriateness']} reporting={d['reporting_completeness']} originality={d['source_originality']} consistency={d['internal_consistency']}")
        for issue in issues: print("  - "+issue)
        report.append({"case":case["id"],"status":status,"issues":issues,"result":d})
    a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"\n{passed}/{len(suite['cases'])} cases matched the declared expectations."); print(f"Report written to {a.out}")
if __name__=="__main__": main()
