"""Actual all-n uncertainty-growth replays, prefix re-clustering and sensitivity.

The real arrival timestamps are absent. Random permutations are finite observed
worker-order sensitivity, not new participants and not calendar-time learning.
P: recent re-clustered mode pattern persistence.
D10/D20: P plus empirical frequency TV to the FULL OBSERVED partition <=.10/.20.
G10: D10 plus <=.02 change in within-mode pairwise median d_mask.
All are exploratory, retrospective and keep singleton/invalid status explicit.
"""
import argparse,collections,itertools,json,time
import numpy as np,pandas as pd
from tools.thesis_main.analysis.image_portrait.convergence_v2_common import *

RULES=['P_pattern','D10_distribution','D20_distribution','G10_geometry']

def partition_stats(dm,pcs,labels):
 n=len(labels);sizes=collections.Counter(labels);tri=np.triu_indices(n,1);samepc=pcs[:,None]==pcs[None,:];samecl=labels[:,None]==labels[None,:]
 pairs=dm[tri];pc=samepc[tri];cl=samecl[tri]
 supp=[c for c,s in sizes.items() if s>=2];within=mean_finite(pairs[cl]);between=mean_finite(pairs[pc&~cl])
 within_med=core.median(pairs[cl]);all_same_med=core.median(pairs[pc])
 mode_medians=[core.median(dm[np.ix_(np.flatnonzero(labels==l),np.flatnonzero(labels==l))][np.triu_indices(sizes[l],1)]) for l in supp]
 return dict(n_valid=n,n_modes=len(sizes),n_supported_modes=len(supp),supported_mass=sum(sizes[c] for c in supp)/n if n else 0,
  singleton_mass=sum(s for s in sizes.values() if s==1)/n if n else 1,largest_share=max(sizes.values())/n if n else np.nan,
  topology_disagreement=float((~pc).mean()) if len(pc) else np.nan,
  same_topology_between_mode_pair_fraction=float((pc&~cl).sum()/pc.sum()) if pc.sum() else np.nan,
  within_mode_mean_d=within,between_mode_same_topology_mean_d=between,
  within_mode_median_d=within_med,within_mode_max_median_d=max(mode_medians) if mode_medians else np.nan,within_mode_macro_median_d=mean_finite(mode_medians),same_topology_median_d=all_same_med,
  mode_entropy=entropy(labels),topology_entropy=entropy(pcs),
  supported_topologies=len(set(pcs[j] for j,c in enumerate(labels) if c in supp)),
  supported_minority_modes=sum(2<=s<=n*.2 for s in sizes.values()),
  same_topology_multimodality=any(len({labels[j] for j in range(n) if pcs[j]==p and sizes[labels[j]]>=2})>=2 for p in set(pcs)))

def snapshot(dm,pcs,quality,scope,full,ix,cut):
 z=dm[np.ix_(ix,ix)];p=pcs[ix];lab=cluster(z,p,cut);s=partition_stats(z,p,lab)
 counts=collections.Counter(full[ix]);total=collections.Counter(full)
 s['TV_full_observed']=.5*sum(abs(counts[c]/len(ix)-total[c]/len(full)) for c in total)
 s['supported_full_mass']=sum(total[c] for c in total if counts[c]>=2)/len(full)
 if len(ix):
  largest=sorted(collections.Counter(lab),key=lambda c:(-np.sum(lab==c),tuple(ix[lab==c])))[0]
  j=np.flatnonzero(lab==largest);med=j[np.argmin(z[np.ix_(j,j)].sum(1))]
  s['largest_mode_medoid_reference_error']=quality[ix[med]]
  s['member_reference_median']=core.median(quality[ix])
  known=[v for v in scope[ix] if v!='unknown'];s['scope_entropy']=entropy(known)
  meds=medoids(z,lab,2);rest=np.setdiff1d(np.arange(len(full)),ix)
  s['future_n']=len(rest)
  s['future_coverage']=float((dm[np.ix_(rest,ix[meds])].min(1)<=cut+1e-12).mean()) if len(rest) and len(meds) else 0. if len(rest) else np.nan
  s['future_new_structure_rate']=float((~np.isin(pcs[rest],p)).mean()) if len(rest) else np.nan
  s['future_new_geometry_rate']=float((dm[np.ix_(rest,ix)].min(1)>cut+1e-12).mean()) if len(rest) else np.nan
 return s,lab

def status_for(n,n_invalid,full_stats,ok):
 if n<4:return 'cannot_judge_low_n'
 if n_invalid:return 'cannot_judge_invalid'
 if full_stats['supported_mass']<.9-1e-12:return 'cannot_judge_singletons'
 if not ok:return 'current_changes'
 return 'observed_unified' if full_stats['n_supported_modes']==1 else 'stable_multicluster'

