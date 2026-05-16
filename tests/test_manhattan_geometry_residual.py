import pytest

from tools.manhattan_geometry_residual import (
    RESIDUAL_VERSION,
    compute_m1_residual,
    compute_residual_from_pairs,
)
from tools.manhattan_preview_compat import (
    FAILURE_DUPLICATE,
    FAILURE_ODD_KEYPOINT,
    check_preview_compatibility,
)


"""Tests for M1 offline residual diagnostics only.

These tests do not validate correctness, worker quality, formal g_t, routing,
snap suggestions, adjustment vectors, UI behavior, or Label Studio integration.
"""


def _points(rows):
    return [
        {"point_id": point_id, "x": x, "y": y, "role": role}
        for point_id, x, y, role in rows
    ]


CLEAN_RECTANGLE = _points(
    [
        ("p1", 20.0, 25.0, "ceiling"),
        ("p2", 20.0, 78.0, "floor"),
        ("p3", 40.0, 22.0, "ceiling"),
        ("p4", 40.0, 80.0, "floor"),
        ("p5", 60.0, 22.0, "ceiling"),
        ("p6", 60.0, 80.0, "floor"),
        ("p7", 80.0, 25.0, "ceiling"),
        ("p8", 80.0, 78.0, "floor"),
    ]
)

ODD_KEYPOINT = CLEAN_RECTANGLE[:-1]

NEAR_DUPLICATE = _points(
    [
        ("p1", 20.0, 25.0, "ceiling"),
        ("p2", 20.0, 78.0, "floor"),
        ("p3", 40.0, 22.0, "ceiling"),
        ("p4", 40.0, 80.0, "floor"),
        ("p5", 40.3, 22.2, "ceiling"),
        ("p6", 40.3, 79.8, "floor"),
        ("p7", 80.0, 25.0, "ceiling"),
        ("p8", 80.0, 78.0, "floor"),
    ]
)

INCONSISTENT_HEIGHT = _points(
    [
        ("p1", 20.0, 25.0, "ceiling"),
        ("p2", 20.0, 78.0, "floor"),
        ("p3", 40.0, 30.0, "ceiling"),
        ("p4", 40.0, 80.0, "floor"),
        ("p5", 60.0, 18.0, "ceiling"),
        ("p6", 60.0, 88.0, "floor"),
        ("p7", 80.0, 25.0, "ceiling"),
        ("p8", 80.0, 70.0, "floor"),
    ]
)


def test_clean_rectangle_residual_is_valid_and_stable():
    result = check_preview_compatibility(CLEAN_RECTANGLE)
    residual = compute_m1_residual(result)

    assert residual["diagnostic_valid"] is True
    assert residual["exclusion_reason"] is None
    assert residual["n_corners"] == 4
    assert residual["x_spacing_cv"] == pytest.approx(0.0)
    assert residual["vertical_pair_x_residual"] == pytest.approx(0.0)
    assert residual["closure_status"] == "implicit_preview_loop_closure"
    assert residual["residual_version"] == RESIDUAL_VERSION


def test_non_compatible_odd_keypoint_result_is_excluded():
    result = check_preview_compatibility(ODD_KEYPOINT)
    residual = compute_m1_residual(result)

    assert result.status == FAILURE_ODD_KEYPOINT
    assert residual["diagnostic_valid"] is False
    assert residual["exclusion_reason"] == FAILURE_ODD_KEYPOINT
    assert residual["closure_status"] is None


def test_non_compatible_duplicate_result_is_excluded():
    result = check_preview_compatibility(NEAR_DUPLICATE)
    residual = compute_m1_residual(result)

    assert result.status == FAILURE_DUPLICATE
    assert residual["diagnostic_valid"] is False
    assert residual["exclusion_reason"] == FAILURE_DUPLICATE


def test_ceiling_and_floor_y_ranges_are_computed():
    result = check_preview_compatibility(CLEAN_RECTANGLE)
    residual = compute_m1_residual(result)

    assert residual["ceiling_y_range"] == pytest.approx(15.36)
    assert residual["floor_y_range"] == pytest.approx(10.24)


def test_wall_height_range_reacts_to_inconsistent_height():
    clean = compute_m1_residual(check_preview_compatibility(CLEAN_RECTANGLE))
    inconsistent = compute_m1_residual(check_preview_compatibility(INCONSISTENT_HEIGHT))

    assert clean["wall_height_range"] == pytest.approx(25.6)
    assert inconsistent["wall_height_range"] > clean["wall_height_range"]


def test_residual_can_be_computed_from_ordered_pairs():
    compatibility = check_preview_compatibility(CLEAN_RECTANGLE)
    residual = compute_residual_from_pairs(compatibility.ordered_corners)

    assert residual["diagnostic_valid"] is True
    assert residual["n_corners"] == 4


def test_residual_output_has_no_snap_or_adjustment_fields():
    residual = compute_m1_residual(check_preview_compatibility(CLEAN_RECTANGLE))

    assert "snap_to_axis" not in residual
    assert "snap_residual" not in residual
    assert "adjustment" not in residual
    assert "adjustment_vector" not in residual
