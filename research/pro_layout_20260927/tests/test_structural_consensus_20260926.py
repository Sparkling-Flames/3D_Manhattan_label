import json

import numpy as np
import pytest

from tools.thesis_main.analysis.structural_consensus_20260926 import (
    fit_consensus, local_support, match_ring, score_candidate,
)


SQUARE = [[-2, -2], [2, -2], [2, 2], [-2, 2]]
DETAIL = [[-2, -2], [2, -2], [2, -.1], [2.08, -.1],
          [2.08, .1], [2, .1], [2, 2], [-2, 2]]


def records(points, count, start=0):
    return [dict(id=f'a{i:02}', worker=f'w{i:02}', floor=points,
                 heights=[2.7] * len(points), order_status='given_ring')
            for i in range(start, start + count)]


def test_complete_ring_invariants_and_input_failures():
    assert match_ring(SQUARE, np.roll(SQUARE, 2, axis=0), .2)['matched']
    assert match_ring(SQUARE, SQUARE[::-1], .2)['matched']
    assert not match_ring(SQUARE, np.array(SQUARE)[[0, 2, 1, 3]], .2)['matched']
    assert not match_ring(SQUARE, DETAIL, .2)['matched']
    with pytest.raises(ValueError, match='duplicate_worker'):
        fit_consensus(records(SQUARE, 1) * 2)
    assert fit_consensus([])['status'] == 'no_training_records'


def test_two_seeds_reach_supported_multi_modes_and_holdout_never_fits():
    data = records(SQUARE, 8) + records(DETAIL, 4, 8)
    heldout = ['w06', 'w07', 'w10', 'w11']
    result = fit_consensus(data, heldout_workers=heldout)
    assert sorted(m['n_corners'] for m in result['modes']) == [4, 8]
    assert sorted(m['train_support'] for m in result['modes']) == [2, 6]
    assert sorted(m['heldout_support'] for m in result['modes']) == [2, 2]
    assert all(p['reaches_target'] for p in result['seed_paths'])
    assert any(p['inserted'] == 4 for p in result['seed_paths'])
    assert any(p['deleted'] == 4 for p in result['seed_paths'])
    frozen = fit_consensus([r for r in data if r['worker'] not in heldout])
    assert [m['floor'] for m in result['modes']] == [m['floor'] for m in frozen['modes']]
    changed = records([[-7, -2], [2, -2], [2, 2], [-7, 2]], 1, 12)
    novel = fit_consensus(data + changed, heldout_workers=heldout + ['w12'])
    assert [m['floor'] for m in novel['modes']] == [m['floor'] for m in result['modes']]
    assert novel['heldout']['unmatched_workers'] == ['w12']
    assert next(m for m in result['modes'] if m['n_corners'] == 8)['geometry']['short_edges']
    plain = next(m for m in result['modes'] if m['n_corners'] == 4)
    assert plain['local_support_denominator'] == 8
    assert plain['point_support_counts'] == [8] * 4
    assert sorted(plain['edge_support_counts']) == [6, 8, 8, 8]
    json.dumps(result, allow_nan=False)


def test_common_bias_invalid_geometry_and_collinear_point_are_not_hidden():
    bad = np.array(SQUARE)[[0, 2, 1, 3]].tolist()
    extra = SQUARE[:1] + [[0, -2]] + SQUARE[1:]
    result = fit_consensus(records(bad, 8) + records(extra, 3, 8), geometry_weight=0)
    invalid = next(m for m in result['modes'] if m['n_corners'] == 4)
    assert invalid['train_support'] == 8
    assert invalid['geometry']['polygon_status'] == 'invalid'
    assert invalid['status'] == 'supported_geometry_review'
    collinear = next(m for m in result['modes'] if m['n_corners'] == 5)
    assert collinear['geometry']['near_collinear_corners'] == [1]
    assert collinear['n_corners'] == 5


def test_soft_geometry_ablation_changes_fit_without_removing_modes():
    noisy = np.array(SQUARE, float)
    noisy[1] += [.12, .15]
    data = records(noisy.tolist(), 4)
    free = fit_consensus(data, geometry_weight=0, height_weight=0)
    regularized = fit_consensus(data, geometry_weight=.3, height_weight=.02)
    a, b = free['modes'][0], regularized['modes'][0]
    assert a['train_support'] == b['train_support'] == 4
    assert np.allclose(a['floor'], noisy)
    assert not np.allclose(b['floor'], noisy)
    assert b['geometry']['weighted_direction_residual_deg'] < a['geometry']['weighted_direction_residual_deg']
    assert np.max(np.abs(np.asarray(b['floor']) - noisy)) <= .2 / 2 + 1e-7


def test_unsupported_local_union_cannot_become_consensus():
    left = [[-2, -2], [2, -2], [2, 2], [-2, 2], [-2, .1], [-2.1, 0], [-2, -.1]]
    right = [[-2, -2], [2, -2], [2, -.1], [2.1, 0], [2, .1], [2, 2], [-2, 2]]
    hybrid = [[-2, -2], [2, -2], [2, -.1], [2.1, 0], [2, .1], [2, 2],
              [-2, 2], [-2, .1], [-2.1, 0], [-2, -.1]]
    data = records(left, 4) + records(right, 4, 4)
    verdict = score_candidate(hybrid, data, point_tol=.2)
    assert verdict['whole_ring_support'] == 0
    assert verdict['status'] == 'unsupported_complete_ring'
    result = fit_consensus(data, geometry_weight=0)
    assert all(m['n_corners'] == 7 for m in result['modes'])
    result = fit_consensus(data + records(SQUARE, 3, 8), geometry_weight=0, point_tol=.03)
    assert len(result['unsupported_hybrids']) == 1
    rejected = result['unsupported_hybrids'][0]
    assert rejected['whole_ring_support'] == 0
    assert min(rejected['point_support_counts']) == 4
    assert min(rejected['edge_support_counts']) == 4
    assert rejected['local_support_denominator'] == 11
    scrambled = np.asarray(SQUARE)[[0, 2, 1, 3]].tolist()
    support = local_support(SQUARE, records(scrambled, 1), point_tol=.01)
    assert support['point_support_counts'] == [1] * 4
    assert sorted(support['edge_support_counts']) == [0, 0, 1, 1]
