"""Matched composition effects on time magnitude and prespecified slow-class shifts.

Reads existing result rows only. No fusion/scoring/selection by time outcome.
"""
from __future__ import annotations
import argparse,json,math,time
from pathlib import Path
import numpy as np
import pandas as pd
from evaluate_n20_abc import HERE,read_csv,save_json,sha,summary
from atomic_checkpoint_io import save_csv

def counts(text):return {k:int(v) for k,v in (x.split(':') for x in text.split('|'))}

def run(condition):
    base=HERE/('checkpointed_'+condition);start=time.monotonic()
    meta=['event_id','method_id','tier','condition','building','image','pool_id','difficulty','layer','n','m_AB','m_BC','all_scored','all_complete',
        'within_parent_fine_change','same_source_counts','source_and_historyQ2_matched','source_and_historyQ5_matched','time_population',
        'composition_B','composition_C','team_A','team_B','team_C']
    values=['same_source_log_time_ratio','cross_source_log_time_ratio','net_source_log_time_ratio','net_B8L2','net_D10','net_loss_gt5','net_loss_gt10','B_failure','C_failure']
    inputs=[]
    if condition=='manual':
        for r in read_csv(base/'CHECKPOINT_PLAN.csv'):
            p=base/'shards'/(r['part']+'_RECEIPT.json');assert p.exists();receipt=json.loads(p.read_text());inputs.append(HERE/receipt['output']['path'])
    else:inputs=[HERE/'results_semi/N20_ABC_ALL_COMPONENT_EVENTS.csv.gz']
    data=pd.concat([pd.read_csv(p,usecols=meta+values,dtype={'event_id':str}) for p in inputs],ignore_index=True)
    assert data.event_id.is_unique
    common=data.same_source_log_time_ratio.notna()&data.cross_source_log_time_ratio.notna()
    data['time_common_within_abs_logratio']=data.same_source_log_time_ratio.abs().where(common)
    data['time_common_cross_abs_logratio']=data.cross_source_log_time_ratio.abs().where(common)
    data['time_abs_change_advantage']=data.time_common_cross_abs_logratio-data.time_common_within_abs_logratio
    data['within_time_change_gt10pct']=data.time_common_within_abs_logratio.gt(math.log(1.1)).astype(float).where(common)
    data['cross_time_change_gt10pct']=data.time_common_cross_abs_logratio.gt(math.log(1.1)).astype(float).where(common)
    data['within_time_change_gt20pct']=data.time_common_within_abs_logratio.gt(math.log(1.2)).astype(float).where(common)
    data['cross_time_change_gt20pct']=data.time_common_cross_abs_logratio.gt(math.log(1.2)).astype(float).where(common)
    data['net_source_time_percent_change']=100*np.expm1(data.net_source_log_time_ratio)
    metrics=['time_common_within_abs_logratio','time_common_cross_abs_logratio','time_abs_change_advantage','within_time_change_gt10pct','cross_time_change_gt10pct','within_time_change_gt20pct','cross_time_change_gt20pct']
    rows,buildings=summary(data,metrics)
    bf=pd.DataFrame(buildings)
    for row in rows:
        if row['metric']=='time_abs_change_advantage':
            z=bf[(bf.method_id==row['method_id'])&(bf.tier==row['tier'])&(bf.scope==row['scope'])&(bf.metric==row['metric'])].value.to_numpy(float)
            if len(z)>=3:
                rng=np.random.default_rng(2026102141);boots=z[rng.integers(len(z),size=(2500,len(z)))].mean(axis=1);row['lo95'],row['hi95']=map(float,np.quantile(boots,[.025,.975]))
    directional=[]
    for r in data[(data.method_id=='MV_QTD_manual_new')&(data.tier=='fine')&(data.within_parent_fine_change)].itertuples():
        b,c=counts(r.composition_B),counts(r.composition_C);delta=c.get('QL.2',0)-b.get('QL.2',0)
        if delta==0 or any(b.get(k,0)!=c.get(k,0) for k in set(b)|set(c) if k not in {'QL.1','QL.2'}):continue
        directional.append(dict(event_id=r.event_id,method_id=r.method_id,tier=r.tier,condition=r.condition,building=r.building,image=r.image,pool_id=r.pool_id,
          n=r.n,m_AB=r.m_AB,m_BC=r.m_BC,slow_QL2_count_change=delta,direction='increase_slow_QL2' if delta>0 else 'reduce_slow_QL2',
          net_time_percent=r.net_source_time_percent_change,net_B8L2=r.net_B8L2,net_D10=r.net_D10,net_loss_gt5=r.net_loss_gt5,net_loss_gt10=r.net_loss_gt10,
          B_failure=r.B_failure,C_failure=r.C_failure,time_direction_matches_training=float(np.sign(r.net_source_time_percent_change)==np.sign(delta)) if pd.notna(r.net_source_time_percent_change) else None))
    directional_summary=[]
    if directional:
        d=pd.DataFrame(directional)
        for direction,g in d.groupby('direction'):
            cols=['net_time_percent','net_B8L2','net_D10','net_loss_gt5','net_loss_gt10','B_failure','C_failure','time_direction_matches_training','m_BC','slow_QL2_count_change']
            bm=g.groupby(['building','image','pool_id'])[cols].mean().groupby(level=['building','image']).mean().groupby(level='building').mean()
            for metric in cols:
                z=bm[metric].dropna();lo=hi=None
                if len(z)>=3:
                    rng=np.random.default_rng(2026102141);v=z.to_numpy(float);boots=v[rng.integers(len(v),size=(2500,len(v)))].mean(axis=1);lo,hi=map(float,np.quantile(boots,[.025,.975]))
                directional_summary.append(dict(direction=direction,events=len(g),images=g.image.nunique(),buildings=g.building.nunique(),m_min=int(g.m_AB.min()),m_max=int(g.m_AB.max()),metric=metric,
                    mean=float(z.mean()) if len(z) else None,valid_events=int(g[metric].notna().sum()),valid_buildings=len(z),lo95=lo,hi95=hi))
    out=base/'time_analysis';out.mkdir(parents=True,exist_ok=True)
    def clean(rows):
        return [{k:(None if isinstance(v,float) and not math.isfinite(v) else v) for k,v in r.items()} for r in rows]
    outputs=[save_csv(out/'N20_MATCHED_TIME_SUMMARY.csv',clean(rows)),save_csv(out/'N20_MATCHED_TIME_BUILDING_METRICS.csv.gz',clean(buildings))]
    if directional:outputs.extend([save_csv(out/'N20_QTD_LOWQ_SLOW_CLASS_DIRECTIONAL_EVENTS.csv',clean(directional),key='event_id'),save_csv(out/'N20_QTD_LOWQ_SLOW_CLASS_DIRECTIONAL_SUMMARY.csv',clean(directional_summary))])
    outputs.append(save_csv(out/'N20_MATCHED_TIME_EVENT_VALUES.csv.gz',clean(data[meta+metrics+['net_source_time_percent_change']].to_dict('records')),key='event_id'))
    receipt=dict(condition=condition,registered_events=len(data),common_time_comparable_events=int(common.sum()),outputs=outputs,
        directional_rule='QH/fine other classes unchanged; QL.1 and QL.2 counts trade within the same coarse vector. QL.2 is slower by frozen training labels, not selected using target time.',
        metric_rule='absolute natural log time ratio, common A/B and A/C usable time denominator; >10/20pct means absolute log ratio above log(1.1/1.2)',
        frozen_input_files=[dict(path=str(p.relative_to(HERE)),sha256=sha(p)) for p in inputs],fusion_calls=0,score_calls=0,seconds=time.monotonic()-start)
    save_json(out/'TIME_RECEIPT.json',receipt);print(json.dumps({k:v for k,v in receipt.items() if k!='frozen_input_files'},ensure_ascii=False),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--condition',required=True);a=p.parse_args();run(a.condition)
