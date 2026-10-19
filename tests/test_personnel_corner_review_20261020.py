import numpy as np

from tools.thesis_main.analysis.personnel_corner_review_20261020 import project, pixel_delta


def test_projection_scale_and_horizon_sensitivity():
    bottom, top = project([[512,128],[512,384],[768,128],[768,384],[0,128],[0,384]])
    np.testing.assert_allclose(bottom[0], [0,-1,-1], atol=1e-12)
    np.testing.assert_allclose(top[0], [0,1,-1], atol=1e-12)
    far, _ = project([[512,128],[512,258],[768,128],[768,258],[0,128],[0,258]])
    nearer, _ = project([[512,128],[512,259],[768,128],[768,259],[0,128],[0,259]])
    assert np.linalg.norm(far[0]-nearer[0]) > 20


def test_pixel_wrap_uses_short_path():
    np.testing.assert_allclose(pixel_delta(np.array([[1023.,300.]]),np.array([[1.,302.]])), [[2.,2.]])
