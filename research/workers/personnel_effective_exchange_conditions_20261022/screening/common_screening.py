"""Shared read-only access to prior completed experiments; base data are v2.

The directory named v3 records a research round, not a new data version.
All writes from this module are restricted to this round's screening directory.
"""
from __future__ import annotations
import os
for _name in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS',
              'NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS']:
    os.environ[_name]='1'
import collections, csv, gzip, hashlib, io, json, math
from pathlib import Path
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
WORKERS=HERE.parents[1]
PRIOR=WORKERS/'personnel_useful_taxonomy_v3_20261021'
COMPOSITION=PRIOR/'composition'
TAXONOMY=PRIOR/'taxonomy'
EXPECTED={'PANEL':65371,'LARGE':16244,'PURE':1899,'PURE_CROSS':2056}

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for data in iter(lambda:f.read(1024*1024),b''):h.update(data)
    return h.hexdigest()

def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,
        separators=(',',':'),default=str).encode()).hexdigest()

def save_json(name,value):
    p=HERE/name;p.parent.mkdir(parents=True,exist_ok=True)
    t=p.with_name(p.name+'.tmp')
    with t.open('w',encoding='utf-8') as f:
        json.dump(value,f,ensure_ascii=False,sort_keys=True,indent=2,default=str)
        f.flush();os.fsync(f.fileno())
    t.replace(p)

def save_csv(name,table):
    p=HERE/name;p.parent.mkdir(parents=True,exist_ok=True)
    t=p.with_name(p.name+'.tmp')
    payload=table.to_csv(index=False).encode('utf-8-sig')
    if p.suffix=='.gz':payload=gzip.compress(payload,compresslevel=5,mtime=0)
    with t.open('wb') as f:f.write(payload);f.flush();os.fsync(f.fileno())
    opener=gzip.open if p.suffix=='.gz' else open
    with opener(t,'rt',encoding='utf-8-sig',newline='') as f:
        rows=csv.reader(f);head=next(rows);n=0
        for row in rows:
            assert len(row)==len(head),(name,n,len(row),len(head));n+=1
    assert n==len(table),(name,n,len(table))
    t.replace(p)
    return dict(path=name,rows=n,columns=len(head),bytes=p.stat().st_size,sha256=sha(p),EOF_verified=True)

def workers(value):
    if pd.isna(value) or not str(value):return []
    return sorted(set(str(value).split('|')))

def canonical_counts(values):
    if not isinstance(values,dict):values=collections.Counter(values)
    return '|'.join(f'{k}:{int(v)}' for k,v in sorted(values.items()) if v)

def parse_counts(value):
    if pd.isna(value) or not str(value):return {}
    return {part.rsplit(':',1)[0]:int(part.rsplit(':',1)[1]) for part in str(value).split('|')}

def label_maps():
    d=pd.read_csv(COMPOSITION/'delivery/FROZEN_EVALUATION_LABELS.csv.gz')
    maps={}
    for key,g in d.groupby(['method_id','tier','condition','heldout_building']):
        maps[key]={r.worker_id:r.class_id for r in g.itertuples()}
    return maps,d

def pool_workers():
    d=pd.read_csv(COMPOSITION/'PANELS.csv')
    pools={r.pool_id:workers(r.domain_workers) for r in d[d.source_domain.eq('all_formal')].itertuples()}
    hist=pd.read_csv(TAXONOMY/'ALL_METHOD_LABELS_LOBO.csv.gz',usecols=['worker_id','origin'])
    origin=hist.drop_duplicates('worker_id').set_index('worker_id').origin.to_dict()
    return pools,origin

def event_sources(stages=None,conditions=None):
    for stage in stages or EXPECTED:
        for condition in conditions or ['manual','semi']:
            yield stage,condition,COMPOSITION/'matched'/f'{stage}_{condition.upper()}_COMPLETE_EVENTS.csv.gz'

META=['pool_id','image','building','condition','layer','difficulty','method_id','tier',
 'panel_id','source_domain','original_source_domain','anchor_id','design_scope','event_mode',
 'n','m_AB','m_AC','m_BC','event_id','physical_triple_id','oriented_triple_id','physical_pair_id',
 'team_A','team_B','team_C','A_member_workers','B_member_workers','C_member_workers',
 'common_background','outgoing_block_X','same_count_block_Y','changed_count_block_Z',
 'A_counts','B_counts','C_counts','A_parent_counts','B_parent_counts','C_parent_counts',
 'composition_turnover_AC','within_parent_fine_change','direction_source_class','direction_target_class',
 'labelled_domain_workers','unknown_domain_workers','known_domain_n','class_seat_transfer',
 'fold_selected_family','fold_coarse_k','fold_fine_k','same_source_counts','source_and_historyQ5_matched',
 'all_complete','all_scored','A_failure','B_failure','C_failure','A_score_status','B_score_status','C_score_status',
 'recorded_time_single_source','recorded_time_comparable','same_time_comparable','cross_time_comparable',
 'endpoint_A__minimum_support','endpoint_B__minimum_support','endpoint_C__minimum_support',
 'endpoint_A__time_source_kinds','endpoint_B__time_source_kinds','endpoint_C__time_source_kinds',
 'endpoint_A__source_time_known_n','endpoint_B__source_time_known_n','endpoint_C__source_time_known_n']

CORE=['A_B8L2','B_B8L2','C_B8L2','A_D10','B_D10','C_D10',
 'common_quality_within_abs','common_quality_cross_abs','abs_Q_change_advantage',
 'stable_advantage','stable_D10_advantage','within_joint_stable_main','cross_joint_stable_main',
 'same_B8L2','cross_B8L2','net_B8L2','same_D10','cross_D10',
 'same_loss_gt10','cross_loss_gt10','same_recorded_time_pct','cross_recorded_time_pct','recorded_time_pct',
 'same_abs_log_time','cross_abs_log_time','time_variation_advantage',
 'cross_turn_history_change','cross_short_history_change','cross_redundancy_history_change',
 'cross_area_history_change','cross_height_history_change','cross_history_block_Q_change',
 'X_history_q_effect','Y_history_q_effect','Z_history_q_effect']

