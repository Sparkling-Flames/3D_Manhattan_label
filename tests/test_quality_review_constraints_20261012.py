import math
from pathlib import Path

import pytest

from tools.thesis_main.analysis.quality_review_constraints_20261012 import (
    components,
    audit,
    local_scale_boundary,
    periodic_pair,
    read_json,
)


def metrics(**changes):
    return dict(iou_2d=1, dir=0, flat=0, Hmean=0, Hcenter=0,
                S_top_deg=0, S_bottom_deg=0, height_mean_ratio=1, **changes)


def config(**changes):
    result = dict(direction_mode="bounded_denominator", direction_cap=1,
                  direction_scale_deg=5, flat_mode="none", height_mean_scale=.5,
                  height_center_scale=.25, height_combine="sum", top_weight=0,
                  top_combine="sum")
    result.update(changes)
    return result


def test_independent_height_errors_sum_and_max_differ():
    row = metrics()
    row.update(Hmean=.2, Hcenter=.1)
    result = components(row, config())
    assert result["score"] == pytest.approx(100 / 1.32)
    assert result["top_only_penalty"] == pytest.approx(1 - 1 / 1.32)
    assert components(row, config(height_combine="max"))["score"] == pytest.approx(100 / 1.16)


def test_top_only_penalty_does_not_inherit_better_floor_credit():
    a, b = metrics(), metrics()
    a.update(Hmean=.25)
    b.update(iou_2d=.5, Hcenter=.1, dir=10, S_bottom_deg=2)
    ca, cb = components(a, config()), components(b, config())
    assert ca["score"] > cb["score"]
    assert ca["top_only_penalty"] > cb["top_only_penalty"]


def test_flatness_counterfactual_preserves_additive_old_direction_discount():
    row = metrics()
    row.update(dir=5, flat=2, Hmean=.2)
    actual = components(row, config(direction_mode="old_numerator", flat_mode="old_numerator"))
    assert actual["score"] == pytest.approx(100 * .925 / 1.16)
    assert actual["score_without_top_height"] == pytest.approx(100 * .9625)
    assert actual["top_only_penalty"] == pytest.approx(1 - .9625 / 1.16)


def test_conditional_local_scale_boundary_and_weak_top():
    a, b = metrics(), metrics()
    a.update(Hmean=.2, S_top_deg=4)
    b.update(Hmean=.1, Hcenter=.1, S_top_deg=2)
    bound = local_scale_boundary(a, b, .5, 0)
    assert bound == pytest.approx(math.sqrt(.01 / .12))
    equal = config(height_center_scale=bound)
    assert components(a, equal)["top_only_penalty"] == pytest.approx(components(b, equal)["top_only_penalty"])
    assert components(b, config(height_center_scale=bound * .9))["top_only_penalty"] > components(a, config(height_center_scale=bound * .9))["top_only_penalty"]
    assert local_scale_boundary(a, b, .5, 1 / 16) < bound


def test_log_height_requires_actual_ratio_and_respects_reciprocal_ratio():
    a, b = metrics(), metrics()
    a["height_mean_ratio"], b["height_mean_ratio"] = .5, 2
    cfg = config(height_mean_representation="absolute_log_ratio")
    assert components(a, cfg)["score"] == pytest.approx(components(b, cfg)["score"])
    del a["height_mean_ratio"]
    with pytest.raises(KeyError):
        components(a, cfg)


def test_periodic_pair_can_hide_residual_without_changing_midpoint():
    a = periodic_pair(1018, 6)
    b = periodic_pair(0, 0)
    assert a["shared_x"] == b["shared_x"] == 0
    assert a["gap_px"] == 12
    assert a["gap_deg"] == pytest.approx(12 * 360 / 1024)
    assert b["gap_px"] == 0


def test_received_feedback_scope_and_missing_geometry_survive_audit():
    root = Path(__file__).resolve().parents[1]
    evidence = read_json(root / "research/quality_review_constraints_20261012/evidence.json")
    result = audit(evidence)
    assert result["unique_real_records_in_scalar_pool"] == 45
    assert sum(p["scalar_cells"] for p in result["parity"]) == 3721
    assert sum(len(p["unavailable"]) for p in result["parity"]) == 1
    for pair in result["overall_pairs"]:
        if pair["panel"] in ("C01", "C02", "C04"):
            assert pair["numeric_close_tolerance"] is None
            assert not pair["close_pass_fail_assigned"]
            assert all(score["strict_preference_agrees"] is None for score in pair["scores"])
    assert result["P05"]["input_quality_grade"] is None
    assert not result["P05"]["automatic_pairing_repair"]
    assert result["P05"]["largest_gap_pair"]["source_point_indices_zero_based"] == [9, 10]
    assert result["P05"]["largest_gap_pair"]["gap_px"] == pytest.approx(17.43653250774014)
