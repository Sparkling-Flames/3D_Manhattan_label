from datetime import datetime
import hashlib
import pytest
from tools.thesis_main.analysis.new_annotation_intake_audit_20261017 import audit_time, audit_review_scope, verify_review_export, confirmed_identity_mapping


def annotation():
    return dict(id=20,task=10,project=98,completed_by=6,updated_at='2026-09-23T00:01:00Z',lead_time=999,
                result=[dict(type='keypointlabels',value={'x':1,'y':2}),dict(type='keypointlabels',value={'x':1,'y':3}),
                        dict(type='choices',from_name='worker_scope_response',value={'choices':['in_scope']})])


def event(second,active,**extra):
    return dict(project_id='98',task_id='10',annotator_id='6',active_time_key='98|10|6',session_id='s',
        timestamp=datetime.fromisoformat('2026-09-23T00:00:00+00:00').timestamp()*1000+second*1000,active_seconds=active,active_seconds_fragment=active,
        active_time_schema_version='c2plus_task_worker_v1',script_version='manual_scope_only_20260913_v10',
        page_type='annotation',page_gate_eligible=True,store_mismatch_present=False,**extra)


def test_cumulative_snapshots_not_summed_and_annotation_boundary_unproven():
    a=annotation();r=audit_time(a,[event(10,10),event(20,20),event(70,25)])
    assert r['task_worker_active_seconds']==25 and r['task_worker_time_available']
    assert r['pre_annotation_cumulative_seconds']==20
    assert r['annotation_active_seconds'] is None and r['n_reports_after_annotation']==1
    assert r['time_status']=='replay_available_task_worker_unadopted'


def test_duplicate_log_copy_collapses_but_conflicting_event_is_ambiguous():
    r=audit_time(annotation(),[event(10,10,server_received_at='2026-09-23T08:00:11'),
                               event(10,10,server_received_at='2026-09-23T08:05:11')])
    assert r['n_unique_reports']==1 and r['n_duplicate_reports']==1
    r=audit_time(annotation(),[event(10,10),event(10,11)])
    assert r['time_status']=='ambiguous_log_conflict' and r['task_worker_active_seconds'] is None


def test_missing_wrong_identity_and_multiple_annotations_never_use_lead_time():
    assert audit_time(annotation(),[])['annotation_active_seconds'] is None
    assert set(audit_time(annotation(),[]))==set(audit_time(annotation(),[event(10,10)]))
    wrong=event(10,10);wrong['active_time_key']='98|11|6'
    r=audit_time(annotation(),[wrong]);assert r['n_identity_conflict_reports']==1 and r['task_worker_active_seconds'] is None
    old_version=event(10,10);old_version['script_version']='unverified_old_version'
    r=audit_time(annotation(),[old_version])
    assert r['time_status']=='identity_or_schema_conflict' and r['task_worker_active_seconds'] is None
    r=audit_time(annotation(),[event(10,10)],same_key_annotations=2)
    assert r['task_worker_active_seconds']==10 and r['annotation_active_seconds'] is None
    assert r['annotation_attribution_status']=='multiple_annotations_share_task_time'


def test_session_max_then_sum_and_UTC_annotation_metadata_do_not_change_task_time():
    later=event(80,5);later['session_id']='second'
    a=annotation();a['updated_at']='2026-09-23T08:01:00+08:00'
    r=audit_time(a,[event(10,10),event(20,20),later])
    assert r['task_worker_active_seconds']==25 and r['n_sessions']==2
    assert [s['peak_active_seconds'] for s in r['session_peaks']]==[20,5]
    assert r['n_reports_before_annotation']==2
    r=audit_time(annotation(),[event(10,20),event(20,10)])
    assert r['time_status']=='ambiguous_cumulative_reset' and r['task_worker_active_seconds'] is None


def test_valid_order_and_scope_choice_do_not_prove_geometry_or_target_version():
    review=dict(order=[0],order_confirmed=True,filter='keep')
    r=audit_review_scope(annotation(),review,[{'target_id':'current','current_target':True}])
    assert r['review_order_index_compatible'] and r['review_geometry_version_status']=='not_proven_source_snapshot_unavailable'
    assert r['worker_scope_choices']==['in_scope'] and r['bound_target_id'] is None
    assert r['scope_status']=='unbound_existing_image_candidates'


def test_exact_review_export_binding_proves_geometry_but_not_pair_index_basis():
    source=b'original export bytes'
    review=dict(source_name='old_name.json',source_sha256=hashlib.sha256(source).hexdigest(),
                order=[0],order_confirmed=True,filter='keep')
    assert verify_review_export(source,review)
    assert not verify_review_export(source+b'changed',review)
    r=audit_review_scope(annotation(),review,[],review_geometry_verified=True)
    assert r['review_geometry_version_status']=='verified_full_export_identity'
    assert r['order_adoption_status']=='pending_pair_index_basis' and not r['order_applied']


def test_identity_mapping_requires_confirmation_and_matches_old_source_candidates():
    candidates=[dict(source_account_id='1',candidate_existing_worker_ids=['W001'])]
    document=dict(schema='annotation_source_identity_mapping_v1',source_project=98,target_namespace='existing_W',
                  identity_confirmed=True,mappings=[dict(source_account_id='1',worker_id='W001',identity_confirmed=True)])
    assert confirmed_identity_mapping(document,candidates)=={'1':'W001'}
    document['mappings'][0]['identity_confirmed']=False
    with pytest.raises(ValueError,match='identity_mapping_unconfirmed'):
        confirmed_identity_mapping(document,candidates)


def test_prepared_package_does_not_imply_formal_adoption_and_active_package_checks_pair_binding():
    from tools.thesis_main.analysis.new_annotation_intake_audit_20261017 import apply_admission_status,ADMITTED_MANIFEST
    row=dict(source_id='ls98:10:20',worker_id='W006',image_id='a',review_order=[0],
             task_worker_active_seconds=10,task_worker_time_available=True,order_applied=False)
    registered=dict(source_id='ls98:10:20',object_id='new',worker_id='W006',image_id='a',task_worker_active_seconds=10)
    obj=dict(object_id='new',links_zero_based=[[0,1]],ordered_source_pair_indices=[0],ring_confirmed=True)
    bundle=dict(batch_admission=dict(records=[registered]),data=dict(objects=[obj]))
    pairs=dict(pair_maps={'ls98:10:20':[[0,1]]},historical_basis_recovered=False,basis='explicit_current_numbering')
    rows,active=apply_admission_status([row],bundle,'analysis_results/old/manifest.json',pairs)
    assert not active and not rows[0]['formal_input_admitted'] and not rows[0]['order_applied']
    rows,active=apply_admission_status([row],bundle,ADMITTED_MANIFEST,pairs)
    assert active and rows[0]['inventory_included'] and rows[0]['analysis_included']
    assert rows[0]['time_adopted'] and rows[0]['order_applied']
    assert not rows[0]['quality_analysis_included'] and not rows[0]['historical_basis_recovered']
    bundle['batch_admission']['records']=[]
    with pytest.raises(ValueError,match='admitted_source_population'):
        apply_admission_status([row],bundle,ADMITTED_MANIFEST,pairs)
