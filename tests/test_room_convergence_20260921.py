import numpy as np

from tools.thesis_main.analysis.room_convergence_20260921 import split_sizes, stage_states, onset, median_bounds, image_curves, endpoint_check


def test_persistent_multicluster_and_all_balanced_splits():
    # Two genuinely supported groups stay unchanged, with balanced arrivals.
    parts = {k: (sum(1 << i for i in range(k) if i % 2 == 0),
                 sum(1 << i for i in range(k) if i % 2)) for k in range(2, 13)}
    states = stage_states(parts, 12, 3, 2, .1)
    assert states[8] == 0
    assert stage_states(parts, 12, 3, 1, .1)[8] == 2
    singleton = {k: tuple(1 << i for i in range(k)) for k in range(2, 13)}
    assert all(v != 0 for v in stage_states(singleton, 12, 3, 4, .2).values())
    assert split_sizes(5) == [2, 3]
    assert split_sizes(4) == [2]
    assert onset([2, 3, 4], [.3, .8, 1.]) == 3
    assert onset([2, 3], [.3, .7]) is None


def test_known_change_overrides_unknown_and_late_cap_failure():
    parts = {2: (1, 2), 3: (3, 4), 4: (3, 12), 5: (3, 12, 16)}
    # First anchor has no repeated support, but later promotion is known change.
    assert stage_states(parts, 5, 2, None, None)[2] == 2
    assert stage_states(parts, 5, 2, 2, .2)[3] == 2


def test_censoring_not_dropped_and_matched_endpoint_equals_full_curve():
    known = dict(possible_onset=12, conservative_onset=12, ks=list(range(2, 20)))
    censored = dict(possible_onset=None, conservative_onset=None, ks=[2, 3])
    assert median_bounds([known, censored]) == (8, float('inf'))
    assert median_bounds([known, known, censored]) == (12, 12)
    v = dict(ids=list('abcdef'), workers=list('ABCDEF'), image=np.zeros((6, 6)), job_id='test')
    orders = [list('ABCDEF'), list('FEDCBA')]
    _, full = image_curves((v, orders)); _, last = endpoint_check((v, orders, 6, 'test'))
    for a in last:
        b = next(c for c in full if c['method'] == a['method'] and c['profile'] == a['profile'] and c['tail'] == 3)
        assert (a['L'], a['U']) == (b['L'][-1], b['U'][-1])
    _, cropped = image_curves((dict(v, horizon=5), orders))
    assert all(c['L'] == [1.] for c in cropped if c['tail'] == 3)
    _, cropped = image_curves((dict(v, horizon=5), orders))
    assert all(c['L'] == [1.] for c in cropped if c['tail'] == 3)
