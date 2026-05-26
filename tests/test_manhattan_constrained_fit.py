import math

from tools.manhattan_constrained_fit import fit_manhattan_layout


CAMERA_HEIGHT = 1.6


def _ls_pair_from_bev(x, y, top_y=32.0):
    theta = math.atan2(y, x)
    distance = math.hypot(x, y)
    floor_y = (math.pi / 2.0 + math.atan(CAMERA_HEIGHT / distance)) / math.pi * 100.0
    ls_x = ((theta + math.pi) / (2.0 * math.pi)) * 100.0
    return {"top": {"x": ls_x, "y": top_y}, "bottom": {"x": ls_x, "y": floor_y}}


def _rectangle_pairs():
    return [
        _ls_pair_from_bev(-2.0, -1.0),
        _ls_pair_from_bev(2.0, -1.0),
        _ls_pair_from_bev(2.0, 1.0),
        _ls_pair_from_bev(-2.0, 1.0),
    ]


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


def test_oos_metadata_fails_without_writing_export_or_annotation():
    result = fit_manhattan_layout(_rectangle_pairs(), metadata={"scope": "oos_open_boundary"})

    assert result["fit_status"] == "failed"
    assert result["direction_label"] == "oos_open_boundary"
    assert result["fitted_points"] == []
    assert result["per_point_delta"] == []
