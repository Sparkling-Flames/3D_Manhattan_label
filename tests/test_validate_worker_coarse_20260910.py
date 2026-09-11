import numpy as np
import pytest

from tools.thesis_main.analysis.validate_worker_coarse_20260910 import hard_partition, path_states


def test_different_counts_never_merge_and_identity_is_preserved():
    result = hard_partition(np.array([[0., 6.], [6., 0.]]), [8, 10], [True, True], [0, 1], 6.)
    assert result['clusters'] == [{0}, {1}]
    result = hard_partition(np.zeros((3, 3)), [8, 8, 8], [True]*3, [1, 2], 6.)
    assert result['clusters'] == [{1, 2}]


def test_invalid_geometry_is_unknown():
    assert hard_partition(np.zeros((2, 2)), [8, 8], [True, False], [0, 1], .05)['status'] != 'unique'


def test_persistent_two_supported_clusters_can_be_stable():
    trajectory = {n: {'status': 'unique', 'clusters': [set(range(0, n, 2)), set(range(1, n, 2))]} for n in range(2, 16)}
    trajectory[1] = {'status': 'unique', 'clusters': [{0}]}
    assert path_states(trajectory, 15)[10] == 'stable'


def test_late_second_support_breaks_earlier_stability():
    trajectory = {n: {'status': 'unique', 'clusters': [set(range(n))]} for n in range(1, 16)}
    trajectory[15] = {'status': 'unique', 'clusters': [set(range(13)), {13, 14}]}
    assert path_states(trajectory, 15)[10] == 'changing'
    assert path_states(trajectory, 10)[5] == 'stable'


def test_insufficient_future_cannot_be_called_convergence():
    with pytest.raises(ValueError):
        path_states({}, 6)
