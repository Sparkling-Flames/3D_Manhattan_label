from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from tools.thesis_main.analysis import build_c2_assignment_manifest_from_c1_gaps as c2b
from tools.thesis_main.analysis.c1_c2_mainline import materialize_analysis_views, materialize_measurement_readiness
from tools.thesis_main.analysis.materialize_c1_preannotation_task_features import materialize as materialize_preannotation_features
from tools.thesis_main.analysis.materialize_c1_rehearsal_audits import materialize_row_analysis_eligibility


def _write(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


def test_row_eligibility_is_sidecar_only_and_upstream_sha_is_immutable(tmp_path: Path) -> None:
    canonical, versions, quality, loo, structural, reference, independence = [tmp_path / name for name in ("canonical.csv", "versions.csv", "quality.csv", "loo.csv", "structural.csv", "reference.csv", "independence.csv")]
    row = {"project_id": "p", "ls_runtime_task_id": "r", "task_id": "t", "base_task_id": "b", "condition": "manual", "worker_id": "w", "annotation_id": "a", "canonical_annotation_id": "c", "assigned_expected": "true", "outside_assignment_submission": "false", "duplicate_worker_task_submission": "false"}
    _write(canonical, [row]); _write(versions, [{"annotation_id": "a", "version_disposition": "selected_canonical"}])
    _write(quality, [{"canonical_annotation_id": "c", "quality_evaluable": "true", "worker_id": "w", "base_task_id": "b"}])
    _write(loo, [{"canonical_annotation_id": "c", "q_LOO_primary": ".9", "primary_loo_eligible": "true", "worker_id": "w", "base_task_id": "b"}])
    _write(structural, [{"canonical_annotation_id": "c", "structural_validation_status": "passed", "worker_id": "w", "base_task_id": "b"}])
    _write(reference, [{"project_id": "p", "ls_runtime_task_id": "r", "task_id": "t", "base_task_id": "b", "condition": "manual", "final_scope": "in_scope", "geometry_reference_ready": "true"}])
    _write(independence, [{"canonical_annotation_id": "c", "independence_status": "independent"}])
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in (canonical, quality, loo, structural)}
    materialize_row_analysis_eligibility(canonical, versions, quality, loo, structural, reference, tmp_path, independence_csv=independence)
    materialize_analysis_views(quality, loo, structural, tmp_path / "c1_row_analysis_eligibility.csv", tmp_path)
    assert before == {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in before}
    assert (tmp_path / "c1_gt_quality_analysis.csv").exists()


def test_measurement_freeze_requires_three_axes_but_not_active_time(tmp_path: Path) -> None:
    completion, quality, loo, structural = [tmp_path / name for name in ("completion.csv", "quality.csv", "loo.csv", "structural.csv")]
    _write(completion, [{"worker_id": "w", "completion_status": "completed"}])
    common = {"worker_id": "w", "base_task_id": "b", "building_id": "house"}
    _write(quality, [{**common, "global_analysis_eligible": "true"}])
    _write(loo, [{**common, "loo_analysis_eligible": "true"}])
    _write(structural, [{**common, "structural_opportunity_eligible": "true"}])
    result = materialize_measurement_readiness(completion, quality, loo, structural, tmp_path, canonical_closed=True, preannotation_feature_ready=True)
    assert result["C1_MEASUREMENT_FROZEN"] is True
    assert result["C2B_DESIGN_READY"] is True


def test_c2b_design_does_not_require_risk_route(tmp_path: Path) -> None:
    workers = tmp_path / "workers.csv"; tasks = tmp_path / "tasks.csv"; manifest = tmp_path / "design.json"; closeout = tmp_path / "closeout.json"
    _write(workers, [
        {"worker_id": "w1", "c2_candidate_eligible": "true", "risk_slope": "0.1", "risk_slope_se": "0.1", "risk_slope_support": "3", "Q_GT_task_adjusted": ".8", "missing_rate": "0", "F_struct": "0"},
        {"worker_id": "w2", "c2_candidate_eligible": "true", "risk_slope": "0.2", "risk_slope_se": "0.1", "risk_slope_support": "3", "Q_GT_task_adjusted": ".7", "missing_rate": "0", "F_struct": "0"},
    ])
    _write(tasks, [
        {"task_id": f"t{i}", "base_task_id": f"b{i}", "assignment_eligible": "true", "anchor_eligible": "true", "bridge_eligible": "true", "task_stratum": "ordinary" if i % 2 else "stress", "building_id": f"h{i % 2}", "risk_design_A": str(i / 10), "risk_route_status": "pending_c2b_confirmation"}
        for i in range(1, 5)
    ])
    closeout.write_text(json.dumps({"C1_MEASUREMENT_FROZEN": True, "C2B_DESIGN_READY": True}), encoding="utf-8")
    manifest.write_text(json.dumps({"manifest_version": "c2_design_v1", "input_sha256": {"worker_profile_csv": hashlib.sha256(workers.read_bytes()).hexdigest(), "task_pool_csv": hashlib.sha256(tasks.read_bytes()).hexdigest(), "c1_closeout_summary": hashlib.sha256(closeout.read_bytes()).hexdigest()}, "candidate_designs": [{"design_id": "d", "common_anchor_count": 1, "bridge_per_worker": 1, "unique_bridge_tasks": 2, "min_task_support": 1, "max_worker_stratum_imbalance": 2}], "c2b_target_ci_half_width": 10, "simulation": {"seed": 1, "draws": 200}}), encoding="utf-8")
    result = c2b.materialize(tasks, workers, manifest, tmp_path / "out", input_status="formal", c1_closeout_summary=closeout)
    assert result["launch_ready"] is True
    assert (tmp_path / "out" / "assignment_manifest_C2B.csv").exists()


def test_preannotation_feature_requires_frozen_model_identity(tmp_path: Path) -> None:
    assignments, inventory, features = tmp_path / "assignments.csv", tmp_path / "inventory.csv", tmp_path / "features.csv"
    _write(assignments, [{"base_task_id": "b1"}]); _write(inventory, [{"base_task_id": "b1", "image_id": "i1", "building_id": "h1"}])
    _write(features, [{"base_task_id": "b1", "d_model_feat": "1", "d_model_feat_local": "2", "g_pair_count": "4", "g_topology_invalid": "false", "g_duplicate_peak": "false", "g_seam_instability": "0", "g_postprocess_invalid": "false"}])
    summary = materialize_preannotation_features([assignments], inventory, tmp_path, frozen_feature_csv=features)
    assert summary["n_ready"] == 0
