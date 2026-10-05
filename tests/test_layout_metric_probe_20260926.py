import json

import numpy as np
import pytest

from tools.thesis_main.analysis.layout_metric_probe_20260926 import (
    compare_regions, nearest_wall_mask, pairs_from_floor, polygon_metrics, run,
)
from tools.thesis_main.analysis.consensus_region_20260923 import wall_mask


def test_region_inputs_are_validated_before_boolean_conversion():
    binary = np.array([[0, 1], [1, 0]])
    assert compare_regions(binary, binary) == compare_regions(binary.astype(bool), binary.astype(bool))
    for value in (float('nan'), float('inf'), .2, -1):
        bad = binary.astype(float); bad[0, 0] = value
        for a, b in ((bad, binary), (binary, bad)):
            with pytest.raises(ValueError, match='binary_mask'):
                compare_regions(a, b)


def test_fixed_l_shape_order_counterexample_and_invalid_state():
    p = np.array([[-2, -2], [2, -2], [2, 0], [0, 0], [0, 2], [-2, 2]]) - [-1, 1.3]
    order = np.argsort(np.arctan2(p[:, 0], -p[:, 1]))
    m = polygon_metrics(p, p[order])
    assert m['status'] == 'ok'
    assert m['intersection_area'] == pytest.approx(8)
    assert m['iou'] == pytest.approx(4 / 7)
    assert m['volume_iou'] == pytest.approx(4 / 7)
    pairs = pairs_from_floor(p)
    assert np.array_equal(wall_mask(pairs), wall_mask(pairs[order]))
    assert not np.array_equal(nearest_wall_mask(p), nearest_wall_mask(p[order]))
    bad = polygon_metrics([[-1, -1], [1, 1], [1, -1], [-1, 1]], p)
    assert bad['status'] == 'invalid_a' and bad['iou'] is None


def test_known_rectangle_area_height_and_representation_invariance():
    p = np.array([[-2, -2], [2, -2], [2, 2], [-2, 2]])
    q = np.array([[-4, -1], [4, -1], [4, 1], [-4, 1]])
    m = polygon_metrics(p, q)
    assert m['iou'] == pytest.approx(1 / 3)
    assert m['centroid_distance'] == pytest.approx(0)
    assert m['boundary_mean_distance'] > 0
    assert polygon_metrics(p, p, height_a=2, height_b=3)['volume_iou'] == pytest.approx(2 / 3)
    theta = ((np.arange(512)+.5)/512-.5)*2*np.pi
    exact_range = 2/np.maximum(np.abs(np.sin(theta)), np.abs(np.cos(theta)))
    latitude = np.pi*(.5-(np.arange(256)+.5)/256)
    exact_mask = ((latitude[:, None] >= -np.arctan2(1., exact_range)) &
                  (latitude[:, None] <= np.arctan2(1.7, exact_range)))
    assert np.array_equal(nearest_wall_mask(p), exact_mask)
    for changed in (np.roll(p, 2, axis=0), p[::-1], np.insert(p, 1, [0, -2], axis=0)):
        assert polygon_metrics(changed, p)['iou'] == pytest.approx(1)
        assert polygon_metrics(changed, p)['centroid_distance'] == pytest.approx(0)
        assert np.array_equal(nearest_wall_mask(changed), nearest_wall_mask(p))
        assert np.array_equal(wall_mask(pairs_from_floor(changed)), wall_mask(pairs_from_floor(p)))


def test_periodic_and_spherical_centroids_have_explicit_degeneracy():
    a = np.zeros((32, 64), bool)
    b = a.copy()
    a[8:24, :8] = True
    b[8:24, 4:12] = True
    before = compare_regions(a, b)
    after = compare_regions(np.roll(a, 60, axis=1), np.roll(b, 60, axis=1))
    assert before['iou'] == pytest.approx(after['iou'])
    assert before['spherical_iou'] == pytest.approx(after['spherical_iou'])
    assert before['circular_dx_px'] == pytest.approx(after['circular_dx_px'])
    assert before['erp_distance_px'] != pytest.approx(after['erp_distance_px'])
    all_sphere = compare_regions(np.ones_like(a), np.ones_like(a))
    assert all_sphere['circular_dx_px'] is None
    assert all_sphere['spherical_angle_rad'] is None
    assert all_sphere['spherical_resultant_a'] < 1e-12


def test_run_emits_finite_versioned_diagnostic_artifacts(tmp_path):
    result = run(tmp_path)
    assert result['schema_version'] == 'layout_metric_probe_20260926_v1'
    assert result['scope'] == 'synthetic_diagnostic_only'
    assert result['lambda_grid'] == [0, .25, .5, 1, 2]
    assert result['cases']['l_order']['bev']['iou'] == pytest.approx(4 / 7)
    assert result['cases']['invalid']['bev']['iou'] is None
    assert result['cases']['top_only']['bev']['iou'] == pytest.approx(1)
    assert result['cases']['top_only']['bev']['volume_iou'] < 1
    correspondence = result['cases']['top_only']['point_correspondence']
    assert correspondence['floor_rmse'] == pytest.approx(0)
    assert correspondence['top_rmse'] == pytest.approx(.7)
    assert correspondence['combined_rmse'] == pytest.approx(.7/np.sqrt(2))
    for name in ['l_order', 'cyclic_shift', 'reverse_ring', 'invalid']:
        assert result['cases'][name]['point_correspondence']['combined_rmse'] == pytest.approx(0)
    inserted = result['cases']['insert_collinear']['point_correspondence']
    assert inserted['combined_rmse'] == pytest.approx(0)
    assert inserted['matched_corners'] == 4 and inserted['unmatched_a'] == 1
    assert result['cases']['known_corner_deformation']['point_correspondence']['floor_rmse'] > 0
    assert result['cases']['symmetric_expansion']['manhattan']['a']['mean_deg'] < 1e-5
    assert result['cases']['invalid']['manhattan']['a']['status'] == 'invalid_polygon'
    assert result['cases']['symmetric_expansion']['bev']['centroid_distance'] == pytest.approx(0)
    assert result['cases']['same_summary_horizontal']['bev']['iou'] == pytest.approx(
        result['cases']['same_summary_vertical']['bev']['iou'])
    for name in ['same_summary_horizontal', 'same_summary_vertical']:
        assert result['cases'][name]['bev']['scores'] == pytest.approx([.6]*5)
    assert result['sensitivities']['near_horizon'][0]['relative_depth_change_one_px'] > \
        result['sensitivities']['near_horizon'][-1]['relative_depth_change_one_px']
    assert json.loads((tmp_path / 'geometry_results.json').read_text(encoding='utf8')) == result
    assert all((tmp_path / name).exists() for name in result['figures'])
    json.dumps(result, allow_nan=False)
