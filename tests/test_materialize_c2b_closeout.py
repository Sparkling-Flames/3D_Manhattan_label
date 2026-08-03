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


def _case(tmp_path: Path, *, assignments: list[dict[str, str]], submissions: list[dict[str, str]], profiles: list[dict[str, str]]) -> Path:
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
    planned.write_text(json.dumps([{"data": {"planned_task_id": row["task_id"]}} for row in assignments]), encoding="utf-8")
    deployment_manifest = tmp_path / "deployment_manifest.json"
    deployment_manifest.write_text(json.dumps({
        "schema_version": "c2b_worker_deployment_manifest_v1", "deployments": [{
            "deployment_id": "zh", "language_group": "Chinese", "server_instance_id": "server-zh",
            "project_id": "project-zh", "worker_ids": [row["worker_id"] for row in profiles],
            "planned_import_path": str(planned), "planned_import_sha256": sha256_file(planned),
        }],
    }), encoding="utf-8")
    launch = (tmp_path / "launch.json"); launch.write_text(json.dumps({
        "schema_version": "paper_a_c2b_launch_ready_report_v4", "C2B_LAUNCH_READY": True,
        "assignment_batch_id": "C2B_BATCH_A", "assignment_sha256": sha256_file(assignment),
        "deployment_manifest_path": str(deployment_manifest), "deployment_manifest_sha256": sha256_file(deployment_manifest),
        "deployments": [{
            "deployment_id": "zh", "language_group": "Chinese", "server_instance_id": "server-zh",
            "project_id": "project-zh", "planned_import_path": str(planned),
            "planned_import_sha256": sha256_file(planned),
        }],
    }), encoding="utf-8")
    runtime = (tmp_path / "runtime.json"); runtime.write_text(json.dumps({
        "formal_ready": True, "C2B_RUNTIME_BINDING_READY": True, "assignment_batch_id": "C2B_BATCH_A",
    }), encoding="utf-8")
    private = (tmp_path / "private.json"); private.write_text(json.dumps({
        "formal_ready": True, "private_assignment_list_audit_passed": True,
        "assignment_batch_id": "C2B_BATCH_A", "assignment_manifest_sha256": sha256_file(assignment),
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
    output = tmp_path / "closeout.json"
    materialize(
        submission, profile, manifest, design, snapshot, assignment, roster, rules,
        launch, runtime, private, output,
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
