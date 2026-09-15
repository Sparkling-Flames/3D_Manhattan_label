"""Separate local membership, behavior and convergence replication.
Additional full-class growth uses real available n, not just2-4 person subsets.
"""
import collections,itertools,json,time
import numpy as np,pandas as pd
from tools.thesis_main.analysis.image_portrait.convergence_v2_common import *
from tools.thesis_main.analysis.image_portrait.convergence_v2_process import group_replay,partition_stats
from tools.thesis_main.analysis.image_portrait.pro_workers import ProfileCache,COMBOS
from tools.thesis_main.analysis.image_portrait.convergence_v2_subgroups import fit_labels,jac


def historical_axes():
 d=pd.DataFrame(core.load(BUNDLE/'history/worker_axes_historical.jsonl.gz'));d=d[d.main_worker_included].copy();d['value']=d.value.astype(float);return d

def behavior_replication():
 old=historical_axes();response=read_responses();old=old.merge(response[['canonical_annotation_id','raw_condition']],on='canonical_annotation_id',how='left',validate='many_to_one');sel=pd.read_csv(OUT/'subgroups/training_selected_local_groups.csv');cache=ProfileCache(old);rows=[]
 for r in sel.to_dict('records'):
  b=r['heldout_building'];members=set(r['workers'].split(';'));req=[a for block in COMBOS[r['information']]for a in block];p,_=cache.fit([b]);test=old[(old.building_id==b)&old.axis.isin(req)]
  for (axis,arm,im,context),g in test.groupby(['axis','raw_condition','image_id','context_key']):
   a=g[g.worker_id.isin(members)];c=g[~g.worker_id.isin(members)]
   if len(a)<2 or len(c)<2 or axis not in p:continue
   ps=p[axis].dropna();inside=ps[ps.index.isin(members)];outside=ps[~ps.index.isin(members)]
   if not len(inside)or not len(outside):continue
   predicted=inside.mean()-outside.mean();actual=a.value.mean()-c.value.mean();rows.append(dict(image_id=im,building=b,condition=arm,information=r['information'],k_classes=r['k'],axis=axis,training_workers=r['workers'],target_members=';'.join(sorted(a.worker_id.unique())),n_members=len(a),n_others=len(c),training_contrast=predicted,target_contrast=actual,aligned_target_contrast=actual*np.sign(predicted),direction_replicated=actual*predicted>0,metric='historical axis unchanged; not substituted for current d_mask'))
 x=csv('subgroups/heldout_behavior_replication.csv',rows);summ=[]
 for key,g in x.groupby(['information','condition','axis']):
  # image-macro, duplicate contexts averaged first
  z=g.groupby(['image_id','building'])[['aligned_target_contrast','direction_replicated']].mean().reset_index();summ.append(dict(information=key[0],condition=key[1],axis=key[2],direction_replication_fraction=z.direction_replicated.mean(),**paired_interval(z,'aligned_target_contrast')))
 csv('subgroups/heldout_behavior_summary.csv',summ)


