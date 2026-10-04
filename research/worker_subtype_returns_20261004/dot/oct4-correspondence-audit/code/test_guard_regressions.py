import json,sys,unittest,copy
from pathlib import Path
import numpy as np
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/'fixtures'));sys.path.insert(0,str(BASE/'patched'))
import consensus_lab_original as original
import consensus_lab_guarded as guarded

def load(name):return json.loads((BASE/'fixtures'/name).read_text())['records']

class GuardRegressions(unittest.TestCase):
    def test_known_two_record_mismatch_stops_single_certificate(self):
        r=load('known_certification_objective_mismatch.json')
        self.assertEqual(guarded.conditional_decision(r)['status'],'unresolved_actual_mapping_certificate_mismatch')
    def test_new_three_record_actual_diameter_violation_is_exposed(self):
        r=load('three_record_actual_mapping_diameter_counterexample.json')
        d=guarded.conditional_decision(r)
        self.assertEqual(d['status'],'unresolved_actual_mapping_certificate_mismatch')
        self.assertAlmostEqual(max(x['distance'] for x in d['actual_induced_pair_errors_deg']),5.579437932904212,places=10)
        self.assertIsNone(d['single_candidate'])
    def test_retains_original_defect_as_regression_fixture(self):
        r=load('three_record_actual_mapping_diameter_counterexample.json')
        d=original.conditional_decision(r)
        self.assertEqual(d['status'],'single_candidate_conditional_on_method_tolerance')
        self.assertFalse(d['cycle_audit']['conflicts'])
    def test_ordinary_consistent_control_uses_fixed_mapping_residuals(self):
        r=json.loads((BASE/'fixtures/reference_tests/inputs/current_excerpt.json').read_text())['images'][0]['annotations']
        d=guarded.conditional_decision(r);c=d['single_candidate']
        self.assertEqual(d['status'],'single_candidate_conditional_on_method_tolerance')
        by={x['id']:dict(x['mapping']) for x in c['alignments']};m=len(guarded.pairs(c))
        expected=[float(guarded.costs(guarded.pairs(c),guarded.pairs(obs))[np.arange(m),[by[obs['id']][i] for i in range(m)]].max()) for obs in sorted(r,key=lambda x:x['id'])]
        np.testing.assert_allclose(d['residuals_deg'],expected)
        self.assertFalse(c['ring_confirmed'])
    def test_nullable_metadata_stays_unknown_without_crash(self):
        r=load('known_certification_objective_mismatch.json');r[0]['source_point_indices']=None;r[0]['source_point_labels']=None
        d=guarded.derive_candidates(r)
        for c in d['candidates']:
            for slot in c['point_donors']:
                for donor in slot:
                    if donor['id']==r[0]['id']:
                        self.assertIsNone(donor['source_point_indices']);self.assertIsNone(donor['source_point_labels'])
    def test_guard_does_not_mutate_records(self):
        r=load('three_record_actual_mapping_diameter_counterexample.json');before=copy.deepcopy(r)
        guarded.conditional_decision(r);self.assertEqual(r,before)

if __name__=='__main__':unittest.main(verbosity=2)
