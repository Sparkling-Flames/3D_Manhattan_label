from __future__ import annotations

import csv
from pathlib import Path
import json
import hashlib
import json
import json

import pytest

from tools.thesis_main.analysis.materialize_c1_estimand_specific_task_support import build_task_support_rows
from tools.thesis_main.analysis.materialize_c1_three_state_task_tags import aggregate_three_state_tags, build_observation_rows
from tools.thesis_main.analysis.materialize_stage3_freeze_gate import REQUIRED_GATES, assert_frozen_roster, build_gate
from tools.thesis_main.analysis.materialize_w034_active_time_validation import sha256_bundle, validate_sentinel
from tools.thesis_main.analysis.materialize_c1_authorized_reassignment_addendum import build_rows as build_authorized_rows
from tools.thesis_main.analysis.materialize_w034_authorized_extension_sensitivity import compare_w034_profiles, materialize as materialize_w034_sensitivity
from tools.thesis_main.registry.build_c1_late_entry_assignment_manifest import build_rows


def _csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


def test_estimand_specific_k_separates_original_authorized_late_outside_and_duplicate(tmp_path: Path) -> None:
    original = tmp_path / "manual.csv"
    _csv(original, [{"worker_id": f"w{i}", "base_task_id": "b", "task_id": "t", "dataset_group": "Calibration_core", "condition": "manual"} for i in range(1, 6)])
    authorized = tmp_path / "authorized.csv"
    _csv(authorized, [{"replacement_worker_id": "w34", "base_task_id": "b", "task_id": "t", "dataset_group": "Calibration_core", "condition": "manual"}])
    late = tmp_path / "late.csv"
    _csv(late, [{"worker_id": "w40", "base_task_id": "b", "task_id": "t", "dataset_group": "Calibration_core", "condition": "manual"}])
    canonical = [
        {"canonical_annotation_id": f"c{i}", "worker_id": worker, "base_task_id": "b", "condition": "manual", "assignment_provenance": "outside_assignment_submission" if worker == "outside" else "authorized_replacement_assignment" if worker == "w34" else "late_entry_calibration_assignment" if worker == "w40" else "original_assignment"}
        for i, worker in enumerate(("w1", "w2", "w3", "w4", "w34", "w40", "outside"), 1)
    ]
    eligibility = []
    for row in canonical:
        eligibility.append({
            "canonical_annotation_id": row["canonical_annotation_id"],
            "gt_primary_analysis_eligible": row["worker_id"] != "outside",
            "peer_analysis_eligible": row["worker_id"] not in {"outside", "w4"},
                "loo_medoid_analysis_eligible": row["worker_id"] in {"w1", "w2", "w34"},
                "strict_loo_analysis_eligible": row["worker_id"] in {"w1", "w2", "w34"},
            "structural_opportunity_eligible": row["worker_id"] != "outside",
            "time_analysis_eligible": row["worker_id"] in {"w1", "w34"},
        })
    row = build_task_support_rows([original], authorized, late, canonical, eligibility)[0]
    assert row["k_target"] == 5 and row["k_outside_observed"] == 1
    assert row["k_original_GT"] == 4 and row["k_authorized_GT"] == 1 and row["k_late_GT"] == 1
    assert row["k_final_GT"] == 6 and row["pooled_support_excess_GT"] == 1
    assert row["k_final_peer"] == 5 and row["k_final_LOO_medoid"] == 3 and row["k_final_LOO_strict"] == 3 and row["k_final_time"] == 2
    with pytest.raises(ValueError, match="duplicate canonical"):
        build_task_support_rows([original], authorized, late, canonical + [{**canonical[0], "canonical_annotation_id": "revision"}], eligibility)


