from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from tools.thesis_main.analysis.build_c2_assignment_manifest_from_c1_gaps import (
    _empirical_cluster_bootstrap,
    _risk_vector,
    _select_anchors,
    _task_set_sha,
)
from tools.thesis_main.analysis.c1_c2_mainline import (
    _building,
    materialize_c2b_design_worker_profile,
    materialize_measurement_readiness,
)
from tools.thesis_main.analysis.materialize_c1_rehearsal_audits import (
    materialize_independence,
    materialize_structural_validation,
)
from tools.thesis_main.analysis.materialize_c2_task_risk import materialize as materialize_risk
from tools.thesis_main.analysis.run_c1_precloseout_rehearsal import (
    _candidate_task_pool,
    _stage_active_log_provenance,
    materialize_c2b_task_eligibility_evidence,
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


def test_partial_worker_does_not_block_estimand_specific_freeze(tmp_path: Path) -> None:
    completion = tmp_path / "completion.csv"
    write_csv(completion, [{"worker_id": "w1", "completion_status": "closed_partial_usable", "completion_disposition_valid": "true"}])
    quality, loo, structural, eligibility = [tmp_path / name for name in ("q.csv", "loo.csv", "s.csv", "elig.csv")]
    write_csv(quality, [{"canonical_annotation_id": "q", "worker_id": "w1", "base_task_id": "tq", "building_id": "b1", "global_analysis_eligible": "true"}])
    write_csv(loo, [{"canonical_annotation_id": "l", "worker_id": "w1", "base_task_id": "tl", "building_id": "b2", "loo_analysis_eligible": "true"}])
    write_csv(structural, [{"canonical_annotation_id": "s", "worker_id": "w1", "base_task_id": "ts", "building_id": "b3", "structural_opportunity_eligible": "true"}])
    write_csv(eligibility, [
        {"canonical_annotation_id": "q", "worker_id": "w1", "base_task_id": "tq", "process_eligible": "true", "independence_eligible": "true", "scope_reference_eligible": "true", "global_analysis_eligible": "true", "loo_analysis_eligible": "false", "structural_opportunity_eligible": "false"},
        {"canonical_annotation_id": "l", "worker_id": "w1", "base_task_id": "tl", "process_eligible": "true", "independence_eligible": "true", "scope_reference_eligible": "true", "global_analysis_eligible": "false", "loo_analysis_eligible": "true", "structural_opportunity_eligible": "false"},
        {"canonical_annotation_id": "s", "worker_id": "w1", "base_task_id": "ts", "process_eligible": "true", "independence_eligible": "true", "scope_reference_eligible": "true", "global_analysis_eligible": "false", "loo_analysis_eligible": "false", "structural_opportunity_eligible": "true"},
    ])
    result = materialize_measurement_readiness(
        completion, quality, loo, structural, tmp_path, canonical_closed=True,
        collection_window_closed=True, eligibility_csv=eligibility,
    )
    assert result["C1_MEASUREMENT_FROZEN"] is True
    assert result["estimand_freeze"]["Q_GT"] is True
    assert result["estimand_freeze"]["R_LOO"] is True
    assert result["estimand_freeze"]["F_struct"] is True


def test_support_axes_cannot_substitute_each_other(tmp_path: Path) -> None:
    completion, state, params, readiness = [tmp_path / name for name in ("c.csv", "state.csv", "p.csv", "r.csv")]
    write_csv(completion, [{"worker_id": "w1", "completion_status": "completed", "completion_disposition_valid": "true"}])
    write_csv(state, [{"worker_id": "w1", "Q_GT_task_adjusted": ".8", "GT_support": "99", "process_eligible_support": "99", "independence_support": "99"}])
    write_csv(params, [{"worker_id": "w1", "parameter_status": "estimated", "risk_slope": ".1", "risk_slope_se": ".1"}])
    write_csv(readiness, [{"worker_id": "w1", "Q_GT_support": "1", "process_support": "0", "independence_support": "1", "scope_reference_support": "1"}])
    materialize_c2b_design_worker_profile(completion, state, params, readiness, tmp_path)
    row = read_csv(tmp_path / "c2b_design_worker_profile.csv")[0]
    assert row["process_support"] == "0"
    assert row["c2b_baseline_eligible"].lower() == "false"


def test_risk_vector_is_the_only_exposure_and_building_never_comes_from_prefix() -> None:
    row = {"risk_design_vector_A": "[1, 2, 3, 4]", "risk_design_score_A": "5"}
    assert _risk_vector(row) == (1.0, 2.0, 3.0, 4.0)
    assert _building({"base_task_id": "house_001"}) == ""


def test_simulation_keeps_sampled_task_edges_and_separates_variance_fields() -> None:
    workers = [{"worker_id": "w1", "Q_GT_task_adjusted": ".8", "risk_slope_for_simulation": ".1", "risk_slope_scale_for_simulation": ".1", "group_slope_sd": ".2", "outcome_residual_sd": ".1", "Q_GT_baseline_se": ".05", "missing_rate": "0", "F_struct": "0"}]
    tasks = {"t1": {"task_id": "t1", "building_id": "b1", "risk_design_vector_A": "[0,0,0,0]", "risk_design_score_A": "0", "risk_design_stratum": "ordinary"}, "t2": {"task_id": "t2", "building_id": "b1", "risk_design_vector_A": "[1,1,1,1]", "risk_design_score_A": "2", "risk_design_stratum": "stress"}}
    assignments = [{"worker_id": "w1", "task_id": "t1"}, {"worker_id": "w1", "task_id": "t2"}]
    result = _empirical_cluster_bootstrap("d", workers, assignments, tasks, {}, seed=7, draws=20)
    assert result["sampled_task_edge_identity_violations"] == 0
    assert result["variance_fields_used"] == ["group_slope_sd", "outcome_residual_sd", "Q_GT_baseline_se"]


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


def test_source_holdout_evidence_changes_task_eligibility_and_legacy_cannot_bypass_history(tmp_path: Path) -> None:
    inventory, risk, reference, assignment, reserve = [tmp_path / name for name in ("inventory.csv", "risk.csv", "reference.csv", "assignment.csv", "reserve.csv")]
    write_csv(inventory, [{"task_id": "t1", "base_task_id": "b1", "image_id": "i1", "building_id": "h1", "source_split_allowed": "true", "future_holdout_clear": "true", "scope_status": "in_scope", "reference_status": "reference_ready", "eligible_after_exclusion": "true"}, {"task_id": "t2", "base_task_id": "b2", "image_id": "i2", "building_id": "h2", "source_split_allowed": "false", "future_holdout_clear": "true", "scope_status": "in_scope", "reference_status": "reference_ready", "eligible_after_exclusion": "true"}])
    write_csv(risk, [{"task_id": "t1", "base_task_id": "b1", "image_id": "i1", "risk_design_vector_A": "[1,1,1,1]", "risk_design_score_A": "2", "risk_status": "frozen"}, {"task_id": "t2", "base_task_id": "b2", "image_id": "i2", "risk_design_vector_A": "[1,1,1,1]", "risk_design_score_A": "2", "risk_status": "frozen"}])
    write_csv(reference, [{"base_task_id": "b1", "image_id": "i1", "final_scope": "in_scope", "geometry_reference_ready": "true"}, {"base_task_id": "b2", "image_id": "i2", "final_scope": "in_scope", "geometry_reference_ready": "true"}])
    write_csv(assignment, [{"task_id": "t1", "base_task_id": "b1"}]); write_csv(reserve, [{"task_id": "t1", "reserve_rank": "1"}])
    evidence = tmp_path / "evidence.csv"
    materialize_c2b_task_eligibility_evidence(inventory, risk, reference, [assignment], evidence)
    evidence_rows = {row["base_task_id"]: row for row in read_csv(evidence)}
    assert evidence_rows["b1"]["assignment_eligible"].lower() == "false"
    assert "history_overlap" in evidence_rows["b1"]["exclusion_reason"]
    assert evidence_rows["b2"]["assignment_eligible"].lower() == "false"
    pool = tmp_path / "pool.csv"
    _candidate_task_pool(inventory, [assignment], pool, reserve)
    legacy_audit = read_csv(tmp_path / "c2_legacy_reverse_candidate_audit.csv")
    assert legacy_audit[0]["not_selected_reason"] == "history_overlap_hard_exclusion"
    assert [row["task_id"] for row in read_csv(pool)] == ["t2"]


def test_common_anchors_require_ordinary_and_stress() -> None:
    rows = [
        {"task_id": "o", "assignment_eligible": "true", "anchor_eligible": "true", "risk_design_stratum": "ordinary", "risk_design_vector_A": "[0,0,0,0]"},
        {"task_id": "s", "assignment_eligible": "true", "anchor_eligible": "true", "risk_design_stratum": "stress", "risk_design_vector_A": "[1,1,1,1]"},
    ]
    selected = _select_anchors(rows, 2)
    assert {row["risk_design_stratum"] for row in selected} == {"ordinary", "stress"}
    assert _select_anchors(rows, 1) == []


def test_selected_task_approval_sha_changes_with_selected_set() -> None:
    assert _task_set_sha({"t1", "t2"}) != _task_set_sha({"t1", "t3"})
