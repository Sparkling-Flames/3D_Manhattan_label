"""Materialize M-Anchor.1.1 audit artifacts for task218_ann3741.

M-Anchor.1.2 only hardens sidecar input validation; it does not change
the emitted M-Anchor.1.1 artifact schema.
"""

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
ANCHOR_SIDECAR_PATH = OUT_DIR / "expert_anchor_constraints_sidecar.json"
EXPECTED_CASE_NAME = "task218_ann3741"
EXPECTED_SOURCE_ANNOTATION_ID = 3741
EXPECTED_COORDINATE_SPACE = "ls_percent"
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


def _write_text_lf(path: Path, text: str) -> None:
    path.write_bytes(text.encode("utf-8"))


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


def _load_anchor_sidecar(path: Path = ANCHOR_SIDECAR_PATH) -> dict[str, Any]:
    payload = _load(path)
    if payload.get("schema_version") != "expert_anchor_constraints_sidecar_v1":
        raise ValueError(f"unsupported anchor sidecar schema: {path}")
    expected = {
        "case_name": EXPECTED_CASE_NAME,
        "source_annotation_id": EXPECTED_SOURCE_ANNOTATION_ID,
        "coordinate_space": EXPECTED_COORDINATE_SPACE,
    }
    for key, value in expected.items():
        if payload.get(key) != value:
            raise ValueError(f"invalid anchor sidecar {key}: {payload.get(key)!r}")
    return payload


def _anchor_constraints(sidecar: Mapping[str, Any]) -> list[dict[str, Any]]:
    allowed_strengths = {"hard", "soft", "preferred"}
    allowed_endpoints = {"top", "bottom"}
    allowed_axes = {"x", "y"}
    constraints = []
    seen_ids = set()
    for raw in sidecar["constraints"]:
        source_id = int(raw["source_pair_id"])
        strength = raw["anchor_strength"]
        endpoint = raw["endpoint"]
        axis = raw["axis"]
        constraint_id = raw["constraint_id"]
        constraint_type = raw["constraint_type"]
        if source_id not in VERIFIED_ORDER_SOURCE_IDS:
            raise ValueError(f"unknown source_pair_id in anchor sidecar: {source_id}")
        if constraint_type != "point_axis_anchor":
            raise ValueError(f"unsupported anchor constraint_type: {constraint_type}")
        if strength not in allowed_strengths:
            raise ValueError(f"unsupported anchor_strength: {strength}")
        if endpoint not in allowed_endpoints:
            raise ValueError(f"unsupported anchor endpoint: {endpoint}")
        if axis not in allowed_axes:
            raise ValueError(f"unsupported anchor axis: {axis}")
        if constraint_id in seen_ids:
            raise ValueError(f"duplicate anchor constraint_id: {constraint_id}")
        expected_id = f"s{source_id}_{endpoint}_{axis}"
        if constraint_id != expected_id:
            raise ValueError(f"invalid anchor constraint_id: {constraint_id}, expected {expected_id}")
        seen_ids.add(constraint_id)
        constraints.append(
            {
                **copy.deepcopy(raw),
                "schema_version": "expert_anchor_constraints_v1",
                "solver_position": VERIFIED_ORDER_SOURCE_IDS.index(source_id) + 1,
                "verified_order_source_id": source_id,
                "hard_fail_on_violation": strength == "hard",
            }
        )
    return constraints


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
        rows.append(
            {
                **constraint,
                "candidate_value": value,
                "delta": delta,
                "satisfied": abs(delta) <= float(constraint["tolerance"]),
            }
        )
    satisfied = sum(row["satisfied"] for row in rows)
    hard_violations = [
        row for row in rows if not row["satisfied"] and row["anchor_strength"] == "hard"
    ]
    return {
        "constraints": rows,
        "satisfied_count": satisfied,
        "total_count": len(rows),
        "anchor_satisfaction_rate": satisfied / len(rows),
        "violations": [row for row in rows if not row["satisfied"]],
        "hard_violations": hard_violations,
        "hard_violation_count": len(hard_violations),
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
    geometry_improved = wall < baseline_wall_residual
    false_drift = bool(geometry_improved and anchor["violations"])
    hard_violation = bool(anchor["hard_violations"])
    if hard_violation:
        decision = "rejected_hard_anchor_violation"
    elif false_drift:
        decision = "rejected_false_visual_drift"
    else:
        decision = "review_available"
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
        "geometry_improved_vs_baseline": bool(geometry_improved),
        "hard_anchor_violation": bool(hard_violation),
        "false_visual_drift": bool(false_drift),
        "decision": decision,
        "candidate_available": decision == "review_available",
        "explanation_card": {
            "what_changed": "geometry consistency prototype under explicit human visual anchors",
            "why_candidate_exists": "test whether human semantic anchors plus solver diagnostics produce a reviewable candidate",
            "why_not_accepted": "M-Anchor.1.1 is audit-only and still requires human visual review",
            "downgrade_rule": "hard anchor violations fail closed; geometry-improving candidates that violate soft/preferred anchors are rejected as false_visual_drift",
        },
        "corrected_coordinates": _ordered(rows_by_source),
        **SAFETY,
    }


