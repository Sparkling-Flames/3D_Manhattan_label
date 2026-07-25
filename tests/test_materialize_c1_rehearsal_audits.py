from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.thesis_main.analysis.materialize_c1_rehearsal_audits import (
    apply_structural_dispositions,
    materialize_c2_eligible_roster,
    materialize_completion_support,
    materialize_active_time_ledgers,
    materialize_independence,
    materialize_project_independence_provenance,
    materialize_final_canonical_closeout_summary,
    materialize_row_analysis_eligibility,
    rebind_canonical_meta_registry,
    materialize_structural_validation,
)


def _csv(path: Path, rows: list[dict]) -> None:
    fields = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)


def test_completion_counts_raw_pending_duplicate_as_observed(tmp_path: Path) -> None:
    assignment = tmp_path / "manual.csv"
    mapping = tmp_path / "mapping.csv"
    canonical = tmp_path / "canonical.csv"
    geometry = tmp_path / "geometry.jsonl"
    export = tmp_path / "export.json"
    _csv(assignment, [
        {"worker_id": "1", "task_id": "t1", "base_task_id": "b1", "dataset_group": "g"},
        {"worker_id": "2", "task_id": "t1", "base_task_id": "b1", "dataset_group": "g"},
    ])
    _csv(mapping, [{"project_id": "66", "ls_runtime_task_id": "10", "task_id": "t1", "base_task_id": "b1", "dataset_group": "g", "condition": "manual"}])
    _csv(canonical, [{"worker_id": "2", "task_id": "t1", "base_task_id": "b1", "dataset_group": "g"}])
    geometry.write_text("", encoding="utf-8")
    export.write_text(json.dumps([{"project": 66, "id": 10, "annotations": [{"id": 1, "completed_by": 1}, {"id": 2, "completed_by": 2}]}]), encoding="utf-8")

    summary = materialize_completion_support([export], [assignment], mapping, canonical, geometry, tmp_path)

    assert summary["observed_submission_count"] == 2
    assert summary["missing_submission_count"] == 0
    rows = list(csv.DictReader((tmp_path / "c1_assignment_realization_audit.csv").open(encoding="utf-8")))
    assert next(row for row in rows if row["worker_id"] == "1")["missing_reason"] == "duplicate_revision_pending"


def test_final_closeout_does_not_block_nonstarter_or_reviewed_local_exclusion(tmp_path: Path) -> None:
    _csv(tmp_path / "structural_validation_audit.csv", [{"structural_validation_status": "not_evaluable", "failure_attribution": "not_evaluable", "structural_disposition_applied": "true"}])
    _csv(tmp_path / "c1_row_analysis_eligibility.csv", [{"global_analysis_eligible": "true", "loo_analysis_eligible": "true", "structural_opportunity_eligible": "true", "global_analysis_exclusion_reason": ""}])
    _csv(tmp_path / "c1_annotation_version_disposition.csv", [{"version_disposition": "selected_canonical"}])
    _csv(tmp_path / "c1_task_outcome_reference.csv", [{"final_scope": "in_scope"}])
    summary = materialize_final_canonical_closeout_summary(tmp_path, {"completed_worker_count": 19, "partial_noncompletion_worker_count": 1, "nonstarter_worker_count": 3, "missing_other_count": 0})
    assert summary["formal_closeout_ready"] is True
    assert summary["reviewed_local_exclusions"] == 1


def test_final_closeout_blocks_unclassified_missing(tmp_path: Path) -> None:
    _csv(tmp_path / "structural_validation_audit.csv", [{"structural_validation_status": "passed"}])
    _csv(tmp_path / "c1_row_analysis_eligibility.csv", [{"global_analysis_eligible": "true", "loo_analysis_eligible": "true", "structural_opportunity_eligible": "true", "global_analysis_exclusion_reason": ""}])
    _csv(tmp_path / "c1_annotation_version_disposition.csv", [{"version_disposition": "selected_canonical"}])
    _csv(tmp_path / "c1_task_outcome_reference.csv", [{"final_scope": "in_scope"}])
    summary = materialize_final_canonical_closeout_summary(tmp_path, {"missing_other_count": 1})
    assert summary["formal_closeout_ready"] is False
    assert "unclassified_missing" in summary["blockers"]


