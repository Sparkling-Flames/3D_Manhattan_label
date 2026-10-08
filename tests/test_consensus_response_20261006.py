import numpy as np


def test_full_difficulty_summary_keeps_fixed_panel_unknown_and_oos_apart(tmp_path, monkeypatch):
    from tools.thesis_main.analysis import difficulty_full_20261007 as m
    monkeypatch.setattr(m,'OUT',tmp_path)
    rows=[]
    for pool,n,label,scene,value in [('a',4,'简单','ordinary',.2),('b',2,'简单','ordinary',.8),('c',4,'未记录','ordinary',.4),('d',4,'简单','oos',.9)]:
        for method in ('mv50','mv_strict'):
            for k in range(1,n+1):
                rows.append(dict(pool=pool,image=pool,building=pool,condition='manual',gate='main_candidate',scene=scene,difficulty=label,
                    quality_compatible=True,n=n,method=method,version='original',k=k,D=value,O=value,E=0.))
    m.summarize(rows)
    s=m.read_csv(tmp_path/'summary.csv')
    selected=[r for r in s if r['scope']=='ordinary_quality' and r['limit']=='4' and r['difficulty']=='简单']
    assert all(r['images']=='a' and float(r['D'])==.2 for r in selected)
    assert any(r['scope']=='ordinary_quality' and r['difficulty']=='未知' and r['images']=='c' for r in s)
    assert any(r['scope']=='oos' and r['images']=='d' for r in s)


def test_difficulty_trajectory_keeps_start_change_endpoint_and_doorway_separate():
    from tools.thesis_main.analysis.difficulty_trajectory_20261007 import trajectory, in_panel
    c={k:{'D':v} for k,v in [(1,.6),(4,.5),(8,.4),(16,.4)]}
    r=trajectory(c)
    assert r['D1']==.6 and r['D_all']==.4
    assert np.isclose(r['gain_4_8'],.1) and r['gain_8_16']==0
    assert r['gain_16_20'] is None
    assert in_panel('doorway_annotatable', True)
    assert not in_panel('doorway_annotatable', False)
    assert not in_panel('oos', True)


def test_member_mean_matches_fixed_composition_enumeration():
    from itertools import combinations
    from tools.thesis_main.analysis.member_fusion_response_20261006 import member_mean
    errors = np.array([[0., 2.], [2., 0.], [3., 1.], [1., 5.], [5., 3.]])
    higher = np.array([True, True, False, False, False])
    for k, h in [(2, 2), (2, 0), (3, 1), (3, 2)]:
        groups = [s for s in combinations(range(5), k) if sum(higher[list(s)]) == h]
        expected = np.mean([errors[list(s)].mean(axis=0) for s in groups], axis=0)
        np.testing.assert_allclose(member_mean(errors, higher, k, h), expected)

from tools.thesis_main.analysis.consensus_response_20261006 import raw_distances
from tools.thesis_main.analysis.consensus_composition_20261006 import expected_pairwise


def test_pairwise_area_uses_distinct_people_and_fixed_union():
    # Two people share area 2; each has a different area 1.
    votes, distances = raw_distances(np.array([3, 1, 2]), np.array([2., 1., 1.]), 2)
    np.testing.assert_array_equal(votes, [[True, True, False], [True, False, True]])
    np.testing.assert_allclose(distances, [[0., .5], [.5, 0.]])
    # Independent one-person draws include identical-person pairs.
    q = votes.mean(axis=0)
    v1 = 2 * (np.array([2., 1., 1.]) @ (q * (1-q))) / 4
    assert distances[0, 1] == 2 * v1


def test_composition_pairwise_matches_unbalanced_pool_enumeration():
    from itertools import combinations
    distance = np.array([[0,1,2,4,3],[1,0,3,2,4],[2,3,0,2,1],[4,2,2,0,3],[3,4,1,3,0]],float)
    higher = np.array([True,True,False,False,False])
    for k,h in [(3,0),(3,1),(3,2),(2,2),(5,2)]:
        groups=[s for s in combinations(range(5),k) if sum(higher[list(s)])==h]
        exact=np.mean([np.mean([distance[a,b] for a,b in combinations(s,2)]) for s in groups])
        assert np.isclose(expected_pairwise(distance,higher,k,h),exact)


def test_local_patch_integrates_partial_tiles_and_uncovered_area():
    from shapely.geometry import box
    from tools.thesis_main.analysis.local_patch_response_20261006 import patch_weights
    # The patch includes half a tile, a whole tile and area nobody covers.
    tiles = [box(0,0,1,1), box(1,0,2,1)]
    patch = box(.5,0,3,1)
    weights = patch_weights(tiles,patch)
    assert np.isclose(weights @ np.array([1.,.25]), .3)
    assert np.isclose(weights.sum(), .6)


def test_person_image_centering_keeps_interaction_separate_from_main_means():
    from tools.thesis_main.analysis.worker_image_response_20261006 import centered_parts
    # Main differences are known; a checkerboard changes neither row nor column means.
    interaction=np.array([[1.,-1.],[-1.,1.]])
    matrix=np.array([[4.,8.],[6.,10.]])+interaction
    mean,image,worker,residual=centered_parts(matrix)
    assert mean==7.
    np.testing.assert_array_equal(image,[-1.,1.])
    np.testing.assert_array_equal(worker,[-2.,2.])
    np.testing.assert_array_equal(residual,interaction)
def test_human_difficulty_overlay_keeps_blank_and_separates_oos():
    from tools.thesis_main.analysis.difficulty_full_labels_20261007 import overlay
    row = dict(image='a', difficulty='未知', scene='ordinary', D=.3)
    decision = dict(updated_at='now', difficulty='中等', oos='是', doorway='否')
    updated = overlay(row, {'a': decision})
    assert updated['scene'] == 'oos' and updated['difficulty'] == '中等'
    assert updated['D'] == row['D'] and row['scene'] == 'ordinary'
    assert overlay(row, {'a': dict(decision, updated_at=None)}) == row
    door = overlay(row, {'a': dict(decision, oos='否', doorway='是', difficulty='困难')})
    assert door['scene'] == 'doorway_difficult'

def test_count_selection_join_keeps_reference_and_latest_scene():
    from tools.thesis_main.analysis.count_selection_20261007 import join_rows
    common=dict(image='a',method='mv50',version='original',n='16')
    c=dict(common,k='8',strategy='higher_rich',random_error_ref='.4',all_error_ref='.3',
           policy='original',higher_fraction='1',ref_symdiff_ref='.2',random_raw_pairwise_union='.5',
           raw_pairwise_union='.6',member_symdiff_union='.1',omission_ref='.1',extension_ref='.1')
    curve=dict(common,condition='manual',gate='main_candidate',building='b',difficulty='中等',
               scene='oos',pool='a',V='.2',O='.1',E='.3')
    rows=[dict(curve,k='8',D='.4'),dict(curve,k='16',D='.3'),
          dict(curve,k='8',D='.9',version='manual_revision')]
    r=join_rows([c],rows)[0]
    assert r['scene']=='oos' and r['difficulty']=='中等'
    assert abs(r['selection_gain']-.2)<1e-12
    assert abs(r['count_gain_8_16']-.1)<1e-12
    assert r['D20'] is None and abs(r['selected8_minus_random16']+.1)<1e-12
