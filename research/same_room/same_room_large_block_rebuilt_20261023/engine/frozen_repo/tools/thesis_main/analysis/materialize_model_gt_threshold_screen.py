from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.thesis_main.analysis.quality_core.geometry_metrics import (
    _interp_periodic,
    compute_layout_mask_iou_from_normalized_pairs,
)
from tools.thesis_main.analysis.geometry_consensus.representation import normalize_geometry


DEFAULT_MASK_THRESHOLDS = (0.05, 0.10, 0.20, 0.30)
DEFAULT_RMSE_THRESHOLDS = (5.0, 10.0, 20.0, 40.0)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _aggregate_sha256(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: item.name):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(_sha256(path).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _read_txt(path: Path) -> np.ndarray:
    points = [[float(value) for value in line.split()] for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    array = np.asarray(points, dtype=np.float32)
    if array.ndim != 2 or array.shape[1] != 2:
        raise ValueError(f"invalid layout txt: {path}")
    return array


def _read_test_gt(path: Path) -> dict[str, np.ndarray]:
    tasks = json.loads(path.read_text(encoding="utf-8"))
    result: dict[str, np.ndarray] = {}
    for task in tasks:
        title = str(task.get("data", {}).get("title", ""))
        image_id = Path(title).stem
        annotations = task.get("annotations") or []
        if not image_id or len(annotations) != 1:
            raise ValueError(f"test GT task must have one annotation: {task.get('id')}")
        points = []
        for item in annotations[0].get("result") or []:
            if item.get("type") != "keypointlabels":
                continue
            value = item.get("value") or {}
            points.append([float(value["x"]) * 10.24, float(value["y"]) * 5.12])
        if image_id in result or not points:
            raise ValueError(f"duplicate or empty test GT image: {image_id}")
        result[image_id] = np.asarray(points, dtype=np.float32)
    return result


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _ordered_pairs(points: np.ndarray, *, source: Path) -> list[dict[str, float]]:
    if len(points) < 4 or len(points) % 2:
        raise ValueError(f"ordered geometry requires an even point count >= 4: {source}")
    if not np.isfinite(points).all():
        raise ValueError(f"ordered geometry contains NaN or Inf: {source}")
    pairs = []
    for first, second in points.reshape(-1, 2, 2):
        dx = abs(float(first[0]) - float(second[0]))
        dx = min(dx, 1024.0 - dx)
        if dx > 1.0 or abs(float(first[1]) - float(second[1])) < 1.0:
            raise ValueError(f"invalid consecutive ceiling/floor pair: {source}")
        x1, x2 = float(first[0]), float(second[0])
        if abs(x1 - x2) > 512.0:
            if x1 < x2:
                x1 += 1024.0
            else:
                x2 += 1024.0
        pairs.append({
            "x": (x1 + x2) / 2.0 % 1024.0,
            "y_ceiling": min(float(first[1]), float(second[1])),
            "y_floor": max(float(first[1]), float(second[1])),
        })
    return pairs


def _boundary_rmse_from_pairs(a: list[dict[str, float]], b: list[dict[str, float]]) -> float:
    def dense(pairs: list[dict[str, float]], field: str) -> np.ndarray:
        return _interp_periodic(
            np.asarray([pair["x"] for pair in pairs], dtype=np.float32),
            np.asarray([pair[field] for pair in pairs], dtype=np.float32),
            1024,
        )

    diff2 = (dense(a, "y_ceiling") - dense(b, "y_ceiling")) ** 2
    diff2 += (dense(a, "y_floor") - dense(b, "y_floor")) ** 2
    return float(np.sqrt(np.mean(diff2)))


def _pairs(points: np.ndarray, *, source: Path, ordered_source: bool) -> list[dict[str, float]]:
    if ordered_source:
        return _ordered_pairs(points, source=source)
    normalized = normalize_geometry(points, width=1024, height=512)
    if normalized.get("valid"):
        return list(normalized["pairs"])
    return _ordered_pairs(points, source=source)


def _metric_row(
    *, split: str, image_id: str, model_path: Path, gt_path: Path, image_path: Path,
    model: np.ndarray, gt: np.ndarray, reference_status: str, gt_provenance: str, gt_ordered: bool,
) -> dict[str, Any]:
    model_pairs = _ordered_pairs(model, source=model_path)
    gt_pairs = _pairs(gt, source=gt_path, ordered_source=gt_ordered)
    row: dict[str, Any] = {
        "split": split,
        "image_id": image_id,
        "evaluation_status": reference_status,
        "gt_provenance": gt_provenance,
        "image_path": image_path.as_posix(),
        "model_path": model_path.as_posix(),
        "model_sha256": _sha256(model_path),
        "gt_path": gt_path.as_posix(),
        "gt_sha256": _sha256(gt_path),
        "model_point_count": len(model),
        "gt_point_count": len(gt),
        "model_pair_count": len(model_pairs),
        "gt_pair_count": len(gt_pairs),
        "pair_count_delta": len(model_pairs) - len(gt_pairs),
        "topology_mismatch": len(model_pairs) != len(gt_pairs),
        "model_pairing_coverage": 1.0,
        "gt_pairing_coverage": 1.0,
        "layout_mask_iou": "",
        "layout_mask_difference": "",
        "boundary_rmse_px": "",
        "metric_status": "not_evaluable" if reference_status != "evaluable" else "",
        "metric_reason": reference_status if reference_status != "evaluable" else "",
    }
    if reference_status != "evaluable":
        return row
    iou, iou_meta = compute_layout_mask_iou_from_normalized_pairs(model_pairs, gt_pairs, width=1024, height=512)
    if iou is None:
        row["metric_status"] = "not_evaluable"
        row["metric_reason"] = str(iou_meta.get("reason") or "layout_mask_iou_failed")
        return row
    row["layout_mask_iou"] = round(iou, 8)
    row["layout_mask_difference"] = round(1.0 - iou, 8)
    row["boundary_rmse_px"] = round(_boundary_rmse_from_pairs(model_pairs, gt_pairs), 6)
    row["metric_status"] = "evaluable"
    row["metric_reason"] = ""
    return row


def materialize(
    *, test_gt: Path, test_model_dir: Path, test_image_dir: Path,
    validation_gt_dir: Path, validation_model_dir: Path, validation_image_dir: Path,
    validation_registry: Path, output_dir: Path,
    mask_thresholds: tuple[float, ...] = DEFAULT_MASK_THRESHOLDS,
    rmse_thresholds: tuple[float, ...] = DEFAULT_RMSE_THRESHOLDS,
) -> dict[str, Any]:
    test_gold = _read_test_gt(test_gt)
    test_models = {path.stem: path for path in test_model_dir.glob("*.txt")}
    if set(test_gold) != set(test_models):
        raise ValueError("test GT and model image identities differ")

    validation_gt = {path.stem: path for path in validation_gt_dir.glob("*.txt")}
    validation_models = {path.stem: path for path in validation_model_dir.glob("*.txt")}
    registry_rows = list(csv.DictReader(validation_registry.open(encoding="utf-8-sig", newline="")))
    registry = {row["image_id"]: row for row in registry_rows}
    if set(validation_gt) != set(validation_models) or set(validation_gt) != set(registry):
        raise ValueError("validation GT, model, and registry image identities differ")

    rows: list[dict[str, Any]] = []
    for image_id in sorted(test_gold):
        rows.append(_metric_row(
            split="test", image_id=image_id, model_path=test_models[image_id], gt_path=test_gt,
            image_path=test_image_dir / f"{image_id}.png", model=_read_txt(test_models[image_id]), gt=test_gold[image_id],
            reference_status="evaluable", gt_provenance="partial_local_correction_not_full_human_review",
            gt_ordered=False,
        ))
    for image_id in sorted(validation_gt):
        reg = registry[image_id]
        ready = str(reg.get("geometry_reference_ready", "")).lower() == "true"
        rows.append(_metric_row(
            split="validation", image_id=image_id, model_path=validation_models[image_id], gt_path=validation_gt[image_id],
            image_path=validation_image_dir / f"{image_id}.png", model=_read_txt(validation_models[image_id]), gt=_read_txt(validation_gt[image_id]),
            reference_status="evaluable" if ready else "reference_unavailable",
            gt_provenance="official_mp3d_valid_no_occ_not_locally_human_reviewed",
            gt_ordered=True,
        ))

    fields = list(rows[0])
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "model_gt_metrics.csv", rows, fields)

    membership: list[dict[str, Any]] = []
    summary: list[dict[str, Any]] = []
    criteria = [
        ("layout_mask_difference_ge", "layout_mask_difference", mask_thresholds),
        ("boundary_rmse_px_ge", "boundary_rmse_px", rmse_thresholds),
    ]
    for split in ("test", "validation", "all"):
        eligible = [row for row in rows if row["metric_status"] == "evaluable" and (split == "all" or row["split"] == split)]
        for criterion, field, thresholds in criteria:
            for threshold in thresholds:
                selected = [row for row in eligible if row[field] != "" and float(row[field]) >= threshold]
                summary.append({
                    "split": split, "criterion": criterion, "threshold": threshold,
                    "eligible_count": len(eligible), "selected_count": len(selected),
                    "selected_fraction": round(len(selected) / len(eligible), 8) if eligible else "",
                })
                if split != "all":
                    for row in sorted(selected, key=lambda item: float(item[field]), reverse=True):
                        membership.append({
                            "split": row["split"], "criterion": criterion, "threshold": threshold,
                            "image_id": row["image_id"], "metric_value": row[field],
                            "topology_mismatch": row["topology_mismatch"], "pair_count_delta": row["pair_count_delta"],
                            "image_path": row["image_path"], "model_path": row["model_path"], "gt_path": row["gt_path"],
                        })
        for threshold in mask_thresholds:
            selected = [
                row for row in eligible
                if float(row["layout_mask_difference"]) >= threshold or row["topology_mismatch"]
            ]
            summary.append({
                "split": split, "criterion": "layout_mask_difference_ge_or_topology_mismatch",
                "threshold": threshold, "eligible_count": len(eligible), "selected_count": len(selected),
                "selected_fraction": round(len(selected) / len(eligible), 8) if eligible else "",
            })
            if split != "all":
                for row in sorted(selected, key=lambda item: float(item["layout_mask_difference"]), reverse=True):
                    membership.append({
                        "split": row["split"], "criterion": "layout_mask_difference_ge_or_topology_mismatch",
                        "threshold": threshold, "image_id": row["image_id"],
                        "metric_value": row["layout_mask_difference"], "topology_mismatch": row["topology_mismatch"],
                        "pair_count_delta": row["pair_count_delta"], "image_path": row["image_path"],
                        "model_path": row["model_path"], "gt_path": row["gt_path"],
                    })
        topology = [row for row in eligible if row["topology_mismatch"]]
        summary.append({
            "split": split, "criterion": "topology_mismatch", "threshold": "",
            "eligible_count": len(eligible), "selected_count": len(topology),
            "selected_fraction": round(len(topology) / len(eligible), 8) if eligible else "",
        })
        if split != "all":
            for row in sorted(topology, key=lambda item: abs(int(item["pair_count_delta"])), reverse=True):
                membership.append({
                    "split": row["split"], "criterion": "topology_mismatch", "threshold": "",
                    "image_id": row["image_id"], "metric_value": abs(int(row["pair_count_delta"])),
                    "topology_mismatch": True, "pair_count_delta": row["pair_count_delta"],
                    "image_path": row["image_path"], "model_path": row["model_path"], "gt_path": row["gt_path"],
                })

    _write_csv(output_dir / "threshold_summary.csv", summary, list(summary[0]))
    _write_csv(output_dir / "threshold_membership.csv", membership, list(membership[0]))
    manifest = {
        "schema_version": "model_gt_threshold_screen_v1",
        "coordinate_space": "1024x512",
        "primary_metric": "layout_mask_difference = 1 - seam-aware layout_mask_iou",
        "secondary_metrics": ["boundary_rmse_px", "pair_count_delta", "topology_mismatch"],
        "threshold_rule": "inclusive >=",
        "mask_difference_thresholds": list(mask_thresholds),
        "boundary_rmse_thresholds_px": list(rmse_thresholds),
        "counts": {
            "test_total": sum(row["split"] == "test" for row in rows),
            "validation_total": sum(row["split"] == "validation" for row in rows),
            "validation_evaluable": sum(row["split"] == "validation" and row["metric_status"] == "evaluable" for row in rows),
            "reference_unavailable": sum(row["evaluation_status"] == "reference_unavailable" for row in rows),
            "metric_not_evaluable": sum(row["metric_status"] == "not_evaluable" for row in rows),
        },
        "inputs": {
            "test_gt": {"path": test_gt.as_posix(), "sha256": _sha256(test_gt)},
            "test_model_dir": {"path": test_model_dir.as_posix(), "aggregate_sha256": _aggregate_sha256(list(test_models.values()))},
            "validation_gt_dir": {"path": validation_gt_dir.as_posix(), "aggregate_sha256": _aggregate_sha256(list(validation_gt.values()))},
            "validation_model_dir": {"path": validation_model_dir.as_posix(), "aggregate_sha256": _aggregate_sha256(list(validation_models.values()))},
            "validation_registry": {"path": validation_registry.as_posix(), "sha256": _sha256(validation_registry)},
        },
    }
    (output_dir / "run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="筛选 Test/Validation 模型预标注与 GT 差异较大的图片。")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--test-gt", type=Path, default=ROOT / "export_label/groudTruth.json")
    parser.add_argument("--test-model-dir", type=Path, default=ROOT / "output/mp3d_layout/HOHO_layout_aug_efficienthc_Transen1_resnet34")
    parser.add_argument("--test-image-dir", type=Path, default=ROOT / "data/mp3d_layout/test/img")
    parser.add_argument("--validation-gt-dir", type=Path, default=ROOT / "data/mp3d_layout/valid_no_occ/label_cor")
    parser.add_argument("--validation-model-dir", type=Path, default=ROOT / "analysis_results/c2b_validation_static_20260802_v16/validation_prediction_txt")
    parser.add_argument("--validation-image-dir", type=Path, default=ROOT / "data/mp3d_layout/valid_no_occ/img")
    parser.add_argument("--validation-registry", type=Path, default=ROOT / "analysis_results/c2a_rp_local_launch_20260807_inputs_v2/reference_registry_post_c2_local.csv")
    args = parser.parse_args()
    print(json.dumps(materialize(**vars(args)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
