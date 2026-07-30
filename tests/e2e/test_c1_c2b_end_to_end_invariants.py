from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from tools.thesis_main.analysis.build_c2_assignment_manifest_from_c1_gaps import (
    _empirical_cluster_bootstrap,
    _risk_vector,
    _select_anchors,
    _task_set_sha,
    build_candidate_design_manifest,
    enumerate_candidates,
    materialize_approved_assignment,
)
from tools.thesis_main.analysis.c1_c2_mainline import (
    _building,
    materialize_c2b_design_worker_profile,
    materialize_measurement_readiness,
)
from tools.thesis_main.analysis.materialize_c1_rehearsal_audits import (
    materialize_independence,
    materialize_structural_validation,
    materialize_three_track_worker_state,
)
from tools.thesis_main.analysis.materialize_c2_task_risk import _feature_freeze_ready, materialize as materialize_risk
from tools.thesis_main.analysis.materialize_c2b_task_eligibility import materialize as materialize_c2b_task_eligibility
from tools.thesis_main.analysis.c2b_static_evidence import materialize_reference_candidate_leakage
from tools.thesis_main.analysis.active_log_utils import freeze_active_log_snapshot, validate_active_log_freeze_manifest
from tools.thesis_main.analysis.run_c1_precloseout_rehearsal import (
    _stage_active_log_provenance,
    _validate_collection_closure,
)


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fields = list(rows[0]) if rows else ["id"]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def bind_clear_leakage(feature: Path, inventory_rows: list[dict[str, object]]) -> str:
    audit_rows: list[dict[str, object]] = []
    seen_images: set[str] = set()
    for row in inventory_rows:
        normalized = Path(str(row.get("source_path", ""))).resolve().as_posix().casefold()
        if normalized not in seen_images:
            audit_rows.append({"role": "candidate_image", "normalized_path": normalized, "path": normalized, "sha256": "i" * 64, "leakage_clear": "true", "leakage_reason": ""})
            seen_images.add(normalized)
        base = str(row["base_task_id"])
        audit_rows.append({"role": "candidate_layout", "normalized_path": f"layout/{base}.json", "path": f"layout/{base}.json", "sha256": (base * 64)[:64], "leakage_clear": "true", "leakage_reason": ""})
    write_csv(feature.parent / "c2b_reference_candidate_leakage_audit.csv", audit_rows)
    summary_path = feature.parent / "c2b_reference_candidate_leakage_audit.summary.json"
    summary_path.write_text(json.dumps({"status": "passed", "formal_feature_pool_allowed": True}), encoding="utf-8")
    summary_sha = hashlib.sha256(summary_path.read_bytes()).hexdigest()
    feature.write_text(json.dumps({"reference_candidate_leakage_audit_sha256": summary_sha}), encoding="utf-8")
    return hashlib.sha256(feature.read_bytes()).hexdigest()


def simulation_worker(worker: str = "w1", *, missing: float = 0, baseline: float = .8) -> dict[str, object]:
    return {
        "worker_id": worker, "Q_GT_task_adjusted": baseline, "Q_GT_baseline_se": .05,
        "Q_GT_contrast_covariance_row_json": json.dumps({worker: .0025}),
        "group_slope_mean": .1, "group_slope_se": .02,
        "risk_slope_for_simulation": .1, "between_worker_slope_sd": .1,
        "outcome_residual_sd": .1, "worker_intercept_sd": .02,
        "task_sd": .03, "building_sd": .04, "missing_rate": str(missing), "F_struct": "0",
    }


def test_stage_active_logs_are_not_substituted(tmp_path: Path) -> None:
    (tmp_path / "prescreen_closeout_run_config.json").write_text(json.dumps({
        "inputs": {"active_logs": {
            "path": "active_logs/prescreen",
            "snapshot_path": "analysis_results/prescreen/raw_inputs/prescreen",
            "aggregate_sha256": "p" * 64,
        }}
    }), encoding="utf-8")
    provenance = _stage_active_log_provenance(tmp_path, Path("active_logs/new_server"))
    assert provenance["prescreen"]["configured_root"] == "active_logs/prescreen"
    assert provenance["c1"]["configured_root"].replace("\\", "/") == "active_logs/new_server"
    assert provenance["prescreen_not_substituted"] is True


def test_prescreen_live_source_cannot_be_an_arbitrary_existing_root(tmp_path: Path) -> None:
    wrong = tmp_path / "wrong"; wrong.mkdir()
    (tmp_path / "prescreen_closeout_run_config.json").write_text(json.dumps({
        "inputs": {"active_logs": {"path": str(wrong)}}
    }), encoding="utf-8")
    assert _stage_active_log_provenance(tmp_path, Path("active_logs/new_server"))["prescreen"]["validated"] is False


def project_clearance(project: str = "p1", condition: str = "manual") -> dict[str, object]:
    evidence_sha = "e" * 64
    return {
        "project_id": project,
        "condition": condition,
        "source_project_evidence_sha256": evidence_sha,
        "project_evidence_sha256": evidence_sha,
        "raw_export_sha256_set": "x" * 64,
        "project_config_sha256": "c" * 64,
        "annotation_visibility_contract": "visible",
        "prior_annotation_visibility": "none",
        "raw_parent_schema_coverage": "1.0",
        "cross_owner_parent_count": "0",
        "unresolved_parent_count": "0",
        "provenance_status": "complete",
        "copy_risk_status": "cleared",
        "parent_field_coverage_complete": "true",
        "reviewed_by": "expert",
        "reviewed_at": "2026-07-25T00:00:00Z",
    }


def test_project_clearance_expands_and_row_adverse_overrides(tmp_path: Path) -> None:
    meta = tmp_path / "meta.csv"
    write_csv(meta, [
        {"project_id": "p1", "condition": "manual", "ls_runtime_task_id": "r1", "worker_id": "w1", "annotation_id": "a1", "canonical_annotation_id": "c1", "parent_cross_owner": "false", "copy_risk_status": "cleared"},
        {"project_id": "p1", "condition": "manual", "ls_runtime_task_id": "r2", "worker_id": "w2", "annotation_id": "a2", "canonical_annotation_id": "c2", "parent_cross_owner": "true", "copy_risk_status": "cross_owner_parent"},
    ])
    project = tmp_path / "project.csv"
    write_csv(project, [project_clearance()])

    summary = materialize_independence(meta, tmp_path, project_disposition_csv=project)
    rows = {row["canonical_annotation_id"]: row for row in read_csv(tmp_path / "c1_independence_evidence.csv")}
    assert rows["c1"]["independence_status"] == "independent_by_project_provenance"
    assert rows["c1"]["project_expansion_applied"] == "True"
    assert rows["c2"]["independence_status"] == "non_independent_confirmed"
    assert rows["c2"]["independence_basis"] == "row_adverse_evidence_overrides_project_clearance"
    assert summary["n_review"] == 1


