from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.thesis_main.analysis.c1_materialize_worker_profile_sidecar import _geometry_metric_summary, build_main_matrix, build_p1_evidence_rows, materialize as materialize_sidecar
from tools.thesis_main.analysis.materialize_p1_post_closeout_evidence_correction import build_correction
from tools.thesis_main.analysis.materialize_p1_post_closeout_geometry_scores import materialize_scores
from tools.thesis_main.analysis.quality_core.geometry_metrics import analyze_layout_pairing, compute_layout_mask_iou


POINTS = [
    {"type": "keypointlabels", "value": {"x": 10, "y": 20, "keypointlabels": ["Corner"]}},
    {"type": "keypointlabels", "value": {"x": 10, "y": 80, "keypointlabels": ["Corner"]}},
    {"type": "keypointlabels", "value": {"x": 60, "y": 20, "keypointlabels": ["Corner"]}},
    {"type": "keypointlabels", "value": {"x": 60, "y": 80, "keypointlabels": ["Corner"]}},
]


def _csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _ann(annotation_id: str, worker: str, created_at: str, *, parent: str | None = None, points=None) -> dict:
    return {
        "id": annotation_id,
        "completed_by": {"id": worker},
        "created_at": created_at,
        "parent_annotation": parent,
        "lead_time": 30,
        "result": points or POINTS,
    }


def _canonical(annotation_id: str, worker: str, task_id: str = "t1", *, geometry=None) -> dict[str, str]:
    return {
        "project_id": "p1",
        "task_id": task_id,
        "base_task_id": f"base-{task_id}",
        "dataset_group": "PreScreen_manual",
        "condition": "manual",
        "worker_id": worker,
        "annotator_id": worker,
        "annotation_id": annotation_id,
        "geometry_hash": geometry or "",
        "canonical_geometry": json.dumps([[102.4, 102.4], [102.4, 409.6], [614.4, 102.4], [614.4, 409.6]]),
        "n_corners": "4",
        "active_time_source": "lead_time_fallback",
        "active_time_match_status": "fallback_no_direct_log",
        "lead_time_seconds": "30",
        "active_time": "30",
    }


def test_cross_worker_exact_parent_is_confirmed_and_capability_excluded(tmp_path: Path) -> None:
    export = tmp_path / "export.json"
    export.write_text(json.dumps([{"id": "t1", "project": "p1", "data": {}, "annotations": [
        _ann("parent", "w1", "2026-07-01T00:00:00Z"),
        _ann("child", "w2", "2026-07-01T00:01:00Z", parent="parent"),
    ]}]), encoding="utf-8")
    canonical = tmp_path / "canonical.csv"
    _csv(canonical, list(_canonical("child", "w2")), [_canonical("child", "w2")])
    admission = tmp_path / "admission.csv"
    _csv(admission, ["worker_id", "admission_status"], [{"worker_id": "w2", "admission_status": "pass"}])
    assignment = tmp_path / "c1.csv"
    _csv(assignment, ["worker_id"], [{"worker_id": "w2"}])

    task_rows, worker_rows, summary = build_correction(canonical, [export], admission, assignment)

    row = task_rows[0]
    assert row["independence_status"] == "non_independent_confirmed"
    assert row["parent_same_task"] is True
    assert row["parent_cross_owner"] is True
    assert row["parent_precedes_child"] is True
    assert row["geometry_relation"] == "identical"
    assert row["capability_evidence_eligible"] is False
    assert row["included_in_r_geometry"] is False
    assert row["included_in_process_reliability"] is True
    assert row["process_failure_observed"] is True
    assert row["process_failure_subfamily"] == "non_independent_submission"
    assert worker_rows[0]["p1_capability_evidence_status"] == "invalid_non_independent_submission"
    assert worker_rows[0]["operational_c1_assignment_status"] == "unchanged_existing_assignment"
    assert summary["n_non_independent_confirmed"] == 1
    assert row["primary_active_time_eligible"] is False
    assert row["sensitivity_active_time_eligible"] is False
    assert row["forensic_timing_audit_eligible"] is True
    assert row["timing_evidence_status"] == "parent_derived_forensic_only"


def test_same_worker_revision_is_independent_and_cross_worker_uncertain_is_suspected(tmp_path: Path) -> None:
    export = tmp_path / "export.json"
    export.write_text(json.dumps([{"id": "t1", "project": "p1", "data": {}, "annotations": [
        _ann("parent", "w1", "2026-07-01T00:00:00Z"),
        _ann("same", "w1", "2026-07-01T00:01:00Z", parent="parent"),
        _ann("different", "w2", "2026-07-01T00:02:00Z", parent="parent", points=POINTS[:2]),
    ]}]), encoding="utf-8")
    canonical = tmp_path / "canonical.csv"
    fields = list(_canonical("same", "w1"))
    _csv(canonical, fields, [_canonical("same", "w1"), _canonical("different", "w2")])
    admission = tmp_path / "admission.csv"
    _csv(admission, ["worker_id", "admission_status"], [{"worker_id": "w1"}, {"worker_id": "w2"}])

    task_rows, _, _ = build_correction(canonical, [export], admission)

    by_annotation = {row["annotation_id"]: row for row in task_rows}
    assert by_annotation["same"]["independence_status"] == "independent"
    assert by_annotation["same"]["parent_cross_owner"] is False
    assert by_annotation["different"]["independence_status"] == "non_independent_suspected"
    assert by_annotation["different"]["process_failure_observed"] is False
    assert by_annotation["different"]["adjudication_status"] == "pending_review"


