"""M15.8 height reproject applicability gate for Paper A Manhattan tools.

This module implements the diagnostic-only safety gate defined by
MANHATTAN_HEIGHT_REPROJECT_SAFETY_CONTRACT_v1.md. It does not implement height
reprojection, does not generate y-coordinate candidates, does not modify
candidate pairs or annotations, and does not connect to UI, Label Studio,
routing, formal g_t, worker quality metrics, or P1/C1/C2/T1/V1 artifacts.
"""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from tools.paper_a_manhattan.manhattan_layout_state import build_room_layout_state


GATE_VERSION = "manhattan_height_reproject_gate_m15_8_v1"

ELIGIBLE = "eligible"
REVIEW_ONLY = "review_only"
SUPPRESS = "suppress"

METADATA_SUPPRESS_TOKENS = {
    "oos_open_boundary",
    "oos_split_level",
    "oos_geometry",
    "oos_insufficient",
    "open_boundary",
    "split_level",
    "non_manhattan",
}
STATE_REVIEW_WARNINGS = {
    "layout_height_spread_high",
    "floor_not_below_horizon_distance_fallback",
}
STATE_SUPPRESS_WARNINGS = {
    "wrap_seam_unresolved",
}
TARGET_REVIEW_WARNINGS = {
    "height_residual_high",
}
TARGET_SUPPRESS_WARNINGS = {
    "top_not_above_bottom",
}
MIN_NON_TARGET_ANCHORS = 3


def _is_false_like(value: Any) -> bool:
    if value is False:
        return True
    if isinstance(value, str):
        return value.strip().lower() in {"false", "0", "no"}
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value == 0
    return False


def _metadata_suppress_reason(metadata: Mapping[str, Any] | None) -> str | None:
    if not metadata:
        return None
    for key in ("scope", "layout_type"):
        value = metadata.get(key)
        if value is not None:
            token = str(value).strip().lower()
            if token in METADATA_SUPPRESS_TOKENS:
                return f"metadata_{token}"
    for token in METADATA_SUPPRESS_TOKENS:
        if metadata.get(token):
            return f"metadata_{token}"
    if _is_false_like(metadata.get("manhattan_assumable")):
        return "metadata_not_manhattan_assumable"
    return None


def _as_pair_index(pair_index: Any) -> int | None:
    if isinstance(pair_index, bool):
        return None
    try:
        value = int(pair_index)
    except (TypeError, ValueError):
        return None
    return value if value >= 1 else None


def _find_target_diagnostic(state: Mapping[str, Any], pair_index: int) -> Mapping[str, Any] | None:
    for diagnostic in state.get("pair_diagnostics", []):
        if diagnostic.get("pair_index") == pair_index:
            return diagnostic
    return None


def _non_target_anchor_count(state: Mapping[str, Any], pair_index: int) -> int:
    count = 0
    for diagnostic in state.get("pair_diagnostics", []):
        if diagnostic.get("pair_index") == pair_index:
            continue
        if diagnostic.get("is_anchor_candidate") is True:
            count += 1
    return count


def _finish(
    *,
    state: Mapping[str, Any],
    target_pair_index: Any,
    target_diagnostic: Mapping[str, Any] | None,
    status: str,
    reasons: list[str],
) -> dict[str, Any]:
    return {
        "state_status": state.get("state_status"),
        "target_pair_index": target_pair_index,
        "height_reproject_status": status,
        "height_reproject_applicable": status == ELIGIBLE,
        "height_reproject_blocking_reasons": sorted(set(reasons)),
        "estimated_layout_height": state.get("layout_height_candidate"),
        "layout_height_spread": state.get("layout_height_spread"),
        "target_height_residual_before": (
            target_diagnostic.get("height_residual") if target_diagnostic else None
        ),
        "max_y_delta": None,
        "y_delta_gate_status": "not_evaluated_no_candidate",
        "gate_version": GATE_VERSION,
    }


