from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.thesis_main.registry.audit_ls_import_materialization_v3_1 import build


def _csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_ls_import_materialization_audit(tmp_path: Path) -> None:
    out = tmp_path / "analysis_results/calibration_rebuild_20260702"
    pool_fields = ["task_id", "base_task_id", "image_stem", "image_id", "image_path"]
    _csv(out / "calibration_anchor_draft_v2.csv", pool_fields, [{"task_id": f"a{i}", "base_task_id": f"a{i}", "image_stem": f"a{i}", "image_id": f"a{i}", "image_path": "http://img"} for i in range(12)])
    _csv(out / "calibration_core_draft_v3_1.csv", pool_fields, [{"task_id": f"c{i}", "base_task_id": f"c{i}", "image_stem": f"c{i}", "image_id": f"c{i}", "image_path": "http://img"} for i in range(75)])
    _csv(out / "calibration_semi_selection_draft_v3_1.csv", pool_fields, [{"task_id": f"s{i}", "base_task_id": f"s{i}", "image_stem": f"s{i}", "image_id": f"s{i}", "image_path": "http://img"} for i in range(25)])
    _csv(out / "calibration_reserve_draft_v3_1.csv", pool_fields, [{"task_id": f"r{i}", "base_task_id": f"r{i}", "image_stem": f"r{i}", "image_id": f"r{i}", "image_path": "http://img"} for i in range(13)])
    mapping_rows = []
    for group, entry, prefix, n in [("Calibration_anchor", "A", "a", 12), ("Calibration_core", "B", "c", 75), ("Calibration_semi", "C", "s", 25), ("Calibration_reserve", "R", "r", 13)]:
        for i in range(n):
            inner = str(i + 1)
            mapping_rows.append({"task_id": f"{prefix}{i}", "base_task_id": f"{prefix}{i}", "task_code": f"{entry}-{i + 1:03d}", "inner_id": inner, "task_url": "http://task", "intended_project_group": group})
    _csv(out / "ls_project_mapping_audit_v3_1.csv", ["task_id", "base_task_id", "task_code", "inner_id", "task_url", "intended_project_group"], mapping_rows)
    internal = []
    for row in mapping_rows:
        if row["intended_project_group"] == "Calibration_reserve":
            continue
        internal.append({"worker_id": "w", "task_id": row["task_id"], "base_task_id": row["base_task_id"], "task_code": row["task_code"], "inner_id": row["inner_id"], "task_url": row["task_url"], "dataset_group": row["intended_project_group"]})
    _csv(out / "worker_distribution_internal_manifest_v3_1.csv", ["worker_id", "task_id", "base_task_id", "task_code", "inner_id", "task_url", "dataset_group"], internal)
    _csv(out / "worker_facing_distribution_zh_merged_v3_1.csv", ["public_worker_code", "worker_name", "task_code"], [{"public_worker_code": "W001", "worker_name": "张三", "task_code": row["task_code"]} for row in internal])
    (out / "worker_facing_distribution_overseas_individual_v3_1").mkdir()
    (out / "c1_launch_readiness_draft_v3_1.json").write_text(json.dumps({"passed": False}), encoding="utf-8")

    summary = build(tmp_path)

    assert summary["passed"] is True
    assert summary["counts"] == {"Calibration_anchor": 12, "Calibration_core": 75, "Calibration_semi": 25, "Calibration_reserve": 13}
    assert summary["assigned_c1_tasks_have_inner_id_and_task_url"] is True
    assert summary["reserve_not_in_c1_worker_facing_distribution"] is True
    assert summary["worker_facing_task_codes_subset_of_manual_semi"] is True
    assert summary["worker_facing_reserve_task_code_count"] == 0
    assert summary["no_duplicate_inner_id_within_each_intended_project_group"] is True
    assert summary["import_candidate_forbidden_keys_found"] == {}
