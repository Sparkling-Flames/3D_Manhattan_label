import csv
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from tools.thesis_main.analysis.materialize_c2_task_risk import _apply_whitener, _composite_q75_bucket, _feature_audit_passes, _feature_freeze_ready, _fit_whitener, _layout_features, _pool_lhfeat, materialize, refresh_feature_freeze_approval
from tools.thesis_main.registry.hohonet_feature_backend import aggregate_orbit


def test_full_checkpoint_constructor_disables_all_pretrained_download_paths(monkeypatch) -> None:
    pytest.importorskip("torch")
    from lib.model.backbone import resnet as backbone_module

    calls = {}
    encoder = SimpleNamespace(
        conv1="conv", inplanes=64, layer1="l1", layer2="l2", layer3="l3", layer4="l4",
        fc="fc", avgpool="avgpool", state_dict=lambda: {}, load_state_dict=lambda _state: None,
    )
    monkeypatch.setattr(backbone_module.models, "resnet34", lambda *, weights: calls.setdefault("backbone_weights", weights) or encoder)
    monkeypatch.setattr(
        backbone_module.models.segmentation, "offline_coco",
        lambda *, pretrained: calls.setdefault("coco_pretrained", pretrained) or SimpleNamespace(backbone=encoder),
        raising=False,
    )

    backbone_module.Resnet(backbone="resnet34", coco="offline_coco", pretrained=False)

    assert calls == {"backbone_weights": None, "coco_pretrained": False}


def test_feature_freeze_cli_is_directly_runnable() -> None:
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(root / "tools/thesis_main/analysis/freeze_c2_feature_reference.py"), "--help"],
        cwd=root, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr


def test_composite_q75_uses_frozen_c1_channel_percentiles() -> None:
    refs = {name: [0.0, 1.0, 2.0, 3.0] for name in ("d_model_feat", "d_model_feat_local_max", "g_model_struct", "d_cal_A")}
    bucket, percentiles = _composite_q75_bucket({name: 3.0 for name in refs}, refs)
    assert bucket == "stress"
    assert max(percentiles.values()) >= .75


def test_frozen_whitener_is_the_transform_consumed_by_candidates() -> None:
    matrix = np.asarray([[1., 2., 4.], [2., 1., 3.], [4., 3., 1.], [5., 6., 2.]])
    mean, components, scale, transformed = _fit_whitener(matrix)
    reapplied = np.stack([_apply_whitener(row, mean, components, scale) for row in matrix])
    assert np.allclose(reapplied, transformed)
    assert np.allclose(transformed.mean(axis=0), 0, atol=1e-12)


def test_degenerate_feature_reference_cannot_be_frozen() -> None:
    with pytest.raises(ValueError, match="degenerate"):
        _fit_whitener(np.ones((3, 4)))


def test_lhfeat_pooling_is_circular_shift_invariant_on_real_feature_shape() -> None:
    feature = np.arange(12 * 64, dtype=float).reshape(12, 64)
    original = _pool_lhfeat(feature)
    shifted = _pool_lhfeat(np.roll(feature, 17, axis=1))
    assert all(np.allclose(left, right) for left, right in zip(original, shifted))


def test_four_phase_orbit_aggregation_is_order_invariant() -> None:
    values = [(np.asarray([float(i)]), np.asarray([float(i * 2)])) for i in range(4)]
    assert all(np.allclose(left, right) for left, right in zip(aggregate_orbit(values), aggregate_orbit(values[1:] + values[:1])))