def test_exact_timing_requires_owner_match_and_task_fallback_keeps_audit_value(tmp_path: Path) -> None:
    export = tmp_path / "export.json"
    export.write_text(json.dumps([{"id": "t1", "project": "p1", "data": {}, "annotations": [_ann("a1", "w1", "2026-07-01T00:00:00Z")]}]), encoding="utf-8")
    canonical = _canonical("a1", "w1")
    canonical.update({"active_time_source": "log", "active_time_match_status": "project+task+annotator+annotation", "active_time": "20", "lead_time_seconds": "20", "annotator_id": "w2"})
    canonical_csv = tmp_path / "canonical.csv"
    _csv(canonical_csv, list(canonical), [canonical])
    admission = tmp_path / "admission.csv"
    _csv(admission, ["worker_id", "admission_status"], [{"worker_id": "w1", "admission_status": "pass"}])

    rows, _, _ = build_correction(canonical_csv, [export], admission)
    row = rows[0]
    assert row["primary_active_time_eligible"] is False
    assert row["timing_evidence_status"] == "task_log_sensitivity_only"
    assert row["active_time_integrity_status"] == "owner_mismatch"
    assert row["active_time_seconds"] == "20"


def test_exact_timing_accepts_real_p1_annotator_only_schema(tmp_path: Path) -> None:
    export = tmp_path / "export.json"
    export.write_text(json.dumps([{"id": "t1", "project": "p1", "annotations": [_ann("a1", "w1", "2026-07-01T00:00:00Z")]}]), encoding="utf-8")
    canonical = _canonical("a1", "w1")
    canonical.pop("worker_id")
    canonical.update({"active_time_source": "log", "active_time_match_status": "project+task+annotator+annotation", "active_time": "20"})
    canonical_csv = tmp_path / "canonical.csv"
    _csv(canonical_csv, list(canonical), [canonical])
    admission = tmp_path / "admission.csv"
    _csv(admission, ["worker_id", "admission_status"], [{"worker_id": "w1", "admission_status": "pass"}])

    rows, _, _ = build_correction(canonical_csv, [export], admission)
    assert rows[0]["primary_active_time_eligible"] is True
    assert rows[0]["active_time_integrity_status"] == "exact_annotation_valid"


def test_non_independent_exact_time_is_forensic_even_without_lead_time(tmp_path: Path) -> None:
    export = tmp_path / "export.json"
    export.write_text(json.dumps([{"id": "t1", "project": "p1", "annotations": [_ann("parent", "w1", "2026-07-01T00:00:00Z"), _ann("confirmed", "w2", "2026-07-01T00:01:00Z", parent="parent"), _ann("suspected", "w3", "2026-07-01T00:02:00Z", parent="parent", points=POINTS[:2])]}]), encoding="utf-8")
    confirmed = _canonical("confirmed", "w2")
    suspected = _canonical("suspected", "w3")
    for row in (confirmed, suspected):
        row.update({"active_time_source": "log", "active_time_match_status": "annotation_exact", "active_time": "20", "lead_time_seconds": ""})
    canonical = tmp_path / "canonical.csv"
    _csv(canonical, list(confirmed), [confirmed, suspected])
    admission = tmp_path / "admission.csv"
    _csv(admission, ["worker_id"], [{"worker_id": "w2"}, {"worker_id": "w3"}])
    rows, _, summary = build_correction(canonical, [export], admission)
    assert {row["timing_evidence_status"] for row in rows} == {"parent_derived_forensic_only"}
    assert all(not row["primary_active_time_eligible"] and not row["sensitivity_active_time_eligible"] and row["forensic_timing_audit_eligible"] for row in rows)
    assert summary["n_primary_active_time"] == 0
    assert summary["n_sensitivity_active_time"] == 0
    assert summary["forensic_timing_audit_count"] == 2


def test_parent_audit_summary_covers_all_workers_and_not_evaluable_parent(tmp_path: Path) -> None:
    tasks = [
        {"id": "confirmed", "project": "p1", "annotations": [_ann("p", "w0", "2026-07-01T00:00:00Z"), _ann("c", "w1", "2026-07-01T00:01:00Z", parent="p")]},
        {"id": "suspected", "project": "p1", "annotations": [_ann("p2", "w0", "2026-07-01T00:00:00Z"), _ann("s", "w2", "2026-07-01T00:01:00Z", parent="p2", points=POINTS[:2])]},
        {"id": "revision", "project": "p1", "annotations": [_ann("r0", "w3", "2026-07-01T00:00:00Z"), _ann("r1", "w3", "2026-07-01T00:01:00Z", parent="r0")]},
        {"id": "solo", "project": "p1", "annotations": [_ann("i", "w4", "2026-07-01T00:00:00Z")]},
        {"id": "missing", "project": "p1", "annotations": [_ann("m", "w5", "2026-07-01T00:00:00Z", parent="gone")]},
    ]
    export = tmp_path / "export.json"
    export.write_text(json.dumps(tasks), encoding="utf-8")
    rows = [_canonical("c", "w1", "confirmed"), _canonical("s", "w2", "suspected"), _canonical("r1", "w3", "revision"), _canonical("i", "w4", "solo"), _canonical("m", "w5", "missing")]
    canonical = tmp_path / "canonical.csv"
    _csv(canonical, list(rows[0]), rows)
    admission = tmp_path / "admission.csv"
    _csv(admission, ["worker_id"], [{"worker_id": f"w{i}"} for i in range(1, 6)])
    _, _, summary = build_correction(canonical, [export], admission)
    assert summary["n_workers_audited"] == 5
    assert summary["n_annotations_audited"] == 5
    assert summary["n_independent"] == 2
    assert summary["n_non_independent_confirmed"] == 1
    assert summary["n_non_independent_suspected"] == 1
    assert summary["n_parent_not_evaluable"] == 1
    assert summary["workers_with_confirmed_non_independence"] == ["w1"]
    assert summary["workers_with_suspected_non_independence"] == ["w2"]


