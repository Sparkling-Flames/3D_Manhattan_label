import pytest

from tools.thesis_main.analysis.difficulty_user_revision_20261015 import remove_pairs


def test_remove_pairs_preserves_surviving_points_and_ring():
    points = [[i, i + .25] for i in range(16)]
    assert remove_pairs(points, [5, 6]) == points[:8] + points[12:]
    assert len(points) == 16


def test_pair_number_is_one_based_and_must_exist():
    with pytest.raises(ValueError):
        remove_pairs([[0, 0], [0, 1]], [0])
    with pytest.raises(ValueError):
        remove_pairs([[0, 0], [0, 1]], [2])
