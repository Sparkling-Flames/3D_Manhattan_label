"""Prepare the validation-only C2-B inventory and its auditable registries."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = list(dict.fromkeys(key for row in rows for key in row))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _ids(path: Path) -> set[str]:
    return {row["base_task_id"].strip() for row in _read_csv(path) if row.get("base_task_id", "").strip()}


def _portable_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _prediction_to_layout(source: Path, destination: Path, stem: str) -> None:
    points = [tuple(map(float, line.split())) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(points) < 4 or len(points) % 2:
        raise ValueError(f"invalid HoHoNet prediction point count: {source}")
    corners = []
    for index in range(0, len(points), 2):
        (x1, y1), (x2, y2) = points[index:index + 2]
        if abs(x1 - x2) > 1 or y1 == y2:
            raise ValueError(f"invalid ceiling/floor pair: {source}:{index + 1}")
        corners.append({
            "x": (x1 + x2) / 2,
            "y_ceiling": min(y1, y2),
            "y_floor": max(y1, y2),
        })
    corners.sort(key=lambda row: row["x"])
    for index, corner in enumerate(corners):
        corner["id"] = index
    payload = {
        "image_filename": f"{stem}.png",
        "image_size": [2048, 1024],
        "layout": {"corners": corners, "num_corners": len(corners), "order": "sorted_x_cyclic"},
        "meta": {
            "source": "hohonet_ep300",
            "config": "config/mp3d_layout/HOHO_layout_aug_efficienthc_Transen1_resnet34.yaml",
            "coordinate_space": "hohonet_model_1024x512",
        },
    }
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def prepare(
    *, full_inventory: Path, c1_assignments: list[Path], legacy_manifest: Path,
    c1_building_registry: Path, validation_image_dir: Path, validation_reference_dir: Path,
    validation_prediction_dir: Path, existing_layout_dir: Path, output_dir: Path,
    image_base_url: str, reviewed_at: str,
) -> dict[str, Any]:
    full_rows = _read_csv(full_inventory)
    full_by_id = {row["base_task_id"]: row for row in full_rows}
    c1_ids = set().union(*(_ids(path) for path in c1_assignments))
    legacy_ids = _ids(legacy_manifest)
    validation_images = sorted(validation_image_dir.glob("*.png"))
    validation_ids = {path.stem for path in validation_images}
    reference_ids = {path.stem for path in validation_reference_dir.glob("*.txt")}
    prediction_ids = {path.stem for path in validation_prediction_dir.glob("*.txt")}

    if c1_ids & legacy_ids or validation_ids & (c1_ids | legacy_ids):
        raise ValueError("C1, legacy, and validation identities must be disjoint")
    if not (c1_ids | legacy_ids) <= full_by_id.keys():
        raise ValueError("C1 or legacy identity missing from the frozen MP3D test inventory")
    if validation_ids != reference_ids or validation_ids != prediction_ids:
        raise ValueError("validation image, reference, and prediction identities must match exactly")

    rows: list[dict[str, Any]] = []
    for base_task_id in sorted(c1_ids | legacy_ids):
        row = dict(full_by_id[base_task_id])
        is_c1 = base_task_id in c1_ids
        row.update({
            "inventory_role": "c1_risk_reference_support_only" if is_c1 else "legacy_provenance_support_only",
            "formal_dataset_split": "mp3d_test",
            "stage_reservation": "C1_HISTORY_SUPPORT_ONLY" if is_c1 else "EXCLUDED_PROVENANCE_ONLY",
            "scene_id": base_task_id.split("_", 1)[0],
        })
        rows.append(row)

    for image in validation_images:
        stem = image.stem
        rows.append({
            "task_id": stem, "base_task_id": stem, "image_id": stem, "image_stem": stem,
            "source_path": _portable_path(image),
            "image_path": f"{image_base_url.rstrip('/')}/{image.name}",
            "source_pool": "mp3d_validation_c2_v16",
            "used_in_prescreen": "false", "used_in_random_c1_deprecated": "false",
            "geometry_gold_ready": "true", "scope_gold_ready": "true",
            "inventory_role": "formal_c2b_validation_candidate",
            "formal_dataset_split": "mp3d_validation", "stage_reservation": "C2",
            "scene_id": stem.split("_", 1)[0],
            "reference_policy": "use_existing_mp3d_validation_reference_as_is",
        })

    output_dir.mkdir(parents=True, exist_ok=True)
    layout_dir = output_dir / "model_layout_json"
    layout_dir.mkdir(exist_ok=True)
    for base_task_id in sorted(c1_ids | legacy_ids):
        source = existing_layout_dir / f"{base_task_id}.json"
        if not source.is_file():
            raise ValueError(f"frozen model layout missing: {source}")
        shutil.copy2(source, layout_dir / source.name)
    for stem in sorted(validation_ids):
        _prediction_to_layout(validation_prediction_dir / f"{stem}.txt", layout_dir / f"{stem}.json", stem)

    inventory_path = output_dir / "c2b_validation_support_inventory.csv"
    _write_csv(inventory_path, rows)

    c1_buildings = {row["base_task_id"]: row for row in _read_csv(c1_building_registry)}
    if c1_ids != c1_buildings.keys():
        raise ValueError("C1 building registry does not exactly cover the frozen C1 task identities")
    building_rows: list[dict[str, Any]] = []
    for stem in sorted(c1_ids):
        row = dict(c1_buildings[stem])
        row.update({"image_id": stem, "task_id": stem})
        building_rows.append(row)
    for stem in sorted(validation_ids):
        building_rows.append({
            "image_id": stem, "base_task_id": stem, "task_id": stem,
            "building_id": stem.split("_", 1)[0], "scene_mapping_key": stem.split("_", 1)[0],
            "registry_status": "approved",
            "reviewed_by": "protocol_execution_under_researcher_validation_only_directive",
            "reviewed_at": reviewed_at, "review_source": "official_mp3d_validation_scene_identity",
        })
    building_path = output_dir / "authoritative_building_registry.csv"
    _write_csv(building_path, building_rows)

    scope_rows = [{
        "image_id": stem, "base_task_id": stem, "task_id": stem, "final_scope": "in_scope",
        "registry_status": "approved_by_dataset_protocol_assumption",
        "reviewed_by": "protocol_execution_under_researcher_validation_only_directive",
        "reviewed_at": reviewed_at, "evidence_basis": "mp3d_layout_valid_no_occ_curated_task_pool",
    } for stem in sorted(validation_ids)]
    scope_path = output_dir / "scope_registry.csv"
    _write_csv(scope_path, scope_rows)

    reference_rows = []
    for stem in sorted(validation_ids):
        reference = validation_reference_dir / f"{stem}.txt"
        reference_rows.append({
            "image_id": stem, "base_task_id": stem, "task_id": stem,
            "geometry_reference_ready": "true", "reference_status": "use_existing_public_gt_as_is",
            "registry_status": "approved_by_frozen_reference_policy",
            "reviewed_by": "protocol_execution_under_researcher_validation_only_directive",
            "reviewed_at": reviewed_at, "reference_path": _portable_path(reference),
            "reference_sha256": _sha256(reference), "evidence_basis": "official_mp3d_validation_label_cor",
        })
    reference_path = output_dir / "reference_registry.csv"
    _write_csv(reference_path, reference_rows)

    role_counts = Counter(str(row["inventory_role"]) for row in rows)
    summary = {
        "schema_version": "paper_a_c2b_validation_input_bundle_v1",
        "dataset_policy": "validation_only_worker_facing_c2b",
        "inventory_row_count": len(rows), "inventory_role_counts": dict(sorted(role_counts.items())),
        "worker_facing_candidate_count": len(validation_ids),
        "worker_facing_dataset_splits": ["mp3d_validation"],
        "building_registry_row_count": len(building_rows),
        "scope_registry_row_count": len(scope_rows), "reference_registry_row_count": len(reference_rows),
        "input_sha256": {
            "full_inventory": _sha256(full_inventory), "legacy_manifest": _sha256(legacy_manifest),
            "c1_building_registry": _sha256(c1_building_registry), "inventory": _sha256(inventory_path),
            "building_registry": _sha256(building_path), "scope_registry": _sha256(scope_path),
            "reference_registry": _sha256(reference_path),
        },
    }
    (output_dir / "c2b_validation_input_bundle.summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return summary


def main() -> None:
    root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--validation-prediction-dir", type=Path, required=True)
    parser.add_argument("--full-inventory", type=Path, default=root / "analysis_results/calibration_rebuild_20260702/calibration_full_candidate_inventory_v3.csv")
    parser.add_argument("--c1-assignment", type=Path, action="append", required=True)
    parser.add_argument("--legacy-manifest", type=Path, default=root / "import_json/paper_a_c2b/legacy_reverse_v3_1_manifest.csv")
    parser.add_argument("--c1-building-registry", type=Path, default=root / "analysis_results/c1_building_registry_review_20260801/authoritative_building_registry.csv")
    parser.add_argument("--validation-image-dir", type=Path, default=root / "data/mp3d_layout/valid_no_occ/img")
    parser.add_argument("--validation-reference-dir", type=Path, default=root / "data/mp3d_layout/valid_no_occ/label_cor")
    parser.add_argument("--existing-layout-dir", type=Path, default=root / "output/layout_json")
    parser.add_argument("--image-base-url", default="https://label-images-1389474327.cos.ap-guangzhou.myqcloud.com/data/mp3d_layout/valid_no_occ/img")
    parser.add_argument("--reviewed-at", default=datetime.now(timezone.utc).isoformat())
    args = parser.parse_args()
    summary = prepare(
        full_inventory=args.full_inventory, c1_assignments=args.c1_assignment,
        legacy_manifest=args.legacy_manifest, c1_building_registry=args.c1_building_registry,
        validation_image_dir=args.validation_image_dir, validation_reference_dir=args.validation_reference_dir,
        validation_prediction_dir=args.validation_prediction_dir, existing_layout_dir=args.existing_layout_dir,
        output_dir=args.output_dir, image_base_url=args.image_base_url, reviewed_at=args.reviewed_at,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
