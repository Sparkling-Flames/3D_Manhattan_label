from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.thesis_main.analysis.c1_materialize_worker_profile_sidecar import _unique_process_rows, build_p1_evidence_rows, build_p1_worker_dimension_readiness, materialize


def _csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    if path.name == "quality.csv":
        eligibility = ["canonical_eligibility_status", "independence_status", "assigned_expected", "outside_assignment_submission", "duplicate_worker_task_submission", "schema_interpretable"]
        fields = fields + [field for field in eligibility if field not in fields]
        rows = [{"canonical_eligibility_status": "valid", "independence_status": "independent", "assigned_expected": "true", "outside_assignment_submission": "false", "duplicate_worker_task_submission": "false", "schema_interpretable": "true", **row} for row in rows]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _rows(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.open(encoding="utf-8")))


def test_p1_process_capability_preserves_unified_eligibility_fields() -> None:
    base = {
        "worker_id": "w1", "task_id": "t1", "annotation_id": "a1", "process_evaluable": "true",
        "process_failure_observed": "false", "canonical_eligibility_status": "valid", "independence_status": "independent",
        "assigned_expected": "true", "outside_assignment_submission": "false", "duplicate_worker_task_submission": "false",
        "schema_interpretable": "true", "parse_error": "", "schema_error": "",
    }
    eligible = build_p1_evidence_rows([base])
    process = next(row for row in eligible if row["family"] == "process_failure")
    assert process["included_in_process_reliability"] is True
    assert process["family_included_in_denominator"] is True
    assert len(_unique_process_rows(eligible)) == 1
    forensic = build_p1_evidence_rows([{**base, "independence_status": "non_independent_confirmed"}])
    forensic_process = next(row for row in forensic if row["family"] == "process_failure")
    assert forensic_process["included_in_process_reliability"] is False
    assert forensic_process["family_included_in_denominator"] is False
    assert _unique_process_rows(forensic) == []


def test_c1_evidence_can_be_complete_with_insufficient_support(tmp_path: Path) -> None:
    quality = tmp_path / "quality.csv"
    _csv(quality, ["round_id", "worker_id", "task_id", "base_task_id", "dataset_group", "condition", "task_outcome_adjudication_status", "duplicate_review_status", "r_u_evidence_included"], [{"round_id": "C1", "worker_id": "w1", "task_id": "t1", "base_task_id": "b1", "dataset_group": "Calibration_anchor", "condition": "manual", "task_outcome_adjudication_status": "approved", "duplicate_review_status": "resolved", "r_u_evidence_included": "false"}])
    worker = tmp_path / "worker.csv"
    _csv(worker, ["worker_id"], [{"worker_id": "w1"}])
    summary = materialize(quality, worker, tmp_path / "out")
    main = _rows(tmp_path / "out" / "worker_profile_main_matrix_C1.csv")[0]
    assert summary["c1_profile_evidence_classified"] is True
    assert summary["full_profile_ready"] is True
    assert summary["c1_support_sufficient"] is False
    assert main["calib_support_status"] == "insufficient"


