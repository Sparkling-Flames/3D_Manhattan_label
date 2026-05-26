import math

from tools.manhattan_constrained_fit import fit_manhattan_layout


CAMERA_HEIGHT = 1.6
LAYOUT_HEIGHT = 3.0


def _ls_pair_from_bev(x, y, layout_height=LAYOUT_HEIGHT):
    theta = math.atan2(y, x)
    distance = math.hypot(x, y)
    floor_y = (math.pi / 2.0 + math.atan(CAMERA_HEIGHT / distance)) / math.pi * 100.0
    ceiling_y = (math.pi / 2.0 - math.atan((layout_height - CAMERA_HEIGHT) / distance)) / math.pi * 100.0
    ls_x = ((theta + math.pi) / (2.0 * math.pi)) * 100.0
    return {"top": {"x": ls_x, "y": ceiling_y}, "bottom": {"x": ls_x, "y": floor_y}}


def _rotate_xy(x, y, yaw):
    cos_y = math.cos(yaw)
    sin_y = math.sin(yaw)
    return x * cos_y - y * sin_y, x * sin_y + y * cos_y


def _rectangle_pairs(yaw=0.0):
    points = [(-2.0, -1.0), (2.0, -1.0), (2.0, 1.0), (-2.0, 1.0)]
    return [_ls_pair_from_bev(*_rotate_xy(x, y, yaw)) for x, y in points]


def _max_abs_delta(result):
    values = []
    for row in result["per_point_delta"]:
        values.extend([row["top_dx"], row["top_dy"], row["bottom_dx"], row["bottom_dy"]])
    return max(abs(value) for value in values)


def test_perfect_rectangle_produces_near_zero_deltas():
    result = fit_manhattan_layout(_rectangle_pairs())

    assert result["fit_status"] == "ok"
    assert result["fit_residual"] < 1e-10
    assert result["fit_confidence"] == "high"
    assert result["direction_label"] == "no_action"
    assert _max_abs_delta(result) < 1e-8
    assert result["layout_height_candidate"] == pytest_approx(LAYOUT_HEIGHT)
    assert result["manhattan_yaw_deg"] == pytest_approx(0.0)


def pytest_approx(value, abs=1e-8):
    import pytest

    return pytest.approx(value, abs=abs)


def test_rotated_rectangle_fits_after_yaw_search():
    yaw = math.radians(25.0)
    result = fit_manhattan_layout(_rectangle_pairs(yaw=yaw))

    assert result["fit_status"] == "ok"
    assert result["fit_residual"] < 1e-10
    assert result["yaw_search_count"] > 1
    assert result["manhattan_yaw_deg"] == pytest_approx(25.0, abs=1e-6)
    assert result["selected_orientation_pattern"] in {"start_horizontal", "start_vertical"}


def test_rotated_perturbed_rectangle_improves_over_no_yaw_axis_fit():
    pairs = _rectangle_pairs(yaw=math.radians(25.0))
    pairs[1] = {
        "top": {"x": pairs[1]["top"]["x"] + 0.7, "y": pairs[1]["top"]["y"]},
        "bottom": {"x": pairs[1]["bottom"]["x"] + 0.7, "y": pairs[1]["bottom"]["y"]},
    }

    result = fit_manhattan_layout(pairs)

    assert result["fit_status"] == "ok"
    assert result["fit_residual"] < result["axis_aligned_baseline_residual"]
    assert result["yaw_fit_residual"] == result["fit_residual"]


def test_top_bottom_x_mismatch_suggests_x_alignment():
    pairs = _rectangle_pairs()
    pairs[0] = {
        "top": {"x": pairs[0]["top"]["x"] + 2.0, "y": pairs[0]["top"]["y"]},
        "bottom": pairs[0]["bottom"],
    }

    result = fit_manhattan_layout(pairs)

    assert result["fit_status"] == "ok"
    assert result["direction_label"] == "align_vertical_pair_x"
    assert "vertical_corner_x_mismatch" in result["warnings"]
    first = result["fitted_points"][0]
    assert first["top"]["x"] == first["bottom"]["x"]


