from itertools import product

import numpy as np
import pytest

from tools.thesis_main.analysis.simulate_building_holdout_20260908 import (
    history_precision, prefix_results, distribution_tv,
)


def test_empirical_iid_precision_matches_exhaustive_sampling():
    values = np.array([0.0, .2, .7, 1.0])
    distance = abs(values[:, None] - values[None, :])
    predicted = history_precision(distance, [2, 3, 4])
    for k in [2, 3, 4]:
        means = [distance[np.ix_(ids, ids)].sum()/(k*(k-1)) for ids in product(range(4), repeat=k)]
        assert predicted[k]**2 == pytest.approx(np.var(means), abs=1e-12)
    assert predicted[4] > 0  # No forced zero at the historical sample size.


def test_validation_cannot_select_history_medoid_or_precision_candidate():
    matrix = np.full((6, 6), .2); np.fill_diagonal(matrix, 0)
    changed = matrix.copy(); changed[:4, 4:] = .9; changed[4:, :4] = .9
    changed[4, 5] = changed[5, 4] = .8
    first = prefix_results(matrix, [0, 1, 2, 3], [4, 5], [2, 3, 4])
    second = prefix_results(changed, [0, 1, 2, 3], [4, 5], [2, 3, 4])
    assert [r['medoid_index'] for r in first] == [r['medoid_index'] for r in second]
    assert [r['train_plugin_sd'] for r in first] == [r['train_plugin_sd'] for r in second]
    assert first[-1]['absolute_disagreement_gap'] != second[-1]['absolute_disagreement_gap']
    assert second[-1]['medoid_validation_distance'] > 0  # Full history endpoint is still held out.
    with pytest.raises(ValueError, match='overlap'):
        prefix_results(matrix, [0, 1, 2], [2, 3], [2])


def test_unseen_count_category_is_not_forced_into_a_training_category():
    assert distribution_tv([8, 8, 8], [8, 12]) == .5
    assert distribution_tv([0, 13], [0, 13]) == 0


def test_identical_training_can_disagree_with_validation():
    matrix = np.zeros((6, 6)); matrix[4, 5] = matrix[5, 4] = 1
    rows = prefix_results(matrix, [0, 1, 2, 3], [4, 5], [2, 4])
    assert rows[-1]['train_plugin_sd'] == 0
    assert rows[-1]['absolute_disagreement_gap'] == 1
