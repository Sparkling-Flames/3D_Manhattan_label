"""M15.18 floor-footprint and dense-corner diagnostic sidecars.

The probes in this module are offline dry-runs. They never mutate the input,
emit annotation patches, authorize expert actions, or select topology changes.
"""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from tools.paper_a_manhattan.manhattan_layout_state import build_room_layout_state


FLOORPRINT_SENSITIVITY_VERSION = "floorprint_sensitivity_m15_18_v1"
LOCAL_DENSE_CORNER_PROBE_VERSION = "local_dense_corner_probe_m15_18_v1"
BOTTOM_Y_PERTURBATIONS = (-3.0, -2.0, -1.0, 1.0, 2.0, 3.0)
BOTTOM_X_MICRO_GRID = (-0.5, -0.25, 0.0, 0.25, 0.5)
BOTTOM_Y_MICRO_GRID = (-3.0, -2.0, -1.0, 0.0, 1.0, 2.0, 3.0)
MIN_WALL_LENGTH = 0.05
SHORT_WALL_REVIEW_LENGTH = 0.2
SCORE_IMPROVEMENT_THRESHOLD = -0.01


def _as_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _delta(before: Any, after: Any) -> float | None:
    left = _as_float(before)
    right = _as_float(after)
    return right - left if left is not None and right is not None else None


def _nearest_manhattan_residual_deg(direction_rad: float) -> float:
    half_pi = math.pi / 2.0
    residual = abs((direction_rad + half_pi / 2.0) % half_pi - half_pi / 2.0)
    return math.degrees(residual)


def _bev_points(state: Mapping[str, Any]) -> dict[int, tuple[float, float]]:
    points: dict[int, tuple[float, float]] = {}
    for corner in state.get("corners", []):
        pair_index = corner.get("pair_index")
        distance = _as_float(corner.get("floor_distance"))
        u_rad = _as_float(corner.get("u_rad"))
        if isinstance(pair_index, int) and distance is not None and u_rad is not None:
            points[pair_index] = (
                distance * math.cos(u_rad),
                distance * math.sin(u_rad),
            )
    return points


def _turn_residual_deg(
    previous: tuple[float, float],
    current: tuple[float, float],
    following: tuple[float, float],
) -> float | None:
    left = (previous[0] - current[0], previous[1] - current[1])
    right = (following[0] - current[0], following[1] - current[1])
    left_norm = math.hypot(*left)
    right_norm = math.hypot(*right)
    if left_norm == 0.0 or right_norm == 0.0:
        return None
    cosine = max(
        -1.0,
        min(1.0, (left[0] * right[0] + left[1] * right[1]) / (left_norm * right_norm)),
    )
    return abs(math.degrees(math.acos(cosine)) - 90.0)


def _affected_wall_indices(
    state: Mapping[str, Any], target_pair_indices: Sequence[int]
) -> list[int]:
    targets = set(target_pair_indices)
    return sorted(
        int(wall["wall_index"])
        for wall in state.get("walls", [])
        if isinstance(wall.get("wall_index"), int)
        and (
            wall.get("from_pair_index") in targets
            or wall.get("to_pair_index") in targets
        )
    )


def _affected_corner_indices(n_pairs: int, targets: Sequence[int]) -> list[int]:
    affected: set[int] = set()
    for target in targets:
        if 1 <= target <= n_pairs:
            affected.update(
                {
                    ((target - 2) % n_pairs) + 1,
                    target,
                    (target % n_pairs) + 1,
                }
            )
    return sorted(affected)


def _wall_summary(
    state: Mapping[str, Any], affected_wall_indices: Sequence[int]
) -> dict[str, Any]:
    affected = set(affected_wall_indices)
    residuals = [
        _nearest_manhattan_residual_deg(float(wall["direction_rad"]))
        for wall in state.get("walls", [])
        if wall.get("wall_index") in affected
        and _as_float(wall.get("direction_rad")) is not None
    ]
    return {
        "residual_sum_deg": sum(residuals) if residuals else None,
        "residual_max_deg": max(residuals) if residuals else None,
        "n_walls": len(residuals),
    }


