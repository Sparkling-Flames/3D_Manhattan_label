from __future__ import annotations

import csv
from pathlib import Path

from tools.thesis_main.analysis.c1_c2_mainline import materialize_c2b_design_worker_profile, materialize_measurement_readiness
from tools.thesis_main.analysis.build_c2_assignment_manifest_from_c1_gaps import _empirical_cluster_bootstrap
from tools.thesis_main.analysis.materialize_c1_rehearsal_audits import (
    apply_completion_disposition,
    apply_outside_assignment_disposition,
)
from tools.thesis_main.analysis.materialize_p1_c1_predictive_association import build_source


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


def test_p1_to_c1_source_is_built_from_closeout_and_independent_c1_axes(tmp_path: Path) -> None:
    p1 = tmp_path / "p1"; p1.mkdir()
    _write(p1 / "prescreen_r0_snapshot.csv", [{"worker_id": "w1", "admission_status": "pass", "r_u_0": ".8"}])
    _write(p1 / "prescreen_worker_scope_summary.csv", [{"annotator_id": "w1", "scope_accuracy_on_adjudicated_tasks": ".9"}])
    state = tmp_path / "state.csv"
    _write(state, [{"worker_id": "w1", "Q_GT_task_adjusted": ".7", "R_LOO_compatible": ".6", "F_struct": ".1", "worker_state_status": "estimated"}])

    summary = build_source(p1, state, tmp_path / "source.csv")
    rows = list(csv.DictReader((tmp_path / "source.csv").open(encoding="utf-8")))

    assert summary == {"n_join_rows": 4, "n_workers": 1, "n_evaluable_rows": 4}
    assert {row["check_name"] for row in rows} == {
        "p1_r_u_0_to_c1_q_gt", "p1_r_u_0_to_c1_loo",
        "p1_scope_to_c1_q_gt", "p1_r_u_0_to_c1_structural_success",
    }
    assert next(row for row in rows if row["check_name"].endswith("structural_success"))["c1_metric_value"] == "0.9"
