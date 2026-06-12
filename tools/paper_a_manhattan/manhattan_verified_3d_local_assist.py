"""Verified 3D local assist harness for Paper A Manhattan tools.

This module is experiment-outside, expert-side, and dry-run only. It never
applies edits, writes annotations, changes pair order, emits UI state, or feeds
formal g_t, routing, worker-quality, or P1/C1/C2/T1/V1 artifacts.
"""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from tools.paper_a_manhattan.manhattan_layout_state import build_room_layout_state


VERIFIED_3D_LOCAL_ASSIST_VERSION = "verified_3d_local_assist_m15_15_v1"
OPERATION_FAMILY = "verified_3d_local_assist"
TRANSLATE_SINGLE_PAIR_X_DRYRUN = "translate_single_pair_x_dryrun"
TRANSLATE_PAIR_CLUSTER_X_DRYRUN = "translate_pair_cluster_x_dryrun"
SEPARATE_DENSE_PAIR_X_DRYRUN = "separate_dense_pair_x_dryrun"

CENTER_X_DUPLICATE_THRESHOLD_PERCENT = 1.0
BEV_DISTINCT_DISTANCE_THRESHOLD = 0.3
FLOOR_DISTANCE_DISTINCT_THRESHOLD = 0.3
TRUE_DUPLICATE_BEV_DISTANCE_THRESHOLD = 0.1
TRUE_DUPLICATE_FLOOR_DISTANCE_THRESHOLD = 0.1
MIN_ADJACENT_WALL_LENGTH_FOR_DISTINCT = 0.2
MAX_LOCAL_X_TRANSLATION_ABS_PERCENT = 0.5
DEFAULT_DX_GRID = (0.25, 0.5)
SUGGESTED_SCORE_DELTA_THRESHOLD = -0.01
MIN_LOCAL_WALL_LENGTH = 0.05
MAX_WALL_LENGTH_CHANGE = 1.0
ANGLE_WARNING_DEG = 15.0


def _pair_index_set(target_pair_indices: Sequence[Any] | None) -> set[int]:
    if target_pair_indices is None:
        return set()
    output: set[int] = set()
    for value in target_pair_indices:
        if isinstance(value, bool):
            continue
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            continue
        if parsed > 0:
            output.add(parsed)
    return output


def _topology_override_active(topology_override: Mapping[str, Any] | None) -> bool:
    if not topology_override:
        return False
    return (
        topology_override.get("preview_order_override_active") is True
        and topology_override.get("order_verified_by_expert") is True
        and topology_override.get("topology_source") == "expert_verified_preview_order"
    )


def _as_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _corner_lookup(state: Mapping[str, Any]) -> dict[int, Mapping[str, Any]]:
    lookup: dict[int, Mapping[str, Any]] = {}
    for corner in state.get("corners", []):
        pair_index = corner.get("pair_index")
        if isinstance(pair_index, int):
            lookup[pair_index] = corner
    return lookup


def _diagnostic_lookup(state: Mapping[str, Any]) -> dict[int, Mapping[str, Any]]:
    lookup: dict[int, Mapping[str, Any]] = {}
    for diagnostic in state.get("pair_diagnostics", []):
        pair_index = diagnostic.get("pair_index")
        if isinstance(pair_index, int):
            lookup[pair_index] = diagnostic
    return lookup


def _wall_lengths_by_pair(state: Mapping[str, Any]) -> dict[int, list[float]]:
    output: dict[int, list[float]] = {}
    for wall in state.get("walls", []):
        length = _as_float(wall.get("length"))
        if length is None:
            continue
        for key in ("from_pair_index", "to_pair_index"):
            pair_index = wall.get(key)
            if isinstance(pair_index, int):
                output.setdefault(pair_index, []).append(length)
    return output


def _bev_from_corner(corner: Mapping[str, Any]) -> tuple[float | None, float | None]:
    distance = _as_float(corner.get("floor_distance"))
    u_rad = _as_float(corner.get("u_rad"))
    if distance is None or u_rad is None:
        return None, None
    return distance * math.cos(u_rad), distance * math.sin(u_rad)


def _source_index_lookup(
    pair_index_mapping: Sequence[Mapping[str, Any]] | None,
) -> dict[int, int]:
    lookup: dict[int, int] = {}
    if pair_index_mapping:
        for row in pair_index_mapping:
            effective = row.get("effective_pair_index")
            source = row.get("source_preview_order_index")
            if isinstance(effective, int) and isinstance(source, int):
                lookup[effective] = source
    return lookup


def _source_index(pair_index: int, source_lookup: Mapping[int, int]) -> int:
    return int(source_lookup.get(pair_index, pair_index))


def _deg(value_rad: float) -> float:
    return math.degrees(value_rad)


def _nearest_axis_deg(direction_rad: float) -> float:
    direction_deg = _deg(direction_rad)
    return round(direction_deg / 90.0) * 90.0


