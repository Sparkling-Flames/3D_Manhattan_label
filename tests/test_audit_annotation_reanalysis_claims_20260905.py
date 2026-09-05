import unittest

import pandas as pd

from tools.thesis_main.analysis.audit_annotation_reanalysis_claims_20260905 import fit_effects, lobo, sign_diagnostic


class IndependentAuditChecks(unittest.TestCase):
    def test_unbalanced_additive_model_transfers_without_test_outcomes(self):
        rows = []
        for b, workers in [('a', [1, 2, 3]), ('b', [1, 2]), ('c', [2, 3])]:
            for task in range(2):
                for w in workers:
                    rows.append(dict(building_id=b, base_task_id=f'{b}{task}', worker_id=w,
                                     value=10 * task + ord(b) + {1: -2, 2: .5, 3: 1.5}[w]))
        d = pd.DataFrame(rows)
        effects = fit_effects(d, 'value')
        self.assertAlmostEqual(effects[3] - effects[1], 3.5)
        self.assertAlmostEqual(lobo(d, 'value')['r2'], 1.)

    def test_disconnected_workers_are_not_given_global_ranks(self):
        d = pd.DataFrame([dict(worker_id=1, base_task_id='a', value=1),
                          dict(worker_id=2, base_task_id='b', value=2)])
        with self.assertRaises(ValueError):
            fit_effects(d, 'value')

    def test_changed_peer_center_is_not_a_prediction_direction_failure(self):
        # A globally positive worker can be below the two stronger peers on the held-out task.
        result = sign_diagnostic('H_positive_direction', -.5, -.5)
        self.assertTrue(result['legacy_label_disagrees_with_local_outcome'])
        self.assertFalse(result['same_center_prediction_sign_error'])


if __name__ == '__main__':
    unittest.main()
