import csv
import json

import pytest

from tools.thesis_main.analysis.materialize_main_inference import materialize
from tools.thesis_main.analysis.materialize_vfinal_main_analysis import analyze_t1_images
from tools.thesis_main.analysis.vfinal_artifact_utils import sha256_file


def _csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def _t1_rows():
    rows = []
    for pair, workers in (("p1", ("w1", "w2")), ("p2", ("w3", "w4"))):
        for condition, worker, quality, valid, active in (("manual", workers[0], .6, "true", 12), ("semi", workers[1], .8, "true", 8)):
            rows.append({"analysis_unit_pair_id": pair, "pair_analysis_disposition": "included", "source_pair_id": pair,
                         "image_id": "img", "worker_id": worker, "condition": condition, "risk_assist": "ordinary",
                         "delivery_adjusted_quality": quality, "structurally_valid": valid, "iou_to_gt": quality,
                         "active_time_seconds": active, "active_time_integrity_status": "exact_annotation_valid"})
    return rows


def test_t1_image_primary_requires_and_materializes_two_plus_two():
    images, audit = analyze_t1_images(_t1_rows())
    assert audit["n_primary_images"] == 1
    assert images[0]["n_unique_workers"] == 4
    assert images[0]["delivery_adjusted_quality_diff_semi_minus_manual"] == pytest.approx(.2)


def test_manifest_bound_t1_and_v1_inference(tmp_path):
    t1 = tmp_path / "t1.csv"
    t1_rows = []
    for index in range(8):
        risk = "ordinary" if index < 4 else "stress_assist"
        t1_rows.append({"image_id": f"i{index}", "building_id": f"b{index // 2}", "risk_assist": risk,
                        "delivery_adjusted_quality_diff_semi_minus_manual": .1 + .01 * index,
                        "structurally_valid_diff_semi_minus_manual": 0,
                        "owner_valid_active_time_diff_semi_minus_manual": -2,
                        "valid_only_iou_diff_semi_minus_manual": .05})
    _csv(t1, t1_rows)
    manifest = tmp_path / "analysis.json"
    manifest.write_text(json.dumps({"T1": {"confidence_level": .95, "bootstrap_replicates": 100, "bootstrap_seed": 7,
        "quality_noninferiority_margin": .05, "structural_noninferiority_margin": .05}}), encoding="utf-8")
    audit = materialize("T1", t1, manifest, tmp_path / "t1out", input_sha256=sha256_file(t1), manifest_sha256=sha256_file(manifest))
    assert audit["n_images"] == 8

    v1 = tmp_path / "v1.csv"
    v1_rows = []
    for arm in ("strong_global", "full_integrated"):
        for index in range(6):
            quality = .7 + (.05 if arm == "full_integrated" else 0)
            v1_rows.append({"task_id": f"{arm}-{index}", "policy_arm": arm, "itt_included": "true",
                            "analysis_disposition": "included", "policy_terminal_status": "resolved", "non_delivery": "false",
                            "policy_failure": "false", "delivery_adjusted_quality": quality, "iou_to_gt": quality,
                            "k_used": 2, "active_time_seconds": 10, "completion_time_seconds": 20})
    _csv(v1, v1_rows)
    manifest.write_text(json.dumps({"V1": {"confidence_level": .95, "bootstrap_replicates": 100, "bootstrap_seed": 9,
        "severe_failure_noninferiority_margin": .05, "non_delivery_noninferiority_margin": .05}}), encoding="utf-8")
    audit = materialize("V1", v1, manifest, tmp_path / "v1out", input_sha256=sha256_file(v1), manifest_sha256=sha256_file(manifest))
    assert audit["n_itt"] == 12
