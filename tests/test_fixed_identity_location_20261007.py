import numpy as np
from tools.thesis_main.analysis.fixed_identity_location_20261007 import compare_locations


def group(values):
    return dict(feature_id='c',support=len(values),center=[[128,120],[128,390]],
        members=[dict(id=str(i),worker=str(i),pair_index=0,points=[[128,t],[128,b]]) for i,(t,b) in enumerate(values)])


def test_marginal_majorities_do_not_invent_joint_support():
    g=group([(120,390)]*2+[(120,430)]*4+[(160,390)]*4)
    r=compare_locations(g,18,9)
    split=r['estimates']['split_mode']
    assert (split['top_support'],split['bottom_support'],split['joint_support'])==(6,6,2)
    assert r['existence_support']==10 and r['vote_denominator']==18
    assert r['estimates']['adaptive']['choice']=='split_mode'
    assert split['top_full_pool_majority'] is False


def test_joint_tie_is_not_broken_by_gt_or_index():
    r=compare_locations(group([(120,390)]*2+[(160,430)]*2),6,9)
    assert r['estimates']['joint_mode']['center'] is None
    assert r['estimates']['adaptive']['choice']=='all_median'
    assert r['existence_support']==4


def test_single_mode_makes_three_routes_equal():
    r=compare_locations(group([(120,390)]*3),4,9)
    for route in ['joint_mode','split_mode','adaptive']:
        np.testing.assert_allclose(r['estimates'][route]['center'],[[128,120],[128,390]])
    assert r['estimates']['adaptive']['choice']=='joint_mode'


def test_expanded_layout_does_not_omit_unresolved_identity_to_close_ring():
    from tools.thesis_main.analysis.correspondence_expanded_20261007 import location_layout
    result = {'ring_diagnostics': {'feature_ids': ['a', 'b', 'c']}}
    locations = [dict(feature_id=f, estimates={'joint_mode': {'center': center}})
                 for f, center in [('a', [[128,120],[128,390]]),
                                   ('b', None), ('c', [[640,120],[640,390]])]]
    layout = location_layout(result, locations, 'joint_mode')
    assert layout['points'] is None
    assert layout['feature_ids'] == ['a', 'b', 'c']
    assert layout['unresolved_nodes'] == ['b']
    assert layout['reason'] == 'unresolved_location'


def test_maximum_subset_is_not_largest_greedy_cluster():
    from tools.thesis_main.analysis.fixed_identity_location_20261007 import largest_compatible_sets
    d=np.array([[0,4,4,1],[4,0,4,8],[4,4,0,8],[1,8,8,0]],float)
    assert largest_compatible_sets(d,5)==[(0,1,2)]
    d[1,2]=d[2,1]=8
    assert largest_compatible_sets(d,5)==[(0,1),(0,2),(0,3)]


def test_maximum_sets_match_independent_enumeration_on_four_nodes():
    import itertools
    from tools.thesis_main.analysis.fixed_identity_location_20261007 import largest_compatible_sets
    edges=list(itertools.combinations(range(4),2))
    for bits in range(64):
        d=np.full((4,4),2.);np.fill_diagonal(d,0)
        for k,(a,b) in enumerate(edges):
            if bits>>k&1:d[a,b]=d[b,a]=0
        subsets=[s for n in range(1,5) for s in itertools.combinations(range(4),n)
                 if all(d[a,b]<=1 for a,b in itertools.combinations(s,2))]
        best=max(map(len,subsets))
        assert largest_compatible_sets(d,1)==sorted(s for s in subsets if len(s)==best)
