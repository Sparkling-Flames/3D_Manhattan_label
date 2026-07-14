from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.thesis_main.analysis.run_c1_closeout_dryrun_chain import build_gate_summary, materialize


def _csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _rows(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.open(encoding="utf-8")))


def _inputs(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    canonical = tmp_path / "c1_canonical_annotations.csv"
    assignment = tmp_path / "assignment.csv"
    reserve = tmp_path / "reserve.csv"
    inventory = tmp_path / "inventory.csv"
    _csv(
        canonical,
        [
            "round_id",
            "task_id",
            "base_task_id",
            "dataset_group",
            "scene_label",
            "condition",
            "worker_id",
            "canonical_annotation_id",
            "scope",
            "n_corners",
            "geometry_hash",
            "active_time_source",
            "primary_active_time_eligible",
            "assigned_expected",
        ],
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
                "n_corners": "4",
                "geometry_hash": "h1",
                "active_time_source": "log",
                "primary_active_time_eligible": "true",
                "assigned_expected": "true",
            }
        ],
    )
    _csv(
        assignment,
        ["round_id", "worker_id", "task_id", "base_task_id", "dataset_group"],
        [{"round_id": "C1", "worker_id": "w1", "task_id": "a1", "base_task_id": "scene_a", "dataset_group": "Calibration_anchor"}],
    )
    _csv(
        reserve,
        ["task_id", "base_task_id", "dataset_group", "calibration_split"],
        [{"task_id": "r1", "base_task_id": "reserve_scene", "dataset_group": "Calibration_reserve", "calibration_split": "reserve"}],
    )
    _csv(inventory, ["task_id", "base_task_id", "calibration_split", "used_for_r_u"], [])
    return canonical, assignment, reserve, inventory


def test_dryrun_chain_generates_provisional_summary_and_blocks_c2_draft(tmp_path: Path) -> None:
    canonical, assignment, reserve, inventory = _inputs(tmp_path)
    out = tmp_path / "out"
    c2 = tmp_path / "c2"

    summary = materialize(canonical, assignment, reserve, out, c2, inventory, 2, 1, 2, 0.15, 1)
    summary_json = json.loads((out / "c1_closeout_dryrun_gate_summary.json").read_text(encoding="utf-8"))
    md = (out / "c1_closeout_dryrun_gate_summary.md").read_text(encoding="utf-8")

    assert summary["passed"] is False
    assert summary["raw_pipeline_ready"] is False
    assert summary["provisional_sidecar_ready"] is False
    assert summary["structural_contract_valid"] is False
    assert summary["formal_inputs_present"] is False
    assert summary["artifacts_fresh"] is False
    assert summary["formal_closeout_ready"] is False
    assert summary["thesis_facing_closeout_ready"] is False
    assert summary["c2_decision_chain_ready"] is False
    assert summary["p1_descriptive_directional_check_status"] == "not_evaluable"
    assert summary["formal_predictive_validity_status"] == "not_run_blocked"
    assert summary_json["profile_sidecar_generated"] is True
    assert summary["analysis_contract_ready"] is False
    assert summary["formal_c1_annotation_data_present"] is False
    assert summary["dry_run_is_formal_data"] is False
    assert summary["vfinal_sidecars"]["routing_replay_scaffold"]["formal_assignment_generated"] is False
    assert (out / "worker_scene_profile_candidates_C1.csv").exists()
    assert (out / "routing_evidence_snapshot_C1.csv").exists()
    assert (out / "routing_replay_scaffold_C1.csv").exists()
    assert (out / "c1_closeout_input_bundle.json").exists()
    assert (out / "worker_profile_sidecar_C1.summary.json").exists()
    assert "# C1 Closeout Dryrun Gate Summary" in md
    assert not (c2 / "assignment_manifest_C2_draft.csv").exists()