def test_structural_pass_is_geometry_eligible_but_not_worker_reliability_without_independence(tmp_path: Path) -> None:
    canonical = tmp_path / "canonical.csv"
    geometry = tmp_path / "geometry.jsonl"
    _csv(canonical, [{"canonical_annotation_id": "c1", "project_id": "66", "ls_runtime_task_id": "1", "annotation_id": "a1", "worker_id": "1", "independence_status": "not_evaluable"}])
    geometry.write_text(json.dumps({"canonical_annotation_id": "c1", "worker_id": "1", "task_id": "t1", "corners_px": [[10, 10], [10, 400], [700, 10], [700, 400]], "width": 1024, "height": 512}) + "\n", encoding="utf-8")

    summary = materialize_structural_validation(canonical, geometry, tmp_path)
    apply_structural_dispositions(canonical, tmp_path / "structural_validation_audit.csv")

    assert summary["structural_status_counts"] == {"passed": 1}
    row = next(csv.DictReader(canonical.open(encoding="utf-8")))
    assert row["failure_attribution"] == "none"
    assert row["worker_reliability_eligible"] == "false"


def test_invalid_pair_count_stays_pending_without_row_disposition(tmp_path: Path) -> None:
    canonical = tmp_path / "canonical.csv"; geometry = tmp_path / "geometry.jsonl"
    _csv(canonical, [{"canonical_annotation_id": "c1", "project_id": "66", "ls_runtime_task_id": "1", "annotation_id": "a1", "worker_id": "1", "independence_status": "independent"}])
    geometry.write_text(json.dumps({"canonical_annotation_id": "c1", "worker_id": "1", "task_id": "t1", "corners_px": [[10, 10], [10, 400], [700, 10]], "width": 1024, "height": 512}) + "\n", encoding="utf-8")
    materialize_structural_validation(canonical, geometry, tmp_path)
    row = next(csv.DictReader((tmp_path / "structural_validation_audit.csv").open(encoding="utf-8")))
    assert row["structural_validation_status"] == "not_evaluable"
    assert row["failure_attribution"] == "not_evaluable"


def test_sha_bound_structural_disposition_confirms_worker_failure(tmp_path: Path) -> None:
    canonical = tmp_path / "canonical.csv"; geometry = tmp_path / "geometry.jsonl"
    _csv(canonical, [{"canonical_annotation_id": "c1", "project_id": "66", "ls_runtime_task_id": "1", "annotation_id": "a1", "worker_id": "1", "independence_status": "independent"}])
    geometry.write_text(json.dumps({"canonical_annotation_id": "c1", "worker_id": "1", "task_id": "t1", "corners_px": [[10, 10], [10, 400], [700, 10]], "width": 1024, "height": 512}) + "\n", encoding="utf-8")
    materialize_structural_validation(canonical, geometry, tmp_path)
    source = tmp_path / "c1_structural_validation_pre_disposition.csv"
    disposition = tmp_path / "disposition.csv"
    _csv(disposition, [{
        "canonical_annotation_id": "c1", "source_structural_audit_sha256": __import__("hashlib").sha256(source.read_bytes()).hexdigest(),
        "final_scope": "in_scope", "detected_issue": "odd_keypoint_count", "final_failure_attribution": "worker_caused_structural_failure",
        "structural_denominator_eligible": "true", "worker_failure_numerator": "true", "reviewed_by": "reviewer",
        "reviewed_at": "2026-07-24T00:00:00Z", "reason": "confirmed missing point",
    }])
    summary = materialize_structural_validation(canonical, geometry, tmp_path, disposition_csv=disposition)
    row = next(csv.DictReader((tmp_path / "structural_validation_audit.csv").open(encoding="utf-8")))
    assert summary["applied_disposition_count"] == 1
    assert row["failure_attribution"] == "worker_caused_structural_failure"


