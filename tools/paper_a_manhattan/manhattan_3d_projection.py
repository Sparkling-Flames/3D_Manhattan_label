"""Local-only projection and geometry metrics mirroring ``vis_3d.html``.

This module is an expert-side diagnostic harness.  It does not read Three.js
state, write annotations, generate patches, reorder corners, or feed formal
experiment artifacts.  The projection formula intentionally mirrors
``tools/label_studio/vis_3d.html::renderGeometry``.
"""

from __future__ import annotations

import math
import statistics
from typing import Any, Mapping, Sequence


PROJECTION_SCHEMA_VERSION = "local_3d_projection_m15_19_v1"
DEFAULT_CAMERA_HEIGHT = 1.6
ANGLE_WARNING_DEG = 15.0
TURN_WARNING_DEG = 15.0
SHORT_WALL_ABSOLUTE_THRESHOLD = 0.2
SHORT_WALL_MEDIAN_RATIO = 0.2
HEIGHT_ABSOLUTE_THRESHOLD = 0.25

# Kept aligned with the existing M15.15 dense-corner diagnostic vocabulary.
CENTER_X_DUPLICATE_THRESHOLD_PERCENT = 1.0
BEV_DISTINCT_DISTANCE_THRESHOLD = 0.3
FLOOR_DISTANCE_DISTINCT_THRESHOLD = 0.3
TRUE_DUPLICATE_BEV_DISTANCE_THRESHOLD = 0.1
TRUE_DUPLICATE_FLOOR_DISTANCE_THRESHOLD = 0.1
MIN_ADJACENT_WALL_LENGTH_FOR_DISTINCT = 0.2


def _as_float(value: Any, *, field: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be numeric")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric") from exc
    if not math.isfinite(parsed):
        raise ValueError(f"{field} must be finite")
    return parsed


def _coerce_pair(pair: Mapping[str, Any], index: int) -> dict[str, Any]:
    """Accept the current M15 ordered-pair and vis_3d pair shapes."""

    top = pair.get("top")
    bottom = pair.get("bottom")
    if isinstance(top, Mapping) and isinstance(bottom, Mapping):
        top_x = _as_float(top.get("x"), field=f"pair[{index}].top.x")
        bottom_x = _as_float(bottom.get("x"), field=f"pair[{index}].bottom.x")
        top_y = _as_float(top.get("y"), field=f"pair[{index}].top.y")
        bottom_y = _as_float(bottom.get("y"), field=f"pair[{index}].bottom.y")
    elif {"x", "y_ceiling", "y_floor"}.issubset(pair):
        top_x = bottom_x = _as_float(pair.get("x"), field=f"pair[{index}].x")
        top_y = _as_float(pair.get("y_ceiling"), field=f"pair[{index}].y_ceiling")
        bottom_y = _as_float(pair.get("y_floor"), field=f"pair[{index}].y_floor")
    elif {"top_x", "bottom_x", "top_y", "bottom_y"}.issubset(pair):
        top_x = _as_float(pair.get("top_x"), field=f"pair[{index}].top_x")
        bottom_x = _as_float(pair.get("bottom_x"), field=f"pair[{index}].bottom_x")
        top_y = _as_float(pair.get("top_y"), field=f"pair[{index}].top_y")
        bottom_y = _as_float(pair.get("bottom_y"), field=f"pair[{index}].bottom_y")
    else:
        raise ValueError(
            f"pair[{index}] must contain top/bottom, x/y_ceiling/y_floor, "
            "or top_x/bottom_x/top_y/bottom_y"
        )

    effective_index = pair.get("effective_pair_index", pair.get("pair_index", index))
    source_index = pair.get("source_preview_order_index")
    return {
        "effective_pair_index": int(effective_index),
        "source_preview_order_index": int(source_index) if source_index is not None else None,
        "top_x": top_x,
        "bottom_x": bottom_x,
        "top_y": top_y,
        "bottom_y": bottom_y,
    }


