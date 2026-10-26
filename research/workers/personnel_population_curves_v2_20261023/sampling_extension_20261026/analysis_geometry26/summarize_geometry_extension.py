"""Fixed-support image/building summaries of actual new geometry paths.

Path Monte Carlo precision and resampling of the observed buildings are
separate columns. No geometric distances or new fusion are computed here.
"""
from __future__ import annotations
import argparse,hashlib,json,math
from pathlib import Path
import numpy as np
import pandas as pd
from safe_io import atomic_bytes,install_safe_csv_writer
install_safe_csv_writer()

PRIMARY=['old48','stage1_104','stage2_104','new208','pooled256']
METRICS=['V_floor','V_centroid_h','V_height_h','V_turn5','V_nodes']


def write_json(path,obj):atomic_bytes(path,json.dumps(obj,ensure_ascii=False,indent=2).encode())


def seed_for(*key):return int.from_bytes(hashlib.sha256(json.dumps(['geometry_extension26',2026102605,*key],ensure_ascii=False,separators=(',',':')).encode()).digest()[:8],'little')


def panels(meta):
    out=[]
    for layer in ['ordinary_manual','doorway_manual']:
        m=meta[meta.layer.eq(layer)]
        if not len(m):continue
        minimum=int(m.pool_n.min())
        for n in sorted(set([minimum,20,30,35])):
            a=m[m.pool_n.ge(n)]
            if not len(a):continue
            # A fixed panel is only drawn through its stated lower capacity.
            for difficulty in ['全部',*sorted(a.difficulty.dropna().unique())]:
                chosen=a if difficulty=='全部' else a[a.difficulty.eq(difficulty)]
                if len(chosen):out.append((layer,f'fixed_N_ge_{n}',difficulty,n,chosen))
    return out


def aggregate(g,value,se,replicates,seed):
    """Conditional observed common-image support; no missing weight recycling."""
    y=g[value].to_numpy(float);s=g[se].to_numpy(float);n=len(g)
    if not n:return []
    assert np.isfinite(y).all()
    buildings=sorted(g.building.unique());B=len(buildings)
    means=g.groupby('building',sort=True)[value].mean().reindex(buildings).to_numpy()
    counts=g.groupby('building',sort=True).size().reindex(buildings).to_numpy(float)
    sums=g.groupby('building',sort=True)[value].sum().reindex(buildings).to_numpy()
    draw=np.random.default_rng(seed).multinomial(B,np.ones(B)/B,size=replicates)
    boot_ie=(draw@sums)/(draw@counts)
    boot_be=(draw@means)/B
    result=[]
    for weighting,weights,boot in [('image_equal',np.ones(n)/n,boot_ie),
        ('building_equal',g.building.map({b:1/(B*c) for b,c in zip(buildings,counts)}).to_numpy(float),boot_be)]:
        estimate=float(weights@y)
        se_path=float(np.sqrt(np.sum((weights*s)**2))) if np.isfinite(s).all() else np.nan
        result.append(dict(weighting=weighting,estimate=estimate,
            path_mcse=se_path,path_normal95_low=estimate-1.96*se_path,path_normal95_high=estimate+1.96*se_path,
            building_boot95_low=float(np.quantile(boot,.025)),building_boot95_high=float(np.quantile(boot,.975)),
            building_boot_se=float(np.std(boot,ddof=1)),building_boot_replicates=replicates,building_seed=str(seed),
            common_images=n,common_buildings=B,common_mcse_estimable_images=int(np.isfinite(s).sum()),
            image_sd=float(np.std(y,ddof=1)) if n>1 else np.nan,
            building_mean_min=float(means.min()),building_mean_max=float(means.max()),
            building_mean_sd=float(np.std(means,ddof=1)) if B>1 else np.nan,
            image_positive=int((y>1e-9).sum()),image_negative=int((y< -1e-9).sum()),image_nearzero=int((np.abs(y)<=1e-9).sum()),
            building_positive=int((means>1e-9).sum()),building_negative=int((means< -1e-9).sum()),building_nearzero=int((np.abs(means)<=1e-9).sum()),
            uncertainty_scope='path MC conditional fixed images; building resampling conditional observed paths; pointwise ranges'))
    return result