def test_project_disposition_must_bind_real_evidence_sha(tmp_path: Path) -> None:
    meta = tmp_path / "meta.csv"
    write_csv(meta, [{"project_id": "p1", "condition": "manual", "ls_runtime_task_id": "r1", "worker_id": "w1", "annotation_id": "a1", "canonical_annotation_id": "c1"}])
    evidence = tmp_path / "c1_project_independence_provenance_evidence.csv"
    write_csv(evidence, [{"project_id": "p1", "condition": "manual", "annotation_count": "1", "raw_export_sha256_set": "x", "parent_field_coverage_complete": "true", "cross_owner_parent_count": "0", "unresolved_parent_count": "0"}])
    disposition = tmp_path / "project.csv"
    row = project_clearance(); row["source_project_evidence_sha256"] = "0" * 64
    write_csv(disposition, [row])
    summary = materialize_independence(meta, tmp_path, project_disposition_csv=disposition, project_evidence_csv=evidence)
    assert summary["project_expansion_count"] == 0


def test_c1_risk_reference_keeps_channels_on_same_base_task(tmp_path: Path) -> None:
    inventory = tmp_path / "inventory.csv"; write_csv(inventory, [{"task_id": "t1", "base_task_id": "b1", "source_path": "missing.jpg"}, {"task_id": "t2", "base_task_id": "b2", "source_path": "missing.jpg"}])
    layouts = tmp_path / "layouts"; layouts.mkdir()
    features = tmp_path / "features.csv"
    rows = []
    for base, image, global_value, local_value in (("b1", "i1", "1", "10"), ("b2", "i2", "2", "20")):
        rows.append({"base_task_id": base, "image_id": image, "building_id": "h1", "d_model_feat": global_value, "d_model_feat_local": local_value, "g_pair_count": "4", "g_topology_invalid": "false", "g_duplicate_peak": "false", "g_seam_instability": "0", "g_postprocess_invalid": "false", "checkpoint_sha256": "a" * 64, "inference_config_sha256": "b" * 64, "layout_output_sha256": "c" * 64, "preannotation_feature_ready": "true"})
    write_csv(features, rows)
    materialize_risk(inventory, layouts, features, tmp_path / "out", input_status="precloseout_rehearsal")
    refs = {row["base_task_id"]: row for row in read_csv(tmp_path / "out" / "c1_task_risk_reference.csv")}
    assert refs["b1"]["d_model_feat"] == "1" and refs["b1"]["d_model_feat_local_max"] == "10"
    assert refs["b2"]["d_model_feat"] == "2" and refs["b2"]["d_model_feat_local_max"] == "20"


def test_partial_worker_does_not_block_estimand_specific_freeze(tmp_path: Path) -> None:
    completion = tmp_path / "completion.csv"
    write_csv(completion, [{"worker_id": "w1", "completion_status": "closed_partial_usable", "completion_disposition_valid": "true"}])
    quality, peer, structural, eligibility, worker_profile = [tmp_path / name for name in ("q.csv", "peer.csv", "s.csv", "elig.csv", "worker_profile.csv")]
    write_csv(quality, [{"canonical_annotation_id": "q", "worker_id": "w1", "base_task_id": "tq", "building_id": "b1", "gt_primary_analysis_eligible": "true"}])
    write_csv(peer, [{"schema_version": "peer_worker_task_v2", "canonical_annotation_id": "l", "worker_id": "w1", "base_task_id": "tl", "building_id": "b2", "R_peer_task": ".8"}])
    write_csv(structural, [{"canonical_annotation_id": "s", "worker_id": "w1", "base_task_id": "ts", "building_id": "b3", "structural_opportunity_eligible": "true"}])
    write_csv(eligibility, [
        {"canonical_annotation_id": "q", "worker_id": "w1", "base_task_id": "tq", "process_eligible": "true", "independence_eligible": "true", "scope_reference_eligible": "true", "gt_primary_analysis_eligible": "true", "loo_medoid_analysis_eligible": "false", "strict_loo_analysis_eligible": "false", "structural_opportunity_eligible": "false"},
        {"canonical_annotation_id": "l", "worker_id": "w1", "base_task_id": "tl", "process_eligible": "true", "independence_eligible": "true", "scope_reference_eligible": "true", "gt_primary_analysis_eligible": "false", "loo_medoid_analysis_eligible": "true", "strict_loo_analysis_eligible": "true", "structural_opportunity_eligible": "false"},
        {"canonical_annotation_id": "s", "worker_id": "w1", "base_task_id": "ts", "process_eligible": "true", "independence_eligible": "true", "scope_reference_eligible": "true", "gt_primary_analysis_eligible": "false", "loo_medoid_analysis_eligible": "false", "strict_loo_analysis_eligible": "false", "structural_opportunity_eligible": "true"},
    ])
    write_csv(worker_profile, [{"worker_id": "w1", "Q_GT_profile_status": "estimated", "R_peer_profile_status": "estimated", "F_struct_profile_status": "estimated", "LOO_medoid_status": "estimated", "LOO_strict_status": "estimated"}])
    result = materialize_measurement_readiness(
        completion, quality, peer, structural, tmp_path, canonical_closed=True,
        collection_window_closed=True, eligibility_csv=eligibility, worker_profile_csv=worker_profile,
    )
    assert result["C1_MEASUREMENT_FROZEN"] is True
    assert result["estimand_freeze"]["Q_GT"] is True
    assert result["estimand_freeze"]["R_peer"] is True
    assert result["estimand_freeze"]["F_struct"] is True


