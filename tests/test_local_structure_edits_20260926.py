import inspect

import numpy as np
import pytest

from tools.thesis_main.analysis.local_structure_edits_20260926 import local_edit_probe, cluster_pool_probe


BASE = [[-2, -2], [2, -2], [2, 2], [-2, 2]]
LOW = [BASE[0], [-.5, -2.8], [.5, -2.8], *BASE[1:]]
HIGH = [*BASE[:3], [.5, 2.8], [-.5, 2.8], BASE[3]]


def records(shapes):
    return [dict(id=str(i), worker=f'w{i}', floor=p) for i, p in enumerate(shapes)]


def test_local_edits_create_unobserved_rings_and_warn_about_joint_support():
    result = local_edit_probe(records([LOW] * 3 + [HIGH] * 3), point_tol=.1)
    candidates = [c for seed in result['seeds'] for c in seed['generated_candidates']]
    assert any(a['type'] == 'insert' for c in candidates for a in c['actions'])
    assert any(a['type'] == 'delete' for c in candidates for a in c['actions'])
    hybrids = [c for c in candidates if len(c['floor']) == 8]
    assert hybrids and all(c['status'] == 'unsupported_joint_candidate' for c in hybrids)
    assert all(c['whole_ring_support'] == 0 for c in hybrids)
    assert all(min(c['local_support']['edge_counts']) >= 3 for c in hybrids)
    assert any(len(c['floor']) == 4 for c in candidates)
    assert result['parameters']['vote_denominator'] == 6
    assert result['schema_version'] == 'local_structure_edits_20260926_v1'
    assert not {'gt', 'iou', 'centroid'} & set(inspect.signature(local_edit_probe).parameters)
    assert len(result['candidates']) <= 2*result['parameters']['beam_width']
    assert result['search']['proposed'] == result['search']['evaluated'] + result['search']['truncated']


def test_exact_collinear_delete_and_cyclic_input_do_not_require_target_ring():
    redundant = [BASE[0], [0, -2], *BASE[1:]]
    result = local_edit_probe(records([redundant]), point_tol=.1)
    candidates = result['seeds'][0]['generated_candidates']
    simplified = [c for c in candidates if len(c['floor']) == 4]
    assert simplified and simplified[0]['actions'][0]['evidence'] == 'exact_collinear_redundancy'
    assert np.allclose(simplified[0]['floor'], BASE)
    rotated = np.roll(np.array(LOW)[::-1], 2, axis=0).tolist()
    result = local_edit_probe(records([BASE, rotated, rotated]), point_tol=.1)
    assert any(a['type'] == 'insert' for c in result['seeds'][0]['generated_candidates'] for a in c['actions'])
    with pytest.raises(ValueError, match='duplicate_worker'):
        local_edit_probe([dict(id='a', worker='same', floor=BASE), dict(id='b', worker='same', floor=LOW)])
    with pytest.raises(ValueError, match='invalid_parameters'):
        local_edit_probe(records([BASE]), support_threshold=2)
    invalid = [BASE[0], BASE[2], BASE[1], BASE[3]]
    result = local_edit_probe(records([invalid]), max_steps=0)
    assert all(c['status'] == 'invalid_input_seed_kept_for_review' for c in result['candidates'])


def test_cluster_conditioned_pool_keeps_minority_and_separates_weight_from_votes():
    rows = records([BASE]*7 + [LOW]*3)
    for outside in ('hard', 'soft'):
        result = cluster_pool_probe(rows, point_tol=.1, outside_mode=outside, max_steps=1, beam_width=2)
        assert len(result['pool']['points']) == 7*4+3*6
        partition = [worker for m in result['modes'] for worker in m['members']]
        assert sorted(partition) == sorted(r['worker'] for r in rows)
        assert len(partition) == len(set(partition))
        detail = next(m for m in result['modes'] if m['train_support'] == 3)
        assert detail['search_status'] == 'searched'
        weights = detail['worker_weights']
        assert sum(weights[w] for w in detail['members']) == 3
        outside_mass = sum(v for w, v in weights.items() if w not in detail['members'])
        assert outside_mass <= .75+1e-12
        assert outside_mass == 0 if outside == 'hard' else outside_mass > 0
        selected = [c for c in result['candidates'] if c['cluster_id'] == detail['cluster_id']]
        assert selected and all(len(c['floor']) == 6 for c in selected)
        assert all(c['local_support']['denominator'] == 10 for c in selected)
        assert all(c['local_support']['weight_denominator'] <= 3.75+1e-12 for c in selected)
        assert result['input_workers'] == [r['worker'] for r in rows]
    duplicated = [*rows, dict(rows[0], id='duplicate')]
    with pytest.raises(ValueError, match='duplicate_worker'):
        cluster_pool_probe(duplicated)
    adjacent_modes = records([[[x+dx, y] for x, y in BASE] for dx in (0, .12, .24, .36)])
    result = cluster_pool_probe(adjacent_modes, point_tol=.25, max_steps=0)
    partition = [worker for m in result['modes'] for worker in m['members']]
    assert len(partition) == len(set(partition)) == 4
    assert any(m['source_candidate_whole_ring_support'] > m['train_support'] for m in result['modes'])
