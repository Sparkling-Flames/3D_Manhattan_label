import copy

import numpy as np
import pytest

from tools.thesis_main.analysis.point_context_probe_20261006 import compare_context, threshold_sensitivity


def pairs(floor):
    """Constant-height wall pairs from a declared floor; exact collinear subdivision."""
    p = np.asarray(floor, float)
    x = (np.arctan2(p[:, 0], -p[:, 1])/(2*np.pi)+.5)*1024
    phi = np.arctan2(1, np.linalg.norm(p, axis=1))*512/np.pi
    return np.stack([np.c_[x, 256-phi], np.c_[x, 256+phi]], axis=1)


def test_cycle_reverse_and_seam_preserve_context_and_source():
    a = pairs([[-2,-2], [2,-2], [2,2], [-2,2]])
    before = copy.deepcopy(a)
    for b, j in [(a, 0), (a[::-1], 3), (np.roll(a, 1, axis=0), 1)]:
        row = compare_context(a, 0, b, j, 'pair')
        assert row['anchor_deg'] == pytest.approx(0, abs=1e-10)
        assert row['combined_deg'] == pytest.approx(0, abs=1e-10)
    shifted = a.copy(); shifted[:,:,0] = (shifted[:,:,0]+723.5)%1024
    assert compare_context(shifted, 0, shifted[::-1], 3, 'pair')['combined_deg'] < 1e-10
    assert np.array_equal(a, before)


def test_collinear_subdivision_can_hurt_neighbor_score_without_changing_corner():
    a = pairs([[-2,-2], [2,-2], [2,2], [-2,2]])
    b = pairs([[-2,-2], [0,-2], [2,-2], [2,2], [-2,2]])
    r = compare_context(a, 0, b, 0, 'pair')
    assert r['anchor_deg'] == pytest.approx(0, abs=1e-10)
    assert r['combined_deg'] > 10  # A known limitation, not a desired matcher behavior.


def test_endpoint_scope_and_orientation_ties_are_not_hidden():
    a = np.array([[[100.,120.],[100.,400.]]]*3)
    b = a.copy(); b[:,0,1] += 30
    assert compare_context(a, 0, b, 0, 'bottom')['combined_deg'] == pytest.approx(0)
    r = compare_context(a, 0, b, 0, 'top')
    assert r['combined_deg'] == pytest.approx(30*180/512)
    assert r['best_orientations'] == ['forward', 'reverse']


def test_threshold_intervals_include_positive_boundary_but_exclude_negative():
    rows = [dict(case_id='x', metric='pair', relation=rel, anchor_deg=a, combined_deg=b)
            for rel, a, b in [('same_corner', 4., 7.), ('different_corner', 5., 6.)]]
    result = threshold_sensitivity(rows)
    a, b = result
    assert a['development_separation_interval_deg'] == [4., 5.]
    assert b['development_separation_interval_deg'] is None
    at4 = next(r for r in a['intervals'] if r['lower_inclusive_deg'] == 4.)
    assert at4['positive_retained'] == 1 and at4['negative_admitted'] == 0
    assert all(x['development_separation_interval_deg'] is None for x in threshold_sensitivity(rows[:1]))
