"""Independent interval, finite-window and same-building audit (read-only).
Uses reviewed archived prefix partitions/windows. Does not recluster raw geometry.
All intervals are logical missing-state bounds, NOT confidence intervals.
"""
from __future__ import annotations
import argparse,json,hashlib,math
from pathlib import Path
import numpy as np
import pandas as pd
SEED=20260909

def save(out,name,d):
 out.mkdir(parents=True,exist_ok=True)
 (d if isinstance(d,pd.DataFrame) else pd.DataFrame(d)).to_csv(out/name,index=False,float_format='%.12g',compression={'method':'gzip','mtime':0} if name.endswith('.gz') else None)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def err(pl,pu,tl,tu):
 return np.maximum(0,np.maximum(pl-tu,tl-pu)),np.maximum(abs(pl-tu),abs(pu-tl))
def joint(pl,pu,ql,qu,tl,tu):
 """Bounds on |q-t|-|p-t| sharing the SAME target t, pointwise.
 Optimizing separately over baseline groups/nodes still yields conservative bounds.
 """
 values=np.broadcast_arrays(pl,pu,ql,qu,tl,tu)
 p,P,q,Q,t,T=values
 candidates=np.stack([t,T,np.clip(p,t,T),np.clip(P,t,T),np.clip(q,t,T),np.clip(Q,t,T),np.clip((p+P)/2,t,T),np.clip((q+Q)/2,t,T)])
 lo=np.maximum(0,np.maximum(q[None]-candidates,candidates-Q[None]))-np.maximum(abs(candidates-p[None]),abs(candidates-P[None]))
 hi=np.maximum(abs(candidates-q[None]),abs(candidates-Q[None]))-np.maximum(0,np.maximum(p[None]-candidates,candidates-P[None]))
 return lo.min(0),hi.max(0)
def first(v):
 ix=np.flatnonzero(np.minimum.accumulate(np.asarray(v)[::-1])[::-1]>=.8-1e-12)
 return int(ix[0]+1) if len(ix) else np.nan

def math_tests(out):
 rng=np.random.default_rng(SEED);checks=[]
 for trial in range(100):
  p,P=np.sort(rng.random(2));q,Q=np.sort(rng.random(2));t,T=np.sort(rng.random(2))
  lo,hi=joint(p,P,q,Q,t,T);tt=np.linspace(t,T,10001)
  vlo=np.maximum(0,np.maximum(q-tt,tt-Q))-np.maximum(abs(tt-p),abs(tt-P))
  vhi=np.maximum(abs(tt-q),abs(tt-Q))-np.maximum(0,np.maximum(p-tt,tt-P))
  assert lo<=vlo.min()+1e-12 and hi>=vhi.max()-1e-12
  assert max(abs(lo-vlo.min()),abs(hi-vhi.max()))<1e-4
  checks.append(dict(trial=trial,analytic_lower=float(lo),grid_lower=vlo.min(),analytic_upper=float(hi),grid_upper=vhi.max()))
 for _ in range(200):
  a=rng.dirichlet(np.ones(8));b=rng.dirichlet(np.ones(8));k=int(rng.integers(1,30));h=int(rng.integers(1,6));mix=(k*a+h*b)/(k+h)
  tv=.5*abs(a-mix).sum();assert abs(tv-h/(k+h)*.5*abs(a-b).sum())<1e-12 and tv<=h/(k+h)+1e-12
 save(out,'scene_mathematical_checks.csv',checks)
 save(out,'share_criterion_ceiling.csv',[dict(k=k,h=h,maximum_TV=h/(k+h),epsilon=e,share_check_automatically_satisfied=h/(k+h)<=e+1e-12) for k in range(1,51) for h in [1,2,3,5] for e in [.05,.1,.2]])

