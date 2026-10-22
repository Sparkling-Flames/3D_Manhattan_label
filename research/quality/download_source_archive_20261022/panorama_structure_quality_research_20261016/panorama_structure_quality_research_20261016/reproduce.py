#!/usr/bin/env python3
"""Offline snapshot replay. Does NOT claim a fresh project-loader/LFS execution."""
from __future__ import annotations
import argparse, hashlib, json, subprocess, sys
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
from structure_quality import structure, working_config, old_score, candidate_score, floor_iou, direction_rms, mean_height, length_dsc, boundary_iou
from run_audit import xz, prism_iou, geometry_from_points
from run_experiments import angular_boundary_mean

def readj(p):return json.loads(Path(p).read_text(encoding='utf8'))
def dump(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
def main(out:Path):
 if out.exists():raise FileExistsError('Choose a NEW output directory; archived results are immutable.')
 manifest=readj(ROOT/'INPUT_HASHES.json')
 for relative,expected in manifest.items():
  got=hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()
  if got!=expected:raise ValueError('Input hash mismatch: '+relative)
 out.mkdir(parents=True)
 checks=[]
 for filename in ['current891_frozen_components.csv','historical1145_frozen_components.csv']:
  d=pd.read_csv(ROOT/'inputs'/filename)
  for model in ['WQ','A10','B8L2']:
   column=model if model in d else 'Q_'+model
   calculated=old_score(d.iou_2d,d.S_bottom_deg,d.dir,d.Hmean,d.Hcenter,model)
   error=float(np.max(abs(calculated-d[column])))
   checks.append(dict(set=filename,model=model,n=len(d),max_abs_error=error))
   if error>1e-9:raise AssertionError((filename,model,error))
 pd.DataFrame(checks).to_csv(out/'scalar_parity.csv',index=False)
 g=readj(ROOT/'inputs/geometries30.json');baseline=pd.read_csv(ROOT/'inputs/frozen_metrics30.csv').set_index('case_id');feedback=pd.read_csv(ROOT/'inputs/FEEDBACK_30_JOINED.csv');arch=pd.read_csv(ROOT/'results/review30_working.csv').set_index('case_id')
 rows=[];coordinate=[]
 for _,f in feedback.iterrows():
  a,b=g[f.object_id.strip()],g[f.reference_id];m=baseline.loc[f.case_id];s=structure(xz(a),xz(b),working_config())
  i=floor_iou(xz(a),xz(b));dd=direction_rms(xz(a));hm=abs(mean_height(a)/mean_height(b)-1);i3=prism_iou(a,b)
  errors={k:abs(v-float(m[k])) for k,v in [('iou_2d',i),('dir',dd),('Hmean',hm),('IoU3D100',i3)]}
  if max(errors.values())>1e-8:raise AssertionError((f.case_id,errors))
  q=candidate_score(i,float(m.S_bottom_deg),hm,float(m.Hcenter),s['C'],working_config())
  if abs(q-arch.loc[f.case_id,'Q_RCS02'])>1e-8:raise AssertionError('Score mismatch '+f.case_id)
  rows.append(dict(case_id=f.case_id,object_id=f.object_id,reference_id=f.reference_id,C=s['C'],precision=s['precision'],recall=s['recall'],Q_RCS02=q,**{'error_'+k:v for k,v in errors.items()}))
 # Every stored answer and reference, rather than only the thirty answers.
 for oid,geom in g.items():
  converted=geometry_from_points(geom['points_1024x512'])
  e=max(float(np.max(abs(np.array(converted[key])-np.array(geom[key])))) for key in ['bottom3d','top3d'])
  if e>1e-10:raise AssertionError('ERP parity '+oid)
  coordinate.append(dict(object_id=oid,max_coordinate_error=e))
 pd.DataFrame(rows).to_csv(out/'review30_replayed.csv',index=False);pd.DataFrame(coordinate).to_csv(out/'ERP_all60_replayed.csv',index=False)
 current=pd.read_csv(ROOT/'inputs/current227_frozen_audit.csv').set_index('object_id');expected=pd.read_csv(ROOT/'results/current227_working.csv').set_index('object_id');rows=[]
 for p in readj(ROOT/'inputs/current_matched_pairs.json'):
  m=current.loc[p['object_id']];a,b=p['answer'],p['reference']
  if str(m.reference_id)!=p['reference_id']:raise AssertionError('Reference binding changed')
  s=structure(xz(a),xz(b),working_config());i=floor_iou(xz(a),xz(b));dd=direction_rms(xz(a));hm=abs(mean_height(a)/mean_height(b)-1);i3=prism_iou(a,b)
  errors={k:abs(v-float(m[k])) for k,v in [('iou_2d',i),('dir',dd),('Hmean',hm),('IoU3D100',i3)]}
  if max(errors.values())>1e-5:raise AssertionError((p['object_id'],errors))
  q=candidate_score(float(m.iou_2d),p['frozen_Sb'],float(m.Hmean),p['frozen_Hcenter'],s['C'],working_config())
  if abs(q-expected.loc[p['object_id'],'Q_RCS02'])>1e-8:raise AssertionError('Current score changed')
  rows.append(dict(object_id=p['object_id'],reference_id=p['reference_id'],C=s['C'],Q_RCS02=q,**{'error_'+k:v for k,v in errors.items()}))
 pd.DataFrame(rows).to_csv(out/'current227_replayed.csv',index=False)
 rows=[];expected=pd.read_csv(ROOT/'results/synthetic_controls.csv').set_index('case')
 for p in readj(ROOT/'inputs/synthetic_geometry_controls.json'):
  a,b=np.asarray(p['answer']),np.asarray(p['reference']);s=structure(a,b,working_config());i=floor_iou(a,b);sb=angular_boundary_mean(a,b);dd=direction_rms(a)
  q=candidate_score(i,sb,p['Hmean_control'],p['Hcenter_control'],s['C'],working_config());dsc=length_dsc(a,b)['length_dsc'];bi=boundary_iou(a,b)
  measured={'C':s['C'],'I':i,'D':dd,'Q_RCS02_arc_analogue':q,'length_dsc':dsc,'boundary_iou':bi}
  for k,v in measured.items():
   if abs(v-expected.loc[p['case'],k])>1e-8:raise AssertionError((p['case'],k))
  rows.append({'case':p['case'],**measured})
 pd.DataFrame(rows).to_csv(out/'synthetic72_replayed.csv',index=False)
 rows=[]
 for r in readj(ROOT/'inputs/current77_references.json'):
  geom=r['geometry'];p=xz(geom);s=structure(p,p,working_config());q=candidate_score(1,0,0,0,s['C'],working_config())
  if abs(q-100)>1e-10:raise AssertionError('self mismatch')
  rows.append(dict(reference_id=r['target_id'],C_self=s['C'],Q_self=q,B8L2_self=float(old_score(1,0,direction_rms(p),0,0))))
 pd.DataFrame(rows).to_csv(out/'current77_reference_self_replayed.csv',index=False)
 run=subprocess.run([sys.executable,'-m','pytest','-q',str(ROOT/'src/test_structure_quality.py')],cwd=ROOT,capture_output=True,text=True)
 (out/'tests.log').write_text(run.stdout+run.stderr,encoding='utf8')
 if run.returncode:raise RuntimeError('Unit tests failed; see tests.log')
 result=dict(status='PASS',input_hashes_verified=len(manifest),scalar_rows=2036,human_panel_pairs=30,current_supplement_pairs=227,unique_current_compatible_geometry_responses=242,ERP_objects=60,synthetic_controls=72,current_reference_self_checks=len(rows),qualification='offline snapshot replay; no fresh loader, LFS, photo audit, Sb/Hcenter geometry remeasurement or downstream replay')
 dump(out/'SUMMARY.json',result);print(json.dumps(result,ensure_ascii=False,indent=2));print(run.stdout)
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',required=True,type=Path);a=p.parse_args();main(a.out.resolve())
