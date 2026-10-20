"""Regression tests on preserved representative inputs, without native refitting."""
import importlib.util
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
CORNER = ROOT / 'research/workers/personnel_interchangeability_followup_20261020/audit_corner'
BUNDLE = ROOT / 'research/workers/personnel_interchangeability_20261020'
saved = os.environ.get('INTERCHANGEABILITY_BUNDLE')
os.environ['INTERCHANGEABILITY_BUNDLE'] = str(BUNDLE)
sys.path.insert(0, str(CORNER))
try:
    spec = importlib.util.spec_from_file_location('personnel_corner_followup_tests', CORNER / 'test_corner_distance.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    TestCorner = module.TestCorner
finally:
    sys.path.pop(0)
    if saved is None:
        os.environ.pop('INTERCHANGEABILITY_BUNDLE', None)
    else:
        os.environ['INTERCHANGEABILITY_BUNDLE'] = saved
