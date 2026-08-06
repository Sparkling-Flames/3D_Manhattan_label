from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from tools.thesis_main.analysis.materialize_c2b_closeout import materialize
from tools.thesis_main.analysis.paper_a_contracts import METHOD_CONTRACT, load_method_contract, sha256_file


def _csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _case(
    tmp_path: Path,
    *,
    assignments: list[dict[str, str]],
    submissions: list[dict[str, str]],
    profiles: list[dict[str, str]],
    reference_review: bool = True,
    terminal_dispositions: list[dict[str, str]] | None = None,
) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    fields = ["worker_id", "task_id", "c2_component", "assignment_batch_id", "task_stratum"]
    assignment = _csv(tmp_path / "assignment.csv", fields, assignments)
    submission = _csv(tmp_path / "submissions.csv", ["worker_id", "task_id"], submissions)
    roster = _csv(tmp_path / "roster.csv", ["worker_id"], [{"worker_id": row["worker_id"]} for row in profiles])
    profile = _csv(tmp_path / "profile.csv", list(profiles[0]), profiles)
    snapshot = (tmp_path / "snapshot.json"); snapshot.write_text(json.dumps({
        "schema_version": "paper_a_c1_batch_analysis_snapshot_v1",
        "status": "formal_design_eligible", "C2B_DESIGN_INPUT_FROZEN_FROM_C1_A": True,
    }), encoding="utf-8")
    rules = (tmp_path / "rules.json"); rules.write_text(json.dumps({
        "min_common_anchor_per_worker": 1, "min_bridge_per_worker": 0, "min_task_support": 1,
    }), encoding="utf-8")
    design = (tmp_path / "design.json"); design.write_text(json.dumps({
        "c2b_design_ready": True, "launch_ready": True, "candidate_only": False,
        "design_manifest_sha256": "d" * 64,
    }), encoding="utf-8")
    planned = tmp_path / "planned.json"
    planned_rows = []
    for task_id in sorted({row["task_id"] for row in assignments}):
        planned_rows.append({"data": {
            "planned_task_id": task_id, "deployment_id": "zh", "language_group": "Chinese",
            "server_instance_id": "server-zh", "project_id": "project-zh",
            "c2b_batch_id": "C2B_BATCH_A", "selected_design_sha": "design-sha",
        }})
    planned.write_text(json.dumps(planned_rows), encoding="utf-8")
    distribution = tmp_path / "distribution.csv"
    _csv(distribution, fields, assignments)
    deployment_manifest = tmp_path / "deployment_manifest.json"
    worker_registry_sha = "r" * 64
    deployment_manifest.write_text(json.dumps({
        "schema_version": "c2b_worker_deployment_manifest_v1",
        "method_contract_version": load_method_contract()["contract_version"],
        "method_contract_sha256": sha256_file(METHOD_CONTRACT), "assignment_batch_id": "C2B_BATCH_A",
        "assignment_sha256": sha256_file(assignment), "deployments": [{
            "deployment_id": "zh", "language_group": "Chinese", "server_instance_id": "server-zh",
            "project_id": "project-zh", "worker_ids": [row["worker_id"] for row in profiles],
            "server_url": "https://example.test", "worker_registry_sha256": worker_registry_sha,
            "method_contract_version": load_method_contract()["contract_version"],
            "method_contract_sha256": sha256_file(METHOD_CONTRACT),
            "assignment_sha256": sha256_file(assignment),
            "selected_design_sha": "design-sha",
            "planned_import_path": str(planned), "planned_import_sha256": sha256_file(planned),
        }],
    }), encoding="utf-8")
    runtime_export = tmp_path / "runtime-with-arbitrary-name.json"
    runtime_export.write_text(json.dumps([{
        "id": f"runtime-{task_id}", "data": {
            "planned_task_id": task_id, "deployment_id": "zh", "language_group": "Chinese",
            "server_instance_id": "server-zh", "project_id": "project-zh",
            "c2b_batch_id": "C2B_BATCH_A", "selected_design_sha": "design-sha",
        },
    } for task_id in sorted({row["task_id"] for row in assignments})]), encoding="utf-8")
    runtime_mapping = tmp_path / "c2b_runtime_task_mapping.csv"
    runtime_mapping.write_text("worker_id,planned_task_id,runtime_task_id\n", encoding="utf-8")
    launch = (tmp_path / "launch.json"); launch.write_text(json.dumps({
        "schema_version": "paper_a_c2b_launch_ready_report_v4", "C2B_LAUNCH_READY": True,
        "method_contract_version": load_method_contract()["contract_version"], "method_contract_sha256": sha256_file(METHOD_CONTRACT),
        "assignment_batch_id": "C2B_BATCH_A", "assignment_sha256": sha256_file(assignment),
        "selected_design_sha": "design-sha",
        "deployment_manifest_path": str(deployment_manifest), "deployment_manifest_sha256": sha256_file(deployment_manifest),
        "deployments": [{
            "deployment_id": "zh", "language_group": "Chinese", "server_instance_id": "server-zh",
            "project_id": "project-zh", "server_url": "https://example.test", "worker_registry_sha256": worker_registry_sha,
            "method_contract_version": load_method_contract()["contract_version"],
            "method_contract_sha256": sha256_file(METHOD_CONTRACT),
            "assignment_sha256": sha256_file(assignment),
            "selected_design_sha": "design-sha",
            "planned_import_path": str(planned),
            "planned_import_sha256": sha256_file(planned),
        }],
    }), encoding="utf-8")
    runtime = (tmp_path / "runtime.json"); runtime.write_text(json.dumps({
        "schema_version": "paper_a_c2b_runtime_mapping_audit_v2", "method_contract_version": load_method_contract()["contract_version"],
        "method_contract_sha256": sha256_file(METHOD_CONTRACT), "formal_ready": True, "C2B_RUNTIME_BINDING_READY": True,
        "assignment_batch_id": "C2B_BATCH_A", "selected_design_sha": "design-sha", "deployment_manifest_sha256": sha256_file(deployment_manifest),
        "deployment_ids": ["zh"], "planned_import_sha256": {"zh": sha256_file(planned)},
        "runtime_export_sha256": {"zh": sha256_file(runtime_export)}, "runtime_mapping_sha256": sha256_file(runtime_mapping),
        "runtime_task_count": len(planned_rows), "runtime_task_count_by_deployment": {"zh": len(planned_rows)},
        "worker_task_binding_count": len(assignments), "dependencies": [
            {"role": "RUNTIME_MAPPING", "path": str(runtime_mapping), "sha256": sha256_file(runtime_mapping)},
            {"role": "PLANNED_IMPORT_zh", "path": str(planned), "sha256": sha256_file(planned)},
            {"role": "RUNTIME_EXPORT_zh", "path": str(runtime_export), "sha256": sha256_file(runtime_export)},
        ],
    }), encoding="utf-8")
    private = (tmp_path / "private.json"); private.write_text(json.dumps({
        "schema_version": "paper_a_c2b_private_assignment_list_audit_v2", "method_contract_version": load_method_contract()["contract_version"],
        "method_contract_sha256": sha256_file(METHOD_CONTRACT), "formal_ready": True, "private_assignment_list_audit_passed": True,
        "assignment_batch_id": "C2B_BATCH_A", "assignment_manifest_sha256": sha256_file(assignment),
        "worker_distribution_sha256": sha256_file(distribution),
        "dependencies": [
            {"role": "ASSIGNMENT_MANIFEST", "path": str(assignment), "sha256": sha256_file(assignment)},
            {"role": "WORKER_DISTRIBUTION", "path": str(distribution), "sha256": sha256_file(distribution)},
        ],
    }), encoding="utf-8")
    manifest = tmp_path / "profile.manifest.json"
    actual = {
        "c2b_submissions_csv": sha256_file(submission), "post_c2b_worker_profile_csv": sha256_file(profile),
        "c2b_design_summary": sha256_file(design), "c1_a_snapshot": sha256_file(snapshot),
        "c2b_assignment_csv": sha256_file(assignment), "worker_roster_csv": sha256_file(roster),
        "rule_config": sha256_file(rules), "c2b_launch_report": sha256_file(launch),
        "c2b_runtime_mapping_audit": sha256_file(runtime), "c2b_private_assignment_audit": sha256_file(private),
    }
    manifest.write_text(json.dumps({
        "manifest_version": "c2b_post_profile_v1", "profile_version": "p1", "cohort_id": "c1",
        "input_sha256": actual, "output_sha256": {},
    }), encoding="utf-8")
    review = None
    if reference_review:
        review = tmp_path / "reference_review.csv"
        review_fields = [
            "schema_version", "base_task_id", "registry_status_before_review", "reference_status_before_review",
            "reference_normalizer_status_before_review", "geometry_reference_ready_before_review", "review_status",
            "review_disposition", "reviewer_blinding", "review_evidence", "reviewed_by", "reviewed_at",
            "original_reference_sha256", "method_contract_sha256",
        ]
        with review.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=review_fields)
            writer.writeheader()
            for row in assignments:
                writer.writerow({
                    "schema_version": "paper_a_reference_conflict_review_record_v2",
                    "base_task_id": row["task_id"],
                    "registry_status_before_review": "approved_by_frozen_reference_policy",
                    "reference_status_before_review": "use_existing_public_gt_as_is",
                    "reference_normalizer_status_before_review": "passed",
                    "geometry_reference_ready_before_review": "true",
                    "review_status": "closed", "review_disposition": "retain_original",
                    "reviewer_blinding": "worker_and_analysis_metric_blinded",
                    "review_evidence": "manual_scene_review_record", "reviewed_by": "reviewer-1",
                    "reviewed_at": "2026-08-05T12:00:00Z", "original_reference_sha256": "a" * 64,
                    "method_contract_sha256": sha256_file(METHOD_CONTRACT),
                })
    output = tmp_path / "closeout.json"
    terminal_disposition = None
    if terminal_dispositions is not None:
        terminal_disposition = _csv(
            tmp_path / "terminal_disposition.csv",
            ["worker_id", "task_id", "terminal_status", "missing_reason"],
            terminal_dispositions,
        )
    materialize(
        submission, profile, manifest, design, snapshot, assignment, roster, rules,
        launch, runtime, private, output, terminal_disposition_csv=terminal_disposition,
        reference_conflict_review_record=review,
    )
    return output


