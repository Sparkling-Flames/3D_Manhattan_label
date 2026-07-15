from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.thesis_main.analysis.c1_materialize_quality_table import _r_u_evidence, _scope_outcome, build_quality_rows, materialize
from tools.thesis_main.analysis.c1_materialize_worker_profile_sidecar import build_evidence_rows, build_main_matrix
from tools.thesis_main.analysis.c1_materialize_worker_state import build_worker_state


def _write(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_quality_reads_fresh_canonical_choice_payload(tmp_path: Path) -> None:
    raw = tmp_path / "raw_export.json"
    raw.write_text("[]", encoding="utf-8")
    raw_sha = __import__("hashlib").sha256(raw.read_bytes()).hexdigest()
    registry = tmp_path / "c1_canonical_annotations.csv"
    _write(registry, ["canonical_annotation_id"], [{"canonical_annotation_id": "a1"}])
    sha = __import__("hashlib").sha256(registry.read_bytes()).hexdigest()
    meta = tmp_path / "c1_canonical_meta_observations.csv"
    _write(meta, ["canonical_registry_sha256", "source_artifact", "source_sha256", "source_export_sha256", "task_id", "base_task_id", "dataset_group", "worker_id", "canonical_annotation_id", "choice_map_json", "difficulty_present", "model_issue_present", "canonical_eligibility_status", "schema_interpretable", "n_corners", "geometry_hash", "assigned_expected", "independence_status", "independence_audit_identity"], [{"canonical_registry_sha256": sha, "source_artifact": str(raw), "source_sha256": raw_sha, "source_export_sha256": raw_sha, "task_id": "t", "base_task_id": "b", "dataset_group": "Calibration_anchor", "worker_id": "w", "canonical_annotation_id": "a1", "choice_map_json": json.dumps({"difficulty": ["occlusion"], "model_issue": ["acceptable"]}), "difficulty_present": "true", "model_issue_present": "true", "canonical_eligibility_status": "valid", "schema_interpretable": "true", "n_corners": "4", "geometry_hash": "g", "assigned_expected": "true", "independence_status": "independent", "independence_audit_identity": "project|task|worker|annotation"}])
    summary = materialize(registry, tmp_path, None)
    quality = list(csv.DictReader((tmp_path / "c1_quality_annotations.csv").open(encoding="utf-8")))
    assert summary["canonical_meta_fresh"] is True
    assert quality[0]["difficulty"] == "occlusion"
    assert quality[0]["model_issue"] == "acceptable"
    assert quality[0]["independence_audit_identity"] == "project|task|worker|annotation"


def test_quality_marks_missing_canonical_meta_as_blocker(tmp_path: Path) -> None:
    registry = tmp_path / "c1_canonical_annotations.csv"
    _write(registry, ["task_id"], [{"task_id": "t"}])
    assert "canonical_meta_missing_or_stale" in materialize(registry, tmp_path, None)["blockers"]


def test_quality_marks_registry_hash_mismatch_as_stale(tmp_path: Path) -> None:
    registry = tmp_path / "c1_canonical_annotations.csv"
    _write(registry, ["canonical_annotation_id"], [{"canonical_annotation_id": "a1"}])
    _write(tmp_path / "c1_canonical_meta_observations.csv", ["canonical_registry_sha256", "canonical_annotation_id"], [{"canonical_registry_sha256": "stale", "canonical_annotation_id": "a1"}])
    summary = materialize(registry, tmp_path, None)
    assert summary["canonical_meta_fresh"] is False
    assert "canonical_meta_missing_or_stale" in summary["blockers"]


def test_quality_marks_replaced_raw_export_as_stale(tmp_path: Path) -> None:
    registry = tmp_path / "c1_canonical_annotations.csv"
    _write(registry, ["canonical_annotation_id"], [{"canonical_annotation_id": "a1"}])
    raw = tmp_path / "raw.json"
    raw.write_text("original", encoding="utf-8")
    registry_sha = __import__("hashlib").sha256(registry.read_bytes()).hexdigest()
    raw_sha = __import__("hashlib").sha256(raw.read_bytes()).hexdigest()
    _write(tmp_path / "c1_canonical_meta_observations.csv", ["canonical_registry_sha256", "source_artifact", "source_sha256", "source_export_sha256", "canonical_annotation_id"], [{"canonical_registry_sha256": registry_sha, "source_artifact": str(raw), "source_sha256": raw_sha, "source_export_sha256": raw_sha, "canonical_annotation_id": "a1"}])
    raw.write_text("replaced", encoding="utf-8")
    summary = materialize(registry, tmp_path, None)
    assert summary["canonical_meta_fresh"] is False
    assert "raw_export_sha_mismatch" in summary["canonical_meta_freshness_reasons"]


def test_worker_scope_never_becomes_task_final_scope_without_task_adjudication() -> None:
    row = build_quality_rows([{"scope": "oos_open_boundary", "worker_scope_response": "oos_open_boundary"}])[0]
    assert row["task_final_scope"] == ""
    assert row["worker_scope_response"] == "oos_open_boundary"


def test_worker_scope_profile_consumes_adjudicated_outcome_not_raw_response() -> None:
    evidence = build_evidence_rows([{
        "round_id": "C1", "worker_id": "w1", "task_id": "t1", "base_task_id": "b1",
        "dataset_group": "Calibration_anchor", "condition": "manual",
        "task_final_scope": "in_scope", "worker_scope_response": "oos_open_boundary",
        "worker_scope_outcome": "correct_in_scope", "canonical_eligibility_status": "valid",
        "independence_status": "independent", "assigned_expected": "true",
        "outside_assignment_submission": "false", "duplicate_worker_task_submission": "false",
        "schema_interpretable": "true", "process_evaluable": "true",
        "geometry_valid": "true", "canonical_annotation_id": "a1",
    }])
    assert evidence[0]["worker_scope_outcome"] == "correct_in_scope"
    assert evidence[0]["included_in_r_scope"] is True


def test_duplicate_review_process_failure_is_preserved_in_quality_evidence() -> None:
    row = build_quality_rows([{
        "process_disposition": "worker_process_failure", "canonical_eligibility_status": "valid",
        "independence_status": "independent", "assigned_expected": "true",
        "outside_assignment_submission": "false", "duplicate_worker_task_submission": "false",
        "schema_interpretable": "true",
    }])[0]
    assert row["process_failure_observed"] == "true"
    assert row["process_failure_subfamily"] == "duplicate_review_worker_process_failure"


def test_task_outcome_drives_scope_outcome_and_oos_excludes_r_u() -> None:
    assert _scope_outcome("in_scope", "oos") == "scope_false_negative"
    included, reason = _r_u_evidence({
        "used_for_r_u": "true", "task_outcome_adjudication_status": "approved", "task_final_scope": "oos", "condition": "manual",
        "geometry_reference_status": "expert_hard_single", "geometry_valid": "true", "process_evaluable": "true", "process_failure_observed": "false",
        "duplicate_review_status": "resolved", "eligible_independent_evidence": "true",
    })
    assert included is False
    assert "not_in_scope" in reason


def test_formal_r_u_accepts_worker_excluded_reference_only_with_explicit_exclusion() -> None:
    base = {
        "used_for_r_u": "true", "task_outcome_adjudication_status": "approved", "task_final_scope": "in_scope",
        "condition": "manual", "geometry_reference_status": "worker_excluded_loo_consensus",
        "geometry_valid": "true", "process_evaluable": "true", "process_failure_observed": "false",
        "duplicate_review_status": "resolved", "eligible_independent_evidence": "true",
        "reference_identity": "loo-ref", "reference_evidence_status": "evaluable",
        "r_u_score_status": "evaluable", "r_u_metric_name": "score", "r_u_metric_value": "0.5",
        "r_u_score_source": "frozen-score.csv",
    }
    included, reason = _r_u_evidence({**base, "reference_worker_excluded": "true"}, formal_score_required=True)
    assert included is True, reason
    included, reason = _r_u_evidence({**base, "reference_worker_excluded": "false"}, formal_score_required=True)
    assert included is False
    assert "reference_includes_worker" in reason


def test_r_u_truth_count_matches_worker_state_and_profile_support(tmp_path: Path) -> None:
    quality = [{
        "worker_id": "w1", "task_id": "t1", "base_task_id": "b1", "round_id": "C1", "dataset_group": "Calibration_anchor", "condition": "manual",
        "canonical_annotation_id": "a1", "canonical_eligibility_status": "valid", "independence_status": "independent", "assigned_expected": "true",
        "outside_assignment_submission": "false", "duplicate_worker_task_submission": "false", "schema_interpretable": "true", "r_u_evidence_included": "true",
        "task_final_scope": "in_scope", "geometry_reference_status": "expert_hard_single", "geometry_valid": "true", "process_evaluable": "true",
    }]
    assignment = tmp_path / "assignment.csv"
    _write(assignment, ["worker_id"], [{"worker_id": "w1"}])
    worker_rows = build_worker_state(quality, [assignment], 1)
    evidence = build_evidence_rows(quality)
    profile = build_main_matrix(evidence, {"w1": worker_rows[0]}, {})[0]
    assert worker_rows[0]["n_calib_completed"] == 1
    assert sum(row["r_u_evidence_included"] == "true" for row in quality) == 1
    assert profile["n_calib_support"] == 1


def test_provisional_worker_state_uses_assignment_roster_not_forensic_quality_rows(tmp_path: Path) -> None:
    assignment = tmp_path / "assignment.csv"
    _write(assignment, ["worker_id"], [{"worker_id": "w1"}])
    rows = [{"worker_id": "w1", "r_u_evidence_included": "false"}, {"worker_id": "forensic-w2", "r_u_evidence_included": "true"}]
    worker_rows = build_worker_state(rows, [assignment], 1)
    assert [row["worker_id"] for row in worker_rows] == ["w1"]


def test_task_outcome_materialization_controls_scope_and_r_u_manifest(tmp_path: Path) -> None:
    registry = tmp_path / "c1_canonical_annotations.csv"
    fields = ["round_id", "task_id", "base_task_id", "dataset_group", "condition", "worker_id", "canonical_annotation_id", "scope", "n_corners", "geometry_hash", "assigned_expected", "outside_assignment_submission", "duplicate_worker_task_submission", "duplicate_review_status", "canonical_eligibility_status", "independence_status", "schema_interpretable", "process_evaluable", "process_failure_observed"]
    _write(registry, fields, [{"round_id": "C1", "task_id": "t", "base_task_id": "b", "dataset_group": "Calibration_anchor", "condition": "manual", "worker_id": "w", "canonical_annotation_id": "a", "scope": "in_scope", "n_corners": "4", "geometry_hash": "g", "assigned_expected": "true", "outside_assignment_submission": "false", "duplicate_worker_task_submission": "false", "duplicate_review_status": "resolved", "canonical_eligibility_status": "valid", "independence_status": "independent", "schema_interpretable": "true", "process_evaluable": "true", "process_failure_observed": "false"}])
    outcome = tmp_path / "task_outcome.csv"
    _write(outcome, ["task_id", "base_task_id", "condition", "final_scope", "scope_resolution_status", "oos_subtype", "geometry_reference_status", "reference_identity", "adjudication_status", "reviewed_by", "reviewed_at"], [{"task_id": "t", "base_task_id": "b", "condition": "manual", "final_scope": "in_scope", "scope_resolution_status": "resolved", "oos_subtype": "", "geometry_reference_status": "expert_hard_single", "reference_identity": "ref-1", "adjudication_status": "approved", "reviewed_by": "reviewer", "reviewed_at": "2026-07-15T00:00:00Z"}])
    summary = materialize(registry, tmp_path, None, task_outcome_csv=outcome)
    quality = next(csv.DictReader((tmp_path / "c1_quality_annotations.csv").open(encoding="utf-8")))
    evidence = next(csv.DictReader((tmp_path / "calibration_r_u_evidence_C1.csv").open(encoding="utf-8")))
    assert quality["task_final_scope"] == "in_scope"
    assert quality["worker_scope_outcome"] == "correct_in_scope"
    assert quality["r_u_evidence_included"] == "true"
    assert evidence["r_u_evidence_included"] == "true"
    assert summary["n_r_u_evidence_included"] == 1