def test_worker_profile_sidecar_keeps_dual_chain_boundaries(tmp_path: Path) -> None:
    fields = [
        "round_id",
        "task_id",
        "base_task_id",
        "dataset_group",
        "condition",
        "worker_id",
        "canonical_annotation_id",
        "task_final_scope",
        "worker_scope_response",
        "geometry_reference_status",
        "geometry_score_gate_passed",
        "geometry_valid",
        "used_for_r_u",
        "assigned_expected",
        "active_time_source",
        "primary_active_time_eligible",
        "source_manifest_version",
        "family",
        "subfamily",
        "response_type",
    ]
    quality = tmp_path / "quality.csv"
    _csv(
        quality,
        fields,
        [
            {
                "round_id": "C1",
                "task_id": "m1",
                "base_task_id": "b1",
                "dataset_group": "Calibration_anchor",
                "condition": "manual",
                "worker_id": "w1",
                "canonical_annotation_id": "a1",
                "task_final_scope": "in_scope",
                "worker_scope_response": "correct_in_scope",
                "geometry_reference_status": "expert_hard_single",
                "geometry_valid": "true",
                "used_for_r_u": "true",
                "assigned_expected": "true",
                "active_time_source": "log",
                "primary_active_time_eligible": "true",
                "source_manifest_version": "m1",
                "family": "geometry_quality_failure",
                "subfamily": "normal_geometry_degraded",
                "response_type": "geometry_ok",
            },
            {
                "round_id": "C1",
                "task_id": "s1",
                "base_task_id": "b2",
                "dataset_group": "Calibration_semi",
                "condition": "semi",
                "worker_id": "w1",
                "canonical_annotation_id": "a2",
                "task_final_scope": "in_scope",
                "worker_scope_response": "correct_in_scope",
                "geometry_reference_status": "expert_hard_single",
                "geometry_valid": "true",
                "used_for_r_u": "true",
                "assigned_expected": "true",
                "active_time_source": "log",
                "primary_active_time_eligible": "true",
                "source_manifest_version": "m1",
                "family": "semi_correction_failure",
                "subfamily": "blind_trust",
                "response_type": "blind_trust_fail",
            },
            {
                "round_id": "C1",
                "task_id": "o1",
                "base_task_id": "b3",
                "dataset_group": "Calibration_core",
                "condition": "manual",
                "worker_id": "w1",
                "canonical_annotation_id": "a3",
                "task_final_scope": "oos_geometry",
                "worker_scope_response": "scope_false_negative",
                "geometry_reference_status": "audit_only",
                "geometry_valid": "false",
                "used_for_r_u": "false",
                "assigned_expected": "true",
                "active_time_source": "log",
                "primary_active_time_eligible": "true",
                "source_manifest_version": "m1",
                "family": "scope_oos_failure",
                "subfamily": "scope_false_negative",
                "response_type": "scope_false_negative",
            },
            {
                "round_id": "C1",
                "task_id": "u1",
                "base_task_id": "b4",
                "dataset_group": "Calibration_core",
                "condition": "manual",
                "worker_id": "w1",
                "canonical_annotation_id": "a4",
                "task_final_scope": "in_scope",
                "worker_scope_response": "correct_in_scope",
                "geometry_reference_status": "consensus_reference",
                "geometry_valid": "true",
                "used_for_r_u": "false",
                "assigned_expected": "true",
                "active_time_source": "log",
                "primary_active_time_eligible": "true",
                "source_manifest_version": "m1",
                "family": "undercoverage_failure",
                "subfamily": "minimal_space_bias",
                "response_type": "minimal_space_bias",
            },
            {
                "round_id": "P1",
                "task_id": "psemi1",
                "base_task_id": "pb2",
                "dataset_group": "PreScreen_semi",
                "condition": "semi",
                "worker_id": "w1",
                "canonical_annotation_id": "pa2",
                "task_final_scope": "in_scope",
                "worker_scope_response": "correct_in_scope",
                "geometry_reference_status": "expert_hard_single",
                "geometry_valid": "true",
                "used_for_r_u": "false",
                "assigned_expected": "true",
                "active_time_source": "log",
                "primary_active_time_eligible": "true",
                "source_manifest_version": "p1",
                "family": "semi_correction_failure",
                "subfamily": "failed_correction",
                "response_type": "failed_correction",
            },
            {
                "round_id": "P1",
                "task_id": "poos1",
                "base_task_id": "pb3",
                "dataset_group": "PreScreen_oos",
                "condition": "oos_gate",
                "worker_id": "w1",
                "canonical_annotation_id": "pa3",
                "task_final_scope": "oos_open_boundary",
                "worker_scope_response": "correct_oos",
                "geometry_reference_status": "audit_only",
                "geometry_valid": "false",
                "used_for_r_u": "false",
                "assigned_expected": "true",
                "active_time_source": "log",
                "primary_active_time_eligible": "true",
                "source_manifest_version": "p1",
                "family": "scope_oos_failure",
                "subfamily": "scope_false_positive",
                "response_type": "correct_oos",
            },
            {
                "round_id": "C2b",
                "task_id": "c2b1",
                "base_task_id": "db1",
                "dataset_group": "C2b_diagnostic_extension",
                "condition": "diagnostic_extension",
                "worker_id": "w1",
                "canonical_annotation_id": "d1",
                "task_final_scope": "in_scope",
                "worker_scope_response": "correct_in_scope",
                "geometry_reference_status": "expert_hard_single",
                "geometry_valid": "true",
                "used_for_r_u": "true",
                "assigned_expected": "true",
                "active_time_source": "log",
                "primary_active_time_eligible": "true",
                "source_manifest_version": "c2b",
                "family": "geometry_quality_failure",
                "subfamily": "normal_geometry_degraded",
                "response_type": "geometry_ok",
            },
            {
                "round_id": "C1",
                "task_id": "proc1",
                "base_task_id": "b5",
                "dataset_group": "Calibration_core",
                "condition": "manual",
                "worker_id": "w1",
                "canonical_annotation_id": "a5",
                "task_final_scope": "in_scope",
                "worker_scope_response": "correct_in_scope",
                "geometry_reference_status": "consensus_reference",
                "geometry_valid": "true",
                "used_for_r_u": "false",
                "assigned_expected": "false",
                "active_time_source": "log",
                "primary_active_time_eligible": "true",
                "source_manifest_version": "m1",
                "family": "process_failure",
                "subfamily": "assignment_mismatch",
                "response_type": "assignment_mismatch",
            },
            {
                "round_id": "C1",
                "task_id": "missing_ref1",
                "base_task_id": "b6",
                "dataset_group": "Calibration_core",
                "condition": "manual",
                "worker_id": "w1",
                "canonical_annotation_id": "a6",
                "task_final_scope": "in_scope",
                "worker_scope_response": "correct_in_scope",
                "geometry_reference_status": "",
                "geometry_valid": "true",
                "used_for_r_u": "true",
                "assigned_expected": "true",
                "active_time_source": "log",
                "primary_active_time_eligible": "true",
                "source_manifest_version": "m1",
                "family": "geometry_quality_failure",
                "subfamily": "normal_geometry_degraded",
                "response_type": "geometry_ok",
            },
            {
                "round_id": "C1",
                "task_id": "ambiguous_scope1",
                "base_task_id": "b7",
                "dataset_group": "Calibration_core",
                "condition": "manual",
                "worker_id": "w1",
                "canonical_annotation_id": "a7",
                "task_final_scope": "scope_ambiguous",
                "worker_scope_response": "correct_oos",
                "geometry_reference_status": "scope_ambiguous",
                "geometry_valid": "false",
                "used_for_r_u": "false",
                "assigned_expected": "true",
                "active_time_source": "log",
                "primary_active_time_eligible": "true",
                "source_manifest_version": "m1",
                "family": "scope_oos_failure",
                "subfamily": "unresolved_scope_case",
                "response_type": "not_evaluable",
            },
        ],
    )
    worker_state = tmp_path / "worker.csv"
    _csv(worker_state, ["worker_id", "r_u_hat", "r_u_ci_low"], [{"worker_id": "w1", "r_u_hat": "0.8", "r_u_ci_low": "0.7"}])

    summary = materialize(quality, worker_state, tmp_path / "out")
    evidence = _rows(tmp_path / "out" / "worker_task_evidence_table_C1.csv")
    main = _rows(tmp_path / "out" / "worker_profile_main_matrix_C1.csv")[0]
    family = _rows(tmp_path / "out" / "worker_failure_family_response_C1.csv")
    subfamily = _rows(tmp_path / "out" / "worker_subfamily_response_C1.csv")
    predictive = _rows(tmp_path / "out" / "p1_to_c1_descriptive_directional_check.csv")
    summary_json = json.loads((tmp_path / "out" / "worker_profile_sidecar_C1.summary.json").read_text(encoding="utf-8"))

    by_task = {row["task_id"]: row for row in evidence}
    assert by_task["s1"]["included_in_r_u_calib"] == "false"
    assert by_task["s1"]["included_in_r_geometry"] == "false"
    assert by_task["s1"]["included_in_T_u"] == "false"
    assert by_task["psemi1"]["included_in_r_geometry"] == "false"
    assert by_task["psemi1"]["included_in_T_u"] == "false"
    assert by_task["poos1"]["task_final_scope"] == "oos"
    assert by_task["poos1"]["task_oos_subtype"] == "oos_open_boundary"
    assert by_task["poos1"]["included_in_r_scope"] == "true"
    assert by_task["poos1"]["included_in_r_geometry"] == "false"
    assert by_task["c2b1"]["included_in_r_u_calib"] == "false"
    assert by_task["o1"]["included_in_r_scope"] == "true"
    assert by_task["o1"]["included_in_r_geometry"] == "false"
    assert by_task["u1"]["included_in_U_u"] == "false"
    assert by_task["u1"]["task_final_scope"] == "in_scope"
    assert by_task["proc1"]["included_in_process_reliability"] == "false"
    assert by_task["proc1"]["included_in_r_geometry"] == "false"
    assert by_task["missing_ref1"]["geometry_reference_status"] == "unavailable"
    assert by_task["missing_ref1"]["included_in_r_u_calib"] == "false"
    assert by_task["missing_ref1"]["included_in_r_geometry"] == "false"
    assert by_task["ambiguous_scope1"]["task_final_scope"] == "unknown"
    assert by_task["ambiguous_scope1"]["included_in_r_scope"] == "false"
    assert by_task["m1"]["source_manifest_version"] == "m1"
    assert set(row["geometry_valid"] for row in evidence) <= {"true", "false"}

    assert main["r_u_calib"] == "0.8"
    assert main["r_u_calib_ci_low"] == "0.7"
    assert main["profile_freeze_status"] == "C1_provisional"
    assert {"profile_confidence", "protocol_confidence", "diagnostic_profile_confidence", "profile_confidence_notes"} <= set(main)
    assert main["n_calib_support"] == "1"
    assert main["n_geometry_support"] == "0"
    assert main["n_scope_support"] == "8"
    assert main["n_undercoverage_support"] == "0"
    assert main["blind_trust_or_correction_failure_rate"] == ""
    assert main["correction_reliability_u"] == ""
    assert main["undercoverage_failure_rate"] == ""
    assert main["coverage_reliability_u"] == ""
    assert main["T_u_direction"] == "higher_is_worse_failure_rate"
    assert main["n_process_support"] == "9"
    assert main["process_reliability"] == "1.000000"
    assert any(row["family"] == "undercoverage_failure" and row["n_observed"] == "0" and row["interpretation_level"] == "none" and row["interpretation_allowed"] == "false" for row in family)
    assert not any(row["subfamily"] == "minimal_space_bias" for row in subfamily)
    assert {row["support_status"] for row in predictive} == {"not_evaluable"}
    assert (tmp_path / "out" / "p1_to_c1_descriptive_directional_check_report.md").exists()
    assert summary["r_u_calib_estimated"] is True
    assert summary_json["input_p1_artifacts"] == []
    assert summary_json["profile_freeze_status"] == "C1_provisional"
    assert "family_interpretation_level_counts" in summary_json
    assert "subfamily_interpretation_level_counts" in summary_json
    assert summary_json["warnings"] == ["p1_informed_artifact_bundle_missing", "p1_descriptive_directional_check_not_evaluable_without_p1_artifacts"]


