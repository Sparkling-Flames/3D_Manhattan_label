import itertools
import unittest

import numpy as np

from tools.thesis_main.analysis.audit_preflight_claims_20260906 import finite_variance_projection, metric_representation_probe


class PreflightAuditTest(unittest.TestCase):
    def test_projection_matches_all_subsets_with_shared_worker_edges(self):
        rng = np.random.default_rng(81)
        raw = rng.uniform(size=(7, 7))
        distance = (raw + raw.T) / 2
        np.fill_diagonal(distance, 0)
        for k in range(2, 8):
            values = [distance[np.ix_(s, s)].sum() / (k * (k - 1))
                      for s in itertools.combinations(range(7), k)]
            self.assertAlmostEqual(finite_variance_projection(distance, k), np.var(values), places=12)

    def test_fixed_panel_contains_cross_task_covariance(self):
        distance = np.abs(np.arange(6)[:, None] - np.arange(6)[None, :]) / 6
        # Identical task matrices are perfectly correlated under a common panel.
        fixed = finite_variance_projection((distance + distance) / 2, 3)
        independent = 2 * finite_variance_projection(distance, 3) / 4
        self.assertAlmostEqual(fixed, 2 * independent, places=12)

    def test_same_room_extra_collinear_point_exposes_linear_proxy_difference(self):
        probe = metric_representation_probe()
        self.assertEqual(probe['spherical_wall_band_distance'], 0.)
        self.assertGreater(probe['linear_wall_band_distance'], .04)


if __name__ == '__main__':
    unittest.main()
