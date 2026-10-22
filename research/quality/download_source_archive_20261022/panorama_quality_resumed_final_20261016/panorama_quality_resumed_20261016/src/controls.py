"""Mechanism controls using actual frozen baseline engine, not arc analogues.
All synthetic data are explicitly tagged; none enter real annotation denominators.
"""
from pathlib import Path
import json,sys,time,copy,math
from concurrent.futures import ProcessPoolExecutor
import numpy as np,pandas as pd
from dataclasses import replace
from b8_models import score,configs
from envelope_quality import Config,NormalizedConfig,measure_pair,normalized_pair,combine,shell
import recompute_baseline as base
ROOT=Path(__file__).resolve().parents[1]

def geom(p,h=2.):
 p=np.asarray(p,float);h=np.broadcast_to(np.asarray(h,float),len(p));b=np.column_stack([p[:,0],-np.ones(len(p)),p[:,1]]);t=b.copy();t[:,1]+=h
 return {'bottom3d':b.tolist(),'top3d':t.tolist()}
def transform(g,angle=0,shift=(0,0),scale=1.,roll=0,reverse=False):
 out={};c=np.cos(np.radians(angle));s=np.sin(np.radians(angle));M=np.array([[c,-s],[s,c]])
 for k in ['bottom3d','top3d']:
  a=np.asarray(g[k],float).copy();a[:,[0,2]]=(a[:,[0,2]]*scale)@M.T+shift
  if roll:a=np.roll(a,roll,axis=0)
  if reverse:a=a[::-1]
  out[k]=a.tolist()
 return out

def redundant(g):
 out={}
 for k in ['bottom3d','top3d']:
  a=np.asarray(g[k]);v=[]
  for i,p in enumerate(a):v.extend([p,(2*p+a[(i+1)%len(a)])/3])
  out[k]=np.asarray(v).tolist()
 return out

def make_controls():
 rows=json.loads((ROOT/'inputs/previous_synthetic93.json').read_text())
 for r in rows:r['provenance']='previous synthetic geometry; recomputed this run with real baseline engine'
 sq=geom([[-2,-2],[2,-2],[2,2],[-2,2]])
 extra=[]
 def add(name,a,r=sq,family='new_control',**kwargs):extra.append(dict(name=name,answer=a,reference=r,family=family,provenance='independently constructed this run',**kwargs))
 for eps in [0.,1e-5,1e-4,.001,.01,.03,.1,.3]:
  a=geom([[-2,-2],[0,-2-eps],[2,-2],[2,2],[-2,2]])
  add('near_collinear_'+str(eps),a,family='near_collinear')
  b=geom([[-2,-2],[-.2,-2],[-.2,-2-eps],[.2,-2-eps],[.2,-2],[2,-2],[2,2],[-2,2]]) if eps else sq
  add('short_true_bump_'+str(eps),b,family='short_wall')
 add('bottom_redundant_top_peak',geom([[-2,-2],[0,-2],[2,-2],[2,2],[-2,2]],[2,2.8,2,2,2]),family='height_not_redundant')
 add('full_exact_redundancy',redundant(sq),family='3d_redundant')
 # Crop target is the right half of old parent. Closure edge is part of target.
 parent=geom([[-2,-2],[2,-2],[2,2],[-2,2]])
 crop=geom([[0,-2],[2,-2],[2,2],[0,2]])
 add('crop_target_identity',crop,crop,'crop',introduced_scope_edges=[3],physical_wall_asserted=False)
 add('crop_deleted_parent_not_required',crop,crop,'crop',introduced_scope_edges=[3],physical_wall_asserted=False,parent_reference_not_scored=parent)
 add('crop_closure_shift_0.1',geom([[.1,-2],[2,-2],[2,2],[.1,2]]),crop,'crop',introduced_scope_edges=[3],physical_wall_asserted=False)
 add('crop_closure_shift_0.5',geom([[.5,-2],[2,-2],[2,2],[.5,2]]),crop,'crop',introduced_scope_edges=[3],physical_wall_asserted=False)
 add('crop_edge_join_diagonal',geom([[0,-2],[2,-2],[2,2],[.5,2]]),crop,'crop',introduced_scope_edges=[3],physical_wall_asserted=False)
 add('crop_extends_into_removed_parent',parent,crop,'crop',introduced_scope_edges=[3],physical_wall_asserted=False)
 # Factorial isolations are combined by geometry, not by fabricating components.
 for shift in [0.,.05,.2,.5]:
  for shear in [0.,.05,.2,.5]:
   for hdelta in [0.,.2]:
    p=np.array([[-2,-2],[2,-2],[2,2],[-2,2]],float);p[:,0]+=shear*p[:,1]+shift
    add(f'factor_dx{shift}_shear{shear}_local{hdelta}',geom(p,[2-hdelta,2+hdelta,2-hdelta,2+hdelta]),family='factorial',dx=shift,shear=shear,local_delta=hdelta)
 # Same normalized relative shape at different room sizes.
 for scale in [.25,1,4]:
  add(f'relative_scale_test_{scale}',transform(sq,angle=5,scale=scale),transform(sq,scale=scale),'normalization')
 # Nonorthogonal reference is legitimate for geometric comparison.
 non=geom([[-2,-2],[2,-2],[3,2],[-2,2]])
 add('nonorth_reference_identity',non,non,'nonorth_reference')
 add('nonorth_reference_regularized_wrong',sq,non,'nonorth_reference')
 # Pure severe area and mean-height extremes.
 for scale in [.25,.5,1.1,1.5,2.,4.]:add('pure_size_'+str(scale),transform(sq,scale=scale),family='range')
 for height in [1.,1.5,2.,2.2,2.4,3.,4.,8.]:add('pure_height_'+str(height),geom([[-2,-2],[2,-2],[2,2],[-2,2]],height),family='global_height')
 add('no_overlap',transform(sq,shift=(10,0)),family='zero_overlap')
 add('self_crossing',geom([[-2,-2],[2,2],[-2,2],[2,-2]]),family='invalid')
 add('missing_top',{'bottom3d':sq['bottom3d']},family='invalid')
 add('camera_outside_valid_shape',transform(sq,shift=(3,0)),family='camera_outside')
 rows.extend(extra)
 return rows

