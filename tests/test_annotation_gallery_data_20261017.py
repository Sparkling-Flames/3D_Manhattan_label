from tools.thesis_main.analysis.annotation_gallery_data_20261017 import quality_values, quality_groups, worker_counts
from tools.thesis_main.analysis import annotation_gallery_data_20261017 as gallery


def test_doorway_is_independent_of_oos_and_unknown_is_not_normal():
    scene=gallery.scene_info(dict(scene='oos_and_doorway',doorway_status='difficult',oos_subtype='open'))
    assert scene['doorway_label']=='门洞交界 · 难标'
    assert scene['raw']=='oos_and_doorway'
    assert gallery.scene_info(dict(scene='unflagged',doorway_status='not_recorded',oos_subtype='not_recorded'))['doorway_label']=='门洞情况未记录'
    assert gallery.scene_info(dict(scene='doorway_new',doorway_status='future_type',oos_subtype=''))['doorway_status']=='future_type'


def test_user_scope_candidates_are_distinct_from_gt_versions():
    candidate=gallery.scope_metadata(dict(role='confirmed_space_candidate',candidate_id='B',space_label='浴室内侧',minimal_gap='顶界未知'))
    assert candidate['user_candidate'] and candidate['scope_label']=='浴室内侧'
    assert candidate['note']=='顶界未知'
    assert not gallery.scope_metadata(dict(role='original_GT_version'))['user_candidate']


def test_user_pending_is_explicit_and_does_not_relabel_difficulty_or_erase_people():
    image=dict(flags=dict(current_pending=False,image_hold=False,gt_problem=False),notes=[],counts=dict(retained_people=24),difficulty=dict(label='单列'))
    review=dict(status='pending',date='2026-10-17',reason='用户确认待定')
    gallery.apply_image_review(image,review)
    assert image['flags']==dict(current_pending=True,image_hold=True,gt_problem=False)
    assert image['counts']['retained_people']==24 and image['difficulty']['label']=='单列'
    assert '用户确认待定' in image['notes'][0]


def test_new_image_grade_does_not_admit_annotations_or_inflate_old_inventory():
    image=dict(image_id='new',new_batch_only=True,counts=dict(retained_people=0),quality_groups=[],notes=[])
    document=dict(summary=dict(images=259,retained_records=2921),images=[image])
    gallery.apply_new_image_difficulty(document,[dict(image_id='new',difficulty='中等',qualifier='偏简单',date='2026-10-17')])
    assert image['difficulty']['label']=='中等' and image['difficulty']['qualifier']=='偏简单'
    assert image['counts']['retained_people']==0 and image['quality_groups']==[]
    assert document['summary']==dict(images=259,retained_records=2921)


def test_oos_and_unusable_scores_are_not_normal_quality():
    row = dict(quality_usable='True', condition='oos', B8L2='99', WQ='98', A10='97', IoU3D100='96')
    assert set(quality_values(row).values()) == {None}
    row.update(condition='manual', quality_usable='False')
    assert set(quality_values(row).values()) == {None}


def test_partial_worker_exclusion_and_quality_spaces_stay_separate():
    rows = [dict(worker_id='A', retained=True), dict(worker_id='A', retained=False), dict(worker_id='B', retained=False)]
    assert worker_counts(rows) == dict(raw_people=2, removed_people=2, fully_removed_people=1)
    annotations = [dict(quality_usable=True, condition=c, target_id=t, target_binding_unique=True, quality=dict(B8L2=score, D10=score+2, WQ=None, A10=None, IoU3D100=None)) for c, t, score in [('manual', 'a', 40), ('manual', 'b', 80), ('semi', 'a', 60)]]
    groups = quality_groups(annotations, dict(a='A', b='B'))
    assert len(groups) == 3
    assert {g['B8L2'] for g in groups} == {40, 60, 80}
    assert {g['D10'] for g in groups} == {42,62,82}


