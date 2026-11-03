"""Recompute only impacted execution/evaluability funnel cells and cohorts."""
from pathlib import Path
import sys
import numpy as np
import pandas as pd
from .evaluate_manual_order_ac_20261104 import AC,OUT,save,jsave,compare,align
from .evaluate_manual_order_ac_sensitivity_20261104 import changed_rows,patch,subset

SOURCE=AC/'stage05_funnel_bridge'
COHORT=['method','scope','role_direction','n','m','metric']


def cells(d,f,ks):
    d=d[d.condition.eq('manual')&d.layer.eq('ordinary_manual')&d.equal_team_size.map(f.truth)&d.pure_cross_class_blocks.map(f.truth)].copy()
    if d.empty:return pd.DataFrame()
    d['n']=d.n.astype(int);d['m']=d.m.astype(int)
    k=d.method.map(ks).astype(int).astype(str)
    d['role_direction']=d.source_role_rank.astype(int).astype(str)+'/'+k+'->'+d.target_role_rank.astype(int).astype(str)+'/'+k
    d['_block']=d.X_workers+'::'+d.Z_workers
    d['design_A_or_bridge']=d.design_family.str.contains('A_equal_AC|F_strict_common_n_bridge',regex=True)
    d['explicit_equal_whole']=d.design_family.str.contains('B_equal_whole_class',regex=False)
    rstats=d.groupby(f.KEYS,dropna=False).agg(registered_events=('event_id','size'),registered_blocks=('_block','nunique'),
        registered_A_or_bridge_events=('design_A_or_bridge','sum'),registered_equal_whole_events=('explicit_equal_whole','sum')).reset_index()
    meta=d.groupby(f.KEYS,dropna=False)[['image','building','scope','role_direction','D_n']].first().reset_index()
    rstats=rstats.merge(meta,on=f.KEYS,validate='one_to_one')
    for flag in f.STATUS:d['pair_'+flag]=d['A_'+flag].map(f.truth)|d['C_'+flag].map(f.truth)
    for metric,col in f.FIELDS.items():d[metric+'_numeric']=pd.to_numeric(d[col],errors='coerce');d[metric+'_absolute']=pd.to_numeric(d[col],errors='coerce').abs()
    cols=[m+s for m in f.FIELDS for s in ['_numeric','_absolute']]
    blocks=d.groupby(f.KEYS+['_block'],dropna=False)[cols].mean()
    means=blocks.groupby(f.KEYS,dropna=False).mean();bn=blocks.groupby(f.KEYS,dropna=False).count()
    vn=d.groupby(f.KEYS,dropna=False)[cols].count();flags=d.groupby(f.KEYS,dropna=False)[['pair_'+s for s in f.STATUS]].sum()
    en=d.groupby(f.KEYS,dropna=False).size();rows=[]
    for key,avg in means.iterrows():
        row=dict(zip(f.KEYS,key));row.update(measured_events=int(en.loc[key]),**{s+'_pair_events':int(flags.loc[key,'pair_'+s]) for s in f.STATUS})
        for metric in f.FUNNEL_METRICS:
            rows.append(dict(row,metric=metric,numerical_direction_available=metric not in f.PAIRS,
                mean_change=avg[metric+'_numeric'],mean_absolute_change=avg[metric+'_absolute'],
                valid_events=int(vn.loc[key,metric+'_numeric']),valid_blocks=int(bn.loc[key,metric+'_numeric'])))
    return rstats.merge(pd.DataFrame(rows),on=f.KEYS,how='left',validate='one_to_many')


def population(cell):
    allc=cell.copy();allc['role_direction']='ALL_CANONICAL_DIRECTIONS'
    both=pd.concat([cell,allc],ignore_index=True)
    pooled=both[both.metric.notna()].groupby(COHORT+['pool_id'],dropna=False).agg(
        mean_change=('mean_change','mean'),mean_absolute_change=('mean_absolute_change','mean'),valid_events=('valid_events','sum'),
        registered_events=('registered_events','sum'),measured_events=('measured_events','sum'),exception_events=('fusion_execution_exception_pair_events','sum'),
        structural_failure_events=('fusion_structural_failure_pair_events','sum'),invalid_geometry_events=('output_invalid_geometry_pair_events','sum'),
        measurement_exception_events=('measurement_exception_pair_events','sum'),image=('image','first'),building=('building','first')).reset_index()
    pooled['positive']=pooled.mean_change.gt(1e-9);pooled['negative']=pooled.mean_change.lt(-1e-9)
    pooled['nearzero']=pooled.mean_change.abs().le(1e-9);pooled['fully_valid']=pooled.valid_events.eq(pooled.registered_events)
    for stem in ['exception','structural_failure','invalid_geometry','measurement_exception']:pooled['has_'+stem]=pooled[stem+'_events'].gt(0)
    stats=pooled.groupby(COHORT,dropna=False).agg(valid_pools=('mean_change','count'),mean_change=('mean_change','mean'),median_change=('mean_change','median'),
        positive_pools=('positive','sum'),negative_pools=('negative','sum'),nearzero_pools=('nearzero','sum'),measured_pools=('pool_id','size'),
        metric_valid_events=('valid_events','sum'),registered_events=('registered_events','sum'),metric_all_registered_events_valid_pools=('fully_valid','sum'),
        mean_absolute_change_over_pools=('mean_absolute_change','mean'),pools_with_native_execution_exception=('has_exception','sum'),
        pools_with_structural_failure=('has_structural_failure','sum'),pools_with_invalid_geometry=('has_invalid_geometry','sum'),
        pools_with_measurement_exception=('has_measurement_exception','sum'))
    q=pooled.groupby(COHORT,dropna=False).mean_change.quantile([.1,.9]).unstack().rename(columns={.1:'p10_change',.9:'p90_change'})
    support=pooled[pooled.valid_events.gt(0)].groupby(COHORT,dropna=False).agg(metric_valid_images=('image','nunique'),metric_valid_buildings=('building','nunique'))
    stats=stats.join(q).join(support)
    stats[['metric_valid_images','metric_valid_buildings']]=stats[['metric_valid_images','metric_valid_buildings']].fillna(0).astype(int)
    stats['positive_fraction']=stats.positive_pools.div(stats.valid_pools.where(stats.valid_pools.gt(0)))
    return stats.reset_index()