def _infer_coordinate_mode(
    pairs: Sequence[Mapping[str, Any]], width: int, height: int
) -> tuple[str, str, list[str]]:
    values_x = [float(row[key]) for row in pairs for key in ("top_x", "bottom_x")]
    values_y = [float(row[key]) for row in pairs for key in ("top_y", "bottom_y")]
    max_x = max(values_x, default=0.0)
    max_y = max(values_y, default=0.0)
    min_value = min([*values_x, *values_y], default=0.0)
    warnings: list[str] = []

    if min_value >= 0.0 and max_x <= 100.0 and max_y <= 100.0:
        warnings.append(
            "auto_coordinate_mode_ambiguous_values_fit_both_ls_percent_and_small_pixel_range"
        )
        return (
            "ls_percent",
            "all coordinates are within 0..100; LS/result/report inputs preferentially use ls_percent",
            warnings,
        )

    if max_x <= width * 1.05 and max_y <= height * 1.05:
        return (
            "vis_pixels",
            "at least one coordinate exceeds 100 and values fit the configured W/H pixel bounds",
            warnings,
        )

    warnings.append("coordinates_exceed_configured_width_or_height")
    return (
        "vis_pixels",
        "coordinates exceed 100, so pixel mode is safer despite configured-bound warnings",
        warnings,
    )


def normalize_layout_coordinates(
    raw_layout: Sequence[Mapping[str, Any]],
    width: int,
    height: int,
    coordinate_mode: str,
) -> dict[str, Any]:
    """Normalize ordered corner pairs to the pixel coordinates consumed by vis_3d."""

    if coordinate_mode not in {"auto", "ls_percent", "vis_pixels"}:
        raise ValueError("coordinate_mode must be auto, ls_percent, or vis_pixels")
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be positive")
    if not isinstance(raw_layout, Sequence) or isinstance(raw_layout, (str, bytes)):
        raise ValueError("raw_layout must be a sequence of pair objects")

    coerced = [_coerce_pair(pair, idx) for idx, pair in enumerate(raw_layout, start=1)]
    if not coerced:
        raise ValueError("raw_layout must contain at least one pair")

    warnings: list[str] = []
    if coordinate_mode == "auto":
        effective_mode, inference_reason, warnings = _infer_coordinate_mode(
            coerced, width, height
        )
    else:
        effective_mode = coordinate_mode
        inference_reason = f"coordinate mode explicitly set to {coordinate_mode}"

    scale_x = width / 100.0 if effective_mode == "ls_percent" else 1.0
    scale_y = height / 100.0 if effective_mode == "ls_percent" else 1.0
    normalized: list[dict[str, Any]] = []
    for pair in coerced:
        top_x = pair["top_x"] * scale_x
        bottom_x = pair["bottom_x"] * scale_x
        top_y = pair["top_y"] * scale_y
        bottom_y = pair["bottom_y"] * scale_y
        normalized.append(
            {
                **pair,
                "x": (top_x + bottom_x) / 2.0,
                "top_x_px": top_x,
                "bottom_x_px": bottom_x,
                "top_y_px": top_y,
                "bottom_y_px": bottom_y,
                "top_bottom_x_residual_px": abs(top_x - bottom_x),
                "top_bottom_x_residual_input": abs(pair["top_x"] - pair["bottom_x"]),
            }
        )

    return {
        "coordinate_mode_requested": coordinate_mode,
        "coordinate_mode": effective_mode,
        "inference_reason": inference_reason,
        "warnings": warnings,
        "width": width,
        "height": height,
        "pairs": normalized,
    }