def test_w031_missing_active_time_is_timing_only_and_never_a_roster_gate(tmp_path: Path) -> None:
    original = tmp_path / "w031.csv"
    _csv(original, [
        {"worker_id": "W031", "base_task_id": f"b{index}", "task_id": f"t{index}", "dataset_group": "Calibration_core", "condition": "manual"}
        for index in range(5)
    ])
    canonical = [
        {"canonical_annotation_id": f"w031-{index}", "worker_id": "W031", "base_task_id": f"b{index}",
         "condition": "manual", "assignment_provenance": "original_assignment",
         "active_time_integrity_status": "exact_annotation_valid" if index == 0 else "not_evaluable"}
        for index in range(5)
    ]
    eligibility = [
        {"canonical_annotation_id": row["canonical_annotation_id"], "gt_primary_analysis_eligible": True,
         "peer_analysis_eligible": True, "structural_opportunity_eligible": True,
         "time_analysis_eligible": index == 0}
        for index, row in enumerate(canonical)
    ]
    support = build_task_support_rows([original], None, None, canonical, eligibility)
    assert sum(row["k_final_time"] for row in support) == 1
    assert sum(row["k_final_GT"] for row in support) == 5
    assert sum(row["k_final_peer"] for row in support) == 5
    assert sum(row["k_final_structural"] for row in support) == 5
    from tools.thesis_main.analysis.paper_a_contracts import load_method_contract
    assert load_method_contract()["c2"]["timing_is_roster_gate"] is False


def test_rolling_enrollment_disabled_is_empty_and_active_is_additive(tmp_path: Path) -> None:
    source = tmp_path / "manual.csv"
    tasks = [
        {"worker_id": "old", "task_id": "a", "base_task_id": "a", "dataset_group": "Calibration_anchor", "condition": "manual"},
        {"worker_id": "old", "task_id": "b1", "base_task_id": "b1", "dataset_group": "Calibration_core", "condition": "manual"},
        {"worker_id": "old", "task_id": "b2", "base_task_id": "b2", "dataset_group": "Calibration_core", "condition": "manual"},
    ]
    assert build_rows({"rolling_enrollment_activated": False}, [], [(source, tasks)], []) == []
    config = {
        "rolling_enrollment_activated": True, "N_max": 1,
        "recruitment_window_start": "2026-01-01T00:00:00+00:00", "recruitment_window_end": "2026-12-31T00:00:00+00:00",
        "latest_P1_start": "2026-10-01T00:00:00+00:00", "latest_C1_start": "2026-11-01T00:00:00+00:00", "latest_C2_entry": "2026-12-01T00:00:00+00:00",
        "activation_recorded_at": "2026-07-01T00:00:00+00:00", "frozen_seed": 7,
        "workload_by_dataset_group": {"Calibration_core": 1}, "assignment_rule_version": "v1",
        "instruction_version": "i1", "interface_version": "ui1", "P1_version": "p1",
    }
    worker = {"worker_id": "40", "admission_status": "pass", "enrollment_batch": "late-1", "enrolled_at": "2026-06-01T00:00:00+00:00", "P1_started_at": "2026-06-02T00:00:00+00:00", "P1_version": "p1"}
    rows = build_rows(config, [worker], [(source, tasks)], [])
    assert len(rows) == 2
    assert {row["assignment_provenance"] for row in rows} == {"late_entry_calibration_assignment"}
    with pytest.raises(ValueError, match="forbidden"):
        build_rows({**config, "stage3_frozen": True}, [], [(source, tasks)], [])
    with pytest.raises(ValueError, match="version mismatch"):
        build_rows(config, [{**worker, "P1_version": "wrong"}], [(source, tasks)], [])
    with pytest.raises(ValueError, match="after frozen deadline"):
        build_rows(config, [{**worker, "P1_started_at": "2026-11-02T00:00:00+00:00"}], [(source, tasks)], [])