def test_worker_profile_sidecar_confidence_and_interpretation_levels(tmp_path: Path) -> None:
    fields = [
        "round_id",
        "task_id",
        "base_task_id",
        "dataset_group",
        "condition",
        "worker_id",
        "canonical_annotation_id",
        "task_final_scope",
        "worker_scope_response",
        "geometry_reference_status",
        "geometry_score_gate_passed",
        "geometry_valid",
        "used_for_r_u",
        "assigned_expected",
        "family",
        "subfamily",
        "response_type",
    ]

    def row(i: int, family: str, subfamily: str, dataset_group: str, condition: str, response_type: str, used_for_r_u: str = "false", assigned_expected: str = "true") -> dict[str, str]:
        return {
            "round_id": "C1",
            "task_id": f"t{i}",
            "base_task_id": f"b{i}",
            "dataset_group": dataset_group,
            "condition": condition,
            "worker_id": "w1",
            "canonical_annotation_id": f"a{i}",
            "task_final_scope": "in_scope",
            "worker_scope_response": "correct_in_scope",
            "geometry_reference_status": "expert_hard_single",
            "geometry_score_gate_passed": "true",
            "geometry_valid": "true",
            "used_for_r_u": used_for_r_u,
            "assigned_expected": assigned_expected,
            "family": family,
            "subfamily": subfamily,
            "response_type": response_type,
        }

    quality = tmp_path / "quality.csv"
    rows = [
        *(row(i, "geometry_quality_failure", "normal_geometry_degraded", "Calibration_anchor", "manual", "geometry_ok", "true") for i in range(10)),
        *(row(20 + i, "semi_correction_failure", "successful_correction", "Calibration_semi", "semi", "semi_ok") for i in range(5)),
        *(row(40 + i, "process_failure", "assignment_mismatch", "Calibration_core", "manual", "assignment_mismatch", assigned_expected="false") for i in range(3)),
    ]
    _csv(quality, fields, rows)
    worker_state = tmp_path / "worker.csv"
    _csv(worker_state, ["worker_id", "r_u_hat", "r_u_ci_low"], [{"worker_id": "w1", "r_u_hat": "", "r_u_ci_low": ""}])

    materialize(quality, worker_state, tmp_path / "out")
    main = _rows(tmp_path / "out" / "worker_profile_main_matrix_C1.csv")[0]
    family = {row["family"]: row for row in _rows(tmp_path / "out" / "worker_failure_family_response_C1.csv")}
    subfamily = {row["subfamily"]: row for row in _rows(tmp_path / "out" / "worker_subfamily_response_C1.csv")}
    summary = json.loads((tmp_path / "out" / "worker_profile_sidecar_C1.summary.json").read_text(encoding="utf-8"))

    assert main["protocol_confidence"] == "sufficient"
    assert main["diagnostic_profile_confidence"] == "insufficient"
    assert main["profile_confidence"] == "insufficient"
    assert "diagnostic_profile_confidence_from_non_protocol_dimensions" in main["profile_confidence_notes"]
    assert family["geometry_quality_failure"]["interpretation_level"] == "none"
    assert family["semi_correction_failure"]["interpretation_level"] == "none"
    assert family["process_failure"]["interpretation_level"] == "sufficient_descriptive"
    assert family["undercoverage_failure"]["interpretation_level"] == "none"
    assert family["undercoverage_failure"]["interpretation_allowed"] == "false"
    assert "normal_geometry_degraded" not in subfamily
    assert summary["family_interpretation_level_counts"]["sufficient_descriptive"] == 1
    assert summary["family_interpretation_level_counts"]["moderate_descriptive"] == 0
    assert summary["family_interpretation_level_counts"]["weak_descriptive"] == 0


