"""Current-label half-team capacity on existing direct relationships; no design."""
from pathlib import Path
from collections import Counter
import json,hashlib,gzip
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];SRC=ROOT/'source';OUT=ROOT/'stage02_same_room/abc';OUT.mkdir(parents=True,exist_ok=True)
choices=[ROOT/'stage02_same_room/minimal_inputs/PRIMARY_POOL_INPUT_SNAPSHOT.json.gz',SRC/'research/data/releases/v2.1/pools/INPUT_SNAPSHOT.json.gz',SRC/'research/data/releases/v2.1/pools/INPUT_SNAPSHOT.json',ROOT.parent/'repo/research/data/releases/v2.1/pools/INPUT_SNAPSHOT.json']
snap=next((p for p in choices if p.exists()),None)
if snap is None: raise FileNotFoundError('Missing packaged stage02_same_room/minimal_inputs/PRIMARY_POOL_INPUT_SNAPSHOT.json.gz')
raw_snapshot=gzip.decompress(snap.read_bytes()) if snap.suffix=='.gz' else snap.read_bytes()
ps=json.loads(raw_snapshot)['images'];pools={(p['meta']['condition'],p['meta']['image_id']):p for p in ps}
rels=json.loads((SRC/'research/same_room/relation_adoption_20261016/relations.json').read_text())
labels=pd.read_csv(SRC/'research/data/releases/v2.1/final_classification_downstream/USED_FINAL_LOBO_LABELS.csv.gz')
labels=labels[labels.known&labels.heldout_building.ne('ALL')]
roles=pd.read_csv(SRC/'research/workers/personnel_v21_reselection_20261029/classification/CLASS_ROLES_COMPACT_ALL_LOBO.csv.gz').set_index(['method','heldout_building','class_id'])
old=pd.read_csv(ROOT/'stage02_same_room/abc/EVENT_IDENTITIES.csv.gz')
old['image_pair']=old.apply(lambda r:'|'.join(sorted([r.image_id_a,r.image_id_b])),axis=1)
oc=old.groupby(['final_method','building','n','m','source_labels','target_labels','image_pair']).agg(events=('event_id','size'),q=('Q_common6','sum'),t=('time_common6','sum')).to_dict('index')
lm={(m,b):dict(zip(g.worker_id,g.class_id)) for (m,b),g in labels.groupby(['method','heldout_building'])}
rows=[]
for ri,r in enumerate(rels):
 if not r['physical_adopted'] or r['substantive_conflict']:continue
 for cond in ['manual','semi']:
  pa=pools.get((cond,r['image_a']));pb=pools.get((cond,r['image_b']))
  if not pa or not pb:continue
  ma=pa['meta'];mb=pb['meta'];assert ma['building']==mb['building'];b=ma['building'];wa={z['worker_id'] for z in pa['records']};wb={z['worker_id'] for z in pb['records']};common=wa&wb
  ordinary=r['scope_comparable'] and not r['oos_pending'] and ma['layer']=='ordinary_manual' and mb['layer']=='ordinary_manual'
  for method in sorted(labels.method.unique()):
   # Manual history labels are evaluated only in their registered Manual domain.
   if cond!='manual':continue
   mp=lm[method,b];unknown=common-set(mp);cap=Counter(mp[w] for w in common if w in mp)
   rr=roles.loc[(method,b)];classes=rr.index.tolist()
   for source in classes:
    for target in classes:
     if source==target:continue
     for m in range(1,13):
      n=2*m;source_workers=sorted(w for w in common if mp.get(w)==source);target_workers=sorted(w for w in common if mp.get(w)==target)
      sr=rr.loc[source,'response_hard_turn_rank_asc' if method.startswith('RFUSE') else 'hard_turn_rank_asc'];tr=rr.loc[target,'response_hard_turn_rank_asc' if method.startswith('RFUSE') else 'hard_turn_rank_asc']
      direction=f'{int(sr)}→{int(tr)}';why=[]
      if len(common)<4*m:why.append('total_common_below_n_plus_2m')
      if cap[source]<2*m:why.append('source_class_below_2m')
      if cap[target]<m:why.append('target_class_below_m')
      oo=oc.get((method,b,n,m,source,target,'|'.join(sorted([r['image_a'],r['image_b']]))),dict(events=0,q=0,t=0))
      rows.append(dict(relation_index=ri,method=method,condition=cond,building=b,groups='|'.join(r['user_group_ids']),image_a=ma['image'],image_b=mb['image'],image_id_a=r['image_a'],image_id_b=r['image_b'],pool_a=pa['pool_id'],pool_b=pb['pool_id'],reference_a=ma['reference_id'],reference_b=mb['reference_id'],ordinary_comparable=ordinary,scope_comparable=r['scope_comparable'],n=n,m=m,total_a=len(wa),total_b=len(wb),common_n=len(common),known_common=len(common)-len(unknown),unknown_members='|'.join(sorted(unknown)),source_class=source,target_class=target,role_direction=direction,source_capacity=cap[source],target_capacity=cap[target],source_members='|'.join(source_workers),target_members='|'.join(target_workers),legal=not why,capacity_failures='|'.join(why),old_compatible_events=int(oo['events']),old_Q_common6=int(oo['q']),old_time_common6=int(oo['t'])))
d=pd.DataFrame(rows);d.to_csv(OUT/'HALF_CAPACITY_ALL_DIRECTIONS.csv.gz',index=False)
ss=[]
for keys,z in d.groupby(['method','condition','ordinary_comparable','n','m','role_direction']):
 ok=z[z.legal];run=ok[ok.old_compatible_events>0]
 ss.append(dict(zip(['method','condition','ordinary_comparable','n','m','role_direction'],keys),registered_direct_pairs=len(z),total_capacity_pairs=int(z.common_n.ge(4*z.m).sum()),source_capacity_pairs=int(z.source_capacity.ge(2*z.m).sum()),target_capacity_pairs=int(z.target_capacity.ge(z.m).sum()),legal_pairs=len(ok),legal_buildings=ok.building.nunique(),executed_pairs=len(run),executed_events=int(run.old_compatible_events.sum()),Q_evaluable_pairs=int(run.old_Q_common6.gt(0).sum()),time_evaluable_pairs=int(run.old_time_common6.gt(0).sum()),capacity_sufficient_unexecuted_pairs=int((ok.old_compatible_events==0).sum())))
pd.DataFrame(ss).to_csv(OUT/'HALF_CAPACITY_SUMMARY.csv',index=False)
d[d.method.eq('TARGET_DSTRUCT_K3')&d.ordinary_comparable&d.role_direction.eq('2→3')&d.legal&d.n.isin([10,12,14])&d.old_compatible_events.eq(0)].to_csv(OUT/'CAPACITY_SUFFICIENT_UNEXECUTED_MAIN_HALF_PAIRS.csv',index=False)
(OUT/'HALF_CAPACITY_RECEIPT.json').write_text(json.dumps(dict(pool_snapshot_sha256=hashlib.sha256(raw_snapshot).hexdigest(),pool_count=len(ps),rule='n=2m; disjoint D/X/Y/Z shared in both views; source>=2m target>=m common>=n+2m=4m; background may include explicitly unknown labels',no_new_teams=True,no_transitive_relations=True,manual_only=True),indent=2))
print('CAPACITY',len(d),len(ss),flush=True)
