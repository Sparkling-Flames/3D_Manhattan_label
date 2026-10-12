from copy import deepcopy
from pathlib import Path

import pytest

from tools.thesis_main.analysis.quality_top_height_response_20261012 import analytic_case, profile_moments, read_json
from tools.thesis_main.analysis.quality_top_residual_20261012 import align_mean, diagnose, make_controls, run


def test_global_translation_removed_without_mutating_inputs():
    c = analytic_case(.8, 0)
    before = deepcopy(c)
    d = diagnose(c['annotation'], c['reference'], 256)
    assert c == before
    assert d['original_deg'] > 1
    assert d['to_reference']['deg'] < 1e-10
    assert d['to_annotation']['deg'] < 1e-10
    a = align_mean(c['annotation'], profile_moments(c['reference'])['mean'])
    assert a['bottom3d'] == c['annotation']['bottom3d']
    assert profile_moments(a)['mean'] == pytest.approx(2.4)


def test_same_mean_local_profile_survives_alignment():
    c = analytic_case(1, .1)
    d = diagnose(c['annotation'], c['reference'], 256)
    assert d['original_deg'] > 1
    assert d['to_reference']['deg'] == pytest.approx(d['original_deg'])


def test_floor_error_is_not_pure_local_height_error():
    c = next(c for c in make_controls([2]) if c['family'] == 'floor_radial_20pct')
    d = diagnose(c['annotation'], c['reference'], 256)
    assert d['mean_delta'] == pytest.approx(0, abs=1e-12)
    assert profile_moments(c['annotation'])['std'] == pytest.approx(0, abs=1e-12)
    assert d['to_reference']['deg'] > 1


def test_controls_preserve_vertical_pairs_and_do_not_share_floor_storage():
    for c in make_controls([.5, 2, 10]):
        a, g = c['annotation'], c['reference']
        assert a['bottom3d'] is not g['bottom3d']
        for geo in (a, g):
            for b,t in zip(geo['bottom3d'],geo['top3d']):
                assert (b[0],b[2]) == pytest.approx((t[0],t[2]))
        if c['family'] == 'floor_radial_20pct':
            assert a['bottom3d'][0][0] / g['bottom3d'][0][0] == pytest.approx(1.2)


@pytest.mark.parametrize('family', ['floor_radial_and_cancelled_projection', 'fixed_top_all_bottom_plus1px'])
def test_alignment_can_create_residual_when_raw_top_matches(family):
    c = next(c for c in make_controls([2]) if c['family'] == family)
    d = diagnose(c['annotation'], c['reference'], 256)
    assert d['original_deg'] < 1e-10
    assert d['to_reference']['deg'] > .01
    assert d['change_deg'] > 0


def test_swap_exchanges_alignment_levels_and_domain_is_explicit():
    c = analytic_case(.8, .1)
    d = diagnose(c['annotation'], c['reference'], 256)
    swap = diagnose(c['reference'], c['annotation'], 256)
    assert d['to_reference']['deg'] == pytest.approx(swap['to_annotation']['deg'])
    bad = next(c for c in make_controls([2]) if c['family'] == 'alignment_out_of_camera_domain')
    out = diagnose(bad['annotation'], bad['reference'], 256)
    assert out['original_camera_domain'] is True
    assert out['to_reference']['status'] == 'out_of_camera_domain'
    assert out['to_reference']['deg'] is None
    assert out['to_reference']['minimum_top_y'] < 0


def test_frozen_run_replays_original_metric_and_preserves_research_boundary():
    study = Path(__file__).resolve().parents[1] / 'research/quality_top_height_response_20261012'
    out = run(read_json(study/'inputs.json'), read_json(study/'top_residual_design.json'))
    assert out['schema'] == 'quality_top_residual_results_v1'
    assert len(out['records']) == 907
    assert len(out['coordinate_groups']) == 739
    assert out['strata']['confirmed']['coordinate_group_statistics']['count'] == 114
    assert out['verification']['maximum_frozen_St_error'] < 1e-9
    assert len(out['controls']) == 28
    assert sum(c['diagnostic']['to_reference']['deg'] is None for c in out['controls']) == 1
    assert out['verification']['maximum_2048_8192_difference_deg'] < 1e-4
    assert all(r['human_grade'] is None for r in out['selected_cases'])
    assert all(v is False for v in out['scope'].values())
