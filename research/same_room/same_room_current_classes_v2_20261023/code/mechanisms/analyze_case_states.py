"""Derive transparent per-team, per-node, median and raw-observation case ledgers.

No scoring, point correction or semantic correspondence is introduced. Node links
are within one view and follow shared (object_id,pair_index) observations; they
are an explanatory diagnostic, not cross-camera physical corner adjudication.
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from local_study_paths import WORK,CODE_ROOT,NATIVE,TAXONOMY,MECHANISMS,BUDGET,BUDGET_CASES,BUDGET_FINAL,FIGURES,ENGINE,REPO

from pathlib import Path
import gzip,json,sys
import numpy as np
import pandas as pd

P=MECHANISMS
labels=pd.read_csv(TAXONOMY/'CURRENT_MANUAL_LABELS_LOBO.csv')
metrics=['B8L2','D10','S_bottom_deg','dir','Hmean','Hcenter','iou_2d','IoU3D100',
 'omission','extension','geometry_area_h2','height_mean_h','height_mean_ratio',
 'nodes','fusion_turn_n','fusion_redundancy_n','fusion_short_turn_edges',
 'minimum_support','selected_support_min','identity_groups_n',
 'reference_nodes','ref_node_recall_5','ref_node_recall_9','ref_edge_recall_5',
 'ref_edge_recall_9','recorded_time_eligible','recorded_time_total_seconds',
 'source_time_known_n','source_time_known_sum_seconds','source_time_total_seconds',
 'target_time_known_n','target_time_known_sum_seconds','target_time_total_seconds',
 'source_parallel_active_seconds','target_parallel_active_seconds','time_source_kinds','record_time_by_kind_json',
 'complete_evaluable','geometry_status','score_status','order_status','location_unresolved']

def read(path):
 with gzip.open(path,'rt') as f:return json.load(f)

def obskeys(g):return {(m['id'],m['pair_index']) for m in g['members']}

def analyze(prefix):
 path=P/(prefix+'_EVIDENCE.json.gz')
 if not path.exists():path=P/(prefix+'_REPLAY.json.gz')
 data=read(path)
 endpoints=[];raws=[];groups=[];medians=[];observations=[];links=[];turns=[]
 for row in data:
  t=row['team'];s=t.get('full_state',{});building=t['building']
  base={k:row[k] for k in ['case_id','side','phase','event_explanation_key']}
  base.update({k:t.get(k) for k in ['image','image_id','pool_id','team_key','reference_id','reference_version','repository_commit','building']})
  z=labels[(labels.heldout_building==building)&(labels.method=='V3_BEHAVIOR')].set_index('worker_id')
  j=labels[(labels.heldout_building==building)&(labels.method=='V3_JOINT_QT')].set_index('worker_id')
  c=pd.Series([z.loc[w,'coarse_label'] if w in z.index else 'unknown' for w in t['member_workers']]).value_counts().sort_index()
  e=base|{k:t.get(k) for k in metrics}|dict(n=t['k'],members='|'.join(t['member_workers']),
      class_vector='|'.join(f'{k}:{v}' for k,v in c.items()),
      selected_family=z.selected_family.iloc[0],class_method='V3_BEHAVIOR',
      location_policy=s.get('node_consensus',{}).get('location_policy'))
  endpoints.append(e)
  for r in row['records']:
   rr=base|{k:r.get(k) for k in ['worker_id','object_id','B8L2','D10','origin','source_time_seconds','target_time_seconds','time_source_kind','geometry_status','order_status']}
   rr['class']=z.loc[r['worker_id'],'coarse_label'] if r['worker_id'] in z.index else 'unknown'
   rr['joint_class']=j.loc[r['worker_id'],'coarse_label'] if r['worker_id'] in j.index else 'unknown'
   rr['points_key']=f"{base['case_id']}:{base['side']}:{base['phase']}:records:{r['object_id']}"
   raws.append(rr)
  for g in s.get('identity_groups',[]):
   gb=base|dict(local_feature_key=f"{prefix}:{row['side']}:{row['phase']}:{g['feature_id']}",
      feature_id=g['feature_id'],selected=g['selected'],support=g['support'],minimum_support=s['minimum_support'])
   groups.append(gb|dict(center_x=g['center'][0][0],center_top_y=g['center'][0][1],center_bottom_y=g['center'][1][1],
      workers='|'.join(m['worker'] for m in g['members']),
      observation_keys='|'.join(f"{m['id']}@{m['pair_index']}" for m in g['members'])))
   for m in g['members']:
    observations.append(gb|dict(object_id=m['id'],worker=m['worker'],pair_index=m['pair_index'],
       source_pair_index=m.get('source_pair_index'),x=m['points'][0][0],top_y=m['points'][0][1],bottom_y=m['points'][1][1]))
   for name,i,k in [('x',0,0),('top_y',0,1),('bottom_y',1,1)]:
    vals=sorted([(m['points'][i][k],m['worker'],m['id'],m['pair_index']) for m in g['members']])
    n=len(vals); low=vals[(n-1)//2];high=vals[n//2]
    medians.append(gb|dict(coordinate=name,median=(low[0]+high[0])/2,
       lower_worker=low[1],lower_value=low[0],upper_worker=high[1],upper_value=high[0],
       lower_object_id=low[2],upper_object_id=high[2],lower_pair_index=low[3],upper_pair_index=high[3],
       sorted_workers='|'.join(v[1] for v in vals),sorted_values=json.dumps([v[0] for v in vals])))
  geo=t['geometry'];p=np.array(geo['footprint']);edges=np.roll(p,-1,axis=0)-p;length=np.linalg.norm(edges,axis=1)
  ang=np.degrees(np.arccos(np.clip((np.roll(edges,1,axis=0)*edges).sum(1)/(np.roll(length,1)*length),-1,1)))
  for idx,(fid,point,angle,edge) in enumerate(zip(geo['feature_ids'],p,ang,length)):
   turns.append(base|dict(node_index=idx,feature_id=fid,x_h=point[0],z_h=point[1],turn_angle_deg=angle,
      is_effective_turn=bool(angle>5),next_edge_h=edge,next_edge_fraction=edge/sum(length)))
 for side in ['a','b']:
  pair={r['phase']:r for r in data if r['side']==side}
  a,b=[pair[p]['team'].get('full_state',{}).get('identity_groups',[]) for p in ['before','after']]
  for g in a:
   for h in b:
    common=obskeys(g)&obskeys(h)
    if not common:continue
    links.append(dict(case_id=prefix,side=side,image=pair['before']['team']['image'],
        before_feature=g['feature_id'],after_feature=h['feature_id'],
        before_x=g['center'][0][0],after_x=h['center'][0][0],
        before_support=g['support'],after_support=h['support'],
        before_selected=g['selected'],after_selected=h['selected'],shared_observation_n=len(common),
        shared_observations='|'.join(f'{k}@{i}' for k,i in sorted(common)),
        before_members='|'.join(m['worker'] for m in g['members']),
        after_members='|'.join(m['worker'] for m in h['members'])))
 for suffix,rows in [('ENDPOINTS',endpoints),('RAW_PEOPLE',raws),('LOCAL_GROUPS',groups),
      ('COORDINATE_MEDIANS',medians),('VOTE_OBSERVATIONS',observations),('WITHIN_VIEW_GROUP_LINKS',links),('NODE_TURNS',turns)]:
  target=P/(prefix+'_'+suffix+'.csv')
  if rows:pd.DataFrame(rows).to_csv(target,index=False)
  elif target.exists():target.unlink()
 print(prefix, 'endpoints',len(endpoints),'vote observations',len(observations))

if __name__=='__main__':
 for prefix in sys.argv[1:]:analyze(prefix)