def test_contradictory_structural_disposition_fails_closed(tmp_path: Path) -> None:
    canonical = tmp_path / "canonical.csv"; geometry = tmp_path / "geometry.jsonl"
    _csv(canonical, [{"canonical_annotation_id": "c1", "project_id": "66", "ls_runtime_task_id": "1", "annotation_id": "a1", "worker_id": "1", "independence_status": "independent"}])
    geometry.write_text(json.dumps({"canonical_annotation_id": "c1", "worker_id": "1", "task_id": "t1", "corners_px": [[10, 10], [10, 400], [700, 10]], "width": 1024, "height": 512}) + "\n", encoding="utf-8")
    materialize_structural_validation(canonical, geometry, tmp_path)
    source = tmp_path / "c1_structural_validation_pre_disposition.csv"; disposition = tmp_path / "disposition.csv"
    _csv(disposition, [{"canonical_annotation_id": "c1", "source_structural_audit_sha256": __import__("hashlib").sha256(source.read_bytes()).hexdigest(), "final_scope": "OOS", "detected_issue": "odd_keypoint_count", "final_failure_attribution": "worker_caused_structural_failure", "structural_denominator_eligible": "true", "worker_failure_numerator": "true", "reviewed_by": "r", "reviewed_at": "2026", "reason": "bad combination"}])
    summary = materialize_structural_validation(canonical, geometry, tmp_path, disposition_csv=disposition)
    assert summary["invalid_disposition_count"] == 1


def test_c2_roster_fails_closed_on_unknown_independence(tmp_path: Path) -> None:
    completion = tmp_path / "completion.csv"; canonical = tmp_path / "canonical.csv"
    quality = tmp_path / "quality.csv"; loo = tmp_path / "loo.csv"
    _csv(completion, [{"worker_id": "1", "observed_total_count": "2", "completion_status": "completed"}])
    _csv(canonical, [{"worker_id": "1", "independence_status": "not_evaluable", "structural_validation_status": "passed", "outside_assignment_submission": "false", "duplicate_worker_task_submission": "false"}])
    _csv(quality, [{"worker_id": "1", "quality_evaluable": "true"}])
    _csv(loo, [{"worker_id": "1", "peer_count_excluding_self": "2"}])

    summary = materialize_c2_eligible_roster(completion, canonical, quality, loo, tmp_path)

    assert summary["n_eligible"] == 0
    row = next(csv.DictReader((tmp_path / "c2_eligible_roster_C1.csv").open(encoding="utf-8")))
    assert row["c2_candidate_eligible"] == "False"
    assert "no_independence_valid_support" in row["candidate_exclusion_reason"]


def test_cumulative_events_retry_and_unknown_are_not_double_counted_or_bound(tmp_path: Path) -> None:
    meta = tmp_path / "meta.csv"
    logs = tmp_path / "logs"; logs.mkdir()
    _csv(meta, [{"project_id": "66", "ls_runtime_task_id": "10", "worker_id": "1", "annotation_id": "a1", "canonical_annotation_id": "c1"}])
    base = {"project_id": "66", "task_id": "10", "annotator_id": "1", "annotation_id": "a1", "server_annotation_id": "a1", "session_id": "s1", "script_version": "v1", "active_seconds_fragment": 1, "page_gate_eligible": True, "page_gate_reason": "eligible"}
    events = [
        {**base, "active_seconds": 2, "timestamp": 1},
        {**base, "active_seconds": 5, "timestamp": 2, "server_received_at": "2026-01-01T00:00:00"},
        {**base, "active_seconds": 5, "timestamp": 2, "server_received_at": "2026-01-01T00:00:01"},
        {**base, "annotation_id": "unknown_annotation", "server_annotation_id": "", "active_seconds": 3, "timestamp": 3},
    ]
    (logs / "active.jsonl").write_text("\n".join(json.dumps(row) for row in events), encoding="utf-8")

    summary = materialize_active_time_ledgers(meta, logs, tmp_path)

    assert summary["deduplicated_event_count"] == 3
    assert summary["exact_annotation_count"] == 0
    assert summary["unknown_active_seconds"] is None
    assert summary["task_sensitivity_annotation_count"] == 0
    session = next(csv.DictReader((tmp_path / "c1_active_time_session_ledger.csv").open(encoding="utf-8")))
    assert session["session_status"] == "audit_only_mixed_known_unknown"
    assert session["session_active_seconds"] == "0.0"
    assert session["duration_not_allocatable"] == "True"


