"""声明表示的反例；直接调用仓库函数，不复制 Pro 重建适配器。"""
import copy

import numpy as np
import pytest
from shapely.geometry import Polygon

from tools.thesis_main.analysis.consensus_region_20260923 import wall_mask
from tools.thesis_main.analysis.layout_metric_probe_20260926 import bev_range_metrics, polygon_metrics
from tools.thesis_main.analysis.research_round_20260929 import reconstruct, declared_column_wall_mask
from tools.thesis_main.analysis.layout_foundation_20260930 import (
    synthetic_record, synthetic_cases, synthetic_mesh_wall_mask, inspect_panel,
)

SQUARE = [[-2, -2], [2, -2], [2, 2], [-2, 2]]


@pytest.mark.parametrize('width', [128, 512])
@pytest.mark.parametrize('change', ['cycle', 'reverse', 'collinear'])
def test_equivalent_rings_and_coordinate_phase(width, change):
    a = synthetic_record(SQUARE)
    if change == 'cycle': points = np.roll(SQUARE, 1, axis=0)
    elif change == 'reverse': points = SQUARE[::-1]
    else: points = [[-2, -2], [0, -2], [2, -2], [2, 2], [-2, 2]]
    b = synthetic_record(points)
    snapshot = copy.deepcopy(b)
    for convention in ('continuous', 'pixel_center'):
        records = [dict(r, points=(np.array(r['points'])-(.5 if convention=='pixel_center' else 0)).tolist())
                   for r in (a, b)]
        ga, gb = [reconstruct(r, coordinate_convention=convention) for r in records]
        ma, mb = [declared_column_wall_mask(g, width, width//2) for g in (ga, gb)]
        assert np.array_equal(ma, mb)
        assert bev_range_metrics(ga['floor'], gb['floor'])['bev_range_iou'] == pytest.approx(1)
        assert np.array_equal(ma, wall_mask(np.array(records[0]['points']).reshape(-1, 2, 2),
            width, width//2, coordinate_convention=convention))
    assert b == snapshot
    assert len(reconstruct(b)['source_pair_indices']) == len(points)


def test_seam_and_legacy_default_are_explicit():
    from tools.label_studio.panorama_studio.geometry import pixel_ray, project_pixel
    for convention in ('continuous','pixel_center'):
        projected=project_pixel(pixel_ray(0,310,1024,512,coordinate_convention=convention),
            1024,512,coordinate_convention=convention)
        np.testing.assert_allclose(projected,[0,310],atol=1e-10)
    a = synthetic_record(SQUARE); b = copy.deepcopy(a)
    p = np.array(a['points']).reshape(-1, 2, 2)
    b['points'] = ((np.array(b['points']) + [80, 0]) % [1024, 1024]).tolist()
    ma = declared_column_wall_mask(reconstruct(a), 128, 64)
    assert np.array_equal(np.roll(ma, 10, axis=1), declared_column_wall_mask(reconstruct(b), 128, 64))
    assert np.array_equal(wall_mask(p), wall_mask(p, coordinate_convention='pixel_center'))
    assert np.array_equal(wall_mask(p, coordinate_convention='continuous'), wall_mask(p-.5))
    with pytest.raises(ValueError, match='unknown_coordinate_convention'):
        wall_mask(p, coordinate_convention='unknown')


def test_pixel_center_seam_roundtrip_is_accepted_on_reinput():
    from tools.label_studio.panorama_studio.geometry import pixel_ray, project_pixel, normalize
    for width in (128,1024):
        height=width//2;y=height*310/512
        for x in (-.25,-.5,-.5+1e-7,0,width-.5-1e-7,width-.5):
            projected=project_pixel(pixel_ray(x,y,width,height,coordinate_convention='pixel_center'),
                width,height,coordinate_convention='pixel_center')
            payload=dict(width=width,height=height,coordinate_mode='pixels',ordered_pairs=[
                dict(top=dict(x=projected[0],y=height/4),bottom=dict(x=projected[0],y=projected[1]))
                for _ in range(3)])
            normalize(payload,coordinate_convention='pixel_center')
            assert -.5<=projected[0]<width-.5
            assert abs((projected[0]-x+width/2)%width-width/2)<1e-9
            assert projected[1]==pytest.approx(y)


def test_valid_adjacency_change_and_self_intersection_are_not_sorted():
    a, b = synthetic_cases()['different_ring']
    ga, gb = reconstruct(a), reconstruct(b)
    assert ga['polygon_valid'] and gb['polygon_valid']
    assert ga['camera_relation'] == gb['camera_relation'] == 'inside'
    assert bev_range_metrics(ga['floor'], gb['floor'])['bev_range_iou'] == pytest.approx(77/120)
    assert not np.array_equal(declared_column_wall_mask(ga), declared_column_wall_mask(gb))
    assert np.array_equal(wall_mask(np.array(a['points']).reshape(-1, 2, 2)),
                          wall_mask(np.array(b['points']).reshape(-1, 2, 2)))
    bad = synthetic_record([SQUARE[i] for i in [0, 2, 1, 3]])
    g = reconstruct(bad)
    assert not g['polygon_valid'] and 'invalid_footprint' in g['reason']
    with pytest.raises(ValueError, match='invalid_footprint'): declared_column_wall_mask(g)


def test_hidden_extension_and_vertex_median_proxy_blind_spots():
    a, b = synthetic_cases()['hidden_extension']
    ga, gb = reconstruct(a), reconstruct(b)
    assert not ga['camera_in_visible_kernel'] and not gb['camera_in_visible_kernel']
    assert np.array_equal(declared_column_wall_mask(ga), declared_column_wall_mask(gb))
    assert bev_range_metrics(ga['floor'], gb['floor'])['bev_range_iou'] == pytest.approx(20.5/36.5)
    a, b = synthetic_cases()['collinear_height_proxy']; ga, gb = reconstruct(a), reconstruct(b)
    assert np.array_equal(declared_column_wall_mask(ga), declared_column_wall_mask(gb))
    assert bev_range_metrics(ga['floor'], gb['floor'])['bev_range_iou'] == pytest.approx(1)
    assert polygon_metrics(ga['floor'], gb['floor'], np.median(ga['heights']),
                           np.median(gb['heights']))['volume_iou'] == pytest.approx(5/7)


def test_same_longitude_and_close_vertices_keep_identity():
    a = synthetic_record([[-3, -3], [3, -3], [3, 3], [2, 2], [1, 1], [-3, 3]])
    g = reconstruct(a)
    assert len(g['floor']) == 6 and declared_column_wall_mask(g).any()
    with pytest.raises(ValueError, match='duplicate_longitude'):
        wall_mask(np.array(a['points']).reshape(-1, 2, 2))
    close = synthetic_record([[-2, -2], [-1.99999, -2], [2, -2], [2, 2], [-2, 2]])
    assert len(reconstruct(close)['floor']) == 5


def test_footprint_top_camera_and_review_are_separate():
    a = synthetic_record(SQUARE); a['points'][0][1] = 270
    a.update(order_status='default_unreviewed', ring_confirmed=False)
    g = reconstruct(a)
    assert g['representations']['declared_footprint']['status'] == 'ok'
    assert g['representations']['declared_column_wall_band']['status'] == 'unavailable'
    assert Polygon(g['floor']).area == pytest.approx(16)
    assert g['ring_confirmed'] is False and g['order_status'] == 'default_unreviewed'
    outside = reconstruct(synthetic_record([[1, -2], [3, -2], [3, 2], [1, 2]]))
    assert outside['polygon_valid'] and outside['camera_relation'] == 'outside'
    assert outside['representations']['declared_footprint']['status'] == 'ok'
    assert outside['representations']['declared_column_wall_band']['reason'] == 'camera_not_strictly_inside'
    boundary = reconstruct(synthetic_record([[0, -2], [2, -2], [2, 2], [0, 2]]))
    assert boundary['camera_relation'] == 'boundary'
    from tools.label_studio.panorama_studio.geometry import footprint_state, geometry_issues
    close_boundary=[[-1e-13,-2],[2,-2],[2,2],[-1e-13,2]]
    assert footprint_state(close_boundary)['camera_relation']=='boundary'
    assert geometry_issues(close_boundary)==[]  # 历史精确相机判定，不回改为新容差。
    a = synthetic_record(SQUARE); a['points'][1][1] = 256.01
    assert reconstruct(a)['representations']['declared_footprint']['reason'] == 'near_horizon'
    a = synthetic_record(SQUARE); a['points'][0][0] += .1
    g = reconstruct(a)
    assert g['representations']['declared_footprint']['status'] == 'ok'
    assert g['representations']['declared_column_wall_band']['reason'] == 'vertical_pair_mismatch'
    # 非法完整输入先被拒绝；此边界不同于合法top的几何失败。
    for invalid_top_y in (-1,float('nan')):
        a=synthetic_record(SQUARE);a['points'][0][1]=invalid_top_y
        g=reconstruct(a)
        assert all(s['status']=='unavailable' for s in g['representations'].values())


def test_known_mesh_oracle_requires_roof_and_exposes_nonflat_occlusion():
    for a in (synthetic_record(SQUARE), synthetic_cases()['hidden_extension'][0]):
        g = reconstruct(a)
        from tools.label_studio.panorama_studio.geometry import triangulate
        mesh = synthetic_mesh_wall_mask(g['floor'], g['heights'], triangulate(g['floor']), 128)
        assert np.array_equal(mesh, declared_column_wall_mask(g, 128, 64))
    g = reconstruct(synthetic_record([[-1, -2], [3, -2], [3, 2], [-1, 2]], [1.25, 4, 1.25, 4]))
    with pytest.raises(ValueError, match='explicit_roof_required'):
        synthetic_mesh_wall_mask(g['floor'], g['heights'], None)
    mesh = synthetic_mesh_wall_mask(g['floor'], g['heights'], [[0, 1, 2], [0, 2, 3]], 128)
    from tools.thesis_main.analysis.research_round_20260929 import iou
    assert .90 < iou(mesh, declared_column_wall_mask(g, 128, 64)) < .93


def test_census_preserves_unknowns_and_denominators():
    a = synthetic_record(SQUARE); a.update(worker='P1', condition='manual', cleaning='retained',
        independent=True, consensus_eligible=True, quality_candidate=True,
        geometry_status='surface_valid', order_status='default_unreviewed', ring_confirmed=False)
    b = copy.deepcopy(a); b.update(id='B', worker='P2', points=None, cleaning='excluded_by_review', independent=False)
    panel = dict(schema='layout_research_panel_v1', images=[dict(code='B-01', building='B',
        scene=dict(oos_status='not_recorded', doorway_status='not_recorded', coverage='partial'),
        annotations=[a, b], references=[])])
    rows, strata, summary = inspect_panel(panel, width=128)
    assert summary['annotations'] == 2 and summary['workers'] == 2
    assert rows[1]['bev_range_status'] == 'unavailable' and rows[1]['bev_range_reason'] == 'pairing_unavailable'
    assert rows[0]['ring_confirmed'] is False and rows[0]['oos_status'] == 'not_recorded'
    assert rows[0]['scope_annotation_mark'] == 'no_recorded_mark'
    assert next(s for s in strata if s['dimension']=='oos_status')['records'] == 2
    assert panel['images'][0]['annotations'][1]['independent'] is False


def test_new_output_schema_separates_bev_and_optional_historical_proxy(tmp_path):
    import csv
    from tools.thesis_main.analysis.research_round_20260929 import run
    a=synthetic_record(SQUARE); a.update(worker='P1',condition='manual',cleaning='retained',
        independent=False,consensus_eligible=False,quality_candidate=True,geometry_status='surface_valid')
    a['points'][0][1]=270
    ref=synthetic_record(SQUARE);ref.update(id='GT',version='original')
    panel=dict(schema='layout_research_panel_v1',images=[dict(code='B-01',building='B',scene={},annotations=[a],references=[ref])])
    result=run(panel,tmp_path,seeds=0,width=128)
    rows=list(csv.DictReader((tmp_path/'individual_quality.csv').open(encoding='utf-8-sig')))
    assert result['schema']=='research_round_baseline_v2'
    assert {r['representation'] for r in rows}=={'bev_range','declared_column_wall_band',
        'legacy_x_envelope_continuous','legacy_x_envelope_pixel_center'}
    bev=next(r for r in rows if r['representation']=='bev_range')
    assert bev['status']=='ok' and float(bev['bev_range_iou'])==pytest.approx(1)
    column=next(r for r in rows if r['representation']=='declared_column_wall_band')
    assert column['status']=='unavailable' and 'wrong_hemisphere' in column['reason'] and column['iou']==''
    result=run(panel,tmp_path,seeds=0,width=128,include_legacy_proxy=True)
    assert result['historical_vertex_median_proxy_requested'] is True
    rows=list(csv.DictReader((tmp_path/'individual_quality.csv').open(encoding='utf-8-sig')))
    proxy=next(r for r in rows if r['representation']=='historical_vertex_median_prism_proxy')
    assert proxy['status']=='unavailable' and proxy['prism_surrogate_iou']==''