def test_worker_profile_sidecar_reads_p1_artifacts_without_writeback(tmp_path: Path) -> None:
    quality = tmp_path / "quality.csv"
    _csv(
        quality,
        [
            "round_id",
            "task_id",
            "base_task_id",
            "dataset_group",
            "condition",
            "worker_id",
            "canonical_annotation_id",
            "task_final_scope",
            "worker_scope_response",
            "geometry_reference_status",
            "geometry_valid",
            "used_for_r_u",
            "assigned_expected",
            "family",
            "subfamily",
            "response_type",
        ],
        [
            {
                "round_id": "C1",
                "task_id": "m1",
                "base_task_id": "b1",
                "dataset_group": "Calibration_anchor",
                "condition": "manual",
                "worker_id": "w1",
                "canonical_annotation_id": "a1",
                "task_final_scope": "in_scope",
                "worker_scope_response": "correct_in_scope",
                "geometry_reference_status": "expert_hard_single",
                "geometry_valid": "true",
                "used_for_r_u": "true",
                "assigned_expected": "true",
                "family": "geometry_quality_failure",
                "subfamily": "normal_geometry_degraded",
                "response_type": "geometry_ok",
            }
        ],
    )
    worker_state = tmp_path / "worker.csv"
    p1 = tmp_path / "p1_artifact.csv"
    _csv(worker_state, ["worker_id", "r_u_hat", "r_u_ci_low"], [{"worker_id": "w1", "r_u_hat": "0.8", "r_u_ci_low": "0.7"}])
    _csv(p1, ["worker_id", "r_u_0", "p1_geometry_profile"], [{"worker_id": "w1", "r_u_0": "0.9", "p1_geometry_profile": "0.8"}])

    summary = materialize(quality, worker_state, tmp_path / "out", [p1])
    predictive = _rows(tmp_path / "out" / "p1_to_c1_descriptive_directional_check.csv")
    by_check = {row["check_name"]: row for row in predictive}
    report = (tmp_path / "out" / "p1_to_c1_descriptive_directional_check_report.md").read_text(encoding="utf-8")

    assert summary["input_p1_artifacts"] == [str(p1)]
    assert summary["p1_descriptive_directional_check_status"] == "evaluable"
    assert by_check["p1_r0_vs_c1_r_u_calib"]["p1_metric_value"] == "0.9"
    assert by_check["p1_r0_vs_c1_r_u_calib"]["support_status"] == "weak_descriptive"
    assert by_check["p1_r0_vs_c1_r_u_calib"]["descriptive_directional_alignment"] == "true"
    assert by_check["p1_geometry_vs_c1_geometry"]["support_status"] == "not_evaluable"
    assert "P1 artifacts are read-only inputs" in report


