from pathlib import Path

import pytest

from tools.thesis_main.analysis.run_topology_sequential_preflight import (
    FLAGS,
    LIVE_WORKERS,
    PRIMARY_METRICS,
    M2_STATUS,
    M3_STATUS,
    _order_signature,
    _result_row,
    _stable_order,
    attach_pair_metrics,
    _cluster,
    _topology_signature_from_structural,
    load_frozen_inputs,
    operating_rows,
    run_f0,
    run_m0,
    run_m1,
    summarize_rows,
    topology_status,
)


ROOT = Path(__file__).resolve().parents[1]


def _candidate(index, *, valid=True, quality=.8):
    return {
        "canonical_annotation_id": f"a{index}",
        "worker_id": index,
        "structurally_valid": valid,
        "structural_validation_status": "passed" if valid else "failed",
        "geometry_metric_evaluable": valid,
        "topology_signature": "n_pairs:4",
        "gt": {
            "quality_evaluable": True,
            "gt_primary_analysis_eligible": True,
            "iou_to_gt": quality,
        },
    }


def _cluster_with_support(records, largest, second, count):
    return {
        "task_crowd_structure_status": "unimodal" if count == 1 else "dominant_with_dissent" if second <= 1 else "supported_multimodal",
        "cluster_count": count,
        "largest_cluster_support": largest,
        "second_cluster_support": second,
        "largest_cluster_medoid_annotation_id": records[0]["canonical_annotation_id"],
    }


def test_frozen_denominator_live_filter_and_exhaustion_facts():
    data = load_frozen_inputs(ROOT)
    assert len(data["tasks"]) == 78
    assert LIVE_WORKERS == {1, 2, 6, 8, 10, 11, 12, 13, 15, 17, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37}
    assert {worker for rows in data["candidates"].values() for worker in (row["worker_id"] for row in rows)} <= LIVE_WORKERS
    assert {size: sum(len(rows) == size for rows in data["candidates"].values()) for size in (4, 5, 20)} == {4: 28, 5: 38, 20: 12}
    assert {size: sum(data["tasks"][task]["structural_candidate_count"] == size for task in data["tasks"]) for size in (4, 5, 20)} == {4: 30, 5: 36, 20: 12}
    assert data["reference_audit"]["gt_issue_declared"] is False
    assert data["reference_audit"]["n_pending_contexts"] == 0
    assert data["conflict_queue_rows"] == []
    assert sum(count for size, count in data["operational_distribution"].items() if size >= 5) == 47
    assert sum(count for size, count in data["operational_distribution"].items() if size < 5) == 31
    conflicts = [row for rows in data["candidates"].values() for row in rows if not row["geometry_metric_evaluable"]]
    assert len(conflicts) == 1
    assert conflicts[0]["canonical_annotation_id"] == "370095f69c5b170678fa"
    assert conflicts[0]["structurally_valid"] is True


def test_m0_topology_signature_does_not_require_gt_repaired_field():
    assert _topology_signature_from_structural({"repaired_point_count": "36"}, {}) == "n_pairs:18"


def test_normalized_geometry_reaches_real_cluster_prefixes_and_selected_outputs():
    data = load_frozen_inputs(ROOT)
    task_id = next(task for task in data["tasks"] if data["tasks"][task]["structural_candidate_count"] >= 5)
    order = _stable_order(data["candidates"][task_id], task_id, 0, 20260818)
    accepted = [row for row in order if row["structurally_valid"]]
    assert _cluster(accepted[:3], task_id)["valid_k"] == 3
    assert _cluster(accepted[:5], task_id)["valid_k"] == 5
    f0_selected = 0
    for replicate in range(5):
        permuted = _stable_order(data["candidates"][task_id], task_id, replicate, 20260818)
        f0_selected += run_f0(permuted, task_id)["selected"] is not None
    assert f0_selected > 0


def test_one_shared_permutation_for_all_policies():
    data = load_frozen_inputs(ROOT)
    task_id = next(iter(data["tasks"]))
    order = _stable_order(data["candidates"][task_id], task_id, 0, 20260818)
    assert _order_signature(order) == _order_signature(list(order))
    assert [row["canonical_annotation_id"] for row in run_m0(order, task_id)["order"]] == [row["canonical_annotation_id"] for row in run_m1(order, task_id)["order"]]


