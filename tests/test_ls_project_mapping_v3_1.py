from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.thesis_main.registry.audit_ls_project_mapping_v3_1 import build


def _csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_ls_project_mapping_v3_1_audits_counts_and_redaction(tmp_path: Path) -> None:
    out = tmp_path / "analysis_results/calibration_rebuild_20260702"
    manual_fields = ["worker_id", "task_id", "base_task_id", "dataset_group", "assignment_batch", "expected_completion_order"]
    manual = []
    for i in range(12):
        manual.append({"worker_id": "1", "task_id": f"a{i}", "base_task_id": f"anchor_{i}", "dataset_group": "Calibration_anchor", "assignment_batch": "anchor_all", "expected_completion_order": str(i)})
    for i in range(375):
        manual.append({"worker_id": str(i % 23), "task_id": f"c{i % 75}", "base_task_id": f"core_{i % 75}", "dataset_group": "Calibration_core", "assignment_batch": "core", "expected_completion_order": str(i)})
    manual += manual[:264]
    manual = manual[:651]
    semi = [{"worker_id": str(i % 23), "task_id": f"s{i % 25}", "base_task_id": f"semi_{i % 25}", "dataset_group": "Calibration_semi", "assignment_batch": "semi", "expected_completion_order": str(i)} for i in range(100)]
    _csv(out / "assignment_manifest_C1_manual_draft_v3_1.csv", manual_fields, manual)
    _csv(out / "assignment_manifest_C1_semi_draft_v3_1.csv", manual_fields, semi)
    _csv(out / "calibration_anchor_draft_v2.csv", ["task_id", "base_task_id", "image_stem"], [{"task_id": f"a{i}", "base_task_id": f"anchor_{i}", "image_stem": f"anchor_{i}"} for i in range(12)])
    _csv(out / "calibration_core_draft_v3_1.csv", ["task_id", "base_task_id", "image_stem"], [{"task_id": f"c{i}", "base_task_id": f"core_{i}", "image_stem": f"core_{i}"} for i in range(75)])
    _csv(out / "calibration_reserve_draft_v3_1.csv", ["task_id", "base_task_id", "image_stem"], [{"task_id": f"r{i}", "base_task_id": f"reserve_{i}", "image_stem": f"reserve_{i}"} for i in range(13)])
    _csv(out / "calibration_semi_selection_draft_v3_1.csv", ["task_id", "base_task_id", "image_stem"], [{"task_id": f"s{i}", "base_task_id": f"semi_{i}", "image_stem": f"semi_{i}"} for i in range(25)])
    internal_fields = ["worker_id", "public_worker_code", "task_id", "base_task_id", "task_code", "inner_id", "task_url", "dataset_group", "assignment_batch", "expected_completion_order", "source_manifest", "internal_only"]
    internal = []
    for idx, row in enumerate(manual + semi, start=1):
        prefix = {"Calibration_anchor": "A", "Calibration_core": "B", "Calibration_semi": "C"}[row["dataset_group"]]
        internal.append({**row, "public_worker_code": "W001", "task_code": f"{prefix}-{idx:03d}", "inner_id": str(idx), "task_url": f"http://x/{idx}", "source_manifest": "x", "internal_only": "true"})
    _csv(out / "worker_distribution_internal_manifest_v3_1.csv", internal_fields, internal)
    _csv(out / "worker_facing_distribution_zh_merged_v3_1.csv", ["public_worker_code", "worker_name", "task_code"], [{"public_worker_code": "W001", "worker_name": "张三", "task_code": row["task_code"]} for row in internal])
    redaction = {"passed": True, "counts": {"zh_rows": 751}, "dataset_group_leaked": False, "anchor_core_semi_leaked": False, "used_for_r_u_or_rq2_leaked": False, "semi_family_leaked": False, "model_issue_difficulty_source_status_leaked": False}
    (out / "worker_facing_distribution_redaction_audit_v3_1.json").write_text(json.dumps(redaction), encoding="utf-8")
    (out / "c1_launch_readiness_draft_v3_1.json").write_text(json.dumps({"passed": False, "blockers": []}), encoding="utf-8")
    summary = build(tmp_path)

    assert summary["passed"] is True
    assert summary["manual_assignment_rows"] == 651
    assert summary["semi_assignment_rows"] == 100
    assert summary["worker_distribution_internal_rows"] == 751
    assert summary["reserve_c2_only_not_in_worker_distribution"] is True
    assert summary["worker_facing_redaction_passed"] is True
    assert summary["worker_facing_uses_task_code_only"] is True
    assert summary["task_code_backlinks_planned_project_and_inner_id"] is True
    rows = list(csv.DictReader((out / "ls_project_mapping_audit_v3_1.csv").open(encoding="utf-8-sig")))
    assert next(row for row in rows if row["base_task_id"] == "anchor_0")["inner_id"] == "1"
    assert next(row for row in rows if row["base_task_id"] == "anchor_0")["task_code"] == "A-001"
    assert next(row for row in rows if row["base_task_id"] == "core_0")["inner_id"] == "1"
    assert next(row for row in rows if row["base_task_id"] == "core_0")["task_code"] == "B-001"
    assert next(row for row in rows if row["base_task_id"] == "reserve_0")["mapping_status"] == "planned_c2_only"
