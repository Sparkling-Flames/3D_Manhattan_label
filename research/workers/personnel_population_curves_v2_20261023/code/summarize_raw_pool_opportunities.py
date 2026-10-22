#!/usr/bin/env python3
"""Describe actual pool members' original structures using preserved v2 features."""
from pathlib import Path
import argparse,json
import numpy as np
import pandas as pd
from build_annotations import save_csv


def main(a):
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    pools=pd.read_csv(a.pools)
    source='research/workers/personnel_mixture_comparison_20261022/difficulty/record_opportunity_index.csv.gz'
    r=pd.read_csv(Path(a.repo)/source,low_memory=False)
    prefix=pd.read_csv(a.prefix,usecols=['pool_id','k','pool_n','member_object_ids'],low_memory=False)
    full=prefix[prefix.k.eq(prefix.pool_n)].drop_duplicates('pool_id').set_index('pool_id')
    links=[]
    for p in pools.itertuples():
        ids=full.loc[p.pool_id,'member_object_ids']
        ids=json.loads(ids) if str(ids).startswith('[') else str(ids).split('|')
        assert len(ids)==p.pool_n
        for oid in ids:
            links.append(dict(pool_id=p.pool_id,object_id=oid,pool_reference_id=p.reference_id))
    links=pd.DataFrame(links)
    assert not r.object_id.duplicated().any()
    data=links.merge(r,on='object_id',how='left',validate='one_to_one')
    data['pool_reference_matches_features']=data.pool_reference_id.eq(data.reference_id)
    metrics=['turn_n','short_turn_edges','near_straight_nodes_5deg','log_area','log_height','B8L2','D10',
             'source_active_time_seconds','reference_turn_deficit','reference_turn_excess','reference_reduced',
             'reference_extra','unmatched_ref_9','unmatched_ref_12','bottom_bias_9','abs_bottom_bias_9','omission','extension','log_area_ratio']
    for m in metrics:
        data[m]=pd.to_numeric(data[m],errors='coerce')
        if m.startswith('reference_') or m in ['unmatched_ref_9','unmatched_ref_12','bottom_bias_9','abs_bottom_bias_9','omission','extension','log_area_ratio']:
            data.loc[~data.pool_reference_matches_features,m]=np.nan
    save_csv(data[['pool_id','image_id','image_code','condition','worker_id','object_id','pool_reference_matches_features']+metrics],out/'RAW_POOL_MEMBER_FEATURES.csv.gz')
    all=[]
    for m in metrics:
        z=data.groupby('pool_id')[m].agg(['count','mean','median','std','min','max']).reset_index();z['metric']=m
        all.append(z)
    s=pd.concat(all,ignore_index=True).merge(pools.drop(columns='workers'),on='pool_id',validate='many_to_one')
    save_csv(s,out/'RAW_POOL_FEATURE_SUMMARY.csv')
    (out/'RAW_OPPORTUNITY_RECEIPT.json').write_text(json.dumps({'source':source,'pools':len(pools),'member_links':len(data),'features_available':int(data.object_id.notna().sum()),'reference_matching':int(data.pool_reference_matches_features.sum()),'new_measurements':0,'note':'Historical raw features reaggregated to exact current pool; no quality qualification restored. Reference angular unmatched fraction does not uniquely establish a semantic missing corner.'},ensure_ascii=False,indent=2)+'\n')
    print(len(s),len(data),data.object_id.notna().sum())


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--repo',required=True);p.add_argument('--pools',required=True);p.add_argument('--prefix',required=True);p.add_argument('--out',required=True);main(p.parse_args())
