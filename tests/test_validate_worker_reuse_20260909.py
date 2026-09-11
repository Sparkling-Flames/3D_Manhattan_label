import numpy as np
import pandas as pd
import pytest

from tools.thesis_main.analysis.validate_worker_reuse_20260909 import (
    crossfit, partition_outcomes, paired_means, subset_values, adjusted_rand, medoid_reference, project_orders,
)


def test_crossfit_never_uses_target_building_for_groups():
    data = pd.DataFrame([
        dict(building_id=b, image_id=b, context_key=b, worker_id=str(w),
             canonical_annotation_id=f'{b}{w}', value=10*i+w)
        for i, b in enumerate('abcd') for w in range(1, 7)
    ])
    first, _ = crossfit(data)
    data.loc[(data.building_id == 'a') & (data.worker_id == '1'), 'value'] += 1000
    second, _ = crossfit(data)
    a = first[first.heldout_building == 'a'].sort_values(['model', 'worker_id'])
    b = second[second.heldout_building == 'a'].sort_values(['model', 'worker_id'])
    pd.testing.assert_frame_equal(a.reset_index(drop=True), b.reset_index(drop=True))
    assert all(row.heldout_building not in row.training_buildings.split('|') for row in first.itertuples())


def test_exact_subsets_use_distinct_people_and_hard_count_clusters():
    frame = pd.DataFrame(dict(worker_id=['1', '2', '3', '4'], reference=[1., 3., 5., 7.]))
    distance = np.zeros((4, 4))
    values = subset_values(frame, distance, np.array([8, 8, 10, 10]), np.ones(4, bool), 4, 6.)
    assert values['subsets'].tolist() == [[0, 1, 2, 3]]
    assert values['reference'].tolist() == [4.]
    assert values['supported_clusters'].tolist() == [2.]
    assert values['multi_supported'].tolist() == [1.]
    with pytest.raises(ValueError, match='duplicate_worker'):
        subset_values(frame.assign(worker_id='same'), distance, np.array([8]*4), np.ones(4, bool), 4, 6.)
    assert partition_outcomes(4, 0)['supported_clusters'] == 0
    # A-B-C path has multiple v5 maximum-clique partitions; do not choose one.
    assert partition_outcomes(3, 5)['unknown'] == 1
    distances = np.ones((4, 4)); np.fill_diagonal(distances, 0)
    distances[3, :3] = distances[:3, 3] = 10.
    score, tied = medoid_reference(np.array([1., 3., 5., 20.]), distances, np.array([[0, 1, 2, 3]]))
    assert score.tolist() == [3.] and tied.tolist() == [1.]
    score, tied = medoid_reference(np.array([1., 3.]), np.array([[0., 5.], [5., 0.]]), np.array([[0, 1]]))
    assert score.tolist() == [2.] and tied.tolist() == [1.]
    assert project_orders(['1', '2', '3'], [['4', '3', '1', '2']], 2).tolist() == [[2, 0]]
    with pytest.raises(ValueError, match='projected_order'):
        project_orders(['1', '2', '3'], [['1', '1', '2', '3']], 2)


def test_paired_summary_does_not_mix_different_image_support():
    d = pd.DataFrame([
        dict(image_id='x', building_id='b', arm='AA', value=1.),
        dict(image_id='x', building_id='b', arm='AB', value=2.),
        dict(image_id='y', building_id='b', arm='AA', value=100.),
        dict(image_id='z', building_id='c', arm='AA', value=3.),
        dict(image_id='z', building_id='c', arm='AB', value=4.),
    ])
    result = paired_means(d, ['AA', 'AB'])
    assert result['images'] == 2 and result['buildings'] == 2
    assert result['means'] == {'AA': 2., 'AB': 3.}
    with pytest.raises(ValueError, match='duplicate_arm'):
        paired_means(pd.concat([d, d.iloc[:1]]), ['AA', 'AB'])
    assert adjusted_rand([0, 0, 1, 1], [1, 1, 0, 0]) == 1
    assert adjusted_rand([0, 0, 1, 1], [0, 1, 0, 1]) == pytest.approx(-.5)
