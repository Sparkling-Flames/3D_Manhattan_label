import json
import pandas as pd
import numpy as np
from tools.thesis_main.analysis.bootstrap_v21_two_person_20261029 import TARGET


def test_intervals_preserve_point_estimates_and_separate_paired_support():
    checks=json.loads((TARGET/'K2_INTERVAL_CHECKS.json').read_text(encoding='utf8'))
    assert checks['pools']==223 and checks['prior_curve_Q1_Q3_draw_parity']
    d=pd.read_csv(TARGET/'K2_AGGREGATE_INTERVALS.csv')
    d=d[(d.scope=='combined')&(d.panel=='N_ge_30')&(d.layer=='ordinary_manual')&(d.weighting=='image_equal')]
    a=d[d.uncertainty=='paths_fixed_images'].set_index('metric')
    b=d[d.uncertainty=='buildings_fixed_path_estimates'].set_index('metric')
    assert len(a)==len(b)==4 and a.images.eq(171).all() and a.valid_draws.eq(2000).all()
    old=pd.read_csv(TARGET/'SUMMARY.csv');old=old[(old.panel=='N_ge_30')&(old.layer=='ordinary_manual')&(old.weighting=='image_equal')].set_index('metric')
    for metric in ['Q2','delta_1_2','delta_2_3']:
        assert np.isclose(a.loc[metric,'estimate'],old.loc[metric,'estimate'])
        assert np.isclose(a.loc[metric,'estimate'],b.loc[metric,'estimate'])
        assert a.loc[metric,'low']<=a.loc[metric,'high'] and b.loc[metric,'low']<=b.loc[metric,'high']
    assert a.loc['delta_1_2','valid_paths']==40342
    assert a.loc['delta_2_3','valid_paths']==40235