def test_formal_scope_semi_undercoverage_sources_gate_capability(tmp_path: Path) -> None:
    model_choice = {"type": "choices", "from_name": "model_issue", "value": {"choices": ["acceptable"]}}
    export = tmp_path / "export.json"
    export.write_text(json.dumps([{"id": "t1", "project": "p1", "annotations": [_ann("a1", "w1", "2026-07-01T00:00:00Z", points=POINTS + [model_choice])]}]), encoding="utf-8")
    canonical_row = _canonical("a1", "w1")
    canonical_row["dataset_group"] = "PreScreen_semi"
    canonical_row["condition"] = "semi"
    canonical = tmp_path / "canonical.csv"
    _csv(canonical, list(canonical_row), [canonical_row])
    admission = tmp_path / "admission.csv"
    _csv(admission, ["worker_id", "admission_status", "r_u_0"], [{"worker_id": "w1", "admission_status": "pass", "r_u_0": "0.8"}])
    scope = tmp_path / "scope.csv"
    _csv(scope, ["annotator_id", "project_id", "task_id", "task_final_scope", "worker_scope_response", "scope_response_primary_eligible"], [{"annotator_id": "w1", "project_id": "p1", "task_id": "t1", "task_final_scope": "in_scope", "worker_scope_response": "correct_in_scope", "scope_response_primary_eligible": "true"}])
    semi = tmp_path / "semi.csv"
    _csv(semi, ["runtime_task_id", "expert_realized_model_issue_primary"], [{"runtime_task_id": "t1", "expert_realized_model_issue_primary": "corner_drift"}])
    under = tmp_path / "under.csv"
    _csv(under, ["annotator_id", "task_id", "undercoverage_risk_level"], [{"annotator_id": "w1", "task_id": "t1", "undercoverage_risk_level": "high"}])

    rows, workers, summary = build_correction(canonical, [export], admission, scope_evidence_csv=scope, semi_evidence_csv=semi, undercoverage_evidence_csv=under)
    row = rows[0]
    assert row["included_in_r_scope"] is True
    assert row["semi_response_type"] == "blind_trust"
    assert row["semi_correction_failure_observed"] is True
    assert row["semi_issue_recognition_evaluable"] is True
    assert row["included_in_T_u"] is False
    assert row["undercoverage_evidence_status"] == "candidate_only_pending_adjudication"
    assert row["undercoverage_response"] == ""
    assert row["undercoverage_interpretation_allowed"] is False
    assert row["included_in_U_u"] is False  # semi rows never enter manual coverage support
    assert workers[0]["p1_r0_analysis_eligible"] is True
    assert workers[0]["c1_r_u_calib_status"] == "pending_c1_calibration_evidence"
    assert summary["warnings"] == []


def test_missing_dimension_artifacts_are_not_evaluable_not_success(tmp_path: Path) -> None:
    export = tmp_path / "export.json"
    export.write_text(json.dumps([{"id": "t1", "project": "p1", "annotations": [_ann("a1", "w1", "2026-07-01T00:00:00Z")]}]), encoding="utf-8")
    canonical = tmp_path / "canonical.csv"
    _csv(canonical, list(_canonical("a1", "w1")), [_canonical("a1", "w1")])
    admission = tmp_path / "admission.csv"
    _csv(admission, ["worker_id"], [{"worker_id": "w1"}])
    scope = tmp_path / "scope.csv"
    _csv(scope, ["annotator_id", "project_id", "task_id", "task_final_scope", "worker_scope_response", "scope_response_primary_eligible"], [{"annotator_id": "w1", "project_id": "p1", "task_id": "t1", "task_final_scope": "in_scope", "worker_scope_response": "correct_in_scope", "scope_response_primary_eligible": "true"}])
    rows, _, summary = build_correction(canonical, [export], admission)
    assert rows[0]["included_in_r_scope"] is False
    assert rows[0]["included_in_T_u"] is False
    assert rows[0]["included_in_U_u"] is False
    assert set(summary["warnings"]) == {"p1_scope_evidence_missing", "p1_semi_evidence_missing", "p1_undercoverage_evidence_missing"}


def test_undercoverage_proxy_needs_expert_verdict_before_u_u(tmp_path: Path) -> None:
    export = tmp_path / "export.json"
    export.write_text(json.dumps([{"id": "t1", "project": "p1", "annotations": [_ann("a1", "w1", "2026-07-01T00:00:00Z")]}]), encoding="utf-8")
    canonical = tmp_path / "canonical.csv"
    _csv(canonical, list(_canonical("a1", "w1")), [_canonical("a1", "w1")])
    admission = tmp_path / "admission.csv"
    _csv(admission, ["worker_id"], [{"worker_id": "w1"}])
    scope = tmp_path / "scope.csv"
    _csv(scope, ["annotator_id", "project_id", "task_id", "task_final_scope", "worker_scope_response", "scope_response_primary_eligible"], [{"annotator_id": "w1", "project_id": "p1", "task_id": "t1", "task_final_scope": "in_scope", "worker_scope_response": "correct_in_scope", "scope_response_primary_eligible": "true"}])
    under = tmp_path / "under.csv"
    _csv(under, ["annotator_id", "task_id", "undercoverage_risk_level", "undercoverage_expert_verdict"], [{"annotator_id": "w1", "task_id": "t1", "undercoverage_risk_level": "high", "undercoverage_expert_verdict": "confirmed_partial_undercoverage"}])
    rows, _, _ = build_correction(canonical, [export], admission, scope_evidence_csv=scope, undercoverage_evidence_csv=under)
    assert rows[0]["undercoverage_evidence_status"] == "evaluable_expert_adjudicated"
    assert rows[0]["undercoverage_failure_observed"] is True
    assert rows[0]["included_in_U_u"] is True