def test_feature_freeze_requires_the_actual_bound_cache(tmp_path) -> None:
    checkpoint = tmp_path / "model.pth"; checkpoint.write_bytes(b"model")
    config = tmp_path / "config.yaml"; config.write_text("model: fixed\n", encoding="utf-8")
    cache = tmp_path / "features.npz"; np.savez(cache, reference_global=np.zeros((2, 1)))
    candidate_cache = tmp_path / "candidate.npz"; np.savez(candidate_cache, paths=np.asarray([]), global_descriptors=np.asarray([]), local_descriptors=np.asarray([]))
    import hashlib
    cache_sha = hashlib.sha256(cache.read_bytes()).hexdigest()
    circular = tmp_path / "circular.json"; circular.write_text(json.dumps({"audit_basis": "off_grid_rotation_reinference", "four_phase_permutation_role": "diagnostic_only"}), encoding="utf-8")
    seam = tmp_path / "seam.json"; seam.write_text(json.dumps({"audit_basis": "small_seam_offset_sensitivity"}), encoding="utf-8")
    circular_sha = hashlib.sha256(circular.read_bytes()).hexdigest(); seam_sha = hashlib.sha256(seam.read_bytes()).hexdigest()
    leakage = tmp_path / "c2b_reference_candidate_leakage_audit.summary.json"
    leakage.write_text(json.dumps({"status": "passed", "formal_feature_pool_allowed": True}), encoding="utf-8")
    manifest = tmp_path / "freeze.json"
    manifest.write_text(json.dumps({
        "schema_version": "paper_a_c2_feature_freeze_v2", "feature_audit_status": "approved",
        "feature_cache_path": str(cache), "candidate_descriptor_cache_path": str(candidate_cache), "candidate_descriptor_cache_sha256": hashlib.sha256(candidate_cache.read_bytes()).hexdigest(), "circular_audit_path": str(circular), "seam_audit_path": str(seam),
        "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        "config_sha256": hashlib.sha256(config.read_bytes()).hexdigest(), "reference_feature_sha256": cache_sha,
        "reference_image_count": 2,
        "pca_frozen": True, "whitening_frozen": True, "circular_shift_invariant": True, "off_grid_circular_robustness": True, "seam_invariant": True,
        "pca_frozen_sha256": cache_sha, "whitening_frozen_sha256": cache_sha,
        "circular_shift_invariant_sha256": circular_sha, "seam_invariant_sha256": seam_sha,
        "pca_sha256": cache_sha, "whitening_sha256": cache_sha,
        "circular_shift_audit_sha256": circular_sha, "seam_audit_sha256": seam_sha,
        "reference_candidate_leakage_audit_sha256": hashlib.sha256(leakage.read_bytes()).hexdigest(),
    }), encoding="utf-8")
    assert _feature_freeze_ready(manifest, checkpoint=checkpoint, config=config)
    cache.write_bytes(b"tampered")
    assert not _feature_freeze_ready(manifest, checkpoint=checkpoint, config=config)


def test_frozen_feature_caches_can_refresh_approval_without_model_inference(tmp_path) -> None:
    import hashlib

    reference = tmp_path / "reference"; reference.mkdir()
    for name, content in (("a.jpg", b"a"), ("b.jpg", b"b")):
        (reference / name).write_bytes(content)
    checkpoint = tmp_path / "model.pth"; checkpoint.write_bytes(b"model")
    config = tmp_path / "config.yaml"; config.write_text("model: fixed\n", encoding="utf-8")
    inventory = tmp_path / "inventory.csv"; inventory.write_text("image_id,base_task_id\ni,t\n", encoding="utf-8")
    cache = tmp_path / "reference.npz"; cache.write_bytes(b"reference-cache")
    candidate = tmp_path / "candidate.npz"; candidate.write_bytes(b"candidate-cache")
    circular = tmp_path / "circular.json"; circular.write_text(json.dumps({"circular_relative_l2_max": 1e-8, "circular_audited_image_count": 32, "audit_basis": "off_grid_rotation_reinference", "four_phase_permutation_role": "diagnostic_only"}), encoding="utf-8")
    seam = tmp_path / "seam.json"; seam.write_text(json.dumps({"seam_relative_l2_q95": .02, "seam_audited_image_count": 32}), encoding="utf-8")
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    paths = sorted(reference.glob("*.jpg"))
    listing_sha = hashlib.sha256("\n".join(
        f"{path.resolve().as_posix()}|{path.stat().st_size}|{sha(path)}" for path in paths
    ).encode()).hexdigest()
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "schema_version": "paper_a_c2_feature_freeze_v2",
        "feature_cache_path": str(cache), "reference_feature_sha256": sha(cache),
        "candidate_descriptor_cache_path": str(candidate), "candidate_descriptor_cache_sha256": sha(candidate),
        "circular_audit_path": str(circular), "circular_shift_audit_sha256": sha(circular),
        "seam_audit_path": str(seam), "seam_audit_sha256": sha(seam),
        "checkpoint_sha256": sha(checkpoint), "config_sha256": sha(config),
        "candidate_inventory_sha256": sha(inventory), "reference_image_count": 2,
        "reference_listing_sha256": listing_sha,
    }), encoding="utf-8")
    thresholds = tmp_path / "thresholds.json"
    thresholds.write_text(json.dumps({
        "status": "approved", "formal_feature_freeze_allowed": True,
        "approved_by": "reviewer", "approved_at": "2026-07-26T00:00:00Z",
        "thresholds": {"circular_relative_l2_max": 1e-7, "seam_relative_l2_q95": .03, "minimum_circular_audited_image_count": 32, "minimum_seam_audited_image_count": 32},
    }), encoding="utf-8")
    refreshed = refresh_feature_freeze_approval(
        manifest, thresholds, checkpoint=checkpoint, config=config,
        reference_dir=reference, candidate_inventory=inventory,
    )
    assert refreshed["feature_audit_status"] == "approved"
    assert refreshed["cache_reused_without_model_inference"] is True


