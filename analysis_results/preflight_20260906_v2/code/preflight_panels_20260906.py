"""Actual-current20 support, panel dependence and cross-fitted strata.
Permutation contrasts describe this finite roster, not causal effects of worker type.
"""
from pathlib import Path
from itertools import combinations
import sys,math,json
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from tools.thesis_main.analysis.preflight_data_20260906 import load,save,OUT,CURRENT
from tools.thesis_main.analysis.preflight_statistics_20260906 import moments,finite_var
SEED=20260906

def support(groups,rows):
 rr=[];dense=[]
 all_groups=dict(groups)
 for key,q in pd.DataFrame(rows).groupby('context',sort=True):
  if key not in all_groups:
   first=q.iloc[0];valid=q[q.valid]
   all_groups[key]=dict(context=key,image=first.base_task_id,building=first.building_id,stage=first.stage,condition=first.condition,n=len(valid),workers=valid.worker_id.to_numpy())
 for g in all_groups.values():
  pool=sorted(set(g['workers'])&set(CURRENT));missing=sorted(set(CURRENT)-set(pool))
  mask=sum(1<<j for j,w in enumerate(CURRENT) if w in pool)
  for k in range(15,21):
   rr.append(dict(context=g['context'],image=g['image'],building=g['building'],stage=g['stage'],condition=g['condition'],
                  historical_N=g['n'],current20_N=len(pool),k=k,feasible=len(pool)>=k,feasible_panel_count=math.comb(len(pool),k) if len(pool)>=k else 0,
                  supported_workers=';'.join(map(str,pool)),missing_workers=';'.join(map(str,missing)),shortfall=max(0,k-len(pool))))
  if len(pool)>=15:dense.append((g,mask))
 save('current20_support_gaps.csv',rr)
 summary=pd.DataFrame(rr).groupby(['stage','condition','k']).agg(contexts=('context','size'),supported=('feasible','sum')).reset_index();save('current20_support_summary.csv',summary)
 panels=[];summ=[]
 for k in range(15,21):
  comb=list(combinations(range(20),k));masks=np.array([sum(1<<j for j in c) for c in comb],dtype=np.uint32)
  support_masks=np.array([s for g,s in dense],dtype=np.uint32)
  inc=(masks[:,None]&support_masks[None,:])==masks[:,None]
  for j,c in enumerate(comb):
   gg=[dense[z][0] for z in np.flatnonzero(inc[j])]
   panels.append(dict(k=k,workers=';'.join(map(str,CURRENT[list(c)])),contexts=len(gg),buildings=len({g['building'] for g in gg}),
      P1_manual=sum(g['stage']=='P1' and g['condition']=='manual' for g in gg),P1_semi=sum(g['stage']=='P1' and g['condition']=='semi' for g in gg),
      C1_manual=sum(g['stage']=='C1' and g['condition']=='manual' for g in gg)))
  summ.append(dict(k=k,panel_count=len(comb),min_common_contexts=int(inc.sum(1).min()),max_common_contexts=int(inc.sum(1).max()),median_common_contexts=float(np.median(inc.sum(1)))))
 save('current20_panel_candidates.csv',panels);save('current20_panel_feasibility.csv',summ)
 return rr

