"""Independently count saved identity groups and recompute coordinate medians."""
from pathlib import Path
import gzip,json
import numpy as np
import pandas as pd

BASE=Path(__file__).resolve().parents[1]/'unpacked'
OUT=Path(__file__).resolve().parent
paths=[
 '06B/cases_reverse/f261cd4329817662818a5684',
 '06B/cases_size_threshold/3b15e1f073610cfe79b11d8a',
 '06B/cases_size_threshold/d8c03de1c870a22a3d448441',
]
cases={};groups=observations=0
native_files=['04B/results/batch02/ENDPOINT_SCALARS.csv.gz','05/results/size_paths/NATIVE_ENDPOINT_SCALARS.csv.gz']
fields=['team_key','B8L2','D10','IoU3D100','iou_2d','nodes','source_time_total_seconds']
targets=set()
for p in paths:
 with gzip.open(BASE/p/'CASE_GEOMETRY.json.gz','rt',encoding='utf8') as f:case=json.load(f)
 cases[case['event']['event_id']]=case
 targets.update(case['event'][a+'_team_key'] for a in 'ABC')
native=[]
for p in native_files:
 for d in pd.read_csv(BASE/p,usecols=fields,chunksize=10000):
  native.append(d[d.team_key.isin(targets)])
native=pd.concat(native).set_index('team_key')
assert len(native)==9 and not native.index.duplicated().any()
for case in cases.values():
 ev=case['event'];raw={r['id']:r for r in case['pool']['records']}
 votes=pd.read_csv(BASE/paths[list(cases).index(ev['event_id'])]/'VOTES.csv')
 for arm,state in case['states'].items():
  key=ev[arm+'_team_key'];saved=case['saved_endpoint_rows'][arm]
  for col in fields[1:]:assert np.isclose(saved[col],native.loc[key,col],rtol=1e-10,atol=1e-8),(arm,col)
  sel=[]
  for group in state['identity_groups']:
   groups+=1;ms=group['members'];workers={m['worker'] for m in ms}
   assert group['support']==len(workers)==len(ms)
   assert group['selected']==(group['support']>=state['minimum_support'])
   pts=[]
   for m in ms:
    r=raw[m['id']];p=np.array(r['points'])[m['pair_index']*2:m['pair_index']*2+2]
    assert r['worker']==m['worker'] and np.allclose(p,m['points'],atol=1e-9)
    pts.append(p);observations+=1
   points=np.array(pts);assert np.ptp(points[:,:,0])<512
   assert np.allclose(np.median(points,axis=0),group['center'],atol=1e-7)
   vr=votes[(votes.role==arm)&(votes.feature_id==group['feature_id'])].iloc[0]
   assert vr.support==len(workers) and vr.threshold==state['minimum_support'] and vr.selected==group['selected']
   if group['selected']:sel.append(group['feature_id'])
  assert set(sel)==set(state['candidate']['feature_ids'])
  assert len(sel)==saved['nodes']

# Verify the claimed R4/R6 changes using saved groups, not only the mechanism caption.
pre=cases['3b15e1f073610cfe79b11d8a'];post=cases['d8c03de1c870a22a3d448441']
ref=pd.read_csv(BASE/'06B/cases_size_threshold/REFERENCE_GROUPS_ACROSS_N.csv')
getgroup=lambda c,role,fid:next(g for g in c['states'][role]['identity_groups'] if g['feature_id']==fid)
casefacts={}
for rc in [4,6]:
 row=ref[(ref.role=='C')&(ref.reference_corner==rc)].iloc[0]
 x=getgroup(pre,'C',row.n14_feature_id);y=getgroup(post,'C',row.n15_feature_id)
 wx={m['worker'] for m in x['members']};wy={m['worker'] for m in y['members']}
 casefacts['R'+str(rc)]={'before_votes':len(wx),'after_votes':len(wy),'lost_workers':sorted(wx-wy),'before_selected':x['selected'],'after_selected':y['selected']}
 if rc==4:
  assert len(wx)==7 and wx==wy and np.allclose(x['center'],y['center'])
 else:
  assert len(wx)==8 and len(wy)==7 and wx-wy=={'W115'}
newgroup=next(g for g in post['states']['C']['identity_groups'] if {m['worker'] for m in g['members']}=={'W115','W117'})
assert not newgroup['selected']
casefacts['new_W115_W117_center']=newgroup['center']
casefacts['Q_C14_C15']=[pre['saved_endpoint_rows']['C']['B8L2'],post['saved_endpoint_rows']['C']['B8L2']]

reverse=cases['f261cd4329817662818a5684']
keyvotes=pd.read_csv(BASE/'06B/cases_reverse/f261cd4329817662818a5684/KEY_STRUCTURE_VOTES.csv')
reversefacts=[]
for row in keyvotes.itertuples(index=False):
 g=getgroup(reverse,row.role,row.group);ws={m['worker'] for m in g['members']};d=set(reverse['event']['D'].split('|'));block=set(reverse['event'][{'A':'X','B':'Y','C':'Z'}[row.role]].split('|'))
 assert len(ws&d)==row.common_D_votes and len(ws&block)==row.replacement_block_votes and len(ws)==row.total_votes
 reversefacts.append({'reference_corner':row.reference_corner,'arm':row.role,'D':len(ws&d),'block':len(ws&block),'total':len(ws)})

result={'case_endpoints':9,'identity_groups':groups,'raw_observations':observations,'all_group_support_selection_and_medians_match':True,'case_vs_original_native_scalar_match':True,'threshold_case':casefacts,'reverse_key_votes':reversefacts}
(OUT/'CASE_CHECKS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(result,ensure_ascii=False,indent=2))
