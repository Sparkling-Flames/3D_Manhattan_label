"""Original declared room-group weighting, with building-cluster intervals."""
from __future__ import annotations
import hashlib,json,sys
from pathlib import Path
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent;PROFILES=HERE.parent/'profiles'
sys.path.insert(0,str(PROFILES))
from room_weighting import aggregate_declared_groups
SEED=2026101947

def group_bootstrap(g,value):
    z=g.loc[g[value].notna(),['building_id',value]]
    if not len(z):return np.nan,np.nan,np.nan,0
    assert not z.building_id.str.contains(';',regex=False).any(),'A declared group spans buildings; inference needs explicit treatment.'
    moments=z.groupby('building_id')[value].agg(['sum','count']);rng=np.random.default_rng(SEED)
    draw=rng.integers(0,len(moments),size=(3000,len(moments)))
    a=moments['sum'].to_numpy()[draw].sum(1)/moments['count'].to_numpy()[draw].sum(1)
    return z[value].mean(),np.quantile(a,.025),np.quantile(a,.975),len(moments)

def aggregate(name,data,strata,values,memberships,out):
    if not len(data):return
    groups,coverage=aggregate_declared_groups(data,memberships,values,strata=strata)
    groups.to_csv(out/(name+'_groups.csv'),index=False)
    (out/(name+'_coverage.json')).write_text(json.dumps(coverage,indent=2)+'\n')
    rows=[]
    for key,g in groups.groupby(strata,dropna=False):
        if not isinstance(key,tuple):key=(key,)
        for value in values:
            mean,lo,hi,nb=group_bootstrap(g,value)
            rows.append(dict(zip(strata,key),value=value,group_equal_mean=mean,low=lo,high=hi,buildings=nb,
                evaluable_groups=int(g[value].notna().sum()),observed_memberships=int(g.observed_images.sum()),
                groups_with_multiple_observed_images=int(g.observed_images.ge(2).sum())))
    pd.DataFrame(rows).to_csv(out/(name+'_summary.csv'),index=False)

def main():
    out=HERE/'room_sensitivity';out.mkdir(exist_ok=True);m=pd.read_csv(PROFILES/'declared_room_groups.csv');inputs=[]
    for kind in ['pair','largest']:
        p=HERE/'transfer'/(kind+'_image_scores.csv')
        d=pd.read_csv(p);d=d[d.panel.eq('all')]
        key=['threshold_deg','pool_id','image_id','image_code','building_id','difficulty']
        w=d.pivot(index=key,columns='model',values='brier');comparisons=[]
        for model,base in [('Q_relative','difficulty_prevalence'),('QT','Q_relative'),('QTD','QT'),('QTD','difficulty_prevalence'),('QTD_behavior','QTD'),('QTD_origin_time','QTD')]:
            z=(w[model]-w[base]).dropna().rename('delta_brier').reset_index();z['model']=model;z['baseline']=base;comparisons.append(z)
        z=pd.concat(comparisons,ignore_index=True)
        aggregate(kind+'_transfer',z,['threshold_deg','model','baseline'],['delta_brier'],m,out);inputs.append(str(p))
    for name in ['replacement','cross_route','composition']:
        p=HERE/'fusion_analysis'/(name+'_image_effects.csv')
        if not p.exists():continue
        d=pd.read_csv(p);aggregate(name,d,['threshold_deg','k','contrast','metric'],['difference'],m,out);inputs.append(str(p))
    p=HERE/'forward_swaps/image_effects.csv'
    if p.exists():
        d=pd.read_csv(p);aggregate('forward_labels',d,['label_metric','family','panel','outcome','k'],['difference'],m,out);inputs.append(str(p))
    p=HERE/'swap_transfer/image_k_scores.csv'
    if p.exists():
        d=pd.read_csv(p);key=['outcome','k','pool_id','image_id','image_code','building_id','difficulty'];w=d.pivot(index=key,columns='model',values='squared_error');z=[]
        for model,base in [('Q','known_task'),('QT','Q'),('QTD','QT'),('actual_cluster_9','known_task'),('actual_cluster_12','known_task'),('QTD_actual_cluster_9','QTD'),('raw_pair_geometry','known_task')]:
            q=(w[model]-w[base]).dropna().rename('delta_MSE').reset_index();q['model']=model;q['baseline']=base;z.append(q)
        d=pd.concat(z,ignore_index=True);aggregate('swap_prediction',d,['outcome','k','model','baseline'],['delta_MSE'],m,out);inputs.append(str(p))
    (out/'RECEIPT.json').write_text(json.dumps(dict(source_groups=str(PROFILES/'declared_room_groups.csv'),
        memberships_sha256=hashlib.sha256((PROFILES/'declared_room_groups.csv').read_bytes()).hexdigest(),inputs=inputs,
        fixed_original_supported_groups_only=True,no_invented_singletons=True,groups_not_independent_N=True,
        group_equal_point_estimate_building_cluster_bootstrap=3000,bootstrap_seed=SEED),indent=2)+'\n')
    print(json.dumps(dict(input_families=len(inputs),inputs=inputs),indent=2))

if __name__=='__main__':main()
