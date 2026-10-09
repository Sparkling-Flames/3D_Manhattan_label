import numpy as np
import pytest

from tools.thesis_main.analysis.difficulty_model_probe_20261009 import (
    orbit_metrics, boundary_curve, trace_inference,
)


def test_yaw_inverse_alignment_preserves_zero_and_detects_actual_change():
    boundary = np.stack([np.arange(8), np.arange(8)+20.]).astype(float)
    corner = np.arange(8)/8
    phases = [dict(y_bon_=np.roll(boundary, shift, axis=-1),
                   y_cor_=np.roll(corner, shift), cor_id=np.zeros((8, 2))) for shift in (0, 2, 4, 6)]
    result = orbit_metrics(phases, [0, 2, 4, 6], height=32)
    assert result['raw_boundary_rotation_mae_deg'] == 0.
    assert result['raw_corner_rotation_mae'] == 0.
    phases[1]['y_bon_'][0, 0] += 2
    assert orbit_metrics(phases, [0, 2, 4, 6], height=32)['raw_boundary_rotation_mae_deg'] > 0
    phases[1]['y_bon_'][0, 0] = np.nan
    with pytest.raises(ValueError, match='nonfinite'):
        orbit_metrics(phases, [0, 2, 4, 6], height=32)


def test_closed_boundary_covers_seam_without_straight_erp_interpolation():
    corners = np.array([[0, 100], [0, 400], [256, 100], [256, 400],
                        [512, 100], [512, 400], [768, 100], [768, 400]], float)
    curve = boundary_curve(corners)
    assert curve.shape == (2, 1024) and np.isfinite(curve).all()
    assert curve[0, 128] < 100
    assert curve[1, 128] > 400
    corners = np.insert(corners, 4, [[0, 120], [0, 400], [256, 100], [256, 400]], axis=0)
    with pytest.raises(ValueError, match='multiple_boundary'):
        boundary_curve(corners)


def test_trace_records_forced_operations_and_observed_fallback_without_changing_output():
    from lib.misc import post_proc
    def decoder(*args, **kwargs):
        return np.zeros((4, 2)), [dict(type=i%2, val=float(i), action='forced infer' if i==0 else 'ori') for i in range(4)]
    class Model:
        def infer(self, value):
            post_proc.gen_ww([1], [2], force_cuboid=False)
            post_proc.gen_ww([1], [2], force_cuboid=True)
            return {'cor_id': value}
    x = np.arange(16).reshape(8, 2)
    result, trace = trace_inference(Model(), x, decoder=decoder)
    assert result['cor_id'] is x
    assert trace['fallback_used'] is True
    assert trace['general_forced_infer_count'] == 1
    assert trace['decoder_calls'] == 2
    one, first = trace_inference(type('One', (), {'infer': lambda self, v: {'cor_id':v}})(), x, decoder=decoder)
    assert first['fallback_used'] is False and first['decoder_calls'] == 0
