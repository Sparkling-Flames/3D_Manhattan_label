from copy import deepcopy

from tools.thesis_main.analysis.same_room_relation_adoption_20261016 import adopt_relations
from tools.thesis_main.analysis.same_room_b8l2_20261016 import confirmed_relation


def registry(status='viewed_per_user_statement'):
    raw = dict(physical_same='支持', main_visual_alignment='一致', extent_alignment='预期相近',
               difficulty_similarity='存在明显差异', note='', status='')
    group = dict(review_code='G001', image_ids=['a','b'], numbers=[1,2], building='B',
        viewed=True, viewed_basis='all reviewed', review_state=status, raw_current=raw, interpretation={})
    candidate = dict(candidate_id='G001', source_group_codes=['G001'], image_ids=['a','b'],
        numbers=[1,2], physical_same_supported=True, comparable_for_prediction=True,
        oos_pending=False, review_state=status, subset_scope='whole_group', difficulty_similarity='存在明显差异')
    return dict(groups=[group], candidates=[candidate])


def test_review_state_and_difficulty_similarity_are_not_new_admission_gates():
    for state in ['explicit_confirmed','viewed_per_user_statement','explicit_discussion']:
        source=registry(state);before=deepcopy(source)
        pairs,candidates=adopt_relations(source)
        assert pairs['a','b']['analysis_layer']=='user_classified_comparable'
        assert confirmed_relation(pairs['a','b'])=='user_classified_comparable'
        assert source==before


def test_negative_unknown_and_no_transitive_extension_are_preserved():
    source=registry();other=deepcopy(source['groups'][0]);other.update(review_code='G002',image_ids=['b','c'])
    source['groups'].append(other)
    pairs,_=adopt_relations(source)
    assert ('a','c') not in pairs
    for value in ['不支持','待定']:
        source=registry();source['groups'][0]['raw_current']['physical_same']=value
        pairs,_=adopt_relations(source)
        assert not pairs['a','b']['physical_adopted']


def test_explicit_subgroup_keeps_parent_physical_room_but_not_cross_subset_comparability():
    source=registry('explicit_discussion')
    source['groups'][0].update(review_code='G095',image_ids=['a','b','c'],numbers=[12,19,22])
    source['groups'][0]['interpretation']={'subgroups':[[12,19],[22]],'interpretation':'前三张可以配对，后两张可以配对'}
    source['candidates'][0].update(candidate_id='G095-S1',source_group_codes=['G095'],
        comparable_for_prediction=False,subset_scope='explicit_split')
    pairs,candidates=adopt_relations(source)
    assert pairs['a','b']['analysis_layer']=='user_classified_comparable'
    assert pairs['a','c']['physical_adopted']
    assert pairs['a','c']['analysis_layer']=='user_classified_other_scope'
    assert candidates[0]['adopted_comparable']


def test_view_information_or_doorway_location_does_not_negate_existing_scope_classification():
    source=registry('explicit_discussion')
    source['groups'][0]['raw_current']['note']='71是站在门洞交界处了'
    source['candidates'][0].update(candidate_id='G172', comparable_for_prediction=False, subset_scope='unclear_subset')
    pairs,candidates=adopt_relations(source)
    assert pairs['a','b']['scope_comparable']
    assert pairs['a','b']['analysis_layer']=='user_classified_comparable'


def test_substantive_opposing_classifications_remain_a_conflict():
    source=registry();opposing=deepcopy(source['groups'][0])
    opposing['review_code']='G002';opposing['raw_current']['physical_same']='不支持'
    source['groups'].append(opposing)
    pairs,_=adopt_relations(source)
    assert pairs['a','b']['analysis_layer']=='content_disputed'
    assert not pairs['a','b']['physical_adopted']
