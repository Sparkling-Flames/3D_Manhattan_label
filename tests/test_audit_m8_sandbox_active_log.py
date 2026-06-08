import json
from pathlib import Path

from tools.paper_a_manhattan.audit_m8_sandbox_active_log import audit_m8_sandbox_active_log, main


def _write_jsonl(path: Path, rows: list[dict | str]) -> None:
    path.write_text(
        "\n".join(row if isinstance(row, str) else json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )


def _m8_event(**overrides):
    base = {
        "task_id": "3110",
        "project_id": "31",
        "project_name": "m8 sandbox",
        "annotator_id": "expert-1",
        "session_id": "m8-session",
        "page_type": "annotation",
        "active_seconds": 15,
        "active_seconds_fragment": 15,
        "event": "heartbeat",
        "telemetry_elapsed_seconds": 15,
        "log_context": "manhattan_ls_sandbox",
        "tool_stage": "M8",
        "script_variant": "timed",
        "is_sandbox": True,
        "sandbox_project": True,
        "exclude_from_primary_active_time": True,
        "exclude_from_thesis_evidence": True,
        "not_worker_facing": True,
        "not_p1_c1_c2_t1_v1_artifact": True,
        "manhattan_panel_version": "m8-dev-only-timed-0.1.0",
        "server_received_at": "2026-05-17T10:00:15",
    }
    base.update(overrides)
    return base


def test_valid_synthetic_m8_log_passes(tmp_path: Path) -> None:
    log = tmp_path / "active_times_2026-05-17.jsonl"
    _write_jsonl(
        log,
        [
            _m8_event(event="panel_loaded", active_seconds=0, active_seconds_fragment=0, server_received_at="2026-05-17T10:00:00"),
            _m8_event(active_seconds=15, active_seconds_fragment=15, server_received_at="2026-05-17T10:00:15"),
            _m8_event(active_seconds=30, active_seconds_fragment=15, server_received_at="2026-05-17T10:00:30"),
            _m8_event(event="panel_unloaded", active_seconds=31, active_seconds_fragment=1, server_received_at="2026-05-17T10:00:31"),
        ],
    )

    summary = audit_m8_sandbox_active_log(log)

    assert summary["audit_status"] == "pass"
    assert summary["n_m8_sandbox_events"] == 4
    assert summary["event_counts"]["heartbeat"] == 2
    assert summary["session_counts"] == {"m8-session": 4}
    assert summary["task_counts"] == {"3110": 4}
    assert summary["project_counts"] == {"31": 4}
    assert summary["exclusion_tag_fail_counts"] == {}
    assert summary["heartbeat_interval_summary"] == {
        "count": 1,
        "median": 15.0,
        "min": 15.0,
        "max": 15.0,
    }
    assert summary["errors"] == []
    assert summary["warnings"] == []
    assert "excluded from primary active_time" in " ".join(summary["notes"])


def test_missing_exclusion_tag_fails(tmp_path: Path) -> None:
    log = tmp_path / "active_times.jsonl"
    row = _m8_event()
    row.pop("exclude_from_primary_active_time")
    _write_jsonl(log, [row])

    summary = audit_m8_sandbox_active_log(log)

    assert summary["audit_status"] == "fail"
    assert summary["missing_required_field_counts"]["exclude_from_primary_active_time"] == 1
    assert summary["exclusion_tag_fail_counts"]["exclude_from_primary_active_time"] == 1


def test_false_primary_exclusion_tag_fails(tmp_path: Path) -> None:
    log = tmp_path / "active_times.jsonl"
    _write_jsonl(log, [_m8_event(exclude_from_primary_active_time=False)])

    summary = audit_m8_sandbox_active_log(log)

    assert summary["audit_status"] == "fail"
    assert summary["exclusion_tag_fail_counts"]["exclude_from_primary_active_time"] == 1


def test_no_m8_events_warns_and_ignores_official_active_time(tmp_path: Path) -> None:
    log = tmp_path / "active_times.jsonl"
    _write_jsonl(
        log,
        [
            {
                "task_id": "100",
                "project_id": "31",
                "annotator_id": "worker-1",
                "session_id": "official",
                "active_seconds": 22,
                "server_received_at": "2026-05-17T10:00:00",
            }
        ],
    )

    summary = audit_m8_sandbox_active_log(log)

    assert summary["audit_status"] == "warning"
    assert summary["n_m8_sandbox_events"] == 0
    assert "no_m8_sandbox_events" in summary["warnings"]
    assert summary["errors"] == []


def test_malformed_json_line_warns_when_rate_is_low(tmp_path: Path) -> None:
    log = tmp_path / "active_times.jsonl"
    rows = [_m8_event(active_seconds=i, active_seconds_fragment=1, server_received_at=f"2026-05-17T10:00:{i:02d}") for i in range(1, 11)]
    _write_jsonl(log, rows + ["{bad json"])

    summary = audit_m8_sandbox_active_log(log)

    assert summary["audit_status"] == "warning"
    assert summary["n_parse_errors"] == 1
    assert any(item.startswith("parse_error line=") for item in summary["warnings"])
    assert not any("parse_error_rate_too_high" in item for item in summary["errors"])


def test_malformed_json_line_fails_when_rate_is_high(tmp_path: Path) -> None:
    log = tmp_path / "active_times.jsonl"
    _write_jsonl(log, [_m8_event(), "{bad json"])

    summary = audit_m8_sandbox_active_log(log)

    assert summary["audit_status"] == "fail"
    assert summary["n_parse_errors"] == 1
    assert any("parse_error_rate_too_high" in item for item in summary["errors"])


def test_unknown_identity_warns(tmp_path: Path) -> None:
    log = tmp_path / "active_times.jsonl"
    _write_jsonl(log, [_m8_event(task_id="unknown", project_id="unknown", annotator_id="unknown")])

    summary = audit_m8_sandbox_active_log(log)

    assert summary["audit_status"] == "warning"
    assert summary["unknown_identity_counts"] == {
        "annotator_id": 1,
        "project_id": 1,
        "task_id": 1,
    }
    assert any("all_identity_fields_unknown" in item for item in summary["warnings"])


def test_forbidden_payload_field_fails_when_not_negation_guard(tmp_path: Path) -> None:
    log = tmp_path / "active_times.jsonl"
    _write_jsonl(log, [_m8_event(routing_decision="send_to_worker")])

    summary = audit_m8_sandbox_active_log(log)

    assert summary["audit_status"] == "fail"
    assert any("forbidden_payload_field" in item for item in summary["errors"])


def test_stdout_and_output_file(tmp_path: Path, capsys) -> None:
    log = tmp_path / "active_times.jsonl"
    _write_jsonl(log, [_m8_event()])

    assert main(["--input", str(log)]) == 0
    stdout = capsys.readouterr().out
    assert '"audit_status": "pass"' in stdout

    output = tmp_path / "audit.json"
    assert main(["--input", str(log), "--output", str(output)]) == 0
    summary = json.loads(output.read_text(encoding="utf-8"))
    assert summary["audit_status"] == "pass"