def project_corner_to_3d(
    corner: Mapping[str, Any],
    width: int,
    height: int,
    camera_height: float = DEFAULT_CAMERA_HEIGHT,
) -> dict[str, Any]:
    """Project one normalized vis_3d corner using renderGeometry parity formulas."""

    x = _as_float(corner.get("x"), field="corner.x")
    y_floor = _as_float(
        corner.get("y_floor", corner.get("bottom_y_px")), field="corner.y_floor"
    )
    y_ceiling = _as_float(
        corner.get("y_ceiling", corner.get("top_y_px")), field="corner.y_ceiling"
    )
    camera_height = _as_float(camera_height, field="camera_height")
    if width <= 0 or height <= 0 or camera_height <= 0:
        raise ValueError("width, height, and camera_height must be positive")

    u = (x / width) * 2.0 * math.pi - math.pi
    v_floor = (y_floor / height - 0.5) * math.pi
    v_ceiling = (y_ceiling / height - 0.5) * math.pi
    safe_floor = max(0.01, min(1.5, v_floor))
    safe_ceiling = max(-1.5, min(-0.01, v_ceiling))
    dist = camera_height / math.tan(safe_floor)
    x_3d = dist * math.sin(u)
    z_3d = -dist * math.cos(u)
    ceiling_y = -dist * math.tan(safe_ceiling)

    return {
        "u_rad": u,
        "v_floor_raw_rad": v_floor,
        "v_floor_safe_rad": safe_floor,
        "v_ceiling_raw_rad": v_ceiling,
        "v_ceiling_safe_rad": safe_ceiling,
        "floor_clamped": not math.isclose(v_floor, safe_floor, abs_tol=1e-12),
        "ceiling_clamped": not math.isclose(v_ceiling, safe_ceiling, abs_tol=1e-12),
        "floor_distance": dist,
        "floor_3d": {"x": x_3d, "y": -camera_height, "z": z_3d},
        "ceiling_3d": {"x": x_3d, "y": ceiling_y, "z": z_3d},
    }


def floor_point_to_layout_pair(
    x_3d: float,
    z_3d: float,
    *,
    layout_height: float,
    camera_height: float = DEFAULT_CAMERA_HEIGHT,
) -> dict[str, dict[str, float]]:
    """Invert the local floor projection into one vertical LS-percent pair."""

    x_3d = _as_float(x_3d, field="x_3d")
    z_3d = _as_float(z_3d, field="z_3d")
    layout_height = _as_float(layout_height, field="layout_height")
    camera_height = _as_float(camera_height, field="camera_height")
    distance = math.hypot(x_3d, z_3d)
    if distance <= 1e-9 or layout_height <= camera_height or camera_height <= 0:
        raise ValueError("invalid floor point or layout height for reprojection")
    u = math.atan2(x_3d, -z_3d)
    x = ((u + math.pi) % (2.0 * math.pi)) / (2.0 * math.pi) * 100.0
    floor_v = math.atan(camera_height / distance)
    ceiling_v = -math.atan((layout_height - camera_height) / distance)
    floor_y = (floor_v / math.pi + 0.5) * 100.0
    ceiling_y = (ceiling_v / math.pi + 0.5) * 100.0
    return {
        "top": {"x": x, "y": ceiling_y},
        "bottom": {"x": x, "y": floor_y},
    }


def project_layout_to_3d(
    ordered_pairs: Sequence[Mapping[str, Any]],
    width: int,
    height: int,
    coordinate_mode: str,
    camera_height: float = DEFAULT_CAMERA_HEIGHT,
) -> dict[str, Any]:
    """Normalize and project a complete ordered layout without modifying its order."""

    normalized = normalize_layout_coordinates(
        ordered_pairs, width, height, coordinate_mode
    )
    projected_pairs: list[dict[str, Any]] = []
    clamp_warnings: list[str] = []
    for pair in normalized["pairs"]:
        projection = project_corner_to_3d(pair, width, height, camera_height)
        pair_warnings: list[str] = []
        if projection["floor_clamped"]:
            pair_warnings.append("floor_angle_clamped")
        if projection["ceiling_clamped"]:
            pair_warnings.append("ceiling_angle_clamped")
        for warning in pair_warnings:
            clamp_warnings.append(
                f"pair_{pair['effective_pair_index']}:{warning}"
            )
        projected_pairs.append(
            {
                "effective_pair_index": pair["effective_pair_index"],
                "source_preview_order_index": pair["source_preview_order_index"],
                "input": {
                    "top_x": pair["top_x"],
                    "bottom_x": pair["bottom_x"],
                    "top_y": pair["top_y"],
                    "bottom_y": pair["bottom_y"],
                },
                "normalized": {
                    "x": pair["x"],
                    "top_x": pair["top_x_px"],
                    "bottom_x": pair["bottom_x_px"],
                    "top_y": pair["top_y_px"],
                    "bottom_y": pair["bottom_y_px"],
                },
                **projection,
                "wall_height": projection["ceiling_3d"]["y"]
                - projection["floor_3d"]["y"],
                "top_bottom_x_residual": pair["top_bottom_x_residual_input"],
                "top_bottom_x_residual_px": pair["top_bottom_x_residual_px"],
                "warnings": pair_warnings,
            }
        )

    return {
        "schema_version": PROJECTION_SCHEMA_VERSION,
        "coordinate_mode": normalized["coordinate_mode"],
        "coordinate_provenance": {
            key: normalized[key]
            for key in (
                "coordinate_mode_requested",
                "coordinate_mode",
                "inference_reason",
                "warnings",
            )
        },
        "width": width,
        "height": height,
        "camera_height": camera_height,
        "pairs": projected_pairs,
        "warnings": [*normalized["warnings"], *clamp_warnings],
    }


