"""Conservative height/y reproject dry-run candidates for Paper A Manhattan.

This module is expert-side and review-only. It computes sidecar diagnostics for
fixed-bottom top-y reprojection and never emits annotation patches, writeback
payloads, UI state, routing signals, formal g_t, worker-quality metrics, or
P1/C1/C2/T1/V1 artifacts.
"""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from tools.paper_a_manhattan.manhattan_layout_state import build_room_layout_state


HEIGHT_REPROJECT_CANDIDATE_VERSION = "manhattan_height_reproject_candidate_m15_16_v1"
FIXED_BOTTOM_TOP_Y_REPROJECT = "fixed_bottom_top_y_reproject"

MAX_TOP_Y_DELTA_PERCENT = 8.0
MIN_HEIGHT_RESIDUAL_IMPROVEMENT = 0.05
MAX_LAYOUT_HEIGHT_SPREAD_WORSENING = 0.10


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _target_indices(
    state: Mapping[str, Any],
    target_pair_indices: Sequence[Any] | None,
) -> list[int]:
    if target_pair_indices is not None:
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
        return sorted(output)

    diagnostics = [
        row
        for row in state.get("pair_diagnostics", [])
        if isinstance(row.get("pair_index"), int)
    ]
    return [
        int(row["pair_index"])
        for row in sorted(
            diagnostics,
            key=lambda item: _as_float(item.get("height_residual")) or 0.0,
            reverse=True,
        )
    ]


def _corner_lookup(state: Mapping[str, Any]) -> dict[int, Mapping[str, Any]]:
    return {
        int(row["pair_index"]): row
        for row in state.get("corners", [])
        if isinstance(row.get("pair_index"), int)
    }


def _diagnostic_lookup(state: Mapping[str, Any]) -> dict[int, Mapping[str, Any]]:
    return {
        int(row["pair_index"]): row
        for row in state.get("pair_diagnostics", [])
        if isinstance(row.get("pair_index"), int)
    }


def _v_to_ls_y(v_rad: float) -> float:
    return (0.5 - v_rad / math.pi) * 100.0


def _top_y_for_layout_height(
    *,
    layout_height: float,
    camera_height: float,
    floor_distance: float,
) -> float | None:
    if floor_distance <= 0:
        return None
    v_rad = math.atan((layout_height - camera_height) / floor_distance)
    y = _v_to_ls_y(v_rad)
    return y if math.isfinite(y) else None


def _candidate_pairs_with_top_y(
    ordered_pairs: Sequence[Mapping[str, Any]],
    target_pair_index: int,
    top_y_after: float,
) -> list[dict[str, Any]]:
    candidate: list[dict[str, Any]] = []
    for index, pair in enumerate(ordered_pairs, start=1):
        top = dict(pair["top"])
        bottom = dict(pair["bottom"])
        if index == target_pair_index:
            top["y"] = top_y_after
        candidate.append({"top": top, "bottom": bottom})
    return candidate


def _finish_suppressed(
    *,
    target_pair_index: Any,
    gate_reasons: Sequence[str],
    state: Mapping[str, Any],
) -> dict[str, Any]:
    reasons = sorted(set(gate_reasons))
    return {
        "candidate_schema_version": HEIGHT_REPROJECT_CANDIDATE_VERSION,
        "operation": FIXED_BOTTOM_TOP_Y_REPROJECT,
        "target_pair_index": target_pair_index,
        "candidate_decision": "suppress",
        "decision_reasons": reasons,
        "top_x_before": None,
        "top_x_after": None,
        "bottom_x_before": None,
        "bottom_x_after": None,
        "top_y_before": None,
        "top_y_after": None,
        "bottom_y_before": None,
        "bottom_y_after": None,
        "top_y_delta": None,
        "bottom_y_delta": 0.0,
        "height_residual_before": None,
        "height_residual_after": None,
        "height_residual_delta": None,
        "layout_height_candidate": state.get("layout_height_candidate"),
        "layout_height_spread_before": state.get("layout_height_spread"),
        "layout_height_spread_after": None,
        "max_abs_y_delta": None,
        "gate_status": "suppress",
        "gate_reasons": reasons,
        "y_change_allowed": False,
        "writeback_allowed": False,
        "expert_action_allowed": False,
        "annotation_patch_allowed": False,
    }


