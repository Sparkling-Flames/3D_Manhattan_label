from copy import deepcopy
from pathlib import Path

import pytest

from tools.thesis_main.analysis.quality_top_height_response_20261012 import profile_moments, read_json
from tools.thesis_main.analysis.quality_local_profile_20261012 import (
    make_controls, exact_same_floor_centered, centered_distance, support_fraction, flattened_reference, run,
)


def test_controls_hold_floor_mean_rms_and_keep_raw_inputs_separate():
    cases = make_controls([.04,.1,.18],[.05,.1])
    floor = cases[0]['annotation']['bottom3d']
    assert len(cases) == 24
    for c in cases:
        a,g = c['annotation'],c['reference']
        assert a['bottom3d'] == g['bottom3d'] == floor
        assert a['bottom3d'] is not g['bottom3d']
        p = profile_moments(a)
        assert p['mean'] == pytest.approx(2.4)
        assert p['std']/2.4 == pytest.approx(c['target_rms'])
        for b,t in zip(a['bottom3d'],a['top3d']):
            assert (b[0],b[2]) == (t[0],t[2])
            assert t[1] > 0


def test_flat_reference_rms_equal_but_peak_and_support_change():
    cases = [c for c in make_controls([.04,.18],[.1]) if c['reference_type']=='flat' and c['location']=='near']
    for c in cases:
        assert exact_same_floor_centered(c['annotation'],c['reference']) == pytest.approx(.1)
    peaks = [max(abs(h-2.4) for h in profile_moments(c['annotation'])['heights'])/2.4 for c in cases]
    assert peaks[0] > peaks[1]
    assert support_fraction(cases[0]['annotation'],2.4,.2) != pytest.approx(support_fraction(cases[1]['annotation'],2.4,.2))


def test_nonflat_reference_identifies_location_mismatch_despite_equal_moments():
    cases = [c for c in make_controls([.1],[.1]) if c['reference_type']=='nonflat_near']
    near,far = cases
    assert exact_same_floor_centered(near['annotation'],near['reference']) == pytest.approx(0,abs=1e-14)
    assert exact_same_floor_centered(far['annotation'],far['reference']) > .1
    assert profile_moments(far['annotation'])['std'] == pytest.approx(profile_moments(far['reference'])['std'])


def test_exact_residual_rejects_different_floor_and_numerical_match_is_nonmutating():
    c = make_controls([.1],[.1])[-1]
    before = deepcopy(c)
    actual = centered_distance(c['annotation'],c['reference'],4096)
    assert c == before
    assert actual == pytest.approx(exact_same_floor_centered(c['annotation'],c['reference']),abs=1e-6)
    c['annotation']['bottom3d'][0][0] += .1
    with pytest.raises(ValueError,match='same floor'):
        exact_same_floor_centered(c['annotation'],c['reference'])


def test_support_integrates_linear_crossings_instead_of_counting_vertices():
    c = make_controls([.1],[.1])[0]
    assert support_fraction(c['annotation'],2.4,0) == pytest.approx(1)
    assert support_fraction(c['annotation'],2.4,10) == 0
    # The largest deviation is positive; support above any higher threshold is zero.
    p = profile_moments(c['annotation'])
    peak=max(abs(h-p['mean']) for h in p['heights'])/2.4
    assert support_fraction(c['annotation'],2.4,peak+1e-12) == 0


def test_reference_flattening_is_a_copy_preserving_floor_and_mean():
    g=make_controls([.1],[.1])[-1]['reference']
    before=deepcopy(g)
    flat=flattened_reference(g)
    assert g==before
    assert flat['bottom3d']==g['bottom3d']
    assert profile_moments(flat)['mean']==pytest.approx(profile_moments(g)['mean'])
    assert profile_moments(flat)['std']==pytest.approx(0,abs=1e-14)


def test_frozen_height_replay_and_output_contract():
    study=Path(__file__).resolve().parents[1]/'research/quality_top_height_response_20261012'
    result=run(read_json(study/'inputs.json'),read_json(study/'local_profile_design.json'))
    assert result['schema']=='quality_local_profile_results_v1'
    assert len(result['records'])==907
    assert len(result['coordinate_groups'])==739
    assert len(result['controls'])==24
    assert result['verification']['maximum_frozen_Hcenter_error'] < 1e-9
    assert result['verification']['maximum_control_Hcenter_exact_error'] < 1e-5
    assert all(r['human_grade'] is None for r in result['selected_cases'])
    assert all(v is False for v in result['scope'].values())
