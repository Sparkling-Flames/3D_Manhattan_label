import pandas as pd
import pytest

from tools.thesis_main.analysis.review_worker_mixture_replay_20260908 import candidate_counts, check_profile, paired_summary, small_partitions, expected_geometry


def test_combinations_count_distinct_workers_and_keep_unknown_pool_separate():
    assert candidate_counts(3, 2, 1, 4) == {'A_only': 0, 'AB_balanced': 3, 'B_only': 0, 'random_AB': 5, 'random_all': 15}
    assert candidate_counts(1, 1, 8, 2)['random_AB'] == 1
    with pytest.raises(ValueError):
        candidate_counts(1, 1, 0, 3)


def test_target_building_cannot_train_worker_profile():
    row = {'fold': 'target', 'training_buildings': '["other"]', 'label': 'high', 'fit_status': 'usable'}
    assert check_profile(row) == 'A'
    with pytest.raises(ValueError, match='target_in_training'):
        check_profile(dict(row, training_buildings='["target"]'))


def test_paired_summary_does_not_compare_different_contexts_or_missing_arms():
    data = pd.DataFrame([
        dict(building_id='b1', context_key='c1', split_id='s1', arm='A', value=2.),
        dict(building_id='b1', context_key='c1', split_id='s1', arm='B', value=1.),
        dict(building_id='b1', context_key='c2', split_id='s2', arm='A', value=100.),
        dict(building_id='b2', context_key='c3', split_id='s3', arm='B', value=100.),
        dict(building_id='b3', context_key='c4', split_id='s4', arm='A', value=5.),
        dict(building_id='b3', context_key='c4', split_id='s4', arm='B', value=1.),
    ])
    row = paired_summary(data, ['A', 'B'])
    assert row['paired_splits'] == 2
    assert row['paired_contexts'] == 2
    assert row['paired_buildings'] == 2
    assert row['means']['A'] == 3.5
    assert row['means']['B'] == 1.


def test_independent_partition_and_ambiguous_validation_are_not_forced_unique():
    assert len(small_partitions(3, ((0,1),(1,2)))) == 2
    distances={('a','b'):10.,('v','a'):5.,('v','b'):5.,('w','a'):0.,('w','b'):10.}
    state,_,values=expected_geometry(['a','b'],['v','w'],distances)
    assert state=='unique'
    assert values['validation_ambiguous_fraction']==.5
    assert pd.isna(values['distribution_tv'])