def test_dryrun_chain_passes_p1_artifacts_read_only_to_sidecar(tmp_path: Path) -> None:
    canonical, assignment, reserve, inventory = _inputs(tmp_path)
    p1 = tmp_path / "p1_artifact.csv"
    _csv(p1, ["worker_id", "r_u_0"], [{"worker_id": "w1", "r_u_0": "0.9"}])

    summary = materialize(canonical, assignment, reserve, tmp_path / "out", tmp_path / "c2", inventory, 2, 1, 2, 0.15, 1, [p1])
    sidecar_summary = summary["worker_profile_sidecar_summary"]

    assert sidecar_summary["input_p1_artifacts"] == [str(p1)]
    assert summary["p1_descriptive_directional_check_status"] == sidecar_summary["p1_descriptive_directional_check_status"]


def test_quality_table_blocker_blocks_launch(tmp_path: Path) -> None:
    canonical, assignment, reserve, inventory = _inputs(tmp_path)
    _csv(
        canonical,
        ["round_id", "task_id", "base_task_id", "dataset_group", "condition", "worker_id", "canonical_annotation_id", "n_corners", "geometry_hash", "assigned_expected"],
        [
            {
                "round_id": "C1",
                "task_id": "c1",
                "base_task_id": "scene_c",
                "dataset_group": "Calibration_core",
                "condition": "manual",
                "worker_id": "w1",
                "canonical_annotation_id": "cc1",
                "n_corners": "4",
                "geometry_hash": "h",
                "assigned_expected": "true",
            }
        ],
    )

    summary = materialize(canonical, assignment, reserve, tmp_path / "out", tmp_path / "c2", inventory, 1, 1, 1, 0.15, 1)

    assert summary["blocked_for_launch"] is True
    assert "quality_table_blockers" in summary["blockers"]


def test_c2_materialization_is_blocked_before_capacity_evaluation(tmp_path: Path) -> None:
    canonical, assignment, reserve, inventory = _inputs(tmp_path)

    summary = materialize(canonical, assignment, reserve, tmp_path / "out", tmp_path / "c2", inventory, 3, 2, 3, 0.15, 1)

    assert summary["c2_draft_summary"]["materialization_blocked"] is True
    assert summary["blocked_for_launch"] is True
    assert "c2_decision_chain_blocked_pending_formal_closeout" in summary["blockers"]


def test_gate_blocks_formal_closeout_even_when_c2_inputs_are_present(tmp_path: Path) -> None:
    summary = build_gate_summary(
        {"blockers": [], "r_u_estimated": False, "dt_backflow": False},
        {"r_u_estimated": False, "provisional": True},
        {"direct_assignment": False},
        {"reserve_only": False, "reserve_capacity_shortfall_count": 0},
        {"profile_freeze_status": "C1_provisional", "warnings": []},
        tmp_path,
    )

    assert summary["blocked_for_launch"] is True
    assert "c2_decision_chain_blocked_pending_formal_closeout" in summary["blockers"]


def test_gate_blocks_when_profile_sidecar_missing_or_not_provisional(tmp_path: Path) -> None:
    missing = build_gate_summary(
        {"blockers": [], "r_u_estimated": False, "dt_backflow": False},
        {"r_u_estimated": False, "provisional": True},
        {"direct_assignment": False},
        {"reserve_only": True, "reserve_capacity_shortfall_count": 0},
        {},
        tmp_path / "missing.json",
    )
    bad_status_path = tmp_path / "profile.json"
    bad_status_path.write_text("{}", encoding="utf-8")
    bad_status = build_gate_summary(
        {"blockers": [], "r_u_estimated": False, "dt_backflow": False},
        {"r_u_estimated": False, "provisional": True},
        {"direct_assignment": False},
        {"reserve_only": True, "reserve_capacity_shortfall_count": 0},
        {"profile_freeze_status": "C2_final", "warnings": []},
        bad_status_path,
    )

    assert missing["blocked_for_launch"] is True
    assert "profile_sidecar_missing" in missing["blockers"]
    assert bad_status["blocked_for_launch"] is True
    assert "profile_prepare_status_not_C1_provisional" in bad_status["blockers"]
