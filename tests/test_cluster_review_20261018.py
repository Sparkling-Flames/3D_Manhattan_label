import itertools
import json
from pathlib import Path

import numpy as np

from tools.thesis_main.analysis.build_cluster_review_20261018 import affinity_partition, objective


def partitions(n):
    if n == 0:
        yield []
        return
    for groups in partitions(n - 1):
        yield groups + [[n - 1]]
        for k in range(len(groups)):
            yield [g + [n - 1] if i == k else g[:] for i, g in enumerate(groups)]


def test_global_matches_exhaustive_and_respects_diameter():
    d = np.array([[0, 1, 4, 8], [1, 0, 2, 7], [4, 2, 0, 3], [8, 7, 3, 0.]])
    for cut in [2., 4., 9.]:
        groups, status = affinity_partition(d, cut)
        feasible = [g for g in partitions(4) if all(d[a, b] <= cut for s in g for a, b in itertools.combinations(s, 2))]
        assert status['optimal']
        assert sorted(i for g in groups for i in g) == list(range(4))
        assert all(d[a, b] <= cut for g in groups for a, b in itertools.combinations(g, 2))
        assert abs(objective(d, groups, cut) - max(objective(d, g, cut) for g in feasible)) < 1e-8


def test_singleton_and_no_compatible_edges():
    assert affinity_partition(np.zeros((1, 1)), 9)[0] == [[0]]
    assert affinity_partition(np.array([[0., 10], [10, 0]]), 9)[0] == [[0], [1]]


def test_delivered_input_and_common_distance_partitions():
    root = Path(__file__).resolve().parents[1]
    payload = json.loads((root / 'research/statistics/cluster_review_20261018/review.json').read_text(encoding='utf-8'))
    snapshot = json.loads((root / payload['source']).read_text(encoding='utf-8'))
    original = {r['object_id']: r for p in snapshot['images'] for r in p['records']}
    page = root / 'research/statistics/research_explorer_v1_r2_20261017'
    assert len(payload['images']) == 8
    assert sum(len(p['records']) for p in payload['images']) == 191
    for p in payload['images']:
        assert (page / p['photo']).is_file()
        for r in p['records']:
            assert r['points'] == original[r['object_id']]['points']
            assert 'reference' not in r and 'quality' not in r
        n = len(p['records'])
        distances = {(r['a'], r['b']): r['d'] for r in p['pairs']}
        assert len(distances) == n * (n-1)//2
        for s in p['states']:
            for gs in s['groups'].values():
                assert sorted(i for g in gs for i in g) == list(range(n))
                for g in gs:
                    for a, b in itertools.combinations(sorted(g), 2):
                        assert distances[a,b] is not None and distances[a,b] <= s['cut']
            assert all(r['optimal'] for r in s['solver'])
            assert s['objective']['affinity'] >= s['objective']['complete'] - 1e-7