def test_task_equal_averages_replicates_within_task_first():
    tasks = {"a1": {"building_id": "b1"}, "a2": {"building_id": "b1"}, "b1": {"building_id": "b2"}}
    rows = []
    for task, values in {"a1": [3, 3], "a2": [3], "b1": [5]}.items():
        for replicate, value in enumerate(values):
            rows.append({
                "estimand_scope": "primary_common47", "policy": "M0_corner_count_gate_geometry_medoid",
                "base_task_id": task, "building_id": tasks[task]["building_id"],
                "mean_paid_valid_submissions": value, "mean_raw_paid_attempts": 9,
                "paid_valid_replicate_support": 1, "raw_attempt_replicate_support": 1,
                "replicate_support": 1,
            })
    metric = next(row for row in operating_rows(rows, tasks, 20260818) if row["policy"] == "M0_corner_count_gate_geometry_medoid" and row["metric"] == "conditional mean paid valid submissions on common valid-candidate support")
    assert metric["estimate"] == 11 / 3
    assert metric["task_support"] == 3
    paid = next(row for row in operating_rows(rows, tasks, 20260818) if row["policy"] == "M0_corner_count_gate_geometry_medoid" and row["metric"] == "conditional mean raw paid attempts on common valid-candidate support")
    assert paid["estimate"] == 9.0


def test_summary_outcomes_are_unconditional_and_historical_shortfall_is_not_prospective_exhaustion():
    statuses = ["stop@3", "stop@4", "cap_reached_output", "historical_counterfactual_support_shortfall"]
    rows = [{
        "base_task_id": "t", "building_id": "b", "policy": "M0_corner_count_gate_geometry_medoid", "order_signature": str(i), "candidate_permutation_n": 5,
        "status": status, "K_attempts": 3 if status == "stop@3" else 4 if status == "stop@4" else 5,
        "K_valid": 3 if status == "stop@3" else 4 if status == "stop@4" else 5 if status == "cap_reached_output" else 4,
        "invalid_attempts": 0, "replacement_attempts": 0, "metric_invalid_attempts": 0,
        "stop_at_3": status == "stop@3", "incremental_stop_at_4": status == "stop@4", "reach5": status == "cap_reached_output",
        "historical_counterfactual_support_shortfall": status == "historical_counterfactual_support_shortfall", "supported_multimodal_encountered": False,
        "selected_annotation_id": "a" if status != "historical_counterfactual_support_shortfall" else None,
        "public_gt_quality": None, "paired_quality_delta_vs_f0": None, "paid_valid_savings_vs_f0": None,
        "paid_submission_savings": None, "prefix_full5_selected_output_instability": None, "selected_structural_invalidity": None,
    } for i, status in enumerate(statuses)]
    summary = summarize_rows(rows, {"t": {"building_id": "b"}}, 4)[0]
    outcomes = [summary["stop_at_3_probability"], summary["incremental_stop_at_4_probability"], summary["reach5_probability"], summary["historical_counterfactual_support_shortfall_probability"]]
    assert outcomes == [0.25, 0.25, 0.25, 0.25]
    assert sum(outcomes) == 1.0
    assert "candidate exhaustion" not in {label for _, label, _, _ in PRIMARY_METRICS}


def test_m0_status_uses_only_topology_signature():
    records = [{"topology_signature": "n_pairs:4"}, {"topology_signature": "n_pairs:4"}, {"topology_signature": "n_pairs:5"}]
    assert topology_status(records)[0] == "dominant_with_dissent"
    assert topology_status(records)[1][0][0]["topology_signature"] == "n_pairs:4"


def test_m1_gate_stops_only_at_strict_k3_and_k4_patterns(monkeypatch):
    records = [_candidate(index) for index in range(1, 6)]

    monkeypatch.setattr(
        "tools.thesis_main.analysis.run_topology_sequential_preflight._cluster",
        lambda rows, task: _cluster_with_support(rows, 3, 0, 1),
    )
    assert run_m1(records, "task")["status"] == "stop@3"

    def stop_at_four(rows, task):
        return _cluster_with_support(rows, 2, 1, 2) if len(rows) == 3 else _cluster_with_support(rows, 3, 1, 2)

    monkeypatch.setattr("tools.thesis_main.analysis.run_topology_sequential_preflight._cluster", stop_at_four)
    result = run_m1(records, "task")
    assert result["stop_at_3"] is False
    assert result["status"] == "stop@4"


