import numpy as np

from tools.thesis_main.analysis.audit_cluster_validation_return_20260922 import brute_affinity, wilson


def test_exact_partition_objective_and_monte_carlo_interval():
    # Two admissible edges conflict: a partition can preserve either, never both.
    d = np.array([[0., 2., 40.], [2., 0., 20.], [40., 20., 0.]])
    value, _ = brute_affinity(d, 25.6)
    assert np.isclose(value, (1 - 2 / 25.6) ** 2)
    lo, hi = wilson(np.array([.8]), np.array([80]))
    assert .69 < lo[0] < .71 and .87 < hi[0] < .88
