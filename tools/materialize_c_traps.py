from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from perturbation_operators import (
    PerturbationEngine,
    canonical_corners_to_runtime_pairs,
    freeze_plan,
    ls_keypoints_to_canonical_corners,
)


def _stable_hash(payload: Any) -> str:
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def load_stage1_task_sources(import_json_path: Path) -> dict[str, dict[str, Any]]:
    payload = json.loads(import_json_path.read_text(encoding="utf-8"))
    task_sources: dict[str, dict[str, Any]] = {}
    for item in payload:
        title = str(item.get("data", {}).get("title", "")).strip()
        if not title:
            continue
        base_task_id = title.rsplit(".", 1)[0]
        prediction_list = item.get("predictions") or []
        prediction = prediction_list[0] if prediction_list else {}
        prediction_result = prediction.get("result") or []
        corners_norm, stats = ls_keypoints_to_canonical_corners(prediction_result)
        prediction_hash = _stable_hash(prediction_result)
        task_sources[base_task_id] = {
            "base_task_id": base_task_id,
            "title": title,
            "image": item.get("data", {}).get("image"),
            "dataset_group": item.get("data", {}).get("dataset_group"),
            "init_type": item.get("data", {}).get("init_type"),
            "image_width": stats.get("width", 1024),
            "image_height": stats.get("height", 512),
            "n_keypoints": stats.get("n_keypoints", 0),
            "n_corners": stats.get("n_corners", 0),
            "pair_coverage": stats.get("pair_coverage", 0.0),
            "prediction_hash": prediction_hash,
            "corners_norm": corners_norm,
            "runtime_pairs": canonical_corners_to_runtime_pairs(corners_norm, stats.get("width", 1024), stats.get("height", 512)),
        }
    return task_sources


def read_csv_rows(csv_path: Path) -> list[dict[str, Any]]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def build_operator_config(row: dict[str, Any], task_source: dict[str, Any]) -> dict[str, Any]:
    operator_id = row["operator_id"]
    corners = task_source.get("corners_norm", [])
    corner_count = len(corners)
    default_corner_index = 1 if corner_count > 1 else 0

    if operator_id == "underextend":
        return {"remove_index": default_corner_index}
    if operator_id == "corner_drift":
        return {"corner_index": default_corner_index}
    if operator_id == "corner_duplicate":
        return {"corner_index": default_corner_index, "new_points": 1 if row["lambda_level"] != "strong" else 2}
    if operator_id == "overextend_adjacent":
        return {"approved_edge_index": min(default_corner_index, max(corner_count - 1, 0)), "surrogate_mode": True}
    if operator_id == "over_parsing":
        return {"approved_edge_index": min(default_corner_index, max(corner_count - 1, 0)), "surrogate_mode": True}
    return {}