def test_new_batch_keeps_old_denominator_and_includes_new_only_image(tmp_path, monkeypatch):
    monkeypatch.setattr(gallery, 'ROOT', tmp_path)
    monkeypatch.setattr(gallery, 'read_csv', lambda path: [])
    for name in ('data/mp3d_layout/img_v/new_x.jpg', 'data/mp3d_layout/valid/img/new_x.png'):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'image')
    doc = dict(summary=dict(images=1, retained_records=3), images=[dict(image_id='old', image_code='old', counts=dict(retained_people=3), flags=dict(gt_problem=False))])
    batch = dict(images=[dict(image_id='new_x', n_submitted_records=7, n_people=7, n_raw_records=7)], checks=dict(image_count=1, submitted_records=7, unmatched_image_ids=['new_x']))
    gallery.attach_new_batch(doc, batch)
    assert doc['summary']['images'] == 1 and doc['summary']['retained_records'] == 3
    assert doc['summary']['display_images'] == 2
    new = next(r for r in doc['images'] if r['image_id'] == 'new_x')
    assert new['new_batch_only'] and new['counts']['retained_people'] == 0
    assert new['new_batch']['records'] == 7


def test_admitted_batch_is_provenance_only_and_new_grade_allows_inventory_image(tmp_path,monkeypatch):
    monkeypatch.setattr(gallery,'ROOT',tmp_path)
    monkeypatch.setattr(gallery,'read_csv',lambda path:[])
    image=dict(image_id='new',image_code='new',counts=dict(retained_people=7),flags={},notes=[],new_batch_only=False,
        annotations=[dict(new_batch=True,quality_usable=i<5,calculation_status='full_computed' if i<6 else 'floor_only_computed') for i in range(7)])
    doc=dict(summary=dict(images=1,raw_records=7,retained_records=7),images=[image],admitted_source_ids=['ls98:1:2'])
    batch=dict(images=[dict(image_id='new',n_submitted_records=7,n_people=7,n_raw_records=7)],
               records=[dict(image_id='new',source_id='ls98:1:2')],
               checks=dict(image_count=1,submitted_records=7,unmatched_image_ids=['new']))
    gallery.attach_new_batch(doc,batch)
    gallery.apply_new_image_difficulty(doc,[dict(image_id='new',difficulty='中等',qualifier='偏简单',date='2026-10-17')])
    assert len(doc['images'])==1 and image['new_batch']['admitted']
    assert image['counts']['retained_people']==7 and doc['summary']['raw_records']==7
    assert doc['summary']['new_batch_only_images']==0
    assert image['difficulty']['exclusion']==''
    assert image['new_batch']['scored_records']==6 and image['new_batch']['quality_records']==5
    assert image['new_batch']['limited_records']==2 and doc['summary']['new_batch_quality_records']==5
    assert '待目标绑定' not in image['new_batch']['note']


def test_two_metrics_cannot_use_different_group_denominators():
    import pytest
    annotation=dict(quality_usable=True,condition='manual',target_id='a',target_binding_unique=True,
                    quality=dict(B8L2=40,D10=None,WQ=None,A10=None,IoU3D100=None))
    with pytest.raises(AssertionError,match='denominator'):
        quality_groups([annotation],dict(a='A'))


def test_geometry_routing_uncertainty_is_retained_separately_from_human_confirmation():
    import json
    evidence=dict(version='router_v1',quality_or_height_used_for_route=False,true_intent_established=False,
        route_reason='local_family_then_floor_iou_fallback',uncertainty='low_margin',surviving_candidates=['A','B'],
        survivor_iou_gap=.01)
    result=gallery.routing_info(dict(local_routing_evidence=json.dumps(evidence)))
    assert result['uncertainty']=='low_margin' and result['surviving_candidates']==['A','B']
    assert gallery.routing_info(dict(local_routing_evidence='null')) is None
    unavailable={k:evidence[k] for k in ('version','quality_or_height_used_for_route','true_intent_established','uncertainty')}
    unavailable['status']='floor_unavailable'
    assert gallery.routing_info(dict(local_routing_evidence=unavailable))['route_reason']=='floor_unavailable'
