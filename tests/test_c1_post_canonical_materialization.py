from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.thesis_main.analysis.build_c2_assignment_manifest_from_c1_gaps import materialize as materialize_c2
from tools.thesis_main.analysis.c1_materialize_c2_gap_audits import materialize as materialize_gaps
from tools.thesis_main.analysis.c1_materialize_quality_table import materialize as materialize_quality
from tools.thesis_main.analysis.c1_materialize_worker_profile_sidecar import materialize as materialize_sidecar
from tools.thesis_main.analysis.c1_materialize_worker_state import materialize as materialize_worker_state


def _csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    if path.name in {"c1_canonical_annotations.csv", "canonical.csv"}:
        eligibility = ["canonical_eligibility_status", "independence_status", "assigned_expected", "outside_assignment_submission", "duplicate_worker_task_submission", "schema_interpretable"]
        fields = fields + [field for field in eligibility if field not in fields]
        rows = [{"canonical_eligibility_status": "valid", "independence_status": "independent", "assigned_expected": "true", "outside_assignment_submission": "false", "duplicate_worker_task_submission": "false", "schema_interpretable": "true", **row} for row in rows]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _rows(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.open(encoding="utf-8")))


def test_c1_quality_worker_gaps_and_c2_reserve_draft_chain(tmp_path: Path) -> None:
    canonical = tmp_path / "c1_canonical_annotations.csv"
    fields = [
        "round_id",
        "task_id",
        "base_task_id",
        "dataset_group",
        "scene_label",
        "condition",
        "worker_id",
        "canonical_annotation_id",
        "scope",
        "difficulty",
        "model_issue",
        "n_corners",
        "geometry_hash",
        "parse_error",
        "active_time",
        "active_time_source",
        "primary_active_time_eligible",
        "sensitivity_active_time_eligible",
        "unassigned_active_time_seconds",
        "unknown_annotation_event_count",
        "unknown_annotation_session_count",
        "known_unknown_oscillation_flag",
        "unassigned_audit_present",
        "unassigned_active_time_exclusion_reason",
        "active_time_integrity_status",
        "system_collection_issue",
        "audit_only",
        "assigned_expected",
    ]
    _csv(
        canonical,
        fields,
        [
            {
                "round_id": "C1",
                "task_id": "a1",
                "base_task_id": "scene_a",
                "dataset_group": "Calibration_anchor",
                "scene_label": "room_a",
                "condition": "manual",
                "worker_id": "w1",
                "canonical_annotation_id": "ca1",
                "scope": "in_scope",
                "difficulty": "occlusion",
                "model_issue": "acceptable",
                "n_corners": "4",
                "geometry_hash": "h1",
                "parse_error": "",
                "active_time": "10",
                "active_time_source": "log",
                "primary_active_time_eligible": "true",
                "sensitivity_active_time_eligible": "true",
                "unassigned_active_time_seconds": "4",
                "unknown_annotation_event_count": "1",
                "unknown_annotation_session_count": "1",
                "known_unknown_oscillation_flag": "true",
                "unassigned_audit_present": "true",
                "unassigned_active_time_exclusion_reason": "unknown_annotation_audit_only",
                "active_time_integrity_status": "exact_annotation_valid",
                "system_collection_issue": "true",
                "audit_only": "false",
                "assigned_expected": "true",
            },
            {
                "round_id": "C1",
                "task_id": "c1",
                "base_task_id": "scene_b",
                "dataset_group": "Calibration_core",
                "scene_label": "room_b",
                "condition": "manual",
                "worker_id": "w1",
                "canonical_annotation_id": "cc1",
                "scope": "in_scope",
                "difficulty": "trivial",
                "model_issue": "underextend",
                "n_corners": "3",
                "geometry_hash": "",
                "parse_error": "bad",
                "active_time": "12",
                "active_time_source": "log",
                "primary_active_time_eligible": "true",
                "assigned_expected": "true",
            },
            {
                "round_id": "C1",
                "task_id": "s1",
                "base_task_id": "scene_s",
                "dataset_group": "Calibration_semi",
                "scene_label": "room_s",
                "condition": "semi",
                "worker_id": "w1",
                "canonical_annotation_id": "cs1",
                "scope": "in_scope",
                "difficulty": "",
                "model_issue": "acceptable",
                "n_corners": "4",
                "geometry_hash": "h2",
                "parse_error": "",
                "active_time": "8",
                "active_time_source": "log",
                "primary_active_time_eligible": "true",
                "assigned_expected": "true",
            },
        ],
    )

    out = tmp_path / "out"
    inventory = tmp_path / "core.csv"
    _csv(
        inventory,
        ["task_id", "base_task_id", "calibration_split", "used_for_r_u"],
        [{"task_id": "c1", "base_task_id": "scene_b", "calibration_split": "core", "used_for_r_u": "false_non_reliability_core"}],
    )
    quality_summary = materialize_quality(canonical, out, inventory)
    quality = _rows(out / "c1_quality_annotations.csv")
    by_task = {row["task_id"]: row for row in quality}
    assert quality_summary["r_u_estimated"] is False
    assert by_task["a1"]["geometry_valid"] == "true"
    assert by_task["a1"]["unassigned_active_time_seconds"] == "4"
    assert by_task["a1"]["active_time_integrity_status"] == "exact_annotation_valid"
    assert by_task["a1"]["system_collection_issue"] == "true"
    assert quality_summary["unassigned_active_time_seconds_total"] == 4.0
    assert quality_summary["system_collection_issue_row_count"] == 1
    assert by_task["c1"]["geometry_valid"] == "false"
    assert by_task["c1"]["used_for_r_u"] == "false"
    assert by_task["s1"]["used_for_r_u"] == "false"
    assert (out / "meta_label_consensus_summary_C1.csv").exists()
    assert json.loads((out / "meta_label_consensus_summary_C1.audit.json").read_text(encoding="utf-8"))["sidecar_only_no_dt_backflow"] is True

    assignment = tmp_path / "assignment.csv"
    _csv(
        assignment,
        ["round_id", "worker_id", "task_id", "base_task_id", "dataset_group"],
        [{"round_id": "C1", "worker_id": "w1", "task_id": "a1", "base_task_id": "scene_a", "dataset_group": "Calibration_anchor"}],
    )
    worker_summary = materialize_worker_state(out / "c1_quality_annotations.csv", [assignment], out, min_r_u_tasks=2)
    worker = _rows(out / "worker_state_snapshot_C1.csv")[0]
    assert worker_summary["r_u_estimated"] is False
    assert worker["n_calib_completed"] == "0"
    assert worker["needs_c2_ci_fill"] == "true"

    profile = tmp_path / "post_c2b_profile.csv"
    _csv(profile, ["worker_id", "support", "ci_half_width"], [{"worker_id": "w1", "support": "4", "ci_half_width": "0.2"}])
    design = tmp_path / "design.json"
    design.write_text(json.dumps({
        "manifest_version": "c2_design_v1",
        "input_sha256": {"worker_profile_csv": __import__("hashlib").sha256(profile.read_bytes()).hexdigest()},
        "precision": {"target_ci_half_width": 0.15, "max_additional_blocks": 3},
    }), encoding="utf-8")
    precision = materialize_gaps(profile, design, tmp_path / "c2")
    assert precision["candidate_only"] is True
    assert _rows(tmp_path / "c2" / "precision_plan_C2A_RP.csv")[0]["additional_blocks"] == "2"


