import numpy as np
import pytest
from shapely.geometry import box

from tools.thesis_main.analysis.audit_supervisor_gt_sensitivity_20260922 import (
    region_mesh, region_score, error_components, is_substantive_revision,
    wall_mask, mask_iou, mask_centroid,
)


def test_gt_change_does_not_change_votes_and_error_identity_is_exact():
    small, large = box(-1, -1, 1, 1), box(-2, -2, 2, 2)
    mesh = region_mesh([small, large, small])
    vote = mesh['votes'].mean(axis=0) > .5
    old = region_score(mesh, vote, large)
    new = region_score(mesh, vote, small)
    assert old['iou'] == pytest.approx(.25)
    assert new['iou'] == pytest.approx(1)
    assert old['centroid_norm'] == pytest.approx(0)
    for gt in [small, large, box(3, 3, 4, 4)]:
        terms = error_components(mesh, gt)
        direct = np.mean([p.symmetric_difference(gt).area / gt.area
                          for p in [small, large, small]])
        assert terms['shared_bias'] + terms['disagreement'] == pytest.approx(direct)
    assert not is_substantive_revision(np.array([[1., 2], [3, 4]]),
                                      np.array([[3., 4], [1, 2]]))
    assert is_substantive_revision(np.array([[1., 2], [3, 4]]),
                                   np.array([[3., 4], [1, 4]]))


def test_wall_region_does_not_depend_on_input_ring_and_centroid_is_periodic():
    p = np.array([[[x, t], [x, b]] for x, t, b in
                  [(0, 100, 400), (256, 90, 410), (512, 130, 390), (768, 100, 400)]])
    a = wall_mask(p)
    np.testing.assert_array_equal(a, wall_mask(p[[2, 0, 3, 1]]))
    b = np.roll(a, 40, axis=1)
    assert mask_iou(a, b) == mask_iou(np.roll(a, 70, axis=1), np.roll(b, 70, axis=1))
    ca, cb = mask_centroid(a), mask_centroid(b)
    assert ca['concentration'] == pytest.approx(cb['concentration'])
    assert (cb['angle']-ca['angle']) % (2*np.pi) == pytest.approx(2*np.pi*40/256)
