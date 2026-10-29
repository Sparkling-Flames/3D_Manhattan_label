"""Fine-class exchange on exact A/B/C-invariant parent compositions.

Uses frozen labels and already computed endpoints only. All fixed-parent events
are retained. Global candidate ranking is a separate analysis.
"""
from pathlib import Path
import argparse,gzip,hashlib,json,os
import numpy as np,pandas as pd

W=Path(__file__).resolve().parents[1];O=W/'analysis/fine_increment';O.mkdir(exist_ok=True)
def save(p,d):
 p=Path(p);b=d.to_csv(index=False).encode('utf-8-sig')
 if p.suffix=='.gz':b=gzip.compress(b,compresslevel=6,mtime=0)
 t=p.with_name(p.name+'.writing')
 with t.open('wb') as f:f.write(b);f.flush();os.fsync(f.fileno())
 t.replace(p)
def truth(s):return s.astype(str).str.lower().isin(['true','1','1.0'])
def direction(s,eps=1e-9):
 return np.select([s.gt(eps),s.lt(-eps),s.abs().le(eps)],['higher','lower','equal'],default='unknown')

ROLE_FEATURES={'turn':'m_all_turn_n','challenge_turn':'m_challenge_turn_n',
 'Q':'m_all_B8L2','log_time':'m_all_log_time','log_area':'m_all_log_area_ratio',
 'log_height':'m_all_log_height','redundancy':'m_all_near_straight_nodes_5deg',
 'response_turn':'own_fusion_all_turn','response_hard_turn':'own_fusion_hard_turn','response_Q':'own_fusion_Q'}
SCALARS=['B8L2','D10','IoU3D100','iou_2d','S_bottom_deg','dir','Hmean','Hcenter',
 'omission','extension','height_mean_ratio','nodes','fusion_turn_n','fusion_short_turn_edges',
 'fusion_redundancy_n','geometry_area_h2','height_mean_h','height_min_h','height_max_h',
 'centroid_x_h','centroid_z_h','ref_node_recall_5','ref_node_recall_9','ref_edge_recall_5','ref_edge_recall_9',
 'reference_node_shortfall','reference_node_excess','top_y_mean_px','bottom_y_mean_px',
 'matched_ref_top_abs_deg','matched_ref_bottom_abs_deg','matched_ref_horizontal_abs_deg',
 'boundary_loss','direction_loss','height_loss','floor_WQ','WQ','WQ_no_D','WQ_no_B','WQ_no_H',
 'diag_wall_coverage_03','diag_wall_coverage_05','diag_corner_recall_05','minimum_support',
 'identity_groups_n','unselected_groups_n','half_vote_nodes','selected_support_min',
 'source_time_total_seconds','recorded_time_total_seconds']
GEOMETRY=['geometry_bev_distance','geometry_pair_angle','geometry_top_angle','geometry_bottom_angle',
 'geometry_centroid_distance','geometry_log_area_distance','geometry_unmatched_pairs']
EFFECTS=['same_abs','cross_symmetric_abs','cross_AC_abs','gap_symmetric','gap_AC','BA','CA','CB']

