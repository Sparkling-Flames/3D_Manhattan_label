#!/usr/bin/env python3
"""Compact, explicitly scoped report tables from actual completed analyses."""
from pathlib import Path
import argparse,json
import numpy as np
import pandas as pd


def save(frame,path):
    frame.to_csv(path,index=False,encoding='utf-8-sig')


def run(root):
    nd=root/'analysis_precision/new_results';out=root/'key_tables';out.mkdir(exist_ok=True)
    d=pd.read_csv(nd/'NATURAL_FIXED_SUPPORT_STABILITY.csv.gz',low_memory=False)
    keep=d[(d.domain=='balanced_all')&(d.weighting=='image_equal')].copy()
    wanted=[('fixed_N_ge_20','3_to_6'),('fixed_N_ge_20','6_to_10'),('fixed_N_ge_20','10_to_20'),
            ('fixed_N_ge_30','20_to_30'),('fixed_N_ge_30','30_to_full'),('fixed_N_ge_35','30_to_35')]
    intervals=pd.concat([keep[(keep.panel==p)&(keep.position.astype(str)==s)&(keep.kind=='interval')] for p,s in wanted])
    save(intervals,out/'T01_FIXED_SUPPORT_PERSON_COUNT_CHANGES.csv')
    curves=keep[(keep.kind=='curve')&(keep.panel.isin(['fixed_N_ge_20','fixed_N_ge_30','fixed_N_ge_35','relative_pool_endpoints']))]
    save(curves,out/'T02_FIXED_SUPPORT_CURVE_LEVELS.csv')
    changes=pd.read_csv(nd/'NATURAL_FIXED_SUPPORT_BATCH_COMPARISONS.csv.gz',low_memory=False)
    save(changes[(changes.domain=='balanced_all')&(changes.weighting=='image_equal')],out/'T03_OLD_NEW_COMMON_IMAGE_COMPARISON.csv')
    q=pd.read_csv(nd/'PRECISION_TARGET_REACH.csv.gz',low_memory=False)
    rows=[]
    for layer in ['ordinary_manual','doorway_manual']:
        diffs=['全部','简单','中等','困难'] if layer=='ordinary_manual' else ['单列']
        for threshold in [6,20,30,35]:
            for diff in diffs:
                g=q[(q.layer==layer)&(q.pool_n>=threshold)&(q.k<=threshold)]
                if diff in ['简单','中等','困难']:g=g[g.difficulty==diff]
                for (version,k),h in g.groupby(['version','k']):
                    if k not in [1,3,4,6,10,20,30,35]:continue
                    ok=h.Q_mean_MCSE_analytic.notna();p=h.p10_boot95_halfwidth.notna()
                    rows.append(dict(layer=layer,difficulty=diff,panel=f'fixed_N_ge_{threshold}',version=version,k=k,
                        candidate_images=len(h),candidate_buildings=h.building.nunique(),
                        mean_uncertainty_available_images=int(ok.sum()),P10_uncertainty_available_images=int(p.sum()),
                        mean_MCSE_median=h.Q_mean_MCSE_analytic.median(),mean_MCSE_P90=h.Q_mean_MCSE_analytic.quantile(.9),
                        mean_MCSE_le1_images=int(h.mean_MCSE_le1.sum()),
                        mean_MCSE_le1_fraction_available=h.loc[ok,'mean_MCSE_le1'].mean(),
                        P10_empirical95_halfwidth_median=h.p10_boot95_halfwidth.median(),
                        P10_empirical95_halfwidth_P90=h.p10_boot95_halfwidth.quantile(.9),
                        P10_halfwidth_le2_images=int(h.p10_boot95_halfwidth_le2.sum()),
                        P10_halfwidth_le2_fraction_available=h.loc[p,'p10_boot95_halfwidth_le2'].mean(),
                        design_domain='old_noise_focus_only' if version=='focus96' else 'balanced_all'))
    save(pd.DataFrame(rows),out/'T04_SINGLE_IMAGE_PRECISION_REACH.csv')
    # Focused images are compared to their OWN old24/pooled48 observations.
    focus_ids=set(q.loc[q.version.eq('focus96'),'pool_id'])
    focused=q[q.pool_id.isin(focus_ids)].copy();frows=[]
    for keys,h in focused.groupby(['layer','difficulty','version','k']):
        if keys[3] not in [1,3,4,6,10,20,30,35]:continue
        frows.append(dict(zip(['layer','difficulty','version','k'],keys))|dict(
            candidate_images=len(h),candidate_buildings=h.building.nunique(),
            mean_uncertainty_available_images=int(h.Q_mean_MCSE_analytic.notna().sum()),
            P10_uncertainty_available_images=int(h.p10_boot95_halfwidth.notna().sum()),
            mean_MCSE_median=h.Q_mean_MCSE_analytic.median(),mean_MCSE_P90=h.Q_mean_MCSE_analytic.quantile(.9),
            P10_empirical95_halfwidth_median=h.p10_boot95_halfwidth.median(),
            mean_MCSE_le1_images=int(h.mean_MCSE_le1.sum()),P10_halfwidth_le2_images=int(h.p10_boot95_halfwidth_le2.sum()),
            design_domain='same_fixed_old_noise_focus_pools'))
    save(pd.DataFrame(frows),out/'T04B_FOCUS_MATCHED_SINGLE_IMAGE_PRECISION.csv')
    e=pd.read_csv(nd/'EXACT_ANCHOR_BATCH_ACCURACY.csv.gz',low_memory=False)
    rows=[]
    for keys,g in e.groupby(['layer','version','exact_kind','metric']):
        good=g.error.notna();h=g[good]
        cov=h.exact_reference_inside_empirical_bootstrap_interval.dropna()
        rows.append(dict(zip(['layer','version','exact_kind','metric'],keys))|dict(
            candidate_rows=len(g),finite_rows=len(h),images=h.pool_id.nunique(),buildings=h.building.nunique(),
            mean_signed_error=h.error.mean(),MAE=h.absolute_error.mean(),median_absolute_error=h.absolute_error.median(),
            P90_absolute_error=h.absolute_error.quantile(.9),RMSE=np.sqrt(np.mean(h.error**2)),
            bootstrap_coverage_available_rows=len(cov),empirical95_coverage_fraction=cov.astype(str).str.lower().eq('true').mean()))
    save(pd.DataFrame(rows),out/'T05_EXACT_FINITE_TRUTH_ACCURACY.csv')
    p=pd.read_csv(root/'analysis_policy/results/POLICY_PRECISION_SUMMARY.csv')
    save(p[(p.weighting=='image_equal')&(p.phase.isin(['early_3_to_half','low_3_to_6']))],out/'T06_PRIORITY_POLICY_PRECISION.csv')
    ip=pd.read_csv(root/'analysis_policy/results/POLICY_INDEPENDENT_BATCH_AGREEMENT.csv')
    rows=[]
    for (policy,phase),g in ip.groupby(['policy','phase']):
        for diff in ['全部','简单','中等','困难']:
            h=g if diff=='全部' else g[g.difficulty==diff]
            h=h[h.paired_Q_delta_old.notna()&h.paired_Q_delta_new.notna()]
            old=h.paired_Q_delta_old.to_numpy();new=h.paired_Q_delta_new.to_numpy()
            a=np.sign(np.where(abs(old)<=1e-9,0,old));b=np.sign(np.where(abs(new)<=1e-9,0,new))
            rows.append(dict(policy=policy,phase=phase,difficulty=diff,common_images=len(h),buildings=h.building.nunique(),
                old_Q_delta=old.mean() if len(h) else np.nan,new_Q_delta=new.mean() if len(h) else np.nan,
                mean_absolute_change=np.mean(abs(new-old)) if len(h) else np.nan,
                both_positive=int(((a>0)&(b>0)).sum()),both_negative=int(((a<0)&(b<0)).sum()),both_nearzero=int(((a==0)&(b==0)).sum()),
                opposite_nonzero=int((a*b<0).sum()),one_sided=int(((a==0)^(b==0)).sum()),
                same_nonzero_fraction=(a*b>0).mean() if len(h) else np.nan))
    save(pd.DataFrame(rows),out/'T07_POLICY_INDEPENDENT_BATCH_DIRECTION.csv')
    exact=pd.read_csv(nd/'EXACT_FINITE_MARGINAL_STATISTICS.csv')
    failed=exact[(exact.exact_kind=='leave_one_out')&(exact.actual_failure_teams>0)]
    save(failed,out/'T08_EXACT_LEAVE_ONE_OUT_FAILURES.csv')
    f=e[(e.metric=='failure_rate')&(e.exact_kind=='leave_one_out')].copy()
    save(f,out/'T09_LEAVE_ONE_OUT_FAILURE_SAMPLING.csv')
    fs=[]
    for (layer,version),g in f.groupby(['layer','version']):
        h=g[g.exact_value.notna()&g.estimate.notna()]
        positive=h.exact_value.gt(0)
        fs.append(dict(layer=layer,version=version,images=len(h),buildings=h.building.nunique(),
            exact_failure_present_images=int(positive.sum()),
            sampled_zero_despite_exact_failure=int((positive&h.estimate.eq(0)).sum()),
            exact_failure_rate_image_equal=h.exact_value.mean(),sampled_failure_rate_image_equal=h.estimate.mean(),
            mean_absolute_error=h.absolute_error.mean()))
    save(pd.DataFrame(fs),out/'T09B_FAILURE_SAMPLING_SUMMARY.csv')
    components=pd.read_csv(nd/'NATURAL_COMPONENT_COMMON_SUPPORT_COMPARISONS.csv.gz')
    save(components[(components.domain=='balanced_all')&(components.weighting=='image_equal')&
        (components.panel=='fixed_N_ge_30')&(components.k.isin([3,10,20,30]))&
        components.component.isin(['B8_floor_block','B8_direction_block','B8_height_block','iou_2d','S_bottom_deg','Hmean'])],
        out/'T10_QUALITY_COMPONENT_COMMON_SUPPORT.csv')
    note=dict(tables=[f.name for f in sorted(out.glob('T*.csv'))],
        description='Derived from saved natural and policy analysis tables; no additional fusion or selection.',
        source_commit='40d0fe62dc62f6f6c12723af10195b7abb7bc9fe',
        caution='T04 focus96 is the old-noise-selected subset. Compare it only against the same focus pools, not all-image old24/pooled48 rows.',
        precision='MCSE is one standard error, not a 95 percent half-width. P10 empirical interval is accompanied by rank bounds in the detailed table.')
    (out/'KEY_TABLE_RECEIPT.json').write_text(json.dumps(note,ensure_ascii=False,indent=2))
    print(json.dumps(note,ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);run(p.parse_args().root)
