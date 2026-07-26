from __future__ import annotations

import csv
from pathlib import Path

from tools.thesis_main.analysis.c1_c2_mainline import materialize_c2b_design_worker_profile, materialize_measurement_readiness
from tools.thesis_main.analysis.build_c2_assignment_manifest_from_c1_gaps import (
    _anchor_pool,
    _empirical_cluster_bootstrap,
    _projected_worker_intervals,
    _select_anchors,
)
from tools.thesis_main.analysis.materialize_c1_rehearsal_audits import (
    apply_completion_disposition,
    apply_outside_assignment_disposition,
    finalize_partial_completion_support,
)
from tools.thesis_main.analysis.materialize_p1_c1_predictive_association import build_source
from tools.thesis_main.analysis.materialize_c2b_legacy_provenance import EXPECTED_SOURCE_SHA256, materialize as materialize_legacy


def _write(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


def test_three_axes_are_independent_and_qgt_baseline_admission_does_not_need_loo_or_slope(tmp_path: Path) -> None:
    completion, quality, loo, structural = [tmp_path / name for name in ("completion.csv", "quality.csv", "loo.csv", "structural.csv")]
    _write(completion, [{"worker_id": "w", "completion_status": "completed", "completion_disposition_valid": "true"}])
    _write(quality, [{"canonical_annotation_id": "q", "worker_id": "w", "base_task_id": "q_task", "building_id": "b1", "global_analysis_eligible": "true"}])
    _write(loo, [{"canonical_annotation_id": "l", "worker_id": "w", "base_task_id": "l_task", "building_id": "b2", "loo_analysis_eligible": "true"}])
    _write(structural, [{"canonical_annotation_id": "s", "worker_id": "w", "base_task_id": "s_task", "building_id": "b3", "structural_opportunity_eligible": "true"}])

    readiness = materialize_measurement_readiness(completion, quality, loo, structural, tmp_path, canonical_closed=True)
    assert readiness["axis_graphs"]["gt"]["edge_count"] == 1
    assert readiness["axis_graphs"]["loo"]["edge_count"] == 1
    assert readiness["axis_graphs"]["structural"]["edge_count"] == 1
    worker = next(csv.DictReader((tmp_path / "c1_measurement_readiness_by_worker.csv").open(encoding="utf-8")))
    assert worker["Q_GT_status"] == "estimated"
    assert worker["R_LOO_status"] == "estimated"
    assert worker["F_struct_status"] == "estimated"

    state, parameters = tmp_path / "state.csv", tmp_path / "parameters.csv"
    _write(state, [{"worker_id": "w", "worker_state_status": "insufficient_support", "Q_GT_task_adjusted": ".8", "GT_support": "1", "process_eligible_support": "1", "independence_support": "1", "scope_reference_support": "1"}])
    _write(parameters, [{"worker_id": "w", "parameter_status": "insufficient_support", "risk_support": "0", "risk_slope": "", "risk_slope_se": "", "group_prior_slope": ".1", "group_prior_scale": ".5", "c1_risk_slope_status": "not_evaluable_but_C2B_eligible", "missing_rate": "0"}])
    materialize_c2b_design_worker_profile(completion, state, parameters, tmp_path / "c1_measurement_readiness_by_worker.csv", tmp_path)
    profile = next(csv.DictReader((tmp_path / "c2b_design_worker_profile.csv").open(encoding="utf-8")))
    assert profile["c2b_baseline_eligible"].lower() == "true"
    assert profile["c2_candidate_eligible"].lower() == "true"
    assert profile["c1_risk_slope_status"] == "not_evaluable_but_C2B_eligible"


def test_completion_and_outside_dispositions_change_consumed_evidence(tmp_path: Path) -> None:
    completion = tmp_path / "completion.csv"
    _write(completion, [{"worker_id": "w", "completion_status": "partial_noncompletion"}])
    disposition = tmp_path / "completion_disposition.csv"
    source_sha = __import__("hashlib").sha256(completion.read_bytes()).hexdigest()
    _write(disposition, [{"worker_id": "w", "source_completion_audit_sha256": source_sha, "final_completion_disposition": "administrative_exclusion", "reviewed_by": "r", "reviewed_at": "2026-07-25", "reason": "withdrawn"}])
    result = apply_completion_disposition(completion, disposition, tmp_path)
    assert result["applied_count"] == 1
    assert next(csv.DictReader((tmp_path / "c1_worker_completion_disposition_evidence.csv").open(encoding="utf-8"))) ["completion_status"] == "administrative_exclusion"

    outside = tmp_path / "outside.csv"
    _write(outside, [{"canonical_annotation_id": "a", "classification": "unknown"}])
    outside_disposition = tmp_path / "outside_disposition.csv"
    outside_sha = __import__("hashlib").sha256(outside.read_bytes()).hexdigest()
    _write(outside_disposition, [{"canonical_annotation_id": "a", "source_outside_assignment_audit_sha256": outside_sha, "final_process_disposition": "valid_authorized_exception", "reviewed_by": "r", "reviewed_at": "2026-07-25", "reason": "authorized"}])
    applied = apply_outside_assignment_disposition(outside, outside_disposition, tmp_path)
    assert applied["applied_count"] == 1
    evidence = next(csv.DictReader((tmp_path / "c1_outside_assignment_disposition_evidence.csv").open(encoding="utf-8")))
    assert evidence["process_eligible_override"] == "True"


def test_computed_completion_needs_only_exception_dispositions_and_partial_support_promotes_locally(tmp_path: Path) -> None:
    completion = tmp_path / "completion.csv"
    _write(completion, [
        {"worker_id": "usable", "completion_status": "closed_partial_insufficient"},
        {"worker_id": "insufficient", "completion_status": "closed_partial_insufficient"},
    ])
    result = apply_completion_disposition(completion, None, tmp_path)
    assert result["applied_count"] == 0
    evidence = list(csv.DictReader((tmp_path / "c1_worker_completion_disposition_evidence.csv").open(encoding="utf-8")))
    assert all(row["completion_disposition_valid"].lower() == "true" for row in evidence)
    eligibility = tmp_path / "eligibility.csv"
    _write(eligibility, [{
        "worker_id": "usable", "global_analysis_eligible": "true",
        "loo_analysis_eligible": "false", "structural_opportunity_eligible": "false",
    }])
    finalized = finalize_partial_completion_support(
        tmp_path / "c1_worker_completion_disposition_evidence.csv", eligibility, tmp_path, {},
        collection_window_closed=True,
    )
    rows = {row["worker_id"]: row for row in csv.DictReader((tmp_path / "c1_worker_completion_audit.csv").open(encoding="utf-8"))}
    assert rows["usable"]["completion_status"] == "closed_partial_usable"
    assert rows["usable"]["Q_GT_eligible_row_support"] == "1"
    assert rows["insufficient"]["completion_status"] == "closed_partial_insufficient"
    assert finalized["closed_partial_usable_worker_count"] == 1


def test_hierarchical_simulation_rebuilds_graph_after_delivery() -> None:
    workers = [
        {"worker_id": "w1", "Q_GT_task_adjusted": ".8", "risk_slope_for_simulation": ".1", "between_worker_slope_sd": ".1", "outcome_residual_sd": ".1", "worker_intercept_sd": ".02", "task_sd": ".03", "building_sd": ".04", "Q_GT_baseline_se": ".05", "missing_rate": "0", "F_struct": "1"},
        {"worker_id": "w2", "Q_GT_task_adjusted": ".7", "risk_slope_for_simulation": ".1", "between_worker_slope_sd": ".1", "outcome_residual_sd": ".1", "worker_intercept_sd": ".02", "task_sd": ".03", "building_sd": ".04", "Q_GT_baseline_se": ".05", "missing_rate": "0", "F_struct": "0"},
    ]
    tasks = {
        "t1": {"task_id": "t1", "building_id": "b1", "risk_design_score_A": ".1", "risk_design_stratum": "ordinary"},
        "t2": {"task_id": "t2", "building_id": "b2", "risk_design_score_A": ".9", "risk_design_stratum": "stress"},
    }
    assignments = [{"worker_id": worker, "task_id": task} for worker in ("w1", "w2") for task in tasks]
    result = _empirical_cluster_bootstrap("d", workers, assignments, tasks, {"worker_task_graph_connected": True}, seed=7, draws=30)
    assert result["simulation_method"] == "hierarchical_building_task_resampling_with_c1_group_prior"
    assert result["graph_connectivity_probability"] == 0
    assert float(result["expected_assignment_count"]) < len(assignments)
    assert result["worker_rank_spearman"] != ""


def test_group_prior_only_worker_has_finite_projection() -> None:
    workers = [{
        "worker_id": "w", "risk_slope_se": "", "risk_slope_support": "0",
        "group_prior_slope": ".1", "between_worker_slope_sd": ".2",
        "outcome_residual_sd": ".1", "worker_intercept_sd": ".02",
        "task_sd": ".03", "building_sd": ".04", "missing_rate": "0", "F_struct": "0",
    }]
    tasks = {
        "o": {"task_id": "o", "building_id": "b1", "risk_design_score_A": ".1", "risk_design_stratum": "ordinary"},
        "s": {"task_id": "s", "building_id": "b2", "risk_design_score_A": ".9", "risk_design_stratum": "stress"},
    }
    assignments = [{"worker_id": "w", "task_id": task, "design_id": "d", "c2_component": "common_anchor"} for task in tasks]
    projected, rows = _projected_worker_intervals(workers, assignments, tasks, seed=1, draws=30, require_c1_slopes=False)
    assert projected < float("inf")
    assert rows[0]["projected_interval_half_width"] != ""


def test_all_finally_eligible_tasks_can_be_anchor_candidates_without_legacy_flags() -> None:
    tasks = [
        {"task_id": "o", "assignment_eligible": "true", "risk_design_stratum": "ordinary", "risk_design_vector_A": "[0,0,0,0]", "building_id": "b1"},
        {"task_id": "s", "assignment_eligible": "true", "risk_design_stratum": "stress", "risk_design_vector_A": "[1,1,1,1]", "building_id": "b2"},
    ]
    pool = _anchor_pool(tasks)
    selected = _select_anchors(pool, 2)
    assert {row["task_id"] for row in pool} == {"o", "s"}
    assert {row["risk_design_stratum"] for row in selected} == {"ordinary", "stress"}


def test_p1_to_c1_source_is_built_from_closeout_and_independent_c1_axes(tmp_path: Path) -> None:
    p1 = tmp_path / "p1"; p1.mkdir()
    _write(p1 / "prescreen_r0_snapshot.csv", [{"worker_id": "w1", "admission_status": "pass", "r_u_0": ".8"}])
    _write(p1 / "prescreen_worker_scope_summary.csv", [{"annotator_id": "w1", "scope_accuracy_on_adjudicated_tasks": ".9"}])
    state = tmp_path / "state.csv"
    _write(state, [{"worker_id": "w1", "Q_GT_task_adjusted": ".7", "R_LOO_compatible": ".6", "F_struct": ".1", "worker_state_status": "estimated"}])

    summary = build_source(p1, state, tmp_path / "source.csv")
    rows = list(csv.DictReader((tmp_path / "source.csv").open(encoding="utf-8")))

    assert summary["n_join_rows"] == 4 and summary["n_workers"] == 1 and summary["n_evaluable_rows"] == 4
    assert summary["p1_integrity_amendment_applied"] is False
    assert {row["check_name"] for row in rows} == {
        "p1_r_u_0_to_c1_q_gt", "p1_r_u_0_to_c1_loo",
        "p1_scope_to_c1_q_gt", "p1_r_u_0_to_c1_structural_success",
    }
    assert next(row for row in rows if row["check_name"].endswith("structural_success"))["c1_metric_value"] == "0.9"


def test_p1_predictive_uses_retrospective_corrected_geometry_and_suppresses_legacy_scope(tmp_path: Path) -> None:
    p1 = tmp_path / "p1"; p1.mkdir(); corrected = tmp_path / "corrected"; corrected.mkdir()
    _write(p1 / "prescreen_r0_snapshot.csv", [{"worker_id": "w1", "admission_status": "pass", "r_u_0": ".99"}])
    _write(p1 / "prescreen_worker_scope_summary.csv", [{"annotator_id": "w1", "scope_accuracy_on_adjudicated_tasks": ".95"}])
    _write(corrected / "p1_worker_evidence_status_v1.csv", [{"worker_id": "w1", "p1_predictive_capability_eligible": "true"}])
    _write(corrected / "p1_worker_geometry_profile_v1.csv", [{"worker_id": "w1", "p1_geometry_component": ".61"}])
    state = tmp_path / "state.csv"; _write(state, [{"worker_id": "w1", "Q_GT_task_adjusted": ".7", "R_LOO_compatible": ".6", "F_struct": ".1", "worker_state_status": "estimated"}])
    summary = build_source(p1, state, tmp_path / "source.csv", correction_dir=corrected)
    rows = list(csv.DictReader((tmp_path / "source.csv").open(encoding="utf-8")))
    assert summary["p1_integrity_amendment_applied"] is True
    assert {row["check_name"] for row in rows} == {"p1_r_u_0_to_c1_q_gt", "p1_r_u_0_to_c1_loo", "p1_r_u_0_to_c1_structural_success"}
    assert {row["p1_metric_value"] for row in rows} == {".61"}


def test_legacy_reverse_is_provenance_only_and_history_gate_wins(tmp_path: Path) -> None:
    manifest, inventory, evidence = tmp_path / "legacy.csv", tmp_path / "inventory.csv", tmp_path / "evidence.csv"
    legacy_rows = [{"selection_rank": index + 1, "task_id": f"t{index}", "base_task_id": f"b{index}", "image_id": f"i{index}", "source_path": f"i{index}.jpg", "selection_reason": "legacy", "source_manifest_sha256": EXPECTED_SOURCE_SHA256, "formal_selection_priority": "false"} for index in range(13)]
    _write(manifest, legacy_rows)
    _write(inventory, [{"task_id": f"t{index}", "base_task_id": f"b{index}", "image_id": f"i{index}"} for index in range(13)])
    _write(evidence, [{"base_task_id": f"b{index}", "image_id": f"i{index}", "assignment_eligible": "false" if index == 0 else "true", "history_overlap": "true" if index == 0 else "false", "exclusion_reason": "history_overlap" if index == 0 else ""} for index in range(13)])
    result = materialize_legacy(manifest, inventory, tmp_path / "out", task_eligibility_csv=evidence)
    rows = list(csv.DictReader((tmp_path / "out" / "c2_legacy_reverse_candidate_audit.csv").open(encoding="utf-8")))
    assert result["legacy_priority_used"] is False
    assert rows[0]["assignment_eligible"].lower() == "false"
    assert rows[0]["eligibility_exclusion_reason"] == "history_overlap"
