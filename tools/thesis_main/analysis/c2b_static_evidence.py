"""C2-B 静态证据、泄漏审计与非支配 split 候选工具。"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from tools.thesis_main.analysis.vfinal_artifact_utils import sha256_file


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _write(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = fields or list(dict.fromkeys(key for row in rows for key in row)) or ["status"]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader(); writer.writerows(rows)


def _aggregate(rows: Iterable[dict[str, Any]]) -> str:
    payload = json.dumps(list(rows), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def candidate_scene_mapping_key(row: dict[str, Any]) -> tuple[str, str]:
    """Return a review key, never an authoritative building_id."""
    explicit = str(row.get("scene_id") or row.get("scene_key") or "").strip()
    if explicit:
        scene, source = explicit, "explicit_inventory_scene_key"
    else:
        stem = Path(str(row.get("source_path", ""))).stem
        scene = stem.split("_", 1)[0] if "_" in stem else stem
        source = "filename_scene_key_candidate_requires_human_validation"
    return f"{row.get('source_pool', '')}|{scene}", source


def _file_rows(paths: Iterable[Path], *, role: str) -> list[dict[str, Any]]:
    rows = []
    for path in sorted((item.resolve() for item in paths), key=lambda item: item.as_posix().casefold()):
        rows.append({
            "role": role, "normalized_path": path.as_posix().casefold(), "path": path.as_posix(),
            "size": path.stat().st_size, "sha256": sha256_file(path),
        })
    return rows


def materialize_p1_integrity_bundle(directory: Path) -> dict[str, Any]:
    required = {
        "p1_post_closeout_correction_summary_v1.json",
        "p1_geometry_score_summary_v1.json",
        "p1_task_evidence_correction_v1.csv",
        "p1_worker_evidence_status_v1.csv",
        "p1_geometry_task_scores_v1.csv",
        "p1_worker_geometry_profile_v1.csv",
    }
    missing = sorted(name for name in required if not (directory / name).exists())
    if missing:
        raise ValueError(f"P1 integrity bundle is incomplete:{','.join(missing)}")
    files = sorted(
        (path for path in directory.iterdir() if path.is_file() and path.name != "p1_integrity_bundle_manifest.json"),
        key=lambda path: path.name,
    )
    rows = [{"name": path.name, "size": path.stat().st_size, "sha256": sha256_file(path)} for path in files]
    status_rows = {
        str(row.get("worker_id", "")).strip(): row
        for row in _read(directory / "p1_worker_evidence_status_v1.csv")
        if str(row.get("worker_id", "")).strip()
    }
    predictive_workers: list[str] = []
    for row in _read(directory / "p1_worker_geometry_profile_v1.csv"):
        worker = str(row.get("worker_id", "")).strip()
        try:
            component = float(row.get("p1_geometry_component", ""))
        except (TypeError, ValueError):
            continue
        if (
            worker in status_rows and math.isfinite(component)
            and str(status_rows[worker].get("p1_predictive_capability_eligible", "")).lower() in {"true", "1"}
            and str(row.get("p1_geometry_support_status", "")).lower() == "sufficient"
        ):
            predictive_workers.append(worker)
    predictive_workers = sorted(set(predictive_workers))
    predictive_ready = len(predictive_workers) >= 3
    payload = {
        "schema_version": "paper_a_p1_integrity_bundle_v1",
        "bundle_status": "frozen",
        "P1_INTEGRITY_BUNDLE_FROZEN": True,
        "P1_PREDICTIVE_EVIDENCE_READY": predictive_ready,
        "p1_predictive_eligible_worker_count": len(predictive_workers),
        "p1_predictive_minimum_worker_count": 3,
        "p1_predictive_ready_basis": "at_least_three_integrity_eligible_workers_with_sufficient_numeric_geometry_component",
        "p1_predictive_not_ready_action": "disable_P1_predictive_component_without_blocking_risk_only_C2B" if not predictive_ready else "enabled",
        "required_files": sorted(required),
        "files": rows,
        "aggregate_sha256": _aggregate(rows),
    }
    (directory / "p1_integrity_bundle_manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    return payload


def validate_p1_integrity_bundle(directory: Path | None) -> dict[str, Any]:
    if directory is None:
        return {"status": "not_evaluable_missing_p1_integrity", "valid": False, "reason": "directory_not_provided"}
    manifest = directory / "p1_integrity_bundle_manifest.json"
    if not manifest.exists():
        return {"status": "not_evaluable_missing_p1_integrity", "valid": False, "reason": "manifest_missing"}
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        if payload.get("schema_version") != "paper_a_p1_integrity_bundle_v1" or payload.get("bundle_status") != "frozen":
            raise ValueError("unsupported_or_unfrozen_manifest")
        actual = []
        for row in payload.get("files", []):
            path = directory / str(row.get("name", ""))
            if not path.exists() or path.stat().st_size != int(row.get("size", -1)) or sha256_file(path) != row.get("sha256"):
                raise ValueError(f"stale:{path.name}")
            actual.append({"name": path.name, "size": path.stat().st_size, "sha256": sha256_file(path)})
        if not actual or _aggregate(actual) != payload.get("aggregate_sha256"):
            raise ValueError("aggregate_mismatch")
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return {"status": "invalid_p1_integrity_bundle", "valid": False, "reason": str(exc)}
    return {
        "status": "validated", "valid": True, "manifest_sha256": sha256_file(manifest),
        "aggregate_sha256": payload["aggregate_sha256"], "file_count": len(actual),
        "P1_INTEGRITY_BUNDLE_FROZEN": payload.get("P1_INTEGRITY_BUNDLE_FROZEN") is True,
        "P1_PREDICTIVE_EVIDENCE_READY": payload.get("P1_PREDICTIVE_EVIDENCE_READY") is True,
        "p1_predictive_eligible_worker_count": int(payload.get("p1_predictive_eligible_worker_count", 0)),
        "p1_predictive_minimum_worker_count": int(payload.get("p1_predictive_minimum_worker_count", 3)),
    }


def materialize_history_overlap(
    inventory_csv: Path, p1_canonical_csv: Path, c1_assignment_csvs: list[Path], output_csv: Path,
) -> dict[str, Any]:
    history: set[tuple[str, str]] = set()
    sources: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in _read(p1_canonical_csv):
        key = (str(row.get("image_id") or row.get("base_task_id") or "").strip(), str(row.get("base_task_id") or row.get("task_id") or "").strip())
        if any(key):
            history.add(key); sources[key].add("P1_resolved_identity")
    for path in c1_assignment_csvs:
        for row in _read(path):
            key = (str(row.get("image_id") or row.get("base_task_id") or "").strip(), str(row.get("base_task_id") or row.get("task_id") or "").strip())
            if any(key):
                history.add(key); sources[key].add(f"C1_assignment:{path.name}")
    rows = []
    for row in _read(inventory_csv):
        image, task = str(row.get("image_id", "")).strip(), str(row.get("base_task_id", "")).strip()
        matching = {
            key for key in history
            if (image and image == key[0]) or (task and task == key[1])
        }
        provenance = sorted({value for key in matching for value in sources[key]})
        rows.append({
            "image_id": image, "base_task_id": task, "task_id": row.get("task_id", ""),
            "history_overlap": bool(matching), "history_clear": not bool(matching),
            "history_source": ";".join(provenance), "evidence_status": "derived_from_P1_C1_truth",
        })
    _write(output_csv, rows)
    return {
        "n_tasks": len(rows), "n_history_overlap": sum(bool(row["history_overlap"]) for row in rows),
        "inventory_sha256": sha256_file(inventory_csv), "p1_identity_evidence_sha256": sha256_file(p1_canonical_csv),
        "c1_assignment_sha256": {path.name: sha256_file(path) for path in c1_assignment_csvs},
        "output_sha256": sha256_file(output_csv),
    }


def materialize_building_registry_from_scene_mapping(
    inventory_csv: Path, approved_scene_mapping_csv: Path, output_csv: Path,
) -> dict[str, Any]:
    """Expand only explicitly approved scene-key mappings; unresolved tasks stay visible."""
    mappings: dict[str, dict[str, str]] = {}
    for row in _read(approved_scene_mapping_csv):
        key = str(row.get("scene_mapping_key", "")).strip()
        approved = (
            key and str(row.get("registry_status", "")).lower() == "approved"
            and all(str(row.get(field, "")).strip() for field in ("building_id", "reviewed_by", "reviewed_at"))
        )
        if not approved:
            continue
        if key in mappings and mappings[key].get("building_id") != row.get("building_id"):
            raise ValueError(f"conflicting approved scene mapping:{key}")
        mappings[key] = row
    rows = []
    for item in _read(inventory_csv):
        key, _key_source = candidate_scene_mapping_key(item)
        mapping = mappings.get(key, {})
        rows.append({
            "image_id": item.get("image_id", ""), "base_task_id": item.get("base_task_id", ""),
            "task_id": item.get("task_id", ""), "scene_mapping_key": key,
            "building_id": mapping.get("building_id", ""),
            "registry_status": "approved" if mapping else "unresolved_scene_mapping",
            "reviewed_by": mapping.get("reviewed_by", ""), "reviewed_at": mapping.get("reviewed_at", ""),
            "scene_mapping_manifest_sha256": sha256_file(approved_scene_mapping_csv),
        })
    _write(output_csv, rows)
    unresolved = [row for row in rows if row["registry_status"] != "approved"]
    _write(output_csv.with_name("authoritative_building_registry.unresolved_review_queue.csv"), unresolved)
    return {
        "n_tasks": len(rows), "n_approved": len(rows) - len(unresolved), "n_unresolved": len(unresolved),
        "formal_registry_ready": bool(rows) and not unresolved,
        "scene_mapping_sha256": sha256_file(approved_scene_mapping_csv), "output_sha256": sha256_file(output_csv),
    }


def materialize_reference_candidate_leakage(
    reference_image_dir: Path, reference_layout_dir: Path, inventory_csv: Path,
    candidate_layout_dir: Path, output_dir: Path,
) -> dict[str, Any]:
    reference_images = [path for path in reference_image_dir.rglob("*") if path.is_file()]
    reference_layouts = [path for path in reference_layout_dir.rglob("*") if path.is_file()]
    inventory = _read(inventory_csv)
    candidate_images = [Path(str(row.get("source_path", ""))) for row in inventory]
    candidate_layouts = [candidate_layout_dir / f"{row.get('base_task_id', '')}.json" for row in inventory]
    missing = [path.as_posix() for path in [*candidate_images, *candidate_layouts] if not path.exists()]
    if missing:
        raise ValueError(f"candidate leakage audit requires complete image/layout files:{missing[:5]}")
    listings = {
        "reference_image": _file_rows(reference_images, role="reference_image"),
        "reference_layout": _file_rows(reference_layouts, role="reference_layout"),
        "candidate_image": _file_rows(candidate_images, role="candidate_image"),
        "candidate_layout": _file_rows(candidate_layouts, role="candidate_layout"),
    }
    for role, rows in listings.items():
        _write(output_dir / f"c2b_{role}_file_listing.csv", rows)
    reference_paths = {row["normalized_path"] for role in ("reference_image", "reference_layout") for row in listings[role]}
    reference_hashes = {row["sha256"] for role in ("reference_image", "reference_layout") for row in listings[role]}
    candidate_seen_paths: set[str] = set()
    candidate_seen_hashes: set[str] = set()
    audit_rows = []
    for role in ("candidate_image", "candidate_layout"):
        for row in listings[role]:
            path_overlap = row["normalized_path"] in reference_paths
            content_overlap = row["sha256"] in reference_hashes
            duplicate_candidate_path = row["normalized_path"] in candidate_seen_paths
            duplicate_candidate_content = row["sha256"] in candidate_seen_hashes
            reasons = []
            if path_overlap: reasons.append("reference_candidate_normalized_path_overlap")
            if content_overlap: reasons.append("reference_candidate_content_sha_overlap")
            if duplicate_candidate_path: reasons.append("duplicate_candidate_normalized_path")
            if duplicate_candidate_content: reasons.append("duplicate_candidate_content_sha")
            candidate_seen_paths.add(row["normalized_path"]); candidate_seen_hashes.add(row["sha256"])
            audit_rows.append({**row, "leakage_clear": not reasons, "leakage_reason": ";".join(reasons)})
    audit_csv = output_dir / "c2b_reference_candidate_leakage_audit.csv"
    _write(audit_csv, audit_rows)
    reference_complete = bool(listings["reference_image"]) and bool(listings["reference_layout"])
    passed = reference_complete and bool(audit_rows) and not any(row["leakage_reason"] for row in audit_rows)
    summary = {
        "schema_version": "paper_a_c2b_reference_candidate_leakage_v1",
        "status": "passed" if passed else "failed",
        "formal_feature_pool_allowed": passed,
        "inventory_sha256": sha256_file(inventory_csv),
        "listing_aggregate_sha256": {role: _aggregate(rows) for role, rows in listings.items()},
        "leakage_audit_csv_sha256": sha256_file(audit_csv),
        "n_candidate_files": len(audit_rows),
        "reference_image_count": len(listings["reference_image"]),
        "reference_layout_count": len(listings["reference_layout"]),
        "reference_listing_complete": reference_complete,
        "n_leakage_or_duplicate": sum(bool(row["leakage_reason"]) for row in audit_rows),
    }
    summary_path = output_dir / "c2b_reference_candidate_leakage_audit.summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def materialize_static_model_risk(feature_manifest: Path, inventory_csv: Path, output_csv: Path) -> dict[str, Any]:
    manifest = json.loads(feature_manifest.read_text(encoding="utf-8"))
    reference_cache = Path(str(manifest["feature_cache_path"]))
    candidate_cache = Path(str(manifest["candidate_descriptor_cache_path"]))
    reference = np.load(reference_cache)
    candidate = np.load(candidate_cache)
    transformed_global = ((candidate["global_descriptors"] - reference["global_mean"]) @ reference["global_components"].T) / reference["global_scale"]
    transformed_local = ((candidate["local_descriptors"] - reference["local_mean"]) @ reference["local_components"].T) / reference["local_scale"]

    def knn(vector: np.ndarray, matrix: np.ndarray, k: int = 5) -> float:
        distances = np.linalg.norm(matrix - vector[None], axis=1)
        return float(np.mean(np.partition(distances, min(k, len(distances)) - 1)[:min(k, len(distances))]))

    path_to_score = {
        str(path): (knn(transformed_global[index], reference["reference_global"]), knn(transformed_local[index], reference["reference_local"]))
        for index, path in enumerate(candidate["paths"])
    }
    rows = []
    for row in _read(inventory_csv):
        resolved = Path(row["source_path"]).resolve().as_posix()
        global_score, local_score = path_to_score[resolved]
        rows.append({
            "image_id": row.get("image_id", ""), "base_task_id": row.get("base_task_id", ""), "task_id": row.get("task_id", ""),
            "d_model_feat_static": global_score, "d_model_feat_local_max_static": local_score,
            "static_model_risk_score": math.hypot(global_score, local_score),
        })
    _write(output_csv, rows)
    return {"n_tasks": len(rows), "output_sha256": sha256_file(output_csv), "uses_c1_outcomes": False}


def materialize_split_proposals(
    inventory_csv: Path, history_csv: Path, building_registry_csv: Path, static_risk_csv: Path,
    output_dir: Path, *, seed: int = 20260726, holdout_fraction: float = 0.30, proposal_count: int = 3,
) -> dict[str, Any]:
    if not 0 < holdout_fraction < 1 or proposal_count < 2:
        raise ValueError("split proposal contract requires 0<holdout_fraction<1 and at least two proposals")
    history = {(row.get("image_id", ""), row.get("base_task_id", "")): row for row in _read(history_csv)}
    buildings = {(row.get("image_id", ""), row.get("base_task_id", "")): row for row in _read(building_registry_csv)}
    risk = {(row.get("image_id", ""), row.get("base_task_id", "")): row for row in _read(static_risk_csv)}
    eligible = []
    for row in _read(inventory_csv):
        key = (row.get("image_id", ""), row.get("base_task_id", ""))
        building = buildings.get(key, {})
        approved = str(building.get("registry_status", "")).lower() == "approved" and all(str(building.get(field, "")).strip() for field in ("building_id", "reviewed_by", "reviewed_at"))
        if str(history.get(key, {}).get("history_overlap", "")).lower() in {"true", "1"} or not approved or key not in risk:
            continue
        eligible.append({**row, "building_id": building["building_id"], "static_model_risk_score": float(risk[key]["static_model_risk_score"])})
    if not eligible:
        raise ValueError("no history-clear tasks with approved building and static risk evidence")
    cutoff = float(np.quantile([row["static_model_risk_score"] for row in eligible], .75))
    for row in eligible:
        row["static_risk_stratum"] = "stress" if row["static_model_risk_score"] >= cutoff else "ordinary"
    holdout_count = max(1, min(len(eligible) - 1, round(len(eligible) * holdout_fraction)))
    candidate_sets: dict[tuple[str, ...], dict[str, Any]] = {}
    pool_risk_mean = sum(row["static_model_risk_score"] for row in eligible) / len(eligible)
    pool_building_counts = Counter(row["building_id"] for row in eligible)
    for proposal_index in range(max(32, proposal_count * 16)):
        rng = random.Random(f"{seed}|{proposal_index}")
        buckets: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for row in eligible:
            buckets[(row["building_id"], row["static_risk_stratum"])].append(row)
        ordered = []
        for key in sorted(buckets):
            values = buckets[key][:]
            rng.shuffle(values)
            ordered.extend(values)
        rng.shuffle(ordered)
        selected = {row["base_task_id"] for row in ordered[:holdout_count]}
        signature = tuple(sorted(selected))
        if signature in candidate_sets:
            continue
        selected_rows = [row for row in eligible if row["base_task_id"] in selected]
        risks = [row["static_model_risk_score"] for row in selected_rows]
        selected_buildings = Counter(row["building_id"] for row in selected_rows)
        building_distribution_error = sum(
            abs(selected_buildings[building] / holdout_count - count / len(eligible))
            for building, count in pool_building_counts.items()
        )
        candidate_sets[signature] = {
            "signature": signature, "selected": selected,
            "building_coverage": len(selected_buildings),
            "ordinary_count": sum(row["static_risk_stratum"] == "ordinary" for row in selected_rows),
            "stress_count": sum(row["static_risk_stratum"] == "stress" for row in selected_rows),
            "risk_range": max(risks) - min(risks) if len(risks) > 1 else 0.0,
            "risk_mean_error": abs(sum(risks) / len(risks) - pool_risk_mean),
            "building_distribution_error": building_distribution_error,
        }

    def dominates(left: dict[str, Any], right: dict[str, Any]) -> bool:
        left_values = (
            -left["building_coverage"], -left["ordinary_count"], -left["stress_count"],
            -left["risk_range"], left["risk_mean_error"], left["building_distribution_error"],
        )
        right_values = (
            -right["building_coverage"], -right["ordinary_count"], -right["stress_count"],
            -right["risk_range"], right["risk_mean_error"], right["building_distribution_error"],
        )
        return all(left_value <= right_value for left_value, right_value in zip(left_values, right_values)) and any(
            left_value < right_value for left_value, right_value in zip(left_values, right_values)
        )

    frontier = [
        candidate for candidate in candidate_sets.values()
        if not any(dominates(other, candidate) for other in candidate_sets.values() if other is not candidate)
    ]
    frontier.sort(key=lambda candidate: candidate["signature"])
    selected_candidates = frontier[:proposal_count]
    if len(selected_candidates) < 2:
        raise ValueError("unable to produce multiple non-dominated split candidates")
    proposal_rows, audit_rows = [], []
    for proposal_number, candidate in enumerate(selected_candidates, 1):
        proposal_id = f"split_candidate_{proposal_number:02d}"
        selected = candidate["selected"]
        for row in eligible:
            proposal_rows.append({
                "proposal_id": proposal_id, "seed": seed, "image_id": row.get("image_id", ""),
                "base_task_id": row.get("base_task_id", ""), "task_id": row.get("task_id", ""),
                "building_id": row["building_id"], "static_risk_stratum": row["static_risk_stratum"],
                "static_model_risk_score": row["static_model_risk_score"],
                "allocation": "future_holdout" if row["base_task_id"] in selected else "c2_source",
                "history_clear": True,
            })
        audit_rows.append({
            "proposal_id": proposal_id, "seed": seed, "eligible_task_count": len(eligible),
            "c2_source_count": len(eligible) - holdout_count, "future_holdout_count": holdout_count,
            "future_holdout_building_count": candidate["building_coverage"],
            "future_holdout_ordinary_count": candidate["ordinary_count"],
            "future_holdout_stress_count": candidate["stress_count"],
            "future_holdout_risk_range": candidate["risk_range"],
            "future_holdout_risk_mean_error": candidate["risk_mean_error"],
            "building_distribution_error": candidate["building_distribution_error"],
            "source_holdout_disjoint": True, "history_overlap_count": 0, "non_dominated": True,
        })
    proposal_path = output_dir / "c2b_source_holdout_split_proposals.csv"
    audit_path = output_dir / "c2b_source_holdout_split_disjointness_audit.csv"
    _write(proposal_path, proposal_rows)
    _write(audit_path, audit_rows)
    summary = {
        "schema_version": "paper_a_c2b_split_proposals_v1", "status": "candidate_only",
        "selected_proposal_id": "", "approval_materialized": False, "seed": seed,
        "holdout_fraction": holdout_fraction, "proposal_count": len(selected_candidates),
        "all_candidates_non_dominated": True, "generated_candidate_count": len(candidate_sets),
        "history_sha256": sha256_file(history_csv), "building_registry_sha256": sha256_file(building_registry_csv),
        "static_risk_sha256": sha256_file(static_risk_csv),
        "proposal_rows_sha256": sha256_file(proposal_path), "disjointness_audit_sha256": sha256_file(audit_path),
    }
    (output_dir / "c2b_source_holdout_split_proposals.summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def materialize_static_freeze_manifest(output_dir: Path, artifacts: dict[str, Path], *, code_sha256: str) -> dict[str, Any]:
    bound = {
        name: {"path": path.resolve().as_posix(), "sha256": sha256_file(path)}
        for name, path in artifacts.items() if path.exists()
    }
    required = {
        "p1_integrity", "feature_freeze", "leakage_audit", "leakage_audit_rows",
        "reference_image_listing", "reference_layout_listing",
        "candidate_image_listing", "candidate_layout_listing",
        "split_proposals", "split_proposal_rows", "split_disjointness_audit", "environment",
    }
    missing = sorted(required - set(bound))
    blockers = [f"missing:{name}" for name in missing]

    def load(name: str) -> dict[str, Any]:
        if name not in bound:
            return {}
        try:
            return json.loads(Path(bound[name]["path"]).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError):
            blockers.append(f"invalid_json:{name}")
            return {}

    p1 = load("p1_integrity")
    feature = load("feature_freeze")
    leakage = load("leakage_audit")
    split = load("split_proposals")
    if p1 and (p1.get("schema_version") != "paper_a_p1_integrity_bundle_v1" or p1.get("bundle_status") != "frozen"):
        blockers.append("p1_integrity_not_frozen")
    if feature and (
        feature.get("schema_version") != "paper_a_c2_feature_freeze_v2"
        or feature.get("feature_audit_status") != "approved"
        or feature.get("off_grid_circular_robustness") is not True
    ):
        blockers.append("feature_freeze_not_approved")
    if leakage and (leakage.get("status") != "passed" or leakage.get("formal_feature_pool_allowed") is not True):
        blockers.append("reference_candidate_leakage_not_clear")
    if feature and leakage and feature.get("reference_candidate_leakage_audit_sha256") != bound["leakage_audit"]["sha256"]:
        blockers.append("feature_leakage_sha_not_bound")
    if split and (split.get("status") != "candidate_only" or split.get("approval_materialized") is not False):
        blockers.append("split_proposals_not_candidate_only")
    if split and (
        split.get("proposal_rows_sha256") != bound.get("split_proposal_rows", {}).get("sha256")
        or split.get("disjointness_audit_sha256") != bound.get("split_disjointness_audit", {}).get("sha256")
    ):
        blockers.append("split_proposal_artifacts_sha_not_bound")
    if not str(code_sha256).strip():
        blockers.append("code_sha256_missing")
    payload = {
        "schema_version": "paper_a_c2b_static_freeze_manifest_v1", "artifact_owner": "prepare-c2b-static",
        "artifacts": bound, "code_sha256": code_sha256, "missing_required_artifacts": missing,
        "freeze_blockers": sorted(set(blockers)),
        "static_evidence_frozen": not blockers,
    }
    path = output_dir / "c2b_static_freeze_manifest.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload
