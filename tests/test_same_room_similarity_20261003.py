from tools.thesis_main.analysis.same_room_similarity_20261003 import relation_index, compare_profiles


def test_relations_do_not_propagate_and_profiles_use_common_people():
    candidates = [dict(candidate_id='a', image_ids=['A', 'B'], physical_same_supported=True,
                       comparable_for_prediction=True, oos_pending=False, review_state='explicit_confirmed'),
                  dict(candidate_id='b', image_ids=['B', 'C'], physical_same_supported=True,
                       comparable_for_prediction=False, oos_pending=False, review_state='explicit_discussion')]
    relations = relation_index(candidates)
    assert relations[('A', 'B')]['tier'] == 'confirmed_comparable'
    assert relations[('B', 'C')]['tier'] == 'supported_other'
    assert ('A', 'C') not in relations
    result = compare_profiles({'p1': .9, 'p2': .7, 'p3': .5, 'only_a': 0},
                              {'p1': .8, 'p2': .6, 'p3': .4, 'only_b': 1})
    assert result['n_common'] == 3
    assert abs(result['worker_iou_spearman'] - 1) < 1e-12
    assert abs(result['common_mean_iou_gap'] - .1) < 1e-12
    assert compare_profiles({'a': .5, 'b': .5}, {'a': .8, 'b': .7})['worker_iou_spearman'] is None