def fixed_vs_independent(groups):
 rng=np.random.default_rng(SEED+11);rr=[];allcommon=[g for g in groups.values() if set(CURRENT)<=set(g['workers'])]
 strata=sorted({(g['stage'],g['condition']) for g in allcommon})
 for stage,condition in strata:
  gg=[g for g in allcommon if (g['stage'],g['condition'])==(stage,condition)];M=len(gg)
  matrices=[]
  for g in gg:
   idx=[list(g['workers']).index(w) for w in CURRENT];matrices.append(g['D'][np.ix_(idx,idx)])
  meanD=np.stack(matrices).mean(0)
  # Exact covariance-inclusive fixed-panel variance is the U-stat variance of the average distance matrix.
  for k in range(15,21):
   exact_fixed=finite_var(moments(meanD),k)
   exact_ind=sum(finite_var(moments(D),k) for D in matrices)/M**2
   sampled=[]
   for rep in range(1000):
    same=rng.choice(20,k,replace=False);fixed=meanD[np.ix_(same,same)].sum()/(k*(k-1));ind=[]
    for D in matrices:
     ids=rng.choice(20,k,replace=False);ind.append(D[np.ix_(ids,ids)].sum()/(k*(k-1)))
    sampled.append((fixed,np.mean(ind)))
   draws=np.array(sampled);save(f'panels/{stage}_{condition}_k{k}_draws.csv',[dict(replicate=i,fixed_panel=x,independent_per_image=y) for i,(x,y) in enumerate(draws)])
   rr.append(dict(stage=stage,condition=condition,k=k,images=M,buildings=len({g['building'] for g in gg}),target=meanD.sum()/380,
      exact_fixed_panel_variance=exact_fixed,exact_independent_variance=exact_ind,cross_image_covariance_contribution=exact_fixed-exact_ind,
      exact_variance_ratio=exact_fixed/exact_ind if exact_ind>1e-20 else np.nan,
      simulated_fixed_variance=draws[:,0].var(),simulated_independent_variance=draws[:,1].var(),
      fixed_mean=draws[:,0].mean(),independent_mean=draws[:,1].mean(),endpoint_mechanical=k==20))
 save('fixed_panel_vs_independent.csv',rr)
 save('fixed_panel_common_images.csv',[dict(context=g['context'],image=g['image'],building=g['building'],stage=g['stage'],condition=g['condition']) for g in allcommon])

def worker_effect(rows,feature):
 d=pd.DataFrame(rows);d=d[(d.stage=='C1')&(d.condition=='manual')&d.valid&d.worker_id.isin(CURRENT)].copy()
 if feature=='log_time':
  d=d[d.time_status.isin(['owner_valid_complete','owner_valid_complete_with_deviation']) & np.isfinite(d.time) & (d.time>0)]
  d['value']=np.log1p(d.time)
 else:d['value']=d[feature]
 return d

def fit_effect(d):
 workers=sorted(d.worker_id.unique());tasks=sorted(d.context.unique());wi={w:j for j,w in enumerate(workers)};ti={t:j for j,t in enumerate(tasks)}
 A=np.zeros((len(tasks),len(workers)));ws=np.zeros(len(workers));ts=np.zeros(len(tasks))
 for r in d.itertuples():
  w=wi[r.worker_id];t=ti[r.context];A[t,w]+=1;ws[w]+=r.value;ts[t]+=r.value
 counts=A.sum(1);normal=np.diag(A.sum(0))-A.T@(A/counts[:,None]);rhs=ws-A.T@(ts/counts)
 rank=np.linalg.matrix_rank(normal,tol=1e-8)
 if rank!=len(workers)-1:return {},rank
 effects=np.linalg.lstsq(normal,rhs,rcond=None)[0];effects-=effects.mean()
 return dict(zip(workers,effects)),rank

def separation(D,workers,high):
 a=np.array([j for j,w in enumerate(workers) if w in high]);b=np.array([j for j,w in enumerate(workers) if w not in high])
 if min(len(a),len(b))<2:return None
 aa=D[np.ix_(a,a)].sum()/(len(a)*(len(a)-1));bb=D[np.ix_(b,b)].sum()/(len(b)*(len(b)-1));ab=D[np.ix_(a,b)].mean()
 return aa,bb,ab,len(a),len(b)

