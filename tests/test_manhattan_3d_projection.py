import math

import pytest

from tools.paper_a_manhattan.manhattan_3d_projection import (
    compute_corner_turn_metrics,
    compute_floorprint_metrics,
    normalize_layout_coordinates,
    project_corner_to_3d,
    project_layout_to_3d,
)


WIDTH = 1024
HEIGHT = 512
CAM_H = 1.6


def _pixel_pair_from_floor(x, z, *, ceiling_y=1.0):
    distance = math.hypot(x, z)
    u = math.atan2(x, -z)
    floor_v = math.atan(CAM_H / distance)
    ceiling_v = math.atan(-ceiling_y / distance)
    pixel_x = (u + math.pi) / (2.0 * math.pi) * WIDTH
    return {
        "top": {"x": pixel_x, "y": (ceiling_v / math.pi + 0.5) * HEIGHT},
        "bottom": {"x": pixel_x, "y": (floor_v / math.pi + 0.5) * HEIGHT},
    }


def test_projection_formula_parity_and_clamp_flags():
    corner = {"x": WIDTH * 0.75, "y_floor": HEIGHT * 0.75, "y_ceiling": HEIGHT * 0.25}
    result = project_corner_to_3d(corner, WIDTH, HEIGHT, CAM_H)

    u = math.pi / 2.0
    floor_v = math.pi / 4.0
    distance = CAM_H / math.tan(floor_v)
    assert result["u_rad"] == pytest.approx(u)
    assert result["floor_distance"] == pytest.approx(distance)
    assert result["floor_3d"] == pytest.approx({"x": distance, "y": -CAM_H, "z": 0.0})
    assert result["ceiling_3d"]["y"] == pytest.approx(distance)
    assert result["floor_clamped"] is False
    assert result["ceiling_clamped"] is False

    clamped = project_corner_to_3d(
        {"x": 0, "y_floor": 0, "y_ceiling": HEIGHT}, WIDTH, HEIGHT, CAM_H
    )
    assert clamped["floor_clamped"] is True
    assert clamped["ceiling_clamped"] is True
    assert clamped["v_floor_safe_rad"] == pytest.approx(0.01)
    assert clamped["v_ceiling_safe_rad"] == pytest.approx(-0.01)


def test_coordinate_normalization_modes_and_auto_provenance():
    raw = [{"top": {"x": 25, "y": 20}, "bottom": {"x": 27, "y": 80}}]
    percent = normalize_layout_coordinates(raw, WIDTH, HEIGHT, "ls_percent")
    pair = percent["pairs"][0]
    assert pair["x"] == pytest.approx(266.24)
    assert pair["top_y_px"] == pytest.approx(102.4)
    assert pair["bottom_y_px"] == pytest.approx(409.6)

    pixels = normalize_layout_coordinates(raw, WIDTH, HEIGHT, "vis_pixels")
    assert pixels["pairs"][0]["x"] == pytest.approx(26.0)
    assert pixels["pairs"][0]["bottom_y_px"] == pytest.approx(80.0)

    inferred = normalize_layout_coordinates(raw, WIDTH, HEIGHT, "auto")
    assert inferred["coordinate_mode"] == "ls_percent"
    assert "0..100" in inferred["inference_reason"]
    assert inferred["warnings"] == [
        "auto_coordinate_mode_ambiguous_values_fit_both_ls_percent_and_small_pixel_range"
    ]

    pixel_like = normalize_layout_coordinates(
        [{"x": 420, "y_ceiling": 100, "y_floor": 390}], WIDTH, HEIGHT, "auto"
    )
    assert pixel_like["coordinate_mode"] == "vis_pixels"
    assert pixel_like["warnings"] == []


def test_rectangle_has_near_zero_wall_and_turn_residuals():
    rectangle = [
        _pixel_pair_from_floor(-2, -1),
        _pixel_pair_from_floor(2, -1),
        _pixel_pair_from_floor(2, 1),
        _pixel_pair_from_floor(-2, 1),
    ]
    projected = project_layout_to_3d(rectangle, WIDTH, HEIGHT, "vis_pixels", CAM_H)
    floor = compute_floorprint_metrics(projected)
    corners = compute_corner_turn_metrics(projected)

    assert floor["summary"]["wall_residual_sum_deg"] == pytest.approx(0.0, abs=1e-9)
    assert floor["self_intersection"] is False
    assert corners["summary"]["corner_residual_sum_deg"] == pytest.approx(0.0, abs=1e-9)
    assert all(row["angle_to_90_residual_deg"] == pytest.approx(0.0) for row in corners["corners"])

    non_manhattan = [
        _pixel_pair_from_floor(-2, -1),
        _pixel_pair_from_floor(2, -1),
        _pixel_pair_from_floor(2.7, 1),
        _pixel_pair_from_floor(-2, 1),
    ]
    non_projected = project_layout_to_3d(
        non_manhattan, WIDTH, HEIGHT, "vis_pixels", CAM_H
    )
    non_floor = compute_floorprint_metrics(non_projected)
    non_corners = compute_corner_turn_metrics(non_projected)
    assert non_floor["summary"]["wall_residual_sum_deg"] > 10.0
    assert non_corners["summary"]["corner_residual_sum_deg"] > 10.0


def test_layout_projection_keeps_vertical_residual_and_source_order():
    projected = project_layout_to_3d(
        [
            {
                "top": {"x": 44.612, "y": 14.787},
                "bottom": {"x": 44.987, "y": 86.466},
                "effective_pair_index": 5,
                "source_preview_order_index": 6,
            }
        ],
        WIDTH,
        HEIGHT,
        "ls_percent",
    )
    pair = projected["pairs"][0]
    assert pair["effective_pair_index"] == 5
    assert pair["source_preview_order_index"] == 6
    assert pair["top_bottom_x_residual"] == pytest.approx(0.375)
    assert pair["normalized"]["x"] == pytest.approx(((44.612 + 44.987) / 2) * WIDTH / 100)

