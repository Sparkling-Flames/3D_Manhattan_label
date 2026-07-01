from __future__ import annotations

import json
import csv
import hashlib
import inspect
from pathlib import Path

from tools.thesis_main.analysis.prescreen_active_time_source_audit import build_active_time_source_audit
from tools.thesis_main.analysis.prescreen_completion_audit import build_completion_audit, write_completion_audit
import tools.thesis_main.analysis.prescreen_canonicalize_export as canonicalize_module
from tools.thesis_main.analysis.prescreen_canonicalize_export import MANIFEST_FIELDS, build_canonical_tables, snapshot_inputs

BASE_POINTS = [(10, 10), (10, 90), (50, 20), (50, 80)]
DIFF_POINTS = [(15, 10), (15, 90), (55, 20), (55, 80)]


def _kp(x: float, y: float) -> dict:
    return {"type": "keypointlabels", "value": {"x": x, "y": y, "keypointlabels": ["Corner"]}}


def _annotation(worker_id: str, points=BASE_POINTS, *, annotation_id: str, lead_time: float = 0.0, updated_at: str = "") -> dict:
    return {
        "id": annotation_id,
        "completed_by": {"id": worker_id},
        "lead_time": lead_time,
        "updated_at": updated_at,
        "result": [_kp(x, y) for x, y in points],
    }


def _task(task_id: int, annotations: list[dict]) -> dict:
    return {
        "id": task_id,
        "project": 23,
        "data": {"title": f"task_{task_id}.jpg", "dataset_group": "PreScreen_manual"},
        "annotations": annotations,
    }


def _task_with_group(task_id: int, group: str, annotations: list[dict]) -> dict:
    task = _task(task_id, annotations)
    task["data"]["dataset_group"] = group
    return task


def _write_export(tmp_path: Path, tasks: list[dict]) -> Path:
    path = tmp_path / "export.json"
    path.write_text(json.dumps(tasks), encoding="utf-8")
    return path