def group_replay(g,dense,cut,orders=100,record_steps=True):
 all_n=len(g);valid=g[g.geometry_valid].sort_values('worker_id').reset_index(drop=True);n=len(valid)
 assert valid.worker_id.nunique()==n
 if not n:return [],[],[],dict(n_observed=all_n,n_valid=0,n_invalid=all_n,status='cannot_judge_invalid')
 dm,pcs=pairs_for(valid,dense);full=cluster(dm,pcs,cut);q=valid.quality.to_numpy(float);scope=valid.scope.fillna('unknown').to_numpy()
 st=partition_stats(dm,pcs,full);st.update(n_observed=all_n,n_invalid=all_n-n)
 members=[]
 for l in np.unique(full):
  ix=np.flatnonzero(full==l);med=ix[np.argmin(dm[np.ix_(ix,ix)].sum(1))]
  for j in ix:members.append(dict(worker_id=valid.worker_id.iloc[j],canonical_annotation_id=valid.canonical_annotation_id.iloc[j],point_count=int(pcs[j]),cluster=int(l),cluster_people=len(ix),medoid_canonical_annotation_id=valid.canonical_annotation_id.iloc[med],medoid_worker_id=valid.worker_id.iloc[med],scope=str(scope[j]),reference_error=q[j]))
 rng=np.random.default_rng(seed_for(valid.image_id.iloc[0],valid.raw_condition.iloc[0],cut,'growth'))
 steps=[];summary=[];cache={}
 for rep in range(orders if n>=2 else 1):
  order=rng.permutation(n);prev=None;prev_ix=None;seq=[]
  for k in range(1,n+1):
   ix=np.sort(order[:k]);key=tuple(ix)
   if key not in cache:cache[key]=snapshot(dm,pcs,q,scope,full,ix,cut)
   row,lab=cache[key];row=row.copy();changed_pairs=0.;new=0.;promotion=0.;wg=np.nan;qd=np.nan
   if prev is not None:
    shared=np.searchsorted(ix,prev_ix);oldlab=prev[1];newlab=lab[shared];tri=np.triu_indices(k-1,1)
    changed_pairs=float(np.mean((oldlab[:,None]==oldlab[None,:])[tri]!=(newlab[:,None]==newlab[None,:])[tri])) if len(tri[0]) else 0.
    arrival=order[k-1];new=float(np.min(dm[arrival,prev_ix])>cut+1e-12)
    promotion=max(0,row['n_supported_modes']-prev[0]['n_supported_modes'])
    a=row['within_mode_median_d'];b=prev[0]['within_mode_median_d'];wg=abs(a-b) if np.isfinite(a) and np.isfinite(b) else np.nan
    qd=row['largest_mode_medoid_reference_error']-prev[0]['largest_mode_medoid_reference_error']
   row.update(replay=rep,k=k,arrival_worker=valid.worker_id.iloc[order[k-1]],new_incompatible_mode=new,support_promotions=promotion,repartition_pair_change=changed_pairs,within_mode_step_delta=wg,medoid_reference_step_delta=qd)
   seq.append(row);prev=(row,lab);prev_ix=ix
  # No extra people are required. Last 2-3 observed transitions form the empirical
  # plateau window; this is finite evidence, not a future guarantee.
  w=min(3,max(0,n-2));tail=seq[n-w-1:] if w else seq
  pattern=bool(n>=4 and len({(x['n_modes'],x['n_supported_modes']) for x in tail})==1 and max(x['repartition_pair_change'] for x in tail[1:])<=.05)
  d10=pattern and max(x['TV_full_observed'] for x in tail)<=.1+1e-12
  d20=pattern and max(x['TV_full_observed'] for x in tail)<=.2+1e-12
  wd=[x['within_mode_max_median_d'] for x in tail]
  geom=d10 and all(np.isfinite(wd)) and max(wd)-min(wd)<=.02+1e-12
  states={r:status_for(n,all_n-n,st,ok) for r,ok in zip(RULES,[pattern,d10,d20,geom])}
  # Retrospective sustained range: mode counts, partition and TV checks from k
  # through n. n-1 is allowed; n cannot trivially certify itself.
  onsets={}
  for rule,tv,geo in [('P_pattern',None,False),('D10_distribution',.1,False),('D20_distribution',.2,False),('G10_geometry',.1,True)]:
   onset=np.nan
   if n>=4 and st['supported_mass']>=.9 and all_n==n:
    for k0 in range(2,n):
     ss=seq[k0-1:];same=len({(x['n_modes'],x['n_supported_modes']) for x in ss})==1 and max(x['repartition_pair_change'] for x in ss[1:])<=.05
     same=same and (tv is None or max(x['TV_full_observed'] for x in ss)<=tv+1e-12)
     zz=[x['within_mode_max_median_d'] for x in ss]
     same=same and (not geo or (all(np.isfinite(zz)) and max(zz)-min(zz)<=.02+1e-12))
     if same:onset=k0;break
   onsets[rule]=onset
  for rule in RULES:summary.append(dict(replay=rep,rule=rule,state=states[rule],onset=onsets[rule],tail_first_k=n-w,late_new_geometry=sum(x['new_incompatible_mode'] for x in tail[1:]),late_support_promotions=sum(x['support_promotions'] for x in tail[1:]),tail_max_TV=max(x['TV_full_observed'] for x in tail)))
  if record_steps:steps+=seq
 return steps,summary,members,st

