"""Propagate AC patches through frozen context and common-method summaries."""
from __future__ import annotations
import argparse
from itertools import combinations
from pathlib import Path
import sys
import numpy as np
import pandas as pd
from .evaluate_manual_order_ac_20261104 import AC,ROOT,OUT,modules,save,jsave,compare,align
from .evaluate_manual_order_ac_sensitivity_20261104 import patch,subset,changed_rows


def direction_means(pool,important):
    d=pool[pool.scope.eq('primary')&pool.condition.eq('manual')&pool.analysis_view.eq('A_fixed_n')].copy()
    fields=[m+'__mean_absolute' for m in important if m+'__mean_absolute' in d]
    signed=[m+'__mean' for m in important if m+'__mean' in d]
    keys=['pool_id','image','building','method','n_condition','m_condition']
    means=d.groupby(keys,sort=False)[fields+signed].mean().reset_index()
    directions=d.groupby(keys,sort=False).agg(role_directions=('role_direction',lambda x:'|'.join(sorted(set(x)))),class_pair_directions=('role_direction','nunique')).reset_index()
    return means.merge(directions,on=keys,validate='one_to_one')


def common_pairs(means,important):
    rows=[]
    for (n,m),g in means.groupby(['n_condition','m_condition'],sort=False):
        by={method:d.set_index('pool_id') for method,d in g.groupby('method',sort=False)}
        for left,right in combinations(sorted(by),2):
            x,y=by[left],by[right];common=sorted(set(x.index)&set(y.index))
            if not common:continue
            x=x.loc[common];y=y.loc[common]
            for metric in important:
                col=metric+'__mean_absolute'
                if col not in x:continue
                valid=x[col].notna()&y[col].notna();xx=x.loc[valid,col];yy=y.loc[valid,col]
                rows.append(dict(method_left=left,method_right=right,n=n,m=m,metric=metric,
                    common_registered_pools=len(common),valid_common_images=int(valid.sum()),
                    valid_common_buildings=x.loc[valid,'building'].nunique(),left_image_mean_absolute_change=xx.mean(),
                    right_image_mean_absolute_change=yy.mean(),right_minus_left_absolute_change=(yy-xx).mean(),
                    right_absolute_larger_images=int((yy-xx>1e-9).sum()),left_full_coverage_pools=len(by[left]),
                    right_full_coverage_pools=len(by[right]),common_pool_ids='|'.join(common),
                    interpretation='same image target n m; own class directions averaged equally; members and meanings differ; descriptive contrast, not method superiority'))
    return pd.DataFrame(rows)


def cancellation(pool,group):
    q=pool[pool.scope.eq('primary')&pool.condition.eq('manual')&pool.analysis_view.eq('A_fixed_n')].copy()
    q['small_signed_Q_mean']=q['B8L2_CA__mean'].abs()<=1
    q['small_mean_absolute_Q_change']=q['B8L2_CA__mean_absolute']<=1
    q['member_or_background_sign_cancellation']=q.small_signed_Q_mean&(q['B8L2_CA__mean_absolute']>=5)
    q['both_high_mean_Q']=q['A_B8L2__mean'].ge(90)&q['C_B8L2__mean'].ge(90)
    q['both_low_mean_Q']=q['A_B8L2__mean'].le(70)&q['C_B8L2__mean'].le(70)
    q['geometry_changes_despite_small_signed_Q']=q.small_signed_Q_mean&q['geometry_bev_distance_AC__mean'].ge(.1)
    keep=group+['pool_id','image','building','registered_pairs']+[c for c in q if c.startswith(('B8L2_CA__','D10_CA__','A_B8L2__','C_B8L2__','fusion_turn_n_CA__','ref_node_recall_5_CA__','geometry_bev_distance_AC__'))]+['small_signed_Q_mean','small_mean_absolute_Q_change','member_or_background_sign_cancellation','both_high_mean_Q','both_low_mean_Q','geometry_changes_despite_small_signed_Q']
    return q[keep]


