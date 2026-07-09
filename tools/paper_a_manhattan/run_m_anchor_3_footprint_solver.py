"""M-Anchor.3 review-only bottom_y footprint audit for task218_ann3741.

Goal: verify whether bottom_y-only adjustment can improve BEV footprint
Manhattan consistency under fixed/limited expert visual x anchors, while
avoiding visual drift.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.paper_a_manhattan.manhattan_3d_projection import (
    DEFAULT_CAMERA_HEIGHT,
    compute_all_geometry_metrics,
    project_layout_to_3d,
)
from tools.paper_a_manhattan.run_m_anchor_1_3741 import (
    ANCHOR_SIDECAR_PATH,
    BASELINE_PATH,
    SAFETY,
    _anchor_audit,
    _anchor_constraints,
    _by_source,
    _load,
    _load_anchor_sidecar,
    _ordered,
    _per_wall_residuals,
    _sha,
    _write_text_lf,
)

M1_AUDIT_PATH = Path(
    "analysis_results/paper_a_manhattan/m_anchor/task218_ann3741_m_anchor_1/"
    "m_anchor_1_audit.json"
)
M2_VERDICT_PATH = Path(
    "analysis_results/paper_a_manhattan/m_anchor/task218_ann3741_m_anchor_2/"
    "m_anchor_2_human_verdict.json"
)
OUT_DIR = Path("analysis_results/paper_a_manhattan/m_anchor/task218_ann3741_m_anchor_3")
TARGET_STATEMENT = (
    "M-Anchor.3 verifies whether bottom_y-only adjustment can improve BEV "
    "footprint Manhattan consistency under fixed/limited expert visual x anchors, "
    "while avoiding visual drift."
)
DELTAS = (0.25, 0.5, 1.0)


def _check_m2(verdict: Mapping[str, Any]) -> None:
    required = {
        "accept_for_next_stage": True,
        "accepted_as_final_fix": False,
        "annotation_writeback": False,
    }
    for key, value in required.items():
        if verdict.get(key) is not value:
            raise ValueError(f"M-Anchor.3 blocked by M-Anchor.2 {key}={verdict.get(key)!r}")
    if verdict.get("expert_verdict") == "reject":
        raise ValueError("M-Anchor.3 blocked by rejected M-Anchor.2 verdict")


def _move_range(sidecar: Mapping[str, Any]) -> dict[str, Any]:
    ranges = [
        row
        for row in sidecar.get("move_ranges", [])
        if row.get("constraint_type") == "field_move_range"
        and int(row.get("source_pair_id")) == 6
        and row.get("endpoint") == "bottom"
        and row.get("axis") == "y"
    ]
    if len(ranges) != 1:
        raise ValueError("M-Anchor.3 requires exactly one s6 bottom_y field_move_range")
    return ranges[0]


def _geometry(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    projection = project_layout_to_3d(rows, 1024, 512, "ls_percent", DEFAULT_CAMERA_HEIGHT)
    return compute_all_geometry_metrics(projection)


def _edge_length(rows: Sequence[Mapping[str, Any]], source_a: int, source_b: int) -> float:
    projection = project_layout_to_3d(rows, 1024, 512, "ls_percent", DEFAULT_CAMERA_HEIGHT)
    by_source = {
        int(source["source_pair_id"]): projected
        for source, projected in zip(rows, projection["pairs"])
    }
    a = by_source[source_a]["floor_3d"]
    b = by_source[source_b]["floor_3d"]
    return ((float(a["x"]) - float(b["x"])) ** 2 + (float(a["z"]) - float(b["z"])) ** 2) ** 0.5


def _candidate(
    delta: float,
    before_rows: Sequence[Mapping[str, Any]],
    constraints: Sequence[Mapping[str, Any]],
    before_geometry: Mapping[str, Any],
    before_keep_distinct_margin: float,
) -> dict[str, Any]:
    rows = copy.deepcopy(list(before_rows))
    for row in rows:
        if int(row["source_pair_id"]) == 6:
            row["bottom"]["y"] = float(row["bottom"]["y"]) + delta
            break

    after_geometry = _geometry(rows)
    anchor = _anchor_audit(_by_source(rows), constraints)
    x_rows = [row for row in anchor["constraints"] if row["axis"] == "x"]
    x_satisfied = sum(row["satisfied"] for row in x_rows)
    after_margin = _edge_length(rows, 5, 6)
    before_wall = before_geometry["floorprint"]["summary"]
    after_wall = after_geometry["floorprint"]["summary"]
    before_turn = before_geometry["corner_turns"]["summary"]
    after_turn = after_geometry["corner_turns"]["summary"]

    hard_violation = bool(anchor["hard_violations"])
    top_y_changed = False
    reorder_changed = False
    keep_distinct_ok = after_margin > 0.15 and after_margin >= before_keep_distinct_margin * 0.5
    wall_sum_improved = after_wall["wall_residual_sum_deg"] < before_wall["wall_residual_sum_deg"]
    wall_max_ok = after_wall["wall_residual_max_deg"] <= before_wall["wall_residual_max_deg"] + 0.25

    if hard_violation:
        decision = "rejected_hard_anchor_violation"
    elif top_y_changed or reorder_changed or not keep_distinct_ok:
        decision = "rejected_topology_risk"
    elif x_satisfied != len(x_rows):
        decision = "rejected_visual_drift"
    elif wall_sum_improved and wall_max_ok:
        decision = "review_available"
    else:
        decision = "neutral_review"

    return {
        "candidate_id": f"m_anchor_3_s6_bottom_y_p{str(delta).replace('.', '')}",
        "changed_pairs": [6],
        "changed_fields": ["bottom_y"],
        "bottom_y_delta_by_pair": {"6": delta},
        "x_anchor_satisfaction": {
            "satisfied_count": x_satisfied,
            "total_count": len(x_rows),
            "rate": x_satisfied / len(x_rows),
        },
        "hard_anchor_violation": hard_violation,
        "wall_residual_sum_before": before_wall["wall_residual_sum_deg"],
        "wall_residual_sum_after": after_wall["wall_residual_sum_deg"],
        "wall_residual_max_before": before_wall["wall_residual_max_deg"],
        "wall_residual_max_after": after_wall["wall_residual_max_deg"],
        "turn_residual_max_before": before_turn["corner_residual_max_deg"],
        "turn_residual_max_after": after_turn["corner_residual_max_deg"],
        "short_wall_preservation": keep_distinct_ok,
        "keep_distinct_margin_5_6": {
            "before": before_keep_distinct_margin,
            "after": after_margin,
        },
        "seam_edge_status": {
            "source_edge_ids": [11, 2],
            "preserved": True,
            "reorder_changed": reorder_changed,
        },
        "height_not_evaluated_or_fixed": True,
        "top_y_changed": top_y_changed,
        "reorder_changed": reorder_changed,
        "candidate_available": decision == "review_available",
        "decision": decision,
        "corrected_coordinates": rows,
        **SAFETY,
    }


def _summary(payload: Mapping[str, Any]) -> str:
    lines = [
        "# M-Anchor.3 task218_ann3741",
        "",
        TARGET_STATEMENT,
        "",
        f"- candidate_count: `{len(payload['candidate_cards'])}`",
        "- Variables: `bottom_y` only; `top_y` fixed; reorder/merge/delete/new corner forbidden.",
        "- Safety: accepted/downstream/writeback/ranking/portfolio all remain `false`.",
        "",
        "| candidate | s6 bottom_y delta | wall sum before | wall sum after | wall max after | decision |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in payload["candidate_cards"]:
        lines.append(
            f"| {row['candidate_id']} | {row['bottom_y_delta_by_pair']['6']:.2f} | "
            f"{row['wall_residual_sum_before']:.3f} | {row['wall_residual_sum_after']:.3f} | "
            f"{row['wall_residual_max_after']:.3f} | {row['decision']} |"
        )
    return "\n".join(lines) + "\n"


def run(out_dir: Path = OUT_DIR) -> dict[str, Path]:
    m1 = _load(M1_AUDIT_PATH)
    m2 = _load(M2_VERDICT_PATH)
    sidecar = _load_anchor_sidecar()
    baseline = _load(BASELINE_PATH)
    _check_m2(m2)
    move_range = _move_range(sidecar)

    reviewed = next(
        row
        for row in m1["solver_prototypes"]
        if row["candidate_id"] == m2["reviewed_candidate"]
    )
    before_rows = reviewed["corrected_coordinates"]
    constraints = _anchor_constraints(sidecar)
    before_geometry = _geometry(before_rows)
    before_margin = _edge_length(before_rows, 5, 6)
    min_delta = float(move_range["min_delta"])
    max_delta = float(move_range["max_delta"])
    candidates = [
        _candidate(delta, before_rows, constraints, before_geometry, before_margin)
        for delta in DELTAS
        if min_delta <= delta <= max_delta
    ][:5]

    payload = {
        "schema_version": "m_anchor_3_footprint_solver_audit_v1",
        "case_name": "task218_ann3741",
        "goal": TARGET_STATEMENT,
        "input_sources": {
            "m_anchor_1_audit": {"path": M1_AUDIT_PATH.as_posix(), "sha256": _sha(M1_AUDIT_PATH)},
            "expert_anchor_constraints_sidecar": {
                "path": ANCHOR_SIDECAR_PATH.as_posix(),
                "sha256": _sha(ANCHOR_SIDECAR_PATH),
            },
            "m_anchor_2_human_verdict": {
                "path": M2_VERDICT_PATH.as_posix(),
                "sha256": _sha(M2_VERDICT_PATH),
            },
            "baseline_ordered_pairs": {
                "path": BASELINE_PATH.as_posix(),
                "sha256": _sha(BASELINE_PATH),
            },
        },
        "reviewed_candidate": reviewed["candidate_id"],
        "baseline_pair_count": len(baseline["ordered_pairs"]),
        "variable_boundary": {
            "allowed_variables": ["bottom_y"],
            "x_policy": m2["next_stage_authorization"]["x_policy"],
            "top_y_policy": m2["next_stage_authorization"]["top_y_policy"],
            "forbidden": ["top_y", "reorder", "merge", "delete", "new_corner", "writeback", "active_ranking", "portfolio_selection"],
        },
        "move_ranges_used": [move_range],
        "candidate_count": len(candidates),
        "candidate_cards": candidates,
        "baseline_per_wall_residual_diagnostic": _per_wall_residuals(_ordered(_by_source(before_rows))),
        **SAFETY,
    }

    ledger = {
        "schema_version": "m_anchor_3_feedback_ledger_stub_v1",
        "case_name": payload["case_name"],
        "reviewed_candidate": payload["reviewed_candidate"],
        "candidate_ids": [row["candidate_id"] for row in candidates],
        "candidate_verdicts": {row["candidate_id"]: row["decision"] for row in candidates},
        "expert_selected_candidate": None,
        "accepted_as_final_fix": False,
        **SAFETY,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    audit_path = out_dir / "m_anchor_3_footprint_solver_audit.json"
    summary_path = out_dir / "m_anchor_3_footprint_solver_summary.md"
    cards_path = out_dir / "m_anchor_3_candidate_cards.jsonl"
    ledger_path = out_dir / "m_anchor_3_feedback_ledger_stub.jsonl"
    _write_text_lf(audit_path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    _write_text_lf(summary_path, _summary(payload))
    _write_text_lf(
        cards_path,
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in candidates),
    )
    _write_text_lf(ledger_path, json.dumps(ledger, ensure_ascii=False) + "\n")
    return {
        "audit": audit_path,
        "summary": summary_path,
        "cards": cards_path,
        "ledger": ledger_path,
    }


if __name__ == "__main__":
    print(run()["audit"])
