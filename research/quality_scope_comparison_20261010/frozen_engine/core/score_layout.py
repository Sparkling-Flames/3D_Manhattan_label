#!/usr/bin/env python3
"""Score one unchanged annotation/reference JSON pair and preserve failures."""
import argparse
import json
from pathlib import Path

from quality_v11 import score_geometry, load_parameters, Parameters


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--annotation-json',required=True)
    p.add_argument('--reference-json',required=True)
    p.add_argument('--parameters')
    p.add_argument('--output')
    a=p.parse_args()
    ann=json.loads(Path(a.annotation_json).read_text(encoding='utf-8-sig'))
    ref=json.loads(Path(a.reference_json).read_text(encoding='utf-8-sig'))
    result=score_geometry(ann,ref,load_parameters(a.parameters) if a.parameters else Parameters())
    result.update(original_annotation=ann,frozen_reference=ref)
    text=json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    if a.output:Path(a.output).write_text(text,encoding='utf-8')
    else:print(text)


if __name__=='__main__':main()
