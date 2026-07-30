from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from tools.thesis_main.analysis.materialize_w034_authorized_extension_sensitivity import materialize as materialize_w034
from tools.thesis_main.analysis.paper_a_contracts import METHOD_CONTRACT, load_method_contract, sha256_file
from tools.thesis_main.analysis.run_c1_closeout_launch import _snapshot_dependencies, bind_c2b_runtime_mapping, design_c2b, freeze_c1_batch


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]) if rows else ["status"])
        writer.writeheader(); writer.writerows(rows)


def _batch_scope() -> dict[str, object]:
    return {
        "schema_version": "paper_a_c1_batch_scope_v1", "batch_id": "C1_A",
        "data_cutoff_server_time": "2026-07-30T00:00:00Z", "original_worker_ids": ["W001"],
        "authorized_repair_identities": {
            "w034": [{"worker_id": "W034", "base_task_id": f"w034-{index}", "condition": "manual"} for index in range(17)],
            "w001": [{"worker_id": "W001", "base_task_id": f"w001-{index}", "condition": "manual"} for index in range(3)],
        },
        "original_completion_exception_task_ids": [],
    }


def _batch_artifacts(root: Path, *, w034_status: str = "frozen") -> None:
    root.mkdir()
    _write_csv(root / "c1_three_track_worker_state.csv", [
        {"worker_id": "W001", "enrollment_batch": "original", "c2_risk_model_eligible": "true"},
        {"worker_id": "W034", "enrollment_batch": "original", "c2_risk_model_eligible": "true"},
    ])
    tasks = [f"w034-{index}" for index in range(17)] + [f"w001-{index}" for index in range(3)]
    _write_csv(root / "c1_row_analysis_eligibility.csv", [
        {"task_id": task, "canonical_annotation_id": f"annotation-{task}", "base_task_id": task,
         "worker_id": "W034" if task.startswith("w034-") else "W001", "condition": "manual",
         "assignment_provenance": "authorized_replacement_assignment", "formal_assignment_eligible": "true"}
        for task in tasks
    ])
    for name in (
        "analysis_dependency_manifest.json", "c1_estimand_specific_task_support.csv", "geometry_worker_task_peer_analysis.csv",
        "geometry_worker_task_loo_analysis.csv", "c1_task_adjusted_qgt_model_audit.json", "c1_gt_quality_analysis.csv", "structural_validation_analysis.csv", "c1_structural_reliability_eb.csv",
        "c1_worker_completion_audit.csv", "c1_task_outcome_reference.csv", "c1_task_building_binding.csv",
    ):
        (root / name).write_text("{}" if name.endswith(".json") else "status\nok\n", encoding="utf-8")
    (root / "c1_measurement_freeze_manifest.json").write_text(json.dumps({"C1_CANONICAL_CLOSED": True}), encoding="utf-8")
    (root / "w034_original_vs_authorized_sensitivity.json").write_text(json.dumps({"status": w034_status}), encoding="utf-8")


def test_c1_a_snapshot_is_formal_without_global_enrollment_close(tmp_path: Path) -> None:
    c1_dir = tmp_path / "c1"; _batch_artifacts(c1_dir)
    scope = tmp_path / "scope.json"; scope.write_text(json.dumps(_batch_scope()), encoding="utf-8")
    output = tmp_path / "c1_a_analysis_snapshot.json"
    result = freeze_c1_batch(type("Args", (), {"c1_output_dir": c1_dir, "batch_scope_manifest": scope, "output": output})())
    assert result["status"] == "formal_design_eligible"
    assert result["C2B_DESIGN_INPUT_FROZEN_FROM_C1_A"] is True
    assert result["CALIBRATION_ENROLLMENT_CLOSED"] is False
    assert result["FINAL_POOLED_PROFILE_FROZEN"] is False


def test_c1_a_snapshot_stays_provisional_when_w034_repairs_are_not_frozen(tmp_path: Path) -> None:
    c1_dir = tmp_path / "c1"; _batch_artifacts(c1_dir, w034_status="pending_authorized_completion")
    scope = tmp_path / "scope.json"; scope.write_text(json.dumps(_batch_scope()), encoding="utf-8")
    result = freeze_c1_batch(type("Args", (), {"c1_output_dir": c1_dir, "batch_scope_manifest": scope, "output": tmp_path / "snapshot.json"})())
    assert result["status"] == "provisional"
    assert "w034_sensitivity_not_frozen" in result["blockers"]