def test_support_axes_cannot_substitute_each_other(tmp_path: Path) -> None:
    completion, state, params, readiness = [tmp_path / name for name in ("c.csv", "state.csv", "p.csv", "r.csv")]
    write_csv(completion, [{"worker_id": "w1", "completion_status": "completed", "completion_disposition_valid": "true"}])
    write_csv(state, [{"schema_version": "worker_profile_v2", "worker_id": "w1", "profile_version": "p", "cohort_id": "c", "enrollment_batch": "original", "administratively_eligible": True, "process_eligible": False, "independence_eligible": True, "Q_GT_estimable": True, "reference_evaluable": True, "Q_GT_profile_status": "estimated", "R_peer_profile_status": "estimated", "peer_task_support": 5, "F_struct_profile_status": "estimated", "LOO_medoid_status": "not_evaluable", "LOO_strict_status": "not_evaluable", "global_policy_eligible": True, "c2_risk_model_eligible": False, "peer_tiebreak_eligible": True, "structural_gate_eligible": True, "F_struct_raw": 0, "F_struct_EB": 0, "F_struct_interval_lower": 0, "F_struct_interval_upper": .1, "Q_GT_task_adjusted": ".8", "GT_support": "99", "process_eligible_support": "99", "independence_support": "99"}])
    write_csv(params, [{"worker_id": "w1", "parameter_status": "estimated", "risk_slope": ".1", "risk_slope_se": ".1"}])
    write_csv(readiness, [{"worker_id": "w1", "Q_GT_support": "1", "process_support": "0", "independence_support": "1", "scope_reference_support": "1"}])
    materialize_c2b_design_worker_profile(completion, state, params, readiness, tmp_path)
    row = read_csv(tmp_path / "c2b_design_worker_profile.csv")[0]
    assert row["c2b_baseline_eligible"].lower() == "false"
    assert "process_ineligible" in row["exclusion_reason"]


def test_three_track_worker_state_counts_each_row_gate_instead_of_using_max_axis_support(tmp_path: Path) -> None:
    global_csv, loo, structural, completion, eligibility = [tmp_path / name for name in ("g.csv", "l.csv", "s.csv", "c.csv", "e.csv")]
    write_csv(global_csv, [{"worker_id": "w1", "GT_support": "7", "Q_GT_task_adjusted": ".8"}])
    write_csv(loo, [])
    write_csv(structural, [])
    write_csv(completion, [{"worker_id": "w1", "completion_status": "completed"}])
    write_csv(eligibility, [
        {"schema_version": "assignment_evidence_v2", "canonical_annotation_id": "a-process", "worker_id": "w1", "base_task_id": "process_only", "condition": "manual", "assignment_provenance": "original_assignment", "formal_assignment_eligible": True, "gt_primary_analysis_eligible": False, "peer_analysis_eligible": False, "loo_medoid_analysis_eligible": False, "strict_loo_analysis_eligible": False, "structural_opportunity_eligible": False, "time_analysis_eligible": False, "semi_correction_analysis_eligible": False, "predictive_validity_analysis_eligible": False, "routing_feature_analysis_eligible": False, "process_eligible": "true", "independence_eligible": "false", "scope_reference_eligible": "false"},
        {"schema_version": "assignment_evidence_v2", "canonical_annotation_id": "a-independent", "worker_id": "w1", "base_task_id": "independent_only", "condition": "manual", "assignment_provenance": "original_assignment", "formal_assignment_eligible": True, "gt_primary_analysis_eligible": False, "peer_analysis_eligible": False, "loo_medoid_analysis_eligible": False, "strict_loo_analysis_eligible": False, "structural_opportunity_eligible": False, "time_analysis_eligible": False, "semi_correction_analysis_eligible": False, "predictive_validity_analysis_eligible": False, "routing_feature_analysis_eligible": False, "process_eligible": "false", "independence_eligible": "true", "scope_reference_eligible": "false"},
    ])
    materialize_three_track_worker_state(
        global_csv, loo, structural, completion, tmp_path, eligibility_csv=eligibility,
    )
    row = read_csv(tmp_path / "c1_three_track_worker_state.csv")[0]
    assert row["process_eligible_support"] == "1"
    assert row["independence_support"] == "1"
    assert row["scope_reference_support"] == "0"


def test_closed_partial_insufficient_cannot_enter_c2b_even_with_some_support(tmp_path: Path) -> None:
    completion, state, params, readiness = [tmp_path / name for name in ("c.csv", "state.csv", "p.csv", "r.csv")]
    write_csv(completion, [{"worker_id": "w1", "completion_status": "closed_partial_insufficient", "completion_disposition_valid": "true"}])
    write_csv(state, [{"schema_version": "worker_profile_v2", "worker_id": "w1", "profile_version": "p", "cohort_id": "c", "enrollment_batch": "original", "administratively_eligible": True, "process_eligible": True, "independence_eligible": True, "Q_GT_estimable": False, "reference_evaluable": True, "Q_GT_profile_status": "not_evaluable", "R_peer_profile_status": "estimated", "peer_task_support": 5, "F_struct_profile_status": "estimated", "LOO_medoid_status": "not_evaluable", "LOO_strict_status": "not_evaluable", "global_policy_eligible": False, "c2_risk_model_eligible": False, "peer_tiebreak_eligible": True, "structural_gate_eligible": True, "F_struct_raw": 0, "F_struct_EB": 0, "F_struct_interval_lower": 0, "F_struct_interval_upper": .1, "Q_GT_task_adjusted": ".8"}])
    write_csv(params, [{"worker_id": "w1", "parameter_status": "estimated"}])
    write_csv(readiness, [{"worker_id": "w1", "Q_GT_support": "2", "process_support": "2", "independence_support": "2"}])
    materialize_c2b_design_worker_profile(completion, state, params, readiness, tmp_path)
    row = read_csv(tmp_path / "c2b_design_worker_profile.csv")[0]
    assert row["c2b_baseline_eligible"].lower() == "false"
    assert "q_gt_not_estimated" in row["exclusion_reason"]


def test_risk_vector_is_the_only_exposure_and_building_never_comes_from_prefix() -> None:
    row = {"risk_design_vector_A": "[1, 2, 3, 4]", "risk_design_score_A": "5"}
    assert _risk_vector(row) == (1.0, 2.0, 3.0, 4.0)
    assert _building({"base_task_id": "house_001"}) == ""


