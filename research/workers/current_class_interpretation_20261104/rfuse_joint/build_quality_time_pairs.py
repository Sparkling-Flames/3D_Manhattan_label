#!/usr/bin/env python3
"""Q/T contrasts on exactly the same timed records and source strata."""
from itertools import combinations
import json
import hashlib
import numpy as np
import pandas as pd
from build_profiles import ROOT, OUT, BASE, CUR, save

def main():
    source=ROOT/CUR/'classification/RAW_TARGET_RESPONSE_RECORDS.csv.gz'
    label_source=BASE/'WORKER_LABELS_ALL_LOBO.csv.gz'
    raw=pd.read_csv(source,low_memory=False)
    raw=raw[raw.layer.isin(['ordinary_manual','ordinary_semi'])].copy()
    raw['record_time_seconds']=raw.source_active_time_seconds.where(raw.source_active_time_seconds.gt(0))
    raw['record_log_time']=np.log(raw.record_time_seconds)
    labels=pd.read_csv(label_source,low_memory=False)
    labels=labels[labels.heldout_building.ne('ALL')]
    d=raw.merge(labels[['method','worker_id','heldout_building','class_id','known']],left_on=['worker_id','building'],right_on=['worker_id','heldout_building'],validate='many_to_many')
    assert len(d)==len(raw)*5
    d=d[d.known & np.isfinite(d.B8L2) & np.isfinite(d.record_time_seconds) & np.isfinite(d.record_log_time)].copy()
    d['source_stratum']=d.origin.astype(str)+'|'+d.time_source.astype(str)
    base=['method','condition','scope','source_stratum']
    meta=['pool_id','image','image_id','building','reference_id','reference_version','official_difficulty']
    w=d.groupby(base+meta+['class_id','worker_id'],dropna=False)[['B8L2','record_time_seconds','record_log_time']].mean().reset_index()
    t=w.groupby(base+meta+['class_id'],dropna=False).agg(Q=('B8L2','mean'),T_seconds=('record_time_seconds','mean'),T_log=('record_log_time','mean'),workers=('worker_id','nunique')).reset_index()
    pairs=[]
    for key,g in t.groupby(base,dropna=False):
        for ca,cb in combinations(sorted(g.class_id.unique()),2):
            p=g[g.class_id.eq(ca)].merge(g[g.class_id.eq(cb)],on=base+meta,suffixes=('_A','_B'),validate='one_to_one')
            p['class_A']=ca;p['class_B']=cb
            for v in ['Q','T_seconds','T_log']:p['delta_'+v]=p[v+'_B']-p[v+'_A']
            pairs.append(p)
    p=pd.concat(pairs,ignore_index=True)
    save(p,'Q_T_COMMON_RECORDS_TARGET_PAIRS.csv.gz')
    keys=base+['class_A','class_B']
    metrics=['Q_A','Q_B','T_seconds_A','T_seconds_B','T_log_A','T_log_B','delta_Q','delta_T_seconds','delta_T_log']
    im=p.groupby(keys+['building','image','image_id','official_difficulty'],dropna=False)[metrics].mean().reset_index()
    save(im,'Q_T_COMMON_RECORDS_IMAGE_PAIRS.csv.gz')
    result=[]
    for difficulty in ['ALL','简单','中等','困难']:
        s=im if difficulty=='ALL' else im[im.official_difficulty.eq(difficulty)]
        for key,g in s.groupby(keys,dropna=False):
            row=dict(zip(keys,key));row.update(difficulty=difficulty,n_images=g.image_id.nunique(),n_buildings=g.building.nunique())
            for m in metrics:
                row['image_equal_'+m]=float(g[m].mean())
                row['building_equal_'+m]=float(g.groupby('building')[m].mean().mean())
            row['image_equal_geometric_time_ratio']=float(np.exp(g.delta_T_log.mean()))
            row['building_equal_geometric_time_ratio']=float(np.exp(g.groupby('building').delta_T_log.mean().mean()))
            row['Q_positive_images']=int(g.delta_Q.gt(0).sum())
            row['T_positive_images']=int(g.delta_T_log.gt(0).sum())
            row['Q_positive_T_nonpositive_images']=int((g.delta_Q.gt(0)&g.delta_T_log.le(0)).sum())
            row['Q_positive_T_positive_images']=int((g.delta_Q.gt(0)&g.delta_T_log.gt(0)).sum())
            row['delta_Q_p10']=float(g.delta_Q.quantile(.1));row['delta_Q_p90']=float(g.delta_Q.quantile(.9))
            row['delta_logT_p10']=float(g.delta_T_log.quantile(.1));row['delta_logT_p90']=float(g.delta_T_log.quantile(.9))
            result.append(row)
    s=pd.DataFrame(result)
    save(s,'Q_T_COMMON_RECORDS_PAIR_SUMMARY.csv')
    b=source.read_bytes()
    (OUT/'Q_T_COMMON_RECORDS_CHECKS.json').write_text(json.dumps(dict(source_path=str(source.relative_to(ROOT)),source_sha256=hashlib.sha256(b).hexdigest(),label_source=str(label_source.relative_to(ROOT)),label_sha256=hashlib.sha256(label_source.read_bytes()).hexdigest(),methods=sorted(d.method.unique()),same_records_for_Q_and_T=True,source_strata_separate=True,source_records=len(d),target_pair_rows=len(p),image_pair_rows=len(im),summary_rows=len(s),new_experiments=0),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(s[(s.condition.eq('manual'))&(s.scope.eq('primary'))&(s.difficulty.eq('ALL'))][['method','source_stratum','class_A','class_B','n_images','image_equal_delta_Q','building_equal_delta_Q','image_equal_geometric_time_ratio','building_equal_geometric_time_ratio']].to_string(index=False))

if __name__=='__main__':main()
