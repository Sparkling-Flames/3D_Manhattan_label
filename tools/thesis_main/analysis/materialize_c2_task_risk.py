"""Materialize pre-annotation C2 task risk from fixed HoHoNet and layout evidence."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.thesis_main.analysis.geometry_consensus.representation import normalize_geometry
from tools.thesis_main.analysis.vfinal_artifact_utils import sha256_file
from tools.thesis_main.analysis.paper_a_contracts import METHOD_CONTRACT, load_method_contract
from tools.thesis_main.registry.hohonet_feature_backend import extract_orbit_descriptors, pool_lhfeat


DEFAULT_RISK_CONTRACT = _PROJECT_ROOT / "docs" / "thesis_main" / "C2B_RISK_DESIGN_CONTRACT_v1.json"


def _risk_contract(path: Path | None) -> tuple[dict[str, Any], Path]:
    contract_path = path or DEFAULT_RISK_CONTRACT
    try:
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"C2-B risk design contract unavailable: {contract_path}") from exc
    if contract.get("schema_version") != "paper_a_c2b_risk_design_contract_v1":
        raise ValueError("unsupported C2-B risk design contract")
    if contract.get("stratum_rule", {}).get("forbid_legacy_proxies") is None:
        raise ValueError("C2-B risk design contract lacks legacy-proxy guard")
    method = load_method_contract()
    if contract.get("contract_role") != "generated_subordinate" or contract.get("method_contract_version") != method["contract_version"] or contract.get("method_contract_sha256") != sha256_file(METHOD_CONTRACT):
        raise ValueError("C2-B risk design contract has a stale method contract binding")
    return contract, contract_path


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _write(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = list(dict.fromkeys(key for row in rows for key in row)) if rows else ["task_id"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader(); writer.writerows(rows)


def _layout_features(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"layout_status": "missing", "g_model_struct": "", "pair_count": "", "postprocess_valid": False}
    payload = json.loads(path.read_text(encoding="utf-8"))
    corners = (payload.get("layout") or {}).get("corners") or []
    points = [point for row in corners for point in ([float(row["x"]), float(row["y_ceiling"])], [float(row["x"]), float(row["y_floor"])])]
    normalized = normalize_geometry(points)
    xs = sorted(float(row["x"]) % 1024 for row in corners)
    gaps = [xs[index + 1] - xs[index] for index in range(len(xs) - 1)] + ([xs[0] + 1024 - xs[-1]] if xs else [])
    seam_stability = 1.0 - min(1.0, (gaps[-1] if gaps else 1024) / max(gaps or [1024]))
    pair_count = len(corners)
    duplicate_x = len({round(value, 6) for value in xs}) != len(xs)
    seam_instability = 1.0 - seam_stability
    g_score = min(1.0, abs(pair_count - 6) / 8 + (0.35 if duplicate_x else 0) + (0.35 if not normalized["topology_valid"] else 0) + 0.15 * seam_instability)
    return {
        "layout_status": "ready", "g_model_struct": g_score, "pair_count": pair_count,
        "ceiling_floor_curve_present": bool(corners), "wall_peak_count": pair_count,
        "topology_valid": normalized["topology_valid"], "seam_stability": seam_stability,
        "seam_instability": seam_instability,
        "postprocess_valid": normalized["valid"], "duplicate_wall_peak": duplicate_x,
        "layout_sha256": sha256_file(path),
    }


def _pool_lhfeat(feature: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    return pool_lhfeat(feature)


def _lhfeat_descriptors(
    paths: list[Path], checkpoint: Path, *, config: Path, device: str = "auto",
    invariance_audit: dict[str, Any] | None = None,
) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    output, audit = extract_orbit_descriptors(
        paths, checkpoint, config, device=device, batch_size=4,
        audit_seam=invariance_audit is not None,
    )
    if invariance_audit is not None:
        invariance_audit.update(audit)
    return output


def _fit_whitener(matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    if matrix.ndim != 2 or len(matrix) < 2 or not np.isfinite(matrix).all():
        raise ValueError("feature reference matrix must contain at least two finite rows")
    mean = matrix.mean(axis=0)
    _u, singular, components = np.linalg.svd(matrix - mean, full_matrices=False)
    keep = singular > np.finfo(float).eps * max(matrix.shape) * singular[0]
    components = components[keep]
    scale = singular[keep] / np.sqrt(max(1, len(matrix) - 1))
    if not len(components) or not np.isfinite(scale).all() or np.any(scale <= 0):
        raise ValueError("feature reference PCA/whitening is degenerate")
    transformed = ((matrix - mean) @ components.T) / scale
    return mean, components, scale, transformed


def _apply_whitener(vector: np.ndarray, mean: np.ndarray, components: np.ndarray, scale: np.ndarray) -> np.ndarray:
    return ((vector - mean) @ components.T) / scale


def _feature_audit_passes(circular: dict[str, Any], seam: dict[str, Any], thresholds: dict[str, Any]) -> tuple[bool, bool]:
    values = thresholds.get("thresholds", {})
    approved = (
        thresholds.get("status") == "approved"
        and thresholds.get("formal_feature_freeze_allowed") is True
        and all(str(thresholds.get(field, "")).strip() for field in ("approved_by", "approved_at"))
    )
    try:
        circular_value = float(circular["circular_relative_l2_max"])
        seam_value = float(seam["seam_relative_l2_q95"])
        circular_limit = float(values["circular_relative_l2_max"])
        seam_limit = float(values["seam_relative_l2_q95"])
        circular_count = int(circular["circular_audited_image_count"])
        seam_count = int(seam["seam_audited_image_count"])
        minimum_circular = int(values["minimum_circular_audited_image_count"])
        minimum_seam = int(values["minimum_seam_audited_image_count"])
    except (KeyError, TypeError, ValueError, OverflowError):
        return False, False
    return (
        approved and math.isfinite(circular_value) and math.isfinite(circular_limit)
        and circular_count >= minimum_circular and circular_value <= circular_limit,
        approved and math.isfinite(seam_value) and math.isfinite(seam_limit)
        and seam_count >= minimum_seam and seam_value <= seam_limit,
    )


def freeze_feature_reference(
    reference_dir: Path, checkpoint: Path, config: Path, cache_path: Path,
    manifest_path: Path, *, device: str = "auto", audit_threshold_manifest: Path | None = None,
) -> dict[str, Any]:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    paths = sorted(path for path in reference_dir.rglob("*") if path.suffix.lower() in {".jpg", ".jpeg", ".png"})
    if len(paths) < 2:
        raise ValueError("feature reference requires at least two images")
    invariance: dict[str, Any] = {}
    descriptors = _lhfeat_descriptors(paths, checkpoint, config=config, device=device, invariance_audit=invariance)
    global_matrix = np.stack([descriptors[path.resolve().as_posix()][0] for path in paths])
    local_matrix = np.stack([descriptors[path.resolve().as_posix()][1] for path in paths])
    global_mean, global_components, global_scale, reference_global = _fit_whitener(global_matrix)
    local_mean, local_components, local_scale, reference_local = _fit_whitener(local_matrix)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        cache_path, global_mean=global_mean, global_components=global_components, global_scale=global_scale,
        local_mean=local_mean, local_components=local_components, local_scale=local_scale,
        reference_global=reference_global, reference_local=reference_local,
    )
    reference_listing_sha = hashlib.sha256("\n".join(f"{path.resolve().as_posix()}|{path.stat().st_size}|{sha256_file(path)}" for path in paths).encode()).hexdigest()
    circular_path = manifest_path.with_name(f"{manifest_path.stem}.circular_audit.json")
    seam_path = manifest_path.with_name(f"{manifest_path.stem}.seam_audit.json")
    circular = {key: value for key, value in invariance.items() if key.startswith(("circular_", "off_grid_", "four_phase_")) or key in {"device", "batch_size", "dtype", "orbit_fractions"}}
    circular["audit_basis"] = "off_grid_rotation_reinference"
    circular["four_phase_permutation_role"] = "diagnostic_only"
    seam = {key: value for key, value in invariance.items() if key.startswith("seam_") or key in {"device", "batch_size", "dtype"}}
    seam["audit_basis"] = "small_seam_offset_sensitivity"
    circular_path.write_text(json.dumps(circular, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    seam_path.write_text(json.dumps(seam, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    thresholds = json.loads(audit_threshold_manifest.read_text(encoding="utf-8")) if audit_threshold_manifest and audit_threshold_manifest.exists() else {}
    circular_ready, seam_ready = _feature_audit_passes(circular, seam, thresholds)
    cache_sha, circular_sha, seam_sha = sha256_file(cache_path), sha256_file(circular_path), sha256_file(seam_path)
    payload = {
        "schema_version": "paper_a_c2_feature_freeze_v2", "feature_cache_path": cache_path.resolve().as_posix(),
        "circular_audit_path": circular_path.resolve().as_posix(), "seam_audit_path": seam_path.resolve().as_posix(),
        "checkpoint_sha256": sha256_file(checkpoint), "config_sha256": sha256_file(config),
        "reference_feature_sha256": cache_sha, "reference_listing_sha256": reference_listing_sha,
        "reference_image_count": len(paths), "pca_frozen": True, "whitening_frozen": True,
        "circular_shift_invariant": circular_ready, "off_grid_circular_robustness": circular_ready, "seam_invariant": seam_ready,
        "pca_frozen_sha256": cache_sha, "whitening_frozen_sha256": cache_sha,
        "circular_shift_invariant_sha256": circular_sha, "seam_invariant_sha256": seam_sha,
        "pca_sha256": cache_sha, "whitening_sha256": cache_sha,
        "circular_shift_audit_sha256": circular_sha, "seam_audit_sha256": seam_sha,
        "feature_audit_threshold_manifest_sha256": sha256_file(audit_threshold_manifest) if audit_threshold_manifest and audit_threshold_manifest.exists() else "",
        "feature_audit_status": "approved" if circular_ready and seam_ready else "pending_threshold_approval_or_failed",
    }
    manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def refresh_feature_freeze_approval(
    manifest_path: Path, audit_threshold_manifest: Path, *, checkpoint: Path,
    config: Path, reference_dir: Path, candidate_inventory: Path,
) -> dict[str, Any]:
    """Revalidate immutable caches and apply a threshold manifest without rerunning HoHoNet."""
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "paper_a_c2_feature_freeze_v2":
        raise ValueError("unsupported feature freeze manifest")

    def artifact(field: str, sha_field: str) -> Path:
        path = Path(str(payload.get(field, "")))
        if not path.is_absolute():
            path = manifest_path.parent / path
        if not path.exists() or sha256_file(path) != payload.get(sha_field):
            raise ValueError(f"stale feature artifact: {field}")
        return path

    artifact("feature_cache_path", "reference_feature_sha256")
    artifact("candidate_descriptor_cache_path", "candidate_descriptor_cache_sha256")
    circular_path = artifact("circular_audit_path", "circular_shift_audit_sha256")
    seam_path = artifact("seam_audit_path", "seam_audit_sha256")
    if payload.get("checkpoint_sha256") != sha256_file(checkpoint) or payload.get("config_sha256") != sha256_file(config):
        raise ValueError("feature checkpoint/config identity mismatch")
    if payload.get("candidate_inventory_sha256") != sha256_file(candidate_inventory):
        raise ValueError("candidate inventory identity mismatch")
    reference_paths = sorted(path for path in reference_dir.rglob("*") if path.suffix.lower() in {".jpg", ".jpeg", ".png"})
    listing_sha = hashlib.sha256("\n".join(
        f"{path.resolve().as_posix()}|{path.stat().st_size}|{sha256_file(path)}" for path in reference_paths
    ).encode()).hexdigest()
    if len(reference_paths) != int(payload.get("reference_image_count") or 0) or listing_sha != payload.get("reference_listing_sha256"):
        raise ValueError("reference image listing identity mismatch")
    thresholds = json.loads(audit_threshold_manifest.read_text(encoding="utf-8"))
    circular = json.loads(circular_path.read_text(encoding="utf-8"))
    seam = json.loads(seam_path.read_text(encoding="utf-8"))
    if circular.get("audit_basis") != "off_grid_rotation_reinference" or circular.get("four_phase_permutation_role") != "diagnostic_only":
        raise ValueError("feature circular audit is not the off-grid reinference contract")
    circular_ready, seam_ready = _feature_audit_passes(circular, seam, thresholds)
    payload.update({
        "circular_shift_invariant": circular_ready,
        "off_grid_circular_robustness": circular_ready,
        "seam_invariant": seam_ready,
        "feature_audit_threshold_manifest_sha256": sha256_file(audit_threshold_manifest),
        "feature_audit_status": "approved" if circular_ready and seam_ready else "pending_threshold_approval_or_failed",
        "cache_reused_without_model_inference": True,
    })
    manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def _knn(candidate: np.ndarray, reference: np.ndarray, k: int = 5) -> float:
    distances = np.linalg.norm(reference - candidate[None], axis=1)
    return float(np.mean(np.partition(distances, min(k, len(distances)) - 1)[:min(k, len(distances))]))


def _composite_q75_bucket(
    values: dict[str, float], references: dict[str, list[float]], *, stress_quantile: float = .75,
) -> tuple[str, dict[str, float]]:
    percentiles = {
        name: sum(reference <= values[name] for reference in refs) / len(refs)
        for name, refs in references.items() if refs and name in values
    }
    return ("stress" if len(percentiles) == 4 and max(percentiles.values()) >= stress_quantile else "ordinary"), percentiles


RISK_VECTOR_FIELDS = ("d_model_feat", "d_model_feat_local_max", "g_model_struct", "d_cal_A")


def _frozen_vector(values: dict[str, float], scales: dict[str, float]) -> list[float] | None:
    if any(name not in values for name in RISK_VECTOR_FIELDS):
        return None
    return [float(values[name]) / (float(scales.get(name) or 1.0) or 1.0) for name in RISK_VECTOR_FIELDS]


def _score(vector: list[float] | None) -> float | None:
    return float(np.linalg.norm(np.asarray(vector, dtype=float))) if vector is not None else None


def load_frozen_c1_risk_reference(
    reference_csv: Path, *, stress_quantile: float = .75,
) -> dict[str, Any]:
    """Load the already-materialized C1 risk reference without recomputing it."""
    rows = _read(reference_csv)
    if not rows:
        raise ValueError("frozen C1 risk reference is empty")
    seen_tasks: set[str] = set()
    complete: list[dict[str, Any]] = []
    for row in rows:
        task = str(row.get("base_task_id") or row.get("task_id") or "").strip()
        if not task or task in seen_tasks:
            raise ValueError("frozen C1 risk reference requires unique base_task_id")
        seen_tasks.add(task)
        try:
            values = {name: float(row[name]) for name in RISK_VECTOR_FIELDS}
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("frozen C1 risk reference has incomplete risk channels") from exc
        if not all(math.isfinite(value) for value in values.values()):
            raise ValueError("frozen C1 risk reference contains non-finite risk channels")
        complete.append({"base_task_id": task, **values})
    if len(complete) < 2:
        raise ValueError("frozen C1 risk reference requires at least two complete rows")
    channel_scales = {
        name: (float(np.std([row[name] for row in complete])) or 1.0)
        for name in RISK_VECTOR_FIELDS
    }
    reference_scores = [
        float(np.linalg.norm(np.asarray([row[name] / channel_scales[name] for name in RISK_VECTOR_FIELDS], dtype=float)))
        for row in complete
    ]
    q75 = float(np.quantile(reference_scores, stress_quantile))
    for row, score in zip(rows, reference_scores):
        declared_score = str(row.get("risk_design_score_A", "")).strip()
        if declared_score and not math.isclose(float(declared_score), score, rel_tol=1e-9, abs_tol=1e-9):
            raise ValueError("frozen C1 risk reference score does not match its channels")
        declared_stratum = str(row.get("risk_design_stratum", "")).strip()
        if declared_stratum and declared_stratum != ("stress" if score >= q75 else "ordinary"):
            raise ValueError("frozen C1 risk reference stratum does not match its Q75")
    support_names = ("d_model_feat", "d_model_feat_local_max", "g_model_struct")
    support_matrix = np.asarray([[row[name] for name in support_names] for row in complete], dtype=float)
    support_scale = support_matrix.std(axis=0)
    support_scale[support_scale == 0] = 1.0
    return {
        "reference_csv": reference_csv,
        "reference_rows": rows,
        "channel_scales": channel_scales,
        "reference_scores": reference_scores,
        "q75": q75,
        "stress_quantile": float(stress_quantile),
        "support_matrix": support_matrix,
        "support_scale": support_scale,
    }


def score_frozen_c1_risk_candidate(
    values: dict[str, Any], reference: dict[str, Any],
) -> dict[str, Any]:
    """Score one candidate against the immutable C1 risk distribution."""
    numeric: dict[str, float] = {}
    for name in RISK_VECTOR_FIELDS:
        try:
            value = float(values[name])
        except (KeyError, TypeError, ValueError):
            return {"risk_design_vector_A": "", "risk_design_score_A": "", "risk_design_stratum": "", "risk_status": "missing_channel"}
        if not math.isfinite(value):
            return {"risk_design_vector_A": "", "risk_design_score_A": "", "risk_design_stratum": "", "risk_status": "nonfinite_channel"}
        numeric[name] = value
    vector = _frozen_vector(numeric, reference["channel_scales"])
    score = _score(vector)
    if vector is None or score is None:
        return {"risk_design_vector_A": "", "risk_design_score_A": "", "risk_design_stratum": "", "risk_status": "missing_channel"}
    percentile = sum(value <= score for value in reference["reference_scores"]) / len(reference["reference_scores"])
    bucket = "stress" if percentile >= float(reference["stress_quantile"]) else "ordinary"
    return {
        "risk_design_vector_A": json.dumps(vector, separators=(",", ":")),
        "risk_design_score_A": score,
        "risk_design_stratum": bucket,
        "risk_design_score_A_percentile": percentile,
        "risk_design_q75": reference["q75"],
        "risk_status": "ready",
    }


def _feature_freeze_ready(
    path: Path | None, *, checkpoint: Path | None = None, config: Path | None = None,
    reference_feature: Path | None = None,
) -> bool:
    if not path or not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if payload.get("schema_version") != "paper_a_c2_feature_freeze_v2" or payload.get("feature_audit_status") != "approved":
        return False
    required = ("pca_frozen", "whitening_frozen", "circular_shift_invariant", "seam_invariant")
    if not all(bool(payload.get(flag)) and str(payload.get(f"{flag}_sha256", "")).strip() for flag in required):
        return False
    if payload.get("off_grid_circular_robustness") is not True:
        return False
    expected = {
        "checkpoint_sha256": checkpoint,
        "config_sha256": config,
        "reference_feature_sha256": reference_feature,
    }
    for field, source in expected.items():
        if source is not None and (not source.exists() or payload.get(field) != sha256_file(source)):
            return False
    cache = Path(str(payload.get("feature_cache_path", "")))
    candidate_cache = Path(str(payload.get("candidate_descriptor_cache_path", "")))
    circular = Path(str(payload.get("circular_audit_path", "")))
    seam = Path(str(payload.get("seam_audit_path", "")))
    if not cache.is_absolute():
        cache = path.parent / cache
    if not candidate_cache.is_absolute(): candidate_cache = path.parent / candidate_cache
    if not circular.is_absolute(): circular = path.parent / circular
    if not seam.is_absolute(): seam = path.parent / seam
    leakage = path.parent / "c2b_reference_candidate_leakage_audit.summary.json"
    try:
        circular_payload = json.loads(circular.read_text(encoding="utf-8"))
        leakage_payload = json.loads(leakage.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return (
        cache.exists()
        and sha256_file(cache) == payload.get("reference_feature_sha256")
        and candidate_cache.exists()
        and sha256_file(candidate_cache) == payload.get("candidate_descriptor_cache_sha256")
        and circular.exists() and seam.exists() and circular != seam
        and sha256_file(circular) == payload.get("circular_shift_audit_sha256")
        and sha256_file(seam) == payload.get("seam_audit_sha256")
        and circular_payload.get("audit_basis") == "off_grid_rotation_reinference"
        and circular_payload.get("four_phase_permutation_role") == "diagnostic_only"
        and leakage.exists()
        and sha256_file(leakage) == payload.get("reference_candidate_leakage_audit_sha256")
        and leakage_payload.get("formal_feature_pool_allowed") is True
        and all(str(payload.get(field, "")).strip() for field in ("pca_sha256", "whitening_sha256", "circular_shift_audit_sha256", "seam_audit_sha256"))
    )


def materialize(
    inventory_csv: Path, layout_dir: Path, c1_task_feature_csv: Path, output_dir: Path, *,
    input_status: str, checkpoint: Path | None = None,
    extract_lhfeat: bool = False,
    risk_contract: Path | None = None, feature_freeze_manifest: Path | None = None,
    c1_freeze_manifest: Path | None = None, building_registry_csv: Path | None = None,
    device: str = "auto",
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    contract, contract_path = _risk_contract(risk_contract)
    stress_quantile = float(contract["stratum_rule"]["stress_quantile"])
    inventory = _read(inventory_csv)
    building_registry: dict[tuple[str, str], dict[str, str]] = {}
    if building_registry_csv and building_registry_csv.exists():
        for row in _read(building_registry_csv):
            key = (str(row.get("image_id", "")).strip(), str(row.get("base_task_id", "")).strip())
            if not all(key) or key in building_registry:
                raise ValueError("building registry requires unique image_id + base_task_id")
            building_registry[key] = row
    for item in inventory:
        key = (str(item.get("image_id", "")).strip(), str(item.get("base_task_id", "")).strip())
        registry_row = building_registry.get(key, {})
        approved = str(registry_row.get("registry_status", "")).lower() == "approved" and all(
            str(registry_row.get(field, "")).strip() for field in ("building_id", "reviewed_by", "reviewed_at")
        )
        # Never infer or inherit a building from an inventory/task-name
        # convention.  Rehearsal and formal runs use the same evidence rule;
        # only an explicitly approved registry row can set building_id.
        item["building_id"] = registry_row.get("building_id", "") if approved else ""
        item["building_registry_status"] = "approved" if approved else "missing_or_unapproved"
    # C1 calibration support is a task-side, pre-annotation feature table.  Do
    # not derive a model-risk channel from crowd canonical geometry.
    c1_channels: dict[str, list[float]] = {name: [] for name in ("d_model_feat", "d_model_feat_local_max", "g_model_struct", "d_cal_A")}
    c1_by_task: dict[str, dict[str, Any]] = {}
    config_path = _PROJECT_ROOT / contract["feature_freeze"]["config"]
    formal_c1_identity = {
        "checkpoint_sha256": sha256_file(checkpoint) if checkpoint and checkpoint.exists() else "",
        "inference_config_sha256": sha256_file(config_path) if config_path.exists() else "",
        "feature_freeze_manifest_sha256": sha256_file(feature_freeze_manifest) if feature_freeze_manifest and feature_freeze_manifest.exists() else "",
        "building_registry_sha256": sha256_file(building_registry_csv) if building_registry_csv and building_registry_csv.exists() else "",
    }
    for row in _read(c1_task_feature_csv):
        task = str(row.get("base_task_id") or row.get("task_id") or "")
        if not task or task in c1_by_task or str(row.get("preannotation_feature_ready", "")).lower() not in {"true", "1"}:
            continue
        if any(not str(row.get(field, "")).strip() for field in ("checkpoint_sha256", "inference_config_sha256", "layout_output_sha256")):
            continue
        if input_status == "formal" and any(not expected or row.get(field) != expected for field, expected in formal_c1_identity.items()):
            continue
        try:
            pair_count = float(row.get("g_pair_count", ""))
            g_model_struct = min(1.0, abs(pair_count - 6) / 8 + .35 * float(str(row.get("g_topology_invalid", "")).lower() in {"true", "1"}) + .35 * float(str(row.get("g_duplicate_peak", "")).lower() in {"true", "1"}) + .15 * float(row.get("g_seam_instability", "0") or 0) + .15 * float(str(row.get("g_postprocess_invalid", "")).lower() in {"true", "1"}))
            c1_by_task[task] = {"base_task_id": task, "image_id": row.get("image_id", ""), "building_id": row.get("building_id", ""), "g_model_struct": g_model_struct, "d_model_feat": row.get("d_model_feat", ""), "d_model_feat_local_max": row.get("d_model_feat_local", ""), "d_cal_A": row.get("d_cal_A", "")}
        except (TypeError, ValueError):
            continue
    # d_cal_A is a leave-one-C1-task-out distance in the frozen C1 feature
    # space.  It is derived before the reference table is written, so the C1
    # slope fit can never be fed future C2 candidate distances.
    c1_feature_names = ("d_model_feat", "d_model_feat_local_max", "g_model_struct")
    c1_feature_rows = []
    for task, row in c1_by_task.items():
        try:
            c1_feature_rows.append((task, np.asarray([float(row[name]) for name in c1_feature_names], dtype=float)))
        except (KeyError, TypeError, ValueError):
            continue
    if c1_feature_rows:
        c1_matrix = np.stack([vector for _task, vector in c1_feature_rows])
        c1_scale = c1_matrix.std(axis=0); c1_scale[c1_scale == 0] = 1.0
        normalized = c1_matrix / c1_scale
        for index, (task, _vector) in enumerate(c1_feature_rows):
            try:
                float(c1_by_task[task].get("d_cal_A", ""))
            except (TypeError, ValueError):
                peers = np.delete(normalized, index, axis=0)
                c1_by_task[task]["d_cal_A"] = float(np.min(np.linalg.norm(peers - normalized[index], axis=1))) if len(peers) else 0.0
    c1_reference_output = output_dir / "c1_task_risk_reference.csv"
    reference_rows = list(c1_by_task.values())
    c1_channels = {name: [] for name in c1_channels}
    complete_reference_rows = []
    for row in reference_rows:
        vector = {}
        for name in c1_channels:
            try: vector[name] = float(row[name])
            except (KeyError, TypeError, ValueError): pass
        if len(vector) == 4:
            complete_reference_rows.append({"base_task_id": row.get("base_task_id", ""), **vector})
            for name, value in vector.items(): c1_channels[name].append(value)
    channel_scales = {name: (float(np.std(c1_channels[name])) if c1_channels[name] else 1.0) or 1.0 for name in RISK_VECTOR_FIELDS}
    enriched_reference_rows = []
    reference_score_values = []
    for row in reference_rows:
        try:
            numeric = {name: float(row[name]) for name in RISK_VECTOR_FIELDS}
        except (KeyError, TypeError, ValueError):
            numeric = {}
        vector = _frozen_vector(numeric, channel_scales)
        score = _score(vector)
        if score is not None: reference_score_values.append(score)
        enriched_reference_rows.append({
            **row, "reference_eligible": vector is not None,
            "risk_design_vector_A": json.dumps(vector, separators=(",", ":")) if vector is not None else "",
            "risk_design_score_A": "" if score is None else score,
        })
    q75 = float(np.quantile(reference_score_values, stress_quantile)) if reference_score_values else math.nan
    reference_rows = [{
        **row,
        "risk_design_stratum": "stress" if row.get("risk_design_score_A") != "" and float(row["risk_design_score_A"]) >= q75 else "ordinary" if row.get("risk_design_score_A") != "" else "",
    } for row in enriched_reference_rows]
    _write(c1_reference_output, reference_rows)
    (output_dir / "c1_task_risk_reference_manifest.json").write_text(json.dumps({
        "schema_version": "c1_task_risk_reference_v1", "unit": "base_task_id",
        "n_base_tasks": len(reference_rows), "source_preannotation_feature_sha256": sha256_file(c1_task_feature_csv),
        "reference_sha256": sha256_file(c1_reference_output),
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    c1_scores = sorted(row["g_model_struct"] for row in complete_reference_rows if "g_model_struct" in row)
    support_names = ("d_model_feat", "d_model_feat_local_max", "g_model_struct")
    support_matrix = np.asarray(list(zip(*(c1_channels[name] for name in support_names))), dtype=float) if all(c1_channels[name] for name in support_names) and len({len(c1_channels[name]) for name in support_names}) == 1 else np.empty((0, 3))
    support_scale = support_matrix.std(axis=0) if len(support_matrix) else np.ones(3)
    support_scale[support_scale == 0] = 1.0
    if len(support_matrix) and not c1_channels["d_cal_A"]:
        normalized = support_matrix / support_scale
        c1_channels["d_cal_A"] = [float(np.min(np.linalg.norm(np.delete(normalized, index, axis=0) - normalized[index], axis=1))) if len(normalized) > 1 else 0.0 for index in range(len(normalized))]
    feature_status = "not_evaluable_feature_freeze_missing" if input_status == "formal" and not extract_lhfeat else "not_requested"
    candidate_features: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    reference_features: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    ref_global = ref_local = None
    if extract_lhfeat:
        if not checkpoint:
            raise ValueError("checkpoint is required for LHFeat")
        feature_ready = _feature_freeze_ready(feature_freeze_manifest, checkpoint=checkpoint, config=config_path)
        if not feature_ready:
            feature_status = "not_ready_feature_freeze_incomplete"
        else:
            try:
                freeze_payload = json.loads(feature_freeze_manifest.read_text(encoding="utf-8"))
                cache_path = Path(freeze_payload["feature_cache_path"])
                if not cache_path.is_absolute():
                    cache_path = feature_freeze_manifest.parent / cache_path
                candidate_cache_path = Path(freeze_payload["candidate_descriptor_cache_path"])
                if not candidate_cache_path.is_absolute(): candidate_cache_path = feature_freeze_manifest.parent / candidate_cache_path
                with np.load(candidate_cache_path) as candidate_cache:
                    candidate_features = {
                        str(name): (global_value, local_value)
                        for name, global_value, local_value in zip(candidate_cache["paths"], candidate_cache["global_descriptors"], candidate_cache["local_descriptors"])
                    }
                with np.load(cache_path) as cache:
                    ref_global, ref_local = cache["reference_global"], cache["reference_local"]
                    candidate_features = {
                        name: (
                            _apply_whitener(value[0], cache["global_mean"], cache["global_components"], cache["global_scale"]),
                            _apply_whitener(value[1], cache["local_mean"], cache["local_components"], cache["local_scale"]),
                        ) for name, value in candidate_features.items()
                    }
                feature_status = "ready"
            except (OSError, KeyError, ValueError, TypeError, json.JSONDecodeError):
                feature_status = "not_ready_feature_freeze_incomplete"
    if reference_features:
        ref_global = np.stack([value[0] for value in reference_features.values()])
        ref_local = np.stack([value[1] for value in reference_features.values()])
    rows = []
    for item in inventory:
        task = item.get("task_id", "")
        layout_identity = item.get("base_task_id") or task
        layout = _layout_features(layout_dir / f"{layout_identity}.json")
        g = layout.get("g_model_struct")
        d_cal = ""
        source_path = Path(item.get("source_path", ""))
        feature = candidate_features.get(source_path.resolve().as_posix()) if source_path.exists() else None
        global_distance = _knn(feature[0], ref_global) if feature and ref_global is not None else ""
        local_distance = _knn(feature[1], ref_local) if feature and ref_local is not None else ""
        if global_distance != "" and local_distance != "" and g != "" and len(support_matrix):
            vector = np.asarray([global_distance, local_distance, g], dtype=float) / support_scale
            d_cal = _knn(vector, support_matrix / support_scale)
        channels = {"d_model_feat": global_distance, "d_model_feat_local_max": local_distance, "g_model_struct": g, "d_cal_A": d_cal}
        numeric = {name: float(value) for name, value in channels.items() if value != ""}
        vector = _frozen_vector(numeric, channel_scales)
        score = _score(vector)
        reference_scores = [_score(_frozen_vector({name: float(reference.get(name, "")) for name in RISK_VECTOR_FIELDS}, channel_scales)) for reference in complete_reference_rows]
        reference_scores = [value for value in reference_scores if value is not None]
        score_percentile = sum(value <= score for value in reference_scores) / len(reference_scores) if score is not None and reference_scores else None
        bucket = "stress" if score_percentile is not None and score_percentile >= stress_quantile else "ordinary"
        percentiles = {"risk_design_score_A": score_percentile} if score_percentile is not None else {}
        assist_ready = len(numeric) == 4 and all(c1_channels.values()) and layout.get("postprocess_valid") is True
        route_score = ""  # Requires cross-fitted C1 outcomes; model-only Q75 must never impersonate routing risk.
        source_holdout_ready = all(str(item.get(field, "")).lower() in {"true", "1"} for field in ("source_split_allowed", "history_clear", "future_holdout_clear"))
        reference_ready = str(item.get("reference_status") or item.get("geometry_gold_ready") or "").lower() in {"reference_ready", "true", "1"}
        scope_ready = str(item.get("scope_status") or item.get("final_scope") or "").lower() in {"in_scope", "included", "true", "1"}
        risk_design_ready = vector is not None and score is not None and layout.get("postprocess_valid") is True and bool(item.get("building_id"))
        c1_frozen = False
        if c1_freeze_manifest and c1_freeze_manifest.exists():
            try:
                c1_frozen = bool(json.loads(c1_freeze_manifest.read_text(encoding="utf-8")).get("C2B_BASELINE_INPUT_FROZEN"))
            except (OSError, json.JSONDecodeError):
                c1_frozen = False
        design_frozen = input_status == "formal" and c1_frozen and risk_design_ready and feature_status == "ready"
        rows.append({
            **item, **layout, "d_model_feat": global_distance, "d_model_feat_local_max": local_distance,
            "d_cal_A": d_cal, "d_cal_F": "", "d_cal_F_status": "post_c2_only",
            "risk_design_vector_A": json.dumps(vector, separators=(",", ":")) if vector is not None else "",
            "risk_design_score_A": "" if score is None else score,
            "risk_design_A": "",
            "risk_design_A_status": "frozen_from_C1" if design_frozen else "pending_complete_C1" if input_status != "formal" else "not_evaluable",
            "risk_design_stratum": bucket if design_frozen else "",
            "risk_design_stratum_status": "frozen_from_C1" if design_frozen else "provisional_not_frozen" if input_status != "formal" else "not_evaluable",
            "risk_assist_candidate": bucket if assist_ready else "", "risk_route_candidate": route_score,
            "risk_assist_status": "ready" if assist_ready else "not_evaluable", "risk_route_status": "pending_c2b_confirmation",
            "risk_channel_percentiles_json": json.dumps(percentiles, sort_keys=True), "risk_bucket_rule": contract["stratum_rule"]["name"],
            "risk_feature_eligible": design_frozen, "assignment_eligible": False,
            "reference_ready": reference_ready, "scope_ready": scope_ready, "source_holdout_ready": source_holdout_ready,
            "feature_status": feature_status, "checkpoint_sha256": sha256_file(checkpoint) if checkpoint and checkpoint.exists() else "",
            "feature_freeze_manifest_sha256": sha256_file(feature_freeze_manifest) if feature_freeze_manifest and feature_freeze_manifest.exists() else "",
            "risk_contract_sha256": sha256_file(contract_path),
            "risk_status": "candidate_only" if input_status != "formal" else "frozen" if design_frozen else "not_evaluable",
        })
    inventory_output = output_dir / "c2_task_risk_inventory.csv"
    _write(inventory_output, rows)
    eligible_rows = [row for row in rows if row["risk_feature_eligible"]]
    eligible_buildings = {row.get("building_id") for row in eligible_rows if row.get("building_id")}
    eligible_strata = {row.get("risk_design_stratum") for row in eligible_rows}
    c1_state = {}
    if c1_freeze_manifest and c1_freeze_manifest.exists():
        try:
            c1_payload = json.loads(c1_freeze_manifest.read_text(encoding="utf-8"))
            c1_state = {**c1_payload, **c1_payload.get("state_machine", {})}
        except (OSError, json.JSONDecodeError): c1_state = {}
    task_features_frozen = feature_status == "ready"
    # Final pool readiness is owned by the post-eligibility join, not by this
    # feature materializer.  This summary therefore never promotes it.
    formal_ready = False
    summary = {
        "input_status": input_status, "method_contract": contract["method_contract"], "contract_role": "generated_subordinate", "method_contract_version": load_method_contract()["contract_version"], "method_contract_sha256": sha256_file(METHOD_CONTRACT), "n_tasks": len(rows), "n_c1_calibration_tasks": len(reference_rows),
        "n_risk_design_ready": len(eligible_rows), "n_assignment_eligible": 0, "eligible_building_count": len(eligible_buildings),
        "feature_status": feature_status, "formal_ready": formal_ready,
        "C2_TASK_FEATURES_FROZEN": task_features_frozen,
        "C2B_ELIGIBLE_RISK_POOL_FROZEN": False,
        "risk_design_A_status": "frozen_from_C1" if input_status == "formal" and feature_status == "ready" else "pending_complete_C1" if input_status != "formal" else "not_evaluable",
        "risk_design_stratum_status": "frozen_from_C1" if input_status == "formal" and feature_status == "ready" else "provisional_not_frozen" if input_status != "formal" else "not_evaluable",
        "risk_contract_path": str(contract_path), "risk_contract_sha256": sha256_file(contract_path),
        "checkpoint_sha256": sha256_file(checkpoint) if checkpoint and checkpoint.exists() else "",
        "feature_freeze_manifest_sha256": sha256_file(feature_freeze_manifest) if feature_freeze_manifest and feature_freeze_manifest.exists() else "",
        "building_registry_sha256": sha256_file(building_registry_csv) if building_registry_csv and building_registry_csv.exists() else "",
        "config_sha256": sha256_file(_PROJECT_ROOT / contract["feature_freeze"]["config"]) if (_PROJECT_ROOT / contract["feature_freeze"]["config"]).exists() else "",
        "inventory_sha256": sha256_file(inventory_csv), "c1_preannotation_feature_sha256": sha256_file(c1_task_feature_csv),
        "output_inventory_sha256": sha256_file(inventory_output),
        "c1_task_risk_reference_path": str(c1_reference_output), "c1_task_risk_reference_sha256": sha256_file(c1_reference_output),
    }
    summary["state_machine"] = {
        "C1_COLLECTION_INCOMPLETE": bool(c1_state.get("C1_COLLECTION_INCOMPLETE", False)),
        "C1_CANONICAL_CLOSED": bool(c1_state.get("C1_CANONICAL_CLOSED", False)),
        "C1_MEASUREMENT_FROZEN": bool(c1_state.get("C1_MEASUREMENT_FROZEN", False)),
        "C2B_BASELINE_INPUT_FROZEN": bool(c1_state.get("C2B_BASELINE_INPUT_FROZEN", False)),
        "C2_TASK_FEATURES_FROZEN": task_features_frozen,
        "C2B_ELIGIBLE_RISK_POOL_FROZEN": False,
        "C2B_RISK_DESIGN_FROZEN": False,
        "C2B_DESIGN_FROZEN": False,
        "C2B_ASSIGNMENT_MATERIALIZED": False,
        "C2B_LAUNCH_READY": False,
    }
    (output_dir / "c2_task_risk.summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def materialize_formal(
    inventory_csv: Path,
    layout_dir: Path,
    c1_task_feature_csv: Path,
    output_dir: Path,
    *,
    checkpoint: Path,
    feature_freeze_manifest: Path,
    c1_freeze_manifest: Path,
    building_registry_csv: Path,
    device: str = "auto",
) -> dict[str, Any]:
    """Formal risk entry: every freeze dependency is explicit and mandatory."""
    return materialize(
        inventory_csv, layout_dir, c1_task_feature_csv, output_dir,
        input_status="formal", checkpoint=checkpoint, extract_lhfeat=True,
        feature_freeze_manifest=feature_freeze_manifest,
        c1_freeze_manifest=c1_freeze_manifest,
        building_registry_csv=building_registry_csv, device=device,
    )