def test_simulation_keeps_sampled_task_edges_and_separates_variance_fields() -> None:
    workers = [simulation_worker()]
    tasks = {"t1": {"task_id": "t1", "building_id": "b1", "risk_design_vector_A": "[0,0,0,0]", "risk_design_score_A": "0", "risk_design_stratum": "ordinary"}, "t2": {"task_id": "t2", "building_id": "b1", "risk_design_vector_A": "[1,1,1,1]", "risk_design_score_A": "2", "risk_design_stratum": "stress"}}
    assignments = [{"worker_id": "w1", "task_id": "t1"}, {"worker_id": "w1", "task_id": "t2"}]
    result = _empirical_cluster_bootstrap("d", workers, assignments, tasks, {}, seed=7, draws=20)
    assert result["sampled_task_edge_identity_violations"] == 0
    assert result["expected_assignment_count"] == 2
    assert result["building_coverage"] == 1
    assert result["variance_fields_used"] == ["group_slope_mean", "group_slope_se", "between_worker_slope_sd", "outcome_residual_sd", "task_sd", "building_sd", "Q_GT_baseline_se"]
    assert result["known_c1_worker_intercept_sd_resampled"] is False


def test_simulation_counts_zero_delivery_and_preserves_task_instances() -> None:
    workers = [simulation_worker(missing=1)]
    tasks = {"t1": {"task_id": "t1", "building_id": "b1", "risk_design_score_A": "0", "risk_design_stratum": "ordinary"}, "t2": {"task_id": "t2", "building_id": "b1", "risk_design_score_A": "1", "risk_design_stratum": "stress"}}
    result = _empirical_cluster_bootstrap("d", workers, [{"worker_id": "w1", "task_id": "t1"}, {"worker_id": "w1", "task_id": "t2"}], tasks, {}, seed=1, draws=4)
    assert result["minimum_task_support"] == 0
    assert result["ordinary_coverage_probability"] == 0


def test_not_evaluable_structural_row_has_false_numerator_and_denominator(tmp_path: Path) -> None:
    canonical = tmp_path / "canonical.csv"
    geometry = tmp_path / "geometry.jsonl"
    write_csv(canonical, [{"canonical_annotation_id": "c1"}])
    geometry.write_text(json.dumps({"canonical_annotation_id": "c1", "worker_id": "w1", "task_id": "t1", "base_task_id": "b1", "pool": "manual", "corners_px": []}) + "\n", encoding="utf-8")
    materialize_structural_validation(canonical, geometry, tmp_path)
    row = read_csv(tmp_path / "structural_validation_audit.csv")[0]
    assert row["failure_attribution"] == "not_evaluable"
    assert row["structural_denominator_eligible"].lower() == "false"
    assert row["worker_failure_numerator"].lower() == "false"


def test_formal_risk_without_feature_freeze_or_c1_freeze_is_not_ready(tmp_path: Path) -> None:
    inventory = tmp_path / "inventory.csv"
    write_csv(inventory, [{"task_id": "t1", "base_task_id": "b1", "image_id": "i1", "building_id": "h1", "source_path": "missing.jpg", "source_split_allowed": "true", "history_clear": "true", "future_holdout_clear": "true", "reference_status": "reference_ready", "scope_status": "in_scope"}])
    layouts = tmp_path / "layouts"
    layouts.mkdir()
    features = tmp_path / "features.csv"
    write_csv(features, [])
    result = materialize_risk(inventory, layouts, features, tmp_path / "out", input_status="formal")
    assert result["formal_ready"] is False
    assert result["state_machine"]["C1_MEASUREMENT_FROZEN"] is False


def test_null_threshold_cannot_formally_select() -> None:
    from tools.thesis_main.analysis.build_c2_assignment_manifest_from_c1_gaps import _thresholds_allow_formal_selection

    assert _thresholds_allow_formal_selection({"q_gt_ci_half_width": None}) is False


def test_history_overlap_blocks_task_and_legacy_reverse_has_no_formal_input(tmp_path: Path) -> None:
    inventory, risk, reference, source, holdout, history, scope = [tmp_path / name for name in ("inventory.csv", "risk.csv", "reference.csv", "source.csv", "holdout.csv", "history.csv", "scope.csv")]
    feature = tmp_path / "feature.json"
    inventory_rows = [{"task_id": "t1", "base_task_id": "b1", "image_id": "i1", "building_id": "h1", "source_split_allowed": "true", "future_holdout_clear": "true", "scope_status": "in_scope", "reference_status": "reference_ready", "eligible_after_exclusion": "true"}, {"task_id": "t2", "base_task_id": "b2", "image_id": "i2", "building_id": "h2", "source_split_allowed": "false", "future_holdout_clear": "true", "scope_status": "in_scope", "reference_status": "reference_ready", "eligible_after_exclusion": "true"}]
    write_csv(inventory, inventory_rows)
    feature_sha = bind_clear_leakage(feature, inventory_rows)
    write_csv(risk, [{"task_id": "t1", "base_task_id": "b1", "image_id": "i1", "building_id": "h1", "risk_design_vector_A": "[1,1,1,1]", "risk_design_score_A": "2", "risk_status": "frozen", "feature_freeze_manifest_sha256": feature_sha}, {"task_id": "t2", "base_task_id": "b2", "image_id": "i2", "building_id": "h2", "risk_design_vector_A": "[1,1,1,1]", "risk_design_score_A": "2", "risk_status": "frozen", "feature_freeze_manifest_sha256": feature_sha}])
    write_csv(reference, [{"base_task_id": "b1", "image_id": "i1", "final_scope": "in_scope", "geometry_reference_ready": "true"}, {"base_task_id": "b2", "image_id": "i2", "final_scope": "in_scope", "geometry_reference_ready": "true"}])
    write_csv(source, [{"base_task_id": "b1", "image_id": "i1", "source_split_allowed": "true"}, {"base_task_id": "b2", "image_id": "i2", "source_split_allowed": "true"}])
    write_csv(holdout, [{"base_task_id": "b1", "image_id": "i1", "future_holdout_clear": "true"}, {"base_task_id": "b2", "image_id": "i2", "future_holdout_clear": "true"}])
    write_csv(history, [{"base_task_id": "b1", "image_id": "i1", "history_clear": "false", "history_overlap": "true"}, {"base_task_id": "b2", "image_id": "i2", "history_clear": "true", "history_overlap": "false"}])
    write_csv(scope, [{"base_task_id": "b1", "image_id": "i1", "final_scope": "in_scope"}, {"base_task_id": "b2", "image_id": "i2", "final_scope": "in_scope"}])
    evidence = tmp_path / "evidence.csv"
    materialize_c2b_task_eligibility(inventory, risk, source, holdout, history, scope, reference, feature, evidence)
    evidence_rows = {row["base_task_id"]: row for row in read_csv(evidence)}
    assert evidence_rows["b1"]["assignment_eligible"].lower() == "false"
    assert "history_overlap" in evidence_rows["b1"]["exclusion_reason"]
    assert evidence_rows["b2"]["assignment_eligible"].lower() == "true"


