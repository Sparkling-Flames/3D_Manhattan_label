from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from tools.thesis_main.analysis.materialize_w034_authorized_extension_sensitivity import materialize as materialize_w034
from tools.thesis_main.analysis.paper_a_contracts import METHOD_CONTRACT, load_method_contract, sha256_file
from tools.thesis_main.analysis.run_c1_closeout_launch import _addendum_row_sha256, _snapshot_dependencies, bind_c2b_runtime_mapping, design_c2b, freeze_c1_batch
from tools.thesis_main.analysis.worker_identity import normalize_worker_id


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]) if rows else ["status"])
        writer.writeheader(); writer.writerows(rows)


def _batch_scope() -> dict[str, object]:
    return {
        "schema_version": "paper_a_c1_batch_scope_v1", "batch_id": "C1_A",
        "data_cutoff_server_time": "2026-07-30T00:00:00Z", "original_worker_ids": ["W001", "W034"],
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
        "c1_task_outcome_reference.csv", "c1_task_building_binding.csv",
    ):
        (root / name).write_text("{}" if name.endswith(".json") else "status\nok\n", encoding="utf-8")
    _write_csv(root / "c1_task_scope_final_disposition.csv", [
        {"base_task_id": task, "task_final_scope": "in_scope", "scope_resolution_status": "resolved"}
        for task in tasks
    ])
    _write_csv(root / "c1_worker_completion_audit.csv", [
        {"worker_id": "W001", "completion_status": "completed"},
        {"worker_id": "W034", "completion_status": "completed"},
    ])
    _write_csv(root / "c1_measurement_readiness_by_worker.csv", [
        {"worker_id": "W001", "Q_GT_support": "1"}, {"worker_id": "W034", "Q_GT_support": "1"},
    ])
    (root / "c1_measurement_freeze_manifest.json").write_text(json.dumps({"C1_CANONICAL_CLOSED": True}), encoding="utf-8")
    (root / "w034_original_vs_authorized_sensitivity.json").write_text(json.dumps({"status": w034_status}), encoding="utf-8")


def test_c1_a_snapshot_is_formal_without_global_enrollment_close(tmp_path: Path) -> None:
    c1_dir = tmp_path / "c1"; _batch_artifacts(c1_dir)
    (c1_dir / "c1_measurement_freeze_manifest.json").write_text(json.dumps({"C1_CANONICAL_CLOSED": False}), encoding="utf-8")
    scope = tmp_path / "scope.json"; scope.write_text(json.dumps(_batch_scope()), encoding="utf-8")
    output = tmp_path / "c1_a_analysis_snapshot.json"
    result = freeze_c1_batch(type("Args", (), {"c1_output_dir": c1_dir, "batch_scope_manifest": scope, "output": output})())
    assert result["status"] == "formal_design_eligible"
    assert result["C2B_DESIGN_INPUT_FROZEN_FROM_C1_A"] is True
    assert result["CALIBRATION_ENROLLMENT_CLOSED"] is False
    assert result["FINAL_POOLED_PROFILE_FROZEN"] is False


def test_c1_a_snapshot_scopes_out_late_entry_inputs(tmp_path: Path) -> None:
    c1_dir = tmp_path / "c1"; _batch_artifacts(c1_dir)
    profile = list(csv.DictReader((c1_dir / "c1_three_track_worker_state.csv").open(encoding="utf-8")))
    profile.append({"worker_id": "W099", "enrollment_batch": "late_entry", "c2_risk_model_eligible": "true"})
    _write_csv(c1_dir / "c1_three_track_worker_state.csv", profile)
    readiness = list(csv.DictReader((c1_dir / "c1_measurement_readiness_by_worker.csv").open(encoding="utf-8")))
    readiness.append({"worker_id": "W099", "Q_GT_support": "9"})
    _write_csv(c1_dir / "c1_measurement_readiness_by_worker.csv", readiness)
    scope = tmp_path / "scope.json"; scope.write_text(json.dumps(_batch_scope()), encoding="utf-8")
    result = freeze_c1_batch(type("Args", (), {"c1_output_dir": c1_dir, "batch_scope_manifest": scope, "output": tmp_path / "snapshot.json"})())
    assert result["status"] == "formal_design_eligible"
    assert result["excluded_late_entry_worker_ids"] == ["99"]