def test_c1_a_snapshot_keeps_w011_completion_exception_visible(tmp_path: Path) -> None:
    c1_dir = tmp_path / "c1"; _batch_artifacts(c1_dir)
    scope_data = _batch_scope() | {"original_completion_exception_task_ids": ["w011-missing"]}
    scope = tmp_path / "scope.json"; scope.write_text(json.dumps(scope_data), encoding="utf-8")
    result = freeze_c1_batch(type("Args", (), {"c1_output_dir": c1_dir, "batch_scope_manifest": scope, "output": tmp_path / "snapshot.json"})())
    assert result["status"] == "provisional"
    assert "original_completion_exception_missing:w011-missing" in result["blockers"]


def test_authorized_repair_requires_exact_worker_task_and_condition_identity(tmp_path: Path) -> None:
    c1_dir = tmp_path / "c1"; _batch_artifacts(c1_dir)
    scope = tmp_path / "scope.json"; scope.write_text(json.dumps(_batch_scope()), encoding="utf-8")
    rows = list(csv.DictReader((c1_dir / "c1_row_analysis_eligibility.csv").open(encoding="utf-8")))
    rows[0]["worker_id"] = "W999"
    _write_csv(c1_dir / "c1_row_analysis_eligibility.csv", rows)
    result = freeze_c1_batch(type("Args", (), {"c1_output_dir": c1_dir, "batch_scope_manifest": scope, "output": tmp_path / "snapshot.json"})())
    assert result["status"] == "provisional"
    assert any(item.startswith("authorized_repair_identity_unresolved:w034:W034:w034-0:manual") for item in result["blockers"])
    rows[0]["worker_id"] = "W034"; rows[0]["condition"] = "semi"
    _write_csv(c1_dir / "c1_row_analysis_eligibility.csv", rows)
    result = freeze_c1_batch(type("Args", (), {"c1_output_dir": c1_dir, "batch_scope_manifest": scope, "output": tmp_path / "snapshot-2.json"})())
    assert result["status"] == "provisional"
    assert any(item.startswith("authorized_repair_identity_unresolved:w034:W034:w034-0:manual") for item in result["blockers"])


def test_repair_scope_cannot_relabel_another_worker_as_w034(tmp_path: Path) -> None:
    c1_dir = tmp_path / "c1"; _batch_artifacts(c1_dir)
    scope_data = _batch_scope()
    scope_data["authorized_repair_identities"]["w034"][0]["worker_id"] = "W999"
    scope = tmp_path / "scope.json"; scope.write_text(json.dumps(scope_data), encoding="utf-8")
    with pytest.raises(ValueError, match="w034 repair identities"):
        freeze_c1_batch(type("Args", (), {"c1_output_dir": c1_dir, "batch_scope_manifest": scope, "output": tmp_path / "snapshot.json"})())


def test_snapshot_dependencies_are_path_bound_after_snapshot_move(tmp_path: Path) -> None:
    dependency = tmp_path / "c1" / "profile.csv"; dependency.parent.mkdir(); dependency.write_text("worker_id\nW001\n", encoding="utf-8")
    snapshot = {"dependencies": [{"role": "WORKER_PROFILE", "path": str(dependency.resolve()), "sha256": sha256_file(dependency)}]}
    assert _snapshot_dependencies(snapshot, "WORKER_PROFILE")["WORKER_PROFILE"] == dependency
    dependency.write_text("worker_id\nW001\nW034\n", encoding="utf-8")
    with pytest.raises(ValueError, match="stale or unavailable:WORKER_PROFILE"):
        _snapshot_dependencies(snapshot, "WORKER_PROFILE")


