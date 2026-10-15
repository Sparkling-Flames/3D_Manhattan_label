import numpy as np
import pandas as pd
import pytest

from tools.thesis_main.analysis.same_room_personnel_patterns_20261015 import (
    person_pattern, split_types, type_gap, check_fold,
)


def test_view_offset_and_general_worker_pattern_are_separate():
    a = pd.Series([80., 60., 40.], index=['x', 'y', 'z'])
    b = a-10
    ability = pd.Series([20., 0., -20.], index=a.index)
    r = person_pattern(a, b, ability)
    assert r['mean_gap'] == 10
    assert r['centered_rmse'] == 0
    assert r['raw_spearman'] == pytest.approx(1)
    assert r['residual_spearman'] is None
    assert r['general_ability_rmse_target'] == 0


def test_residual_pattern_can_differ_from_general_ability():
    ability = pd.Series([10., 0., -10.], index=['x', 'y', 'z'])
    extra = pd.Series([-5., 10., -5.], index=ability.index)
    a, b = 60+ability+extra, 40+ability+extra
    r = person_pattern(a, b, ability)
    assert r['residual_spearman'] == pytest.approx(1)
    assert r['general_ability_rmse_target'] > r['centered_rmse']
    with pytest.raises(ValueError, match='identical workers'):
        person_pattern(a, b.drop('z'), ability)
    incomplete = ability.copy(); incomplete['x'] = np.nan
    assert person_pattern(a, b, incomplete)['residual_spearman'] is None


def test_types_need_two_real_workers_each_and_zero_is_unclassified():
    profiles = pd.DataFrame({'worker_id': list('abcde'), 'effect': [1., 2., -1., 0., -2.],
                             'supported': [True]*5})
    partial = split_types(profiles, list('abcd'))
    assert partial['usable'] is False and partial['positive_usable'] is True
    result = split_types(profiles, list('abcde'))
    assert result['positive'] == ['a', 'b'] and result['negative'] == ['c', 'e']
    assert result['unclassified'] == ['d'] and result['usable'] is True
    assert type_gap(pd.Series({'a': 80., 'b': 70., 'c': 50., 'e': 60.}), result) == 20


def test_fold_rejects_target_building_even_when_effects_look_valid():
    rows = pd.DataFrame({'worker_id': ['w'], 'training_buildings': ['["other"]']})
    check_fold(rows, 'target')
    rows.loc[0, 'training_buildings'] = '["other", "target"]'
    with pytest.raises(ValueError, match='target building'):
        check_fold(rows, 'target')


def test_shared_baseline_can_create_high_diagnostic_correlation():
    a = pd.Series([60., 40., 60., 40.], index=list('abcd'))
    b = pd.Series([60., 60., 40., 40.], index=list('abcd'))
    baseline = pd.Series([30., -30., 30., -30.], index=a.index)
    result = person_pattern(a, b, baseline)
    assert result['raw_spearman'] == pytest.approx(0)
    assert result['residual_spearman'] > .8
    assert result['centered_rmse'] == person_pattern(a, b, baseline*0)['centered_rmse']
