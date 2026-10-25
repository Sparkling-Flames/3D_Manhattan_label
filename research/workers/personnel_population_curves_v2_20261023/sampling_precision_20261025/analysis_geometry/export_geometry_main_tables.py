"""Export fixed-image geometry statements from the already-computed path results.

No fusion, geometric-distance calculation, seed selection or bootstrap occurs.
The building distribution is descriptive and is not a confidence interval.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
from safe_io import install_safe_csv_writer
install_safe_csv_writer()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--results', required=True)
    args = ap.parse_args()
    p = Path(args.results)
    d = pd.read_csv(p / 'GEOMETRY_PAIRED_INTERVAL_PRECISION.csv.gz')
    pairs = {(3, 6), (6, 10), (10, 20), (20, 30)}
    d = d[d.layer.eq('ordinary_manual') & d.pool_n.ge(30)
          & d.cohort.isin(['old24', 'new24', 'combined48'])
          & d.metric.eq('V_floor')]
    d = d[[tuple(x) in pairs for x in d[['k_from', 'k_to']].to_numpy()]].copy()
    d.to_csv(p / 'GEOMETRY_FIXED157_INTERVAL_IMAGE.csv', index=False)
    rows = []
    for key, g in d.groupby(['cohort', 'k_from', 'k_to', 'building']):
        good = g[g.delta.notna()]
        rows.append(dict(cohort=key[0], k_from=key[1], k_to=key[2], building=key[3],
                         candidate_images=len(g), valid_images=len(good),
                         delta=good.delta.mean(),
                         positive_images=int((good.delta > 1e-9).sum()),
                         negative_images=int((good.delta < -1e-9).sum()),
                         nearzero_images=int((good.delta.abs() <= 1e-9).sum())))
    b = pd.DataFrame(rows)
    b.to_csv(p / 'GEOMETRY_FIXED157_INTERVAL_BUILDING.csv', index=False)
    s = pd.read_csv(p / 'GEOMETRY_INTERVAL_MC_SUMMARY.csv')
    s = s[s.layer.eq('ordinary_manual') & s.minimum_pool_n.eq(30)
          & s.difficulty.eq('ALL') & s.metric.eq('V_floor')
          & s.cohort.isin(['old24', 'new24', 'combined48'])]
    s = s[[tuple(x) in pairs for x in s[['k_from', 'k_to']].to_numpy()]].copy()
    rows = []
    for key, g in b.groupby(['cohort', 'k_from', 'k_to']):
        x = g.delta.dropna()
        rows.append(dict(cohort=key[0], k_from=key[1], k_to=key[2],
                         building_min=x.min(), building_p10=x.quantile(.1),
                         building_p90=x.quantile(.9), building_max=x.max(),
                         positive_buildings=int((x > 1e-9).sum()),
                         negative_buildings=int((x < -1e-9).sum()),
                         nearzero_buildings=int((x.abs() <= 1e-9).sum())))
    s = s.merge(pd.DataFrame(rows), on=['cohort', 'k_from', 'k_to'], validate='one_to_one')
    s.to_csv(p / 'GEOMETRY_FIXED157_INTERVAL_MAIN.csv', index=False)
    natural = pd.read_csv(p / 'GEOMETRY_PATH_PRECISION.csv.gz')
    focus = set(natural[natural.cohort.eq('combined96')].pool_id)
    natural = natural[natural.pool_id.isin(focus) & natural.metric.eq('V_floor')]
    rows = []
    for layer, minimum, limit in [('ordinary_manual', 30, 30), ('doorway_manual', 0, 20)]:
        x = natural[natural.layer.eq(layer) & natural.pool_n.ge(minimum) & natural.k.le(limit)]
        for (cohort, k), g in x.groupby(['cohort', 'k']):
            good = g[g['mean'].notna()]
            se = good.mcse
            rows.append(dict(layer=layer, minimum_pool_n=minimum, cohort=cohort, k=k,
                             registered_focus_images=g.pool_id.nunique(), valid_images=len(good),
                             buildings=good.building.nunique(), estimate=good['mean'].mean(),
                             image_mcse_median=se.median(), image_mcse_p90=se.quantile(.9),
                             aggregate_mcse=np.sqrt((se**2).sum())/len(good) if len(good) and se.notna().all() else np.nan,
                             building_equal_estimate=good.groupby('building')['mean'].mean().mean()))
    pd.DataFrame(rows).to_csv(p / 'GEOMETRY_FOCUS_FIXED_SUPPORT_CURVES.csv', index=False)
    exact_path=p/'GEOMETRY_SAMPLE_VS_EXACT.csv.gz'
    if exact_path.exists():
        e=pd.read_csv(exact_path)
        e=e[e.metric.eq('V_floor') & e.k.eq(e.pool_n-1)]
        old=e[e.cohort.eq('old24')]
        rows=[]
        for cohort in ['new24','combined48','focus48','combined96']:
            new=e[e.cohort.eq(cohort)]
            merged=old.merge(new,on=['pool_id','k'],suffixes=('_old','_new'),validate='one_to_one')
            for layer,g in merged.groupby('layer_old'):
                common=g[g.error_from_exact_old.notna() & g.error_from_exact_new.notna()]
                row=dict(layer=layer,comparison=cohort,candidate_images=len(g),
                         exact_valid_images=int(g.exact_mean_old.notna().sum()),
                         old_estimable_images=int(g.error_from_exact_old.notna().sum()),
                         new_estimable_images=int(g.error_from_exact_new.notna().sum()),
                         common_images=len(common),buildings=common.building_old.nunique())
                for label in ['old','new']:
                    err=common['error_from_exact_'+label]
                    row.update({label+'_signed_error_mean':err.mean(),label+'_mae':err.abs().mean(),
                                label+'_absolute_error_p90':err.abs().quantile(.9),label+'_absolute_error_max':err.abs().max(),
                                label+'_rmse':np.sqrt(err.pow(2).mean())})
                rows.append(row)
        pd.DataFrame(rows).to_csv(p/'GEOMETRY_NMINUS_COMMON_SUPPORT_ACCURACY.csv',index=False)
    print('Saved', len(d), 'image intervals;', len(b), 'building intervals;', len(s), 'summary rows')


if __name__ == '__main__':
    main()
