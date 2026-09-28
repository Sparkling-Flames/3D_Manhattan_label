import numpy as np

from tools.thesis_main.analysis.cluster_threshold_audit_20260921 import partition_stats


def test_nontransitive_neighbours_require_split_or_far_join():
    # A-B and B-C are close, while A-C is far: no partition preserves all edges.
    d = np.array([[0., 20., 40.], [20., 0., 20.], [40., 20., 0.]])
    a = partition_stats(d, ['a', 'b', 'c'], 'complete', 25.6)
    b = partition_stats(d, ['a', 'b', 'c'], 'representative', 25.6)
    assert (a['near_split_pairs'], a['far_join_pairs']) == (1, 0)
    assert (b['near_split_pairs'], b['far_join_pairs']) == (0, 1)
    assert a['singleton_reasons'] == {'count_unique': 0, 'geometry_isolated': 0, 'partition_isolated': 1}
    # An unequal-count sentinel cannot become a measured geometric residual.
    e = np.array([[0., 1e6], [1e6, 0.]])
    z = partition_stats(e, ['a', 'b'], 'complete', 51.2)
    assert z['singleton_reasons']['count_unique'] == 2