def test_structural_p1_bundle_is_not_full_without_expert_undercoverage_or_semi_geometry(tmp_path: Path) -> None:
    quality = tmp_path / "quality.csv"
    worker = tmp_path / "worker.csv"
    _csv(quality, ["worker_id"], [])
    _csv(worker, ["worker_id"], [{"worker_id": "w1"}])
    correction = tmp_path / "correction.csv"
    _csv(correction, ["worker_id", "project_id", "task_id", "annotation_id", "rule_version", "source_canonical_sha256", "source_scope_sha256", "source_semi_sha256", "source_undercoverage_sha256", "dataset_group", "independence_status", "model_issue_primary", "scope_evidence_status", "semi_issue_recognition_ready", "semi_geometry_correction_evidence_status", "undercoverage_evidence_status", "process_evaluable", "adjudication_status"], [{"worker_id": "w1", "project_id": "p1", "task_id": "t1", "annotation_id": "a1", "rule_version": "r1", "source_canonical_sha256": "canon", "source_scope_sha256": "scope", "source_semi_sha256": "semi", "source_undercoverage_sha256": "under", "dataset_group": "PreScreen_semi", "independence_status": "independent", "model_issue_primary": "corner_drift", "scope_evidence_status": "evaluable", "semi_issue_recognition_ready": "true", "semi_geometry_correction_evidence_status": "not_evaluable_missing_geometry_comparison", "undercoverage_evidence_status": "candidate_only_pending_adjudication", "process_evaluable": "true", "adjudication_status": "not_required"}])
    status = tmp_path / "status.csv"
    _csv(status, ["worker_id", "rule_version"], [{"worker_id": "w1", "rule_version": "r1"}])
    scores = tmp_path / "scores.csv"
    _csv(scores, ["worker_id", "task_id", "annotation_id", "scoring_rule_version", "source_canonical_sha256", "source_final_gold_sha256", "included_in_p1_geometry_profile"], [{"worker_id": "w1", "task_id": "t1", "annotation_id": "a1", "scoring_rule_version": "g1", "source_canonical_sha256": "canon", "source_final_gold_sha256": "gold", "included_in_p1_geometry_profile": "true"}])
    profile = tmp_path / "profile.csv"
    _csv(profile, ["worker_id", "scoring_rule_version", "source_canonical_sha256", "source_final_gold_sha256"], [{"worker_id": "w1", "scoring_rule_version": "g1", "source_canonical_sha256": "canon", "source_final_gold_sha256": "gold"}])

    summary = materialize(quality, worker, tmp_path / "out", p1_task_evidence_csv=correction, p1_worker_status_csv=status, p1_geometry_task_scores=scores, p1_worker_geometry_profile=profile)
    assert summary["p1_bundle_structurally_complete"] is True
    assert summary["p1_undercoverage_dimension_ready"] is False
    assert summary["p1_semi_issue_recognition_ready"] is False
    assert summary["p1_semi_geometry_correction_ready"] is False
    assert summary["full_diagnostic_profile_ready"] is False
    readiness = {row["dimension"]: row for row in _rows(tmp_path / "out" / "p1_worker_dimension_readiness_C1.csv")}
    assert readiness["semi_issue_recognition"]["expected_count"] == "0"
    assert readiness["semi_issue_recognition"]["evaluable_count"] == "0"
    assert readiness["semi_issue_recognition"]["support_ready"] == "false"
    assert readiness["undercoverage"]["not_applicable_count"] == "1"
    assert summary["pending_dimension_cell_count"] == 0
    assert summary["unique_pending_annotation_count"] == 1


