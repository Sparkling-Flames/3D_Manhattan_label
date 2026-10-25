import gzip

import pytest

from tools.thesis_main.analysis.audit_population_precision_geometry_20261025 import (
    self_check,
    stream_array,
)


def test_sample_frequency_and_exact_diagonal():
    self_check()


def test_stream_array_reads_all_objects(tmp_path):
    path = tmp_path / "small.json.gz"
    with gzip.open(path, "wt", encoding="utf-8") as f:
        f.write('[{"x":1},{"x":2}]')
    assert list(stream_array(path)) == [{"x": 1}, {"x": 2}]


def test_stream_array_rejects_missing_end(tmp_path):
    path = tmp_path / "incomplete.json.gz"
    with gzip.open(path, "wt", encoding="utf-8") as f:
        f.write('[{"x":1}')
    with pytest.raises(ValueError):
        list(stream_array(path))
