"""Single-image expert-side Manhattan assist CLI.

This is an offline M15.x diagnostic entrypoint. It reads one image annotation,
checks preview compatibility when raw keypoints are supplied, builds
RoomLayoutState diagnostics, proposes low-risk Align Pair X review prompts, and
reports height reproject applicability rows plus conservative fixed-bottom /
top-y review-only dry-run rows. It does not implement UI, ghost overlays,
apply/undo/writeback, true automatic height reproject, routing, or formal
artifacts.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.paper_a_manhattan.manhattan_assist_review_harness import (  # noqa: E402
    HEIGHT_REPROJECT_APPLICABILITY_OPERATION,
    build_pair_assist_review_rows,
)
from tools.paper_a_manhattan.manhattan_layout_state import build_room_layout_state  # noqa: E402
from tools.paper_a_manhattan.manhattan_height_reproject_candidate import (  # noqa: E402
    build_height_reproject_candidate_rows,
)
from tools.paper_a_manhattan.manhattan_pair_assist import (  # noqa: E402
    ELIGIBLE,
    diagnose_pair_alignment,
    propose_align_pair_x,
)
from tools.paper_a_manhattan.manhattan_preview_compat import (  # noqa: E402
    COMPATIBLE,
    DEFAULT_HEIGHT,
    DEFAULT_WIDTH,
    DUPLICATE_CORNER_THRESHOLD_RATIO,
    check_preview_compatibility,
)
from tools.paper_a_manhattan.manhattan_verified_3d_local_assist import (  # noqa: E402
    build_verified_3d_local_assist,
)


TOOL_VERSION = "single_image_manhattan_assist_m15_18_2_v1"
TOPOLOGY_OVERRIDE_SCHEMA_VERSION = "verified_preview_order_m15_13_v1"
PREVIEW_ORDER_OVERRIDE_ALLOWED_STATUSES = {
    "compatibility_failure_duplicate",
    "compatibility_failure_wrong_order",
}
NO_WRITEBACK_NOTE = (
    "Expert-side diagnostic only: no UI, no apply/writeback, no routing, "
    "no formal g_t, no worker quality metric, no P1/C1/C2/T1/V1 artifact."
)


def _as_int(value: Any, default: int) -> int:
    if isinstance(value, bool) or value is None:
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y"}:
            return True
        if normalized in {"false", "0", "no", "n"}:
            return False
    if isinstance(value, (int, float)):
        return value != 0
    return default


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("single-image assist input must be a JSON object")
    return payload


def _preview_pair_to_ordered_pair(pair: Any) -> dict[str, Any]:
    top = pair.p1 if pair.p1.y <= pair.p2.y else pair.p2
    bottom = pair.p2 if pair.p1.y <= pair.p2.y else pair.p1
    return {
        "top": {"x": top.x_percent, "y": top.y_percent},
        "bottom": {"x": bottom.x_percent, "y": bottom.y_percent},
    }


def _preview_summary(
    preview: Any | None,
    *,
    input_mode: str,
    width: int | None = None,
    height: int | None = None,
    preserve_order: bool | None = None,
) -> dict[str, Any]:
    if preview is None:
        return {
            "status": "not_run_simplified_ordered_pairs",
            "input_mode": input_mode,
            "n_pairs": None,
            "n_unpaired_points": None,
            "suggestion_allowed": True,
            "compatibility_reason": "ordered_pairs_input_bypasses_preview_parser",
            "pairing_rule_version": None,
            "width": width,
            "height": height,
            "preserve_order": preserve_order,
        }
    return {
        "status": preview.status,
        "input_mode": input_mode,
        "n_pairs": len(preview.ordered_corners),
        "n_unpaired_points": len(preview.unpaired_points),
        "suggestion_allowed": preview.suggestion_allowed,
        "compatibility_reason": preview.compatibility_reason,
        "pairing_rule_version": preview.pairing_rule_version,
        "width": width,
        "height": height,
        "preserve_order": preserve_order,
    }


def _extract_label_studio_keypoints(results: Any) -> list[dict[str, Any]]:
    if not isinstance(results, list):
        return []
    keypoints: list[dict[str, Any]] = []
    for idx, result in enumerate(results):
        if not isinstance(result, Mapping) or result.get("type") != "keypointlabels":
            continue
        value = result.get("value")
        if not isinstance(value, Mapping):
            continue
        try:
            x = float(value["x"])
            y = float(value["y"])
        except (KeyError, TypeError, ValueError):
            continue
        keypoints.append({"x": x, "y": y, "point_id": result.get("id"), "original_index": idx})
    return keypoints


def _raw_keypoints_from_payload(payload: Mapping[str, Any]) -> tuple[str, list[Any] | None]:
    if isinstance(payload.get("keypoints"), list):
        return "raw_keypoints", payload["keypoints"]
    if isinstance(payload.get("raw_keypoints"), list):
        return "raw_keypoints", payload["raw_keypoints"]
    if isinstance(payload.get("result"), list):
        return "label_studio_result", _extract_label_studio_keypoints(payload["result"])
    if isinstance(payload.get("label_studio_result"), list):
        return "label_studio_result", _extract_label_studio_keypoints(
            payload["label_studio_result"]
        )
    return "unknown", None


def _topology_override_info(
    *,
    active: bool,
    source: str,
    default_preview_status: str | None,
    default_preview_reason: str | None,
    payload: Mapping[str, Any],
    override_status: str = "not_requested",
    invalid_reason: str | None = None,
    override_order: Sequence[int] | None = None,
    validation_reasons: Sequence[str] | None = None,
) -> dict[str, Any]:
    reasons = list(validation_reasons or ([] if invalid_reason is None else [invalid_reason]))
    return {
        "topology_override_schema_version": TOPOLOGY_OVERRIDE_SCHEMA_VERSION,
        "preview_order_override_active": active,
        "topology_source": source,
        "default_preview_status": default_preview_status,
        "default_preview_reason": default_preview_reason,
        "preview_order_override": list(override_order) if override_order is not None else payload.get("preview_order_override"),
        "order_verified_by_expert": _as_bool(payload.get("order_verified_by_expert"), False),
        "order_override_note": payload.get("order_override_note"),
        "override_status": override_status,
        "invalid_reason": invalid_reason,
        "override_validation_status": (
            "valid"
            if override_status == "valid_preview_order_override"
            else "invalid"
            if invalid_reason is not None
            else "not_requested"
            if payload.get("preview_order_override") is None
            else "not_active"
        ),
        "override_validation_reasons": reasons,
    }


def _validate_preview_order_override(order: Any, pair_count: int) -> tuple[list[int] | None, str | None]:
    if not isinstance(order, list):
        return None, "preview_order_override_not_list"
    parsed: list[int] = []
    for value in order:
        if isinstance(value, bool):
            return None, "preview_order_override_non_integer"
        if not isinstance(value, (int, str)):
            return None, "preview_order_override_non_integer"
        try:
            parsed_value = int(value)
        except (TypeError, ValueError):
            return None, "preview_order_override_non_integer"
        if parsed_value != value and not isinstance(value, str):
            return None, "preview_order_override_non_integer"
        parsed.append(parsed_value)
    if len(parsed) != pair_count:
        return None, "preview_order_override_length_mismatch"
    if len(set(parsed)) != len(parsed):
        return None, "preview_order_override_duplicate_index"
    if any(value < 1 or value > pair_count for value in parsed):
        return None, "preview_order_override_out_of_range"
    return parsed, None


def _ordered_pairs_from_preview_with_order(preview: Any, order: Sequence[int]) -> list[dict[str, Any]]:
    return [
        _preview_pair_to_ordered_pair(preview.ordered_corners[index - 1])
        for index in order
    ]


def _parse_input_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    width = _as_int(payload.get("width"), DEFAULT_WIDTH)
    height = _as_int(payload.get("height"), DEFAULT_HEIGHT)
    preserve_order = _as_bool(payload.get("preserve_order"), False)
    if isinstance(payload.get("ordered_pairs"), list):
        return {
            "input_mode": "simplified_ordered_pairs",
            "ordered_pairs": list(payload["ordered_pairs"]),
            "raw_keypoints": None,
            "width": width,
            "height": height,
            "preserve_order": preserve_order,
        }

    input_mode, raw_keypoints = _raw_keypoints_from_payload(payload)
    if not isinstance(raw_keypoints, list):
        raise ValueError(
            "input must include ordered_pairs, keypoints, raw_keypoints, result, "
            "or label_studio_result"
        )
    return {
        "input_mode": input_mode,
        "ordered_pairs": None,
        "raw_keypoints": raw_keypoints,
        "width": width,
        "height": height,
        "preserve_order": preserve_order,
    }


def _run_default_preview(parsed_input: Mapping[str, Any]) -> tuple[Any | None, dict[str, Any], list[dict[str, Any]]]:
    input_mode = str(parsed_input["input_mode"])
    width = int(parsed_input["width"])
    height = int(parsed_input["height"])
    preserve_order = bool(parsed_input["preserve_order"])
    if input_mode == "simplified_ordered_pairs":
        return (
            None,
            _preview_summary(
                None,
                input_mode=input_mode,
                width=width,
                height=height,
                preserve_order=preserve_order,
            ),
            [],
        )

    preview = check_preview_compatibility(
        parsed_input["raw_keypoints"],
        preserve_order=preserve_order,
        width=width,
        height=height,
    )
    return (
        preview,
        _preview_summary(
            preview,
            input_mode=input_mode,
            width=width,
            height=height,
            preserve_order=preserve_order,
        ),
        _center_rows_from_preview(preview, width),
    )


def _resolve_topology_policy(
    payload: Mapping[str, Any],
    parsed_input: Mapping[str, Any],
    preview: Any | None,
    preview_info: Mapping[str, Any],
) -> dict[str, Any]:
    input_mode = str(parsed_input["input_mode"])
    if input_mode == "simplified_ordered_pairs":
        return _topology_override_info(
            active=False,
            source="ordered_pairs_input_order",
            default_preview_status=preview_info["status"],
            default_preview_reason=preview_info["compatibility_reason"],
            payload=payload,
        )

    default_status = preview.status
    default_reason = preview.compatibility_reason
    if _as_bool(payload.get("order_verified_by_expert"), False):
        override_order, invalid_reason = _validate_preview_order_override(
            payload.get("preview_order_override"),
            len(preview.ordered_corners),
        )
        if invalid_reason is not None:
            return _topology_override_info(
                active=False,
                source="invalid_preview_order_override",
                default_preview_status=default_status,
                default_preview_reason=default_reason,
                payload=payload,
                override_status="invalid_preview_order_override",
                invalid_reason=invalid_reason,
                override_order=override_order,
            )
        if default_status not in PREVIEW_ORDER_OVERRIDE_ALLOWED_STATUSES:
            if default_status == COMPATIBLE:
                return _topology_override_info(
                    active=False,
                    source="default_preview_order",
                    default_preview_status=default_status,
                    default_preview_reason=default_reason,
                    payload=payload,
                    override_status="preview_order_override_ignored_for_compatible_default",
                    override_order=override_order,
                )
            return _topology_override_info(
                active=False,
                source="preview_order_override_not_allowed_for_status",
                default_preview_status=default_status,
                default_preview_reason=default_reason,
                payload=payload,
                override_status="preview_order_override_not_allowed_for_status",
                invalid_reason="preview_order_override_not_allowed_for_status",
                override_order=override_order,
            )
        return _topology_override_info(
            active=True,
            source="expert_verified_preview_order",
            default_preview_status=default_status,
            default_preview_reason=default_reason,
            payload=payload,
            override_status="valid_preview_order_override",
            override_order=override_order,
            validation_reasons=["order_verified_by_expert"],
        )

    if payload.get("preview_order_override") is not None:
        return _topology_override_info(
            active=False,
            source="invalid_preview_order_override",
            default_preview_status=default_status,
            default_preview_reason=default_reason,
            payload=payload,
            override_status="invalid_preview_order_override",
            invalid_reason="order_not_verified_by_expert",
        )

    if preview.status != COMPATIBLE:
        return _topology_override_info(
            active=False,
            source="default_preview_order_unusable",
            default_preview_status=default_status,
            default_preview_reason=default_reason,
            payload=payload,
        )
    return _topology_override_info(
        active=False,
        source="default_preview_order",
        default_preview_status=default_status,
        default_preview_reason=default_reason,
        payload=payload,
    )


def _materialize_ordered_pairs(
    parsed_input: Mapping[str, Any],
    preview: Any | None,
    topology_override: Mapping[str, Any],
) -> list[dict[str, Any]]:
    if parsed_input["input_mode"] == "simplified_ordered_pairs":
        return list(parsed_input["ordered_pairs"])
    if topology_override.get("preview_order_override_active"):
        override_order, _ = _validate_preview_order_override(
            topology_override.get("preview_order_override"),
            len(preview.ordered_corners),
        )
        return _ordered_pairs_from_preview_with_order(preview, override_order or [])
    if topology_override.get("topology_source") == "default_preview_order":
        return [_preview_pair_to_ordered_pair(pair) for pair in preview.ordered_corners]
    return []


def _resolve_ordered_pairs(
    payload: Mapping[str, Any],
) -> tuple[
    str,
    dict[str, Any],
    list[dict[str, Any]],
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    parsed_input = _parse_input_payload(payload)
    preview, preview_info, default_centers = _run_default_preview(parsed_input)
    preview_pair_table = _preview_pair_table_from_preview(preview)
    near_duplicate_pair_table = _near_duplicate_pair_table_from_preview(
        preview_pair_table,
        threshold_percent=DUPLICATE_CORNER_THRESHOLD_RATIO * 100.0,
    )
    topology_override = _resolve_topology_policy(
        payload,
        parsed_input,
        preview,
        preview_info,
    )
    ordered_pairs = _materialize_ordered_pairs(
        parsed_input,
        preview,
        topology_override,
    )
    return (
        str(parsed_input["input_mode"]),
        dict(preview_info),
        ordered_pairs,
        topology_override,
        default_centers,
        preview_pair_table,
        near_duplicate_pair_table,
    )


def _center_rows_from_ordered_pairs(
    ordered_pairs: Sequence[Mapping[str, Any]],
    *,
    index_source: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, pair in enumerate(ordered_pairs, start=1):
        try:
            top_x = float(pair["top"]["x"])
            bottom_x = float(pair["bottom"]["x"])
        except (KeyError, TypeError, ValueError):
            continue
        rows.append(
            {
                "pair_index": idx,
                "center_x": (top_x + bottom_x) / 2.0,
                "index_source": index_source,
            }
        )
    return rows


def _center_rows_from_preview(preview: Any, width: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, pair in enumerate(preview.ordered_corners, start=1):
        rows.append(
            {
                "pair_index": idx,
                "center_x": pair.x * 100.0 / width,
                "index_source": "preview_ordered_corners",
            }
        )
    return rows


def _point_id(point: Any) -> str:
    if point.point_id is not None:
        return str(point.point_id)
    if point.original_index is not None:
        return f"input_index_{point.original_index}"
    return "unknown"


def _preview_pair_table_from_preview(preview: Any | None) -> list[dict[str, Any]]:
    if preview is None:
        return []
    rows: list[dict[str, Any]] = []
    for idx, pair in enumerate(preview.ordered_corners, start=1):
        top = pair.p1 if pair.p1.y <= pair.p2.y else pair.p2
        bottom = pair.p2 if pair.p1.y <= pair.p2.y else pair.p1
        rows.append(
            {
                "preview_pair_index": idx,
                "top_id": _point_id(top),
                "bottom_id": _point_id(bottom),
                "top_x": top.x_percent,
                "bottom_x": bottom.x_percent,
                "center_x": (top.x_percent + bottom.x_percent) / 2.0,
                "top_y": top.y_percent,
                "bottom_y": bottom.y_percent,
                "pairing_source": "default_preview_order",
            }
        )
    return rows


def _near_duplicate_pair_table_from_preview(
    preview_pair_table: Sequence[Mapping[str, Any]],
    *,
    threshold_percent: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    ordered = sorted(preview_pair_table, key=lambda row: float(row["center_x"]))
    for left, right in zip(ordered, ordered[1:]):
        delta = abs(float(right["center_x"]) - float(left["center_x"]))
        if delta < threshold_percent:
            rows.append(
                {
                    "left_preview_pair_index": left["preview_pair_index"],
                    "right_preview_pair_index": right["preview_pair_index"],
                    "left_center_x": left["center_x"],
                    "right_center_x": right["center_x"],
                    "delta_center_x": delta,
                    "duplicate_threshold_percent": threshold_percent,
                    "reason": "near_duplicate_corner_pair",
                    "manual_override_required": True,
                }
            )
    return rows


def _override_pack(
    *,
    preview_info: Mapping[str, Any],
    topology_override: Mapping[str, Any],
) -> dict[str, Any]:
    default_n_pairs = preview_info.get("n_pairs")
    example = (
        list(range(1, int(default_n_pairs) + 1))
        if isinstance(default_n_pairs, int)
        else []
    )
    status = str(topology_override.get("override_validation_status") or "not_requested")
    reasons = list(topology_override.get("override_validation_reasons", []))
    hard_stop = preview_info.get("status") != COMPATIBLE
    return {
        "override_needed": hard_stop and not topology_override.get("preview_order_override_active"),
        "hard_stop_reason": (
            topology_override.get("invalid_reason")
            or preview_info.get("compatibility_reason")
            if hard_stop or status == "invalid"
            else None
        ),
        "default_n_pairs": default_n_pairs,
        "default_preview_status": preview_info.get("status"),
        "default_preview_reason": preview_info.get("compatibility_reason"),
        "accepted_override_formats": [
            "preview_order_override=[2,1,3,4]",
        ],
        "example_preview_order_override": example,
        "override_validation_status": status,
        "override_validation_reasons": reasons,
        "writeback_allowed": False,
    }


def _duplicate_diagnostics_from_centers(
    centers: Sequence[Mapping[str, Any]],
    *,
    threshold_percent: float,
) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    ordered = sorted(centers, key=lambda row: float(row["center_x"]))
    for left, right in zip(ordered, ordered[1:]):
        delta = abs(float(right["center_x"]) - float(left["center_x"]))
        if delta < threshold_percent:
            diagnostics.append(
                {
                    "left_pair_index": left["pair_index"],
                    "right_pair_index": right["pair_index"],
                    "left_center_x": left["center_x"],
                    "right_center_x": right["center_x"],
                    "delta_center_x": delta,
                    "duplicate_threshold_percent": threshold_percent,
                    "reason": "near_duplicate_corner_pair",
                    "manual_only": True,
                    "index_source": left.get("index_source", "unknown"),
                }
            )
    return diagnostics


def _order_diagnostics_from_centers(
    centers: Sequence[Mapping[str, Any]],
    *,
    reason: str = "local_order_zigzag",
    manual_only: bool = True,
) -> dict[str, Any]:
    if len(centers) < 2:
        return {
            "is_x_monotonic": True,
            "n_direction_changes": 0,
            "direction_change_pairs": [],
            "manual_only_reason": None,
        }
    deltas: list[tuple[int, int, float]] = []
    for left, right in zip(centers, centers[1:]):
        delta = float(right["center_x"]) - float(left["center_x"])
        if delta == 0:
            continue
        deltas.append((int(left["pair_index"]), int(right["pair_index"]), delta))
    signs = [1 if delta > 0 else -1 for _, _, delta in deltas]
    direction_changes: list[dict[str, Any]] = []
    for idx in range(1, len(signs)):
        if signs[idx] == signs[idx - 1]:
            continue
        direction_changes.append(
            {
                "left_pair_index": deltas[idx - 1][0],
                "middle_pair_index": deltas[idx - 1][1],
                "right_pair_index": deltas[idx][1],
                "from_direction": "increasing" if signs[idx - 1] > 0 else "decreasing",
                "to_direction": "increasing" if signs[idx] > 0 else "decreasing",
                "reason": reason,
                "manual_only": manual_only,
            }
        )
    return {
        "is_x_monotonic": not direction_changes,
        "n_direction_changes": len(direction_changes),
        "direction_change_pairs": direction_changes,
        "manual_only_reason": reason if direction_changes and manual_only else None,
        "diagnostic_reason": reason if direction_changes else None,
    }


def _diagnostics_from_payload(
    ordered_pairs: Sequence[Mapping[str, Any]],
    *,
    topology_override: Mapping[str, Any],
    default_centers: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    threshold_percent = DUPLICATE_CORNER_THRESHOLD_RATIO * 100.0
    default_centers = list(default_centers)

    if ordered_pairs:
        effective_centers = _center_rows_from_ordered_pairs(
            ordered_pairs,
            index_source=(
                "expert_verified_preview_order"
                if topology_override.get("preview_order_override_active")
                else "effective_ordered_pairs"
            ),
        )
    else:
        effective_centers = default_centers

    effective_reason = (
        "expert_verified_non_x_monotonic_order"
        if topology_override.get("preview_order_override_active")
        else "local_order_zigzag"
    )
    effective_manual_only = not topology_override.get("preview_order_override_active")
    return (
        _duplicate_diagnostics_from_centers(
            effective_centers,
            threshold_percent=threshold_percent,
        ),
        _order_diagnostics_from_centers(default_centers or effective_centers),
        _order_diagnostics_from_centers(
            effective_centers,
            reason=effective_reason,
            manual_only=effective_manual_only,
        ),
    )


def _pair_indices(ordered_pairs: Sequence[Mapping[str, Any]]) -> list[int]:
    return list(range(1, len(ordered_pairs) + 1))


def _pair_index_mapping(
    ordered_pairs: Sequence[Mapping[str, Any]],
    topology_override: Mapping[str, Any],
) -> list[dict[str, Any]]:
    override_order = topology_override.get("preview_order_override")
    use_override = (
        topology_override.get("preview_order_override_active") is True
        and isinstance(override_order, list)
        and len(override_order) == len(ordered_pairs)
    )
    rows: list[dict[str, Any]] = []
    for effective_index, pair in enumerate(ordered_pairs, start=1):
        source_index = override_order[effective_index - 1] if use_override else effective_index
        top = pair.get("top", {})
        bottom = pair.get("bottom", {})
        rows.append(
            {
                "effective_pair_index": effective_index,
                "source_preview_order_index": source_index,
                "top_x": top.get("x"),
                "bottom_x": bottom.get("x"),
                "center_x": (
                    (float(top["x"]) + float(bottom["x"])) / 2.0
                    if "x" in top and "x" in bottom
                    else None
                ),
                "top_y": top.get("y"),
                "bottom_y": bottom.get("y"),
            }
        )
    return rows


def _proposal_row(
    ordered_pairs: Sequence[Mapping[str, Any]],
    pair_index: int,
    metadata: Mapping[str, Any] | None,
) -> dict[str, Any]:
    diagnosis = diagnose_pair_alignment(ordered_pairs, pair_index, metadata=metadata)
    proposal = propose_align_pair_x(ordered_pairs, pair_index, metadata=metadata)
    delta = proposal.get("per_point_delta", [])
    first_delta = delta[0] if delta else {}
    row = {
        "pair_index": diagnosis.get("target_pair_index", pair_index),
        "assist_status": proposal.get("assist_status"),
        "assist_reasons": list(proposal.get("assist_reasons", [])),
        "vertical_x_residual": diagnosis.get("vertical_x_residual"),
        "height_residual": diagnosis.get("height_residual"),
        "pair_warnings": list(diagnosis.get("pair_warnings", [])),
        "state_warnings": list(diagnosis.get("state_warnings", [])),
        "max_abs_delta": proposal.get("max_abs_delta"),
        "top_dx": first_delta.get("top_dx"),
        "bottom_dx": first_delta.get("bottom_dx"),
    }
    if proposal.get("assist_status") == ELIGIBLE and first_delta:
        pair = ordered_pairs[pair_index - 1]
        top = pair["top"]
        bottom = pair["bottom"]
        row["suggested_top_x"] = top["x"] + first_delta["top_dx"]
        row["suggested_bottom_x"] = bottom["x"] + first_delta["bottom_dx"]
        row["y_change_allowed"] = False
    return row


def _manual_edit_row(
    pair: Mapping[str, Any],
    proposal: Mapping[str, Any],
    manual_only_reason: str | None = None,
) -> dict[str, Any]:
    pair_index = proposal["pair_index"]
    top = pair["top"]
    bottom = pair["bottom"]
    eligible = proposal.get("assist_status") == ELIGIBLE and manual_only_reason is None
    reason = manual_only_reason or "; ".join(proposal.get("assist_reasons", []))
    row = {
        "pair_index": pair_index,
        "action": "align_pair_x" if eligible else "manual_review_only",
        "from_top_x": top["x"],
        "from_bottom_x": bottom["x"],
        "to_top_x": proposal.get("suggested_top_x") if eligible else None,
        "to_bottom_x": proposal.get("suggested_bottom_x") if eligible else None,
        "top_dx": proposal.get("top_dx"),
        "bottom_dx": proposal.get("bottom_dx"),
        "reason": None if eligible else reason,
        "y_change_allowed": False,
        "notes": (
            "Manual expert may align top.x and bottom.x only; keep y unchanged."
            if eligible
            else reason
        ),
    }
    return row


def _first_reason(*reason_lists: Sequence[Any]) -> str:
    for reasons in reason_lists:
        for reason in reasons:
            return str(reason)
    return "no_specific_reason"


def _height_row_by_pair(height_rows: Sequence[Mapping[str, Any]]) -> dict[int, Mapping[str, Any]]:
    lookup: dict[int, Mapping[str, Any]] = {}
    for row in height_rows:
        pair_index = row.get("target_pair_index")
        if isinstance(pair_index, int):
            lookup[pair_index] = row
    return lookup


def _review_priority(
    proposal: Mapping[str, Any],
    height_row: Mapping[str, Any] | None,
) -> tuple[str, str, bool, tuple[float, float]]:
    assist_status = proposal.get("assist_status")
    height_status = height_row.get("height_reproject_status") if height_row else None
    vertical = proposal.get("vertical_x_residual")
    height_residual = proposal.get("height_residual")
    has_warnings = bool(proposal.get("pair_warnings") or proposal.get("state_warnings"))
    if not isinstance(vertical, (int, float)):
        vertical = 0.0
    if not isinstance(height_residual, (int, float)):
        height_residual = 0.0
    if assist_status == ELIGIBLE and vertical > 0:
        return "align_x_first", "align_pair_x", False, (0.0, -float(vertical))
    if assist_status == "review_only" or height_status == "review_only" or has_warnings:
        return "diagnostic_review", "manual_review_only", False, (
            1.0,
            -max(float(vertical), float(height_residual)),
        )
    if assist_status == "suppress" or height_status == "suppress":
        return "manual_only_suppressed", "manual_review_only", True, (2.0, -float(vertical))
    return "low_priority_review", "manual_review_only", False, (3.0, -float(vertical))


def _recommended_review_order(
    proposals: Sequence[Mapping[str, Any]],
    height_rows: Sequence[Mapping[str, Any]],
    manual_only_reasons: Mapping[int, str] | None = None,
) -> list[dict[str, Any]]:
    height_lookup = _height_row_by_pair(height_rows)
    manual_only_reasons = manual_only_reasons or {}
    ranked: list[tuple[tuple[float, float], dict[str, Any]]] = []
    for proposal in proposals:
        pair_index = proposal["pair_index"]
        height_row = height_lookup.get(pair_index)
        if pair_index in manual_only_reasons:
            review_priority = "manual_only_dense_or_order"
            primary_action = "manual_review_only"
            manual_only = True
            sort_key = (2.0, 0.0)
        else:
            review_priority, primary_action, manual_only, sort_key = _review_priority(
                proposal,
                height_row,
            )
        reason = _first_reason(
            [manual_only_reasons[pair_index]] if pair_index in manual_only_reasons else [],
            proposal.get("assist_reasons", []),
            height_row.get("height_reproject_blocking_reasons", []) if height_row else [],
            height_row.get("height_reproject_reasons", []) if height_row else [],
        )
        ranked.append(
            (
                sort_key,
                {
                    "rank": 0,
                    "pair_index": pair_index,
                    "review_priority": review_priority,
                    "primary_action": primary_action,
                    "assist_status": proposal.get("assist_status"),
                    "height_reproject_status": (
                        height_row.get("height_reproject_status") if height_row else None
                    ),
                    "vertical_x_residual": proposal.get("vertical_x_residual"),
                    "height_residual": proposal.get("height_residual"),
                    "max_abs_delta": proposal.get("max_abs_delta"),
                    "reason": reason,
                    "manual_only": manual_only,
                },
            )
        )
    output = [row for _, row in sorted(ranked, key=lambda item: item[0])]
    for rank, row in enumerate(output, start=1):
        row["rank"] = rank
    return output


def _summary(
    *,
    input_mode: str,
    ordered_pairs: Sequence[Mapping[str, Any]],
    preview_compatibility: Mapping[str, Any],
    align_pair_x_proposals: Sequence[Mapping[str, Any]],
    height_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "input_mode": input_mode,
        "preview_status": preview_compatibility.get("status"),
        "n_ordered_pairs": len(ordered_pairs),
        "n_align_pair_x_eligible": sum(
            1 for row in align_pair_x_proposals if row.get("assist_status") == ELIGIBLE
        ),
        "n_align_pair_x_review_only": sum(
            1 for row in align_pair_x_proposals if row.get("assist_status") == "review_only"
        ),
        "n_align_pair_x_suppressed": sum(
            1 for row in align_pair_x_proposals if row.get("assist_status") == "suppress"
        ),
        "n_height_reproject_applicable": sum(
            1 for row in height_rows if row.get("height_reproject_applicable") is True
        ),
        "n_height_reproject_review_only": sum(
            1 for row in height_rows if row.get("height_reproject_status") == "review_only"
        ),
        "n_height_reproject_suppressed": sum(
            1 for row in height_rows if row.get("height_reproject_status") == "suppress"
        ),
        "note": NO_WRITEBACK_NOTE,
    }


def build_single_image_assist(payload: Mapping[str, Any]) -> dict[str, Any]:
    (
        input_mode,
        preview_compatibility,
        ordered_pairs,
        topology_override,
        default_preview_centers,
        preview_pair_table,
        near_duplicate_pair_table,
    ) = _resolve_ordered_pairs(payload)
    (
        duplicate_diagnostics,
        default_order_diagnostics,
        effective_order_diagnostics,
    ) = _diagnostics_from_payload(
        ordered_pairs,
        topology_override=topology_override,
        default_centers=default_preview_centers,
    )
    # Backward-compatible alias: downstream M15.11/M15.12 readers used
    # order_diagnostics before default/effective order diagnostics were split.
    # Remove only after all sidecar consumers read effective_order_diagnostics.
    order_diagnostics = effective_order_diagnostics
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), Mapping) else None
    task_id = payload.get("task_id")
    annotation_id = payload.get("annotation_id")
    override_pack = _override_pack(
        preview_info=preview_compatibility,
        topology_override=topology_override,
    )

    invalid_override = topology_override.get("override_status") == "invalid_preview_order_override"
    override_not_allowed = (
        topology_override.get("override_status")
        == "preview_order_override_not_allowed_for_status"
    )
    if (
        invalid_override
        or override_not_allowed
        or (
            preview_compatibility["status"] != COMPATIBLE
            and input_mode != "simplified_ordered_pairs"
            and not topology_override.get("preview_order_override_active")
        )
    ):
        return {
            "task_id": task_id,
            "annotation_id": annotation_id,
            "target_pair_indices": payload.get("target_pair_indices"),
            "input_mode": input_mode,
            "preview_compatibility": preview_compatibility,
            "effective_preview_compatibility": {
                "status": (
                    "invalid_preview_order_override"
                    if invalid_override
                    else "preview_order_override_not_allowed_for_status"
                    if override_not_allowed
                    else "not_compatible"
                ),
                "reason": topology_override.get("invalid_reason")
                or preview_compatibility.get("compatibility_reason"),
            },
            "topology_override": topology_override,
            # Convenience mirrors for older JSON readers; topology_override is
            # the canonical nested provenance object.
            "preview_order_override_active": topology_override["preview_order_override_active"],
            "topology_source": topology_override["topology_source"],
            "default_preview_status": topology_override["default_preview_status"],
            "default_preview_reason": topology_override["default_preview_reason"],
            "ordered_pairs": [],
            "room_layout_state": None,
            "pair_diagnostics": [],
            "align_pair_x_proposals": [],
            "height_reproject_applicability_rows": [],
            "height_reproject_candidate_rows": [],
            "verified_3d_local_assist": None,
            "pair_index_mapping": [],
            "preview_pair_table": preview_pair_table,
            "near_duplicate_pair_table": near_duplicate_pair_table,
            "override_pack": override_pack,
            "duplicate_diagnostics": duplicate_diagnostics,
            "default_order_diagnostics": default_order_diagnostics,
            "effective_order_diagnostics": effective_order_diagnostics,
            "order_diagnostics": order_diagnostics,
            "recommended_review_order": [],
            "manual_edit_table": [],
            "summary": _summary(
                input_mode=input_mode,
                ordered_pairs=[],
                preview_compatibility=preview_compatibility,
                align_pair_x_proposals=[],
                height_rows=[],
            ),
            "tool_version": TOOL_VERSION,
        }

    room_layout_state = build_room_layout_state(ordered_pairs, metadata=metadata)
    pair_diagnostics = list(room_layout_state.get("pair_diagnostics", []))
    proposals = [
        _proposal_row(ordered_pairs, pair_index, metadata)
        for pair_index in _pair_indices(ordered_pairs)
    ]
    height_rows = build_pair_assist_review_rows(
        [
            {
                "task_id": task_id,
                "annotation_id": annotation_id,
                "target_pair_index": pair_index,
                "ordered_pairs": ordered_pairs,
                "metadata": metadata,
            }
            for pair_index in _pair_indices(ordered_pairs)
        ],
        operation=HEIGHT_REPROJECT_APPLICABILITY_OPERATION,
    )
    height_candidate_rows = build_height_reproject_candidate_rows(
        ordered_pairs,
        metadata=metadata,
        target_pair_indices=payload.get("height_target_pair_indices"),
    )
    manual_only_reasons: dict[int, str] = {}
    for diagnostic in duplicate_diagnostics:
        reason = diagnostic["reason"]
        manual_only_reasons[int(diagnostic["left_pair_index"])] = reason
        manual_only_reasons[int(diagnostic["right_pair_index"])] = reason
    if not topology_override.get("preview_order_override_active"):
        for change in order_diagnostics.get("direction_change_pairs", []):
            if change.get("manual_only") is not True:
                continue
            for key in ("left_pair_index", "middle_pair_index", "right_pair_index"):
                manual_only_reasons.setdefault(int(change[key]), "local_order_zigzag")
    recommended = [
        *_recommended_review_order(proposals, height_rows, manual_only_reasons),
    ]
    manual_edit_table = [
        _manual_edit_row(
            ordered_pairs[int(row["pair_index"]) - 1],
            row,
            manual_only_reasons.get(int(row["pair_index"])),
        )
        for row in proposals
    ]
    pair_index_mapping = _pair_index_mapping(ordered_pairs, topology_override)
    verified_3d_local_assist = build_verified_3d_local_assist(
        ordered_pairs,
        metadata=metadata,
        topology_override=topology_override,
        target_pair_indices=payload.get("target_pair_indices"),
        pair_index_mapping=pair_index_mapping,
    )

    return {
        "task_id": task_id,
        "annotation_id": annotation_id,
        "target_pair_indices": payload.get("target_pair_indices"),
        "input_mode": input_mode,
        "preview_compatibility": preview_compatibility,
        "effective_preview_compatibility": {
            "status": "compatible_with_expert_verified_order"
            if topology_override.get("preview_order_override_active")
            else preview_compatibility.get("status"),
            "reason": topology_override.get("override_status")
            if topology_override.get("preview_order_override_active")
            else preview_compatibility.get("compatibility_reason"),
        },
        "topology_override": topology_override,
        # Convenience mirrors for older JSON readers; topology_override is the
        # canonical nested provenance object.
        "preview_order_override_active": topology_override["preview_order_override_active"],
        "topology_source": topology_override["topology_source"],
        "default_preview_status": topology_override["default_preview_status"],
        "default_preview_reason": topology_override["default_preview_reason"],
        "ordered_pairs": ordered_pairs,
        "room_layout_state": room_layout_state,
        "pair_diagnostics": pair_diagnostics,
        "align_pair_x_proposals": proposals,
        "height_reproject_applicability_rows": height_rows,
        "height_reproject_candidate_rows": height_candidate_rows,
        "verified_3d_local_assist": verified_3d_local_assist,
        "pair_index_mapping": pair_index_mapping,
        "preview_pair_table": preview_pair_table,
        "near_duplicate_pair_table": near_duplicate_pair_table,
        "override_pack": override_pack,
        "duplicate_diagnostics": duplicate_diagnostics,
        "default_order_diagnostics": default_order_diagnostics,
        "effective_order_diagnostics": effective_order_diagnostics,
        "order_diagnostics": order_diagnostics,
        "recommended_review_order": recommended,
        "manual_edit_table": manual_edit_table,
        "summary": _summary(
            input_mode=input_mode,
            ordered_pairs=ordered_pairs,
            preview_compatibility=preview_compatibility,
            align_pair_x_proposals=proposals,
            height_rows=height_rows,
        ),
        "tool_version": TOOL_VERSION,
}


def _format_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def _markdown_table(headers: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_format_cell(row.get(header)) for header in headers) + " |")
    return lines


def render_markdown_report(payload: Mapping[str, Any]) -> str:
    preview = payload.get("preview_compatibility", {})
    topology = payload.get("topology_override", {})
    summary = payload.get("summary", {})
    lines = [
        "# Single-image Manhattan Assist Report",
        "",
        NO_WRITEBACK_NOTE,
        (
            "Legacy Manual Edit Table only covers align_pair_x. Verified 3D Local "
            "Assist and Conservative Height Reproject rows are review-level "
            "dry-runs, not edit instructions. Do not apply without visual confirmation."
        ),
        "",
        "## Preview Compatibility",
        "",
        f"- status: `{preview.get('status')}`",
        f"- input_mode: `{payload.get('input_mode')}`",
        f"- reason: `{preview.get('compatibility_reason')}`",
        f"- preserve_order: `{preview.get('preserve_order')}`",
        "",
        "## Preview Pair Table",
        "",
    ]
    lines.extend(
        _markdown_table(
            [
                "preview_pair_index",
                "top_id",
                "bottom_id",
                "top_x",
                "bottom_x",
                "center_x",
                "top_y",
                "bottom_y",
                "pairing_source",
            ],
            payload.get("preview_pair_table", []),
        )
    )
    lines.extend(["", "## Near Duplicate Pair Table", ""])
    lines.extend(
        _markdown_table(
            [
                "left_preview_pair_index",
                "right_preview_pair_index",
                "left_center_x",
                "right_center_x",
                "delta_center_x",
                "duplicate_threshold_percent",
                "reason",
                "manual_override_required",
            ],
            payload.get("near_duplicate_pair_table", []),
        )
    )
    lines.extend(
        [
            "",
            "## Override Pack",
            "",
            (
                "Override pack only helps expert prepare a verified order; it is "
                "not automatic reorder."
            ),
            "",
        ]
    )
    lines.extend(
        _markdown_table(
            [
                "override_needed",
                "hard_stop_reason",
                "default_n_pairs",
                "default_preview_status",
                "default_preview_reason",
                "accepted_override_formats",
                "example_preview_order_override",
                "override_validation_status",
                "override_validation_reasons",
                "writeback_allowed",
            ],
            [payload.get("override_pack", {})],
        )
    )
    lines.extend(
        [
            "",
            "## Topology Override",
            "",
        ]
    )
    lines.extend(
        _markdown_table(
            [
                "preview_order_override_active",
                "topology_source",
                "default_preview_status",
                "default_preview_reason",
                "preview_order_override",
                "order_override_note",
                "override_validation_status",
                "override_validation_reasons",
            ],
            [
                {
                    "preview_order_override_active": topology.get(
                        "preview_order_override_active"
                    ),
                    "topology_source": topology.get("topology_source"),
                    "default_preview_status": topology.get("default_preview_status"),
                    "default_preview_reason": topology.get("default_preview_reason"),
                    "preview_order_override": topology.get("preview_order_override"),
                    "order_override_note": topology.get("order_override_note"),
                    "override_validation_status": topology.get(
                        "override_validation_status"
                    ),
                    "override_validation_reasons": topology.get(
                        "override_validation_reasons"
                    ),
                }
            ],
        )
    )
    lines.extend(
        [
            "",
            "## Pair Index Mapping",
            "",
            (
                "Report `pair_index` values refer to the effective ordered_pairs position. "
                "`source_preview_order_index` is the original default preview pair number. "
                "Candidate `target_pair_indices` use `effective_pair_index`."
            ),
            "",
        ]
    )
    lines.extend(
        _markdown_table(
            [
                "effective_pair_index",
                "source_preview_order_index",
                "top_x",
                "bottom_x",
                "center_x",
                "top_y",
                "bottom_y",
            ],
            payload.get("pair_index_mapping", []),
        )
    )
    lines.extend(
        [
            "",
            "## Pair Diagnostics",
            "",
        ]
    )
    lines.extend(
        _markdown_table(
            [
                "pair_index",
                "vertical_x_residual",
                "height_residual",
                "top_bottom_delta_y",
                "warnings",
            ],
            payload.get("pair_diagnostics", []),
        )
    )
    lines.extend(["", "## Recommended Review Order", ""])
    lines.extend(
        _markdown_table(
            [
                "rank",
                "pair_index",
                "review_priority",
                "primary_action",
                "assist_status",
                "height_reproject_status",
                "vertical_x_residual",
                "height_residual",
                "max_abs_delta",
                "reason",
                "manual_only",
            ],
            payload.get("recommended_review_order", []),
        )
    )
    lines.extend(["", "## Manual Edit Table", ""])
    lines.extend(
        _markdown_table(
            [
                "pair_index",
                "action",
                "from_top_x",
                "to_top_x",
                "from_bottom_x",
                "to_bottom_x",
                "top_dx",
                "bottom_dx",
                "y_change_allowed",
                "reason",
            ],
            payload.get("manual_edit_table", []),
        )
    )
    lines.extend(["", "## Duplicate / Dense Corner Diagnostics", ""])
    lines.extend(
        _markdown_table(
            [
                "left_pair_index",
                "right_pair_index",
                "left_center_x",
                "right_center_x",
                "delta_center_x",
                "duplicate_threshold_percent",
                "reason",
                "manual_only",
                "index_source",
            ],
            payload.get("duplicate_diagnostics", []),
        )
    )
    order_diagnostics = payload.get("order_diagnostics") or {}
    lines.extend(["", "## Order Diagnostics", ""])
    lines.extend(
        _markdown_table(
            [
                "is_x_monotonic",
                "n_direction_changes",
                "direction_change_pairs",
                "manual_only_reason",
            ],
            [order_diagnostics],
        )
    )
    lines.extend(["", "## Height Applicability Summary", ""])
    lines.extend(
        [
            f"- applicable: `{summary.get('n_height_reproject_applicable')}`",
            f"- review_only: `{summary.get('n_height_reproject_review_only')}`",
            f"- suppressed: `{summary.get('n_height_reproject_suppressed')}`",
            "",
        ]
    )
    lines.extend(["## Conservative Height Reproject Candidates", ""])
    lines.extend(
        _markdown_table(
            [
                "candidate_rank",
                "target_pair_index",
                "operation",
                "top_y_before",
                "top_y_after",
                "top_y_delta",
                "height_residual_before",
                "height_residual_after",
                "height_residual_delta",
                "candidate_decision",
                "gate_reasons",
                "writeback_allowed",
            ],
            payload.get("height_reproject_candidate_rows", []),
        )
    )
    lines.append("")
    verified_local = payload.get("verified_3d_local_assist") or {}
    lines.extend(["## Verified 3D Local Assist", ""])
    lines.extend(
        [
            f"- schema_version: `{verified_local.get('schema_version')}`",
            f"- operation_family: `{verified_local.get('operation_family')}`",
            f"- state_status: `{verified_local.get('state_status')}`",
            f"- writeback_allowed: `{verified_local.get('writeback_allowed')}`",
            "- These candidates are review-level dry-runs, not edit instructions.",
            "- Use them to inspect directionality; do not apply without visual confirmation.",
            (
                "- Existing x-only rows leave y unchanged; M15.18 changes bottom-y "
                "only inside sensitivity/hypothesis dry-runs."
            ),
            "",
            "### Dense Corner Reclassification",
            "",
        ]
    )
    lines.extend(
        _markdown_table(
            [
                "left_pair_index",
                "right_pair_index",
                "delta_center_x",
                "bev_distance",
                "floor_distance_delta",
                "min_adjacent_wall_length",
                "classification",
                "reason_tokens",
            ],
            verified_local.get("dense_corner_reclassification", []),
        )
    )
    lines.extend(["", "### Pair Index Mapping", ""])
    lines.extend(
        [
            (
                "See the global Pair Index Mapping table above. Inside verified 3D "
                "local assist, candidate `target_pair_indices` refer to "
                "`effective_pair_index`; source preview order is provenance only."
            ),
            "",
        ]
    )
    lines.extend(["", "### Wall Angle Diagnostics", ""])
    lines.extend(
        _markdown_table(
            [
                "wall_index",
                "from_pair_index",
                "to_pair_index",
                "from_source_preview_order_index",
                "to_source_preview_order_index",
                "direction_deg",
                "nearest_manhattan_axis_deg",
                "angle_residual_deg",
                "length",
            ],
            verified_local.get("wall_angle_table", []),
        )
    )
    lines.extend(["", "### Corner Angle Diagnostics", ""])
    lines.extend(
        [
            (
                "`turn_angle_deg` is the BEV angle between the previous and next wall "
                "vectors at the current corner; residual is measured from 90 degrees."
            ),
            "",
        ]
    )
    lines.extend(
        _markdown_table(
            [
                "corner_pair_index",
                "corner_source_preview_order_index",
                "prev_wall_index",
                "next_wall_index",
                "turn_angle_deg",
                "angle_to_90_residual_deg",
                "local_angle_warning",
            ],
            verified_local.get("corner_angle_table", []),
        )
    )
    lines.extend(["", "### Local X Translation Dry-run Candidates", ""])
    lines.extend(
        [
            "2D x-order crossing is not topology reordering.",
            (
                "Explicit target pair mode is an exploratory x-only dry-run; it "
                "does not claim to solve y/height residuals."
                if payload.get("target_pair_indices")
                else ""
            ),
            "",
        ]
    )
    lines.extend(
        _markdown_table(
            [
                "candidate_rank",
                "candidate_id",
                "candidate_family",
                "operation",
                "target_pair_indices",
                "dx",
                "status",
                "local_geometry_score_delta",
                "wall_angle_residual_sum_delta_deg",
                "wall_angle_residual_max_delta_deg",
                "affected_wall_indices",
                "affected_corner_indices",
                "x_order_crossing_after_translation",
                "crossed_pair_indices",
                "crossing_scope",
                "candidate_decision",
                "decision_reasons",
                "improved_metrics",
                "risk_reasons",
                "y_change_allowed",
                "writeback_allowed",
            ],
            verified_local.get("candidate_rows", []),
        )
    )
    lines.extend(["", "### Adaptive Local X Search", ""])
    lines.extend(
        [
            "Adaptive search is a review-level bounded dry-run, not an edit instruction.",
            (
                "A flat region means the exact dx is not reliable; use it only "
                "as directionality."
            ),
            "Y coordinates remain unchanged.",
            "",
        ]
    )
    lines.extend(
        _markdown_table(
            [
                "search_rank",
                "search_family",
                "target_pair_indices",
                "best_dx",
                "score_delta",
                "confidence_label",
                "flat_score_region",
                "x_order_crossing_at_best",
                "decision_reasons",
                "y_change_allowed",
                "writeback_allowed",
            ],
            verified_local.get("adaptive_x_search_rows", []),
        )
    )
    lines.extend(["", "### Floor-Footprint Sensitivity", ""])
    lines.extend(
        [
            (
                "- schema_version: "
                f"`{verified_local.get('floorprint_sensitivity_schema_version')}`"
            ),
            "- writeback_allowed: `false`",
            "- expert_action_allowed: `false`",
            "- annotation_patch_allowed: `false`",
            (
                "Bottom-y changes alter the floor footprint and may change BEV "
                "wall/corner angles."
            ),
            "This is sensitivity analysis only, not an edit instruction.",
            "",
        ]
    )
    lines.extend(
        _markdown_table(
            [
                "target_pair_index",
                "bottom_y_delta",
                "wall_angle_residual_sum_delta",
                "corner_angle_residual_sum_delta",
                "height_residual_delta",
                "state_status_after",
                "x_order_crossing_after_translation",
                "decision_label",
                "decision_reasons",
                "writeback_allowed",
                "expert_action_allowed",
                "annotation_patch_allowed",
            ],
            verified_local.get("floorprint_sensitivity_rows", []),
        )
    )
    lines.extend(["", "### Local Dense-Corner Hypothesis Probe", ""])
    lines.extend(
        [
            (
                "- schema_version: "
                f"`{verified_local.get('local_dense_corner_probe_schema_version')}`"
            ),
            "- writeback_allowed: `false`",
            "- expert_action_allowed: `false`",
            "- annotation_patch_allowed: `false`",
            "Only triggered for unresolved dense corners.",
            "Hypotheses are local dry-runs.",
            "Topology variants are not automatic reorder.",
            (
                "Bottom-only hypothesis rows are sensitivity-only and must not be "
                "used to edit Label Studio points."
            ),
            (
                "Directional rows must be column-constrained: top_x and bottom_x "
                "move together and the dense-separation gate must pass."
            ),
            "No writeback / no patch.",
            "",
        ]
    )
    lines.extend(
        _markdown_table(
            [
                "hypothesis_id",
                "topology_variant",
                "probe_mode",
                "local_window_pair_indices",
                "bottom_xy_offsets",
                "column_xy_offsets",
                "local_geometry_score_delta",
                "wall_angle_residual_sum_delta",
                "corner_angle_residual_sum_delta",
                "confidence_label",
                "pair_vertical_x_consistent",
                "dense_pair_center_x_separation_before",
                "dense_pair_center_x_separation_after",
                "minimum_dense_pair_center_x_separation",
                "dense_pair_bev_separation_before",
                "dense_pair_bev_separation_after",
                "minimum_dense_pair_bev_separation",
                "dense_separation_gate_passed",
                "recommendation_eligible",
                "decision_reasons",
                "risk_reasons",
                "writeback_allowed",
                "expert_action_allowed",
                "annotation_patch_allowed",
            ],
            verified_local.get("local_dense_corner_probe_rows", []),
        )
    )
    return "\n".join(lines) + "\n"


def run_single_image_assist(
    input_path: Path,
    output_path: Path | None = None,
    *,
    markdown_output: Path | None = None,
    pretty: bool = False,
) -> dict[str, Any]:
    payload = build_single_image_assist(_load_json(input_path))
    text = json.dumps(payload, indent=2 if pretty else None, sort_keys=pretty)
    if output_path is None:
        print(text)
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text + "\n", encoding="utf-8")
    if markdown_output is not None:
        markdown_output.parent.mkdir(parents=True, exist_ok=True)
        markdown_output.write_text(render_markdown_report(payload), encoding="utf-8")
    return payload


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run single-image expert-side Manhattan assist diagnostics.",
    )
    parser.add_argument("--input", required=True, type=Path, help="Single-image input JSON.")
    parser.add_argument("--output", type=Path, help="Optional output JSON sidecar path.")
    parser.add_argument("--markdown-output", type=Path, help="Optional Markdown report path.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    run_single_image_assist(
        args.input,
        args.output,
        markdown_output=args.markdown_output,
        pretty=args.pretty,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
