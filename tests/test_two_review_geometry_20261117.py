import numpy as np
from tools.thesis_main.analysis.audit_two_reviews_20261117 import project


def test_known_ray_depth_height_and_horizontal_seam():
    pairs = np.array([[[512., 128.], [512., 384.]],
                      [[0., 128.], [0., 384.]],
                      [[1024., 128.], [1024., 384.]]])
    floor, top, rho = project(pairs)
    np.testing.assert_allclose(rho, 1., atol=1e-12)
    np.testing.assert_allclose(floor[:, 1], -1.)
    np.testing.assert_allclose(top[:, 1], 1., atol=1e-12)
    np.testing.assert_allclose(floor[1], floor[2], atol=1e-12)
    np.testing.assert_allclose(top[1], top[2], atol=1e-12)


def test_upper_horizontal_direction_is_preserved():
    floor, top, rho = project(np.array([[[768., 128.], [512., 384.]]]))
    assert abs(np.dot(floor[0, [0, 2]], top[0, [0, 2]])) < 1e-12
    np.testing.assert_allclose(rho, 1., atol=1e-12)
