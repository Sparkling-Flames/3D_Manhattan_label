import importlib.util
from pathlib import Path

import pandas as pd
import pytest


path = Path(__file__).parents[1] / 'tools/thesis_main/analysis/personnel_part_a_acceptance_20261019.py'
spec = importlib.util.spec_from_file_location('part_a_acceptance', path)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def test_labels_use_heldout_building_condition_and_keep_unknown():
    events = pd.DataFrame([
        dict(event_id='e1', building='b1', difficulty='困难', worker_a='a', worker_b='b'),
        dict(event_id='e2', building='b2', difficulty='困难', worker_a='a', worker_b='b'),
    ])
    labels = pd.DataFrame([
        dict(heldout_building=b, difficulty=d, worker_id=w, class_id=c)
        for b, d, w, c in [('b1', 'hard', 'a', 'C1'), ('b1', 'hard', 'b', 'C1'),
                           ('b2', 'hard', 'a', 'C1'), ('b2', 'hard', 'b', 'unknown'),
                           ('FULL', 'hard', 'a', 'X'), ('FULL', 'hard', 'b', 'Y'),
                           ('b1', 'easy', 'a', 'X'), ('b1', 'easy', 'b', 'Y')]
    ])
    got = m.attach_labels(events, labels)
    assert got.relation.tolist() == ['within', 'unknown']
    with pytest.raises(pd.errors.MergeError):
        m.attach_labels(events, pd.concat([labels, labels.iloc[[0]]]))
    with pytest.raises(AssertionError, match='missing_label_row'):
        m.attach_labels(events, labels[~labels.heldout_building.eq('b2')])


def test_matched_cells_do_not_compare_unmatched_backgrounds_or_drop_bad_edges():
    events = pd.DataFrame([
        dict(building='b', pool_id='p', context=c, relation=r, value=v)
        for c, r, v in [(0, 'within', 1.), (0, 'between', 0.),
                        (1, 'within', 0.), (2, 'between', 1.),
                        (3, 'within', float('nan')), (3, 'within', 1.), (3, 'between', 1.)]
    ])
    got = m.matched_cells(events, 'value')
    assert got.context.tolist() == [0]
    assert got[['near', 'far']].iloc[0].tolist() == [1., 0.]


def test_single_building_has_no_bootstrap_uncertainty_interval():
    result = m.paired_summary(pd.DataFrame([dict(building='b', pool_id='p', near=.8, far=.5)]))
    assert result['delta'] == pytest.approx(-.3)
    assert result['low'] is None and result['high'] is None
