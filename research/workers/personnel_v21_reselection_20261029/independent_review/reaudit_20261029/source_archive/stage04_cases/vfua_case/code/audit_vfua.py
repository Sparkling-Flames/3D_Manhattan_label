#!/usr/bin/env python3
"""Trace-only explanation of the VFua shared-pool negative tail and failures."""
from pathlib import Path
import gzip, hashlib, itertools, json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT.parent
STAGE = WORK / "HOHONET_v21_reaudit_20261029/stage03_new_abc"
PAIRS = [
 ("f48b5b2dcce86d87b6ce5ece", "724f9d200edfa11b34e56ebb"),
 ("cee80eb52074a9b2d594a037", "44ebc9dfe43f07b6030f2fcd"),
]
IDS = set(sum((list(p) for p in PAIRS), []))
RESULTS = ROOT / "results"
RESULTS.mkdir(exist_ok=True)

def save(name, rows):
 (rows if isinstance(rows,pd.DataFrame) else pd.DataFrame(rows)).to_csv(RESULTS/name,index=False,encoding="utf-8-sig")

events = pd.read_csv(STAGE/"EVENTS_EXACT.csv.gz", dtype=str).set_index("event_id")
metrics = pd.read_csv(STAGE/"metrics/EVENT_METRICS.csv.gz").set_index("event_id")
labels = pd.concat([pd.read_csv(WORK/"prior_extracted/stage02/classification/MAIN45_LABELS_ALL_LOBO.csv.gz",low_memory=False),
                    pd.read_csv(WORK/"audit_classification/results/NEW_LABELS_ALL_LOBO.csv.gz",low_memory=False)])
lookup = {(r.method,r.heldout_building,r.worker_id):str(r.class_id).removeprefix("C").removesuffix(".0")
          for r in labels.itertuples() if str(r.known).lower() in {"true","1"}}

equivalent=[]; arms=[]; groups=[]; voters=[]; common=[]; obstructions=[]; sets=[]
for target, raw in PAIRS:
 a,b=events.loc[target],events.loc[raw]
 keys=["D","X","Y","Z","A_team_key","B_team_key","C_team_key","A_members","B_members","C_members","reference_id"]
 assert all(a[k]==b[k] for k in keys)
 for eid in [target,raw]:
  e=events.loc[eid];blocks={k:set(e[k].split('|')) for k in 'DXYZ'}
  assert all(len(blocks[k])==8 for k in 'DXYZ')
  assert all(not blocks[k]&blocks[j] for k,j in itertools.combinations('DXYZ',2))
  for block in 'XYZ':
   expected=e['target_class'] if block=='Z' else e['source_class']
   expected=str(expected).removeprefix('C').removesuffix('.0')
   assert {lookup[(e.method,e.building,w)] for w in blocks[block]}=={expected}
  equivalent.append(dict(event_id=eid,paired_event_id=raw if eid==target else target,
    method=e.method,all_DXYZ_and_ABC_teams_and_reference_identical=True,strict_mutually_disjoint_ABC=True,
    known_LOBO_X_Y_same_class_Z_other_class=True))
 with gzip.open(ROOT/'traces'/(target+'.json.gz'),'rt') as f:t=json.load(f)
 e=t['event'];D=set(e['D'].split('|'));maps={}
 for arm,block in zip('ABC','XYZ'):
  a=t['arms'][arm];fs=a['full_state'];sel=[g for g in fs['identity_groups'] if g['selected']]
  selected={g['feature_id'] for g in sel}
  cover=[z['worker'] for z in fs['assignments'] if selected<=set(z['feature_ids'])]
  row={k:v for k,v in a.items() if not isinstance(v,(dict,list))}
  row.update(event_id=target,arm=arm,source_ring_covering_all_selected_n=len(cover),
    source_ring_covering_all_selected_workers='|'.join(sorted(cover)))
  arms.append(row)
  obs={}
  for g in fs['identity_groups']:
   who={z['worker'] for z in g['members']};assert len(who)==g['support']
   assert bool(g['selected'])==(g['support']>=8)
   groups.append(dict(event_id=target,arm=arm,feature_id=g['feature_id'],support=g['support'],selected=g['selected'],
     D_support=len(who&D),replacement_support=len(who-D),D_workers='|'.join(sorted(who&D)),
     replacement_workers='|'.join(sorted(who-D)),top_x_px=g['center'][0][0],top_y_px=g['center'][0][1],
     bottom_x_px=g['center'][1][0],bottom_y_px=g['center'][1][1]))
   for z in g['members']:
    key=(z['id'],z['source_pair_index'])
    voters.append(dict(event_id=target,arm=arm,feature_id=g['feature_id'],worker=z['worker'],
      block='D' if z['worker'] in D else block,object_id=z['id'],source_pair_index=z['source_pair_index'],
      points_json=json.dumps(z['points'],separators=(',',':'))))
    if z['worker'] in D:
     assert key not in obs
     obs[key]=g['feature_id']
  maps[arm]=obs
  if not cover:
   assert a['score_status']=='no_connection' and a['B8L2'] is None
   for k in range(2,len(sel)+1):
    found=[]
    for sub in itertools.combinations(sel,k):
     support=[{z['worker'] for z in g['members']} for g in sub]
     if not set.intersection(*support):
      found.append(dict(event_id=target,arm=arm,minimum_obstruction_group_count=k,
        feature_ids='|'.join(g['feature_id'] for g in sub),
        supports='|'.join(str(g['support']) for g in sub),
        all_proper_subsets_have_shared_supporter=True,
        group_workers_json=json.dumps({g['feature_id']:sorted(su) for g,su in zip(sub,support)},ensure_ascii=False,separators=(',',':'))))
    if found:
     obstructions+=found;break
 for arm in 'BC':
  a,b=maps['A'],maps[arm];assert set(a)==set(b)
  changes=[dict(observation_1=list(u),observation_2=list(v),coassigned_A=a[u]==a[v],coassigned_other=b[u]==b[v])
    for u,v in itertools.combinations(a,2) if (a[u]==a[v])!=(b[u]==b[v])]
  common.append(dict(event_id=target,other_arm=arm,common_D_observations_n=len(a),
    pairwise_coassignment_changes_n=len(changes),changes_json=json.dumps(changes,separators=(',',':'))))