def delta(a,b,keys,path):
    c0,c1=changed_rows(a,b,keys)
    d=align(c0,keys).add_prefix('automatic_').join(align(c1,keys).add_prefix('assisted_')).reset_index()
    save(d,path);return len(d)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=OUT/'context_common')
    args=parser.parse_args();out=args.out;out.mkdir(parents=True,exist_ok=True)
    _,summary,_,_,_=modules()
    import summarize_context_and_common_pools as context
    group=summary.GROUP;important=context.IMPORTANT
    original=pd.read_csv(AC/'stage05_main/POOL_CONDITION_EFFECTS.csv.gz',low_memory=False,dtype={k:str for k in group})
    local=pd.read_csv(OUT/'AFFECTED_POOLS_ASSISTED.csv.gz',low_memory=False,dtype={k:str for k in group})
    keys=group+['pool_id','image','building'];assisted=patch(original,local,keys)
    source=AC/'stage05_context_common';parity=[];counts={}
    a,b=direction_means(original,important),direction_means(assisted,important)
    k=['pool_id','image','building','method','n_condition','m_condition']
    parity.extend(compare(pd.read_csv(source/'METHOD_POOL_ALL_DIRECTION_EFFECTS.csv.gz',dtype={c:str for c in ['n_condition','m_condition']}),a,k,'original_method_direction_means'))
    counts['method_pool_changes']=delta(a,b,k,out/'METHOD_POOL_ALL_DIRECTION_CHANGES.csv.gz')
    ca,cb=common_pairs(a,important),common_pairs(b,important)
    k=['method_left','method_right','n','m','metric']
    parity.extend(compare(pd.read_csv(source/'COMMON_POOL_METHOD_COMPARISONS.csv.gz'),ca,k,'original_common_method_comparisons'))
    counts['common_method_changes']=delta(ca,cb,k,out/'COMMON_POOL_METHOD_COMPARISON_CHANGES.csv.gz')
    save(cb,out/'COMMON_POOL_METHOD_COMPARISONS_ASSISTED.csv.gz')
    ca,cb=cancellation(original,group),cancellation(assisted,group)
    parity.extend(compare(pd.read_csv(source/'SMALL_RESPONSE_AND_CANCELLATION_DIAGNOSTICS.csv.gz',dtype={k:str for k in group}),ca,keys,'original_cancellation_diagnostics'))
    counts['small_response_changes']=delta(ca,cb,keys,out/'SMALL_RESPONSE_DIAGNOSTIC_CHANGES.csv.gz')
    target=ROOT/'research/workers/personnel_v21_reselection_20261029/targets/POOL_TARGET_CONDITIONS.csv'
    ctx=pd.read_csv(target,low_memory=False);axes=[c for c in ['official_difficulty','structural_condition','geometric_challenge'] if c in ctx]
    frames=[]
    for d in (original,assisted):
        d=d.merge(ctx[['pool_id']+axes],on='pool_id',how='left',validate='many_to_one')
        relevant=d.scope.eq('primary')&d.condition.eq('manual')&d.analysis_view.isin(['A_fixed_n','A_pool_frontier','whole_equal_fixed_n_all_m','whole_equal_pool_frontier'])
        d=d[relevant&d.n_condition.isin(['14','16','18','20','22','N_minus_m'])].copy()
        cols=[c for c in d if '__' not in c or c.split('__')[0] in important];d=d[cols]
        parts=[]
        for axis in axes:
            own=d.copy();own['analysis_view']=own.analysis_view+'|ctx:'+axis+'='+own[axis].fillna('ungraded_or_unavailable').astype(str);parts.append(own)
        frames.append(pd.concat(parts,ignore_index=True))
    before,after=frames;cha,chb=changed_rows(before,after,keys)
    selected=cha[group].drop_duplicates()
    before,after=subset(before,selected,group),subset(after,selected,group)
    for d,dest in [(before,out/'automatic'),(after,out/'assisted')]:
        dest.mkdir(exist_ok=True);summary.aggregate(d,dest)
        result=pd.read_csv(dest/'CONDITION_METRIC_SUMMARY.csv.gz',low_memory=False,dtype={k:str for k in group})
        p=result.analysis_view.str.split('|ctx:',regex=False,expand=True)
        result['analysis_view']=p[0];q=p[1].str.split('=',n=1,expand=True)
        result['context_axis']=q[0];result['context_value']=q[1]
        save(result,dest/'FROZEN_CONTEXT_EFFECT_SUMMARY.csv.gz')
    a=pd.read_csv(out/'automatic/FROZEN_CONTEXT_EFFECT_SUMMARY.csv.gz',low_memory=False,dtype={k:str for k in group})
    b=pd.read_csv(out/'assisted/FROZEN_CONTEXT_EFFECT_SUMMARY.csv.gz',low_memory=False,dtype={k:str for k in group})
    k=group+['context_axis','context_value','metric']
    frozen=pd.read_csv(source/'FROZEN_CONTEXT_EFFECT_SUMMARY.csv.gz',low_memory=False,dtype={c:str for c in group})
    frozen=subset(frozen,a,k)
    parity.extend(compare(frozen,a,k,'original_frozen_context_summary'))
    counts['context_changes']=delta(a,b,k,out/'FROZEN_CONTEXT_SUMMARY_CHANGES.csv.gz')
    save(pd.DataFrame(parity),out/'PARITY.csv')
    jsave(out/'CONTEXT_IMPACT_RECEIPT.json',dict(counts,official_difficulty_changed=False,context_assignments_changed=False,
        classes_refitted=False,classifier_selection_rerun=False,new_scores=0,new_fusions=0,
        original_outputs_modified=False,method_comparison='descriptive frozen methods; not classifier superiority'))
    print(counts,flush=True)


if __name__=='__main__':main()
