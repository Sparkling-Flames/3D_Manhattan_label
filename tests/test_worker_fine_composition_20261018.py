import pandas as pd

from tools.thesis_main.analysis.worker_fine_composition_20261018 import (
    add_classes, composition, count_compositions, draw_members, choose_compositions,
)


def test_thresholds_use_only_supported_training_effects_and_ties_stay_together():
    frame = pd.DataFrame(dict(fold=['target'] * 5, metric=['B8L2'] * 5,
        worker_id=list('abcde'), Q_effect=[-3., -1., 1., 3., 1000.],
        Q_supported=[True] * 4 + [False], Q_contexts=[6] * 5,
        Q_buildings=[3] * 5, Q_training_buildings=['["outside"]'] * 5,
        Q_group=['lower', 'lower', 'higher', 'higher', 'unclassified'],
        QT_group=['lower_faster'] * 5))
    classes, thresholds = add_classes(frame)
    assert thresholds.iloc[0].lower_cut == -1.
    assert thresholds.iloc[0].upper_cut == 1.
    assert classes.Q3.tolist() == ['low', 'middle', 'middle', 'high', 'unclassified']
    assert classes.Q2.tolist() == frame.Q_group.tolist()


def test_composition_support_and_distinct_draws_keep_missing_class_visible():
    people = {'a': 'A', 'b': 'A', 'c': 'A', 'd': 'B', 'e': 'B'}
    counts = count_compositions(people, 4)
    assert counts['A:2|B:2'] == 3
    assert counts['A:3|B:1'] == 2
    draws = draw_members(people, 'A:2|B:2', 3, 17)
    assert len(draws) == len(set(draws)) == 3
    assert all(composition([people[w] for w in team]) == 'A:2|B:2' for team in draws)
    assert draw_members(people, 'A:2|B:2', 3, 17) == draws
    assert set(choose_compositions(counts, 'Q2')) == set(counts)


def test_cannot_use_target_building_for_classes():
    import pytest
    frame = pd.DataFrame(dict(fold=['target'], metric=['B8L2'], worker_id=['a'],
        Q_effect=[1.], Q_supported=[True], Q_contexts=[6], Q_buildings=[3],
        Q_training_buildings=['["target"]'], Q_group=['higher'], QT_group=['higher_faster']))
    with pytest.raises(AssertionError):
        add_classes(frame)


def test_all_replaceable_pure_classes_are_requested_not_only_most_supported():
    counts = {'high:4': 70, 'middle:4': 35, 'low:4': 5, 'high:2|middle:2': 100,
        'high:2|low:2': 200}
    chosen = choose_compositions(counts, 'Q3')
    assert {'high:4', 'middle:4', 'low:4'} <= set(chosen)
    assert 'high:2|low:2' in chosen and 'high:2|middle:2' not in chosen


def test_delivered_design_keeps_holdout_and_failures_and_does_not_count_orders_as_members():
    import json
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / 'research/workers/worker_fine_composition_20261018'
    requests = json.loads((path / 'TEAM_REQUESTS.json').read_text(encoding='utf-8'))['requests']
    result = pd.read_csv(path / 'team_analysis.csv')
    assert len(requests) == len(result) == 528
    assert set(result.request_id) == {r['request_id'] for r in requests}
    assert result.original_holdout_member_n.eq(0).all()
    assert result.building_id.nunique() == 8
    fixed = result[result.experiment.eq('fixed_k_composition_and_members')]
    assert len(fixed) == 432 and fixed.k.eq(4).all()
    assert fixed.groupby(['image_code', 'scheme', 'composition']).worker_ids.nunique().eq(3).all()
    assert result[result.score_status.eq('two_person_deferred')].B8L2.isna().all()
    assert result[~result.main_comparison_allowed].B8L2.isna().all()
    endpoints = result[result.experiment.eq('same_endpoint_order') & result.k.eq(4)]
    assert endpoints.groupby('image_code').worker_ids.apply(
        lambda rows: len({tuple(sorted(x.split('|'))) for x in rows})).eq(1).all()
