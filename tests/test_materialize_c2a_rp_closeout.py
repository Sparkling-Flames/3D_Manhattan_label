from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

import tools.thesis_main.analysis.materialize_c2a_rp_closeout as c2a_closeout
from tools.thesis_main.analysis.materialize_c2a_rp_closeout import materialize
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
    blocks: int,
    assignments: list[dict[str, str]],
    submissions: list[dict[str, str]],
    profile_status: str = "completed",
    history: list[dict[str, str]] | None = None,
    terminal_rows: list[dict[str, str]] | None = None,
    legacy_schema: bool = False,
    reference_review_closed: bool = True,
) -> tuple[Path, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    threshold = tmp_path / "threshold.json"
    threshold.write_text(json.dumps({
        "status": "approved", "formal_selection_allowed": True,
        "thresholds": {"risk_slope_ci_half_width": 0.15},
        "derivation": {"formula_ids": {"risk_slope_ci_half_width": "normal_95_max_unified_slope_sd"}},
    }), encoding="utf-8")
    threshold_sha = sha256_file(threshold)
    csv_schema = load_method_contract()["c2"]["c2_a_rp_csv_schema"]
    precision_schema = "c2a_rp_precision_plan_v1" if legacy_schema else csv_schema["precision_plan"]
    assignment_schema = "c2a_rp_assignment_manifest_v1" if legacy_schema else csv_schema["assignment_manifest"]
    plan = _csv(tmp_path / "precision_plan.csv", [
        "schema_version", "worker_id", "additional_blocks", "ordinary_tasks", "stress_tasks",
        "precision_target_met", "routing_eligibility", "unmet_reason", "target_component", "gap_reason", "formal_goal", "interval_level",
        "target_ci_half_width", "ci_method", "threshold_manifest_sha256",
    ], [{
        "schema_version": precision_schema, "worker_id": "w1", "additional_blocks": str(blocks), "ordinary_tasks": str(blocks),
        "stress_tasks": str(blocks), "precision_target_met": "false" if blocks else "true",
        "routing_eligibility": "uncertain_fallback_global" if blocks else "eligible",
        "unmet_reason": "target_not_met_at_frozen_cap" if blocks else "",
        "target_component": "risk_slope", "gap_reason": "target_not_met" if blocks else "target_already_met", "formal_goal": "risk_slope_precision",
        "target_ci_half_width": "0.15", "interval_level": "0.95", "ci_method": "normal_95_max_unified_slope_sd",
        "threshold_manifest_sha256": threshold_sha,
    }])
    assignment = _csv(tmp_path / "assignment.csv", ["schema_version", "worker_id", "task_id", "base_task_id", "task_stratum", "block_index", "target_component", "gap_reason", "formal_goal", "task_support_after"], [
        {"schema_version": assignment_schema, "target_component": "risk_slope", "gap_reason": "target_not_met", "formal_goal": "risk_slope_precision", **row, "block_index": row.get("block_index", "1")} for row in assignments
    ])
    history_path = _csv(tmp_path / "history.csv", ["worker_id", "task_id", "base_task_id"], history or [])
    submission = _csv(tmp_path / "submissions.csv", ["worker_id", "task_id"], submissions)
    profile = _csv(tmp_path / "profile.csv", ["worker_id", "profile_version", "cohort_id", "completion_status"], [{
        "worker_id": "w1", "profile_version": "p1", "cohort_id": "c1", "completion_status": profile_status,
    }])
    c2b = tmp_path / "c2b.json"
    c2b_payload = {
        "schema_version": "c2b_closeout_v2", "artifact_role": "C2B_BATCH_A_CLOSEOUT_FROZEN",
        "contract_role": "generated_subordinate", "formal_ready": True, "c2b_closeout_ready": True,
        "method_contract_version": load_method_contract()["contract_version"],
        "method_contract_sha256": sha256_file(METHOD_CONTRACT), "profile_version": "p1", "cohort_id": "c1",
        "worker_summaries": [{"worker_id": "w1"}],
    }
    if reference_review_closed:
        c2b_payload.update({"reference_conflict_review_closed": True, "reference_conflict_review_record_sha256": "r" * 64})
    c2b.write_text(json.dumps(c2b_payload), encoding="utf-8")
    terminal = None
    if terminal_rows is not None:
        terminal = _csv(tmp_path / "terminal.csv", ["worker_id", "task_id", "terminal_status", "missing_reason"], terminal_rows)
    output = tmp_path / "closeout.json"
    materialize(plan, assignment, history_path, submission, profile, c2b, output, terminal_disposition_csv=terminal, threshold_manifest=threshold)
    return output, profile


def test_zero_task_c2a_rp_closeout_is_formal(tmp_path: Path) -> None:
    output, _ = _case(tmp_path, blocks=0, assignments=[], submissions=[])
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "c2a_rp_closeout_v2"
    assert payload["artifact_role"] == "C2A_RP_CLOSEOUT_FROZEN"
    assert payload["formal_ready"] is True
    assert payload["n_workers_assigned"] == 0
    assert payload["n_assignments"] == 0
    assert payload["closure_reason"] == "all_precision_targets_met_or_unsupported_adjustments_fallback"
    assert payload["C2_A_RP_CLOSED"] is True


def test_c2a_rp_closeout_rejects_legacy_csv_schema(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="CSV schema is stale"):
        _case(tmp_path, blocks=0, assignments=[], submissions=[], legacy_schema=True)


def test_c2a_rp_requires_closed_reference_review(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="closed reference conflict review"):
        _case(tmp_path, blocks=0, assignments=[], submissions=[], reference_review_closed=False)


def test_partial_c2a_rp_missing_with_profile_terminal_status_closes(tmp_path: Path) -> None:
    output, _ = _case(
        tmp_path, blocks=1,
        assignments=[
            {"worker_id": "w1", "task_id": "o1", "base_task_id": "o1", "task_stratum": "ordinary", "task_support_after": "1"},
            {"worker_id": "w1", "task_id": "s1", "base_task_id": "s1", "task_stratum": "stress", "task_support_after": "1"},
        ],
        submissions=[{"worker_id": "w1", "task_id": "o1"}],
        profile_status="closed_partial_usable",
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["C2_A_RP_CLOSED"] is True
    assert payload["n_workers_completed"] == 0
    assert payload["n_workers_partial"] == 1
    assert payload["n_missing"] == 1


def test_c2a_rp_missing_without_terminal_disposition_fails(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="terminal disposition"):
        _case(
            tmp_path, blocks=1,
            assignments=[
                {"worker_id": "w1", "task_id": "o1", "base_task_id": "o1", "task_stratum": "ordinary", "task_support_after": "1"},
                {"worker_id": "w1", "task_id": "s1", "base_task_id": "s1", "task_stratum": "stress", "task_support_after": "1"},
            ],
            submissions=[], profile_status="in_progress",
        )


def test_c2a_rp_rejects_orphan_terminal_disposition(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown worker"):
        _case(
            tmp_path, blocks=1,
            assignments=[
                {"worker_id": "w1", "task_id": "o1", "base_task_id": "o1", "task_stratum": "ordinary", "task_support_after": "1"},
                {"worker_id": "w1", "task_id": "s1", "base_task_id": "s1", "task_stratum": "stress", "task_support_after": "1"},
            ],
            submissions=[], profile_status="in_progress",
            terminal_rows=[{"worker_id": "w2", "task_id": "", "terminal_status": "nonstarter", "missing_reason": "wrong_worker"}],
        )


def test_c2a_rp_rejects_six_tasks_and_support_over_cap(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="normative cap"):
        _case(tmp_path / "six", blocks=3, assignments=[], submissions=[])

    case = tmp_path / "support"
    case.mkdir()
    with pytest.raises(ValueError, match="support"):
        _case(
            case, blocks=1,
            assignments=[
                {"worker_id": "w1", "task_id": "new", "base_task_id": "new", "task_stratum": "ordinary", "task_support_after": "3"},
                {"worker_id": "w1", "task_id": "stress", "base_task_id": "stress", "task_stratum": "stress", "task_support_after": "1"},
            ],
            submissions=[], profile_status="closed_partial_usable",
            history=[
                {"worker_id": "w2", "task_id": "new", "base_task_id": "old-1"},
                {"worker_id": "w3", "task_id": "new", "base_task_id": "old-2"},
            ],
        )


def test_c2a_rp_refits_each_block_and_counts_only_observed_eligible_support(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    threshold = tmp_path / "threshold.json"
    threshold.write_text(json.dumps({
        "status": "approved", "formal_selection_allowed": True,
        "thresholds": {"risk_slope_ci_half_width": 0.15},
        "derivation": {"formula_ids": {"risk_slope_ci_half_width": "normal_95_max_unified_slope_sd"}},
    }), encoding="utf-8")
    threshold_sha = sha256_file(threshold)
    csv_schema = load_method_contract()["c2"]["c2_a_rp_csv_schema"]
    plan = _csv(tmp_path / "plan.csv", [
        "schema_version", "worker_id", "additional_blocks", "ordinary_tasks", "stress_tasks", "precision_target_met",
        "routing_eligibility", "target_component", "gap_reason", "formal_goal", "interval_level", "target_ci_half_width", "ci_method",
        "threshold_manifest_sha256", "declared_support_after",
    ], [
        {"schema_version": csv_schema["precision_plan"], "worker_id": "w1", "additional_blocks": "2", "ordinary_tasks": "2", "stress_tasks": "2", "precision_target_met": "false", "routing_eligibility": "pending_actual_reestimate", "target_component": "risk_slope", "gap_reason": "target_not_met", "formal_goal": "risk_slope_precision", "interval_level": "0.95", "target_ci_half_width": "0.15", "ci_method": "normal_95_max_unified_slope_sd", "threshold_manifest_sha256": threshold_sha, "declared_support_after": "6"},
        {"schema_version": csv_schema["precision_plan"], "worker_id": "w2", "additional_blocks": "1", "ordinary_tasks": "1", "stress_tasks": "1", "precision_target_met": "false", "routing_eligibility": "pending_actual_reestimate", "target_component": "risk_slope", "gap_reason": "target_not_met", "formal_goal": "risk_slope_precision", "interval_level": "0.95", "target_ci_half_width": "0.15", "ci_method": "normal_95_max_unified_slope_sd", "threshold_manifest_sha256": threshold_sha, "declared_support_after": "3"},
    ])
    assignments = _csv(tmp_path / "assignment.csv", ["schema_version", "worker_id", "task_id", "base_task_id", "task_stratum", "block_index", "target_component", "gap_reason", "formal_goal", "task_support_after"], [
        {"schema_version": csv_schema["assignment_manifest"], "worker_id": "w1", "task_id": "o1", "base_task_id": "o1", "task_stratum": "ordinary", "block_index": "1", "target_component": "risk_slope", "gap_reason": "target_not_met", "formal_goal": "risk_slope_precision", "task_support_after": "1"},
        {"schema_version": csv_schema["assignment_manifest"], "worker_id": "w1", "task_id": "s1", "base_task_id": "s1", "task_stratum": "stress", "block_index": "1", "target_component": "risk_slope", "gap_reason": "target_not_met", "formal_goal": "risk_slope_precision", "task_support_after": "1"},
        {"schema_version": csv_schema["assignment_manifest"], "worker_id": "w1", "task_id": "o2", "base_task_id": "o2", "task_stratum": "ordinary", "block_index": "2", "target_component": "risk_slope", "gap_reason": "target_not_met", "formal_goal": "risk_slope_precision", "task_support_after": "1"},
        {"schema_version": csv_schema["assignment_manifest"], "worker_id": "w1", "task_id": "s2", "base_task_id": "s2", "task_stratum": "stress", "block_index": "2", "target_component": "risk_slope", "gap_reason": "target_not_met", "formal_goal": "risk_slope_precision", "task_support_after": "1"},
        {"schema_version": csv_schema["assignment_manifest"], "worker_id": "w2", "task_id": "o3", "base_task_id": "o3", "task_stratum": "ordinary", "block_index": "1", "target_component": "risk_slope", "gap_reason": "target_not_met", "formal_goal": "risk_slope_precision", "task_support_after": "1"},
        {"schema_version": csv_schema["assignment_manifest"], "worker_id": "w2", "task_id": "s3", "base_task_id": "s3", "task_stratum": "stress", "block_index": "1", "target_component": "risk_slope", "gap_reason": "target_not_met", "formal_goal": "risk_slope_precision", "task_support_after": "1"},
    ])
    history = _csv(tmp_path / "history.csv", ["worker_id", "task_id", "base_task_id"], [])
    submissions = _csv(tmp_path / "submissions.csv", ["worker_id", "task_id"], [
        {"worker_id": "w1", "task_id": task} for task in ("o1", "s1", "o2", "s2")
    ] + [{"worker_id": "w2", "task_id": "o3"}])
    profiles = _csv(tmp_path / "profile.csv", ["worker_id", "profile_version", "cohort_id", "completion_status", "risk_slope_ci_half_width", "risk_slope_support"], [
        {"worker_id": "w1", "profile_version": "p1", "cohort_id": "c1", "completion_status": "completed", "risk_slope_ci_half_width": "0.3", "risk_slope_support": "2"},
        {"worker_id": "w2", "profile_version": "p1", "cohort_id": "c1", "completion_status": "closed_partial_usable", "risk_slope_ci_half_width": "0.3", "risk_slope_support": "1"},
    ])
    c2b = tmp_path / "c2b.json"
    c2b.write_text(json.dumps({
        "schema_version": "c2b_closeout_v2", "artifact_role": "C2B_BATCH_A_CLOSEOUT_FROZEN",
        "contract_role": "generated_subordinate", "formal_ready": True, "c2b_closeout_ready": True,
        "reference_conflict_review_closed": True, "reference_conflict_review_record_sha256": "r" * 64,
        "method_contract_version": load_method_contract()["contract_version"], "method_contract_sha256": sha256_file(METHOD_CONTRACT),
        "profile_version": "p1", "cohort_id": "c1", "worker_summaries": [{"worker_id": "w1"}, {"worker_id": "w2"}],
    }), encoding="utf-8")
    terminal = _csv(tmp_path / "terminal.csv", ["worker_id", "task_id", "terminal_status", "missing_reason"], [{
        "worker_id": "w2", "task_id": "s3", "terminal_status": "closed_partial_usable", "missing_reason": "worker_absent",
    }])
    evidence = _csv(tmp_path / "risk_evidence.csv", [
        "worker_id", "canonical_annotation_id", "task_id", "base_task_id", "building_id", "risk_design_score_A", "Q_GT_raw",
        "formal_assignment_eligible", "routing_feature_analysis_eligible", "canonical_valid", "task_stratum",
    ], [
        {"worker_id": "w1", "canonical_annotation_id": "a0", "task_id": "p1", "base_task_id": "p1", "building_id": "b1", "risk_design_score_A": "0", "Q_GT_raw": "0.8", "formal_assignment_eligible": "true", "routing_feature_analysis_eligible": "true", "canonical_valid": "true", "task_stratum": "ordinary"},
        {"worker_id": "w1", "canonical_annotation_id": "a1", "task_id": "p2", "base_task_id": "p2", "building_id": "b2", "risk_design_score_A": "1", "Q_GT_raw": "0.7", "formal_assignment_eligible": "true", "routing_feature_analysis_eligible": "true", "canonical_valid": "true", "task_stratum": "stress"},
        *[{"worker_id": "w1", "canonical_annotation_id": f"{task}-ann", "task_id": task, "base_task_id": task, "building_id": f"b-{task}", "risk_design_score_A": "0.5", "Q_GT_raw": "0.75", "formal_assignment_eligible": "true", "routing_feature_analysis_eligible": "true", "canonical_valid": "true", "task_stratum": "ordinary" if task.startswith("o") else "stress"} for task in ("o1", "s1", "o2", "s2")],
        {"worker_id": "w1", "canonical_annotation_id": "invalid-ann", "task_id": "invalid", "base_task_id": "invalid", "building_id": "b-invalid", "risk_design_score_A": "0.5", "Q_GT_raw": "0.5", "formal_assignment_eligible": "true", "routing_feature_analysis_eligible": "true", "canonical_valid": "false", "task_stratum": "ordinary"},
        {"worker_id": "w2", "canonical_annotation_id": "w2-old", "task_id": "p3", "base_task_id": "p3", "building_id": "b3", "risk_design_score_A": "0", "Q_GT_raw": "0.8", "formal_assignment_eligible": "true", "routing_feature_analysis_eligible": "true", "canonical_valid": "true", "task_stratum": "ordinary"},
        {"worker_id": "w2", "canonical_annotation_id": "w2-o3", "task_id": "o3", "base_task_id": "o3", "building_id": "b-o3", "risk_design_score_A": "0.5", "Q_GT_raw": "0.75", "formal_assignment_eligible": "true", "routing_feature_analysis_eligible": "true", "canonical_valid": "true", "task_stratum": "ordinary"},
        {"worker_id": "w2", "canonical_annotation_id": "w2-s3", "task_id": "s3", "base_task_id": "s3", "building_id": "b-s3", "risk_design_score_A": "0.5", "Q_GT_raw": "0.75", "formal_assignment_eligible": "true", "routing_feature_analysis_eligible": "true", "canonical_valid": "true", "task_stratum": "stress"},
    ])
    calls: list[list[dict[str, object]]] = []

    def fake_fit(records: list[dict[str, object]]) -> dict[str, dict[str, object]]:
        calls.append(records)
        return {"1": {"estimate": 0.1, "se": 0.02, "ci_half_width": 0.04, "support": sum(row["worker_id"] == "1" for row in records), "model_status": "estimated"}}

    monkeypatch.setattr(c2a_closeout, "_actual_worker_slope", fake_fit)
    output = tmp_path / "closeout.json"
    materialize(plan, assignments, history, submissions, profiles, c2b, output, terminal_disposition_csv=terminal, risk_slope_evidence_csv=evidence, threshold_manifest=threshold)
    payload = json.loads(output.read_text(encoding="utf-8"))
    outcomes = {row["worker_id"]: row for row in payload["worker_outcomes"]}
    assert outcomes["1"]["terminal_state"] == "target_met"
    assert outcomes["1"]["observed_support_after"] == 6
    assert outcomes["2"]["observed_support_after"] == 2
    assert outcomes["2"]["terminal_state"] == "not_evaluable"
    assert len(outcomes["1"]["reestimate_history"]) == 2
    assert len(calls) == 2
    assert all("invalid" not in {row["task_id"] for row in records} and "s3" not in {row["task_id"] for row in records} for records in calls)
