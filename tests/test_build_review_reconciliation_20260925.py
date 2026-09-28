import json

import pytest

from tools.thesis_main.analysis.build_review_reconciliation_20260925 import (
    ROOT, add_comment_and_cluster_questions, add_scene_point_checks, collect_events, derive_image_review, historical_evidence, supported_rooms, worker_summary,
)


def test_review_events_keep_both_authors_and_require_comment_interpretation():
    row = dict(id='a', image_id='image', code='house-01', worker='W001', condition='manual')
    decision = dict(image_id='image', code='house-01', worker_id='W001', condition='manual',
                    verdict='retain', comment='同图', updated_at='2026-09-25T00:00:00Z')
    documents = {who: dict(schema='consensus_visual_review_decisions_v1',
        contract_version='consensus_research_20260923_v1', decisions={'a': decision})
        for who in ['user', 'yizheng']}
    documents['yizheng'] = dict(documents['yizheng'], decisions={'a': dict(decision, verdict='pending')})
    notes = {who + ':a': dict(summary='引用同图，当前指代待核。', targets=['image'],
        topics=[], related_workers=[], anchor_event_ids=[], unresolved_reference=True)
        for who in documents}
    events = collect_events(documents, {'a': row}, notes)
    assert [e['verdict'] for e in events] == ['retain', 'pending']
    assert all(e['comment'] == '同图' for e in events)
    review = derive_image_review([row], events, {}, {'a': dict(repairs=[])})
    assert {'pending', 'yizheng', 'followup'} <= set(review['flags'])
    assert 'conflict' not in review['flags']
    assert review['reviewed_ids'] == ['a']

    with pytest.raises(ValueError, match='释义'):
        collect_events(documents, {'a': row}, {})


def test_different_option_meanings_do_not_create_reaudit_requirements():
    rows = [dict(id='a', worker='W001', condition='manual')]
    events = [dict(canonical_annotation_id='a', reviewer='user', verdict='retain'),
              dict(canonical_annotation_id='a', reviewer='yizheng', verdict='gt_scope')]
    review = derive_image_review(rows, events, {}, {'a': dict(repairs=[])})
    assert not review['followup_ids'] and not review['image_followup']
    assert 'followup' not in review['flags'] and not review['questions']
    assert review['reviewed_ids'] == ['a']
    events[0]['verdict'] = 'representation'
    optional = dict(questions=[dict(kind='scope', title='需要区分范围', evidence_event_ids=[], workers=[])])
    review = derive_image_review(rows, events, optional, {'a': dict(repairs=[])})
    assert not review['followup_ids'] and not review['image_followup']
    assert 'representation' in review['flags'] and 'comment_questions' in review['flags']


def test_image_hold_does_not_spread_across_room_or_worker():
    row = dict(id='a', image_id='i1', code='h-01', worker='W001', condition='manual')
    review = derive_image_review([row], [], {'doorway_hold': True}, {'a': dict(repairs=[])})
    assert review['geometry_hold'] and review['quality_hold']
    ordinary = derive_image_review([dict(row, id='b', image_id='i2')], [], {}, {'b': dict(repairs=[])})
    assert not ordinary['geometry_hold']
    registry = {'candidates': [dict(candidate_id='G1', physical_same_supported=True,
        comparable_for_prediction=False, image_ids=['i1', 'i2'], source_group_codes=['G1'])]}
    rooms, by_image = supported_rooms(registry, {'i1', 'i2', 'i3'})
    assert by_image == {'i1': 'G1', 'i2': 'G1'}
    assert not rooms[0]['comparable_for_prediction']
    registry['candidates'].append(dict(registry['candidates'][0], candidate_id='G2'))
    with pytest.raises(ValueError, match='同房'):
        supported_rooms(registry, {'i1', 'i2'})


def test_similar_exclusion_and_user_image_context_recall_specific_answers():
    annotations = [dict(canonical_annotation_id=k, worker_id='W00'+str(i), raw_condition='manual',
        screening=dict(cluster_coverage='matched_effective_points', clusters=[dict(method='affinity', label=1 if k in 'ab' else 2)]))
        for i,k in enumerate('abc',1)]
    events = [dict(event_id='user:a', canonical_annotation_id='a', reviewer='user', worker_id='W001', condition='manual', verdict='invalid', comment='门洞背景',
                   interpretation=dict(targets=['image'], topics=['图片条件'])),
              dict(event_id='user:b', canonical_annotation_id='b', reviewer='user', worker_id='W002', condition='manual', verdict='retain'),
              dict(event_id='yizheng:c', canonical_annotation_id='c', reviewer='yizheng', worker_id='W003', condition='manual', verdict='retain')]
    review = dict(followup_ids=[], questions=[], flags=['doorway'], history=[])
    add_comment_and_cluster_questions(review, annotations, events)
    assert review['followup_ids'] == ['a','b','c']
    assert {r['kind'] for r in review['followup_reasons']} == {'similar_exclusion','reviewer_context','exclusion_review'}
    assert all('verdict' not in r for r in review['followup_reasons'])
    ordinary = dict(followup_ids=[], questions=[], flags=[], history=[])
    add_comment_and_cluster_questions(ordinary, annotations, events)
    assert ordinary['followup_ids'] == ['a','b'], '普通图片条件评论不能让一正全图重审'
    historical = dict(followup_ids=[], questions=[], flags=[], history=[dict(quote='斜墙开口，我个人倾向于oos')])
    add_comment_and_cluster_questions(historical, annotations, events)
    assert 'c' in historical['followup_ids'], '历史具体OOS背景需提供给一正复核'