def test_formal_task_eligibility_uses_joined_evidence_and_feature_sha(tmp_path: Path) -> None:
    paths = {name: tmp_path / f"{name}.csv" for name in ("inventory", "risk", "reference", "source", "holdout", "history", "scope")}
    feature = tmp_path / "feature.json"
    identity = {"task_id": "t1", "base_task_id": "b1", "image_id": "i1"}
    write_csv(paths["inventory"], [identity])
    feature_sha = bind_clear_leakage(feature, [identity])
    write_csv(paths["risk"], [{**identity, "building_id": "h1", "risk_design_vector_A": "[1,1,1,1]", "risk_design_score_A": "2", "risk_status": "frozen", "feature_freeze_manifest_sha256": feature_sha}])
    write_csv(paths["reference"], [{**identity, "reference_status": "reference_ready"}])
    write_csv(paths["source"], [{**identity, "source_split_allowed": "false"}])
    write_csv(paths["holdout"], [{**identity, "future_holdout_clear": "true"}])
    write_csv(paths["history"], [{**identity, "history_clear": "true", "history_overlap": "false"}])
    write_csv(paths["scope"], [{**identity, "final_scope": "in_scope"}])

    inputs = (paths["inventory"], paths["risk"], paths["source"], paths["holdout"], paths["history"], paths["scope"], paths["reference"], feature)
    materialize_c2b_task_eligibility(*inputs, tmp_path / "blocked.csv")
    assert read_csv(tmp_path / "blocked.csv")[0]["assignment_eligible"].lower() == "false"

    write_csv(paths["source"], [{**identity, "source_split_allowed": "true"}])
    materialize_c2b_task_eligibility(*inputs, tmp_path / "eligible.csv")
    assert read_csv(tmp_path / "eligible.csv")[0]["assignment_eligible"].lower() == "true"

    write_csv(paths["history"], [{**identity, "history_clear": "false", "history_overlap": "true"}])
    materialize_c2b_task_eligibility(*inputs, tmp_path / "history_blocked.csv")
    assert "history_overlap" in read_csv(tmp_path / "history_blocked.csv")[0]["exclusion_reason"]


def test_common_anchors_require_ordinary_and_stress() -> None:
    rows = [
        {"task_id": "o", "assignment_eligible": "true", "anchor_eligible": "true", "risk_design_stratum": "ordinary", "risk_design_vector_A": "[0,0,0,0]"},
        {"task_id": "s", "assignment_eligible": "true", "anchor_eligible": "true", "risk_design_stratum": "stress", "risk_design_vector_A": "[1,1,1,1]"},
    ]
    selected = _select_anchors(rows, 2)
    assert {row["risk_design_stratum"] for row in selected} == {"ordinary", "stress"}
    assert _select_anchors(rows, 1) == []


def test_common_anchor_center_prefers_cross_building_coverage() -> None:
    rows = [
        {"task_id": "o", "building_id": "h1", "assignment_eligible": "true", "anchor_eligible": "true", "risk_design_stratum": "ordinary", "risk_design_vector_A": "[0,0,0,0]"},
        {"task_id": "s_same", "building_id": "h1", "assignment_eligible": "true", "anchor_eligible": "true", "risk_design_stratum": "stress", "risk_design_vector_A": "[1,1,1,1]"},
        {"task_id": "s_other", "building_id": "h2", "assignment_eligible": "true", "anchor_eligible": "true", "risk_design_stratum": "stress", "risk_design_vector_A": "[2,2,2,2]"},
    ]
    selected = _select_anchors(rows, 2)
    assert {row["building_id"] for row in selected} == {"h1", "h2"}


def test_selected_task_approval_sha_changes_with_selected_set() -> None:
    assert _task_set_sha({"t1", "t2"}) != _task_set_sha({"t1", "t3"})


def test_threshold_manifest_is_not_ignored_in_fresh_checkout() -> None:
    result = subprocess.run(["git", "check-ignore", "-q", "docs/thesis_main/C2B_DESIGN_SELECTION_THRESHOLDS.json"], capture_output=True)
    assert result.returncode != 0


def test_active_log_freeze_binds_root_sha_and_cutoff(tmp_path: Path) -> None:
    live = tmp_path / "new_server"; live.mkdir()
    (live / "active_times_1.jsonl").write_text(
        json.dumps({"server_time": "2026-07-01T00:00:00+00:00"}) + "\n", encoding="utf-8"
    )
    frozen = tmp_path / "c1"
    manifest = tmp_path / "c1_active_log_freeze_manifest.json"
    payload = freeze_active_log_snapshot(live, frozen, "2026-07-01T00:00:00+00:00", "tester", manifest)
    assert payload["source_live_root"].endswith("new_server")
    assert payload["frozen_root"].endswith("c1")
    assert payload["source_aggregate_sha256"] == payload["frozen_aggregate_sha256"]
    assert payload["post_cutoff_event_count"] == 0
    validate_active_log_freeze_manifest(manifest, frozen)


def test_active_log_freeze_excludes_post_cutoff_event(tmp_path: Path) -> None:
    live = tmp_path / "new_server"; live.mkdir()
    (live / "active_times_1.jsonl").write_text(
        json.dumps({"server_received_at": "2026-07-01T00:00:00+00:00", "event": "included"}) + "\n"
        + json.dumps({"server_received_at": "2026-07-02T00:00:00+00:00", "event": "excluded"}) + "\n",
        encoding="utf-8",
    )
    manifest = tmp_path / "freeze.json"
    frozen = tmp_path / "c1"
    payload = freeze_active_log_snapshot(live, frozen, "2026-07-01T00:00:00+00:00", "tester", manifest)
    assert payload["source_post_cutoff_event_count"] == 1
    assert payload["post_cutoff_event_count"] == 0
    assert payload["source_live_aggregate_sha256"] != payload["frozen_aggregate_sha256"]
    assert payload["source_aggregate_sha256"] == payload["frozen_aggregate_sha256"]
    assert "excluded" not in (frozen / "active_times_1.jsonl").read_text(encoding="utf-8")
    validate_active_log_freeze_manifest(manifest, frozen)


