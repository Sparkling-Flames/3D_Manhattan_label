from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd

from tools.thesis_main.registry.build_worker_distribution_v3_1 import build


def _csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_worker_distribution_redacts_worker_facing_fields(tmp_path: Path) -> None:
    out = tmp_path / "analysis_results/calibration_rebuild_20260702"
    fields = ["round_id", "worker_id", "task_id", "base_task_id", "dataset_group", "assignment_batch", "assignment_reason", "is_common_anchor", "expected_completion_order", "manifest_version", "watch_flag"]
    _csv(out / "assignment_manifest_C1_manual_draft_v3_1.csv", fields, [{"round_id": "C1", "worker_id": "1", "task_id": "t1", "base_task_id": "scene_a", "dataset_group": "Calibration_core", "assignment_batch": "core", "assignment_reason": "x", "is_common_anchor": "false", "expected_completion_order": "1", "manifest_version": "v", "watch_flag": "True"}])
    _csv(out / "assignment_manifest_C1_semi_draft_v3_1.csv", fields + ["used_for_r_u", "used_for_rq2", "semi_family"], [{"round_id": "C1", "worker_id": "28", "task_id": "t2", "base_task_id": "scene_b", "dataset_group": "Calibration_semi", "assignment_batch": "semi", "assignment_reason": "x", "is_common_anchor": "false", "expected_completion_order": "1", "manifest_version": "v", "watch_flag": "True", "used_for_r_u": "false", "used_for_rq2": "true", "semi_family": "x"}])
    pool_fields = ["task_id", "base_task_id", "image_stem"]
    _csv(out / "calibration_anchor_draft_v2.csv", pool_fields, [{"task_id": "a1", "base_task_id": "scene_anchor", "image_stem": "scene_anchor"}])
    _csv(out / "calibration_core_draft_v3_1.csv", pool_fields, [{"task_id": "t1", "base_task_id": "scene_a", "image_stem": "scene_a"}])
    _csv(out / "calibration_semi_selection_draft_v3_1.csv", pool_fields, [{"task_id": "t2", "base_task_id": "scene_b", "image_stem": "scene_b"}])
    export = [
        {"id": 101, "inner_id": 11, "project": 9, "data": {"title": "scene_a.jpg"}},
        {"id": 102, "inner_id": 12, "project": 9, "data": {"title": "scene_b.jpg"}},
    ]
    export_dir = tmp_path / "export_label"
    export_dir.mkdir()
    (export_dir / "groudTruth.json").write_text(json.dumps(export), encoding="utf-8")
    pd.DataFrame([{"编号": 1, "年级+专业+姓名": "张三"}]).to_excel(export_dir / "标注人员.xlsx", index=False)
    pd.DataFrame([{"user id": 28, "Unnamed: 1": "Overseas Worker"}]).to_excel(export_dir / "外国标注人员.xlsx", index=False)
    (out / "c1_launch_readiness_draft_v3_1.json").write_text(json.dumps({"passed": False}), encoding="utf-8")

    audit = build(tmp_path)

    assert audit["passed"] is True
    zh_fields = next(csv.reader((out / "worker_facing_distribution_zh_merged_v3_1.csv").open(encoding="utf-8-sig")))
    overseas_fields = next(csv.reader((out / "worker_facing_distribution_overseas_individual_v3_1/worker_W028.csv").open(encoding="utf-8-sig")))
    assert zh_fields == ["public_worker_code", "worker_name", "entry", "inner_id"]
    assert overseas_fields == ["entry", "inner_id"]
    zh_row = next(csv.DictReader((out / "worker_facing_distribution_zh_merged_v3_1.csv").open(encoding="utf-8-sig")))
    overseas_row = next(csv.DictReader((out / "worker_facing_distribution_overseas_individual_v3_1/worker_W028.csv").open(encoding="utf-8-sig")))
    assert zh_row["entry"] == "B"
    assert overseas_row["entry"] == "C"
    assert zh_row["inner_id"] == "1"
    assert overseas_row["inner_id"] == "1"
    assert not any(audit["worker_facing_forbidden_terms"].values())