def _point_xz(pair: Mapping[str, Any], layer: str) -> tuple[float, float]:
    point = pair[layer]
    return float(point["x"]), float(point["z"])


def _direction_metrics(dx: float, dz: float) -> tuple[float, float, float]:
    direction = math.degrees(math.atan2(dz, dx)) % 360.0
    nearest = (round(direction / 90.0) * 90.0) % 360.0
    delta = abs((direction - nearest + 180.0) % 360.0 - 180.0)
    return direction, nearest, delta


def _orientation(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _segments_intersect(
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
    d: tuple[float, float],
) -> bool:
    o1 = _orientation(a, b, c)
    o2 = _orientation(a, b, d)
    o3 = _orientation(c, d, a)
    o4 = _orientation(c, d, b)
    return (o1 * o2 < -1e-12) and (o3 * o4 < -1e-12)


def _self_intersection(points: Sequence[tuple[float, float]]) -> bool:
    n = len(points)
    if n < 4:
        return False
    for i in range(n):
        a, b = points[i], points[(i + 1) % n]
        for j in range(i + 1, n):
            if j == i or (j + 1) % n == i or (i + 1) % n == j:
                continue
            c, d = points[j], points[(j + 1) % n]
            if _segments_intersect(a, b, c, d):
                return True
    return False


def compute_floorprint_metrics(projected_layout: Mapping[str, Any]) -> dict[str, Any]:
    pairs = list(projected_layout.get("pairs", []))
    if len(pairs) < 2:
        return {"walls": [], "self_intersection": False, "summary": {}}

    provisional: list[dict[str, Any]] = []
    for idx, left in enumerate(pairs):
        right = pairs[(idx + 1) % len(pairs)]
        floor_a = _point_xz(left, "floor_3d")
        floor_b = _point_xz(right, "floor_3d")
        ceil_a = _point_xz(left, "ceiling_3d")
        ceil_b = _point_xz(right, "ceiling_3d")
        dx, dz = floor_b[0] - floor_a[0], floor_b[1] - floor_a[1]
        floor_length = math.hypot(dx, dz)
        ceiling_length = math.hypot(ceil_b[0] - ceil_a[0], ceil_b[1] - ceil_a[1])
        direction, nearest, residual = _direction_metrics(dx, dz)
        provisional.append(
            {
                "wall_index": idx + 1,
                "from_pair": left["effective_pair_index"],
                "to_pair": right["effective_pair_index"],
                "floor_wall_vector": {"x": dx, "z": dz},
                "floor_wall_length": floor_length,
                "direction_deg": direction,
                "nearest_manhattan_axis_deg": nearest,
                "angle_residual_deg": residual,
                "ceiling_wall_length": ceiling_length,
                "length_ratio": (
                    ceiling_length / floor_length if floor_length > 1e-12 else None
                ),
                "angle_warning": residual > ANGLE_WARNING_DEG,
            }
        )

    lengths = [row["floor_wall_length"] for row in provisional]
    median_length = statistics.median(lengths)
    short_threshold = max(
        SHORT_WALL_ABSOLUTE_THRESHOLD, median_length * SHORT_WALL_MEDIAN_RATIO
    )
    walls = [
        {
            **row,
            "short_wall": row["floor_wall_length"] < short_threshold,
            "short_wall_threshold": short_threshold,
        }
        for row in provisional
    ]
    residuals = [row["angle_residual_deg"] for row in walls]
    intersection = _self_intersection([_point_xz(pair, "floor_3d") for pair in pairs])
    return {
        "walls": walls,
        "self_intersection": intersection,
        "summary": {
            "n_walls": len(walls),
            "wall_residual_sum_deg": sum(residuals),
            "wall_residual_max_deg": max(residuals),
            "minimum_wall_length": min(lengths),
            "short_wall_count": sum(bool(row["short_wall"]) for row in walls),
            "self_intersection": intersection,
        },
    }


def compute_corner_turn_metrics(projected_layout: Mapping[str, Any]) -> dict[str, Any]:
    pairs = list(projected_layout.get("pairs", []))
    if len(pairs) < 3:
        return {"corners": [], "summary": {}}
    points = [_point_xz(pair, "floor_3d") for pair in pairs]
    rows: list[dict[str, Any]] = []
    for idx, point in enumerate(points):
        prev = points[(idx - 1) % len(points)]
        nxt = points[(idx + 1) % len(points)]
        v1 = (prev[0] - point[0], prev[1] - point[1])
        v2 = (nxt[0] - point[0], nxt[1] - point[1])
        denom = math.hypot(*v1) * math.hypot(*v2)
        turn = None
        residual = None
        warning = True
        if denom > 1e-12:
            cosine = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / denom))
            turn = math.degrees(math.acos(cosine))
            residual = abs(turn - 90.0)
            warning = residual > TURN_WARNING_DEG
        rows.append(
            {
                "corner_pair_index": pairs[idx]["effective_pair_index"],
                "prev_wall_index": ((idx - 1) % len(points)) + 1,
                "next_wall_index": idx + 1,
                "turn_angle_deg": turn,
                "angle_to_90_residual_deg": residual,
                "warning_far_from_90": warning,
            }
        )
    residuals = [row["angle_to_90_residual_deg"] for row in rows if row["angle_to_90_residual_deg"] is not None]
    return {
        "corners": rows,
        "summary": {
            "n_corners": len(residuals),
            "corner_residual_sum_deg": sum(residuals),
            "corner_residual_max_deg": max(residuals) if residuals else None,
        },
    }