def windows(base,out):
 counts=[];onsets=[];short=[];files=[];maxerr=0
 for cohort in ['with_workers','without_workers']:
  win=base/cohort/'replay/window_metrics.csv.gz';cur=base/cohort/'replay/stability_curves.csv';files.extend([win,cur]);parts=[];small=[]
  for d in pd.read_csv(win,chunksize=200000):
   d=d[d.config.isin(['q_0.950','ospa30_t6']) & d.lookahead.isin([1,5])].copy()
   if d.empty:continue
   evaluated=d.status=='evaluated';no_support=d.prefix_support_2==0
   d['unknown_calc']=~evaluated|no_support
   d['stable_calc']=evaluated&~no_support&(d.max_membership<=.1+1e-12)&(d.max_shares<=.1+1e-12)&(d.promotion_2==0)
   d['changing_calc']=~d.unknown_calc&~d.stable_calc
   # Main SOP is unchanged. This sidecar separates a KNOWN failed prerequisite.
   d['known_not_supported']=no_support&(evaluated|(d.k==1))
   keys=['image_id','config','k','lookahead']
   parts.append(d.groupby(keys)[['unknown_calc','stable_calc','changing_calc','known_not_supported']].sum().reset_index())
   e=d[(d.k==4)&(d.config=='q_0.950')][['image_id','replicate','lookahead','stable_calc','unknown_calc','changing_calc']]
   small.append(e)
  agg=pd.concat(parts).groupby(['image_id','config','k','lookahead']).sum().reset_index();agg['total']=agg.unknown_calc+agg.stable_calc+agg.changing_calc;assert (agg.total==200).all()
  source=pd.read_csv(cur);source=source[(source.min_support==2)&np.isclose(source.epsilon,.1)&source.config.isin(['q_0.950','ospa30_t6'])&source.lookahead.isin([1,5])]
  z=agg.merge(source,on=['image_id','config','k','lookahead'],validate='one_to_one')
  for a,b in [('unknown_calc','unknown'),('stable_calc','stable'),('changing_calc','changing')]:assert (z[a]==z[b]).all(),(a,b)
  z['upper_separate_known_support']=(z.stable+z.unknown-z.known_not_supported)/200;z['lower_separate_known_support']=z.stable/200;z['cohort']=cohort
  counts.append(z)
  for key,g in z.groupby(['image_id','building_id','config','lookahead']):
   g=g.sort_values('k');meta=dict(zip(['image_id','building_id','config','lookahead'],key))
   a,b,c=first(g.stable_lower),first(g.stable_upper),first(g.upper_separate_known_support)
   onsets.append(meta|dict(cohort=cohort,max_observed_k=g.k.max(),original_lower_onset=a,original_possible_onset=b,support_separated_possible_onset=c,original_identified=bool(np.isfinite(a) and a==b),support_separated_identified=bool(np.isfinite(a) and a==c)))
  pair=pd.concat(small).pivot(index=['image_id','replicate'],columns='lookahead',values=['stable_calc','unknown_calc','changing_calc']).dropna()
  keep=pair[('stable_calc',1)].astype(bool);q=pair[keep]
  short.append(dict(cohort=cohort,k=4,short_h=1,long_h=5,short_stable=len(q),long_stable=int(q[('stable_calc',5)].sum()),long_unknown=int(q[('unknown_calc',5)].sum()),long_changing=int(q[('changing_calc',5)].sum()),long_stable_rate=q[('stable_calc',5)].mean()))
 save(out,'window_recomputation_and_support_sensitivity.csv.gz',pd.concat(counts,ignore_index=True));save(out,'support_prerequisite_onsets.csv',onsets);save(out,'short_window_extension_recomputed.csv',short)
 return files,len(pd.concat(counts))

