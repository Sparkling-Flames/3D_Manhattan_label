import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.thesis_main import local_inputs as inputs


class LocalInputsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.enterContext(patch.object(inputs, 'ROOT', self.root))
        self.enterContext(patch.dict(inputs.os.environ, {}, clear=True))

    def put(self, name, content=b'original'):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def test_repository_default_independent_of_cwd(self):
        expected = self.put('data/external/label_data.zip')
        self.assertEqual(inputs.source_zip(), expected)

    def test_explicit_argument_and_environment(self):
        default = self.put('data/external/label_data.zip')
        configured = self.put('sources/original.zip')
        argument = self.put('sources/selected.zip')
        with patch.dict(inputs.os.environ, {'HOHONET_SOURCE_ZIP': 'sources/original.zip'}):
            self.assertEqual(inputs.source_zip(), configured)
            self.assertEqual(inputs.source_zip(argument), argument)
            with self.assertRaises(FileNotFoundError):
                inputs.source_zip('missing.zip')
        self.assertTrue(default.exists())

    def test_missing_never_searches_downloads_or_falls_back(self):
        self.put('Downloads/label_data.zip')
        with self.assertRaisesRegex(FileNotFoundError, 'No Downloads fallback'):
            inputs.source_zip()
        self.put('data/external/label_data.zip')
        with patch.dict(inputs.os.environ, {'HOHONET_SOURCE_ZIP': 'absent.zip'}):
            with self.assertRaises(FileNotFoundError):
                inputs.source_zip()

    def test_pinned_receipt_hash_and_explicit_directory(self):
        archive = self.put('evidence/receipt.json', b'{}')
        manifest = self.put('archives.json', json.dumps({'review.json': {
            'path': 'evidence/receipt.json', 'sha256': hashlib.sha256(b'{}').hexdigest()
        }}).encode())
        with patch.object(inputs, 'ARCHIVES', manifest):
            self.assertEqual(inputs.review_input('review.json'), archive)
            archive.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
                inputs.review_input('review.json')
            explicit = self.put('inputs/local_reviews/review.json', b'new input')
            with patch.dict(inputs.os.environ, {'HOHONET_REVIEW_INPUT_DIR': 'inputs/local_reviews'}):
                self.assertEqual(inputs.review_input('review.json'), explicit)
                explicit.unlink()
                with self.assertRaises(FileNotFoundError):
                    inputs.review_input('review.json')

    def test_real_archives_remain_pinned(self):
        with patch.object(inputs, 'ROOT', Path(__file__).resolve().parents[1]):
            for name in json.loads(inputs.ARCHIVES.read_text(encoding='utf-8')):
                self.assertTrue(inputs.review_input(name).is_file())


if __name__ == '__main__':
    unittest.main()


def test_source_planes_uses_configured_zip_and_rejects_wrong_geometry(tmp_path, monkeypatch):
    import zipfile
    import pytest
    from tools.thesis_main.analysis import scope_reference_reconstruction_20261016 as module

    archive_path = tmp_path / 'selected.zip'
    with zipfile.ZipFile(archive_path, 'w') as archive:
        archive.writestr('label_data/image_label.json', '{}')
    monkeypatch.setenv('HOHONET_SOURCE_ZIP', str(archive_path))
    monkeypatch.setattr(module, 'ORIGINAL_LAYOUTS', None)
    monkeypatch.setattr(module, 'convert_original', lambda raw: [])
    bundle = {'data': {'objects': [{'object_kind': 'gt_original', 'image_id': 'image',
                                   'object_id': 'original', 'points_1024x512': [[1, 2]]}]}}
    with pytest.raises(ValueError, match='original JSON / live GT conversion mismatch'):
        module.source_planes(bundle)