cols=['event_id','method','source_stage','n','m','pool_id','image','role_direction','joint_Q_BA','joint_Q_CA','joint_Q_CB','B8L2_same_origin_gap','B8L2_symmetric_gap','ABC_scored']
union_path=WORK/'audit_comparison/abc_integrated/COMBINED_UNION_EVENTS_WITH_ROLES.csv.gz'
union=pd.read_csv(union_path,usecols=cols)
overlap=pd.read_csv(WORK/'audit_comparison/abc_integrated/NEW_M8_COMMON_POOL_EXACT_TEAM_OVERLAP.csv')
pools=set(overlap[(overlap.n==16)&(overlap.m==8)].pool_id)
z=union[union.pool_id.isin(pools)&union.n.eq(16)&union.m.eq(8)&union.source_stage.eq('this_turn_supplement')&union.role_direction.eq('hard_turn_rank_asc:2/3->3/3')&union.method.isin(['TARGET_DSTRUCT_K3','V21_DSTRUCT_RAW3_K3'])]
assert len(z.pool_id.unique())==7
assert set(z[z.image.eq('VFuaQ6m2Qom-04')].event_id)==IDS
panel=z.groupby(['method','pool_id','image'],as_index=False).agg(
 event_n=('event_id','size'),ABC_evaluable_n=('ABC_scored','sum'),
 Q_BA=('joint_Q_BA','mean'),Q_CA=('joint_Q_CA','mean'),Q_CB=('joint_Q_CB','mean'),
 direct_gap=('B8L2_same_origin_gap','mean'),symmetric_gap=('B8L2_symmetric_gap','mean'))
for method,g in panel.groupby('method'):
 for metric in ['Q_CA','Q_CB','direct_gap','symmetric_gap']:
  sets.append(dict(method=method,metric=metric,pools=len(g),mean=g[metric].mean(),
    positive_images=int((g[metric]>1e-10).sum()),negative_images=int((g[metric]<-1e-10).sum()),
    vfua_value=float(g[g.image.eq('VFuaQ6m2Qom-04')][metric].iloc[0]),
    other_six_mean_diagnostic_only=g[~g.image.eq('VFuaQ6m2Qom-04')][metric].mean(),
    vfua_is_not_excluded_from_primary_mean=True))

save('EXACT_METHOD_EQUIVALENCE_AND_STRICT_ABC.csv',equivalent)
save('FOUR_EVENT_SOURCE_ROWS.csv',events.loc[sorted(IDS)].reset_index())
save('FOUR_EVENT_FULL_METRICS.csv.gz',metrics.loc[sorted(IDS)].reset_index())
save('SIX_ARM_METRICS_AND_RING_COVERAGE.csv',arms)
save('ALL_110_VOTE_GROUPS.csv',groups)
save('ALL_VOTE_OBSERVATIONS.csv.gz',voters)
save('COMMON_D_COASSIGNMENT_CHANGES.csv',common)
save('MINIMUM_SOURCE_RING_COVER_OBSTRUCTIONS.csv',obstructions)
save('COMMON_SEVEN_POOL_EVENTS.csv',z)
save('COMMON_SEVEN_POOL_MEANS.csv',panel)
save('COMMON_SEVEN_POOL_MEAN_AND_SIGN.csv',sets)
receipt={'new_physical_teams':0,'method_event_rows':4,'distinct_ABC_sets':2,'distinct_replayed_teams':6,
  'source_group_count':len(groups),'source_vote_observations':len(voters),'same_method_pair_entities_verified':True,
  'reference_change':False,'Q_missing_policy':'missing, never zero','case_chosen_after_complete_results':True,
  'reason':'diagnose common-seven-pool negative mean versus six positive images',
  'source_sha256':{str(p.relative_to(WORK)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [STAGE/'EVENTS_EXACT.csv.gz',STAGE/'metrics/EVENT_METRICS.csv.gz',union_path]}}
(RESULTS/'VFUA_AUDIT_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
print(json.dumps({k:receipt[k] for k in ['method_event_rows','distinct_ABC_sets','distinct_replayed_teams','source_group_count','source_vote_observations']}))