def _corner_summary(
    state: Mapping[str, Any], affected_corner_indices: Sequence[int]
) -> dict[str, Any]:
    points = _bev_points(state)
    ordered = [
        int(corner["pair_index"])
        for corner in state.get("corners", [])
        if isinstance(corner.get("pair_index"), int)
    ]
    residuals: list[float] = []
    affected = set(affected_corner_indices)
    for position, pair_index in enumerate(ordered):
        if pair_index not in affected or len(ordered) < 3:
            continue
        previous = ordered[(position - 1) % len(ordered)]
        following = ordered[(position + 1) % len(ordered)]
        if not {previous, pair_index, following}.issubset(points):
            continue
        residual = _turn_residual_deg(
            points[previous], points[pair_index], points[following]
        )
        if residual is not None:
            residuals.append(residual)
    return {
        "residual_sum_deg": sum(residuals) if residuals else None,
        "residual_max_deg": max(residuals) if residuals else None,
        "n_corners": len(residuals),
    }


def _height_summary(
    state: Mapping[str, Any], target_pair_indices: Sequence[int]
) -> dict[str, Any]:
    targets = set(target_pair_indices)
    residuals = [
        _as_float(row.get("height_residual"))
        for row in state.get("pair_diagnostics", [])
        if row.get("pair_index") in targets
    ]
    residuals = [value for value in residuals if value is not None]
    return {
        "residual_sum": sum(residuals) if residuals else None,
        "residual_max": max(residuals) if residuals else None,
        "n_pairs": len(residuals),
    }


def _segments_intersect(
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
    d: tuple[float, float],
) -> bool:
    def orientation(
        left: tuple[float, float],
        middle: tuple[float, float],
        right: tuple[float, float],
    ) -> float:
        return (middle[0] - left[0]) * (right[1] - left[1]) - (
            middle[1] - left[1]
        ) * (right[0] - left[0])

    return (
        orientation(a, b, c) * orientation(a, b, d) < 0.0
        and orientation(c, d, a) * orientation(c, d, b) < 0.0
    )


def _has_self_intersection(state: Mapping[str, Any]) -> bool | None:
    points_by_pair = _bev_points(state)
    ordered = [
        int(corner["pair_index"])
        for corner in state.get("corners", [])
        if isinstance(corner.get("pair_index"), int)
    ]
    if len(points_by_pair) != len(ordered):
        return None
    if len(ordered) < 4:
        return False
    points = [points_by_pair[index] for index in ordered]
    for left_index in range(len(points)):
        left_a = points[left_index]
        left_b = points[(left_index + 1) % len(points)]
        for right_index in range(left_index + 1, len(points)):
            if right_index in {
                left_index,
                (left_index - 1) % len(points),
                (left_index + 1) % len(points),
            }:
                continue
            if left_index == 0 and right_index == len(points) - 1:
                continue
            if _segments_intersect(
                left_a,
                left_b,
                points[right_index],
                points[(right_index + 1) % len(points)],
            ):
                return True
    return False


def _minimum_wall_length(
    state: Mapping[str, Any], affected_wall_indices: Sequence[int]
) -> float | None:
    affected = set(affected_wall_indices)
    lengths = [
        _as_float(wall.get("length"))
        for wall in state.get("walls", [])
        if wall.get("wall_index") in affected
    ]
    lengths = [value for value in lengths if value is not None]
    return min(lengths) if lengths else None


def _snapshot(
    state: Mapping[str, Any], target_pair_indices: Sequence[int]
) -> dict[str, Any]:
    n_pairs = len(state.get("corners", []))
    walls = _affected_wall_indices(state, target_pair_indices)
    corners = _affected_corner_indices(n_pairs, target_pair_indices) if n_pairs else []
    wall_summary = _wall_summary(state, walls)
    corner_summary = _corner_summary(state, corners)
    height_summary = _height_summary(state, target_pair_indices)
    score_parts = (
        _as_float(wall_summary.get("residual_sum_deg")),
        _as_float(corner_summary.get("residual_sum_deg")),
        _as_float(height_summary.get("residual_sum")),
    )
    score = None
    if score_parts[0] is not None and score_parts[1] is not None:
        score = score_parts[0] + score_parts[1] + (score_parts[2] or 0.0) * 10.0
    return {
        "state_status": state.get("state_status"),
        "state_warnings": list(state.get("state_warnings", [])),
        "affected_wall_indices": walls,
        "affected_corner_indices": corners,
        "wall_angle_summary": wall_summary,
        "corner_angle_summary": corner_summary,
        "height_residual_summary": height_summary,
        "self_intersection": _has_self_intersection(state),
        "short_wall_length": _minimum_wall_length(state, walls),
        "local_geometry_score": score,
    }


