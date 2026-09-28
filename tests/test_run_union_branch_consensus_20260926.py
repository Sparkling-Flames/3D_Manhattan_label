import numpy as np

from tools.thesis_main.analysis.run_union_branch_consensus_20260926 import (
    distribution_distance, reference_summary, worker_orders,
)


def branch(points, support=1):
    return dict(floor=points, support=support)


def test_distribution_preserves_alternatives_and_bounds_unknown_mass():
    a = [[-2, -2], [2, -2], [2, 2], [-2, 2]]
    b = [[3, -2], [7, -2], [7, 2], [3, 2]]
    invalid = [a[0], a[2], a[1], a[3]]
    mixture = [branch(a, 3), branch(b)]
    assert distribution_distance(mixture, 4, list(reversed(mixture)), 4)['upper'] < 1e-8
    d = distribution_distance(mixture, 4, [branch(a, 1), branch(b, 3)], 4)
    assert np.allclose([d['lower'], d['upper']], [.5, .5])
    d = distribution_distance([branch(invalid)], 1, [branch(invalid)], 1)
    assert d['lower'] == 0 and d['upper'] == 1
    d = distribution_distance([branch(a)], 2, [branch(a)], 1)
    assert np.allclose([d['lower'], d['upper']], [0, .5])
    s = reference_summary([branch(a)], 2, a)
    assert s['weighted_iou_lower'] == .5 and s['weighted_iou_upper'] == 1
    assert s['unknown_mass'] == .5
    s = reference_summary([branch(a), branch(invalid)], 2, a)
    assert s['tied_dominant_unknown_count'] == 1 and s['tied_dominant_bounds'] == [0, 1]


def test_orders_are_reproducible_and_each_person_votes_once():
    workers = ['w4', 'w1', 'w3', 'w2']
    orders = worker_orders(workers, repeats=4)
    assert orders == worker_orders(workers[::-1], repeats=4)
    assert all(sorted(order) == sorted(workers) for order in orders)
    for order in orders:
        assert not set(order[:2]) & set(order[-2:])
