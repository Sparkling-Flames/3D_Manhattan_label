import csv
import json

from pathlib import Path

from tools.thesis_main.analysis.geometry_consensus.materialize import materialize_geometry_consensus
from tools.thesis_main.analysis.geometry_consensus.loo import leave_one_out
from tools.thesis_main.analysis.geometry_consensus.representation import normalize_geometry
from tools.thesis_main.analysis.geometry_consensus.stability import _maximum_complete_link_clusters, stability_summary
from tools.thesis_main.analysis.quality_core.geometry_metrics import compute_layout_mask_iou_from_normalized_pairs


def _record(worker: str, offset: int = 0):
    corners = [[100, 100 + offset], [100, 400], [500, 100 + offset], [500, 400]]
    return {"task_id": "t1", "worker_id": worker, "annotation_id": f"a-{worker}", "canonical_annotation_id": f"c-{worker}", "geometry": normalize_geometry(corners)}


def test_loo_excludes_held_out_worker_and_scores_against_unique_peer_medoid() -> None:
    rows = leave_one_out([_record("w1"), _record("w2", 1), _record("w3", 3), _record("w4", 9)])
    assert all(row["peer_count_excluding_self"] == 3 for row in rows)
    assert all(row["valid_k"] == 4 for row in rows)
    assert all(row["q_LOO_tu"] is not None for row in rows)
    assert all(row["loo_consensus_annotation_id"] != row.get("canonical_annotation_id") for row in rows)
    assert all(len(row["loo_consensus_geometry_sha256"]) == 64 for row in rows)
    stability = stability_summary([_record("w1"), _record("w2", 1), _record("w3", 2)])
    assert stability["valid_k"] == 3
    assert stability["medoid_annotation_id"]
    assert len(stability["medoid_geometry_sha256"]) == 64


def test_loo_keeps_variable_count_peer_diagnostics_without_pointwise_correspondence() -> None:
    rows = leave_one_out([_record("w1"), _record("w2", 1), {"task_id": "t1", "worker_id": "w3", "geometry": normalize_geometry([[100, 100], [100, 400], [500, 100], [500, 400], [800, 100], [800, 400]])}])
    w1 = next(row for row in rows if row["worker_id"] == "w1")
    assert w1["peer_count_excluding_self"] == 2
    assert w1["validity_status"] == "not_evaluable"
    assert len(w1["loo_boundary_values_json"]) == 2
    assert len(w1["loo_wallwall_values_json"]) == 2


def test_complete_link_enumerates_true_maximum_and_exposes_ties() -> None:
    similarities = {
        (0, 1): .9, (0, 2): .9, (1, 2): .9,
        (0, 3): .9, (1, 3): .9, (2, 3): .1,
    }
    assert _maximum_complete_link_clusters((0, 1, 2, 3), similarities, .8) == [(0, 1, 2), (0, 1, 3)]


def test_normalized_pair_iou_does_not_repair_or_repair_pairs() -> None:
    left = normalize_geometry([[100, 400], [100, 100], [500, 100], [500, 400]])
    right = normalize_geometry([[100, 110], [100, 390], [500, 110], [500, 390]])
    value, meta = compute_layout_mask_iou_from_normalized_pairs(left["pairs"], right["pairs"])
    assert value is not None
    assert meta["reason"] == ""


def test_overlapping_maximum_cliques_are_cluster_tie_not_multimodal(monkeypatch) -> None:
    records = [_record(f"w{i}", i) for i in range(4)]
    similarities = {
        frozenset((0, 1)): .9,
        frozenset((0, 2)): .9,
        frozenset((1, 2)): .9,
        frozenset((0, 3)): .9,
        frozenset((1, 3)): .9,
        frozenset((2, 3)): .1,
    }
    def fake(left, right, **_kwargs):
        score = similarities[frozenset((round(left["top_y"][0] - 100), round(right["top_y"][0] - 100)))]
        return {"boundary_similarity": score, "wallwall_similarity": score}
    monkeypatch.setattr("tools.thesis_main.analysis.geometry_consensus.stability.pairwise_similarity", fake)
    summary = stability_summary(records)
    assert summary["consensus_status"] == "weak"


def test_geometry_materializer_emits_candidate_sidecars_with_common_fields(tmp_path: Path) -> None:
    geometry = tmp_path / "geometry.jsonl"
    geometry.write_text("\n".join(json.dumps({"task_id": "t1", "base_task_id": "b1", "worker_id": worker, "condition": "manual", "pool": "Calibration_core", "schema_version": "v4", "corners_px": [[100, 100 + offset], [100, 400], [500, 100 + offset], [500, 400]]}) for worker, offset in [("w1", 0), ("w2", 1), ("w3", 2)]) + "\n", encoding="utf-8")
    summary = materialize_geometry_consensus(geometry, tmp_path)
    assert summary["dry_run"] is True
    coverage = list(csv.DictReader((tmp_path / "geometry_metric_coverage_C1.csv").open(encoding="utf-8")))
    assert coverage[0]["pairwise_metric_coverage"] == "3/3"
    assert coverage[0]["interpretation_allowed"] == "false"
    loo = list(csv.DictReader((tmp_path / "geometry_worker_task_loo_C1.csv").open(encoding="utf-8")))
    assert all(row["loo_boundary_median"] for row in loo)
    assert all(row["loo_wallwall_median"] for row in loo)
