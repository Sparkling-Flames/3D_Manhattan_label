import math
import numpy as np
import pytest

from tools.thesis_main.analysis.compute_building_convergence_evidence_20260908 import (
    prefix_validation, adjacent, fixed_mask,
)


def test_prefix_uses_only_prefix_and_keeps_positive_entropy():
    d = np.full((8, 8), 20.0)
    for group in ([0, 1, 4, 6], [2, 3, 5, 7]):
        d[np.ix_(group, group)] = 0
    h, v, clusters = list(range(6)), [6, 7], [[0, 1], [2, 3]]
    r = prefix_validation(d, h, v, clusters, 3, 4, 'unique')
    assert r['distribution_tv'] == 0
    assert r['training_entropy'] == pytest.approx(math.log(2))
    changed = d.copy()
    changed[4:6, :] = changed[:, 4:6] = 100
    assert prefix_validation(changed, h, v, clusters, 3, 4, 'unique') == r
    changed[6, :4] = changed[:4, 6] = 100
    other = prefix_validation(changed, h, v, clusters, 3, 4, 'unique')
    assert other['training_cluster_support_json'] == r['training_cluster_support_json']
    assert other['validation_outside_fraction'] == .5


def test_ambiguous_nonunique_truncated_and_missing_stay_missing():
    d = np.array([[0, 10, 1], [10, 0, 1], [1, 1, 0]], float)
    r = prefix_validation(d, [0, 1], [2], [[0], [1]], 3, 2, 'unique')
    assert r['validation_ambiguous_fraction'] == 1 and math.isnan(r['distribution_tv'])
    for status in ('non_unique', 'truncated', 'missing'):
        r = prefix_validation(d, [0, 1], [2], [], 3, 2, status)
        assert math.isnan(r['distribution_tv']) and r['prefix_status'] == status
    with pytest.raises(ValueError):
        prefix_validation(d, [0, 1], [1], [[0], [1]], 3, 2, 'unique')


def test_adjacent_checks_membership_not_only_count():
    a = dict(k=4, status='unique', prefix_clusters_json='[["a","b"],["c","d"]]')
    b = dict(k=5, status='unique', prefix_clusters_json='[["a","c","e"],["b","d"]]')
    assert adjacent(a, b, list('abcde'))['coassignment_disagreement'] == pytest.approx(4/6)
    b['status'] = 'non_unique'
    assert math.isnan(adjacent(a, b, list('abcde'))['coassignment_disagreement'])


def test_fixed_mask_prevents_changing_population_and_is_metric_specific():
    support = {s: dict(history_n=5, validation_n=2) for s in ('a', 'b', 'c')}
    support['c']['history_n'] = 3
    data = {'a': {3: {'status': 'unique', 'x': 0., 'y': 1.}, 5: {'status': 'unique', 'x': 1., 'y': 1.}},
            'b': {3: {'status': 'unique', 'x': 10., 'y': 2.}, 5: {'status': 'unique', 'x': float('nan'), 'y': 2.}}}
    r = fixed_mask(support, data, [3, 5], 5, 'x')
    assert r['valid_split_ids'] == ['a'] and r['support_eligible_splits'] == 2
    assert r['all_splits'] == 3 and r['missing_or_nonfinite_splits'] == 1
    assert fixed_mask(support, data, [3, 5], 5, 'y')['valid_split_ids'] == ['a', 'b']
    data['a'][5]['status'] = 'truncated'
    r = fixed_mask(support, data, [3, 5], 5, 'x')
    assert r['truncated_splits'] == 1 and not r['valid_split_ids']


def test_partition_status_indicators_keep_all_supported_splits():
    support = {s: dict(history_n=8, validation_n=2) for s in ('a', 'b')}
    data = {'a': {k: dict(status='unique', unique_indicator=1) for k in (3, 5, 8)},
            'b': {3: dict(status='unique', unique_indicator=1),
                  5: dict(status='non_unique', unique_indicator=0),
                  8: dict(status='truncated', unique_indicator=0)}}
    mask = fixed_mask(support, data, [3, 5, 8], 8, 'unique_indicator')
    assert mask['valid_split_ids'] == ['a', 'b']
    assert mask['non_unique_splits'] == mask['truncated_splits'] == 1
    assert mask['missing_or_nonfinite_splits'] == 0
