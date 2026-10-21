import hashlib,json,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
from tools.thesis_main.analysis.scope_quality_scoring_20261016 import scoring_engine,ROOT

INPUTS=ROOT/'research/statistics/b8l2_shared_v6_20261016/inputs'
DIRECT=INPUTS/'measurement_engine'
MODELS=INPUTS/'working_models.py'
class DirectEngineTests(unittest.TestCase):
 def test_direct_engine_does_not_open_zip(self):
  with patch('zipfile.ZipFile',side_effect=AssertionError('ZIP must not be opened')):
   with scoring_engine(DIRECT,MODELS) as (engine,models):
    self.assertEqual(Path(engine.__file__).resolve(),(DIRECT/'src/quality.py').resolve())
    self.assertTrue(callable(engine.measure))
 def test_old_zip_argument_prefers_existing_directory(self):
  with patch('zipfile.ZipFile',side_effect=AssertionError('ZIP must not be opened')):
   with scoring_engine(INPUTS/'measurement_engine.zip',MODELS) as (engine,models):
    self.assertEqual(Path(engine.__file__).resolve(),(DIRECT/'src/quality.py').resolve())
 def test_legacy_archive_still_supported(self):
  with tempfile.TemporaryDirectory() as d:
   old=Path(d)/'legacy.zip'
   with zipfile.ZipFile(old,'w') as z:
    for p in DIRECT.rglob('*'):
     if p.is_file() and p.suffix in ['.py','.json']:z.writestr(p.relative_to(DIRECT).as_posix(),p.read_bytes())
   with scoring_engine(old,MODELS) as (engine,models):self.assertTrue(callable(engine.measure))
 def test_original_engine_files_are_unchanged(self):
  manifest=json.loads((INPUTS/'measurement_engine_manifest.json').read_text(encoding='utf8'))
  for r in manifest['files']:
   self.assertEqual(hashlib.sha256((DIRECT/r['path']).read_bytes()).hexdigest(),r['sha256'])
if __name__=='__main__':unittest.main()
