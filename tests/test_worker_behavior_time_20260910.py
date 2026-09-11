import numpy as np
import pandas as pd

from tools.thesis_main.analysis.worker_behavior_time_20260910 import clean_time, interpret, speed_quality_prediction


def test_timing_provenance_and_independent_axes():
    d = pd.DataFrame(dict(active_time_formal_available=[True, True, True, False, True],
        active_time_seconds=[30., 30., 30., 30., 0.],
        timing_status=['eligible', 'eligible_partial_session_coverage', 'eligible_with_protocol_deviation', 'eligible', 'eligible'],
        active_time_source=['log'] * 5))
    assert clean_time(d).tolist() == [True, False, False, False, False]
    assert clean_time(d, deviations=True).tolist() == [True, True, True, False, False]
    assert interpret('low', 'low') == '较快／参考偏差较低'
    assert interpret('low', 'high') == '较快／参考偏差较高'
    assert interpret('uncertain', 'high') == '速度未分明／参考偏差较高'


def test_speed_mapping_uses_training_workers_only():
    p = pd.DataFrame(dict(worker_id=['1', '2', '3'], effect=[-1., 0., 1.]))
    q = pd.DataFrame(dict(worker_id=['1', '2', '3'], effect=[2., 0., -2.]))
    mapped, slope = speed_quality_prediction(p, q)
    assert slope == -2.
    assert np.allclose(mapped.effect, [2., 0., -2.])
    assert np.allclose(p.effect, [-1., 0., 1.])