def test_same_bytes_at_another_path_cannot_impersonate_frozen_active_log(tmp_path: Path) -> None:
    live = tmp_path / "new_server"; live.mkdir()
    content = json.dumps({"server_time": "2026-07-01T00:00:00+00:00"}) + "\n"
    (live / "active_times_1.jsonl").write_text(content, encoding="utf-8")
    frozen, manifest = tmp_path / "c1", tmp_path / "freeze.json"
    freeze_active_log_snapshot(live, frozen, "2026-07-01T00:00:00+00:00", "tester", manifest)
    impostor = tmp_path / "renamed_new_server"; impostor.mkdir()
    (impostor / "active_times_1.jsonl").write_text(content, encoding="utf-8")
    with pytest.raises(ValueError, match="frozen root"):
        validate_active_log_freeze_manifest(manifest, impostor)


def test_active_log_freeze_rejects_unfilterable_events_before_creating_snapshot(tmp_path: Path) -> None:
    live = tmp_path / "live"; live.mkdir()
    (live / "active_times_1.jsonl").write_text(json.dumps({"task_id": "1"}) + "\n", encoding="utf-8")
    frozen = tmp_path / "frozen"
    with pytest.raises(ValueError, match="lacks server/event time"):
        freeze_active_log_snapshot(live, frozen, "2026-07-01T00:00:00Z", "tester", tmp_path / "freeze.json")
    assert not frozen.exists()


def test_collection_closure_manifest_unlocks_formal_window(tmp_path: Path) -> None:
    export = tmp_path / "export.json"; export.write_text("{}", encoding="utf-8")
    manual = tmp_path / "manual.csv"; manual.write_text("task_id\nt1\n", encoding="utf-8")
    semi = tmp_path / "semi.csv"; semi.write_text("task_id\nt2\n", encoding="utf-8")
    freeze = tmp_path / "freeze.json"; freeze.write_text(json.dumps({"collection_cutoff_server_time": "2026-07-01T00:00:00+00:00"}), encoding="utf-8")
    from tools.thesis_main.analysis.run_c1_precloseout_rehearsal import _aggregate_sha, _manifest_rows
    closure = tmp_path / "closure.json"
    closure.write_text(json.dumps({
        "c1_export_aggregate_sha256": _aggregate_sha(_manifest_rows([export])),
        "c1_active_log_freeze_manifest_sha256": hashlib.sha256(freeze.read_bytes()).hexdigest(),
        "c1_assignment_sha256": _aggregate_sha(_manifest_rows([manual, semi])),
        "collection_window_closed": True, "closure_time": "2026-07-01T00:00:00Z",
        "operator": "tester", "late_submission_policy": "exclude_after_cutoff",
    }), encoding="utf-8")
    closed, payload = _validate_collection_closure(closure, formal=True, export_sha=_aggregate_sha(_manifest_rows([export])), active_freeze_manifest=freeze, assignment_paths=[manual, semi], export_paths=[export])
    assert closed is True and payload["status"] == "validated"


