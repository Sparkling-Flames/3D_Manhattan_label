"""Evaluate frozen numerical components, without granting reference/worker eligibility."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/'src'))
from working_models import MODELS,score,attribution
p=argparse.ArgumentParser();p.add_argument('--model',choices=list(MODELS),required=True)
for name in ['I','Sb','D','Hm','Hc']:p.add_argument('--'+name,type=float,required=True)
a=p.parse_args();par=MODELS[a.model];r=attribution(a.I,a.Sb,a.D,a.Hm,a.Hc,par)
r.update(version=par.version,formal_eligibility_granted=False,interpretation='Conditional numerical score; caller must verify same target, complete reference and source restrictions.')
print(json.dumps(r,ensure_ascii=False,indent=2,allow_nan=False))
