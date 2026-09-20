"""Local image distances, partition guarantees and human mapping boundaries."""
import numpy as np
import pytest

from tools.thesis_main.analysis.clustering_release.local_points import pixel_distance, partition, endpoint_rows
from tools.thesis_main.analysis.clustering_release.history_analysis import next_uncovered
from tools.thesis_main.analysis.paired_split_research.study import angular


def test_local_distance_seam_and_endpoint_roles():
    assert pixel_distance([[1023, 100]], [[1, 100]])[0, 0] == 2
    for y in (100, 300, 400):
        assert pixel_distance([[500, y]], [[500, y+5]])[0, 0] == 5
        assert angular([[500, y]], [[500, y+5]])[0, 0] == pytest.approx(5*180/512)
    assert angular([[500, 100]], [[505, 100]])[0, 0] < angular([[500, 250]], [[505, 250]])[0, 0]


def test_partition_tradeoff_and_permutation():
    ids = ['c', 'a', 'b']
    d = np.array([[0., 8., 16.], [8., 0., 8.], [16., 8., 0.]])
    complete, _ = partition(d, ids, 9, 'complete')
    representative, centres = partition(d, ids, 9, 'representative')
    assert len(set(complete)) == 2 and len(set(representative)) == 1
    assert centres == ['a']
    order = [2, 0, 1]
    for kind in ('complete','representative'):
        original, original_reps = partition(d, ids, 9, kind)
        labels, reps = partition(d[np.ix_(order, order)], [ids[i] for i in order], 9, kind)
        assert dict(zip(ids, original)) == dict(zip([ids[i] for i in order], labels))
        assert reps == original_reps
    # Coverage uses pair distances, never labels from a partition.
    assert next_uncovered(d, 1, 9) == pytest.approx(1/3)


def test_human_mapping_is_complete_and_role_preserving():
    a = {'p': np.array([[100., 100.], [100., 400.], [105., 101.], [105., 399.]]),
         'links': np.array([[0, 1], [2, 3]])}
    b = {'p': a['p'][[2, 3, 0, 1]], 'links': np.array([[0, 1], [2, 3]])}
    assert max(r['image_px'] for r in endpoint_rows(a, b, [2, 1])) == 0
    for bad in ([2], [1, 1], [1, 3]):
        with pytest.raises(ValueError):
            endpoint_rows(a, b, bad)
    assert np.array_equal(a['p'], [[100, 100], [100, 400], [105, 101], [105, 399]])
