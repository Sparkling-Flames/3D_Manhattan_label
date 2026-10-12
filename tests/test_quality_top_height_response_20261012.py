import math
from pathlib import Path

import pytest

from tools.thesis_main.analysis.quality_top_height_response_20261012 import (
    analytic_case, evaluate, profile_moments, read_json, response_terms, summarize_changes, validate_development_gates,
)


def config(power=2, representation="relative", top_weight=0, flat=False):
    return dict(power=power, representation=representation, global_scale=.5,
                top_weight=top_weight, flat=flat)


def test_fourth_power_crosses_at_inherited_scale_and_keeps_local_loss():
    for ratio, expected in ((1.2, "higher"), (1.5, "same"), (2, "lower")):
        m = analytic_case(ratio, .1)["metrics"]
        a, b = response_terms(m, config()), response_terms(m, config(4))
        assert a["local_height_loss"] == b["local_height_loss"] == pytest.approx(.16)
        if expected == "same":
            assert a["score"] == pytest.approx(b["score"])
        elif expected == "higher":
            assert b["score"] > a["score"]
        else:
            assert b["score"] < a["score"]


def test_log_is_reciprocal_but_has_different_physical_crossover():
    half, twice = (analytic_case(r, 0)["metrics"] for r in (.5, 2))
    assert response_terms(half, config(4, "log"))["score"] == pytest.approx(response_terms(twice, config(4, "log"))["score"])
    assert response_terms(analytic_case(math.exp(.5), 0)["metrics"], config(4, "log"))["global_height_loss"] == pytest.approx(1)
    assert response_terms(analytic_case(1.5, 0)["metrics"], config(4))["global_height_loss"] == pytest.approx(1)
    del half["height_mean_ratio"]
    with pytest.raises(KeyError):
        response_terms(half, config(4, "log"))


def test_top_and_flat_guards_retain_actual_and_neutral_penalties():
    m = analytic_case(1.2, .1)["metrics"]
    m.update(iou_2d=.6, dir=5, S_bottom_deg=4, S_top_deg=8, flat=2)
    a = response_terms(m, config(4, top_weight=1/16, flat=True))
    loss = .4**4 + .4**2 + .125
    assert a["score"] == pytest.approx(60 * .9625 / (2 + loss))
    assert a["top_only_penalty"] == pytest.approx(1 - .9625 / (1 + loss))
    assert a["actual_top_height_score_drop"] == pytest.approx(30 - a["score"])


def test_exact_profile_control_preserves_mean_and_local_shape_and_domain():
    case = analytic_case(.7, .1)
    m = profile_moments(case["annotation"])
    assert m["mean"] == pytest.approx(2.4 * .7)
    assert m["std"] == pytest.approx(2.4 * .1)
    assert case["camera_inside_height_assumption"]
    assert not analytic_case(.5, .1)["camera_inside_height_assumption"]
    # Same physical edge split with a redundant midpoint must preserve moments.
    split = {k: [v[0], [(x+y)/2 for x,y in zip(v[0],v[1])], *v[1:]] for k,v in case["annotation"].items()}
    assert profile_moments(split)["mean"] == pytest.approx(m["mean"])
    assert profile_moments(split)["std"] == pytest.approx(m["std"])


def test_exposure_and_missing_gate_cannot_enter_development():
    rows = [{"record_id": "a"}]
    gates = [{"record_id": "a", "new_descriptive_development_allowed": True, "explicit_exposure_barriers": []}]
    validate_development_gates(rows, gates)
    with pytest.raises(ValueError):
        validate_development_gates(rows, [])
    gates[0]["explicit_exposure_barriers"] = ["holdout"]
    with pytest.raises(ValueError):
        validate_development_gates(rows, gates)


def test_descriptive_change_counts_are_not_labels_or_independent_images():
    rows = [dict(id="a", image_id="i", building_id="b", scores={"x": 10, "y": 16}),
            dict(id="c", image_id="i", building_id="b", scores={"x": 20, "y": 17})]
    result = summarize_changes(rows, "x", "y")
    assert result["records"] == 2 and result["images"] == result["buildings"] == 1
    assert result["increase_ge_5"] == 1 and result["decrease_ge_2"] == 1
    assert result["quality_improvement_claimed"] is False


def test_frozen_study_preserves_domains_missingness_and_parity():
    root = Path(__file__).resolve().parents[1] / "research/quality_top_height_response_20261012"
    out = evaluate(read_json(root / "inputs.json"), read_json(root / "protocol.json"))
    assert out["verification"]["saved_development_scalar_cells"] == 4535
    assert out["verification"]["max_scalar_delta"] < 1e-10
    assert max(out["verification"]["geometry_max_deltas"].values()) < 1e-12
    assert sum(c["status"] != "available" for c in out["inherited_controls"]) == 1
    assert sum(c["metadata"].get("camera_inside_height_assumption") == "False" for c in out["inherited_controls"]) == 4
    assert len(out["analytic_controls"]) == 70
    assert sum(c["camera_inside_height_assumption"] for c in out["analytic_controls"]) == 65
    assert all(not c["angular_terms_evaluated"] and c["human_grade"] is None for c in out["analytic_controls"])
    assert all("relative4_weakTop" not in c["terms"] for c in out["analytic_controls"])
    assert len(out["reviewed_development_overlap_ids"]) == 30
    assert out["strata"]["confirmed"]["records"] == 143
    assert out["strata"]["unknown"]["records"] == 764
    assert all(s["relative_global_above_crossover"] == s["log_global_above_crossover"] == 0 for s in out["strata"].values())
    assert all(c["human_grade"] is None for c in out["selected_real_cases"])
    assert all(p["numeric_tolerance"] is None for p in out["overall_pairs"])
