import numpy as np
import pytest

from tools.thesis_main.analysis.validate_building_stages_20260909 import (
    anchored_states, complete_link_partition, stage_tail, weighted_curve, stage_onset,
)


def unique(*groups):
    return {'status': 'unique', 'clusters': [set(g) for g in groups]}


def test_supported_multicluster_and_singleton_promotion():
    # 两个各有两人的簇已形成；后来在原簇内增加支持不等于新簇。
    t = {4: unique([0, 1], [2, 3]), 5: unique([0, 1, 4], [2, 3]),
         6: unique([0, 1, 4], [2, 3, 5])}
    assert anchored_states(t, 6, min_future=2, epsilon=.1)[4] == 'stable'
    t = {4: unique([0, 1, 2], [3]), 5: unique([0, 1, 2], [3, 4])}
    assert anchored_states(t, 5, min_future=1, epsilon=1)[4] == 'changing'


def test_anchor_catches_accumulated_drift_and_known_failure_survives_unknown():
    t = {k: unique(range(10), range(10, k)) for k in range(20, 41)}
    # 任一相邻一步变化很小，但20人与40人之间的份额变化为0.25。
    assert anchored_states(t, 40, min_future=5, epsilon=.1)[20] == 'changing'
    t[30] = {'status': 'non_unique', 'clusters': []}
    assert anchored_states(t, 40, min_future=5, epsilon=.1)[20] == 'changing'
    t = {2: unique([0, 1]), 3: {'status': 'non_unique', 'clusters': []}}
    assert anchored_states(t, 3, min_future=1)[2] == 'unknown'
    assert stage_tail(['stable', 'unknown', 'changing', 'stable']) == ['changing', 'changing', 'changing', 'stable']


def test_complete_link_hard_counts_and_no_chain_merge():
    d = np.array([[0, .01, .2], [.01, 0, .04], [.2, .04, 0]])
    p = complete_link_partition(d, .05, [8, 8, 8])
    assert sorted(map(sorted, p['clusters'])) == [[0, 1], [2]]
    assert len(complete_link_partition(np.zeros((3, 3)), .05, [8, 10, 12])['clusters']) == 3


def test_prediction_does_not_use_target_outcome_and_weights_are_valid():
    curves = np.array([[[.2, .4]], [[.6, .8]]])
    assert np.allclose(weighted_curve(curves, [.25, .75]), [[.5, .7]])
    with pytest.raises(ValueError):
        weighted_curve(curves, [-1, 2])


def test_neighbors_reject_target_and_preserve_scalar_distance():
    from tools.thesis_main.analysis.predict_building_stages_20260909 import neighbor_weights, image_distances
    d = np.array([[0, 1, 2], [1, 0, 1], [2, 1, 0]], float)
    ids, weights = neighbor_weights(0, [1, 2], d)
    assert ids == [1, 2] and weights[0] > weights[1]
    with pytest.raises(ValueError):
        neighbor_weights(0, [0, 1], d)
    assert np.allclose(image_distances([[1, 0], [0, 1]]), [[0, np.sqrt(2)], [np.sqrt(2), 0]])


def test_onset_domain_starts_at_two_distinct_people():
    # k=1没有支持是定义上的不合格，不应让k>=2完全稳定的图变成未知起点。
    assert stage_onset([0, 1, 1], [1, 1, 1]) == (2, 2, 2, 'identified')
    assert stage_onset([0, .3, .8], [0, .3, .8]) == (3, 3, 3, 'identified')


def test_identical_source_coefficients_give_identical_forecast():
    from tools.thesis_main.analysis.predict_building_stages_20260909 import same_linear_prediction
    assert same_linear_prediction({'source':1.}, {'source':1.})
    assert not same_linear_prediction({'source':1.}, {'other':1.})
