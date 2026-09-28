import json

import numpy as np
import pytest

from tools.thesis_main.analysis.layout_real_case_probe_20260926 import (
    candidate_reason, source_points, compare_footprints, run,
)


def test_source_points_reads_and_checks_raw_export(tmp_path):
    path = tmp_path / 'export_label' / 'one.json'
    path.parent.mkdir()
    path.write_text(json.dumps([{'id': 2, 'annotations': [{'id': 3, 'result': [
        {'type': 'keypointlabels', 'value': {'x': 25, 'y': 75}}
    ]}]}]), encoding='utf8')
    row = dict(canonical_annotation_id='c', provenance=None, raw_export_path='export_label/one.json',
               runtime_task_id=2, raw_annotation_id=3, raw_points_1024x512=[[256, 384]])
    points, evidence = source_points(tmp_path, row, {})
    assert points.tolist() == [[256, 384]]
    assert evidence['source_tier'] == 'runtime_raw_export'
    row['raw_points_1024x512'] = [[257, 384]]
    with pytest.raises(ValueError, match='raw_coordinate_mismatch'):
        source_points(tmp_path, row, {})


def test_preliminary_evidence_does_not_become_confirmed_order():
    assert candidate_reason(None) == 'no_existing_order_evidence'
    evidence = dict(verdict='无需调整', image_code='q9vSo1VnCiC-16', pending_user_confirmation=True)
    assert candidate_reason(evidence) == 'preliminary_order_evidence'
    evidence['image_code'] = 'e9zR4mvMWw7-09'
    assert candidate_reason(evidence) == 'existing_evidence_hidden_adjacency_unresolved'


def test_footprint_change_detects_adjacency_and_rejects_invalid_ring():
    square = np.array([[-2, -2], [2, -2], [2, 2], [-2, 2]], float)
    same = compare_footprints(square, square[::-1])
    assert same['iou'] == 1
    assert same['centroid_distance_camera_height'] == 0
    assert same['boundary_rms_camera_height'] < 1e-12
    with pytest.raises(ValueError, match='invalid_floor_polygon'):
        compare_footprints(square[[0, 2, 1, 3]], square)
    points = np.array([[-.2, 2], [-.2, -3], [1.3, -3], [.5, -.4], [1, -.35], [.5, 2]])
    different = compare_footprints(points, points[[0, 1, 2, 4, 3, 5]])
    assert different['iou'] < 1
    # 相同顶点不等于相同边；Shapely默认离散Hausdorff会漏掉此差异。
    assert different['boundary_sampled_hausdorff_camera_height'] > .1


def test_real_panel_preserves_all_comment_ids_and_marks_conditional_evidence(tmp_path):
    result = run(tmp_path)
    inventory = [r for r in result['panel_inventory'] if r['from_comment_lookup']]
    assert len(inventory) == len({r['canonical_annotation_id'] for r in inventory}) == 240
    assert all(r['source']['status'] == 'verified_against_raw_export' for r in inventory)
    assert result['selected_annotations'] == 4
    assert result['formally_confirmed_orders'] == 0
    assert all(r['evidence_status'] == 'preliminary_order_evidence_pending_user_confirmation'
               for r in result['selected_cases'])
    screenshot = result['screenshot_representation_probe'][0]['views']
    assert screenshot['raw']['comparison']['bev']['iou'] == pytest.approx(.7606367948408241)
    assert screenshot['shared_x']['comparison']['erp']['iou'] == 1
    assert screenshot['shared_x']['comparison']['erp']['erp_distance_px'] == 0
    assert result['screenshot_cross_worker_probe']['raw_differing_endpoint_ids_1based'] == [5]
