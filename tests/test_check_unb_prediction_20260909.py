import numpy as np
import pytest

from tools.thesis_main.analysis.check_unb_prediction_20260909 import (
    paired_gain_bounds, source_prediction, balanced_source, feature_matched_sources, known_state_probability,
)


def test_source_prediction_uses_only_supplied_sources_and_preserves_unknown():
    def step(k):
        values = (np.arange(1, 7) >= k).astype(float)
        return np.column_stack([values, values])
    vectors = {'a': step(2), 'b': step(4), 'held_out': step(6),
               'unknown': np.tile([0., 1.], (6, 1))}
    curve, count, low, high, identified_n = source_prediction(vectors, ['a', 'b', 'unknown'])
    assert (count, low, high, identified_n) == (3., 2., 4., 2)
    assert np.allclose(curve[:, 1] - curve[:, 0], 1 / 3)
    vectors['held_out'][:] = 0
    after = source_prediction(vectors, ['a', 'b', 'unknown'])
    assert np.array_equal(after[0], curve) and after[1:] == (count, low, high, identified_n)
    assert np.isnan(source_prediction(vectors, ['unknown'])[1])
    with pytest.raises(ValueError, match='source_identity'):
        source_prediction(vectors, ['a', 'a'])


def test_shared_target_gain_bounds_match_piecewise_extrema_and_exact_errors():
    low, high = paired_gain_bounds(np.array([.2, .2]), np.array([.8, .8]), np.array([.1, .1]))
    assert np.isclose(low, .6) and np.isclose(high, .6)
    low, high = paired_gain_bounds(np.array([.3, .3]), np.array([.3, .3]), np.array([0., 1.]))
    assert low == high == 0
    rng = np.random.default_rng(71)
    for _ in range(20):
        same, outside, target = np.sort(rng.random((3, 2)), axis=1)
        low, high = paired_gain_bounds(same, outside, target)
        t = np.unique(np.r_[np.linspace(*target, 1001),
                            np.clip(np.r_[same, outside, same.mean(), outside.mean()], *target)])
        lower = np.maximum(0, np.maximum(outside[0] - t, t - outside[1])) - np.maximum(abs(same[0] - t), abs(same[1] - t))
        upper = np.maximum(abs(outside[0] - t), abs(outside[1] - t)) - np.maximum(0, np.maximum(same[0] - t, t - same[1]))
        assert np.isclose(low, lower.min()) and np.isclose(high, upper.max())
    with pytest.raises(ValueError, match='invalid_interval'):
        paired_gain_bounds(np.array([.8, .2]), np.array([0., 1.]), np.array([0., 1.]))


def test_balance_uses_only_feature_strata_and_response_counts():
    ids = [str(i) for i in range(12)]
    dt_bins = {key: i // 4 for i, key in enumerate(ids)}
    counts = {key: 23 + i % 2 for i, key in enumerate(ids)}
    assert balanced_source(['0', '1', '4', '5', '8', '9'], ids, dt_bins, counts)
    assert balanced_source(['0', '1', '4', '5', '8', '9', '10'], ids, dt_bins, counts)
    assert not balanced_source(['0', '1', '2', '3', '4', '5'], ids, dt_bins, counts)
    assert not balanced_source(['0', '2', '4', '6', '8', '10'], ids, dt_bins, counts)


def test_feature_matched_baseline_uses_distinct_outside_images_without_outcomes():
    dt = {'a': 2., 'b': 8., 'x': 1., 'y': 3., 'z': 9.}
    result = feature_matched_sources(['a','b'], ['x','y','z'], dt)
    assert len(set(result)) == 2 and set(result) <= {'x','y','z'}
    assert sum(abs(dt[s]-dt[o]) for s,o in zip(['a','b'],result)) == 2.


def test_unknown_short_window_state_is_neither_success_nor_failure():
    states={'a':1.,'b':0.,'c':np.nan,'held_out':0.}
    assert known_state_probability(states,['a','c']) == (1.,1)
    assert known_state_probability(states,['a','b','c']) == (.5,2)
    assert np.isnan(known_state_probability(states,['c'])[0])
    states['held_out']=1.
    assert known_state_probability(states,['a','b','c']) == (.5,2)