def transfer(base,out):
 f=base/'comparison/common_budget_curves.csv.gz';d=pd.read_csv(f);d=d[(d.lookahead==5)&(d.min_support==2)&np.isclose(d.epsilon,.1)];files=[f];results=[];checks=[]
 for cohort in ['with_workers','without_workers']:
  folder=base/'comparison'/('common_transfer_'+cohort);foldfile=folder/'folds.csv.gz';bgfile=folder/'baseline_groups.csv';files.extend([foldfile,bgfile]);folds=pd.read_csv(foldfile);outside=pd.read_csv(bgfile)
  vectors={(i,c):g.sort_values('k')[[f'stable_lower_{cohort}',f'stable_upper_{cohort}']].to_numpy() for (i,c),g in d.groupby(['image_id','config'])}
  # Do not let the 4094 uNb partitions dominate: explicit one-source and leave-one-target designs.
  selected=folds[(folds.source_n==1)|(folds.target_n==1)].copy()
  for r in selected.itertuples():
   n=int(r.k_nodes);sources=json.loads(r.source_images_json);targets=json.loads(r.target_images_json)
   prediction=np.mean([vectors[(i,r.config)][:n] for i in sources],axis=0)
   bs=outside[(outside.building_id==r.building_id)&(outside.source_n==r.source_n)]
   # Same saved outside IDs, same source count and common person budget, no tuning on target.
   groups=[json.loads(s) for s in bs.source_images_json];Q=np.stack([np.mean([vectors[(i,r.config)][:n] for i in g],axis=0) for g in groups])
   same=[];other=[];lower=[];upper=[];width=[]
   for image in targets:
    target=vectors[(image,r.config)][:n];sl,su=err(prediction[:,0],prediction[:,1],target[:,0],target[:,1]);ol,ou=err(Q[:,:,0],Q[:,:,1],target[:,0],target[:,1]);jl,ju=joint(prediction[:,0],prediction[:,1],Q[:,:,0],Q[:,:,1],target[:,0],target[:,1])
    same.append([sl.mean(),su.mean()]);other.append([ol.mean(),ou.mean()]);lower.append(jl.mean());upper.append(ju.mean());width.append(np.mean(target[:,1]-target[:,0]))
   s=np.mean(same,axis=0);o=np.mean(other,axis=0)
   maxdiff=max(abs(s[0]-r.same_error_lower),abs(s[1]-r.same_error_upper),abs(o[0]-r.outside_error_lower),abs(o[1]-r.outside_error_upper));assert maxdiff<1e-9
   checks.append(dict(cohort=cohort,building=r.building_id,config=r.config,fold_id=r.fold_id,max_abs_error=maxdiff))
   designs=[]
   if r.source_n==1:designs.append('one_source_image')
   if r.target_n==1:designs.append('leave_one_target')
   for design in designs:
    results.append(dict(cohort=cohort,building=r.building_id,config=r.config,design=design,fold_id=r.fold_id,source_n=r.source_n,target_n=r.target_n,budget=r.common_people_budget,images=r.source_n+r.target_n,k_nodes=n,same_lower=s[0],same_upper=s[1],outside_lower=o[0],outside_upper=o[1],old_benefit_lower=o[0]-s[1],old_benefit_upper=o[1]-s[0],shared_target_benefit_lower=np.mean(lower),shared_target_benefit_upper=np.mean(upper),target_unknown_width=np.mean(width),source_unknown_width=np.mean(prediction[:,1]-prediction[:,0]),identified_number_pairs=r.N_identified_pairs,identified_number_error_sum=r.N_absolute_error_sum))
 z=pd.DataFrame(results);numeric=['same_lower','same_upper','outside_lower','outside_upper','old_benefit_lower','old_benefit_upper','shared_target_benefit_lower','shared_target_benefit_upper','target_unknown_width','source_unknown_width']
 buildings=z.groupby(['cohort','config','design','building'])[numeric].mean().reset_index();top=[]
 for key,g in buildings.groupby(['cohort','config','design']):
  row=dict(zip(['cohort','config','design'],key));row.update(g[numeric].mean().to_dict());row.update(buildings=len(g),buildings_positive_bound=int((g.shared_target_benefit_lower>0).sum()),buildings_negative_bound=int((g.shared_target_benefit_upper<0).sum()),buildings_unresolved=int(((g.shared_target_benefit_lower<=0)&(g.shared_target_benefit_upper>=0)).sum()))
  top.append(row)
 assert (z.shared_target_benefit_lower>=z.old_benefit_lower-1e-9).all() and (z.shared_target_benefit_upper<=z.old_benefit_upper+1e-9).all()
 save(out,'transfer_recomputed_checks.csv',checks);save(out,'same_building_fixed_design_folds.csv',z);save(out,'same_building_fixed_design_buildings.csv',buildings);save(out,'same_building_fixed_design_summary.csv',top)
 return files,len(checks)

def main(repo,out):
 base=Path(repo)/'analysis_results/multibuilding_threshold_stability_20260909_v1/revised';out=Path(out);math_tests(out);files,n=windows(base,out);print('WINDOWS VERIFIED',n,flush=True);more,nfold=transfer(base,out);files+=more
 save(out,'scene_input_manifest.csv',[dict(path=str(p.relative_to(repo)),sha256=sha(p),bytes=p.stat().st_size) for p in files])
 (out/'SCENE_QA.json').write_text(json.dumps(dict(window_nodes_reproduced=n,selected_transfer_folds_reproduced=nfold,counts_identical=True,interval_formulas_independent=True,source='archived reviewed prefix windows and current common-budget curves',geometry_reclustered=False,hard_point_count_rule_unchanged=True,building_is_similarity_definition=True,new_person_generalization_tested=False,interval_type='logical missing-state bounds; shared-target bound is pointwise and conservative, not confidence'),indent=2))
 print(pd.read_csv(out/'same_building_fixed_design_summary.csv').query("config=='q_0.950'").to_string(index=False));print('SCENE DONE',flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();main(a.repo,a.out)