def strata(rows,groups):
 outputs=[];profiles=[];gaps=[];perm_summary=[]
 for feature in ['corners','log_time']:
  source=worker_effect(rows,feature);rng=np.random.default_rng(SEED+21)
  shuffled=[set(rng.permutation(CURRENT)[:10]) for _ in range(600)]
  store=[]
  for building in sorted({g['building'] for g in groups.values()}):
   train=source[source.building_id!=building];effect,rank=fit_effect(train)
   valid={int(w) for w,q in train.groupby('worker_id') if len(q)>=3 and q.building_id.nunique()>=2}
   if set(effect)!=set(CURRENT) or valid!=set(CURRENT):
    gaps.append(dict(feature=feature,building=building,reason='incomplete_or_disconnected_training_support',missing=';'.join(map(str,set(CURRENT)-valid))))
    continue
   high=set(sorted(CURRENT,key=lambda w:(effect[w],w))[10:])
   for w in CURRENT: profiles.append(dict(feature=feature,heldout_building=building,worker=int(w),effect=effect[w],group='high' if w in high else 'low',training_rank=rank))
   for g in groups.values():
    if g['building']!=building or g['condition']!='manual':continue
    idx=np.flatnonzero(np.isin(g['workers'],CURRENT));D=g['D'][np.ix_(idx,idx)];workers=g['workers'][idx]
    sep=separation(D,workers,high)
    if sep is None:continue
    aa,bb,ab,na,nb=sep
    if min(na,nb)<4:
     gaps.append(dict(feature=feature,building=building,context=g['context'],reason='k6_4plus2_and2plus4_not_common_supported',available_high=na,available_low=nb));continue
    for nh,nl in [(4,2),(3,3),(2,4),(10,5),(5,10)]:
     feasible=na>=nh and nb>=nl
     if not feasible:
      gaps.append(dict(feature=feature,building=building,context=g['context'],reason=f'composition_{nh}+{nl}_unsupported',available_high=na,available_low=nb));continue
     expected=(math.comb(nh,2)*aa+math.comb(nl,2)*bb+nh*nl*ab)/math.comb(nh+nl,2)
     a=np.array([j for j,w in enumerate(workers) if w in high]);b=np.array([j for j,w in enumerate(workers) if w not in high]);vals=[];qvals=[]
     reference=g['reference'][idx]
     for rep in range(160):
      s=np.r_[rng.choice(a,nh,replace=False),rng.choice(b,nl,replace=False)];S=D[np.ix_(s,s)];pick=s[S.sum(1).argmin()]
      vals.append(S.sum()/((nh+nl)*(nh+nl-1)))
      if np.isfinite(reference[pick]):qvals.append(reference[pick])
     outputs.append(dict(feature=feature,context=g['context'],image=g['image'],building=building,stage=g['stage'],n_high=nh,n_low=nl,k=nh+nl,
                          available_high=na,available_low=nb,expected_pairwise_D=expected,simulated_pairwise_D=np.mean(vals),
                          medoid_reference_distance=np.mean(qvals) if qvals else np.nan,reference_n=len(qvals),
                          group_separation=ab-.5*(aa+bb),group_definition='crossfitted_rank_split_not_natural_type'))
    if len(workers)==20:
     rand=[separation(D,workers,h) for h in shuffled]
     store.append((g,ab-.5*(aa+bb),np.array([x[2]-.5*(x[0]+x[1]) for x in rand])))
  if store:
   buildings=sorted({g['building'] for g,o,r in store});observed=[];random=[]
   for b in buildings:
    ss=[(o,r) for g,o,r in store if g['building']==b];observed.append(np.mean([o for o,r in ss]));random.append(np.mean([r for o,r in ss],axis=0))
   obs=np.mean(observed);draws=np.mean(random,axis=0)
   perm_summary.append(dict(feature=feature,contexts=len(store),buildings=len(buildings),observed_separation=obs,random_mean=draws.mean(),
        random_q025=np.quantile(draws,.025),random_q975=np.quantile(draws,.975),random_upper_tail_fraction=(1+np.sum(draws>=obs))/(len(draws)+1),
        interpretation='exploratory_finite_roster_permutation_benchmark_not_causal_or_confirmatory_p'))
 save('crossfit_current20_profiles.csv',profiles);save('current20_composition_replay.csv',outputs)
 save('composition_support_gaps.csv',gaps);save('strata_vs_random_partition.csv',perm_summary)

if __name__=='__main__':
 rows,groups,refs=load();support(groups,rows);fixed_vs_independent(groups);strata(rows,groups);print('DONE panels',flush=True)
