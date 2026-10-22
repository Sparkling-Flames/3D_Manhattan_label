"""Score an explicit fixed manifest without finding/changing any reference.
The manifest is an analysis contract, not a collection of candidate GTs.
Ineligible, incomplete and invalid rows remain in the output with NA and reasons.
"""
from pathlib import Path
import argparse,json,hashlib
import numpy as np
from envelope_quality import normalized_pair
from b8_models import score,configs
import recompute_baseline as base

def geometry_hash(g):
 return hashlib.sha256(json.dumps(g,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def score_record(p):
 ids={k:p.get(k) for k in ['object_id','record_id','image_id','reference_id','current_target_id','reference_version','input_revision','difficulty_version','answer_sha256','reference_sha256','source_pool_workers']}
 if not p.get('original_quality_eligible',False):return dict(**ids,status='not_admitted',reason='explicit_analysis_eligibility_not_true',B8L2=None,B8L2_D10=None,EBC2_L2=None)
 if not p.get('reference_complete',False):return dict(**ids,status='reference_incomplete',reason='full_reference_not_approved',B8L2=None,B8L2_D10=None,EBC2_L2=None)
 if p.get('source_pool_workers',0)<3:return dict(**ids,status='source_pool_below3',reason='source_pool_under_current_minimum',B8L2=None,B8L2_D10=None,EBC2_L2=None)
 if p.get('worker_id') in ['W019','W026']:return dict(**ids,status='not_admitted',reason='existing_worker_exclusion',B8L2=None,B8L2_D10=None,EBC2_L2=None)
 if not p.get('reference_id') or p.get('reference_id')!=p.get('current_target_id'):return dict(**ids,status='binding_error',reason='fixed_reference_target_identity_mismatch',B8L2=None,B8L2_D10=None,EBC2_L2=None)
 for side in ['answer','reference']:
  try:actual=geometry_hash(p[side])
  except (KeyError,ValueError,TypeError):actual=None
  if actual!=p.get(side+'_sha256') or actual is None:return dict(**ids,status='hash_error',reason=side+'_geometry_hash_mismatch',B8L2=None,B8L2_D10=None,EBC2_L2=None)
 result=dict(**ids,status='complete',B8L2=None,B8L2_D10=None,EBC2_L2=None)
 if base.engine is None:base.initialize()
 old=base.engine.measure(p['answer'],p['reference']);new=normalized_pair(p['answer'],p['reference']);result['baseline_measurement']=old;result['new_measurement']=new
 if old['status']=='complete':
  m=old['metrics'];result['B8L2']=float(score(m['iou_2d'],m['S_bottom_deg'],m['dir'],m['Hmean'],m['Hcenter']));result['B8L2_D10']=float(score(m['iou_2d'],m['S_bottom_deg'],m['dir'],m['Hmean'],m['Hcenter'],configs()[1]));result['IoU3D_vertexmean100']=100*m['iou_3d_corner_mean']
 else:result['status']='partial_or_not_evaluable'
 if new['status']=='complete':result['EBC2_L2']=new['score_l2']
 else:result['status']='partial_or_not_evaluable'
 return result

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--input',required=True);ap.add_argument('--output',required=True);args=ap.parse_args();dest=Path(args.output)
 if dest.exists():raise SystemExit('Refusing to overwrite existing output: '+str(dest))
 records=json.loads(Path(args.input).read_text(encoding='utf-8-sig'));dest.parent.mkdir(parents=True,exist_ok=True)
 with dest.open('w',encoding='utf-8') as f:
  for p in records:f.write(json.dumps(score_record(p),ensure_ascii=False,allow_nan=False)+'\n');f.flush()
 print('Recorded',len(records),'rows; every original row retained.')
