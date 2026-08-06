from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from tools.thesis_main.analysis.c1_materialize_c2_gap_audits import build_precision_assignments, build_precision_plan, materialize as materialize_c2a
from tools.thesis_main.analysis.materialize_c2b_closeout import materialize as materialize_c2b_closeout
from tools.thesis_main.analysis.paper_a_contracts import METHOD_CONTRACT, load_method_contract


def _csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _reference_review(tmp_path: Path) -> Path:
    path = tmp_path / "reference_review.csv"
    fields = [
        "schema_version", "base_task_id", "registry_status_before_review", "reference_status_before_review",
        "reference_normalizer_status_before_review", "geometry_reference_ready_before_review", "review_status",
        "review_disposition", "reviewer_blinding", "review_evidence", "reviewed_by", "reviewed_at",
        "original_reference_sha256", "method_contract_sha256",
    ]
    _csv(path, fields, [{
        "schema_version": "paper_a_reference_conflict_review_record_v2", "base_task_id": "t1",
        "registry_status_before_review": "approved_by_frozen_reference_policy",
        "reference_status_before_review": "use_existing_public_gt_as_is",
        "reference_normalizer_status_before_review": "passed", "geometry_reference_ready_before_review": "true",
        "review_status": "closed", "review_disposition": "retain_original",
        "reviewer_blinding": "worker_and_analysis_metric_blinded", "review_evidence": "manual_scene_review_record",
        "reviewed_by": "reviewer-1", "reviewed_at": "2026-08-05T12:00:00Z",
        "original_reference_sha256": "a" * 64, "method_contract_sha256": _sha(METHOD_CONTRACT),
    }])
    return path