def test_c1_geometry_components_stay_continuous_while_binary_and_expert_gates_apply(tmp_path: Path) -> None:
    fields = [
        "round_id", "task_id", "base_task_id", "dataset_group", "condition", "worker_id", "canonical_annotation_id",
        "task_final_scope", "geometry_reference_status", "geometry_valid", "geometry_score_gate_passed", "quality_metric_name",
        "quality_metric_value", "geometry_metric_direction", "geometry_normalization_rule", "geometry_failure_threshold_status",
        "geometry_failure_family_evaluable", "geometry_failure_observed", "family", "undercoverage_evidence_status",
        "undercoverage_expert_verdict", "undercoverage_subfamily", "undercoverage_failure_observed", "undercoverage_risk_level",
        "semi_issue_recognition_evaluable", "semi_geometry_correction_evaluable", "semi_response_type", "semi_correction_failure_observed",
    ]
    common = {"round_id": "C1", "worker_id": "w1", "task_final_scope": "in_scope", "geometry_reference_status": "expert_hard_single", "geometry_valid": "true"}
    rows = [
        {**common, "task_id": "g1", "base_task_id": "g1", "dataset_group": "Calibration_anchor", "condition": "manual", "canonical_annotation_id": "g1", "geometry_score_gate_passed": "true", "quality_metric_name": "iou", "quality_metric_value": "0.8", "geometry_metric_direction": "higher_is_better", "geometry_normalization_rule": "identity_0_1", "geometry_failure_threshold_status": "not_frozen", "family": "geometry_quality_failure"},
        {**common, "task_id": "g2", "base_task_id": "g2", "dataset_group": "Calibration_core", "condition": "manual", "canonical_annotation_id": "g2", "geometry_score_gate_passed": "true", "quality_metric_name": "iou", "quality_metric_value": "0.6", "geometry_metric_direction": "higher_is_better", "geometry_normalization_rule": "identity_0_1", "geometry_failure_threshold_status": "not_frozen", "family": "geometry_quality_failure"},
        {**common, "task_id": "u1", "base_task_id": "u1", "dataset_group": "Calibration_core", "condition": "manual", "canonical_annotation_id": "u1", "family": "undercoverage_failure", "undercoverage_evidence_status": "evaluable_expert_adjudicated", "undercoverage_expert_verdict": "rejected_proxy_false_positive", "undercoverage_subfamily": "full_room_attempt", "undercoverage_failure_observed": "false"},
        {**common, "task_id": "u2", "base_task_id": "u2", "dataset_group": "Calibration_core", "condition": "manual", "canonical_annotation_id": "u2", "family": "undercoverage_failure", "undercoverage_risk_level": "high"},
        {**common, "task_id": "s1", "base_task_id": "s1", "dataset_group": "Calibration_semi", "condition": "semi", "canonical_annotation_id": "s1", "family": "semi_correction_failure", "semi_issue_recognition_evaluable": "true", "semi_geometry_correction_evaluable": "true", "semi_response_type": "successful_correction", "semi_correction_failure_observed": "false"},
    ]
    quality = tmp_path / "quality.csv"
    worker = tmp_path / "worker.csv"
    _csv(quality, fields, rows)
    _csv(worker, ["worker_id"], [{"worker_id": "w1"}])

    summary = materialize(quality, worker, tmp_path / "out")
    evidence = _rows(tmp_path / "out" / "worker_task_evidence_table_C1.csv")
    main = _rows(tmp_path / "out" / "worker_profile_main_matrix_C1.csv")[0]
    family = {row["family"]: row for row in _rows(tmp_path / "out" / "worker_failure_family_response_C1.csv")}
    semi = [row for row in evidence if row["task_id"] == "s1"]

    assert main["r_geometry_u"] == "0.700000"
    assert family["geometry_quality_failure"]["n_observed"] == "0"
    assert family["undercoverage_failure"]["n_observed"] == "1"
    assert family["undercoverage_failure"]["n_fail"] == "0"
    assert {row["evidence_signal"] for row in semi} == {"semi_issue_recognition", "semi_geometry_correction"}
    assert sum(row["included_in_T_u"] == "true" for row in semi) == 1
    assert summary["formal_predictive_validity_status"] == "not_run_blocked"
    assert (tmp_path / "out" / "p1_to_c1_predictive_validity.deprecated.json").exists()
    assert not (tmp_path / "out" / "p1_to_c1_predictive_validity.csv").exists()


