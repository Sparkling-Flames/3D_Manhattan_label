"""Complete status/component denominators, pair-direction repetition and cases."""
from pathlib import Path
import pandas as pd,numpy as np,json,gzip,hashlib
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'stage02_same_room/abc';SRC=ROOT/'source'
def save(d,name):
 p=OUT/name;t=p.with_name(p.name+'.tmp');d.to_csv(t,index=False,compression={'method':'gzip','compresslevel':3,'mtime':0} if name.endswith('.gz') else None);t.replace(p)
e=pd.read_csv(OUT/'EVENT_IDENTITIES.csv.gz');native=pd.read_csv(OUT/'EXISTING_ENDPOINT_STATUS_COMPONENTS.csv.gz',low_memory=False).set_index('team_key');original=pd.read_csv(ROOT/'stage02_same_room/EXISTING_VALID_EVENT_SOURCE.csv.gz',low_memory=False).set_index('event_id')
e['block_key']=e.X_members.fillna('')+' / '+e.Y_members.fillna('')+' / '+e.Z_members.fillna('')
relations=json.loads((SRC/'research/same_room/relation_adoption_20261016/relations.json').read_text());rm={tuple(sorted([r['image_a'],r['image_b']])):r for r in relations}
e['relation_oos_pending']=[rm[tuple(sorted([a,b]))]['oos_pending'] for a,b in zip(e.image_id_a,e.image_id_b)]
e['relation_tier']=[rm[tuple(sorted([a,b]))]['tier'] for a,b in zip(e.image_id_a,e.image_id_b)]
save(e.drop(columns='block_key'),'EVENT_IDENTITIES.csv.gz')
state=e[['event_id','physical_event_key','final_method','analysis_scope','condition','building','pair_key','groups','image_a','image_b','n','m','ratio_band','role_direction','relation_oos_pending']].copy()
for v in ['a','b']:
 for r in ['A','B','C']:
  nn=native.reindex(e[f'team_{r}_{v}'])
  assert nn.index.to_numpy().tolist()==e[f'team_{r}_{v}'].tolist()
  for c in ['score_status','geometry_status','geometry_reason','complete_evaluable','score_available','connection_available','B8L2','D10','geometry_state_pointer']:
   state[f'{c}_{r}_{v}']=nn[c].to_numpy()
  # Independently verify every stored Q endpoint against the original event table.
  old=original.reindex(e.event_id)[f'Q_{r}_{v}'].to_numpy(float);cur=nn.B8L2.to_numpy(float)
  assert np.array_equal(np.isnan(old),np.isnan(cur));assert np.max(np.abs(old[np.isfinite(old)]-cur[np.isfinite(cur)]),initial=0)<1e-10
save(state,'EVENT_ENDPOINT_STATES.csv.gz')
st=[]
for keys,z in state.groupby(['final_method','analysis_scope','condition','role_direction','n','m','ratio_band']):
 row=dict(zip(['final_method','analysis_scope','condition','role_direction','n','m','ratio_band'],keys));row.update(events=len(z),pairs=z.pair_key.nunique(),buildings=z.building.nunique())
 arr=z[[f'score_status_{r}_{v}' for v in ['a','b'] for r in ['A','B','C']]].to_numpy()
 for status in ['complete_conditional','below_four','no_connection','invalid_floor']:
  row[status+'_endpoint_uses']=int((arr==status).sum());row[status+'_events_any']=int((arr==status).any(axis=1).sum())
 row['endpoint_uses']=arr.size;st.append(row)
save(pd.DataFrame(st),'CONDITION_ENDPOINT_STATUS_COUNTS.csv')
keys=['final_method','analysis_scope','condition','building','groups','pair_key','role_direction','n','m','ratio_band']
comp=[];cfgall=[]
for metric in ['WQ','A10','boundary_loss','direction_loss','height_loss','global_height_loss','local_height_loss']:
 z=e[keys+['block_key']].copy();valid=np.ones(len(e),bool)
 for v in ['a','b']:
  arr=np.column_stack([native.reindex(e[f'team_{r}_{v}'])[metric].to_numpy(float) for r in ['A','B','C']]);valid &=np.all(np.isfinite(arr),axis=1)
  A,B,C=arr.T
  for c,val in [('A',A),('B',B),('C',C),('CB',C-B),('W',np.abs(B-A)),('GA',np.abs(C-A)-np.abs(B-A)),('GS',(np.abs(C-A)+np.abs(C-B))/2-np.abs(B-A))]:z[c+'_'+v]=val
 cols=[c+'_'+v for c in ['A','B','C','CB','W','GA','GS'] for v in ['a','b']];z.loc[~valid,cols]=np.nan
 for c in ['A','B','C','CB','W','GA','GS']:z[c+'_mean']=(z[c+'_a']+z[c+'_b'])/2
 cols+=['A_mean','B_mean','C_mean','CB_mean','W_mean','GA_mean','GS_mean']
 cfg=z.groupby(keys+['block_key'],dropna=False)[cols].mean().groupby(level=list(range(len(keys)))).mean().reset_index();cfg['metric']=metric;cfgall.append(cfg)
 for level,ek in [('all',[]),('ratio',['ratio_band']),('direction_nm',['role_direction','n','m'])]:
  for kk,g in cfg.groupby(['final_method','analysis_scope','condition']+ek,dropna=False):
   meta=dict(zip(['final_method','analysis_scope','condition']+ek,kk));pa=g.groupby(['building','groups','pair_key'])[cols].mean().reset_index();ex=pa.assign(group_id=pa.groups.str.split('|')).explode('group_id');bd=ex.groupby(['building','group_id'])[cols].mean().groupby('building').mean()
   row={**meta,'metric':metric,'level':level,'valid_pairs':int(pa.CB_mean.notna().sum()),'valid_buildings':int(bd.CB_mean.notna().sum())}
   for c in cols:row['building_equal_'+c]=bd[c].mean();row['pair_equal_'+c]=pa[c].mean()
   row['pair_CB_positive']=int(pa.CB_mean.gt(1e-9).sum());row['pair_CB_negative']=int(pa.CB_mean.lt(-1e-9).sum());comp.append(row)