def snapshot():
 p=W/'analysis/global_parent_links/EVENT_PARENT_LINKS.csv.gz';links=pd.read_csv(p)
 links=links[truth(links.fine_exchange_fixed_parent)].copy();ids=set(links.event_id)
 assert len(ids)==len(links)
 source=W/'analysis/global_screen/EVENT_METRICS.csv.gz';parts=[]
 for chunk in pd.read_csv(source,chunksize=4096,low_memory=False):
  z=chunk[chunk.event_id.isin(ids)]
  if len(z):parts.append(z.copy())
 e=pd.concat(parts,ignore_index=True)
 assert set(e.event_id)==ids and e.event_id.is_unique
 e=e.merge(links,on=['event_id','method','heldout_building'],validate='one_to_one')
 assert e.A_parent_vector.eq(e.B_parent_vector).all() and e.A_parent_vector.eq(e.C_parent_vector).all()
 assert (e.actual_m_AB==e.m).all() and (e.actual_m_AC==e.m).all() and (e.actual_m_BC==e.m).all()
 roles=pd.read_csv(W/'classification/CLASS_ROLES_COMPACT_ALL_LOBO.csv.gz',low_memory=False)
 rolecols=['method','heldout_building','class_id','semantic_training_role','workers']+list(ROLE_FEATURES.values())
 for prefix,key in [('source','source_class'),('target','target_class')]:
  r=roles[rolecols].rename(columns={'class_id':key,**{c:prefix+'_'+c for c in rolecols if c not in ['method','heldout_building','class_id']}})
  e=e.merge(r,on=['method','heldout_building',key],how='left',validate='many_to_one')
 for short,col in ROLE_FEATURES.items():
  e['history_delta_'+short]=e['target_'+col]-e['source_'+col]
  e['direction_'+short]=direction(e['history_delta_'+short])
 e['direction_QT']=e.direction_Q+'_Q__'+e.direction_log_time+'_logtime'
 def family_axis(method):
  if method.startswith(('RFUSE','TARGET_RFUSE')):return 'response_hard_turn'
  if method.startswith('DBOUNDARY'):return 'log_height'
  if method.startswith(('DJOINT','OPPJOINT','V3_JOINT')):return 'QT'
  return 'challenge_turn'
 e['direction_axis']=e.method.map(family_axis)
 e['role_direction']=[row['direction_'+row['direction_axis']] for _,row in e.iterrows()]
 e['direction_semantic']=e.direction_axis+'__'+e.role_direction
 e['source_pool_capacity']=(e.m/e.source_candidate_fraction).round().astype('Int64')
 e['target_pool_capacity']=(e.m/e.target_candidate_fraction).round().astype('Int64')
 for letter in ['A','B','C']:
  e[letter+'_nonusable']=(truth(e[letter+'_failed'])|truth(e[letter+'_incomplete'])|e[letter+'_B8L2'].isna()).astype(float)
  e[letter+'_failed']=truth(e[letter+'_failed']).astype(float)
  e[letter+'_incomplete']=truth(e[letter+'_incomplete']).astype(float)
 e['time_signature_group']='not_comparable'
 for i in e.index[truth(e.time_comparable_ABC)]:
  sig=json.loads(e.at[i,'time_source_signature_A'])
  e.at[i,'time_signature_group']=str(sig[0][0]) if len(sig)==1 else 'mixed_sources_matched_counts'
 save(O/'FIXED_PARENT_EVENT_METRICS.csv.gz',e)
 save(O/'FIXED_PARENT_EVENT_LINKS.csv.gz',links)
 used=roles.merge(pd.concat([e[['method','heldout_building','source_class']].rename(columns={'source_class':'class_id'}),
  e[['method','heldout_building','target_class']].rename(columns={'target_class':'class_id'})]).drop_duplicates(),
  on=['method','heldout_building','class_id'],validate='one_to_one')
 save(O/'USED_LOBO_ROLE_CENTERS.csv.gz',used)
 hierarchy=pd.read_csv(W/'analysis/global_parent_links/METHOD_HIERARCHY_ALL_LOBO.csv')
 save(O/'EXACT_PARENT_CLASS_MAP.csv',hierarchy[hierarchy.child_method.isin(e.method)])
 result=dict(events=len(e),methods=e.method.nunique(),images=e.image.nunique(),buildings=e.building.nunique(),
  pools=e.pool_id.nunique(),strict_ABC=True,new_fusions=0,unique_endpoints=len(set(e.A_team_key)|set(e.B_team_key)|set(e.C_team_key)),
  source_hashes={str(q.relative_to(W)):hashlib.sha256(q.read_bytes()).hexdigest() for q in [p,source,W/'classification/CLASS_ROLES_COMPACT_ALL_LOBO.csv.gz']})
 (O/'SNAPSHOT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
 print(json.dumps(result,ensure_ascii=False),flush=True)
 return e

def metric_values(e,metric):
 if metric in GEOMETRY:
  a=pd.to_numeric(e[metric+'_AB'],errors='coerce');b=pd.to_numeric(e[metric+'_AC'],errors='coerce');c=pd.to_numeric(e[metric+'_BC'],errors='coerce')
  complete=a.notna()&b.notna()&c.notna();a=a.where(complete);b=b.where(complete);c=c.where(complete)
  return pd.DataFrame(dict(same_abs=a,cross_symmetric_abs=(b+c)/2,cross_AC_abs=b,
   gap_symmetric=(b+c)/2-a,gap_AC=b-a,BA=np.nan,CA=np.nan,CB=np.nan),index=e.index)
 if metric=='record_time_pct_source_matched':
  ba=e.record_time_BA_pct_source_matched;ca=e.record_time_CA_pct_source_matched;cb=e.record_time_CB_pct_source_matched
  valid=ba.notna()&ca.notna()&cb.notna();ba=ba.where(valid);ca=ca.where(valid);cb=cb.where(valid)
 else:
  a=pd.to_numeric(e['A_'+metric],errors='coerce');b=pd.to_numeric(e['B_'+metric],errors='coerce');c=pd.to_numeric(e['C_'+metric],errors='coerce')
  valid=a.notna()&b.notna()&c.notna()
  if metric in ['source_time_total_seconds','recorded_time_total_seconds']:valid &= truth(e.time_comparable_ABC)
  a=a.where(valid);b=b.where(valid);c=c.where(valid);ba=b-a;ca=c-a;cb=c-b
 return pd.DataFrame(dict(same_abs=ba.abs(),cross_symmetric_abs=(ca.abs()+cb.abs())/2,cross_AC_abs=ca.abs(),
  gap_symmetric=(ca.abs()+cb.abs())/2-ba.abs(),gap_AC=ca.abs()-ba.abs(),BA=ba,CA=ca,CB=cb),index=e.index)

def summaries(e):
 # Per exact-cell endpoints are all fixed-parent. Average backgrounds within
 # block path, then block paths, before target/image/building macro summaries.
 meta=['event_id','method','parent_method','condition','scope','layer','official_difficulty',
  'pool_id','image','building','n','m','background_id','block_id','direction_axis','role_direction',
  'direction_semantic','source_pool_capacity','target_pool_capacity','pool_n','replacement_fraction',
  'time_signature_group']
 scalar=[m for m in SCALARS if 'A_'+m in e]+['failed','incomplete','nonusable']
 metrics=scalar+[m for m in GEOMETRY if m+'_AB' in e]+['record_time_pct_source_matched']
 all_cells=[];all_images=[];all_buildings=[];all_summary=[]
 for metric in metrics:
  vals=metric_values(e,metric);x=pd.concat([e[meta].reset_index(drop=True),vals.reset_index(drop=True)],axis=1)
  x['metric']=metric
  x['time_source']=x.time_signature_group if metric in ['source_time_total_seconds','recorded_time_total_seconds','record_time_pct_source_matched'] else 'not_time'
  x=x[x.same_abs.notna()].copy()
  if not len(x):continue
  cell=['method','parent_method','condition','scope','layer','direction_axis','role_direction','direction_semantic','n','m','metric','time_source']
  block=x.groupby(cell+['pool_id','image','building','official_difficulty','block_id'],dropna=False)[EFFECTS].mean().reset_index()
  pc=block.groupby(cell+['pool_id','image','building','official_difficulty'],dropna=False)[EFFECTS].mean().reset_index()
  ct=x.groupby(cell+['pool_id'],dropna=False).agg(valid_events=('event_id','nunique'),
    backgrounds=('background_id','nunique'),block_paths=('block_id','nunique'),source_capacity_min=('source_pool_capacity','min'),
    target_capacity_min=('target_pool_capacity','min'),pool_capacity_min=('pool_n','min'),
    events_positive_gap=('gap_symmetric',lambda v:int(v.gt(1e-9).sum())),events_positive_CA=('CA',lambda v:int(v.gt(1e-9).sum())),
    events_positive_CB=('CB',lambda v:int(v.gt(1e-9).sum()))).reset_index()
  pc=pc.merge(ct,on=cell+['pool_id'],validate='one_to_one');all_cells.append(pc)
  im=pc.groupby(cell+['image','building','official_difficulty'],dropna=False)[EFFECTS].mean().reset_index()
  cc=pc.groupby(cell+['image','building','official_difficulty'],dropna=False).agg(pools=('pool_id','nunique'),
    valid_events=('valid_events','sum'),backgrounds=('backgrounds','sum'),block_paths=('block_paths','sum')).reset_index()
  im=im.merge(cc,on=cell+['image','building','official_difficulty'],validate='one_to_one');all_images.append(im)
  bu=im.groupby(cell+['building'],dropna=False)[EFFECTS].mean().reset_index();all_buildings.append(bu)
  for axis,group_cols in [('direction_n_m',cell),('method',cell[:5]+['metric','time_source']),
    ('direction',cell[:5]+['direction_axis','role_direction','direction_semantic','metric','time_source']),
    ('n_m',cell[:5]+['n','m','metric','time_source']),
    ('difficulty',cell[:5]+['official_difficulty','metric','time_source'])]:
   # Within a picture, equally weight available cells; images then buildings.
   ii=im.groupby(group_cols+['image','building'],dropna=False)[EFFECTS].mean().reset_index()
   bb=ii.groupby(group_cols+['building'],dropna=False)[EFFECTS].mean().reset_index()
   avg=bb.groupby(group_cols,dropna=False)[EFFECTS].mean().reset_index()
   ic=ii.groupby(group_cols,dropna=False).agg(images=('image','nunique'),buildings=('building','nunique'),
     images_gap_positive=('gap_symmetric',lambda v:int(v.gt(1e-9).sum())),images_gap_negative=('gap_symmetric',lambda v:int(v.lt(-1e-9).sum())),
     images_CA_positive=('CA',lambda v:int(v.gt(1e-9).sum())),images_CB_positive=('CB',lambda v:int(v.gt(1e-9).sum())),
     images_CB_loss10=('CB',lambda v:int(v.lt(-10).sum()))).reset_index()
   bc=bb.groupby(group_cols,dropna=False).agg(buildings_gap_positive=('gap_symmetric',lambda v:int(v.gt(1e-9).sum())),
    buildings_CA_positive=('CA',lambda v:int(v.gt(1e-9).sum())),buildings_CB_positive=('CB',lambda v:int(v.gt(1e-9).sum()))).reset_index()
   ec=x.groupby(group_cols,dropna=False).agg(valid_events=('event_id','nunique'),backgrounds=('background_id','nunique'),block_paths=('block_id','nunique')).reset_index()
   avg=avg.merge(ic,on=group_cols,validate='one_to_one').merge(bc,on=group_cols,validate='one_to_one').merge(ec,on=group_cols,validate='one_to_one')
   avg['gap_positive_image_fraction']=avg.images_gap_positive/avg.images
   avg['gap_positive_building_fraction']=avg.buildings_gap_positive/avg.buildings
   avg['cross_to_same_ratio']=avg.cross_symmetric_abs/avg.same_abs.where(avg.same_abs.gt(1e-12))
   avg['summary_axis']=axis;all_summary.append(avg)
  print('summarized',metric,flush=True)
 save(O/'CELL_METRICS.csv.gz',pd.concat(all_cells,ignore_index=True))
 save(O/'IMAGE_DIRECTION_N_M_METRICS.csv.gz',pd.concat(all_images,ignore_index=True))
 save(O/'BUILDING_DIRECTION_N_M_METRICS.csv.gz',pd.concat(all_buildings,ignore_index=True))
 s=pd.concat(all_summary,ignore_index=True);save(O/'ALL_FINE_CONDITIONS.csv.gz',s)
 key=s[s.metric.isin(['B8L2','D10','fusion_turn_n','geometry_bev_distance','height_mean_h','record_time_pct_source_matched','failed','nonusable'])]
 save(O/'KEY_FINE_CONDITIONS.csv',key)
 # Actual registered opportunity/capacity, independent of metric availability.
 c=e.groupby(['method','parent_method','condition','scope','layer','direction_axis','role_direction','n','m'],dropna=False).agg(
  events=('event_id','nunique'),pools=('pool_id','nunique'),images=('image','nunique'),buildings=('building','nunique'),
  backgrounds=('background_id','nunique'),block_paths=('block_id','nunique'),source_capacity_min=('source_pool_capacity','min'),
  source_capacity_max=('source_pool_capacity','max'),target_capacity_min=('target_pool_capacity','min'),
  target_capacity_max=('target_pool_capacity','max'),pool_capacity_min=('pool_n','min'),pool_capacity_max=('pool_n','max'),
  replacement_fraction=('replacement_fraction','first'),A_failed=('A_failed','sum'),B_failed=('B_failed','sum'),C_failed=('C_failed','sum'),
  A_nonusable=('A_nonusable','sum'),B_nonusable=('B_nonusable','sum'),C_nonusable=('C_nonusable','sum')).reset_index()
 save(O/'REGISTERED_FINE_CAPACITY_AND_FAILURES.csv',c)
 (O/'SUMMARY_COMPLETE.json').write_text(json.dumps(dict(metrics=len(metrics),condition_rows=len(s),events=len(e),new_fusions=0),indent=2))
 print(json.dumps(dict(metrics=len(metrics),condition_rows=len(s),events=len(e))),flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--stage',choices=['snapshot','summaries','all'],default='all');a=p.parse_args()
 e=snapshot() if a.stage in ['snapshot','all'] else pd.read_csv(O/'FIXED_PARENT_EVENT_METRICS.csv.gz',low_memory=False)
 if a.stage in ['summaries','all']:summaries(e)