def materialize_bundle(
    *,
    draft_rows: list[dict[str, Any]],
    task_sources: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    plan_rows = []
    for row in draft_rows:
        task_source = task_sources.get(row["base_task_id"], {})
        if row["source_type"] == "natural_failure":
            continue
        plan_rows.append(
            {
                "manifest_row_id": row["manifest_row_id"],
                "target_registry_uid": row["target_registry_uid"],
                "base_task_id": row["base_task_id"],
                "title": row["title"],
                "operator_id": row["operator_id"],
                "source_type": row["source_type"],
                "lambda_level": row["lambda_level"],
                "seed": int(row["seed"]),
                "config": build_operator_config(row, task_source),
            }
        )

    frozen_plan = freeze_plan(plan_rows, task_sources)
    generated_rows = PerturbationEngine().generate_batch(frozen_plan, task_sources)
    generated_by_id = {item["manifest_row_id"]: item for item in generated_rows}

    materialized_rows: list[dict[str, Any]] = []
    generated_bank: list[dict[str, Any]] = []

    for row in draft_rows:
        base_task_id = row["base_task_id"]
        task_source = task_sources.get(base_task_id, {})
        source_corners = task_source.get("corners_norm", [])
        common = dict(row)
        common.update(
            {
                "source_prediction_hash": task_source.get("prediction_hash", ""),
                "source_corner_count": len(source_corners),
                "source_pair_coverage": task_source.get("pair_coverage", ""),
                "materialization_source": "natural_passthrough" if row["source_type"] == "natural_failure" else "synthetic_operator_engine",
            }
        )

        if row["source_type"] == "natural_failure":
            common.update(
                {
                    "manifest_status": "realized",
                    "realized_quota": "1",
                    "materialization_status": "realized",
                    "generated_corner_count": len(source_corners),
                    "generated_corner_delta": 0,
                    "audit_hash": task_source.get("prediction_hash", ""),
                }
            )
            materialized_rows.append(common)
            generated_bank.append(
                {
                    "manifest_row_id": row["manifest_row_id"],
                    "base_task_id": base_task_id,
                    "artifact_status": "natural_passthrough",
                    "family_id": row["operator_id"],
                    "source_type": row["source_type"],
                    "runtime_pairs": task_source.get("runtime_pairs", []),
                    "corners_norm": source_corners,
                    "audit": {"selection_rule": row.get("selection_rule", "")},
                }
            )
            continue

        generated = generated_by_id.get(row["manifest_row_id"], {})
        generated_corners = generated.get("corners_norm", [])
        realized = generated.get("status") == "success"
        common.update(
            {
                "manifest_status": "realized" if realized else "blocked_by_dependency",
                "realized_quota": "1" if realized else "0",
                "materialization_status": "realized" if realized else generated.get("status", "blocked_by_dependency"),
                "generated_corner_count": len(generated_corners),
                "generated_corner_delta": len(generated_corners) - len(source_corners),
                "audit_hash": _stable_hash(generated.get("audit", {})) if generated else "",
            }
        )
        materialized_rows.append(common)
        generated_bank.append(
            {
                "manifest_row_id": row["manifest_row_id"],
                "base_task_id": base_task_id,
                "artifact_status": "generated_synthetic" if realized else generated.get("status", "blocked_by_dependency"),
                "family_id": row["operator_id"],
                "source_type": row["source_type"],
                "runtime_pairs": canonical_corners_to_runtime_pairs(generated_corners, task_source.get("image_width", 1024), task_source.get("image_height", 512)),
                "corners_norm": generated_corners,
                "audit": generated.get("audit", {}),
                "failure_code": generated.get("failure_code"),
                "source_runtime_pairs": task_source.get("runtime_pairs", []),
            }
        )

    return frozen_plan, materialized_rows, generated_bank


def write_csv(csv_path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Materialize Dev C trap bundle from current PreScreen_semi import predictions.")
    parser.add_argument("--draft", default="analysis_results/c_manifests_20260310/trap_manifest_draft_v1.csv")
    parser.add_argument("--import-json", default="import_json/outline_v2_seed20260228/stage1_prescreen_semi_import.json")
    parser.add_argument("--output-dir", default="analysis_results/c_manifests_20260311")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    draft_path = root / args.draft
    import_json_path = root / args.import_json
    output_dir = root / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    draft_rows = read_csv_rows(draft_path)
    task_sources = load_stage1_task_sources(import_json_path)
    frozen_plan, materialized_rows, generated_bank = materialize_bundle(draft_rows=draft_rows, task_sources=task_sources)

    write_csv(output_dir / "trap_manifest_materialized_v2.csv", materialized_rows)
    (output_dir / "perturbation_plan_frozen_v1.json").write_text(json.dumps(frozen_plan, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "synthetic_trap_bank_v1.json").write_text(json.dumps(generated_bank, ensure_ascii=False, indent=2), encoding="utf-8")

    status_counter = Counter(row["materialization_status"] for row in materialized_rows)
    family_counter = Counter(row["operator_id"] for row in materialized_rows)
    summary = {
        "bundle_version": "c-materialized-v1",
        "source_manifest": str(draft_path.relative_to(root)).replace("\\", "/"),
        "source_import_json": str(import_json_path.relative_to(root)).replace("\\", "/"),
        "n_rows": len(materialized_rows),
        "n_realized_rows": sum(1 for row in materialized_rows if row["materialization_status"] == "realized"),
        "n_generated_synthetic_rows": sum(1 for row in materialized_rows if row["materialization_source"] == "synthetic_operator_engine" and row["materialization_status"] == "realized"),
        "status_counts": dict(status_counter),
        "family_counts": dict(family_counter),
        "important_note": "This bundle no longer stops at frozen_rule for synthetic rows. It materializes operator outputs from current PreScreen_semi import predictions, but it still depends on the current import JSON and does not claim that the revised thesis Stage 1 target quotas are already fulfilled.",
    }
    (output_dir / "materialization_summary_v1.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