save(pd.concat(cfgall,ignore_index=True),'Q_COMPONENT_CONDITIONS.csv.gz');save(pd.DataFrame(comp),'Q_COMPONENT_SUMMARY.csv')
# A pair-average positive is distinct from both views being positive.
p=pd.read_csv(OUT/'PAIR_METRICS.csv.gz',low_memory=False);levels=['final_method','analysis_scope','condition','metric','level','role_direction','n','m','ratio_band'];out=[]
pair_images=e.drop_duplicates('pair_key').set_index('pair_key')[['image_a','image_b']].to_dict('index')
for kk,g in p.groupby(levels,dropna=False):
 meta=dict(zip(levels,kk));good=g.GS_mean.notna();z=g[good];row={**meta,'valid_pairs':len(z),'valid_images':len({im for pair in z.pair_key for im in pair_images[pair].values()}),'valid_buildings':z.building.nunique()}
 for c in ['GA','GS','CB']:
  x=z.dropna(subset=[c+'_a',c+'_b']);aa=x[c+'_a'];bb=x[c+'_b'];eps=1e-9
  row.update({c+'_pairs_evaluable':len(x),c+'_both_positive_pairs':int(((aa>eps)&(bb>eps)).sum()),c+'_both_negative_pairs':int(((aa< -eps)&(bb< -eps)).sum()),c+'_opposite_pairs':int((aa*bb< -eps).sum()),c+'_both_zero_pairs':int(((aa.abs()<=eps)&(bb.abs()<=eps)).sum()),c+'_one_zero_pairs':int(((aa.abs()<=eps)^(bb.abs()<=eps)).sum()),c+'_pair_mean_positive':int(x[c+'_mean'].gt(eps).sum())})
  den=int((aa>eps).sum()+(bb>eps).sum());row[c+'_positive_source_pairviews']=den;row[c+'_positive_source_then_positive']=2*row[c+'_both_positive_pairs']/den if den else np.nan
 out.append(row)
save(pd.DataFrame(out),'PAIR_VIEW_REPETITION.csv')
# Complete event sets for two 14/7 pairs and the 10/5 C-B sign-reversal pair.
selected=['S9hNv5qa7GM-05','S9hNv5qa7GM-10','pa4otMbVnkk-42']
case=e[e.final_method.eq('TARGET_DSTRUCT_K3')&e.analysis_scope.eq('ordinary_comparable')&e.role_direction.eq('2→3')&(((e.n.eq(14)&e.m.eq(7)))|((e.n.eq(10)&e.m.eq(5))&e.image_a.eq('S9hNv5qa7GM-10')&e.image_b.eq('S9hNv5qa7GM-19')))].copy()
ce=case.merge(original.reset_index()[['event_id']+[f'{mt}_{v}_{c}' for mt in ['B8L2','D10','fusion_turn_n','fusion_short_turn_edges','S_bottom_deg','dir','Hmean','Hcenter','recorded_time_total_seconds'] for v in ['a','b'] for c in ['BA','CA','CB']]],on='event_id',validate='one_to_one')
save(ce,'PAIRED_CASE_EVENTS.csv.gz')
save(state[state.event_id.isin(case.event_id)&state.final_method.eq('TARGET_DSTRUCT_K3')],'PAIRED_CASE_ENDPOINT_STATES.csv.gz')
oldsum=pd.read_csv(OUT/'SUMMARY.csv',low_memory=False);assert len(pd.DataFrame(out))==len(oldsum)
check=dict(endpoint_Q_cells_verified=len(state)*6,endpoint_Q_nan_patterns_equal=True,current_event_relation_pending_rows=int(e.relation_oos_pending.sum()),raw_statuses=native.score_status.value_counts().to_dict(),cases_events=len(case),case_pairs=case.pair_key.nunique(),pair_view_summary_rows=len(out),component_metrics=7,new_fusion_calls=0,interpretation='no_connection is a saved native connection failure; below_four and invalid_floor are separate incomplete/unscorable states, not zero Q')
(OUT/'FINAL_JOIN_CHECKS.json').write_text(json.dumps(check,ensure_ascii=False,indent=2));print(json.dumps(check,ensure_ascii=False),flush=True)