def test_w034_sentinel_and_stage3_gate_fail_closed(tmp_path: Path) -> None:
    spec = {"worker_id": "34", "project_id": "p", "runtime_task_id": "t", "annotation_id": "a", "validation_timestamp": "2026-07-01T00:00:00Z", "reviewed_by": "owner"}
    active = [{"project_id": "p", "runtime_task_id": "t", "worker_id": "34", "annotation_id": "a", "owner_valid": "true", "session_count": "1", "started_at": "s", "completed_at": "e", "active_duration_seconds": "20", "duplicate_time_ambiguous": "false"}]
    runtime = [{"project_id": "p", "ls_runtime_task_id": "t"}]
    assert validate_sentinel(spec, active, runtime, raw_log_bundle_sha256="a" * 64, derived_audit_sha256="b" * 64)["validation_result"] == "passed"
    assert validate_sentinel(spec, [{**active[0], "active_duration_seconds": "0"}], runtime, raw_log_bundle_sha256="a" * 64, derived_audit_sha256="b" * 64)["validation_result"] == "failed"
    assert validate_sentinel(spec, [{key: value for key, value in active[0].items() if key != "owner_valid"}], runtime, raw_log_bundle_sha256="a" * 64, derived_audit_sha256="b" * 64)["validation_result"] == "failed"
    roster = tmp_path / "roster.csv"; enrollment = tmp_path / "enrollment.csv"
    roster.write_text("x\n1\n", encoding="utf-8"); enrollment.write_text("x\n1\n", encoding="utf-8")
    from tools.thesis_main.analysis.paper_a_contracts import METHOD_CONTRACT, sha256_file
    child_items = []
    for child_role in ("C1_ROW_ELIGIBILITY_FROZEN", "C1_PEER_EVIDENCE_FROZEN", "C1_STRUCTURAL_EB_FROZEN", "W034_SENSITIVITY_FROZEN"):
        child = tmp_path / f"{child_role}.json"
        child.write_text(json.dumps({"schema_version": "test_dependency_v2", "formal_ready": True, "profile_version": "p", "cohort_id": "c", "blockers": [], "dependencies": []}), encoding="utf-8")
        child_items.append({"role": child_role, "frozen": True, "path": child.name, "sha256": sha256_file(child), "expected_schema": "test_dependency_v2", "required_status_field": "formal_ready", "required_status_value": True, "profile_version": "p", "cohort_id": "c"})
    state = {}
    for name in REQUIRED_GATES:
        dependency = tmp_path / f"{name}.json"
        payload = {"schema_version": "test_dependency_v2", "formal_ready": True, "profile_version": "p", "cohort_id": "c", "blockers": [], "dependencies": child_items if name == "C1_EVIDENCE_FROZEN" else []}
        if name == "C1_EVIDENCE_FROZEN":
            payload.update({
                "method_contract_sha256": sha256_file(METHOD_CONTRACT),
                "CALIBRATION_ENROLLMENT_CLOSED": True,
                "ALL_CALIBRATION_WORKERS_TERMINAL": True,
                "FINAL_POOLED_PROFILE_FROZEN": True,
            })
        dependency.write_text(json.dumps(payload), encoding="utf-8")
        state[name] = {"frozen": True, "path": dependency.name, "sha256": hashlib.sha256(dependency.read_bytes()).hexdigest(), "expected_schema": "test_dependency_v2", "required_status_field": "formal_ready", "required_status_value": True, "profile_version": "p", "cohort_id": "c"}
    gate = build_gate(state, hashlib.sha256(roster.read_bytes()).hexdigest(), hashlib.sha256(enrollment.read_bytes()).hexdigest(), base_dir=tmp_path)
    assert gate["STAGE3_LAUNCH_ALLOWED"] is True
    assert build_gate({**state, "C2_A_RP_CLOSED": False}, "r", "e")["STAGE3_LAUNCH_ALLOWED"] is False
    assert_frozen_roster(gate, roster, enrollment)
    roster.write_text("x\n2\n", encoding="utf-8")
    with pytest.raises(ValueError):
        assert_frozen_roster(gate, roster, enrollment)


def test_w034_directory_bundle_and_sensitivity_are_sha_bound(tmp_path: Path) -> None:
    left, right = tmp_path / "left", tmp_path / "right"
    left.mkdir(); right.mkdir()
    (left / "a.jsonl").write_text("a\n", encoding="utf-8")
    (left / "b.jsonl").write_text("b\n", encoding="utf-8")
    (right / "renamed-1.jsonl").write_text("b\n", encoding="utf-8")
    (right / "renamed-2.jsonl").write_text("a\n", encoding="utf-8")
    assert sha256_bundle(left) == sha256_bundle(right)
    original, augmented = tmp_path / "original.csv", tmp_path / "augmented.csv"
    _csv(original, [{"worker_id": "34", "profile_version": "p", "cohort_id": "c", "Q_GT_EB": .8, "R_peer_all": .7, "F_struct_EB": .1, "task_support": 5}])
    _csv(augmented, [{"worker_id": "34", "profile_version": "p", "cohort_id": "c", "Q_GT_EB": .81, "R_peer_all": .71, "F_struct_EB": .09, "task_support": 8}])
    thresholds = tmp_path / "thresholds.json"
    thresholds.write_text(json.dumps({"version": "v", "maximum_rank_displacement": 1, "maximum_absolute_metric_change": .2}), encoding="utf-8")
    result = materialize_w034_sensitivity(original, augmented, thresholds, tmp_path / "sensitivity.json")
    assert result["status"] == "frozen"
    assert result["artifact_role"] == "W034_SENSITIVITY_FROZEN"
    assert len(result["dependencies"]) == 4


