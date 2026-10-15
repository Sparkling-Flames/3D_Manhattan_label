import numpy as np

from tools.thesis_main.analysis.layout_foundation_20260930 import synthetic_record
from tools.thesis_main.analysis.scope_reference_reconstruction_20261016 import reconstruct_scope, build_reference_catalog
from tools.thesis_main.analysis import scope_reference_reconstruction_20261016 as module


def test_same_floor_cycle_reverse_and_collinear_retains_complete_source_points():
    source = [[-2,-2],[0,-2],[2,-2],[2,2],[-2,2]]
    points = synthetic_record(source, [2,3,2,2,2])['points']
    target = [[2,2],[2,-2],[-2,-2],[-2,2]]
    row = reconstruct_scope(target, points)
    assert row['full_reference_available']
    assert row['points_1024x512'] == points
    assert len(row['points_1024x512']) == 10
    assert row['method'] == 'identical_footprint_existing_full_geometry'


def test_new_boundary_without_declared_roof_does_not_invent_top():
    source = [[-2,-2],[2,-2],[2,2],[-2,2]]
    points = synthetic_record(source, [2,3,4,2])['points']
    row = reconstruct_scope([[-1,-1],[1,-1],[1,1],[-1,1]], points)
    assert not row['full_reference_available']
    assert row['points_1024x512'] is None
    assert 'explicit_ceiling_plane_missing' in row['minimal_gap']


def test_explicit_source_plane_computes_only_contained_cut_without_mean_height():
    source = [[-2,-2],[2,-2],[2,2],[-2,2]]
    points = synthetic_record(source, 3)['points']
    target = [[-1,-1],[1,-1],[1,1],[-1,1]]
    row = reconstruct_scope(target, points, ceiling_plane=[0,0,2])
    assert row['full_reference_available']
    assert np.allclose(np.asarray(row['geometry']['top3d'])[:,1], 2)
    assert row['introduced_scope_edges'] == [0,1,2,3]
    outside = reconstruct_scope([[-3,-1],[1,-1],[1,1],[-3,1]], points, ceiling_plane=[0,0,2])
    assert not outside['full_reference_available']
    assert outside['outside_source_area_h2'] > 0


def test_two_explicit_user_revisions_keep_full_points_and_exclusions(monkeypatch):
    points = synthetic_record([[-2,-2],[2,-2],[2,2],[-2,2]],3)['points']
    monkeypatch.setattr(module, 'read_prepared', lambda: {'candidate_images': []})
    monkeypatch.setattr(module, 'source_planes', lambda bundle: {})
    monkeypatch.setattr(module, 'scope_sources', lambda bundle: {
        'r1':dict(image_id='i1',floor=module.floor(points).tolist(),points=points,source='revised1.json',pointer='',receipt='user'),
        'r2':dict(image_id='i2',floor=module.floor(points).tolist(),points=points,source='revised2.json',pointer='',receipt='user')})
    records = [dict(image_id='i'+str(i),image='image'+str(i),target_version='r'+str(i),
                    selected=dict(target_id='r'+str(i),role='user_revised_gt',floor=module.floor(points).tolist()),
                    candidates=[],gt_error_excluded=i==2,reference_status='user_corrected_gt') for i in [1,2]]
    bundle = dict(data=dict(objects=[]),research=dict(images=[]))
    rows = build_reference_catalog(bundle, records)
    assert len(rows)==2
    assert all(row['points_1024x512']==points and row['full_reference_available'] for row in rows)
    assert rows[1]['image_analysis_blocked']
