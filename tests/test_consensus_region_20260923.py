import inspect

import numpy as np
import pytest

from tools.thesis_main.analysis.consensus_region_20260923 import (
    aggregate, centroid, compare_masks, wall_mask,
)


def test_curve_periodicity_and_validation():
    pairs = np.array([[[x, 130], [x, 380]] for x in (41, 290, 540, 801)], float)
    for mode in ("curve", "linear"):
        a = wall_mask(pairs, width=128, height=64, mode=mode)
        shifted = pairs.copy()
        shifted[:, :, 0] = (shifted[:, :, 0] + 24 * 1024 / 128) % 1024
        assert np.array_equal(wall_mask(shifted, width=128, height=64, mode=mode), np.roll(a, 24, axis=1))
        assert np.array_equal(a, wall_mask(pairs[::-1], width=128, height=64, mode=mode))
    assert not np.array_equal(wall_mask(pairs), wall_mask(pairs, mode="linear"))
    for change in ("nan", "x", "invert", "duplicate", "horizon"):
        bad = pairs.copy()
        if change == "nan": bad[0, 0, 1] = np.nan
        if change == "x": bad[0, 0, 0] += 1
        if change == "invert": bad[0, 0, 1] = 400
        if change == "duplicate": bad[1, :, 0] = bad[0, :, 0]
        if change == "horizon": bad[0, 0, 1] = 260
        with pytest.raises(ValueError): wall_mask(bad)
    with pytest.raises(ValueError, match="half_circle"):
        wall_mask([[[x, 100], [x, 400]] for x in (10, 100, 200)])


def test_centroid_is_not_shape_and_circular_direction_can_be_undefined():
    a = np.zeros((64, 128), bool)
    b = a.copy()
    a[16:48, 48:80] = True
    b[24:40, 32:96] = True
    result = compare_masks(a, b)
    assert result["erp_distance_px"] == 0
    assert 0 < result["iou"] < 1
    full = centroid(np.ones_like(a))
    assert full["circular_angle_rad"] is None
    assert full["erp_x_px"] == 511.5
    assert full["erp_y_px"] == 255.5
    assert centroid(np.zeros_like(a))["erp_x_px"] is None
    shift = compare_masks(np.roll(a, 3, axis=1), a)
    assert shift["circular_dx_px"] == pytest.approx(24)


def test_consensus_rules_no_gt_and_truthful_optional_dependency():
    a = np.zeros((16, 32), bool)
    a[4:12, 8:24] = True
    for method in ("mv50", "mv_strict", "medoid", "em_correct_probability", "greedy_empirical"):
        result = aggregate([a, a, a], method)
        assert np.array_equal(result["mask"], a)
    b = np.roll(a, 8, axis=1)
    assert np.array_equal(aggregate([a, b])["mask"], a | b)
    assert np.array_equal(aggregate([a, b], "mv_strict")["mask"], a & b)
    assert np.array_equal(aggregate([a, b], weights=[1, 0])["mask"], a)
    assert np.array_equal(aggregate([a, b], "medoid")["mask"], a)
    assert "gt" not in inspect.signature(aggregate).parameters
    with pytest.raises(TypeError): aggregate([a, b], gt=a)
    with pytest.raises(ValueError): aggregate([a, b], weights=[0, 0])
    with pytest.raises(ValueError): aggregate([a, b], "medoid", weights=[1, 1])
    staple = aggregate([a, b], "staple")
    assert staple["status"] in ("ok", "unavailable", "failed")
    if staple["status"] == "unavailable":
        assert staple["mask"] is None and staple["reason"] == "SimpleITK_not_installed"
