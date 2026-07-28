from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from tools.thesis_main.analysis.c1_c2_mainline import materialize_c2b_design_worker_profile, materialize_measurement_readiness
from tools.thesis_main.analysis.build_c2_assignment_manifest_from_c1_gaps import (
    _anchor_pool,
    _empirical_cluster_bootstrap,
    _joint_qgt_posterior,
    _projected_worker_intervals,
    _recompute_stability_audits,
    _resolve_slope_distribution,
    _select_anchors,
)
from tools.thesis_main.analysis.materialize_c1_rehearsal_audits import (
    apply_completion_disposition,
    apply_outside_assignment_disposition,
    finalize_partial_completion_support,
    materialize_independence,
    materialize_three_track_worker_state,
)
from tools.thesis_main.analysis.c1_task_adjusted_quality import _BootstrapSupportFailure, estimate_task_adjusted_qgt
from tools.thesis_main.analysis.materialize_c1_c2_design_parameters import _risk_model_spec, _variance_boundary_decision
from tools.thesis_main.analysis.c2b_static_evidence import (
    materialize_history_overlap,
    materialize_p1_integrity_bundle,
    materialize_building_registry_from_scene_mapping,
    materialize_reference_candidate_leakage,
    materialize_split_proposals,
    materialize_static_freeze_manifest,
    validate_p1_integrity_bundle,
)
from tools.thesis_main.analysis.run_c1_precloseout_rehearsal import _validate_p1_integrity_for_mode
from tools.thesis_main.analysis.materialize_p1_c1_predictive_association import build_source
from tools.thesis_main.analysis.materialize_c2b_legacy_provenance import EXPECTED_SOURCE_SHA256, materialize as materialize_legacy


