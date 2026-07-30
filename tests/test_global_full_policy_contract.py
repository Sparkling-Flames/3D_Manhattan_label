import pytest

from tools.thesis_main.analysis.materialize_global_policy import build_global_policy
from tools.thesis_main.analysis.materialize_full_policy import build_full_policy


def _manifest(status="candidate"):
    return {"status": status, "interpretation_allowed": status == "approved", "approved_by": "x" if status == "approved" else "", "approved_at": "now" if status == "approved" else "", "thresholds": {"minimum_GT_support": 1, "minimum_task_support": 1, "minimum_building_support": 1, "quality_floor": 0, "maximum_structural_failure_eb": .5, "require_process_eligible": True, "require_independence_eligible": True, "frozen_random_seed": 1}}


def _workers():
    common = {"schema_version": "worker_profile_v2", "profile_version": "p", "cohort_id": "c", "enrollment_batch": "original", "administratively_eligible": True, "Q_GT_estimable": True, "reference_evaluable": True, "Q_GT_profile_status": "estimated", "R_peer_profile_status": "estimated", "peer_task_support": 5, "F_struct_profile_status": "estimated", "LOO_medoid_status": "estimated", "LOO_strict_status": "estimated", "global_policy_eligible": True, "c2_risk_model_eligible": True, "peer_tiebreak_eligible": True, "structural_gate_eligible": True, "F_struct_raw": 0, "F_struct_EB": 0, "F_struct_interval_lower": 0, "F_struct_interval_upper": .1, "R_peer_stable": .8, "R_LOO_medoid": .8, "process_eligible": True, "independence_eligible": True}
    return [{**common, "worker_id": "w1", "Q_GT_EB": .8, "Q_GT_EB_LCB": .7, "Q_GT_task_adjusted_FE": .79, "Q_GT_support": 3, "task_support": 3, "building_support": 2}, {**common, "worker_id": "w2", "Q_GT_EB": .6, "Q_GT_EB_LCB": .5, "Q_GT_task_adjusted_FE": .61, "Q_GT_support": 3, "task_support": 3, "building_support": 2}]


def test_candidate_manifest_cannot_materialize_formal_global():
    with pytest.raises(ValueError): build_global_policy(_workers(), _manifest(), formal=True)

    false_string = _manifest("approved")
    false_string["interpretation_allowed"] = "false"
    with pytest.raises(ValueError):
        build_global_policy(_workers(), false_string, formal=True)


def test_missing_formal_global_eligibility_fields_fail_closed():
    rows = _workers()
    del rows[0]["administratively_eligible"]
    with pytest.raises(ValueError, match="missing fields"):
        build_global_policy(rows, _manifest("approved"), formal=True)


def test_full_has_at_most_risk_and_one_family_adjustment():
    global_rows = build_global_policy(_workers(), _manifest("approved"), formal=True)
    global_rows[0].update(risk_activation_status="supported", risk_adjustment=.1)
    full = build_full_policy(global_rows, {"calibration_support": True, "activated_failure_family": "undercoverage"}, [
        {"worker_id": "w1", "component_family": "undercoverage", "component_status": "cross_stage_supported", "adjustment": .2},
        {"worker_id": "w2", "component_family": "undercoverage", "component_status": "cross_stage_supported", "adjustment": 0},
    ])
    assert full[0]["S_F"] == pytest.approx(full[0]["S_G"] + .3)


def test_global_freezes_z_from_qgt_eb_and_uses_lcb_only_as_quality_gate():
    rows = _workers()
    rows[1]["serious_recurrent_failure_flag"] = "true"
    output = build_global_policy(rows, _manifest("approved"), formal=True)
    assert output[0]["S_G"] == pytest.approx(.70710678)
    assert output[0]["S_G_z_center"] == pytest.approx(.7)
    assert output[0]["global_rank_S_G"] == 1
    assert output[0]["global_policy_eligible"] is True
    assert output[1]["global_exclusion_reason"] == "serious_recurrent_failure"


def test_global_fails_closed_for_insufficient_or_zero_variance_cohort():
    with pytest.raises(ValueError):
        build_global_policy([_workers()[0]], _manifest("approved"), formal=True)
    same = _workers()
    same[1]["Q_GT_EB"] = same[0]["Q_GT_EB"]
    with pytest.raises(ValueError):
        build_global_policy(same, _manifest("approved"), formal=True)