def _wall_angle_table(
    state: Mapping[str, Any],
    source_lookup: Mapping[int, int],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for wall in state.get("walls", []):
        direction = _as_float(wall.get("direction_rad"))
        if direction is None:
            direction_deg = None
            nearest_axis = None
            residual_deg = None
        else:
            direction_deg = _deg(direction)
            nearest_axis = _nearest_axis_deg(direction)
            residual_deg = _deg(_nearest_manhattan_angle_residual(direction))
        from_pair = wall.get("from_pair_index")
        to_pair = wall.get("to_pair_index")
        rows.append(
            {
                "wall_index": wall.get("wall_index"),
                "from_pair_index": from_pair,
                "to_pair_index": to_pair,
                "from_source_preview_order_index": (
                    _source_index(from_pair, source_lookup)
                    if isinstance(from_pair, int)
                    else None
                ),
                "to_source_preview_order_index": (
                    _source_index(to_pair, source_lookup)
                    if isinstance(to_pair, int)
                    else None
                ),
                "direction_deg": direction_deg,
                "nearest_manhattan_axis_deg": nearest_axis,
                "angle_residual_deg": residual_deg,
                "length": wall.get("length"),
            }
        )
    return rows


def _bev_points_by_pair(state: Mapping[str, Any]) -> dict[int, tuple[float, float]]:
    output: dict[int, tuple[float, float]] = {}
    for corner in state.get("corners", []):
        pair_index = corner.get("pair_index")
        x, y = _bev_from_corner(corner)
        if isinstance(pair_index, int) and x is not None and y is not None:
            output[pair_index] = (x, y)
    return output


def _turn_angle_deg(
    prev_point: tuple[float, float],
    point: tuple[float, float],
    next_point: tuple[float, float],
) -> float | None:
    v1 = (prev_point[0] - point[0], prev_point[1] - point[1])
    v2 = (next_point[0] - point[0], next_point[1] - point[1])
    n1 = math.hypot(v1[0], v1[1])
    n2 = math.hypot(v2[0], v2[1])
    if n1 == 0 or n2 == 0:
        return None
    dot = v1[0] * v2[0] + v1[1] * v2[1]
    cos_value = max(-1.0, min(1.0, dot / (n1 * n2)))
    return math.degrees(math.acos(cos_value))


def _corner_angle_table(
    state: Mapping[str, Any],
    source_lookup: Mapping[int, int],
) -> list[dict[str, Any]]:
    corners = list(state.get("corners", []))
    bev_points = _bev_points_by_pair(state)
    n_corners = len(corners)
    rows: list[dict[str, Any]] = []
    if n_corners < 3:
        return rows
    for index, corner in enumerate(corners):
        pair_index = corner.get("pair_index")
        prev_corner = corners[(index - 1) % n_corners]
        next_corner = corners[(index + 1) % n_corners]
        if not all(
            isinstance(row.get("pair_index"), int)
            for row in (prev_corner, corner, next_corner)
        ):
            continue
        prev_pair = int(prev_corner["pair_index"])
        current_pair = int(pair_index)
        next_pair = int(next_corner["pair_index"])
        angle = None
        residual = None
        if (
            prev_pair in bev_points
            and current_pair in bev_points
            and next_pair in bev_points
        ):
            angle = _turn_angle_deg(
                bev_points[prev_pair],
                bev_points[current_pair],
                bev_points[next_pair],
            )
            residual = abs(angle - 90.0) if angle is not None else None
        rows.append(
            {
                "corner_pair_index": current_pair,
                "corner_source_preview_order_index": _source_index(
                    current_pair,
                    source_lookup,
                ),
                "prev_wall_index": index if index > 0 else n_corners,
                "next_wall_index": index + 1,
                "turn_angle_deg": angle,
                "angle_to_90_residual_deg": residual,
                "local_angle_warning": (
                    "turn_angle_far_from_90"
                    if residual is not None and residual > ANGLE_WARNING_DEG
                    else None
                ),
            }
        )
    return rows


def _build_local_3d_diagnostics(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    corners = _corner_lookup(state)
    diagnostics = _diagnostic_lookup(state)
    wall_lengths = _wall_lengths_by_pair(state)
    rows: list[dict[str, Any]] = []
    for pair_index in sorted(corners):
        corner = corners[pair_index]
        diagnostic = diagnostics.get(pair_index, {})
        bev_x, bev_y = _bev_from_corner(corner)
        rows.append(
            {
                "pair_index": pair_index,
                "center_x": corner.get("center_x"),
                "floor_distance": corner.get("floor_distance"),
                "ceiling_height_estimate": corner.get("ceiling_height_estimate"),
                "bev_x": bev_x,
                "bev_y": bev_y,
                "adjacent_wall_lengths": list(wall_lengths.get(pair_index, [])),
                "pair_height_residual": diagnostic.get("height_residual"),
                "pair_warnings": list(diagnostic.get("warnings", [])),
            }
        )
    return rows


def _row_by_pair(rows: Sequence[Mapping[str, Any]]) -> dict[int, Mapping[str, Any]]:
    lookup: dict[int, Mapping[str, Any]] = {}
    for row in rows:
        pair_index = row.get("pair_index")
        if isinstance(pair_index, int):
            lookup[pair_index] = row
    return lookup


def _bev_distance(left: Mapping[str, Any], right: Mapping[str, Any]) -> float | None:
    lx = _as_float(left.get("bev_x"))
    ly = _as_float(left.get("bev_y"))
    rx = _as_float(right.get("bev_x"))
    ry = _as_float(right.get("bev_y"))
    if None in (lx, ly, rx, ry):
        return None
    return math.hypot(rx - lx, ry - ly)


def _min_adjacent_wall_length(*rows: Mapping[str, Any]) -> float | None:
    lengths: list[float] = []
    for row in rows:
        for value in row.get("adjacent_wall_lengths", []):
            parsed = _as_float(value)
            if parsed is not None:
                lengths.append(parsed)
    if not lengths:
        return None
    return min(lengths)


def _classification_reason_tokens(
    *,
    bev_distance: float | None,
    floor_distance_delta: float | None,
    min_adjacent_wall_length: float | None,
    warnings: Sequence[str],
) -> list[str]:
    reasons: list[str] = []
    if warnings:
        reasons.append("pair_or_state_warning_present")
    if bev_distance is None or floor_distance_delta is None:
        reasons.append("missing_3d_metric")
    else:
        if bev_distance >= BEV_DISTINCT_DISTANCE_THRESHOLD:
            reasons.append("bev_distance_separates_dense_pair")
        if floor_distance_delta >= FLOOR_DISTANCE_DISTINCT_THRESHOLD:
            reasons.append("floor_distance_delta_separates_dense_pair")
        if (
            bev_distance <= TRUE_DUPLICATE_BEV_DISTANCE_THRESHOLD
            and floor_distance_delta <= TRUE_DUPLICATE_FLOOR_DISTANCE_THRESHOLD
        ):
            reasons.append("bev_and_depth_also_near_duplicate")
    if (
        min_adjacent_wall_length is not None
        and min_adjacent_wall_length < MIN_ADJACENT_WALL_LENGTH_FOR_DISTINCT
    ):
        reasons.append("adjacent_wall_too_short_for_confident_split")
    return reasons


def _reclassify_dense_corners(
    local_rows: Sequence[Mapping[str, Any]],
    state: Mapping[str, Any],
) -> list[dict[str, Any]]:
    rows = sorted(local_rows, key=lambda row: float(row.get("center_x", 0.0)))
    state_warnings = list(state.get("state_warnings", []))
    output: list[dict[str, Any]] = []
    for left, right in zip(rows, rows[1:]):
        left_center = _as_float(left.get("center_x"))
        right_center = _as_float(right.get("center_x"))
        if left_center is None or right_center is None:
            continue
        center_delta = abs(right_center - left_center)
        if center_delta >= CENTER_X_DUPLICATE_THRESHOLD_PERCENT:
            continue
        distance = _bev_distance(left, right)
        left_floor = _as_float(left.get("floor_distance"))
        right_floor = _as_float(right.get("floor_distance"))
        floor_delta = (
            abs(right_floor - left_floor)
            if left_floor is not None and right_floor is not None
            else None
        )
        pair_warnings = [
            *left.get("pair_warnings", []),
            *right.get("pair_warnings", []),
        ]
        warnings = [*state_warnings, *pair_warnings]
        blocking_warnings = [
            warning
            for warning in warnings
            if warning
            in {
                "layout_height_spread_high",
                "wrap_seam_unresolved",
                "top_not_above_bottom",
                "vertical_corner_x_mismatch",
            }
        ]
        min_wall = _min_adjacent_wall_length(left, right)
        reasons = _classification_reason_tokens(
            bev_distance=distance,
            floor_distance_delta=floor_delta,
            min_adjacent_wall_length=min_wall,
            warnings=warnings,
        )
        if blocking_warnings or distance is None or floor_delta is None:
            classification = "unresolved_dense_corner"
        elif (
            distance >= BEV_DISTINCT_DISTANCE_THRESHOLD
            or floor_delta >= FLOOR_DISTANCE_DISTINCT_THRESHOLD
        ) and (
            min_wall is None
            or min_wall >= MIN_ADJACENT_WALL_LENGTH_FOR_DISTINCT
        ):
            classification = "dense_but_distinct_3d_corner"
        elif (
            distance <= TRUE_DUPLICATE_BEV_DISTANCE_THRESHOLD
            and floor_delta <= TRUE_DUPLICATE_FLOOR_DISTANCE_THRESHOLD
        ):
            classification = "true_duplicate_2d_3d"
        else:
            classification = "unresolved_dense_corner"
        output.append(
            {
                "left_pair_index": left["pair_index"],
                "right_pair_index": right["pair_index"],
                "left_center_x": left_center,
                "right_center_x": right_center,
                "delta_center_x": center_delta,
                "duplicate_threshold_percent": CENTER_X_DUPLICATE_THRESHOLD_PERCENT,
                "bev_distance": distance,
                "floor_distance_delta": floor_delta,
                "min_adjacent_wall_length": min_wall,
                "classification": classification,
                "reason_tokens": reasons,
                "manual_only": True,
            }
        )
    return output


def _metric_summary(
    state: Mapping[str, Any],
    target_pair_indices: Sequence[int],
) -> dict[str, Any]:
    diagnostic_lookup = _diagnostic_lookup(state)
    target_residuals = [
        _as_float(diagnostic_lookup[pair_index].get("height_residual"))
        for pair_index in target_pair_indices
        if pair_index in diagnostic_lookup
    ]
    target_residuals = [value for value in target_residuals if value is not None]
    return {
        "state_status": state.get("state_status"),
        "state_warnings": list(state.get("state_warnings", [])),
        "layout_height_candidate": state.get("layout_height_candidate"),
        "layout_height_spread": state.get("layout_height_spread"),
        "target_height_residual_max": max(target_residuals) if target_residuals else None,
        "target_height_residual_sum": sum(target_residuals) if target_residuals else None,
    }


def _nearest_manhattan_angle_residual(direction_rad: float) -> float:
    half_pi = math.pi / 2.0
    return abs((direction_rad + half_pi / 2.0) % half_pi - half_pi / 2.0)


def _local_wall_indices(state: Mapping[str, Any], target_pair_indices: Sequence[int]) -> set[int]:
    target_set = set(target_pair_indices)
    wall_indices: set[int] = set()
    for wall in state.get("walls", []):
        if (
            wall.get("from_pair_index") in target_set
            or wall.get("to_pair_index") in target_set
        ):
            wall_index = wall.get("wall_index")
            if isinstance(wall_index, int):
                wall_indices.add(wall_index)
    return wall_indices


def _segments_intersect(
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
    d: tuple[float, float],
) -> bool:
    def orient(p: tuple[float, float], q: tuple[float, float], r: tuple[float, float]) -> float:
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    o1 = orient(a, b, c)
    o2 = orient(a, b, d)
    o3 = orient(c, d, a)
    o4 = orient(c, d, b)
    return o1 * o2 < 0 and o3 * o4 < 0


def _has_self_intersection(state: Mapping[str, Any]) -> bool | None:
    points: list[tuple[float, float]] = []
    for corner in state.get("corners", []):
        x, y = _bev_from_corner(corner)
        if x is None or y is None:
            return None
        points.append((x, y))
    if len(points) < 4:
        return False
    n_points = len(points)
    for i in range(n_points):
        a = points[i]
        b = points[(i + 1) % n_points]
        for j in range(i + 1, n_points):
            if j in {i, (i - 1) % n_points, (i + 1) % n_points}:
                continue
            if i == 0 and j == n_points - 1:
                continue
            c = points[j]
            d = points[(j + 1) % n_points]
            if _segments_intersect(a, b, c, d):
                return True
    return False


def _dense_pair_metrics(
    state: Mapping[str, Any],
    target_pair_indices: Sequence[int],
) -> tuple[float | None, float | None]:
    if len(target_pair_indices) != 2:
        return None, None
    rows = _row_by_pair(_build_local_3d_diagnostics(state))
    left = rows.get(target_pair_indices[0])
    right = rows.get(target_pair_indices[1])
    if left is None or right is None:
        return None, None
    left_floor = _as_float(left.get("floor_distance"))
    right_floor = _as_float(right.get("floor_distance"))
    return (
        _bev_distance(left, right),
        abs(right_floor - left_floor)
        if left_floor is not None and right_floor is not None
        else None,
    )


def _local_geometry_metrics(
    state: Mapping[str, Any],
    target_pair_indices: Sequence[int],
    *,
    before_state: Mapping[str, Any] | None = None,
    movement_abs_max: float = 0.0,
) -> dict[str, Any]:
    reasons: list[str] = []
    if state.get("state_status") != "ok":
        reasons.append("state_not_ok")
        return {
            "local_manhattan_angle_residual_sum": None,
            "local_manhattan_angle_residual_max": None,
            "local_wall_length_min": None,
            "local_wall_length_ratio": None,
            "local_wall_length_change_max": None,
            "local_fold_or_self_intersection": None,
            "dense_pair_bev_distance": None,
            "dense_pair_floor_distance_delta": None,
            "movement_abs_max": movement_abs_max,
            "movement_penalty": movement_abs_max / MAX_LOCAL_X_TRANSLATION_ABS_PERCENT,
            "local_geometry_score": None,
            "metric_unavailable_reasons": reasons,
        }

    wall_indices = _local_wall_indices(state, target_pair_indices)
    local_walls = [
        wall for wall in state.get("walls", []) if wall.get("wall_index") in wall_indices
    ]
    if not local_walls:
        reasons.append("no_local_walls")
    angle_residuals = [
        _nearest_manhattan_angle_residual(float(wall["direction_rad"]))
        for wall in local_walls
        if _as_float(wall.get("direction_rad")) is not None
    ]
    lengths = [
        _as_float(wall.get("length"))
        for wall in local_walls
        if _as_float(wall.get("length")) is not None
    ]
    wall_length_min = min(lengths) if lengths else None
    wall_length_ratio = (
        min(lengths) / max(lengths)
        if lengths and max(lengths) > 0
        else None
    )

    length_change_max = None
    if before_state is not None:
        before_lengths = {
            wall.get("wall_index"): _as_float(wall.get("length"))
            for wall in before_state.get("walls", [])
        }
        changes: list[float] = []
        for wall in local_walls:
            wall_index = wall.get("wall_index")
            before_length = before_lengths.get(wall_index)
            after_length = _as_float(wall.get("length"))
            if before_length is not None and after_length is not None:
                changes.append(abs(after_length - before_length))
        length_change_max = max(changes) if changes else 0.0

    self_intersection = _has_self_intersection(state)
    if self_intersection is None:
        reasons.append("self_intersection_unavailable")
    dense_bev, dense_floor = _dense_pair_metrics(state, target_pair_indices)

    movement_penalty = movement_abs_max / MAX_LOCAL_X_TRANSLATION_ABS_PERCENT
    angle_sum = sum(angle_residuals) if angle_residuals else None
    angle_max = max(angle_residuals) if angle_residuals else None
    short_wall_penalty = (
        max(0.0, MIN_LOCAL_WALL_LENGTH - wall_length_min) * 10.0
        if wall_length_min is not None
        else 1.0
    )
    wall_ratio_penalty = (
        (1.0 - wall_length_ratio) * 0.1
        if wall_length_ratio is not None
        else 1.0
    )
    wall_change_penalty = (length_change_max or 0.0) * 0.1
    self_intersection_penalty = 10.0 if self_intersection else 0.0
    local_geometry_score = (
        (angle_sum if angle_sum is not None else 1.0)
        + short_wall_penalty
        + wall_ratio_penalty
        + wall_change_penalty
        + self_intersection_penalty
        + movement_penalty * 0.01
    )
    return {
        "local_manhattan_angle_residual_sum": angle_sum,
        "local_manhattan_angle_residual_max": angle_max,
        "local_wall_length_min": wall_length_min,
        "local_wall_length_ratio": wall_length_ratio,
        "local_wall_length_change_max": length_change_max,
        "local_fold_or_self_intersection": self_intersection,
        "dense_pair_bev_distance": dense_bev,
        "dense_pair_floor_distance_delta": dense_floor,
        "movement_abs_max": movement_abs_max,
        "movement_penalty": movement_penalty,
        "local_geometry_score": local_geometry_score,
        "metric_unavailable_reasons": reasons,
    }


def _geometry_metric_deltas(
    before_metrics: Mapping[str, Any],
    after_metrics: Mapping[str, Any],
) -> dict[str, Any]:
    deltas: dict[str, Any] = {}
    for key in (
        "local_manhattan_angle_residual_sum",
        "local_manhattan_angle_residual_max",
        "local_wall_length_min",
        "local_wall_length_ratio",
        "local_wall_length_change_max",
        "dense_pair_bev_distance",
        "dense_pair_floor_distance_delta",
        "movement_abs_max",
        "movement_penalty",
        "local_geometry_score",
    ):
        before = _as_float(before_metrics.get(key))
        after = _as_float(after_metrics.get(key))
        deltas[key] = after - before if before is not None and after is not None else None
    return deltas


def _wall_angle_summary(
    wall_angle_rows: Sequence[Mapping[str, Any]],
    affected_wall_indices: Sequence[int],
) -> dict[str, Any]:
    affected = set(affected_wall_indices)
    residuals = [
        _as_float(row.get("angle_residual_deg"))
        for row in wall_angle_rows
        if row.get("wall_index") in affected
    ]
    residuals = [value for value in residuals if value is not None]
    return {
        "wall_angle_residual_sum_deg": sum(residuals) if residuals else None,
        "wall_angle_residual_max_deg": max(residuals) if residuals else None,
        "n_walls": len(residuals),
    }


def _summary_delta(
    before_summary: Mapping[str, Any],
    after_summary: Mapping[str, Any],
    key: str,
) -> float | None:
    before = _as_float(before_summary.get(key))
    after = _as_float(after_summary.get(key))
    return after - before if before is not None and after is not None else None


def _affected_wall_indices(state: Mapping[str, Any], target_pair_indices: Sequence[int]) -> list[int]:
    return sorted(_local_wall_indices(state, target_pair_indices))


def _affected_corner_indices(target_pair_indices: Sequence[int]) -> list[int]:
    return sorted(set(target_pair_indices))


def _center_xs(ordered_pairs: Sequence[Mapping[str, Any]]) -> dict[int, float]:
    centers: dict[int, float] = {}
    for index, pair in enumerate(ordered_pairs, start=1):
        top = pair.get("top", {})
        bottom = pair.get("bottom", {})
        top_x = _as_float(top.get("x"))
        bottom_x = _as_float(bottom.get("x"))
        if top_x is not None and bottom_x is not None:
            centers[index] = (top_x + bottom_x) / 2.0
    return centers


def _x_order_crossing(
    before_pairs: Sequence[Mapping[str, Any]],
    after_pairs: Sequence[Mapping[str, Any]],
    target_pair_indices: Sequence[int],
) -> tuple[bool, list[int]]:
    before_centers = _center_xs(before_pairs)
    after_centers = _center_xs(after_pairs)
    target_set = set(target_pair_indices)
    crossed: set[int] = set()
    for target in target_set:
        if target not in before_centers or target not in after_centers:
            continue
        for other, before_other in before_centers.items():
            if other == target or other not in after_centers:
                continue
            before_delta = before_centers[target] - before_other
            after_delta = after_centers[target] - after_centers[other]
            if before_delta == 0 or after_delta == 0:
                continue
            if before_delta * after_delta < 0:
                crossed.add(other)
    return bool(crossed), sorted(crossed)


def _apply_x_offsets(
    ordered_pairs: Sequence[Mapping[str, Any]],
    offsets: Mapping[int, float],
) -> list[dict[str, Any]]:
    candidate: list[dict[str, Any]] = []
    for index, pair in enumerate(ordered_pairs, start=1):
        top = dict(pair["top"])
        bottom = dict(pair["bottom"])
        dx = offsets.get(index)
        if dx is not None:
            top["x"] = float(top["x"]) + dx
            bottom["x"] = float(bottom["x"]) + dx
        candidate.append({"top": top, "bottom": bottom})
    return candidate


def _candidate_risk_reasons(
    before_metrics: Mapping[str, Any],
    after_metrics: Mapping[str, Any],
    before_local_metrics: Mapping[str, Any],
    after_local_metrics: Mapping[str, Any],
    state: Mapping[str, Any],
    movement_abs_max: float,
) -> list[str]:
    reasons: list[str] = []
    if movement_abs_max > MAX_LOCAL_X_TRANSLATION_ABS_PERCENT:
        reasons.append("x_translation_too_large")
    if before_metrics.get("state_status") == "ok" and after_metrics.get("state_status") != "ok":
        reasons.append("state_status_worsened")
    after_warnings = set(after_metrics.get("state_warnings", []))
    if "wrap_seam_unresolved" in after_warnings:
        reasons.append("wrap_seam_unresolved_after_translation")
    for diagnostic in state.get("pair_diagnostics", []):
        if "top_not_above_bottom" in diagnostic.get("warnings", []):
            reasons.append("top_not_above_bottom_after_translation")
            break
    if after_local_metrics.get("local_fold_or_self_intersection") is True:
        reasons.append("local_fold_or_self_intersection")
    wall_min = _as_float(after_local_metrics.get("local_wall_length_min"))
    if wall_min is not None and wall_min < MIN_LOCAL_WALL_LENGTH:
        reasons.append("local_wall_too_short")
    wall_change = _as_float(after_local_metrics.get("local_wall_length_change_max"))
    if wall_change is not None and wall_change > MAX_WALL_LENGTH_CHANGE:
        reasons.append("local_wall_length_change_too_large")
    return sorted(set(reasons))


def _improved_metrics(
    before_metrics: Mapping[str, Any],
    after_metrics: Mapping[str, Any],
) -> dict[str, Any]:
    before_spread = _as_float(before_metrics.get("layout_height_spread"))
    after_spread = _as_float(after_metrics.get("layout_height_spread"))
    before_residual = _as_float(before_metrics.get("target_height_residual_sum"))
    after_residual = _as_float(after_metrics.get("target_height_residual_sum"))
    return {
        "layout_height_spread_delta": (
            after_spread - before_spread
            if before_spread is not None and after_spread is not None
            else None
        ),
        "target_height_residual_sum_delta": (
            after_residual - before_residual
            if before_residual is not None and after_residual is not None
            else None
        ),
    }


def _candidate_decision(
    risk_reasons: Sequence[str],
    score_delta: float | None,
) -> tuple[str, list[str]]:
    if risk_reasons:
        return "suppress", list(risk_reasons)
    if score_delta is not None and score_delta <= SUGGESTED_SCORE_DELTA_THRESHOLD:
        return "suggested_review", ["local_geometry_score_improved"]
    return "neutral_review", ["no_clear_local_geometry_score_improvement"]


def _target_clusters(
    dense_reclassification: Sequence[Mapping[str, Any]],
    target_pair_indices: Sequence[Any] | None,
) -> list[list[int]]:
    explicit_targets = sorted(_pair_index_set(target_pair_indices))
    if explicit_targets:
        return [[pair_index] for pair_index in explicit_targets]
    clusters: list[list[int]] = []
    for row in dense_reclassification:
        if row.get("classification") != "dense_but_distinct_3d_corner":
            continue
        clusters.append([int(row["left_pair_index"]), int(row["right_pair_index"])])
    return clusters


def _candidate_specs_for_cluster(cluster: Sequence[int]) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for pair_index in cluster:
        for dx in (-0.5, -0.25, 0.25, 0.5):
            specs.append(
                {
                    "candidate_family": TRANSLATE_SINGLE_PAIR_X_DRYRUN,
                    "target_pair_indices": [pair_index],
                    "dx": dx,
                    "offsets": {pair_index: dx},
                }
            )
    for dx in (-0.5, -0.25, 0.25, 0.5):
        specs.append(
            {
                "candidate_family": TRANSLATE_PAIR_CLUSTER_X_DRYRUN,
                "target_pair_indices": list(cluster),
                "dx": dx,
                "offsets": {pair_index: dx for pair_index in cluster},
            }
        )
    if len(cluster) == 2:
        left, right = cluster
        for dx in DEFAULT_DX_GRID:
            specs.append(
                {
                    "candidate_family": SEPARATE_DENSE_PAIR_X_DRYRUN,
                    "target_pair_indices": [left, right],
                    "dx": dx,
                    "offsets": {left: -dx, right: dx},
                    "separation_direction": "left_negative_right_positive",
                }
            )
            specs.append(
                {
                    "candidate_family": SEPARATE_DENSE_PAIR_X_DRYRUN,
                    "target_pair_indices": [left, right],
                    "dx": dx,
                    "offsets": {left: dx, right: -dx},
                    "separation_direction": "left_positive_right_negative",
                }
            )
    return specs


def _explicit_candidate_specs(target_pair_indices: Sequence[Any] | None) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for pair_index in sorted(_pair_index_set(target_pair_indices)):
        for dx in (-0.5, -0.25, 0.25, 0.5):
            specs.append(
                {
                    "candidate_family": TRANSLATE_SINGLE_PAIR_X_DRYRUN,
                    "candidate_source": "explicit_target_pair_indices",
                    "target_pair_indices": [pair_index],
                    "dx": dx,
                    "offsets": {pair_index: dx},
                }
            )
    return specs


def _build_translation_candidates(
    ordered_pairs: Sequence[Mapping[str, Any]],
    metadata: Mapping[str, Any] | None,
    topology_override: Mapping[str, Any] | None,
    dense_reclassification: Sequence[Mapping[str, Any]],
    target_pair_indices: Sequence[Any] | None,
    before_state: Mapping[str, Any],
    source_lookup: Mapping[int, int],
) -> list[dict[str, Any]]:
    explicit_targets = sorted(_pair_index_set(target_pair_indices))
    specs = _explicit_candidate_specs(explicit_targets)
    if _topology_override_active(topology_override):
        for cluster in _target_clusters(dense_reclassification, None):
            specs.extend(_candidate_specs_for_cluster(cluster))
    if not specs:
        return []
    candidates: list[dict[str, Any]] = []
    for spec in specs:
        cluster = list(spec["target_pair_indices"])
        offsets = dict(spec["offsets"])
        movement_abs_max = max(abs(value) for value in offsets.values())
        before_metrics = _metric_summary(before_state, cluster)
        before_local_metrics = _local_geometry_metrics(
            before_state,
            cluster,
            movement_abs_max=0.0,
        )
        candidate_pairs = _apply_x_offsets(ordered_pairs, offsets)
        after_state = build_room_layout_state(candidate_pairs, metadata=metadata)
        after_metrics = _metric_summary(after_state, cluster)
        affected_walls = _affected_wall_indices(before_state, cluster)
        affected_corners = _affected_corner_indices(cluster)
        before_angle_summary = _wall_angle_summary(
            _wall_angle_table(before_state, source_lookup),
            affected_walls,
        )
        after_angle_summary = _wall_angle_summary(
            _wall_angle_table(after_state, source_lookup),
            affected_walls,
        )
        after_local_metrics = _local_geometry_metrics(
            after_state,
            cluster,
            before_state=before_state,
            movement_abs_max=movement_abs_max,
        )
        improved = _improved_metrics(before_metrics, after_metrics)
        geometry_deltas = _geometry_metric_deltas(before_local_metrics, after_local_metrics)
        score_before = _as_float(before_local_metrics.get("local_geometry_score"))
        score_after = _as_float(after_local_metrics.get("local_geometry_score"))
        score_delta = (
            score_after - score_before
            if score_before is not None and score_after is not None
            else None
        )
        risks = _candidate_risk_reasons(
            before_metrics,
            after_metrics,
            before_local_metrics,
            after_local_metrics,
            after_state,
            movement_abs_max,
        )
        x_crossing, crossed_pairs = _x_order_crossing(
            ordered_pairs,
            candidate_pairs,
            cluster,
        )
        decision, decision_reasons = _candidate_decision(risks, score_delta)
        if x_crossing:
            decision_reasons = [
                *decision_reasons,
                "x_order_crossing_after_translation",
            ]
        family = str(spec["candidate_family"])
        dx = float(spec["dx"])
        candidates.append(
            {
                "candidate_id": (
                    f"{family}_{'-'.join(str(index) for index in cluster)}_{dx:+.2f}"
                    if family != SEPARATE_DENSE_PAIR_X_DRYRUN
                    else (
                        f"{family}_{'-'.join(str(index) for index in cluster)}_"
                        f"{spec.get('separation_direction')}_{dx:+.2f}"
                    )
                ),
                "operation": family,
                "candidate_family": family,
                "candidate_source": spec.get("candidate_source", "dense_corner_reclassification"),
                "target_pair_indices": list(cluster),
                "dx": dx,
                "offsets": {str(key): value for key, value in offsets.items()},
                "status": decision,
                "before_metrics": before_metrics,
                "after_metrics": after_metrics,
                "improved_metrics": improved,
                "before_local_geometry_metrics": before_local_metrics,
                "after_local_geometry_metrics": after_local_metrics,
                "geometry_metric_deltas": geometry_deltas,
                "local_geometry_score_before": score_before,
                "local_geometry_score_after": score_after,
                "local_geometry_score_delta": score_delta,
                "before_local_wall_angle_summary": before_angle_summary,
                "after_local_wall_angle_summary": after_angle_summary,
                "wall_angle_residual_sum_delta_deg": _summary_delta(
                    before_angle_summary,
                    after_angle_summary,
                    "wall_angle_residual_sum_deg",
                ),
                "wall_angle_residual_max_delta_deg": _summary_delta(
                    before_angle_summary,
                    after_angle_summary,
                    "wall_angle_residual_max_deg",
                ),
                "affected_wall_indices": affected_walls,
                "affected_corner_indices": affected_corners,
                "x_order_crossing_after_translation": x_crossing,
                "crossed_pair_indices": crossed_pairs,
                "crossing_scope": "2d_x_only_not_topology",
                "candidate_decision": decision,
                "decision_reasons": decision_reasons,
                "risk_reasons": risks,
                "expert_action_allowed": False,
                "y_change_allowed": False,
                "writeback_allowed": False,
            }
        )
    return _rank_candidates(candidates)


def _rank_candidates(candidates: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    def sort_key(candidate: Mapping[str, Any]) -> tuple[int, float, str]:
        decision_rank = {
            "suggested_review": 0,
            "neutral_review": 1,
            "suppress": 2,
        }.get(str(candidate.get("candidate_decision")), 3)
        delta = _as_float(candidate.get("local_geometry_score_delta"))
        return (decision_rank, delta if delta is not None else 999.0, str(candidate.get("candidate_id")))

    ranked = [dict(candidate) for candidate in sorted(candidates, key=sort_key)]
    for index, candidate in enumerate(ranked, start=1):
        candidate["candidate_rank"] = index
    return ranked


def build_verified_3d_local_assist(
    ordered_pairs: Sequence[Mapping[str, Any]],
    metadata: Mapping[str, Any] | None = None,
    topology_override: Mapping[str, Any] | None = None,
    target_pair_indices: Sequence[Any] | None = None,
    pair_index_mapping: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build verified 3D local assist diagnostics and dry-run candidates."""
    state = build_room_layout_state(ordered_pairs, metadata=metadata)
    source_lookup = _source_index_lookup(pair_index_mapping)
    local_diagnostics = _build_local_3d_diagnostics(state)
    dense_reclassification = _reclassify_dense_corners(local_diagnostics, state)
    wall_angles = _wall_angle_table(state, source_lookup)
    corner_angles = _corner_angle_table(state, source_lookup)
    candidates = _build_translation_candidates(
        ordered_pairs,
        metadata,
        topology_override,
        dense_reclassification,
        target_pair_indices,
        state,
        source_lookup,
    )
    return {
        "schema_version": VERIFIED_3D_LOCAL_ASSIST_VERSION,
        "operation_family": OPERATION_FAMILY,
        "state_status": state.get("state_status"),
        "state_warnings": list(state.get("state_warnings", [])),
        "before_metrics": _metric_summary(state, []),
        "local_3d_diagnostics": local_diagnostics,
        "dense_corner_reclassification": dense_reclassification,
        "wall_angle_table": wall_angles,
        "corner_angle_table": corner_angles,
        "candidate_rows": candidates,
        "risk_reasons": sorted(
            {
                reason
                for candidate in candidates
                for reason in candidate.get("risk_reasons", [])
            }
        ),
        "writeback_allowed": False,
        "ui_allowed": False,
    }


__all__ = [
    "OPERATION_FAMILY",
    "SEPARATE_DENSE_PAIR_X_DRYRUN",
    "TRANSLATE_SINGLE_PAIR_X_DRYRUN",
    "TRANSLATE_PAIR_CLUSTER_X_DRYRUN",
    "VERIFIED_3D_LOCAL_ASSIST_VERSION",
    "build_verified_3d_local_assist",
]