def _write(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


def _simulation_worker(worker: str, *, baseline: float, structural: float) -> dict[str, str]:
    workers = ("w1", "w2")
    covariance = {name: (.0025 if name == worker else .0005) for name in workers}
    return {
        "worker_id": worker, "Q_GT_task_adjusted": str(baseline),
        "Q_GT_contrast_covariance_row_json": __import__("json").dumps(covariance),
        "Q_GT_baseline_se": ".05", "group_slope_mean": ".1", "group_slope_se": ".02",
        "risk_slope_for_simulation": ".1", "between_worker_slope_sd": ".1",
        "outcome_residual_sd": ".1", "worker_intercept_sd": ".02",
        "task_sd": ".03", "building_sd": ".04", "missing_rate": "0", "F_struct": str(structural),
    }


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


def test_unique_qgt_estimator_emits_measurement_evidence_without_rank(tmp_path: Path) -> None:
    rows = [
        {
            "worker_id": worker, "base_task_id": task, "condition": "manual",
            "building_id": f"b{index % 3}", "Q_GT_raw": value,
            "global_analysis_eligible": "true",
        }
        for index, (task, w1, w2) in enumerate((
            ("t1", .90, .72), ("t2", .45, .61), ("t3", .82, .66),
            ("t4", .53, .70), ("t5", .75, .63), ("t6", .49, .59),
        ))
        for worker, value in (("w1", w1), ("w2", w2))
    ]
    workers, tasks, audit = estimate_task_adjusted_qgt(
        rows, estimator_contract={"bootstrap_replicates": 20, "minimum_successful_bootstrap_fraction": .5},
    )
    assert audit["status"] == "estimated" and audit["ranking_materialized"] is False
    assert len(tasks) == 6
    assert all(row["global_rank"] == "" and row["provisional_rank"] == "" for row in workers)
    assert all(set(json.loads(row["Q_GT_contrast_covariance_row_json"])) == {"w1", "w2"} for row in workers)


def test_qgt_bootstrap_missing_worker_is_a_failed_replicate_not_a_model_abort(monkeypatch) -> None:
    rows = [
        {
            "worker_id": worker, "base_task_id": task, "condition": "manual",
            "building_id": "b1", "Q_GT_raw": value, "global_analysis_eligible": "true",
        }
        for task, values in (("t1", (.8, .7)), ("t2", (.6, .5)))
        for worker, value in zip(("w1", "w2"), values)
    ]
    calls = {"count": 0}

    def fake_fit(_frame, _contract):
        calls["count"] += 1
        estimates = {"w1": .8, "w2": .7}
        if calls["count"] == 2:
            estimates.pop("w2")
        return {
            "formula": "quality ~ 0 + C(worker_id)", "optimizer": "test",
            "estimates": estimates, "task_effects": {}, "warnings": [],
            "residual_variance": .01, "task_intercept_variance": .01,
        }

    monkeypatch.setattr("tools.thesis_main.analysis.c1_task_adjusted_quality._fit_once", fake_fit)
    workers, _tasks, audit = estimate_task_adjusted_qgt(
        rows,
        estimator_contract={"bootstrap_replicates": 21, "minimum_successful_bootstrap_fraction": .5},
    )
    assert len(workers) == 2
    assert audit["bootstrap_replicates_successful"] == 20
    assert audit["bootstrap_failure_reasons"] == {"missing_worker_level": 1}


def test_qgt_bootstrap_failure_below_threshold_keeps_structured_reason_audit(monkeypatch) -> None:
    rows = [
        {"worker_id": worker, "base_task_id": task, "building_id": building, "condition": "manual", "Q_GT_raw": value}
        for worker, value in (("w1", .8), ("w2", .7))
        for task, building in (("t1", "b1"), ("t2", "b2"))
    ]
    calls = {"value": 0}

    def fake_fit(_frame, _contract):
        calls["value"] += 1
        estimates = {"w1": .8, "w2": .7} if calls["value"] <= 2 else {"w1": .8}
        return {
            "formula": "quality ~ C(worker_id)", "optimizer": "fake", "estimates": estimates,
            "task_effects": {}, "warnings": [], "residual_variance": .01,
            "task_intercept_variance": .01,
        }

    monkeypatch.setattr("tools.thesis_main.analysis.c1_task_adjusted_quality._fit_once", fake_fit)
    with pytest.raises(_BootstrapSupportFailure) as captured:
        estimate_task_adjusted_qgt(rows, estimator_contract={"bootstrap_replicates": 20})
    assert captured.value.audit["bootstrap_replicates_successful"] == 1
    assert captured.value.audit["bootstrap_failure_reasons"] == {"missing_worker_level": 19}
    assert captured.value.audit["bootstrap_minimum_successful_replicates"] == 20


def test_p1_integrity_is_optional_only_for_rehearsal(tmp_path: Path) -> None:
    rehearsal = _validate_p1_integrity_for_mode("precloseout_rehearsal", None)
    assert rehearsal["status"] == "not_evaluable_missing_p1_integrity"
    with pytest.raises(ValueError, match="SHA-bound P1 integrity bundle"):
        _validate_p1_integrity_for_mode("formal", None)
    for name in (
        "p1_post_closeout_correction_summary_v1.json", "p1_geometry_score_summary_v1.json",
        "p1_task_evidence_correction_v1.csv", "p1_worker_evidence_status_v1.csv",
        "p1_geometry_task_scores_v1.csv", "p1_worker_geometry_profile_v1.csv",
    ):
        (tmp_path / name).write_text("{}\n" if name.endswith(".json") else "worker_id\nw1\n", encoding="utf-8")
    materialize_p1_integrity_bundle(tmp_path)
    validated = validate_p1_integrity_bundle(tmp_path)
    assert validated["valid"] is True
    assert validated["P1_INTEGRITY_BUNDLE_FROZEN"] is True
    assert validated["P1_PREDICTIVE_EVIDENCE_READY"] is False
    (tmp_path / "p1_worker_geometry_profile_v1.csv").write_text("worker_id\nw2\n", encoding="utf-8")
    assert validate_p1_integrity_bundle(tmp_path)["valid"] is False


def test_p1_predictive_ready_requires_three_legal_numeric_worker_components(tmp_path: Path) -> None:
    for name in (
        "p1_post_closeout_correction_summary_v1.json", "p1_geometry_score_summary_v1.json",
        "p1_task_evidence_correction_v1.csv", "p1_geometry_task_scores_v1.csv",
    ):
        (tmp_path / name).write_text("{}\n" if name.endswith(".json") else "worker_id\nw1\n", encoding="utf-8")
    _write(tmp_path / "p1_worker_evidence_status_v1.csv", [
        {"worker_id": f"w{index}", "p1_predictive_capability_eligible": "true"}
        for index in range(1, 4)
    ])
    _write(tmp_path / "p1_worker_geometry_profile_v1.csv", [
        {"worker_id": f"w{index}", "p1_geometry_component": str(.8 + index / 100),
         "p1_geometry_support_status": "sufficient"}
        for index in range(1, 4)
    ])

    manifest = materialize_p1_integrity_bundle(tmp_path)

    assert manifest["P1_INTEGRITY_BUNDLE_FROZEN"] is True
    assert manifest["P1_PREDICTIVE_EVIDENCE_READY"] is True
    assert manifest["p1_predictive_eligible_worker_count"] == 3


def test_history_overlap_consumes_resolved_p1_identity_for_all_real_tasks(tmp_path: Path) -> None:
    inventory = tmp_path / "inventory.csv"
    p1 = tmp_path / "p1_corrected.csv"
    output = tmp_path / "history.csv"
    _write(inventory, [
        {"task_id": f"c2-{index}", "base_task_id": f"base-{index}", "image_id": f"image-{index}"}
        for index in range(57)
    ])
    _write(p1, [
        {"task_id": f"runtime-{index}", "base_task_id": f"base-{index}", "image_id": f"image-{index}"}
        for index in range(57)
    ])
    summary = materialize_history_overlap(inventory, p1, [], output)
    assert summary["n_history_overlap"] == 57
    assert all(row["history_overlap"].lower() == "true" for row in csv.DictReader(output.open(encoding="utf-8")))


def test_cross_worker_exact_geometry_has_three_distinct_independence_classes(tmp_path: Path) -> None:
    meta = tmp_path / "meta.csv"
    rows = []
    for condition, task, geometry in (("manual", "m", "gm"), ("semi", "initial", "gi"), ("semi", "copy", "gc")):
        for index, worker in enumerate(("w1", "w2"), 1):
            rows.append({
                "project_id": f"p-{condition}-{task}", "condition": condition,
                "ls_runtime_task_id": f"r-{task}-{index}", "worker_id": worker,
                "annotation_id": f"a-{task}-{index}", "canonical_annotation_id": f"c-{task}-{index}",
                "base_task_id": task, "geometry_hash": geometry,
            })
    _write(meta, rows)
    provenance = tmp_path / "provenance.csv"
    _write(provenance, [{
        "project_id": row["project_id"], "ls_runtime_task_id": row["ls_runtime_task_id"],
        "artifact_kind": "prediction", "prediction_selection_status": "selected_unique",
        "initial_geometry_hash": row["geometry_hash"] if row["base_task_id"] == "initial" else "different",
    } for row in rows if row["condition"] == "semi"])
    materialize_independence(meta, tmp_path, model_provenance_csv=provenance)
    evidence = {row["canonical_annotation_id"]: row for row in csv.DictReader((tmp_path / "c1_independence_evidence.csv").open(encoding="utf-8"))}
    assert evidence["c-m-1"]["exact_geometry_match_classification"] == "suspected_cross_worker_exact_geometry"
    assert evidence["c-m-1"]["independence_status"] == "not_evaluable"
    assert evidence["c-initial-1"]["exact_geometry_match_classification"] == "shared_initialization_match"
    assert evidence["c-copy-1"]["exact_geometry_match_classification"] == "suspected_cross_worker_exact_geometry"


def test_formal_audit_cannot_write_the_final_c1_freeze_owner_artifact(tmp_path: Path) -> None:
    global_csv, loo, structural, completion = [tmp_path / name for name in ("global.csv", "loo.csv", "structural.csv", "completion.csv")]
    _write(global_csv, [{"worker_id": "w1", "GT_support": 1, "Q_GT_task_adjusted": .8}])
    _write(loo, [{"worker_id": "w1", "base_task_id": "t", "q_LOO_tu": .7, "loo_analysis_eligible": "true"}])
    _write(structural, [{"worker_id": "w1", "structural_opportunity_eligible": "true", "failure_attribution": "passed"}])
    _write(completion, [{"worker_id": "w1", "completion_status": "completed"}])
    materialize_three_track_worker_state(global_csv, loo, structural, completion, tmp_path, formal=True)
    assert not (tmp_path / "c1_evidence_freeze_manifest.json").exists()
    manifest = json.loads((tmp_path / "c1_three_track_worker_state_manifest.json").read_text(encoding="utf-8"))
    assert manifest["c1_evidence_freeze_status"] == "pending_finalize_c1"


def test_only_zero_worker_slope_variance_selects_common_slope_nested_form() -> None:
    decision, boundary, tolerance = _variance_boundary_decision(
        {"worker_slope": 0.0, "task": .03, "building": .04}, .1,
    )
    assert decision == "refit_crossed_common_worker_slope"
    assert boundary == ["worker_slope"] and tolerance == pytest.approx(1e-7)
    unsupported, components, _ = _variance_boundary_decision(
        {"worker_slope": 0.0, "task": 0.0, "building": .04}, .1,
    )
    assert unsupported == "fail_multiple_variance_boundaries"
    assert components == ["task", "worker_slope"]


def test_single_task_or_building_boundary_has_a_frozen_component_drop() -> None:
    task_decision, task_boundary, _ = _variance_boundary_decision(
        {"worker_slope": .02, "task": 0.0, "building": .04}, .1,
    )
    building_decision, building_boundary, _ = _variance_boundary_decision(
        {"worker_slope": .02, "task": .03, "building": 0.0}, .1,
    )
    assert (task_decision, task_boundary) == ("refit_without_task_component", ["task"])
    assert (building_decision, building_boundary) == ("refit_without_building_component", ["building"])


def test_risk_model_uses_worker_fixed_intercepts_and_nested_task_identity() -> None:
    formula, variance = _risk_model_spec({"worker_slope", "task", "building"})
    assert "0 + C(worker_id)" in formula
    assert "worker_intercept" not in variance
    assert variance["task"] == "0 + C(task_within_building)"


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
        _simulation_worker("w1", baseline=.8, structural=1),
        _simulation_worker("w2", baseline=.7, structural=0),
    ]
    tasks = {
        "t1": {"task_id": "t1", "building_id": "b1", "risk_design_score_A": ".1", "risk_design_stratum": "ordinary"},
        "t2": {"task_id": "t2", "building_id": "b2", "risk_design_score_A": ".9", "risk_design_stratum": "stress"},
    }
    assignments = [{"worker_id": worker, "task_id": task} for worker in ("w1", "w2") for task in tasks]
    result = _empirical_cluster_bootstrap("d", workers, assignments, tasks, {"worker_task_graph_connected": True}, seed=7, draws=30)
    assert result["simulation_method"] == "hierarchical_building_task_resampling_with_joint_qgt_and_unified_slope_posterior_v2"
    assert result["graph_connectivity_probability"] == 0
    assert float(result["expected_assignment_count"]) < len(assignments)
    assert result["worker_rank_spearman"] != ""