def test_missing_core_used_for_r_u_flag_fails_closed(tmp_path: Path) -> None:
    canonical = tmp_path / "c1_canonical_annotations.csv"
    _csv(
        canonical,
        ["round_id", "task_id", "base_task_id", "dataset_group", "worker_id", "canonical_annotation_id", "n_corners", "geometry_hash", "assigned_expected"],
        [
            {
                "round_id": "C1",
                "task_id": "460",
                "base_task_id": "X7Hy",
                "dataset_group": "Calibration_core",
                "worker_id": "w1",
                "canonical_annotation_id": "c",
                "n_corners": "4",
                "geometry_hash": "h",
                "assigned_expected": "true",
            }
        ],
    )
    inventory = tmp_path / "core.csv"
    _csv(
        inventory,
        ["task_id", "base_task_id", "calibration_split", "used_for_r_u"],
        [{"task_id": "460", "base_task_id": "X7Hy", "calibration_split": "core", "used_for_r_u": "false_non_reliability_core"}],
    )

    summary = materialize_quality(canonical, tmp_path / "out", inventory)
    row = _rows(tmp_path / "out" / "c1_quality_annotations.csv")[0]

    assert row["used_for_r_u"] == "false"
    assert row["used_for_r_u_source_status"] == "from_candidate_inventory"
    assert summary["blockers"] == ["canonical_meta_missing_or_stale"]


