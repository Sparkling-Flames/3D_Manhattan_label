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
    assert summary["geometry_reference_ready"] is False
    assert summary["task_outcome_reference_ready"] is False
    assert summary["estimand_specific_closeout_ready"] is False
    with (tmp_path / "c1_task_outcome_reference.csv").open(encoding="utf-8") as stream:
        assert list(csv.DictReader(stream))[0]["final_scope"] == "in_scope"
    queue = list(csv.DictReader((tmp_path / "c1_scope_review_queue.csv").open(encoding="utf-8")))
    assert [row["base_task_id"] for row in queue] == ["pending"]


def test_reference_amendment_scores_with_corrected_gt_but_excludes_triggering_submission(tmp_path: Path) -> None:
    canonical, geometry, inventory, gt, amendment = [tmp_path / name for name in ("canonical.csv", "geometry.jsonl", "inventory.csv", "gt.json", "amendment.csv")]
    _csv(canonical, [
        {"project_id": "66", "ls_runtime_task_id": "1", "task_id": "t1", "base_task_id": "b1", "condition": "manual", "worker_id": "w1", "annotation_id": "a1", "canonical_annotation_id": "c1", "dataset_group": "Calibration_core"},
        {"project_id": "66", "ls_runtime_task_id": "1", "task_id": "t1", "base_task_id": "b1", "condition": "manual", "worker_id": "w2", "annotation_id": "a2", "canonical_annotation_id": "c2", "dataset_group": "Calibration_core"},
    ])
    points = [[100, 100], [100, 400], [700, 100], [700, 400]]
    geometry.write_text("\n".join(json.dumps({"canonical_annotation_id": key, "corners_px": points}) for key in ("c1", "c2")), encoding="utf-8")
    _csv(inventory, [{"base_task_id": "b1", "expert_review_status": "latest_human_reviewed", "expert_scope_confirmed": "inscope", "old_manual_scope_raw": ""}])
    gt.write_text("[]", encoding="utf-8")
    _csv(amendment, [{
        "base_task_id": "b1", "reference_status": "reference_corrected", "corrected_points_json": json.dumps(points),
        "triggering_canonical_annotation_ids_json": json.dumps(["c1"]), "reviewed_by": "expert", "reviewed_at": "2026-07-25T00:00:00Z",
    }])
    summary = materialize(canonical, geometry, inventory, gt, tmp_path / "out", reference_amendment=amendment)
    rows = {row["canonical_annotation_id"]: row for row in csv.DictReader((tmp_path / "out" / "c1_gt_quality_evidence.csv").open(encoding="utf-8"))}
    assert summary["reference_status_counts"]["reference_corrected"] == 1
    assert rows["c1"]["quality_evaluable"].lower() == "false"
    assert rows["c1"]["score_reason"] == "submission_informed_reference_revision"
    assert rows["c2"]["quality_evaluable"].lower() == "true"


def test_scope_adjudication_must_bind_the_generated_base_task_queue(tmp_path: Path) -> None:
    canonical, geometry, inventory, gt = [tmp_path / name for name in ("canonical.csv", "geometry.jsonl", "inventory.csv", "gt.json")]
    _csv(canonical, [{"project_id": "66", "ls_runtime_task_id": "1", "task_id": "t1", "base_task_id": "b1", "condition": "manual", "worker_id": "w1", "annotation_id": "a1", "canonical_annotation_id": "c1", "dataset_group": "Calibration_core"}])
    points = [[100, 100], [100, 400], [700, 100], [700, 400]]
    geometry.write_text(json.dumps({"canonical_annotation_id": "c1", "corners_px": points}), encoding="utf-8")
    _csv(inventory, [{"base_task_id": "b1", "expert_review_status": "unreviewed_pool", "expert_scope_confirmed": "", "old_manual_scope_raw": ""}])
    gt.write_text("[]", encoding="utf-8")
    materialize(canonical, geometry, inventory, gt, tmp_path / "audit")
    template = next(csv.DictReader((tmp_path / "audit" / "c1_scope_adjudication_template.csv").open(encoding="utf-8")))
    decision = tmp_path / "scope.csv"
    _csv(decision, [{**template, "final_scope": "oos", "oos_subtype": "unsupported", "reviewed_by": "expert", "reviewed_at": "2026-07-25T00:00:00Z", "source_queue_sha256": "stale"}])
    summary = materialize(canonical, geometry, inventory, gt, tmp_path / "formal", scope_adjudication_csv=decision)
    assert summary["invalid_or_stale_scope_adjudication_count"] == 1
    assert summary["n_pending_contexts"] == 1