def test_v2_identity_tuple_is_primary_without_server_annotation_extension(tmp_path: Path) -> None:
    meta = tmp_path / "meta.csv"; logs = tmp_path / "logs"; logs.mkdir()
    _csv(meta, [{"project_id": "66", "ls_runtime_task_id": "10", "worker_id": "1", "annotation_id": "a1", "canonical_annotation_id": "c1"}])
    events = [
        {"project_id": "66", "task_id": "10", "annotator_id": "1", "annotation_id": "a1", "session_id": "s1", "script_version": "stage3_active_time_page_gate_20260711_v2", "active_seconds": 2, "server_received_at": "2026-01-01T00:00:02", "page_gate_eligible": True, "page_gate_reason": "eligible"},
        {"project_id": "66", "task_id": "10", "annotator_id": "1", "annotation_id": "a1", "session_id": "s1", "script_version": "stage3_active_time_page_gate_20260711_v2", "active_seconds": 5, "server_received_at": "2026-01-01T00:00:05", "page_gate_eligible": True, "page_gate_reason": "eligible"},
    ]
    (logs / "active.jsonl").write_text("\n".join(json.dumps(row) for row in events), encoding="utf-8")

    summary = materialize_active_time_ledgers(meta, logs, tmp_path)

    assert summary["exact_annotation_count"] == 1
    assert summary["primary_active_time_status"] == "available"
    annotation = next(csv.DictReader((tmp_path / "c1_active_time_annotation_summary.csv").open(encoding="utf-8")))
    assert annotation["primary_active_time_eligible"] == "True"
    assert float(annotation["active_seconds"]) == 5.0


def test_self_declared_late_binding_stays_unavailable_without_frozen_alias_registry(tmp_path: Path) -> None:
    meta = tmp_path / "meta.csv"; logs = tmp_path / "logs"; logs.mkdir()
    _csv(meta, [{"project_id": "66", "ls_runtime_task_id": "10", "worker_id": "1", "annotation_id": "a1", "canonical_annotation_id": "c1"}])
    common = {"project_id": "66", "task_id": "10", "annotator_id": "1", "session_id": "s1", "script_version": "v3", "page_gate_eligible": True, "page_gate_reason": "eligible"}
    events = [
        {**common, "annotation_id": "unknown_annotation", "active_seconds": 7, "server_received_at": "2026-01-01T00:00:07Z"},
        {**common, "annotation_id": "a1", "server_annotation_id": "a1", "active_seconds": 7, "server_received_at": "2026-01-01T00:00:08Z", "active_time_alias_from": "66|10|1|unknown_annotation", "active_time_alias_reason": "unknown_annotation_late_bound", "late_binding_status": "single_actual_annotation"},
    ]
    (logs / "active.jsonl").write_text("\n".join(json.dumps(row) for row in events), encoding="utf-8")

    summary = materialize_active_time_ledgers(meta, logs, tmp_path)

    assert summary["exact_annotation_count"] == 0
    session = next(csv.DictReader((tmp_path / "c1_active_time_session_ledger.csv").open(encoding="utf-8")))
    assert session["session_status"] == "audit_only_mixed_known_unknown"
    assert float(session["session_active_seconds"]) == 0
    assert session["duration_not_allocatable"] == "True"