@pytest.mark.parametrize("largest,second,count", [(5, 0, 1), (4, 1, 2)])
def test_m1_gate_resolves_only_allowed_k5_patterns(monkeypatch, largest, second, count):
    records = [_candidate(index) for index in range(1, 6)]

    def cluster(rows, task):
        if len(rows) == 3:
            return _cluster_with_support(rows, 2, 1, 2)
        if len(rows) == 4:
            return _cluster_with_support(rows, 2, 1, 3)
        return _cluster_with_support(rows, largest, second, count)

    monkeypatch.setattr("tools.thesis_main.analysis.run_topology_sequential_preflight._cluster", cluster)
    result = run_m1(records, "task")
    assert result["stop_at_3"] is False
    assert result["incremental_stop_at_4"] is False
    assert result["K_valid"] == 5
    assert result["selected"] is not None


@pytest.mark.parametrize("largest,second,count", [(3, 2, 2), (3, 1, 3)])
def test_m1_gate_marks_remaining_k5_multimodality_unresolved(monkeypatch, largest, second, count):
    records = [_candidate(index) for index in range(1, 6)]

    def cluster(rows, task):
        if len(rows) == 3:
            return _cluster_with_support(rows, 2, 1, 2)
        if len(rows) == 4:
            return _cluster_with_support(rows, 2, 1, 3)
        return _cluster_with_support(rows, largest, second, count)

    monkeypatch.setattr("tools.thesis_main.analysis.run_topology_sequential_preflight._cluster", cluster)
    result = run_m1(records, "task")
    assert result["status"] == "unresolved_expert_escalation_required"
    assert result["selected"] is None
    row = _result_row({"base_task_id": "task", "building_id": "b"}, 0, "order", result)
    assert "policy_failure" not in row
    assert row["expert_escalation_required"] is True
    assert row["autonomous_non_delivery"] is True
    assert row["reference_evaluable_autonomous_delivery_quality"] == 0.0


def test_m0_corner_count_only_replaces_invalid_attempt(monkeypatch):
    records = [_candidate(0, valid=False)] + [_candidate(index) for index in range(1, 4)]
    monkeypatch.setattr(
        "tools.thesis_main.analysis.run_topology_sequential_preflight.topology_status",
        lambda rows: ("unimodal", [rows]),
    )
    monkeypatch.setattr("tools.thesis_main.analysis.run_topology_sequential_preflight._medoid", lambda rows: rows[0])
    result = run_m0(records, "task")
    assert result["policy"] == "M0_corner_count_gate_geometry_medoid"
    assert result["status"] == "stop@3"
    assert result["K_attempts"] == 4
    assert result["K_valid"] == 3
    assert result["invalid_attempts"] == 1
    assert result["replacement_attempts"] == 1
    row = _result_row({"base_task_id": "task", "building_id": "b"}, 0, "order", result)
    assert row["raw_paid_attempts"] == 4
    assert row["paid_valid_submissions"] == 3


def test_no_output_keeps_cost_and_enters_reference_evaluable_autonomous_mitt_as_zero():
    f0 = {
        "policy": "F0", "status": "fixed_k5", "paid_valid_submissions": 5,
        "raw_paid_attempts": 5, "selected_annotation_id": "full5",
        "public_gt_quality": .8, "reference_evaluable_autonomous_delivery_quality": .8,
    }
    unresolved = {
        "policy": "M1", "status": "unresolved_expert_escalation_required", "paid_valid_submissions": 5,
        "raw_paid_attempts": 5, "selected_annotation_id": None, "public_gt_quality": None,
        "reference_evaluable_autonomous_delivery_quality": 0.0,
    }
    attach_pair_metrics(unresolved, f0)
    assert unresolved["raw_paid_attempt_savings_vs_f0"] == 0
    assert unresolved["reference_evaluable_autonomous_delivery_quality"] == 0.0
    assert unresolved["reference_evaluable_autonomous_delivery_mitt_delta_vs_f0"] == pytest.approx(-.8)
    assert unresolved["paired_complete_case_quality_delta_vs_f0"] is None
    unresolved.update({
        "base_task_id": "task", "building_id": "b", "order_signature": "order",
        "candidate_permutation_n": 5, "stop_at_3": False, "incremental_stop_at_4": False,
        "reach5": True, "historical_counterfactual_support_shortfall": False,
        "unresolved": True, "invalid_attempts": 0, "replacement_attempts": 0,
        "autonomous_non_delivery": True, "expert_escalation_required": True,
        "metric_invalid_attempts": 0, "supported_multimodal_encountered": True,
        "selected_structural_invalidity": None, "prefix_full5_selected_output_instability": None,
    })
    summary = summarize_rows([unresolved], {"task": {"building_id": "b"}}, 1)[0]
    assert summary["paired_reference_evaluable_autonomous_delivery_replicate_support"] == 1
    assert summary["paired_complete_case_quality_replicate_support"] == 0

    f0_no_output = dict(f0, status="policy_failure_no_output", selected_annotation_id=None, public_gt_quality=None, reference_evaluable_autonomous_delivery_quality=0.0)
    resolved = dict(unresolved, status="stop@3", paid_valid_submissions=3, raw_paid_attempts=3, selected_annotation_id="prefix", public_gt_quality=.7, reference_evaluable_autonomous_delivery_quality=.7)
    attach_pair_metrics(resolved, f0_no_output)
    assert resolved["paid_valid_savings_vs_f0"] == 2
    assert resolved["raw_paid_attempt_savings_vs_f0"] == 2
    assert resolved["reference_evaluable_autonomous_delivery_mitt_delta_vs_f0"] == pytest.approx(.7)
    assert resolved["paired_complete_case_quality_delta_vs_f0"] is None


