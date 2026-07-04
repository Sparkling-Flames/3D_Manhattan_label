from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.thesis_main.analysis.build_c2_assignment_manifest_from_c1_gaps import materialize as materialize_c2
from tools.thesis_main.analysis.c1_materialize_c2_gap_audits import materialize as materialize_gaps
from tools.thesis_main.analysis.c1_materialize_quality_table import materialize as materialize_quality
from tools.thesis_main.analysis.c1_materialize_worker_state import materialize as materialize_worker_state


def _csv(path: Path, fields: list[str], rows: list[dict]) -> None:
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
    assert worker["n_calib_completed"] == "1"
    assert worker["needs_c2_ci_fill"] == "true"

    gap_summary = materialize_gaps(out / "c1_quality_annotations.csv", out / "worker_state_snapshot_C1.csv", out, min_scene=1, min_calib=2, epsilon_r=0.15)
    assert gap_summary["direct_assignment"] is False
    assert _rows(out / "ci_precision_audit_C1.csv")[0]["needs_c2_ci_fill"] == "true"
    assert any(row["needs_c2_scene_fill"] == "true" for row in _rows(out / "scene_coverage_gap_C1.csv"))

    reserve = tmp_path / "reserve.csv"
    _csv(
        reserve,
        ["task_id", "base_task_id", "dataset_group", "calibration_split"],
        [{"task_id": "r1", "base_task_id": "reserve_scene", "dataset_group": "Calibration_reserve", "calibration_split": "reserve"}],
    )
    c2_summary = materialize_c2(reserve, out / "ci_precision_audit_C1.csv", out / "scene_coverage_gap_C1.csv", tmp_path / "c2", tasks_per_fill=1)
    manifest = _rows(tmp_path / "c2" / "assignment_manifest_C2_draft.csv")
    audit = _rows(tmp_path / "c2" / "reserve_usage_audit_C2_draft.csv")
    assert c2_summary["reserve_only"] is True
    assert {row["dataset_group"] for row in manifest} == {"Calibration_reserve"}
    assert {row["reserve_misuse_flag"] for row in audit} == {"false"}


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
    assert summary["blockers"] == []


def test_missing_scene_label_does_not_fallback_to_base_task(tmp_path: Path) -> None:
    quality = tmp_path / "quality.csv"
    worker = tmp_path / "worker.csv"
    _csv(
        quality,
        ["worker_id", "task_id", "base_task_id", "dataset_group", "used_for_r_u"],
        [{"worker_id": "w1", "task_id": "t1", "base_task_id": "base_is_not_scene", "dataset_group": "Calibration_core", "used_for_r_u": "true"}],
    )
    _csv(worker, ["worker_id", "n_calib_completed", "needs_c2_ci_fill", "r_u_ci_low", "r_u_ci_high", "r_u_h"], [{"worker_id": "w1", "n_calib_completed": "5", "needs_c2_ci_fill": "false", "r_u_ci_low": "", "r_u_ci_high": "", "r_u_h": ""}])

    summary = materialize_gaps(quality, worker, tmp_path / "out", min_scene=1, min_calib=5, epsilon_r=0.15)
    scene = _rows(tmp_path / "out" / "scene_coverage_gap_C1.csv")[0]

    assert summary["n_scene_fill_cells"] == 0
    assert scene["scene_gap_evaluable"] == "false"
    assert scene["needs_c2_scene_fill"] == "false"
    assert scene["scene_fill_reason"] == "scene_label_missing"


def test_empty_ci_is_not_formal_precision_failure_when_count_sufficient(tmp_path: Path) -> None:
    quality = tmp_path / "quality.csv"
    worker = tmp_path / "worker.csv"
    _csv(quality, ["worker_id", "scene_label", "used_for_r_u"], [{"worker_id": "w1", "scene_label": "room", "used_for_r_u": "true"}])
    _csv(worker, ["worker_id", "n_calib_completed", "needs_c2_ci_fill", "r_u_ci_low", "r_u_ci_high", "r_u_h"], [{"worker_id": "w1", "n_calib_completed": "5", "needs_c2_ci_fill": "false", "r_u_ci_low": "", "r_u_ci_high": "", "r_u_h": ""}])

    materialize_gaps(quality, worker, tmp_path / "out", min_scene=1, min_calib=5, epsilon_r=0.15)
    ci = _rows(tmp_path / "out" / "ci_precision_audit_C1.csv")[0]

    assert ci["ci_evaluable"] == "false"
    assert ci["needs_c2_ci_fill"] == "false"
    assert ci["ci_fill_reason"] == "not_evaluable_without_r_u_estimate"


def test_c2_draft_reports_reserve_capacity_shortfall_without_reuse(tmp_path: Path) -> None:
    reserve = tmp_path / "reserve.csv"
    ci = tmp_path / "ci.csv"
    scene = tmp_path / "scene.csv"
    _csv(reserve, ["task_id", "base_task_id", "dataset_group", "calibration_split"], [{"task_id": "r1", "base_task_id": "rb1", "dataset_group": "Calibration_reserve", "calibration_split": "reserve"}])
    _csv(ci, ["worker_id", "needs_c2_ci_fill", "ci_fill_reason"], [{"worker_id": "w1", "needs_c2_ci_fill": "true", "ci_fill_reason": "count"}])
    _csv(
        scene,
        ["worker_id", "scene_label", "needs_c2_scene_fill", "scene_fill_reason"],
        [{"worker_id": "w1", "scene_label": "room", "needs_c2_scene_fill": "true", "scene_fill_reason": "gap"}],
    )

    summary = materialize_c2(reserve, ci, scene, tmp_path / "out", tasks_per_fill=1)
    manifest = _rows(tmp_path / "out" / "assignment_manifest_C2_draft.csv")
    audit = _rows(tmp_path / "out" / "reserve_usage_audit_C2_draft.csv")
    worker_task_keys = {(row["worker_id"], row["task_id"], row["base_task_id"]) for row in manifest}

    assert len(worker_task_keys) == len(manifest) == 1
    assert summary["reserve_capacity_shortfall_count"] == 1
    assert any(row["reserve_capacity_shortfall"] == "1" for row in audit)
