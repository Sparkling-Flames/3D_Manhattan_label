import copy

import numpy as np
import pytest

from tools.thesis_main.analysis.layout_foundation_20260930 import synthetic_record
from tools.thesis_main.analysis.layout_3d_quality_probe_20261002 import (
    prepare_record, height_stats, diagnostics, compare, restore_initial,
)


SQUARE = np.array([[-2., -2.], [2., -2.], [2., 2.], [-2., 2.]])


def test_height_integrals_ignore_collinear_sampling():
    heights = np.array([2., 3., 4., 3.])
    a = height_stats(SQUARE, heights)
    assert a['mean_h'] == pytest.approx(3)
    assert a['rms_h'] == pytest.approx(np.sqrt(1/3))
    p = np.insert(SQUARE, 1, (SQUARE[0]+SQUARE[1])/2, axis=0)
    h = np.insert(heights, 1, 2.5)
    assert height_stats(p, h) == pytest.approx(a)
    assert height_stats(p[::-1], h[::-1]) == pytest.approx(a)


def test_default_order_preserves_preprocessed_pairs_and_confirmed_ring():
    r = dict(synthetic_record(SQUARE), ring_confirmed=False,
             source_pair_indices=[0, 1, 2, 3], source_point_indices=list(range(8)),
             source_point_labels=list('abcdefgh'))
    original = copy.deepcopy(r)
    result = prepare_record(r)
    assert np.all(np.diff(np.array(result['points'])[::2, 0]) >= 0)
    assert r == original
    for j, i in enumerate(result['source_pair_indices']):
        assert result['points'][2*j:2*j+2] == r['points'][2*i:2*i+2]
    r['ring_confirmed'] = True
    assert prepare_record(r)['points'] == r['points']
    r['version'] = 'original'; r['ring_confirmed'] = False
    assert prepare_record(r)['points'] == r['points']


def test_volume_height_and_zero_residual_are_different():
    a = synthetic_record(SQUARE, 2.)
    b = synthetic_record(SQUARE, 3.)
    m = compare(a, b)
    assert m['bev']['bev_range_iou'] == pytest.approx(1)
    assert m['model_volume']['iou'] == pytest.approx(2/3)
    assert m['model_volume']['height_signed_h'] == pytest.approx(-1)
    c = synthetic_record(SQUARE*2, 2.)
    n = compare(a, c)
    assert n['model_volume']['iou'] == pytest.approx(n['bev']['bev_range_iou'])
    assert diagnostics(a)['direction_self']['rms_deg'] < 1e-5
    assert diagnostics(c)['direction_self']['rms_deg'] < 1e-5


def test_missing_and_invalid_stay_unavailable():
    a = synthetic_record(SQUARE)
    assert compare(a, None)['reason'] == 'reference_version_absent'
    a['points'][0][1] = -1
    assert diagnostics(a)['status'] == 'unavailable'
    assert compare(a, synthetic_record(SQUARE))['model_volume']['iou'] is None


def test_nonflat_top_and_horizon_failure_are_not_fitted_away():
    a = synthetic_record(SQUARE, [2., 3., 4., 3.])
    d = diagnostics(a)
    assert d['height']['rms_h'] == pytest.approx(np.sqrt(1/3))
    assert d['heights'] == pytest.approx([2., 3., 4., 3.])
    b = copy.deepcopy(a)
    b['points'][1][1] = 256.
    assert diagnostics(b)['status'] == 'unavailable'
    assert compare(b, a)['model_volume']['iou'] is None


def test_initial_binding_maps_labels_not_array_positions():
    import json
    source = dict(preprocessed_points=[[1, 1], [1, 3], [2, 1], [2, 3], [3, 1], [3, 3]],
                  point_labels=['a','b','c','d','e','f'], links_zero_based=[[0,1],[2,3],[4,5]])
    binding = dict(labels=['c','d','a','b','e','f'], links=[[0,1],[2,3],[4,5]])
    source['order_record'] = dict(binding=json.dumps(binding))
    result = restore_initial(source, {'initial_order':'[0,1,2]', 'final_order':'[1,0,2]'}, [0,1,2])
    assert result['source_pair_indices'] == [1,0,2]
    with pytest.raises(ValueError, match='final_ring_binding_mismatch'):
        restore_initial(source, {'initial_order':'[0,1,2]', 'final_order':'[1,0,2]'}, [1,0,2])