def _copy_pairs(
    ordered_pairs: Sequence[Mapping[str, Any]],
) -> list[dict[str, dict[str, float]]]:
    return [
        {
            "top": {"x": float(pair["top"]["x"]), "y": float(pair["top"]["y"])},
            "bottom": {
                "x": float(pair["bottom"]["x"]),
                "y": float(pair["bottom"]["y"]),
            },
        }
        for pair in ordered_pairs
    ]


def _center_xs(ordered_pairs: Sequence[Mapping[str, Any]]) -> dict[int, float]:
    return {
        index: (float(pair["top"]["x"]) + float(pair["bottom"]["x"])) / 2.0
        for index, pair in enumerate(ordered_pairs, start=1)
    }


def _x_order_crossing(
    before_pairs: Sequence[Mapping[str, Any]],
    after_pairs: Sequence[Mapping[str, Any]],
    targets: Sequence[int],
) -> bool:
    before = _center_xs(before_pairs)
    after = _center_xs(after_pairs)
    for target in targets:
        for other in before:
            if other == target:
                continue
            before_delta = before[target] - before[other]
            after_delta = after[target] - after[other]
            if before_delta != 0.0 and after_delta != 0.0 and before_delta * after_delta < 0.0:
                return True
    return False


def _top_not_above_bottom(state: Mapping[str, Any]) -> bool:
    return any(
        "top_not_above_bottom" in row.get("warnings", [])
        for row in state.get("pair_diagnostics", [])
    )


def _risk_reasons(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    *,
    movement_x: float,
    movement_y: float,
) -> list[str]:
    reasons: list[str] = []
    if not math.isfinite(movement_x) or not math.isfinite(movement_y):
        reasons.append("non_finite_movement")
    if abs(movement_x) > 0.5 or abs(movement_y) > 3.0:
        reasons.append("movement_too_large")
    if before.get("state_status") == "ok" and after.get("state_status") != "ok":
        reasons.append("state_status_worsened")
    if set(after.get("state_warnings", [])) - set(before.get("state_warnings", [])):
        reasons.append("state_warnings_worsened")
    if after.get("top_not_above_bottom") is True:
        reasons.append("top_not_above_bottom")
    if after.get("self_intersection") is True:
        reasons.append("self_intersection")
    short_wall = _as_float(after.get("short_wall_length"))
    if short_wall is not None and short_wall < MIN_WALL_LENGTH:
        reasons.append("severe_short_wall")
    return sorted(set(reasons))