def diagnose_height_reproject_applicability(
    ordered_pairs: Sequence[Mapping[str, Any]],
    pair_index: int,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Diagnose whether future height reproject may be considered.

    This is an applicability gate only. It computes no y candidate and has no
    annotation writeback role.
    """
    target_pair_index = _as_pair_index(pair_index)
    if target_pair_index is None:
        return _finish(
            state={"state_status": "failed"},
            target_pair_index=pair_index,
            target_diagnostic=None,
            status=SUPPRESS,
            reasons=["invalid_pair_index"],
        )

    metadata_reason = _metadata_suppress_reason(metadata)
    state = build_room_layout_state(ordered_pairs, metadata=metadata)
    state_status = state.get("state_status")
    if state_status in {"failed", "excluded"}:
        reasons = [f"state_{state_status}"] + list(state.get("state_warnings", []))
        if metadata_reason:
            reasons.append(metadata_reason)
        return _finish(
            state=state,
            target_pair_index=target_pair_index,
            target_diagnostic=None,
            status=SUPPRESS,
            reasons=reasons,
        )

    suppress_reasons: list[str] = []
    review_reasons: list[str] = []
    if metadata_reason:
        suppress_reasons.append(metadata_reason)

    state_warnings = set(state.get("state_warnings", []))
    suppress_reasons.extend(
        f"state_warning_{warning}" for warning in sorted(state_warnings & STATE_SUPPRESS_WARNINGS)
    )
    review_reasons.extend(
        f"state_warning_{warning}" for warning in sorted(state_warnings & STATE_REVIEW_WARNINGS)
    )

    target_diagnostic = _find_target_diagnostic(state, target_pair_index)
    if target_diagnostic is None:
        suppress_reasons.append("target_pair_missing")
        return _finish(
            state=state,
            target_pair_index=target_pair_index,
            target_diagnostic=None,
            status=SUPPRESS,
            reasons=suppress_reasons,
        )

    target_warnings = set(target_diagnostic.get("warnings", []))
    suppress_reasons.extend(
        f"target_warning_{warning}" for warning in sorted(target_warnings & TARGET_SUPPRESS_WARNINGS)
    )
    review_reasons.extend(
        f"target_warning_{warning}" for warning in sorted(target_warnings & TARGET_REVIEW_WARNINGS)
    )

    non_target_anchors = _non_target_anchor_count(state, target_pair_index)
    if non_target_anchors < MIN_NON_TARGET_ANCHORS:
        review_reasons.append("insufficient_non_target_anchor_candidates")

    if suppress_reasons:
        return _finish(
            state=state,
            target_pair_index=target_pair_index,
            target_diagnostic=target_diagnostic,
            status=SUPPRESS,
            reasons=suppress_reasons,
        )
    if review_reasons:
        return _finish(
            state=state,
            target_pair_index=target_pair_index,
            target_diagnostic=target_diagnostic,
            status=REVIEW_ONLY,
            reasons=review_reasons,
        )
    return _finish(
        state=state,
        target_pair_index=target_pair_index,
        target_diagnostic=target_diagnostic,
        status=ELIGIBLE,
        reasons=["height_reproject_applicable"],
    )


def _as_finite_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def gate_height_y_delta(
    max_y_delta: Any,
    expert_review_threshold: Any,
    hard_fail_threshold: Any,
) -> dict[str, Any]:
    """Gate a future y delta numerically without generating a candidate."""
    parsed_delta = _as_finite_float(max_y_delta)
    expert_threshold = _as_finite_float(expert_review_threshold)
    hard_threshold = _as_finite_float(hard_fail_threshold)
    if parsed_delta is None or expert_threshold is None or hard_threshold is None:
        return {
            "height_reproject_status": REVIEW_ONLY,
            "height_reproject_blocking_reasons": ["max_y_delta_unavailable"],
            "max_y_delta": parsed_delta,
            "y_delta_gate_status": "review_only_delta_unavailable",
            "gate_version": GATE_VERSION,
        }
    if parsed_delta > hard_threshold:
        return {
            "height_reproject_status": SUPPRESS,
            "height_reproject_blocking_reasons": ["max_y_delta_exceeds_hard_fail_threshold"],
            "max_y_delta": parsed_delta,
            "y_delta_gate_status": "suppress_large_y_delta",
            "gate_version": GATE_VERSION,
        }
    if parsed_delta >= expert_threshold:
        return {
            "height_reproject_status": REVIEW_ONLY,
            "height_reproject_blocking_reasons": ["max_y_delta_large"],
            "max_y_delta": parsed_delta,
            "y_delta_gate_status": "review_only_large_y_delta",
            "gate_version": GATE_VERSION,
        }
    return {
        "height_reproject_status": ELIGIBLE,
        "height_reproject_blocking_reasons": [],
        "max_y_delta": parsed_delta,
        "y_delta_gate_status": "eligible_y_delta",
        "gate_version": GATE_VERSION,
    }


__all__ = [
    "ELIGIBLE",
    "GATE_VERSION",
    "REVIEW_ONLY",
    "SUPPRESS",
    "diagnose_height_reproject_applicability",
    "gate_height_y_delta",
]