def test_rejected_undercoverage_proxy_is_evaluable_nonfailure(tmp_path: Path) -> None:
    export = tmp_path / "export.json"
    export.write_text(json.dumps([{"id": "t1", "project": "p1", "annotations": [_ann("a1", "w1", "2026-07-01T00:00:00Z")]}]), encoding="utf-8")
    canonical = tmp_path / "canonical.csv"
    _csv(canonical, list(_canonical("a1", "w1")), [_canonical("a1", "w1")])
    admission = tmp_path / "admission.csv"
    _csv(admission, ["worker_id"], [{"worker_id": "w1"}])
    scope = tmp_path / "scope.csv"
    _csv(scope, ["annotator_id", "project_id", "task_id", "task_final_scope", "worker_scope_response", "scope_response_primary_eligible"], [{"annotator_id": "w1", "project_id": "p1", "task_id": "t1", "task_final_scope": "in_scope", "worker_scope_response": "correct_in_scope", "scope_response_primary_eligible": "true"}])
    under = tmp_path / "under.csv"
    _csv(under, ["annotator_id", "task_id", "undercoverage_risk_level", "undercoverage_expert_verdict"], [{"annotator_id": "w1", "task_id": "t1", "undercoverage_risk_level": "high", "undercoverage_expert_verdict": "rejected_proxy_false_positive"}])
    rows, _, _ = build_correction(canonical, [export], admission, scope_evidence_csv=scope, undercoverage_evidence_csv=under)
    assert rows[0]["included_in_U_u"] is True
    assert rows[0]["undercoverage_failure_observed"] is False


def test_sidecar_ingests_p1_scope_semi_and_undercoverage_evidence() -> None:
    base = {"worker_id": "w1", "project_id": "p1", "base_task_id": "b", "annotation_id": "a", "independence_status": "independent", "process_evaluable": "true", "process_failure_observed": "false", "capability_evidence_eligible": "true"}
    rows = build_p1_evidence_rows([
        {**base, "task_id": "scope", "dataset_group": "PreScreen_oos", "condition": "oos_gate", "scope_evidence_status": "evaluable", "task_final_scope": "oos", "worker_scope_response": "scope_false_negative", "included_in_r_scope": "true"},
        {**base, "task_id": "semi", "dataset_group": "PreScreen_semi", "condition": "semi", "semi_evidence_status": "evaluable", "semi_response_type": "blind_trust", "semi_correction_failure_observed": "true", "included_in_T_u": "true"},
        {**base, "task_id": "under", "dataset_group": "PreScreen_manual", "condition": "manual", "undercoverage_evidence_status": "evaluable_expert_adjudicated", "undercoverage_response": "partial_undercoverage", "undercoverage_subfamily": "partial_undercoverage", "undercoverage_failure_observed": "true", "included_in_U_u": "true"},
    ])
    assert any(row["task_id"] == "scope" and row["family"] == "scope_oos_failure" and row["_is_fail"] is True for row in rows)
    assert any(row["task_id"] == "semi" and row["family"] == "semi_correction_failure" and row["_is_fail"] is True for row in rows)
    assert any(row["task_id"] == "under" and row["family"] == "undercoverage_failure" and row["_is_fail"] is True for row in rows)


def test_one_p1_submission_keeps_multiple_signals_without_process_denominator_duplication() -> None:
    correction = {
        "worker_id": "w1", "project_id": "p1", "task_id": "t1", "base_task_id": "b1", "annotation_id": "a1",
        "dataset_group": "PreScreen_manual", "condition": "manual", "independence_status": "independent",
        "process_evaluable": "true", "process_failure_observed": "false", "capability_evidence_eligible": "true",
        "scope_evidence_status": "evaluable", "worker_scope_response": "correct_in_scope", "included_in_r_scope": "true",
        "semi_evidence_status": "evaluable", "semi_response_type": "blind_trust", "semi_correction_failure_observed": "true", "included_in_T_u": "true",
        "undercoverage_evidence_status": "evaluable_expert_adjudicated", "undercoverage_response": "partial_undercoverage", "undercoverage_subfamily": "partial_undercoverage", "undercoverage_failure_observed": "true", "included_in_U_u": "true",
    }
    score = {("w1", "t1", "a1"): {"geometry_score_raw": "0.9", "included_in_p1_geometry_profile": "true", "geometry_metric_name": "iou", "geometry_metric_direction": "higher_is_better", "geometry_normalization_rule": "unit_interval", "geometry_component_name": "p1_iou"}}
    rows = build_p1_evidence_rows([correction], score)
    assert {row["evidence_signal"] for row in rows} == {"geometry", "scope", "semi", "undercoverage", "process"}
    main = build_main_matrix(rows, {"w1": {}})[0]
    assert main["n_process_support"] == 1


