import csv
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / 'tools/thesis_main/analysis/stage_v21_full_chain_source.py'
spec = importlib.util.spec_from_file_location('adapter', MODULE)
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.repo = self.base / 'repo'
        self.study = self.repo / adapter.STUDY_REL
        (self.study / 'delivery_manifests').mkdir(parents=True)

    def manifest(self, content=b'frozen\n', path='source/research/input.csv'):
        with (self.study/'delivery_manifests/core_MANIFEST.csv').open('w', newline='') as f:
            w=csv.DictWriter(f, fieldnames=['path','bytes','sha256']); w.writeheader()
            w.writerow(dict(path=path, bytes=len(content), sha256=hashlib.sha256(content).hexdigest()))

    def put(self, path, content):
        path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(content)

    def test_exact_root_reuse_and_independent_copy(self):
        self.manifest(); original=self.repo/'research/input.csv'; self.put(original,b'frozen\n')
        plan=adapter.source_plan(self.repo,self.study)
        self.assertEqual(plan['status'],'ready'); self.assertEqual(plan['entries'][0]['selected']['kind'],'root_reuse')
        dest=self.base/'staged'; adapter.stage_copy(self.repo,self.study,dest,plan)
        target=dest/'source/research/input.csv'; self.assertEqual(target.read_bytes(),b'frozen\n')
        target.write_bytes(b'modified'); self.assertEqual(original.read_bytes(),b'frozen\n')
        self.assertFalse((self.study/'source').exists())

    def test_frozen_variant_beats_changed_current_root(self):
        self.manifest(); self.put(self.repo/'research/input.csv',b'changed\n')
        self.put(self.study/'source_variants/research/input.csv',b'frozen\n')
        plan=adapter.source_plan(self.repo,self.study)
        self.assertEqual(plan['entries'][0]['selected']['kind'],'variant')

    def test_missing_and_mismatch_fail_closed_without_copy(self):
        self.manifest(); self.put(self.repo/'research/input.csv',b'wrong!\n')
        plan=adapter.source_plan(self.repo,self.study)
        self.assertEqual(plan['status'],'blocked'); self.assertEqual(plan['blocked'],['research/input.csv'])
        dest=self.base/'not_created'
        with self.assertRaises(ValueError): adapter.stage_copy(self.repo,self.study,dest,plan)
        self.assertFalse(dest.exists())

    def test_exact_archive_supported_without_dedup(self):
        self.manifest(); self.put(self.study/'source/research/input.csv',b'frozen\n')
        self.assertEqual(adapter.source_plan(self.repo,self.study)['entries'][0]['selected']['kind'],'archive')

    def test_existing_destination_is_never_overwritten(self):
        self.manifest(); self.put(self.repo/'research/input.csv',b'frozen\n')
        dest=self.base/'existing'; dest.mkdir(); (dest/'sentinel').write_text('keep')
        with self.assertRaises(FileExistsError): adapter.stage_copy(self.repo,self.study,dest,adapter.source_plan(self.repo,self.study))
        self.assertEqual((dest/'sentinel').read_text(),'keep')

    def test_unsafe_manifest_rejected(self):
        for path in ['source/../../escape','/absolute','source/research\\escape','source/C:/escape']:
            with self.subTest(path=path):
                self.manifest(path=path)
                with self.assertRaises(ValueError): adapter.source_plan(self.repo,self.study)

    def test_source_change_after_preflight_rejected(self):
        self.manifest(); src=self.repo/'research/input.csv'; self.put(src,b'frozen\n')
        plan=adapter.source_plan(self.repo,self.study); src.write_bytes(b'changed\n')
        with self.assertRaisesRegex(ValueError,'changed after preflight'):
            adapter.stage_copy(self.repo,self.study,self.base/'staged',plan)
        self.assertEqual(src.read_bytes(),b'changed\n')

    def test_target_inside_historical_archive_rejected(self):
        self.manifest(); self.put(self.repo/'research/input.csv',b'frozen\n')
        with self.assertRaisesRegex(ValueError,'historical archive'):
            adapter.stage_copy(self.repo,self.study,self.study/'nested',adapter.source_plan(self.repo,self.study))
        self.assertFalse((self.study/'nested').exists())

    def test_checker_roots_are_isolated_and_identity_is_current(self):
        checker=self.repo/'tools/thesis_main/analysis/check_v21_full_chain_20261030.py'
        self.put(checker, b'''from pathlib import Path
def main():
    assert (ROOT/'research/data/releases/v2.1/pools/INPUT_SNAPSHOT.json').read_bytes() == b'current snapshot'
    assert (ROOT/'research/data/releases/v2.1/final_classification_downstream/TARGET_MAIN_EVENTS.csv.gz').read_bytes() == b'current events'
    assert ROOT != Path(__file__).resolve().parents[3]
    assert STUDY.name == 'staged'
    assert QT.name == 'v21_q_qt_common_support_20261030'
    (OUT/'test_ok.json').write_text('{}')
''')
        self.put(self.repo/'research/data/releases/v2.1/pools/INPUT_SNAPSHOT.json', b'current snapshot')
        self.put(self.repo/'research/data/releases/v2.1/final_classification_downstream/TARGET_MAIN_EVENTS.csv.gz', b'current events')
        reports=self.base/'reports'
        adapter.run_archived_checker(self.repo,self.base/'staged',reports)
        self.assertTrue((reports/'test_ok.json').is_file())
        self.assertFalse((self.study.parent/'local_review').exists())
        with self.assertRaises(FileExistsError):
            adapter.run_archived_checker(self.repo,self.base/'staged',reports)

    def test_checker_refuses_historical_report_destination(self):
        with self.assertRaisesRegex(ValueError,'historical archive'):
            adapter.run_archived_checker(self.repo,self.base/'staged',self.study.parent/'local_review')


if __name__ == '__main__':
    unittest.main()