def test_common_slope_simulation_uses_one_pooled_shared_posterior() -> None:
    workers = [
        _simulation_worker("w1", baseline=.8, structural=0),
        _simulation_worker("w2", baseline=.7, structural=0),
    ]
    for worker in workers:
        worker.update({
            "slope_model_form": "crossed_common_worker_slope",
            "between_worker_slope_sd": "0", "risk_slope_for_simulation": "-.9",
            "risk_slope_se": ".8", "risk_slope_support": "6",
        })
    tasks = {
        "t1": {"task_id": "t1", "building_id": "b1", "risk_design_score_A": ".1", "risk_design_stratum": "ordinary"},
        "t2": {"task_id": "t2", "building_id": "b2", "risk_design_score_A": ".9", "risk_design_stratum": "stress"},
    }
    assignments = [{"worker_id": worker, "task_id": task} for worker in ("w1", "w2") for task in tasks]
    result = _empirical_cluster_bootstrap("common", workers, assignments, tasks, {}, seed=11, draws=10)
    assert result["simulation_status"] == "estimated"
    assert set(result["worker_slope_distribution_sources"].values()) == {"common_group_posterior"}
    assert result["risk_slope_posterior_method"] == "shared_common_slope_pooled_within_worker"


def test_simulation_never_replaces_missing_uncertainty_with_zero() -> None:
    worker = _simulation_worker("w1", baseline=.8, structural=0)
    worker["Q_GT_contrast_covariance_row_json"] = json.dumps({"w1": .0025})
    tasks = {"t": {"task_id": "t", "building_id": "b", "risk_design_score_A": ".5", "risk_design_stratum": "ordinary"}}
    assignments = [{"worker_id": "w1", "task_id": "t"}]
    missing_slope = dict(worker); missing_slope.pop("group_slope_se")
    assert _empirical_cluster_bootstrap("d", [missing_slope], assignments, tasks, {}, seed=1, draws=2)["simulation_status"] == "insufficient_variance_parameters"
    missing_rate = dict(worker); missing_rate.pop("missing_rate")
    assert _empirical_cluster_bootstrap("d", [missing_rate], assignments, tasks, {}, seed=1, draws=2)["simulation_status"] == "insufficient_missingness_parameters"
    missing_covariance = dict(worker); missing_covariance.pop("Q_GT_contrast_covariance_row_json")
    assert _empirical_cluster_bootstrap("d", [missing_covariance], assignments, tasks, {}, seed=1, draws=2)["simulation_status"] == "insufficient_q_gt_baseline_covariance"


