"""Aggregate verified result shards without materializing the full wide table."""
from __future__ import annotations
import argparse,collections,csv,gzip,json,time
from pathlib import Path
import numpy as np
import pandas as pd
from discover_n20_abc import HERE,read_csv,save_csv,save_json,sha
from atomic_checkpoint_io import save_csv

NONMETRICS={'within_parent_fine_change','same_count_block_Y','same_source_counts','net_shared_workers','cross_shared_workers','within_shared_workers'}
NONNUMERIC_ENDINGS=('_structure_reason','_geometry_comparison_error','_corner_corner_metric_schema','_corner_status')
META=['event_id','method_id','tier','condition','building','image','pool_id','difficulty','layer','m_AB','m_BC','all_scored','all_complete','computed_all_arms',
      'within_parent_fine_change','same_source_counts','source_and_historyQ2_matched','source_and_historyQ5_matched','time_population']
PRIMARY={'common_quality_within_abs','common_quality_cross_abs','stable_advantage','stable_D10_advantage','within_joint_stable_main','cross_joint_stable_main','within_joint_stable_D10_main','cross_joint_stable_D10_main',
 'same_loss_gt5','cross_loss_gt5','same_loss_gt10','cross_loss_gt10','A_failure','B_failure','C_failure','within_floor_jaccard_difference','cross_floor_jaccard_difference','within_structure_bound_cyclic_deg','cross_structure_bound_cyclic_deg',
 'same_source_log_time_ratio','cross_source_log_time_ratio','within_mean_height_prism_pair_difference','cross_mean_height_prism_pair_difference','within_centroid_distance_h','cross_centroid_distance_h','abs_Q_change_advantage'}