def _build_row_for_target(
    ordered_pairs: Sequence[Mapping[str, Any]],
    metadata: Mapping[str, Any] | None,
    state: Mapping[str, Any],
    target_pair_index: int,
) -> dict[str, Any]:
    if state.get("state_status") != "ok":
        return _finish_suppressed(
            target_pair_index=target_pair_index,
            gate_reasons=["state_status_not_ok"],
            state=state,
        )

    corners = _corner_lookup(state)
    diagnostics = _diagnostic_lookup(state)
    corner = corners.get(target_pair_index)
    diagnostic = diagnostics.get(target_pair_index)
    if corner is None or diagnostic is None or target_pair_index > len(ordered_pairs):
        return _finish_suppressed(
            target_pair_index=target_pair_index,
            gate_reasons=["target_pair_missing"],
            state=state,
        )

    layout_height = _as_float(state.get("layout_height_candidate"))
    camera_height = _as_float(state.get("camera_height"))
    floor_distance = _as_float(corner.get("floor_distance"))
    if layout_height is None or camera_height is None or floor_distance is None:
        return _finish_suppressed(
            target_pair_index=target_pair_index,
            gate_reasons=["computed_y_non_finite"],
            state=state,
        )

    pair = ordered_pairs[target_pair_index - 1]
    top = pair["top"]
    bottom = pair["bottom"]
    top_y_before = float(top["y"])
    bottom_y_before = float(bottom["y"])
    top_y_after = _top_y_for_layout_height(
        layout_height=layout_height,
        camera_height=camera_height,
        floor_distance=floor_distance,
    )
    gate_reasons: list[str] = []
    if top_y_after is None:
        gate_reasons.append("computed_y_non_finite")
        top_y_after = top_y_before

    top_y_delta = top_y_after - top_y_before
    if top_y_after >= bottom_y_before:
        gate_reasons.append("top_y_after_not_above_bottom_y")
    if abs(top_y_delta) > MAX_TOP_Y_DELTA_PERCENT:
        gate_reasons.append("top_y_delta_exceeds_threshold")

    candidate_pairs = _candidate_pairs_with_top_y(
        ordered_pairs,
        target_pair_index,
        top_y_after,
    )
    after_state = build_room_layout_state(candidate_pairs, metadata=metadata)
    after_diagnostic = _diagnostic_lookup(after_state).get(target_pair_index)
    residual_before = _as_float(diagnostic.get("height_residual"))
    residual_after = (
        _as_float(after_diagnostic.get("height_residual")) if after_diagnostic else None
    )
    spread_before = _as_float(state.get("layout_height_spread"))
    spread_after = _as_float(after_state.get("layout_height_spread"))
    if spread_before is not None and spread_after is not None:
        if spread_after - spread_before > MAX_LAYOUT_HEIGHT_SPREAD_WORSENING:
            gate_reasons.append("layout_height_spread_worsened_severely")

    if gate_reasons:
        decision = "suppress"
        decision_reasons = sorted(set(gate_reasons))
    else:
        improvement = (
            residual_before - residual_after
            if residual_before is not None and residual_after is not None
            else None
        )
        if improvement is not None and improvement >= MIN_HEIGHT_RESIDUAL_IMPROVEMENT:
            decision = "suggested_review"
            decision_reasons = ["height_residual_reduced_substantially"]
        else:
            decision = "neutral_review"
            decision_reasons = ["height_residual_improvement_small_or_uncertain"]

    return {
        "candidate_schema_version": HEIGHT_REPROJECT_CANDIDATE_VERSION,
        "operation": FIXED_BOTTOM_TOP_Y_REPROJECT,
        "target_pair_index": target_pair_index,
        "candidate_decision": decision,
        "decision_reasons": decision_reasons,
        "top_x_before": top.get("x"),
        "top_x_after": top.get("x"),
        "bottom_x_before": bottom.get("x"),
        "bottom_x_after": bottom.get("x"),
        "top_y_before": top_y_before,
        "top_y_after": top_y_after,
        "bottom_y_before": bottom_y_before,
        "bottom_y_after": bottom_y_before,
        "top_y_delta": top_y_delta,
        "bottom_y_delta": 0.0,
        "height_residual_before": residual_before,
        "height_residual_after": residual_after,
        "height_residual_delta": (
            residual_after - residual_before
            if residual_before is not None and residual_after is not None
            else None
        ),
        "layout_height_candidate": layout_height,
        "layout_height_spread_before": spread_before,
        "layout_height_spread_after": spread_after,
        "max_abs_y_delta": abs(top_y_delta),
        "gate_status": "suppress" if gate_reasons else "pass",
        "gate_reasons": sorted(set(gate_reasons)),
        "y_change_allowed": False,
        "writeback_allowed": False,
        "expert_action_allowed": False,
        "annotation_patch_allowed": False,
    }


def build_height_reproject_candidate_rows(
    ordered_pairs: Sequence[Mapping[str, Any]],
    metadata: Mapping[str, Any] | None = None,
    target_pair_indices: Sequence[Any] | None = None,
) -> list[dict[str, Any]]:
    """Build fixed-bottom top-y review candidates without returning edit payloads."""
    state = build_room_layout_state(ordered_pairs, metadata=metadata)
    rows = [
        _build_row_for_target(ordered_pairs, metadata, state, pair_index)
        for pair_index in _target_indices(state, target_pair_indices)
    ]

    def sort_key(row: Mapping[str, Any]) -> tuple[int, float, int]:
        decision_rank = {
            "suggested_review": 0,
            "neutral_review": 1,
            "suppress": 2,
        }.get(str(row.get("candidate_decision")), 3)
        residual = _as_float(row.get("height_residual_before")) or -1.0
        pair_index = row.get("target_pair_index")
        return (decision_rank, -residual, int(pair_index) if isinstance(pair_index, int) else 999)

    ranked = [dict(row) for row in sorted(rows, key=sort_key)]
    for rank, row in enumerate(ranked, start=1):
        row["candidate_rank"] = rank
    return ranked


__all__ = [
    "FIXED_BOTTOM_TOP_Y_REPROJECT",
    "HEIGHT_REPROJECT_CANDIDATE_VERSION",
    "MAX_TOP_Y_DELTA_PERCENT",
    "MIN_HEIGHT_RESIDUAL_IMPROVEMENT",
    "build_height_reproject_candidate_rows",
]
