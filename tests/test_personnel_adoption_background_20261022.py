"""Portable ZIP receipt-only batches must not hide the complete endpoint union."""
import importlib.util
from pathlib import Path

import pytest


SOURCE = Path(__file__).resolve().parents[1] / 'research/workers/personnel_exchange_adoption_followup_20261022/structure_followup/analyze_background_gradient.py'
spec = importlib.util.spec_from_file_location('background_adoption', SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_portable_union_precedes_receipt_only_batches(tmp_path):
    out = tmp_path / 'background'
    native = out / 'native'
    batch = native / 'batches/background_001'
    batch.mkdir(parents=True)
    (batch / 'COMPLETION.json').write_text('{}')
    for name in ('ENDPOINT_SCALARS.csv.gz', 'ENDPOINT_GEOMETRY.csv.gz'):
        (out / name).touch()
    assert module.endpoint_folders(out, native) == [out]


def test_native_batches_require_both_tables(tmp_path):
    native = tmp_path / 'native'
    batch = native / 'batches/background_001'
    batch.mkdir(parents=True)
    (batch / 'COMPLETION.json').write_text('{}')
    (batch / 'ENDPOINT_SCALARS.csv.gz').touch()
    with pytest.raises(FileNotFoundError):
        module.endpoint_folders(tmp_path, native)
    (batch / 'ENDPOINT_GEOMETRY.csv.gz').touch()
    assert module.endpoint_folders(tmp_path, native) == [batch]
