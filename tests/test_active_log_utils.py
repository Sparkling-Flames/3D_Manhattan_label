import json
from pathlib import Path

from tools.active_log_utils import resolve_active_log_files
from tools.analyze_quality import load_active_logs


def test_resolve_active_log_files_prefers_new_server_and_ignores_legacy(tmp_path: Path):
    active_logs = tmp_path / "active_logs"
    new_server = active_logs / "new_server"
    legacy = new_server / "legacy"
    new_server.mkdir(parents=True)
    legacy.mkdir(parents=True)

    good_file = new_server / "active_times_2026-03-29.jsonl"
    legacy_file = legacy / "active_times_2026-03-01.jsonl"

    good_file.write_text("", encoding="utf-8")
    legacy_file.write_text("", encoding="utf-8")

    resolved_dir, files = resolve_active_log_files(active_logs)
    assert resolved_dir == new_server
    assert files == [good_file]


def test_load_active_logs_does_not_read_new_server_legacy(tmp_path: Path):
    active_logs = tmp_path / "active_logs"
    new_server = active_logs / "new_server"
    legacy = new_server / "legacy"
    new_server.mkdir(parents=True)
    legacy.mkdir(parents=True)

    current = new_server / "active_times_2026-03-29.jsonl"
    archived = legacy / "active_times_2026-03-01.jsonl"

    current.write_text(
        json.dumps(
            {
                "task_id": "100",
                "annotator_id": "2",
                "session_id": "abc",
                "active_seconds": 33,
                "project_id": "15",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    archived.write_text(
        json.dumps(
            {
                "task_id": "100",
                "annotator_id": "2",
                "session_id": "old",
                "active_seconds": 999,
                "project_id": "15",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    logs = load_active_logs(str(active_logs))
    assert ("100", "2") in logs
    assert logs[("100", "2")]["active_time_value"] == 33.0
    assert logs[("100", "2")]["active_time_source_file"] == current.name