def build_floorprint_sensitivity_rows(
    ordered_pairs: Sequence[Mapping[str, Any]],
    metadata: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Enumerate fixed bottom-y perturbations without changing x, top-y, or order."""
    before_state = build_room_layout_state(ordered_pairs, metadata=metadata)
    rows: list[dict[str, Any]] = []
    for pair_index, pair in enumerate(ordered_pairs, start=1):
        before_snapshot = _snapshot(before_state, [pair_index])
        for dy in BOTTOM_Y_PERTURBATIONS:
            candidate = _copy_pairs(ordered_pairs)
            candidate[pair_index - 1]["bottom"]["y"] += dy
            after_state = build_room_layout_state(candidate, metadata=metadata)
            after_snapshot = _snapshot(after_state, [pair_index])
            after_snapshot["top_not_above_bottom"] = _top_not_above_bottom(after_state)
            risks = _risk_reasons(
                before_snapshot,
                after_snapshot,
                movement_x=0.0,
                movement_y=dy,
            )
            wall_sum_delta = _delta(
                before_snapshot["wall_angle_summary"]["residual_sum_deg"],
                after_snapshot["wall_angle_summary"]["residual_sum_deg"],
            )
            corner_sum_delta = _delta(
                before_snapshot["corner_angle_summary"]["residual_sum_deg"],
                after_snapshot["corner_angle_summary"]["residual_sum_deg"],
            )
            height_delta = _delta(
                before_snapshot["height_residual_summary"]["residual_sum"],
                after_snapshot["height_residual_summary"]["residual_sum"],
            )
            combined_delta = sum(
                value for value in (wall_sum_delta, corner_sum_delta, height_delta) if value is not None
            )
            if risks:
                decision = "suppress"
                decision_reasons = list(risks)
            elif combined_delta <= SCORE_IMPROVEMENT_THRESHOLD:
                decision = "improves"
                decision_reasons = ["local_diagnostic_residuals_decrease"]
            elif combined_delta > abs(SCORE_IMPROVEMENT_THRESHOLD):
                decision = "worsens"
                decision_reasons = ["local_diagnostic_residuals_increase"]
            else:
                decision = "neutral"
                decision_reasons = ["no_clear_local_diagnostic_change"]
            rows.append(
                {
                    "schema_version": FLOORPRINT_SENSITIVITY_VERSION,
                    "target_pair_index": pair_index,
                    "bottom_y_before": float(pair["bottom"]["y"]),
                    "bottom_y_after": float(pair["bottom"]["y"]) + dy,
                    "bottom_y_delta": dy,
                    "top_x_before": float(pair["top"]["x"]),
                    "top_x_after": float(candidate[pair_index - 1]["top"]["x"]),
                    "top_y_before": float(pair["top"]["y"]),
                    "top_y_after": float(candidate[pair_index - 1]["top"]["y"]),
                    "bottom_x_before": float(pair["bottom"]["x"]),
                    "bottom_x_after": float(candidate[pair_index - 1]["bottom"]["x"]),
                    "pair_order_before": list(range(1, len(ordered_pairs) + 1)),
                    "pair_order_after": list(range(1, len(ordered_pairs) + 1)),
                    "affected_wall_indices": before_snapshot["affected_wall_indices"],
                    "affected_corner_indices": before_snapshot["affected_corner_indices"],
                    "wall_angle_residual_sum_before": before_snapshot["wall_angle_summary"]["residual_sum_deg"],
                    "wall_angle_residual_sum_after": after_snapshot["wall_angle_summary"]["residual_sum_deg"],
                    "wall_angle_residual_sum_delta": wall_sum_delta,
                    "wall_angle_residual_max_before": before_snapshot["wall_angle_summary"]["residual_max_deg"],
                    "wall_angle_residual_max_after": after_snapshot["wall_angle_summary"]["residual_max_deg"],
                    "wall_angle_residual_max_delta": _delta(
                        before_snapshot["wall_angle_summary"]["residual_max_deg"],
                        after_snapshot["wall_angle_summary"]["residual_max_deg"],
                    ),
                    "corner_angle_residual_sum_before": before_snapshot["corner_angle_summary"]["residual_sum_deg"],
                    "corner_angle_residual_sum_after": after_snapshot["corner_angle_summary"]["residual_sum_deg"],
                    "corner_angle_residual_sum_delta": corner_sum_delta,
                    "height_residual_before": before_snapshot["height_residual_summary"]["residual_sum"],
                    "height_residual_after": after_snapshot["height_residual_summary"]["residual_sum"],
                    "height_residual_delta": height_delta,
                    "self_intersection_before": before_snapshot["self_intersection"],
                    "self_intersection_after": after_snapshot["self_intersection"],
                    "state_status_after": after_snapshot["state_status"],
                    "state_warnings_after": after_snapshot["state_warnings"],
                    "x_order_crossing_after_translation": _x_order_crossing(
                        ordered_pairs, candidate, [pair_index]
                    ),
                    "decision_label": decision,
                    "decision_reasons": decision_reasons,
                    "risk_reasons": risks,
                    "writeback_allowed": False,
                    "expert_action_allowed": False,
                    "annotation_patch_allowed": False,
                }
            )
    return rows


def _local_window(n_pairs: int, dense_pair_indices: Sequence[int]) -> list[int]:
    start = max(1, min(dense_pair_indices) - 2)
    stop = min(n_pairs, max(dense_pair_indices) + 2)
    return list(range(start, stop + 1))


def _apply_bottom_offsets(
    ordered_pairs: Sequence[Mapping[str, Any]],
    offsets: Mapping[int, tuple[float, float]],
) -> list[dict[str, dict[str, float]]]:
    candidate = _copy_pairs(ordered_pairs)
    for pair_index, (dx, dy) in offsets.items():
        candidate[pair_index - 1]["bottom"]["x"] += dx
        candidate[pair_index - 1]["bottom"]["y"] += dy
    return candidate


def _flip_dense_pair(
    ordered_pairs: Sequence[Mapping[str, Any]], dense_pair_indices: Sequence[int]
) -> tuple[list[dict[str, dict[str, float]]], list[int]]:
    candidate = _copy_pairs(ordered_pairs)
    order = list(range(1, len(candidate) + 1))
    left, right = dense_pair_indices
    candidate[left - 1], candidate[right - 1] = candidate[right - 1], candidate[left - 1]
    order[left - 1], order[right - 1] = order[right - 1], order[left - 1]
    return candidate, order


def _evaluate_dense_candidate(
    ordered_pairs: Sequence[Mapping[str, Any]],
    candidate_pairs: Sequence[Mapping[str, Any]],
    metadata: Mapping[str, Any] | None,
    local_window: Sequence[int],
    before_snapshot: Mapping[str, Any],
    *,
    movement_x: float,
    movement_y: float,
) -> tuple[dict[str, Any], list[str], float | None]:
    after_state = build_room_layout_state(candidate_pairs, metadata=metadata)
    after = _snapshot(after_state, local_window)
    after["top_not_above_bottom"] = _top_not_above_bottom(after_state)
    risks = _risk_reasons(
        before_snapshot,
        after,
        movement_x=movement_x,
        movement_y=movement_y,
    )
    return after, risks, _delta(
        before_snapshot.get("local_geometry_score"), after.get("local_geometry_score")
    )


def _best_micro_candidate(
    ordered_pairs: Sequence[Mapping[str, Any]],
    metadata: Mapping[str, Any] | None,
    dense_pair_indices: Sequence[int],
    local_window: Sequence[int],
    before_snapshot: Mapping[str, Any],
) -> tuple[
    list[dict[str, dict[str, float]]],
    dict[int, tuple[float, float]],
    dict[str, Any],
    list[str],
    float | None,
]:
    evaluated: list[
        tuple[
            tuple[int, float, float],
            list[dict[str, dict[str, float]]],
            dict[int, tuple[float, float]],
            dict[str, Any],
            list[str],
            float | None,
        ]
    ] = []
    for pair_index in dense_pair_indices:
        for dx in BOTTOM_X_MICRO_GRID:
            for dy in BOTTOM_Y_MICRO_GRID:
                offsets = {pair_index: (dx, dy)}
                candidate = _apply_bottom_offsets(ordered_pairs, offsets)
                after, risks, score_delta = _evaluate_dense_candidate(
                    ordered_pairs,
                    candidate,
                    metadata,
                    local_window,
                    before_snapshot,
                    movement_x=dx,
                    movement_y=dy,
                )
                evaluated.append(
                    (
                        (len(risks), float("inf") if score_delta is None else score_delta, abs(dx) + abs(dy)),
                        candidate,
                        offsets,
                        after,
                        risks,
                        score_delta,
                    )
                )
    _, candidate, offsets, after, risks, score_delta = min(
        evaluated, key=lambda item: item[0]
    )
    return candidate, offsets, after, risks, score_delta


def _probe_row(
    *,
    hypothesis_id: str,
    topology_variant: str,
    local_window: Sequence[int],
    dense_pair_indices: Sequence[int],
    target_pair_indices: Sequence[int],
    bottom_xy_offsets: Mapping[int, tuple[float, float]],
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    score_delta: float | None,
    risks: Sequence[str],
    x_order_crossing: bool,
    evaluation_pair_order: Sequence[int],
) -> dict[str, Any]:
    topology_review_only = topology_variant != "keep_local_order"
    if risks:
        confidence = "suppressed"
        decision_reasons = list(risks)
    elif topology_review_only:
        confidence = "neutral_review"
        decision_reasons = [
            "topology_variant_manual_review_only",
            "local_geometry_score_is_plausibility_not_correctness",
            "automatic_topology_change_forbidden",
        ]
        if score_delta is not None and score_delta <= SCORE_IMPROVEMENT_THRESHOLD:
            decision_reasons.insert(
                0,
                "score_improved_but_topology_variant_remains_neutral_review",
            )
        else:
            decision_reasons.insert(0, "no_actionable_topology_improvement")
    elif score_delta is not None and score_delta <= SCORE_IMPROVEMENT_THRESHOLD:
        confidence = "directional"
        decision_reasons = ["local_geometry_score_improved_directionally"]
    else:
        confidence = "no_improvement"
        decision_reasons = ["no_clear_local_geometry_improvement"]
    short_wall_length = _as_float(after.get("short_wall_length"))
    return {
        "schema_version": LOCAL_DENSE_CORNER_PROBE_VERSION,
        "hypothesis_id": hypothesis_id,
        "topology_variant": topology_variant,
        "local_window_pair_indices": list(local_window),
        "dense_pair_indices": list(dense_pair_indices),
        "target_pair_indices": list(target_pair_indices),
        "bottom_xy_offsets": {
            str(pair_index): {"bottom_x_delta": dx, "bottom_y_delta": dy}
            for pair_index, (dx, dy) in bottom_xy_offsets.items()
        },
        "top_y_policy": "unchanged",
        "y_change_allowed": False,
        "evaluation_pair_order": list(evaluation_pair_order),
        "before_wall_angle_summary": before["wall_angle_summary"],
        "after_wall_angle_summary": after["wall_angle_summary"],
        "wall_angle_residual_sum_delta": _delta(
            before["wall_angle_summary"]["residual_sum_deg"],
            after["wall_angle_summary"]["residual_sum_deg"],
        ),
        "before_corner_angle_summary": before["corner_angle_summary"],
        "after_corner_angle_summary": after["corner_angle_summary"],
        "corner_angle_residual_sum_delta": _delta(
            before["corner_angle_summary"]["residual_sum_deg"],
            after["corner_angle_summary"]["residual_sum_deg"],
        ),
        "before_height_residual_summary": before["height_residual_summary"],
        "after_height_residual_summary": after["height_residual_summary"],
        "height_residual_sum_delta": _delta(
            before["height_residual_summary"]["residual_sum"],
            after["height_residual_summary"]["residual_sum"],
        ),
        "short_wall_flag": (
            short_wall_length is not None and short_wall_length < SHORT_WALL_REVIEW_LENGTH
        ),
        "short_wall_length": short_wall_length,
        "self_intersection_after": after.get("self_intersection"),
        "state_status_after": after.get("state_status"),
        "state_warnings_after": after.get("state_warnings", []),
        "x_order_crossing_after_translation": x_order_crossing,
        "local_geometry_score_before": before.get("local_geometry_score"),
        "local_geometry_score_after": after.get("local_geometry_score"),
        "local_geometry_score_delta": score_delta,
        "confidence_label": confidence,
        "decision_reasons": decision_reasons,
        "risk_reasons": list(risks),
        "writeback_allowed": False,
        "expert_action_allowed": False,
        "annotation_patch_allowed": False,
    }


def build_local_dense_corner_probe_rows(
    ordered_pairs: Sequence[Mapping[str, Any]],
    dense_reclassification: Sequence[Mapping[str, Any]],
    metadata: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Evaluate five local dry-run hypotheses for unresolved dense corners only."""
    before_state = build_room_layout_state(ordered_pairs, metadata=metadata)
    rows: list[dict[str, Any]] = []
    base_order = list(range(1, len(ordered_pairs) + 1))
    for dense in dense_reclassification:
        if dense.get("classification") != "unresolved_dense_corner":
            continue
        dense_pair_indices = [
            int(dense["left_pair_index"]),
            int(dense["right_pair_index"]),
        ]
        window = _local_window(len(ordered_pairs), dense_pair_indices)
        before = _snapshot(before_state, window)

        baseline = _copy_pairs(ordered_pairs)
        baseline_after, baseline_risks, baseline_delta = _evaluate_dense_candidate(
            ordered_pairs,
            baseline,
            metadata,
            window,
            before,
            movement_x=0.0,
            movement_y=0.0,
        )
        rows.append(
            _probe_row(
                hypothesis_id="keep_local_order",
                topology_variant="keep_local_order",
                local_window=window,
                dense_pair_indices=dense_pair_indices,
                target_pair_indices=dense_pair_indices,
                bottom_xy_offsets={},
                before=before,
                after=baseline_after,
                score_delta=baseline_delta,
                risks=baseline_risks,
                x_order_crossing=False,
                evaluation_pair_order=base_order,
            )
        )

        flipped, flipped_order = _flip_dense_pair(ordered_pairs, dense_pair_indices)
        flipped_after, flipped_risks, flipped_delta = _evaluate_dense_candidate(
            ordered_pairs,
            flipped,
            metadata,
            window,
            before,
            movement_x=0.0,
            movement_y=0.0,
        )
        rows.append(
            _probe_row(
                hypothesis_id="local_dense_pair_order_flip",
                topology_variant="local_dense_pair_order_flip",
                local_window=window,
                dense_pair_indices=dense_pair_indices,
                target_pair_indices=dense_pair_indices,
                bottom_xy_offsets={},
                before=before,
                after=flipped_after,
                score_delta=flipped_delta,
                risks=flipped_risks,
                x_order_crossing=False,
                evaluation_pair_order=flipped_order,
            )
        )

        rows.append(
            _probe_row(
                hypothesis_id="allow_short_wall_between_dense_pair",
                topology_variant="allow_short_wall_between_dense_pair",
                local_window=window,
                dense_pair_indices=dense_pair_indices,
                target_pair_indices=dense_pair_indices,
                bottom_xy_offsets={},
                before=before,
                after=baseline_after,
                score_delta=baseline_delta,
                risks=baseline_risks,
                x_order_crossing=False,
                evaluation_pair_order=base_order,
            )
        )

        micro, offsets, micro_after, micro_risks, micro_delta = _best_micro_candidate(
            ordered_pairs,
            metadata,
            dense_pair_indices,
            window,
            before,
        )
        micro_crossing = _x_order_crossing(ordered_pairs, micro, list(offsets))
        rows.append(
            _probe_row(
                hypothesis_id="keep_order_with_bottom_xy_micro_probe",
                topology_variant="keep_local_order",
                local_window=window,
                dense_pair_indices=dense_pair_indices,
                target_pair_indices=list(offsets),
                bottom_xy_offsets=offsets,
                before=before,
                after=micro_after,
                score_delta=micro_delta,
                risks=micro_risks,
                x_order_crossing=micro_crossing,
                evaluation_pair_order=base_order,
            )
        )
        rows.append(
            _probe_row(
                hypothesis_id="short_wall_with_bottom_xy_micro_probe",
                topology_variant="allow_short_wall_between_dense_pair",
                local_window=window,
                dense_pair_indices=dense_pair_indices,
                target_pair_indices=list(offsets),
                bottom_xy_offsets=offsets,
                before=before,
                after=micro_after,
                score_delta=micro_delta,
                risks=micro_risks,
                x_order_crossing=micro_crossing,
                evaluation_pair_order=base_order,
            )
        )
    return rows


__all__ = [
    "BOTTOM_Y_PERTURBATIONS",
    "FLOORPRINT_SENSITIVITY_VERSION",
    "LOCAL_DENSE_CORNER_PROBE_VERSION",
    "build_floorprint_sensitivity_rows",
    "build_local_dense_corner_probe_rows",
]
