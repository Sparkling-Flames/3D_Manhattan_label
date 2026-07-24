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

from tools.thesis_main.analysis.c1_live_collection_monitor import read_csv, write_csv, write_json
from tools.thesis_main.analysis.vfinal_artifact_utils import sha256_file


REQUIRED = ("d_model_feat", "d_model_feat_local", "g_pair_count", "g_topology_invalid", "g_duplicate_peak", "g_seam_instability", "g_postprocess_invalid")
FROZEN_IDENTITY = ("checkpoint_sha256", "inference_config_sha256", "layout_output_sha256")


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
    args = parser.parse_args(argv)
    print(json.dumps(materialize(args.assignment_csv, args.inventory_csv, args.output_dir, frozen_feature_csv=args.frozen_feature_csv), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
