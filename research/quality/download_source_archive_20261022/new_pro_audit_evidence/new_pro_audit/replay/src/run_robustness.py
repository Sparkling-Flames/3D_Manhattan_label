"""Separate mechanism/property/sensitivity audits; none is a human validity proof."""
import json,time,itertools
from dataclasses import replace
from pathlib import Path
import numpy as np,pandas as pd
from shapely.geometry import Polygon
from geomscore import *
from run_controls import geom,square,rotate,erp
O=Path(__file__).resolve().parents[1]
def wj(name,x):(O/'results'/name).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False))
def dense_tf(pa,pr,nshift=1001):
 ca,va=turning_rep(pa);cr,vr=turning_rep(pr);best=np.inf
 for t in np.linspace(0,1,nshift):
  br=np.unique(np.r_[0,ca[1:-1],np.mod(cr[:-1]-t,1),1]);dd=np.diff(br);ss=(br[1:]+br[:-1])/2
  z=turning_value(ca,va,ss)-turning_value(cr,vr,ss+t);loss=dd@((z-dd@z)**2);best=min(best,loss)
 return np.rad2deg(np.sqrt(best))

def main():
 pairs=json.load(open(O/'inputs/current_pairs.json'));scores=pd.read_csv(O/'results/current244_scores.csv').set_index('object_id');selves=json.load(open(O/'inputs/reference_self.json'))
 # Geometry-preserving insertion on every actual current reference, heights linear in real arclength.
 insert=[];gta=[]
 for x in selves:
  r=shell(x['reference']);p=r['p'];h=r['h'];k=int(np.argmax(r['length']));point=(p[k]+p[(k+1)%len(p)])/2;hnew=(h[k]+h[(k+1)%len(p)])/2
  pp=np.insert(p,k+1,point,axis=0);hh=np.insert(h,k+1,hnew);res=score_pair(geom(pp,hh),x['reference'])
  insert.append(dict(reference_id=x['reference_id'],QA=res['QA'],QB=res['QB'],QC=res['QC'],mean_error=abs(res['surface_height']['mean_A']-r['mu'])))
  counts=[len(simplify(p,t)[0]) for t in [.01,.03,.06]]
  tr,_=turns(p); u=p-np.roll(p,1,axis=0);v=np.roll(p,-1,axis=0)-np.roll(p,1,axis=0);proj=np.clip((u*v).sum(1)/(v*v).sum(1),0,1)
  dev=np.linalg.norm(u-proj[:,None]*v,axis=1)
  near=(abs(tr)<=1)&(dev<=.01)
  gta.append(dict(reference_id=x['reference_id'],raw_pairs=len(p),exact_floor_pairs=len(exact_floor(p)),at_001=counts[0],at_003=counts[1],at_006=counts[2],near_straight_candidates=int(near.sum()),max_own_top_std_over_mean=r['std']/r['mu']))
 pd.DataFrame(insert).to_csv(O/'results/reference77_redundant_insert.csv',index=False);pd.DataFrame(gta).to_csv(O/'results/GT_resolution_audit.csv',index=False)
 # Common rigid rotation is an invariance expectation, apart from quadrature and simplifier choices.
 inv=[]
 for p in pairs[::12]:
  base=score_pair(p['answer'],p['reference'])
  a=p['answer'];r=p['reference']
  reversed_g={k:np.array(a[k])[::-1].tolist() for k in ['bottom3d','top3d']}
  shifted_g={k:np.roll(np.array(a[k]),2,axis=0).tolist() for k in ['bottom3d','top3d']}
  for kind,ag,rg in [('reverse',reversed_g,r),('cyclic',shifted_g,r),('common_rotation_23',rotate(a,23),rotate(r,23))]:
   s=score_pair(ag,rg);inv.append(dict(object_id=p['object_id'],kind=kind,**{'delta_'+k:s[k]-base[k] for k in ['QA','QB','QC']}))
 pd.DataFrame(inv).to_csv(O/'results/invariance_audit.csv',index=False)
 # Step refinement all real records (component C and local height only are sampled).
 conv=[]
 for p in pairs:
  s=score_pair(p['answer'],p['reference'],replace(Config(),step_h=.0025,min_samples=1024));b=scores.loc[p['object_id']]
  conv.append(dict(object_id=p['object_id'],**{'delta_'+k:float(s[k]-b[k]) for k in ['QA','QB','QC']}))
 pd.DataFrame(conv).to_csv(O/'results/quadrature_refinement244.csv',index=False)
 # No optimization: predeclared coarse sensitivity, preserve every tested configuration.
 configs={'working':Config(),'angle15':replace(Config(),angle_scale_deg=15),'angle30':replace(Config(),angle_scale_deg=30),'detail0':replace(Config(),edit_budget=0),
 'detail025':replace(Config(),edit_budget=.25),'finer_resolution':replace(Config(),simplify_h=(.005,.015,.03)),
 'coarser_resolution':replace(Config(),simplify_h=(.02,.06,.12)), 'placement10_30':replace(Config(),placement_free_deg=10,placement_zero_deg=30),
 'placement20_60':replace(Config(),placement_free_deg=20,placement_zero_deg=60),'turning45':replace(Config(),turning_scale_deg=45),
 'turning75':replace(Config(),turning_scale_deg=75),'wall_weight05':replace(Config(),wall_weight=.5), 'local_scale015':replace(Config(),local_scale=.15),'local_scale030':replace(Config(),local_scale=.30)}
 sr=[]
 baseline=json.load(open(O/'results/current244_measurements.json'))
 chosen={p['object_id'] for p in pairs[::12]}|set(scores[scores.same_feedback_reference_id&scores.same_feedback_reference_geometry].index)
 # Scalar-only variants replay ALL 244. Geometric correspondence variants use a declared 39/40-case subset.
 for name,cfg in configs.items():
  geometry_variant=name in ['angle15','angle30','finer_resolution','coarser_resolution','placement10_30','placement20_60']
  for p in pairs:
   if geometry_variant and p['object_id'] not in chosen:continue
   old=baseline[p['object_id']];b=scores.loc[p['object_id']]
   ad=angle_detail(shell(p['answer'])['p'],shell(p['reference'])['p'],cfg) if geometry_variant else old['angle_detail']
   hh=old['surface_height'];H=(max(hh['local_error']-cfg.local_free,0)/cfg.local_scale)**2+(max(hh['mean_log_error']-np.log(cfg.mean_free_ratio),0)/np.log(cfg.mean_scale_ratio))**2
   I=old['I'];tp=(max(old['turning']['distance_deg']-cfg.turning_free_deg,0)/cfg.turning_scale_deg)**2
   res=dict(QA=100*I*np.exp(-ad['angle_penalty']-H)*(1-cfg.edit_budget*ad['structural_loss']),QB=100*I**cfg.range_power_bc*np.exp(-tp-H),QC=100*I**cfg.range_power_bc*np.exp(-cfg.wall_weight*hh['wall_loss']-H))
   sr.append(dict(config=name,object_id=p['object_id'],case_id='' if pd.isna(b['case_id']) else b['case_id'],**res))
  pd.DataFrame(sr).to_csv(O/'results/coarse_sensitivity.csv',index=False)
  print('config',name,'done',flush=True)
 wj('sensitivity_configurations.json',{k:asdict(v) for k,v in configs.items()})
 # Independent dense shift search checks event solver, not an external library equivalence claim.
 tfcheck=[]
 for p in pairs[::41]:
  a=shell(p['answer'])['p'];r=shell(p['reference'])['p'];fast=turning_distance(a,r)['distance_deg'];dense=dense_tf(a,r)
  tfcheck.append(dict(object_id=p['object_id'],event_exact_deg=fast,dense_grid_deg=dense,dense_minus_event=dense-fast))
 pd.DataFrame(tfcheck).to_csv(O/'results/turning_event_dense_check.csv',index=False)
 # Descriptive ordinal reversals: all crossed pairs are dependent; no significance claims.
 ordinal=[];bad=[];rank={'poor':0,'average_poor':1,'average':2,'good_average':3,'good':4}
 for name,use in [('strict20',scores.same_feedback_reference_id&scores.same_feedback_reference_geometry),('alias_geometry22',scores.same_feedback_reference_geometry)]:
  sub=scores[use].copy();n=0
  for ver in ['WQ','A10','B8L2','IoU3D100','QA','QB','QC']:
   n=wrong=tied=0
   for (ida,a),(idb,b) in itertools.combinations(sub.iterrows(),2):
    g=rank[a.grade]-rank[b.grade]
    if not g:continue
    n+=1;z=(a[ver]-b[ver])*g
    if z<0:
     wrong+=1;bad.append(dict(cohort=name,algorithm=ver,caseA=a.case_id,caseB=b.case_id,scoreA=a[ver],scoreB=b[ver]))
    elif z==0:tied+=1
   ordinal.append(dict(cohort=name,algorithm=ver,n=len(sub),ordered_pairs=n,reversals=wrong,tied=tied))
 pd.DataFrame(ordinal).to_csv(O/'results/ordinal_descriptive.csv',index=False);pd.DataFrame(bad).to_csv(O/'results/ordinal_reversal_cases.csv',index=False)
 # The archived prism's corner mean is NOT invariant to exact edge subdivision.
 r=geom(square(),[1,2,3,2]);a=geom(np.insert(square(),1,[0,-2],axis=0),[1,1.5,2,3,2])
 rr=shell(r);aa=shell(a);prism=100*min(np.mean(aa['h']),np.mean(rr['h']))/max(np.mean(aa['h']),np.mean(rr['h']))
 wj('prism_subdivision.json',dict(answer=a,reference=r,old_prism_IoU3D100=prism,arc_mean_A=aa['mu'],arc_mean_R=rr['mu'],new_scores=score_pair(a,r)))
 summary=dict(current_n=len(pairs),synthetic_n=len(json.load(open(O/'inputs/synthetic_geometry.json'))),
               self_min=pd.read_csv(O/'results/reference_self77.csv')[['QA','QB','QC']].min().to_dict(),insert_min=pd.DataFrame(insert)[['QA','QB','QC']].min().to_dict(),
               invariance_max_by_type=pd.DataFrame(inv).groupby('kind')[['delta_QA','delta_QB','delta_QC']].agg(lambda x:float(abs(x).max())).to_dict('index'),
               quadrature_max=pd.DataFrame(conv)[['delta_QA','delta_QB','delta_QC']].abs().max().to_dict(),quadrature_p95=pd.DataFrame(conv)[['delta_QA','delta_QB','delta_QC']].abs().quantile(.95).to_dict(),
               reference_near_straight_count=int((pd.DataFrame(gta).near_straight_candidates>0).sum()),
               turning_dense_check_min=float(pd.DataFrame(tfcheck).dense_minus_event.min()),turning_dense_check_max=float(pd.DataFrame(tfcheck).dense_minus_event.max()),
               ordinal=ordinal)
 wj('ROBUSTNESS_SUMMARY.json',summary);print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
