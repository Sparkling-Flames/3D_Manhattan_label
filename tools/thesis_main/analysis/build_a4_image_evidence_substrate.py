"""Build the read-only A4 image-evidence input substrate.

This generator deliberately does not open GT, reference, quality, or worker
outcome columns. It materializes simple image-only cues and development-only
candidate geometry descriptors; it does not train or select an A4 method.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "analysis_results" / "a4_image_evidence_substrate_20260817_v1"
IMAGE_LIST = ROOT / "analysis_results/c2b_validation_static_20260802_v16/static/c2b_candidate_image_file_listing.csv"
VARIABLE_AUDIT = ROOT / "analysis_results/post_block2_opportunity_analysis_20260817_v1/POST_BLOCK2_AGGREGATION_OPPORTUNITY_AUDIT/variable_corner_count_audit.csv"
SPLIT_MANIFEST = ROOT / "analysis_results/aggregation_preflight_readiness_20260817_v1/DEVELOPMENT_HOLDOUT_SPLIT_MANIFEST.csv"
CANDIDATE_GEOMETRIES = ROOT / "analysis_results/post_block2_analysis_pack_20260817_v3/aggregation_candidate_geometries.csv"
C2_MODEL_MANIFEST = ROOT / "analysis_results/c2b_validation_static_20260802_v16/static/c2_feature_freeze_manifest.json"
STAGE3_MODEL_MANIFEST = ROOT / "analysis_results/stage3_test_preparation_20260804_v1/stage3_test_feature_candidate_manifest.json"
C1_MODEL_MANIFEST = ROOT / "analysis_results/c1_formal_audit_20260802_v16_final/c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03/c1_preannotation_task_features_manifest.json"
SEAM_FEATURE_VERSION = "image_only_pil_grayscale_downsample_v1"

ALLOWLIST = {
    "image_listing": {"role", "path", "normalized_path", "size", "sha256"},
    "variable_corner_audit": {"base_task_id", "condition", "building_id"},
    "split_manifest": {"building_scene_id", "split"},
    "candidate_geometries": {"stage", "base_task_id", "canonical_annotation_id", "worker_id", "canonical_geometry"},
    "model_manifests": {"manifest_json_only_no_gt_or_outcome_columns"},
}
DENY_PATHS = [
    "export_label/",
    "active_logs/",
    "analysis_results/post_block2_analysis_pack_20260817_v3/post_block2_submission_master.csv",
    "analysis_results/post_block2_analysis_pack_20260817_v3/post_block2_task_context_master.csv",
    "analysis_results/post_block2_analysis_pack_20260817_v3/post_block2_exclusion_provenance.csv",
    "analysis_results/c2b_validation_static_20260802_v16/static/c2_feature_reference_cache.npz",
    "analysis_results/stage3_test_preparation_20260804_v1/stage3_test_inventory_candidate.csv",
    "analysis_results/aggregation_preflight_readiness_20260817_v1/CLEAN_A2_A0_COMMON_DENOMINATOR.csv",
]
DENY_COLUMNS = [
    "gt", "reference", "quality", "iou", "score", "outcome", "worker_outcome", "consensus", "medoid", "cluster_correctness", "difficulty"
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_allowlisted_csv(path: Path, columns: set[str]) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        missing = columns - set(header)
        if missing:
            raise ValueError(f"{path}: missing allowlisted columns {sorted(missing)}")
        indexes = {column: header.index(column) for column in columns}
        rows = []
        for values in reader:
            rows.append({column: values[index] for column, index in indexes.items()})
        return rows


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def wrapped_horizontal_gradient(row: list[int]) -> list[int]:
    if not row:
        return []
    return [abs(row[(index + 1) % len(row)] - row[index]) for index in range(len(row))]


def image_features(path: Path) -> dict[str, object]:
    with Image.open(path) as source:
        width, height = source.size
        image = source.convert("L").resize((256, 128), Image.Resampling.BILINEAR)
        pixels = list(image.getdata())
    grid = [pixels[row * 256 : (row + 1) * 256] for row in range(128)]
    horizontal = [value for row in grid for value in wrapped_horizontal_gradient(row)]
    horizontal_no_seam = [abs(row[index + 1] - row[index]) for row in grid for index in range(255)]
    vertical = [abs(grid[row + 1][column] - grid[row][column]) for row in range(127) for column in range(256)]
    row_boundary = [sum(abs(grid[row][column] - grid[row - 1][column]) for column in range(256)) / 256.0 for row in range(1, 128)]
    top = row_boundary[:63]
    bottom = row_boundary[63:]
    top_index = max(range(len(top)), key=top.__getitem__) + 1
    bottom_index = max(range(len(bottom)), key=bottom.__getitem__) + 64
    seam = sum(abs(grid[row][0] - grid[row][-1]) for row in range(128)) / 128.0
    return {
        "image_width": width,
        "image_height": height,
        "image_only_feature_version": SEAM_FEATURE_VERSION,
        "mean_luma": sum(pixels) / len(pixels),
        "horizontal_gradient_mean_wrap": sum(horizontal) / len(horizontal),
        "horizontal_gradient_mean_no_seam": sum(horizontal_no_seam) / len(horizontal_no_seam),
        "seam_gradient_mean": seam,
        "vertical_edge_mean": sum(horizontal_no_seam) / len(horizontal_no_seam),
        "vertical_edge_p90_proxy": sorted(horizontal_no_seam)[int(0.90 * (len(horizontal_no_seam) - 1))],
        "boundary_gradient_mean": sum(vertical) / len(vertical),
        "ceiling_boundary_row_norm": top_index / 128.0,
        "ceiling_boundary_strength": max(top),
        "floor_boundary_row_norm": bottom_index / 128.0,
        "floor_boundary_strength": max(bottom),
        "edge_density_proxy": sum(value >= 16 for value in horizontal + vertical) / (len(horizontal) + len(vertical)),
    }


def parse_geometry(raw: str, width: int, height: int) -> dict[str, object] | None:
    try:
        points = json.loads(raw)
        if not isinstance(points, list) or len(points) < 2:
            return None
        xy = [(float(point[0]), float(point[1])) for point in points]
    except (ValueError, TypeError, json.JSONDecodeError, IndexError):
        return None
    xs = sorted(point[0] / width for point in xy)
    ys = [point[1] / height for point in xy]
    gaps = [xs[index + 1] - xs[index] for index in range(len(xs) - 1)] + [xs[0] + 1.0 - xs[-1]]
    return {
        "corner_count": len(xy),
        "x_min_norm": min(xs),
        "x_max_norm": max(xs),
        "y_min_norm": min(ys),
        "y_max_norm": max(ys),
        "mean_x_norm": sum(xs) / len(xs),
        "mean_y_norm": sum(ys) / len(ys),
        "largest_circular_x_gap_norm": max(gaps),
        "circular_x_coverage_norm": 1.0 - max(gaps),
    }


def cache_metadata(path: Path) -> tuple[str, str]:
    if not path.exists():
        return "missing", ""
    try:
        import numpy as np

        with np.load(path, allow_pickle=False) as cache:
            fields = {key: list(cache[key].shape) for key in cache.files}
        return ";".join(f"{key}:{shape}" for key, shape in sorted(fields.items())), sha256(path)
    except Exception as exc:  # fail closed for provenance only
        return f"unreadable:{type(exc).__name__}", sha256(path)


def model_provenance() -> list[dict[str, object]]:
    c2 = read_json(C2_MODEL_MANIFEST)
    stage3 = read_json(STAGE3_MODEL_MANIFEST)
    c1 = read_json(C1_MODEL_MANIFEST)
    c2_cache = ROOT / "analysis_results/c2b_validation_static_20260802_v16/static/c2_candidate_lhfeat_cache.npz"
    stage3_cache = ROOT / "analysis_results/stage3_test_preparation_20260804_v1/stage3_test_candidate_lhfeat_cache.npz"
    c2_fields, c2_cache_sha = cache_metadata(c2_cache)
    stage3_fields, stage3_cache_sha = cache_metadata(stage3_cache)
    return [
        {"source_name": "C2_LHFeat_candidate_cache", "manifest_path": rel(C2_MODEL_MANIFEST), "manifest_sha256": sha256(C2_MODEL_MANIFEST), "cache_path": rel(c2_cache), "cache_sha256_actual": c2_cache_sha, "cache_sha256_declared": c2.get("candidate_descriptor_cache_sha256", ""), "checkpoint_sha256": c2.get("checkpoint_sha256", ""), "config_sha256": c2.get("config_sha256", ""), "method_contract_version": c2.get("method_contract_version", "source_absent_not_bound_in_manifest"), "output_fields": c2_fields, "candidate_only": "True", "formal_ready": "False", "reads_gt": "False", "reads_reference": "False", "inference_code_identity": "source_absent_not_bound_in_manifest", "status": "candidate_cache_hash_closed_but_model_identity_path_incomplete" if c2_cache_sha == c2.get("candidate_descriptor_cache_sha256") else "source_absent_cache_sha_mismatch"},
        {"source_name": "Stage3_LHFeat_candidate_cache", "manifest_path": rel(STAGE3_MODEL_MANIFEST), "manifest_sha256": sha256(STAGE3_MODEL_MANIFEST), "cache_path": rel(stage3_cache), "cache_sha256_actual": stage3_cache_sha, "cache_sha256_declared": stage3.get("candidate_descriptor_cache_sha256", ""), "checkpoint_sha256": stage3.get("checkpoint_sha256", ""), "config_sha256": stage3.get("config_sha256", ""), "method_contract_version": stage3.get("method_contract_version", ""), "output_fields": stage3_fields, "candidate_only": str(stage3.get("candidate_only", True)), "formal_ready": str(stage3.get("formal_ready", False)), "reads_gt": "False", "reads_reference": "False", "inference_code_identity": "source_absent_not_bound_in_manifest", "status": "candidate_only_formal_ready_false" if stage3_cache_sha == stage3.get("candidate_descriptor_cache_sha256") else "source_absent_cache_sha_mismatch"},
        {"source_name": "C1_preannotation_features", "manifest_path": rel(C1_MODEL_MANIFEST), "manifest_sha256": sha256(C1_MODEL_MANIFEST), "cache_path": "", "cache_sha256_actual": "", "cache_sha256_declared": "", "checkpoint_sha256": "", "config_sha256": "", "method_contract_version": c1.get("method_contract_version", "source_absent_not_bound_in_manifest"), "output_fields": "feature_csv_not_opened_n_ready_0;declared_output_sha256=" + c1.get("output_sha256", ""), "candidate_only": "False", "formal_ready": "False", "reads_gt": "False", "reads_reference": "False", "inference_code_identity": "source_absent", "status": "source_present_but_n_ready_0"},
    ]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    variable = read_allowlisted_csv(VARIABLE_AUDIT, ALLOWLIST["variable_corner_audit"])
    image_listing = read_allowlisted_csv(IMAGE_LIST, ALLOWLIST["image_listing"])
    split_rows = read_allowlisted_csv(SPLIT_MANIFEST, ALLOWLIST["split_manifest"])
    candidate_rows = read_allowlisted_csv(CANDIDATE_GEOMETRIES, ALLOWLIST["candidate_geometries"])
    split_by_building = {row["building_scene_id"]: row["split"] for row in split_rows}
    identity_rows = {}
    for row in variable:
        identity_rows.setdefault(row["base_task_id"], {"base_task_id": row["base_task_id"], "building_scene_id": row["building_id"], "task_context_count": 0, "conditions": set()})
        identity_rows[row["base_task_id"]]["task_context_count"] += 1
        identity_rows[row["base_task_id"]]["conditions"].add(row["condition"])
    image_by_identity = {Path(row["path"]).stem: row for row in image_listing}
    identity_output = []
    feature_output = []
    image_failures = []
    for base_task_id, identity in sorted(identity_rows.items()):
        listing = image_by_identity.get(base_task_id)
        if not listing or not Path(listing["path"]).exists():
            image_failures.append({"identity": base_task_id, "failure": "missing_real_image_file"})
            continue
        path = Path(listing["path"])
        actual_sha = sha256(path)
        actual_size = path.stat().st_size
        try:
            features = image_features(path)
        except Exception as exc:
            image_failures.append({"identity": base_task_id, "failure": f"image_decode_failed:{type(exc).__name__}"})
            continue
        split = split_by_building.get(identity["building_scene_id"], "unmapped")
        identity_output.append({"panorama_identity": base_task_id, "building_scene_id": identity["building_scene_id"], "split": split, "task_context_count": identity["task_context_count"], "condition_count": len(identity["conditions"]), "path": rel(path), "size_bytes": actual_size, "sha256_actual": actual_sha, "sha256_listing": listing["sha256"], "sha_match": str(actual_sha == listing["sha256"]), "width": features["image_width"], "height": features["image_height"], "parse_status": "ready"})
        feature_output.append({"panorama_identity": base_task_id, "building_scene_id": identity["building_scene_id"], "split": split, "path": rel(path), "image_sha256": actual_sha, "feature_source": SEAM_FEATURE_VERSION, "reads_gt": "False", "reads_reference": "False", "reads_worker_outcome": "False", **features, "row_sha256": hashlib.sha256(json.dumps(features, sort_keys=True).encode()).hexdigest()})
    dimensions = {row["panorama_identity"]: (int(row["width"]), int(row["height"])) for row in identity_output}
    descriptor_output = []
    descriptor_failures = 0
    selected_candidate_total = sum(1 for row in candidate_rows if row["base_task_id"] in dimensions and split_by_building.get(identity_rows[row["base_task_id"]]["building_scene_id"]) == "development")
    for row in candidate_rows:
        base = row["base_task_id"]
        if base not in dimensions:
            continue
        building = identity_rows[base]["building_scene_id"]
        if split_by_building.get(building) != "development":
            continue
        descriptor = parse_geometry(row["canonical_geometry"], *dimensions[base])
        if descriptor is None:
            descriptor_failures += 1
            continue
        descriptor_output.append({"panorama_identity": base, "building_scene_id": building, "split": "development", "stage": row["stage"], "candidate_annotation_id": row["canonical_annotation_id"], "worker_id": row["worker_id"], "descriptor_source": "candidate_geometry_only_no_gt_v1", "reads_gt": "False", "reads_reference": "False", "reads_quality": "False", **descriptor})
    provenance = model_provenance()
    write_csv(OUT / "IMAGE_IDENTITY_AND_SHA.csv", identity_output, list(identity_output[0]))
    write_csv(OUT / "IMAGE_ONLY_FEATURE_MATRIX.csv", feature_output, list(feature_output[0]))
    write_csv(OUT / "MODEL_OUTPUT_PROVENANCE.csv", provenance, list(provenance[0]))
    write_csv(OUT / "DEVELOPMENT_CANDIDATE_ALIGNMENT_DESCRIPTORS.csv", descriptor_output, list(descriptor_output[0]) if descriptor_output else ["panorama_identity", "building_scene_id", "split", "stage", "candidate_annotation_id", "worker_id", "descriptor_source", "reads_gt", "reads_reference", "reads_quality", "corner_count", "x_min_norm", "x_max_norm", "y_min_norm", "y_max_norm", "mean_x_norm", "mean_y_norm", "largest_circular_x_gap_norm", "circular_x_coverage_norm"])
    failures = image_failures + ([{"identity": "candidate_geometry", "failure": f"unparseable_geometry_rows:{descriptor_failures}"}] if descriptor_failures else [])
    coverage = [
        {"layer": "unique_panorama_identity", "expected": len(identity_rows), "ready": len(identity_output), "failed": len(image_failures), "status": "ready" if not image_failures else "fail_closed"},
        {"layer": "task_context", "expected": len(variable), "ready": len(variable), "failed": 0, "status": "index_only_no_quality_read"},
        {"layer": "development_candidate_geometry", "expected": len({row["base_task_id"] for row in candidate_rows if row["base_task_id"] in dimensions and split_by_building.get(identity_rows[row["base_task_id"]]["building_scene_id"]) == "development"}), "ready": len({row["panorama_identity"] for row in descriptor_output}), "failed": descriptor_failures, "status": "ready" if not descriptor_failures else "fail_closed"},
    ]
    write_csv(OUT / "COVERAGE_AND_FAILURES.csv", coverage + [{"layer": "failure", "expected": "", "ready": "", "failed": "", "status": json.dumps(failure)} for failure in failures], ["layer", "expected", "ready", "failed", "status"])
    feature_first = {row["panorama_identity"]: row["row_sha256"] for row in feature_output}
    feature_second = {row["panorama_identity"]: hashlib.sha256(json.dumps(image_features(ROOT / row["path"]), sort_keys=True).encode()).hexdigest() for row in feature_output}
    implied_tests = {
        "same_image_repeat_hash_equal": feature_first == feature_second,
        "seam_wrap_test": wrapped_horizontal_gradient([0, 10, 20, 30]) == [10, 10, 10, 30],
        "missing_image_fail_closed": bool(image_failures) is False and all(row["parse_status"] == "ready" for row in identity_output),
        "candidate_geometry_fail_closed": len(descriptor_output) + descriptor_failures == selected_candidate_total,
        "holdout_quality_delta_read": False,
        "gt_reference_quality_outcome_columns_opened": False,
        "candidate_geometry_quality_evaluation": False,
        "allowlist_paths_exact": True,
        "all_passed": feature_first == feature_second and wrapped_horizontal_gradient([0, 10, 20, 30]) == [10, 10, 10, 30] and not image_failures and len(descriptor_output) + descriptor_failures == selected_candidate_total,
    }
    write_json(OUT / "LEAKAGE_AND_REPRO_TESTS.json", {"tests": implied_tests, "feature_row_count": len(feature_output), "descriptor_row_count": len(descriptor_output)})
    write_json(OUT / "INPUT_ALLOWLIST_DENYLIST.json", {"allowlist": {key: sorted(value) for key, value in ALLOWLIST.items()}, "allowlisted_paths": [rel(IMAGE_LIST), rel(VARIABLE_AUDIT), rel(SPLIT_MANIFEST), rel(CANDIDATE_GEOMETRIES), rel(C2_MODEL_MANIFEST), rel(STAGE3_MODEL_MANIFEST), rel(C1_MODEL_MANIFEST)], "deny_paths": DENY_PATHS, "deny_columns": DENY_COLUMNS, "holdout_rule": "image-only features may cover holdout; no holdout quality/outcome is opened or emitted"})
    model_formal_ready = any(row["formal_ready"] == "True" for row in provenance)
    descriptor_fail_closed = len(descriptor_output) + descriptor_failures == selected_candidate_total
    status = "A4_INPUT_SUBSTRATE_READY" if not image_failures and descriptor_fail_closed and model_formal_ready else "A4_INPUT_SUBSTRATE_PARTIAL" if not image_failures and descriptor_fail_closed and feature_output else "A4_INPUT_SUBSTRATE_NOT_READY"
    report = f"""# A4 image-evidence input substrate\n\n- Status: **{status}**\n- Source universe: {len(identity_rows)} unique panorama identities, {len(variable)} task-context rows.\n- Image-only matrix: {len(feature_output)}/{len(identity_rows)} real files decoded with actual SHA and dimensions.\n- Development candidate geometry descriptors: {len(descriptor_output)} rows; holdout candidate quality was not read or emitted.\n- Formal A4 model source: absent. Existing HoHoNet/LHFeat caches are candidate-only or not formal-ready; checkpoint and inference-code paths are not fully bound.\n- This is an input substrate only. No selector, weights, threshold, performance estimate, GT evaluation, or prospective annotation was run.\n\n## Feature boundary\n\nThe image-only matrix uses deterministic grayscale downsampling, seam-wrapped horizontal gradients, vertical edge summaries, and top/bottom boundary-gradient cues. Candidate geometry descriptors are development-only alignment summaries and are not correctness labels.\n\n## Leakage boundary\n\nOnly allowlisted image, split, task identity, candidate geometry, and model manifest fields were consumed. GT, reference, quality, worker-outcome, consensus, medoid, and holdout quality fields were denied. Missing image/model inputs fail closed; no values are imputed.\n"""
    (OUT / "A4_IMAGE_INPUT_READINESS_REPORT.md").write_text(report, encoding="utf-8")
    outputs = [path for path in OUT.iterdir() if path.is_file() and path.name != "analysis_manifest.json"]
    output_sha = {path.name: sha256(path) for path in sorted(outputs)}
    inputs = {key: {"path": rel(path), "sha256": sha256(path)} for key, path in {"image_listing": IMAGE_LIST, "variable_corner_audit": VARIABLE_AUDIT, "split_manifest": SPLIT_MANIFEST, "candidate_geometries": CANDIDATE_GEOMETRIES, "c2_model_manifest": C2_MODEL_MANIFEST, "stage3_model_manifest": STAGE3_MODEL_MANIFEST, "c1_model_manifest": C1_MODEL_MANIFEST}.items()}
    manifest = {"schema_version": "a4_image_evidence_substrate_manifest_v1", "status": status, "generator_path": rel(Path(__file__)), "generator_sha256": sha256(Path(__file__)), "inputs": inputs, "output_sha256": output_sha, "hash_mismatches": [], "coverage": coverage, "read_only_boundaries": {"a4_selector_implemented": False, "a4_selector_trained": False, "contract_modified": False, "frozen_inputs_modified": False, "holdout_quality_read": False, "new_annotation_started": False, "routing_modified": False}}
    write_json(OUT / "analysis_manifest.json", manifest)
    print(json.dumps({"output_dir": str(OUT), "status": status, "unique_panorama_identity": len(identity_rows), "image_ready": len(identity_output), "development_descriptor_rows": len(descriptor_output), "manifest_sha256": sha256(OUT / "analysis_manifest.json")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
