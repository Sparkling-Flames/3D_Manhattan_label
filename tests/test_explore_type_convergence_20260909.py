import numpy as np
from tools.thesis_main.analysis.explore_type_convergence_20260909 import split_people, pattern_sequence, evaluate_path


def test_people_split_and_exact_composition():
    labels={'1':1,'2':1,'3':1,'4':1,'5':2,'6':2,'7':2}
    h,v=split_people(labels,9)
    assert set(h).isdisjoint(v) and set(h)|set(v)==set(labels)
    assert sum(labels[x]==2 for x in h)==2
    seq,step=pattern_sequence({1:[0,1,2,3],2:[4,5]},[1,1,2])
    assert seq==[0,1,4,2,3,5] and step==3


def test_stable_multicluster_is_not_forced_to_one():
    # Two persistent modes, equally represented in training and separate validation.
    types=np.array([0,1,0,1,0,1])
    matrix=(types[:,None]!=types[None,:]).astype(float)*20
    rows=evaluate_path(matrix,[0,1,2,3],[4,5],6.,[2,4],np.zeros(6))
    assert [r['prefix_clusters'] for r in rows]==[2,2]
    assert all(r['distribution_tv']==0 for r in rows)
    assert rows[-1]['historical_largest_share']==.5
    try:
        evaluate_path(matrix,[0,1],[1,2],6.,[2],np.zeros(6))
    except ValueError:
        pass
    else:
        raise AssertionError('overlapping people accepted')