def main(root,stage,replicates):
    out=root/f'results_stage{stage}';out.mkdir(exist_ok=True)
    precision=pd.read_csv(out/'GEOMETRY_PATH_PRECISION.csv.gz',low_memory=False)
    intervals=pd.read_csv(out/'GEOMETRY_PAIRED_INTERVAL_PRECISION.csv.gz',low_memory=False)
    meta=pd.read_csv(root/'POOL_META.csv');present=set(precision.cohort)
    versions=[v for v in PRIMARY if v in present]
    if stage==1:versions=['old48','stage1_104','pooled152']
    summaries=[];support=[];interval_summary=[];image_intervals=[];building_intervals=[]
    strict_curve=[];strict_support=[]
    full_summaries=[];full_intervals=[];full_images=[]
    for layer,panel,difficulty,max_k,chosen in panels(meta):
        ids=set(chosen.pool_id);base=precision[precision.pool_id.isin(ids)&precision.cohort.isin(versions)&precision.k.le(max_k)]
        # A second view fixes the same estimable images across the complete
        # plotted k range as well as across all compared cohorts. Incomplete
        # images remain in the candidate/status tables; this does not restore
        # qualification or make their full-population endpoint zero.
        expected_k=[k for k in range(1,max_k+1) if k!=2]
        for metric,allmetric in base.groupby('metric',sort=True):
            grid=allmetric.pivot(index='pool_id',columns=['cohort','k'],values='mean').reindex(
                index=chosen.pool_id,columns=pd.MultiIndex.from_product([versions,expected_k],names=['cohort','k']))
            common_whole=set(grid.index[grid.notna().all(axis=1)])
            for pid in chosen.pool_id:
                strict_support.append(dict(layer=layer,panel=panel,difficulty=difficulty,metric=metric,pool_id=pid,
                    common_entire_curve=pid in common_whole,expected_k='|'.join(map(str,expected_k)),required_cohorts='|'.join(versions)))
            for (cohort,k),gg in allmetric[allmetric.pool_id.isin(common_whole)].groupby(['cohort','k'],sort=True):
                if k==2:continue
                for r in aggregate(gg,'mean','mcse',replicates,seed_for(layer,panel,difficulty,'strict_curve',int(k),metric)):
                    strict_curve.append(dict(layer=layer,panel=panel,difficulty=difficulty,k=int(k),metric=metric,cohort=cohort,
                        candidate_images=len(chosen),candidate_buildings=chosen.building.nunique(),
                        image_mcse_median=gg.mcse.median(),image_mcse_p90=gg.mcse.quantile(.9),
                        support_rule='same images estimable at every plotted k and every required cohort',**r))
        for (k,metric),g in base.groupby(['k','metric'],sort=True):
            pivot=g.pivot(index='pool_id',columns='cohort',values='mean').reindex(columns=versions)
            common=set(pivot.index[pivot.notna().all(axis=1)])
            for pid in chosen.pool_id:
                support.append(dict(kind='curve',layer=layer,panel=panel,difficulty=difficulty,k_from=int(k),k_to=int(k),metric=metric,
                    pool_id=pid,common_available=pid in common,required_cohorts='|'.join(versions)))
            for cohort in versions:
                allg=g[g.cohort.eq(cohort)];x=allg[allg.pool_id.isin(common)]
                for r in aggregate(x,'mean','mcse',replicates,seed_for(layer,panel,difficulty,'curve',int(k),metric)):
                    summaries.append(dict(layer=layer,panel=panel,difficulty=difficulty,k=int(k),metric=metric,cohort=cohort,
                        candidate_images=len(chosen),candidate_buildings=chosen.building.nunique(),
                        cohort_estimable_images=int(allg['mean'].notna().sum()),image_mcse_median=x.mcse.median(),image_mcse_p90=x.mcse.quantile(.9),
                        **r))
        ibase=intervals[intervals.pool_id.isin(ids)&intervals.cohort.isin(versions)]
        # All ordinary fixed-N rows keep their original path endpoints and panel.
        # A given interval is available only if every panel image has that k.
        fullbase=ibase[ibase.k_to.eq(ibase.pool_n)&ibase.k_from.le(max_k)&ibase.k_from.isin([1,3,6,10,20,30,35])]
        for (a,metric),g in fullbase.groupby(['k_from','metric'],sort=True):
            pivot=g.pivot(index='pool_id',columns='cohort',values='delta').reindex(columns=versions)
            common=set(pivot.index[pivot.notna().all(axis=1)])
            for pid in chosen.pool_id:
                support.append(dict(kind='interval_actual_full',layer=layer,panel=panel,difficulty=difficulty,k_from=int(a),k_to=-1,metric=metric,
                    pool_id=pid,common_available=pid in common,required_cohorts='|'.join(versions)))
            for cohort in versions:
                allg=g[g.cohort.eq(cohort)];x=allg[allg.pool_id.isin(common)]
                full_images.extend(dict(panel=panel,panel_difficulty=difficulty,**r) for r in x.to_dict('records'))
                for r in aggregate(x,'delta','mcse',replicates,seed_for(layer,panel,difficulty,'interval_actual_full',int(a),metric)):
                    full_intervals.append(dict(layer=layer,panel=panel,difficulty=difficulty,k_from=int(a),target='actual_full',metric=metric,cohort=cohort,
                        candidate_images=len(chosen),candidate_buildings=chosen.building.nunique(),cohort_estimable_images=int(allg.delta.notna().sum()),
                        common_same_endpoint_images=int(x.k_from.eq(x.k_to).sum()),**r))
        fullbase=precision[precision.pool_id.isin(ids)&precision.cohort.isin(versions)&precision.k.eq(precision.pool_n)]
        for metric,g in fullbase.groupby('metric',sort=True):
            pivot=g.pivot(index='pool_id',columns='cohort',values='mean').reindex(columns=versions)
            common=set(pivot.index[pivot.notna().all(axis=1)])
            for cohort in versions:
                allg=g[g.cohort.eq(cohort)];x=allg[allg.pool_id.isin(common)]
                for r in aggregate(x,'mean','mcse',replicates,seed_for(layer,panel,difficulty,'actual_full',metric)):
                    full_summaries.append(dict(layer=layer,panel=panel,difficulty=difficulty,target='actual_full',metric=metric,cohort=cohort,
                        candidate_images=len(chosen),candidate_buildings=chosen.building.nunique(),cohort_estimable_images=int(allg['mean'].notna().sum()),**r))
        ibase=ibase[ibase.k_to.le(max_k)&ibase.k_from.lt(ibase.k_to)]
        for (a,b,metric),g in ibase.groupby(['k_from','k_to','metric'],sort=True):
            pivot=g.pivot(index='pool_id',columns='cohort',values='delta').reindex(columns=versions)
            common=set(pivot.index[pivot.notna().all(axis=1)])
            for pid in chosen.pool_id:
                support.append(dict(kind='interval',layer=layer,panel=panel,difficulty=difficulty,k_from=int(a),k_to=int(b),metric=metric,
                    pool_id=pid,common_available=pid in common,required_cohorts='|'.join(versions)))
            for cohort in versions:
                allg=g[g.cohort.eq(cohort)];x=allg[allg.pool_id.isin(common)]
                for r in aggregate(x,'delta','mcse',replicates,seed_for(layer,panel,difficulty,'interval',int(a),int(b),metric)):
                    interval_summary.append(dict(layer=layer,panel=panel,difficulty=difficulty,k_from=int(a),k_to=int(b),metric=metric,cohort=cohort,
                        candidate_images=len(chosen),candidate_buildings=chosen.building.nunique(),cohort_estimable_images=int(allg.delta.notna().sum()),**r))
                if panel=='fixed_N_ge_30' and difficulty=='全部' and metric=='V_floor' and (a,b) in [(3,6),(6,10),(10,20),(20,30)]:
                    image_intervals.extend(x.to_dict('records'))
                    for building,bg in x.groupby('building'):
                        building_intervals.append(dict(layer=layer,panel=panel,cohort=cohort,k_from=a,k_to=b,building=building,
                            images=len(bg),delta=bg.delta.mean(),positive_images=int(bg.delta.gt(1e-9).sum()),
                            negative_images=int(bg.delta.lt(-1e-9).sum()),nearzero_images=int(bg.delta.abs().le(1e-9).sum())))
    pd.DataFrame(summaries).to_csv(out/'GEOMETRY_FIXED_SUPPORT_CURVES.csv.gz',index=False)
    pd.DataFrame(strict_curve).to_csv(out/'GEOMETRY_STRICT_COMMON_CURVE_SUMMARY.csv.gz',index=False)
    pd.DataFrame(strict_support).to_csv(out/'GEOMETRY_STRICT_COMMON_CURVE_SUPPORT.csv.gz',index=False)
    pd.DataFrame(interval_summary).to_csv(out/'GEOMETRY_FIXED_SUPPORT_INTERVALS.csv.gz',index=False)
    pd.DataFrame(support).to_csv(out/'GEOMETRY_COMMON_IMAGE_SUPPORT.csv.gz',index=False)
    pd.DataFrame(image_intervals).to_csv(out/'GEOMETRY_FIXED157_INTERVAL_IMAGE.csv.gz',index=False)
    pd.DataFrame(building_intervals).to_csv(out/'GEOMETRY_FIXED157_INTERVAL_BUILDING.csv',index=False)
    pd.DataFrame(full_summaries).to_csv(out/'GEOMETRY_ACTUAL_FULL_SUMMARY.csv',index=False)
    pd.DataFrame(full_intervals).to_csv(out/'GEOMETRY_TO_ACTUAL_FULL_SUMMARY.csv',index=False)
    pd.DataFrame(full_images).to_csv(out/'GEOMETRY_TO_ACTUAL_FULL_IMAGE.csv.gz',index=False)
    # Point estimates and precision in exact finite margins are source-qualified.
    prior=root.parent/'prior_recovered/research/workers/personnel_population_curves_v2_20261023/sampling_precision_20261025'
    exact=pd.read_csv(prior/'analysis_geometry/results/EXACT_GEOMETRY_MARGINALS.csv')
    merged=precision.merge(exact[['pool_id','k','metric','exact_kind','finite_team_space','exact_mean','exact_valid_teams','valid_fraction']],on=['pool_id','k','metric'],how='inner',validate='many_to_one')
    merged['error_from_exact']=merged['mean']-merged.exact_mean
    merged['absolute_error_from_exact']=merged.error_from_exact.abs()
    merged['pointwise_normal95_covers_exact']=np.where(merged.mcse.notna()&merged.exact_mean.notna(),merged.absolute_error_from_exact.le(1.96*merged.mcse+1e-12),np.nan)
    merged['exact_source']='20261025 frozen finite catalogue; no new exact geometry measurement'
    merged.to_csv(out/'GEOMETRY_SAMPLE_VS_EXACT.csv.gz',index=False)
    exact_summary=[]
    baseline=merged[merged.cohort.eq('old48')]
    for cohort in [v for v in versions if v!='old48']:
        z=baseline.merge(merged[merged.cohort.eq(cohort)],on=['pool_id','k','metric'],suffixes=('_old','_new'),validate='one_to_one')
        for (layer,kind,metric),g in z.groupby(['layer_old','exact_kind_old','metric']):
            x=g[g.error_from_exact_old.notna()&g.error_from_exact_new.notna()]
            r=dict(cohort=cohort,layer=layer,exact_kind=kind,metric=metric,candidate_pool_k=len(g),common_pool_k=len(x),
                common_images=x.pool_id.nunique(),common_buildings=x.building_old.nunique())
            for label in ['old','new']:
                e=x['error_from_exact_'+label]
                r.update({label+'_mae':e.abs().mean(),label+'_rmse':np.sqrt(e.pow(2).mean()),label+'_abs_error_p90':e.abs().quantile(.9),label+'_abs_error_max':e.abs().max()})
            exact_summary.append(r)
    pd.DataFrame(exact_summary).to_csv(out/'GEOMETRY_EXACT_COMMON_SUPPORT_ACCURACY.csv',index=False)
    # Independent-batch and enlarged-sample differences across the entire curve.
    comparisons=[('old48','new208'),('stage1_104','stage2_104'),('old48','pooled256')]
    if stage==1:comparisons=[('old48','stage1_104'),('old48','pooled152')]
    compare=[];whole=[]
    for left,right in comparisons:
        a=precision[precision.cohort.eq(left)];b=precision[precision.cohort.eq(right)]
        x=a.merge(b,on=['pool_id','k','metric'],suffixes=('_left','_right'),validate='one_to_one')
        x['comparison']=left+'_vs_'+right
        x['estimate_delta']=x['mean_right']-x['mean_left']
        x['absolute_estimate_delta']=x.estimate_delta.abs()
        x['independent_batches']=left=='old48' and right in ['stage1_104','new208'] or left=='stage1_104' and right=='stage2_104'
        x['independent_difference_mcse']=np.where(x.independent_batches,np.sqrt(x.mcse_left**2+x.mcse_right**2),np.nan)
        compare.append(x)
        for (pid,metric),g in x.groupby(['pool_id','metric']):
            valid=g[g.k.ge(3)&g.estimate_delta.notna()]
            if not len(valid):continue
            largest=valid.loc[valid.absolute_estimate_delta.idxmax()]
            whole.append(dict(pool_id=pid,comparison=left+'_vs_'+right,metric=metric,image=largest.image_left,building=largest.building_left,
                layer=largest.layer_left,difficulty=largest.difficulty_left,pool_n=largest.pool_n_left,
                common_k_count=len(valid),possible_k_count=int(largest.pool_n_left)-2,
                max_absolute_curve_difference=valid.absolute_estimate_delta.max(),max_difference_k=int(largest.k),
                signed_change_at_max=float(largest.estimate_delta),rms_curve_difference=float(np.sqrt(valid.estimate_delta.pow(2).mean())),
                mean_absolute_curve_difference=valid.absolute_estimate_delta.mean(),
                old_or_left_max_mcse=valid.mcse_left.max(),new_or_right_max_mcse=valid.mcse_right.max(),
                interpretation='descriptive whole-curve difference; not a simultaneous confidence bound'))
    all_compare=pd.concat(compare,ignore_index=True)
    all_compare.to_csv(out/'GEOMETRY_BATCH_POINT_COMPARISONS.csv.gz',index=False)
    pd.DataFrame(whole).to_csv(out/'GEOMETRY_WHOLE_CURVE_REPLICATION.csv',index=False)
    # The difference itself, rather than subtracting separately resampled CIs.
    # Its image support is the same all-primary-cohort support used above.
    support_df=pd.DataFrame(support);batch_summary=[];precision_changes=[]
    for layer,panel,difficulty,max_k,chosen in panels(meta):
        common_keys=support_df[(support_df.kind=='curve')&(support_df.layer==layer)&(support_df.panel==panel)&
            (support_df.difficulty==difficulty)&support_df.common_available][['pool_id','k_from','metric']].rename(columns={'k_from':'k'})
        selected=all_compare[all_compare.pool_id.isin(chosen.pool_id)&all_compare.k.le(max_k)].merge(common_keys,on=['pool_id','k','metric'],validate='many_to_one')
        for (comparison,k,metric),g in selected.groupby(['comparison','k','metric'],sort=True):
            gg=g.copy();gg['building']=gg.building_left
            for r in aggregate(gg,'estimate_delta','independent_difference_mcse',replicates,seed_for(layer,panel,difficulty,'batch_change',comparison,int(k),metric)):
                batch_summary.append(dict(layer=layer,panel=panel,difficulty=difficulty,k=int(k),metric=metric,comparison=comparison,
                    candidate_images=len(chosen),candidate_buildings=chosen.building.nunique(),
                    independent_batches=bool(g.independent_batches.all()),**r))
            se=g[g.mcse_left.notna()&g.mcse_right.notna()]
            ratio=se[se.mcse_left.gt(0)]
            precision_changes.append(dict(layer=layer,panel=panel,difficulty=difficulty,k=int(k),metric=metric,comparison=comparison,
                candidate_images=len(chosen),common_point_images=len(g),common_mcse_images=len(se),
                left_mcse_median=se.mcse_left.median(),right_mcse_median=se.mcse_right.median(),
                left_mcse_p90=se.mcse_left.quantile(.9),right_mcse_p90=se.mcse_right.quantile(.9),
                mcse_ratio_median=(ratio.mcse_right/ratio.mcse_left).median(),positive_left_mcse_images=len(ratio),
                left_zero_mcse_images=int(se.mcse_left.eq(0).sum()),right_zero_mcse_images=int(se.mcse_right.eq(0).sum()),
                left_zero_right_positive_mcse_images=int((se.mcse_left.eq(0)&se.mcse_right.gt(0)).sum()),
                absolute_point_change_median=g.absolute_estimate_delta.median(),absolute_point_change_p90=g.absolute_estimate_delta.quantile(.9),
                absolute_point_change_max=g.absolute_estimate_delta.max()))
    pd.DataFrame(batch_summary).to_csv(out/'GEOMETRY_COMMON_SUPPORT_BATCH_CHANGES.csv.gz',index=False)
    pd.DataFrame(precision_changes).to_csv(out/'GEOMETRY_SINGLE_IMAGE_PRECISION_CHANGES.csv.gz',index=False)
    # Preserved original48 computation is checked only where actually repeated.
    old=precision[precision.cohort.eq('old48')]
    saved=pd.read_csv(prior/'analysis_geometry/results/GEOMETRY_PATH_PRECISION.csv.gz')
    saved=saved[saved.cohort.eq('combined48')]
    check=old.merge(saved,on=['pool_id','k','metric'],suffixes=('_new','_saved'),validate='one_to_one')
    value_difference=(check['mean_new']-check['mean_saved']).abs()
    se_difference=(check.mcse_new-check.mcse_saved).abs()
    assert (check['mean_new'].isna()==check['mean_saved'].isna()).all()
    assert (check.mcse_new.isna()==check.mcse_saved.isna()).all()
    assert value_difference.max()<1e-11 and se_difference.max()<1e-11
    receipt=dict(stage=stage,source_commit='b9bcec809fbaec8ab055931a1abb7baa5db44dac',summary_curve_rows=len(summaries),
        interval_rows=len(interval_summary),image_support_rows=len(support),building_bootstrap_replicates=replicates,
        baseline48_common_metric_rows=len(check),baseline48_max_point_difference=float(value_difference.max()),
        baseline48_max_mcse_difference=float(se_difference.max()),new_geometry_or_fusion_calls=0,
        exact_anchors='reused 20261025 exact geometry catalogue',common_support_required_cohorts=versions)
    write_json(out/'SUMMARY_RECEIPT.json',receipt);print(json.dumps(receipt,ensure_ascii=False),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--stage',type=int,choices=[1,2],default=2);p.add_argument('--replicates',type=int,default=2000)
    a=p.parse_args();main(a.root.resolve(),a.stage,a.replicates)