def test_global_skips_incomplete_peer_layer_for_entire_sg_tie_group():
    rows = _workers()
    rows[1]["Q_GT_EB"] = rows[0]["Q_GT_EB"]
    rows[1]["Q_GT_task_adjusted_FE"] = rows[0]["Q_GT_task_adjusted_FE"]
    rows[1]["R_peer_stable"] = None
    rows[1]["R_peer_profile_status"] = "not_evaluable"
    rows[0]["R_LOO_medoid"], rows[1]["R_LOO_medoid"] = .1, .9
    rows.append({**rows[0], "worker_id": "w3", "Q_GT_EB": .4, "Q_GT_EB_LCB": .3, "Q_GT_task_adjusted_FE": .4})
    output = build_global_policy(rows, _manifest("approved"), formal=True)
    ranks = {row["worker_id"]: row["global_rank_S_G"] for row in output}
    assert ranks["w2"] < ranks["w1"]


def test_full_false_support_and_unstable_endpoint_fall_back_global():
    global_rows = build_global_policy(_workers(), _manifest("approved"), formal=True)
    components = [
        {"worker_id": "w1", "component_family": "undercoverage", "component_status": "cross_stage_supported", "adjustment": .1, "adjustment_lower": -.8, "adjustment_upper": .8},
        {"worker_id": "w2", "component_family": "undercoverage", "component_status": "cross_stage_supported", "adjustment": 0, "adjustment_lower": -.8, "adjustment_upper": .8},
    ]
    unsupported = build_full_policy(global_rows, {"calibration_support": "false", "activated_failure_family": "undercoverage"}, components)
    assert all(row["full_fallback_global"] for row in unsupported)
    unstable = build_full_policy(global_rows, {"calibration_support": "true", "activated_failure_family": "undercoverage"}, components)
    assert all(row["full_exclusion_reason"] == "ranking_unstable_endpoint" for row in unstable)


def test_full_ambiguous_family_disables_only_family_component() -> None:
    global_rows = build_global_policy(_workers(), _manifest("approved"), formal=True)
    global_rows[0].update(risk_activation_status="supported", risk_adjustment=.1)
    global_rows[1].update(risk_activation_status="supported", risk_adjustment=0)
    output = build_full_policy(
        global_rows,
        {"calibration_support": True, "family_scores": {"undercoverage": .7, "topology": .65}},
        [],
    )
    assert output[0]["family_component_disabled"] is True
    assert output[0]["overall_global_fallback"] is False
    assert output[0]["risk_adjustment_applied"] == pytest.approx(.1)


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


def test_formal_full_requires_explicit_routing_contract_fields():
    global_rows = build_global_policy(_workers(), _manifest("approved"), formal=True)
    policy = {"status": "approved", "interpretation_allowed": True, "approved_by": "x", "approved_at": "now", "input_sha256": {"global_csv": "x", "task_json": "x", "components_csv": "x"}, "allowed_family_whitelist": ["undercoverage"], "allowed_component_weights": [1.0], "minimum_component_worker_support": 1, "minimum_component_task_support": 1, "symmetric_adjustment_cap": .2, "activation_threshold": .5, "activation_margin": .1}
    profile = {"status": "approved", "interpretation_allowed": True, "approved_by": "x", "approved_at": "now", "input_sha256": {"x": "x"}, "profile_version": "p1"}
    component = {"status": "approved", "interpretation_allowed": True, "approved_by": "x", "approved_at": "now", "input_sha256": {"x": "x"}, "required_component_fields": ["component_status", "full_component_eligible", "combined_effect", "worker_support", "task_support", "shrinkage", "weight", "profile_version", "adjustment_lower", "adjustment_upper"]}
    components = [{"worker_id": worker, "component_family": "undercoverage", "component_status": "cross_stage_supported", "full_component_eligible": "true", "combined_effect": 0, "worker_support": 1, "task_support": 1, "shrinkage": 1, "weight": 1.0, "profile_version": "p1", "adjustment": 0, "adjustment_lower": 0, "adjustment_upper": 0} for worker in ("w1", "w2")]
    task = {"calibration_support": True, "activated_failure_family": "undercoverage", "family_scores": {"undercoverage": .9, "other": .1}}
    result = build_full_policy(global_rows, task, components, policy_manifest=policy, profile_manifest=profile, component_manifest=component, formal=True)
    assert result[0]["S_F"] == pytest.approx(result[0]["S_G"])
    del policy["activation_margin"]
    with pytest.raises(ValueError, match="activation_margin"):
        build_full_policy(global_rows, task, components, policy_manifest=policy, profile_manifest=profile, component_manifest=component, formal=True)