def class_pool_growth():
 d=read_responses();d=d[d.main_worker_included&d.raw_condition.isin(['manual','semi'])];dense=boundary_map();membership=pd.read_csv(OLD/'E/worker_memberships_oof.csv.gz');membership=membership[membership.panel=='native'];configs=[('Q',2),('T',2),('B',2),('QTSB',4),('quality_time_edit',3)];rows=[];curves=[];modes=[];fail=[]
 for count,((im,arm),g) in enumerate(d.groupby(['image_id','raw_condition'])):
  if len(g)<6:continue
  b=g.building.iloc[0]
  for info,k in configs:
   m=membership[(membership.heldout_building==b)&(membership.information==info)&(membership.k==k)];mp=dict(zip(m.worker_id,m.label));known=g[g.worker_id.isin(mp)];classes=sorted(set(mp[w]for w in known.worker_id));group_summ=[]
   cache={}
   for label in classes:
    x=known[known.worker_id.map(mp)==label];n=len(x)
    if n<2:continue
    ss,states,mm,stats=group_replay(x,dense,.1,orders=30);p=pd.DataFrame(states);p=p[p.rule=='G10_geometry']if len(p)else p
    row=dict(image_id=im,building=b,condition=arm,information=info,k_classes=k,pool=label,pool_workers=';'.join(sorted(x.worker_id)),n_pool=n,n_all=len(g),unknown_workers=len(g)-len(known),stable_fraction=float(p.state.isin(['observed_unified','stable_multicluster']).mean())if len(p)else np.nan,unified_fraction=float((p.state=='observed_unified').mean())if len(p)else np.nan,multiple_fraction=float((p.state=='stable_multicluster').mean())if len(p)else np.nan,undetermined_fraction=float(p.state.str.startswith('cannot').mean())if len(p)else 1.,supported_modes=stats.get('n_supported_modes',0),topology_disagreement=stats.get('topology_disagreement'),same_point_dispersion=stats.get('same_topology_median_d'))
    rows.append(row);group_summ.append(row);cache[label]=x
    if ss:
     for kk,z in pd.DataFrame(ss).groupby('k'):curves.append(dict(image_id=im,condition=arm,information=info,k_classes=k,pool=label,pool_workers=row['pool_workers'],n_pool=n,k=kk,mode_count=z.n_modes.mean(),supported_modes=z.n_supported_modes.mean(),novel_geometry=z.new_incompatible_mode.mean(),within_geometry=z.within_mode_max_median_d.mean(),TV_full=z.TV_full_observed.mean(),future_coverage=z.future_coverage.mean()))
   # Evaluate every possible pair of classes with >=4 people each. The merged
   # finite process is computed afresh, never inferred from pairwise summaries.
   qualified=[r for r in group_summ if r['n_pool']>=4]
   if len(qualified)<2:fail.append(dict(image_id=im,condition=arm,information=info,k_classes=k,reason='fewer_than_two_classes_with_four_actual_people',qualified_classes=len(qualified)));continue
   for a,c in itertools.combinations(qualified,2):
    union=pd.concat([cache[a['pool']],cache[c['pool']]],ignore_index=True);ss,p,mm,stats=group_replay(union,dense,.1,orders=30);p=pd.DataFrame(p);p=p[p.rule=='G10_geometry'];rows.append(dict(image_id=im,building=b,condition=arm,information=info,k_classes=k,pool=a['pool']+'+'+c['pool'],pool_workers=';'.join(sorted(union.worker_id)),n_pool=len(union),n_all=len(g),unknown_workers=len(g)-len(known),stable_fraction=float(p.state.isin(['observed_unified','stable_multicluster']).mean()),unified_fraction=float((p.state=='observed_unified').mean()),multiple_fraction=float((p.state=='stable_multicluster').mean()),undetermined_fraction=float(p.state.str.startswith('cannot').mean()),supported_modes=stats.get('n_supported_modes',0),topology_disagreement=stats.get('topology_disagreement'),same_point_dispersion=stats.get('same_topology_median_d'),class_a_unified=a['unified_fraction'],class_b_unified=c['unified_fraction'],class_a_n=a['n_pool'],class_b_n=c['n_pool'],both_classes_unified80=a['unified_fraction']>=.8 and c['unified_fraction']>=.8))
    for kk,z in pd.DataFrame(ss).groupby('k'):curves.append(dict(image_id=im,condition=arm,information=info,k_classes=k,pool=a['pool']+'+'+c['pool'],pool_workers=';'.join(sorted(union.worker_id)),n_pool=len(union),k=kk,mode_count=z.n_modes.mean(),supported_modes=z.n_supported_modes.mean(),novel_geometry=z.new_incompatible_mode.mean(),within_geometry=z.within_mode_max_median_d.mean(),TV_full=z.TV_full_observed.mean(),future_coverage=z.future_coverage.mean()))
  if count%30==0:print('CLASS POOL',count+1,'rows',len(rows),flush=True)
 csv('combinations/actual_class_pool_growth_states.csv',rows);csv('combinations/actual_class_pool_growth_curves.csv.gz',curves);csv('combinations/class_pool_coverage_failures.csv',fail)


