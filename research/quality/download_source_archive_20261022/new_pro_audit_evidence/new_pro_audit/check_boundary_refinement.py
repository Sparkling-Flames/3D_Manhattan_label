"""Diagnostic-only quadrature refinement on yaw worst cases and a disclosed nearest-tie construction."""
from pathlib import Path
import sys,json,argparse
from dataclasses import replace
import numpy as np
ROOT=Path(__file__).resolve().parents[1];STUDY=ROOT/'new_pro_return/panorama_quality_three_routes_20261016'
sys.path.insert(0,str(STUDY/'src'))
from geomscore import Config,score_pair,shell
from run_controls import geom
pairs=json.loads((ROOT/'new_pro_audit/current891_extension/fixed891_pairs.json').read_text())
wanted={'R01568','R01510','R00772'};cases=[p for p in pairs if p['record_id'] in wanted]
tie=json.loads((ROOT/'new_pro_audit/common_yaw_height_tie.json').read_text())
a=np.array(tie['answer']);r=np.array(tie['reference']);rh=np.array([2.,2.,2.,4.]);mu=shell(geom(r,rh))['mu']
cases.append(dict(record_id='synthetic_nearest_tie_amp2',object_id='synthetic_nearest_tie_amp2',answer=geom(a,mu),reference=geom(r,rh)))
rot=np.array([[0.,-1.],[1.,0.]])
def rotate(g,M):
 out={k:np.array(g[k],float).copy() for k in ['bottom3d','top3d']}
 for v in out.values():v[:,[0,2]]=v[:,[0,2]]@M
 return {k:v.tolist() for k,v in out.items()}
rows=[]
for p in cases:
 for step in [.01,.005,.0025,.001,.0005]:
  cfg=replace(Config(),step_h=step,max_samples=200000)
  raw=[]
  for yaw,M in [(0,np.eye(2)),(90,rot),(180,-np.eye(2)),(270,-rot)]:
   s=score_pair(rotate(p['answer'],M),rotate(p['reference'],M),cfg)
   h=s['surface_height'];raw.append(dict(yaw=yaw,QA=s['QA'],QB=s['QB'],QC=s['QC'],I=s['I'],local_error=h['local_error'],height_penalty=h['local_penalty']+h['mean_penalty'],wall_loss=h['wall_loss'],distance_loss=h['distance_loss'],normal_loss=h['normal_loss'],max_step_h=h['max_step_h']))
  row=dict(record_id=p['record_id'],object_id=p['object_id'],step_h=step,states=raw,range_QA=max(x['QA'] for x in raw)-min(x['QA'] for x in raw),range_QB=max(x['QB'] for x in raw)-min(x['QB'] for x in raw),range_QC=max(x['QC'] for x in raw)-min(x['QC'] for x in raw),range_local=max(x['local_error'] for x in raw)-min(x['local_error'] for x in raw))
  rows.append(row);print(json.dumps({k:v for k,v in row.items() if k!='states'}),flush=True)
result=dict(diagnostic_config_change='Only integration step varied; max_samples increased to 200000 to permit refinement. This is NOT official GQS v2 scoring.',cases=[{k:p[k] for k in ['record_id','object_id','answer','reference']} for p in cases],rows=rows)
ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=ROOT/'new_pro_audit/boundary_refinement.json');args=ap.parse_args();out=args.out;assert not out.exists();out.write_text(json.dumps(result,indent=2)+'\n')
