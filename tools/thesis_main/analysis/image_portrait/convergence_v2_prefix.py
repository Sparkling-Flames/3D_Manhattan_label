"""Observed first-k updates for the uncertainty process, with disjoint future people.
No full-data labels, reference error or future outcomes enter prefix predictors.
Targets are future novelty, supported coverage, frequency drift, and new supported
modes; none is treated as a complete convergence definition.
"""
import collections,itertools,json,time
import numpy as np,pandas as pd
from tools.thesis_main.analysis.image_portrait.convergence_v2_common import *
from tools.thesis_main.analysis.image_portrait.convergence_v2_process import partition_stats
from scipy.linalg import solve

PX=['prefix_modes','prefix_supported_modes','prefix_supported_mass','prefix_largest_share','prefix_topology_disagreement','prefix_topology_entropy','prefix_same_point_pair_distance_contribution','prefix_scope_entropy','prefix_scope_known_fraction']
YS=['future_new_point_rate','future_new_geometry_rate','future_unsupported_geometry_rate','prefix_future_mass_TV','new_supported_future_mode']

def build(repeats=30):
 d=read_responses();d=d[d.main_worker_included&d.raw_condition.isin(['manual','semi'])];dense=boundary_map();rows=[];fails=[]
 for (image,arm),allg in d.groupby(['image_id','raw_condition']):
  g=allg[allg.geometry_valid].sort_values('worker_id').reset_index(drop=True);n=len(g)
  if not n:continue
  dm,pcs=pairs_for(g,dense);scope=g.scope.fillna('unknown').to_numpy()
  for k in [2,3,5]:
   if n<=k:
    fails.append(dict(image_id=image,condition=arm,prefix_k=k,n_valid=n,n_observed=len(allg),reason='no_unobserved_real_person_remains'));continue
   rng=np.random.default_rng(seed_for(image,arm,k,'prefix_update'))
   for rep in range(repeats):
    order=rng.permutation(n);ix=order[:k];future=order[k:];sub=dm[np.ix_(ix,ix)];lab=cluster(sub,pcs[ix],.1);stats=partition_stats(sub,pcs[ix],lab);med=medoids(sub,lab,1);smed=medoids(sub,lab,2);sizes=np.array([np.sum(lab==lab[j])for j in med]);p=sizes/k
    dist=dm[np.ix_(future,ix[med])];nearest=dist.argmin(1);unmatched=dist.min(1)>.1+1e-12;assigned=nearest.copy();assigned[unmatched]=len(med);freq=np.bincount(assigned,minlength=len(med)+1)/len(future);tv=.5*np.abs(np.r_[p,0.]-freq).sum()
    future_dm=dm[np.ix_(future,future)];future_labels=cluster(future_dm,pcs[future],.1);fm=medoids(future_dm,future_labels,2)
    new_supported=bool(len(fm) and (dm[np.ix_(future[fm],ix)].min(1)>.1+1e-12).any())
    tri=np.triu_indices(k,1);same=pcs[ix][tri[0]]==pcs[ix][tri[1]];contrib=float(sub[tri][same].sum()/len(tri[0]))
    known=[x for x in scope[ix]if x!='unknown']
    row=dict(image_id=image,building=image.split('_')[0],condition=arm,prefix_k=k,replay=rep,n_observed=len(allg),n_valid=n,n_invalid=len(allg)-n,future_n=len(future),prefix_workers=';'.join(g.worker_id.iloc[ix]),future_workers=';'.join(g.worker_id.iloc[future]),prefix_canonical_ids=';'.join(g.canonical_annotation_id.iloc[ix]),prefix_modes=stats['n_modes'],prefix_supported_modes=stats['n_supported_modes'],prefix_supported_mass=stats['supported_mass'],prefix_largest_share=stats['largest_share'],prefix_topology_disagreement=stats['topology_disagreement'],prefix_topology_entropy=stats['topology_entropy'],prefix_same_point_pair_distance_contribution=contrib,prefix_scope_entropy=entropy(known) if known else 0.,prefix_scope_known_fraction=len(known)/k,
      future_new_point_rate=float((~np.isin(pcs[future],pcs[ix])).mean()),future_new_geometry_rate=float((dm[np.ix_(future,ix)].min(1)>.1+1e-12).mean()),future_unsupported_geometry_rate=float((dm[np.ix_(future,ix[smed])].min(1)>.1+1e-12).mean()) if len(smed) else 1.,prefix_future_mass_TV=tv,new_supported_future_mode=float(new_supported))
    rows.append(row)
 return csv('prefix/observed_prefix_and_future.csv.gz',rows),csv('prefix/coverage_failures.csv',fails)


def fit_predict(x,y,tr,te,alpha):
 a=x[tr];b=x[te];mu=a.mean(0);sd=a.std(0);keep=sd>1e-12
 if not keep.any():return np.broadcast_to(np.median(y[tr],axis=0),(len(te),y.shape[1]))
 a=(a[:,keep]-mu[keep])/sd[keep];b=(b[:,keep]-mu[keep])/sd[keep];ym=y[tr].mean(0);beta=solve(a.T@a+alpha*np.eye(a.shape[1]),a.T@(y[tr]-ym),assume_a='pos',check_finite=False)
 return np.clip(b@beta+ym,0,1)

