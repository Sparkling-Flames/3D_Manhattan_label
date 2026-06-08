import pytest

from tools.paper_a_manhattan.manhattan_preview_compat import (
    COMPATIBLE,
    FAILURE_DUPLICATE,
    FAILURE_ODD_KEYPOINT,
    FAILURE_WRAPAROUND,
    FAILURE_WRONG_ORDER,
    PAIRING_RULE_VERSION,
    build_ordered_preview_corners,
    check_preview_compatibility,
    pair_keypoints_like_current_preview,
    percent_to_pixel,
)


"""Tests for experiment-outside preview parity only.

These tests do not validate correctness, formal g_t, routing behavior,
worker-facing guidance, UI integration, or Label Studio integration.
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

WRAPAROUND_SEAM = _points(
    [
        ("p1", 2.0, 26.0, "ceiling"),
        ("p2", 2.0, 79.0, "floor"),
        ("p3", 18.0, 23.0, "ceiling"),
        ("p4", 18.0, 81.0, "floor"),
        ("p5", 82.0, 23.0, "ceiling"),
        ("p6", 82.0, 81.0, "floor"),
        ("p7", 98.0, 26.0, "ceiling"),
        ("p8", 98.0, 79.0, "floor"),
    ]
)

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

ODD_KEYPOINT = _points(
    [
        ("p1", 20.0, 25.0, "ceiling"),
        ("p2", 20.0, 78.0, "floor"),
        ("p3", 40.0, 22.0, "ceiling"),
        ("p4", 40.0, 80.0, "floor"),
        ("p5", 60.0, 22.0, "ceiling"),
        ("p6", 60.0, 80.0, "floor"),
        ("p7", 80.0, 25.0, "ceiling"),
    ]
)

WRONG_ORDER = _points(
    [
        ("p1", 20.0, 25.0, "ceiling"),
        ("p2", 20.0, 78.0, "floor"),
        ("p3", 80.0, 25.0, "ceiling"),
        ("p4", 80.0, 78.0, "floor"),
        ("p5", 40.0, 22.0, "ceiling"),
        ("p6", 40.0, 80.0, "floor"),
        ("p7", 60.0, 22.0, "ceiling"),
        ("p8", 60.0, 80.0, "floor"),
    ]
)


def test_clean_axis_aligned_rectangle_matches_fixture_plan():
    expected_pixels = [
        (204.8, 128.0),
        (204.8, 399.36),
        (409.6, 112.64),
        (409.6, 409.6),
        (614.4, 112.64),
        (614.4, 409.6),
        (819.2, 128.0),
        (819.2, 399.36),
    ]

    pixels = [percent_to_pixel(point) for point in CLEAN_RECTANGLE]
    assert [(point.x, point.y) for point in pixels] == pytest.approx(expected_pixels)

    pairs, unpaired = pair_keypoints_like_current_preview(CLEAN_RECTANGLE)
    assert len(pairs) == 4
    assert unpaired == ()

    ordered = build_ordered_preview_corners(CLEAN_RECTANGLE)
    assert [corner.x for corner in ordered] == pytest.approx(
        [204.8, 409.6, 614.4, 819.2]
    )

    result = check_preview_compatibility(CLEAN_RECTANGLE)
    assert result.status == COMPATIBLE
    assert result.suggestion_allowed is True
    assert result.allowed_adjustment_type == "closure_check_only"
    assert result.compatibility_reason == "current_preview_pairing_and_order_compatible"
    assert result.pairing_rule_version == PAIRING_RULE_VERSION


def test_wraparound_seam_unresolved_blocks_suggestions():
    result = check_preview_compatibility(WRAPAROUND_SEAM)

    assert result.status == FAILURE_WRAPAROUND
    assert result.suggestion_allowed is False
    assert result.allowed_adjustment_type == "none"
    assert result.compatibility_reason == "seam_adjacent_x_sort_order_unresolved"


def test_near_duplicate_corner_blocks_suggestions():
    result = check_preview_compatibility(NEAR_DUPLICATE)

    assert result.status == FAILURE_DUPLICATE
    assert result.suggestion_allowed is False
    assert result.allowed_adjustment_type == "none"
    assert result.compatibility_reason == "near_duplicate_corner_pair"


def test_odd_keypoint_count_blocks_suggestions():
    result = check_preview_compatibility(ODD_KEYPOINT)

    assert result.status == FAILURE_ODD_KEYPOINT
    assert result.suggestion_allowed is False
    assert result.allowed_adjustment_type == "none"
    assert result.compatibility_reason == "odd_keypoint_count_or_unpaired_points"
    assert len(result.unpaired_points) == 1


def test_wrong_order_with_preserve_order_blocks_suggestions():
    # This failure only suppresses assistant suggestions; it is not a correctness label.
    result = check_preview_compatibility(WRONG_ORDER, preserve_order=True)

    assert result.status == FAILURE_WRONG_ORDER
    assert [corner.x for corner in result.ordered_corners] == pytest.approx(
        [204.8, 819.2, 409.6, 614.4]
    )
    assert result.suggestion_allowed is False
    assert result.allowed_adjustment_type == "none"
    assert (
        result.compatibility_reason
        == "preserve_order_conflicts_with_x_sorted_preview_order"
    )


def test_wrong_order_without_preserve_order_is_resolved_by_x_sort():
    """Current preview x-sort resolves this synthetic wrong-order fixture.

    The fixture remains a preserve-order failure case because assistant
    suggestions must respect explicit preview order semantics when enabled.
    """

    result = check_preview_compatibility(WRONG_ORDER, preserve_order=False)

    assert result.status == COMPATIBLE
    assert [corner.x for corner in result.ordered_corners] == pytest.approx(
        [204.8, 409.6, 614.4, 819.2]
    )
    assert result.suggestion_allowed is True
    assert result.allowed_adjustment_type == "closure_check_only"


def test_threshold_boundary_uses_strict_less_than_w_times_005():
    width = 100
    height = 100
    exact_threshold = _points(
        [
            ("p1", 10.0, 25.0, "ceiling"),
            ("p2", 15.0, 78.0, "floor"),
        ]
    )
    slightly_under = _points(
        [
            ("p1", 10.0, 25.0, "ceiling"),
            ("p2", 14.999, 78.0, "floor"),
        ]
    )
    slightly_over = _points(
        [
            ("p1", 10.0, 25.0, "ceiling"),
            ("p2", 15.001, 78.0, "floor"),
        ]
    )

    exact_pairs, exact_unpaired = pair_keypoints_like_current_preview(
        exact_threshold,
        width=width,
        height=height,
    )
    assert exact_pairs == ()
    assert len(exact_unpaired) == 2
    assert (
        check_preview_compatibility(exact_threshold, width=width, height=height).status
        == FAILURE_ODD_KEYPOINT
    )

    under_pairs, under_unpaired = pair_keypoints_like_current_preview(
        slightly_under,
        width=width,
        height=height,
    )
    assert len(under_pairs) == 1
    assert under_unpaired == ()
    assert (
        check_preview_compatibility(slightly_under, width=width, height=height).status
        == COMPATIBLE
    )

    over_pairs, over_unpaired = pair_keypoints_like_current_preview(
        slightly_over,
        width=width,
        height=height,
    )
    assert over_pairs == ()
    assert len(over_unpaired) == 2
    assert (
        check_preview_compatibility(slightly_over, width=width, height=height).status
        == FAILURE_ODD_KEYPOINT
    )


def test_pairing_rule_scans_for_nearest_x_candidate_like_official_userscript():
    close_x = _points(
        [
            ("p1", 40.0, 25.0, "ceiling"),
            ("p2", 40.4, 78.0, "floor"),
            ("p3", 40.2, 80.0, "floor"),
            ("p4", 60.0, 25.0, "ceiling"),
        ]
    )

    pairs, unpaired = pair_keypoints_like_current_preview(close_x)

    assert len(pairs) == 1
    assert pairs[0].p1.point_id == "p1"
    assert pairs[0].p2.point_id == "p3"
    assert pairs[0].x == pytest.approx(410.624)
    assert [point.point_id for point in unpaired] == ["p2", "p4"]
    result = check_preview_compatibility(close_x)
    assert result.status == FAILURE_ODD_KEYPOINT
    assert result.suggestion_allowed is False
    assert result.pairing_rule_version == PAIRING_RULE_VERSION


def test_preserve_order_false_uses_x_sort_as_authoritative_preview_order():
    result = check_preview_compatibility(WRONG_ORDER, preserve_order=False)

    assert result.status == COMPATIBLE
    assert [corner.x for corner in result.ordered_corners] == pytest.approx(
        [204.8, 409.6, 614.4, 819.2]
    )
    assert result.suggestion_allowed is True