def apply_stats(base,stats,f):
    a=align(base,COHORT);b=align(stats,COHORT)
    ix=a.index.intersection(b.index)
    for col in b.columns:
        if col in a:a.loc[ix,col]=b.loc[ix,col]
    a['native_complete_no_valid_metric_pools']=a.native_complete_registered_pools-a.valid_pools
    a['native_complete_unmeasured_pools']=a.native_complete_registered_pools-a.measured_pools
    a['measured_no_valid_metric_pools']=a.measured_pools-a.valid_pools
    a['nonzero_difference_pools']=a.positive_pools+a.negative_pools
    result=a.reset_index()[base.columns]
    result.loc[result.metric.isin(f.PAIRS),['positive_pools','negative_pools','positive_fraction']]=np.nan
    return result


def main():
    sys.path.insert(0,str(SOURCE/'code'));import analyze_execution_funnel as f
    out=OUT/'funnel';out.mkdir(exist_ok=True)
    roles=pd.read_csv(AC/'stage01_capacity/FROZEN_ROLE_PARENT_MAP_ALL_LOBO.csv')
    ks=roles.groupby('method').k.first().astype(int).to_dict()
    a,b=[],[];pids=[]
    for path in sorted((OUT/'metric_shards').glob('*.csv.gz')):
        pids.append(path.name[:-7])
        a.append(cells(pd.read_csv(AC/'stage04_metrics/metric_shards'/path.name,low_memory=False),f,ks))
        b.append(cells(pd.read_csv(path,low_memory=False),f,ks))
    a,b=pd.concat(a,ignore_index=True),pd.concat(b,ignore_index=True)
    old=pd.read_csv(SOURCE/'POOL_DIRECTION_N_M_METRIC_SUPPORT.csv.gz',low_memory=False)
    keys=f.KEYS+['metric']
    parity=compare(old[old.pool_id.isin(pids)],a,keys,'original_funnel_pool_cells')
    ca,cb=changed_rows(a,b,keys);save(ca,out/'POOL_DIRECTION_N_M_AUTOMATIC_CHANGED.csv.gz');save(cb,out/'POOL_DIRECTION_N_M_ASSISTED_PATCH.csv.gz')
    updated=patch(old,b,keys)
    selected=cb[COHORT].drop_duplicates();extra=selected.copy();extra['role_direction']='ALL_CANONICAL_DIRECTIONS'
    selected=pd.concat([selected,extra],ignore_index=True).drop_duplicates()
    stats0,stats1=population(old),population(updated)
    published=pd.read_csv(SOURCE/'CAPACITY_REGISTRATION_EXECUTION_EVALUABILITY_DIRECTION_FUNNEL.csv.gz',low_memory=False)
    target=subset(published,selected,COHORT)
    before,after=apply_stats(target,stats0,f),apply_stats(target,stats1,f)
    parity.extend(compare(target,before,COHORT,'original_funnel_cohort_stats'))
    save(after,out/'CAPACITY_REGISTRATION_EXECUTION_EVALUABILITY_DIRECTION_FUNNEL_PATCH.csv.gz')
    d0,d1=changed_rows(before,after,COHORT)
    save(align(d0,COHORT).add_prefix('automatic_').join(align(d1,COHORT).add_prefix('assisted_')).reset_index(),out/'FUNNEL_CHANGES.csv.gz')
    brief=pd.read_csv(SOURCE/'MAIN_SCALE_FUNNEL_BRIEF.csv')
    briefkey=['method','n','m','metric']
    impacted=after[after.scope.eq('primary')&after.role_direction.eq('ALL_CANONICAL_DIRECTIONS')]
    outbrief=patch(brief,impacted[brief.columns],briefkey)
    save(outbrief,out/'MAIN_SCALE_FUNNEL_BRIEF.csv')
    ba,bb=changed_rows(brief,outbrief,briefkey)
    save(pd.DataFrame(parity),out/'PARITY.csv')
    jsave(out/'FUNNEL_IMPACT_RECEIPT.json',dict(changed_pool_metric_cells=len(cb),changed_population_metric_cells=len(d1),
        main_scale_brief_changed_rows=len(bb),capacity_registration_execution_unchanged=True,
        new_fusions=0,new_scores=0,missing_Q_imputed=False,
        weights='exact XZ block background mean; equal blocks; equal class directions within pooled all-direction row; equal pools',
        patch_keys={'pool':keys,'cohort':COHORT}))
    print('AC funnel complete',len(cb),len(d1),flush=True)


if __name__=='__main__':main()