def test_three_state_counts_unique_workers_and_excludes_not_evaluable_from_denominator() -> None:
    rows = [
        {"base_task_id": "b", "tag_family": "f", "tag_name": "x", "worker_id": worker, "assertion_state": state}
        for worker, state in (("w1", "positive"), ("w2", "positive"), ("w3", "explicit_negative"), ("w4", "explicit_negative"), ("w5", "unasserted"), ("w6", "not_evaluable"))
    ]
    result = aggregate_three_state_tags(rows)[0]
    assert result["repeated_opposing_claims"] is True
    assert result["positive_assertion_share"] == pytest.approx(0.4)
    assert result["not_evaluable_count"] == 1
    with pytest.raises(ValueError, match="duplicate/conflicting"):
        aggregate_three_state_tags(rows + [{**rows[0], "assertion_state": "explicit_negative"}])


def test_three_state_is_materialized_from_canonical_choice_map_and_excludes_outside() -> None:
    common = {"base_task_id": "b", "condition": "manual", "canonical_eligibility_status": "valid", "schema_interpretable": "true", "outside_assignment_submission": "false"}
    rows = build_observation_rows([
        {**common, "worker_id": "w1", "canonical_annotation_id": "c1", "assignment_provenance": "original_assignment", "choice_map_json": '{"difficulty":["occlusion"],"model_issue":["acceptable"]}'},
        {**common, "worker_id": "w2", "canonical_annotation_id": "c2", "assignment_provenance": "outside_assignment_submission", "outside_assignment_submission": "true", "choice_map_json": '{"difficulty":["occlusion"]}'},
    ])
    assert next(row for row in rows if row["worker_id"] == "w1" and row["tag_name"] == "occlusion")["assertion_state"] == "positive"
    assert all(row["assertion_state"] == "not_evaluable" for row in rows if row["worker_id"] == "w2")


def test_authorized_addendum_is_additive_and_w034_sensitivity_is_thresholded(tmp_path: Path) -> None:
    source = tmp_path / "manual.csv"
    originals = [
        {"round_id": "C1", "worker_id": "14", "task_id": "t1", "base_task_id": "b1", "dataset_group": "Calibration_core"},
        {"round_id": "C1", "worker_id": "14", "task_id": "t2", "base_task_id": "b2", "dataset_group": "Calibration_core"},
    ]
    _csv(source, originals)
    plan = [
        {"displaced_worker_id": "14", "replacement_worker_id": "34", "base_task_id": "b1", "authorization_reason": "administrative replacement", "authorized_by": "owner", "authorized_at": "2026-07-01", "replacement_project_id": "p", "replacement_runtime_task_id": "1", "active_time_expected": "true"},
        {"displaced_worker_id": "14", "replacement_worker_id": "1", "base_task_id": "b2", "authorization_reason": "administrative replacement", "authorized_by": "owner", "authorized_at": "2026-07-01", "replacement_project_id": "p", "replacement_runtime_task_id": "2", "active_time_expected": "false"},
    ]
    runtime = [
        {"project_id": "p", "ls_runtime_task_id": str(i), "task_id": f"t{i}", "base_task_id": f"b{i}", "dataset_group": "Calibration_core", "condition": "manual"}
        for i in (1, 2)
    ]
    rows = build_authorized_rows(plan, [(source, originals)], runtime, expected_w034=1, expected_w001=1)
    assert [row["replacement_worker_id"] for row in rows] == ["34", "1"]
    result = compare_w034_profiles(
        {"worker_id": "34", "Q_GT_EB": .7, "R_peer_all": .8, "F_struct_EB": .1, "global_rank": 5, "task_support": 30},
        {"worker_id": "34", "Q_GT_EB": .72, "R_peer_all": .81, "F_struct_EB": .1, "global_rank": 3, "task_support": 47},
        {"version": "v1", "maximum_rank_displacement": 1, "maximum_absolute_metric_change": .05},
    )
    assert result["support_difference"] == 17
    assert result["authorized_extension_sensitive"] is True
