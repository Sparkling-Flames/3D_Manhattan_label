"""按图内目标等权接合补充曲线；原范围与新增范围分别保留。"""
import gzip
import sys
import numpy as np
import pandas as pd
from .extend_v21_admitted_spaces_20261029 import OUT, TARGET, read, save, two_payloads
from .prepare_v21_natural_inputs_20261028 import EXT


def two_results(pools, core):
    rows=[];intervals=[];pathrows=[]
    for p,links in two_payloads(pools):
        pid=p['pool_id']
        with gzip.open(TARGET/'two_person_natural256/pools'/(pid+'.json.gz'),'rt',encoding='utf8') as f:
            teams={tuple(r['member_workers']):r for r in __import__('json').load(f)['teams']}
        raw=pd.read_csv(TARGET/'natural_inputs'/(pid+'.csv.gz'),low_memory=False).set_index(['path_id','k'])
        part=[]
        for link in links:
            team=teams[tuple(sorted([link['first'],link['entrant_worker']]))]
            q1=raw.at[(link['path_id'],1),'B8L2'];q3=raw.at[(link['path_id'],3),'B8L2'];q2=team.get('B8L2')
            q2=np.nan if q2 is None else q2
            status=team['score_status'];failure=status in ['no_connection','below_four','fusion_exception']
            assert status in ['complete_conditional','complete','no_connection','below_four','fusion_exception','invalid_floor','invalid_full_geometry','measurement_exception'], ('unclassified k2 status',status)
            part.append(dict(pool_id=pid,path_id=link['path_id'],team_key=team['team_key'],Q1=q1,Q2=q2,Q3=q3,
                delta_1_2=q2-q1,delta_2_3=q3-q2,failure=float(failure),unscoreable=float(pd.isna(q2) and not failure),score_status=status))
        d=pd.DataFrame(part).sort_values('path_id');pathrows.append(d)
        fields=['Q2','delta_1_2','delta_2_3','failure','unscoreable']
        w=core.bootstrap_weights(pid,'new_space256',256,2000,2026102607)
        draws=core.weighted_mean(d[fields].to_numpy(float),w)[0]
        row=dict(p['meta'],k=2,paths=256,unique_teams=d.team_key.nunique())
        for j,c in enumerate(fields):
            row[c]=d[c].mean();row[c+'_valid']=int(d[c].notna().sum())
            intervals.append(dict(pool_id=pid,metric=c,estimate=row[c],valid_paths=row[c+'_valid'],**core.boot_summary(draws[:,j])))
        rows.append(row)
    folder=TARGET/'two_person_natural256'
    pd.concat(pathrows).to_csv(folder/'PAIRED_PATH_RESULTS.csv.gz',index=False)
    pd.DataFrame(rows).to_csv(folder/'IMAGE_RESULTS.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(intervals).to_csv(folder/'IMAGE_INTERVALS.csv',index=False)
    return pd.DataFrame(rows)


def image_weights(d, weighting):
    """A second target cannot give its image a second aggregate vote."""
    counts=d.groupby('image').pool_id.transform('size').to_numpy(float)
    if weighting=='image_equal':return 1/counts/d.image.nunique()
    images=d[['image','building']].drop_duplicates()
    per_building=images.groupby('building').size()
    return 1/counts/d.building.map(per_building).to_numpy(float)/len(per_building)


def main():
    sys.path.insert(0,str(EXT/'analysis_precision26'))
    import precision_core as core
    pools=read(TARGET/'pools/INPUT_SNAPSHOT.json')['images']
    two=two_results(pools,core)
    new=pd.read_csv(TARGET/'natural_analysis/UPDATED_CURVES.csv.gz',low_memory=False)
    new=new[new.cohort.eq('new_space256')].copy();new['support']='other_admitted_target'
    old=pd.read_csv(OUT/'natural_results/NATURAL_CURVES.csv.gz',low_memory=False)
    old=old[old.cohort.isin(['pooled256','new_space256']) & old.condition.eq('manual') & old.layer.isin(['ordinary_manual','doorway_manual'])].copy()
    assert old.pool_id.nunique()==223 and new.pool_id.nunique()==31
    old['support']='original_current_target'
    data=pd.concat([old,new],ignore_index=True)
    metrics=['Q_mean','Q_p10','Q_sd_ddof1','actual_consensus_failure_rate','output_unscoreable_rate']
    # k2 is separately measured; it never changes the frozen natural cache.
    oldtwo=pd.read_csv(OUT/'two_person_natural256/IMAGE_RESULTS.csv')
    for source,frame in [('original_current_target',oldtwo),('other_admitted_target',two)]:
        for r in frame.to_dict('records'):
            mask=data.pool_id.eq(r['pool_id']) & data.k.eq(2)
            data.loc[mask,'Q_mean']=r['Q2']
            data.loc[mask,'actual_consensus_failure_rate']=r['consensus_failure_rate'] if source=='original_current_target' else r['failure']
            data.loc[mask,'output_unscoreable_rate']=r['unscoreable_rate'] if source=='original_current_target' else r['unscoreable']
    data.to_csv(TARGET/'DISPLAY_CURVES.csv.gz',index=False)
    summaries=[]
    rng=np.random.default_rng(2026102907)
    for support in ['original_current_target','other_admitted_target','combined']:
        subset=data if support=='combined' else data[data.support.eq(support)]
        for (condition,layer),d in subset.groupby(['condition','layer']):
            for cutoff in [0,3,6,10,14]:
                selected=d if cutoff==0 else d[d.pool_n.ge(cutoff) & d.k.le(cutoff)]
                for k,g in selected.groupby('k'):
                    for metric in metrics:
                        valid=g[g[metric].notna()]
                        if valid.empty:continue
                        x=valid[metric].to_numpy(float)
                        perimage=valid.groupby(['building','image'])[metric].mean().reset_index()
                        blocks=[z[metric].to_numpy(float) for _,z in perimage.groupby('building')]
                        selected_blocks=rng.integers(0,len(blocks),(2000,len(blocks)))
                        for weighting in ['image_equal','building_equal']:
                            w=image_weights(valid,weighting);estimate=float(w@x)
                            bm=np.array([b.mean() for b in blocks]);bs=np.array([b.sum() for b in blocks]);bn=np.array([len(b) for b in blocks])
                            draws=bm[selected_blocks].mean(axis=1) if weighting=='building_equal' else bs[selected_blocks].sum(axis=1)/bn[selected_blocks].sum(axis=1)
                            lo,hi=np.quantile(draws,[.025,.975]) if len(blocks)>1 else [np.nan,np.nan]
                            summaries.append(dict(support=support,condition=condition,layer=layer,panel='available_at_k' if cutoff==0 else 'fixed_N_ge_'+str(cutoff),k=k,metric=metric,weighting=weighting,estimate=estimate,pools=len(valid),images=valid.image.nunique(),eligible_pools=len(g),missing_pools=len(g)-len(valid),buildings=len(blocks),building95_low=lo,building95_high=hi,uncertainty='building_resampling_fixed_estimated_target_means',target_weighting='equal_targets_within_image'))
    summary=pd.DataFrame(summaries);summary.to_csv(TARGET/'SUMMARY.csv',index=False,encoding='utf-8-sig')
    comparison=[]
    for (condition,layer,k),g in data.groupby(['condition','layer','k']):
        for metric in metrics:
            z=g.groupby(['image','support'])[metric].mean().unstack('support')
            if not {'original_current_target','other_admitted_target'}<=set(z):continue
            z=z.dropna();delta=z.other_admitted_target-z.original_current_target
            comparison.append(dict(condition=condition,layer=layer,k=k,metric=metric,common_images=len(z),original=z.original_current_target.mean(),added=z.other_admitted_target.mean(),delta=delta.mean(),positive_images=int(delta.gt(0).sum()),interpretation='different target and disjoint members; descriptive, not reference-only effect'))
    pd.DataFrame(comparison).to_csv(TARGET/'COMMON_IMAGE_COMPARISON.csv',index=False,encoding='utf-8-sig')
    save('CURVE_CHECKS.json',dict(complete=True,pools=len(pools),records=231,path_prefixes=int(sum(p['meta']['pool_n'] for p in pools)*256),orders=len(pools)*256,k2_pools=len(two),k2_scored_paths=int(two.Q2_valid.sum()),bootstrap=2000,original_manual_pools=223,added_manual_pools=30,added_semi_pools=1,combined_manual_pools=253,original_results_unchanged=True,current_pointer_advanced=False))
    print('curves complete',len(data),'summary',len(summary),flush=True)


if __name__=='__main__':main()
