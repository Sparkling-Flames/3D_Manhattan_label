import json

import numpy as np
import pytest

from tools.thesis_main.analysis.union_branch_consensus_20260926 import fit_union_branches


POINTS = {'1': [-3, -2], '2': [3, -2], '3': [3, 2], '4': [1, 2],
          '5': [1, 0], '6': [-3, 0], '7': [-1, 2], '8': [-3, 2]}


def symbolic(ids, n, start=0, label=None):
    rows = [dict(id=f'a{i:02}', worker=f'w{i:02}', feature_ids=list(ids),
                 floor=[POINTS[p] for p in ids], heights=[2.7] * len(ids),
                 order_status='user_confirmed_default_ring') for i in range(start, start + n)]
    if label is not None:
        for row in rows:
            row['cluster_label'] = label
    return rows


def test_user_union_subtraction_support_and_parent_deletion():
    data = symbolic('123456', 10, label='A') + symbolic('123478', 8, 10, 'B') + symbolic('12345', 2, 18, 'C')
    result = fit_union_branches(data)
    assert [b['support'] for b in result['branches']] == [10, 8, 2]
    assert [b['support_fraction'] for b in result['branches']] == [.5, .4, .1]
    assert {f['feature_id'] for f in result['features']} == set('12345678')
    a, b, c = result['branches']
    assert a['shared_feature_candidate']['point_support_counts'][:4] == [20] * 4
    assert a['support'] == 10
    assert set(a['deleted_feature_ids']) == set('78')
    assert set(b['deleted_feature_ids']) == set('56')
    assert set(c['deleted_feature_ids']) == set('678')
    assert c['parent_deletions'] == [dict(parent_branch_id=a['branch_id'], deleted_feature_ids=['6'])]
    assert sum(x['support'] for x in result['branches']) == 20
    assert all(len(f['support_workers']) == len(set(f['support_workers'])) for f in result['features'])
    json.dumps(result, allow_nan=False)
    shifted = json.loads(json.dumps(data))
    for row in shifted[10:]:
        row['floor'][0][0] += .2
    shifted_a = fit_union_branches(shifted)['branches'][0]
    assert shifted_a['floor'][0] == a['floor'][0]
    assert np.isclose(shifted_a['shared_feature_candidate']['floor'][0][0], a['floor'][0][0] + .1)


def test_same_points_different_adjacency_and_bad_majority_are_preserved():
    bad = symbolic('1328', 10)
    good = symbolic('1238', 2, 10)
    result = fit_union_branches(bad + good)
    assert len(result['branches']) == 2
    assert result['branches'][0]['support'] == 10
    assert result['branches'][0]['geometry']['polygon_status'] == 'invalid'
    assert result['branches'][0]['geometry_status'] == 'invalid_3d_candidate'
    assert result['branches'][1]['geometry']['polygon_status'] == 'valid'
    reversed_row = dict(good[0], id='reverse', worker='reverse', feature_ids=list('8321'),
                        floor=[POINTS[i] for i in '8321'])
    assert len(fit_union_branches(good + [reversed_row])['branches']) == 1
    poset = fit_union_branches(symbolic('123456', 1) + symbolic('1243', 1, 1) + symbolic('123', 1, 2))
    child = next(b for b in poset['branches'] if len(b['feature_ids']) == 3)
    # 中间点集是子集但邻接不同，不能误删六点环到三点环的直接路径。
    assert len(child['parent_deletions']) == 2


def test_periodic_angular_identity_nearby_corners_and_complete_linkage():
    floor = [[-2, -2], [2, -2], [2, 2], [-2, 2]]
    data = []
    for i, offset in enumerate([0., 1., 16.]):
        # 前两个同人角点非常靠近，必须保留；第一个跨ERP接缝。
        pairs = np.array([[[1023., 100.], [1023., 400.]], [[3., 100.], [3., 400.]],
                          [[300., 100.], [300., 400.]], [[600., 100.], [600., 400.]]])
        pairs[:, :, 0] = (pairs[:, :, 0] + offset) % 1024
        data.append(dict(id=str(i), worker=str(i), floor=floor, heights=[2.7] * 4,
                         pairs=pairs.tolist()))
    result = fit_union_branches(data, point_tol_deg=1.)
    assert len(result['features']) == 8
    assert sorted(b['support'] for b in result['branches']) == [1, 2]
    for feature in result['features']:
        assert len(feature['members']) == len({x['worker'] for x in feature['members']})
        assert feature['maximum_pair_angle_deg'] <= 1. + 1e-10
    chain = []
    for i, offset in enumerate([0., 2., 4.]):
        row = dict(data[0], id=str(i), worker=str(i))
        pairs = np.array(row['pairs'])
        pairs[:, :, 0] = (pairs[:, :, 0] + offset) % 1024
        row['pairs'] = pairs.tolist()
        chain.append(row)
    result = fit_union_branches(chain, point_tol_deg=.6)
    assert all(f['maximum_pair_angle_deg'] <= .6 + 1e-10 for f in result['features'])
    assert len(result['branches']) > 1
    with pytest.raises(ValueError, match='duplicate_worker'):
        fit_union_branches(data + data[:1])
    with pytest.raises(ValueError, match='missing_pairs'):
        fit_union_branches([dict(id='x', worker='x', floor=floor, heights=[2.7] * 4)])
    assert fit_union_branches([])['status'] == 'no_training_records'
