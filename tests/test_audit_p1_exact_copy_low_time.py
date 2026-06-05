from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from audit_p1_exact_copy_low_time import (  # noqa: E402
    AuditConfig,
    apply_exact_copy_low_time_rules,
    build_audit_rows,
    canonical_geometry_hash,
    run_audit,
)


BASE_POINTS = [(10, 10), (10, 90), (50, 20), (50, 80)]
DIFF_POINTS = [(15, 10), (15, 90), (55, 20), (55, 80)]


def _kp(x: float, y: float) -> dict:
    return {
        "type": "keypointlabels",
        "value": {"x": x, "y": y, "keypointlabels": ["Corner"]},
    }


def _annotation(worker_id: str, points=BASE_POINTS, *, annotation_id: str = "1", lead_time: float = 0.0, completed_by=None) -> dict:
    return {
        "id": annotation_id,
        "completed_by": {"id": worker_id} if completed_by is None else completed_by,
        "lead_time": lead_time,
        "result": [_kp(x, y) for x, y in points],
    }


def _bad_annotation(worker_id: str, *, annotation_id: str = "bad") -> dict:
    return {
        "id": annotation_id,
        "completed_by": {"id": worker_id},
        "lead_time": 1.0,
        "result": [],
    }


def _task(task_id: int, annotations: list[dict], *, dataset_group: str | None = "P1_manual") -> dict:
    data = {"title": f"task_{task_id}.jpg"}
    if dataset_group is not None:
        data["dataset_group"] = dataset_group
    return {
        "id": task_id,
        "project": 23,
        "data": data,
        "annotations": annotations,
    }


def _write_export(tmp_path: Path, tasks: list[dict]) -> Path:
    path = tmp_path / "export.json"
    path.write_text(json.dumps(tasks), encoding="utf-8")
    return path


def _write_active_log(tmp_path: Path, events: list[tuple]) -> Path:
    path = tmp_path / "active_times_test.jsonl"
    with path.open("w", encoding="utf-8") as f:
        for event in events:
            task_id, worker_id, seconds = event[:3]
            event_time = event[3] if len(event) > 3 else "2026-06-05T10:00:00"
            f.write(
                json.dumps(
                    {
                        "project_id": "23",
                        "task_id": str(task_id),
                        "annotator_id": worker_id,
                        "session_id": f"s-{task_id}-{worker_id}",
                        "active_seconds": seconds,
                        "server_received_at": event_time,
                    }
                )
                + "\n"
            )
    return path


def _rows_and_summary(tmp_path: Path, tasks: list[dict], events: list[tuple[int, str, float]], config=None):
    export_path = _write_export(tmp_path, tasks)
    active_path = _write_active_log(tmp_path, events)
    cfg = config or AuditConfig(min_valid_tasks_for_worker=1)
    rows, _metadata = build_audit_rows(export_path, str(active_path), cfg)
    return apply_exact_copy_low_time_rules(rows, cfg)


def test_same_geometry_normal_active_time_does_not_trigger_event(tmp_path):
    tasks = [_task(1, [_annotation("w1", annotation_id="a1"), _annotation("w2", annotation_id="a2")])]
    rows, worker_summary, _rule_summary = _rows_and_summary(
        tmp_path,
        tasks,
        [(1, "w1", 100), (1, "w2", 120)],
    )

    assert all(not row["exact_copy_low_time_event"] for row in rows)
    assert {row["recommended_action"] for row in worker_summary} == {"no_action"}


def test_low_active_time_with_different_geometry_does_not_trigger_event(tmp_path):
    tasks = [_task(1, [_annotation("w1", BASE_POINTS, annotation_id="a1"), _annotation("w2", DIFF_POINTS, annotation_id="a2")])]
    rows, _worker_summary, _rule_summary = _rows_and_summary(
        tmp_path,
        tasks,
        [(1, "w1", 5), (1, "w2", 100)],
    )

    w1 = next(row for row in rows if row["worker_id"] == "w1")
    assert w1["same_hash_cluster_size"] == 1
    assert w1["same_hash_worker_count"] == 1
    assert not w1["exact_copy_low_time_event"]


