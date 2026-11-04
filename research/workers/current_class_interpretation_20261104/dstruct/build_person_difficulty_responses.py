#!/usr/bin/env python3
"""Companion to same-image contrasts: hard/easy responses of identical people."""
from pathlib import Path
from itertools import combinations
import gzip
import json
import numpy as np
import pandas as pd

OUT=Path(__file__).resolve().parent
GROUP=['method','condition','scope','source_stratum','metric']

def save(d,name):
    b=d.to_csv(index=False).encode('utf-8-sig')
    if name.endswith('.gz'):b=gzip.compress(b,mtime=0)
    (OUT/name).write_bytes(b)

def main():
    d=pd.read_csv(OUT/'HELDOUT_ORIGINAL_RECORDS.csv.gz',low_memory=False)
    d=d[d.known & d.official_difficulty.isin(['简单','困难'])]
    results=[]
    for metric in ['B8L2','D10','turn_n','short_turn_edges','near_straight_nodes_5deg','unmatched_ref_9','matched_boundary_abs_deg','omission','extension','log_time']:
        z=d[np.isfinite(d[metric])].copy()
        z['metric']=metric;z['value']=z[metric]
        views=[]
        if metric=='log_time':
            z['source_stratum']=z.origin+'|'+z.time_source;views=[z]
        else:
            z['source_stratum']='all_sources';views=[z]
            for origin,g in z.groupby('origin'):
                g=g.copy();g['source_stratum']='origin:'+origin;views.append(g)
        for v in views:
            cols=GROUP+['building','class_id','worker_id','official_difficulty']
            # Targets equal within an image before averaging each person's images.
            pi=v.groupby(cols+['image_id'],dropna=False).value.mean().reset_index()
            pw=pi.groupby(cols,dropna=False).agg(value=('value','mean'),images=('image_id','nunique')).reset_index()
            aa=pw[pw.official_difficulty.eq('简单')].drop(columns='official_difficulty')
            bb=pw[pw.official_difficulty.eq('困难')].drop(columns='official_difficulty')
            c=aa.merge(bb,on=GROUP+['building','class_id','worker_id'],suffixes=('_easy','_hard'),validate='one_to_one')
            c['hard_minus_easy']=c.value_hard-c.value_easy;results.append(c)
    persons=pd.concat(results,ignore_index=True)
    save(persons,'SAME_PERSON_SAME_BUILDING_DIFFICULTY.csv.gz')
    bc=persons.groupby(GROUP+['building','class_id'],dropna=False).agg(
        response=('hard_minus_easy','mean'),workers=('worker_id','nunique')).reset_index()
    bp=[]
    for key,g in bc.groupby(GROUP,dropna=False):
        for a,b in combinations(sorted(g.class_id.unique()),2):
            p=g[g.class_id.eq(a)].merge(g[g.class_id.eq(b)],on=GROUP+['building'],suffixes=('_A','_B'),validate='one_to_one')
            p['class_A']=a;p['class_B']=b;p['response_difference']=p.response_B-p.response_A;bp.append(p)
    bp=pd.concat(bp,ignore_index=True)
    save(bp,'SAME_PERSON_DIFFICULTY_BUILDING_PAIRS.csv.gz')
    summary=bp.groupby(GROUP+['class_A','class_B'],dropna=False).agg(
        buildings=('building','nunique'),building_equal_response_difference=('response_difference','mean'),
        median=('response_difference','median'),p10=('response_difference',lambda s:s.quantile(.1)),
        p90=('response_difference',lambda s:s.quantile(.9)),
        positive_buildings=('response_difference',lambda s:int(s.gt(1e-12).sum())),
        negative_buildings=('response_difference',lambda s:int(s.lt(-1e-12).sum())),
        workers_buildings_A=('workers_A','sum'),workers_buildings_B=('workers_B','sum')).reset_index()
    save(summary,'SAME_PERSON_DIFFICULTY_RESPONSE_SUMMARY.csv')
    out=summary[(summary.method=='TARGET_DSTRUCT_K3')&(summary.condition=='manual')&(summary.scope=='primary')&(summary.source_stratum=='all_sources')&(summary.class_A=='C2')&(summary.class_B=='C3')]
    print(out.to_json(orient='records',force_ascii=False))
    (OUT/'SAME_PERSON_RESPONSE_CONTRACT.json').write_text(json.dumps(dict(
        source='HELDOUT_ORIGINAL_RECORDS.csv.gz',labels='target building excluded',
        unit='same worker within same heldout building has both easy and hard; targets equal within image; images equal per level; people equal in class within building; paired buildings equal',
        distinction='companion to same-image class contrasts; each person may have a different image set. This is not a randomized difficulty intervention.',
        new_fit=False,new_score=False,new_team=False),ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':main()
