"""Training-only local subclass recovery, all 16 information combinations.

No requirement that the entire partition or all people be stable. Missing
workers stay missing. Groups are selected by training membership recovery,
never target convergence. Native and equal-size untyped controls are retained.
"""
import argparse,collections,itertools,json,time,math
import numpy as np,pandas as pd
from scipy.special import comb
from scipy.cluster.hierarchy import linkage,cut_tree
from sklearn.metrics import adjusted_rand_score
from tools.thesis_main.analysis.image_portrait.convergence_v2_common import *
from tools.thesis_main.analysis.image_portrait.convergence_v2_process import group_replay,partition_stats
from tools.thesis_main.analysis.image_portrait.pro_workers import ProfileCache,COMBOS,standardize_blocks,labels_for


def fit_labels(profile,blocks,k):
 req=[a for b in blocks for a in b]
 if not set(req)<=set(profile):return None,None
 p=profile.dropna(subset=req).sort_index()
 if len(p)<2*k:return None,None
 x,_=standardize_blocks(p,blocks)
 if x is None:return None,None
 lab=labels_for(x,p,k,req[0]);return dict(zip(p.index,lab)),p

def jac(a,b):return len(a&b)/len(a|b) if a|b else np.nan

def rarefaction(sizes,n):
 """Exact finite-population occupancy of a descriptive full partition.
 Not online re-clustering; never called prospective mode discovery."""
 sizes=np.asarray(sizes,int);out=[]
 for k in range(1,n+1):
  den=comb(n,k,exact=False);p0=comb(n-sizes,k,exact=False)/den;p1=sizes*comb(n-sizes,k-1,exact=False)/den
  out.append(dict(k=k,expected_seen_modes=float((1-p0).sum()),expected_supported_modes=float((1-p0-p1).sum()),expected_supported_population_mass=float(((1-p0-p1)*sizes/n).sum()),expected_remaining_unseen_mass=float((p0*sizes/(n-k)).sum()) if k<n else np.nan))
 return out

