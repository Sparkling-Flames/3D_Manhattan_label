import copy
import csv
import pytest

from tools.thesis_main.data_prep.admit_workers_v2_20261019 import image_policy, make_object
from tests.test_intake_workers_v2_20261019 import record
from tools.thesis_main.data_prep.intake_workers_v2_20261019 import preprocess_record


def policy(code,scene='unflagged',subtype='not_recorded'):
    return image_policy(dict(image_id='i',image_code=code,oos_status='not_recorded'),
        dict(scene=scene,oos_subtype=subtype,gt_error_excluded=False,difficulty_analysis_exclusion=''),[],{})


def test_reference_error_and_oos_are_independent_and_holds_win_over_difficulty():
    p=policy('pRbA3pwrgk9-12')
    assert p['quality_gate']=='hold_reference_quality' and p['oos_status']=='not_recorded'
    p=policy('x8F5xyUWy9e-01','oos','nonorthogonal_annotatable')
    assert p['quality_gate']=='hold_reference_quality' and p['oos_status']=='confirmed'
    assert policy('uNb9QFRL6hY-51','unflagged;oos_suspected','suspected_user_review')['oos_status']=='pending'
    assert policy('pRbA3pwrgk9-16')['quality_gate']=='hold_all_analysis'
    assert policy('ordinary','oos','nonorthogonal_annotatable')['quality_gate']=='out_of_primary_scene'
    assert policy('ordinary','oos','nonorthogonal_annotatable')['consensus_gate']=='main_candidate'


def test_excluded_record_and_worker_scope_never_override_image_policy():
    r=record();r.update(preprocess_record(r));r.update(object_id='v2:new:1',disposition='excluded_by_user',
        before_preprocessing_points=copy.deepcopy(r['points_1024x512']))
    im=dict(image_id='i',image_code='pRbA3pwrgk9-12',building_id='b',room_id='')
    obj=make_object(r,im,policy('pRbA3pwrgk9-12'))
    assert obj['cleaning_disposition']=='excluded_by_review' and not obj['independent_vote_eligible']
    assert obj['worker_scope_response']=='in_scope' and obj['scene_oos_status']=='not_recorded'
    assert not obj['ring_confirmed'] and obj['order_record'] is None
    assert obj['original_export_points'] is None


def test_pending_image_preserves_votes_but_blocks_analysis_and_does_not_guess_pairing():
    r=record();r['geometry_status']='pairing_unverified';r.update(preprocess_record(r))
    r.update(object_id='v2:new:1',disposition='retained_user',before_preprocessing_points=r['points_1024x512'])
    im=dict(image_id='i',image_code='uNb9QFRL6hY-36',building_id='b',room_id='')
    obj=make_object(r,im,policy('uNb9QFRL6hY-36'))
    assert obj['independent_vote_eligible'] and obj['main_quality_gate']['status']=='hold_main_analysis'
    assert obj['points_1024x512'] is None and obj['geometry']['status']=='pairing_unavailable'


def test_admitted_bundle_preserves_v1_and_holds_every_user_list_image():
    from tools.thesis_main.data_prep.admit_workers_v2_20261019 import BASE,OUT,RECONFIRMED
    from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
    base=load_current_bundle(BASE);v2=load_current_bundle(OUT/'manifest.json')
    assert v2['validation']['annotations']==10439
    assert v2['data']['objects'][:len(base['data']['objects'])]==base['data']['objects']
    with (OUT/'record_eligibility.csv').open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
    blocked=[r for r in rows if r['image_code'] in RECONFIRMED]
    assert {r['image_code'] for r in blocked}==set(RECONFIRMED)
    assert all(r['quality_input_candidate']=='False' and r['pool_analysis_eligible']=='False' for r in blocked)
    assert all(r['score_status']=='not_scored_v2' for r in rows)
    assert sum(r['origin']=='new' and r['cleaning_disposition']=='excluded_by_review' for r in rows)==14
    from tools.thesis_main.analysis.current_annotation_context_20261017 import load_scored_context
    scored=load_scored_context(v2)
    assert scored['score_context_version']=='quality_workers_v2_20261019'
    assert len(scored['quality_records'])==10439