def run(orders=100):
 start=time.time();df=read_responses();df=df[df.main_worker_included&df.raw_condition.isin(['manual','semi'])];dense=boundary_map();layers=pd.read_csv(OUT/'images/evidence_layers.csv').set_index('image_id')
 allsteps=[];allstates=[];members=[];structures=[];orderstates=[]
 for counter,((image,arm),g) in enumerate(df.groupby(['image_id','raw_condition'])):
  for cut in CUTS:
   steps,ss,mm,st=group_replay(g,dense,cut,orders)
   meta=dict(image_id=image,building=g.building.iloc[0],condition=arm,cut=cut,scene=layers.loc[image,'scene_human_adopted'])
   structures.append(dict(**meta,**st,stages=';'.join(sorted(g.stage.unique())),contexts=g.context_key.nunique(),imputed_responses=int(g.imputed_point.sum())))
   members += [dict(**meta,**x) for x in mm]
   if not steps:
    for rule in RULES:allstates.append(dict(**meta,rule=rule,state='cannot_judge_invalid',fraction=1.,n_observed=len(g),n_valid=0))
    continue
   a=pd.DataFrame(steps)
   num=[c for c in a if c not in ['k','replay','arrival_worker']]
   means=a.groupby('k')[num].mean().reset_index();means['n_observed']=len(g);means['n_valid_full']=st['n_valid']
   allsteps += [dict(**meta,**x) for x in means.to_dict('records')]
   z=pd.DataFrame(ss)
   for rule,u in z.groupby('rule'):
    cnt=u.state.value_counts()
    for state,count in cnt.items():allstates.append(dict(**meta,rule=rule,state=state,fraction=count/len(u),n_observed=len(g),n_valid=st['n_valid'],onset_median=core.median(u.onset),onset_p10=u.onset.quantile(.1),onset_p90=u.onset.quantile(.9)))
   orderstates += [dict(**meta,**x) for x in ss]
  if counter%30==0:print('PROCESS',counter+1,'elapsed',round(time.time()-start,1),flush=True)
 csv('process/image_uncertainty_structure.csv',structures);csv('process/image_growth_curves.csv.gz',allsteps);csv('process/image_state_probabilities.csv',allstates);csv('process/replay_states.csv.gz',orderstates);csv('process/mode_memberships.csv.gz',members)
 st=pd.DataFrame(allstates);csv('process/state_summary.csv',st.groupby(['condition','cut','rule','state']).agg(expected_images=('fraction','sum'),images_with_state=('image_id','nunique')).reset_index())
 js('process/method.json',dict(version='followup_v2_prefix_recluster_20260914',orders=orders,seed=SEED,cuts=CUTS,states=['observed_unified','stable_multicluster','current_changes','cannot_judge_low_n','cannot_judge_singletons','cannot_judge_invalid'],min_n_for_two_observed_transition_check=4,tail_window='last min(3,n-2) transitions, no requirement to collect beyond actual n',rules=RULES,TV_reference='full observed partition, retrospective only',supported_cluster='at least2 distinct actual workers',singleton_mass_threshold=.1,geometry_drift=.02,partition_coassignment_drift=.05,real_chronology_available=False,pooling='Manual/Semi separate, same-worker duplicate forbidden; context-specific sensitivity follows',quality='actual medoid reference error, not majority truth, not automatic fusion',future_coverage='complementary people only; terminal n returns NA',onset='finite observed sustained interval, not a stopping guarantee'))
 print('PROCESS DONE',len(structures),'elapsed',time.time()-start,flush=True)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--orders',type=int,default=100);run(ap.parse_args().orders)
