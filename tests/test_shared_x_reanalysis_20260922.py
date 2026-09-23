import numpy as np
import pytest

from tools.thesis_main.analysis.shared_x_reanalysis_20260922 import shared_x, evaluate_sequence, residual_attribution


def test_shared_x_uses_all_bound_pairs_and_retains_exceptions():
    p = np.array([[1023., 20.], [1., 490.], [40., 30.], [41., 480.]])
    links = np.array([[0, 1], [2, 3]])
    q = shared_x(p, links)
    np.testing.assert_array_equal(q[:, 0], [0., 0., 40.5, 40.5])
    np.testing.assert_array_equal(q[:, 1], p[:, 1])
    np.testing.assert_array_equal(p[:, 0], [1023., 1., 40., 41.])
    np.testing.assert_array_equal(shared_x(p, links, preserve=True), p)
    np.testing.assert_array_equal(shared_x(p, None), p)
    with pytest.raises(ValueError):
        shared_x(p, np.array([[0, 1], [1, 2]]))


def test_onset_requires_every_later_prefix_support_and_observation_tail():
    labs = {k: np.ones(k, int) for k in range(4, 9)}
    compare = lambda a, b: (0., 0.)
    r = evaluate_sequence(labs, 8, (3, 2, .1), 3, compare)
    assert r['observed_onset'] == 4 and r['reason'] == 'success'
    assert evaluate_sequence(labs, 8, (3, 2, .1), 5, compare)['reason'] == 'no_anchor_room'
    labs[8] = np.arange(8)
    assert evaluate_sequence(labs, 8, (3, 2, .1), 3, compare)['reason'] == 'no_support_suffix'
    labs[8] = np.ones(8, int)
    assert evaluate_sequence(labs, 8, (3, 2, .1), 3, lambda a,b:(.2,0.))['reason'] == 'share_drift'
    assert evaluate_sequence(labs, 8, (3, 2, .1), 3, lambda a,b:(0.,.2))['reason'] == 'membership_drift'


def test_prediction_attribution_is_additive_even_across_absolute_value():
    a = residual_attribution(.2, .4, .5, .45)
    assert a['residual_change'] == pytest.approx(.25)
    assert a['target_contribution'] + a['source_contribution'] == pytest.approx(a['error_change'])
    assert a['error_change'] == pytest.approx(-.15)
