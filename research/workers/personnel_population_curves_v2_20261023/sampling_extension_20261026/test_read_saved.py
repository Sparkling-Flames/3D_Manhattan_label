import gzip
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import read_saved


class SavedAccessTests(unittest.TestCase):
    def test_default_cohort_bom_seed_and_blank_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'sample.csv'
            path.write_text('\ufeffcohort,seed,Q\nold48,18446744073709551615,\npooled256,18446744073709551614,0\n', encoding='utf-8')
            spec = dict(path='unused', required_columns=['cohort','seed','Q'], default_filters={'cohort':'pooled256'})
            with patch.dict(read_saved.ACCESS['tables'], fixture=spec), patch.object(read_saved,'table_path',return_value=path):
                self.assertEqual(list(read_saved.rows('fixture'))[0]['seed'],'18446744073709551614')
                self.assertEqual(list(read_saved.rows('fixture',defaults=False))[0]['Q'],'')
                with self.assertRaisesRegex(ValueError,'missing/duplicate'):
                    list(read_saved.rows('fixture',typo='pooled256'))

    def test_bad_row_width_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'bad.csv';path.write_text('a,b\n1,2,3\n',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'row width'):
                list(read_saved.csv_rows(path))

    def test_geometry_identity_and_line_boundaries(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);record=dict(team_key='team',pool_id='pool',reference_id='ref',geometry=None)
            with gzip.open(root/'geometry.jsonl.gz','wt',encoding='utf-8') as stream:
                stream.write(json.dumps(record)+'\n')
            scalar={**record,'geometry_state_pointer':'geometry.jsonl.gz#L1'}
            with patch.object(read_saved,'BASE',root):
                self.assertEqual(read_saved.geometry(scalar),record)
                with self.assertRaisesRegex(ValueError,'identity mismatch'):
                    read_saved.geometry({**scalar,'team_key':'other'})
                with self.assertRaisesRegex(ValueError,'exceeds'):
                    read_saved.geometry({**scalar,'geometry_state_pointer':'geometry.jsonl.gz#L2'})
                with self.assertRaisesRegex(ValueError,'1-based'):
                    read_saved.geometry({**scalar,'geometry_state_pointer':'geometry.jsonl.gz#L0'})
            with self.assertRaisesRegex(ValueError,'leaves'):
                read_saved.resolve('../outside',root)


if __name__ == '__main__':
    unittest.main()
