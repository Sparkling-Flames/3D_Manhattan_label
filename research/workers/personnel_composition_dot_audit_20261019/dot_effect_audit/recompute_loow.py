import pandas as pd,numpy as np,json,gzip
from pathlib import Path
root=Path('/workspace/shared/composition_audit_20261019');P=root/'extracted/personnel_composition_study_20261019/analysis/composition/compact_block_evidence'; O=Path(__file__).parent
E=pd.read_csv(P/'01_highlight_events.csv.gz');L=pd.read_csv(P/'04_highlight_loow_person.csv.gz');members={};event_checks=[]
for phase in ['discovery','validation']:
 with gzip.open(root/f'dot_replay_audit/requests/{phase.upper()}_BLOCK_REQUESTS.json.gz','rt') as f:d=json.load(f)
 selected=set(E[E.phase==phase].event_id)
 for e in d['events']:
  if e['event_id'] not in selected:continue
  arms=[set(e[a+'_workers']) for a in 'ABC'];core=set(e['core_workers'])
  if not (arms[0]&arms[1]==arms[0]&arms[2]==core):event_checks.append(e['event_id'])
  if not len(arms[0]-arms[1])==len(arms[0]-arms[2])==e['m']:event_checks.append(e['event_id'])
  members[e['event_id']]=set.union(*arms)
E['members']=E.event_id.map(members);errors=[];recomputed=[]
for r in L.to_dict('records'):
 g=E[(E.phase==r['phase'])&(E.highlight_id==r['highlight_id'])]
 if r['subset']=='actual_source_matched':g=g[g.actual_source_match]
 h=g[[r['removed_worker'] not in x for x in g.members]];q=h.C_B8L2-h.B_B8L2;b=q.groupby([h.building,h.pool_id]).mean().groupby(level=0).mean()
 vals={'retained_net_B8L2_change':b.mean(),'retained_events':len(h),'retained_images':h.pool_id.nunique(),'retained_buildings':h.building.nunique(),'net_B8L2_change_finite_events':q.notna().sum(),'net_B8L2_change_finite_images':h.loc[q.notna(),'pool_id'].nunique(),'net_B8L2_change_finite_buildings':b.notna().sum()}
 for key,v in vals.items():
  if not np.isclose(v,r[key],atol=1e-8,equal_nan=True):errors.append(dict(highlight=r['highlight_id'],phase=r['phase'],worker=r['removed_worker'],field=key,value=float(v),reported=r[key]))
 recomputed.append({k:r[k] for k in ['highlight_id','phase','subset','removed_worker','base_net_B8L2_change']}|{k:float(v) for k,v in vals.items()})
pd.DataFrame(recomputed).to_csv(O/'independent_loow.csv',index=False)
result=dict(rows_checked=len(L),exact_event_members_checked=len(members),member_match_errors=event_checks,loow_errors=errors)
(O/'loow_checks.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
