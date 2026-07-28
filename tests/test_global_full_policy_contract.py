import pytest

from tools.thesis_main.analysis.materialize_global_policy import build_global_policy
from tools.thesis_main.analysis.materialize_full_policy import build_full_policy


def _manifest(status="candidate"):
    return {"status": status, "interpretation_allowed": status == "approved", "approved_by": "x" if status == "approved" else "", "approved_at": "now" if status == "approved" else "", "thresholds": {"minimum_GT_support": 1, "minimum_task_support": 1, "minimum_building_support": 1, "quality_floor": 0, "maximum_structural_failure_eb": .5, "require_process_eligible": True, "require_independence_eligible": True, "frozen_random_seed": 1}}


def _workers():
    return [{"worker_id": "w1", "Q_GT_EB": .8, "Q_GT_EB_LCB": .7, "Q_GT_task_adjusted_FE": .79, "Q_GT_support": 3, "task_support": 3, "building_support": 2, "process_eligible": True, "independence_eligible": True}, {"worker_id": "w2", "Q_GT_EB": .6, "Q_GT_EB_LCB": .5, "Q_GT_task_adjusted_FE": .61, "Q_GT_support": 3, "task_support": 3, "building_support": 2, "process_eligible": True, "independence_eligible": True}]


def test_candidate_manifest_cannot_materialize_formal_global():
    with pytest.raises(ValueError): build_global_policy(_workers(), _manifest(), formal=True)


def test_full_has_at_most_risk_and_one_family_adjustment():
    global_rows = build_global_policy(_workers(), _manifest("approved"), formal=True)
    global_rows[0].update(risk_activation_status="supported", risk_adjustment=.1)
    full = build_full_policy(global_rows, {"calibration_support": True, "activated_failure_family": "undercoverage"}, [
        {"worker_id": "w1", "component_family": "undercoverage", "component_status": "cross_stage_supported", "adjustment": .2},
        {"worker_id": "w2", "component_family": "undercoverage", "component_status": "cross_stage_supported", "adjustment": 0},
    ])
    assert full[0]["S_F"] == pytest.approx(full[0]["S_G"] + .3)


def test_global_uses_lcb_and_numeric_support_and_recurrent_failure_gate():
    rows = _workers()
    rows[0].update(process_eligible="", process_support="2", independence_eligible="", independence_support="1")
    rows[1]["serious_recurrent_failure_flag"] = "true"
    output = build_global_policy(rows, _manifest("approved"), formal=True)
    assert output[0]["S_G"] == pytest.approx(.7)
    assert output[0]["global_policy_eligible"] is True
    assert output[1]["global_exclusion_reason"] == "serious_recurrent_failure"


def test_full_false_support_and_unstable_endpoint_fall_back_global():
    global_rows = build_global_policy(_workers(), _manifest("approved"), formal=True)
    components = [
        {"worker_id": "w1", "component_family": "undercoverage", "component_status": "cross_stage_supported", "adjustment": .1, "adjustment_lower": -.4, "adjustment_upper": .4},
        {"worker_id": "w2", "component_family": "undercoverage", "component_status": "cross_stage_supported", "adjustment": 0, "adjustment_lower": -.4, "adjustment_upper": .4},
    ]
    unsupported = build_full_policy(global_rows, {"calibration_support": "false", "activated_failure_family": "undercoverage"}, components)
    assert all(row["full_fallback_global"] for row in unsupported)
    unstable = build_full_policy(global_rows, {"calibration_support": "true", "activated_failure_family": "undercoverage"}, components)
    assert all(row["full_exclusion_reason"] == "ranking_unstable_endpoint" for row in unstable)


def test_full_caps_adjustment_and_formal_requires_bound_manifests():
    global_rows = build_global_policy(_workers(), _manifest("approved"), formal=True)
    components = [
        {"worker_id": "w1", "component_family": "undercoverage", "component_status": "cross_stage_supported", "adjustment": .8},
        {"worker_id": "w2", "component_family": "undercoverage", "component_status": "cross_stage_supported", "adjustment": 0},
    ]
    policy = {"symmetric_adjustment_cap": .2, "allowed_p1_families": ["undercoverage"]}
    rows = build_full_policy(global_rows, {"calibration_support": "true", "activated_failure_family": "undercoverage"}, components, policy_manifest=policy)
    assert rows[0]["raw_adjustment"] == pytest.approx(.8)
    assert rows[0]["capped_adjustment"] == pytest.approx(.2)
    with pytest.raises(ValueError):
        build_full_policy(global_rows, {"calibration_support": "true", "activated_failure_family": "undercoverage"}, components, formal=True)
