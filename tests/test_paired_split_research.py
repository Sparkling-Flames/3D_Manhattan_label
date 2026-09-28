"""Independent checks of the received experiment, not a new clustering policy."""
import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd

from tools.thesis_main.analysis.paired_split_research import study


ROOT = Path(__file__).resolve().parents[1] / 'analysis_results/paired_split_research_received_20260920'


def test_fixed_distances_against_original_endpoints():
    rows = {r['canonical_annotation_id']: r for r in
            map(json.loads, gzip.open(ROOT / 'inputs/responses.jsonl.gz', 'rt', encoding='utf-8'))}
    result = ROOT / 'local_recheck/results'
    e = pd.read_csv(result / 'all_fixed_endpoint_comparisons.csv.gz')
    def vectors(ids, indices):
        p = np.array([rows[c]['effective_points_1024x512'][int(i)-1] for c, i in zip(ids, indices)])
        longitude = p[:, 0] * (2*np.pi/1024)
        latitude = ((p[:, 1]+.5)/512-.5)*np.pi
        return np.column_stack((np.cos(latitude)*np.cos(longitude),
                                np.cos(latitude)*np.sin(longitude), np.sin(latitude)))
    a, b = vectors(e.id_a, e.point_a), vectors(e.id_b, e.point_b)
    degrees = np.degrees(np.arctan2(np.linalg.norm(np.cross(a, b), axis=1), np.sum(a*b, axis=1)))
    assert len(e) == 237416
    np.testing.assert_allclose(degrees, e.angular_deg, atol=1e-9, rtol=0)
    pairs = pd.read_csv(result / 'pairwise_rules.csv').set_index(['id_a', 'id_b'])
    for route in ['split_fixed', 'bound_fixed']:
        maxima = e[e.route.eq(route)].groupby(['id_a', 'id_b']).angular_deg.max()
        np.testing.assert_allclose(maxima, pairs.loc[maxima.index, route], atol=1e-9, rtol=0)
    ordinals = pd.read_csv(result / 'point_ordinals.csv')
    for _, group in ordinals[ordinals.route.eq('split')].groupby(['id', 'role']):
        expected = group.sort_values(['x', 'y', 'point_index']).point_index.tolist()
        assert group.sort_values('ordinal').point_index.tolist() == expected


def test_known_pair_midpoint_tie_limit_is_visible():
    # Same supplied physical links and coordinates, only storage order changes.
    # The retained algorithm uses source indices to break midpoint ties.
    p = np.array([[100, 100], [100, 400], [100, 180], [100, 320]], float)
    links = np.array([[0, 1], [2, 3]])
    def record(points, association):
        return dict(p=points, up=study.order_indices(points, association[:, 0]),
                    dn=study.order_indices(points, association[:, 1]),
                    links=study.pair_order(points, association))
    permutation = np.array([2, 3, 0, 1])
    a = record(p, links)
    b = record(p[permutation], np.argsort(permutation)[links])
    scores, _ = study.compare(a, b)
    assert scores['split_fixed'] == 0
    assert scores['bound_fixed'] > 20
    # This counterexample is synthetic. No exact pair-midpoint ties in this snapshot.
    o = pd.read_csv(ROOT / 'local_recheck/results/point_ordinals.csv')
    o = o[o.route.eq('bound')]
    t = o[o.role.eq('top')].set_index(['id', 'ordinal']).x
    b = o[o.role.eq('bottom')].set_index(['id', 'ordinal']).x
    mids = ((t + ((b-t+512) % 1024-512)/2) % 1024).reset_index(name='midpoint')
    assert not mids.duplicated(['id', 'midpoint']).any()
