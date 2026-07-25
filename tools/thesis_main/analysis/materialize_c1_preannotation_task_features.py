"""Bind C1 task identities to frozen pre-annotation model features.

No crowd geometry is read here.  Missing frozen model evidence is represented as
not-evaluable, never reconstructed from an annotation.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import numpy as np

from tools.thesis_main.analysis.c1_live_collection_monitor import read_csv, write_csv, write_json
from tools.thesis_main.analysis.materialize_c2_task_risk import (
    _apply_whitener,
    _feature_freeze_ready,
    _knn,
    _layout_features,
    _lhfeat_descriptors,
)
from tools.thesis_main.analysis.vfinal_artifact_utils import sha256_file


REQUIRED = ("d_model_feat", "d_model_feat_local", "g_pair_count", "g_topology_invalid", "g_duplicate_peak", "g_seam_instability", "g_postprocess_invalid")
FROZEN_IDENTITY = (
    "checkpoint_sha256", "inference_config_sha256", "layout_output_sha256",
    "feature_freeze_manifest_sha256", "building_registry_sha256",
)


def _unique(rows: list[dict[str, str]], fields: tuple[str, ...], source: str) -> dict[tuple[str, ...], dict[str, str]]:
    result: dict[tuple[str, ...], dict[str, str]] = {}
    for row in rows:
        key = tuple(str(row.get(field, "")).strip() for field in fields)
        if not all(key) or key in result:
            raise ValueError(f"{source} requires unique non-empty {'+'.join(fields)}")
        result[key] = row
    return result


def extract_frozen_model_features(
    assignment_csvs: list[Path], inventory_csv: Path, building_registry_csv: Path,
    layout_dir: Path, checkpoint: Path, config: Path, feature_freeze_manifest: Path,
    output_csv: Path, *, device: str = "auto",
) -> dict[str, Any]:
    """Create the one pre-annotation C1 feature table from frozen model evidence."""
    if not _feature_freeze_ready(
        feature_freeze_manifest, checkpoint=checkpoint, config=config,
    ):
        raise ValueError("feature_freeze_manifest_not_ready_or_sha_mismatch")
    manifest = json.loads(feature_freeze_manifest.read_text(encoding="utf-8"))
    cache_path = Path(str(manifest["feature_cache_path"]))
    if not cache_path.is_absolute():
        cache_path = feature_freeze_manifest.parent / cache_path

    inventory_rows = read_csv(inventory_csv)
    inventory = _unique(inventory_rows, ("base_task_id",), "inventory")
    buildings = _unique(read_csv(building_registry_csv), ("image_id", "base_task_id"), "building registry")
    task_ids = sorted({
        str(row.get("base_task_id") or "").strip()
        for path in assignment_csvs for row in read_csv(path)
    } - {""})
    paths: list[Path] = []
    joined: list[tuple[str, dict[str, str], dict[str, str], Path, Path]] = []
    for base_task_id in task_ids:
        item = inventory.get((base_task_id,))
        if not item:
            raise ValueError(f"inventory_missing_base_task:{base_task_id}")
        image_id = str(item.get("image_id", "")).strip()
        building = buildings.get((image_id, base_task_id))
        if not building or str(building.get("registry_status", "")).lower() != "approved" or not all(
            str(building.get(field, "")).strip() for field in ("building_id", "reviewed_by", "reviewed_at")
        ):
            raise ValueError(f"authoritative_building_missing_or_unapproved:{base_task_id}")
        image_path, layout_path = Path(str(item.get("source_path", ""))), layout_dir / f"{base_task_id}.json"
        if not image_path.exists() or not layout_path.exists():
            raise ValueError(f"preannotation_source_or_layout_missing:{base_task_id}")
        paths.append(image_path)
        joined.append((base_task_id, item, building, image_path, layout_path))

    descriptors = _lhfeat_descriptors(paths, checkpoint, config=config, device=device)
    rows: list[dict[str, Any]] = []
    with np.load(cache_path) as cache:
        for base_task_id, item, building, image_path, layout_path in joined:
            raw_global, raw_local = descriptors[image_path.resolve().as_posix()]
            global_feature = _apply_whitener(raw_global, cache["global_mean"], cache["global_components"], cache["global_scale"])
            local_feature = _apply_whitener(raw_local, cache["local_mean"], cache["local_components"], cache["local_scale"])
            layout = _layout_features(layout_path)
            ready = layout.get("layout_status") == "ready" and layout.get("postprocess_valid") is True
            rows.append({
                "base_task_id": base_task_id,
                "task_id": item.get("task_id", ""),
                "image_id": item.get("image_id", ""),
                "building_id": building["building_id"],
                "d_model_feat": _knn(global_feature, cache["reference_global"]),
                "d_model_feat_local": _knn(local_feature, cache["reference_local"]),
                "g_pair_count": layout.get("pair_count", ""),
                "g_topology_invalid": not bool(layout.get("topology_valid")),
                "g_duplicate_peak": bool(layout.get("duplicate_wall_peak")),
                "g_seam_instability": layout.get("seam_instability", ""),
                "g_postprocess_invalid": not bool(layout.get("postprocess_valid")),
                "checkpoint_sha256": sha256_file(checkpoint),
                "inference_config_sha256": sha256_file(config),
                "layout_output_sha256": sha256_file(layout_path),
                "building_registry_sha256": sha256_file(building_registry_csv),
                "feature_freeze_manifest_sha256": sha256_file(feature_freeze_manifest),
                "preannotation_feature_ready": ready,
                "exclusion_reason": "" if ready else "layout_not_ready",
            })
    write_csv(output_csv, rows)
    summary = {
        "schema_version": "paper_a_c1_preannotation_feature_extract_v1",
        "n_tasks": len(rows),
        "n_ready": sum(bool(row["preannotation_feature_ready"]) for row in rows),
        "assignment_sha256": {path.name: sha256_file(path) for path in assignment_csvs},
        "inventory_sha256": sha256_file(inventory_csv),
        "building_registry_sha256": sha256_file(building_registry_csv),
        "feature_freeze_manifest_sha256": sha256_file(feature_freeze_manifest),
        "output_sha256": sha256_file(output_csv),
        "human_geometry_used": False,
    }
    write_json(output_csv.with_suffix(".manifest.json"), summary)
    return summary


def materialize(
    assignment_csvs: list[Path], inventory_csv: Path, output_dir: Path, *,
    frozen_feature_csv: Path | None = None,
) -> dict[str, Any]:
    inventory = {str(row.get("base_task_id") or row.get("task_id") or ""): row for row in read_csv(inventory_csv)}
    features = {str(row.get("base_task_id") or row.get("task_id") or ""): row for row in read_csv(frozen_feature_csv)} if frozen_feature_csv and frozen_feature_csv.exists() else {}
    task_ids = sorted({str(row.get("base_task_id") or row.get("task_id") or "") for path in assignment_csvs for row in read_csv(path)} - {""})
    rows: list[dict[str, Any]] = []
    for base_task_id in task_ids:
        inventory_row, feature = inventory.get(base_task_id, {}), features.get(base_task_id, {})
        image_id = str(feature.get("image_id") or inventory_row.get("image_id") or "")
        building_id = str(feature.get("building_id") or inventory_row.get("building_id") or "")
        complete = bool(feature) and all(str(feature.get(field, "")).strip() for field in (*REQUIRED, *FROZEN_IDENTITY)) and bool(image_id and building_id)
        rows.append({
            "base_task_id": base_task_id, "image_id": image_id, "building_id": building_id,
            **{field: feature.get(field, "") for field in REQUIRED},
            "checkpoint_sha256": feature.get("checkpoint_sha256", ""),
            "inference_config_sha256": feature.get("inference_config_sha256", ""),
            "layout_output_sha256": feature.get("layout_output_sha256", ""),
            "feature_freeze_manifest_sha256": feature.get("feature_freeze_manifest_sha256", ""),
            "building_registry_sha256": feature.get("building_registry_sha256", ""),
            "feature_source": "frozen_preannotation_model" if feature else "missing_frozen_preannotation_model",
            "preannotation_feature_ready": complete,
            "exclusion_reason": "" if complete else "missing_feature_or_frozen_model_identity_or_task_identity",
        })
    output = output_dir / "c1_preannotation_task_features.csv"
    write_csv(output, rows)
    summary = {
        "schema_version": "paper_a_preannotation_task_features_v1", "unit": "base_task_id",
        "n_tasks": len(rows), "n_ready": sum(str(row["preannotation_feature_ready"]).lower() in {"true", "1"} for row in rows),
        "input_inventory_sha256": sha256_file(inventory_csv),
        "frozen_feature_sha256": sha256_file(frozen_feature_csv) if frozen_feature_csv and frozen_feature_csv.exists() else "",
        "output_sha256": sha256_file(output), "human_geometry_used": False,
    }
    write_json(output_dir / "c1_preannotation_task_features_manifest.json", summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--assignment-csv", type=Path, action="append", required=True)
    parser.add_argument("--inventory-csv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--frozen-feature-csv", type=Path)
    parser.add_argument("--building-registry-csv", type=Path)
    parser.add_argument("--layout-dir", type=Path)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--feature-freeze-manifest", type=Path)
    parser.add_argument("--device", default="auto")
    args = parser.parse_args(argv)
    frozen_feature_csv = args.frozen_feature_csv
    producer_args = (args.building_registry_csv, args.layout_dir, args.checkpoint, args.config, args.feature_freeze_manifest)
    if any(producer_args):
        if not all(producer_args):
            parser.error("feature extraction requires building registry, layout dir, checkpoint, config, and feature freeze manifest")
        frozen_feature_csv = args.output_dir / "c1_frozen_preannotation_model_features.csv"
        extract_frozen_model_features(
            args.assignment_csv, args.inventory_csv, args.building_registry_csv, args.layout_dir,
            args.checkpoint, args.config, args.feature_freeze_manifest, frozen_feature_csv,
            device=args.device,
        )
    print(json.dumps(materialize(args.assignment_csv, args.inventory_csv, args.output_dir, frozen_feature_csv=frozen_feature_csv), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
