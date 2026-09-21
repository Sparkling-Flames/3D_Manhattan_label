import numpy as np

from tools.thesis_main.analysis import worker_cluster_sensitivity_20260921 as m


def test_subset_and_replay_match_reference(monkeypatch):
    v = dict(image_id='x', code='x', building='b', N=8,
             ids=list('abcdefgh'), workers=list('ABCDEFGH'),
             d=np.array([[0 if i//3 == j//3 else 60 for j in range(8)] for i in range(8)]))
    sub = m.subset(v, [0, 2, 5])
    assert sub['workers'] == ['A', 'C', 'F'] and sub['d'][0, 1] == 0
    orders = [list('ABCDEFGH'), list('HGFEDCBA')]
    actual = m.replay(v, orders)
    monkeypatch.setattr(m.ref, 'EPS', [.1])
    monkeypatch.setattr(m.ref, 'TAILS', [3])
    monkeypatch.setattr(m.ref, 'PROFILES', [('uncapped', None, None), ('cap3_s20', 3, .2)])
    expected = m.ref.run((v, orders))[0]
    for row in actual:
        match = next(r for r in expected if r['method'] == row['method'] and r['profile'] == row['profile'])
        for key in ['status', 'possible_onset', 'conservative_onset', 'final_stable_probability']:
            assert row[key] == match[key]