def test_long_open_flag_is_relative_and_lead_time_never_becomes_primary(tmp_path: Path) -> None:
    tasks = []
    canonical_rows = []
    for index, lead in enumerate([10, 12, 11, 13, 1000]):
        task_id = f"t{index}"
        annotation_id = f"a{index}"
        tasks.append({"id": task_id, "project": "p1", "data": {}, "annotations": [_ann(annotation_id, "w1", f"2026-07-01T00:0{index}:00Z")]})
        row = _canonical(annotation_id, "w1", task_id=task_id)
        row.update({"active_time_source": "lead_time_fallback", "active_time_match_status": "fallback_no_direct_log", "active_time": "", "lead_time_seconds": str(lead)})
        canonical_rows.append(row)
    export = tmp_path / "export.json"
    export.write_text(json.dumps(tasks), encoding="utf-8")
    canonical = tmp_path / "canonical.csv"
    _csv(canonical, list(canonical_rows[0]), canonical_rows)
    admission = tmp_path / "admission.csv"
    _csv(admission, ["worker_id", "admission_status"], [{"worker_id": "w1", "admission_status": "pass"}])

    rows, _, _ = build_correction(canonical, [export], admission)
    outlier = next(row for row in rows if row["task_id"] == "t4")
    assert outlier["long_open_draft_flag"] is True
    assert outlier["primary_active_time_eligible"] is False
    assert outlier["active_time_seconds"] == ""
    assert outlier["lead_time_seconds"] == 1000.0


def test_layout_mask_iou_is_one_for_identical_and_handles_seam() -> None:
    points = [[0, 100], [0, 400], [512, 100], [512, 400]]
    score, meta = compute_layout_mask_iou(points, points)
    assert score == 1.0
    assert meta["reason"] == ""

    seam_points = [[1020, 100], [1020, 400], [10, 100], [10, 400]]
    seam_score, _ = compute_layout_mask_iou(seam_points, seam_points)
    assert seam_score == 1.0


def test_strict_pairing_rejects_odd_partial_and_dense_ambiguous_layouts() -> None:
    _, odd = analyze_layout_pairing([[100, 100], [100, 400], [600, 100]])
    assert odd["odd_points"] is True
    assert odd["coverage"] < 1
    _, partial = analyze_layout_pairing([[100, 100], [100, 400], [600, 100], [900, 400]])
    assert partial["unpaired_point_count"] > 0
    _, ambiguous = analyze_layout_pairing([[100, 100], [100, 200], [100, 300], [100, 400]])
    assert ambiguous["pairing_ambiguous"] is True


def test_pairing_search_keeps_later_unique_best_and_marks_near_tie() -> None:
    _, unique = analyze_layout_pairing([[0, 10], [10, 20], [20, 30], [30, 40]])
    assert unique["optimal_matching_count"] == 1
    assert unique["best_cost"] == 20.0
    assert unique["second_best_cost"] == 40.0
    _, near = analyze_layout_pairing([[0, 10], [10, 20], [10.01, 30], [20, 40]])
    assert near["pairing_ambiguous"] is True
    assert near["ambiguity_reason"] == "near_equivalent_matching"


def test_incompatible_geometry_metrics_do_not_form_combined_profile() -> None:
    rows = [
        {"included_in_r_geometry": True, "quality_metric_value": "0.9", "quality_metric_name": "iou", "geometry_metric_direction": "higher_is_better", "geometry_normalization_rule": "unit_interval", "stage": "P1", "pool": "PreScreen_manual"},
        {"included_in_r_geometry": True, "quality_metric_value": "0.1", "quality_metric_name": "residual", "geometry_metric_direction": "lower_is_better", "geometry_normalization_rule": "raw_pixels", "stage": "C1", "pool": "Calibration_anchor"},
    ]
    assert _geometry_metric_summary(rows) == ""


def test_process_reliability_uses_successes_and_excludes_system_only_rows(tmp_path: Path) -> None:
    quality = tmp_path / "quality.csv"
    _csv(
        quality,
        ["round_id", "task_id", "base_task_id", "dataset_group", "condition", "worker_id", "geometry_valid", "assigned_expected", "active_time_source", "system_collection_issue", "active_time_integrity_status"],
        [{"round_id": "C1", "task_id": "system", "base_task_id": "b0", "dataset_group": "Calibration_core", "condition": "manual", "worker_id": "w1", "geometry_valid": "true", "assigned_expected": "true", "active_time_source": "missing", "system_collection_issue": "true", "active_time_integrity_status": "unknown_audit_only"}],
    )
    p1 = tmp_path / "p1.csv"
    fields = ["worker_id", "task_id", "base_task_id", "dataset_group", "condition", "annotation_id", "independence_status", "process_evaluable", "process_failure_observed", "process_failure_subfamily", "active_time_source", "timing_evidence_status", "primary_active_time_eligible", "capability_evidence_eligible"]
    rows = []
    for index in range(57):
        rows.append({"worker_id": "w1", "task_id": f"p{index}", "base_task_id": f"b{index}", "dataset_group": "PreScreen_manual", "condition": "manual", "annotation_id": f"a{index}", "independence_status": "non_independent_confirmed" if index == 0 else "independent", "process_evaluable": "true", "process_failure_observed": "true" if index == 0 else "false", "process_failure_subfamily": "non_independent_submission" if index == 0 else "process_ok", "active_time_source": "lead_time_fallback", "timing_evidence_status": "lead_time_fallback_sensitivity_only", "primary_active_time_eligible": "false", "capability_evidence_eligible": "false" if index == 0 else "true"})
    _csv(p1, fields, rows)
    worker_state = tmp_path / "worker.csv"
    _csv(worker_state, ["worker_id"], [{"worker_id": "w1"}])

    materialize_sidecar(quality, worker_state, tmp_path / "out", p1_task_evidence_csv=p1)
    main = next(csv.DictReader((tmp_path / "out" / "worker_profile_main_matrix_C1.csv").open(encoding="utf-8")))

    assert main["n_process_support"] == "57"
    assert main["process_reliability"] == "0.982456"


