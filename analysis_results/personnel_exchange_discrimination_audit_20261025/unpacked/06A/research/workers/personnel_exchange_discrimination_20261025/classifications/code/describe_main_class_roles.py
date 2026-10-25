#!/usr/bin/env python3
"""Readable ALL members and easy/hard raw+peer centers for main candidates."""
import argparse,json
from pathlib import Path
import numpy as np
import pandas as pd
from build_condition_response_classes import save_csv,save_json,sha

METRICS=['turn_n','short_turn_edges','near_straight_nodes_5deg',
 'matched_top_bias_deg','matched_bottom_bias_deg','log_area_ratio','log_height',
 'B8L2','D10','log_time','source_active_time_seconds']

def main(a):
 p=Path(a.classifications);fp=Path(a.features)
 raw=pd.read_csv(fp/'RAW_CONDITION_RESPONSE_RECORDS.csv.gz')
 labels=pd.read_csv(p/'CANDIDATE_LABELS_COMPLETE_ALL_LOBO.csv.gz')
 hist=pd.read_csv(fp/'HISTORY_FEATURES_WITH_SCOPE_ALL_LOBO.csv.gz')
 labs=labels[labels.heldout_building.eq('ALL') & labels.method.isin(['DSTRUCT_K2','DJOINT_K2'])]
 save_csv(labs.merge(hist[hist.heldout_building.eq('ALL')].drop(columns=['origin']),on=['worker_id','heldout_building'],validate='many_to_one'),p/'MAIN_CANDIDATE_PERSON_HISTORY_ALL.csv.gz')
 out=[];people=[]
 d=raw[raw.condition.eq('manual')&raw.history_eligible]
 for (method,cl),l in labs[labs.known].groupby(['method','class_id']):
  workers=set(l.worker_id);dd=d[d.worker_id.isin(workers)]
  role=('常规结构响应' if cl=='C1' else '困难图较多转折响应') if method=='DSTRUCT_K2' else ('困难图相对常规质量—结构角色' if cl=='C1' else '困难图较高质量—较多转折角色')
  people.append(dict(method=method,class_id=cl,role=role,people=len(workers),members='|'.join(sorted(workers)),new_people=int(l.origin.eq('new').sum()),old_people=int(l.origin.eq('v1').sum()),label_stage='ALL_descriptive_only'))
  for level in ['ALL','简单','中等','困难']:
   z=dd if level=='ALL' else dd[dd.difficulty_coarse.eq(level)]
   for metric in METRICS:
    for kind in ['raw','peer']:
     col=metric if kind=='raw' else metric+'_peer'
     if col not in z:continue
     zz=z[z[col].notna()]
     if not len(zz):continue
     v=zz.groupby(['worker_id','building'])[col].mean().groupby('worker_id').mean()
     out.append(dict(method=method,class_id=cl,role=role,difficulty=level,metric=metric,kind=kind,
       mean=float(v.mean()),between_worker_sd=float(v.std()),worker_p20=float(v.quantile(.2)),worker_p80=float(v.quantile(.8)),
       workers=len(v),records=len(zz),images=zz.image_id.nunique(),buildings=zz.building.nunique(),
       aggregation='equal building per worker; equal worker per class',
       note='source record seconds, not newly measured production time' if metric in ['source_active_time_seconds','log_time'] else ''))
 centers=pd.DataFrame(out);save_csv(centers,p/'MAIN_CANDIDATE_EASY_HARD_CENTERS_ALL.csv');save_csv(pd.DataFrame(people),p/'MAIN_CANDIDATE_PEOPLE_AND_ROLE_ALL.csv')
 # Source-separated time means keep the originating measurement context visible.
 time=[]
 for (method,cl),l in labs[labs.known].groupby(['method','class_id']):
  z=d[d.worker_id.isin(l.worker_id)&d.source_active_time_seconds.notna()]
  for (origin,source,level),g in z.groupby(['origin','time_source','difficulty_coarse']):
   v=g.groupby(['worker_id','building']).source_active_time_seconds.mean().groupby('worker_id').mean()
   time.append(dict(method=method,class_id=cl,origin=origin,time_source=source,difficulty=level,workers=len(v),records=len(g),mean_seconds=float(v.mean()),note='inventory recorded active seconds; equal building/worker aggregation'))
 save_csv(pd.DataFrame(time),p/'MAIN_CANDIDATE_TIME_BY_SOURCE_ALL.csv')
 receipt=dict(stage='complete_20_candidate_feature_discovery',underlying_data_version='v2',
   input_commit='972857b2b3f548316be215400e42d6ef6e639250',methods=labels.method.nunique(),folds=labels.heldout_building.nunique(),
   label_rows=len(labels),scope_included=True,scope_workers_available=62,
   historical_stage_receipt='BUILD_RECEIPT.json is the initial 12-method stage, when scope was not yet incorporated. Its old-worker-only scope note was a provisional assumption superseded by the full-v2 scope recovery.',
   scope_source='../features_scope/SCOPE_FEATURES_ALL_LOBO.csv.gz',scope_recovery='286 historical oos strings restored from exact old questionnaire to features only; no GT/qualification change.',
   labels_selected_on_target_fusion=False,raw_pair_validation='Held-out original answers; not a fusion replacement outcome.',
   effects='Manual and Semi must be evaluated separately even for joint-input labels.',
   reproducible_scripts=['build_condition_response_classes.py','build_axis_controls.py','build_scope_increment.py','describe_candidate_support.py','assemble_classification_links.py','describe_main_class_roles.py'],
   all_descriptive_vs_lobo='ALL centers describe population, target use must join heldout_building.',
   status='Candidate discovery complete; main fusion experiment is in the parent experiment outputs.',
   history_scope_clarification='Non-doorway fixed-reference history includes e9zR4mvMWw7-16 and jtcxE69GiFV-18 as declared auxiliary special-range history. Ordinary effects use snapshot pool_layer=ordinary_manual.',
   history_records_by_pool_layer=raw[raw.history_eligible].groupby('pool_layer').size().to_dict() if 'pool_layer' in raw else {},
   special_range_history_support_file='SPECIAL_RANGE_HISTORY_SUPPORT.csv')
 save_json(receipt,p/'LATEST_STAGE_RECEIPT.json')
 manifest=[]
 for path in sorted(list(p.rglob('*'))+list(fp.rglob('*'))):
  if not path.is_file() or path.name=='FILE_MANIFEST.csv' or '__pycache__' in str(path) or path.name.endswith('_LOG.txt') or path.suffix=='.log':continue
  manifest.append(dict(path=str(path),bytes=path.stat().st_size,sha256=sha(path)))
 save_csv(pd.DataFrame(manifest),p/'FILE_MANIFEST.csv')
 print(pd.DataFrame(people).to_string(index=False));print('Saved role centers',len(centers))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--classifications',required=True);p.add_argument('--features',required=True);main(p.parse_args())