def _closeout_dependencies(tmp_path: Path, manifest_data: dict) -> tuple[Path, Path, Path, Path, Path, Path, Path]:
    paths = [
        tmp_path / "c1_closeout.json", tmp_path / "c2b_assignment.csv",
        tmp_path / "worker_roster.csv", tmp_path / "rule_config.json", tmp_path / "launch.json",
        tmp_path / "runtime.json", tmp_path / "private.json",
    ]
    paths[1].write_text("task_id,worker_id,c2_component,assignment_batch_id\nt1,w1,common_anchor,C2B_BATCH_A\n", encoding="utf-8")
    assignment_sha = _sha(paths[1])
    planned = tmp_path / "planned.json"
    planned.write_text(json.dumps([{"data": {"planned_task_id": "t1", "deployment_id": "zh", "language_group": "Chinese", "server_instance_id": "server-zh", "project_id": "project-zh", "c2b_batch_id": "C2B_BATCH_A", "selected_design_sha": "design-sha"}}]), encoding="utf-8")
    deployment_manifest = tmp_path / "deployment_manifest.json"
    deployment_manifest.write_text(json.dumps({
        "schema_version": "c2b_worker_deployment_manifest_v1", "method_contract_version": load_method_contract()["contract_version"], "method_contract_sha256": _sha(METHOD_CONTRACT), "assignment_batch_id": "C2B_BATCH_A", "assignment_sha256": assignment_sha, "deployments": [{
            "deployment_id": "zh", "language_group": "Chinese", "server_instance_id": "server-zh",
            "project_id": "project-zh", "server_url": "https://example.test", "worker_registry_sha256": "r" * 64, "worker_ids": ["w1"],
            "method_contract_version": load_method_contract()["contract_version"], "method_contract_sha256": _sha(METHOD_CONTRACT),
            "assignment_sha256": assignment_sha, "selected_design_sha": "design-sha",
            "planned_import_path": str(planned), "planned_import_sha256": _sha(planned),
        }],
    }), encoding="utf-8")
    runtime_export = tmp_path / "runtime-export.json"
    runtime_export.write_text(json.dumps([{"id": "runtime-t1", "data": {"planned_task_id": "t1", "deployment_id": "zh", "language_group": "Chinese", "server_instance_id": "server-zh", "project_id": "project-zh", "c2b_batch_id": "C2B_BATCH_A", "selected_design_sha": "design-sha"}}]), encoding="utf-8")
    runtime_mapping = tmp_path / "runtime_mapping.csv"
    runtime_mapping.write_text("worker_id,planned_task_id,runtime_task_id\n", encoding="utf-8")
    contents = [
        json.dumps({"schema_version": "paper_a_c1_batch_analysis_snapshot_v1", "status": "formal_design_eligible", "C2B_DESIGN_INPUT_FROZEN_FROM_C1_A": True}),
        None,
        "worker_id\nw1\n",
        json.dumps({"min_common_anchor_per_worker": 1, "min_bridge_per_worker": 0, "min_task_support": 1}),
        json.dumps({"schema_version": "paper_a_c2b_launch_ready_report_v4", "C2B_LAUNCH_READY": True, "method_contract_version": load_method_contract()["contract_version"], "method_contract_sha256": _sha(METHOD_CONTRACT), "assignment_batch_id": "C2B_BATCH_A", "assignment_sha256": assignment_sha, "selected_design_sha": "design-sha", "deployment_manifest_path": str(deployment_manifest), "deployment_manifest_sha256": _sha(deployment_manifest), "deployments": [{"deployment_id": "zh", "language_group": "Chinese", "server_instance_id": "server-zh", "server_url": "https://example.test", "project_id": "project-zh", "worker_registry_sha256": "r" * 64, "method_contract_version": load_method_contract()["contract_version"], "method_contract_sha256": _sha(METHOD_CONTRACT), "assignment_sha256": assignment_sha, "selected_design_sha": "design-sha", "planned_import_path": str(planned), "planned_import_sha256": _sha(planned)}]}),
        json.dumps({"schema_version": "paper_a_c2b_runtime_mapping_audit_v2", "method_contract_version": load_method_contract()["contract_version"], "method_contract_sha256": _sha(METHOD_CONTRACT), "formal_ready": True, "C2B_RUNTIME_BINDING_READY": True, "assignment_batch_id": "C2B_BATCH_A", "selected_design_sha": "design-sha", "deployment_manifest_sha256": _sha(deployment_manifest), "deployment_ids": ["zh"], "planned_import_sha256": {"zh": _sha(planned)}, "runtime_export_sha256": {"zh": _sha(runtime_export)}, "runtime_mapping_sha256": _sha(runtime_mapping), "runtime_task_count": 1, "runtime_task_count_by_deployment": {"zh": 1}, "worker_task_binding_count": 1, "dependencies": [{"role": "RUNTIME_MAPPING", "path": str(runtime_mapping), "sha256": _sha(runtime_mapping)}, {"role": "PLANNED_IMPORT_zh", "path": str(planned), "sha256": _sha(planned)}, {"role": "RUNTIME_EXPORT_zh", "path": str(runtime_export), "sha256": _sha(runtime_export)}]}),
        json.dumps({"schema_version": "paper_a_c2b_private_assignment_list_audit_v2", "method_contract_version": load_method_contract()["contract_version"], "method_contract_sha256": _sha(METHOD_CONTRACT), "formal_ready": True, "private_assignment_list_audit_passed": True, "assignment_batch_id": "C2B_BATCH_A", "assignment_manifest_sha256": assignment_sha, "worker_distribution_sha256": assignment_sha, "dependencies": [{"role": "ASSIGNMENT_MANIFEST", "path": str(paths[1]), "sha256": assignment_sha}, {"role": "WORKER_DISTRIBUTION", "path": str(paths[1]), "sha256": assignment_sha}]}),
    ]
    for path, content in zip(paths, contents):
        if content is not None:
            path.write_text(content, encoding="utf-8")
    manifest_data.setdefault("input_sha256", {}).update({
        "c1_a_snapshot": _sha(paths[0]),
        "c2b_assignment_csv": _sha(paths[1]),
        "worker_roster_csv": _sha(paths[2]),
        "rule_config": _sha(paths[3]),
        "c2b_launch_report": _sha(paths[4]),
        "c2b_runtime_mapping_audit": _sha(paths[5]),
        "c2b_private_assignment_audit": _sha(paths[6]),
    })
    return tuple(paths)


