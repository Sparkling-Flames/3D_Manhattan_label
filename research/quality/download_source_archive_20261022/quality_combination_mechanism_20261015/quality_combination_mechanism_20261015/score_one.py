#!/usr/bin/env python3
"""Score already validated, complete frozen components. No reference selection."""
from pathlib import Path
import argparse,json,sys
sys.path.insert(0,str(Path(__file__).resolve().parent/'src'))
from mechanisms import score,MODEL_MAP
p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--model',choices=MODEL_MAP,default='B8L2');a=p.parse_args()
v=json.loads(a.input.read_text(encoding='utf-8-sig'))
try:
    q=float(score(*[v[k] for k in ['I','Sb','D','Hm','Hc']],a.model))
except (KeyError,ValueError,TypeError) as e:
    p.error(str(e))
print(json.dumps(dict(model=a.model,score=q,score_status='complete_components_only',reference_id=v.get('reference_id'),eligibility_granted=False),ensure_ascii=False,indent=2))
