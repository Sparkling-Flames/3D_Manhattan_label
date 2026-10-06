from itertools import combinations

import numpy as np
import pytest

from tools.thesis_main.analysis.worker_count_composition_20261006 import (
    area_summary, fit_labels, feasible_compositions, probabilities, summarize,
)


@pytest.mark.parametrize('method', ['mv50', 'mv_strict'])
def test_stratified_probabilities_and_area_match_small_enumeration(method):
    patterns = np.array([1, 3, 6, 12, 15], dtype=np.uint32)
    area = np.array([1., 2., 1., 3., 2.])
    inside = np.array([.5, 2., 0., 1., 2.])
    reference_area = 7.  # Includes 1.5 outside the entire worker union.
    for draws in [(1, 1), (2, 0), (2, 2)]:
        subsets = [a+b for a in combinations(range(2), draws[0])
                   for b in combinations(range(2, 4), draws[1])]
        votes = np.array([[(int(p) & sum(1 << j for j in s)).bit_count()
                           for p in patterns] for s in subsets])
        keep = 2*votes >= sum(draws) if method == 'mv50' else 2*votes > sum(draws)
        q = probabilities(patterns, (3, 12), (2, 2), draws, method)
        np.testing.assert_allclose(q, keep.mean(axis=0))
        got = area_summary(area, inside, reference_area, q)
        assert got['omission_h2'] == pytest.approx(np.mean(reference_area-keep @ inside))
        assert got['extension_h2'] == pytest.approx(np.mean(keep @ (area-inside)))
        expected_pair = np.mean([area @ (a != b) for a in keep for b in keep])
        assert got['member_symdiff_h2'] == pytest.approx(expected_pair)
        if draws == (2, 2):
            assert got['member_symdiff_h2'] == 0
            assert got['ref_symdiff_h2'] > 0  # Exhausting the pool is not correctness.


def test_calibration_excludes_whole_target_building_and_keeps_global_groups():
    workers = ['a', 'b', 'c', 'd']
    rows = [dict(image='i1', building='other', a=.9, b=.8, c=.3, d=.2),
            dict(image='i2', building='target', a=.1, b=.2, c=.8, d=.9),
            dict(image='i3', building='target', a=.2, b=.1, c=.9, d=.8)]
    first, train = fit_labels(rows, workers, 'target')
    rows[1]['a'] = 100
    assert fit_labels(rows, workers, 'target')[0] == first
    assert train == ['i1']
    assert first == dict(a=True, b=True, c=False, d=False)
    assert feasible_compositions(12, 12, 16) == {'lower_rich': 4, 'balanced': 8, 'higher_rich': 12}
    assert feasible_compositions(12, 12, 24) == {'lower_rich': 12, 'balanced': 12, 'higher_rich': 12}


def test_fixed_panel_does_not_drop_exhausted_image_from_add_one_mean():
    base = dict(scenario='uniform', policy='none', method='mv50', version='original',
                k=20, strategy='random', building='b', ref_symdiff_ref=.2)
    rows = [dict(base, image='a', add_one_symdiff_union=None),
            dict(base, image='b', add_one_symdiff_union=.1)]
    for r in summarize(rows, {'fixed20': ({'a','b'},20)}):
        assert r['image_n'] == 2
        assert r['ref_symdiff_ref'] == pytest.approx(.2)
        assert r['add_one_symdiff_union'] is None


def test_metrics_can_run_without_geometry_or_experiment_imports():
    import subprocess
    import sys

    subprocess.run([sys.executable, '-c', """
import sys
sys.modules['shapely'] = None
sys.modules['tools.thesis_main.analysis.worker_count_composition_20261006'] = None
import numpy as np
from tools.thesis_main.analysis.worker_count_metrics_20261006 import area_summary, summarize
result = area_summary(np.array([2.]), np.array([1.]), 1., np.array([.5]))
assert result['ref_symdiff_ref'] == 1.
assert result['member_symdiff_union'] == .5
assert summarize([], {}) == []
"""], check=True)


def test_experiment_preserves_existing_numeric_entry_points():
    from tools.thesis_main.analysis import worker_count_composition_20261006 as experiment
    from tools.thesis_main.analysis import worker_count_metrics_20261006 as metrics

    for name in ('FIELDS', 'area_summary', 'fit_labels', 'feasible_compositions', 'summarize'):
        assert getattr(experiment, name) is getattr(metrics, name)