def test_precision_adds_only_needed_paired_blocks_and_caps_uncertain(tmp_path: Path) -> None:
    profile = tmp_path / "post_c2b.csv"
    _csv(profile, ["worker_id", "support", "ci_half_width"], [
        {"worker_id": "met", "support": 8, "ci_half_width": 0.14},
        {"worker_id": "fillable", "support": 8, "ci_half_width": 0.18},
        {"worker_id": "capped", "support": 8, "ci_half_width": 0.4},
    ])
    design = tmp_path / "design.json"
    design.write_text(json.dumps({
        "manifest_version": "c2_design_v1",
        "input_sha256": {"worker_profile_csv": _sha(profile)},
        "precision": {"target_ci_half_width": 0.15, "max_additional_blocks": 2},
    }), encoding="utf-8")
    pool = tmp_path / "c2a_pool.csv"
    _csv(pool, ["task_id", "base_task_id", "task_stratum", "c2a_rp_eligible"], [
        {"task_id": f"{stratum}-{index}", "base_task_id": f"{stratum}-{index}",
         "task_stratum": stratum, "c2a_rp_eligible": "true"}
        for stratum in ("ordinary", "stress") for index in range(1, 4)
    ])
    summary = materialize_c2a(profile, design, tmp_path / "out", task_pool_csv=pool)
    rows = {row["worker_id"]: row for row in _rows(tmp_path / "out" / "precision_plan_C2A_RP.csv")}
    assignments = _rows(tmp_path / "out" / "assignment_manifest_C2A_RP.csv")

    assert rows["met"]["additional_blocks"] == "0"
    assert rows["fillable"]["ordinary_tasks"] == rows["fillable"]["stress_tasks"] == "2"
    assert rows["fillable"]["declared_support_after"] == "12"
    assert rows["capped"]["additional_blocks"] == "2"
    assert rows["capped"]["routing_eligibility"] == "uncertain_fallback_global"
    assert rows["capped"]["unmet_reason"] == "target_not_met_at_frozen_cap"
    assert len(assignments) == 8
    assert {(row["worker_id"], row["task_stratum"]) for row in assignments} == {
        ("fillable", "ordinary"), ("fillable", "stress"),
        ("capped", "ordinary"), ("capped", "stress"),
    }
    assert all(row["task_id"] for row in assignments)
    assert summary["searches_new_risk_family"] is False
    assert summary["modifies_c1"] is False


def test_precision_plan_marks_zero_support_worker_not_evaluable() -> None:
    row = build_precision_plan(
        [{"worker_id": "27", "support": 0, "risk_slope_ci_half_width": ""}],
        target_half_width=0.15, max_additional_blocks=2, manifest_sha="m", formal=True,
    )[0]

    assert row["gap_reason"] == "precision_not_evaluable"
    assert row["unmet_reason"] == "precision_not_evaluable"
    assert row["terminal_state"] == "not_evaluable"
    assert row["routing_eligibility"] == "not_evaluable"
    assert row["fallback_action"] == "STRONG_GLOBAL"
    assert row["additional_blocks"] == row["ordinary_tasks"] == row["stress_tasks"] == 0