def _profile(worker: str, *, completion: str = "completed", risk: str = "estimated", qgt: str = "estimated") -> dict[str, str]:
    return {
        "schema_version": "worker_profile_v2", "worker_id": worker, "profile_version": "p1", "cohort_id": "c1",
        "enrollment_batch": "original", "administratively_eligible": "true", "process_eligible": "true",
        "independence_eligible": "true", "Q_GT_estimable": "true", "reference_evaluable": "true",
        "Q_GT_profile_status": qgt, "R_peer_profile_status": "estimated",
        "peer_task_support": "5", "F_struct_profile_status": "estimated", "LOO_medoid_status": "not_evaluable",
        "LOO_strict_status": "not_evaluable", "global_policy_eligible": "true", "c2_risk_model_eligible": "true",
        "peer_tiebreak_eligible": "true", "structural_gate_eligible": "true", "F_struct_raw": "0",
        "F_struct_EB": "0", "F_struct_interval_lower": "0", "F_struct_interval_upper": "0.1",
        "c1_risk_slope_status": risk,
        "conditional_component_status": "not_evaluable", "completion_status": completion,
    }


def test_partial_missing_with_terminal_status_closes_and_preserves_denominator(tmp_path: Path) -> None:
    output = _case(
        tmp_path,
        assignments=[
            {"worker_id": "w1", "task_id": "t1", "c2_component": "common_anchor", "assignment_batch_id": "C2B_BATCH_A", "task_stratum": "ordinary"},
            {"worker_id": "w1", "task_id": "t2", "c2_component": "diverse_bridge", "assignment_batch_id": "C2B_BATCH_A", "task_stratum": "stress"},
            {"worker_id": "w2", "task_id": "t3", "c2_component": "common_anchor", "assignment_batch_id": "C2B_BATCH_A", "task_stratum": "ordinary"},
        ],
        submissions=[{"worker_id": "w1", "task_id": "t1"}, {"worker_id": "w2", "task_id": "t3"}],
        profiles=[_profile("w1", completion="closed_partial_usable"), _profile("w2")],
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["c2b_closeout_ready"] is True
    assert (payload["assigned_count"], payload["submitted_count"], payload["missing_count"]) == (3, 2, 1)
    w1 = next(row for row in payload["worker_summaries"] if row["worker_id"] == "1")
    assert (w1["assigned"], w1["submitted"], w1["missing"], w1["terminal_status"]) == (2, 1, 1, "closed_partial_usable")


def test_missing_without_terminal_disposition_still_fails(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="terminal disposition"):
        _case(
            tmp_path,
            assignments=[{"worker_id": "w1", "task_id": "t1", "c2_component": "common_anchor", "assignment_batch_id": "C2B_BATCH_A", "task_stratum": "ordinary"}],
            submissions=[], profiles=[_profile("w1", completion="in_progress")],
        )


def test_worker_terminal_disposition_must_cover_a_real_missing_assignment(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no missing assignment"):
        _case(
            tmp_path,
            assignments=[{"worker_id": "w1", "task_id": "t1", "c2_component": "common_anchor", "assignment_batch_id": "C2B_BATCH_A", "task_stratum": "ordinary"}],
            submissions=[{"worker_id": "w1", "task_id": "t1"}], profiles=[_profile("w1")],
            terminal_dispositions=[{
                "worker_id": "w1", "task_id": "", "terminal_status": "closed_partial_insufficient",
                "missing_reason": "lost_to_followup_after_C1_before_C2B_completion",
            }],
        )


def test_nonstarter_does_not_block_other_workers(tmp_path: Path) -> None:
    output = _case(
        tmp_path,
        assignments=[
            {"worker_id": "w1", "task_id": "t1", "c2_component": "common_anchor", "assignment_batch_id": "C2B_BATCH_A", "task_stratum": "ordinary"},
            {"worker_id": "w2", "task_id": "t2", "c2_component": "common_anchor", "assignment_batch_id": "C2B_BATCH_A", "task_stratum": "ordinary"},
        ],
        submissions=[{"worker_id": "w2", "task_id": "t2"}],
        profiles=[_profile("w1", completion="nonstarter"), _profile("w2")],
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["c2b_closeout_ready"] is True
    assert payload["n_workers_nonstarter"] == 1
    assert payload["n_workers_fully_evaluable"] == 1


def test_not_evaluable_axis_is_local_fallback_not_global_closeout_failure(tmp_path: Path) -> None:
    output = _case(
        tmp_path,
        assignments=[
            {"worker_id": "w1", "task_id": "t1", "c2_component": "common_anchor", "assignment_batch_id": "C2B_BATCH_A", "task_stratum": "ordinary"},
            {"worker_id": "w2", "task_id": "t2", "c2_component": "common_anchor", "assignment_batch_id": "C2B_BATCH_A", "task_stratum": "ordinary"},
        ],
        submissions=[{"worker_id": "w1", "task_id": "t1"}, {"worker_id": "w2", "task_id": "t2"}],
        profiles=[_profile("w1", risk="not_evaluable"), _profile("w2")],
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["c2b_closeout_ready"] is True
    assert payload["n_workers_risk_adjustment_eligible"] == 1
    w1 = next(row for row in payload["worker_summaries"] if row["worker_id"] == "1")
    assert w1["risk_slope_status"] == "not_evaluable"
    assert w1["risk_adjustment"] == 0


def test_profile_without_any_legal_axis_status_fails_closed(tmp_path: Path) -> None:
    profile = _profile("w1")
    for field in ("Q_GT_profile_status", "R_peer_profile_status", "F_struct_profile_status", "c1_risk_slope_status", "conditional_component_status"):
        profile.pop(field)
    with pytest.raises(ValueError, match="missing fields"):
        _case(
            tmp_path,
            assignments=[{"worker_id": "w1", "task_id": "t1", "c2_component": "common_anchor", "assignment_batch_id": "C2B_BATCH_A", "task_stratum": "ordinary"}],
            submissions=[{"worker_id": "w1", "task_id": "t1"}], profiles=[profile],
        )


def test_unassigned_or_duplicate_submission_fails(tmp_path: Path) -> None:
    assignment = [{"worker_id": "w1", "task_id": "t1", "c2_component": "common_anchor", "assignment_batch_id": "C2B_BATCH_A", "task_stratum": "ordinary"}]
    with pytest.raises(ValueError, match="unassigned submission"):
        _case(tmp_path / "unassigned", assignments=assignment, submissions=[{"worker_id": "w1", "task_id": "other"}], profiles=[_profile("w1")])
    with pytest.raises(ValueError, match="duplicate/revision"):
        _case(tmp_path / "duplicate", assignments=assignment, submissions=[{"worker_id": "w1", "task_id": "t1"}, {"worker_id": "w1", "task_id": "t1"}], profiles=[_profile("w1")])


def test_formal_closeout_requires_reference_review_record(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="formal C2-B closeout requires reference_conflict_review_record"):
        _case(
            tmp_path,
            assignments=[{"worker_id": "w1", "task_id": "t1", "c2_component": "common_anchor", "assignment_batch_id": "C2B_BATCH_A", "task_stratum": "ordinary"}],
            submissions=[{"worker_id": "w1", "task_id": "t1"}],
            profiles=[_profile("w1")],
            reference_review=False,
        )
