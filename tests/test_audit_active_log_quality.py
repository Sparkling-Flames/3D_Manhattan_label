import csv
import json
from pathlib import Path

from tools.audit_active_log_quality import audit_active_logs, main


def test_audit_active_logs_ignores_legacy_and_counts_quality_signals(tmp_path: Path) -> None:
    active_logs = tmp_path / "active_logs"
    new_server = active_logs / "new_server"
    legacy = new_server / "legacy"
    new_server.mkdir(parents=True)
    legacy.mkdir(parents=True)

    current = new_server / "active_times_2026-03-29.jsonl"
    legacy_file = legacy / "active_times_2026-03-01.jsonl"

    current.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "task_id": "100",
                        "annotator_id": "2",
                        "project_id": "15",
                        "session_id": "abc",
                        "script_version": "v1",
                        "active_seconds": 12,
                    }
                ),
                "{bad json",
                json.dumps(
                    {
                        "task_id": "100",
                        "annotator_id": "2",
                        "project_id": "15",
                        "session_id": "def",
                        "active_seconds": 18,
                    }
                ),
                json.dumps(
                    {
                        "task_id": "unknown",
                        "annotator_id": "3",
                        "project_id": "",
                        "session_id": "",
                        "script_version": "v1",
                        "active_seconds": 3,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    legacy_file.write_text(
        json.dumps(
            {
                "task_id": "999",
                "annotator_id": "old",
                "project_id": "15",
                "session_id": "legacy",
                "script_version": "old",
                "active_seconds": 999,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    summary, rows = audit_active_logs(active_logs)

    assert summary["selected_file_count"] == 1
    assert summary["selected_file_names"] == [current.name]
    assert summary["parsed_event_count"] == 3
    assert summary["parse_error_count"] == 1
    assert summary["unknown_task_count"] == 1
    assert summary["unknown_project_count"] == 1
    assert summary["unknown_session_count"] == 1
    assert summary["missing_script_version_count"] == 1
    assert summary["valid_task_annotator_pair_count"] == 1
    assert summary["multi_session_pair_count"] == 1
    assert rows[0]["file_name"] == current.name
    assert rows[0]["parse_error_count"] == 1
    assert rows[0]["missing_script_version_count"] == 1


def test_main_writes_summary_json_and_per_file_csv(tmp_path: Path) -> None:
    log_file = tmp_path / "active_times_2026-03-29.jsonl"
    log_file.write_text(
        json.dumps(
            {
                "task_id": "200",
                "annotator_id": "7",
                "project_id": "15",
                "session_id": "xyz",
                "script_version": "v2",
                "active_seconds": 9,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    summary_json = tmp_path / "summary.json"
    per_file_csv = tmp_path / "per_file.csv"

    exit_code = main(
        [
            str(log_file),
            "--summary-json",
            str(summary_json),
            "--per-file-csv",
            str(per_file_csv),
        ]
    )

    assert exit_code == 0
    summary = json.loads(summary_json.read_text(encoding="utf-8"))
    assert summary["selected_file_count"] == 1
    assert summary["parsed_event_count"] == 1

    with per_file_csv.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    assert rows[0]["file_name"] == log_file.name