def compute_height_metrics(
    projected_layout: Mapping[str, Any], *, local_window: int = 1
) -> dict[str, Any]:
    pairs = list(projected_layout.get("pairs", []))
    heights = [float(pair["wall_height"]) for pair in pairs]
    if not heights:
        return {"pairs": [], "summary": {}}
    median_height = statistics.median(heights)
    deviations = [abs(value - median_height) for value in heights]
    mad = statistics.median(deviations)
    threshold = max(HEIGHT_ABSOLUTE_THRESHOLD, 2.5 * mad)
    rows: list[dict[str, Any]] = []
    for idx, (pair, height) in enumerate(zip(pairs, heights)):
        local_indices = [
            offset % len(heights)
            for offset in range(idx - max(0, local_window), idx + max(0, local_window) + 1)
        ]
        local_median = statistics.median([heights[item] for item in local_indices])
        residual = height - median_height
        rows.append(
            {
                "effective_pair_index": pair["effective_pair_index"],
                "source_preview_order_index": pair.get("source_preview_order_index"),
                "wall_height": height,
                "median_wall_height": median_height,
                "height_residual": residual,
                "height_residual_abs": abs(residual),
                "local_height_median": local_median,
                "local_height_residual": height - local_median,
                "suspicious_low_height": residual < -threshold,
                "suspicious_high_height": residual > threshold,
                "suspicious_threshold": threshold,
            }
        )
    return {
        "pairs": rows,
        "summary": {
            "n_pairs": len(rows),
            "median_wall_height": median_height,
            "height_mad": mad,
            "height_residual_sum": sum(abs(row["height_residual"]) for row in rows),
            "height_residual_max": max(abs(row["height_residual"]) for row in rows),
            "suspicious_low_pair_indices": [
                row["effective_pair_index"] for row in rows if row["suspicious_low_height"]
            ],
            "suspicious_high_pair_indices": [
                row["effective_pair_index"] for row in rows if row["suspicious_high_height"]
            ],
        },
    }


