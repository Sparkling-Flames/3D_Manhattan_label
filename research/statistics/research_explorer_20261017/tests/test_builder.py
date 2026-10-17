"""Portable, offline tests for pinned source loading and output validation."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / 'tools/thesis_main/analysis/build_research_explorer_20261017.py'
spec = importlib.util.spec_from_file_location('explorer_builder', SCRIPT)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def entry(path, data):
    return {'path':path, 'bytes':len(data), 'sha256':hashlib.sha256(data).hexdigest()}


class BuilderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        self.target = self.root / 'target'
        self.target.mkdir()
        self.data = b'id,value\n1,2\n'
        self.item = entry('table.csv', self.data)
        self.manifest = {'source_commit':builder.COMMIT, 'files':[self.item]}
        (self.source / 'table.csv').write_bytes(self.data)

    def tearDown(self):
        self.tmp.cleanup()

    def test_exact_export(self):
        result = builder.materialize(self.source, self.source, self.target, self.manifest)
        self.assertEqual(result, ['table.csv'])
        self.assertEqual((self.target / 'table.csv').read_bytes(), self.data)

    def test_rejects_changed_source(self):
        (self.source / 'table.csv').write_bytes(b'id,value\n1,3\n')
        with self.assertRaisesRegex(ValueError, 'mismatch'):
            builder.materialize(self.source, self.source, self.target, self.manifest)

    def test_rejects_commit_mismatch(self):
        self.manifest['source_commit'] = 'wrong'
        with self.assertRaisesRegex(ValueError, 'commit'):
            builder.materialize(self.source, self.source, self.target, self.manifest)

    def test_rejects_traversal(self):
        for path in ['../outside', '/outside', 'nested/../../outside']:
            with self.assertRaises(ValueError):
                builder.validate_relative(path)

    def test_rejects_symlink_escape(self):
        external = self.root / 'external.csv'
        external.write_bytes(self.data)
        (self.source / 'table.csv').unlink()
        (self.source / 'table.csv').symlink_to(external)
        with self.assertRaisesRegex(ValueError, 'leaves'):
            builder.materialize(self.source, self.source, self.target, self.manifest)

    def test_rejects_lfs_pointer(self):
        (self.source / 'table.csv').write_bytes(b'version https://git-lfs.github.com/spec/v1\n')
        with self.assertRaisesRegex(ValueError, 'Git LFS'):
            builder.materialize(self.source, self.source, self.target, self.manifest)

    def test_git_reads_pinned_blob_not_new_head_or_worktree(self):
        def git(*args):
            return subprocess.check_output(['git','-C',str(self.source),*args], text=True, stderr=subprocess.DEVNULL).strip()
        git('init')
        git('config','user.name','Test')
        git('config','user.email','test@example.invalid')
        git('add','table.csv')
        git('commit','-m','frozen fixture')
        pinned = git('rev-parse','HEAD')
        (self.source / 'table.csv').write_bytes(b'id,value\n1,99\n')
        git('commit','-am','newer snapshot must not be read')
        (self.source / 'table.csv').write_bytes(b'uncommitted data')
        original_commit = builder.COMMIT
        try:
            builder.COMMIT = pinned
            self.manifest['source_commit'] = pinned
            builder.materialize(self.source, None, self.target, self.manifest)
        finally:
            builder.COMMIT = original_commit
        self.assertEqual((self.target / 'table.csv').read_bytes(), self.data)

    def test_output_hash_and_extra_file_guard(self):
        item = entry('index.json', b'{}')
        expected = {'source_commit':builder.COMMIT,'files':[item]}
        (self.target / 'index.json').write_bytes(b'{}')
        self.assertEqual(builder.verify_output(self.target, expected), 1)
        (self.target / 'unexpected.json').write_bytes(b'{}')
        with self.assertRaisesRegex(ValueError, 'unexpected'):
            builder.verify_output(self.target, expected)
        (self.target / 'unexpected.json').unlink()
        (self.target / 'index.json').write_bytes(b'[]')
        with self.assertRaisesRegex(ValueError, 'index.json'):
            builder.verify_output(self.target, expected)

    def test_display_conversion_preserves_missing_and_ids(self):
        self.assertIsNone(builder.parse_cell('', 'B8L2'))
        self.assertEqual(builder.parse_cell('0', 'B8L2'), 0)
        self.assertEqual(builder.parse_cell('001', 'worker_id'), '001')
        self.assertEqual(builder.parse_cell('true', 'quality_usable'), True)
        self.assertEqual(builder.parse_cell('test@example.invalid', 'comment'), '[redacted email]')


if __name__ == '__main__':
    unittest.main(verbosity=2)
