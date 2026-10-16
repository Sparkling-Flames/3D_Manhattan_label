from copy import deepcopy

import pytest

from tools.thesis_main.analysis.descriptive_inventory_20261015 import inventory_rows


def inputs():
    obj = dict(object_id='O1', object_kind='annotation', image_id='I1', image_code='I-1',
        worker_id='W001', building_id='B1', room_id=None, condition='manual',
        source=dict(project=28, task=5, annotation=9, path='export_label/example.json'),
        canonical_unit=['W001', 'I1', 'manual'], person_image_unit=['W001', 'I1'],
        independent_vote_eligible=True, independent_vote_reasons=[],
        cleaning_disposition='retained', worker_quality_gate='candidate_pending_geometry',
        main_quality_gate=dict(status='candidate_pending_geometry'),
        main_consensus_gate=dict(status='main_candidate'), preprocessing_status='ready',
        geometry=dict(status='surface_valid'), ring_confirmed=False)
    timing = dict(canonical_annotation_id='H1', project_id='28', runtime_task_id='5', worker_id='1',
        active_time_seconds='42', active_time_formal_available=True, timing_status='project+task+annotator',
        active_time_source='log', active_time_source_file='example.jsonl', stage='P1',
        timing_rule_version='frozen_stage_task_worker_active_time')
    spine = dict(canonical_annotation_id='H1', image_id='I1', building_id='B1', worker_id='1',
        project_id='28', runtime_task_id='5', raw_condition='manual')
    return obj, timing, spine


def test_time_never_uses_fallback_or_manually_adjusted_values():
    obj, timing, spine = inputs()
    assert inventory_rows([obj], [timing], [spine], set())[0]['active_time_seconds'] == 42
    adjusted = inventory_rows([obj], [timing], [spine], {('28', '5', '1')})[0]
    assert adjusted['active_time_seconds'] is None
    assert adjusted['time_status'] == 'known_manual_adjustment'
    timing['active_time_source'] = 'lead_time_fallback'
    assert inventory_rows([obj], [timing], [spine], set())[0]['active_time_seconds'] is None
    missing = inventory_rows([obj], [], [], set())[0]
    assert missing['active_time_seconds'] is None
    assert missing['time_status'] == 'not_in_historical_table'
    obj['object_id'] = 'new_28_5_9_W001'
    assert inventory_rows([obj], [], [], set())[0]['time_status'] == 'new_collection_time_unfrozen'


def test_identity_mismatch_and_duplicate_keys_fail():
    obj, timing, spine = inputs()
    wrong = deepcopy(spine)
    wrong['image_id'] = 'I2'
    with pytest.raises(ValueError, match='identity mismatch'):
        inventory_rows([obj], [timing], [wrong], set())
    with pytest.raises(ValueError, match='duplicate'):
        inventory_rows([obj], [timing, timing], [spine], set())


def test_admitted_collection_time_is_bound_to_source_task_account():
    obj,_,_=inputs()
    obj['source']['project']=98
    obj['source']['source_account_id']='6'
    obj['collection_active_time']=dict(seconds=103,identity_key='98|5|6',adopted=True,
        rule='session_max_then_sum_v10_task_worker',source_audit='research/audit.json')
    row=inventory_rows([obj],[],[],set())[0]
    assert row['active_time_seconds']==103 and row['time_stage']=='project98_admitted'
    obj['collection_active_time']['identity_key']='98|9|6'
    with pytest.raises(ValueError,match='admitted time identity'):
        inventory_rows([obj],[],[],set())
