from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.thesis_main.registry.manual_zh_analysis_chain_precheck_v3_1 import build


def _csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _kp(x: float, y: float) -> dict:
    return {"type": "keypointlabels", "from_name": "kp", "to_name": "img", "value": {"x": x, "y": y, "keypointlabels": ["Corner"]}}


def _ann(annotation_id: str, worker: str = "2", lead_time: float = 5.0) -> dict:
    return {"id": annotation_id, "completed_by": {"id": worker}, "lead_time": lead_time, "result": [_kp(1, 1), _kp(1, 2)]}


def _task(runtime_id: str, annotation: list[dict], *, task_id: str, base: str, source: str = "core") -> dict:
    return {
        "id": runtime_id,
        "project": 65,
        "data": {"task_id": task_id, "base_task_id": base, "title": f"{base}.jpg", "source_draft": source, "condition": "manual"},
        "annotations": annotation,
    }


def test_manual_zh_precheck_preserves_binding_and_assignment_boundaries(tmp_path: Path) -> None:
    out = tmp_path / "analysis_results/calibration_rebuild_20260702"
    mapping_fields = ["task_id", "base_task_id", "inner_id", "task_url", "intended_project_group", "mapping_status"]
    _csv(
        out / "ls_project_mapping_audit_v3_1.csv",
        mapping_fields,
        [
            {"task_id": "a", "base_task_id": "anchor_base", "inner_id": "1", "task_url": "planned://A/1", "intended_project_group": "Calibration_anchor", "mapping_status": "planned_import_order"},
            {"task_id": "c", "base_task_id": "core_base", "inner_id": "1", "task_url": "planned://B/1", "intended_project_group": "Calibration_core", "mapping_status": "planned_import_order"},
            {"task_id": "d", "base_task_id": "dup_base", "inner_id": "2", "task_url": "planned://B/2", "intended_project_group": "Calibration_core", "mapping_status": "planned_import_order"},
            {"task_id": "x", "base_task_id": "outside_base", "inner_id": "3", "task_url": "planned://B/3", "intended_project_group": "Calibration_core", "mapping_status": "planned_import_order"},
        ],
    )
    assign_fields = ["worker_id", "task_id", "base_task_id", "dataset_group"]
    assigned = [
        {"worker_id": "2", "task_id": "a", "base_task_id": "anchor_base", "dataset_group": "Calibration_anchor"},
        {"worker_id": "2", "task_id": "c", "base_task_id": "core_base", "dataset_group": "Calibration_core"},
        {"worker_id": "2", "task_id": "d", "base_task_id": "dup_base", "dataset_group": "Calibration_core"},
    ]
    _csv(out / "assignment_manifest_C1_manual_draft_v3_1.csv", assign_fields, assigned)
    _csv(out / "assignment_manifest_C1_semi_draft_v3_1.csv", assign_fields, [])
    _csv(out / "worker_distribution_internal_manifest_v3_1.csv", assign_fields, assigned)

    export = tmp_path / "manual_zh.json"
    export.write_text(
        json.dumps(
            [
                _task("100", [_ann("ann_exact")], task_id="a", base="anchor_base", source="anchor"),
                _task("101", [_ann("ann_lead", lead_time=9)], task_id="c", base="core_base"),
                _task("102", [_ann("ann_old"), _ann("ann_new", lead_time=8)], task_id="d", base="dup_base"),
                _task("103", [_ann("ann_outside")], task_id="x", base="outside_base"),
            ]
        ),
        encoding="utf-8",
    )
    log = tmp_path / "active_times_2026-07-03.jsonl"
    log.write_text(
        "\n".join(
            [
                json.dumps({"project_id": "65", "task_id": "100", "annotator_id": "2", "annotation_id": "ann_exact", "session_id": "s1", "active_seconds": 12, "is_manual_flush": True, "script_version": "v"}),
                json.dumps({"project_id": "65", "task_id": "102", "annotator_id": "2", "annotation_id": "ann_new", "session_id": "s2", "active_seconds": 4, "is_manual_flush": True, "script_version": "v"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    summary = build(tmp_path, export, log)
    precheck = out / "manual_zh_analysis_chain_precheck_v3_1"
    canonical = list(csv.DictReader((precheck / "manual_zh_canonical_annotations_precheck_v3_1.csv").open(encoding="utf-8-sig")))
    active = {row["annotation_id"]: row for row in csv.DictReader((precheck / "manual_zh_active_time_binding_audit_v3_1.csv").open(encoding="utf-8-sig"))}
    realized = list(csv.DictReader((precheck / "manual_zh_realized_vs_assigned_audit_v3_1.csv").open(encoding="utf-8-sig")))

    negative = list(csv.DictReader((precheck / "manual_zh_negative_guard_outside_assignment_v3_1.csv").open(encoding="utf-8-sig")))

    assert {row["annotation_id"] for row in canonical} >= {"ann_exact", "ann_lead", "ann_new"}
    assert "ann_outside" not in {row["annotation_id"] for row in canonical}
    assert all(row["canonical_annotation_id"] for row in canonical)
    assert active["ann_exact"]["active_time_key"] == "65|100|2|ann_exact"
    assert active["ann_exact"]["active_time_source"] == "log"
    assert active["ann_exact"]["primary_active_time_eligible"] == "True"
    assert active["ann_lead"]["active_time_source"] == "lead_time_fallback"
    assert active["ann_lead"]["primary_active_time_eligible"] == "False"
    assert sum(row["task_id"] == "d" for row in realized) == 1
    assert not any(row["outside_assignment_submission"] == "true" for row in realized)
    assert next(row for row in negative if row["task_id"] == "x")["reason"] == "outside_assignment_submission_filtered_from_positive_fixture"
    assert summary["worker_facing_bare_inner_id_ambiguity_detected"] is False
    assert summary["source_export_bare_inner_id_ambiguity_detected"] is True
    assert summary["worker_facing_task_code_identity_passed"] is True
    assert summary["positive_fixture_excluded_outside_assignment_count"] == 1
    assert summary["statistical_interpretation_allowed"] is False
    assert summary["full_c1_smoke_test_passed"] is False
