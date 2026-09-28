import numpy as np

from tools.thesis_main.analysis.explore_layout_metrics_20260926 import effect_probe


def test_image_adjustment_recovers_known_effects_despite_reversed_raw_means():
    result = effect_probe()
    truth = np.asarray(result['true_worker_effects'])
    balanced, confounded, disconnected = result['designs']
    assert balanced['worker_rank_correlation_raw'] == 1
    assert confounded['worker_rank_correlation_raw'] == -1
    for design in (balanced, confounded):
        assert design['identifiable']
        np.testing.assert_allclose(design['two_way_effects'], truth, atol=1e-12)
        np.testing.assert_allclose(design['same_image_effects'], truth, atol=1e-12)
    assert not disconnected['identifiable']
    assert disconnected['two_way_effects'] is None
    assert disconnected['same_image_effects'] is None
    assert disconnected['status'] == 'cross_component_worker_effects_not_identifiable'
