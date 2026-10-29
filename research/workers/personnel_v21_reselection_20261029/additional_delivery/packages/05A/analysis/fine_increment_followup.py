"""Failure/tail denominators and matched finite support for fine-class effects."""
from pathlib import Path
import gzip,json,os,sys
import numpy as np,pandas as pd
W=Path(__file__).resolve().parents[1];O=W/'analysis/fine_increment'
def save(p,d):
 b=d.to_csv(index=False).encode('utf-8-sig')
 if p.suffix=='.gz':b=gzip.compress(b,mtime=0)
 t=p.with_name(p.name+'.writing')
 with t.open('wb') as f:f.write(b);f.flush();os.fsync(f.fileno())
 t.replace(p)

meta=['event_id','method','parent_method','condition','scope','layer','pool_id','image','building','official_difficulty',
 'direction_axis','role_direction','direction_semantic','n','m','background_id','block_id','pool_n',
 'source_pool_capacity','target_pool_capacity','source_candidate_fraction','target_candidate_fraction',
 'replacement_fraction','A_team_key','B_team_key','C_team_key','A_members','B_members','C_members','D','X','Y','Z',
 'A_parent_vector','B_parent_vector','C_parent_vector','A_class_vector','B_class_vector','C_class_vector',
 'source_class','target_class','source_semantic_training_role','target_semantic_training_role','time_signature_group']
values=[f'{letter}_{metric}' for letter in 'ABC' for metric in ['B8L2','D10','failed','incomplete','nonusable']]
percent=[f'record_time_{p}_pct_source_matched' for p in ['BA','CA','CB']]
e=pd.read_csv(O/'FIXED_PARENT_EVENT_METRICS.csv.gz',usecols=meta+values+percent,low_memory=False)
for pair,l,r in [('BA','B','A'),('CA','C','A'),('CB','C','B')]:
 e[pair+'_delta_Q']=e[l+'_B8L2']-e[r+'_B8L2']
 e[pair+'_pair_scored']=e[pair+'_delta_Q'].notna()
 e[pair+'_Q_loss10']=e[pair+'_delta_Q'].lt(-10)
 e[pair+'_Q_improved']=e[pair+'_delta_Q'].gt(1e-9)
 e[pair+'_rescue_nonusable']=e[r+'_nonusable'].eq(1)&e[l+'_nonusable'].eq(0)
 e[pair+'_new_nonusable']=e[r+'_nonusable'].eq(0)&e[l+'_nonusable'].eq(1)
 e[pair+'_target_nonusable_or_Q_loss10']=e[l+'_nonusable'].eq(1)|e[pair+'_Q_loss10']
e['ABC_scored_current']=e[['A_B8L2','B_B8L2','C_B8L2']].notna().all(axis=1)
keys=['method','parent_method','condition','scope','layer','direction_axis','role_direction','n','m']
rows=[]
for k,g in e.groupby(keys,dropna=False):
 r=dict(zip(keys,k));r.update(events=len(g),images=g.image.nunique(),buildings=g.building.nunique(),
  pools=g.pool_id.nunique(),backgrounds=g.background_id.nunique(),block_paths=g.block_id.nunique(),
  unique_endpoints=len(set(g.A_team_key)|set(g.B_team_key)|set(g.C_team_key)),ABC_scored=int(g.ABC_scored_current.sum()))
 for letter in 'ABC':
  for kind in ['failed','incomplete','nonusable']:r[letter+'_'+kind]=int(g[letter+'_'+kind].sum())
 for pair in ['BA','CA','CB']:
  d=g[pair+'_delta_Q'].dropna();r[pair+'_quality_denominator']=len(d)
  for field in ['Q_loss10','Q_improved','rescue_nonusable','new_nonusable','target_nonusable_or_Q_loss10']:
   r[pair+'_'+field]=int(g[pair+'_'+field].sum())
  for name,q in [('p05',.05),('p10',.1),('median',.5),('p90',.9)]:r[pair+'_deltaQ_'+name]=float(d.quantile(q)) if len(d) else np.nan
  r[pair+'_Q_loss10_fraction']=r[pair+'_Q_loss10']/len(d) if len(d) else np.nan
  r[pair+'_target_nonusable_or_Q_loss10_fraction']=r[pair+'_target_nonusable_or_Q_loss10']/len(g)
 rows.append(r)
save(O/'QUALITY_TAIL_AND_FAILURE_DENOMINATORS.csv',pd.DataFrame(rows))
save(O/'EXACT_EVENT_ROLES_MEMBERS_AND_QUALITY_RISK.csv.gz',e)
if '--risk-only' in sys.argv:
 print(json.dumps(dict(risk_conditions=len(rows),events=len(e),risk_stage_complete=True)),flush=True)
 raise SystemExit(0)

# These comparisons share actual target pool, n, m. Fine classes, parent
# mixtures, and physical backgrounds can differ by method; no causal method
# comparison is implied. Within each method the original ABC is exact.
cells=pd.read_csv(O/'CELL_METRICS.csv.gz',low_memory=False)
metrics=['B8L2','D10','fusion_turn_n','geometry_bev_distance','height_mean_h','record_time_pct_source_matched','nonusable']
cells=cells[cells.metric.isin(metrics)].copy()
fields=['same_abs','cross_symmetric_abs','cross_AC_abs','gap_symmetric','gap_AC','BA','CA','CB']
pair_records=[]
for (condition,scope,layer,metric,source),all_rows in cells.groupby(['condition','scope','layer','metric','time_source'],dropna=False):
 base=all_rows.groupby(['method','pool_id','image','building','n','m'],dropna=False)[fields].mean().reset_index()
 methods=sorted(base.method.unique());maps={m:base[base.method.eq(m)] for m in methods}
 for i,left in enumerate(methods):
  for right in methods[i+1:]:
   a=maps[left];b=maps[right]
   z=a.merge(b,on=['pool_id','image','building','n','m'],suffixes=('_left','_right'))
   if not len(z):continue
   cols=[f+s for f in fields for s in ['_left','_right']]
   # Cells -> target pool -> image -> building, equally weighted each level.
   p=z.groupby(['pool_id','image','building'])[cols].mean().reset_index()
   im=p.groupby(['image','building'])[cols].mean().reset_index();bu=im.groupby('building')[cols].mean()
   r=dict(left_method=left,right_method=right,condition=condition,scope=scope,layer=layer,
    metric=metric,time_source=source,common_pool_n_m_cells=len(z),common_pools=z.pool_id.nunique(),
    common_images=z.image.nunique(),common_buildings=z.building.nunique(),
    left_all_pool_n_m_cells=len(a),right_all_pool_n_m_cells=len(b),
    common_level='same target pool/n/m; source/target child roles and physical D may differ; descriptive comparison')
   for f in fields:
    r[f+'_left']=bu[f+'_left'].mean();r[f+'_right']=bu[f+'_right'].mean()
    r[f+'_left_minus_right']=r[f+'_left']-r[f+'_right']
   pair_records.append(r)
save(O/'FINE_METHOD_COMMON_POOL_N_M_COMPARISON.csv',pd.DataFrame(pair_records))
(O/'FOLLOWUP_COMPLETE.json').write_text(json.dumps(dict(risk_conditions=len(rows),paired_method_comparisons=len(pair_records),new_fusions=0),indent=2))
print(json.dumps(dict(risk_conditions=len(rows),paired_method_comparisons=len(pair_records))),flush=True)
