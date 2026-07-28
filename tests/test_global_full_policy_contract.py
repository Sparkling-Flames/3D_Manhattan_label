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
    full = build_full_policy(global_rows, {"calibration_support": True, "activated_failure_family": "undercoverage"}, [{"worker_id": "w1", "component_family": "undercoverage", "component_status": "cross_stage_supported", "adjustment": .2}])
    assert full[0]["S_F"] == pytest.approx(full[0]["S_G"] + .3)