def test_c2a_rp_manifest_cannot_override_four_task_contract_cap(tmp_path: Path) -> None:
    profile = tmp_path / "post_c2b.csv"
    _csv(profile, ["worker_id", "support", "ci_half_width"], [{"worker_id": "w1", "support": 8, "ci_half_width": 0.4}])
    design = tmp_path / "design.json"
    design.write_text(json.dumps({
        "manifest_version": "c2_design_v1",
        "input_sha256": {"worker_profile_csv": _sha(profile)},
        "precision": {"target_ci_half_width": 0.15, "max_additional_blocks": 3},
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="normative C2-A-RP cap"):
        materialize_c2a(profile, design, tmp_path / "out")


def test_c2a_task_support_cap_counts_prior_assignment_history() -> None:
    with pytest.raises(ValueError, match="insufficient C2-A-RP ordinary tasks"):
        build_precision_assignments(
            [{"worker_id": "w1", "additional_blocks": 1, "ordinary_tasks": 1, "stress_tasks": 1, "current_ci_half_width": .2, "current_support": 8, "target_component": "risk_slope", "gap_reason": "target_not_met"}],
            [{"task_id": "o1", "base_task_id": "o1", "task_stratum": "ordinary"}, {"task_id": "s1", "base_task_id": "s1", "task_stratum": "stress"}],
            manifest_sha="m", c2b_sha="c", profile_sha="p",
            history_rows=[{"worker_id": "w9", "task_id": "o1", "base_task_id": "o1"}],
            max_task_support=1,
        )


def test_c2a_prior_round_seen_history_does_not_consume_c2a_support_cap() -> None:
    assignments = build_precision_assignments(
        [{"worker_id": "w1", "additional_blocks": 1, "ordinary_tasks": 1, "stress_tasks": 1, "current_ci_half_width": .2, "current_support": 8, "target_component": "risk_slope", "gap_reason": "target_not_met"}],
        [{"task_id": "o1", "base_task_id": "o1", "task_stratum": "ordinary"}, {"task_id": "s1", "base_task_id": "s1", "task_stratum": "stress"}],
        manifest_sha="m", c2b_sha="c", profile_sha="p",
        history_rows=[
            {"round_id": "C2-B", "worker_id": "w2", "task_id": "o1", "base_task_id": "o1"},
            {"round_id": "C2-B", "worker_id": "w3", "task_id": "o1", "base_task_id": "o1"},
        ],
        max_task_support=2,
    )
    assert {row["task_id"] for row in assignments} == {"o1", "s1"}


def test_c2a_assignment_rejects_current_cross_stratum_base_reuse() -> None:
    with pytest.raises(ValueError, match="insufficient C2-A-RP stress tasks"):
        build_precision_assignments(
            [{"worker_id": "w1", "additional_blocks": 1, "ordinary_tasks": 1, "stress_tasks": 1, "current_ci_half_width": .2, "current_support": 8, "target_component": "risk_slope", "gap_reason": "target_not_met"}],
            [{"task_id": "o1", "base_task_id": "same", "task_stratum": "ordinary"}, {"task_id": "s1", "base_task_id": "same", "task_stratum": "stress"}],
            manifest_sha="m", c2b_sha="c", profile_sha="p",
        )


def test_c2a_formal_dispatch_is_append_only_one_paired_block_at_a_time() -> None:
    plan = [{
        "worker_id": "w1", "additional_blocks": 2,
        "ordinary_tasks": 2, "stress_tasks": 2,
        "current_ci_half_width": .2, "current_support": 8,
        "target_component": "risk_slope", "gap_reason": "target_not_met",
    }]
    tasks = [
        {"task_id": f"ordinary-{index}", "base_task_id": f"ordinary-{index}", "task_stratum": "ordinary"}
        for index in range(2)
    ] + [
        {"task_id": f"stress-{index}", "base_task_id": f"stress-{index}", "task_stratum": "stress"}
        for index in range(2)
    ]
    first = build_precision_assignments(plan, tasks, manifest_sha="m", c2b_sha="c", profile_sha="p", dispatch_block_index=1, formal=True)
    reestimated_plan = [{**plan[0], "current_support": 10}]
    second = build_precision_assignments(reestimated_plan, tasks, manifest_sha="m", c2b_sha="c", profile_sha="p", history_rows=first, dispatch_block_index=2, formal=True)
    assert len(first) == len(second) == 2
    assert {row["block_index"] for row in first} == {1}
    assert {row["block_index"] for row in second} == {2}
    assert not {(row["worker_id"], row["task_id"]) for row in first} & {(row["worker_id"], row["task_id"]) for row in second}
    assert [row["support_after"] for row in second] == [11, 12]
    assert {row["paired_block_support_before"] for row in second} == {1}
    assert {row["paired_block_support_after"] for row in second} == {2}
    assert {row["effective_risk_slope_support_after"] for row in second} == {12}


def test_c2a_block_dispatch_skips_zero_block_workers() -> None:
    assignments = build_precision_assignments(
        [{"worker_id": "w1", "additional_blocks": 0, "ordinary_tasks": 0, "stress_tasks": 0, "current_ci_half_width": "", "current_support": 0, "target_component": "risk_slope", "gap_reason": "precision_not_evaluable"}],
        [{"task_id": "o1", "base_task_id": "o1", "task_stratum": "ordinary"}, {"task_id": "s1", "base_task_id": "s1", "task_stratum": "stress"}],
        manifest_sha="m", c2b_sha="c", profile_sha="p",
        dispatch_block_index=1, formal=True,
    )
    assert assignments == []


@pytest.mark.parametrize("blocks", [0, 1, 2])
def test_c2a_rp_legal_block_counts_materialize_paired_tasks(blocks: int) -> None:
    plan = [{
        "worker_id": "w1", "additional_blocks": blocks,
        "ordinary_tasks": blocks, "stress_tasks": blocks,
        "current_ci_half_width": .2, "current_support": 8,
        "target_component": "risk_slope", "gap_reason": "target_not_met",
    }]
    tasks = [
        {"task_id": f"ordinary-{index}", "base_task_id": f"ordinary-{index}", "task_stratum": "ordinary"}
        for index in range(2)
    ] + [
        {"task_id": f"stress-{index}", "base_task_id": f"stress-{index}", "task_stratum": "stress"}
        for index in range(2)
    ]
    assignments = build_precision_assignments(plan, tasks, manifest_sha="m", c2b_sha="c", profile_sha="p")
    assert len(assignments) == 2 * blocks
    assert sum(row["task_stratum"] == "ordinary" for row in assignments) == blocks
    assert sum(row["task_stratum"] == "stress" for row in assignments) == blocks


def test_formal_c2a_requires_bound_c2b_sha_and_real_task_pool(tmp_path: Path) -> None:
    profile = tmp_path / "post_c2b.csv"
    _csv(profile, ["schema_version", "worker_id", "support", "ci_half_width", "profile_version", "cohort_id", "enrollment_batch", "administratively_eligible", "process_eligible", "independence_eligible", "Q_GT_estimable", "reference_evaluable", "Q_GT_profile_status", "R_peer_profile_status", "peer_task_support", "F_struct_profile_status", "LOO_medoid_status", "LOO_strict_status", "global_policy_eligible", "c2_risk_model_eligible", "peer_tiebreak_eligible", "structural_gate_eligible", "F_struct_raw", "F_struct_EB", "F_struct_interval_lower", "F_struct_interval_upper", "c1_risk_slope_status", "completion_status"], [
        {"schema_version": "worker_profile_v2", "worker_id": "w1", "support": 8, "ci_half_width": 0.18, "profile_version": "p1", "cohort_id": "c1", "enrollment_batch": "original", "administratively_eligible": "true", "process_eligible": "true", "independence_eligible": "true", "Q_GT_estimable": "true", "reference_evaluable": "true", "Q_GT_profile_status": "estimated", "R_peer_profile_status": "estimated", "peer_task_support": 5, "F_struct_profile_status": "estimated", "LOO_medoid_status": "not_evaluable", "LOO_strict_status": "not_evaluable", "global_policy_eligible": "true", "c2_risk_model_eligible": "true", "peer_tiebreak_eligible": "true", "structural_gate_eligible": "true", "F_struct_raw": 0, "F_struct_EB": 0, "F_struct_interval_lower": 0, "F_struct_interval_upper": .1, "c1_risk_slope_status": "estimated", "completion_status": "completed"},
    ])
    pool = tmp_path / "pool.csv"
    _csv(pool, ["task_id", "base_task_id", "task_stratum", "c2a_rp_eligible"], [
        {"task_id": "o1", "base_task_id": "o1", "task_stratum": "ordinary", "c2a_rp_eligible": "true"},
        {"task_id": "o2", "base_task_id": "o2", "task_stratum": "ordinary", "c2a_rp_eligible": "true"},
        {"task_id": "s1", "base_task_id": "s1", "task_stratum": "stress", "c2a_rp_eligible": "true"},
        {"task_id": "s2", "base_task_id": "s2", "task_stratum": "stress", "c2a_rp_eligible": "true"},
    ])
    history = tmp_path / "history.csv"
    _csv(history, ["worker_id", "task_id", "base_task_id"], [
        {"worker_id": "w1", "task_id": "o1", "base_task_id": "o1"},
    ])
    design = tmp_path / "design.json"
    threshold = tmp_path / "threshold.json"
    threshold.write_text(json.dumps({"status": "approved", "formal_selection_allowed": True, "thresholds": {"risk_slope_ci_half_width": 0.17}, "derivation": {"formula_ids": {"risk_slope_ci_half_width": "normal_95_max_unified_slope_sd"}}}), encoding="utf-8")
    design.write_text(json.dumps({
        "manifest_version": "c2_design_v1",
        "input_sha256": {
            "worker_profile_csv": _sha(profile),
            "c2a_task_pool_csv": _sha(pool),
            "assignment_history_csv": _sha(history),
        },
        "threshold_manifest_path": str(threshold), "threshold_manifest_sha256": _sha(threshold),
        "precision": {"target_ci_half_width": 0.17, "max_additional_blocks": 1},
    }), encoding="utf-8")
    submissions = tmp_path / "c2b_submissions.csv"
    submissions.write_text("task_id,worker_id\nt1,w1\n", encoding="utf-8")
    design_summary = tmp_path / "c2b_design.summary.json"
    design_summary.write_text(json.dumps({
        "c2b_design_ready": True, "launch_ready": True, "candidate_only": False,
        "design_manifest_sha256": _sha(design),
    }), encoding="utf-8")
    profile_manifest = tmp_path / "post_profile.manifest.json"
    profile_manifest_data = {
        "manifest_version": "c2b_post_profile_v1",
        "input_sha256": {
            "c2b_submissions_csv": _sha(submissions),
            "c2b_design_summary": _sha(design_summary),
        },
        "output_sha256": {"post_c2b_worker_profile_csv": _sha(profile)},
    }
    closeout_deps = _closeout_dependencies(tmp_path, profile_manifest_data)
    profile_manifest.write_text(json.dumps(profile_manifest_data), encoding="utf-8")
    c2b = tmp_path / "c2b_closeout.summary.json"
    review = _reference_review(tmp_path)
    materialize_c2b_closeout(
        submissions, profile, profile_manifest, design_summary, *closeout_deps, c2b,
        reference_conflict_review_record=review,
    )

    with pytest.raises(ValueError, match="stale_or_unbound"):
        materialize_c2a(
            profile, design, tmp_path / "bad", c2b_summary=c2b,
            c2b_summary_sha256="0" * 64, task_pool_csv=pool,
            assignment_history_csv=history, input_status="formal",
        )
    summary = materialize_c2a(
        profile, design, tmp_path / "good", c2b_summary=c2b,
        c2b_summary_sha256=_sha(c2b), task_pool_csv=pool,
        assignment_history_csv=history, input_status="formal",
    )
    assert summary["launch_ready"] is True
    assert summary["n_assignments"] == 2
    precision = _rows(tmp_path / "good" / "precision_plan_C2A_RP.csv")[0]
    assert precision["projected_ci_half_width"] == ""
    assert precision["formal_goal"] == "risk_slope_precision"
    assigned = _rows(tmp_path / "good" / "assignment_manifest_C2A_RP.csv")
    assert "o1" not in {row["task_id"] for row in assigned}
    assert all(row["target_component"] and row["gap_reason"] for row in assigned)


def test_c2b_closeout_materializes_real_post_profile_sha_chain(tmp_path: Path) -> None:
    submissions = tmp_path / "c2b_submissions.csv"
    profile = tmp_path / "post_profile.csv"
    design = tmp_path / "c2b_design.summary.json"
    manifest = tmp_path / "post_profile.manifest.json"
    submissions.write_text("task_id,worker_id\nt1,w1\n", encoding="utf-8")
    profile.write_text("schema_version,worker_id,risk_slope_se,profile_version,cohort_id,enrollment_batch,administratively_eligible,process_eligible,independence_eligible,Q_GT_estimable,reference_evaluable,Q_GT_profile_status,R_peer_profile_status,peer_task_support,F_struct_profile_status,LOO_medoid_status,LOO_strict_status,global_policy_eligible,c2_risk_model_eligible,peer_tiebreak_eligible,structural_gate_eligible,F_struct_raw,F_struct_EB,F_struct_interval_lower,F_struct_interval_upper,c1_risk_slope_status,completion_status\nworker_profile_v2,w1,0.1,p1,c1,original,true,true,true,true,true,estimated,estimated,5,estimated,not_evaluable,not_evaluable,true,true,true,true,0,0,0,0.1,estimated,completed\n", encoding="utf-8")
    design.write_text(json.dumps({
        "c2b_design_ready": True, "launch_ready": True, "candidate_only": False,
        "design_manifest_sha256": "a" * 64
    }), encoding="utf-8")
    manifest_data = {
        "manifest_version": "c2b_post_profile_v1",
        "input_sha256": {
            "c2b_submissions_csv": _sha(submissions),
            "c2b_design_summary": _sha(design),
        },
        "output_sha256": {"post_c2b_worker_profile_csv": _sha(profile)},
    }
    closeout_deps = _closeout_dependencies(tmp_path, manifest_data)
    manifest.write_text(json.dumps(manifest_data), encoding="utf-8")
    output = tmp_path / "c2b_closeout.summary.json"
    review = _reference_review(tmp_path)
    summary = materialize_c2b_closeout(
        submissions, profile, manifest, design, *closeout_deps, output,
        reference_conflict_review_record=review,
    )
    assert summary["c2b_closeout_ready"] is True
    assert summary["post_c2b_worker_profile_sha256"] == _sha(profile)
    assert summary["post_c2b_profile_manifest_sha256"] == _sha(manifest)

    profile.write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="stale_or_unbound"):
        materialize_c2b_closeout(
            submissions, profile, manifest, design, *closeout_deps, output,
            reference_conflict_review_record=review,
        )
