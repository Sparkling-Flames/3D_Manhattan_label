import json
from pathlib import Path

from tools.thesis_main.analysis.active_log_utils import resolve_active_log_files
from tools.thesis_main.analysis.analyze_quality import load_active_logs, lookup_active_log_entry


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
    assert ("15", "100", "2") in logs
    assert ("100", "2") in logs
    assert logs[("15", "100", "2")]["active_time_value"] == 33.0
    assert logs[("100", "2")]["active_time_value"] == 33.0
    assert logs[("100", "2")]["active_time_source_file"] == current.name


def test_load_active_logs_keeps_reused_task_ids_project_scoped(tmp_path: Path):
    active_logs = tmp_path / "active_logs"
    active_logs.mkdir()

    log_file = active_logs / "active_times_2026-03-29.jsonl"
    log_file.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "project_id": "15",
                        "task_id": "100",
                        "annotator_id": "2",
                        "session_id": "p15",
                        "active_seconds": 10,
                    }
                ),
                json.dumps(
                    {
                        "project_id": "16",
                        "task_id": "100",
                        "annotator_id": "2",
                        "session_id": "p16",
                        "active_seconds": 20,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    logs = load_active_logs(str(active_logs))

    assert logs[("15", "100", "2")]["active_time_value"] == 10.0
    assert logs[("16", "100", "2")]["active_time_value"] == 20.0
    assert ("100", "2") not in logs
    assert logs[("__ambiguous__", "100", "2")]["active_time_project_ids"] == "15;16"

    entry, status = lookup_active_log_entry(logs, "16", "100", "2")
    assert status == "project+task+annotator"
    assert entry["active_time_value"] == 20.0

    entry, status = lookup_active_log_entry(logs, "17", "100", "2")
    assert entry is None
    assert status == "project_mismatch_ambiguous_active_log"


def test_load_active_logs_can_filter_by_server_received_date(tmp_path: Path):
    active_logs = tmp_path / "active_logs"
    active_logs.mkdir()

    log_file = active_logs / "active_times_2026-03-30.jsonl"
    log_file.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "project_id": "23",
                        "task_id": "200",
                        "annotator_id": "7",
                        "session_id": "old",
                        "active_seconds": 99,
                        "server_received_at": "2026-03-29T23:59:00",
                    }
                ),
                json.dumps(
                    {
                        "project_id": "23",
                        "task_id": "200",
                        "annotator_id": "7",
                        "session_id": "current",
                        "active_seconds": 12,
                        "server_received_at": "2026-03-30T00:01:00",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    logs = load_active_logs(str(active_logs), start_time="2026-03-30", end_time="2026-03-30")

    assert logs[("23", "200", "7")]["active_time_value"] == 12.0
    assert logs[("23", "200", "7")]["active_time_session_count"] == 1


def test_load_active_logs_keeps_annotation_sessions_separate(tmp_path: Path):
    active_logs = tmp_path / "active_logs"
    active_logs.mkdir()

    log_file = active_logs / "active_times_2026-06-30.jsonl"
    log_file.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "project_id": "23",
                        "task_id": "300",
                        "annotator_id": "8",
                        "annotation_id": "a1",
                        "session_id": "s1",
                        "active_seconds": 10,
                    }
                ),
                json.dumps(
                    {
                        "project_id": "23",
                        "task_id": "300",
                        "annotator_id": "8",
                        "annotation_id": "a1",
                        "session_id": "s1",
                        "active_seconds": 14,
                    }
                ),
                json.dumps(
                    {
                        "project_id": "23",
                        "task_id": "300",
                        "annotator_id": "8",
                        "annotation_id": "a1",
                        "session_id": "s2",
                        "active_seconds": 3,
                    }
                ),
                json.dumps(
                    {
                        "project_id": "23",
                        "task_id": "300",
                        "annotator_id": "8",
                        "annotation_id": "a2",
                        "session_id": "s1",
                        "active_seconds": 40,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    logs = load_active_logs(str(active_logs))

    assert logs[("23", "300", "8", "a1")]["active_time_value"] == 17.0
    assert logs[("23", "300", "8", "a1")]["active_time_session_count"] == 2
    assert logs[("23", "300", "8", "a2")]["active_time_value"] == 40.0
    assert logs[("23", "300", "8")]["active_time_value"] == 57.0

    entry, status = lookup_active_log_entry(logs, "23", "300", "8", annotation_id="a2")
    assert status == "project+task+annotator+annotation"
    assert entry["active_time_value"] == 40.0


def test_lookup_annotation_disables_task_level_fallback_for_duplicate_rows(tmp_path: Path):
    active_logs = tmp_path / "active_logs"
    active_logs.mkdir()
    (active_logs / "active_times_2026-06-30.jsonl").write_text(
        json.dumps(
            {
                "project_id": "23",
                "task_id": "301",
                "annotator_id": "8",
                "session_id": "legacy",
                "active_seconds": 99,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    logs = load_active_logs(str(active_logs))

    entry, status = lookup_active_log_entry(logs, "23", "301", "8", annotation_id="a1")
    assert status == "project+task+annotator"
    assert entry["active_time_value"] == 99.0

    entry, status = lookup_active_log_entry(
        logs,
        "23",
        "301",
        "8",
        annotation_id="a1",
        allow_task_level_fallback=False,
    )
    assert entry is None
    assert status == "annotation_missing_task_level_ambiguous"
