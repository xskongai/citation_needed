#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from citation_needed.models import Evidence, SourceAssessmentInput
from citation_needed.source_assessment import assess_source_openai

def load(path: Path): return json.loads(path.read_text(encoding="utf-8"))
def main():
    p=argparse.ArgumentParser(); p.add_argument("--source",required=True,type=Path); p.add_argument("--evidence",required=True,type=Path); p.add_argument("--model",default=None); p.add_argument("--out",type=Path,default=None); a=p.parse_args()
    src=SourceAssessmentInput.model_validate(load(a.source)); ev=[Evidence.model_validate(x) for x in load(a.evidence)["evidence"]]
    result=assess_source_openai(src,ev,model=a.model); rendered=result.model_dump_json(indent=2)
    if a.out: a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_text(rendered+"\n",encoding="utf-8")
    print(rendered)
if __name__=="__main__": main()