def test_feature_audit_fails_closed_on_zero_support_or_nonfinite_metrics() -> None:
    thresholds = {
        "status": "approved", "formal_feature_freeze_allowed": True,
        "approved_by": "reviewer", "approved_at": "2026-07-26T00:00:00Z",
        "thresholds": {
            "circular_relative_l2_max": .3, "seam_relative_l2_q95": .05,
            "minimum_circular_audited_image_count": 32, "minimum_seam_audited_image_count": 32,
        },
    }
    audit = {
        "circular_relative_l2_max": .2, "seam_relative_l2_q95": .04,
        "circular_audited_image_count": 0, "seam_audited_image_count": 32,
    }
    assert _feature_audit_passes(audit, audit, thresholds) == (False, True)
    audit["circular_audited_image_count"] = 32
    audit["seam_relative_l2_q95"] = "nan"
    assert _feature_audit_passes(audit, audit, thresholds) == (True, False)


def test_candidate_risk_uses_c1_only_and_layout_structure(tmp_path):
    inventory = tmp_path / "inventory.csv"
    with inventory.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["task_id", "source_path"]); writer.writeheader(); writer.writerow({"task_id": "t1", "source_path": "missing.jpg"})
    layouts = tmp_path / "layouts"; layouts.mkdir()
    (layouts / "t1.json").write_text(json.dumps({"layout": {"corners": [
        {"x": 10, "y_ceiling": 100, "y_floor": 400}, {"x": 300, "y_ceiling": 100, "y_floor": 400},
        {"x": 600, "y_ceiling": 100, "y_floor": 400}, {"x": 900, "y_ceiling": 100, "y_floor": 400},
    ]}}), encoding="utf-8")
    c1 = tmp_path / "c1.jsonl"
    c1.write_text(json.dumps({"corners_px": [[10, 100], [10, 400], [500, 100], [500, 400]]}) + "\n", encoding="utf-8")

    summary = materialize(inventory, layouts, c1, tmp_path / "out", input_status="precloseout_rehearsal")

    assert summary["n_tasks"] == 1
    assert summary["formal_ready"] is False
    row = next(csv.DictReader((tmp_path / "out" / "c2_task_risk_inventory.csv").open(encoding="utf-8")))
    assert row["g_model_struct"]
    assert not row["d_cal_A"]
    assert row["feature_status"] == "not_requested"
    assert row["assignment_eligible"].lower() == "false"


def test_layout_identity_uses_base_task_id_not_runtime_task_id(tmp_path):
    inventory = tmp_path / "inventory.csv"
    inventory.write_text("task_id,base_task_id,source_path\n582,scene_image,missing.jpg\n", encoding="utf-8")
    layouts = tmp_path / "layouts"; layouts.mkdir()
    (layouts / "scene_image.json").write_text(json.dumps({"layout": {"corners": [
        {"x": 10, "y_ceiling": 100, "y_floor": 400}, {"x": 300, "y_ceiling": 100, "y_floor": 400},
        {"x": 600, "y_ceiling": 100, "y_floor": 400}, {"x": 900, "y_ceiling": 100, "y_floor": 400},
    ]}}), encoding="utf-8")
    c1 = tmp_path / "c1.csv"; c1.write_text("base_task_id,preannotation_feature_ready\n", encoding="utf-8")
    materialize(inventory, layouts, c1, tmp_path / "out", input_status="precloseout_rehearsal")
    row = next(csv.DictReader((tmp_path / "out" / "c2_task_risk_inventory.csv").open(encoding="utf-8")))
    assert row["layout_status"] == "ready"


