import importlib.util
from pathlib import Path

import pandas as pd
import pytest

PATH = Path(__file__).parents[1] / 'tools/thesis_main/analysis/personnel_type_validation_20261019.py'
spec = importlib.util.spec_from_file_location('personnel_validation', PATH)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def test_fixed_candidates_nested_background_and_no_geometry_selection():
    workers = [f'W{i:03}' for i in range(35)]
    a = m.member_design('pool', workers)
    assert a == m.member_design('pool', workers[::-1])
    assert len(a['candidates']) == 3
    for background in a['backgrounds']:
        assert not set(background) & set(a['candidates'])
        for w in a['candidates']:
            teams = [background[:k-1] + [w] for k in m.KS]
            assert all(len(t) == k and len(set(t)) == k for k, t in zip(m.KS, teams))
            assert all(set(x) < set(y) for x, y in zip(teams, teams[1:]))


def test_failure_and_missing_structure_cannot_pass_stability():
    row = dict(both_complete=True, abs_B8L2_change=0.1, node_count_difference=0,
               floor_jaccard_difference=0.001, structure_bound_cyclic_deg=0.1)
    assert m.stable(row, 2, .05, 3)
    for key, value in [('both_complete', False), ('structure_bound_cyclic_deg', None),
                       ('abs_B8L2_change', float('nan')), ('node_count_difference', 1)]:
        assert not m.stable(dict(row, **{key: value}), 2, .05, 3)


def test_swap_isolation_and_vote_boundary():
    assert m.vote_gate([4, 7], 8)['one_swap_can_flip']
    assert not m.vote_gate([2, 6], 8)['one_swap_can_flip']
    assert m.vote_gate([4, 7], 9)['one_swap_can_flip']
    assert m.same_class('unknown', 'unknown') is None
    assert m.same_class('A', 'A') is True
    edge = dict(worker_a='A',worker_b='B',q_a=1.,q_b=2.)
    assert m.alternative_q(edge,'A') == 2.
    assert m.alternative_q(edge,'B') == 1.
    with pytest.raises(ValueError,match='anchor_not_in_edge'):
        m.alternative_q(edge,'C')


def test_building_equal_paired_effect_keeps_missing_pairs_out():
    df = pd.DataFrame([
        dict(building='a', pool_id='i', context=0, near=1., far=0.),
        dict(building='a', pool_id='i', context=1, near=1., far=0.),
        dict(building='b', pool_id='j', context=0, near=0., far=1.),
        dict(building='c', pool_id='k', context=0, near=None, far=0.),
    ])
    result = m.paired_summary(df, 'near', 'far')
    assert result['buildings'] == 2
    assert result['paired_rows'] == 3
    assert result['delta'] == pytest.approx(0.)
    assert result['experiment_delta'] == pytest.approx(-1/3)
    flags = df.dropna().assign(near=lambda d:d.near.astype(bool), far=lambda d:d.far.astype(bool))
    assert m.paired_summary(flags, 'near', 'far')['experiment_delta'] == pytest.approx(-1/3)


def test_point_control_changes_only_declared_coordinates(monkeypatch):
    monkeypatch.syspath_prepend(str(PATH.parent))
    from personnel_case_score_audit_20261019 import replace_pair_coordinates
    a = [[1, 2], [1, 3], [4, 5], [4, 6]]
    b = [[10, 20], [10, 30], [40, 50], [40, 60]]
    assert replace_pair_coordinates(a, b, [1], 'bottom_y') == [[1, 2], [1, 3], [4, 5], [4, 60]]
    assert replace_pair_coordinates(a, b, [0], 'x') == [[10, 2], [10, 3], [4, 5], [4, 6]]
    assert replace_pair_coordinates(a, b, [0, 1], 'pair') == b
    assert a == [[1, 2], [1, 3], [4, 5], [4, 6]]
    assert b == [[10, 20], [10, 30], [40, 50], [40, 60]]
    with pytest.raises(ValueError):
        replace_pair_coordinates(a, b, [0], 'guess')


def test_mechanism_unknown_does_not_become_no_change():
    df = pd.DataFrame(dict(changed_coidentity_pairs=[0,2,None,1],node_count_difference=[0,1,1,None],
                           selected_shared_change=[0,.1,None,.2]))
    r = m.mechanism_flags(df)
    assert r.loc[0,'identity_and_node_change'] == False
    assert r.loc[1,'identity_and_node_change'] == True
    assert pd.isna(r.loc[2,'identity_and_node_change'])
    assert pd.isna(r.loc[3,'identity_and_node_change'])
    assert pd.isna(r.loc[2,'selected_membership_change'])