def evaluate(d):
 rows=[];bs=pd.read_csv(FOUND/'B/model_feedback.csv').set_index('image_id');cols=[c for c in bs if c!='building' and c!='hohonet_raw_vs_exported_boundary_max_pixel_difference'];meta=pd.read_csv(OUT/'images/evidence_layers.csv').set_index('image_id');scene=pd.get_dummies(meta.scene_human_adopted,dtype=float)
 for (arm,k),g in d.groupby(['condition','prefix_k']):
  g=g.sort_values(['image_id','replay']).reset_index(drop=True);ids=g.image_id.tolist();y=g[YS].to_numpy(float);building=g.building.to_numpy();n=g.n_valid.to_numpy(float)[:,None]
  cold=np.column_stack([n,bs.loc[ids,cols].to_numpy(float),scene.loc[ids].to_numpy(float)]);prefix=np.column_stack([n,g[PX].to_numpy(float)]);sets={'cold_portrait':cold,'prefix_only':prefix,'portrait_plus_prefix':np.column_stack([cold,g[PX].to_numpy(float)]),'horizon_only':n}
  for name,x in sets.items():
   for f in [r for r in core.load(BUNDLE/'evaluation/folds.jsonl.gz')if r['design']=='leave_building']:
    tr=np.flatnonzero(g.image_id.isin(f['train']).to_numpy());te=np.flatnonzero(g.image_id.isin(f['test']).to_numpy())
    if not len(te)or not len(tr):continue
    errors=np.zeros((4,len(YS)));cnt=0;alphas=[100.,10.,1.,.1]
    for vb in sorted(set(building[tr])):
     itr=tr[building[tr]!=vb];iv=tr[building[tr]==vb]
     if not len(itr):continue
     for j,a in enumerate(alphas):errors[j]+=np.abs(fit_predict(x,y,itr,iv,a)-y[iv]).sum(0)
     cnt+=len(iv)
    best=errors.argmin(0)if cnt else np.ones(len(YS),int);preds=[fit_predict(x,y,tr,te,a)for a in alphas]
    for t,target in enumerate(YS):
     pp=preds[best[t]][:,t]
     for pos,idx in enumerate(te):rows.append(dict(image_id=g.image_id.iloc[idx],building=building[idx],condition=arm,prefix_k=k,replay=int(g.replay.iloc[idx]),feature=name,target=target,truth=y[idx,t],prediction=pp[pos],absolute_error=abs(y[idx,t]-pp[pos]),alpha=alphas[best[t]],n_valid=int(g.n_valid.iloc[idx]),future_n=int(g.future_n.iloc[idx])))
   print('PREFIX FIT',arm,k,name,flush=True)
 pred=csv('prefix/predictions.csv.gz',rows);im=pred.groupby(['image_id','building','condition','prefix_k','feature','target'])[['absolute_error']].mean().reset_index();csv('prefix/image_prediction_errors.csv',im)
 summaries=im.groupby(['condition','prefix_k','feature','target']).agg(images=('image_id','size'),MAE=('absolute_error','mean'),buildings=('building','nunique')).reset_index();csv('prefix/score_summary.csv',summaries)
 results=[]
 for keys,g in im.groupby(['condition','prefix_k','target']):
  for a,b in [('prefix_only','cold_portrait'),('portrait_plus_prefix','prefix_only'),('portrait_plus_prefix','cold_portrait'),('cold_portrait','horizon_only')]:
   m=g[g.feature==a][['image_id','building','absolute_error']].merge(g[g.feature==b][['image_id','absolute_error']],on='image_id',suffixes=('','_base'));m['delta']=m.absolute_error-m.absolute_error_base;results.append(dict(condition=keys[0],prefix_k=keys[1],target=keys[2],feature=a,baseline=b,method_MAE=m.absolute_error.mean(),baseline_MAE=m.absolute_error_base.mean(),**paired_interval(m,'delta')))
 csv('prefix/paired_increments.csv',results)
 js('prefix/method.json',dict(prefix_people=[2,3,5],orders=30,cut=.1,targets=YS,prefix_features=PX,missing_pair_dispersion='Use sum of same-point pair d divided by all pairs: defined0 when no same-point pair, not imputed mean.',scope_missing='Known fraction retained; empty-known-set entropy convention0 is paired with known fraction.',future='Only actual disjoint people; none at terminaln; no duplicate workers.',TV='Prefix-defined modes + one unmatched overflow bucket; future assigned to nearest prefix mode medoid within cut. This evaluates distribution drift, not physical mode truth.',no_full_partition_in_predictors=True,training='Original building folds and inner building alpha selection; equal30 replays per image; inference aggregates by image then building',interpretation='Process update is not a complete convergence certificate and is not new-worker validation'))

if __name__=='__main__':
 p=OUT/'prefix/observed_prefix_and_future.csv.gz';d=pd.read_csv(p)if p.exists()else build()[0];evaluate(d)
