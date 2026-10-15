import copy

import pytest

from tools.thesis_main.analysis.wall_consensus_population_20261014 import (
    automatic_prefixes, transition, summarize_state, footprint_metrics,
)


def records(n=4):
    return [dict(id=f'R{i}', worker=f'P{i}',
                 points=[[x+i, y] for x in (128, 384, 640, 896) for y in (120, 390)])
            for i in range(n)]


def test_prefix_only_uses_current_people_and_two_people_remain_deferred():
    rows = records()
    path = automatic_prefixes(rows, ['P2', 'P0', 'P3', 'P1'])
    assert path[1]['candidate']['order_status'] == 'two_person_sorting_deferred'
    for k, state in enumerate(path, 1):
        assert {a['worker'] for a in state['assignments']} == set(['P2', 'P0', 'P3', 'P1'][:k])
        assert all(not state['candidate']['ring_confirmed'] for state in path)
    changed = copy.deepcopy(rows)
    changed[1]['points'][0][1] = 70
    assert automatic_prefixes(changed, ['P2', 'P0', 'P3', 'P1'])[:3] == path[:3]
    assert automatic_prefixes(rows, ['P1', 'P3', 'P0', 'P2'])[-1] == path[-1]


def state(n, groups):
    return dict(n=n, identity_groups=[dict(selected=2*len(ms)>=n, members=[dict(id=i, pair_index=p) for i,p in ms]) for ms in groups])


def test_parity_loss_is_separate_from_regrouping():
    a = [('a', 0), ('b', 0)]
    old = state(4, [a, [('c', 0)], [('d', 0)]])
    new = state(5, [a, [('c', 0)], [('d', 0)], [('e', 0)]])
    t = transition(old, new)
    assert t['changed_coidentity_pairs'] == 0
    assert t['unchanged_identity_vote_losses'] == 1
    assert t['threshold_increased']
    split = state(5, [[a[0]], [a[1]], [('c', 0)], [('d', 0)], [('e', 0)]])
    t = transition(old, split)
    assert t['changed_coidentity_pairs'] == 1
    assert t['unchanged_identity_vote_losses'] == 0


def test_incomplete_and_unavailable_are_not_zero_quality():
    s = dict(n=3, minimum_support=2, identity_groups=[],
             node_consensus={'nodes':[{'support':2}]*3},
             ring_diagnostics={'tied_best':False, 'alternatives':[]},
             candidate={'points':None, 'footprint':None, 'reason':'no_source_ring',
                        'order_status':'needs_manual_order'})
    r = summarize_state(s)
    assert r['below_four'] and not r['complete_evaluable']
    assert footprint_metrics(None, [[0,0],[1,0],[1,1],[0,1]]) is None
    m = footprint_metrics([[0,0],[2,0],[2,1],[0,1]], [[0,0],[1,0],[1,1],[0,1]])
    assert m['omission_ref'] == 0 and m['extension_ref'] == 1
    assert m['D_ref'] == 1 and m['iou'] == pytest.approx(.5)
