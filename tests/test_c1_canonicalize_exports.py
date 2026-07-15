from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.thesis_main.analysis.c1_canonicalize_exports import build_canonicalization


def _csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _kp(x: float, y: float) -> dict:
    return {"type": "keypointlabels", "value": {"x": x, "y": y, "keypointlabels": ["Corner"]}}


def _ann(ann_id: str, worker: str, lead_time: float = 0.0) -> dict:
    return {"id": ann_id, "completed_by": {"id": worker}, "lead_time": lead_time, "result": [_kp(1, 1), _kp(2, 2)]}


def _task(runtime_id: str, task_id: str, base: str, annotations: list[dict]) -> dict:
    return {
        "id": runtime_id,
        "project": 66,
        "data": {
            "task_id": task_id,
            "base_task_id": base,
            "title": f"{base}.jpg",
            "image": f"{base}.jpg",
            "source_draft": "core",
            "condition": "manual",
        },
        "annotations": annotations,
    }


def _read_csv(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.open(encoding="utf-8")))


def test_c1_canonicalization_materializes_required_fields_and_active_policy(tmp_path: Path) -> None:
    fields = ["round_id", "worker_id", "task_id", "base_task_id", "dataset_group"]
    manual = tmp_path / "manual.csv"
    semi = tmp_path / "semi.csv"
    internal = tmp_path / "internal.csv"
    mapping = tmp_path / "mapping.csv"
    assigned = [
        {"round_id": "C1", "worker_id": "w1", "task_id": "t1", "base_task_id": "base1", "dataset_group": "Calibration_core"},
        {"round_id": "C1", "worker_id": "w2", "task_id": "t2", "base_task_id": "base2", "dataset_group": "Calibration_core"},
        {"round_id": "C1", "worker_id": "w3", "task_id": "t3", "base_task_id": "base3", "dataset_group": "Calibration_core"},
        {"round_id": "C1", "worker_id": "w4", "task_id": "missing", "base_task_id": "base_missing", "dataset_group": "Calibration_core"},
    ]
    _csv(manual, fields, assigned)
    _csv(semi, fields, [])
    _csv(internal, fields, assigned)
    _csv(
        mapping,
        ["task_id", "base_task_id", "inner_id", "intended_project_group", "mapping_status"],
        [
            {"task_id": "t1", "base_task_id": "base1", "inner_id": "1", "intended_project_group": "Calibration_core", "mapping_status": "planned"},
            {"task_id": "t2", "base_task_id": "base2", "inner_id": "2", "intended_project_group": "Calibration_core", "mapping_status": "planned"},
            {"task_id": "t3", "base_task_id": "base3", "inner_id": "3", "intended_project_group": "Calibration_core", "mapping_status": "planned"},
            {"task_id": "missing", "base_task_id": "base_missing", "inner_id": "4", "intended_project_group": "Calibration_core", "mapping_status": "planned"},
        ],
    )
    export = tmp_path / "c1_export.json"
    export.write_text(
        json.dumps(
            [
                _task("200", "t1", "base1", [_ann("a1", "w1")]),
                _task("201", "t2", "base2", [_ann("b1", "w2")]),
                _task("202", "t3", "base3", [_ann("c1", "w3", lead_time=11)]),
                _task("203", "t1", "base1", [_ann("d1", "w1"), _ann("d2", "w1", lead_time=9)]),
            ]
        ),
        encoding="utf-8",
    )
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "active_times_2026-07-03.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"project_id": "66", "task_id": "200", "annotator_id": "w1", "annotation_id": "a1", "session_id": "s1", "active_seconds": 12}),
                json.dumps({"project_id": "66", "task_id": "200", "annotator_id": "w1", "annotation_id": "unknown", "session_id": "s1", "active_seconds": 4}),
                json.dumps({"project_id": "66", "task_id": "201", "annotator_id": "w2", "session_id": "single", "active_seconds": 7}),
                json.dumps({"project_id": "66", "task_id": "203", "annotator_id": "w1", "session_id": "single", "active_seconds": 5}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    out = tmp_path / "out"
    summary = build_canonicalization(
        [export],
        manual_assignment=manual,
        semi_assignment=semi,
        worker_distribution=internal,
        planned_task_mapping=mapping,
        active_log=logs,
        output_dir=out,
    )

    rows = list(csv.DictReader((out / "c1_canonical_annotations.csv").open(encoding="utf-8")))
    by_runtime = {row["ls_runtime_task_id"]: row for row in rows}
    assert summary["n_canonical_rows"] == 3
    assert summary["outside_assignment_submission_count"] == 0
    assert summary["duplicate_worker_task_submission_count"] == 0
    assert summary["duplicate_review_pending_count"] == 1
    assert summary["active_time_primary_ineligible_count"] == 2
    assert summary["active_time_log_missing_count"] == 0
    assert summary["active_time_task_level_fallback_count"] == 1
    assert summary["active_time_lead_time_fallback_count"] == 1
    assert summary["active_time_sensitivity_eligible_count"] == 3
    assert summary["structural_integrity_passed"] is False
    assert summary["collection_completeness_passed"] is False
    assert summary["passed_semantics"] == "structural_only_not_collection_complete"
    assert all(row["round_id"] == "C1" for row in rows)
    assert all(row["canonical_annotation_id"] for row in rows)
    assert by_runtime["200"]["primary_active_time_eligible"] == "true"
    assert by_runtime["200"]["active_time"] == "12.0"
    assert by_runtime["200"]["active_time_integrity_status"] == "exact_annotation_valid"
    assert by_runtime["200"]["unassigned_audit_present"] == "true"
    assert by_runtime["200"]["system_collection_issue"] == "true"
    assert by_runtime["200"]["audit_only"] == "false"
    assert by_runtime["200"]["active_time_exclusion_reason"] == ""
    assert by_runtime["200"]["unassigned_active_time_exclusion_reason"] == "unknown_annotation_audit_only"
    assert by_runtime["201"]["active_time_match_status"] == "project+task+annotator"
    assert by_runtime["201"]["primary_active_time_eligible"] == "false"
    assert by_runtime["202"]["active_time_source"] == "lead_time_fallback"
    assert by_runtime["202"]["primary_active_time_eligible"] == "false"
    assert by_runtime["202"]["sensitivity_active_time_eligible"] == "true"
    assert "203" not in by_runtime
    duplicate = _read_csv(out / "c1_duplicate_annotation_audit.csv")[0]
    assert duplicate["duplicate_review_status"] == "pending"
    assert duplicate["duplicate_geometry_type"] == "distinct_ids_exact_match"
    realized_audit = _read_csv(out / "c1_realized_vs_assigned_audit.csv")
    assert any(row["task_id"] == "missing" and row["worker_id"] == "w4" and row["missing_submission"] == "true" for row in realized_audit)
    assert (out / "raw_inputs" / "raw_input_snapshot_manifest.csv").exists()
    assert (out / "c1_runtime_task_mapping.csv").exists()
    assert summary["unassigned_active_time_seconds_total"] == 4.0
    assert summary["unknown_annotation_event_count_total"] == 1
    assert summary["unknown_annotation_session_count_total"] == 1
    assert summary["workers_with_unknown_audit_count"] == 1
    assert summary["exact_annotation_primary_count"] == 1
    assert "unknown_annotation_audit_present" not in summary["blockers"]


def test_same_annotation_id_across_exports_is_input_duplicate_not_worker_duplicate(tmp_path: Path) -> None:
    fields = ["round_id", "worker_id", "task_id", "base_task_id", "dataset_group"]
    assignment = [{"round_id": "C1", "worker_id": "w1", "task_id": "t1", "base_task_id": "b1", "dataset_group": "Calibration_core"}]
    manual, semi, internal, mapping = (tmp_path / name for name in ("manual.csv", "semi.csv", "internal.csv", "mapping.csv"))
    _csv(manual, fields, assignment); _csv(semi, fields, []); _csv(internal, fields, assignment)
    _csv(mapping, ["task_id", "base_task_id", "inner_id", "intended_project_group", "mapping_status"], [{"task_id": "t1", "base_task_id": "b1", "inner_id": "1", "intended_project_group": "Calibration_core", "mapping_status": "planned"}])
    export_a, export_b = tmp_path / "a.json", tmp_path / "b.json"
    payload = [_task("1", "t1", "b1", [_ann("ann", "w1", lead_time=99)])]
    export_a.write_text(json.dumps(payload), encoding="utf-8"); export_b.write_text(json.dumps(payload), encoding="utf-8")
    out = tmp_path / "out"
    summary = build_canonicalization([export_a, export_b], manual, semi, internal, mapping, active_log=None, output_dir=out)
    row = _read_csv(out / "c1_canonical_annotations.csv")[0]
    review = _read_csv(out / "c1_duplicate_annotation_audit.csv")[0]
    assert summary["duplicate_review_pending_count"] == 0
    assert summary["duplicate_input_repeat_count"] == 1
    assert row["duplicate_worker_task_submission"] == "false"
    assert row["primary_active_time_eligible"] == "false"
    assert review["duplicate_geometry_type"] == "repeated_export_same_annotation_id"


def test_distinct_annotation_ids_require_review_and_selected_exact_time_follows_choice(tmp_path: Path) -> None:
    fields = ["round_id", "worker_id", "task_id", "base_task_id", "dataset_group"]
    assignment = [{"round_id": "C1", "worker_id": "w1", "task_id": "t1", "base_task_id": "b1", "dataset_group": "Calibration_core"}]
    manual, semi, internal, mapping = (tmp_path / name for name in ("manual.csv", "semi.csv", "internal.csv", "mapping.csv"))
    _csv(manual, fields, assignment); _csv(semi, fields, []); _csv(internal, fields, assignment)
    _csv(mapping, ["task_id", "base_task_id", "inner_id", "intended_project_group", "mapping_status"], [{"task_id": "t1", "base_task_id": "b1", "inner_id": "1", "intended_project_group": "Calibration_core", "mapping_status": "planned"}])
    export = tmp_path / "export.json"
    export.write_text(json.dumps([_task("1", "t1", "b1", [_ann("a1", "w1", 100), _ann("a2", "w1", 1)])]), encoding="utf-8")
    logs = tmp_path / "active.jsonl"
    logs.write_text("\n".join(json.dumps({"project_id": "66", "task_id": "1", "annotator_id": "w1", "annotation_id": ann, "session_id": ann, "active_seconds": seconds}) for ann, seconds in (("a1", 5), ("a2", 17))) + "\n", encoding="utf-8")
    pending = build_canonicalization([export], manual, semi, internal, mapping, active_log=logs, output_dir=tmp_path / "pending")
    assert pending["duplicate_review_pending_count"] == 1
    assert _read_csv(tmp_path / "pending" / "c1_canonical_annotations.csv") == []
    decision = tmp_path / "decision.csv"
    _csv(decision, ["project_id", "ls_runtime_task_id", "worker_id", "decision", "selected_annotation_id", "reviewed_by", "reviewed_at"], [{"project_id": "66", "ls_runtime_task_id": "1", "worker_id": "w1", "decision": "confirm_exact_duplicate", "selected_annotation_id": "a2", "reviewed_by": "reviewer", "reviewed_at": "2026-07-15T00:00:00Z"}])
    resolved = build_canonicalization([export], manual, semi, internal, mapping, active_log=logs, output_dir=tmp_path / "resolved", duplicate_adjudication_csv=decision)
    row = _read_csv(tmp_path / "resolved" / "c1_canonical_annotations.csv")[0]
    assert resolved["duplicate_review_pending_count"] == 0
    assert row["annotation_id"] == "a2"
    assert row["active_time"] == "17.0"
    assert row["active_time_source"] == "log"
    _csv(decision, ["project_id", "ls_runtime_task_id", "worker_id", "decision", "selected_annotation_id", "reviewed_by", "reviewed_at"], [{"project_id": "66", "ls_runtime_task_id": "1", "worker_id": "w1", "decision": "exclude_group", "selected_annotation_id": "", "reviewed_by": "reviewer", "reviewed_at": "2026-07-15T00:00:00Z"}])
    excluded = build_canonicalization([export], manual, semi, internal, mapping, active_log=logs, output_dir=tmp_path / "excluded", duplicate_adjudication_csv=decision, require_complete=True)
    assert excluded["duplicate_review_pending_count"] == 0
    assert excluded["missing_submission_count"] == 0
    assert excluded["collection_completeness_passed"] is True
    assert _read_csv(tmp_path / "excluded" / "c1_canonical_annotations.csv") == []


def test_c1_canonicalization_runtime_collision_blocks(tmp_path: Path) -> None:
    fields = ["round_id", "worker_id", "task_id", "base_task_id", "dataset_group"]
    manual = tmp_path / "manual.csv"
    semi = tmp_path / "semi.csv"
    internal = tmp_path / "internal.csv"
    mapping = tmp_path / "mapping.csv"
    _csv(manual, fields, [])
    _csv(semi, fields, [])
    _csv(internal, fields, [])
    _csv(mapping, ["task_id", "base_task_id", "inner_id", "intended_project_group", "mapping_status"], [])
    export_a = tmp_path / "a.json"
    export_b = tmp_path / "b.json"
    export_a.write_text(json.dumps([_task("same", "t1", "b1", [])]), encoding="utf-8")
    export_b.write_text(json.dumps([_task("same", "t2", "b2", [])]), encoding="utf-8")

    out = tmp_path / "out"
    summary = build_canonicalization([export_a, export_b], manual, semi, internal, mapping, active_log=None, output_dir=out)

    assert summary["runtime_key_collision_count"] == 1
    assert "runtime_key_collision_detected" in summary["blockers"]
    assert _read_csv(out / "c1_runtime_key_collision_audit.csv")[0]["collision_task_id"] == "t2"


def test_c1_canonicalization_planned_mapping_missing_blocks(tmp_path: Path) -> None:
    fields = ["round_id", "worker_id", "task_id", "base_task_id", "dataset_group"]
    manual = tmp_path / "manual.csv"
    semi = tmp_path / "semi.csv"
    internal = tmp_path / "internal.csv"
    mapping = tmp_path / "mapping.csv"
    _csv(manual, fields, [])
    _csv(semi, fields, [])
    _csv(internal, fields, [])
    _csv(mapping, ["task_id", "base_task_id", "inner_id", "intended_project_group", "mapping_status"], [])
    export = tmp_path / "export.json"
    export.write_text(json.dumps([_task("1", "unplanned", "base_unplanned", [])]), encoding="utf-8")

    out = tmp_path / "out"
    summary = build_canonicalization([export], manual, semi, internal, mapping, active_log=None, output_dir=out)

    assert summary["planned_mapping_missing_count"] == 1
    assert "planned_mapping_missing" in summary["blockers"]
    assert _read_csv(out / "c1_runtime_task_mapping.csv")[0]["planned_mapping_status"] == "planned_mapping_missing"


def test_require_complete_makes_missing_submission_fail_passed(tmp_path: Path) -> None:
    fields = ["round_id", "worker_id", "task_id", "base_task_id", "dataset_group"]
    manual = tmp_path / "manual.csv"
    semi = tmp_path / "semi.csv"
    internal = tmp_path / "internal.csv"
    mapping = tmp_path / "mapping.csv"
    assigned = [{"round_id": "C1", "worker_id": "w1", "task_id": "missing", "base_task_id": "base_missing", "dataset_group": "Calibration_core"}]
    _csv(manual, fields, assigned)
    _csv(semi, fields, [])
    _csv(internal, fields, assigned)
    _csv(
        mapping,
        ["task_id", "base_task_id", "inner_id", "intended_project_group", "mapping_status"],
        [{"task_id": "missing", "base_task_id": "base_missing", "inner_id": "1", "intended_project_group": "Calibration_core", "mapping_status": "planned"}],
    )
    export = tmp_path / "export.json"
    export.write_text(json.dumps([]), encoding="utf-8")

    summary = build_canonicalization([export], manual, semi, internal, mapping, active_log=None, output_dir=tmp_path / "out")

    assert summary["structural_integrity_passed"] is True
    assert summary["collection_completeness_passed"] is False
    assert summary["passed"] is True

    strict = build_canonicalization([export], manual, semi, internal, mapping, active_log=None, output_dir=tmp_path / "strict", require_complete=True)

    assert strict["passed"] is False
    assert strict["passed_semantics"] == "structural_and_collection_complete"