def test_layout_seam_stability_is_not_used_as_instability(tmp_path):
    layout = tmp_path / "layout.json"
    layout.write_text(json.dumps({"layout": {"corners": [
        {"x": 10, "y_ceiling": 100, "y_floor": 400}, {"x": 300, "y_ceiling": 100, "y_floor": 400},
        {"x": 600, "y_ceiling": 100, "y_floor": 400}, {"x": 900, "y_ceiling": 100, "y_floor": 400},
    ]}}), encoding="utf-8")
    result = _layout_features(layout)
    assert np.isclose(result["seam_stability"] + result["seam_instability"], 1.0)


def test_c1_risk_reference_has_one_row_per_base_task(tmp_path):
    inventory = tmp_path / "inventory.csv"
    inventory.write_text("task_id,source_path\nt1,missing.jpg\n", encoding="utf-8")
    layouts = tmp_path / "layouts"; layouts.mkdir()
    c1 = tmp_path / "c1_features.csv"
    c1.write_text("base_task_id,image_id,building_id,d_model_feat,d_model_feat_local,g_pair_count,g_topology_invalid,g_duplicate_peak,g_seam_instability,g_postprocess_invalid,checkpoint_sha256,inference_config_sha256,layout_output_sha256,preannotation_feature_ready\nb1,i1,h1,1,2,4,false,false,0,false," + "a" * 64 + "," + "b" * 64 + "," + "c" * 64 + ",true\n", encoding="utf-8")
    summary = materialize(inventory, layouts, c1, tmp_path / "out", input_status="precloseout_rehearsal")
    rows = list(csv.DictReader((tmp_path / "out" / "c1_task_risk_reference.csv").open(encoding="utf-8")))
    assert len(rows) == summary["n_c1_calibration_tasks"] == 1
    assert rows[0]["d_cal_A"] == "0.0"


def test_risk_assist_does_not_impersonate_risk_route(tmp_path):
    inventory = tmp_path / "inventory.csv"
    inventory.write_text("task_id,source_path\nt1,missing.jpg\n", encoding="utf-8")
    layouts = tmp_path / "layouts"; layouts.mkdir(); c1 = tmp_path / "c1_features.csv"; c1.write_text("base_task_id,preannotation_feature_ready\n", encoding="utf-8")
    materialize(inventory, layouts, c1, tmp_path / "out", input_status="precloseout_rehearsal")
    row = next(csv.DictReader((tmp_path / "out" / "c2_task_risk_inventory.csv").open(encoding="utf-8")))
    assert row["risk_route_candidate"] == ""
    assert row["risk_route_status"] == "pending_c2b_confirmation"


def test_precloseout_never_materializes_a_risk_design_stratum(tmp_path):
    inventory = tmp_path / "inventory.csv"
    inventory.write_text("task_id,building_id,source_path,source_split_allowed,history_clear,future_holdout_clear\nt1,b1,missing.jpg,true,true,true\n", encoding="utf-8")
    layouts = tmp_path / "layouts"; layouts.mkdir()
    (layouts / "t1.json").write_text(json.dumps({"layout": {"corners": [
        {"x": 10, "y_ceiling": 100, "y_floor": 400}, {"x": 300, "y_ceiling": 100, "y_floor": 400},
        {"x": 600, "y_ceiling": 100, "y_floor": 400}, {"x": 900, "y_ceiling": 100, "y_floor": 400},
    ]}}), encoding="utf-8")
    c1 = tmp_path / "c1_features.csv"
    c1.write_text("base_task_id,preannotation_feature_ready\n", encoding="utf-8")
    summary = materialize(inventory, layouts, c1, tmp_path / "out", input_status="precloseout_rehearsal")
    row = next(csv.DictReader((tmp_path / "out" / "c2_task_risk_inventory.csv").open(encoding="utf-8")))
    assert summary["risk_design_A_status"] == "pending_complete_C1"
    assert row["risk_design_stratum"] == ""
    assert row["risk_design_stratum_status"] == "provisional_not_frozen"
    assert row["assignment_eligible"].lower() == "false"
    assert row["building_id"] == ""
    assert row["building_registry_status"] == "missing_or_unapproved"