def test_active_time_excludes_non_c1_context_before_session_aggregation(tmp_path: Path) -> None:
    meta = tmp_path / "meta.csv"; logs = tmp_path / "logs"; logs.mkdir()
    _csv(meta, [{"project_id": "66", "ls_runtime_task_id": "10", "worker_id": "1", "annotation_id": "a1", "canonical_annotation_id": "c1"}])
    current = {"project_id": "66", "task_id": "10", "annotator_id": "1", "annotation_id": "a1", "session_id": "s1", "active_seconds": 5, "timestamp": 1}
    historical = {**current, "project_id": "1", "task_id": "999", "session_id": "old"}
    (logs / "active.jsonl").write_text("\n".join(json.dumps(row) for row in (current, historical)), encoding="utf-8")
    summary = materialize_active_time_ledgers(meta, logs, tmp_path)
    assert summary["raw_event_count"] == 2
    assert summary["c1_context_event_count"] == 1
    assert summary["excluded_event_count"] == 1


def test_active_time_malformed_json_is_audited_not_silently_dropped(tmp_path: Path) -> None:
    meta = tmp_path / "meta.csv"; logs = tmp_path / "logs"; logs.mkdir()
    _csv(meta, [{"project_id": "66", "ls_runtime_task_id": "10", "worker_id": "1", "annotation_id": "a1"}])
    (logs / "active.jsonl").write_text('{"project_id":"66"\n', encoding="utf-8")
    summary = materialize_active_time_ledgers(meta, logs, tmp_path)
    assert summary["parse_error_count"] == 1
    error = next(csv.DictReader((tmp_path / "c1_active_time_parse_error_audit.csv").open(encoding="utf-8")))
    assert error["source_line"] == "1"
    assert len(error["line_sha256"]) == 64


def test_independence_requires_explicit_cleared_provenance(tmp_path: Path) -> None:
    meta = tmp_path / "meta.csv"
    base = {"project_id": "66", "ls_runtime_task_id": "10", "task_id": "t1", "worker_id": "1", "annotation_id": "a1", "canonical_annotation_id": "c1", "provenance_status": "", "copy_risk_status": "", "parent_cross_owner": ""}
    _csv(meta, [base, {**base, "annotation_id": "a2", "canonical_annotation_id": "c2", "provenance_status": "complete", "copy_risk_status": "cleared"}, {**base, "annotation_id": "a3", "canonical_annotation_id": "c3", "parent_cross_owner": "true"}])
    summary = materialize_independence(meta, tmp_path)
    assert summary["status_counts"] == {"not_evaluable": 2, "non_independent_confirmed": 1}


def test_sha_bound_independence_disposition_can_clear_a_row(tmp_path: Path) -> None:
    meta = tmp_path / "meta.csv"; disposition = tmp_path / "disposition.csv"
    _csv(meta, [{"project_id": "66", "condition": "manual", "ls_runtime_task_id": "10", "task_id": "t1", "worker_id": "1", "annotation_id": "a1", "canonical_annotation_id": "c1", "provenance_status": "", "copy_risk_status": ""}])
    source_sha = __import__("hashlib").sha256(meta.read_bytes()).hexdigest()
    _csv(disposition, [{"canonical_annotation_id": "c1", "provenance_status": "complete", "copy_risk_status": "cleared", "parent_annotation_id": "none", "parent_owner_id": "none", "parent_cross_owner": "false", "independence_status": "independent", "reviewed_by": "reviewer", "reviewed_at": "2026-07-24T00:00:00Z", "source_meta_sha256": source_sha}])
    evidence = tmp_path / "project_evidence.csv"
    _csv(evidence, [{"project_id": "66", "condition": "manual", "raw_parent_schema_coverage": "1", "raw_export_sha256_set": "a" * 64, "cross_owner_parent_count": "0", "unresolved_parent_count": "0", "project_evidence_sha256": "evidence"}])
    project = tmp_path / "project.csv"
    _csv(project, [{"project_id": "66", "condition": "manual", "source_project_evidence_sha256": "evidence", "project_evidence_sha256": "evidence", "raw_export_sha256_set": "a" * 64, "project_config_sha256": "b" * 64, "annotation_visibility_contract": "restricted", "prior_annotation_visibility": "none", "raw_parent_schema_coverage": "1", "cross_owner_parent_count": "0", "unresolved_parent_count": "0", "reviewed_by": "reviewer", "reviewed_at": "2026"}])
    summary = materialize_independence(meta, tmp_path, disposition_csv=disposition, project_disposition_csv=project)
    assert summary["status_counts"] == {"independent": 1}
    assert summary["disposition_manifest_sha256"] == __import__("hashlib").sha256(disposition.read_bytes()).hexdigest()


