import csv
import json

from pathlib import Path

from tools.thesis_main.analysis.geometry_consensus.materialize import materialize_geometry_consensus
from tools.thesis_main.analysis.geometry_consensus.loo import leave_one_out
from tools.thesis_main.analysis.geometry_consensus.representation import normalize_geometry
from tools.thesis_main.analysis.geometry_consensus.stability import stability_summary


def _record(worker: str, offset: int = 0):
    corners = [[100, 100 + offset], [100, 400], [500, 100 + offset], [500, 400]]
    return {"task_id": "t1", "worker_id": worker, "geometry": normalize_geometry(corners)}


def test_loo_excludes_held_out_worker_and_requires_three_for_candidate() -> None:
    rows = leave_one_out([_record("w1"), _record("w2", 1), _record("w3", 2)])
    assert all(row["peer_count_excluding_self"] == 2 for row in rows)
    assert all(row["valid_k"] == 3 for row in rows)
    assert all(row["interpretation_allowed"] is False for row in rows)
    assert stability_summary([_record("w1"), _record("w2", 1), _record("w3", 2)])["valid_k"] == 3


def test_loo_does_not_count_incompatible_peers_as_valid_support() -> None:
    rows = leave_one_out([_record("w1"), _record("w2", 1), {"task_id": "t1", "worker_id": "w3", "geometry": normalize_geometry([[100, 100], [100, 400], [500, 100], [500, 400], [800, 100], [800, 400]])}])
    w1 = next(row for row in rows if row["worker_id"] == "w1")
    assert w1["peer_count_excluding_self"] == 1
    assert w1["validity_status"] == "not_evaluable"


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
