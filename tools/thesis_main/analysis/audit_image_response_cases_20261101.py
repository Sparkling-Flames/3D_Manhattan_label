from pathlib import Path
import pandas as pd,numpy as np,json,gzip,math
from shapely.geometry import Polygon
BASE=Path(__file__).resolve().parents[3]/'research/workers/image_response_v21_20261101'
R=BASE/'HOHONET_v21_image_response_20261101';out=BASE/'audit_geometry';result={}
# Explicit raw point -> candidate support reconstruction.
p=R/'stage04_doorway_cases';groups=pd.read_csv(p/'ALL_IDENTITY_GROUPS.csv');votes=pd.read_csv(p/'ALL_MEMBER_POINT_VOTES.csv')
for g in groups.itertuples():
 v=votes[(votes.case_id==g.case_id)&(votes.side==g.side)&(votes.feature_id==g.feature_id)]
 assert v.worker.nunique()==g.support
 assert g.selected==(g.support>=math.ceil(g.k*.5))
 assert set(str(g.workers).split('|'))==set(v.worker)
assert len(groups)==62 and len(votes)==727
for folder in (p/'cases').iterdir():
 lo=json.loads((folder/'low_VERIFIED_FULL_TRACE.json').read_text(encoding='utf8'));hi=json.loads((folder/'high_VERIFIED_FULL_TRACE.json').read_text(encoding='utf8'))
 a=set(lo['request']['member_object_ids_in_source_order']);b=set(hi['request']['member_object_ids_in_source_order']);assert a<b and len(b-a)==1
 for side,state in [('low',lo),('high',hi)]:
  workers=set(state['request']['member_workers_in_source_order'])
  observed=votes[(votes.case_id==folder.name)&votes.side.eq(side)]
  assert set(observed.worker)<=workers
  assert state['full_state']['n']==len(workers)
  for group in state['full_state']['identity_groups']:
   row=groups[(groups.case_id==folder.name)&groups.side.eq(side)&groups.feature_id.eq(group['feature_id'])].iloc[0]
   assert len(set(m['worker'] for m in group['members']))==row.support
 ex=pd.read_csv(folder/'ALL_EXACT_LEAVE_ONE_OUT_TEAMS.csv');assert ex.team_low.nunique()==len(b)==len(ex)
 result[folder.name]={'n':len(b),'exact_positive_Q':int((ex.delta_B8>0).sum()),'exact_added_nodes':int((ex.delta_nodes>0).sum()),'mean_delta_Q':float(ex.delta_B8.mean())}
# VFua full-team votes and status.
p=R/'stage05_cases/manual/VFuaQ6m2Qom-04';state=json.load(gzip.open(p/'FULL35_VERIFIED_DIAGNOSTIC_STATE.json.gz','rt',encoding='utf8'));f=state['full_state'];v=pd.read_csv(p/'FULL35_CANDIDATE_GROUP_VOTES.csv')
for g in f['identity_groups']:
 row=v[v.feature_id.eq(g['feature_id'])].iloc[0]
 assert len(set(x['worker'] for x in g['members']))==row.support
 assert bool(row.selected)==(row.support>=18)
assert (v.support==17).sum()==2 and v.selected.sum()==3
result['VFua_full35']={'selected':int(v.selected.sum()),'groups_at17':int((v.support==17).sum()),'formal_status':state['formal_status'],'formal_quality':state['formal_quality']}
for im in ['e9zR4mvMWw7-17','pa4otMbVnkk-11']:
 p=R/'stage05_cases/manual'/im;data=json.load(gzip.open(p/'SELECTED_CACHED_ENDPOINTS.json.gz','rt',encoding='utf8'));data=sorted(data,key=lambda x:x['k'])
 traced=pd.read_csv(p/'TRACED_ENDPOINT_METRICS.csv').set_index('team_key')
 for d in data:
  t=traced.loc[d['team_key']];assert np.isclose(t.B8L2,d['B8L2']);assert set(t.member_object_ids.split('|'))==set(d['member_object_ids'])
  assert all(s==d['k'] for s in d['node_supports'])
  assert d['unselected_groups_n']==0
 if im.startswith('e9'):
  assert [d['k'] for d in data]==[11,12,13] and all(d['nodes']==4 for d in data)
  for a,b in zip(data,data[1:]):assert set(a['member_object_ids'])<set(b['member_object_ids']) and len(set(b['member_object_ids'])-set(a['member_object_ids']))==1
  geo=[Polygon(d['geometry']['footprint']) for d in data]
  result[im]={'Q':[d['B8L2'] for d in data],'area_changes_percent':[(b.area/a.area-1)*100 for a,b in zip(geo,geo[1:])],'centroid_displacements':[a.centroid.distance(b.centroid) for a,b in zip(geo,geo[1:])]}
 else:
  raw=pd.read_csv(p/'ALL_RAW_POINT_PAIRS.csv');assert raw.worker.nunique()==35 and (raw.groupby('worker').pair_index.nunique()==8).all()
  assert all(d['nodes']==8 and d['reference_nodes']==4 for d in data)
  curve=pd.read_csv(p/'CURRENT_256_CURVE.csv');print('curve cols',list(curve.columns))
  result[im]={'people':35,'pairs_per_person':8,'reference_pairs':4,'fullQ':data[-1]['B8L2']}
(out/'CASE_CHECKS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(result,ensure_ascii=False,indent=2))