def test_project_provenance_manifest_does_not_clear_rows_without_annotation_disposition(tmp_path: Path) -> None:
    meta = tmp_path / "meta.csv"; project = tmp_path / "project.csv"
    rows = [{"project_id": "66", "condition": "manual", "ls_runtime_task_id": str(i), "task_id": f"t{i}", "worker_id": "1", "annotation_id": f"a{i}", "canonical_annotation_id": f"c{i}"} for i in range(2)]
    _csv(meta, rows)
    source_sha = __import__("hashlib").sha256(meta.read_bytes()).hexdigest()
    _csv(project, [{"project_id": "66", "condition": "manual", "source_meta_sha256": source_sha, "provenance_status": "complete", "copy_risk_status": "cleared", "parent_field_coverage_complete": "true", "cross_owner_parent_count": "0", "reviewed_by": "reviewer", "reviewed_at": "2026-07-24T00:00:00Z"}])
    summary = materialize_independence(meta, tmp_path, project_disposition_csv=project)
    assert summary["status_counts"] == {"not_evaluable": 2}


def test_project_clearance_does_not_override_adverse_row_evidence(tmp_path: Path) -> None:
    meta = tmp_path / "meta.csv"; project = tmp_path / "project.csv"
    _csv(meta, [{"project_id": "66", "condition": "manual", "ls_runtime_task_id": "1", "task_id": "t", "worker_id": "1", "annotation_id": "a", "canonical_annotation_id": "c", "parent_cross_owner": "true", "copy_risk_status": "confirmed_copy"}])
    source_sha = __import__("hashlib").sha256(meta.read_bytes()).hexdigest()
    _csv(project, [{"project_id": "66", "condition": "manual", "source_meta_sha256": source_sha, "provenance_status": "complete", "copy_risk_status": "cleared", "parent_field_coverage_complete": "true", "cross_owner_parent_count": "0", "reviewed_by": "r", "reviewed_at": "2026"}])
    summary = materialize_independence(meta, tmp_path, project_disposition_csv=project)
    assert summary["status_counts"] == {"non_independent_confirmed": 1}


def test_project_independence_evidence_is_grouped_by_project_condition(tmp_path: Path) -> None:
    meta = tmp_path / "meta.csv"
    _csv(meta, [{"project_id": "66", "condition": "manual", "parent_annotation_id": "", "parent_owner_id": "", "source_sha256": "a" * 64}, {"project_id": "66", "condition": "manual", "parent_annotation_id": "a", "parent_owner_id": "1", "source_sha256": "a" * 64}])
    summary = materialize_project_independence_provenance(meta, tmp_path)
    assert summary["project_condition_count"] == 1
    assert next(csv.DictReader((tmp_path / "c1_project_independence_provenance_evidence.csv").open(encoding="utf-8")))["annotation_count"] == "2"


