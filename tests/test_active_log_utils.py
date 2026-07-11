import json
from pathlib import Path

from tools.thesis_main.analysis.active_log_utils import resolve_active_log_files
from tools.thesis_main.analysis.quality_core.active_time import is_unknown_annotation_id, load_active_logs, lookup_active_log_entry, lookup_unknown_active_time_audit
from tools.thesis_main.analysis.c1_live_collection_monitor import active_time_for_annotation


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


def test_short_unknown_bootstrap_merges_to_single_actual_without_double_count(tmp_path: Path):
    active_logs = tmp_path / "active_logs"
    active_logs.mkdir()
    (active_logs / "active_times_2026-06-30.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "project_id": "23",
                        "task_id": "400",
                        "annotator_id": "8",
                        "annotation_id": "unknown_annotation",
                        "session_id": "s1",
                        "active_seconds": 4,
                        "server_received_at": "2026-07-01T10:00:00",
                    }
                ),
                json.dumps(
                    {
                        "project_id": "23",
                        "task_id": "400",
                        "annotator_id": "8",
                        "annotation_id": "a123",
                        "active_time_alias_from": "23|400|8|unknown_annotation",
                        "active_time_alias_reason": "short_unknown_bootstrap",
                        "late_binding_status": "short_unknown_bootstrap_merged",
                        "session_id": "s1",
                        "active_seconds": 4,
                        "server_received_at": "2026-07-01T10:00:08",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    logs = load_active_logs(str(active_logs))

    assert logs[("23", "400", "8")]["active_time_value"] == 4.0
    assert logs[("23", "400", "8", "a123")]["active_time_value"] == 4.0
    assert ("23", "400", "8", "unknown_annotation") not in logs


def test_long_unknown_does_not_merge_but_actual_time_remains(tmp_path: Path):
    active_logs = tmp_path / "active_logs"
    active_logs.mkdir()
    (active_logs / "active_times_2026-06-30.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "project_id": "23",
                        "task_id": "401",
                        "annotator_id": "8",
                        "annotation_id": "unknown_annotation",
                        "session_id": "s1",
                        "active_seconds": 6,
                        "server_received_at": "2026-07-01T10:00:00",
                    }
                ),
                json.dumps(
                    {
                        "project_id": "23",
                        "task_id": "401",
                        "annotator_id": "8",
                        "annotation_id": "a123",
                        "session_id": "s1",
                        "active_seconds": 10,
                        "server_received_at": "2026-07-01T10:00:08",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    logs = load_active_logs(str(active_logs))

    assert logs[("23", "401", "8")]["active_time_value"] == 16.0
    assert logs[("23", "401", "8", "unknown_annotation")]["active_time_value"] == 6.0
    assert logs[("23", "401", "8", "a123")]["active_time_value"] == 10.0


def test_non_continuous_unknown_does_not_merge_but_actual_time_remains(tmp_path: Path):
    active_logs = tmp_path / "active_logs"
    active_logs.mkdir()
    (active_logs / "active_times_2026-06-30.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "project_id": "23",
                        "task_id": "402",
                        "annotator_id": "8",
                        "annotation_id": "unknown_annotation",
                        "session_id": "s1",
                        "active_seconds": 4,
                        "server_received_at": "2026-07-01T10:00:00",
                    }
                ),
                json.dumps(
                    {
                        "project_id": "23",
                        "task_id": "402",
                        "annotator_id": "8",
                        "annotation_id": "a123",
                        "active_time_alias_from": "23|402|8|unknown_annotation",
                        "active_time_alias_reason": "short_unknown_bootstrap",
                        "late_binding_status": "short_unknown_bootstrap_merged",
                        "session_id": "s1",
                        "active_seconds": 4,
                        "server_received_at": "2026-07-01T10:01:00",
                    }
                ),
                json.dumps(
                    {
                        "project_id": "23",
                        "task_id": "402",
                        "annotator_id": "8",
                        "annotation_id": "a123",
                        "session_id": "s1",
                        "active_seconds": 12,
                        "server_received_at": "2026-07-01T10:01:05",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    logs = load_active_logs(str(active_logs))

    assert logs[("23", "402", "8")]["active_time_value"] == 16.0
    assert logs[("23", "402", "8", "unknown_annotation")]["active_time_value"] == 4.0
    assert logs[("23", "402", "8", "a123")]["active_time_value"] == 12.0


def test_multiple_actual_annotations_keep_actual_times_and_leave_unknown_unassigned(tmp_path: Path):
    active_logs = tmp_path / "active_logs"
    active_logs.mkdir()
    (active_logs / "active_times_2026-06-30.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "project_id": "23",
                        "task_id": "403",
                        "annotator_id": "8",
                        "annotation_id": "unknown_annotation",
                        "session_id": "s1",
                        "active_seconds": 4,
                        "server_received_at": "2026-07-01T10:00:00",
                    }
                ),
                json.dumps(
                    {
                        "project_id": "23",
                        "task_id": "403",
                        "annotator_id": "8",
                        "annotation_id": "a123",
                        "active_time_alias_from": "23|403|8|unknown_annotation",
                        "active_time_alias_reason": "short_unknown_bootstrap",
                        "late_binding_status": "short_unknown_bootstrap_merged",
                        "session_id": "s1",
                        "active_seconds": 4,
                        "server_received_at": "2026-07-01T10:00:08",
                    }
                ),
                json.dumps(
                    {
                        "project_id": "23",
                        "task_id": "403",
                        "annotator_id": "8",
                        "annotation_id": "a123",
                        "session_id": "s1",
                        "active_seconds": 10,
                        "server_received_at": "2026-07-01T10:00:20",
                    }
                ),
                json.dumps(
                    {
                        "project_id": "23",
                        "task_id": "403",
                        "annotator_id": "8",
                        "annotation_id": "b456",
                        "session_id": "s1",
                        "active_seconds": 5,
                        "server_received_at": "2026-07-01T10:00:30",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    logs = load_active_logs(str(active_logs))

    assert logs[("23", "403", "8")]["active_time_value"] == 19.0
    assert logs[("23", "403", "8", "unknown_annotation")]["active_time_value"] == 4.0
    assert logs[("23", "403", "8", "a123")]["active_time_value"] == 10.0
    assert logs[("23", "403", "8", "b456")]["active_time_value"] == 5.0


def test_annotation_owner_mismatch_does_not_create_exact_or_task_fallback_match(tmp_path: Path):
    active_logs = tmp_path / "active_logs"
    active_logs.mkdir()
    (active_logs / "active_times_2026-06-30.jsonl").write_text(
        json.dumps(
            {
                "project_id": "23",
                "task_id": "404",
                "annotator_id": "worker_b",
                "annotation_id": "ann_owned_by_a",
                "session_id": "s1",
                "active_seconds": 20,
                "server_received_at": "2026-07-01T10:00:00",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    logs = load_active_logs(
        str(active_logs),
        annotation_owner_map={("23", "404", "ann_owned_by_a"): "worker_a"},
    )
    entry, status = lookup_active_log_entry(logs, "23", "404", "worker_b", annotation_id="ann_owned_by_b")

    assert entry is None
    assert status == "missing"


def test_annotation_owner_match_still_allows_exact_match(tmp_path: Path):
    active_logs = tmp_path / "active_logs"
    active_logs.mkdir()
    (active_logs / "active_times_2026-06-30.jsonl").write_text(
        json.dumps(
            {
                "project_id": "23",
                "task_id": "405",
                "annotator_id": "worker_a",
                "annotation_id": "ann_a",
                "session_id": "s1",
                "active_seconds": 20,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    logs = load_active_logs(str(active_logs), annotation_owner_map={("23", "405", "ann_a"): "worker_a"})
    entry, status = lookup_active_log_entry(logs, "23", "405", "worker_a", annotation_id="ann_a")

    assert status == "project+task+annotator+annotation"
    assert entry["active_time_value"] == 20.0


def test_annotation_owner_map_none_keeps_legacy_annotation_log_behavior(tmp_path: Path):
    active_logs = tmp_path / "active_logs"
    active_logs.mkdir()
    (active_logs / "active_times_2026-06-30.jsonl").write_text(
        json.dumps(
            {
                "project_id": "23",
                "task_id": "406",
                "annotator_id": "worker_b",
                "annotation_id": "ann_owned_by_a",
                "session_id": "s1",
                "active_seconds": 20,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    logs = load_active_logs(str(active_logs), annotation_owner_map=None)
    entry, status = lookup_active_log_entry(logs, "23", "406", "worker_b", annotation_id="ann_owned_by_a")

    assert status == "project+task+annotator+annotation"
    assert entry["active_time_value"] == 20.0


def test_calibration_unknown_is_audit_only_and_not_task_time(tmp_path: Path):
    active_logs = tmp_path / "active_logs"
    active_logs.mkdir()
    (active_logs / "active_times_2026-07-03.jsonl").write_text(
        json.dumps({"project_id": "65", "task_id": "1", "annotator_id": "w1", "annotation_id": "unknown_annotation", "session_id": "s1", "active_seconds": 7}) + "\n",
        encoding="utf-8",
    )
    logs = load_active_logs(str(active_logs), policy="calibration")

    assert ("65", "1", "w1") not in logs
    audit = lookup_unknown_active_time_audit(logs, "65", "1", "w1")
    assert audit["unassigned_active_time_seconds"] == 7.0
    assert audit["unknown_annotation_event_count"] == 1
    assert audit["unknown_annotation_session_count"] == 1
    assert audit["audit_only"] is True
    row = active_time_for_annotation(logs, "65", "1", "w1", "a1", 0)
    assert row["active_time"] == ""
    assert row["primary_active_time_eligible"] is False
    assert row["sensitivity_active_time_eligible"] is False
    assert row["audit_only"] is True
    assert row["system_collection_issue"] is True
    assert row["active_time_integrity_status"] == "unknown_audit_only"


def test_calibration_known_and_unknown_counts_only_owner_validated_known(tmp_path: Path):
    active_logs = tmp_path / "active_logs"
    active_logs.mkdir()
    (active_logs / "active_times_2026-07-03.jsonl").write_text(
        "\n".join([
            json.dumps({"project_id": "65", "task_id": "2", "annotator_id": "w1", "annotation_id": "unknown_annotation", "session_id": "s1", "active_seconds": 4}),
            json.dumps({"project_id": "65", "task_id": "2", "annotator_id": "w1", "annotation_id": "a1", "session_id": "s1", "active_seconds": 10}),
        ]) + "\n",
        encoding="utf-8",
    )
    logs = load_active_logs(
        str(active_logs), annotation_owner_map={("65", "2", "a1"): "w1"}, policy="calibration"
    )

    assert logs[("65", "2", "w1")]["active_time_value"] == 10.0
    assert logs[("65", "2", "w1", "a1")]["active_time_value"] == 10.0
    assert logs[("65", "2", "w1", "a1")]["known_unknown_oscillation_flag"] is True
    assert logs[("65", "2", "w1", "a1")]["unassigned_active_time_seconds"] == 4.0


def test_calibration_does_not_merge_short_unknown_bootstrap(tmp_path: Path):
    active_logs = tmp_path / "active_logs"
    active_logs.mkdir()
    (active_logs / "active_times_2026-07-03.jsonl").write_text(
        "\n".join([
            json.dumps({"project_id": "65", "task_id": "3", "annotator_id": "w1", "annotation_id": "unknown_annotation", "session_id": "s1", "active_seconds": 4, "server_received_at": "2026-07-03T00:00:00"}),
            json.dumps({"project_id": "65", "task_id": "3", "annotator_id": "w1", "annotation_id": "a1", "session_id": "s1", "active_seconds": 4, "server_received_at": "2026-07-03T00:00:05", "active_time_alias_from": "65|3|w1|unknown_annotation", "active_time_alias_reason": "short_unknown_bootstrap", "late_binding_status": "short_unknown_bootstrap_merged"}),
        ]) + "\n",
        encoding="utf-8",
    )
    logs = load_active_logs(
        str(active_logs), annotation_owner_map={("65", "3", "a1"): "w1"}, policy="calibration"
    )

    assert logs[("65", "3", "w1", "a1")]["active_time_value"] == 4.0
    assert lookup_unknown_active_time_audit(logs, "65", "3", "w1")["unassigned_active_time_seconds"] == 4.0


def test_calibration_owner_mismatch_remains_unmatched(tmp_path: Path):
    active_logs = tmp_path / "active_logs"
    active_logs.mkdir()
    (active_logs / "active_times_2026-07-03.jsonl").write_text(
        json.dumps({"project_id": "65", "task_id": "4", "annotator_id": "w2", "annotation_id": "a1", "session_id": "s1", "active_seconds": 10}) + "\n",
        encoding="utf-8",
    )
    logs = load_active_logs(
        str(active_logs), annotation_owner_map={("65", "4", "a1"): "w1"}, policy="calibration"
    )

    entry, status = lookup_active_log_entry(logs, "65", "4", "w2", "a1")
    assert entry is None
    assert status == "missing"


def test_unknown_like_annotation_values_are_calibration_audit_only(tmp_path: Path):
    active_logs = tmp_path / "active_logs"
    active_logs.mkdir()
    values = [None, "", "unknown", "null", "none"]
    lines = [json.dumps({"project_id": "65", "task_id": "5", "annotator_id": "w1", "annotation_id": value, "session_id": "s1", "active_seconds": index + 1}) for index, value in enumerate(values)]
    (active_logs / "active_times_2026-07-03.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")

    logs = load_active_logs(str(active_logs), policy="calibration")
    audit = lookup_unknown_active_time_audit(logs, "65", "5", "w1")

    assert all(is_unknown_annotation_id(value) for value in values)
    assert ("65", "5", "w1") not in logs
    assert audit["unassigned_active_time_seconds"] == 5.0
    assert audit["unknown_annotation_event_count"] == 5
    assert audit["unknown_annotation_session_count"] == 1


def test_calibration_task_fallback_excludes_unknown_seconds(tmp_path: Path):
    active_logs = tmp_path / "active_logs"
    active_logs.mkdir()
    (active_logs / "active_times_2026-07-03.jsonl").write_text(
        "\n".join([
            json.dumps({"project_id": "65", "task_id": "6", "annotator_id": "w1", "annotation_id": "unknown", "session_id": "s1", "active_seconds": 4}),
            json.dumps({"project_id": "65", "task_id": "6", "annotator_id": "w1", "session_id": "s2", "active_seconds": 9}),
        ]) + "\n",
        encoding="utf-8",
    )
    logs = load_active_logs(str(active_logs), policy="calibration")
    entry, status = lookup_active_log_entry(logs, "65", "6", "w1", annotation_id="a1")

    assert status == "project+task+annotator"
    assert entry["active_time_value"] == 9.0
    assert entry["unassigned_active_time_seconds"] == 4.0
    row = active_time_for_annotation(logs, "65", "6", "w1", "a1", 0)
    assert row["active_time"] == 9.0
    assert row["primary_active_time_eligible"] is False
    assert row["sensitivity_active_time_eligible"] is True
    assert row["active_time_integrity_status"] == "task_level_fallback"