def test_geometry_score_uses_final_gold_and_keeps_correction_gate(tmp_path: Path) -> None:
    canonical = tmp_path / "canonical.csv"
    canonical_row = _canonical("a1", "w1", task_id="t1")
    canonical_row["canonical_geometry"] = json.dumps([[100, 100], [100, 400], [300, 100], [300, 400], [600, 100], [600, 400], [800, 100], [800, 400]])
    _csv(canonical, list(canonical_row), [canonical_row])
    correction = tmp_path / "correction.csv"
    _csv(
        correction,
        ["worker_id", "project_id", "task_id", "base_task_id", "dataset_group", "condition", "annotation_id", "independence_status", "process_failure_observed"],
        [{"worker_id": "w1", "project_id": "p1", "task_id": "t1", "base_task_id": "base-t1", "dataset_group": "PreScreen_manual", "condition": "manual", "annotation_id": "a1", "independence_status": "independent", "process_failure_observed": "false"}],
    )
    gold_status = tmp_path / "gold.csv"
    _csv(
        gold_status,
        ["task_id", "task_final_scope", "gold_status_for_alignment", "validation_status", "geometry_gold_task_id", "gold_reference_role"],
        [{"task_id": "t1", "task_final_scope": "in_scope", "gold_status_for_alignment": "ready_for_alignment", "validation_status": "final_gold_geometry_checked", "geometry_gold_task_id": "task_id:g1", "gold_reference_role": "expert_hard_single"}],
    )
    final_gold = tmp_path / "gold.jsonl"
    final_gold.write_text(json.dumps({"task_id": "g1", "runtime_pairs_1024x512": [{"x": 100, "y_ceiling": 100, "y_floor": 400}, {"x": 300, "y_ceiling": 100, "y_floor": 400}, {"x": 600, "y_ceiling": 100, "y_floor": 400}, {"x": 800, "y_ceiling": 100, "y_floor": 400}]}) + "\n", encoding="utf-8")

    summary = materialize_scores(correction, canonical, gold_status, final_gold, tmp_path / "out")
    score = next(csv.DictReader((tmp_path / "out" / "p1_geometry_task_scores_v1.csv").open(encoding="utf-8")))
    profile = next(csv.DictReader((tmp_path / "out" / "p1_worker_geometry_profile_v1.csv").open(encoding="utf-8")))

    assert score["geometry_metric_name"] == "equirectangular_layout_mask_iou"
    assert float(score["geometry_score_raw"]) == 1.0
    assert score["included_in_p1_geometry_profile"] == "true"
    assert score["geometry_score_task_percentile"] == ""
    assert profile["p1_geometry_support_status"] == "insufficient"
    assert summary["n_included_scores"] == 1


def test_geometry_score_invalid_geometry_is_retained_as_excluded_audit(tmp_path: Path) -> None:
    canonical = tmp_path / "canonical.csv"
    canonical_row = _canonical("a1", "w1", task_id="t1")
    canonical_row.update({"canonical_geometry": "not-json", "parse_error": "invalid_geometry"})
    _csv(canonical, list(canonical_row), [canonical_row])
    correction = tmp_path / "correction.csv"
    _csv(correction, ["worker_id", "project_id", "task_id", "base_task_id", "dataset_group", "condition", "annotation_id", "independence_status", "process_failure_observed"], [{"worker_id": "w1", "project_id": "p1", "task_id": "t1", "base_task_id": "base-t1", "dataset_group": "PreScreen_manual", "condition": "manual", "annotation_id": "a1", "independence_status": "independent", "process_failure_observed": "false"}])
    gold_status = tmp_path / "gold.csv"
    _csv(gold_status, ["task_id", "task_final_scope", "gold_status_for_alignment", "validation_status", "geometry_gold_task_id"], [{"task_id": "t1", "task_final_scope": "in_scope", "gold_status_for_alignment": "ready_for_alignment", "validation_status": "final_gold_geometry_checked", "geometry_gold_task_id": "task_id:g1"}])
    final_gold = tmp_path / "gold.jsonl"
    final_gold.write_text(json.dumps({"task_id": "g1", "runtime_pairs_1024x512": [{"x": 100, "y_ceiling": 100, "y_floor": 400}, {"x": 600, "y_ceiling": 100, "y_floor": 400}]}) + "\n", encoding="utf-8")

    materialize_scores(correction, canonical, gold_status, final_gold, tmp_path / "out")
    row = next(csv.DictReader((tmp_path / "out" / "p1_geometry_task_scores_v1.csv").open(encoding="utf-8")))
    assert row["geometry_score_raw"] == ""
    assert row["included_in_p1_geometry_profile"] == "false"
    assert "geometry_score_unavailable" in row["exclusion_reason"]