def test_collection_closure_rejects_cutoff_mismatch(tmp_path: Path) -> None:
    export = tmp_path / "export.json"; export.write_text("{}", encoding="utf-8")
    manual = tmp_path / "manual.csv"; manual.write_text("task_id\nt1\n", encoding="utf-8")
    semi = tmp_path / "semi.csv"; semi.write_text("task_id\nt2\n", encoding="utf-8")
    freeze = tmp_path / "freeze.json"; freeze.write_text(json.dumps({"collection_cutoff_server_time": "2026-07-01T00:00:00+00:00"}), encoding="utf-8")
    from tools.thesis_main.analysis.run_c1_precloseout_rehearsal import _aggregate_sha, _manifest_rows
    closure = tmp_path / "closure.json"
    closure.write_text(json.dumps({
        "c1_export_aggregate_sha256": _aggregate_sha(_manifest_rows([export])),
        "c1_active_log_freeze_manifest_sha256": hashlib.sha256(freeze.read_bytes()).hexdigest(),
        "c1_assignment_sha256": _aggregate_sha(_manifest_rows([manual, semi])),
        "collection_window_closed": True, "closure_time": "2026-07-02T00:00:00Z",
        "operator": "tester", "late_submission_policy": "exclude_after_cutoff",
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="cutoff"):
        _validate_collection_closure(closure, formal=True, export_sha=_aggregate_sha(_manifest_rows([export])), active_freeze_manifest=freeze, assignment_paths=[manual, semi], export_paths=[export])


def test_formal_snapshot_uses_verified_source_aggregates_for_closure(tmp_path: Path) -> None:
    export = tmp_path / "sha_export.json"; export.write_text("{}", encoding="utf-8")
    manual = tmp_path / "sha_manual.csv"; manual.write_text("task_id\nt1\n", encoding="utf-8")
    semi = tmp_path / "sha_semi.csv"; semi.write_text("task_id\nt2\n", encoding="utf-8")
    freeze = tmp_path / "freeze.json"; freeze.write_text(json.dumps({"collection_cutoff_server_time": "2026-07-01T00:00:00+00:00"}), encoding="utf-8")
    closure = tmp_path / "closure.json"
    closure.write_text(json.dumps({
        "c1_export_aggregate_sha256": "verified-source-export",
        "c1_active_log_freeze_manifest_sha256": hashlib.sha256(freeze.read_bytes()).hexdigest(),
        "c1_assignment_sha256": "verified-source-assignment",
        "collection_window_closed": True, "closure_time": "2026-07-01T00:00:00Z",
        "operator": "tester", "late_submission_policy": "exclude_after_cutoff",
    }), encoding="utf-8")
    closed, _ = _validate_collection_closure(
        closure, formal=True, export_sha="verified-source-export",
        active_freeze_manifest=freeze, assignment_paths=[manual, semi], export_paths=[export],
        assignment_sha_override="verified-source-assignment",
    )
    assert closed is True


def test_collection_closure_builder_binds_export_assignment_and_freeze(tmp_path: Path) -> None:
    from argparse import Namespace
    from tools.thesis_main.analysis.run_c1_closeout_launch import build_collection_closure
    export_dir = tmp_path / "exports"; export_dir.mkdir(); (export_dir / "e.json").write_text("{}", encoding="utf-8")
    manual = tmp_path / "manual.csv"; manual.write_text("task_id\nt1\n", encoding="utf-8")
    semi = tmp_path / "semi.csv"; semi.write_text("task_id\nt2\n", encoding="utf-8")
    live = tmp_path / "live"; live.mkdir(); (live / "active_times_1.jsonl").write_text(json.dumps({"server_time": "2026-07-25T00:00:00+00:00"}) + "\n", encoding="utf-8")
    freeze = tmp_path / "freeze.json"; frozen = tmp_path / "frozen"
    freeze_active_log_snapshot(live, frozen, "2026-07-25T00:00:00+00:00", "tester", freeze)
    output = tmp_path / "closure.json"
    result = build_collection_closure(Namespace(export_dir=[export_dir], manual_assignment=manual, semi_assignment=semi, c1_active_log_freeze_manifest=freeze, closure_time="2026-07-25T00:00:00Z", operator="tester", late_submission_policy="exclude_after_cutoff", output=output))
    assert result["collection_window_closed"] is True
    assert json.loads(output.read_text(encoding="utf-8"))["c1_active_log_freeze_manifest_sha256"] == hashlib.sha256(freeze.read_bytes()).hexdigest()


def test_formal_without_collection_closure_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="collection-closure"):
        _validate_collection_closure(None, formal=True, export_sha="x", active_freeze_manifest=None, assignment_paths=[], export_paths=[])


def test_feature_freeze_sha_mismatch_keeps_risk_not_ready(tmp_path: Path) -> None:
    checkpoint = tmp_path / "ep300.pth"; checkpoint.write_bytes(b"checkpoint")
    config = tmp_path / "config.yaml"; config.write_text("config", encoding="utf-8")
    reference = tmp_path / "features.csv"; reference.write_text("base_task_id\nb1\n", encoding="utf-8")
    manifest = tmp_path / "feature_freeze.json"
    payload = {"pca_frozen": True, "pca_frozen_sha256": "p" * 64, "whitening_frozen": True, "whitening_frozen_sha256": "w" * 64, "circular_shift_invariant": True, "circular_shift_invariant_sha256": "c" * 64, "seam_invariant": True, "seam_invariant_sha256": "s" * 64, "checkpoint_sha256": "0" * 64, "config_sha256": "0" * 64, "reference_feature_sha256": "0" * 64, "pca_sha256": "p" * 64, "whitening_sha256": "w" * 64, "circular_shift_audit_sha256": "c" * 64, "seam_audit_sha256": "s" * 64}
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    assert _feature_freeze_ready(manifest, checkpoint=checkpoint, config=config, reference_feature=reference) is False


def test_slope_and_residual_sd_are_not_copied(tmp_path: Path) -> None:
    from tools.thesis_main.analysis.materialize_c1_c2_design_parameters import materialize as materialize_parameters
    quality, risk, structural, completion = [tmp_path / name for name in ("q.csv", "r.csv", "s.csv", "c.csv")]
    write_csv(quality, [{"worker_id": "w1", "base_task_id": f"b{i}", "Q_GT_raw": str(1 - i / 10), "gt_primary_analysis_eligible": "true"} for i in range(4)])
    write_csv(risk, [{"base_task_id": f"b{i}", "risk_design_score_A": str(i / 10), "building_id": "h1"} for i in range(4)])
    write_csv(structural, [{"worker_id": "w1", "structural_opportunity_eligible": "true", "failure_attribution": "none"}])
    write_csv(completion, [{"worker_id": "w1", "assigned_total_count": "4", "observed_total_count": "4", "completion_status": "completed"}])
    summary = materialize_parameters(quality, risk, structural, completion, tmp_path / "out")
    row = read_csv(tmp_path / "out" / "c1_c2_design_parameters.csv")[0]
    assert row["group_slope_sd"] == ""
    assert row["outcome_residual_sd"] == ""
    assert summary["model_status"] == "insufficient_support"


def test_hierarchical_variance_components_are_separately_materialized(tmp_path: Path) -> None:
    from tools.thesis_main.analysis.materialize_c1_c2_design_parameters import materialize as materialize_parameters
    quality, risk, structural, completion = [tmp_path / name for name in ("q.csv", "r.csv", "s.csv", "c.csv")]
    risk_rows, quality_rows = [], []
    for building_index, building in enumerate(("h1", "h2")):
        for task_index in range(3):
            task = f"{building}_t{task_index}"
            x = building_index + task_index / 3
            risk_rows.append({"base_task_id": task, "risk_design_score_A": x, "building_id": building})
            for worker_index, worker in enumerate(("w1", "w2", "w3")):
                quality_rows.append({"worker_id": worker, "base_task_id": task, "Q_GT_raw": .9 - .08 * x + .03 * worker_index + .01 * task_index, "gt_primary_analysis_eligible": "true"})
    write_csv(quality, quality_rows); write_csv(risk, risk_rows)
    write_csv(structural, [{"worker_id": worker, "structural_opportunity_eligible": "true", "failure_attribution": "none"} for worker in ("w1", "w2", "w3")])
    write_csv(completion, [{"worker_id": worker, "assigned_total_count": "6", "observed_total_count": "6", "completion_status": "completed"} for worker in ("w1", "w2", "w3")])
    worker_state = tmp_path / "worker_state.csv"
    write_csv(worker_state, [{"worker_id": worker, "Q_GT_task_adjusted": .8, "standard_error": .03} for worker in ("w1", "w2", "w3")])
    summary = materialize_parameters(quality, risk, structural, completion, tmp_path / "out", worker_state_csv=worker_state)
    row = read_csv(tmp_path / "out" / "c1_c2_design_parameters.csv")[0]
    assert summary["model_status"] in {"estimated", "not_converged_or_singular"}
    assert row["Q_GT_baseline_source"] == "strong_global_task_adjusted"
    assert row["between_worker_slope_sd"] != row["outcome_residual_sd"]


def test_formal_candidate_chain_never_auto_selects_and_requires_bound_human_choice(tmp_path: Path) -> None:
    from tools.thesis_main.analysis.build_c2_assignment_manifest_from_c1_gaps import RISK_CONTRACT
    closeout, risk_summary = tmp_path / "closeout.json", tmp_path / "risk.json"
    closeout.write_text(json.dumps({"C1_MEASUREMENT_FROZEN": False, "C2B_BASELINE_INPUT_FROZEN": True, "C2B_DESIGN_READY": True}), encoding="utf-8")
    risk_summary.write_text(json.dumps({"formal_ready": True, "state_machine": {"C2B_RISK_DESIGN_FROZEN": True}}), encoding="utf-8")
    workers, tasks, evidence = tmp_path / "workers.csv", tmp_path / "tasks.csv", tmp_path / "evidence.csv"
    write_csv(workers, [{
        "worker_id": worker, "c2b_baseline_eligible": "true", "Q_GT_task_adjusted": .8,
        "Q_GT_contrast_covariance_row_json": json.dumps({other: (.0009 if other == worker else .0001) for other in ("w1", "w2")}),
        "group_slope_mean": -.05, "group_slope_se": .02,
        "risk_slope_for_simulation": -.05, "risk_slope_se": .05, "risk_slope_support": 6,
        "between_worker_slope_sd": .02, "outcome_residual_sd": .04,
        "worker_intercept_sd": .02, "task_sd": .02, "building_sd": .02,
        "Q_GT_baseline_se": .03, "missing_rate": 0, "F_struct": 0,
    } for worker in ("w1", "w2")])
    contract_sha = hashlib.sha256(RISK_CONTRACT.read_bytes()).hexdigest()
    task_rows = []
    for index in range(16):
        stratum = "ordinary" if index % 2 == 0 else "stress"
        task_rows.append({
            "task_id": f"t{index}", "base_task_id": f"t{index}", "image_id": f"i{index}",
            "building_id": f"h{index % 2}", "assignment_eligible": "true",
            "anchor_eligible": str(index < 6).lower(), "bridge_eligible": str(index >= 6).lower(),
            "risk_design_vector_A": json.dumps([index / 5] * 4), "risk_design_score_A": index / 5,
            "risk_design_stratum": stratum, "risk_design_stratum_status": "frozen_from_C1",
            "risk_contract_sha256": contract_sha,
        })
    write_csv(tasks, task_rows)
    write_csv(evidence, [{"task_id": row["task_id"], "assignment_eligible": "true"} for row in task_rows])
    thresholds = tmp_path / "thresholds.json"
    thresholds.write_text(json.dumps({
        "schema_version": "paper_a_c2b_design_selection_thresholds_v1", "status": "approved", "formal_selection_allowed": True,
        "approved_by": "design-reviewer", "approved_at": "2026-07-25T00:00:00Z",
        "common_anchor_requirements": {"minimum_count": 2, "required_strata": ["ordinary", "stress"]},
        "thresholds": {"q_gt_ci_half_width": 10, "risk_slope_ci_half_width": 10, "minimum_worker_rank_spearman": -1, "minimum_top_k_overlap": 0, "maximum_mean_rank_displacement": 100, "minimum_worker_support": 0, "minimum_task_support": 0, "graph_connectivity_probability": 0, "minimum_building_coverage": 0, "building_coverage_probability": 0, "ordinary_coverage_probability": 0, "stress_coverage_probability": 0, "minimum_eligible_task_count": 1, "minimum_eligible_building_count": 1, "minimum_ordinary_task_count": 1, "minimum_stress_task_count": 1},
    }), encoding="utf-8")
    design_manifest = build_candidate_design_manifest(tasks, workers, closeout, tmp_path / "design.json", threshold_manifest=thresholds, risk_summary=risk_summary, draws=200)
    candidate = enumerate_candidates(
        tasks, workers, design_manifest, tmp_path / "candidate",
        c1_closeout_summary=closeout, risk_summary=risk_summary,
        threshold_manifest=thresholds, eligibility_evidence_csv=evidence,
    )
    assert candidate["candidate_only"] is True and candidate["chosen_design_id"] == ""
    assert not (tmp_path / "candidate" / "assignment_manifest_C2B.csv").exists()
    audit = read_csv(tmp_path / "candidate" / "c2b_design_candidates.csv")
    selected_id = next(row["design_id"] for row in audit if row["non_dominated"].lower() == "true")
    edges = [row for row in read_csv(tmp_path / "candidate" / "c2b_candidate_worker_task_edges.csv") if row["design_id"] == selected_id]
    selected_tasks = {row["task_id"] for row in edges}
    design_sha = hashlib.sha256(design_manifest.read_bytes()).hexdigest()
    design_approval = tmp_path / "design_approval.json"
    design_approval.write_text(json.dumps({
        "approved": True, "design_manifest_sha256": design_sha, "selected_design_id": selected_id,
        "candidate_summary_sha256": hashlib.sha256((tmp_path / "candidate" / "c2b_design.summary.json").read_bytes()).hexdigest(),
        "candidate_edges_sha256": hashlib.sha256((tmp_path / "candidate" / "c2b_candidate_worker_task_edges.csv").read_bytes()).hexdigest(),
    }), encoding="utf-8")
    task_approval = tmp_path / "task_approval.json"
    task_approval.write_text(json.dumps({
        "approved": True, "design_manifest_sha256": design_sha,
        "task_eligibility_evidence_sha256": hashlib.sha256(evidence.read_bytes()).hexdigest(),
        "selected_task_ids": sorted(selected_tasks),
        "approved_task_set_sha256": _task_set_sha(selected_tasks),
    }), encoding="utf-8")
    selected = materialize_approved_assignment(
        tmp_path / "candidate", design_manifest, thresholds, design_approval,
        task_approval, evidence, closeout, risk_summary, tmp_path / "selected",
    )
    assert selected["chosen_design_id"] == selected_id
    assert selected["n_assignments"] == len(edges) > 0
    assert selected["state_machine"]["C1_MEASUREMENT_FROZEN"] is False
    assert read_csv(tmp_path / "selected" / "assignment_manifest_C2B.csv") == edges
