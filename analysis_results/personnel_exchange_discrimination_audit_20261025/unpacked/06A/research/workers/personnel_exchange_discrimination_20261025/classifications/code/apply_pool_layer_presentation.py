#!/usr/bin/env python3
"""Correct pool-layer presentation only; never refit frozen personnel labels."""
import argparse,gzip,json
from pathlib import Path
import pandas as pd
from build_condition_response_classes import save_csv,save_json,sha
from describe_candidate_support import summarize_result

def main(a):
 p=Path(a.classifications);f=Path(a.features);inp=Path(a.inputs)
 labelpaths=sorted(p.glob('*LABELS*.csv*'));before={str(x):sha(x) for x in labelpaths}
 snapshot=json.load(gzip.open(inp/'INPUT_SNAPSHOT.json.gz','rt'))
 rows=[]
 for pool in snapshot['images']:
  m=pool['meta'];rows.append(dict(pool_id=pool['pool_id'],pool_layer=m['layer'],image=m['image'],image_id=m['image_id'],condition=m['condition'],building=m['building'],records=len(pool['records']),workers=len({r['worker_id'] for r in pool['records']})))
 pools=pd.DataFrame(rows);save_csv(pools,p/'POOL_LAYER_INVENTORY.csv')
 link=pools[['pool_id','pool_layer']]
 for path in [f/'RAW_CONDITION_RESPONSE_RECORDS.csv.gz',f/'RAW_ORIGINAL_PAIR_DISTANCES.csv.gz',p/'HELDOUT_RAW_DISTANCE_BY_IMAGE.csv.gz']:
  d=pd.read_csv(path);d=d.drop(columns=['pool_layer'],errors='ignore').merge(link,on='pool_id',how='left',validate='many_to_one');assert d.pool_layer.notna().all();save_csv(d,path)
 raw=pd.read_csv(f/'RAW_CONDITION_RESPONSE_RECORDS.csv.gz')
 support=raw[raw.history_eligible].groupby(['pool_id','image_code','condition','pool_layer','difficulty_coarse','building']).agg(records=('object_id','size'),workers=('worker_id','nunique')).reset_index()
 save_csv(support,p/'CLASSIFICATION_HISTORY_POOL_SUPPORT.csv')
 special=support[support.pool_layer.str.startswith('special_')];save_csv(special,p/'SPECIAL_RANGE_HISTORY_SUPPORT.csv')
 result=pd.read_csv(p/'HELDOUT_RAW_DISTANCE_BY_IMAGE.csv.gz');summary=summarize_result(result);save_csv(summary,p/'HELDOUT_RAW_DISTANCE_SUMMARY.csv')
 focus=summary[summary.pool_layer.eq('ordinary_manual')&summary.difficulty.eq('困难')&summary.method.isin(['DSTRUCT_K2','DJOINT_K2','MSDGEOM_SCOPE_K2'])]
 save_csv(focus,p/'ORDINARY_DIFFICULT_RAW_FOCUS.csv')
 for name in ['BUILD_RECEIPT.json','LATEST_STAGE_RECEIPT.json','CAPACITY_RAW_USE_RECEIPT.json']:
  path=p/name
  if not path.exists():continue
  receipt=json.loads(path.read_text())
  receipt['history_scope_clarification']='Frozen labels use non-doorway fixed-reference history with known easy/medium/hard grade; includes declared auxiliary special-range history e9zR4mvMWw7-16 and jtcxE69GiFV-18. No relabeling was performed.'
  receipt['history_records_by_pool_layer']=raw[raw.history_eligible].groupby('pool_layer').size().to_dict()
  receipt['special_range_history_support']=special.to_dict('records')
  if 'class_history' in receipt:receipt['class_history']=receipt['history_scope_clarification']
  if 'support_rules' in receipt:receipt['support_rules']['manual_geometry']='>=12 non-doorway fixed-reference images/3 buildings, >=5 easy images/2 buildings, >=4 hard images/2 buildings; declared special-range history retained'
  if 'raw_test_scope' in receipt:receipt['raw_test_scope']='Snapshot pool_layer separates ordinary_manual, special_manual, doorway_manual, ordinary_semi, special_semi; non_doorway alone does not mean ordinary.'
  save_json(receipt,path)
 after={str(x):sha(x) for x in labelpaths};assert before==after
 save_json(dict(action='Presentation-only pool-layer correction and raw-result regrouping',labels_unchanged=True,label_sha256=after,new_fusion=0,new_classification=0,
   historical_records=int(raw.history_eligible.sum()),special_range_records=int(special.records.sum()),
   effect_main_scope='ordinary_manual; special_manual separately reported',
   note='This supersedes non_doorway-as-ordinary wording, not the frozen historical classification.'),p/'POOL_LAYER_CORRECTION_RECEIPT.json')
 print(special.to_string(index=False))
 print(focus[focus.metric.isin(['turn_difference','top_difference_deg','bottom_difference_deg'])][['method','subset','metric','images','image_within','image_cross','images_cross_larger','buildings','buildings_cross_larger']].to_string(index=False))

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--classifications',required=True);ap.add_argument('--features',required=True);ap.add_argument('--inputs',required=True);main(ap.parse_args())
