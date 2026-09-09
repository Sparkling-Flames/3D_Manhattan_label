import numpy as np
import pytest
import warnings

from tools.thesis_main.analysis.prepare_human_bi_comparisons_20260908 import native_floor_polygon, comparison, evaluated
from tools.thesis_main.analysis.prepare_uncertainty_visual_review import helpers


def test_native_axes_and_missing_comparisons():
    audit, _ = helpers()
    # An asymmetric quadrilateral catches a one-axis reflection that symmetric
    # model-model self-IoU tests cannot detect.
    uv = np.array([[.04,.72],[.3,.67],[.55,.78],[.81,.64]])
    points = np.empty((8,2))
    points[1::2] = uv*[1024,512]
    points[::2] = np.c_[uv[:,0], 1-uv[:,1]]*[1024,512]
    original = points.copy()
    poly = native_floor_polygon(uv)
    assert audit.dp(poly, audit.footprint(points)) < 1e-12
    assert np.array_equal(points, original)
    r = comparison(audit, (poly,'computable'), (poly,'computable'), (None,'degenerate'))
    assert r['d_enclosed'] == 0
    assert np.isnan(r['minimum_residual']) and r['comparison_status']=='not_computable'
    assert evaluated(native_floor_polygon, [[0,.5],[.2,.7],[.7,.8]])[0] is None
    with pytest.raises(ValueError):
        native_floor_polygon([[0,.7],[1.1,.7],[.7,.8]])

    class WarningAudit:
        @staticmethod
        def dp(first, second):
            warnings.warn('test geometric warning', RuntimeWarning)
            return 0.125

    warned = comparison(WarningAudit, (poly,'computable'), (poly,'computable'), (poly,'computable'))
    assert warned['numeric_warning'] == 'test geometric warning'
    assert warned['d_enclosed'] == .125 and warned['comparison_status'] == 'computable'
