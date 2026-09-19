"""探索性局部测量：保留平均/覆盖/数量及有限池事件的区别。"""
import itertools

import numpy as np
import pytest
import pandas as pd

from tools.thesis_main.analysis.local_point_research import local_points as lp
from tools.thesis_main.analysis.local_point_research.audit_extensions import finite_pool_events, union_point_expectation, time_baselines


def test_local_metrics_and_invariance():
    a = np.array([[0., 255.5], [200., 255.5], [500., 255.5], [800., 255.5]])
    f = lp.features(lp.angular(a, np.vstack([a, a[:1]])))
    assert f['hausdorff'] == pytest.approx(0, abs=2e-6)
    assert f['ospa1'] == pytest.approx(6, abs=2e-6)
    assert f['matched_9'] == 4
    q = a.copy(); q[:, 0] = (q[:, 0] + 137) % 1024
    assert np.allclose(lp.angular(a, a[::-1]), lp.angular(q, q[::-1]), atol=2e-6)
    # Every point has a neighbour, but local multiplicity prevents a full matching.
    c = np.array([[0., 20., 20.], [0., 20., 20.], [20., 0., 0.]])
    f = lp.features(c)
    assert f['hausdorff'] == 0 and f['matched_9'] == 2 and f['bottleneck'] == 20


def test_finite_pool_event_is_not_union_point_novelty():
    o = np.array([[0, 1, 1], [1, 0, 0], [1, 0, 0]], dtype=bool)
    h = np.zeros((3, 3), dtype=bool)
    got = finite_pool_events(o, h, 2)
    brute = []
    for target in range(3):
        for chosen in itertools.combinations([i for i in range(3) if i != target], 2):
            brute.append(o[target, list(chosen)].any() and not h[target, list(chosen)].any())
    assert got['ospa_covered_but_local_uncovered'] == pytest.approx(np.mean(brute))
    # Two earlier workers each cover one distinct target point: no single full
    # response matches, but every target point has appeared in their union.
    assert union_point_expectation(np.array([[True, False], [False, True]]), 2) == 0
    assert union_point_expectation(np.array([[True, False], [False, True]]), 1) == .5
    with pytest.raises(ValueError):
        finite_pool_events(o, h, 3)


def test_time_qualification_and_user_text_survive_integration():
    root = lp.ROOT
    original = pd.read_csv(root/'previous_pairing_time/results/time_record_audit.csv')
    qualified, predictions = time_baselines(original)
    assert len(qualified) == 1971 and len(predictions) == 1583
    assert qualified.source_seconds_match.all()
    # These explicit fields are developer mappings, never whole-image gold labels.
    from pathlib import Path
    source = Path(__file__).resolve().parents[1]/'tools/thesis_main/analysis/local_point_research/review_audit.py'
    text = source.read_text(encoding='utf-8')
    assert '相近' in text and '有增减或不同表达' in text
