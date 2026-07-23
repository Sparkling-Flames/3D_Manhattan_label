import csv
import json
from pathlib import Path

from tools.thesis_main.analysis.materialize_c1_operational_reference import materialize


def _csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_operational_reference_preserves_reviewed_and_leaves_unreviewed_pending(tmp_path: Path) -> None:
    canonical = tmp_path / "canonical.csv"
    geometry = tmp_path / "geometry.jsonl"
    inventory = tmp_path / "inventory.csv"
    gt = tmp_path / "gt.json"
    _csv(canonical, [
        {"project_id": "66", "ls_runtime_task_id": "1", "task_id": "t1", "base_task_id": "reviewed", "condition": "manual", "worker_id": "w1", "annotation_id": "a1", "canonical_annotation_id": "c1", "dataset_group": "Calibration_anchor"},
        {"project_id": "67", "ls_runtime_task_id": "2", "task_id": "t2", "base_task_id": "pending", "condition": "manual", "worker_id": "w1", "annotation_id": "a2", "canonical_annotation_id": "c2", "dataset_group": "Calibration_core"},
    ])
    points = [[100, 100], [100, 400], [700, 100], [700, 400]]
    geometry.write_text("\n".join(json.dumps({"canonical_annotation_id": key, "corners_px": points}) for key in ("c1", "c2")), encoding="utf-8")
    _csv(inventory, [
        {"base_task_id": "reviewed", "expert_review_status": "latest_human_reviewed", "expert_scope_confirmed": "inscope", "old_manual_scope_raw": ""},
        {"base_task_id": "pending", "expert_review_status": "unreviewed_pool", "expert_scope_confirmed": "", "old_manual_scope_raw": ""},
    ])
    result = [{"type": "keypointlabels", "value": {"x": x / 10.24, "y": y / 5.12}} for x, y in points]
    gt.write_text(json.dumps([{"id": "g1", "project": 70, "data": {"title": "reviewed.jpg"}, "annotations": [{"id": "ga1", "ground_truth": True, "result": result}]}]), encoding="utf-8")

    summary = materialize(canonical, geometry, inventory, gt, tmp_path)

    assert summary["n_resolved_contexts"] == 1
    assert summary["n_pending_contexts"] == 1
    assert summary["n_gt_quality_evaluable"] == 1
    with (tmp_path / "c1_task_outcome_reference.csv").open(encoding="utf-8") as stream:
        assert list(csv.DictReader(stream))[0]["final_scope"] == "in_scope"
