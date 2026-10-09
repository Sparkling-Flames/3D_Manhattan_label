import numpy as np
import pytest

from tools.thesis_main.analysis.difficulty_score_20261009 import (
    empirical_percentiles, weight_grid, calibrate_weights, building_holdout, score_features, rank_metrics,
)


def test_percentiles_keep_ties_and_do_not_fit_to_queries():
    reference = np.array([[1, 10], [1, 20], [3, 30]], dtype=float)
    query = np.array([[1, 5], [2, 20], [4, 40]], dtype=float)
    result = empirical_percentiles(query, reference)
    assert result == pytest.approx(np.array([[1 / 3, 0], [2 / 3, .5], [1, 1]]))
    assert empirical_percentiles(query[:1], reference) == pytest.approx(result[:1])
    with pytest.raises(ValueError, match='finite'):
        empirical_percentiles([[float('nan'), 1]], reference)


def test_nonnegative_weights_can_discard_an_uninformative_feature():
    assert len(weight_grid(2)) == 5
    x = np.array([[0, 1], [.5, .5], [1, 0]])
    assert calibrate_weights(x, [0, 1, 2], ['a', 'a', 'a']) == pytest.approx([1, 0])


def test_three_axis_calibration_can_keep_uniform_instead_of_forcing_a_change():
    assert any(np.allclose(w, [1/3]*3) for w in weight_grid(3))
    assert calibrate_weights(np.eye(3), [1, 1, 1], ['a', 'b', 'c']) == pytest.approx([1/3]*3)


def test_missing_features_do_not_reweight_and_constant_scores_are_chance_pairs():
    scores, complete = score_features([dict(image='a', f1=1, f2=2),
                                       dict(image='b', f1=2, f2=None)], ('f1', 'f2'))
    assert scores[1]['baseline_score'] is None
    assert scores[1]['missing_features'] == 'f2'
    assert set(complete) == {'a'}
    metrics = rank_metrics([1, 1, 1], [0, 1, 2])
    assert metrics['spearman'] is None
    assert metrics['concordance'] == .5


def test_outer_building_labels_cannot_change_its_scaler_or_weights():
    rows = [dict(image=f'{b}{i}', building=b, x=x, label=i)
            for b in ('a', 'b', 'c')
            for i, x in enumerate(([0, 2], [1, 1], [2, 0]))]
    original = building_holdout(rows)
    changed = [dict(r, label=2-r['label']) if r['building']=='c' else dict(r) for r in rows]
    repeat = building_holdout(changed)
    for a, b in zip(original, repeat):
        if a['building']=='c':
            assert a['baseline_score'] == b['baseline_score']
            assert a['calibrated_score'] == b['calibrated_score']
            assert a['weights'] == b['weights']
            assert 'c' not in a['training_buildings']
