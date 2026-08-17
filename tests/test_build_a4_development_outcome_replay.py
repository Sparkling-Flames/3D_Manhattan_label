import math

import pytest

from tools.thesis_main.analysis.build_a4_development_outcome_replay import (
    classify_effect_band,
    common_pair_eligibility,
    delivery_adjusted_quality,
    direction_gate,
    choose_lobo_variant,
    conflict_pool_sets,
    validate_action_keyset,
    validate_preoutcome_spec,
    validate_quality_building,
    validate_development_split,
)


def test_common_denominator_is_intersection_and_missing_is_not_zero():
    assert common_pair_eligibility(
        {"selected": True, "gt_primary_analysis_eligible": True, "iou_to_gt": "0.8"},
        {"selected": True, "gt_primary_analysis_eligible": True, "iou_to_gt": "0.7"},
    ) == (True, "paired_public_gt_primary")
    assert common_pair_eligibility(
        {"selected": True, "gt_primary_analysis_eligible": True, "iou_to_gt": ""},
        {"selected": True, "gt_primary_analysis_eligible": True, "iou_to_gt": "0.7"},
    ) == (False, "quality_value_missing")
    assert delivery_adjusted_quality({"structurally_valid": False, "worker_caused_structural_failure": False, "iou_to_gt": "0"}) is None


def test_worker_attributable_invalid_is_the_only_invalid_zero():
    assert delivery_adjusted_quality({"structurally_valid": False, "worker_caused_structural_failure": True, "iou_to_gt": ""}) == 0.0
    assert delivery_adjusted_quality({"structurally_valid": True, "worker_caused_structural_failure": False, "iou_to_gt": "0.42"}) == 0.42


def test_effect_bands_and_direction_boundaries_are_fixed():
    assert classify_effect_band(0.010999999) == "no_go"
    assert classify_effect_band(0.011) == "conditional"
    assert classify_effect_band(0.015) == "strong_go"
    assert direction_gate([0.0, 0.1, 0.2, 0.0, 0.3, 0.4, 0.5, 0.6, 0.7]) == (True, "direction_gate_pass")
    assert direction_gate([0.0] * 8 + [None]) == (False, "missing_building")
    assert math.isclose(0.015, 0.015, rel_tol=0.0, abs_tol=1e-12)


def test_lobo_tie_is_deterministically_a4_s():
    assert choose_lobo_variant({"A4-S": 0.2, "A4-C": 0.2, "A4-L": 0.2}) == "A4-S"
    assert choose_lobo_variant({"A4-S": 0.1, "A4-C": 0.2, "A4-L": 0.2}) == "A4-C"


def test_a4_c_l_cannot_upgrade_a4_s_decision():
    from tools.thesis_main.analysis.build_a4_development_outcome_replay import build_decision

    decision = build_decision(0.010, [0.1] * 9, {"A4-C": 0.5, "A4-L": 0.6})
    assert decision["a4_s_classification"] == "no_go"
    assert decision["overall_decision"] == "no_go"


def test_split_rejects_locked_candidates_and_wrong_manifest():
    development = [{"building_scene_id": str(i), "split": "development"} for i in range(9)]
    development += [{"building_scene_id": str(i), "split": "internal_holdout"} for i in range(9, 13)]
    assert validate_development_split(development, set(range(9))) == (set(map(str, range(9))), set(map(str, range(9, 13))))
    with pytest.raises(RuntimeError):
        validate_development_split(development[:-1], set(range(9)))
    with pytest.raises(RuntimeError):
        validate_development_split(development, set(range(13)))


def test_conflict_pool_audit_separates_all_hits_from_paired_exclusions():
    state = [
        {"deployment_pool_id": "public_conflict", "base_task_id": "x"},
        {"deployment_pool_id": "nonpublic_conflict", "base_task_id": "x"},
        {"deployment_pool_id": "clean", "base_task_id": "y"},
    ]
    all_hits, paired_exclusions = conflict_pool_sets(state, {"x"}, {"public_conflict", "clean"})
    assert all_hits == {"public_conflict", "nonpublic_conflict"}
    assert paired_exclusions == {"public_conflict"}


def test_action_keyset_rejects_extra_pool_or_variant():
    state = {"p1", "p2"}
    actions = [(pool, variant) for pool in state for variant in ("A0", "A4-S", "A4-C", "A4-L")]
    validate_action_keyset(state, actions)
    with pytest.raises(RuntimeError):
        validate_action_keyset(state, actions + [("locked", "A4-S")])


def test_preoutcome_spec_gate_mismatch_fails_closed():
    spec = {
        "development_replay": {"buildings": "9 development buildings only"},
        "future_effect_gates_not_evaluated": {
            "strong_go_delta": ">=0.015", "conditional_delta": "0.011<=delta<0.015", "no_go_delta": "<0.011",
            "effect_sensitivity_only": "0.020", "direction_gate": "at least 6/9 buildings non-negative and at least 5/9 strictly positive",
            "selection_rule": "no max-observed selection; outer LOBO only; ties A4-S; A4-S retained as primary safety estimate",
        },
        "variants": {"A4-S": "median of four; median cluster score; ties support then formal medoid; fallback A0"},
    }
    validate_preoutcome_spec(spec, 9)
    spec["future_effect_gates_not_evaluated"]["strong_go_delta"] = ">=0.020"
    with pytest.raises(RuntimeError):
        validate_preoutcome_spec(spec, 9)


def test_quality_building_binding_fails_closed():
    validate_quality_building({"building_id": "b1"}, "b1")
    with pytest.raises(RuntimeError):
        validate_quality_building({"building_id": "locked"}, "b1")
