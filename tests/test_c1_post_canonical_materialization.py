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
        "used_for_r_u",
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
                "used_for_r_u": "true",
            },
            {
                "round_id": "C1",
                "task_id": "c1",
                "base_task_id": "scene_b",
                "dataset_group": "Calibration_core",
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
                "used_for_r_u": "false_non_reliability_core",
            },
            {
                "round_id": "C1",
                "task_id": "s1",
                "base_task_id": "scene_s",
                "dataset_group": "Calibration_semi",
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
                "used_for_r_u": "",
            },
        ],
    )

    out = tmp_path / "out"
    quality_summary = materialize_quality(canonical, out)
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