def _write_log(tmp_path: Path) -> Path:
    path = tmp_path / "active_times_2026-06-28.jsonl"
    path.write_text(
        json.dumps(
            {
                "project_id": "23",
                "task_id": "1",
                "annotator_id": "w_log",
                "session_id": "s1",
                "active_seconds": 12,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _write_annotation_logs(tmp_path: Path, rows: list[dict]) -> Path:
    path = tmp_path / "active_times_2026-06-30.jsonl"
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    return path


def test_same_worker_task_duplicate_same_geometry_becomes_one_canonical_row(tmp_path: Path) -> None:
    export = _write_export(
        tmp_path,
        [
            _task(
                1,
                [
                    _annotation("w1", annotation_id="a1", lead_time=10, updated_at="2026-01-01T00:00:00"),
                    _annotation("w1", annotation_id="a2", lead_time=20, updated_at="2026-01-01T00:01:00"),
                ],
            )
        ],
    )

    canonical, duplicate, summary = build_canonical_tables([export])

    assert summary["n_raw_annotation_rows"] == 2
    assert len(canonical) == 1
    assert canonical[0]["raw_canonical_annotation_id"] == "a2"
    assert canonical[0]["duplicate_annotation_ids"] == "a1"
    assert canonical[0]["duplicate_geometry_type"] == "duplicate_same_geometry"
    assert canonical[0]["lead_time_seconds"] == "20.0"
    assert duplicate[0]["lead_time_policy"] == "canonical_only_not_summed"


def test_same_geometry_duplicate_keeps_longer_lead_time_even_if_older(tmp_path: Path) -> None:
    export = _write_export(
        tmp_path,
        [
            _task(
                1,
                [
                    _annotation("w1", annotation_id="a1", lead_time=60, updated_at="2026-01-01T00:00:00"),
                    _annotation("w1", annotation_id="a2", lead_time=10, updated_at="2026-01-01T00:01:00"),
                ],
            )
        ],
    )

    canonical, duplicate, _summary = build_canonical_tables([export])

    assert canonical[0]["raw_canonical_annotation_id"] == "a1"
    assert canonical[0]["duplicate_annotation_ids"] == "a2"
    assert canonical[0]["duplicate_geometry_type"] == "duplicate_same_geometry"
    assert canonical[0]["lead_time_seconds"] == "60.0"
    assert duplicate[0]["raw_canonical_annotation_id"] == "a1"


def test_snapshot_inputs_writes_sha256_for_regular_file(tmp_path: Path) -> None:
    source = tmp_path / "export.json"
    source.write_text('{"ok": true}', encoding="utf-8")

    manifest = snapshot_inputs([source], tmp_path / "out")
    rows = list(csv.DictReader(manifest.open("r", encoding="utf-8-sig", newline="")))

    snapshot = Path(rows[0]["snapshot_path"])
    assert list(rows[0].keys()) == MANIFEST_FIELDS
    assert rows[0]["sha256"]
    assert rows[0]["sha256"] == hashlib.sha256(snapshot.read_bytes()).hexdigest()
    assert rows[0]["data_complete"] == "false"
    assert rows[0]["completion_basis"] == "current_partial_export_with_known_dropout_and_pending_completion"


def test_snapshot_inputs_missing_source_has_empty_sha256_field(tmp_path: Path) -> None:
    manifest = snapshot_inputs([tmp_path / "missing.json"], tmp_path / "out")
    row = next(csv.DictReader(manifest.open("r", encoding="utf-8-sig", newline="")))

    assert row["exists"] == "False"
    assert "sha256" in row
    assert row["sha256"] == ""


def test_snapshot_inputs_directory_has_aggregate_sha256_that_changes_with_content(tmp_path: Path) -> None:
    source_dir = tmp_path / "active_logs"
    source_dir.mkdir()
    (source_dir / "active_times_2026.jsonl").write_text("{}\n", encoding="utf-8")

    manifest1 = snapshot_inputs([source_dir], tmp_path / "out1")
    row = next(csv.DictReader(manifest1.open("r", encoding="utf-8-sig", newline="")))

    assert row["exists"] == "True"
    assert row["file_count"] == "1"
    assert "sha256" in row
    assert row["sha256"]
    (source_dir / "active_times_2026.jsonl").write_text('{"changed": true}\n', encoding="utf-8")
    manifest2 = snapshot_inputs([source_dir], tmp_path / "out2")
    changed = next(csv.DictReader(manifest2.open("r", encoding="utf-8-sig", newline="")))
    assert changed["sha256"] != row["sha256"]


def test_snapshot_inputs_marks_groudtruth_as_reference_geometry_gt(tmp_path: Path) -> None:
    source = tmp_path / "export_label" / "groudTruth.json"
    source.parent.mkdir()
    source.write_text("[]", encoding="utf-8")

    manifest = snapshot_inputs([source], tmp_path / "out")
    row = next(csv.DictReader(manifest.open("r", encoding="utf-8-sig", newline="")))

    assert row["source_kind"] == "reference_geometry_gt_snapshot"
    assert "geometry GT" in row["notes"]


def test_same_worker_task_duplicate_different_geometry_is_revision_audit(tmp_path: Path) -> None:
    export = _write_export(
        tmp_path,
        [
            _task(
                1,
                [
                    _annotation("w1", BASE_POINTS, annotation_id="a1", updated_at="2026-01-01T00:00:00"),
                    _annotation("w1", DIFF_POINTS, annotation_id="a2", updated_at="2026-01-01T00:01:00"),
                ],
            )
        ],
    )

    canonical, duplicate, _summary = build_canonical_tables([export])

    assert len(canonical) == 1
    assert canonical[0]["duplicate_geometry_type"] == "revision"
    assert duplicate[0]["n_distinct_geometry_hashes"] == 2
    assert duplicate[0]["duplicate_time_ambiguous"] is True


def test_duplicate_annotations_use_exact_annotation_active_time_when_available(tmp_path: Path) -> None:
    export = _write_export(
        tmp_path,
        [
            _task(
                1,
                [
                    _annotation("w1", annotation_id="a1", lead_time=10, updated_at="2026-01-01T00:00:00"),
                    _annotation("w1", annotation_id="a2", lead_time=20, updated_at="2026-01-01T00:01:00"),
                ],
            )
        ],
    )
    active_log = _write_annotation_logs(
        tmp_path,
        [
            {
                "project_id": "23",
                "task_id": "1",
                "annotator_id": "w1",
                "annotation_id": "a1",
                "session_id": "s1",
                "active_seconds": 12,
            },
            {
                "project_id": "23",
                "task_id": "1",
                "annotator_id": "w1",
                "annotation_id": "a2",
                "session_id": "s1",
                "active_seconds": 34,
            },
        ],
    )

    canonical, duplicate, _summary = build_canonical_tables([export], active_log)

    assert canonical[0]["raw_canonical_annotation_id"] == "a2"
    assert canonical[0]["annotation_match_status"] == "annotation_id_present"
    assert canonical[0]["active_time_key"] == "23|1|w1|a2"
    assert canonical[0]["active_time"] == "34.0"
    assert canonical[0]["active_time_source"] == "log"
    assert canonical[0]["active_time_match_status"] == "project+task+annotator+annotation"
    assert canonical[0]["duplicate_time_ambiguous"] is False
    assert duplicate[0]["duplicate_time_ambiguous"] is False


def test_duplicate_annotations_do_not_use_legacy_task_level_active_time(tmp_path: Path) -> None:
    export = _write_export(
        tmp_path,
        [
            _task(
                1,
                [
                    _annotation("w1", annotation_id="a1", lead_time=10, updated_at="2026-01-01T00:00:00"),
                    _annotation("w1", annotation_id="a2", lead_time=20, updated_at="2026-01-01T00:01:00"),
                ],
            )
        ],
    )
    active_log = _write_annotation_logs(
        tmp_path,
        [
            {
                "project_id": "23",
                "task_id": "1",
                "annotator_id": "w1",
                "session_id": "legacy",
                "active_seconds": 99,
            }
        ],
    )

    canonical, duplicate, _summary = build_canonical_tables([export], active_log)

    assert canonical[0]["raw_canonical_annotation_id"] == "a2"
    assert canonical[0]["active_time"] == "20.0"
    assert canonical[0]["active_time_source"] == "lead_time_fallback"
    assert canonical[0]["active_time_match_status"] == "fallback_annotation_missing_task_level_ambiguous"
    assert canonical[0]["duplicate_time_ambiguous"] is True
    assert duplicate[0]["duplicate_time_ambiguous"] is True


def test_prescreen_canonicalize_imports_quality_core_directly() -> None:
    source = inspect.getsource(canonicalize_module)

    assert "tools.thesis_main.analysis.analyze_quality import" not in source
    assert "tools.thesis_main.analysis.quality_core.active_time import" in source
    assert "tools.thesis_main.analysis.quality_core.choice_parser import" in source


def test_owner_mismatch_annotation_log_does_not_pollute_canonical_task_fallback(tmp_path: Path) -> None:
    export = _write_export(
        tmp_path,
        [
            _task(
                1,
                [
                    _annotation("worker_a", annotation_id="ann_a", lead_time=11),
                    _annotation("worker_b", annotation_id="ann_b", lead_time=22),
                ],
            )
        ],
    )
    active_log = _write_annotation_logs(
        tmp_path,
        [
            {
                "project_id": "23",
                "task_id": "1",
                "annotator_id": "worker_b",
                "annotation_id": "ann_a",
                "session_id": "s1",
                "active_seconds": 99,
            }
        ],
    )

    canonical, _duplicate, _summary = build_canonical_tables([export], active_log)
    by_worker = {row["annotator_id"]: row for row in canonical}

    assert by_worker["worker_b"]["raw_canonical_annotation_id"] == "ann_b"
    assert by_worker["worker_b"]["active_time_source"] == "lead_time_fallback"
    assert by_worker["worker_b"]["active_time"] == "22.0"
    assert by_worker["worker_b"]["active_time_match_status"] == "fallback_no_direct_log"


def test_owner_match_annotation_log_exact_matches_in_canonicalize(tmp_path: Path) -> None:
    export = _write_export(tmp_path, [_task(1, [_annotation("worker_a", annotation_id="ann_a", lead_time=11)])])
    active_log = _write_annotation_logs(
        tmp_path,
        [
            {
                "project_id": "23",
                "task_id": "1",
                "annotator_id": "worker_a",
                "annotation_id": "ann_a",
                "session_id": "s1",
                "active_seconds": 33,
            }
        ],
    )

    canonical, _duplicate, _summary = build_canonical_tables([export], active_log)

    assert canonical[0]["active_time_source"] == "log"
    assert canonical[0]["active_time"] == "33.0"
    assert canonical[0]["active_time_match_status"] == "project+task+annotator+annotation"


def test_active_time_sources_define_primary_sensitivity_and_missing_without_imputation(tmp_path: Path) -> None:
    export = _write_export(
        tmp_path,
        [
            _task(
                1,
                [
                    _annotation("w_log", annotation_id="a1", lead_time=99),
                    _annotation("w_fallback", annotation_id="a2", lead_time=30),
                    _annotation("w_missing", annotation_id="a3", lead_time=0),
                ],
            )
        ],
    )
    active_log = _write_log(tmp_path)

    canonical, _duplicate, _summary = build_canonical_tables([export], active_log)
    by_worker = {row["annotator_id"]: row for row in canonical}

    assert by_worker["w_log"]["active_time_source"] == "log"
    assert by_worker["w_log"]["primary_active_time_eligible"] is True
    assert by_worker["w_fallback"]["active_time_source"] == "lead_time_fallback"
    assert by_worker["w_fallback"]["primary_active_time_eligible"] is False
    assert by_worker["w_fallback"]["sensitivity_active_time_eligible"] is True
    assert by_worker["w_missing"]["active_time_source"] == "missing"
    assert by_worker["w_missing"]["active_time"] == ""

    csv_path = tmp_path / "canonical.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        import csv

        writer = csv.DictWriter(f, fieldnames=list(canonical[0].keys()))
        writer.writeheader()
        writer.writerows(canonical)

    audit = {row["annotator_id"]: row for row in build_active_time_source_audit(csv_path)}
    assert audit["w_log"]["primary_active_time_eligible_count"] == 1
    assert audit["w_fallback"]["primary_active_time_eligible_count"] == 0
    assert audit["w_fallback"]["sensitivity_active_time_eligible_count"] == 1
    assert audit["w_missing"]["n_missing"] == 1


def _write_csv(path: Path, rows: list[dict]) -> Path:
    import csv

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return path


def _minimal_canonical(path: Path) -> Path:
    rows = [
        {"annotator_id": "complete", "dataset_group": "PreScreen_manual", "condition": "", "active_time_source": "log"},
        {"annotator_id": "pending", "dataset_group": "PreScreen_manual", "condition": "", "active_time_source": "log"},
        {"annotator_id": "known_bad", "dataset_group": "PreScreen_manual", "condition": "", "active_time_source": "lead_time_fallback"},
        {"annotator_id": "unknown", "dataset_group": "PreScreen_manual", "condition": "", "active_time_source": "missing"},
    ]
    return _write_csv(path, rows)


def _minimal_roster(path: Path) -> Path:
    rows = [
        {
            "annotator_id": "complete",
            "language": "zh",
            "expected_manual": "1",
            "expected_semi": "0",
            "expected_oos": "0",
            "expected_total": "1",
            "will_continue": "true",
            "dropout": "false",
            "known_bad_or_process_risk": "false",
            "exclude_from_primary_candidate": "false",
            "completion_status_override": "",
            "notes": "",
        },
        {
            "annotator_id": "pending",
            "language": "zh",
            "expected_manual": "2",
            "expected_semi": "0",
            "expected_oos": "0",
            "expected_total": "2",
            "will_continue": "true",
            "dropout": "false",
            "known_bad_or_process_risk": "false",
            "exclude_from_primary_candidate": "false",
            "completion_status_override": "",
            "notes": "",
        },
        {
            "annotator_id": "dropout",
            "language": "zh",
            "expected_manual": "1",
            "expected_semi": "0",
            "expected_oos": "0",
            "expected_total": "1",
            "will_continue": "false",
            "dropout": "true",
            "known_bad_or_process_risk": "false",
            "exclude_from_primary_candidate": "true",
            "completion_status_override": "",
            "notes": "quit before completion",
        },
        {
            "annotator_id": "known_bad",
            "language": "zh",
            "expected_manual": "1",
            "expected_semi": "0",
            "expected_oos": "0",
            "expected_total": "1",
            "will_continue": "true",
            "dropout": "false",
            "known_bad_or_process_risk": "true",
            "exclude_from_primary_candidate": "true",
            "completion_status_override": "",
            "notes": "process risk",
        },
    ]
    return _write_csv(path, rows)


def test_completion_audit_statuses_and_denominator_policy(tmp_path: Path) -> None:
    canonical = _minimal_canonical(tmp_path / "canonical.csv")
    roster = _minimal_roster(tmp_path / "roster.csv")

    audit = {row["annotator_id"]: row for row in build_completion_audit(canonical, roster)}

    assert audit["complete"]["completion_status"] == "complete"
    assert audit["pending"]["completion_status"] == "pending_completion"
    assert audit["dropout"]["completion_status"] == "dropout_no_future"
    assert audit["dropout"]["total_observed"] == 0
    assert audit["known_bad"]["completion_status"] == "known_bad_complete"
    assert audit["unknown"]["completion_status"] == "unknown_roster"
    assert audit["complete"]["eligible_for_final_completion_denominator"] is True
    assert audit["dropout"]["eligible_for_final_completion_denominator"] is False
    assert audit["known_bad"]["eligible_for_final_completion_denominator"] is False

    include_known_bad = {row["annotator_id"]: row for row in build_completion_audit(canonical, roster, exclude_known_bad_from_denominator=False)}
    assert include_known_bad["known_bad"]["eligible_for_final_completion_denominator"] is True


def test_active_time_audit_carries_completion_status(tmp_path: Path) -> None:
    canonical = _minimal_canonical(tmp_path / "canonical.csv")
    roster = _minimal_roster(tmp_path / "roster.csv")
    completion_rows = build_completion_audit(canonical, roster)
    completion_csv = tmp_path / "completion.csv"
    write_completion_audit(completion_csv, completion_rows)

    audit = {(row["annotator_id"], row["condition"]): row for row in build_active_time_source_audit(canonical, completion_csv)}

    assert audit[("complete", "manual")]["language"] == "zh"
    assert audit[("complete", "manual")]["completion_status"] == "complete"
    assert audit[("complete", "manual")]["eligible_for_primary_prescreen_candidate"] == "True"
    assert audit[("known_bad", "manual")]["completion_status"] == "known_bad_complete"
    assert audit[("known_bad", "manual")]["eligible_for_primary_prescreen_candidate"] == "False"


def test_known_bad_incomplete_worker_in_roster_is_not_unknown_roster(tmp_path: Path) -> None:
    canonical = _write_csv(
        tmp_path / "canonical.csv",
        [{"annotator_id": "26", "dataset_group": "PreScreen_manual", "condition": "", "active_time_source": "log"}],
    )
    roster = _write_csv(
        tmp_path / "roster.csv",
        [
            {
                "annotator_id": "26",
                "language": "en",
                "expected_manual": "30",
                "expected_semi": "18",
                "expected_oos": "9",
                "expected_total": "57",
                "will_continue": "false",
                "dropout": "false",
                "known_bad_or_process_risk": "true",
                "exclude_from_primary_candidate": "true",
                "completion_status_override": "incomplete_excluded",
                "notes": "known bad / bad annotation / will not complete remaining manual task",
            }
        ],
    )

    row = build_completion_audit(canonical, roster)[0]

    assert row["completion_status"] == "incomplete_excluded"
    assert row["eligible_for_final_completion_denominator"] is False
    assert row["eligible_for_primary_prescreen_candidate"] is False


def test_unknown_roster_only_when_worker_absent_from_roster(tmp_path: Path) -> None:
    canonical = _write_csv(
        tmp_path / "canonical.csv",
        [{"annotator_id": "missing", "dataset_group": "PreScreen_manual", "condition": "", "active_time_source": "log"}],
    )
    roster = _write_csv(
        tmp_path / "roster.csv",
        [
            {
                "annotator_id": "listed",
                "language": "en",
                "expected_manual": "1",
                "expected_semi": "0",
                "expected_oos": "0",
                "expected_total": "1",
                "will_continue": "true",
                "dropout": "false",
                "known_bad_or_process_risk": "false",
                "exclude_from_primary_candidate": "false",
                "completion_status_override": "",
                "notes": "",
            }
        ],
    )

    audit = {row["annotator_id"]: row for row in build_completion_audit(canonical, roster)}

    assert audit["missing"]["completion_status"] == "unknown_roster"
    assert audit["listed"]["completion_status"] == "pending_completion"


def test_completion_audit_flags_unknown_condition_schema_drift(tmp_path: Path) -> None:
    canonical = _write_csv(
        tmp_path / "canonical.csv",
        [{"annotator_id": "w1", "dataset_group": "unexpected_pool", "condition": "weird", "active_time_source": "log"}],
    )
    roster = _write_csv(
        tmp_path / "roster.csv",
        [
            {
                "annotator_id": "w1",
                "language": "zh",
                "expected_manual": "0",
                "expected_semi": "0",
                "expected_oos": "0",
                "expected_total": "1",
                "will_continue": "true",
                "dropout": "false",
                "known_bad_or_process_risk": "false",
                "exclude_from_primary_candidate": "false",
                "completion_status_override": "",
                "notes": "",
            }
        ],
    )

    row = build_completion_audit(canonical, roster)[0]

    assert row["unknown_observed"] == 1
    assert row["condition_schema_warning"] == "unknown_condition_observed"


def test_fixed_closeout_roster_status_summary_matches_expected_counts() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    rows = build_completion_audit(
        repo_root / "analysis_results/prescreen_closeout/prescreen_canonical_annotations.csv",
        repo_root / "analysis_results/prescreen_closeout/prescreen_worker_roster.csv",
    )
    counts: dict[str, int] = {}
    for row in rows:
        status = str(row["completion_status"])
        counts[status] = counts.get(status, 0) + 1

    assert counts == {
        "complete": 23,
        "dropout_no_future": 3,
        "known_bad_complete": 2,
        "incomplete_excluded": 1,
    }
    assert "unknown_roster" not in counts
    id21 = next(row for row in rows if row["annotator_id"] == "21")
    assert id21["completion_status"] == "known_bad_complete"
    assert id21["known_bad_or_process_risk"] is True
    assert id21["eligible_for_primary_prescreen_candidate"] is False
