#!/usr/bin/env python3
"""Exact real natural-prefix fusion training support; no category-priority data."""
from pathlib import Path
import argparse,gzip,json,zipfile,hashlib,os
import numpy as np
import pandas as pd

NS=[10,12,14,16,20,24]
GEOM=['floor_turn5_n','floor_short_edge_03_n','floor_redundant5_n','bottom_y_mean_px','top_y_mean_px','log_floor_area','log_height_mean']
QUALITY=['B8L2','D10','iou2d100','IoU3D100','boundary_loss','direction_loss','height_loss']
def save_csv(d,p):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);data=d.to_csv(index=False).encode('utf-8-sig')
 if str(p).endswith('.gz'):data=gzip.compress(data,compresslevel=5,mtime=0)
 t=p.with_name(p.name+'.partial');t.write_bytes(data);os.replace(t,p)
def save_json(d,p):
 p=Path(p);t=p.with_name(p.name+'.partial');t.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');os.replace(t,p)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main(a):
 pop=Path(a.population);out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
 orders=pd.read_csv(pop/'design/EXACT_ORDER_DESIGN.csv.gz');orders=orders[orders.policy.eq('natural_random')&orders.layer.eq('ordinary_manual')&orders.condition.eq('manual')]
 keep=['pool_id','path_id','base_path_id','replicate','policy','k','team_key','order_kind','generation','sample_kind']
 with zipfile.ZipFile(a.links_zip) as z:
  links=pd.read_csv(gzip.GzipFile(fileobj=z.open('results/PREFIX_TEAM_LINKS.csv.gz')),usecols=keep)
 links=links[links.policy.eq('natural_random')&links.path_id.isin(orders.path_id)&links.k.isin(NS)].copy()
 assert links.path_id.isin(orders.path_id).all() and links.policy.eq('natural_random').all()
 save_csv(links,out/'NATURAL_TRAINING_PATH_TEAM_LINKS.csv.gz')
 wanted=['team_key','team_id','pool_id','building','image','image_id','condition','layer','difficulty','k','pool_n',
  'member_workers','member_object_ids','score_available','score_status','complete_evaluable','geometry_status','endpoint_origin',
  'floor_turn5_n','floor_short_edge_03_n','floor_redundant5_n','bottom_y_mean_px','top_y_mean_px',
  'floor_area_camera_h2','height_mean_h','B8L2','D10','iou2d100','IoU3D100','boundary_loss','direction_loss','height_loss',
  'minimum_support','reference_nodes','ref_node_recall_9','ref_edge_recall_9','source_time_total_seconds']
 endpoints=pd.read_csv(pop/'results/ENDPOINT_SCALARS.csv.gz',usecols=wanted,low_memory=False)
 count=links.groupby('team_key').agg(path_occurrences=('path_id','size'),natural_path_n=('path_id','nunique')).reset_index()
 d=count.merge(endpoints,on='team_key',how='left',validate='one_to_one')
 assert d.pool_id.notna().all();assert d.condition.eq('manual').all();assert d.layer.eq('ordinary_manual').all()
 d['log_floor_area']=np.log(d.floor_area_camera_h2.where(d.floor_area_camera_h2>0));d['log_height_mean']=np.log(d.height_mean_h.where(d.height_mean_h>0))
 d['fusion_failure']=~d.score_available.fillna(False).astype(bool)
 d['complete_model_outputs']=d[GEOM+QUALITY].notna().all(axis=1)
 d['group_id']=d.pool_id+'__n'+d.k.astype(str)
 n=d.groupby('group_id').team_key.transform('nunique');d['group_unique_teams']=n
 d['training_eligible']=d.complete_model_outputs & n.ge(4)
 # Endpoint is stored once; path multiplicity remains an explicit sample weight.
 d['raw_mc_weight']=d.path_occurrences
 save_csv(d,out/'NATURAL_TRAINING_ENDPOINTS.csv.gz')
 save_csv(orders[['pool_id','path_id','building','image','image_id','difficulty','pool_n','worker_order','generation','seed','sampling_weight']],out/'NATURAL_ORDER_INVENTORY.csv.gz')
 coverage=d.groupby(['building','difficulty','k'],dropna=False).agg(unique_teams=('team_key','nunique'),images=('image_id','nunique'),path_occurrences=('path_occurrences','sum'),eligible_teams=('training_eligible','sum'),failures=('fusion_failure','sum')).reset_index();save_csv(coverage,out/'TRAINING_COVERAGE_BY_BUILDING_N.csv')
 allworkers=[]
 for r in d.itertuples():
  for w in str(r.member_workers).split('|'):
   allworkers.append(dict(worker_id=w,building=r.building,image_id=r.image_id,difficulty=r.difficulty,k=r.k,team_key=r.team_key,eligible=r.training_eligible))
 m=pd.DataFrame(allworkers);save_csv(m,out/'TRAINING_TEAM_MEMBER_LINKS.csv.gz')
 ws=m[m.eligible].groupby('worker_id').agg(images=('image_id','nunique'),buildings=('building','nunique'),teams=('team_key','nunique')).reset_index();save_csv(ws,out/'WORKER_TRAINING_SUPPORT_ALL.csv')
 receipt=dict(actual_commit='972857b2b3f548316be215400e42d6ef6e639250',underlying_data_version='v2',
  sampling_policy='natural_random only; category-priority orders excluded',pool_layer='ordinary_manual',team_sizes=NS,
  natural_orders=len(orders),registered_links=len(links),unique_endpoints=len(d),eligible_endpoints=int(d.training_eligible.sum()),
  images=d.image_id.nunique(),buildings=d.building.nunique(),workers=len(ws),
  failures=int(d.fusion_failure.sum()),finite_by_output={c:int(d[c].notna().sum()) for c in GEOM+QUALITY},
  distinct_team_rule='Each deterministic member endpoint stored once; original natural-order multiplicity retained as explicit MC weight.',
  no_new_fusion=True,source_files={str(pop/'design/EXACT_ORDER_DESIGN.csv.gz'):sha(pop/'design/EXACT_ORDER_DESIGN.csv.gz'),str(pop/'results/ENDPOINT_SCALARS.csv.gz'):sha(pop/'results/ENDPOINT_SCALARS.csv.gz'),str(a.links_zip):sha(a.links_zip)},
  geometry_outputs=GEOM,quality_outputs=QUALITY)
 save_json(receipt,out/'TRAINING_INPUT_RECEIPT.json');print(json.dumps({k:v for k,v in receipt.items() if k not in ['source_files','finite_by_output']},ensure_ascii=False,indent=2));print(ws.to_string(index=False))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--population',required=True);p.add_argument('--links-zip',required=True);p.add_argument('--output',required=True);main(p.parse_args())