def test_design_reads_sha_bound_snapshot_dependencies_not_snapshot_parent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "c1_source"; source.mkdir()
    roles = ("WORKER_PROFILE", "COMPLETION", "Q_GT", "STRUCTURAL_EB", "MEASUREMENT_READINESS", "CANONICAL_ELIGIBILITY", "REFERENCE", "BUILDING")
    dependencies = []
    for role in roles:
        path = source / f"{role}.csv"; path.write_text("evidence\nok\n", encoding="utf-8")
        dependencies.append({"role": role, "path": str(path.resolve()), "sha256": sha256_file(path)})
    method = load_method_contract()
    snapshot = tmp_path / "moved_snapshot" / "c1_a_analysis_snapshot.json"; snapshot.parent.mkdir()
    snapshot.write_text(json.dumps({
        "schema_version": "paper_a_c1_batch_analysis_snapshot_v1", "status": "formal_design_eligible",
        "method_contract_version": method["contract_version"], "method_contract_sha256": sha256_file(METHOD_CONTRACT),
        "C2B_DESIGN_INPUT_FROZEN_FROM_C1_A": True, "dependencies": dependencies,
    }), encoding="utf-8")
    monkeypatch.setattr("tools.thesis_main.analysis.run_c1_closeout_launch.formal_git_state", lambda _root: {"clean": True, "git_commit_sha": "a" * 40})
    monkeypatch.setattr("tools.thesis_main.analysis.run_c1_closeout_launch._materialize_c2b_evidence_envelope", lambda _args: {"C2B_EVIDENCE_FROZEN": False})
    result = design_c2b(type("Args", (), {"c1_closeout_summary": snapshot})())
    assert result["blockers"] == ["c2b_evidence_freeze_envelope_incomplete"]
    source.joinpath("Q_GT.csv").write_text("changed\n", encoding="utf-8")
    with pytest.raises(ValueError, match="stale or unavailable:Q_GT"):
        design_c2b(type("Args", (), {"c1_closeout_summary": snapshot})())


def test_w034_sensitivity_preserves_pending_and_partial_states(tmp_path: Path) -> None:
    rows = [{"worker_id": "34", "Q_GT_EB": ".7", "R_peer_all": ".8", "F_struct_EB": ".1", "task_support": "5"}]
    original, augmented = tmp_path / "original.csv", tmp_path / "augmented.csv"
    _write_csv(original, rows); _write_csv(augmented, rows)
    thresholds = tmp_path / "thresholds.json"; thresholds.write_text(json.dumps({"maximum_rank_displacement": 1, "maximum_absolute_metric_change": .1, "version": "v1"}), encoding="utf-8")
    pending = materialize_w034(original, augmented, thresholds, tmp_path / "pending.json", status="pending_authorized_completion", authorized_completed_count=0)
    partial = materialize_w034(original, augmented, thresholds, tmp_path / "partial.json", status="provisional_augmented", authorized_completed_count=4)
    assert pending["status"] == "pending_authorized_completion"
    assert partial["status"] == "provisional_augmented"


def test_runtime_mapping_binds_only_the_frozen_batch_and_design(tmp_path: Path) -> None:
    method = load_method_contract(); design_sha = "d" * 64
    report = tmp_path / "launch.json"; report.write_text(json.dumps({
        "contract_role": "generated_subordinate", "method_contract_version": method["contract_version"],
        "method_contract_sha256": sha256_file(METHOD_CONTRACT), "assignment_batch_id": "C2B_BATCH_A",
        "selected_design_sha": design_sha,
    }), encoding="utf-8")
    distribution = tmp_path / "distribution.csv"; _write_csv(distribution, [{"worker_id": "W001", "task_id": "planned-1"}])
    planned = tmp_path / "planned.json"; planned.write_text(json.dumps([{"data": {"planned_task_id": "planned-1"}}]), encoding="utf-8")
    runtime = tmp_path / "runtime.json"; runtime.write_text(json.dumps([{"id": 7, "data": {"planned_task_id": "planned-1", "c2b_batch_id": "C2B_BATCH_A", "selected_design_sha": design_sha}}]), encoding="utf-8")
    result = bind_c2b_runtime_mapping(type("Args", (), {"launch_report": report, "worker_distribution": distribution, "planned_import": planned, "runtime_export": runtime, "output_dir": tmp_path / "out"})())
    assert result["one_to_one"] is True
    assert (tmp_path / "out" / "c2b_runtime_task_mapping.csv").is_file()