def compute_dense_pair_metrics(projected_layout: Mapping[str, Any]) -> dict[str, Any]:
    pairs = list(projected_layout.get("pairs", []))
    floorprint = compute_floorprint_metrics(projected_layout)
    wall_lookup: dict[frozenset[int], Mapping[str, Any]] = {
        frozenset((int(row["from_pair"]), int(row["to_pair"]))): row
        for row in floorprint["walls"]
    }
    rows: list[dict[str, Any]] = []
    mode = projected_layout.get("coordinate_mode")
    width = float(projected_layout.get("width", 1))
    for i, left in enumerate(pairs):
        for right in pairs[i + 1 :]:
            left_center = float(left["normalized"]["x"])
            right_center = float(right["normalized"]["x"])
            center_px = abs(right_center - left_center)
            center_percent = center_px / width * 100.0
            left_floor = _point_xz(left, "floor_3d")
            right_floor = _point_xz(right, "floor_3d")
            separation = math.dist(left_floor, right_floor)
            floor_delta = abs(float(left["floor_distance"]) - float(right["floor_distance"]))
            relation = wall_lookup.get(
                frozenset(
                    (int(left["effective_pair_index"]), int(right["effective_pair_index"]))
                )
            )
            min_wall = float(relation["floor_wall_length"]) if relation else None
            warnings = [*left.get("warnings", []), *right.get("warnings", [])]
            if center_percent >= CENTER_X_DUPLICATE_THRESHOLD_PERCENT:
                classification = "not_dense_2d"
            elif warnings:
                classification = "unresolved_dense_corner"
            elif (
                separation >= BEV_DISTINCT_DISTANCE_THRESHOLD
                or floor_delta >= FLOOR_DISTANCE_DISTINCT_THRESHOLD
            ) and (min_wall is None or min_wall >= MIN_ADJACENT_WALL_LENGTH_FOR_DISTINCT):
                classification = "dense_but_distinct_3d_corner"
            elif (
                separation <= TRUE_DUPLICATE_BEV_DISTANCE_THRESHOLD
                and floor_delta <= TRUE_DUPLICATE_FLOOR_DISTANCE_THRESHOLD
            ):
                classification = "true_duplicate_2d_3d"
            else:
                classification = "unresolved_dense_corner"
            rows.append(
                {
                    "pair_i": left["effective_pair_index"],
                    "pair_j": right["effective_pair_index"],
                    "center_x_separation": center_percent if mode == "ls_percent" else center_px,
                    "center_x_separation_percent": center_percent,
                    "center_x_separation_px": center_px,
                    "floor_3d_separation": separation,
                    "floor_distance_delta": floor_delta,
                    "short_wall_relation": bool(relation and relation.get("short_wall")),
                    "adjacent_wall_length": min_wall,
                    "classification": classification,
                    "warnings": warnings,
                }
            )
    return {
        "pairs": rows,
        "summary": {
            "n_pair_relations": len(rows),
            "dense_relations": [
                row for row in rows if row["classification"] != "not_dense_2d"
            ],
        },
    }


def compute_all_geometry_metrics(projected_layout: Mapping[str, Any]) -> dict[str, Any]:
    """Compute all M15.19 metric families for one projected variant."""

    return {
        "floorprint": compute_floorprint_metrics(projected_layout),
        "corner_turns": compute_corner_turn_metrics(projected_layout),
        "heights": compute_height_metrics(projected_layout),
        "dense_pairs": compute_dense_pair_metrics(projected_layout),
    }