def _summary(payload: Mapping[str, Any]) -> str:
    metrics = payload["acceptance_metrics"]
    lines = [
        "# M-Anchor.1.1 task218_ann3741",
        "",
        "- Mode: human visual semantics anchor the layout; solver only fills geometry consistency.",
        f"- anchor_satisfaction_rate: `{metrics['anchor_satisfaction_rate']:.4f}`",
        f"- candidate_available_rate: `{metrics['candidate_available_rate']:.4f}`",
        f"- expert_accept@3: `{metrics['expert_accept_at_3']}` ({metrics['expert_accept_at_3_status']})",
        f"- rejected_false_drift_rate: `{metrics['rejected_false_drift_rate']:.4f}`",
        f"- available_false_drift_rate: `{metrics['available_false_drift_rate']:.4f}`",
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
    anchor_sidecar = _load_anchor_sidecar()
    baseline_rows = baseline_payload["ordered_pairs"]
    baseline = _by_source(baseline_rows)
    constraints = _anchor_constraints(anchor_sidecar)
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
    rejected_false_drift = [
        row for row in candidates if row["false_visual_drift"] and not row["candidate_available"]
    ]
    available_false_drift = [row for row in available if row["false_visual_drift"]]
    aggregate = {
        "anchor_satisfaction_rate": sum(
            row["anchor_audit"]["satisfied_count"] for row in candidates
        )
        / sum(row["anchor_audit"]["total_count"] for row in candidates),
        "candidate_available_rate": len(available) / len(candidates),
        "expert_accept_at_3": None,
        "expert_accept_at_3_status": "pending_human_review",
        "rejected_false_drift_rate": len(rejected_false_drift) / len(candidates),
        "available_false_drift_rate": len(available_false_drift) / max(1, len(available)),
        "false_visual_drift_rejected_count": len(rejected_false_drift),
    }
    payload = {
        "schema_version": "m_anchor_1_1_audit_v1",
        "case_name": "task218_ann3741",
        "source_image": joint_payload["source_image"],
        "input_sources": {
            "baseline": {"path": BASELINE_PATH.as_posix(), "sha256": _sha(BASELINE_PATH)},
            "robust": {"path": ROBUST_PATH.as_posix(), "sha256": _sha(ROBUST_PATH)},
            "height_only": {"path": HEIGHT_PATH.as_posix(), "sha256": _sha(HEIGHT_PATH)},
            "footprint_only": {"path": JOINT_PATH.as_posix(), "sha256": _sha(JOINT_PATH)},
            "expert_anchor_constraints_sidecar": {
                "path": ANCHOR_SIDECAR_PATH.as_posix(),
                "sha256": _sha(ANCHOR_SIDECAR_PATH),
            },
        },
        "id_semantics": joint_payload["id_semantics"],
        "pair_sid_order_seam_mapping_table": _mapping_table(joint_payload["source_image"]),
        "expert_anchor_constraints_schema": {
            "schema_version": "expert_anchor_constraints_v1",
            "constraint_types": ["point_axis_anchor"],
            "anchor_strengths": ["hard", "soft", "preferred"],
            "source": "independent_sidecar",
            "false_visual_drift_policy": "fail_closed",
        },
        "expert_anchor_constraints_sidecar": {
            "path": ANCHOR_SIDECAR_PATH.as_posix(),
            "schema_version": anchor_sidecar["schema_version"],
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
                "hard_anchor_violation": row["hard_anchor_violation"],
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
        "schema_version": "m_anchor_1_1_feedback_ledger_row_v1",
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
    _write_text_lf(json_path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    _write_text_lf(summary_path, _summary(payload))
    _write_text_lf(ledger_path, json.dumps(ledger_row, ensure_ascii=False) + "\n")
    return {"json": json_path, "summary": summary_path, "ledger": ledger_path}


if __name__ == "__main__":
    print(run()["json"])