def test_precision_plan_fails_closed_when_uncertainty_is_not_evaluable(tmp_path: Path) -> None:
    worker = tmp_path / "worker.csv"
    _csv(worker, ["worker_id", "support", "ci_half_width"], [{"worker_id": "w1", "support": "", "ci_half_width": ""}])
    design = tmp_path / "design.json"
    design.write_text(json.dumps({
        "manifest_version": "c2_design_v1",
        "input_sha256": {"worker_profile_csv": __import__("hashlib").sha256(worker.read_bytes()).hexdigest()},
        "precision": {"target_ci_half_width": 0.15, "max_additional_blocks": 3},
    }), encoding="utf-8")
    materialize_gaps(worker, design, tmp_path / "out")
    row = _rows(tmp_path / "out" / "precision_plan_C2A_RP.csv")[0]
    assert row["additional_blocks"] == "0"
    assert row["unmet_reason"] == "precision_not_evaluable"


def test_precision_plan_does_not_add_tasks_when_target_is_met(tmp_path: Path) -> None:
    worker = tmp_path / "worker.csv"
    _csv(worker, ["worker_id", "support", "ci_half_width"], [{"worker_id": "w1", "support": "10", "ci_half_width": "0.1"}])
    design = tmp_path / "design.json"
    design.write_text(json.dumps({
        "manifest_version": "c2_design_v1",
        "input_sha256": {"worker_profile_csv": __import__("hashlib").sha256(worker.read_bytes()).hexdigest()},
        "precision": {"target_ci_half_width": 0.15, "max_additional_blocks": 3},
    }), encoding="utf-8")
    materialize_gaps(worker, design, tmp_path / "out")
    row = _rows(tmp_path / "out" / "precision_plan_C2A_RP.csv")[0]
    assert row["additional_blocks"] == "0"
    assert row["precision_target_met"] == "true"


