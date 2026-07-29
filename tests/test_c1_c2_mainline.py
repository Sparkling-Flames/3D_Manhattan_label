from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from tools.thesis_main.analysis.c1_c2_mainline import materialize_analysis_views, materialize_measurement_readiness
from tools.thesis_main.analysis.materialize_c1_preannotation_task_features import extract_frozen_model_features, materialize as materialize_preannotation_features
from tools.thesis_main.analysis.materialize_c1_rehearsal_audits import materialize_row_analysis_eligibility


def _write(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


def test_row_eligibility_is_sidecar_only_and_upstream_sha_is_immutable(tmp_path: Path) -> None:
    canonical, versions, quality, loo, structural, reference, independence = [tmp_path / name for name in ("canonical.csv", "versions.csv", "quality.csv", "loo.csv", "structural.csv", "reference.csv", "independence.csv")]
    row = {"project_id": "p", "ls_runtime_task_id": "r", "task_id": "t", "base_task_id": "b", "condition": "manual", "worker_id": "w", "annotation_id": "a", "canonical_annotation_id": "c", "assignment_provenance": "original_assignment", "assigned_expected": "true", "outside_assignment_submission": "false", "duplicate_worker_task_submission": "false"}
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


def test_measurement_bundle_closes_without_requiring_every_estimand_for_c2b(tmp_path: Path) -> None:
    completion, quality, loo, structural = [tmp_path / name for name in ("completion.csv", "quality.csv", "loo.csv", "structural.csv")]
    _write(completion, [{"worker_id": "w", "completion_status": "completed"}])
    _write(quality, [{"worker_id": "w", "base_task_id": "b", "global_analysis_eligible": "true"}])
    _write(loo, [{"worker_id": "w", "base_task_id": "b", "loo_analysis_eligible": "false"}])
    _write(structural, [{"worker_id": "w", "base_task_id": "b", "structural_opportunity_eligible": "false"}])
    result = materialize_measurement_readiness(completion, quality, loo, structural, tmp_path, canonical_closed=True, collection_window_closed=True)
    assert result["estimand_freeze"] == {"Q_GT": True, "R_LOO": False, "F_struct": False}
    assert result["estimand_status"] == {"Q_GT": "frozen", "R_LOO": "support_limited", "F_struct": "support_limited"}
    assert result["C1_EVIDENCE_BUNDLE_FROZEN"] is True
    assert result["C2B_BASELINE_INPUT_FROZEN"] is True
    assert result["C1_MEASUREMENT_FROZEN"] is True


def test_preannotation_feature_requires_frozen_model_identity(tmp_path: Path) -> None:
    assignments, inventory, features = tmp_path / "assignments.csv", tmp_path / "inventory.csv", tmp_path / "features.csv"
    _write(assignments, [{"base_task_id": "b1"}]); _write(inventory, [{"base_task_id": "b1", "image_id": "i1", "building_id": "h1"}])
    _write(features, [{"base_task_id": "b1", "d_model_feat": "1", "d_model_feat_local": "2", "g_pair_count": "4", "g_topology_invalid": "false", "g_duplicate_peak": "false", "g_seam_instability": "0", "g_postprocess_invalid": "false"}])
    summary = materialize_preannotation_features([assignments], inventory, tmp_path, frozen_feature_csv=features)
    assert summary["n_ready"] == 0


def test_preannotation_feature_producer_requires_authoritative_building_and_base_layout(tmp_path: Path, monkeypatch) -> None:
    import numpy as np
    assignments, inventory, buildings = tmp_path / "assignments.csv", tmp_path / "inventory.csv", tmp_path / "buildings.csv"
    image = tmp_path / "scene.jpg"; image.write_bytes(b"image")
    _write(assignments, [{"base_task_id": "scene", "task_id": "582"}])
    _write(inventory, [{"base_task_id": "scene", "task_id": "582", "image_id": "i1", "source_path": str(image)}])
    _write(buildings, [{"image_id": "i1", "base_task_id": "scene", "building_id": "house", "registry_status": "approved", "reviewed_by": "expert", "reviewed_at": "2026-07-25"}])
    layouts = tmp_path / "layouts"; layouts.mkdir()
    (layouts / "scene.json").write_text(json.dumps({"layout": {"corners": [
        {"x": 10, "y_ceiling": 100, "y_floor": 400}, {"x": 300, "y_ceiling": 100, "y_floor": 400},
        {"x": 600, "y_ceiling": 100, "y_floor": 400}, {"x": 900, "y_ceiling": 100, "y_floor": 400},
    ]}}), encoding="utf-8")
    checkpoint = tmp_path / "model.pth"; checkpoint.write_bytes(b"model")
    config = tmp_path / "config.yaml"; config.write_text("model: fixed\n", encoding="utf-8")
    cache = tmp_path / "cache.npz"
    np.savez(cache, global_mean=np.zeros(1), global_components=np.eye(1), global_scale=np.ones(1), local_mean=np.zeros(1), local_components=np.eye(1), local_scale=np.ones(1), reference_global=np.asarray([[0.], [2.]]), reference_local=np.asarray([[0.], [2.]]))
    candidate_cache = tmp_path / "candidate.npz"
    np.savez(candidate_cache, paths=np.asarray([image.resolve().as_posix()]), global_descriptors=np.asarray([[1.]]), local_descriptors=np.asarray([[1.]]))
    circular = tmp_path / "circular.json"; circular.write_text(json.dumps({"audit_basis": "off_grid_rotation_reinference", "four_phase_permutation_role": "diagnostic_only"}), encoding="utf-8")
    seam = tmp_path / "seam.json"; seam.write_text(json.dumps({"audit_basis": "small_seam_offset_sensitivity"}), encoding="utf-8")
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    leakage = tmp_path / "c2b_reference_candidate_leakage_audit.summary.json"
    leakage.write_text(json.dumps({"status": "passed", "formal_feature_pool_allowed": True}), encoding="utf-8")
    feature_manifest = tmp_path / "feature.json"
    feature_manifest.write_text(json.dumps({
        "schema_version": "paper_a_c2_feature_freeze_v2", "feature_audit_status": "approved", "feature_cache_path": str(cache), "candidate_descriptor_cache_path": str(candidate_cache), "candidate_descriptor_cache_sha256": sha(candidate_cache), "circular_audit_path": str(circular), "seam_audit_path": str(seam), "checkpoint_sha256": sha(checkpoint), "config_sha256": sha(config), "reference_feature_sha256": sha(cache), "reference_image_count": 2,
        "pca_frozen": True, "whitening_frozen": True, "circular_shift_invariant": True, "off_grid_circular_robustness": True, "seam_invariant": True,
        "pca_frozen_sha256": sha(cache), "whitening_frozen_sha256": sha(cache), "circular_shift_invariant_sha256": sha(circular), "seam_invariant_sha256": sha(seam),
        "pca_sha256": sha(cache), "whitening_sha256": sha(cache), "circular_shift_audit_sha256": sha(circular), "seam_audit_sha256": sha(seam),
        "reference_candidate_leakage_audit_sha256": sha(leakage),
    }), encoding="utf-8")
    output = tmp_path / "features.csv"
    summary = extract_frozen_model_features([assignments], inventory, buildings, layouts, checkpoint, config, feature_manifest, output)
    row = next(csv.DictReader(output.open(encoding="utf-8")))
    assert summary["n_ready"] == 1
    assert row["building_id"] == "house"
    assert row["layout_output_sha256"] == sha(layouts / "scene.json")
    assert row["preannotation_feature_ready"].lower() == "true"
