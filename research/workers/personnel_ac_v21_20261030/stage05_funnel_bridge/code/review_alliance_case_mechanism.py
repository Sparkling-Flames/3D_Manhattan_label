"""Small read-only mechanism check for the capacity-preselected 7-alliance case.

This is not an eligibility, exclusion, reference, or label reaudit.
"""
from pathlib import Path
import gzip,hashlib,json,math
import numpy as np
import pandas as pd

OUT=Path(__file__).resolve().parents[1];BASE=OUT.parent
CASE=BASE/'stage06_cases/alliance_pa4_06'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(gzip.decompress(p.read_bytes()))
def known_time(d):
 x=json.loads(d['record_time_by_kind_json']);a={k:v for k,v in x.items() if int(v['n'])>0}
 known=all(v['known_n']==v['n'] and v['total_seconds'] is not None and v['total_seconds']>=0 for v in a.values())
 return known,tuple(sorted((k,v['n']) for k,v in a.items())),next(iter(a)) if len(a)==1 else '',sum(v['total_seconds'] for v in a.values())
def main():
 endpoints=pd.read_csv(CASE/'figures/SEVEN_ALLIANCE_ENDPOINTS.csv');pairs=pd.read_csv(CASE/'figures/ALL_21_CONTRASTS_ORIGINAL_ORIENTATION.csv')
 choice=pd.read_csv(CASE/'SELECTION_REGISTERED_21.csv').set_index('event_id')
 traces={r.team_key:load(CASE/'trace_endpoints'/(r.team_key+'.json.gz')) for r in endpoints.itertuples()}
 assert len(traces)==7 and len(pairs)==21 and len(choice)==21
 sample=load(next((CASE/'traces').glob('*.json.gz')))
 raw=sample['pool']['records'];assert len(raw)==35 and len({r['worker'] for r in raw})==35
 assert all(len(r['points'])==8 and len(r['source_pair_indices'])==4 for r in raw)
 checks=[];groups=0
 for r in endpoints.itertuples():
  e=traces[r.team_key];s=e['full_state'];ws=set(e['member_workers']);n=len(ws);ig=s['identity_groups'];selected={g['feature_id'] for g in ig if g['selected']}
  assert n==r.n==s['n'] and s['minimum_support']==math.ceil(n/2)
  assert len(ig)==len(selected)==4
  for g in ig:
   assert g['support']==n and {m['worker'] for m in g['members']}==ws and len(g['members'])==n
   center=np.median(np.asarray([m['points'] for m in g['members']]),axis=0)
   assert np.max(np.abs(center-np.asarray(g['center'])))<1e-9
  assigns=s['assignments'];assert len(assigns)==n and {a['worker'] for a in assigns}==ws
  assert all(len(a['feature_ids'])==4 and set(a['feature_ids'])==selected for a in assigns)
  edges=s['ring_diagnostics']['edges'];assert len(edges)==4 and not s['ring_diagnostics']['tied_best']
  assert all(ed['direct_support']==n and ed['projected_support']==n and set(ed['direct_workers'])==ws and set(ed['projected_workers'])==ws for ed in edges)
  assert e['score_status']=='complete_conditional' and e['ref_node_recall_9']==e['ref_edge_recall_9']==1
  for metric in ['B8L2','D10','geometry_area_h2','height_mean_h','boundary_loss','direction_loss','height_loss']:
   assert abs(getattr(r,metric)-e[metric])<1e-9
  groups+=len(ig);checks.append(dict(alliance=r.alliance,team_key=r.team_key,n=n,all_identity_groups=4,
    unanimous_groups=4,each_original_ring_covers_all_selected_nodes=True,all_edge_votes_unanimous=True,all_node_centers_equal_full_member_coordinate_medians=True))
 # Restore original link orientation independently from the canonical event.
 eventids=set(pairs.event_id)
 reg=pd.read_csv(BASE/'stage01_registered/AC_EVENTS.csv.gz',usecols=['event_id','A_team_key','C_team_key'],low_memory=False)
 reg=reg[reg.event_id.isin(eventids)].set_index('event_id');assert len(reg)==21
 link=pd.read_csv(BASE/'stage01_registered/DESIGN_LINKS.csv.gz',usecols=['event_id','design_family','input_orientation_sign','A_alliance','C_alliance'],low_memory=False)
 link=link[link.event_id.isin(eventids)&link.design_family.eq('C_complete_class_alliances')]
 single=matched=0;reverse=0;seen_pairs=set()
 metrics=['B8L2','D10','IoU3D100','boundary_loss','direction_loss','height_loss','nodes','geometry_area_h2','height_mean_h']
 for p in pairs.itertuples():
  e=reg.loc[p.event_id];selection=choice.loc[p.event_id];sign=int(p.input_orientation_sign)
  assert sign==int(selection.input_orientation_sign)
  a,c=(e.A_team_key,e.C_team_key) if sign==1 else (e.C_team_key,e.A_team_key)
  assert (a,c)==(p.from_team_key,p.to_team_key);reverse+=sign==-1
  ll=link[link.event_id.eq(p.event_id)]
  assert ((ll.input_orientation_sign.eq(sign))&ll.A_alliance.eq(p.from_alliance)&ll.C_alliance.eq(p.to_alliance)).any()
  edge=tuple(sorted([a,c]));assert edge not in seen_pairs;seen_pairs.add(edge)
  for m in metrics:
   assert abs(getattr(p,'from_'+m)-traces[a][m])<1e-9
   assert abs(getattr(p,'to_'+m)-traces[c][m])<1e-9
   assert abs(getattr(p,'to_minus_from_'+m)-(traces[c][m]-traces[a][m]))<1e-9
  ak,asig,atype,at=known_time(traces[a]);ck,csig,ctype,ct=known_time(traces[c])
  sv=ak and ck and atype!='' and atype==ctype;mv=ak and ck and asig==csig
  assert sv==p.labor_same_single_source_valid and mv==p.labor_source_count_matched_valid
  single+=sv;matched+=mv
  if sv:
   assert abs(p.labor_seconds_single_source-(ct-at))<1e-9 and abs(p.labor_pct_single_source-100*(ct/at-1))<1e-9
  else:assert pd.isna(p.labor_seconds_single_source) and pd.isna(p.labor_pct_single_source)
  if not mv:assert pd.isna(p.labor_seconds_source_count_matched) and pd.isna(p.labor_pct_source_count_matched)
 assert groups==28 and single==3 and matched==0
 receipt=dict(status='passed',scope='read-only mechanism evidence, not qualification/reference/label reaudit',
  original_people=35,all_original_corner_pair_counts=4,teams=7,identity_groups=groups,all_groups_unanimous=True,
  all_source_rings_cover_all_selected_nodes=True,all_connections_unanimous=True,all_centers_equal_full_group_coordinate_medians=True,
  original_orientation_contrasts_checked=21,reversed_from_canonical_events=reverse,same_single_source_labor_pairs=single,
  exact_source_count_matched_labor_pairs=matched,new_teams=0,new_fusions=0,new_scores=0,
  interpretive_boundary='No unselected node or threshold-crossing mechanism occurs in this case. Position/shape/height changes are supported; unequal sizes and background proportions remain confounded in alliance comparisons.',
  endpoints=checks,source_hashes={str(p.relative_to(BASE)):sha(p) for p in [CASE/'figures/SEVEN_ALLIANCE_ENDPOINTS.csv',CASE/'figures/ALL_21_CONTRASTS_ORIGINAL_ORIENTATION.csv',CASE/'SELECTION_REGISTERED_21.csv']})
 (OUT/'ALLIANCE_PA4_06_MECHANISM_INDEPENDENT_REVIEW.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
 print(json.dumps({k:v for k,v in receipt.items() if k not in ['endpoints','source_hashes']},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
