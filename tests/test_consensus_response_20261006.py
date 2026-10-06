import numpy as np

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
