import importlib.util
import json
from pathlib import Path


def test_restore_concatenates_original_bytes_and_keeps_existing_file(tmp_path, monkeypatch):
    script = Path(__file__).resolve().parents[1] / "research/workers/personnel_mixture_comparison_20261022/restore_large_tables.py"
    spec = importlib.util.spec_from_file_location("restore_mixture_tables", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "__file__", str(tmp_path / "restore_large_tables.py"))
    (tmp_path / "part1").write_bytes(b"first\x00")
    (tmp_path / "part2").write_bytes(b"last\xff")
    (tmp_path / "LARGE_TABLE_STORAGE.json").write_text(json.dumps({"files": [{
        "path": "table.gz", "bytes": 11,
        "parts": [{"path": "part1", "bytes": 6}, {"path": "part2", "bytes": 5}]
    }]}), encoding="utf-8")
    module.main()
    assert (tmp_path / "table.gz").read_bytes() == b"first\x00last\xff"
    original_mtime = (tmp_path / "table.gz").stat().st_mtime_ns
    module.main()
    assert (tmp_path / "table.gz").stat().st_mtime_ns == original_mtime


def test_restore_explicit_package_root(tmp_path):
    script = Path(__file__).resolve().parents[1] / "research/workers/personnel_mixture_comparison_20261022/restore_large_tables.py"
    spec = importlib.util.spec_from_file_location("restore_external_package", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    (tmp_path / "part").write_bytes(b"source\x00bytes")
    (tmp_path / "LARGE_TABLE_STORAGE.json").write_text(json.dumps({"files": [{
        "path": "restored.gz", "bytes": 12,
        "parts": [{"path": "part", "bytes": 12}]
    }]}), encoding="utf-8")
    module.main(tmp_path)
    assert (tmp_path / "restored.gz").read_bytes() == b"source\x00bytes"
