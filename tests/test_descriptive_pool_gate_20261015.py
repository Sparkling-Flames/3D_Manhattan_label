from copy import deepcopy

from tools.thesis_main.analysis.descriptive_pool_gate_20261015 import build_pool_gate


def annotation(oid, worker, condition='manual', **changes):
    row = dict(object_id=oid, object_kind='annotation', image_id='i', image_code='building-01',
               worker_id=worker, condition=condition, cleaning_disposition='retained',
               independent_vote_eligible=True, independent_vote_reasons=[],
               main_consensus_gate=dict(status='main_candidate', reasons=['main_candidate']),
               main_quality_gate=dict(status='candidate_pending_geometry', reasons=[]))
    row.update(changes)
    return row


def fixture(objects):
    image = dict(image_id='i', image_code='building-01', building_id='building')
    difficulty = [dict(image_id='i', current_class='简单', gt_error_excluded=False,
                       difficulty_analysis_eligible=True, difficulty_analysis_exclusion='')]
    return dict(data=dict(objects=objects, images=[image]), research=dict(images=[])), difficulty


def test_stable_people_not_rows_or_gt_and_conditions_separate():
    bundle, difficulty = fixture([
        annotation('a', 'w1'), annotation('repeat', 'w1'), annotation('b', 'w2'),
        annotation('c', 'w3', 'semi'),
        annotation('excluded', 'w4', cleaning_disposition='excluded_by_review',
                   independent_vote_eligible=False, independent_vote_reasons=['excluded_by_review']),
        dict(object_id='gt', object_kind='gt_original', image_id='i'),
        dict(object_id='revision', object_kind='gt_manual_revision', image_id='i'),
        dict(object_id='fused', object_kind='fusion', image_id='i')])
    pools, records = build_pool_gate(bundle, difficulty)
    manual = next(r for r in pools if r['condition'] == 'manual')
    assert manual['n_effective_records'] == 3 and manual['n_effective_workers'] == 2
    assert manual['effective_worker_ids'] == ['w1', 'w2']
    assert manual['duplicate_effective_worker_ids'] == ['w1']
    assert not manual['pool_min3_pass']
    assert next(r for r in pools if r['condition'] == 'semi')['n_effective_workers'] == 1
    assert next(r for r in pools if r['condition'] == 'oos')['n_effective_workers'] == 0
    assert len(records) == 5
    assert all(r['object_id'] not in {'gt', 'revision', 'fused'} for r in records)


def test_three_valid_responses_need_no_complete_scores_or_k_filter():
    bundle, difficulty = fixture([annotation(str(i), 'w'+str(i)) for i in range(3)])
    bundle['trajectory'] = [dict(k=1), dict(k=2), dict(k=3)]
    before = deepcopy(bundle)
    pools, records = build_pool_gate(bundle, difficulty)
    pool = next(r for r in pools if r['condition'] == 'manual')
    assert pool['pool_min3_pass'] and pool['pool_analysis_eligible']
    assert all(r['pool_analysis_eligible'] for r in records)
    assert bundle == before


def test_historical_image_holds_and_gt_do_not_erase_people():
    objects = [annotation(str(i), 'w'+str(i)) for i in range(3)]
    objects[0]['main_consensus_gate'] = dict(status='hold_all_analysis', reasons=['explicit_user_hold'])
    objects[1]['main_quality_gate'] = dict(status='hold_reference_quality', reasons=['explicit_reference_error'])
    bundle, difficulty = fixture(objects)
    bundle['research']['images'] = [dict(image_id='i', gt_substantive_error_mark=True)]
    difficulty[0].update(gt_error_excluded=True, difficulty_analysis_eligible=False,
                         difficulty_analysis_exclusion='gt_error')
    pools, records = build_pool_gate(bundle, difficulty)
    pool = next(r for r in pools if r['condition'] == 'manual')
    assert pool['n_effective_workers'] == 3 and pool['pool_min3_pass']
    assert not pool['pool_analysis_eligible']
    assert {'historical_consensus:hold_all_analysis', 'historical_quality:hold_reference_quality',
            'historical_gt_substantive_error', 'current_gt_error'} <= set(pool['image_exclusion_reasons'])
    assert all(r['pool_vote_eligible'] and not r['pool_analysis_eligible'] for r in records)


def test_special_is_separate_from_ordinary_and_zero_pools_remain():
    objects = [annotation(str(i), 'w'+str(i)) for i in range(3)]
    bundle, difficulty = fixture(objects)
    difficulty[0].update(current_class='单列', difficulty_analysis_eligible=False,
                         difficulty_analysis_exclusion='special_or_pending')
    pools, _ = build_pool_gate(bundle, difficulty)
    manual = next(r for r in pools if r['condition'] == 'manual')
    assert manual['pool_analysis_eligible'] and not manual['ordinary_difficulty_eligible']
    assert len(pools) == 3


def test_pending_and_borrowed_are_not_effective_and_scope_hold_has_priority():
    bundle, difficulty = fixture([
        annotation('a', 'w1'), annotation('b', 'w2'),
        annotation('pending', 'w3', cleaning_disposition='retained_pending', independent_vote_eligible=False,
                   independent_vote_reasons=['retained_pending']),
        annotation('borrowed', 'w4', independent_vote_eligible=False,
                   independent_vote_reasons=['borrowed_points_not_independent_complete_response'])])
    difficulty[0].update(difficulty_analysis_eligible=False,
                         difficulty_analysis_exclusion='target_scope_unresolved')
    pools, records = build_pool_gate(bundle, difficulty)
    manual = next(r for r in pools if r['condition'] == 'manual')
    assert manual['n_effective_workers'] == 2
    assert {'effective_workers_below_3', 'current_target_scope_unresolved'} <= set(manual['pool_exclusion_reasons'])
    assert not records[-1]['pool_vote_eligible']
