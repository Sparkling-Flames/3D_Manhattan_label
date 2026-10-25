#!/usr/bin/env python3
"""Paired m7/m6 and complete 7-choose-6 target-panel member sensitivity.

Adding the seventh target member means exchanging the fixed source member for
that target member at n=10; it is never an increase in total team size.
"""
from __future__ import annotations
import argparse
import gzip
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd
from summarize_exchange import write_csv

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from measure_events import METRICS,geometry_metrics


def truth(s):
    return s.astype(str).str.lower().map({'true':1.,'false':0.,'1':1.,'0':0.,'1.0':1.,'0.0':0.})


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--m6-metrics',type=Path,required=True)
    ap.add_argument('--m7-metrics',type=Path,nargs='+',required=True)
    ap.add_argument('--native-dir',type=Path);ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=True)
    six=pd.read_csv(args.m6_metrics,low_memory=False)
    assert not six.event_id.duplicated().any()
    assert six.groupby('anchor_id').Z_omitted_worker.nunique().eq(7).all()
    seven=pd.concat([pd.read_csv(p,low_memory=False) for p in args.m7_metrics],ignore_index=True)
    seven=seven.drop_duplicates('event_id',keep='last').set_index('event_id')
    assert set(six.paired_m7_event_id)<=set(seven.index),'Parent m7 metrics missing; do not silently score them as failures.'
    parent=seven.reindex(six.paired_m7_event_id);parent.index=six.index
    assert six.A_team_key.eq(parent.A_team_key).all(),'Original A must remain exactly fixed.'
    assert six.B7_team_key.eq(parent.B_team_key).all() and six.C7_team_key.eq(parent.C_team_key).all()
    added={}
    stats=[]
    for metric in METRICS:
        cols=['B_'+metric,'C_'+metric]
        if not all(c in six and c in parent for c in cols):continue
        for arm in ['B','C']:
            c=arm+'_'+metric
            p=pd.to_numeric(parent[c],errors='coerce');s=pd.to_numeric(six[c],errors='coerce')
            added[arm+'7_'+metric]=p
            name=metric+'_'+arm+'7_minus_'+arm+'6';added[name]=p-s;stats.append(name)
        name=metric+'_net_m7_minus_m6'
        added[name]=added[metric+'_C7_minus_C6']-added[metric+'_B7_minus_B6'];stats.append(name)
        added[metric+'_parent_CB']=added['C7_'+metric]-added['B7_'+metric]
        for contrast in ['within','cross','gap','CA','CB']:
            c=metric+'_'+contrast
            if c in parent and c in six:
                name=metric+'_'+contrast+'_m7_minus_m6'
                added[name]=pd.to_numeric(parent[c],errors='coerce')-pd.to_numeric(six[c],errors='coerce');stats.append(name)
    for arm in ['B','C']:
        p=truth(parent[arm+'_failed']);s=truth(six[arm+'_failed'])
        added[arm+'7_failed']=p
        for name,flag in [('m7_failed_m6_scored',p.eq(1)&s.eq(0)),('m7_scored_m6_failed',p.eq(0)&s.eq(1)),
                          ('both_failed',p.eq(1)&s.eq(1)),('both_scored',p.eq(0)&s.eq(0))]:
            field=arm+'_'+name;added[field]=flag.astype(float).where(p.notna()&s.notna());stats.append(field)
    delta=added['B8L2_C7_minus_C6']
    added['C6_loss_gt10_vs_C7']=delta.gt(10).astype(float).where(delta.notna())
    added['C6_gain_gt10_vs_C7']=delta.lt(-10).astype(float).where(delta.notna())
    added['C6_failure_or_loss10_vs_scored_C7']=np.where(added['C7_failed'].eq(0),
        (truth(six.C_failed).eq(1)|delta.gt(10)).astype(float),np.nan)
    stats+=['C6_loss_gt10_vs_C7','C6_gain_gt10_vs_C7','C6_failure_or_loss10_vs_scored_C7']
    paired=pd.concat([six,pd.DataFrame(added,index=six.index)],axis=1)
    if args.native_dir:
        geometry_rows=[]
        for pid,g in paired.groupby('pool_id',sort=False):
            with gzip.open(args.native_dir/'endpoints'/(pid+'.json.gz'),'rt') as f:
                end={r['team_key']:r for r in json.load(f)['teams']}
            cache={}
            for row in g.itertuples(index=False):
                values={'event_id':row.event_id}
                for arm in ['B','C']:
                    a=getattr(row,arm+'7_team_key');b=getattr(row,arm+'_team_key');key=tuple(sorted([a,b]))
                    if key not in cache:cache[key]=geometry_metrics(end[a],end[b])
                    values.update({metric+'_'+arm+'7_vs_'+arm+'6':value for metric,value in cache[key].items()})
                geometry_rows.append(values)
        geo=pd.DataFrame(geometry_rows);paired=paired.merge(geo,on='event_id',how='left',validate='one_to_one')
        stats += [c for c in geo if c!='event_id']
    # Full events retain every omission and every unavailable score/failure.
    write_csv(out/'PAIRED_M7_M6_EVENTS.csv.gz',paired)
    meta=['anchor_id','pool_id','image','building','difficulty','method','phase','paired_m7_event_id',
          'total_target_capacity','target_panel_n','x_retained_in_D','y_removed_from_B']
    anchor_rows=[]
    for aid,g in paired.groupby('anchor_id',sort=False):
        row={c:g[c].iloc[0] for c in meta};row['omission_events']=len(g)
        for c in stats:
            x=pd.to_numeric(g[c],errors='coerce')
            row[c]=x.mean();row[c+'__valid_omissions']=x.notna().sum()
        cb=pd.to_numeric(g.B8L2_CB,errors='coerce');q6=pd.to_numeric(g.C_B8L2,errors='coerce')
        q7=float(g.C7_B8L2.iloc[0]) if pd.notna(g.C7_B8L2.iloc[0]) else np.nan
        risk=pd.to_numeric(g.C6_failure_or_loss10_vs_scored_C7,errors='coerce')
        cb_complete=cb.notna().sum()==7
        risk_complete=risk.notna().sum()==7
        row.update(C7_B8L2=q7,C6_B8L2_mean=q6.mean(),C6_B8L2_min=q6.min(),C6_B8L2_max=q6.max(),
                   C6_B8L2_range=q6.max()-q6.min(),valid_C6_omissions=q6.notna().sum(),
                   valid_CB_omissions=cb.notna().sum(),CB_positive_omissions=cb.gt(0).sum(),
                   C7_B8L2_CB=g.B8L2_parent_CB.iloc[0],C6_failed_fraction=truth(g.C_failed).mean(),
                   C7_failed=g.C7_failed.iloc[0],risk_evaluable_omissions=risk.notna().sum(),
                   C6_CB_min=cb.min(),C6_CB_median=cb.median(),C6_CB_max=cb.max(),
                   all_7_C6_scored=float(q6.notna().sum()==7),
                   all_7_valid_and_CB_positive=float(cb_complete and cb.gt(0).sum()==7),
                   all_7_CB_positive=float(cb.gt(0).sum()==7) if cb_complete else np.nan,
                   at_least_6_of_7_CB_positive=float(cb.gt(0).sum()>=6) if cb_complete else np.nan,
                   at_least_4_of_7_CB_positive=float(cb.gt(0).sum()>=4) if cb_complete else np.nan,
                   risky_omission_count=risk.eq(1).sum() if risk_complete else np.nan,
                   single_risky_omission=float(risk.eq(1).sum()==1) if risk_complete else np.nan,
                   no_risky_omission=float(risk.eq(1).sum()==0) if risk_complete else np.nan)
        row['omitted_workers_with_C6_failure_or_loss10']='|'.join(g.loc[risk.eq(1),'Z_omitted_worker'])
        row['C6_CB_negative_workers']='|'.join(g.loc[cb.lt(0),'Z_omitted_worker'])
        anchor_rows.append(row)
    anchors=pd.DataFrame(anchor_rows);write_csv(out/'ANCHOR_SEVEN_OMISSION_SUMMARY.csv.gz',anchors)
    aggregate_fields=stats+['C7_B8L2','C6_B8L2_mean','C6_B8L2_min','C6_B8L2_range','all_7_C6_scored',
                          'C7_B8L2_CB','C6_failed_fraction','C7_failed','all_7_valid_and_CB_positive',
                          'all_7_CB_positive','at_least_6_of_7_CB_positive','at_least_4_of_7_CB_positive',
                          'risky_omission_count','single_risky_omission','no_risky_omission']
    aggregate_fields=list(dict.fromkeys(aggregate_fields))
    pool=anchors.groupby(['phase','method','pool_id','image','building','difficulty'],dropna=False)[aggregate_fields].mean().reset_index()
    buildings=pool.groupby(['phase','method','building'],dropna=False)[aggregate_fields].mean().reset_index()
    write_csv(out/'POOL_OMISSION_SUMMARY.csv.gz',pool);write_csv(out/'BUILDING_OMISSION_SUMMARY.csv.gz',buildings)
    summaries=[]
    for (phase,method),g in pool.groupby(['phase','method']):
        b=buildings[(buildings.phase==phase)&(buildings.method==method)]
        anchor=anchors[(anchors.phase==phase)&(anchors.method==method)]
        for metric in aggregate_fields:
            x=g[metric].dropna();xb=b[metric].dropna()
            summaries.append(dict(phase=phase,method=method,metric=metric,images=len(g),buildings=len(b),
                anchors=len(anchor),omission_events=int(anchor.omission_events.sum()),valid_images=len(x),valid_buildings=len(xb),
                image_equal=x.mean(),building_equal=xb.mean(),image_median=x.median(),image_q10=x.quantile(.1),image_q90=x.quantile(.9),
                positive_images=int(x.gt(0).sum()),positive_buildings=int(xb.gt(0).sum())))
    write_csv(out/'METHOD_PHASE_OMISSION_SUMMARY.csv',pd.DataFrame(summaries))
    worker_fields=['B8L2_C7_minus_C6','B8L2_net_m7_minus_m6','C6_failure_or_loss10_vs_scored_C7',
                   'B8L2_CB','B8L2_CA','C_failed','C7_failed']
    wp=paired.groupby(['phase','method','Z_omitted_worker','pool_id','building'],dropna=False)[worker_fields].mean().reset_index()
    workers=[]
    for key,g in wp.groupby(['phase','method','Z_omitted_worker'],dropna=False):
        for metric in worker_fields:
            v=g[metric].dropna();bv=g.groupby('building')[metric].mean().dropna()
            workers.append(dict(zip(['phase','method','Z_omitted_worker'],key),metric=metric,
                images=len(v),buildings=len(bv),image_equal=v.mean(),building_equal=bv.mean(),
                positive_images=int(v.gt(0).sum()),positive_buildings=int(bv.gt(0).sum())))
    write_csv(out/'TARGET_MEMBER_SENSITIVITY.csv',pd.DataFrame(workers))
    receipt=dict(schema='target_panel_omission_pairs_v1',events=len(paired),anchors=len(anchors),
        images=paired.pool_id.nunique(),buildings=paired.building.nunique(),
        phases=paired.phase.value_counts().to_dict(),panel_enumeration='all seven six-person subsets of each fixed original seven-person target panel',
        causal_comparison='n stays 10. C7 vs C6 replaces the fixed source member by the named omitted target member; B7 vs B6 replaces the same source member by the fixed dropped Y member.',
        aggregation='Seven omissions equal inside an anchor; anchors equal inside pool; images equal; buildings equal separately.',
        missing='No unavailable score or absent comparison is imputed as zero.',
        all_A_exactly_unchanged=True)
    (out/'OMISSION_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(receipt,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
