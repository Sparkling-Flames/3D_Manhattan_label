import json
import numpy as np
import pytest

from tools.thesis_main.analysis.gt_order_visibility_20261009 import (
    classify_ring_x, visibility_from_floor, vertical_wall_occlusion,
)


@pytest.mark.parametrize('xs,expected', [
    ([700, 900, 100, 300], 'cyclic_increasing'),
    ([300, 100, 900, 700], 'cyclic_decreasing'),
    ([700, 900, 100, 300, 250, 500], 'local_backtracking'),
    ([100, 100, 300, 700], 'cyclic_increasing'),
])
def test_cyclic_start_direction_and_ties(xs, expected):
    for shift in range(len(xs)):
        result = classify_ring_x(np.roll(xs, shift))
        assert result['x_order_class'] == expected
        assert result['same_x_pairs'] == (len(set(xs)) < len(xs))
        assert json.loads(json.dumps(result)) == result


def test_visibility_square_and_occluded_l_shape():
    square = [[-2, -2], [2, -2], [2, 2], [-2, 2]]
    assert visibility_from_floor(square)['hidden_vertices_1based'] == []
    # The camera is in the lower arm. Vertex 4 is behind the notch wall.
    shape = [[-2, -1], [3, -1], [3, 3], [1, 3], [1, 1], [-2, 1]]
    result = visibility_from_floor(shape)
    assert result['status'] == 'valid_camera_inside'
    assert result['hidden_vertices_1based'] == [4]
    assert result['visibility'][3]['blockers'][0]['edge_1based'] == [5, 6]


def test_invalid_or_external_camera_is_not_called_occlusion():
    result = visibility_from_floor([[1, 1], [3, 1], [3, 3], [1, 3]])
    assert result['status'] == 'camera_not_strictly_inside'
    assert result['hidden_vertices_1based'] is None
    result = visibility_from_floor([[-1, -1], [1, 1], [-1, 1], [1, -1]])
    assert result['status'] == 'invalid_polygon'
    assert result['hidden_vertices_1based'] is None


def test_same_ray_contact_is_separate_from_transverse_occlusion():
    result = visibility_from_floor([[-2, -2], [2, -2], [2, 2], [1, 1], [1, 2], [-2, 2]])
    assert result['visibility'][2]['status'] == 'grazing_or_collinear'


def test_full_height_occlusion_is_not_inferred_from_floor_alone():
    shape = [[-2, -1], [3, -1], [3, 3], [1, 3], [1, 1], [-2, 1]]
    vis = visibility_from_floor(shape)['visibility']
    ordinary = vertical_wall_occlusion(vis, np.ones(6))
    assert ordinary['fully_occluded_vertical_pairs_1based'] == [4]
    tall = np.ones(6); tall[3] = 10
    result = vertical_wall_occlusion(vis, tall)
    assert result['fully_occluded_vertical_pairs_1based'] == []
    assert result['partial_wall_occlusion_pairs_1based'] == [4]
    assert result['vertical_occlusion'][0]['hidden_height_fraction'] == pytest.approx(4/11)