def test_same_geometry_low_primary_active_time_triggers_event(tmp_path):
    tasks = [_task(1, [_annotation("w1", annotation_id="a1"), _annotation("w2", annotation_id="a2")])]
    rows, worker_summary, rule_summary = _rows_and_summary(
        tmp_path,
        tasks,
        [(1, "w1", 5), (1, "w2", 100)],
    )

    w1 = next(row for row in rows if row["worker_id"] == "w1")
    assert w1["exact_copy_low_time_event"] is True
    assert w1["event_basis"] == "exact_geometry_duplicate+log_active_time_low"
    assert rule_summary["n_primary_exact_copy_low_time_events"] == 1
    assert next(row for row in worker_summary if row["worker_id"] == "w1")["recommended_action"] == "fail_recommended"


def test_few_events_only_warning_not_fail_when_worker_support_is_sufficient(tmp_path):
    tasks = []
    events = []
    for task_id in range(1, 11):
        tasks.append(_task(task_id, [_annotation("w1", annotation_id=f"a{task_id}"), _annotation("w2", annotation_id=f"b{task_id}")]))
        events.append((task_id, "w1", 5 if task_id == 1 else 100))
        events.append((task_id, "w2", 100))

    _rows, worker_summary, _rule_summary = _rows_and_summary(
        tmp_path,
        tasks,
        events,
        AuditConfig(min_valid_tasks_for_worker=10),
    )

    w1 = next(row for row in worker_summary if row["worker_id"] == "w1")
    assert w1["n_exact_copy_low_time_events"] == 1
    assert w1["recommended_action"] == "warning"
    assert w1["fail_recommended"] is False
    w2 = next(row for row in worker_summary if row["worker_id"] == "w2")
    assert w2["recommended_action"] == "no_action"


def test_many_events_trigger_manual_review_without_fail_below_fail_rate(tmp_path):
    tasks = []
    events = []
    for task_id in range(1, 11):
        tasks.append(_task(task_id, [_annotation("w1", annotation_id=f"a{task_id}"), _annotation("w2", annotation_id=f"b{task_id}")]))
        events.append((task_id, "w1", 5 if task_id <= 5 else 100))
        events.append((task_id, "w2", 100))

    _rows, worker_summary, _rule_summary = _rows_and_summary(
        tmp_path,
        tasks,
        events,
        AuditConfig(min_valid_tasks_for_worker=10),
    )

    w1 = next(row for row in worker_summary if row["worker_id"] == "w1")
    assert w1["manual_review_required"] is True
    assert w1["fail_recommended"] is False
    assert w1["recommended_action"] == "manual_review"


def test_high_event_rate_triggers_fail_recommended(tmp_path):
    tasks = []
    events = []
    for task_id in range(1, 11):
        tasks.append(_task(task_id, [_annotation("w1", annotation_id=f"a{task_id}"), _annotation("w2", annotation_id=f"b{task_id}")]))
        events.append((task_id, "w1", 5 if task_id <= 8 else 100))
        events.append((task_id, "w2", 100))

    _rows, worker_summary, _rule_summary = _rows_and_summary(
        tmp_path,
        tasks,
        events,
        AuditConfig(min_valid_tasks_for_worker=10),
    )

    w1 = next(row for row in worker_summary if row["worker_id"] == "w1")
    assert w1["exact_copy_low_time_rate"] == 0.8
    assert w1["fail_recommended"] is True
    assert w1["recommended_action"] == "fail_recommended"


def test_all_valid_tasks_duplicate_low_time_triggers_fail_recommended(tmp_path):
    tasks = []
    events = []
    for task_id in range(1, 4):
        tasks.append(_task(task_id, [_annotation("w1", annotation_id=f"a{task_id}"), _annotation("w2", annotation_id=f"b{task_id}")]))
        events.append((task_id, "w1", 5))
        events.append((task_id, "w2", 100))

    _rows, worker_summary, _rule_summary = _rows_and_summary(
        tmp_path,
        tasks,
        events,
        AuditConfig(min_valid_tasks_for_worker=3, fail_recommended_rate=0.99),
    )

    w1 = next(row for row in worker_summary if row["worker_id"] == "w1")
    assert w1["fail_recommended"] is True
    assert "all_valid_tasks_exact_copy_low_time" in w1["reason"]


