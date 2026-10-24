import numpy as np
import pandas as pd
from tools.thesis_main.analysis.build_population_late_curves_20261024 import (
    fixed_cohorts, late_changes, summarize_curves, summarize_changes, image_curves,
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
                             failure=float(image=='b'), unavailable=float(image=='b'), policy_deferred=0.))
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
        for path, values in [('x', [5.,8.,9.,10.,30.]), ('y', [10.,15.,20.,np.nan,90.])]
        for k,q in zip([3,6,10,20,30],values)])
    rows=[]
    for k,q,fail in [(3,7.5,0.),(6,11.5,0.),(10,14.5,0.),(20,10.,.5),(30,60.,0.)]:
        rows.append(dict(pool_id='p', image='p', building='b', difficulty='简单', pool_n=30,
                         cohort_min_n=20, stage=str(k) if k<30 else 'full', k=k,
                         Q=q, D10=q, P10=q, SD=2., V=.1, failure=fail, unavailable=fail))
    image = late_changes(pd.DataFrame(rows),prefix)
    assert set(image.comparison) == {'3_to_6','6_to_10','10_to_20','3_to_20','20_to_full'}
    row = image[image.comparison=='20_to_full'].iloc[0]
    assert row.Q_delta==50. and row.paired_Q_delta==20.
    assert row.paired_Q_paths==1 and row.recovered_paths==1
    assert row.failure_delta==-.5
    summary=summarize_changes(image)
    assert summary[(summary.metric=='paired_Q') & (summary.comparison=='20_to_full')].delta_mean.eq(20.).all()


def test_full_pool_missing_result_is_not_zero_quality_or_zero_variation():
    row=dict(pool_id='p',image='p',building='b',difficulty='困难',pool_n=35,k=35,
             attempts=24,scorable=0,unique_teams=1,geometry_valid_paths=0,V_pairs=np.nan,
             Q=np.nan,D10=np.nan,P10=np.nan,SD=np.nan,V=np.nan,failure=1.,unavailable=1.,policy_deferred=0.)
    summary=summarize_curves(fixed_cohorts(pd.DataFrame([row])))
    assert summary.Q.isna().all() and summary.V.isna().all()
    assert summary.failure.eq(1.).all()


def test_single_person_baseline_and_two_person_pause_are_preserved():
    meta = dict(pool_id='p', image='p', building='b', difficulty='简单', pool_n=30,
                policy='natural_random', layer='ordinary_manual')
    prefix = pd.DataFrame([dict(meta, path_id='x', team_key=f't{k}', k=k, B8L2=q, D10=q,
                                score_available=k!=2, score_failure_nonpolicy=False, policy_deferred=k==2)
                           for k,q in [(1,75.),(2,np.nan),(3,80.)]])
    geometry = pd.DataFrame([dict(meta, k=k, V_floor_mean=np.nan if k==2 else .1,
                                  V_floor_valid_pairs=0, geometry_valid_paths=0 if k==2 else 1,
                                  member_variation_estimable=False, full_pool_endpoint=False)
                             for k in [1,2,3]])
    images, _ = image_curves(prefix, geometry)
    summary = summarize_curves(fixed_cohorts(images))
    baseline = summary[(summary.cohort_min_n==30) & (summary.stage=='1')]
    paused = summary[(summary.cohort_min_n==30) & (summary.stage=='2')]
    assert baseline.Q.eq(75.).all()
    assert paused.Q.isna().all() and paused.V.isna().all()
    assert paused.policy_deferred.eq(1.).all() and paused.failure.eq(0.).all()
    assert paused.unavailable.eq(1.).all()
