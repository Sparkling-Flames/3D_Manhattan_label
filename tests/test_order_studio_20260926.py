"""检查顺序工作台只改变排列副本，保留坐标和来源。"""
from copy import deepcopy

import pytest

from tools.thesis_main.analysis.build_order_studio_20260926 import annotation_variant, validate_inventory


def annotation():
    points = [[700, 150], [701, 360], [100, 140], [101, 370], [400, 160], [401, 350]]
    return dict(canonical_annotation_id='ann1', worker_id='W008', raw_condition='manual',
                raw_points_1024x512=points, effective_points_1024x512=deepcopy(points),
                links_zero_based=[[2, 3], [0, 1], [4, 5]], pairing_status='existing_accepted_pairing',
                raw_export_path='export_label/source.json', runtime_task_id='1', raw_annotation_id='2',
                processing_status='unchanged')


def test_preserves_endpoint_identity_coordinates_and_existing_ring():
    row = annotation(); before = deepcopy(row)
    variant = annotation_variant(row)
    assert row == before
    assert [p['source_pair_id'] for p in variant['geometry']['pairs']] == ['raw:3/4', 'raw:1/2', 'raw:5/6']
    assert [p['top'] for p in variant['geometry']['pairs']] == [row['effective_points_1024x512'][i] for i in [2, 0, 4]]
    assert variant['geometry']['pairs'][0]['bottom'][0] == 101  # no shared-x averaging
    assert variant['geometry']['fit']['status'] == 'not_requested'
    assert variant['source']['canonical_annotation_id'] == 'ann1'


def test_unpaired_stays_visible_and_added_point_never_claims_raw_identity():
    row = annotation(); row['links_zero_based'] = None; row['pairing_status'] = 'unavailable'
    v = annotation_variant(row)
    assert 'geometry' not in v and v['error']
    assert v['source']['points'] == row['effective_points_1024x512']
    row = annotation(); row['effective_points_1024x512'][3] = [101, 375]
    v = annotation_variant(row)
    assert v['source']['original_point_ids_1based'][3] is None
    assert v['geometry']['pairs'][0]['source_pair_id'] == 'effective:3/4'
    row['links_zero_based'] = [[2, 3], [0, 1], [0, 5]]
    with pytest.raises(ValueError, match='pair_identity'):
        annotation_variant(row)


def test_full_inventory_never_silently_drops_or_duplicates_records():
    rows = [{'id': 'a', 'image_id': 'x'}, {'id': 'b', 'image_id': 'x'}]
    validate_inventory(rows, expected_records=2, expected_images=1)
    with pytest.raises(ValueError, match='inventory'):
        validate_inventory(rows + rows[:1], expected_records=3, expected_images=1)
    with pytest.raises(ValueError, match='inventory'):
        validate_inventory(rows, expected_records=3, expected_images=1)


def test_preprocessed_candidate_baseline():
    import json
    from pathlib import Path
    import numpy as np
    from tools.thesis_main.analysis.shared_x_reanalysis_20260922 import shared_x
    p=Path(__file__).resolve().parents[1]/'analysis_results/order_studio_20260926/preprocessed_source.json'
    records=json.loads(p.read_text(encoding='utf-8'))['objects']
    assert len(records)==len({r['object_id'] for r in records})==90
    assert len({r['image_id'] for r in records})==45
    assert sum(r['object_kind']=='annotation' for r in records)==63
    for r in records:
        before=np.asarray(r['before_preprocessing_points']);after=np.asarray(r['preprocessed_points'])
        assert np.array_equal(before[:,1],after[:,1])
        assert np.array_equal(shared_x(before,r['links_zero_based']),after)
        assert all(after[a,0]==after[b,0] for a,b in r['links_zero_based'])
        if r['object_kind']!='annotation':assert np.array_equal(before,after)
    assert shared_x([[1020,100],[4,400]],[[0,1]]).tolist()==[[0,100],[0,400]]
    full=json.loads((p.parents[1]/'shared_x_baseline_20260928/preprocessed_source.json').read_text(encoding='utf-8'))['objects']
    assert len(full)==3439 and sum(r['object_kind']=='annotation' for r in full)==3152
    lookup={r['object_id']:r for r in full}
    for r in records:assert r['preprocessed_points']==lookup[r['object_id']]['preprocessed_points']
    for r in full:
        if r['preprocessing_status']=='unavailable':assert r['preprocessed_points'] is None
        else:assert np.array_equal(shared_x(r['before_preprocessing_points'],r['links_zero_based']),r['preprocessed_points'])
