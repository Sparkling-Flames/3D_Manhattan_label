#!/usr/bin/env python3
"""Score pre-bound eligible records. No reference search, repairs, or imputation.
Input JSON: list of records with identity, eligibility_version, input_revision,
eligible (bool), geometry answer/reference, and Sb/Hcenter source and value.
This interface is downstream of the project's loader, not a replacement loader.
"""
from pathlib import Path
import argparse,json,hashlib,sys
from dataclasses import asdict
import pandas as pd
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'src'))
from structure_quality import working_config,VERSION,structure,candidate_score,floor_iou,mean_height,direction_rms
from run_audit import xz

def sha(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def score_records(records):
 output=[];seen=set();cfg=working_config()
 for r in records:
  required=['object_id','image_id','worker_id','condition','reference_id','eligibility_version','input_revision','eligible']
  if any(k not in r for k in required):raise ValueError('Identity/eligibility contract missing')
  if not isinstance(r['eligible'],bool):raise ValueError('eligible must be a frozen boolean')
  if r['object_id'] in seen:raise ValueError('Duplicate object_id in one snapshot')
  seen.add(r['object_id']);o={k:r[k] for k in required};o.update(algorithm_id=VERSION,config_sha256=sha(asdict(cfg)),score=None)
  if not r['eligible']:o['status']='excluded_by_frozen_manifest';output.append(o);continue
  try:
   a,b=r['answer'],r['reference'];o['answer_geometry_sha256']=sha(a);o['reference_geometry_sha256']=sha(b)
   sb,hc=r['Sb'],r['Hcenter'];o['Sb_source']=r['Sb_source'];o['Hcenter_source']=r['Hcenter_source']
   if not o['Sb_source'] or not o['Hcenter_source']:raise ValueError('Missing carried-metric provenance')
   c=structure(xz(a),xz(b),cfg);i=floor_iou(xz(a),xz(b));hm=abs(mean_height(a)/mean_height(b)-1)
   o.update(C=c['C'],structure_precision=c['precision'],structure_recall=c['recall'],I=i,D_diagnostic=direction_rms(xz(a)),Hm=hm,Sb=sb,Hcenter=hc,score=candidate_score(i,sb,hm,hc,c['C'],cfg),status='evaluable')
  except (KeyError,ValueError,TypeError) as e:o['status']='not_evaluable:'+str(e)
  output.append(o)
 return pd.DataFrame(output)
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 if a.out.exists():raise FileExistsError('Output exists')
 score_records(json.loads(a.input.read_text(encoding='utf8'))).to_csv(a.out,index=False)