def one(r):
 out={k:r[k] for k in ['name','family','provenance']}
 for k in ['dx','shear','local_delta']:out[k]=r.get(k)
 try:
  m=base.engine.measure(r['answer'],r['reference']);out['baseline_status']=m['status']
  if m['status']=='complete':
   met=m['metrics'];out.update(met)
   for c in configs():out[c.name]=float(score(met['iou_2d'],met['S_bottom_deg'],met['dir'],met['Hmean'],met['Hcenter'],c))
   out['IoU3D100']=100*met['iou_3d_corner_mean']
  else:out['baseline_reason']=str(m.get('reasons'))
 except Exception as e:out['baseline_status']='exception';out['baseline_reason']=repr(e)
 for name,fn in [('EBC1',measure_pair),('EBC2',normalized_pair)]:
  try:
   m=fn(r['answer'],r['reference']);out[name+'_status']=m['status'];out[name]=m['score']
   if m['status']=='complete':out.update({name+'_'+k:m[k] for k in ['I','boundary_coverage','Hmean','Hcenter','score_l2','score_no_normals','score_range_only']})
   else:out[name+'_reason']=m['reason']
  except Exception as e:out[name+'_status']='exception';out[name+'_reason']=repr(e)
 return out

if __name__=='__main__':
 t=time.time();rows=make_controls();(ROOT/'inputs/synthetic_controls_all.json').write_text(json.dumps(rows,ensure_ascii=False,allow_nan=False))
 with ProcessPoolExecutor(max_workers=4,initializer=base.initialize) as pool:res=list(pool.map(one,rows,chunksize=4))
 pd.DataFrame(res).to_csv(ROOT/'results/controls_all_scores.csv',index=False)
 (ROOT/'results/controls_summary.json').write_text(json.dumps(dict(total=len(rows),statuses={n:pd.Series([r.get(n+'_status') for r in res]).value_counts().to_dict() for n in ['baseline','EBC1','EBC2']},seconds=time.time()-t),indent=2))
 print((ROOT/'results/controls_summary.json').read_text())
