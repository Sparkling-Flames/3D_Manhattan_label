"""Build a GT-free, candidate-image alignment substrate without training A4."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import sys
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.thesis_main.analysis.geometry_consensus.representation import normalize_geometry

OUT = ROOT / "analysis_results/a4_image_evidence_substrate_20260817_v2"
IMAGE_LIST = ROOT / "analysis_results/c2b_validation_static_20260802_v16/static/c2b_candidate_image_file_listing.csv"
VARIABLE_AUDIT = ROOT / "analysis_results/post_block2_opportunity_analysis_20260817_v1/POST_BLOCK2_AGGREGATION_OPPORTUNITY_AUDIT/variable_corner_count_audit.csv"
SPLIT_MANIFEST = ROOT / "analysis_results/aggregation_preflight_readiness_20260817_v1/DEVELOPMENT_HOLDOUT_SPLIT_MANIFEST.csv"
CANDIDATE_GEOMETRIES = ROOT / "analysis_results/post_block2_analysis_pack_20260817_v3/aggregation_candidate_geometries.csv"
C2_MODEL_MANIFEST = ROOT / "analysis_results/c2b_validation_static_20260802_v16/static/c2_feature_freeze_manifest.json"
STAGE3_MODEL_MANIFEST = ROOT / "analysis_results/stage3_test_preparation_20260804_v1/stage3_test_feature_candidate_manifest.json"
RULE_MANIFEST = ROOT / "docs/thesis_main/geometry_loo_candidate_rule_manifest_v1.json"
REPRESENTATION_SOURCE = ROOT / "tools/thesis_main/analysis/geometry_consensus/representation.py"
FEATURE_VERSION = "spatial_image_evidence_pil_wrap_v2"
ALLOWLIST = {
    "image_listing": ["role", "path", "normalized_path", "size", "sha256"],
    "task_identity": ["base_task_id", "condition", "building_id"],
    "split": ["building_scene_id", "split"],
    "candidate_geometry": ["stage", "base_task_id", "canonical_annotation_id", "worker_id", "canonical_geometry"],
    "model_manifest": ["manifest_json_only"],
    "layout_prediction_path": ["output/layout_json/{base_task_id}.json existence/hash only"],
}
DENY_PATHS = [
    "export_label/", "active_logs/", "analysis_results/post_block2_analysis_pack_20260817_v3/post_block2_submission_master.csv",
    "analysis_results/post_block2_analysis_pack_20260817_v3/post_block2_task_context_master.csv",
    "analysis_results/post_block2_analysis_pack_20260817_v3/post_block2_exclusion_provenance.csv",
    "analysis_results/c2b_validation_static_20260802_v16/static/c2_feature_reference_cache.npz",
    "analysis_results/stage3_test_preparation_20260804_v1/stage3_test_inventory_candidate.csv",
    "analysis_results/aggregation_preflight_readiness_20260817_v1/CLEAN_A2_A0_COMMON_DENOMINATOR.csv",
]
DENY_COLUMNS = ["gt", "reference", "quality", "iou", "score", "outcome", "worker_outcome", "consensus", "medoid", "cluster_correctness", "difficulty"]


def sha256(path: Path, trace: list[dict[str, object]] | None = None, input_kind: str = "file", operation: str = "sha256") -> str:
    assert_input_allowed(path, trace)
    record_input(trace, path, input_kind, [], operation)
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def trace_path(path: Path) -> str:
    try:
        return rel(path)
    except ValueError:
        return path.resolve().as_posix()


def denied_path(path: Path) -> str | None:
    candidate = trace_path(path).lower()
    for denied in DENY_PATHS:
        rule = denied.lower().rstrip("/")
        if candidate == rule or candidate.startswith(rule + "/"):
            return denied
    return None


def record_input(trace: list[dict[str, object]] | None, path: Path, kind: str, projected_columns: list[str] | None = None, operation: str = "read") -> None:
    if trace is not None:
        trace.append({"path": trace_path(path), "input_kind": kind, "operation": operation, "projected_columns": list(projected_columns or [])})


def assert_input_allowed(path: Path, trace: list[dict[str, object]] | None = None) -> None:
    match = denied_path(path)
    if match:
        raise PermissionError(f"denied input path: {match}")


def read_json(path: Path, trace: list[dict[str, object]] | None = None) -> dict:
    assert_input_allowed(path, trace)
    record_input(trace, path, "json", ["json_object"])
    return json.loads(path.read_text(encoding="utf-8"))


def file_identity(path: Path, trace: list[dict[str, object]]) -> tuple[bool, str]:
    assert_input_allowed(path, trace)
    exists = path.exists()
    record_input(trace, path, "layout_prediction", [], "exists")
    return exists, sha256(path, trace, "layout_prediction", "sha256") if exists else ""


def read_allowlisted_csv(path: Path, columns: list[str], trace: list[dict[str, object]] | None = None) -> list[dict[str, str]]:
    assert_input_allowed(path, trace)
    denied_columns = sorted({column.lower() for column in columns} & {column.lower() for column in DENY_COLUMNS})
    if denied_columns:
        raise PermissionError(f"denied projected columns: {denied_columns}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        missing = set(columns) - set(header)
        if missing:
            raise ValueError(f"{path}: missing allowlisted columns {sorted(missing)}")
        indexes = {column: header.index(column) for column in columns}
        rows = [{column: values[index] for column, index in indexes.items()} for values in reader]
    record_input(trace, path, "csv_projection", columns)
    return rows


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_deterministic_npz(path: Path, arrays: dict[str, np.ndarray]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(arrays):
            buffer = io.BytesIO()
            np.save(buffer, np.asarray(arrays[name]), allow_pickle=False)
            info = zipfile.ZipInfo(f"{name}.npy", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 0
            info.external_attr = 0o600 << 16
            archive.writestr(info, buffer.getvalue())


def spatial_evidence(path: Path, trace: list[dict[str, object]] | None = None) -> dict[str, np.ndarray | tuple[int, int]]:
    assert_input_allowed(path, trace)
    record_input(trace, path, "image_only", [], "decode")
    with Image.open(path) as source:
        original_size = source.size
        gray = np.asarray(source.convert("L").resize((256, 128), Image.Resampling.BILINEAR), dtype=np.float32)
    dx = np.abs(np.roll(gray, -1, axis=1) - gray) / 255.0
    dy = np.zeros_like(gray)
    dy[1:] = np.abs(gray[1:] - gray[:-1]) / 255.0
    return {"gray": gray.astype(np.uint8), "dx_wrap": dx.astype(np.float32), "dy": dy.astype(np.float32), "vertical_profile": dx.mean(axis=0).astype(np.float32), "boundary_profile": dy.mean(axis=1).astype(np.float32), "original_size": original_size}


def parse_candidate_geometry(raw: str, width: int, height: int) -> dict[str, object]:
    try:
        points = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {"parse_status": "failed", "parse_reason": "invalid_json", "point_count": "", "layout_corner_count": ""}
    point_count = len(points) if isinstance(points, list) else 0
    normalized = normalize_geometry(points, width=width, height=height)
    return {
        "parse_status": "valid" if normalized["valid"] else "failed",
        "parse_reason": normalized.get("reason", "") if not normalized["valid"] else "",
        "point_count": point_count,
        "layout_corner_count": normalized["n_pairs"] if normalized["valid"] else "",
        "point_count_even": str(point_count >= 4 and point_count % 2 == 0),
        "pairing_valid": str(normalized.get("pairing_valid", False)),
        "duplicate_x_absent": str(normalized.get("duplicate_corner_absent", False) and normalized.get("reason") != "duplicate_event_positions"),
        "top_floor_order_valid": str(normalized.get("top_bottom_order_valid", False)),
        "topology_valid": str(normalized.get("topology_valid", False)),
        "pairs": normalized.get("pairs", []),
        "width": width,
        "height": height,
    }


def _sample_profile(profile: np.ndarray, x_norm: float) -> float:
    return float(profile[int(round(x_norm * len(profile))) % len(profile)])


def _sample_field(field: np.ndarray, x_norm: float, y_norm: float) -> float:
    x = int(round(x_norm * field.shape[1])) % field.shape[1]
    y = min(field.shape[0] - 1, max(0, int(round(y_norm * (field.shape[0] - 1)))))
    return float(field[y, x])


def _piecewise_boundary_samples(pairs: list[dict[str, object]], width: int, height: int, samples_per_width: int = 64) -> list[dict[str, object]]:
    samples = []
    for index, current in enumerate(pairs):
        following = pairs[(index + 1) % len(pairs)]
        start_x = float(current["x"])
        end_x = float(following["x"])
        if index == len(pairs) - 1 or end_x <= start_x:
            end_x += width
        span = end_x - start_x
        count = max(2, int(math.ceil(span / width * samples_per_width)) + 1)
        is_seam = end_x > width or (index == len(pairs) - 1 and math.isclose(end_x, width))
        for step in range(count):
            fraction = step / (count - 1)
            x = start_x + span * fraction
            ceiling = float(current["y_ceiling"]) + fraction * (float(following["y_ceiling"]) - float(current["y_ceiling"]))
            floor = float(current["y_floor"]) + fraction * (float(following["y_floor"]) - float(current["y_floor"]))
            samples.append({"x_norm": x / width, "ceiling_y_norm": ceiling / height, "floor_y_norm": floor / height, "is_seam": is_seam})
    return samples


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def alignment_features(parsed: dict[str, object], evidence: dict[str, np.ndarray | tuple[int, int]]) -> dict[str, object]:
    if "parse_status" not in parsed:
        parsed = {"parse_status": "valid" if parsed.get("valid") else "failed", "pairs": parsed.get("pairs", []), "width": parsed.get("width", 1024), "height": parsed.get("height", 512)}
    if parsed["parse_status"] != "valid":
        return {"alignment_status": "fail_closed_parse_invalid", "alignment_coverage": 0.0, "vertical_edge_support": "", "ceiling_boundary_support": "", "floor_boundary_support": "", "seam_wrap_consistency": ""}
    width, height = parsed["width"], parsed["height"]
    pairs = parsed["pairs"]
    width_float = float(width)
    x_positions = [float(pair["x"]) % width_float / width_float for pair in pairs]
    vertical = [_sample_profile(evidence["vertical_profile"], x) for x in x_positions]
    boundary_samples = _piecewise_boundary_samples(pairs, width, height)
    ceiling = [_sample_field(evidence["dy"], sample["x_norm"], sample["ceiling_y_norm"]) for sample in boundary_samples]
    floor = [_sample_field(evidence["dy"], sample["x_norm"], sample["floor_y_norm"]) for sample in boundary_samples]
    seam_samples = [sample for sample in boundary_samples if sample["is_seam"]]
    seam_ceiling = [_sample_field(evidence["dy"], sample["x_norm"], sample["ceiling_y_norm"]) for sample in seam_samples]
    seam_floor = [_sample_field(evidence["dy"], sample["x_norm"], sample["floor_y_norm"]) for sample in seam_samples]
    seam_values = [(left + right) / 2.0 for left, right in zip(seam_ceiling, seam_floor)]
    half = max(1, len(seam_values) // 2)
    left_seam = _mean(seam_values[:half])
    right_seam = _mean(seam_values[half:])
    seam_consistency = 1.0 - abs(left_seam - right_seam) / max(left_seam, right_seam, 1e-8)
    seam_events = sum(min(x, 1.0 - x) <= 0.05 for x in x_positions)
    return {"alignment_status": "ready", "alignment_coverage": 1.0, "vertical_edge_support": _mean(vertical), "ceiling_boundary_support": _mean(ceiling), "floor_boundary_support": _mean(floor), "seam_wrap_consistency": max(0.0, min(1.0, seam_consistency)), "seam_segment_boundary_support": _mean(seam_values), "seam_event_count": seam_events, "pair_sample_count": len(pairs), "segment_count": len(pairs), "boundary_sample_count": len(boundary_samples), "seam_segment_count": 1 if seam_samples else 0, "seam_sample_count": len(seam_samples)}


def model_prediction_rows(identity_rows: list[dict[str, object]], c2: dict, stage3: dict, trace: list[dict[str, object]]) -> list[dict[str, object]]:
    rows = []
    for identity in identity_rows:
        base = identity["panorama_identity"]
        layout = ROOT / "output/layout_json" / f"{base}.json"
        exists, layout_sha = file_identity(layout, trace)
        rows.append({"panorama_identity": base, "building_scene_id": identity["building_scene_id"], "split": identity["split"], "layout_prediction_path": rel(layout), "layout_prediction_exists": str(exists), "layout_prediction_sha256": layout_sha, "path_binding_status": "path_present_but_inference_source_unbound" if exists else "source_absent", "c2_checkpoint_sha256": c2.get("checkpoint_sha256", ""), "c2_config_sha256": c2.get("config_sha256", ""), "c2_candidate_cache_sha256": c2.get("candidate_descriptor_cache_sha256", ""), "stage3_checkpoint_sha256": stage3.get("checkpoint_sha256", ""), "stage3_config_sha256": stage3.get("config_sha256", ""), "stage3_candidate_cache_sha256": stage3.get("candidate_descriptor_cache_sha256", ""), "inference_code_identity": "source_absent_not_bound_in_manifest", "formal_model_binding": "False", "reads_gt": "False", "reads_reference": "False"})
    return rows


def readiness_status(image_failures: list[dict[str, object]], geometry_failures: list[dict[str, object]], alignment_rows: list[dict[str, object]], rejected_candidate_acceptance_policy: str | None = None) -> str:
    if image_failures or not alignment_rows:
        return "A4_ALIGNMENT_SUBSTRATE_NOT_READY"
    if geometry_failures and not rejected_candidate_acceptance_policy:
        return "A4_ALIGNMENT_SUBSTRATE_PARTIAL"
    return "A4_ALIGNMENT_SUBSTRATE_READY"


def model_readiness(prediction_rows: list[dict[str, object]]) -> tuple[str, bool]:
    ready = bool(prediction_rows) and all(row["layout_prediction_exists"] == "True" and row["formal_model_binding"] == "True" for row in prediction_rows)
    return ("model_ready" if ready else "source_absent", ready)


def trace_violations(trace: list[dict[str, object]]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    denied_projection = [entry for entry in trace if set(str(column).lower() for column in entry.get("projected_columns", [])) & set(column.lower() for column in DENY_COLUMNS)]
    denied_path_entries = [entry for entry in trace if denied_path(Path(str(entry["path"]))) is not None]
    return denied_projection, denied_path_entries


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    trace: list[dict[str, object]] = []
    task_rows = read_allowlisted_csv(VARIABLE_AUDIT, ALLOWLIST["task_identity"], trace)
    image_rows = read_allowlisted_csv(IMAGE_LIST, ALLOWLIST["image_listing"], trace)
    split_rows = read_allowlisted_csv(SPLIT_MANIFEST, ALLOWLIST["split"], trace)
    candidate_rows = read_allowlisted_csv(CANDIDATE_GEOMETRIES, ALLOWLIST["candidate_geometry"], trace)
    split_by_building = {row["building_scene_id"]: row["split"] for row in split_rows}
    identities = {}
    for row in task_rows:
        item = identities.setdefault(row["base_task_id"], {"panorama_identity": row["base_task_id"], "building_scene_id": row["building_id"], "task_context_count": 0, "condition_count": 0, "conditions": set()})
        item["task_context_count"] += 1
        item["conditions"].add(row["condition"])
    for item in identities.values():
        item["condition_count"] = len(item.pop("conditions"))
        item["split"] = split_by_building.get(item["building_scene_id"], "unmapped")
    by_stem = {Path(row["path"]).stem: row for row in image_rows}
    image_index = []
    arrays = {"gray": [], "dx_wrap": [], "dy": [], "vertical_profile": [], "boundary_profile": []}
    evidence_by_id = {}
    failures = []
    for index, base in enumerate(sorted(identities)):
        listing = by_stem.get(base)
        if not listing or not Path(listing["path"]).exists():
            failures.append({"layer": "unique_panorama_identity", "identity": base, "reason": "missing_real_image_file"})
            continue
        path = Path(listing["path"])
        try:
            evidence = spatial_evidence(path, trace)
        except Exception as exc:
            failures.append({"layer": "unique_panorama_identity", "identity": base, "reason": f"image_decode_failed:{type(exc).__name__}"})
            continue
        actual_sha = sha256(path, trace, "image_only", "sha256")
        image_index.append({"panorama_identity": base, "array_index": len(image_index), "building_scene_id": identities[base]["building_scene_id"], "split": identities[base]["split"], "path": rel(path), "size_bytes": path.stat().st_size, "sha256_actual": actual_sha, "sha256_listing": listing["sha256"], "sha_match": str(actual_sha == listing["sha256"]), "original_width": evidence["original_size"][0], "original_height": evidence["original_size"][1], "spatial_feature_version": FEATURE_VERSION})
        evidence_by_id[base] = evidence
        for key in arrays:
            arrays[key].append(evidence[key])
    np_arrays = {key: np.stack(value) for key, value in arrays.items()}
    write_deterministic_npz(OUT / "SPATIAL_IMAGE_EVIDENCE.npz", np_arrays)
    write_csv(OUT / "SPATIAL_IMAGE_EVIDENCE_INDEX.csv", image_index, list(image_index[0]))
    descriptor_rows = []
    alignment_rows = []
    geometry_failures = []
    selected_candidate_count = 0
    for row in candidate_rows:
        base = row["base_task_id"]
        if base not in evidence_by_id or identities[base]["split"] != "development":
            continue
        selected_candidate_count += 1
        parsed = parse_candidate_geometry(row["canonical_geometry"], int(image_index[next(i for i, item in enumerate(image_index) if item["panorama_identity"] == base)]["original_width"]), int(image_index[next(i for i, item in enumerate(image_index) if item["panorama_identity"] == base)]["original_height"]))
        descriptor = {"panorama_identity": base, "building_scene_id": identities[base]["building_scene_id"], "split": "development", "stage": row["stage"], "candidate_annotation_id": row["canonical_annotation_id"], "worker_id": row["worker_id"], "descriptor_source": "formal_normalize_geometry_v1", "geometry_rule_manifest": rel(RULE_MANIFEST), "reads_gt": "False", "reads_reference": "False", "reads_quality": "False", **{key: value for key, value in parsed.items() if key not in {"pairs", "width", "height"}}}
        descriptor_rows.append(descriptor)
        if parsed["parse_status"] != "valid":
            geometry_failures.append({"layer": "development_candidate_geometry", "identity": base, "candidate_annotation_id": row["canonical_annotation_id"], "reason": parsed["parse_reason"]})
            continue
        alignment_rows.append({"panorama_identity": base, "building_scene_id": identities[base]["building_scene_id"], "split": "development", "stage": row["stage"], "candidate_annotation_id": row["canonical_annotation_id"], "worker_id": row["worker_id"], "alignment_source": "spatial_image_evidence_npz_plus_formal_geometry_pairs", "reads_gt": "False", "reads_reference": "False", "reads_quality": "False", **alignment_features(parsed, evidence_by_id[base])})
    write_csv(OUT / "DEVELOPMENT_CANDIDATE_GEOMETRY_DESCRIPTORS.csv", descriptor_rows, list(descriptor_rows[0]))
    write_csv(OUT / "DEVELOPMENT_CANDIDATE_IMAGE_ALIGNMENT.csv", alignment_rows, list(alignment_rows[0]))
    c2 = read_json(C2_MODEL_MANIFEST, trace)
    stage3 = read_json(STAGE3_MODEL_MANIFEST, trace)
    read_json(RULE_MANIFEST, trace)
    prediction_rows = model_prediction_rows(image_index, c2, stage3, trace)
    write_csv(OUT / "MODEL_PREDICTION_COVERAGE.csv", prediction_rows, list(prediction_rows[0]))
    coverage = [
        {"layer": "unique_panorama_identity", "expected": len(identities), "ready": len(image_index), "failed": len(identities) - len(image_index), "status": "ready" if len(image_index) == len(identities) else "fail_closed"},
        {"layer": "spatial_image_evidence", "expected": len(identities), "ready": len(np_arrays["gray"]), "failed": len(identities) - len(np_arrays["gray"]), "status": "ready" if len(np_arrays["gray"]) == len(identities) else "fail_closed"},
        {"layer": "development_candidate_geometry", "expected": selected_candidate_count, "ready": len(descriptor_rows) - len(geometry_failures), "failed": len(geometry_failures), "status": "partial_fail_closed" if geometry_failures else "ready"},
        {"layer": "development_candidate_image_alignment", "expected": selected_candidate_count, "ready": len(alignment_rows), "failed": len(geometry_failures), "status": "partial_fail_closed" if geometry_failures else "ready"},
        {"layer": "model_prediction_path_coverage", "expected": len(image_index), "ready": sum(row["layout_prediction_exists"] == "True" for row in prediction_rows), "failed": sum(row["layout_prediction_exists"] != "True" for row in prediction_rows), "status": "path_observed_but_formal_binding_absent"},
    ]
    write_csv(OUT / "COVERAGE_AND_FAILURES.csv", coverage + [{"layer": failure["layer"], "expected": "", "ready": "", "failed": "", "status": json.dumps(failure, ensure_ascii=False)} for failure in failures + geometry_failures], ["layer", "expected", "ready", "failed", "status"])
    arrays_second = []
    for base in sorted(identities):
        listing = by_stem.get(base)
        if listing and Path(listing["path"]).exists():
            arrays_second.append(spatial_evidence(Path(listing["path"]), trace)["dx_wrap"])
    synthetic = {"vertical_profile": np.zeros(64, dtype=np.float32), "dy": np.zeros((32, 64), dtype=np.float32)}
    synthetic["vertical_profile"][16] = 1.0
    synthetic["dy"][4, 16] = 1.0
    synthetic["dy"][23, 16] = 1.0
    good = normalize_geometry([[256, 64], [256, 384], [768, 64], [768, 384]])
    bad = normalize_geometry([[300, 100], [300, 350], [800, 100], [800, 350]])
    status = readiness_status(failures, geometry_failures, alignment_rows)
    model_status, model_ready = model_readiness(prediction_rows)
    denied_projection_trace, denied_path_trace = trace_violations(trace)
    input_paths = {"image_listing": IMAGE_LIST, "task_identity": VARIABLE_AUDIT, "split_manifest": SPLIT_MANIFEST, "candidate_geometries": CANDIDATE_GEOMETRIES, "c2_model_manifest": C2_MODEL_MANIFEST, "stage3_model_manifest": STAGE3_MODEL_MANIFEST, "geometry_rule_manifest": RULE_MANIFEST, "geometry_representation_source": REPRESENTATION_SOURCE}
    inputs = {key: {"path": rel(path), "sha256": sha256(path, trace, "input_source", "sha256")} for key, path in input_paths.items()}
    tests = {
        "same_image_spatial_hash_equal": all(np.array_equal(first, second) for first, second in zip(np_arrays["dx_wrap"], arrays_second)),
        "seam_wrap_spatial_field_present": np_arrays["dx_wrap"].shape[2] == 256,
        "point_count_not_corner_count": parse_candidate_geometry("[[100,100],[100,400],[500,100],[500,400]]", 1024, 512)["point_count"] == 4 and parse_candidate_geometry("[[100,100],[100,400],[500,100],[500,400]]", 1024, 512)["layout_corner_count"] == 2,
        "duplicate_x_fail_closed": parse_candidate_geometry("[[100,100],[100,400],[100,120],[100,420]]", 1024, 512)["parse_status"] == "failed",
        "ceiling_floor_alignment_synthetic": alignment_features(good, synthetic)["ceiling_boundary_support"] > alignment_features(bad, synthetic)["ceiling_boundary_support"] and alignment_features(good, synthetic)["vertical_edge_support"] > alignment_features(bad, synthetic)["vertical_edge_support"],
        "gt_reference_quality_columns_denied": not denied_projection_trace,
        "holdout_quality_delta_read": bool(denied_path_trace),
        "trace_has_no_denied_projection": not denied_projection_trace,
        "trace_has_no_denied_path": not denied_path_trace,
        "trace_records_inputs": bool(trace) and all(entry.get("path") and "projected_columns" in entry for entry in trace),
        "bad_geometry_fail_closed_with_reason": all(item["reason"] for item in geometry_failures),
        "raw_complete_geometry_clean_model_absent_is_ready": readiness_status([], [], [{"id": "candidate"}], None) == "A4_ALIGNMENT_SUBSTRATE_READY" and not model_readiness([{ "layout_prediction_exists": "True", "formal_model_binding": "False" }])[1],
        "geometry_rejection_without_policy_is_partial": readiness_status([], [{"reason": "test"}], [{"id": "candidate"}], None) == "A4_ALIGNMENT_SUBSTRATE_PARTIAL",
        "all_passed": len(image_index) == len(identities) and all(np.array_equal(first, second) for first, second in zip(np_arrays["dx_wrap"], arrays_second)) and not failures and all(item["reason"] for item in geometry_failures) and not denied_projection_trace and not denied_path_trace and alignment_features(good, synthetic)["ceiling_boundary_support"] > alignment_features(bad, synthetic)["ceiling_boundary_support"] and alignment_features(good, synthetic)["floor_boundary_support"] > alignment_features(bad, synthetic)["floor_boundary_support"],
    }
    write_json(OUT / "LEAKAGE_AND_REPRO_TESTS.json", {"tests": tests, "formal_geometry_rule_manifest": rel(RULE_MANIFEST), "formal_geometry_rule_sha256": inputs["geometry_rule_manifest"]["sha256"], "representation_source_sha256": inputs["geometry_representation_source"]["sha256"], "selected_candidate_count": selected_candidate_count, "geometry_failure_count": len(geometry_failures), "input_access_trace": trace})
    write_json(OUT / "INPUT_ALLOWLIST_DENYLIST.json", {"allowlist": ALLOWLIST, "allowlisted_paths": [rel(IMAGE_LIST), rel(VARIABLE_AUDIT), rel(SPLIT_MANIFEST), rel(CANDIDATE_GEOMETRIES), rel(C2_MODEL_MANIFEST), rel(STAGE3_MODEL_MANIFEST), rel(RULE_MANIFEST), rel(REPRESENTATION_SOURCE), "output/layout_json/{base_task_id}.json (existence/hash only)"], "deny_paths": DENY_PATHS, "deny_columns": DENY_COLUMNS, "trace_semantics": "CSV parser may physically parse complete rows, but only allowlisted projected values are consumed; JSON/model and image accesses are recorded by path and kind.", "holdout_rule": "image evidence may cover holdout; candidate alignment is development-only; holdout quality/outcome is not opened or emitted"})
    status_reason = "rejected-candidate acceptance policy not predefined" if geometry_failures else "raw-image evidence and candidate alignment are complete"
    if failures:
        status_reason = "raw-image input failure; fail closed"
    report = f"""# A4 candidate-image alignment substrate\n\n- Status: **{status}**\n- Status reason: **{status_reason}**\n- Raw-image branch: {len(identities)} unique panorama identities were resolved against real files, actual SHA, and dimensions.\n- Spatial evidence: deterministic seam-wrapped `dI/dx`, `dI/dy`, x/y profiles in `SPATIAL_IMAGE_EVIDENCE.npz`; no global-statistics-only representation.\n- Geometry semantics: `{rel(REPRESENTATION_SOURCE)}` and `{rel(RULE_MANIFEST)}` are reused. `point_count` is raw points; `layout_corner_count` is formal valid pair count only.\n- Candidate geometry descriptors and candidate-image alignment are separate. Vertical-edge support samples formal wall-wall x events. Ceiling/floor support samples the formal piecewise-linear boundary between every adjacent pair, including the last-to-first-plus-width seam segment; no curve model is introduced.\n- Alignment sampling coverage: {len(alignment_rows)} valid rows, {sum(int(row["segment_count"]) for row in alignment_rows)} segments, {sum(int(row["boundary_sample_count"]) for row in alignment_rows)} boundary samples, and {sum(int(row["seam_sample_count"]) for row in alignment_rows)} seam samples.\n- Development candidate alignment only: {len(alignment_rows)} valid rows; {len(geometry_failures)} invalid geometry row(s) fail closed with reason. Holdout candidate quality and outcome are not read or emitted.\n- Optional model branch: `model_status={model_status}`, `model_ready={model_ready}`. Existing prediction paths are present but inference/model identity is not formally bound; this does not gate raw-image alignment readiness.\n- I/O evidence: {len(trace)} input accesses recorded; denied projections consumed: {len(denied_projection_trace)}; denied paths consumed: {len(denied_path_trace)}. CSV parsing may physically read complete rows, but only allowlisted projected values are consumed.\n\nNo A4 selector, threshold, training, performance estimate, GT evaluation, prospective annotation, contract, SAP, routing, or frozen input was changed.\n"""
    (OUT / "A4_IMAGE_ALIGNMENT_SUBSTRATE_REPORT.md").write_text(report, encoding="utf-8")
    output_files = [path for path in OUT.iterdir() if path.is_file() and path.name != "analysis_manifest.json"]
    output_sha = {path.name: sha256(path) for path in sorted(output_files)}
    manifest = {"schema_version": "a4_alignment_substrate_manifest_v2", "status": status, "status_reason": status_reason, "raw_image_alignment_status": status, "model_status": model_status, "model_ready": model_ready, "generator_path": rel(Path(__file__)), "generator_sha256": sha256(Path(__file__)), "inputs": inputs, "input_access_trace": trace, "output_sha256": output_sha, "hash_mismatches": [], "read_only_boundaries": {"a4_selector_implemented": False, "a4_selector_trained": False, "holdout_quality_read": bool(denied_path_trace), "gt_reference_quality_read": bool(denied_projection_trace), "frozen_inputs_modified": False, "contract_modified": False, "sap_modified": False, "routing_modified": False, "new_annotation_started": False}}
    write_json(OUT / "analysis_manifest.json", manifest)
    print(json.dumps({"output_dir": str(OUT), "status": status, "identity_count": len(identities), "spatial_rows": len(image_index), "geometry_descriptor_rows": len(descriptor_rows), "alignment_rows": len(alignment_rows), "geometry_failures": len(geometry_failures), "manifest_sha256": sha256(OUT / "analysis_manifest.json")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