def test_c1_a_snapshot_requires_the_exact_original_roster_and_preserves_task_level_k(tmp_path: Path) -> None:
    c1_dir = tmp_path / "c1"; _batch_artifacts(c1_dir)
    support = c1_dir / "c1_estimand_specific_task_support.csv"
    _write_csv(support, [{"base_task_id": "b1", "condition": "manual", "k_final_GT": "3", "k_final_peer": "3", "k_final_structural": "3", "k_final_LOO_medoid": "2", "k_final_LOO_strict": "2", "k_final_time": "3"}])
    scope = _batch_scope(); scope["original_worker_ids"] = ["W001"]
    scope_path = tmp_path / "scope.json"; scope_path.write_text(json.dumps(scope), encoding="utf-8")
    result = freeze_c1_batch(type("Args", (), {"c1_output_dir": c1_dir, "batch_scope_manifest": scope_path, "output": tmp_path / "snapshot.json"})())
    assert result["status"] == "provisional"
    assert any(blocker.startswith("original_roster_scope_mismatch") for blocker in result["blockers"])
    scope["original_worker_ids"] = ["W001", "W034"]
    scope_path.write_text(json.dumps(scope), encoding="utf-8")
    result = freeze_c1_batch(type("Args", (), {"c1_output_dir": c1_dir, "batch_scope_manifest": scope_path, "output": tmp_path / "snapshot.json"})())
    variable_k = _snapshot_dependencies(result, "VARIABLE_K")["VARIABLE_K"]
    assert list(csv.DictReader(variable_k.open(encoding="utf-8")))[0]["k_final_GT"] == "3"


def test_worker_id_formats_are_normalized_across_scope_and_eligibility(tmp_path: Path) -> None:
    assert normalize_worker_id("W034") == "34"
    assert normalize_worker_id("034") == "34"
    assert normalize_worker_id("34") == "34"
    c1_dir = tmp_path / "c1"; _batch_artifacts(c1_dir)
    for path in (c1_dir / "c1_three_track_worker_state.csv", c1_dir / "c1_row_analysis_eligibility.csv"):
        rows = list(csv.DictReader(path.open(encoding="utf-8")))
        for row in rows:
            if row.get("worker_id") == "W034": row["worker_id"] = "034"
            if row.get("worker_id") == "W001": row["worker_id"] = "001"
        _write_csv(path, rows)
    scope = tmp_path / "scope.json"; scope.write_text(json.dumps(_batch_scope()), encoding="utf-8")
    result = freeze_c1_batch(type("Args", (), {"c1_output_dir": c1_dir, "batch_scope_manifest": scope, "output": tmp_path / "snapshot.json"})())
    assert result["status"] == "formal_design_eligible"


def test_c1_a_snapshot_stays_provisional_when_w034_repairs_are_not_frozen(tmp_path: Path) -> None:
    c1_dir = tmp_path / "c1"; _batch_artifacts(c1_dir, w034_status="pending_authorized_completion")
    scope = tmp_path / "scope.json"; scope.write_text(json.dumps(_batch_scope()), encoding="utf-8")
    result = freeze_c1_batch(type("Args", (), {"c1_output_dir": c1_dir, "batch_scope_manifest": scope, "output": tmp_path / "snapshot.json"})())
    assert result["status"] == "provisional"
    assert "w034_sensitivity_not_frozen" in result["blockers"]


def test_c1_a_snapshot_requires_terminal_scope_disposition(tmp_path: Path) -> None:
    c1_dir = tmp_path / "c1"; _batch_artifacts(c1_dir)
    scope_rows = list(csv.DictReader((c1_dir / "c1_task_scope_final_disposition.csv").open(encoding="utf-8")))
    scope_rows[0]["scope_resolution_status"] = "pending"
    _write_csv(c1_dir / "c1_task_scope_final_disposition.csv", scope_rows)
    scope = tmp_path / "scope.json"; scope.write_text(json.dumps(_batch_scope()), encoding="utf-8")
    result = freeze_c1_batch(type("Args", (), {"c1_output_dir": c1_dir, "batch_scope_manifest": scope, "output": tmp_path / "snapshot.json"})())
    assert result["status"] == "provisional"
    assert "c1_a_scope_not_terminal:w034-0" in result["blockers"]


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
    assert any(item.startswith("authorized_repair_identity_unresolved:w034:34:w034-0:manual") for item in result["blockers"])
    rows[0]["worker_id"] = "W034"; rows[0]["condition"] = "semi"
    _write_csv(c1_dir / "c1_row_analysis_eligibility.csv", rows)
    result = freeze_c1_batch(type("Args", (), {"c1_output_dir": c1_dir, "batch_scope_manifest": scope, "output": tmp_path / "snapshot-2.json"})())
    assert result["status"] == "provisional"
    assert any(item.startswith("authorized_repair_identity_unresolved:w034:34:w034-0:manual") for item in result["blockers"])