def test_partial_worker_uses_local_valid_support(tmp_path: Path) -> None:
    completion = tmp_path / "completion.csv"; canonical = tmp_path / "canonical.csv"
    quality = tmp_path / "quality.csv"; loo = tmp_path / "loo.csv"
    _csv(completion, [{"worker_id": "1", "observed_total_count": "5", "completion_status": "partial_noncompletion"}])
    _csv(canonical, [
        {"worker_id": "1", "independence_status": "independent", "structural_validation_status": "passed", "outside_assignment_submission": "false", "duplicate_worker_task_submission": "false"},
        {"worker_id": "1", "independence_status": "not_evaluable", "structural_validation_status": "not_evaluable", "outside_assignment_submission": "true", "duplicate_worker_task_submission": "false"},
    ])
    _csv(quality, [{"worker_id": "1", "quality_evaluable": "true"}] * 3)
    _csv(loo, [{"worker_id": "1", "peer_count_excluding_self": "2"}] * 3)
    summary = materialize_c2_eligible_roster(completion, canonical, quality, loo, tmp_path)
    assert summary["n_eligible"] == 1


def test_row_eligibility_excludes_outside_assignment_from_all_tracks(tmp_path: Path) -> None:
    canonical = tmp_path / "canonical.csv"; versions = tmp_path / "versions.csv"; quality = tmp_path / "quality.csv"
    loo = tmp_path / "loo.csv"; structural = tmp_path / "structural.csv"; reference = tmp_path / "reference.csv"
    row = {"project_id": "66", "ls_runtime_task_id": "1", "task_id": "t1", "base_task_id": "b1", "condition": "manual", "worker_id": "1", "annotation_id": "a1", "canonical_annotation_id": "c1", "assigned_expected": "true", "outside_assignment_submission": "true", "duplicate_worker_task_submission": "false", "independence_status": "independent"}
    _csv(canonical, [row]); _csv(versions, [{"annotation_id": "a1", "version_disposition": "selected_canonical"}])
    _csv(quality, [{"canonical_annotation_id": "c1", "quality_evaluable": "true"}])
    _csv(loo, [{"canonical_annotation_id": "c1", "q_LOO_tu": ".9"}])
    _csv(structural, [{"canonical_annotation_id": "c1", "structural_validation_status": "passed"}])
    _csv(reference, [{"project_id": "66", "ls_runtime_task_id": "1", "task_id": "t1", "base_task_id": "b1", "condition": "manual", "final_scope": "in_scope", "geometry_reference_ready": "true"}])
    materialize_row_analysis_eligibility(canonical, versions, quality, loo, structural, reference, tmp_path)
    result = next(csv.DictReader((tmp_path / "c1_row_analysis_eligibility.csv").open(encoding="utf-8")))
    assert result["global_analysis_eligible"] == "False"
    assert result["loo_analysis_eligible"] == "False"
    assert result["structural_opportunity_eligible"] == "False"


def test_canonical_meta_rebinds_after_derived_gate_columns_are_added(tmp_path: Path) -> None:
    canonical = tmp_path / "canonical.csv"; meta = tmp_path / "meta.csv"
    _csv(canonical, [{"canonical_annotation_id": "c1", "derived_gate": "true"}])
    _csv(meta, [{"canonical_annotation_id": "c1", "canonical_registry_sha256": "old"}])
    sha = rebind_canonical_meta_registry(canonical, meta)
    assert next(csv.DictReader(meta.open(encoding="utf-8")))["canonical_registry_sha256"] == sha


def test_canonical_meta_rebinds_after_derived_gate_columns_are_added(tmp_path: Path) -> None:
    canonical = tmp_path / "canonical.csv"; meta = tmp_path / "meta.csv"
    _csv(canonical, [{"canonical_annotation_id": "c1", "derived_gate": "true"}])
    _csv(meta, [{"canonical_annotation_id": "c1", "canonical_registry_sha256": "old"}])
    sha = rebind_canonical_meta_registry(canonical, meta)
    assert next(csv.DictReader(meta.open(encoding="utf-8")))["canonical_registry_sha256"] == sha
