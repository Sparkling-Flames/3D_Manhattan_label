"""Score explicitly frozen, authorized answer/reference pairs; never choose a reference.
Run `python src/score_manifest.py --help`. Every row keeps status and all identity hashes.
The cohort authorization is a frozen audit claim, not independently inferred from geometry.
"""
import argparse,hashlib,json,sys
from dataclasses import asdict
from pathlib import Path
import pandas as pd
import numpy as np
from geomscore import Config,score_pair
from run_real import flat

def digest(x):
 return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def run(manifest_path,output_path):
 mpath=Path(manifest_path).resolve();base=mpath.parent;m=json.loads(mpath.read_text());pp=base/m['pairs_file'];cp=base/m['config_file']
 if sha(pp)!=m['pairs_file_sha256']:raise ValueError('pair file hash mismatch')
 if sha(cp)!=m['config_file_sha256']:raise ValueError('config hash mismatch')
 cfg=Config(**json.loads(cp.read_text()));pairs=json.loads(pp.read_text());rows=[];seen=set()
 for p in pairs:
  ident=(p['object_id'],p['reference_id'],p['current_target_id'])
  if ident in seen:raise ValueError('duplicate answer/reference/target identity')
  seen.add(ident)
  record={k:p[k] for k in ['object_id','reference_id','current_target_id','image_id','worker_id','condition','answer_sha256','reference_sha256']}
  record.update(algorithm_version=cfg.version,config_sha256=sha(cp),geometry_implementation_sha256=sha(Path(__file__).parent/'geomscore.py'),eligibility_version=m['eligibility_version'],reference_catalog_sha256=m['reference_catalog_sha256'])
  auth=m['authorization'].get(p['object_id'])
  reason=None
  if not auth or not auth.get('eligible'):reason='not_authorized_current_cohort'
  elif auth.get('gt_error_excluded') or auth.get('image_analysis_blocked'):reason='excluded_reference_or_image'
  elif auth.get('pool_source_workers',0)<3:reason='source_pool_below_three'
  elif p['worker_id'] in m['excluded_workers']:reason='excluded_worker'
  elif auth['reference_id']!=p['reference_id'] or auth['current_target_id']!=p['current_target_id']:reason='fixed_reference_binding_mismatch'
  elif digest(p['answer'])!=p['answer_sha256'] or digest(p['reference'])!=p['reference_sha256']:reason='explicit_geometry_hash_mismatch'
  if reason:record.update(status='excluded',reason=reason,QA=None,QB=None,QC=None)
  else:
   try:
    s=score_pair(p['answer'],p['reference'],cfg)
    if not s['answer_camera_inside'] or not s['reference_camera_inside']:
     record.update(status='not_evaluable',reason='camera_outside_explicit_footprint',QA=None,QB=None,QC=None)
    else:record.update(flat(s),status='ok',reason='')
   except (ValueError,ArithmeticError) as exc:record.update(status='not_evaluable',reason=str(exc),QA=None,QB=None,QC=None)
  rows.append(record)
 out=Path(output_path)
 if out.exists():raise FileExistsError('choose a new output; frozen scores are never overwritten')
 out.parent.mkdir(parents=True,exist_ok=True);pd.DataFrame(rows).to_csv(out,index=False)
 print(json.dumps({'rows':len(rows),'statuses':pd.DataFrame(rows).status.value_counts().to_dict(),'output':str(out)},ensure_ascii=False))
 return rows
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--manifest',default='RUN_MANIFEST.json');ap.add_argument('--out',required=True);a=ap.parse_args();run(a.manifest,a.out)