def test_primary_comparison_is_the_same_47_tasks_and_orders():
    data = load_frozen_inputs(ROOT)
    common = {
        task for task, rows in data["candidates"].items()
        if sum(row["structurally_valid"] and row["geometry_metric_evaluable"] for row in rows) >= 5
    }
    assert len(common) == 47
    for task in common:
        order = _stable_order(data["candidates"][task], task, 0, 20260818)
        results = [run_f0(order, task), run_m0(order, task), run_m1(order, task)]
        assert results[0]["K_valid"] == 5
        assert {_order_signature(result["order"]) for result in results} == {_order_signature(order)}
    summaries = [{
        "estimand_scope": "primary_common47" if task in common else "historical_support_all78",
        "policy": policy, "base_task_id": task, "building_id": data["tasks"][task]["building_id"],
        "paired_rows_status": "paired_same_order" if task in common else "historical_f0_support_shortfall",
        "mean_paid_valid_submissions": 5, "paid_valid_replicate_support": 1, "replicate_support": 1,
        "historical_counterfactual_support_shortfall_probability": 0 if task in common else 1,
    } for task in data["tasks"] for policy in ("F0", "M0_corner_count_gate_geometry_medoid", "M1")]
    primary = [
        row for row in operating_rows(summaries, data["tasks"], 20260818)
        if row["cohort"] == "primary_common47" and row["metric"] == "conditional mean paid valid submissions on common valid-candidate support"
    ]
    assert {row["policy"] for row in primary} == {"F0", "M0_corner_count_gate_geometry_medoid", "M1"}
    assert all(row["task_total"] == row["task_support"] == 47 for row in primary)


def test_rule_defined_zero_has_no_zero_width_bootstrap_interval():
    tasks = {"t": {"building_id": "b"}}
    rows = [{
        "estimand_scope": "primary_common47", "policy": "M1", "base_task_id": "t", "building_id": "b",
        "selected_structural_invalidity_probability": 0.0, "selected_structural_invalidity_replicate_support": 1,
        "replicate_support": 1,
    }]
    operating = operating_rows(rows, tasks, 20260818)
    metric = next(row for row in operating if row["policy"] == "M1" and row["metric"] == "selected structural invalidity")
    assert metric["status"] == "zero_by_admission_rule"
    assert metric["ci_low"] is None
    assert metric["ci_high"] is None
    workflow = [row for row in operating if row.get("policy") == "M1_with_expert_fallback"]
    assert {row["metric"] for row in workflow} == {"final delivery quality after expert fallback", "total deployment cost including expert fallback"}
    assert all(row["status"] == "not_identifiable" for row in workflow)


def test_missing_and_fail_closed_lanes_are_explicit():
    result = run_m1([], "missing-task")
    assert result["historical_counterfactual_support_shortfall"] is True
    assert result["K_valid"] == 0
    assert result["reach5"] is None
    assert M2_STATUS == "not_evaluated_leakage_safe_estimator_absent"
    assert M3_STATUS == "pending_pre_peer_timing_binding"
    assert FLAGS["block3"] is False
    assert FLAGS["formal_policy_frozen"] is False
    assert FLAGS["formal_profile_frozen"] is False
