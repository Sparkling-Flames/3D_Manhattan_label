"""M-Anchor.4 staged footprint-then-height review candidates for task218_ann3741.

The runner uses the user's expanded source-pair permission set. It first
optimizes footprint wall direction with x/bottom_y only, then keeps that
footprint fixed and adjusts top_y for height consistency. It is review-only.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.paper_a_manhattan.manhattan_3d_projection import (
    DEFAULT_CAMERA_HEIGHT,
    floor_point_to_layout_pair,
    project_layout_to_3d,
)
from tools.paper_a_manhattan.run_local_3d_projection_review import run_local_review
from tools.paper_a_manhattan.run_m_anchor_1_3741 import SAFETY, _geometry, _load, _sha, _write_text_lf
from tools.paper_a_manhattan.run_m_anchor_3_footprint_solver import M1_AUDIT_PATH, M2_VERDICT_PATH


OUT_DIR = Path("analysis_results/paper_a_manhattan/m_anchor/task218_ann3741_m_anchor_4")
REVIEW_OUT_DIR = Path(
    "analysis_results/paper_a_manhattan/hypothesis_local_review/task218_ann3741_m_anchor_4"
)
DEFAULT_IMAGE_ROOT = Path("data/mp3d_layout/img_v")
ALLOWED_SOURCE_PAIR_IDS = (1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 12)
PROTECTED_SOURCE_PAIR_IDS = (3,)
X_STEPS = (-0.3, -0.2, -0.1, 0.1, 0.2, 0.3)
BOTTOM_Y_STEPS = (-1.0, -0.5, -0.25, 0.25, 0.5, 1.0)
MAX_ABS_X_DELTA = 0.8
MAX_ABS_BOTTOM_Y_DELTA = 1.5
MAX_ABS_TOP_Y_DELTA = 3.0
MAX_ITERS = 30
TOP_K = 5
MIN_WALL_LENGTH = 0.15
MODES = (
    ("max_first", ("x", "bottom_y")),
    ("sum_first", ("x", "bottom_y")),
    ("turn_aware", ("x", "bottom_y")),
    ("bottom_only", ("bottom_y",)),
)


def _local_server_root(out_dir: Path) -> Path | None:
    try:
        out_dir.resolve().relative_to(REPO_ROOT.resolve())
    except ValueError:
        return None
    return REPO_ROOT


def _by_source(rows: Sequence[Mapping[str, Any]]) -> dict[int, Mapping[str, Any]]:
    return {int(row["source_pair_id"]): row for row in rows}


def _metrics(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    geometry = _geometry(rows)
    floor = geometry["floorprint"]["summary"]
    turns = geometry["corner_turns"]["summary"]
    heights = geometry["heights"]["summary"]
    return {
        "wall_residual_sum": floor["wall_residual_sum_deg"],
        "wall_residual_max": floor["wall_residual_max_deg"],
        "turn_residual_max": turns["corner_residual_max_deg"],
        "height_l1": heights["height_residual_sum"],
        "height_max": heights["height_residual_max"],
        "height_median": heights["median_wall_height"],
        "min_wall_length": floor["minimum_wall_length"],
        "short_wall_count": floor["short_wall_count"],
        "self_intersection": floor["self_intersection"],
        "vertical_x_residual_sum": sum(
            abs(float(row["top"]["x"]) - float(row["bottom"]["x"])) for row in rows
        ),
    }


def _valid(rows: Sequence[Mapping[str, Any]]) -> bool:
    for row in rows:
        top = row["top"]
        bottom = row["bottom"]
        if not (0.0 <= top["x"] <= 100.0 and 0.0 <= bottom["x"] <= 100.0):
            return False
        if not (0.0 < top["y"] < bottom["y"] < 99.0):
            return False
    metrics = _metrics(rows)
    return (not metrics["self_intersection"]) and metrics["min_wall_length"] >= MIN_WALL_LENGTH


def _movement_cost(deltas: Mapping[int, Mapping[str, float]]) -> float:
    return sum(
        abs(row.get("bottom_y", 0.0))
        + 3.0 * abs(row.get("x", 0.0))
        + 0.25 * abs(row.get("top_y", 0.0))
        for row in deltas.values()
    )


def _objective(metrics: Mapping[str, Any], mode: str, movement: float) -> tuple[float, ...]:
    if mode == "sum_first":
        return (
            metrics["wall_residual_sum"],
            metrics["wall_residual_max"],
            metrics["turn_residual_max"],
            movement,
        )
    if mode == "turn_aware":
        return (
            metrics["wall_residual_max"],
            metrics["turn_residual_max"],
            metrics["wall_residual_sum"],
            movement,
        )
    return (
        metrics["wall_residual_max"],
        metrics["wall_residual_sum"],
        metrics["turn_residual_max"],
        movement,
    )


def _apply_step(rows: Sequence[Mapping[str, Any]], source_pair_id: int, axis: str, step: float) -> list[dict[str, Any]]:
    out = copy.deepcopy(list(rows))
    for row in out:
        if int(row["source_pair_id"]) != source_pair_id:
            continue
        if axis == "x":
            row["top"]["x"] = float(row["top"]["x"]) + step
            row["bottom"]["x"] = float(row["bottom"]["x"]) + step
        elif axis == "bottom_y":
            row["bottom"]["y"] = float(row["bottom"]["y"]) + step
        else:
            raise ValueError(f"unsupported footprint axis: {axis}")
    return out


def _greedy_footprint(
    baseline_rows: Sequence[Mapping[str, Any]], mode: str, axes: Sequence[str]
) -> tuple[list[dict[str, Any]], dict[int, dict[str, float]], list[dict[str, Any]]]:
    rows = copy.deepcopy(list(baseline_rows))
    deltas = {
        sid: {"x": 0.0, "bottom_y": 0.0, "top_y": 0.0} for sid in ALLOWED_SOURCE_PAIR_IDS
    }
    trace: list[dict[str, Any]] = []
    current_metrics = _metrics(rows)
    current_key = _objective(current_metrics, mode, _movement_cost(deltas))
    for _ in range(MAX_ITERS):
        best: tuple[tuple[float, ...], dict[str, Any], list[dict[str, Any]], dict[int, dict[str, float]], tuple[int, str, float]] | None = None
        for sid in ALLOWED_SOURCE_PAIR_IDS:
            for axis in axes:
                steps = X_STEPS if axis == "x" else BOTTOM_Y_STEPS
                limit = MAX_ABS_X_DELTA if axis == "x" else MAX_ABS_BOTTOM_Y_DELTA
                for step in steps:
                    if abs(deltas[sid][axis] + step) > limit + 1e-9:
                        continue
                    trial = _apply_step(rows, sid, axis, step)
                    if not _valid(trial):
                        continue
                    trial_deltas = copy.deepcopy(deltas)
                    trial_deltas[sid][axis] += step
                    trial_metrics = _metrics(trial)
                    key = _objective(trial_metrics, mode, _movement_cost(trial_deltas))
                    if best is None or key < best[0]:
                        best = (key, trial_metrics, trial, trial_deltas, (sid, axis, step))
        if best is None or best[0] >= current_key:
            break
        current_key, current_metrics, rows, deltas, move = best
        trace.append(
            {
                "source_pair_id": move[0],
                "axis": move[1],
                "step": move[2],
                "metrics_after": current_metrics,
            }
        )
    return rows, deltas, trace


def _height_adjust(
    footprint_rows: Sequence[Mapping[str, Any]], deltas: dict[int, dict[str, float]]
) -> tuple[list[dict[str, Any]], float, dict[int, float]]:
    rows = copy.deepcopy(list(footprint_rows))
    projection = project_layout_to_3d(rows, 1024, 512, "ls_percent", DEFAULT_CAMERA_HEIGHT)
    target_height = statistics.median(float(pair["wall_height"]) for pair in projection["pairs"])
    top_y_delta_by_source: dict[int, float] = {}
    for row, projected in zip(rows, projection["pairs"]):
        sid = int(row["source_pair_id"])
        if sid not in ALLOWED_SOURCE_PAIR_IDS:
            continue
        inverse = floor_point_to_layout_pair(
            float(projected["floor_3d"]["x"]),
            float(projected["floor_3d"]["z"]),
            layout_height=target_height,
            camera_height=DEFAULT_CAMERA_HEIGHT,
        )
        before = float(row["top"]["y"])
        raw_delta = float(inverse["top"]["y"]) - before
        delta = max(-MAX_ABS_TOP_Y_DELTA, min(MAX_ABS_TOP_Y_DELTA, raw_delta))
        row["top"]["y"] = before + delta
        if abs(delta) > 1e-9:
            deltas[sid]["top_y"] += delta
            top_y_delta_by_source[sid] = delta
    return rows, target_height, top_y_delta_by_source


def _coordinate_changes(
    before_rows: Sequence[Mapping[str, Any]], after_rows: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    before = _by_source(before_rows)
    changes: list[dict[str, Any]] = []
    for after in after_rows:
        sid = int(after["source_pair_id"])
        old = before[sid]
        fields = {}
        for endpoint, prefix in (("top", "top"), ("bottom", "bottom")):
            for axis in ("x", "y"):
                before_value = float(old[endpoint][axis])
                after_value = float(after[endpoint][axis])
                if abs(after_value - before_value) > 1e-9:
                    fields[f"{prefix}_{axis}"] = {
                        "before": before_value,
                        "after": after_value,
                        "delta": after_value - before_value,
                        "changed": True,
                    }
        if fields:
            changes.append(
                {
                    "source_pair_id": sid,
                    "solver_position": after.get("solver_position", after["effective_pair_index"]),
                    "verified_order_source_id": after.get("verified_order_source_id", sid),
                    "effective_pair_index": after["effective_pair_index"],
                    "fields": fields,
                }
            )
    return changes


def _per_wall_residual_delta(
    before_rows: Sequence[Mapping[str, Any]], after_rows: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    before_walls = _geometry(before_rows)["floorprint"]["walls"]
    after_walls = _geometry(after_rows)["floorprint"]["walls"]
    walls = []
    for index, (before, after) in enumerate(zip(before_walls, after_walls)):
        source_edge_ids = [
            int(before_rows[index]["source_pair_id"]),
            int(before_rows[(index + 1) % len(before_rows)]["source_pair_id"]),
        ]
        delta = after["angle_residual_deg"] - before["angle_residual_deg"]
        walls.append(
            {
                "source_edge_ids": source_edge_ids,
                "wall_index": index + 1,
                "before_residual_deg": before["angle_residual_deg"],
                "after_residual_deg": after["angle_residual_deg"],
                "residual_delta_deg": delta,
                "before_length": before["floor_wall_length"],
                "after_length": after["floor_wall_length"],
                "seam_edge": index == len(before_walls) - 1,
            }
        )
    return {
        "walls": walls,
        "summary": {
            "improved_edges": [row["source_edge_ids"] for row in walls if row["residual_delta_deg"] < -1e-9],
            "worsened_edges": [row["source_edge_ids"] for row in walls if row["residual_delta_deg"] > 1e-9],
            "residual_sum_before": sum(row["before_residual_deg"] for row in walls),
            "residual_sum_after": sum(row["after_residual_deg"] for row in walls),
            "residual_max_before": max(row["before_residual_deg"] for row in walls),
            "residual_max_after": max(row["after_residual_deg"] for row in walls),
        },
    }


def _card(
    index: int,
    mode: str,
    axes: Sequence[str],
    baseline_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    footprint_rows, deltas, trace = _greedy_footprint(baseline_rows, mode, axes)
    final_rows, target_height, top_y_deltas = _height_adjust(footprint_rows, deltas)
    before = _metrics(baseline_rows)
    footprint = _metrics(footprint_rows)
    final = _metrics(final_rows)
    per_wall = _per_wall_residual_delta(baseline_rows, final_rows)
    protected_unchanged = all(
        _by_source(baseline_rows)[sid] == _by_source(final_rows)[sid]
        for sid in PROTECTED_SOURCE_PAIR_IDS
    )
    hard_gate = {
        "protected_pair_3_unchanged": protected_unchanged,
        "no_self_intersection": not final["self_intersection"],
        "minimum_wall_length_ok": final["min_wall_length"] >= MIN_WALL_LENGTH,
        "vertical_wall_x_residual_zero": math.isclose(
            final["vertical_x_residual_sum"], 0.0, abs_tol=1e-9
        ),
        "annotation_writeback_false": True,
        "reorder_unchanged": True,
    }
    decision = "review_available" if all(hard_gate.values()) else "rejected_topology_risk"
    changed_pairs = [
        sid
        for sid, row in deltas.items()
        if any(abs(value) > 1e-9 for value in row.values())
    ]
    return {
        "candidate_id": f"m_anchor_4_candidate_{index:04d}_{mode}",
        "mode": mode,
        "footprint_axes": list(axes),
        "changed_pairs": changed_pairs,
        "protected_source_pair_ids": list(PROTECTED_SOURCE_PAIR_IDS),
        "movement_by_axis": {
            str(sid): row for sid, row in deltas.items() if any(abs(v) > 1e-9 for v in row.values())
        },
        "footprint_trace": trace,
        "target_height_after_footprint": target_height,
        "top_y_delta_by_source_pair": {str(k): v for k, v in top_y_deltas.items()},
        "metrics_before": before,
        "metrics_after_footprint": footprint,
        "metrics_after_height": final,
        "per_wall_residual_diagnostic": per_wall,
        "improved_edges": per_wall["summary"]["improved_edges"],
        "worsened_edges": per_wall["summary"]["worsened_edges"],
        "wall_residual_sum_before": before["wall_residual_sum"],
        "wall_residual_sum_after_footprint": footprint["wall_residual_sum"],
        "wall_residual_sum_after_height": final["wall_residual_sum"],
        "wall_residual_max_before": before["wall_residual_max"],
        "wall_residual_max_after_footprint": footprint["wall_residual_max"],
        "wall_residual_max_after_height": final["wall_residual_max"],
        "height_l1_before": before["height_l1"],
        "height_l1_after_footprint": footprint["height_l1"],
        "height_l1_after_height": final["height_l1"],
        "vertical_x_residual_sum_after": final["vertical_x_residual_sum"],
        "hard_gate": hard_gate,
        "candidate_available": decision == "review_available",
        "decision": decision,
        "coordinate_changes": _coordinate_changes(baseline_rows, final_rows),
        "corrected_coordinates": final_rows,
        **SAFETY,
    }


def _sort_key(card: Mapping[str, Any]) -> tuple[float, ...]:
    return (
        0.0 if card["candidate_available"] else 1.0,
        card["wall_residual_max_after_footprint"],
        card["wall_residual_sum_after_footprint"],
        card["height_l1_after_height"],
        _movement_cost({int(k): v for k, v in card["movement_by_axis"].items()}),
    )


def _summary(payload: Mapping[str, Any]) -> str:
    lines = [
        "# M-Anchor.4 task218_ann3741 staged vertical+height review",
        "",
        "- Goal: first make the footprint/wall directions more Manhattan with `x + bottom_y`; then keep footprint fixed and adjust `top_y` for height consistency.",
        "- Geometry residual is still review triage only; no candidate is accepted or written back.",
        f"- allowed_source_pair_ids: `{payload['authorization']['allowed_source_pair_ids']}`",
        f"- protected_source_pair_ids: `{payload['authorization']['protected_source_pair_ids']}`",
        f"- candidate_count: `{payload['candidate_count']}`",
        "",
        "| candidate | changed pairs | wall max before->footprint | wall sum before->footprint | height L1 before->after | vertical x residual | decision |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in payload["candidate_cards"]:
        lines.append(
            f"| {row['candidate_id']} | {row['changed_pairs']} | "
            f"{row['wall_residual_max_before']:.3f}->{row['wall_residual_max_after_footprint']:.3f} | "
            f"{row['wall_residual_sum_before']:.3f}->{row['wall_residual_sum_after_footprint']:.3f} | "
            f"{row['height_l1_before']:.3f}->{row['height_l1_after_height']:.3f} | "
            f"{row['vertical_x_residual_sum_after']:.6f} | {row['decision']} |"
        )
    return "\n".join(lines) + "\n"


def _review_manifest(
    payload: Mapping[str, Any],
    baseline_rows: Sequence[Mapping[str, Any]],
    source_image: str | None,
) -> dict[str, Any]:
    return {
        "schema_version": "m_anchor_4_local_3d_review_bridge_v1",
        "case_name": "task218_ann3741_m_anchor_4",
        "source_case_name": "task218_ann3741",
        "source_image": source_image,
        "ordered_pairs": list(baseline_rows),
        "candidates": [
            {
                "candidate_id": row["candidate_id"],
                "family": "m_anchor_4_staged_vertical_height_solver",
                "action_family": "m_anchor_4_staged_vertical_height_solver",
                "decision_class": row["decision"],
                "source_stage": "m_anchor_4",
                "source_rank": index,
                "review_role": "m_anchor_4_top_review",
                "selection_reason": "staged_footprint_then_height",
                "manual_review_candidate": True,
                "automatic_fix_claimed": False,
                "direct_ls_trial_allowed": False,
                "accepted": False,
                "downstream_recommendation": False,
                "candidate_preference_authorized": False,
                "annotation_writeback": False,
                "annotation_patch_generated": False,
                "coordinate_changes": row["coordinate_changes"],
                "changed_pairs": row["changed_pairs"],
                "wall_residual_sum_before": row["wall_residual_sum_before"],
                "wall_residual_sum_after": row["wall_residual_sum_after_height"],
                "required_wall_residuals": [
                    {
                        "edge": "-".join(str(part) for part in wall["source_edge_ids"]),
                        "source_edge_ids": wall["source_edge_ids"],
                        "before_residual_deg": wall["before_residual_deg"],
                        "after_residual_deg": wall["after_residual_deg"],
                        "residual_delta_deg": wall["residual_delta_deg"],
                    }
                    for wall in row["per_wall_residual_diagnostic"]["walls"]
                ],
            }
            for index, row in enumerate(payload["candidate_cards"], start=1)
        ],
        "safety_boundary": {
            "audit_only": True,
            "preview_only": True,
            "accepted": False,
            "downstream_recommendation": False,
            "candidate_preference_authorized": False,
            "annotation_writeback": False,
            "annotation_patch_generated": False,
            "active_runner_role": False,
            "ranking_entry_allowed": False,
            "portfolio_selection_allowed": False,
        },
    }


def run(out_dir: Path = OUT_DIR, review_out_dir: Path = REVIEW_OUT_DIR) -> dict[str, Path]:
    m1 = _load(M1_AUDIT_PATH)
    m2 = _load(M2_VERDICT_PATH)
    if m2.get("accepted_as_final_fix") is not False or m2.get("annotation_writeback") is not False:
        raise ValueError("M-Anchor.4 requires M2 to remain review-only/no-writeback")
    baseline_rows = next(
        row for row in m1["solver_prototypes"] if row["candidate_id"] == m2["reviewed_candidate"]
    )["corrected_coordinates"]
    authorization = {
        "schema_version": "m_anchor_4_user_authorization_v1",
        "case_name": "task218_ann3741",
        "allowed_source_pair_ids": list(ALLOWED_SOURCE_PAIR_IDS),
        "protected_source_pair_ids": list(PROTECTED_SOURCE_PAIR_IDS),
        "stage_order": ["footprint_vertical_wall_direction", "height_top_y"],
        "footprint_variables": ["x", "bottom_y"],
        "height_variables": ["top_y"],
        "forbidden": ["reorder", "merge", "delete", "new_corner", "writeback", "ranking"],
        **SAFETY,
    }
    cards = [_card(index, mode, axes, baseline_rows) for index, (mode, axes) in enumerate(MODES, start=1)]
    cards = sorted(cards, key=_sort_key)[:TOP_K]
    payload = {
        "schema_version": "m_anchor_4_staged_vertical_height_solver_audit_v1",
        "case_name": "task218_ann3741",
        "input_sources": {
            "m_anchor_1_audit": {"path": M1_AUDIT_PATH.as_posix(), "sha256": _sha(M1_AUDIT_PATH)},
            "m_anchor_2_human_verdict": {
                "path": M2_VERDICT_PATH.as_posix(),
                "sha256": _sha(M2_VERDICT_PATH),
            },
            "baseline_review_candidate": m2["reviewed_candidate"],
        },
        "authorization": authorization,
        "candidate_count": len(cards),
        "candidate_cards": cards,
        "accepted_as_final_fix": False,
        **SAFETY,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    auth_path = out_dir / "m_anchor_4_user_authorization.json"
    audit_path = out_dir / "m_anchor_4_staged_solver_audit.json"
    cards_path = out_dir / "m_anchor_4_candidate_cards.jsonl"
    summary_path = out_dir / "m_anchor_4_summary.md"
    _write_text_lf(auth_path, json.dumps(authorization, ensure_ascii=False, indent=2) + "\n")
    _write_text_lf(audit_path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    _write_text_lf(cards_path, "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in cards))
    _write_text_lf(summary_path, _summary(payload))

    review_out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = review_out_dir / "hypothesis_review_bridge_manifest.json"
    manifest = _review_manifest(payload, baseline_rows, m1.get("source_image"))
    _write_text_lf(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    review_paths = run_local_review(
        input_path=manifest_path,
        candidate_json=manifest_path,
        candidate_limit=len(manifest["candidates"]),
        out_dir=review_out_dir,
        image_root=DEFAULT_IMAGE_ROOT,
        case_name="task218_ann3741_m_anchor_4",
        width=1024,
        height=512,
        coordinate_mode="ls_percent",
        local_server_root=_local_server_root(review_out_dir),
    )
    return {
        "authorization": auth_path,
        "audit": audit_path,
        "cards": cards_path,
        "summary": summary_path,
        "review_manifest": manifest_path,
        **{f"review_{key}": value for key, value in review_paths.items()},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--review-out-dir", type=Path, default=REVIEW_OUT_DIR)
    args = parser.parse_args()
    for name, path in run(args.out_dir, args.review_out_dir).items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
