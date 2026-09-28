from tools.thesis_main.analysis.order_review_20260928 import screen_order, select_queue, resolve_links, diagnose_points, unique_gt_references
import pytest


def test_periodic_crowding_and_four_pairs_are_not_order_candidates():
    # Three corners straddle the panorama seam; all identities are retained.
    pairs = [[[x, 100], [x, 400]] for x in [1018, 4, 12, 350, 700]]
    result = screen_order(pairs, None)
    assert result['dense_pair_groups'] == [[1, 2, 3]]
    assert select_queue({}, result, 5, False, True) == 'weak'
    assert select_queue({}, result, 4, False, True) == 'normal'
    result['crossings'] = [[1, 3]]
    assert select_queue({}, result, 4, False, True) == 'geometry'
    assert select_queue({}, result, 4, True, True) == 'priority'
    assert select_queue({'scene_category': 'doorway_annotatable'}, result, 5, False, True) == 'priority'
    assert select_queue({'scene_category': 'oos'}, result, 5, True, True) == 'later'
    assert select_queue({'cleaning_disposition': 'excluded_by_review'}, result, 5, True, True) == 'excluded'


def test_crossing_and_repaired_pair_identity():
    floor = [[0, -1, 0], [1, -1, 1], [0, -1, 1], [1, -1, 0]]
    assert screen_order([], floor)['crossings'] == [[1, 3]]
    original = dict(effective_points_1024x512=[[100,100],[100,400],[400,100],[400,400]], links_zero_based=[[0,1],[2,3]])
    points = [[100,100],[100,400],[400,100],[400,400]]
    links, basis = resolve_links(original, points, ['p1','p2','p3','p4'])
    assert links == [[0,1],[2,3]] and basis == 'existing_verified'
    # A deleted stray point must never leave shifted old array indices in use.
    original['effective_points_1024x512'] = points + [[700,110]]
    original['links_zero_based'] = None
    links, basis = resolve_links(original, points, ['p1','p2','p3','p4'])
    assert links == [[0,1],[2,3]] and basis == 'unique_pairing_after_repair'


def test_gt_aliases_are_deduplicated_and_model_is_not_gt():
    refs=[dict(name='gt_original',source='a.txt',raw_points=[[1,2]]),dict(name='gt_revised',source='a.txt',raw_points=[[1,2]]),dict(name='hohonet',source='model.txt')]
    assert len(unique_gt_references(refs))==1
    assert unique_gt_references(refs)[0]['aliases']==['gt_original','gt_revised']
    refs[1]['raw_points']=[[2,3]]
    with pytest.raises(ValueError,match='same_gt_source'):unique_gt_references(refs)


def test_invalid_projection_never_becomes_normal_geometry():
    points=[[100,100],[100,255.6],[400,120],[400,400]]
    assert diagnose_points(points,[[0,1],[2,3]])[1]=='floor_near_horizon'
    assert diagnose_points(points,[[0,1],[0,3]])[1]=='invalid_pair_identity'


def test_generated_candidates_keep_gt_and_annotation_boundaries():
    import csv,json
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]/'analysis_results/order_candidates_20260928'
    with (root/'全量排序初筛.csv').open(encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
    assert len({r['object_id'] for r in rows})==len(rows)
    assert sum(r['object_kind']=='annotation' for r in rows)==3152
    assert sum(r['object_kind'].startswith('gt_') for r in rows)==287
    assert all(r['source_verified']=='true' for r in rows)
    for r in rows:
        if r['queue'] in {'priority','weak'}:
            assert r['cleaning_disposition'] not in {'excluded_by_review','historical_not_accepted'}
            assert r['scene_oos_status']!='confirmed'
            assert r['worker_quality_gate'] not in {'hold_all_analysis','hold_main_analysis'}
        if r['queue']=='weak':assert int(r['pair_count'])>4
    assert any(r['object_kind']=='gt_manual_revision' and r['queue']=='priority' for r in rows)
    assert any(r['object_kind']=='annotation' and r['queue']=='pairing' and json.loads(r['explicit_order_evidence']) for r in rows)
    assert all(r['queue']=='hold' for r in rows if r['object_kind'].startswith('gt_') and r['image_code']=='pRbA3pwrgk9-16')
