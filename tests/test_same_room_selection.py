import copy

import pytest

from tools.thesis_main.analysis.materialize_same_room_selection import assemble, annotation_coverage, reconcile_spatial_history


def test_later_ai_does_not_erase_earlier_human_classification():
    initial = [dict(image_id=i, user_type='卧室' if i != 'd' else '复合／待定', user_doorway='确认',
                    user_room='r1', user_artifact='未见明显异常', user_status='已复核', user_note='') for i in 'abcd']
    last = [dict(image_id=r['image_id'], source_user=r, discussion=None, user_revision={},
                 current_classification=dict(coarse_type='开放复合空间', functions='厨房、起居', focus='厨房',
                                             boundary='暂不归入')) for r in initial]
    for row in last:
        row['prefill'] = copy.deepcopy(row['current_classification'])
    last[1]['discussion'] = dict(record_path='discussion.md', batch_records=[dict(case_id='B01',
        boundary_decisions=[dict(image_id='b', state='低优先级候选')])])
    review = dict(saved_at='group_time', source_user=dict(saved_at='later_time',
        source_user=dict(rows=initial, saved_at='dispute_time'), rows=last))
    result = dict(images=[dict(image_id=i, building='b', number=n, in_previous_disagreement_filter=i in 'bc',
        group_codes=['G001'] if i == 'c' else [], doorway_user_comment_codes=['G001'] if i == 'c' else [],
        annotation_boundary_comment_codes=[]) for n, i in enumerate('abcd', 1)],
        groups=[dict(review_code='G001', image_ids=['c'], raw_current=dict(note='3在门洞'), interpretation=dict(doorway=[3]))], candidates=[])
    baseline = copy.deepcopy(review)
    reconcile_spatial_history(result, review, dict(source_user=dict(saved_at='initial', rows=initial), cases=[]), dict(rows=[]))
    assert review == baseline
    a, b, c, d = result['images']
    assert a['spatial_classification']['coarse_type'] == '卧室'
    assert a['spatial_ai_proposal']['coarse_type'] == '开放复合空间'
    assert a['doorway_reconciliation']['current_working_label'] == '确认'
    assert b['spatial_classification']['coarse_type'] == '开放复合空间'
    assert b['spatial_classification']['boundary'] == '暂不归入'
    assert b['doorway_reconciliation']['current_working_label'] == '否'
    assert c['doorway_reconciliation']['source'] == '最新整组评论.G001'
    assert d['spatial_classification']['coarse_type'] is None and d['legacy_coarse_type_raw'] == '复合／待定'
    assert result['spatial_reconciliation_summary']['initial_dispute_target_images'] == 0


def test_people_are_not_person_images_and_semi_is_retained():
    result = dict(images=[dict(image_id=i) for i in ['a', 'b', 'c']],
                  groups=[dict(image_ids=['a', 'b'])], candidates=[dict(image_ids=['b'])])
    rows = [dict(image_id=i, worker_id=w, assistance_exposure=m, unassisted_manual_included=m == 'none')
            for i, w, m in [('a', '1', 'none'), ('a', '1', 'none'), ('b', '1', 'model_preannotation'),
                            ('b', '2', 'model_preannotation')]]
    annotation_coverage(result, rows)
    g = result['groups'][0]['annotation_counts']
    assert g['n_people']['any'] == 2 and g['n_person_images']['any'] == 3
    assert g['n_canonical_records'] == 4 and g['n_people_both_modes'] == 1
    assert g['n_semi_images'] == g['n_semi_only_images'] == 1
    assert result['candidates'][0]['annotation_counts']['n_people']['manual'] == 0
    assert result['candidates'][0]['annotation_counts']['n_people']['semi'] == 2
    assert result['images'][2]['annotation_counts']['n_people']['any'] == 0


def test_review_scope_subset_and_difficult_images_are_not_lost():
    fields = dict(physical_same='支持', main_visual_alignment='一致', extent_alignment='预期相近',
                  difficulty_similarity='预期相近', decision='优先候选', status='', note='排除1，1为门洞')
    ids = ['b_1', 'b_2', 'b_3']
    group_id = '|'.join(ids)
    images = [dict(image_id=i, building='b', number=n) for n, i in enumerate(ids + ['b_4'], 1)]
    source = [dict(image_id=i, cross_reviews=[dict(verdict='部分支持')] if i == 'b_2' else [],
                   discussion=None, user_revision={}, current_classification=dict(boundary='暂不归入'),
                   changed_fields=[], source_user={}) for i in ids + ['b_4']]
    review = dict(schema='same_room_pair_user_review_v1', form_version=3, saved_at='now', images=images,
        source_user=dict(rows=source), pairs=[dict(pair_id='p', image_ids=ids[:2])], group_reviews=[dict(
            group_id=group_id, image_ids=ids, pair_ids=['p'], current=fields,
            prefill=fields, user_revision={}, changed_fields=[])])
    notes = dict(rows=[dict(group_id=group_id, review_code='G001', original_note=fields['note'],
        interpretation='保留门洞图作为对照', issue_tags=['门洞范围差异'], affected_numbers=[1],
        core=[2, 3], doorway=[1], scope='explicit_subset')])
    before = copy.deepcopy(review)
    result = assemble(review, notes, {'b_2': dict(n_people_any=25, n_people_manual_included=20)})
    assert review == before
    c = result['candidates'][0]
    assert c['numbers'] == [2, 3] and c['n_images'] == 2 and c['n_manual_k_ge_19'] == 1
    assert c['low_ambiguity_batch'] == 3 and c['disagreement_research_candidate']
    assert not c['issue_tags'] and c['original_group_issue_tags'] == ['门洞范围差异']
    assert result['summary']['images_shown_in_group_review'] == 3
    assert result['summary']['images_not_shown_in_group_review'] == 1
    assert not result['images'][3]['same_room_group_review_viewed']
    assert result['groups'][0]['viewed'] and result['groups'][0]['original_status'] == ''
    assert result['images'][0]['doorway_user_comment_codes'] == ['G001']
    assert result['images'][0]['spatial_review_provenance'] == 'ai_or_legacy_not_personally_reviewed_this_round'
    assert result['images'][1]['spatial_review_provenance'] == 'user_reviewed_disagreement_subset'
    assert result['images'][2]['historical_coverage'].startswith('not_found_in_this_snapshot')
    with pytest.raises(ValueError, match='非空评论'):
        assemble(review, dict(rows=[]), {})
    uncertain = copy.deepcopy(notes)
    uncertain['rows'][0].update(scope='unclear_subset', oos='suspected')
    c = assemble(review, uncertain, {})['candidates'][0]
    assert c['low_ambiguity_batch'] is None and c['oos_pending']
    assert not c['comparable_for_prediction']
