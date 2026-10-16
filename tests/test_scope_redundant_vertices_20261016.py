import copy

import numpy as np
import pytest
from shapely.geometry import Polygon

from tools.thesis_main.analysis.scope_redundant_vertices_20261016 import (
    normalize_boundary, precision_floor_view, old_vertex_roles,
)


FLOOR = [[-1, -1], [1, -1], [1, 1], [0, 1], [-1, 1]]


def test_exact_subdivision_preserves_shape_heights_and_original_indices():
    original = copy.deepcopy(FLOOR)
    view = normalize_boundary(FLOOR, [2, 2, 4, 3, 2])
    assert FLOOR == original
    assert view['floor_removed_1based'] == [4]
    assert view['pair_removed_1based'] == [4]
    assert view['pair_kept_1based'] == [1, 2, 3, 5]
    assert view['floor_edge_source_indices_1based'] == [[1], [2], [3, 4], [5]]
    assert Polygon(FLOOR).symmetric_difference(Polygon(view['floor'])).area == 0
    assert view['pair_heights'] == [2, 2, 4, 2]


def test_height_break_is_retained_and_unknown_height_never_inferred():
    peaked = normalize_boundary(FLOOR, [2, 2, 2, 3, 2])
    assert peaked['floor_removed_1based'] == [4]
    assert peaked['pair_removed_1based'] == []
    assert peaked['height_break_1based'] == [4]
    unknown = normalize_boundary(FLOOR)
    assert unknown['pair_removed_1based'] is None
    assert unknown['pair_floor'] is None


def test_near_straight_detail_retained_and_cycle_reversal_is_equivalent():
    near = copy.deepcopy(FLOOR)
    near[3][1] += 0.001
    assert normalize_boundary(near)['floor_removed_1based'] == []
    expected = Polygon(normalize_boundary(FLOOR)['floor'])
    for shift in [0, 2, 4]:
        ring = np.roll(np.asarray(FLOOR)[::-1], shift, axis=0).tolist()
        view = normalize_boundary(ring, [2] * len(ring))
        assert len(view['floor']) == 4
        assert len(view['pair_floor']) == 4
        assert expected.symmetric_difference(Polygon(view['floor'])).area == 0


def test_multiple_collinear_points_and_invalid_input():
    ring = [[-1, -1], [1, -1], [1, 1], [.5, 1], [0, 1], [-.5, 1], [-1, 1]]
    view = normalize_boundary(ring, [2] * len(ring))
    assert view['floor_removed_1based'] == [4, 5, 6]
    assert view['pair_removed_1based'] == [4, 5, 6]
    with pytest.raises(ValueError):
        normalize_boundary(FLOOR, [2])
    with pytest.raises(ValueError):
        normalize_boundary(FLOOR[:2] + [FLOOR[1]] + FLOOR[2:])


def test_precision_view_distinguishes_approximation_from_exact_and_keeps_detail():
    near = copy.deepcopy(FLOOR)
    near[3][1] += .00001
    assert normalize_boundary(near)['floor_removed_1based'] == []
    candidate = precision_floor_view(near)
    assert [r['original_vertex_1based'] for r in candidate['removed']] == [4]
    assert candidate['symmetric_difference_area_h2'] > 0
    near[3][1] += .01
    assert precision_floor_view(near)['removed'] == []
    assert len(precision_floor_view([[-1,0],[0,.00001],[1,0]])['floor']) == 3


def test_old_points_are_relative_to_each_target_not_deleted_globally():
    old = [[-1,-1],[1,-1],[1,1],[0,1],[-1,1]]
    roles = old_vertex_roles(old,[[-1,-1],[1,-1],[1,0],[-1,0]])
    assert [r['relation'] for r in roles] == ['same_coordinate_vertex']*2 + ['outside_new_scope']*3
    other = old_vertex_roles(old,FLOOR)
    assert all(r['relation']=='same_coordinate_vertex' for r in other)