def test_missing_active_time_lead_time_fallback_does_not_enter_primary_event(tmp_path):
    task = _task(
        1,
        [
            _annotation("w1", annotation_id="a1", lead_time=1),
            _annotation("w2", annotation_id="a2"),
        ],
    )
    export_path = _write_export(tmp_path, [task])
    active_path = _write_active_log(tmp_path, [(1, "w2", 100)])
    cfg = AuditConfig(min_valid_tasks_for_worker=1)

    rows, _metadata = build_audit_rows(export_path, str(active_path), cfg)
    rows, _worker_summary, rule_summary = apply_exact_copy_low_time_rules(rows, cfg)

    w1 = next(row for row in rows if row["worker_id"] == "w1")
    assert w1["active_time_source"] == "lead_time_fallback"
    assert w1["fallback_low_time_duplicate_audit"] is True
    assert w1["exact_copy_low_time_event"] is False
    assert rule_summary["n_primary_exact_copy_low_time_events"] == 0
    assert rule_summary["n_fallback_low_time_duplicate_audit"] == 1


def test_same_worker_duplicate_annotation_does_not_trigger_peer_copy_event(tmp_path):
    tasks = [
        _task(
            1,
            [
                _annotation("w1", annotation_id="a1"),
                _annotation("w1", annotation_id="a2"),
            ],
        )
    ]
    rows, worker_summary, rule_summary = _rows_and_summary(
        tmp_path,
        tasks,
        [(1, "w1", 5)],
        AuditConfig(min_valid_tasks_for_worker=1),
    )

    assert all(row["same_hash_annotation_count"] == 2 for row in rows)
    assert all(row["same_hash_worker_count"] == 1 for row in rows)
    assert all(row["same_worker_duplicate_annotation_anomaly"] for row in rows)
    assert all(not row["is_exact_duplicate_geometry"] for row in rows)
    assert rule_summary["n_primary_exact_copy_low_time_events"] == 0
    assert worker_summary[0]["recommended_action"] == "no_action"


def test_two_distinct_workers_required_for_duplicate_geometry(tmp_path):
    tasks = [_task(1, [_annotation("w1", annotation_id="a1"), _annotation("w2", annotation_id="a2")])]
    rows, _worker_summary, _rule_summary = _rows_and_summary(
        tmp_path,
        tasks,
        [(1, "w1", 100), (1, "w2", 100)],
    )

    assert all(row["same_hash_annotation_count"] == 2 for row in rows)
    assert all(row["same_hash_worker_count"] == 2 for row in rows)
    assert all(row["is_exact_duplicate_geometry"] for row in rows)


def test_active_log_start_end_are_applied_and_recorded(tmp_path):
    tasks = [_task(1, [_annotation("w1", annotation_id="a1"), _annotation("w2", annotation_id="a2")])]
    export_path = _write_export(tmp_path, tasks)
    active_path = _write_active_log(
        tmp_path,
        [
            (1, "w1", 5, "2026-06-04T10:00:00"),
            (1, "w1", 100, "2026-06-05T10:00:00"),
            (1, "w2", 100, "2026-06-05T10:00:00"),
        ],
    )
    cfg = AuditConfig(
        min_valid_tasks_for_worker=1,
        active_log_start="2026-06-05T00:00:00",
        active_log_end="2026-06-05T23:59:59",
    )

    rows, metadata = build_audit_rows(export_path, str(active_path), cfg)
    rows, _worker_summary, rule_summary = apply_exact_copy_low_time_rules(rows, cfg)

    w1 = next(row for row in rows if row["worker_id"] == "w1")
    assert w1["active_time"] == 100.0
    assert rule_summary["n_primary_exact_copy_low_time_events"] == 0
    assert metadata["active_log_start"] == "2026-06-05T00:00:00"
    assert metadata["active_log_end"] == "2026-06-05T23:59:59"


