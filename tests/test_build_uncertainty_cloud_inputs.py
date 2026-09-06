import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from tools.thesis_main.data_prep.build_uncertainty_cloud_inputs import (
    context_key, resolve_member, resolve_raw_version, pair_equality, deduplicate_partitions,
)


class CloudInputChecks(unittest.TestCase):
    def test_noncanonical_cluster_member_keeps_its_actual_version(self):
        item=dict(canonical_annotation_id='a', selected_canonical_version='false')
        self.assertEqual(resolve_raw_version(item, {'a'}), ('raw_version_only', '', 'a'))
        item['selected_canonical_version']='true'
        self.assertEqual(resolve_raw_version(item, {'a'}), ('matched', 'a', 'a'))
    def test_context_resolution_does_not_cross_blocks_or_revisions(self):
        rows = [dict(canonical_annotation_id=f'a{b}', stage='C2-A-RP', block_index=str(b),
                     base_task_id='image', raw_condition='manual', worker_id='1') for b in [1, 2]]
        self.assertNotEqual(context_key(rows[0]), context_key(rows[1]))
        self.assertEqual(resolve_member(rows, 'C2-A-RP', 'image', 'manual', '1')[0], 'ambiguous')
        self.assertEqual(resolve_member(rows, 'C2-A-RP', 'image', 'manual', '1', block='2'), ('matched', 'a2'))
        self.assertEqual(resolve_member(rows, 'C2-A-RP', 'image', 'manual', '2')[0], 'missing')

    def test_equality_distinguishes_raw_cycle_and_degenerate(self):
        a = [[0, 100], [0, 400], [256, 120], [256, 380], [600, 80], [600, 420], [900, 120], [900, 380]]
        shifted = a[2:] + a[:2]
        self.assertTrue(pair_equality(a, a)['raw_sequence_equal'])
        result = pair_equality(a, shifted)
        self.assertFalse(result['raw_sequence_equal'])
        self.assertTrue(result['ordered_cycle_equal'])
        reverse = [p for pair in list(zip(a[::2], a[1::2]))[::-1] for p in pair]
        self.assertTrue(pair_equality(a, reverse)['ordered_cycle_equal'])
        b = [p[:] for p in a]; b[0][1] += 1
        self.assertFalse(pair_equality(a, b)['ordered_cycle_equal'])
        self.assertEqual(pair_equality([], [])['comparison_status'], 'not_evaluable')

    def test_repeated_k_partition_must_be_consistent_and_keep_ties(self):
        def row(k, members):
            return dict(stage='P1', condition='manual', base_task_id='i', k=str(k),
                        full_cluster_worker_memberships_json=members,
                        full_structure_status='supported_multimodal', full_partition_status='unique',
                        strict_support='4', full_cluster_count='2', full_second_cluster_support='2')
        rows = [row(15, '[["1","2"],["3","4"]]'), row(16, '[["1","2"],["3","4"]]')]
        self.assertEqual(len(deduplicate_partitions(rows)), 1)
        insufficient = {**row(20, ''), 'evaluable':'False'}
        self.assertEqual(len(deduplicate_partitions(rows + [insufficient])), 1)
        with self.assertRaises(ValueError):
            deduplicate_partitions(rows + [row(17, '[["1","3"],["2","4"]]')])

    def test_exported_bundle_preserves_unknown_room_and_human_blanks(self):
        from tools.thesis_main.data_prep import build_uncertainty_cloud_inputs as m
        package=Path(__file__).resolve().parents[1]/m.PACKAGE
        # Integration check uses the delivered immutable dataset, not a mirrored synthetic implementation.
        self.assertTrue(m.validate(package)['offline'])
        real_read=m.read_csv
        def forged_room(path):
            rows=real_read(path)
            if Path(path).name=='images.csv': rows[0]['room_instance_id']='invented_from_building'
            return rows
        with patch.object(m,'read_csv',side_effect=forged_room):
            with self.assertRaises(AssertionError): m.validate(package)
        with tempfile.TemporaryDirectory() as directory:
            original={'items':[{'human_review':{'scope':'','notes':''}}]}
            p=Path(directory)/'human.json';m.write_json(p,original)
            self.assertEqual(m.read_json(p),original)


if __name__ == '__main__':
    unittest.main()
