from copy import deepcopy

from tools.thesis_main.analysis.scope_quality_binding_20261016 import build_affected_records


def fixture(role='confirmed_scope'):
    square = [[-1, -1], [1, -1], [1, 1], [-1, 1]]
    annotation = dict(object_id='a', object_kind='annotation', image_id='i', image_code='b-01',
                      worker_id='w1', condition='manual', cleaning_disposition='retained',
                      independent_vote_eligible=True, independent_vote_reasons=[],
                      main_consensus_gate=dict(status='main_candidate', reasons=[]),
                      main_quality_gate=dict(status='candidate_pending_geometry', reasons=[]),
                      worker_quality_gate='candidate_pending_geometry',
                      points_1024x512=[[100, 100], [100, 400], [500, 100], [500, 400], [900, 100], [900, 400]],
                      geometry=dict(status='surface_valid'), ring_confirmed=False)
    objects = [dict(annotation, object_id=str(n), worker_id='w'+str(n)) for n in range(3)]
    bundle = dict(data=dict(objects=objects, images=[dict(image_id='i', image_code='b-01', building_id='b', references={})]),
                  research=dict(images=[]))
    difficulty = [dict(image_id='i', image='b-01', current_class='简单', gt_error_excluded=False,
                       difficulty_analysis_eligible=True, difficulty_analysis_exclusion='', target_version='new',
                       top_boundary_pending=False, selected=dict(target_id='new', role=role, floor=square))]
    routing = dict(candidate_images=[dict(image_id='i', candidates=[
        dict(candidate_id='b-01:A', reference_object_id='old', floor_xz_h=[[x*2,y*2] for x,y in square],
             admitted_for_routing=True, full_reference_available=True),
        dict(candidate_id='b-01:B', reference_object_id='new', floor_xz_h=square,
             admitted_for_routing=True, full_reference_available=False)])],
        records=[dict(record_id='R1', object_id='0', source_object=objects[0])],
        manual_overrides={}, manual_family_directives={})
    return bundle, difficulty, routing


def test_revision_is_fixed_not_closeness_or_best_score_and_input_is_unchanged():
    bundle, difficulty, routing = fixture('user_revised_gt')
    before = deepcopy(bundle)
    result = build_affected_records(bundle, difficulty, routing_input=routing)
    assert len(result['affected_records']) == 3
    assert all(r['chosen_target_id'] == 'new' for r in result['affected_records'])
    assert all(r['binding_status'] == 'fixed_current_gt_revision' for r in result['affected_records'])
    assert all(r['pool_source_workers'] == 3 for r in result['affected_records'])
    assert bundle == before


def test_manual_override_and_family_do_not_become_best_score_or_current_target():
    bundle, difficulty, routing = fixture()
    routing['manual_overrides']['R1'] = dict(object_id='0', selected_candidate_id='b-01:A', source='latest_USER_DECISIONS')
    routing['manual_family_directives']['R1'] = dict(allowed_candidate_ids=['b-01:A', 'b-01:B'])
    result = build_affected_records(bundle, difficulty, routing_input=routing)
    bound = result['affected_records'][0]
    assert bound['chosen_target_id'] == 'old' and bound['binding_status'] == 'explicit_manual_target'
    assert not bound['chosen_target_is_current']
    assert all(r['chosen_target_id'] == '' for r in result['affected_records'][1:])
    assert len(result['record_targets']) == 6
    space = next(r for r in result['image_spaces'] if r['target_id'] == 'old' and r['condition'] == 'manual')
    assert space['n_space_bound_workers'] == 1 and space['n_pool_workers'] == 3


def test_family_only_is_pending_and_changed_manual_geometry_is_not_reused():
    bundle, difficulty, routing = fixture()
    routing['manual_family_directives']['R1'] = dict(allowed_candidate_ids=['b-01:A', 'b-01:B'])
    result = build_affected_records(bundle, difficulty, routing_input=routing)
    assert result['affected_records'][0]['binding_status'] == 'pending_manual_family_not_unique'
    routing['manual_overrides']['R1'] = dict(object_id='0', selected_candidate_id='b-01:A')
    routing['records'][0]['source_object'] = deepcopy(routing['records'][0]['source_object'])
    routing['records'][0]['source_object']['points_1024x512'][0][0] += 1
    changed = build_affected_records(bundle, difficulty, routing_input=routing)
    assert changed['affected_records'][0]['binding_status'] == 'pending_manual_evidence_geometry_changed'


def test_all_annotations_retained_in_ledger_but_excluded_people_do_not_support_space():
    bundle, difficulty, routing = fixture('user_revised_gt')
    bundle['data']['objects'][0].update(cleaning_disposition='excluded_by_review',
                                      independent_vote_eligible=False, independent_vote_reasons=['excluded_by_review'])
    bundle['data']['objects'].append(dict(object_id='gt', object_kind='gt_original', image_id='i'))
    result = build_affected_records(bundle, difficulty, routing_input=routing)
    assert len(result['affected_records']) == 3
    assert all(not r['analysis_binding_eligible'] for r in result['affected_records'])
    space = next(r for r in result['image_spaces'] if r['condition'] == 'manual')
    assert space['n_pool_workers'] == 2 and space['n_space_bound_workers'] == 2


def test_individual_quality_hold_does_not_erase_pool_people_but_blocks_quality():
    bundle, difficulty, routing = fixture('user_revised_gt')
    obj = bundle['data']['objects'][0]
    obj['main_quality_gate'] = dict(status='hold_individual_review', reasons=['representation_pending'])
    obj['worker_quality_gate'] = 'hold_individual_review'
    result = build_affected_records(bundle, difficulty, routing_input=routing)
    row = result['affected_records'][0]
    assert row['pool_source_workers'] == 3 and row['pool_analysis_eligible']
    assert row['score_input_eligible'] and not row['person_quality_restriction_clear']