def test_worker_id_falls_back_to_email_then_username(tmp_path):
    tasks = [
        _task(
            1,
            [
                _annotation("", annotation_id="a1", completed_by={"email": "worker@example.com"}),
                _annotation("", annotation_id="a2", completed_by={"username": "user_b"}),
            ],
        )
    ]
    export_path = _write_export(tmp_path, tasks)
    rows, metadata = build_audit_rows(export_path, None, AuditConfig())

    assert {row["worker_id"] for row in rows} == {"worker@example.com", "user_b"}
    assert metadata["unknown_worker_count"] == 0


def test_p1_stage_filter_excludes_unlabeled_unless_assumed(tmp_path):
    tasks = [
        _task(1, [_annotation("w1")], dataset_group=None),
        _task(2, [_annotation("w2")], dataset_group="P1_manual"),
    ]
    export_path = _write_export(tmp_path, tasks)

    rows, metadata = build_audit_rows(export_path, None, AuditConfig(stage_filter="P1"))
    assert {row["task_id"] for row in rows} == {"2"}
    assert metadata["stage_filter_task_breakdown"]["unlabeled_excluded_requires_assume_p1_export"] == 1

    rows_assumed, metadata_assumed = build_audit_rows(
        export_path,
        None,
        AuditConfig(stage_filter="P1", assume_p1_export=True),
    )
    assert {row["task_id"] for row in rows_assumed} == {"1", "2"}
    assert metadata_assumed["stage_filter_task_breakdown"]["unlabeled_included_assume_p1_export"] == 1


def test_corner_order_differs_but_geometry_hash_is_same():
    h1, _payload1, _n1 = canonical_geometry_hash(BASE_POINTS, round_px=0.5)
    h2, _payload2, _n2 = canonical_geometry_hash(list(reversed(BASE_POINTS)), round_px=0.5)
    assert h1 == h2


def test_invalid_missing_corner_annotation_records_parse_error(tmp_path):
    tasks = [_task(1, [_bad_annotation("w1"), _annotation("w2", annotation_id="a2")])]
    rows, _worker_summary, _rule_summary = _rows_and_summary(
        tmp_path,
        tasks,
        [(1, "w1", 5), (1, "w2", 100)],
    )

    bad = next(row for row in rows if row["worker_id"] == "w1")
    assert bad["is_valid_geometry"] is False
    assert bad["parse_error"]
    assert bad["exact_copy_low_time_event"] is False


def test_run_audit_writes_expected_artifacts_and_schema(tmp_path):
    tasks = [_task(1, [_annotation("w1", annotation_id="a1"), _annotation("w2", annotation_id="a2")])]
    export_path = _write_export(tmp_path, tasks)
    active_path = _write_active_log(tmp_path, [(1, "w1", 5), (1, "w2", 100)])
    output_dir = tmp_path / "out"

    summary = run_audit(
        export_path,
        output_dir,
        str(active_path),
        AuditConfig(min_valid_tasks_for_worker=1),
    )

    assert (output_dir / "p1_exact_copy_low_time_event_audit.csv").exists()
    assert (output_dir / "p1_worker_independence_summary.csv").exists()
    assert (output_dir / "p1_exact_copy_low_time_summary.json").exists()
    assert (output_dir / "p1_exact_copy_low_time_report.md").exists()
    assert summary["n_primary_exact_copy_low_time_events"] == 1

    with (output_dir / "p1_worker_independence_summary.csv").open(encoding="utf-8-sig") as f:
        first = next(csv.DictReader(f))
    assert {
        "n_valid_tasks",
        "n_exact_duplicate_tasks",
        "n_exact_copy_low_time_events",
        "exact_copy_low_time_rate",
        "recommended_action",
    }.issubset(first.keys())
    assert summary["stage_filter_task_breakdown"]["explicit_p1"] == 1
