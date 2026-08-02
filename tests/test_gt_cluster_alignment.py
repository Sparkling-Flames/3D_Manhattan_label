import csv

from tools.thesis_main.analysis.materialize_c1_operational_reference import materialize_gt_cluster_alignment


def _write(path, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


def test_minority_better_gt_creates_candidate_without_mutating_structure(tmp_path):
    crowd, loo, quality = tmp_path/"crowd.csv", tmp_path/"loo.csv", tmp_path/"quality.csv"
    _write(crowd, [{
        "base_task_id": "b", "largest_cluster_worker_ids": "w1;w2;w3", "second_cluster_worker_ids": "w4;w5",
        "largest_cluster_medoid_annotation_id": "cw1", "largest_cluster_medoid_worker_id": "w1", "largest_cluster_medoid_geometry_sha256": "g1",
        "second_cluster_medoid_annotation_id": "cw4", "second_cluster_medoid_worker_id": "w4", "second_cluster_medoid_geometry_sha256": "g4",
        "task_crowd_structure_status": "supported_multimodal",
    }])
    _write(loo, [{"base_task_id": "b", "worker_id": worker, "canonical_annotation_id": f"c{worker}"} for worker in ("w1","w2","w3","w4","w5")])
    scores = {"w1": .4, "w2": .99, "w3": .8, "w4": .9, "w5": .95}
    _write(quality, [{"canonical_annotation_id": f"c{worker}", "iou_to_gt": scores[worker], "public_gt_structural_status": "valid"} for worker in scores])
    result = materialize_gt_cluster_alignment(crowd, loo, quality, tmp_path)
    assert result["conflict_candidates"] >= 1 and result["reference_modified"] is False
    with (tmp_path / "c1_gt_cluster_alignment.csv").open(encoding="utf-8") as stream:
        aligned = list(csv.DictReader(stream))
    assert aligned[0]["cluster_medoid_annotation_id"] == "cw1"
    assert float(aligned[0]["cluster_medoid_gt_iou"]) == .4  # never replace the GT-blind medoid with w2
    assert "supported_multimodal" in crowd.read_text(encoding="utf-8")


def test_formal_public_gt_policy_does_not_auto_create_amendment_queue(tmp_path):
    crowd, loo, quality = tmp_path/"crowd.csv", tmp_path/"loo.csv", tmp_path/"quality.csv"
    _write(crowd, [{
        "base_task_id": "b", "largest_cluster_worker_ids": "w1;w2;w3", "second_cluster_worker_ids": "w4;w5",
        "largest_cluster_medoid_annotation_id": "cw1", "largest_cluster_medoid_worker_id": "w1", "largest_cluster_medoid_geometry_sha256": "g1",
        "second_cluster_medoid_annotation_id": "cw4", "second_cluster_medoid_worker_id": "w4", "second_cluster_medoid_geometry_sha256": "g4",
    }])
    _write(loo, [{"base_task_id": "b", "worker_id": "w1"}])
    _write(quality, [
        {"canonical_annotation_id": "cw1", "iou_to_gt": .4, "public_gt_structural_status": "valid"},
        {"canonical_annotation_id": "cw4", "iou_to_gt": .9, "public_gt_structural_status": "valid"},
    ])

    result = materialize_gt_cluster_alignment(crowd, loo, quality, tmp_path, input_status="formal")

    assert result["reference_policy"] == "use_existing_public_gt_as_is"
    assert result["conflict_candidates"] == 0
    assert result["reference_modified"] is False
