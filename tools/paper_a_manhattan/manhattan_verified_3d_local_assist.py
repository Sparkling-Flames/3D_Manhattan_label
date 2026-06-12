"""Verified 3D local assist harness for Paper A Manhattan tools.

This module is experiment-outside, expert-side, and dry-run only. It never
applies edits, writes annotations, changes pair order, emits UI state, or feeds
formal g_t, routing, worker-quality, or P1/C1/C2/T1/V1 artifacts.
"""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from tools.paper_a_manhattan.manhattan_layout_state import build_room_layout_state


VERIFIED_3D_LOCAL_ASSIST_VERSION = "verified_3d_local_assist_m15_14_v1"
OPERATION_FAMILY = "verified_3d_local_assist"
TRANSLATE_PAIR_CLUSTER_X_DRYRUN = "translate_pair_cluster_x_dryrun"

CENTER_X_DUPLICATE_THRESHOLD_PERCENT = 1.0
BEV_DISTINCT_DISTANCE_THRESHOLD = 0.3
FLOOR_DISTANCE_DISTINCT_THRESHOLD = 0.3
TRUE_DUPLICATE_BEV_DISTANCE_THRESHOLD = 0.1
TRUE_DUPLICATE_FLOOR_DISTANCE_THRESHOLD = 0.1
MIN_ADJACENT_WALL_LENGTH_FOR_DISTINCT = 0.2
MAX_LOCAL_X_TRANSLATION_ABS_PERCENT = 0.5
DEFAULT_DX_GRID = (-0.5, -0.25, 0.25, 0.5)


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


def _translate_pairs_x(
    ordered_pairs: Sequence[Mapping[str, Any]],
    target_pair_indices: Sequence[int],
    dx: float,
) -> list[dict[str, Any]]:
    target_set = set(target_pair_indices)
    candidate: list[dict[str, Any]] = []
    for index, pair in enumerate(ordered_pairs, start=1):
        top = dict(pair["top"])
        bottom = dict(pair["bottom"])
        if index in target_set:
            top["x"] = float(top["x"]) + dx
            bottom["x"] = float(bottom["x"]) + dx
        candidate.append({"top": top, "bottom": bottom})
    return candidate


def _candidate_risk_reasons(
    before_metrics: Mapping[str, Any],
    after_metrics: Mapping[str, Any],
    state: Mapping[str, Any],
    dx: float,
) -> list[str]:
    reasons: list[str] = []
    if abs(dx) > MAX_LOCAL_X_TRANSLATION_ABS_PERCENT:
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


def _candidate_status(risk_reasons: Sequence[str], improved: Mapping[str, Any]) -> str:
    if any(reason.endswith("worsened") for reason in risk_reasons) or any(
        reason in risk_reasons
        for reason in (
            "x_translation_too_large",
            "wrap_seam_unresolved_after_translation",
            "top_not_above_bottom_after_translation",
        )
    ):
        return "suppress"
    residual_delta = _as_float(improved.get("target_height_residual_sum_delta"))
    spread_delta = _as_float(improved.get("layout_height_spread_delta"))
    if residual_delta is not None and residual_delta < 0:
        return "eligible"
    if spread_delta is not None and spread_delta < 0:
        return "eligible"
    return "review_only"


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


def _build_translation_candidates(
    ordered_pairs: Sequence[Mapping[str, Any]],
    metadata: Mapping[str, Any] | None,
    topology_override: Mapping[str, Any] | None,
    dense_reclassification: Sequence[Mapping[str, Any]],
    target_pair_indices: Sequence[Any] | None,
    before_state: Mapping[str, Any],
) -> list[dict[str, Any]]:
    if not _topology_override_active(topology_override):
        return []
    clusters = _target_clusters(dense_reclassification, target_pair_indices)
    candidates: list[dict[str, Any]] = []
    for cluster in clusters:
        before_metrics = _metric_summary(before_state, cluster)
        for dx in DEFAULT_DX_GRID:
            candidate_pairs = _translate_pairs_x(ordered_pairs, cluster, dx)
            after_state = build_room_layout_state(candidate_pairs, metadata=metadata)
            after_metrics = _metric_summary(after_state, cluster)
            improved = _improved_metrics(before_metrics, after_metrics)
            risks = _candidate_risk_reasons(before_metrics, after_metrics, after_state, dx)
            status = _candidate_status(risks, improved)
            candidates.append(
                {
                    "candidate_id": (
                        f"{TRANSLATE_PAIR_CLUSTER_X_DRYRUN}_"
                        f"{'-'.join(str(index) for index in cluster)}_{dx:+.2f}"
                    ),
                    "operation": TRANSLATE_PAIR_CLUSTER_X_DRYRUN,
                    "target_pair_indices": list(cluster),
                    "dx": dx,
                    "status": status,
                    "before_metrics": before_metrics,
                    "after_metrics": after_metrics,
                    "improved_metrics": improved,
                    "risk_reasons": risks,
                    "y_change_allowed": False,
                    "writeback_allowed": False,
                }
            )
    return candidates


def build_verified_3d_local_assist(
    ordered_pairs: Sequence[Mapping[str, Any]],
    metadata: Mapping[str, Any] | None = None,
    topology_override: Mapping[str, Any] | None = None,
    target_pair_indices: Sequence[Any] | None = None,
) -> dict[str, Any]:
    """Build verified 3D local assist diagnostics and dry-run candidates."""
    state = build_room_layout_state(ordered_pairs, metadata=metadata)
    local_diagnostics = _build_local_3d_diagnostics(state)
    dense_reclassification = _reclassify_dense_corners(local_diagnostics, state)
    candidates = _build_translation_candidates(
        ordered_pairs,
        metadata,
        topology_override,
        dense_reclassification,
        target_pair_indices,
        state,
    )
    return {
        "schema_version": VERIFIED_3D_LOCAL_ASSIST_VERSION,
        "operation_family": OPERATION_FAMILY,
        "state_status": state.get("state_status"),
        "state_warnings": list(state.get("state_warnings", [])),
        "before_metrics": _metric_summary(state, []),
        "local_3d_diagnostics": local_diagnostics,
        "dense_corner_reclassification": dense_reclassification,
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
    "TRANSLATE_PAIR_CLUSTER_X_DRYRUN",
    "VERIFIED_3D_LOCAL_ASSIST_VERSION",
    "build_verified_3d_local_assist",
]