def fixed_training_test_split():
 old=historical_axes();cache=ProfileCache(old);buildings=sorted(images().building.unique());rng=np.random.default_rng(seed_for('supplemental_fixed_disjoint_building_halves'));order=rng.permutation(buildings);halves=[set(order[:len(order)//2]),set(order[len(order)//2:])];d=read_responses();d=d[d.main_worker_included&d.raw_condition.isin(['manual','semi'])];dense=boundary_map();selected=[];rows=[];audit=[]
 for fold in [0,1]:
  train=halves[fold];test=halves[1-fold];p,_=cache.fit(set(buildings)-train);hp=[];rg=np.random.default_rng(seed_for('fixedsplit',fold))
  for rep in range(20):
   o=rg.permutation(sorted(train));a=set(o[:len(o)//2]);b=set(o[len(o)//2:])
   for allowed in [a,b]:hp.append(cache.fit(set(buildings)-allowed)[0])
  for info,blocks in COMBOS.items():
   req=[a for block in blocks for a in block];maxk=len(p.dropna(subset=req))//2 if set(req)<=set(p)else 0;candidates=[]
   for k in range(2,maxk+1):
    lab,pp=fit_labels(p,blocks,k)
    if lab is None:continue
    cls={l:{w for w,x in lab.items() if x==l}for l in set(lab.values())}
    hl=[fit_labels(h,blocks,k)[0] for h in hp]
    for l,members in cls.items():
     rec=[];available=0
     for h in hl:
      if h is None:rec.append(0.);continue
      groups=[{w for w,z in h.items() if z==ll}for ll in set(h.values())];rec.append(max(jac(members,z)for z in groups));available+=len(members&set(h))/len(members)>=.8
     eligible=len(members)>=3 and len(members)/len(lab)<=.75 and np.median(rec)>=.75 and available/40>=.8
     audit.append(dict(fold=fold,information=info,k=k,workers=';'.join(sorted(members)),median_recovery=np.median(rec),strict_eligible=eligible,valid_support_fraction=available/40))
     if eligible:candidates.append(dict(fold=fold,information=info,k=k,workers=';'.join(sorted(members)),n_members=len(members),median_recovery=np.median(rec),p10_recovery=np.quantile(rec,.1)))
   if not candidates:continue
   c=sorted(candidates,key=lambda x:(-x['median_recovery'],-x['p10_recovery'],-x['n_members'],x['k'],x['workers']))[0];c['training_buildings']=';'.join(sorted(train));c['target_buildings']=';'.join(sorted(test));selected.append(c);members=set(c['workers'].split(';'))
   for (im,arm),g in d[d.building.isin(test)].groupby(['image_id','raw_condition']):
    sub=g[g.worker_id.isin(members)]
    if len(sub)<2:continue
    _,s,_,st=group_replay(sub,dense,.1,orders=30,record_steps=False);s=pd.DataFrame(s);s=s[s.rule=='G10_geometry']if len(s)else s
    rows.append(dict(fold=fold,image_id=im,building=im.split('_')[0],condition=arm,information=info,k_classes=c['k'],training_workers=c['workers'],actual_workers=';'.join(sorted(sub.worker_id)),n=len(sub),unified_fraction=float((s.state=='observed_unified').mean())if len(s)else np.nan,multiple_fraction=float((s.state=='stable_multicluster').mean())if len(s)else np.nan,undetermined_fraction=float(s.state.str.startswith('cannot').mean())if len(s)else 1.))
  print('FIXED SPLIT',fold,'selected',len(selected),flush=True)
 csv('subgroups/fixed_disjoint_split_training_candidates.csv',audit);csv('subgroups/fixed_disjoint_split_selected.csv',selected);csv('subgroups/fixed_disjoint_split_target_processes.csv',rows)
 js('subgroups/fixed_disjoint_split_method.json',dict(supplemental_not_replacement_for_fixed_primary_folds=True,seed=seed_for('supplemental_fixed_disjoint_building_halves'),training_and_all_targets_building_disjoint=True,selection='same training-only membership recovery criterion; every target in a split uses one fixed roster per information family',post_prior_result_exploration=True))


def support_diagnostic():
 old=historical_axes();cache=ProfileCache(old);bs=sorted(images().building.unique());rows=[]
 # The nine OOS rule images cannot provide6 distinct image responses in each
 # of two disjoint halves. Report this as missing support, not instability.
 counts=old.groupby('axis').agg(images=('image_id','nunique'),buildings=('building_id','nunique'),rows=('value','size')).reset_index();csv('subgroups/axis_support_feasibility.csv',counts)
 for b in bs:
  p,_=cache.fit([b]);rng=np.random.default_rng(seed_for(b,'scope_relaxed_support'))
  for info in ['S','QS','TS','QTSB']:
   for k in [2,3,4]:
    lab,pp=fit_labels(p,COMBOS[info],k)
    if lab is None:continue
    groups=[{w for w,x in lab.items()if x==l}for l in set(lab.values())];scores=[[]for _ in groups];attempts=0
    for rep in range(10):
     o=rng.permutation([x for x in bs if x!=b])
     for half in [set(o[:len(o)//2]),set(o[len(o)//2:])]:
      hp,_=cache.fit(set(bs)-half,minimum_rows=3,minimum_buildings=2);hl,_=fit_labels(hp,COMBOS[info],k)
      if hl is None:continue
      attempts+=1;hg=[{w for w,x in hl.items()if x==l}for l in set(hl.values())]
      for j,m in enumerate(groups):scores[j].append(max(jac(m,c)for c in hg))
    for group,s in zip(groups,scores):rows.append(dict(heldout_building=b,information=info,k=k,workers=';'.join(sorted(group)),valid_halves=attempts,requested_halves=20,conditional_median_Jaccard=core.median(s),support_version='3responses_2buildings_diagnostic_not_primary',not_a_target_convergence_selection=True))
 csv('subgroups/rule_relaxed_support_diagnostic.csv',rows)

if __name__=='__main__':
 import argparse
 ap=argparse.ArgumentParser();ap.add_argument('--stage',choices=['behavior','growth','fixed','support','all'],default='all');a=ap.parse_args()
 if a.stage in ['behavior','all']:behavior_replication()
 if a.stage in ['growth','all']:class_pool_growth()
 if a.stage in ['fixed','all']:fixed_training_test_split()
 if a.stage in ['support','all']:support_diagnostic()