def test_canonical_quality_sidecar_preserves_inclusion_contract_fields(tmp_path: Path) -> None:
    canonical = tmp_path / "canonical.csv"
    fields = [
        "round_id", "task_id", "base_task_id", "dataset_group", "condition", "worker_id", "canonical_annotation_id",
        "task_final_scope", "task_oos_subtype", "worker_scope_response", "geometry_reference_status", "n_corners", "geometry_hash",
        "process_evaluable", "process_failure_observed", "process_failure_subfamily", "family", "subfamily", "response_type",
        "geometry_score_gate_passed", "quality_metric_name", "quality_metric_value", "geometry_metric_direction", "geometry_normalization_rule",
        "geometry_failure_threshold_status", "geometry_failure_family_evaluable", "geometry_failure_observed",
        "semi_issue_recognition_evaluable", "semi_geometry_correction_evaluable", "semi_response_type", "semi_correction_failure_observed",
            "undercoverage_evidence_status", "undercoverage_expert_verdict", "undercoverage_response", "undercoverage_subfamily", "undercoverage_failure_observed",
            "failure_attribution", "incident_evidence_status",
    ]
    _csv(canonical, fields, [{
        "round_id": "C1", "task_id": "t1", "base_task_id": "b1", "dataset_group": "Calibration_semi", "condition": "semi", "worker_id": "w1", "canonical_annotation_id": "a1",
        "task_final_scope": "in_scope", "task_oos_subtype": "", "worker_scope_response": "correct_in_scope", "geometry_reference_status": "expert_hard_single", "n_corners": "4", "geometry_hash": "h1",
        "process_evaluable": "true", "process_failure_observed": "false", "process_failure_subfamily": "", "family": "semi_correction_failure", "subfamily": "corner_drift", "response_type": "legacy_ignored",
        "geometry_score_gate_passed": "true", "quality_metric_name": "iou", "quality_metric_value": "0.8", "geometry_metric_direction": "higher_is_better", "geometry_normalization_rule": "identity_0_1",
        "geometry_failure_threshold_status": "not_frozen", "geometry_failure_family_evaluable": "false", "geometry_failure_observed": "",
        "semi_issue_recognition_evaluable": "true", "semi_geometry_correction_evaluable": "true", "semi_response_type": "successful_correction", "semi_correction_failure_observed": "false",
            "undercoverage_evidence_status": "", "undercoverage_expert_verdict": "", "undercoverage_response": "", "undercoverage_subfamily": "", "undercoverage_failure_observed": "",
            "failure_attribution": "none", "incident_evidence_status": "not_applicable",
    }])
    out = tmp_path / "out"
    materialize_quality(canonical, out, candidate_inventory_csv=None)
    quality = _rows(out / "c1_quality_annotations.csv")[0]
    worker = tmp_path / "worker.csv"
    _csv(worker, ["worker_id"], [{"worker_id": "w1"}])
    materialize_sidecar(out / "c1_quality_annotations.csv", worker, out)
    evidence = [row for row in _rows(out / "worker_task_evidence_table_C1.csv") if row["task_id"] == "t1"]

    assert quality["task_final_scope"] == ""
    assert quality["process_evaluable"] == "true"
    assert quality["family"] == "semi_correction_failure"
    assert {row["evidence_signal"] for row in evidence} == {"semi_issue_recognition", "semi_geometry_correction"}
    assert any(row["included_in_T_u"] == "true" and row["response_type"] == "successful_correction" for row in evidence)


def test_c2b_task_shortage_has_no_assignment_manifest_rows(tmp_path: Path) -> None:
    pool = tmp_path / "pool.csv"
    worker = tmp_path / "worker.csv"
    _csv(pool, ["task_id", "anchor_eligible", "bridge_eligible", "task_stratum"], [{"task_id": "a1", "anchor_eligible": "true", "bridge_eligible": "false", "task_stratum": "ordinary"}])
    _csv(worker, ["worker_id", "support", "ci_half_width"], [{"worker_id": "w1", "support": "10", "ci_half_width": "0.1"}])
    design = tmp_path / "design.json"
    design.write_text(json.dumps({
        "manifest_version": "c2_design_v1",
        "input_sha256": {
            "worker_profile_csv": __import__("hashlib").sha256(worker.read_bytes()).hexdigest(),
            "task_pool_csv": __import__("hashlib").sha256(pool.read_bytes()).hexdigest(),
        },
        "c2b_target_ci_half_width": 0.2,
        "candidate_designs": [{"design_id": "d1", "common_anchor_count": 1, "bridge_per_worker": 1, "unique_bridge_tasks": 1, "min_task_support": 1}],
    }), encoding="utf-8")
    summary = materialize_c2(pool, worker, design, tmp_path / "out")
    assert summary["c2b_design_ready"] is False
    assert _rows(tmp_path / "out" / "assignment_manifest_C2B.csv") == []
