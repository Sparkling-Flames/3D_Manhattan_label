import math
from copy import deepcopy
from pathlib import Path

import pytest

from tools.thesis_main.analysis.quality_top_height_response_20261012 import analytic_case, profile_moments, read_json
from tools.thesis_main.analysis.quality_height_conditioning_20261012 import (
    clearance_diagnostics, coordinate_key, perturb_bottom, run,
)


def test_clearance_is_a_rescaling_not_an_independent_error():
    d = clearance_diagnostics(1.6, 2.)
    assert d["wall_ratio"] == pytest.approx(.8)
    assert d["clearance_ratio"] == pytest.approx(.6)
    assert d["signed_clearance_error"] == pytest.approx(d["signed_wall_error"] * d["normalization_multiplier"])
    assert d["normalization_multiplier"] == 2


def test_nonpositive_reference_clearance_is_not_zero_error():
    d = clearance_diagnostics(1.2, 1.)
    assert d["clearance_ratio"] is None
    assert d["clearance_status"] == "nonpositive_reference_clearance"
    assert d["wall_ratio"] == 1.2


def test_bottom_perturbation_preserves_top_rays_and_is_reversible():
    g = analytic_case(1, .05)["annotation"]
    before = deepcopy(g)
    out = perturb_bottom(g, [0], -1, 512)
    assert g == before
    assert out["status"] == "available"
    changed = out["geometry"]
    scale = changed["top3d"][0][0] / g["top3d"][0][0]
    assert changed["top3d"][0] == pytest.approx([v*scale for v in g["top3d"][0]])
    assert changed["bottom3d"][0][1] == -1
    assert changed["top3d"][1:] == g["top3d"][1:]
    restored = perturb_bottom(changed,[0],1,512)["geometry"]
    for key in g:
        for a,b in zip(restored[key],g[key]): assert a == pytest.approx(b)


def test_horizon_crossing_is_reported_and_never_clamped():
    g = analytic_case(1,0)["annotation"]
    radial_scale = (1/math.tan(1.5*math.pi/512))/math.sqrt(2)
    for key in g:
        for p in g[key]:
            p[0] *= radial_scale
            p[2] *= radial_scale
    out = perturb_bottom(g,[0],-2,512)
    assert out["status"] == "out_of_projection_domain"
    assert "geometry" not in out


def test_coherent_bottom_shift_can_change_mean_without_moving_top_pixels():
    g = analytic_case(1,0)["annotation"]
    after = perturb_bottom(g,range(4),1,512)["geometry"]
    scale = (1/math.tan(math.atan2(1,math.sqrt(2))+math.pi/512))/math.sqrt(2)
    p = profile_moments(after)
    assert p["mean"] == pytest.approx(1+1.4*scale)
    assert p["std"] == pytest.approx(0,abs=1e-14)


def test_exact_coordinate_group_keeps_reference_and_order_distinct():
    g = analytic_case(1,0)["annotation"]
    r = dict(image_id="i",reference_object_id="g")
    assert coordinate_key(r,g) == coordinate_key(r,deepcopy(g))
    assert coordinate_key(r,g) != coordinate_key(dict(r,reference_object_id="other"),g)
    rotated = {k:v[1:]+v[:1] for k,v in g.items()}
    assert coordinate_key(r,g) != coordinate_key(r,rotated)


def test_frozen_diagnostic_preserves_denominators_and_separate_review_pool():
    root = Path(__file__).resolve().parents[1] / "research/quality_top_height_response_20261012"
    result = run(read_json(root/"inputs.json"),read_json(root/"results.json"),read_json(root/"conditioning_design.json"))
    assert result["strata"]["all"]["records"] == 907
    assert result["strata"]["all"]["coordinate_groups"] == 739
    assert result["strata"]["confirmed"]["coordinate_groups"] == 114
    assert result["strata"]["all"]["coordinate_group_statistics"]["St_dominant_count"] == 364
    assert result["strata"]["confirmed"]["coordinate_group_statistics"]["St_dominant_count"] == 50
    assert {r["id"] for r in result["review_mean_diagnostics"]} == {"R00397","R00418"}
    assert "R00418" not in {r["id"] for r in result["records"]}
    assert result["scope"]["perturbed_scores_computed"] is False
    assert result["verification"]["unique_coordinate_scenarios"] == 8188
    assert result["verification"]["unavailable_unique_scenarios"] == 0
    assert result["verification"]["maximum_top_unit_ray_change"] < 1e-12
    assert all(r["human_grade"] is None for r in result["selected_cases"])