def test_height_aware_reprojection_produces_y_deltas_for_perturbed_y():
    pairs = _rectangle_pairs()
    pairs[0] = {
        "top": {"x": pairs[0]["top"]["x"], "y": pairs[0]["top"]["y"] + 1.2},
        "bottom": {"x": pairs[0]["bottom"]["x"], "y": pairs[0]["bottom"]["y"] - 0.8},
    }

    result = fit_manhattan_layout(pairs)

    assert result["fit_status"] == "ok"
    first_delta = result["per_point_delta"][0]
    assert abs(first_delta["top_dy"]) > 0.0
    assert abs(first_delta["bottom_dy"]) > 0.0
    assert result["y_projection_model"] == "camera_height_layout_height_atan2_v1"
    assert result["camera_height"] == CAMERA_HEIGHT


def test_mildly_perturbed_manhattan_polygon_fits_candidate():
    pairs = _rectangle_pairs()
    pairs[1] = {
        "top": {"x": pairs[1]["top"]["x"] + 0.7, "y": pairs[1]["top"]["y"]},
        "bottom": {"x": pairs[1]["bottom"]["x"] + 0.7, "y": pairs[1]["bottom"]["y"]},
    }
    pairs[2] = {
        "top": {"x": pairs[2]["top"]["x"] - 0.5, "y": pairs[2]["top"]["y"]},
        "bottom": {"x": pairs[2]["bottom"]["x"] - 0.5, "y": pairs[2]["bottom"]["y"]},
    }

    result = fit_manhattan_layout(pairs)

    assert result["fit_status"] == "ok"
    assert result["fit_residual"] > 0
    assert result["fit_residual"] < 0.08
    assert len(result["fitted_points"]) == len(pairs)
    assert len(result["per_point_delta"]) == len(pairs)


def test_known_height_rectangle_recovers_plausible_layout_height_candidate():
    pairs = _rectangle_pairs(yaw=math.radians(15.0))

    result = fit_manhattan_layout(pairs)

    assert result["fit_status"] == "ok"
    assert result["layout_height_candidate"] == pytest_approx(LAYOUT_HEIGHT, abs=1e-6)
    assert result["layout_height_spread"] < 1e-8


def test_implausible_ceiling_geometry_fails_safely():
    pairs = _rectangle_pairs()
    for pair in pairs:
        pair["top"]["y"] = 5.0

    result = fit_manhattan_layout(pairs)

    assert result["fit_status"] == "failed"
    assert result["direction_label"] in {
        "implausible_layout_height",
        "candidate_moves_points_too_far",
    }


def test_self_crossing_input_fails_safely():
    pairs = _rectangle_pairs()
    crossing = [pairs[0], pairs[2], pairs[1], pairs[3]]

    result = fit_manhattan_layout(crossing)

    assert result["fit_status"] == "failed"
    assert "self_crossing_input" in result["warnings"]


def test_seam_adjacent_input_fails_safely():
    pairs = [
        {"x": 1.0, "y_ceiling": 32.0, "y_floor": 72.0},
        {"x": 25.0, "y_ceiling": 32.0, "y_floor": 72.0},
        {"x": 75.0, "y_ceiling": 32.0, "y_floor": 72.0},
        {"x": 99.0, "y_ceiling": 32.0, "y_floor": 72.0},
    ]

    result = fit_manhattan_layout(pairs)

    assert result["fit_status"] == "failed"
    assert "wrap_seam_unresolved" in result["warnings"]


def test_candidate_preserves_pair_count_and_order():
    pairs = _rectangle_pairs()

    result = fit_manhattan_layout(pairs)

    assert result["fit_status"] == "ok"
    assert [row["pair_index"] for row in result["fitted_points"]] == [1, 2, 3, 4]
    assert [row["pair_index"] for row in result["per_point_delta"]] == [1, 2, 3, 4]


def test_returned_deltas_include_dx_and_dy_fields():
    result = fit_manhattan_layout(_rectangle_pairs())

    assert result["fit_status"] == "ok"
    for row in result["per_point_delta"]:
        assert {"top_dx", "top_dy", "bottom_dx", "bottom_dy"}.issubset(row)


def test_oos_metadata_fails_without_writing_export_or_annotation():
    result = fit_manhattan_layout(_rectangle_pairs(), metadata={"scope": "oos_open_boundary"})

    assert result["fit_status"] == "failed"
    assert result["direction_label"] == "oos_open_boundary"
    assert result["fitted_points"] == []
    assert result["per_point_delta"] == []
