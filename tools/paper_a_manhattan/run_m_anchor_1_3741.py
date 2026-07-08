"""Materialize M-Anchor.1 audit artifacts for task218_ann3741."""

from __future__ import annotations

import copy
import hashlib
import json
import math
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
from tools.paper_a_manhattan.segment_aware_manhattan_refit import (
    VERIFIED_ORDER_SOURCE_IDS,
)

ROOT = Path("analysis_results/paper_a_manhattan/segment_aware_manhattan_refit")
BASELINE_PATH = ROOT / "task218_ann3741_joint_xy_search/_review_input.json"
ROBUST_PATH = ROOT / "task218_ann3741/segment_aware_manhattan_refit_3741.json"
HEIGHT_PATH = (
    ROOT
    / "task218_ann3741_height_plane_preserving/"
    "segment_aware_manhattan_refit_3741_height_plane_preserving.json"
)
JOINT_PATH = (
    ROOT
    / "task218_ann3741_joint_xy_search/"
    "segment_aware_manhattan_refit_3741_joint_xy_search.json"
)
OUT_DIR = Path("analysis_results/paper_a_manhattan/m_anchor/task218_ann3741_m_anchor_1")
SAFETY = {
    "audit_only": True,
    "accepted": False,
    "downstream_recommendation": False,
    "candidate_preference_authorized": False,
    "annotation_writeback": False,
    "annotation_patch_generated": False,
    "active_runner_role": False,
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _by_source(rows: Sequence[Mapping[str, Any]]) -> dict[int, dict[str, Any]]:
    return {int(row["source_pair_id"]): copy.deepcopy(row) for row in rows}


def _ordered(rows_by_source: Mapping[int, Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [copy.deepcopy(rows_by_source[source_id]) for source_id in VERIFIED_ORDER_SOURCE_IDS]


def _mapping_table(source_image: str) -> list[dict[str, Any]]:
    return [
        {
            "source_pair_id": source_id,
            "solver_position": position,
            "verified_order_source_id": source_id,
            "original_preview_pair_id": source_id,
            "source_image": source_image,
            "seam_before_pair": position == 1,
            "seam_after_pair": position == len(VERIFIED_ORDER_SOURCE_IDS),
        }
        for position, source_id in enumerate(VERIFIED_ORDER_SOURCE_IDS, start=1)
    ]


def _anchor_constraints(baseline: Mapping[int, Mapping[str, Any]]) -> list[dict[str, Any]]:
    specs = [
        (2, "top", "x", 0.45, "pair2_occlusion_sensitive_visual_x"),
        (2, "bottom", "x", 0.45, "pair2_occlusion_sensitive_visual_x"),
        (2, "top", "y", 1.00, "pair2_visual_top_y"),
        (2, "bottom", "y", 1.00, "pair2_visual_bottom_y"),
        (11, "top", "x", 0.45, "right_seam_visual_x"),
        (11, "bottom", "x", 0.45, "right_seam_visual_x"),
        (11, "top", "y", 2.00, "right_seam_top_y_soft"),
        (11, "bottom", "y", 1.00, "right_seam_bottom_y"),
    ]
    for source_id in (3, 4):
        for endpoint in ("top", "bottom"):
            for axis in ("x", "y"):
                specs.append((source_id, endpoint, axis, 0.75, "strong_visual_anchor_3_4"))
    return [
        {
            "constraint_id": f"s{source_id}_{endpoint}_{axis}",
            "schema_version": "expert_anchor_constraints_v1",
            "constraint_type": "point_axis_anchor",
            "source_pair_id": source_id,
            "solver_position": VERIFIED_ORDER_SOURCE_IDS.index(source_id) + 1,
            "verified_order_source_id": source_id,
            "endpoint": endpoint,
            "axis": axis,
            "anchor_value": float(baseline[source_id][endpoint][axis]),
            "tolerance": tolerance,
            "role": role,
            "hard_fail_on_violation": True,
        }
        for source_id, endpoint, axis, tolerance, role in specs
    ]


def _geometry(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    projection = project_layout_to_3d(rows, 1024, 512, "ls_percent", DEFAULT_CAMERA_HEIGHT)
    return compute_all_geometry_metrics(projection)


def _per_wall_residuals(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    projection = project_layout_to_3d(rows, 1024, 512, "ls_percent", DEFAULT_CAMERA_HEIGHT)
    points = [
        (float(row["floor_3d"]["x"]), float(row["floor_3d"]["z"]))
        for row in projection["pairs"]
    ]
    walls = []
    for index, left_source_id in enumerate(VERIFIED_ORDER_SOURCE_IDS):
        right_source_id = VERIFIED_ORDER_SOURCE_IDS[(index + 1) % len(VERIFIED_ORDER_SOURCE_IDS)]
        left, right = points[index], points[(index + 1) % len(points)]
        dx, dz = right[0] - left[0], right[1] - left[1]
        angle = abs(math.degrees(math.atan2(dz, dx))) % 90.0
        residual = min(angle, 90.0 - angle)
        walls.append(
            {
                "source_edge_ids": [left_source_id, right_source_id],
                "solver_edge_positions": [index + 1, (index + 1) % len(points) + 1],
                "seam_edge": index == len(points) - 1,
                "length": math.hypot(dx, dz),
                "manhattan_residual_deg": residual,
            }
        )
    return {
        "walls": walls,
        "summary": {
            "wall_count": len(walls),
            "residual_sum": sum(row["manhattan_residual_deg"] for row in walls),
            "residual_max": max(row["manhattan_residual_deg"] for row in walls),
        },
    }


def _anchor_audit(
    candidate: Mapping[int, Mapping[str, Any]],
    constraints: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    rows = []
    for constraint in constraints:
        value = float(
            candidate[int(constraint["source_pair_id"])][constraint["endpoint"]][constraint["axis"]]
        )
        delta = value - float(constraint["anchor_value"])
        rows.append({**constraint, "candidate_value": value, "delta": delta, "satisfied": abs(delta) <= float(constraint["tolerance"])})
    satisfied = sum(row["satisfied"] for row in rows)
    return {
        "constraints": rows,
        "satisfied_count": satisfied,
        "total_count": len(rows),
        "anchor_satisfaction_rate": satisfied / len(rows),
        "violations": [row for row in rows if not row["satisfied"]],
    }


def _candidate(
    candidate_id: str,
    prototype_type: str,
    rows: Sequence[Mapping[str, Any]],
    baseline: Mapping[int, Mapping[str, Any]],
    constraints: Sequence[Mapping[str, Any]],
    baseline_wall_residual: float,
) -> dict[str, Any]:
    rows_by_source = _by_source(rows)
    anchor = _anchor_audit(rows_by_source, constraints)
    geometry = _geometry(_ordered(rows_by_source))
    wall = geometry["floorprint"]["summary"]["wall_residual_sum_deg"]
    false_drift = wall < baseline_wall_residual and anchor["violations"]
    decision = "rejected_false_visual_drift" if false_drift else "review_available"
    solver_scope = (
        "footprint_only"
        if prototype_type.startswith("footprint")
        else "height_only"
        if prototype_type.startswith("height")
        else "diagnostic_reference"
    )
    return {
        "candidate_id": candidate_id,
        "prototype_type": prototype_type,
        "solver_scope": solver_scope,
        "source_pair_order": VERIFIED_ORDER_SOURCE_IDS,
        "pair_count": len(rows),
        "anchor_audit": anchor,
        "per_wall_residual_diagnostic": _per_wall_residuals(_ordered(rows_by_source)),
        "metrics": {
            "wall_residual_sum": wall,
            "turn_residual_max": geometry["corner_turns"]["summary"]["corner_residual_max_deg"],
            "height_consistency_l1": geometry["heights"]["summary"]["height_residual_sum"],
            "self_intersection": geometry["floorprint"]["self_intersection"],
        },
        "false_visual_drift": bool(false_drift),
        "decision": decision,
        "candidate_available": decision == "review_available",
        "explanation_card": {
            "what_changed": "geometry consistency prototype under explicit human visual anchors",
            "why_candidate_exists": "test whether human semantic anchors plus solver diagnostics produce a reviewable candidate",
            "why_not_accepted": "M-Anchor.1 is audit-only and still requires human visual review",
            "downgrade_rule": "any geometry-improving candidate that violates hard visual anchors is rejected as false_visual_drift",
        },
        "corrected_coordinates": _ordered(rows_by_source),
        **SAFETY,
    }


def _summary(payload: Mapping[str, Any]) -> str:
    metrics = payload["acceptance_metrics"]
    lines = [
        "# M-Anchor.1 task218_ann3741",
        "",
        "- Mode: human visual semantics anchor the layout; solver only fills geometry consistency.",
        f"- anchor_satisfaction_rate: `{metrics['anchor_satisfaction_rate']:.4f}`",
        f"- candidate_available_rate: `{metrics['candidate_available_rate']:.4f}`",
        f"- expert_accept@3: `{metrics['expert_accept_at_3']}` ({metrics['expert_accept_at_3_status']})",
        f"- false_visual_drift_rate: `{metrics['false_visual_drift_rate']:.4f}`",
        "",
        "| candidate | scope | anchor rate | wall sum | height L1 | decision |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in payload["candidate_explanation_cards"]:
        lines.append(
            f"| {row['candidate_id']} | {row['solver_scope']} | {row['anchor_satisfaction_rate']:.4f} | "
            f"{row['wall_residual_sum']:.3f} | {row['height_consistency_l1']:.3f} | {row['decision']} |"
        )
    lines += [
        "",
        "- Safety: accepted/downstream/preference/writeback/patch all remain `false`.",
    ]
    return "\n".join(lines) + "\n"


def run(out_dir: Path = OUT_DIR) -> dict[str, Path]:
    baseline_payload = _load(BASELINE_PATH)
    robust_payload = _load(ROBUST_PATH)
    height_payload = _load(HEIGHT_PATH)
    joint_payload = _load(JOINT_PATH)
    baseline_rows = baseline_payload["ordered_pairs"]
    baseline = _by_source(baseline_rows)
    constraints = _anchor_constraints(baseline)
    baseline_geometry = _geometry(baseline_rows)
    baseline_wall = baseline_geometry["floorprint"]["summary"]["wall_residual_sum_deg"]
    candidates = [
        _candidate(
            "m_anchor_1_footprint_only_joint_xy",
            "footprint_only_constrained_solver_prototype",
            joint_payload["top_candidate"]["corrected_coordinates"],
            baseline,
            constraints,
            baseline_wall,
        ),
        _candidate(
            "m_anchor_1_height_only_plane_preserving",
            "height_only_constrained_solver_prototype",
            height_payload["top_candidate"]["corrected_coordinates"],
            baseline,
            constraints,
            baseline_wall,
        ),
        _candidate(
            "m_anchor_1_false_drift_reference_robust_all_long_edges",
            "diagnostic_false_visual_drift_reference",
            robust_payload["corrected_coordinates"],
            baseline,
            constraints,
            baseline_wall,
        ),
    ]
    available = [row for row in candidates if row["candidate_available"]]
    unresolved_false_drift = [row for row in available if row["false_visual_drift"]]
    aggregate = {
        "anchor_satisfaction_rate": sum(
            row["anchor_audit"]["satisfied_count"] for row in candidates
        )
        / sum(row["anchor_audit"]["total_count"] for row in candidates),
        "candidate_available_rate": len(available) / len(candidates),
        "expert_accept_at_3": None,
        "expert_accept_at_3_status": "pending_human_review",
        "false_visual_drift_rate": len(unresolved_false_drift) / max(1, len(available)),
        "false_visual_drift_rejected_count": sum(
            row["false_visual_drift"] and not row["candidate_available"] for row in candidates
        ),
    }
    payload = {
        "schema_version": "m_anchor_1_audit_v1",
        "case_name": "task218_ann3741",
        "source_image": joint_payload["source_image"],
        "input_sources": {
            "baseline": {"path": BASELINE_PATH.as_posix(), "sha256": _sha(BASELINE_PATH)},
            "robust": {"path": ROBUST_PATH.as_posix(), "sha256": _sha(ROBUST_PATH)},
            "height_only": {"path": HEIGHT_PATH.as_posix(), "sha256": _sha(HEIGHT_PATH)},
            "footprint_only": {"path": JOINT_PATH.as_posix(), "sha256": _sha(JOINT_PATH)},
        },
        "id_semantics": joint_payload["id_semantics"],
        "pair_sid_order_seam_mapping_table": _mapping_table(joint_payload["source_image"]),
        "expert_anchor_constraints_schema": {
            "schema_version": "expert_anchor_constraints_v1",
            "constraint_types": ["point_axis_anchor"],
            "false_visual_drift_policy": "fail_closed",
        },
        "expert_anchor_constraints": constraints,
        "baseline_per_wall_residual_diagnostic": _per_wall_residuals(baseline_rows),
        "solver_prototypes": candidates,
        "candidate_explanation_cards": [
            {
                "candidate_id": row["candidate_id"],
                "solver_scope": row["solver_scope"],
                "anchor_satisfaction_rate": row["anchor_audit"]["anchor_satisfaction_rate"],
                "wall_residual_sum": row["metrics"]["wall_residual_sum"],
                "height_consistency_l1": row["metrics"]["height_consistency_l1"],
                "decision": row["decision"],
                "false_visual_drift": row["false_visual_drift"],
                "why_not_accepted": row["explanation_card"]["why_not_accepted"],
            }
            for row in candidates
        ],
        "acceptance_metrics": aggregate,
        "safety_flags": SAFETY,
        **SAFETY,
    }
    ledger_row = {
        "schema_version": "m_anchor_1_feedback_ledger_row_v1",
        "case_name": payload["case_name"],
        "candidate_set": [row["candidate_id"] for row in candidates],
        "shown_rank": [row["candidate_id"] for row in candidates[:3]],
        "expert_selected_candidate": None,
        "expert_accept_at_3": None,
        "candidate_verdicts": {row["candidate_id"]: row["decision"] for row in candidates},
        "acceptance_metrics": aggregate,
        **SAFETY,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "m_anchor_1_audit.json"
    summary_path = out_dir / "m_anchor_1_summary.md"
    ledger_path = out_dir / "m_anchor_1_feedback_ledger_row.jsonl"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary_path.write_text(_summary(payload), encoding="utf-8")
    ledger_path.write_text(json.dumps(ledger_row, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"json": json_path, "summary": summary_path, "ledger": ledger_path}


if __name__ == "__main__":
    print(run()["json"])
