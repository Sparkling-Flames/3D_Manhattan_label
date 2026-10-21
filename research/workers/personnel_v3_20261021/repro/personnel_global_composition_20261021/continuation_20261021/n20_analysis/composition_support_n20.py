"""Count actual composition opportunities without fitting or native fusion."""
from collections import Counter
from pathlib import Path
import argparse
import gzip
import json
import math
import numpy as np
import pandas as pd
from analyze_n20 import HERE, SNAPSHOT, load, load_maps, save, js


def possible_vectors(capacities,n=20):
    dp=[0]*(n+1);dp[0]=1
    for u in capacities:
        new=[0]*(n+1)
        for total in range(n+1):
            if dp[total]:
                for k in range(min(u,n-total)+1):new[total+k]+=dp[total]
        dp=new
    return dp[n]


def analyze(condition):
    out=HERE/condition
    frame,_,_,_=load(condition)
    maps,_,_=load_maps()
    folds=pd.read_csv(out/'N20_FOLD_MAPS.csv.gz',keep_default_na=False)
    formal={p['pool_id']:set(r['worker_id'] for r in p['records']) for p in json.load(gzip.open(SNAPSHOT,'rt'))['images']}
    pred=pd.read_csv(out/'N20_PREDICTION_POOL_RESULTS.csv.gz',usecols=['support_scope','design_anchor','method_id','heldout_building','pool_id','outcome'])
    pred=pred[['support_scope','design_anchor','method_id','heldout_building','pool_id','outcome']]
    evaluated=set(map(tuple,pred.drop_duplicates().to_numpy()))
    rows=[]
    for f in folds.itertuples():
        variable=set(f.variable_workers.split('|'))
        target=frame[frame.method_id.eq(f.design_anchor)&frame.building.eq(f.heldout_building)]
        mapping=maps[f.method_id,condition,f.heldout_building]
        anchor_map=maps[f.design_anchor,condition,f.heldout_building]
        anchor_known=set(anchor_map['coarse'])&set(anchor_map['fine'])
        levels_c=sorted(set(mapping['coarse'].values()));levels_f=sorted(set(mapping['fine'].values()))
        for pool,g in target.groupby('pool_id',sort=True):
            keep=np.array([set(s.split('|'))<=variable for s in g.member_workers],bool)
            h=g[keep]
            population=formal[pool]&variable&anchor_known
            capacity_c=Counter(mapping['coarse'][w] for w in population)
            capacity_f=Counter(mapping['fine'][w] for w in population)
            allc=[];allf=[]
            for s in h.member_workers:
                members=s.split('|')
                cc=Counter(mapping['coarse'][w] for w in members);ff=Counter(mapping['fine'][w] for w in members)
                allc.append(tuple(cc.get(k,0) for k in levels_c));allf.append(tuple(ff.get(k,0) for k in levels_f))
            for outcome in ['all_endpoints','B8L2']:
                good=np.ones(len(h),bool) if outcome=='all_endpoints' else h.B8L2.notna().to_numpy()
                ct=[x for x,ok in zip(allc,good) if ok];ft=[x for x,ok in zip(allf,good) if ok]
                ctof={}
                for cc,ff in zip(ct,ft):ctof.setdefault(cc,set()).add(ff)
                fine_counts=Counter(ft)
                has_extra=any(len(v)>1 for v in ctof.values()) if mapping['has_fine'] else False
                eval_outcome='failure' if outcome=='all_endpoints' else outcome
                rows.append(dict(condition=condition,support_scope=f.support_scope,design_anchor=f.design_anchor,method_id=f.method_id,
                    heldout_building=f.heldout_building,pool_id=pool,image_id=g.image_id.iloc[0],image=g.image.iloc[0],
                    target_panel=g.target_panel.iloc[0],outcome_support=outcome,
                    actual_supported_teams=len(ct),coarse_vectors_observed=len(set(ct)),fine_vectors_observed=len(set(ft)),
                    labelled_pool_n=len(population),possible_member_sets=str(math.comb(len(population),20) if len(population)>=20 else 0),
                    possible_coarse_vectors=possible_vectors(capacity_c.values()),possible_fine_vectors=possible_vectors(capacity_f.values()),
                    distinct_coarse_classes_in_pool=len(capacity_c),distinct_fine_classes_in_pool=len(capacity_f),
                    has_cross_coarse_composition_opportunity=len(set(ct))>1,
                    has_fine_definition=mapping['has_fine'],has_within_coarse_fine_composition_opportunity=has_extra,
                    coarse_vectors_with_multiple_fine_vectors=sum(len(v)>1 for v in ctof.values()) if mapping['has_fine'] else 0,
                    same_fine_composition_member_variation_estimable=any(v>1 for v in fine_counts.values()),
                    member_variation_max_sampled_sets_in_fine_vector=max(fine_counts.values()) if fine_counts else 0,
                    prediction_evaluated=(f.support_scope,f.design_anchor,f.method_id,f.heldout_building,pool,eval_outcome) in evaluated,
                    interpretation='Materialized outer-map target pool support; full failed eligibility denominators remain in N20_COMMON_SUPPORT.csv. No control of background or replacement m. Missing quality is not zero.'))
    d=pd.DataFrame(rows);save(d,out/'N20_TARGET_COMPOSITION_SUPPORT.csv')
    keys=['condition','support_scope','design_anchor','method_id','outcome_support']
    ss=[]
    for panel in ['all','prior_panel','added_images']:
        x=d if panel=='all' else d[d.target_panel.eq(panel)]
        for vals,g in x.groupby(keys,dropna=False):
            r=dict(zip(keys,vals),target_panel=panel,mapped_target_pool_rows=len(g),observed_teams=int(g.actual_supported_teams.sum()))
            for flag in ['has_cross_coarse_composition_opportunity','has_within_coarse_fine_composition_opportunity',
                         'same_fine_composition_member_variation_estimable','prediction_evaluated']:
                z=g[g[flag]]
                r[flag+'_pools']=len(z);r[flag+'_images']=z.image_id.nunique();r[flag+'_buildings']=z.heldout_building.nunique()
            ss.append(r)
    save(pd.DataFrame(ss),out/'N20_TARGET_COMPOSITION_SUPPORT_SUMMARY.csv')
    js(out/'N20_TARGET_COMPOSITION_SUPPORT_RECEIPT.json',dict(condition=condition,rows=len(d),
        new_fusion=False,new_models=False,quality_missing_retained=True,
        fields='Class count K, team n=20, sampled members r<=3 and actual cross/fine opportunities are separately recorded.',
        denominator='This table expands materialized fold maps. All registered target eligibility, including no materialized fold, remains in N20_COMMON_SUPPORT.csv.'))
    print(condition,'composition support',len(d),'rows',flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--condition',required=True,choices=['manual','semi'])
    analyze(ap.parse_args().condition)
