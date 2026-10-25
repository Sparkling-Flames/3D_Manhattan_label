#!/usr/bin/env python3
"""Readable tables from completed natural precision results; no new sampling."""
from pathlib import Path
import argparse
import numpy as np
import pandas as pd
from analyze_new_natural_precision import save, ZERO_TOL

PANELS={'fixed_N_ge_20':['3_to_6','6_to_10','10_to_20'],
        'fixed_N_ge_30':['20_to_30','30_to_full'],
        'fixed_N_ge_35':['30_to_35']}


def strata(d):
    for layer,g in d.groupby('layer'):
        yield layer,'全部' if layer=='ordinary_manual' else '单列',g
        if layer=='ordinary_manual':
            for diff,h in g.groupby('difficulty'):yield layer,diff,h


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True)
    ap.add_argument('--focus',type=Path,required=True);a=ap.parse_args();b=a.root
    s=pd.read_csv(b/'NATURAL_FIXED_SUPPORT_STABILITY.csv.gz',low_memory=False)
    key=s[s.domain.eq('balanced_all')&s.kind.eq('interval')&s.metric.isin([
        'marginal_Q_delta','paired_Q_delta','Q_p10_delta','Q_sd_delta','failure_delta','paired_D10_delta','paired_Q_loss_gt5_rate'])]
    key=pd.concat([key[key.panel.eq(panel)&key.position.isin(names)] for panel,names in PANELS.items()])
    save(key,b/'KEY_NATURAL_INTERVAL_RESULTS.csv')
    f=pd.read_csv(a.focus);focus=set(f.loc[f.focus_selected,'pool_id'])
    x=pd.read_csv(b/'NATURAL_POOL_K_BATCH_PRECISION.csv.gz')
    rows=[]
    for domain in ['balanced_all','old_noise_focus']:
        d=x[x.pool_id.isin(focus)] if domain=='old_noise_focus' else x[x.version.ne('focus96')]
        for threshold,ks in [(20,[1,3,4,6,10,20]),(30,[20,30]),(35,[30,34,35])]:
            h=d[d.pool_n.ge(threshold)&d.k.isin(ks)]
            for layer,diff,g in strata(h):
                for (version,k),z in g.groupby(['version','k']):
                    qse=z.Q_mean_MCSE_analytic;p10hw=(z.Q_p10_boot95_high-z.Q_p10_boot95_low)/2
                    goodq=qse.notna();goodp=p10hw.notna();qpass=qse.le(1)&goodq;ppass=p10hw.le(2)&goodp
                    rows.append(dict(domain=domain,panel=f'fixed_N_ge_{threshold}',layer=layer,difficulty=diff,version=version,k=int(k),
                        available_images=len(z),available_buildings=z.building.nunique(),quality_images=z.Q_mean.notna().sum(),
                        mean_MCSE_estimable_images=int(goodq.sum()),mean_MCSE_median=qse.median(),mean_MCSE_p90=qse.quantile(.9),
                        mean_MCSE_le1_images=int(qpass.sum()),mean_MCSE_le1_fraction_all_images=float(qpass.mean()),
                        mean_MCSE_le1_fraction_estimable=float(qpass[goodq].mean()) if goodq.any() else np.nan,
                        P10_empirical_interval_estimable_images=int(goodp.sum()),P10_empirical95_halfwidth_median=p10hw.median(),
                        P10_empirical95_halfwidth_p90=p10hw.quantile(.9),P10_halfwidth_le2_images=int(ppass.sum()),
                        P10_halfwidth_le2_fraction_all_images=float(ppass.mean()),
                        P10_halfwidth_le2_fraction_estimable=float(ppass[goodp].mean()) if goodp.any() else np.nan,
                        all_attempted_paths=int(z.paths_attempted.sum()),scoreable_paths=int(z.quality_valid_paths.sum()),
                        failure_paths=int(z.failure_paths.sum()),failure_rate_image_equal=z.failure_rate.mean(),
                        full_pool_images=int(z.k.eq(z.pool_n).sum()),
                        caution='P10 bootstrap reach is empirical, not a guarantee against unseen or misweighted modes; full-pool MC error is zero by construction'))
    save(pd.DataFrame(rows),b/'KEY_PRECISION_BY_K.csv')
    c=pd.read_csv(b/'NATURAL_FIXED_SUPPORT_BATCH_COMPARISONS.csv.gz',low_memory=False)
    c=c[c.domain.eq('balanced_all')&c.kind.eq('curve')&c.weighting.eq('image_equal')&c.resampling.eq('path_MC_fixed_images')]
    keep={"fixed_N_ge_20":['1','3','4','6','10','20'],"fixed_N_ge_30":['20','30'],"fixed_N_ge_35":['30','34','35']}
    c=pd.concat([c[c.panel.eq(panel)&c.position.astype(str).isin(ks)] for panel,ks in keep.items()])
    save(c,b/'KEY_BATCH_REPLICATION_CURVE_DIFFS.csv')
    # Independent old24 versus new24 signs of the same within-path-size effect.
    d=pd.read_csv(b/'NATURAL_POOL_INTERVAL_BATCH_POINTS.csv.gz')
    signrows=[]
    for panel,names in PANELS.items():
        threshold=int(panel.rsplit('_',1)[1]);h=d[d.pool_n.ge(threshold)&d.interval.isin(names)&d.version.isin(['old24','new24','pooled48'])]
        for layer,diff,g in strata(h):
            for name,z in g.groupby('interval'):
                w=z.pivot(index='pool_id',columns='version',values='marginal_Q_delta').dropna(subset=['old24','new24','pooled48'])
                old=np.select([w.old24>ZERO_TOL,w.old24 < -ZERO_TOL],[1,-1],default=0)
                new=np.select([w.new24>ZERO_TOL,w.new24 < -ZERO_TOL],[1,-1],default=0)
                flip=(old*new==-1);same_nonzero=(old==new)&(old!=0);zero=(old==0)&(new==0)
                available=z.pool_id.nunique()
                signrows.append(dict(panel=panel,layer=layer,difficulty=diff,interval=name,available_images=available,
                    common_quality_images=len(w),common_buildings=z[z.pool_id.isin(w.index)].building.nunique(),
                    same_nonzero_direction_images=int(same_nonzero.sum()),both_zero_images=int(zero.sum()),
                    opposite_direction_images=int(flip.sum()),one_side_zero_images=int(((old==0)^(new==0)).sum()),
                    opposite_direction_fraction=float(flip.mean()) if len(w) else np.nan,
                    opposite_cases_median_max_absolute_effect=float(np.maximum(abs(w.old24[flip]),abs(w.new24[flip])).median()) if flip.any() else np.nan,
                    mean_old24=w.old24.mean(),mean_new24=w.new24.mean(),mean_pooled48=w.pooled48.mean(),
                    numerical_zero_tolerance=ZERO_TOL,
                    evidence='independent permutations on the same frozen images/pools; not external images/buildings'))
    save(pd.DataFrame(signrows),b/'KEY_INTERVAL_SIGN_REPLICATION.csv')
    e=pd.read_csv(b/'EXACT_ANCHOR_BATCH_ACCURACY.csv.gz')
    exrows=[]
    for layer in ['ordinary_manual','doorway_manual']:
        for boundary,mask in [('k1',e.k.eq(1)),('Nminus1',e.k.eq(e.pool_n-1)),('full',e.k.eq(e.pool_n))]:
            for metric in ['Q_mean','Q_p10','Q_sd_ddof1','failure_rate']:
                g=e[mask&e.layer.eq(layer)&e.metric.eq(metric)&e.version.isin(['old24','new24','pooled48'])]
                common=g.pivot(index='pool_id',columns='version',values='absolute_error').dropna().index
                for version in ['old24','new24','pooled48']:
                    z=g[g.pool_id.isin(common)&g.version.eq(version)];err=z.error.to_numpy();ab=np.abs(err)
                    exrows.append(dict(layer=layer,boundary=boundary,metric=metric,version=version,images=len(z),buildings=z.building.nunique(),
                        mean_error=np.mean(err),MAE=np.mean(ab),median_abs=np.median(ab),p90_abs=np.quantile(ab,.9),
                        rmse=np.sqrt(np.mean(err*err)),within1=float((ab<=1).mean()) if metric.startswith('Q_') else np.nan,
                        within2=float((ab<=2).mean()) if metric.startswith('Q_') else np.nan,
                        units='Q points' if metric.startswith('Q_') else 'failure probability fraction',
                        reference='complete finite marginal linear P10; not every P10 reference difference is pure MC error' if metric=='Q_p10' else 'exact finite marginal; population SD ddof0'))
    save(pd.DataFrame(exrows),b/'KEY_EXACT_ANCHOR_ACCURACY.csv')
    print('saved readable natural interval, precision, replication, sign, and finite-anchor tables; no additional sampling')


if __name__=='__main__':main()