def test_missing_failure_outcomes_do_not_become_successes(tmp_path: Path) -> None:
    fields = [
        "round_id", "task_id", "base_task_id", "dataset_group", "condition", "worker_id", "canonical_annotation_id", "task_final_scope",
        "geometry_reference_status", "geometry_valid", "geometry_score_gate_passed", "geometry_failure_threshold_status", "geometry_failure_family_evaluable", "geometry_failure_observed",
        "family", "undercoverage_evidence_status", "undercoverage_expert_verdict", "undercoverage_failure_observed",
        "semi_issue_recognition_evaluable", "semi_geometry_correction_evaluable", "semi_response_type", "semi_correction_failure_observed",
    ]
    common = {"round_id": "C1", "worker_id": "w1", "task_final_scope": "in_scope", "geometry_reference_status": "expert_hard_single", "geometry_valid": "true"}
    rows = [
        {**common, "task_id": "g", "base_task_id": "g", "dataset_group": "Calibration_anchor", "condition": "manual", "canonical_annotation_id": "g", "geometry_score_gate_passed": "true", "geometry_failure_threshold_status": "frozen", "geometry_failure_family_evaluable": "true", "geometry_failure_observed": "", "family": "geometry_quality_failure"},
        {**common, "task_id": "u", "base_task_id": "u", "dataset_group": "Calibration_core", "condition": "manual", "canonical_annotation_id": "u", "family": "undercoverage_failure", "undercoverage_evidence_status": "evaluable_expert_adjudicated", "undercoverage_expert_verdict": "confirmed_partial_undercoverage", "undercoverage_failure_observed": ""},
        {**common, "task_id": "s", "base_task_id": "s", "dataset_group": "Calibration_semi", "condition": "semi", "canonical_annotation_id": "s", "family": "semi_correction_failure", "semi_issue_recognition_evaluable": "true", "semi_geometry_correction_evaluable": "true", "semi_response_type": "successful_correction", "semi_correction_failure_observed": ""},
    ]
    quality = tmp_path / "quality.csv"
    worker = tmp_path / "worker.csv"
    _csv(quality, fields, rows)
    _csv(worker, ["worker_id"], [{"worker_id": "w1"}])
    materialize(quality, worker, tmp_path / "out")
    evidence = _rows(tmp_path / "out" / "worker_task_evidence_table_C1.csv")
    family = {row["family"]: row for row in _rows(tmp_path / "out" / "worker_failure_family_response_C1.csv")}

    assert next(row for row in evidence if row["task_id"] == "g")["response_type"] == "geometry_not_evaluable"
    assert next(row for row in evidence if row["task_id"] == "u")["included_in_U_u"] == "false"
    assert next(row for row in evidence if row["task_id"] == "s" and row["evidence_signal"] == "semi_geometry_correction")["included_in_T_u"] == "false"
    assert family["geometry_quality_failure"]["n_observed"] == "0"
    assert family["undercoverage_failure"]["n_observed"] == "0"
    assert family["semi_correction_failure"]["n_observed"] == "0"


def test_system_collection_issue_does_not_remove_capability_candidates_from_readiness() -> None:
    task = {
        "worker_id": "w1", "task_id": "t1", "annotation_id": "a1", "independence_status": "independent",
        "canonical_eligibility_status": "valid", "assigned_expected": "true", "outside_assignment_submission": "false", "duplicate_worker_task_submission": "false", "schema_interpretable": "true",
        "process_evaluable": "false", "process_failure_observed": "false", "system_collection_issue": "true",
        "condition": "manual", "task_final_scope": "in_scope", "scope_evidence_status": "evaluable",
    }
    score = {"worker_id": "w1", "task_id": "t1", "annotation_id": "a1", "included_in_p1_geometry_profile": "true"}
    readiness = {row["dimension"]: row for row in build_p1_worker_dimension_readiness([task], [score], {name: True for name in ("geometry", "scope", "semi_issue_recognition", "semi_geometry_correction", "undercoverage", "process")})}

    assert readiness["geometry"]["expected_count"] == 1
    assert readiness["scope"]["expected_count"] == 1
    assert readiness["undercoverage"]["expected_count"] == 1
    assert readiness["process"]["expected_count"] == 0


