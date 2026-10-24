import numpy as np
import pandas as pd
from tools.thesis_main.analysis.build_population_late_curves_20261024 import (
    fixed_cohorts, late_changes, summarize_curves, summarize_changes,
)


def test_capacity_cohort_does_not_change_with_k_or_missing_quality():
    rows = []
    for image, n in [('a', 30), ('b', 35), ('excluded', 29)]:
        for k in range(3, n + 1):
            rows.append(dict(pool_id=image, image=image, building=image, difficulty='困难',
                             pool_n=n, k=k, attempts=24, scorable=0 if image=='b' else 24,
                             unique_teams=1 if k==n else 24, geometry_valid_paths=24, V_pairs=276,
                             Q=np.nan if image=='b' else 80., D10=np.nan, P10=np.nan,
                             SD=0. if k==n else 4., V=0. if k==n else .1,
                             failure=float(image=='b'), unavailable=float(image=='b')))
    p = fixed_cohorts(pd.DataFrame(rows))
    q = summarize_curves(p)
    n30 = q[(q.cohort_min_n==30) & (q.difficulty=='全部')]
    assert n30.images.eq(2).all()
    assert n30.Q_images.eq(1).all()
    assert n30.failure.eq(.5).all()
    full = n30[n30.stage=='full'].iloc[0]
    assert (full.actual_n_min, full.actual_n_max) == (30,35)
    assert full.SD == full.V == 0
    assert set(p[p.cohort_min_n==35].image) == {'b'}


def test_paired_quality_uses_common_paths_and_failure_uses_all_paths():
    prefix = pd.DataFrame([
        dict(pool_id='p', path_id=path, k=k, B8L2=q)
        for path, values in [('x', [10.,30.]), ('y', [np.nan,90.])]
        for k,q in zip([20,30],values)])
    rows=[]
    for k,q,fail in [(20,10.,.5),(30,60.,0.)]:
        rows.append(dict(pool_id='p', image='p', building='b', difficulty='简单', pool_n=30,
                         cohort_min_n=20, stage='20' if k==20 else 'full', k=k,
                         Q=q, D10=q, P10=q, SD=2., V=.1, failure=fail, unavailable=fail))
    image = late_changes(pd.DataFrame(rows),prefix)
    row = image.iloc[0]
    assert row.Q_delta==50. and row.paired_Q_delta==20.
    assert row.paired_Q_paths==1 and row.recovered_paths==1
    assert row.failure_delta==-.5
    summary=summarize_changes(image)
    assert summary[summary.metric=='paired_Q'].delta_mean.eq(20.).all()


def test_full_pool_missing_result_is_not_zero_quality_or_zero_variation():
    row=dict(pool_id='p',image='p',building='b',difficulty='困难',pool_n=35,k=35,
             attempts=24,scorable=0,unique_teams=1,geometry_valid_paths=0,V_pairs=np.nan,
             Q=np.nan,D10=np.nan,P10=np.nan,SD=np.nan,V=np.nan,failure=1.,unavailable=1.)
    summary=summarize_curves(fixed_cohorts(pd.DataFrame([row])))
    assert summary.Q.isna().all() and summary.V.isna().all()
    assert summary.failure.eq(1.).all()
