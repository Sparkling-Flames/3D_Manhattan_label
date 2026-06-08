"""M14.5 low-risk pair operations for Paper A Manhattan expert tools.

This module consumes RoomLayoutState pair diagnostics and can produce one
preview-only candidate: align one pair's top/bottom x coordinate to its center.
It does not change y coordinates, reproject height, snap locally, move walls,
write annotations, connect to UI, or feed correctness, formal g_t, routing,
worker quality metrics, or P1/C1/C2/T1/V1 artifacts.
"""

from __future__ import annotations

import copy
import math
from typing import Any, Mapping, Sequence

from tools.paper_a_manhattan.manhattan_constrained_fit import parse_ordered_pairs
from tools.paper_a_manhattan.manhattan_layout_state import build_room_layout_state


ASSIST_VERSION = "manhattan_pair_assist_m14_5_v1"

ELIGIBLE = "eligible"
REVIEW_ONLY = "review_only"
SUPPRESS = "suppress"

STATE_REVIEW_WARNINGS = {
    "layout_height_spread_high",
}
STATE_SUPPRESS_WARNINGS = {
    "wrap_seam_unresolved",
}
PAIR_REVIEW_WARNINGS = {
    "height_residual_high",
    "top_not_above_bottom",
}


def _finish_diagnosis(
    *,
    state: Mapping[str, Any],
    pair_index: int,
    diagnostic: Mapping[str, Any] | None,
    assist_status: str,
    assist_reasons: list[str],
) -> dict[str, Any]:
    return {
        "state_status": state.get("state_status"),
        "target_pair_index": pair_index,
        "vertical_x_residual": diagnostic.get("vertical_x_residual") if diagnostic else None,
        "height_residual": diagnostic.get("height_residual") if diagnostic else None,
        "is_anchor_candidate": diagnostic.get("is_anchor_candidate") if diagnostic else False,
        "pair_warnings": list(diagnostic.get("warnings", [])) if diagnostic else [],
        "state_warnings": list(state.get("state_warnings", [])),
        "assist_status": assist_status,
        "assist_reasons": assist_reasons,
        "assist_version": ASSIST_VERSION,
    }


def _find_pair_diagnostic(state: Mapping[str, Any], pair_index: int) -> Mapping[str, Any] | None:
    for diagnostic in state.get("pair_diagnostics", []):
        if diagnostic.get("pair_index") == pair_index:
            return diagnostic
    return None


def _state_status_from_warnings(state_warnings: Sequence[str]) -> tuple[str, list[str]]:
    warning_set = set(state_warnings)
    suppress_hits = sorted(warning_set & STATE_SUPPRESS_WARNINGS)
    if suppress_hits:
        return SUPPRESS, [f"state_warning_{warning}" for warning in suppress_hits]
    review_hits = sorted(warning_set & STATE_REVIEW_WARNINGS)
    if review_hits:
        return REVIEW_ONLY, [f"state_warning_{warning}" for warning in review_hits]
    return ELIGIBLE, ["pair_alignment_eligible"]


def _as_pair_index(pair_index: Any) -> int | None:
    if isinstance(pair_index, bool):
        return None
    try:
        value = int(pair_index)
    except (TypeError, ValueError):
        return None
    return value if value >= 1 else None