def summarize(condition,allow_partial=False):
    started=time.monotonic();base=HERE/('checkpointed_'+condition);plan=read_csv(base/'CHECKPOINT_PLAN.csv')
    completed=[r for r in plan if (base/'shards'/(r['part']+'_RECEIPT.json')).exists()]
    if not allow_partial:assert len(completed)==len(plan),(len(completed),len(plan))
    with gzip.open(HERE/'results_semi/N20_ABC_ALL_COMPONENT_EVENTS.csv.gz','rt',encoding='utf-8-sig',newline='') as f:columns=next(csv.reader(f))
    metrics=[c for c in columns if c.startswith(('same_','cross_','net_','within_','common_quality_')) and c not in NONMETRICS and not c.endswith(NONNUMERIC_ENDINGS)]
    metrics+=['A_failure','B_failure','C_failure','stable_advantage','stable_D10_advantage','abs_Q_change_advantage']
    metrics=list(dict.fromkeys(metrics));use=list(dict.fromkeys(META+metrics))
    accum={};infos={};ids=set();inputs=[];computed=0;failed=0;tails=[]
    for pi,part in enumerate(completed):
        receipt=json.loads((base/'shards'/(part['part']+'_RECEIPT.json')).read_text());path=HERE/receipt['output']['path']
        assert sha(path)==receipt['output']['sha256']
        g=pd.read_csv(path,usecols=use,dtype={'event_id':str},low_memory=False)
        expected=[r['event_id'] for r in read_csv(HERE/part['input_path'])]
        assert g.event_id.tolist()==expected and not ids.intersection(expected)
        ids.update(expected);computed+=len(g);failed+=int((~g.all_complete).sum())
        inputs.append(dict(part=part['part'],path=receipt['output']['path'],sha256=receipt['output']['sha256'],events=len(g)))
        for c in metrics:
            if pd.api.types.is_bool_dtype(g[c]):g[c]=g[c].astype(float)
            elif not pd.api.types.is_numeric_dtype(g[c]):g[c]=pd.to_numeric(g[c].replace({'True':1,'False':0}),errors='coerce')
        for (method,tier),g0 in g.groupby(['method_id','tier'],dropna=False):
            scopes={'all_composition_changes':g0}
            if tier=='fine':
                scopes['within_parent_fine_change']=g0[g0.within_parent_fine_change]
                scopes['cross_parent_change']=g0[~g0.within_parent_fine_change]
            scopes['source_count_matched']=g0[g0.same_source_counts]
            scopes['source_history_Q2_matched']=g0[g0.source_and_historyQ2_matched]
            scopes['source_history_Q5_matched']=g0[g0.source_and_historyQ5_matched]
            for m in sorted(g0.m_AB.unique()):scopes['m_'+str(int(m))]=g0[g0.m_AB==m]
            for d in sorted(g0.difficulty.unique()):scopes['difficulty_'+str(d)]=g0[g0.difficulty==d]
            for origin in sorted(g0.time_population.unique()):scopes['time_population_'+str(origin)]=g0[g0.time_population==origin]
            for scope,x in scopes.items():
                if len(x)==0:continue
                prefix=(method,tier,scope);first=x.iloc[0]
                if prefix not in infos:infos[prefix]=dict(condition=condition,events=0,images=set(),buildings=set(),m_min=100,m_max=0,net_m_sum=0,all_scored_events=0,all_complete_events=0,valid_events=np.zeros(len(metrics),dtype=np.int64))
                z=x[metrics].to_numpy(float);count=np.isfinite(z).sum(axis=0);total=np.nansum(z,axis=0)
                i=infos[prefix];i['events']+=len(x);i['images'].add(first.image);i['buildings'].add(first.building)
                i['m_min']=min(i['m_min'],int(x.m_AB.min()));i['m_max']=max(i['m_max'],int(x.m_AB.max()));i['net_m_sum']+=int(x.m_BC.sum())
                i['all_scored_events']+=int(x.all_scored.sum());i['all_complete_events']+=int(x.all_complete.sum());i['valid_events']+=count
                key=prefix+(first.building,first.image,first.pool_id)
                if key not in accum:accum[key]=[total,count]
                else:accum[key][0]+=total;accum[key][1]+=count
                for metric in ['same_B8L2','cross_B8L2','net_B8L2','same_abs_B8L2','cross_abs_B8L2','within_floor_jaccard_difference','cross_floor_jaccard_difference']:
                    values=x[metric].dropna()
                    if len(values):
                        for quantile in ([.05,.5,.95] if metric.endswith('_B8L2') else [.5,.95]):
                            tails.append(dict(method_id=method,tier=tier,condition=condition,scope=scope,building=first.building,image=first.image,pool_id=first.pool_id,
                              metric=metric,quantile=quantile,value=float(values.quantile(quantile)),valid_events=len(values)))
        if (pi+1)%20==0:print(json.dumps({'read_shards':pi+1,'events':computed,'seconds':time.monotonic()-started}),flush=True)
    with gzip.open(HERE/('design_'+condition)/'MATCHED_ABC_EVENTS.csv.gz','rt',encoding='utf-8-sig',newline='') as f:
        expected_ids={r['event_id'] for r in csv.DictReader(f)}
    assert ids<=expected_ids
    if not allow_partial:assert ids==expected_ids
    pool_rows=[]
    for key,(total,count) in accum.items():
        means=np.divide(total,count,out=np.full_like(total,np.nan),where=count>0)
        pool_rows.append(dict(zip(['method_id','tier','scope','building','image','pool_id'],key))|dict(zip(metrics,means)))
    pools=pd.DataFrame(pool_rows)
    images=pools.groupby(['method_id','tier','scope','building','image'])[metrics].mean()
    buildings=images.groupby(level=['method_id','tier','scope','building']).mean()
    rows=[];building_rows=[]
    for prefix,part in buildings.groupby(level=['method_id','tier','scope']):
        i=infos[prefix];common=dict(method_id=prefix[0],tier=prefix[1],condition=condition,scope=prefix[2],events=i['events'],images=len(i['images']),buildings=len(i['buildings']),
            m_min=i['m_min'],m_max=i['m_max'],actual_net_m_mean=i['net_m_sum']/i['events'],all_scored_events=i['all_scored_events'],all_complete_events=i['all_complete_events'])
        for mi,metric in enumerate(metrics):
            z=part[metric].dropna();lo=hi=None
            if len(z)>=3 and metric in {'stable_advantage','stable_D10_advantage','abs_Q_change_advantage'}:
                rng=np.random.default_rng(2026102141);a=z.to_numpy(float);boots=a[rng.integers(len(a),size=(2500,len(a)))].mean(axis=1);lo,hi=map(float,np.quantile(boots,[.025,.975]))
            rows.append(dict(common,metric=metric,mean=float(z.mean()) if len(z) else None,valid_events=int(i['valid_events'][mi]),valid_buildings=len(z),lo95=lo,hi95=hi,
                positive_buildings=int(z.gt(0).sum()),negative_buildings=int(z.lt(0).sum())))
            for key,v in z.items():building_rows.append(dict(method_id=prefix[0],tier=prefix[1],condition=condition,scope=prefix[2],building=key[-1],metric=metric,value=float(v)))
    out=base/('summary_partial' if allow_partial else 'summary');out.mkdir(exist_ok=True)
    outputs=[save_csv(out/'N20_MATCHED_ALL_METRICS_SUMMARY.csv',rows),save_csv(out/'N20_MATCHED_BUILDING_METRICS.csv.gz',building_rows),
             save_csv(out/'N20_MATCHED_PRIMARY_SUMMARY.csv',[r for r in rows if r['metric'] in PRIMARY])]
    # Quantiles are descriptive within each pool. Averaging them across
    # buildings does not purport to be a population-level quantile.
    tail_frame=pd.DataFrame(tails)
    tail_image=tail_frame.groupby(['method_id','tier','condition','scope','metric','quantile','building','image']).value.mean()
    tail_building=tail_image.groupby(level=['method_id','tier','condition','scope','metric','quantile','building']).mean()
    tail_rows=[]
    for key,z in tail_building.groupby(level=['method_id','tier','condition','scope','metric','quantile']):
        tail_rows.append(dict(zip(['method_id','tier','condition','scope','metric','quantile'],key))|dict(mean_of_building_equal_pool_quantiles=float(z.mean()),valid_buildings=len(z)))
    outputs.extend([save_csv(out/'N20_MATCHED_TAIL_QUANTILES_BY_POOL.csv.gz',tails),save_csv(out/'N20_MATCHED_TAIL_QUANTILES_BUILDING_BALANCED.csv',tail_rows)])
    receipt=dict(condition=condition,events_computed=computed,events_expected=len(expected_ids),complete_event_id_equality=ids==expected_ids,shards_complete=len(completed),shards_expected=len(plan),
       all_complete_events=computed-failed,events_with_failure=failed,metrics=len(metrics),input_parts=inputs,
       method='streamed shards -> event means within pool -> image means -> building means; building equal; each metric own denominator; no global wide dataframe',
       tail_method='within-pool empirical quantiles -> image -> building equal; not the quantile of all population events',
       fusion_calls=0,score_calls=0,seconds=time.monotonic()-started,outputs=outputs)
    save_json(out/'SUMMARY_RECEIPT.json',receipt);print(json.dumps({k:v for k,v in receipt.items() if k not in ['input_parts']},ensure_ascii=False),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--condition',required=True);p.add_argument('--allow-partial',action='store_true');a=p.parse_args();summarize(a.condition,a.allow_partial)