def test_geometry_score_with_fewer_than_four_vertical_pairs_is_audit_only(tmp_path: Path) -> None:
    canonical = tmp_path / "canonical.csv"
    canonical_row = _canonical("a1", "w1", task_id="t1")
    _csv(canonical, list(canonical_row), [canonical_row])
    correction = tmp_path / "correction.csv"
    _csv(correction, ["worker_id", "project_id", "task_id", "base_task_id", "dataset_group", "condition", "annotation_id", "independence_status", "process_failure_observed"], [{"worker_id": "w1", "project_id": "p1", "task_id": "t1", "base_task_id": "b1", "dataset_group": "PreScreen_manual", "condition": "manual", "annotation_id": "a1", "independence_status": "independent", "process_failure_observed": "false"}])
    gold = tmp_path / "gold.csv"
    _csv(gold, ["task_id", "task_final_scope", "geometry_reference_status", "geometry_gold_task_id"], [{"task_id": "t1", "task_final_scope": "in_scope", "geometry_reference_status": "expert_hard_single", "geometry_gold_task_id": "task_id:g1"}])
    final = tmp_path / "gold.jsonl"
    final.write_text(json.dumps({"task_id": "g1", "runtime_pairs_1024x512": [{"x": 100, "y_ceiling": 100, "y_floor": 400}, {"x": 600, "y_ceiling": 100, "y_floor": 400}]}) + "\n", encoding="utf-8")
    materialize_scores(correction, canonical, gold, final, tmp_path / "out")
    score = next(csv.DictReader((tmp_path / "out" / "p1_geometry_task_scores_v1.csv").open(encoding="utf-8")))
    assert score["geometry_score_gate_reason"] == "worker_geometry_insufficient_vertical_pairs"
    assert score["included_in_p1_geometry_profile"] == "false"


def test_geometry_hard_single_rejects_multiple_references(tmp_path: Path) -> None:
    canonical = tmp_path / "canonical.csv"
    row = _canonical("a1", "w1")
    _csv(canonical, list(row), [row])
    correction = tmp_path / "correction.csv"
    _csv(correction, ["worker_id", "project_id", "task_id", "base_task_id", "dataset_group", "condition", "annotation_id", "independence_status", "process_failure_observed"], [{"worker_id": "w1", "project_id": "p1", "task_id": "t1", "base_task_id": "base-t1", "dataset_group": "PreScreen_manual", "condition": "manual", "annotation_id": "a1", "independence_status": "independent", "process_failure_observed": "false"}])
    status = tmp_path / "status.csv"
    _csv(status, ["task_id", "task_final_scope", "geometry_reference_status", "geometry_gold_task_id"], [{"task_id": "t1", "task_final_scope": "in_scope", "geometry_reference_status": "expert_hard_single", "geometry_gold_task_id": "task_id:g1"}])
    reference = {"task_id": "g1", "record_id": "r1", "runtime_pairs_1024x512": [{"x": 102.4, "y_ceiling": 102.4, "y_floor": 409.6}, {"x": 614.4, "y_ceiling": 102.4, "y_floor": 409.6}]}
    reference_2 = {**reference, "record_id": "r2"}
    gold = tmp_path / "gold.jsonl"
    gold.write_text(json.dumps(reference) + "\n" + json.dumps(reference_2) + "\n", encoding="utf-8")
    materialize_scores(correction, canonical, status, gold, tmp_path / "out")
    scored = next(csv.DictReader((tmp_path / "out" / "p1_geometry_task_scores_v1.csv").open(encoding="utf-8")))
    assert scored["reference_count"] == "2"
    assert scored["reference_cardinality_valid"] == "false"
    assert scored["geometry_score_gate_reason"] == "hard_single_reference_cardinality_invalid"
    assert scored["geometry_score_raw"] == ""


def test_process_reliability_handles_all_failures_and_zero_denominator(tmp_path: Path) -> None:
    quality = tmp_path / "quality.csv"
    _csv(
        quality,
        ["round_id", "task_id", "base_task_id", "dataset_group", "condition", "worker_id", "geometry_valid", "assigned_expected", "active_time_source", "system_collection_issue", "active_time_integrity_status"],
        [{"round_id": "C1", "task_id": "system", "base_task_id": "b0", "dataset_group": "Calibration_core", "condition": "manual", "worker_id": "w1", "geometry_valid": "true", "assigned_expected": "true", "active_time_source": "missing", "system_collection_issue": "true", "active_time_integrity_status": "unknown_audit_only"}],
    )
    p1 = tmp_path / "all_failures.csv"
    p1_fields = ["worker_id", "task_id", "base_task_id", "dataset_group", "condition", "annotation_id", "independence_status", "process_evaluable", "process_failure_observed", "process_failure_subfamily", "active_time_source", "timing_evidence_status", "primary_active_time_eligible", "capability_evidence_eligible"]
    _csv(
        p1,
        p1_fields,
        [
            {"worker_id": "w1", "task_id": f"p{i}", "base_task_id": f"b{i}", "dataset_group": "PreScreen_manual", "condition": "manual", "annotation_id": f"a{i}", "independence_status": "non_independent_confirmed", "process_evaluable": "true", "process_failure_observed": "true", "process_failure_subfamily": "non_independent_submission", "active_time_source": "lead_time_fallback", "timing_evidence_status": "parent_derived_not_independent", "primary_active_time_eligible": "false", "capability_evidence_eligible": "false"}
            for i in range(57)
        ],
    )
    worker_state = tmp_path / "worker.csv"
    _csv(worker_state, ["worker_id"], [{"worker_id": "w1"}])

    materialize_sidecar(quality, worker_state, tmp_path / "all_fail_out", p1_task_evidence_csv=p1)
    all_fail = next(csv.DictReader((tmp_path / "all_fail_out" / "worker_profile_main_matrix_C1.csv").open(encoding="utf-8")))
    assert all_fail["n_process_support"] == "57"
    assert all_fail["process_reliability"] == "0.000000"

    materialize_sidecar(quality, worker_state, tmp_path / "zero_out")
    zero = next(csv.DictReader((tmp_path / "zero_out" / "worker_profile_main_matrix_C1.csv").open(encoding="utf-8")))
    assert zero["n_process_support"] == "0"
    assert zero["process_reliability"] == ""


