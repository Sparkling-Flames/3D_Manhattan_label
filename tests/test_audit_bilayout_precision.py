import numpy as np
import pytest

from tools.thesis_main.analysis.audit_bilayout_precision import floor_gap, pixel_uv


def test_floor_precision_preserves_native_coordinates_and_rejects_degeneracy():
    pixels = np.array([[127, 383], [383, 383], [639, 383], [895, 383]])
    uv = pixel_uv(pixels)
    original = uv.copy()
    assert np.array_equal(uv, (pixels + 0.5) / [1024, 512])
    assert floor_gap(uv, np.roll(uv[::-1], 1, axis=0)) == pytest.approx(0, abs=1e-12)
    shifted = uv + [0, 0.00001]
    assert np.array_equal(np.round(uv * [1024, 512] - 0.5),
                          np.round(shifted * [1024, 512] - 0.5))
    assert 0 < floor_gap(uv, shifted) < 0.01
    assert np.array_equal(uv, original)
    for invalid in (uv[:2], np.array([[0.1, 0.5], [0.3, 0.75], [0.8, 0.75]])):
        with pytest.raises(ValueError):
            floor_gap(invalid, uv)