def training_candidates(half_repeats=20):
 old=pd.DataFrame(core.load(BUNDLE/'history/worker_axes_historical.jsonl.gz'));old=old[old.main_worker_included].copy();old['value']=old.value.astype(float)
 cache=ProfileCache(old);buildings=sorted(images().building.unique());results=[];membership=[];failures=[];selected=[];globalscore=[]
 for bi,b in enumerate(buildings):
  p,_=cache.fit([b]);others=sorted(set(old.building_id)-{b});rng=np.random.default_rng(seed_for(b,'local_training'))
  halves=[]
  for rep in range(half_repeats):
   order=rng.permutation(others);a=set(order[:len(order)//2]);c=set(order[len(order)//2:])
   for half,allowed in [('a',a),('b',c)]:
    pp,_=cache.fit(set(buildings)-allowed);halves.append((rep,half,pp))
  for info,blocks in COMBOS.items():
   req=[a for group in blocks for a in group]
   maxk=len(p.dropna(subset=req))//2 if set(req)<=set(p) else 0
   if maxk<2:failures.append(dict(heldout_building=b,information=info,reason='insufficient_training_axes_or_people'));continue
   info_candidates=[]
   for k in range(2,maxk+1):
    labs,pp=fit_labels(p,blocks,k)
    if labs is None:failures.append(dict(heldout_building=b,information=info,k=k,reason='constant_axis_or_small_training_panel'));continue
    clusters={l:{w for w,z in labs.items() if z==l}for l in set(labs.values())};recovery={l:[]for l in clusters};coverage={l:[]for l in clusters};aris=[]
    for rep,half,hp in halves:
     hl,hpp=fit_labels(hp,blocks,k)
     if hl is None:
      for l in clusters:recovery[l].append(0.);coverage[l].append(0.)
      continue
     common=sorted(set(labs)&set(hl));ari=adjusted_rand_score([labs[w]for w in common],[hl[w]for w in common]) if len(common)>=2 else np.nan;aris.append(ari)
     hc=[{w for w,z in hl.items() if z==l}for l in set(hl.values())]
     for l,members in clusters.items():
      recovery[l].append(max(jac(members,h)for h in hc));coverage[l].append(len(members&set(hl))/len(members))
    for l,members in clusters.items():
     rec=np.asarray(recovery[l]);cov=np.asarray(coverage[l]);size=len(members);fraction=size/len(labs)
     strict=size>=3 and fraction<=.75 and np.median(rec)>=.75 and np.mean(cov>=.8)>=.8
     relaxed=size>=3 and fraction<=.75 and np.median(rec)>=.6 and np.mean(cov>=.8)>=.5
     row=dict(heldout_building=b,information=info,k=k,label=chr(65+l),workers=';'.join(sorted(members)),n_training_members=size,n_qualified_workers=len(labs),population_fraction=fraction,mean_recovery=float(rec.mean()),median_recovery=float(np.median(rec)),p10_recovery=float(np.quantile(rec,.1)),coverage80_fraction=float(np.mean(cov>=.8)),median_global_ARI=core.median(aris),strict_local_recovered=strict,relaxed_local_recovered=relaxed,training_buildings=';'.join(others),historical_metric_source='history/worker_axes_historical.jsonl.gz; retain original metric_version',axis_centroids=json.dumps(pp.loc[sorted(members),req].mean().to_dict()))
     results.append(row);info_candidates.append(row)
     for w in members:membership.append(dict(heldout_building=b,information=info,k=k,label=chr(65+l),worker_id=w,strict_local_recovered=strict))
   accepted=[x for x in info_candidates if x['strict_local_recovered']]
   if accepted:
    # A single local class per information family for detailed growth, chosen
    # WITHOUT any target image/worker outcomes. All other groups stay in tables.
    best=sorted(accepted,key=lambda r:(-r['median_recovery'],-r['p10_recovery'],-r['n_training_members'],r['k'],r['workers']))[0].copy();best['selection']='training_membership_recovery_only';selected.append(best)
  print('SUBGROUP TRAIN',bi+1,b,'groups',len(results),'selected',len(selected),flush=True)
 csv('subgroups/training_local_group_recovery.csv',results);csv('subgroups/training_memberships.csv.gz',membership);csv('subgroups/training_selected_local_groups.csv',selected);csv('subgroups/training_failures.csv',failures)
 return pd.DataFrame(results),pd.DataFrame(membership),pd.DataFrame(selected)

def target_groups(results,memberships,selected,detailed_orders=40):
 df=read_responses();df=df[df.main_worker_included&df.raw_condition.isin(['manual','semi'])];dense=boundary_map();layer=pd.read_csv(OUT/'images/evidence_layers.csv').set_index('image_id');records=[];growth=[];selection=[];curves=[];matched=[];fails=[];same_lists=[]
 grouping={b:g for b,g in results.groupby('heldout_building')}
 qualified_sets={key:set(g.worker_id) for key,g in memberships.groupby(['heldout_building','information','k'])}
 # Pre-existing out-of-target scores supply continuous-axis tail candidates.
 oldprofiles=pd.read_csv(OLD/'E/worker_axis_profiles_oof.csv.gz')
 for index,((image,arm),gall) in enumerate(df.groupby(['image_id','raw_condition'])):
  b=gall.building.iloc[0];g=gall[gall.geometry_valid].sort_values('worker_id').reset_index(drop=True)
  if not len(g):continue
  dm,pcs=pairs_for(g,dense);wm={w:j for j,w in enumerate(g.worker_id)}
  for r in grouping.get(b,pd.DataFrame()).to_dict('records'):
   workerlist=r['workers'].split(';');ix=np.array([wm[w]for w in workerlist if w in wm],int);n=len(ix)
   if n<2:continue
   lab=cluster(dm[np.ix_(ix,ix)],pcs[ix],.1);stats=partition_stats(dm[np.ix_(ix,ix)],pcs[ix],lab)
   meta=dict(image_id=image,building=b,condition=arm,scene=layer.loc[image,'scene_human_adopted'],information=r['information'],k_classes=r['k'],label=r['label'],strict_local_recovered=r['strict_local_recovered'],training_workers=r['workers'],actual_workers=';'.join(g.worker_id.iloc[ix]),actual_n=n,unknown_target_workers=len(g)-sum(w in qualified_sets[(b,r['information'],r['k'])] for w in g.worker_id))
   records.append(dict(**meta,**stats))
   for x in rarefaction(list(collections.Counter(lab).values()),n):growth.append(dict(**meta,**x))
  detailed=[]
  if len(selected):
   for r in selected[selected.heldout_building==b].to_dict('records'):detailed.append(dict(candidate='local_'+r['information'],source='training_local_recovery',workers=r['workers'],training_recovery=r['median_recovery'],k_classes=r['k']))
  for ax in ['manual__reference_error','manual__log_active_seconds','manual__point_count','manual__reference_band_bias','semi__point_count']:
   ps=oldprofiles[(oldprofiles.heldout_building==b)&(oldprofiles.source=='current_endpoints')&(oldprofiles.axis==ax)&oldprofiles.eligible].copy()
   if len(ps)<8:continue
   lo,hi=ps.effect.quantile([.25,.75])
   if hi-lo<1e-8:continue
   for side,z in [('low',ps[ps.effect<=lo]),('high',ps[ps.effect>=hi])]:
    detailed.append(dict(candidate='continuous_tail_'+ax+'_'+side,source='training_score_quartile_not_a_global_typology',workers=';'.join(sorted(z.worker_id)),training_recovery=np.nan,k_classes=0))
  for candidate in detailed:
   wg=set(candidate['workers'].split(';'));sub=gall[gall.worker_id.isin(wg)];n=sub.geometry_valid.sum()
   meta=dict(image_id=image,building=b,condition=arm,scene=layer.loc[image,'scene_human_adopted'],candidate=candidate['candidate'],selection_source=candidate['source'],training_workers=candidate['workers'],actual_workers=';'.join(sorted(sub.worker_id)),n_subgroup=int(n),n_all=len(g),training_recovery=candidate['training_recovery'])
   if n<2:
    fails.append(dict(**meta,reason='fewer_than_two_target_people'));continue
   steps,states,mm,stat=group_replay(sub,dense,.1,detailed_orders)
   ss=pd.DataFrame(states)
   if len(ss):
    for rule,u in ss.groupby('rule'):
     selection.append(dict(**meta,rule=rule,p_unified=float((u.state=='observed_unified').mean()),p_stable_multi=float((u.state=='stable_multicluster').mean()),p_current_changes=float((u.state=='current_changes').mean()),p_undetermined=float(u.state.str.startswith('cannot').mean()),onset=core.median(u.onset),**{k:stat[k] for k in ['topology_disagreement','same_topology_median_d','n_supported_modes','singleton_mass']}))
    for k,u in pd.DataFrame(steps).groupby('k'):
     curves.append(dict(**meta,k=k,TV_full=u.TV_full_observed.mean(),new_geometry=u.new_incompatible_mode.mean(),supported_modes=u.n_supported_modes.mean(),future_coverage=u.future_coverage.mean(),within_mode_max_median=u.within_mode_max_median_d.mean()))
   # Matched-n untyped controls. Draw real subsets without replacement; equal n
   # prevents an apparently stable class merely being a smaller crowd.
   if n>=4 and n<len(g) and len(sub)==n:
    rng=np.random.default_rng(seed_for(image,arm,candidate['candidate'],'untyped'))
    base=[]
    for rep in range(20):
     pick=rng.choice(len(g),size=n,replace=False);control=g.iloc[pick]
     _,s2,_,st2=group_replay(control,dense,.1,orders=4,record_steps=False)
     u=pd.DataFrame(s2);u=u[u.rule=='G10_geometry'];base.append(float(u.state.isin(['observed_unified','stable_multicluster']).mean()))
    u=ss[ss.rule=='G10_geometry'];actual=float(u.state.isin(['observed_unified','stable_multicluster']).mean())
    matched.append(dict(**meta,subgroup_stable_fraction=actual,matched_n_untyped_stable_fraction=float(np.mean(base)),delta=actual-float(np.mean(base)),control_draws=20,control_orders=4,not_independent_population_samples=True))
  if index%30==0:print('SUBGROUP TARGET',index+1,'group rows',len(records),'detailed',len(selection),flush=True)
 csv('subgroups/all_candidate_target_groups.csv.gz',records);csv('subgroups/all_candidate_fixed_partition_rarefaction.csv.gz',growth);csv('subgroups/selected_and_continuous_target_states.csv',selection);csv('subgroups/selected_subgroup_growth.csv.gz',curves);csv('subgroups/equal_n_untyped_controls.csv',matched);csv('subgroups/target_failures.csv',fails)
 if selection:
  z=pd.DataFrame(selection);csv('subgroups/target_state_summary.csv',z.groupby(['candidate','condition','rule']).agg(image_groups=('image_id','size'),images=('image_id','nunique'),buildings=('building','nunique'),mean_unified=('p_unified','mean'),mean_stable_multi=('p_stable_multi','mean'),mean_current_changes=('p_current_changes','mean'),mean_undetermined=('p_undetermined','mean'),median_people=('n_subgroup','median')).reset_index())
  exact=z.groupby(['candidate','condition','training_workers','actual_workers','rule']).agg(images=('image_id','nunique'),buildings=('building','nunique'),mean_unified=('p_unified','mean'),mean_stable_multi=('p_stable_multi','mean')).reset_index();csv('subgroups/exact_roster_cross_image_recurrence.csv',exact)
 if matched:
  z=pd.DataFrame(matched);summ=[]
  for key,u in z.groupby(['candidate','condition']):summ.append(dict(candidate=key[0],condition=key[1],**paired_interval(u,'delta')))
  csv('subgroups/equal_n_comparison_summary.csv',summ)
 js('subgroups/method.json',dict(information_combinations=list(COMBOS),group_counts='2..floor(training qualified people/2)',training='heldout building excluded from EVERY block',primary_axis_support='6 responses and3 buildings',local_membership_validation='20 disjoint-building half splits per outer fold; unknown people penalize Jaccard rather than form a class',strict_local_rule='>=3 people, <=75% training population, median Jaccard>=.75, >=80% attempts recover at least80% group people',relaxed_rule='separate .60 Jaccard diagnostic, NOT silently promoted',selection='training recovery only; one candidate per information per fold for full prefix replay',continuous_tail='training quartiles from previously verified heldout-building current endpoint scores; tails are not claimed real types',rarefaction='all groups exact fixed-full-partition occupancy; distinct from prefix-reclustered detailed curves',equal_n_control='real same-image people subsets, no duplicate worker; no additional independent samples',repeat_roster_caveat='Overlapping outer training sets do not give independent membership confirmation; disjoint halves are primary recovery diagnostic'))

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--stage',default='all',choices=['train','target','all']);a=ap.parse_args()
 if a.stage in ['all','train']:res,mem,sel=training_candidates()
 if a.stage in ['all','target']:
  if a.stage=='target':res=pd.read_csv(OUT/'subgroups/training_local_group_recovery.csv');mem=pd.read_csv(OUT/'subgroups/training_memberships.csv.gz');sel=pd.read_csv(OUT/'subgroups/training_selected_local_groups.csv')
  target_groups(res,mem,sel)
