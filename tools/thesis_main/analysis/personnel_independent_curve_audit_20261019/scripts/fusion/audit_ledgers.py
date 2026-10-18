import json,gzip,hashlib
from pathlib import Path
from collections import Counter,defaultdict
import pandas as pd,numpy as np
BASE=Path(__file__).resolve().parents[2]; P=BASE/'extracted/work_v2_20261019/fusion';OUT=Path(__file__).resolve().parent
read=lambda p:json.load(gzip.open(p,'rt'))
r=read(P/'ALL_REQUESTS.json.gz')['requests']; pools=read(P/'INPUT_SNAPSHOT.json.gz')['images'];pl={p['pool_id']:p for p in pools};rd={x['request_id']:x for x in r}
t=pd.read_csv(P/'team_results.csv',low_memory=False);ti=t.set_index('request_id');errs=Counter()
for x in r:
 p=pl[x['pool_id']];allowed={a['worker_id']:a for a in p['records']}; w=x['worker_ids']; row=ti.loc[x['request_id']]
 errs['bad_members']+=int(len(set(w))!=x['k'] or not set(w)<=allowed.keys())
 errs['result_members']+=int(set(w)!=set(row.member_workers.split('|')))
 errs['fold_target_mismatch']+=int('profile_training_excludes_building' in x and x['profile_training_excludes_building']!=p['meta']['building'])
 if 'background_worker_ids' in x:errs['bad_background']+=int(set(x['background_worker_ids'])!=set(w)-{x['entrant_worker_id']})
coverage=dict(requests=len(r),result_rows=len(t),unique_request_ids=len(rd),unique_teams=t.team_id.nunique(),quality_available=int(t.B8L2.notna().sum()),N2_deferred=int(t.k.eq(2).sum()),other_quality_missing=int((t.k.ne(2)&t.B8L2.isna()).sum()),families=t.request_family.value_counts().to_dict(),checks=dict(errs),unique_team_complete=int(t.drop_duplicates('team_id').complete_evaluable.sum()),score_status=t.score_status.value_counts(dropna=False).to_dict())
results={}; bg={}
for x in r:
 if x['request_family']=='fixed_background':bg[(x['pool_id'],x['k'],x['draw_id'])]=set(x['background_worker_ids'])
nested=[]
for (pid,k,draw),ws in bg.items():
 for nk in [8,12,16,24]:
  if nk>k and (pid,nk,draw) in bg:nested.append((k,nk,ws<bg[pid,nk,draw]))
coverage['background_nested_check']={'pairs':len(nested),'nested':sum(x[2] for x in nested),'description':'same pool/draw across increasing k; backgrounds are independently sampled, not designed as paths'}
for fam in ['replacements','prefix_transitions','random_same_k','composition_comparisons','policy_comparisons']:
 counts=Counter(); maxerr=0.
 for d in pd.read_csv(P/(fam+'.csv.gz'),chunksize=30000,low_memory=False):
  counts['rows']+=len(d);counts['quality_comparable']+=int(d.quality_comparable.sum());counts['both_complete']+=int(d.both_complete.sum())
  a=ti.loc[d.request_a].reset_index(drop=True);b=ti.loc[d.request_b].reset_index(drop=True);d=d.reset_index(drop=True)
  for col in ['pool_id','k','team_id','member_workers','B8L2']:
   if col in ['pool_id']:counts['mismatch_'+col]+=int((a[col]!=b[col]).sum())
  delta=b.B8L2-a.B8L2
  counts['score_missing_mismatch']+=int((delta.isna()!=d.B8L2_change.isna()).sum())
  maxerr=max(maxerr,float((delta-d.B8L2_change).abs().max(skipna=True) or 0))
  counts['team_pointer_mismatch']+=int(((a.team_id!=d.team_id_a)|(b.team_id!=d.team_id_b)).sum())
  for aa,bb,kk,share in zip(d.member_workers_a,d.member_workers_b,d.k_a,d.shared_workers):
   sa,sb=set(aa.split('|')),set(bb.split('|'));counts['shared_workers_mismatch']+=int(len(sa&sb)!=share)
   if fam=='replacements':counts['not_exact_one_replacement']+=int(len(sa)!=len(sb) or len(sa&sb)!=kk-1)
   if fam=='prefix_transitions':counts['not_nested']+=int(not sa<sb or len(sb)!=len(sa)+1)
  if fam=='replacements':
   for row in d.itertuples():
    x,y=rd[row.request_a],rd[row.request_b]
    counts['background_mismatch']+=int(x['background_id']!=y['background_id'] or set(x['background_worker_ids'])!=set(y['background_worker_ids']))
  stable=d.both_complete & d.B8L2_change.abs().le(2)&d.node_count_difference.eq(0)&d.floor_jaccard_difference.le(.05)&d.structure_bound_cyclic_deg.le(3)
  counts['joint_stability_mismatch']+=int((stable!=d.joint_geometric_stable).sum())
 results[fam]={**dict(counts),'max_abs_delta_error':maxerr};print(fam,results[fam],flush=True)
# Independently regenerate k16 composition headline summaries from raw comparisons.
c=pd.read_csv(P/'composition_comparisons.csv.gz',low_memory=False); c=c[c.k.eq(16)&~c.same_subset&c.same_composition].copy(); c['overlap']=c.shared_workers/c.k
summ=[]
for (family,scheme,threshold),g in c.groupby(['comparison_family','scheme','threshold'],dropna=False):
 row=dict(family=family,scheme=None if pd.isna(scheme) else scheme,threshold=None if pd.isna(threshold) else threshold,attempts=len(g),quality_comparable=int(g.quality_comparable.sum()),images=g.image_id.nunique(),buildings=g.building.nunique())
 for met in ['abs_B8L2_change','joint_geometric_stable','overlap']:
  row[met+'_building_equal']=float(g.groupby(['building','image_id'])[met].mean().groupby('building').mean().mean())
 summ.append(row)
report=dict(coverage=coverage,comparison_integrity=results,k16_same_composition=summ)
(OUT/'LEDGER_AUDIT.json').write_text(json.dumps(report,indent=2,default=int));print(json.dumps(report,indent=2,default=int),flush=True)
