#!/usr/bin/env python3
"""Compare scores ONLY for identical response, condition and full geometry pairs.
Reports unmatched IDs and changed geometry/eligibility separately. Same data with
new algorithm is comparable; changed eligibility version is excluded by default.
"""
import argparse,json
from pathlib import Path
import pandas as pd
KEY=['object_id','image_id','worker_id','condition','reference_id','answer_geometry_sha256','reference_geometry_sha256','eligibility_version']
def compare(a,b,out):
 for t in [a,b]:
  if any(k not in t for k in KEY+['score','status']):raise ValueError('Missing versioned score contract')
  if t.duplicated(KEY).any():raise ValueError('Duplicate identity/geometry key')
 shared=a.merge(b,on=KEY,how='outer',suffixes=('_old','_new'),indicator=True,validate='one_to_one');shared.to_csv(out/'population_audit.csv',index=False)
 good=shared[(shared['_merge']=='both')&(shared.status_old=='evaluable')&(shared.status_new=='evaluable')].copy()
 good['score_change']=good.score_new-good.score_old;good.to_csv(out/'same_set_deltas.csv',index=False)
 summary={'old_rows':len(a),'new_rows':len(b),'same_full_key_evaluable':len(good),'unmatched_old_keys':int((shared['_merge']=='left_only').sum()),'unmatched_new_keys':int((shared['_merge']=='right_only').sum()),'mean_change_descriptive_only':float(good.score_change.mean()) if len(good) else None,'interpretation':'not a validity test; changed reference/geometry/eligibility never treated as algorithm-only difference'}
 (out/'SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False));return summary
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--old',required=True,type=Path);p.add_argument('--new',required=True,type=Path);p.add_argument('--out',required=True,type=Path);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
 print(json.dumps(compare(pd.read_csv(a.old),pd.read_csv(a.new),a.out),indent=2))