def diagnose_pair_alignment(
    ordered_pairs: Sequence[Mapping[str, Any]],
    pair_index: int,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Diagnose whether one pair is eligible for x-alignment preview.

    The result is an expert-side assist decision only. It is not correctness,
    not an apply instruction, and not annotation writeback.
    """
    target_pair_index = _as_pair_index(pair_index)
    if target_pair_index is None:
        return _finish_diagnosis(
            state={"state_status": "failed", "state_warnings": ["invalid_pair_index"]},
            pair_index=pair_index,
            diagnostic=None,
            assist_status=SUPPRESS,
            assist_reasons=["invalid_pair_index"],
        )

    state = build_room_layout_state(ordered_pairs, metadata=metadata)
    state_status = state.get("state_status")
    if state_status in {"failed", "excluded"}:
        return _finish_diagnosis(
            state=state,
            pair_index=target_pair_index,
            diagnostic=None,
            assist_status=SUPPRESS,
            assist_reasons=[f"state_{state_status}"] + list(state.get("state_warnings", [])),
        )

    diagnostic = _find_pair_diagnostic(state, target_pair_index)
    if diagnostic is None:
        return _finish_diagnosis(
            state=state,
            pair_index=target_pair_index,
            diagnostic=None,
            assist_status=SUPPRESS,
            assist_reasons=["target_pair_missing"],
        )

    vertical_x_residual = diagnostic.get("vertical_x_residual")
    if not isinstance(vertical_x_residual, (int, float)) or not math.isfinite(vertical_x_residual):
        return _finish_diagnosis(
            state=state,
            pair_index=target_pair_index,
            diagnostic=diagnostic,
            assist_status=REVIEW_ONLY,
            assist_reasons=["vertical_x_residual_unavailable"],
        )
    if vertical_x_residual <= 0:
        return _finish_diagnosis(
            state=state,
            pair_index=target_pair_index,
            diagnostic=diagnostic,
            assist_status=REVIEW_ONLY,
            assist_reasons=["vertical_x_residual_zero"],
        )

    state_assist_status, state_reasons = _state_status_from_warnings(state.get("state_warnings", []))
    if state_assist_status != ELIGIBLE:
        return _finish_diagnosis(
            state=state,
            pair_index=target_pair_index,
            diagnostic=diagnostic,
            assist_status=state_assist_status,
            assist_reasons=state_reasons,
        )

    pair_warning_hits = sorted(set(diagnostic.get("warnings", [])) & PAIR_REVIEW_WARNINGS)
    if pair_warning_hits:
        return _finish_diagnosis(
            state=state,
            pair_index=target_pair_index,
            diagnostic=diagnostic,
            assist_status=REVIEW_ONLY,
            assist_reasons=[f"pair_warning_{warning}" for warning in pair_warning_hits],
        )

    return _finish_diagnosis(
        state=state,
        pair_index=target_pair_index,
        diagnostic=diagnostic,
        assist_status=ELIGIBLE,
        assist_reasons=["align_pair_x_candidate_available"],
    )


def _set_candidate_pair_x(row: dict[str, Any], target_x: float) -> None:
    if "top" in row and "bottom" in row:
        row["top"]["x"] = target_x
        row["bottom"]["x"] = target_x
    elif "ceiling" in row and "floor" in row:
        row["ceiling"]["x"] = target_x
        row["floor"]["x"] = target_x
    elif {"top_x", "top_y", "bottom_x", "bottom_y"}.issubset(row):
        row["top_x"] = target_x
        row["bottom_x"] = target_x
    elif {"x", "y_ceiling", "y_floor"}.issubset(row):
        row["x"] = target_x


def _empty_proposal(diagnosis: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "candidate_pairs": [],
        "per_point_delta": [],
        "max_abs_delta": None,
        "assist_status": diagnosis.get("assist_status"),
        "assist_reasons": list(diagnosis.get("assist_reasons", [])),
        "assist_version": ASSIST_VERSION,
    }


def propose_align_pair_x(
    ordered_pairs: Sequence[Mapping[str, Any]],
    pair_index: int,
    metadata: Mapping[str, Any] | None = None,
    strategy: str = "center",
) -> dict[str, Any]:
    """Return a preview-only x-alignment candidate for one pair.

    The candidate only changes the target pair's top.x and bottom.x. It keeps
    y values and all other pairs unchanged and performs no apply/writeback.
    """
    diagnosis = diagnose_pair_alignment(ordered_pairs, pair_index, metadata=metadata)
    if strategy != "center":
        result = dict(_empty_proposal(diagnosis))
        result["assist_status"] = SUPPRESS
        result["assist_reasons"] = ["unsupported_strategy"]
        return result
    if diagnosis["assist_status"] != ELIGIBLE:
        return _empty_proposal(diagnosis)

    target_pair_index = int(diagnosis["target_pair_index"])
    try:
        pairs = parse_ordered_pairs(ordered_pairs)
    except ValueError:
        return _empty_proposal(diagnosis)

    pair = next((candidate for candidate in pairs if candidate.pair_index == target_pair_index), None)
    if pair is None:
        return _empty_proposal(diagnosis)

    target_x = pair.center_x
    candidate_pairs = copy.deepcopy(list(ordered_pairs))
    _set_candidate_pair_x(candidate_pairs[target_pair_index - 1], target_x)

    top_dx = target_x - pair.top.x
    bottom_dx = target_x - pair.bottom.x
    deltas = [
        {
            "pair_index": target_pair_index,
            "top_dx": top_dx,
            "top_dy": 0.0,
            "bottom_dx": bottom_dx,
            "bottom_dy": 0.0,
        }
    ]
    delta_values = [abs(top_dx), abs(bottom_dx), 0.0]
    max_abs_delta = max(delta_values) if delta_values else None
    if max_abs_delta is None:
        return {
            **_empty_proposal(diagnosis),
            "assist_status": REVIEW_ONLY,
            "assist_reasons": ["max_abs_delta_unavailable"],
        }

    return {
        "candidate_pairs": candidate_pairs,
        "per_point_delta": deltas,
        "max_abs_delta": max_abs_delta,
        "assist_status": ELIGIBLE,
        "assist_reasons": list(diagnosis["assist_reasons"]),
        "assist_version": ASSIST_VERSION,
    }


__all__ = [
    "ASSIST_VERSION",
    "ELIGIBLE",
    "REVIEW_ONLY",
    "SUPPRESS",
    "diagnose_pair_alignment",
    "propose_align_pair_x",
]
