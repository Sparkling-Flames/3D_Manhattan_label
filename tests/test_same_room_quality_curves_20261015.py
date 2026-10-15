import numpy as np
import pandas as pd
import pytest

from tools.thesis_main.analysis.same_room_quality_curves_20261015 import (
    common_profile, curve_distance, exact_curve, information_block, control_sources,
    control_curve_distance,
)


def test_common_profiles_keep_same_workers_and_missing_values():
    a = pd.DataFrame({'worker_id': ['a', 'b', 'only_a'], 'WQ': [80., 60., 0.]})
    b = pd.DataFrame({'worker_id': ['a', 'b', 'only_b'], 'WQ': [70., 50., 100.]})
    result = common_profile(a, b, 'WQ')
    assert result['workers'] == ['a', 'b']
    assert result['mean_a'] == 70 and result['mean_b'] == 60
    assert result['absolute_gap'] == 10
    b.loc[0, 'WQ'] = np.nan
    assert common_profile(a, b, 'WQ')['n_evaluable'] == 1


def test_curve_level_shape_and_missing_denominators_are_separate():
    a = pd.Series([.7, .8, np.nan, .9], index=[1, 2, 3, 4])
    b = pd.Series([.5, .6, .7, .7], index=[1, 2, 3, 4])
    result = curve_distance(a, b)
    assert result['planned_k'] == 4 and result['evaluated_k'] == 3
    assert result['level_mae'] == pytest.approx(.2)
    assert result['gain_mae'] == pytest.approx(0)
    assert curve_distance(pd.Series([.8, .8], index=[1, 2]),
                          pd.Series([.6, .6], index=[1, 2]))['spearman'] is None
    assert curve_distance(a.drop(1), b)['gain_mae'] is None


def test_connected_evidence_only_blocks_control_leakage():
    edges = {('a', 'b'): {'tier': 'confirmed_comparable'},
             ('b', 'c'): {'tier': 'supported_other'}}
    assert information_block('a', edges) == {'a', 'b', 'c'}
    assert ('a', 'c') not in edges
    images = {'a': ('building', 'simple'), 'b': ('building', 'simple'),
              'c': ('building', 'simple'), 'd': ('building', 'simple'),
              'e': ('other', 'simple')}
    people = {i: {'p', 'q'} for i in images}
    assert control_sources('a', 'b', ['p', 'q'], images, people, edges) == ['d']
    assert control_sources('a', 'b', ['p', 'q'], images, people, edges,
                           external=True) == ['e']


def test_exact_lee_curve_enumerates_real_people_and_keeps_even_ties():
    records = [dict(id='a', worker='a', footprint=[[0, 0], [1, 0], [1, 1], [0, 1]]),
               dict(id='b', worker='b', footprint=[[1, 0], [2, 0], [2, 1], [1, 1]])]
    rows = exact_curve(records, {'original': [[0, 0], [2, 0], [2, 1], [0, 1]]})
    assert [r['subsets'] for r in rows] == [2, 1]
    assert [r['iou_mean'] for r in rows] == pytest.approx([.5, 1.])
    assert all(r['evaluable_subsets'] == r['subsets'] for r in rows)
    assert all(r['nonempty_fraction'] == 1 for r in rows)


def test_one_source_budget_is_not_replaced_by_averaging_all_sources():
    target = pd.Series([.5, .6], index=[1, 2])
    controls = [pd.Series([.4, .4], index=[1, 2]), pd.Series([.6, .8], index=[1, 2])]
    result = control_curve_distance(target, controls)
    assert result['level_mae'] == pytest.approx(.15)
    assert result['ensemble_level_mae'] == pytest.approx(0)
    assert result['gain_mae'] == pytest.approx(.05)