def test_group_prior_only_worker_has_finite_projection() -> None:
    workers = [{
        "worker_id": "w", "risk_slope_se": "", "risk_slope_support": "0",
        "group_prior_slope": ".1", "group_slope_se": ".03", "between_worker_slope_sd": ".2",
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


def test_projection_and_simulation_share_one_worker_slope_distribution_contract() -> None:
    individual = _resolve_slope_distribution({
        "risk_slope_for_simulation": "-.3", "risk_slope_se": ".04", "risk_slope_support": "6",
        "group_slope_mean": "-.1", "group_slope_se": ".03", "between_worker_slope_sd": ".2",
        "slope_model_form": "crossed_random_worker_slope",
    })
    prior = _resolve_slope_distribution({
        "risk_slope_for_simulation": "", "risk_slope_se": "", "risk_slope_support": "0",
        "group_slope_mean": "-.1", "group_slope_se": ".03", "between_worker_slope_sd": ".2",
        "slope_model_form": "crossed_random_worker_slope",
    })
    common = _resolve_slope_distribution({
        "risk_slope_for_simulation": "-.8", "risk_slope_se": ".9", "risk_slope_support": "6",
        "group_slope_mean": "-.1", "group_slope_se": ".03", "between_worker_slope_sd": "0",
        "slope_model_form": "crossed_common_worker_slope",
    })
    assert individual["source"] == "individual_posterior"
    assert individual["mean"] == pytest.approx(-.3)
    assert individual["total_sd"] == pytest.approx(.05)
    assert prior["source"] == "group_prior" and prior["mean"] == pytest.approx(-.1)
    assert prior["total_sd"] == pytest.approx((.03 ** 2 + .2 ** 2) ** .5)
    assert common["source"] == "common_group_posterior"
    assert common["mean"] == pytest.approx(-.1) and common["total_sd"] == pytest.approx(.03)


def test_joint_qgt_posterior_partially_updates_c1_and_preserves_cross_worker_covariance() -> None:
    prior_mean = __import__("numpy").asarray([.8, .7])
    prior_covariance = __import__("numpy").asarray([[.04, .02], [.02, .04]])
    design = __import__("numpy").asarray([[1.0, 0.0]])
    posterior_mean, posterior_covariance = _joint_qgt_posterior(
        prior_mean, prior_covariance, design,
        risk_adjusted_outcomes=__import__("numpy").asarray([.2]),
        likelihood_covariance=__import__("numpy").asarray([[.04]]),
    )
    assert .2 < posterior_mean[0] < .8
    assert posterior_mean[1] < .7  # C1 cross-worker covariance propagates the update.
    assert posterior_covariance[0, 0] < prior_covariance[0, 0]
    unchanged_mean, unchanged_covariance = _joint_qgt_posterior(
        prior_mean, prior_covariance, __import__("numpy").empty((0, 2)),
        risk_adjusted_outcomes=__import__("numpy").empty(0),
        likelihood_covariance=__import__("numpy").empty((0, 0)),
    )
    assert __import__("numpy").allclose(unchanged_mean, prior_mean)
    assert __import__("numpy").allclose(unchanged_covariance, prior_covariance)


def test_loto_lobo_and_anchor_audits_physically_remove_edges_and_recompute() -> None:
    workers = [{
        "worker_id": worker, "risk_slope_se": ".1", "risk_slope_support": "2",
        "missing_rate": "0", "F_struct": "0", "task_sd": ".02", "building_sd": ".02",
    } for worker in ("w1", "w2")]
    tasks = {
        "a": {"task_id": "a", "building_id": "b1", "risk_design_score_A": ".1", "risk_design_stratum": "ordinary"},
        "s": {"task_id": "s", "building_id": "b2", "risk_design_score_A": ".9", "risk_design_stratum": "stress"},
        "x": {"task_id": "x", "building_id": "b3", "risk_design_score_A": ".5", "risk_design_stratum": "ordinary"},
    }
    assignments = [
        {"worker_id": worker, "task_id": task, "task_stratum": tasks[task]["risk_design_stratum"], "design_id": "d", "c2_component": "common_anchor" if task in {"a", "s"} else "diverse_bridge"}
        for worker in ("w1", "w2") for task in tasks
    ]
    rows = _recompute_stability_audits("d", workers, assignments, tasks, seed=1, draws=20)
    leave_task = next(row for row in rows if row["perturbation"] == "leave_one_task_out" and row["removed_id"] == "a")
    leave_building = next(row for row in rows if row["perturbation"] == "leave_one_building_out" and row["removed_id"] == "b1")
    leave_anchor = next(row for row in rows if row["perturbation"] == "leave_one_anchor_out" and row["removed_id"] == "a")
    assert leave_task["remaining_edge_count"] == len(assignments) - 2
    assert leave_building["remaining_edge_count"] == len(assignments) - 2
    assert leave_anchor["remaining_edge_count"] == len(assignments) - 2
    assert leave_task["minimum_worker_support"] == 2 and leave_task["building_coverage"] == 2


def test_all_finally_eligible_tasks_can_be_anchor_candidates_without_legacy_flags() -> None:
    tasks = [
        {"task_id": "o", "assignment_eligible": "true", "risk_design_stratum": "ordinary", "risk_design_vector_A": "[0,0,0,0]", "building_id": "b1"},
        {"task_id": "s", "assignment_eligible": "true", "risk_design_stratum": "stress", "risk_design_vector_A": "[1,1,1,1]", "building_id": "b2"},
    ]
    pool = _anchor_pool(tasks)
    selected = _select_anchors(pool, 2)
    assert {row["task_id"] for row in pool} == {"o", "s"}
    assert {row["risk_design_stratum"] for row in selected} == {"ordinary", "stress"}


def test_reference_candidate_content_duplicate_fails_feature_pool(tmp_path: Path) -> None:
    reference_images, reference_layouts, candidate_layouts = (tmp_path / name for name in ("reference_images", "reference_layouts", "candidate_layouts"))
    for directory in (reference_images, reference_layouts, candidate_layouts):
        directory.mkdir()
    (reference_images / "ref.jpg").write_bytes(b"same-image")
    (reference_layouts / "ref.json").write_text("{}", encoding="utf-8")
    candidate_image = tmp_path / "candidate.jpg"; candidate_image.write_bytes(b"same-image")
    (candidate_layouts / "task.json").write_text('{"layout": 1}', encoding="utf-8")
    inventory = tmp_path / "inventory.csv"
    _write(inventory, [{"image_id": "i", "base_task_id": "task", "task_id": "task", "source_path": str(candidate_image)}])
    summary = materialize_reference_candidate_leakage(
        reference_images, reference_layouts, inventory, candidate_layouts, tmp_path,
    )
    assert summary["status"] == "failed"
    assert summary["formal_feature_pool_allowed"] is False


def test_source_holdout_proposals_are_non_dominated_and_never_auto_approved(tmp_path: Path) -> None:
    inventory, history, buildings, risk = [tmp_path / name for name in ("inventory.csv", "history.csv", "buildings.csv", "risk.csv")]
    inventory_rows = [{
        "image_id": f"i{index}", "base_task_id": f"t{index}", "task_id": f"t{index}",
        "source_path": f"pool/scene{index % 4}/i{index}.jpg", "source_pool": "pool",
    } for index in range(12)]
    _write(inventory, inventory_rows)
    _write(history, [{"image_id": row["image_id"], "base_task_id": row["base_task_id"], "history_overlap": "false"} for row in inventory_rows])
    _write(buildings, [{
        "image_id": row["image_id"], "base_task_id": row["base_task_id"],
        "building_id": f"b{index % 4}", "registry_status": "approved",
        "reviewed_by": "expert", "reviewed_at": "2026-07-26T00:00:00Z",
    } for index, row in enumerate(inventory_rows)])
    _write(risk, [{
        "image_id": row["image_id"], "base_task_id": row["base_task_id"],
        "static_model_risk_score": index / 11,
    } for index, row in enumerate(inventory_rows)])
    summary = materialize_split_proposals(inventory, history, buildings, risk, tmp_path)
    assert summary["status"] == "candidate_only" and summary["approval_materialized"] is False
    assert summary["proposal_count"] >= 2 and summary["all_candidates_non_dominated"] is True
    assert not (tmp_path / "source_split_approval.json").exists()
    audits = list(csv.DictReader((tmp_path / "c2b_source_holdout_split_disjointness_audit.csv").open(encoding="utf-8")))
    assert all(row["non_dominated"].lower() == "true" and row["source_holdout_disjoint"].lower() == "true" for row in audits)


def test_building_registry_expands_only_approved_scene_keys(tmp_path: Path) -> None:
    inventory, mapping, output = tmp_path / "inventory.csv", tmp_path / "mapping.csv", tmp_path / "registry.csv"
    inventory_rows = [
        {"image_id": "i1", "base_task_id": "t1", "task_id": "t1", "scene_id": "scene-a", "source_pool": "pool", "source_path": "pool/scene-a/1.jpg"},
        {"image_id": "i2", "base_task_id": "t2", "task_id": "t2", "scene_id": "scene-a", "source_pool": "pool", "source_path": "pool/scene-a/2.jpg"},
        {"image_id": "i3", "base_task_id": "t3", "task_id": "t3", "scene_id": "scene-b", "source_pool": "pool", "source_path": "pool/scene-b/3.jpg"},
    ]
    _write(inventory, inventory_rows)
    _write(mapping, [{
        "scene_mapping_key": "pool|scene-a", "building_id": "building-a",
        "registry_status": "approved", "reviewed_by": "expert", "reviewed_at": "2026-07-26T00:00:00Z",
    }])
    summary = materialize_building_registry_from_scene_mapping(inventory, mapping, output)
    rows = list(csv.DictReader(output.open(encoding="utf-8")))
    assert summary["n_approved"] == 2 and summary["n_unresolved"] == 1
    assert [row["building_id"] for row in rows] == ["building-a", "building-a", ""]
    assert summary["formal_registry_ready"] is False


def test_static_freeze_requires_statuses_and_every_bound_listing(tmp_path: Path) -> None:
    import hashlib

    def write_json(name: str, payload: dict) -> Path:
        path = tmp_path / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    p1 = write_json("p1.json", {"schema_version": "paper_a_p1_integrity_bundle_v1", "bundle_status": "frozen"})
    leakage = write_json("leakage.json", {"status": "passed", "formal_feature_pool_allowed": True})
    feature = write_json("feature.json", {
        "schema_version": "paper_a_c2_feature_freeze_v2", "feature_audit_status": "approved",
        "off_grid_circular_robustness": True,
        "reference_candidate_leakage_audit_sha256": hashlib.sha256(leakage.read_bytes()).hexdigest(),
    })
    proposal_rows = tmp_path / "proposals.csv"; proposal_rows.write_text("proposal_id\np1\n", encoding="utf-8")
    split_audit = tmp_path / "split_audit.csv"; split_audit.write_text("proposal_id\np1\n", encoding="utf-8")
    split = write_json("split.json", {
        "status": "candidate_only", "approval_materialized": False,
        "proposal_rows_sha256": hashlib.sha256(proposal_rows.read_bytes()).hexdigest(),
        "disjointness_audit_sha256": hashlib.sha256(split_audit.read_bytes()).hexdigest(),
    })
    artifacts = {
        "p1_integrity": p1, "feature_freeze": feature, "leakage_audit": leakage,
        "split_proposals": split, "split_proposal_rows": proposal_rows,
        "split_disjointness_audit": split_audit,
        "environment": write_json("environment.json", {"python": "3.11"}),
    }
    for name in (
        "leakage_audit_rows", "reference_image_listing", "reference_layout_listing",
        "candidate_image_listing", "candidate_layout_listing",
    ):
        path = tmp_path / f"{name}.csv"; path.write_text("status\nok\n", encoding="utf-8"); artifacts[name] = path
    frozen = materialize_static_freeze_manifest(tmp_path, artifacts, code_sha256="c" * 64)
    assert frozen["static_evidence_frozen"] is True and frozen["freeze_blockers"] == []
    leakage.write_text(json.dumps({"status": "failed", "formal_feature_pool_allowed": False}), encoding="utf-8")
    blocked = materialize_static_freeze_manifest(tmp_path, artifacts, code_sha256="c" * 64)
    assert blocked["static_evidence_frozen"] is False
    assert "reference_candidate_leakage_not_clear" in blocked["freeze_blockers"]


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


def test_p1_to_c1_source_excludes_c1_administrative_exclusion(tmp_path: Path) -> None:
    p1 = tmp_path / "p1"; p1.mkdir()
    _write(p1 / "prescreen_r0_snapshot.csv", [
        {"worker_id": "kept", "admission_status": "pass", "r_u_0": ".8"},
        {"worker_id": "excluded", "admission_status": "pass_with_watch", "r_u_0": ".9"},
    ])
    _write(p1 / "prescreen_worker_scope_summary.csv", [
        {"annotator_id": "kept", "scope_accuracy_on_adjudicated_tasks": ".7"},
        {"annotator_id": "excluded", "scope_accuracy_on_adjudicated_tasks": ".8"},
    ])
    state = tmp_path / "state.csv"
    _write(state, [
        {
            "worker_id": "kept", "completion_status": "completed",
            "Q_GT_task_adjusted": ".6", "R_LOO_compatible": ".5", "F_struct": ".1",
            "worker_state_status": "estimated",
        },
        {
            "worker_id": "excluded", "completion_status": "administrative_exclusion",
            "Q_GT_task_adjusted": ".9", "R_LOO_compatible": ".9", "F_struct": "0",
            "worker_state_status": "administrative_exclusion",
        },
    ])

    summary = build_source(p1, state, tmp_path / "source.csv")
    rows = list(csv.DictReader((tmp_path / "source.csv").open(encoding="utf-8")))

    assert summary["n_workers"] == 1
    assert {row["worker_id"] for row in rows} == {"kept"}


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
