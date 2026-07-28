import csv

from tools.thesis_main.analysis.materialize_c1_operational_reference import materialize_gt_cluster_alignment


def _write(path, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


def test_minority_better_gt_creates_candidate_without_mutating_structure(tmp_path):
    crowd, loo, quality = tmp_path/"crowd.csv", tmp_path/"loo.csv", tmp_path/"quality.csv"
    _write(crowd, [{"base_task_id": "b", "largest_cluster_worker_ids": "w1;w2;w3", "second_cluster_worker_ids": "w4;w5", "task_crowd_structure_status": "supported_multimodal"}])
    _write(loo, [{"base_task_id": "b", "worker_id": worker, "canonical_annotation_id": f"c{worker}"} for worker in ("w1","w2","w3","w4","w5")])
    _write(quality, [{"canonical_annotation_id": f"c{worker}", "iou_to_gt": .4 if worker.startswith("w1") or worker.startswith("w2") or worker.startswith("w3") else .9} for worker in ("w1","w2","w3","w4","w5")])
    result = materialize_gt_cluster_alignment(crowd, loo, quality, tmp_path)
    assert result["conflict_candidates"] >= 1 and result["reference_modified"] is False
    assert "supported_multimodal" in crowd.read_text(encoding="utf-8")
