"""Outcome-independent deterministic sample of existing endpoint training cache.

This changes neither endpoint values nor qualification. It is a training cache,
not a claim that all historical or target member sets were enumerated.
"""
from __future__ import annotations
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key]='1'
import argparse,hashlib, json, time
from pathlib import Path
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
WORKERS=HERE.parents[1]
OLD=WORKERS/'personnel_global_composition_20261021'
CONT=OLD/'continuation_20261021'
MAX_PER_POOL_N=256
METRICS=['B8L2','D10','iou_2d','IoU3D100','S_bottom_deg','dir','Hmean','Hcenter',
         'omission','extension','nodes','height_mean_h','geometry_area_h2',
         'ref_node_recall_9','ref_edge_recall_9','diag_wall_coverage_03',
         'top_y_mean_px','bottom_y_mean_px','height_mean_ratio']
FIELDS=['team_key','pool_id','building','image','image_id','condition','layer','difficulty','k',
        'member_workers','score_status','complete_evaluable','source_time_known_n',
        'source_time_total_seconds','time_source_kinds','new_member_n','old_member_n']+METRICS

def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def atomic_csv(d,path):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+'.partial')
    compression={'method':'gzip','mtime':0} if p.name.endswith('.gz') else None
    d.to_csv(tmp,index=False,encoding='utf-8-sig',compression=compression)
    rows=0
    for check in pd.read_csv(tmp,compression='gzip' if compression else None,low_memory=False,chunksize=50000):
        assert check.shape[1]==d.shape[1],(p,check.shape,d.shape)
        rows+=len(check)
    assert rows==len(d),(p,rows,len(d))
    os.replace(tmp,p)

def atomic_json(x,path):
    p=Path(path);tmp=p.with_name(p.name+'.partial')
    tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    json.loads(tmp.read_text());os.replace(tmp,p)

def trim(d):
    # Canonical team-key suffix is an outcome-independent SHA256 member-set hash.
    d=d.sort_values(['pool_id','k','team_key']).drop_duplicates('team_key')
    return d.groupby(['pool_id','k'],sort=False).head(MAX_PER_POOL_N)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--from-consolidated',action='store_true')
    args=parser.parse_args()
    start=time.time()
    files=sorted((OLD/'composition/runtime/scalars').glob('*.csv.gz'))
    use_consolidated=args.from_consolidated or len(files)<229
    if use_consolidated:files=[OLD/'composition/TEAMS_SCALARS.csv.gz']
    files += sorted((CONT/'next_stage/batches').glob('batch_*/ENDPOINT_SCALARS.csv.gz'))
    # Reused n20 rows are already present in phase-one per-pool scalar files.
    pieces=[];ledger=[]
    for path in files:
        recovered=HERE/'recovered_training_input'/path.name
        used=recovered if recovered.exists() else path
        chunks=pd.read_csv(used,usecols=lambda c:c in FIELDS,low_memory=False,chunksize=20000)
        small=[];before=0;eligible=0
        for d in chunks:
            before+=len(d)
            d=d[d.layer.isin(['ordinary_manual','ordinary_semi']) & d.k.ge(10)].copy()
            for c in FIELDS:
                if c not in d:d[c]=np.nan
            eligible+=len(d);small.append(trim(d))
        d=trim(pd.concat(small,ignore_index=True))
        d['training_source']=str(path.relative_to(OLD))
        pieces.append(d)
        ledger.append(dict(path=str(path.relative_to(OLD)),sha256=sha(used),bytes=used.stat().st_size,
                           recovered_copy=str(recovered.relative_to(HERE)) if recovered.exists() else '',
                           source_rows=before,ordinary_n_ge10_rows=eligible,premerge_selected=len(d)))
    result=trim(pd.concat(pieces,ignore_index=True))
    assert not result.team_key.duplicated().any()
    result['failure']=(~result.complete_evaluable.astype(bool)).astype(int)
    timeok=(result.source_time_known_n.eq(result.k)&result.source_time_total_seconds.gt(0)&
            result.time_source_kinds.fillna('').ne('')&
            ~result.time_source_kinds.fillna('').str.contains('|',regex=False))
    result['total_time_compatible']=timeok
    result['log_total_time']=np.log(result.source_time_total_seconds.where(timeok))
    atomic_csv(result,HERE/'TRAINING_ENDPOINTS.csv.gz')
    atomic_csv(pd.DataFrame(ledger),HERE/'TRAINING_SOURCE_INDEX.csv')
    summary=result.groupby(['condition','k'],as_index=False).agg(
        teams=('team_key','size'),pools=('pool_id','nunique'),buildings=('building','nunique'),
        quality_available=('B8L2','count'),time_available=('log_total_time','count'),failures=('failure','sum'))
    atomic_csv(summary,HERE/'TRAINING_COVERAGE.csv')
    atomic_json(dict(source_files=len(files),teams=len(result),pools=result.pool_id.nunique(),
        conditions=sorted(result.condition.unique()),buildings=result.building.nunique(),
        max_per_pool_n=MAX_PER_POOL_N,selection='canonical sorted-member hash, never score',
        endpoint_computation=False,eligibility_changed=False,elapsed_seconds=time.time()-start,
        recovery_source='consolidated first-phase completed export' if use_consolidated else 'per-pool completed export',
        team_key_set_sha256=hashlib.sha256('|'.join(sorted(result.team_key)).encode()).hexdigest(),
        endpoint_sha256=sha(HERE/'TRAINING_ENDPOINTS.csv.gz')),
        HERE/'TRAINING_CACHE_RECEIPT.json')
    print(summary.to_string(index=False),flush=True)
    print('training rows',len(result),'elapsed',round(time.time()-start,2),flush=True)

if __name__=='__main__':main()