def test_confirmed_copy_stays_process_family_and_suppresses_capability_predictive_checks(tmp_path: Path) -> None:
    quality = tmp_path / "quality.csv"
    _csv(
        quality,
        ["round_id", "task_id", "base_task_id", "dataset_group", "condition", "worker_id", "geometry_valid", "used_for_r_u", "assigned_expected", "active_time_source", "family", "subfamily", "response_type"],
        [{"round_id": "C1", "task_id": "c1", "base_task_id": "b1", "dataset_group": "Calibration_anchor", "condition": "manual", "worker_id": "w1", "geometry_valid": "true", "used_for_r_u": "true", "assigned_expected": "true", "active_time_source": "lead_time_fallback", "family": "geometry_quality_failure", "subfamily": "normal_geometry_degraded", "response_type": "geometry_ok"}],
    )
    p1 = tmp_path / "correction.csv"
    _csv(
        p1,
        ["worker_id", "task_id", "base_task_id", "dataset_group", "condition", "annotation_id", "independence_status", "process_evaluable", "process_failure_observed", "process_failure_subfamily", "included_in_r_geometry", "included_in_r_scope", "included_in_T_u", "included_in_U_u", "included_in_p1_predictive_capability", "active_time_source", "primary_active_time_eligible", "capability_evidence_eligible"],
        [{"worker_id": "w1", "task_id": "p1", "base_task_id": "pb1", "dataset_group": "PreScreen_manual", "condition": "manual", "annotation_id": "pa1", "independence_status": "non_independent_confirmed", "process_evaluable": "true", "process_failure_observed": "true", "process_failure_subfamily": "non_independent_submission", "included_in_r_geometry": "false", "included_in_r_scope": "false", "included_in_T_u": "false", "included_in_U_u": "false", "included_in_p1_predictive_capability": "false", "active_time_source": "lead_time_fallback", "primary_active_time_eligible": "false", "capability_evidence_eligible": "false"}],
    )
    status = tmp_path / "status.csv"
    _csv(status, ["worker_id", "p1_capability_evidence_status", "p1_predictive_capability_eligible", "p1_process_warning"], [{"worker_id": "w1", "p1_capability_evidence_status": "invalid_non_independent_submission", "p1_predictive_capability_eligible": "false", "p1_process_warning": "true"}])
    p1_profile = tmp_path / "p1_profile.csv"
    _csv(p1_profile, ["worker_id", "p1_geometry_profile", "p1_process_warning"], [{"worker_id": "w1", "p1_geometry_profile": "0.8", "p1_process_warning": "true"}])
    worker_state = tmp_path / "worker.csv"
    _csv(worker_state, ["worker_id"], [{"worker_id": "w1"}])

    materialize_sidecar(quality, worker_state, tmp_path / "out", [p1_profile], p1, status)
    evidence = list(csv.DictReader((tmp_path / "out" / "worker_task_evidence_table_C1.csv").open(encoding="utf-8")))
    copy_row = next(row for row in evidence if row["task_id"] == "p1" and row["family"] == "process_failure")
    assert copy_row["family"] == "process_failure"
    assert copy_row["subfamily"] == "non_independent_submission"
    assert copy_row["included_in_r_geometry"] == "false"
    assert copy_row["included_in_process_reliability"] == "true"
    subfamily = next(row for row in csv.DictReader((tmp_path / "out" / "worker_subfamily_response_C1.csv").open(encoding="utf-8")) if row["subfamily"] == "non_independent_submission")
    assert subfamily["n_observed"] == "1"
    assert subfamily["n_fail"] == "1"
    assert subfamily["failure_rate"] == "1.000000"

    predictive = {row["check_name"]: row for row in csv.DictReader((tmp_path / "out" / "p1_to_c1_predictive_validity.csv").open(encoding="utf-8"))}
    assert predictive["p1_geometry_vs_c1_geometry"]["support_status"] == "not_evaluable"
    assert predictive["p1_scope_vs_c1_scope"]["support_status"] == "not_evaluable"
    assert predictive["p1_process_warning_vs_c1_process_reliability"]["support_status"] != "not_evaluable"


def test_primary_timing_summary_excludes_fallback_from_primary_coverage(tmp_path: Path) -> None:
    fields = ["round_id", "task_id", "base_task_id", "dataset_group", "condition", "worker_id", "canonical_annotation_id", "geometry_valid", "assigned_expected", "active_time_source", "active_time_integrity_status", "primary_active_time_eligible", "lead_time_seconds"]
    rows = []
    for i in range(57):
        fallback = i == 56
        rows.append({"round_id": "P1", "task_id": f"t{i}", "base_task_id": f"b{i}", "dataset_group": "PreScreen_manual", "condition": "manual", "worker_id": "w1", "canonical_annotation_id": f"a{i}", "geometry_valid": "true", "assigned_expected": "true", "active_time_source": "lead_time_fallback" if fallback else "log", "active_time_integrity_status": "missing" if fallback else "exact_annotation_valid", "primary_active_time_eligible": "false" if fallback else "true", "lead_time_seconds": "30" if fallback else ""})
    quality = tmp_path / "quality.csv"
    _csv(quality, fields, rows)
    worker_state = tmp_path / "worker.csv"
    _csv(worker_state, ["worker_id"], [{"worker_id": "w1"}])

    materialize_sidecar(quality, worker_state, tmp_path / "out")
    main = next(csv.DictReader((tmp_path / "out" / "worker_profile_main_matrix_C1.csv").open(encoding="utf-8")))
    assert main["n_total_tasks"] == "57"
    assert main["n_primary_active_time_tasks"] == "56"
    assert main["n_fallback_tasks"] == "1"
    assert main["primary_active_time_coverage"] == f"{56 / 57:.6f}"
    assert main["fallback_only_flag"] == "false"
