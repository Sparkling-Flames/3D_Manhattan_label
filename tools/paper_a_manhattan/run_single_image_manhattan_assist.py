"""Single-image expert-side Manhattan assist CLI.

This is an offline M15.x diagnostic entrypoint. It reads one image annotation,
checks preview compatibility when raw keypoints are supplied, builds
RoomLayoutState diagnostics, proposes low-risk Align Pair X review prompts, and
reports height reproject applicability. It does not implement UI, ghost
overlays, apply/undo/writeback, true height reproject candidates, routing, or
formal artifacts.
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
from tools.paper_a_manhattan.manhattan_pair_assist import (  # noqa: E402
    ELIGIBLE,
    diagnose_pair_alignment,
    propose_align_pair_x,
)
from tools.paper_a_manhattan.manhattan_preview_compat import (  # noqa: E402
    COMPATIBLE,
    check_preview_compatibility,
)


TOOL_VERSION = "single_image_manhattan_assist_m15_11_v1"
NO_WRITEBACK_NOTE = (
    "Expert-side diagnostic only: no UI, no apply/writeback, no routing, "
    "no formal g_t, no worker quality metric, no P1/C1/C2/T1/V1 artifact."
)


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


def _preview_summary(preview: Any | None, *, input_mode: str) -> dict[str, Any]:
    if preview is None:
        return {
            "status": "not_run_simplified_ordered_pairs",
            "input_mode": input_mode,
            "n_pairs": None,
            "n_unpaired_points": None,
            "suggestion_allowed": True,
            "compatibility_reason": "ordered_pairs_input_bypasses_preview_parser",
            "pairing_rule_version": None,
        }
    return {
        "status": preview.status,
        "input_mode": input_mode,
        "n_pairs": len(preview.ordered_corners),
        "n_unpaired_points": len(preview.unpaired_points),
        "suggestion_allowed": preview.suggestion_allowed,
        "compatibility_reason": preview.compatibility_reason,
        "pairing_rule_version": preview.pairing_rule_version,
    }


def _resolve_ordered_pairs(payload: Mapping[str, Any]) -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
    if isinstance(payload.get("ordered_pairs"), list):
        return (
            "simplified_ordered_pairs",
            _preview_summary(None, input_mode="simplified_ordered_pairs"),
            list(payload["ordered_pairs"]),
        )

    raw_keypoints = payload.get("keypoints", payload.get("raw_keypoints"))
    if not isinstance(raw_keypoints, list):
        raise ValueError("input must include ordered_pairs, keypoints, or raw_keypoints")

    preview = check_preview_compatibility(raw_keypoints)
    preview_info = _preview_summary(preview, input_mode="raw_keypoints")
    if preview.status != COMPATIBLE:
        return "raw_keypoints", preview_info, []
    ordered_pairs = [_preview_pair_to_ordered_pair(pair) for pair in preview.ordered_corners]
    return "raw_keypoints", preview_info, ordered_pairs


def _pair_indices(ordered_pairs: Sequence[Mapping[str, Any]]) -> list[int]:
    return list(range(1, len(ordered_pairs) + 1))


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


def _manual_edit_row(pair: Mapping[str, Any], proposal: Mapping[str, Any]) -> dict[str, Any]:
    pair_index = proposal["pair_index"]
    top = pair["top"]
    bottom = pair["bottom"]
    eligible = proposal.get("assist_status") == ELIGIBLE
    row = {
        "pair_index": pair_index,
        "action": "align_pair_x" if eligible else "review_only_no_x_suggestion",
        "from_top_x": top["x"],
        "from_bottom_x": bottom["x"],
        "top_dx": proposal.get("top_dx"),
        "bottom_dx": proposal.get("bottom_dx"),
        "y_change_allowed": False,
        "notes": (
            "Manual expert may align top.x and bottom.x only; keep y unchanged."
            if eligible
            else "; ".join(proposal.get("assist_reasons", []))
        ),
    }
    if eligible:
        row["to_top_x"] = proposal.get("suggested_top_x")
        row["to_bottom_x"] = proposal.get("suggested_bottom_x")
    return row


def _review_sort_key(proposal: Mapping[str, Any]) -> tuple[float, float]:
    status_priority = {
        ELIGIBLE: 0.0,
        "review_only": 1.0,
        "suppress": 2.0,
    }.get(str(proposal.get("assist_status")), 3.0)
    residual = proposal.get("vertical_x_residual")
    if not isinstance(residual, (int, float)):
        residual = -1.0
    return (status_priority, -float(residual))


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
    input_mode, preview_compatibility, ordered_pairs = _resolve_ordered_pairs(payload)
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), Mapping) else None
    task_id = payload.get("task_id")
    annotation_id = payload.get("annotation_id")

    if preview_compatibility["status"] != COMPATIBLE and input_mode == "raw_keypoints":
        return {
            "task_id": task_id,
            "annotation_id": annotation_id,
            "input_mode": input_mode,
            "preview_compatibility": preview_compatibility,
            "ordered_pairs": [],
            "room_layout_state": None,
            "pair_diagnostics": [],
            "align_pair_x_proposals": [],
            "height_reproject_applicability_rows": [],
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
    recommended = [
        row["pair_index"]
        for row in sorted(proposals, key=_review_sort_key)
    ]
    manual_edit_table = [
        _manual_edit_row(ordered_pairs[int(row["pair_index"]) - 1], row)
        for row in proposals
    ]

    return {
        "task_id": task_id,
        "annotation_id": annotation_id,
        "input_mode": input_mode,
        "preview_compatibility": preview_compatibility,
        "ordered_pairs": ordered_pairs,
        "room_layout_state": room_layout_state,
        "pair_diagnostics": pair_diagnostics,
        "align_pair_x_proposals": proposals,
        "height_reproject_applicability_rows": height_rows,
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


def run_single_image_assist(
    input_path: Path,
    output_path: Path | None = None,
    *,
    pretty: bool = False,
) -> dict[str, Any]:
    payload = build_single_image_assist(_load_json(input_path))
    text = json.dumps(payload, indent=2 if pretty else None, sort_keys=pretty)
    if output_path is None:
        print(text)
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text + "\n", encoding="utf-8")
    return payload


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run single-image expert-side Manhattan assist diagnostics.",
    )
    parser.add_argument("--input", required=True, type=Path, help="Single-image input JSON.")
    parser.add_argument("--output", type=Path, help="Optional output JSON sidecar path.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    run_single_image_assist(args.input, args.output, pretty=args.pretty)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