def test_authorized_addendum_uses_replacement_worker_id(tmp_path: Path) -> None:
    c1_dir = tmp_path / "c1"; _batch_artifacts(c1_dir)
    scope_data = _batch_scope()
    addendum_rows = []
    for group in ("w034", "w001"):
        for index, entry in enumerate(scope_data["authorized_repair_identities"][group], start=1):
            row = {
                "replacement_worker_id": entry["worker_id"], "base_task_id": entry["base_task_id"], "condition": entry["condition"],
                "authorized_addendum_row_identity": f"{group}-{index}",
            }
            entry["authorized_addendum_row_identity"] = row["authorized_addendum_row_identity"]
            entry["authorized_addendum_row_sha256"] = _addendum_row_sha256(row)
            addendum_rows.append(row)
    addendum = tmp_path / "authorized.csv"; _write_csv(addendum, addendum_rows)
    scope = tmp_path / "scope.json"; scope.write_text(json.dumps(scope_data), encoding="utf-8")
    result = freeze_c1_batch(type("Args", (), {"c1_output_dir": c1_dir, "batch_scope_manifest": scope, "authorized_reassignment_manifest": addendum, "output": tmp_path / "snapshot.json"})())
    assert result["authorized_repair_set"]["expected_count"] == 20
    assert len(result["authorized_repair_set"]["resolved_canonical_annotation_ids"]) == 20
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
    roles = ("WORKER_PROFILE", "COMPLETION", "Q_GT", "STRUCTURAL_EB", "MEASUREMENT_READINESS", "CANONICAL_ELIGIBILITY", "REFERENCE", "SCOPE_FINAL_DISPOSITION", "BUILDING")
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
    assignment = tmp_path / "assignment.csv"; _write_csv(assignment, [{"worker_id": "W001", "task_id": "planned-1"}])
    private = tmp_path / "worker_facing_distribution_C2B"; private.mkdir()
    _write_csv(private / "worker_001_C2B.csv", [{"worker_id": "W001", "task_id": "planned-1"}])
    planned = tmp_path / "planned.json"; planned.write_text(json.dumps([{"data": {"planned_task_id": "planned-1"}}]), encoding="utf-8")
    runtime = tmp_path / "runtime.json"; runtime.write_text(json.dumps([{"id": 7, "data": {"planned_task_id": "planned-1", "c2b_batch_id": "C2B_BATCH_A", "selected_design_sha": design_sha}}]), encoding="utf-8")
    result = bind_c2b_runtime_mapping(type("Args", (), {"launch_report": report, "assignment_manifest": assignment, "worker_distribution": distribution, "planned_import": planned, "runtime_export": runtime, "output_dir": tmp_path / "out"})())
    assert result["one_to_one"] is True
    assert result["C2B_RUNTIME_BINDING_READY"] is True
    assert (tmp_path / "out" / "c2b_runtime_task_mapping.csv").is_file()


def test_runtime_mapping_rejects_missing_private_worker_lists(tmp_path: Path) -> None:
    method = load_method_contract(); design_sha = "d" * 64
    report = tmp_path / "launch.json"; report.write_text(json.dumps({
        "contract_role": "generated_subordinate", "method_contract_version": method["contract_version"],
        "method_contract_sha256": sha256_file(METHOD_CONTRACT), "assignment_batch_id": "C2B_BATCH_A",
        "selected_design_sha": design_sha,
    }), encoding="utf-8")
    distribution = tmp_path / "distribution.csv"; _write_csv(distribution, [{"worker_id": "W001", "task_id": "planned-1"}])
    assignment = tmp_path / "assignment.csv"; _write_csv(assignment, [{"worker_id": "W001", "task_id": "planned-1"}])
    planned = tmp_path / "planned.json"; planned.write_text(json.dumps([{"data": {"planned_task_id": "planned-1"}}]), encoding="utf-8")
    runtime = tmp_path / "runtime.json"; runtime.write_text(json.dumps([{"id": 7, "data": {"planned_task_id": "planned-1", "c2b_batch_id": "C2B_BATCH_A", "selected_design_sha": design_sha}}]), encoding="utf-8")
    output = tmp_path / "out"
    with pytest.raises(ValueError, match="private assignment lists"):
        bind_c2b_runtime_mapping(type("Args", (), {"launch_report": report, "assignment_manifest": assignment, "worker_distribution": distribution, "planned_import": planned, "runtime_export": runtime, "output_dir": output})())
    audit = json.loads((output / "c2b_private_assignment_list_audit.json").read_text(encoding="utf-8"))
    assert audit["formal_ready"] is False