def test_all_exclusions_and_yizheng_only_images_are_recalled():
    annotation = dict(canonical_annotation_id='a', worker_id='W001', raw_condition='manual',
        screening=dict(cluster_coverage='not_covered_or_changed', clusters=[]))
    event = dict(event_id='yizheng:a', canonical_annotation_id='a', reviewer='yizheng',
                 worker_id='W001', condition='manual', verdict='invalid', comment='')
    review = dict(followup_ids=[], questions=[], flags=[], history=[])
    add_comment_and_cluster_questions(review, [annotation], [event])
    assert review['followup_ids'] == ['a']
    assert {'excluded', 'recheck_yizheng'} <= set(review['flags'])
    assert {'exclusion_review', 'yizheng_only'} <= {r['kind'] for r in review['followup_reasons']}


def test_scene_point_checks_recall_without_deciding_exclusion():
    review = dict(geometry_hold=True, reviewed_ids=['a','b'], followup_ids=[], followup_reasons=[], questions=[], flags=[])
    audits = {'a':dict(effective_point_labels=list(range(6)), pairing={'status':'existing_accepted_pairing'}),
              'b':dict(effective_point_labels=list(range(8)), pairing={'status':'unavailable','reason':'ambiguous_horizontal_assignment'})}
    add_scene_point_checks(review,audits)
    assert review['followup_ids']==['a','b']
    assert all('verdict' not in r for r in review['followup_reasons'])


def test_user_scene_retention_rule_is_not_applied_to_yizheng():
    events=[dict(event_id='user:a',canonical_annotation_id='a',reviewer='user',worker_id='W001',condition='manual',verdict='gt_scope',comment='门洞交界'),
            dict(event_id='user:b',canonical_annotation_id='b',reviewer='user',worker_id='W002',condition='manual',verdict='retain',comment='勉强能看')]
    review=dict(followup_ids=[],questions=[],flags=[],history=[])
    add_comment_and_cluster_questions(review,[],events)
    assert any(r['kind']=='user_scene_retention' for r in review['followup_reasons'])
    assert review['followup_ids']==['a','b']
    for e in events:e['reviewer']='yizheng'
    review=dict(followup_ids=[],questions=[],flags=[],history=[])
    add_comment_and_cluster_questions(review,[],events)
    assert not any(r['kind']=='user_scene_retention' for r in review['followup_reasons'])


def test_same_image_reference_does_not_become_its_own_background():
    events=[dict(event_id='user:a',canonical_annotation_id='a',reviewer='user',verdict='retain',comment='标得不错，同图',interpretation=dict(targets=['image'])),
            dict(event_id='user:b',canonical_annotation_id='b',reviewer='user',verdict='retain',comment='同图',interpretation=dict(targets=['image']))]
    review=dict(followup_ids=[],questions=[],flags=[],history=[])
    add_comment_and_cluster_questions(review,[],events)
    assert review['shared_image_context_event_ids']==[]
    assert all(x['status']=='missing_current_json_context' for x in review['same_image_links'])
    events.append(dict(event_id='user:c',canonical_annotation_id='c',reviewer='user',verdict='retain',comment='这图GT顺序需调整',interpretation=dict(targets=['reference'])))
    add_comment_and_cluster_questions(review,[],events)
    assert review['shared_image_context_event_ids']==['user:c']


def test_historical_doorway_suspects_are_preserved_without_new_verdicts():
    history = historical_evidence(ROOT)
    image = 'UwV83HsGsw3_16af52545aff47afb4d7b330a49091a2'
    related = [h for h in history[image] if h.get('doorway_related')]
    assert related and '疑似' in related[0]['quote']
    assert '暂缓不等于' in related[0]['interpretation']
    assert all('verdict' not in h for rows in history.values() for h in rows)


def test_worker_denominators_keep_conditions_and_unreviewed_responses():
    base = dict(worker='W001', image_id='i1', condition='manual')
    index = {'a': dict(base, id='a'), 'b': dict(base, id='b', condition='semi'),
             'c': dict(base, id='c', image_id='i2')}
    events = [dict(canonical_annotation_id='a', reviewer='user', verdict='invalid'),
              dict(canonical_annotation_id='a', reviewer='yizheng', verdict='pending')]
    audits = {k: dict(repairs=[]) for k in index}
    audits['a']['current_review_questions'] = [{'comment': '漏一对待核'}]
    rows = worker_summary(index, events, {'i1': {'geometry_hold': True}}, audits)
    assert sum(r['accepted_responses'] for r in rows) == 3
    assert sum(r['old_reviewed_responses'] for r in rows) == 1
    assert sum(r['not_in_old_review'] for r in rows) == 2
    assert sum(r['reviewer_options']['user'].get('invalid', 0) for r in rows) == 1
    assert sum(r['reviewer_options']['yizheng'].get('pending', 0) for r in rows) == 1
    assert sum(r['repair_review_candidates'] for r in rows) == 1
    assert all(r['final_confirmed_invalid'] == 0 for r in rows)
    assert {(r['condition'], r['stratum']) for r in rows} == {
        ('manual', 'doorway_oos'), ('semi', 'doorway_oos'), ('manual', 'outside_review_images')}