def test_system_collection_issue_is_not_worker_process_failure(tmp_path: Path) -> None:
    fields = ["round_id", "task_id", "base_task_id", "dataset_group", "condition", "worker_id", "canonical_annotation_id", "geometry_valid", "assigned_expected", "active_time_source", "active_time_integrity_status", "system_collection_issue", "unassigned_audit_present", "unassigned_active_time_seconds", "audit_only", "outside_assignment_submission", "duplicate_worker_task_submission", "active_time_worker_process_failure"]
    quality = tmp_path / "quality.csv"
    _csv(quality, fields, [
        {"round_id": "C1", "task_id": "unknown_only", "base_task_id": "b1", "dataset_group": "Calibration_core", "condition": "manual", "worker_id": "w1", "canonical_annotation_id": "a1", "geometry_valid": "true", "assigned_expected": "true", "active_time_source": "missing", "active_time_integrity_status": "unknown_audit_only", "system_collection_issue": "true", "unassigned_audit_present": "true", "unassigned_active_time_seconds": "4", "audit_only": "true", "outside_assignment_submission": "false", "duplicate_worker_task_submission": "false"},
        {"round_id": "C1", "task_id": "known_plus_unknown", "base_task_id": "b2", "dataset_group": "Calibration_core", "condition": "manual", "worker_id": "w1", "canonical_annotation_id": "a2", "geometry_valid": "true", "assigned_expected": "true", "active_time_source": "log", "active_time_integrity_status": "exact_annotation_valid", "system_collection_issue": "true", "unassigned_audit_present": "true", "unassigned_active_time_seconds": "3", "audit_only": "false", "outside_assignment_submission": "false", "duplicate_worker_task_submission": "false"},
        {"round_id": "C1", "task_id": "outside", "base_task_id": "b3", "dataset_group": "Calibration_core", "condition": "manual", "worker_id": "w1", "canonical_annotation_id": "a3", "geometry_valid": "true", "assigned_expected": "false", "active_time_source": "missing", "active_time_integrity_status": "unknown_audit_only", "system_collection_issue": "true", "unassigned_audit_present": "true", "unassigned_active_time_seconds": "2", "audit_only": "true", "outside_assignment_submission": "true", "duplicate_worker_task_submission": "false"},
        {"round_id": "C1", "task_id": "duplicate", "base_task_id": "b4", "dataset_group": "Calibration_core", "condition": "manual", "worker_id": "w1", "canonical_annotation_id": "a4", "geometry_valid": "true", "assigned_expected": "true", "active_time_source": "missing", "active_time_integrity_status": "unknown_audit_only", "system_collection_issue": "true", "unassigned_audit_present": "true", "unassigned_active_time_seconds": "1", "audit_only": "true", "outside_assignment_submission": "false", "duplicate_worker_task_submission": "true"},
        {"round_id": "C1", "task_id": "attributable", "base_task_id": "b5", "dataset_group": "Calibration_core", "condition": "manual", "worker_id": "w1", "canonical_annotation_id": "a5", "geometry_valid": "true", "assigned_expected": "true", "active_time_source": "log", "active_time_integrity_status": "exact_annotation_valid", "system_collection_issue": "true", "unassigned_audit_present": "true", "unassigned_active_time_seconds": "1", "audit_only": "false", "outside_assignment_submission": "false", "duplicate_worker_task_submission": "false", "active_time_worker_process_failure": "true"},
    ])
    worker_state = tmp_path / "worker.csv"
    _csv(worker_state, ["worker_id"], [{"worker_id": "w1"}])

    summary = materialize(quality, worker_state, tmp_path / "out")
    evidence = {row["task_id"]: row for row in _rows(tmp_path / "out" / "worker_task_evidence_table_C1.csv")}

    assert evidence["unknown_only"]["active_time_worker_process_failure"] == "false"
    assert evidence["unknown_only"]["process_invalid"] == "false"
    assert evidence["known_plus_unknown"]["active_time_worker_process_failure"] == "false"
    assert evidence["outside"]["process_invalid"] == "true"
    assert evidence["outside"]["active_time_integrity_status"] == "unknown_audit_only"
    assert evidence["duplicate"]["process_invalid"] == "true"
    assert evidence["attributable"]["process_invalid"] == "true"
    assert summary["unassigned_active_time_seconds_total"] == 11.0
    assert summary["system_collection_issue_row_count"] == 5


def test_geometry_audit_rows_do_not_enter_family_denominator_without_scorer_gate(tmp_path: Path) -> None:
    quality = tmp_path / "quality.csv"
    _csv(quality, ["round_id", "worker_id", "task_id", "canonical_annotation_id", "dataset_group", "condition", "task_final_scope", "geometry_reference_status", "geometry_valid", "used_for_r_u", "assigned_expected"], [{"round_id": "C1", "worker_id": "w1", "task_id": "t1", "canonical_annotation_id": "a1", "dataset_group": "Calibration_anchor", "condition": "manual", "task_final_scope": "in_scope", "geometry_reference_status": "expert_hard_single", "geometry_valid": "true", "used_for_r_u": "true", "assigned_expected": "true"}])
    worker = tmp_path / "worker.csv"
    _csv(worker, ["worker_id"], [{"worker_id": "w1"}])
    materialize(quality, worker, tmp_path / "out")
    evidence = _rows(tmp_path / "out" / "worker_task_evidence_table_C1.csv")[0]
    family = next(row for row in _rows(tmp_path / "out" / "worker_failure_family_response_C1.csv") if row["family"] == "geometry_quality_failure")
    assert evidence["family_evaluable"] == "false"
    assert evidence["family_included_in_denominator"] == "false"
    assert family["n_observed"] == "0"


def test_geometry_reliability_rejects_lower_direction_and_accepts_compatible_higher_components(tmp_path: Path) -> None:
    from tools.thesis_main.analysis.c1_materialize_worker_profile_sidecar import build_main_matrix

    lower = [
        {"worker_id": "w1", "stage": "P1", "pool": "a", "included_in_r_geometry": True, "quality_metric_value": "1", "quality_metric_name": "rmse", "geometry_metric_direction": "lower_is_better", "geometry_normalization_rule": "raw", "task_id": "a", "canonical_annotation_id": "a"},
        {"worker_id": "w1", "stage": "C1", "pool": "b", "included_in_r_geometry": True, "quality_metric_value": "2", "quality_metric_name": "rmse", "geometry_metric_direction": "lower_is_better", "geometry_normalization_rule": "raw", "task_id": "b", "canonical_annotation_id": "b"},
    ]
    lower_main = build_main_matrix(lower, {"w1": {}})[0]
    assert lower_main["r_geometry_u"] == ""
    assert lower_main["geometry_reliability_exclusion_reason"] == "geometry_component_direction_not_higher_is_better"
    higher = [
        {**row, "quality_metric_name": "iou", "quality_metric_value": "0.8", "geometry_metric_direction": "higher_is_better", "geometry_normalization_rule": "unit_interval"}
        for row in lower
    ]
    assert build_main_matrix(higher, {"w1": {}})[0]["r_geometry_u"] == "0.800000"
