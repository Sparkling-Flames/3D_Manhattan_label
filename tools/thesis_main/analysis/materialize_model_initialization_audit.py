from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.thesis_main.analysis.materialize_model_gt_threshold_screen import (
    _aggregate_sha256,
    _boundary_rmse_from_pairs,
    _ordered_pairs,
    _pairs,
    _read_test_gt,
    _read_txt,
    _sha256,
    _write_csv,
)
from tools.thesis_main.analysis.quality_core.geometry_metrics import (
    compute_layout_mask_iou_from_normalized_pairs,
    compute_layout_standard_metrics,
)


WIDTH = 1024
HEIGHT = 512
CORNER_MATCH_THRESHOLD_PX = WIDTH * 0.01  # ZInD/CVPR 2021: 1% of image width.
NEAR_MAX_CORNER_ERROR_PX = WIDTH * 0.0025  # Project tier: one quarter of the literature threshold.
NEAR_MASK_DIFFERENCE = 0.01


def _repo_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _pairs_to_points(pairs: list[dict[str, float]]) -> np.ndarray:
    ordered = sorted(pairs, key=lambda item: item["x"])
    return np.asarray(
        [[pair["x"] % WIDTH, pair["y_ceiling"]] for pair in ordered]
        + [[pair["x"] % WIDTH, pair["y_floor"]] for pair in ordered],
        dtype=np.float32,
    )


def _pairs_to_cor_id(pairs: list[dict[str, float]]) -> np.ndarray:
    return np.asarray(
        [point for pair in pairs
         for point in ((pair["x"] % WIDTH, pair["y_ceiling"]), (pair["x"] % WIDTH, pair["y_floor"]))],
        dtype=np.float32,
    )


def _corner_distance(a: np.ndarray, b: np.ndarray, width: int = WIDTH) -> float:
    dx = abs(float(a[0]) - float(b[0]))
    dx = min(dx, float(width) - dx)
    return float(math.hypot(dx, float(a[1]) - float(b[1])))


def exclusive_corner_match(
    model_pairs: list[dict[str, float]],
    gt_pairs: list[dict[str, float]],
    threshold_px: float = CORNER_MATCH_THRESHOLD_PX,
) -> dict[str, float | int]:
    """Project-defined deterministic greedy matching using ZInD's 1%-width threshold."""
    model = _pairs_to_points(model_pairs)
    gt = _pairs_to_points(gt_pairs)
    distances = np.asarray([[_corner_distance(a, b) for b in gt] for a in model], dtype=np.float64)
    tp = 0
    while distances.size:
        index = int(np.argmin(distances))
        i, j = np.unravel_index(index, distances.shape)
        if not np.isfinite(distances[i, j]) or distances[i, j] > threshold_px:
            break
        tp += 1
        distances[i, :] = np.inf
        distances[:, j] = np.inf
    fp = int(len(model) - tp)
    fn = int(len(gt) - tp)
    precision = tp / len(model) if len(model) else 0.0
    recall = tp / len(gt) if len(gt) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": f1}


def _cyclic_corner_errors(
    model_pairs: list[dict[str, float]], gt_pairs: list[dict[str, float]],
) -> tuple[float, float, float] | None:
    if len(model_pairs) != len(gt_pairs):
        return None
    model = sorted(model_pairs, key=lambda item: item["x"])
    gt = sorted(gt_pairs, key=lambda item: item["x"])
    candidates: list[list[float]] = []
    for shift in range(len(gt)):
        shifted = gt[shift:] + gt[:shift]
        errors = []
        for a, b in zip(model, shifted):
            errors.append(_corner_distance(
                np.asarray([a["x"], a["y_ceiling"]]), np.asarray([b["x"], b["y_ceiling"]])
            ))
            errors.append(_corner_distance(
                np.asarray([a["x"], a["y_floor"]]), np.asarray([b["x"], b["y_floor"]])
            ))
        candidates.append(errors)
    errors = min(candidates, key=lambda values: float(np.mean(np.square(values))))
    return (
        float(np.mean(errors)),
        float(np.sqrt(np.mean(np.square(errors)))),
        float(np.max(errors)),
    )


def identify_confirmed_manual_gt(
    manual_gt: dict[str, np.ndarray], official_gt: dict[str, Path], manual_source: Path,
    *, expected_count: int = 30,
) -> tuple[set[str], dict[str, list[dict[str, float]]]]:
    if set(manual_gt) != set(official_gt):
        raise ValueError("manual Test GT and official Test GT identities differ")
    manual_pairs: dict[str, list[dict[str, float]]] = {}
    changed: set[str] = set()
    for image_id in sorted(official_gt):
        current = _pairs(manual_gt[image_id], source=manual_source, ordered_source=False)
        official = _ordered_pairs(_read_txt(official_gt[image_id]), source=official_gt[image_id])
        manual_pairs[image_id] = current
        matched = exclusive_corner_match(current, official, threshold_px=1.0)
        if len(current) != len(official) or int(matched["fp"]) or int(matched["fn"]):
            changed.add(image_id)
    if len(changed) != expected_count:
        raise ValueError(f"expected {expected_count} confirmed manual Test GT changes, found {len(changed)}")
    return changed, manual_pairs


def classify_initialization(
    *, pair_encoding_valid: bool, model_pair_count: int, gt_pair_count: int,
    corner_all_matched: bool, geometry_acceptable: bool,
    max_corner_error_px: float | None,
    layout_mask_difference: float | None,
) -> dict[str, bool | str]:
    topology_exact = model_pair_count == gt_pair_count
    structural_localization_correct = bool(pair_encoding_valid and topology_exact and corner_all_matched)
    correct = bool(structural_localization_correct and geometry_acceptable)
    near = bool(
        correct
        and max_corner_error_px is not None
        and max_corner_error_px <= NEAR_MAX_CORNER_ERROR_PX
        and layout_mask_difference is not None
        and layout_mask_difference <= NEAR_MASK_DIFFERENCE
    )
    if not pair_encoding_valid:
        cls, band = "wrong_initialization_invalid_pair_encoding", "large_difference_invalid"
    elif not topology_exact:
        cls, band = "wrong_initialization_topology", "large_difference_topology"
    elif not corner_all_matched:
        cls, band = "wrong_initialization_localization", "large_difference_localization"
    elif not geometry_acceptable:
        cls, band = "wrong_initialization_geometry", "large_difference_geometry"
    elif near:
        cls, band = "correct_initialization_nearly_identical", "nearly_no_difference"
    else:
        cls, band = "correct_initialization", "correct_but_visible_difference"
    return {
        "pair_structure_correct": bool(pair_encoding_valid and topology_exact),
        "structural_localization_correct": structural_localization_correct,
        "geometry_acceptable": geometry_acceptable,
        "initialization_correct": correct,
        "near_identical": near,
        "initialization_class": cls,
        "difference_band": band,
    }


def is_initialization_acceptable(
    *, pair_encoding_valid: bool, topology_exact: bool, topdown_2d_iou: float | None,
    derived_3d_iou: float | None, corner_error_percent_diagonal: float | None,
) -> bool:
    return bool(
        pair_encoding_valid and topology_exact
        and topdown_2d_iou is not None and topdown_2d_iou >= 0.75
        and derived_3d_iou is not None and derived_3d_iou >= 0.65
        and corner_error_percent_diagonal is not None and corner_error_percent_diagonal <= 2.0
    )


def _metric_row(
    split: str, image_id: str, model_path: Path, gt_path: Path, image_path: Path,
    *, gt: np.ndarray | None = None, gt_pairs: list[dict[str, float]] | None = None,
    gt_source_type: str = "official_mp3d_layout_label_cor_raw_not_no_occ",
) -> dict[str, Any]:
    gt = _read_txt(gt_path) if gt is None else gt
    gt_pairs = _ordered_pairs(gt, source=gt_path) if gt_pairs is None else gt_pairs
    row: dict[str, Any] = {
        "split": split,
        "image_id": image_id,
        "metric_object": "final_layout_as_initialization_proxy",
        "coordinate_space": "1024x512",
        "gt_variant": "test_hybrid_30_manual_else_official" if split == "test" else "official_mp3d_layout_label_cor_raw_not_no_occ",
        "gt_source_type": gt_source_type,
        "image_path": _repo_path(image_path),
        "model_path": _repo_path(model_path),
        "gt_path": _repo_path(gt_path),
        "model_sha256": _sha256(model_path),
        "gt_sha256": _sha256(gt_path),
        "model_pair_encoding_valid": True,
        "model_pair_encoding_invalid_reason": "",
        "model_point_count": "",
        "gt_point_count": len(gt),
        "model_pair_count": "",
        "gt_pair_count": len(gt_pairs),
        "pair_count_delta": "",
        "topology_exact": False,
        "pair_structure_correct": False,
        "corner_match_threshold_px": CORNER_MATCH_THRESHOLD_PX,
        "corner_match_tp": "",
        "corner_match_fp": "",
        "corner_match_fn": "",
        "corner_precision_1pct": "",
        "corner_recall_1pct": "",
        "corner_f1_1pct": "",
        "corner_localization_pass": False,
        "structural_localization_correct": False,
        "mean_corner_error_px": "",
        "corner_rmse_px": "",
        "max_corner_error_px": "",
        "corner_error_percent_diagonal": "",
        "topdown_2d_iou": "",
        "layoutnetv2_style_3d_iou": "",
        "layout_depth_rmse_proxy": "",
        "layout_depth_delta1_proxy": "",
        "layout_metric_status": "",
        "layout_metric_reason": "",
        "layout_mask_iou": "",
        "layout_mask_difference": "",
        "boundary_rmse_px": "",
        "geometry_acceptable": False,
        "initialization_acceptable": False,
        "operational_initialization_band": "",
        "initialization_correct": False,
        "near_identical": False,
        "initialization_class": "",
        "difference_band": "",
    }
    try:
        model = _read_txt(model_path)
        model_pairs = _ordered_pairs(model, source=model_path)
    except (OSError, ValueError) as exc:
        row["model_pair_encoding_valid"] = False
        row["model_pair_encoding_invalid_reason"] = str(exc)
        row.update(classify_initialization(
            pair_encoding_valid=False, model_pair_count=-1, gt_pair_count=len(gt_pairs),
            corner_all_matched=False, geometry_acceptable=False,
            max_corner_error_px=None, layout_mask_difference=None,
        ))
        return row

    model_count = len(model_pairs)
    gt_count = len(gt_pairs)
    row.update({
        "model_point_count": len(model),
        "model_pair_count": model_count,
        "pair_count_delta": model_count - gt_count,
        "topology_exact": model_count == gt_count,
    })

    matched = exclusive_corner_match(model_pairs, gt_pairs)
    row.update({
        "corner_match_tp": matched["tp"],
        "corner_match_fp": matched["fp"],
        "corner_match_fn": matched["fn"],
        "corner_precision_1pct": round(float(matched["precision"]), 8),
        "corner_recall_1pct": round(float(matched["recall"]), 8),
        "corner_f1_1pct": round(float(matched["f1"]), 8),
    })
    all_matched = bool(
        model_count == gt_count
        and int(matched["tp"]) == len(model)
        and int(matched["fp"]) == 0
        and int(matched["fn"]) == 0
    )
    row["corner_localization_pass"] = all_matched

    errors = _cyclic_corner_errors(model_pairs, gt_pairs)
    if errors is not None:
        mean_error, rmse_error, max_error = errors
        row.update({
            "mean_corner_error_px": round(mean_error, 6),
            "corner_rmse_px": round(rmse_error, 6),
            "max_corner_error_px": round(max_error, 6),
            "corner_error_percent_diagonal": round(mean_error / math.hypot(WIDTH, HEIGHT) * 100.0, 8),
        })
    else:
        max_error = None

    mask_iou, mask_meta = compute_layout_mask_iou_from_normalized_pairs(
        model_pairs, gt_pairs, width=WIDTH, height=HEIGHT,
    )
    if mask_iou is None:
        raise ValueError(f"layout mask failed for {image_id}: {mask_meta.get('reason')}")
    mask_difference = 1.0 - mask_iou
    row.update({
        "layout_mask_iou": round(mask_iou, 8),
        "layout_mask_difference": round(mask_difference, 8),
        "boundary_rmse_px": round(_boundary_rmse_from_pairs(model_pairs, gt_pairs), 6),
    })

    iou2d, iou3d, depth_rmse, delta1, used, meta = compute_layout_standard_metrics(
        _pairs_to_cor_id(model_pairs), _pairs_to_cor_id(gt_pairs), width=WIDTH, height=HEIGHT,
        ordered_source=True,
    )
    row.update({
        "topdown_2d_iou": round(float(iou2d), 8) if iou2d is not None else "",
        "layoutnetv2_style_3d_iou": round(float(iou3d), 8) if iou3d is not None else "",
        "layout_depth_rmse_proxy": round(float(depth_rmse), 8) if depth_rmse is not None else "",
        "layout_depth_delta1_proxy": round(float(delta1), 8) if delta1 is not None else "",
        "layout_metric_status": "proxy_evaluable" if used else "not_evaluable",
        "layout_metric_reason": str(meta.get("gate_reason") or ""),
    })
    geometry_acceptable = bool(
        iou2d is not None and iou2d >= 0.90
        and iou3d is not None and iou3d >= 0.80
        and mask_difference <= 0.05
    )
    row.update(classify_initialization(
        pair_encoding_valid=True, model_pair_count=model_count, gt_pair_count=gt_count,
        corner_all_matched=all_matched, geometry_acceptable=geometry_acceptable,
        max_corner_error_px=max_error,
        layout_mask_difference=mask_difference,
    ))
    acceptable = is_initialization_acceptable(
        pair_encoding_valid=True,
        topology_exact=model_count == gt_count,
        topdown_2d_iou=iou2d,
        derived_3d_iou=iou3d,
        corner_error_percent_diagonal=float(row["corner_error_percent_diagonal"]) if row["corner_error_percent_diagonal"] != "" else None,
    )
    row["initialization_acceptable"] = acceptable
    row["operational_initialization_band"] = (
        "strict_correct" if row["initialization_correct"]
        else "acceptable_not_strict" if acceptable
        else "wrong_topology" if not row["topology_exact"]
        else "not_acceptable_same_topology"
    )
    for threshold in (0.95, 0.90, 0.75):
        row[f"topdown_2d_iou_ge_{str(threshold).replace('.', '_')}"] = bool(iou2d is not None and iou2d >= threshold)
    for threshold in (0.01, 0.05, 0.10, 0.20):
        row[f"mask_difference_ge_{str(threshold).replace('.', '_')}"] = mask_difference >= threshold
    for threshold in (5.0, 10.0, 20.0):
        row[f"boundary_rmse_ge_{int(threshold)}px"] = float(row["boundary_rmse_px"]) >= threshold
    return row


def _markdown_table(rows: list[dict[str, Any]]) -> str:
    lines = ["| split | image_id | 类别 | 角点对 model/GT | F1@1% | mask diff | 2D IoU |",
             "|---|---|---|---:|---:|---:|---:|"]
    for row in rows:
        lines.append(
            f"| {row['split']} | `{row['image_id']}` | {row['difference_band']} | "
            f"{row['model_pair_count']}/{row['gt_pair_count']} | {row['corner_f1_1pct']} | "
            f"{row['layout_mask_difference']} | {row['topdown_2d_iou']} |"
        )
    return "\n".join(lines)


def _report(rows: list[dict[str, Any]], manifest: dict[str, Any]) -> str:
    counts = Counter(str(row["difference_band"]) for row in rows)
    split_counts = {split: Counter(str(row["difference_band"]) for row in rows if row["split"] == split)
                    for split in ("test", "validation")}
    test_rows = [row for row in rows if row["split"] == "test"]
    hybrid_test_classes = Counter(str(row["initialization_class"]) for row in test_rows)
    official_test_classes = Counter(
        str(row["official_gt_sensitivity_initialization_class"] or row["initialization_class"])
        for row in test_rows
    )

    def official_test_value(row: dict[str, Any], key: str) -> float:
        sensitivity = row.get(f"official_gt_sensitivity_{key}", "")
        return float(sensitivity if sensitivity != "" else row[key])

    validation_rows = [row for row in rows if row["split"] == "validation"]

    def metric_line(label: str, scope: list[dict[str, Any]], *, official_test: bool = False) -> str:
        value = (lambda row, key: official_test_value(row, key)) if official_test else (lambda row, key: float(row[key]))
        return (
            f"| {label} | {len(scope)} | "
            f"{100 * np.mean([value(row, 'topdown_2d_iou') for row in scope]):.2f} | "
            f"{100 * np.mean([value(row, 'layoutnetv2_style_3d_iou') for row in scope]):.2f} | "
            f"{np.mean([value(row, 'layout_depth_rmse_proxy') for row in scope]):.2f} | "
            f"{np.mean([value(row, 'layout_depth_delta1_proxy') for row in scope]):.2f} |"
        )

    def bin_lines(split: str, scope: list[dict[str, Any]], *, official_test: bool = False) -> list[str]:
        value = (lambda row, key: official_test_value(row, key)) if official_test else (lambda row, key: float(row[key]))
        pair_count = (
            (lambda row: int(row["official_gt_sensitivity_gt_pair_count"] or row["gt_pair_count"]))
            if official_test else (lambda row: int(row["gt_pair_count"]))
        )
        result = []
        for label, predicate in (
            ("4", lambda count: count == 4), ("6", lambda count: count == 6),
            ("8", lambda count: count == 8), ("10+", lambda count: count >= 10),
        ):
            group = [row for row in scope if predicate(pair_count(row))]
            result.append(
                f"| {split} | {label} | {len(group)} | "
                f"{100 * np.mean([value(row, 'topdown_2d_iou') for row in group]):.2f} | "
                f"{100 * np.mean([value(row, 'layoutnetv2_style_3d_iou') for row in group]):.2f} |"
            )
        return result

    def lane(counter: Counter[str]) -> tuple[int, int, int, int, int]:
        near_count = counter["correct_initialization_nearly_identical"]
        return (
            counter["wrong_initialization_topology"],
            counter["wrong_initialization_localization"],
            counter["wrong_initialization_geometry"],
            counter["correct_initialization"] + near_count,
            near_count,
        )

    official_lane = lane(official_test_classes)
    hybrid_lane = lane(hybrid_test_classes)
    hybrid_test_acceptable = sum(bool(row["initialization_acceptable"]) for row in test_rows)
    official_test_acceptable = sum(
        bool(row["official_gt_sensitivity_initialization_acceptable"])
        if row["official_gt_sensitivity_initialization_acceptable"] != ""
        else bool(row["initialization_acceptable"])
        for row in test_rows
    )
    manual_class_changed = sum(bool(row["hybrid_vs_official_class_changed"]) for row in test_rows)
    manual_topology_changed = sum(bool(row["hybrid_vs_official_topology_changed"]) for row in test_rows)
    unchanged_official_topology_errors = sum(
        not bool(row["topology_exact"]) and row["gt_source_type"] != "confirmed_user_manual_gt_correction"
        for row in test_rows
    )
    manual_rows = [row for row in test_rows if row["gt_source_type"] == "confirmed_user_manual_gt_correction"]
    manual_official_topology_errors = sum(
        row["official_gt_sensitivity_initialization_class"] == "wrong_initialization_topology" for row in manual_rows
    )
    manual_hybrid_topology_errors = sum(not bool(row["topology_exact"]) for row in manual_rows)
    manual_topology_resolved = sum(
        row["official_gt_sensitivity_initialization_class"] == "wrong_initialization_topology" and bool(row["topology_exact"])
        for row in manual_rows
    )
    manual_topology_introduced = sum(
        row["official_gt_sensitivity_initialization_class"] != "wrong_initialization_topology" and not bool(row["topology_exact"])
        for row in manual_rows
    )
    model_more = sum(int(row["pair_count_delta"]) > 0 for row in test_rows)
    model_fewer = sum(int(row["pair_count_delta"]) < 0 for row in test_rows)
    topology_examples = sorted(
        [row for row in rows if row["difference_band"] == "large_difference_topology"],
        key=lambda row: (-abs(int(row["pair_count_delta"])), -float(row["layout_mask_difference"])),
    )[:10]
    localization_examples = sorted(
        [row for row in rows if row["difference_band"] == "large_difference_localization"],
        key=lambda row: (float(row["corner_f1_1pct"]), -float(row["layout_mask_difference"])),
    )[:10]
    geometry_examples = sorted(
        [row for row in rows if row["difference_band"] == "large_difference_geometry"],
        key=lambda row: (-float(row["layout_mask_difference"]), float(row["topdown_2d_iou"])),
    )[:10]
    near = sorted(
        [row for row in rows if row["difference_band"] == "nearly_no_difference"],
        key=lambda row: (float(row["layout_mask_difference"]), float(row["max_corner_error_px"])),
    )[:20]
    high_iou_topology = sum(
        not bool(row["topology_exact"]) and float(row["topdown_2d_iou"]) >= .95 for row in rows
    )
    high_mask_iou_topology = sum(
        not bool(row["topology_exact"]) and float(row["layout_mask_iou"]) >= .95 for row in rows
    )
    threshold_lines = []
    for split in ("test", "validation", "all"):
        scope = rows if split == "all" else [row for row in rows if row["split"] == split]
        threshold_lines.append(
            f"| {split} | {len(scope)} | {sum(bool(row['topology_exact']) for row in scope)} | "
            f"{sum(bool(row['initialization_acceptable']) for row in scope)} | "
            f"{sum(bool(row['initialization_correct']) for row in scope)} | "
            f"{sum(float(row['layout_mask_difference']) >= .10 for row in scope)} | "
            f"{sum(row['difference_band'] == 'nearly_no_difference' for row in scope)} |"
        )
    continuous_lines = [
        metric_line("Test 官方原始 GT（benchmark 对照）", test_rows, official_test=True),
        metric_line("Test 混合 GT（30人工+428官方）", test_rows),
        metric_line("Validation 官方原始 GT", validation_rows),
    ]
    corner_bin_lines = bin_lines("Test 官方", test_rows, official_test=True) + bin_lines("Validation", validation_rows)
    return f"""# HoHoNet 模型布局初始化代理全量审计（旧版 post-hoc v1 阈值保留版）

## 结论口径

本文件完整保留旧报告的二元判定体系，供历史结果复核和纵向比较；它不是唯一主分析。角点对数量门保持不变，`.90/.80/.05`、图宽 1% 角点门和较宽松的 `.75/.65/2%` 仍按旧版原样计算，但后几组数值均属分析者定义的 post-hoc operational thresholds，不能解释为文献统一标准或独立校准的最佳阈值。另见同目录的 `MODEL_INITIALIZATION_AUDIT_TOPOLOGY_PRIMARY.md`，其中只把角点对数量一致作为硬二元门，其余误差按连续量和多阈值敏感性报告。

本报告覆盖 Test 458 张与 Validation 190 张，共 {len(rows)} 张。Test 严格采用混合 GT：从 `export_label/groudTruth.json` 顺序无关识别出用户确认的 30 张实质修订并采用人工 GT，其余 428 张采用 `data/mp3d_layout/test/label_cor` 官方 GT；Validation 190 张全部采用 `data/mp3d_layout/valid/label_cor` 官方 GT。全程未使用 `test_no_occ` 或 `valid_no_occ`。30 张清单另见 `docs/thesis_main/TEST_MANUAL_GT_CORRECTIONS_20260823.md`。

当前产物是 HoHoNet ep300 的**最终布局输出**，仓库没有保存 raw corner probability/优化前峰值，因此本报告严谨称为 `final_layout_as_initialization_proxy`，不是网络内部原始初始化。

二元判定不由 IoU 单独决定：

1. `pair_structure_correct`：模型点对编码可解析，且模型与 GT 角点对数量相同。点对编码校验只检查偶数点、相邻 ceiling/floor 的 x 一致和上下关系；**没有**声称已经验证整圈自交或完整 Manhattan 正交约束。
2. `corner_localization_pass`：采用 ZInD/CVPR 2021 的图宽 1% 距离阈值（10.24 px），配合本项目确定性的 seam-aware greedy exclusive matching；所有 ceiling/floor 角点均匹配才通过。它是 point-level 匹配，不强制同一 wall pair 联合匹配。ZInD 只给出阈值与 P/R/F1，没有规定 greedy 算法，因此这里明确称为 ZInD-inspired 项目实现；在本次 648 张上用最大基数匹配复核，TP 未出现差异。
3. `geometry_acceptable`：本项目 v1 联合门，要求 top-down 2D IoU ≥ 0.90、LayoutNetv2-style derived 3D IoU ≥ 0.80、layout mask difference ≤ 0.05。文献没有统一的逐图二元阈值；`.90/.80/.05` 是本次审计在初次全量输出语义复核后由分析者定义的 post-hoc operational threshold，未预注册、未用独立验证集校准，不应冒充文献标准或无偏 benchmark cutoff。它们从本报告起按 v1 固定，供后续复现或前瞻应用。
4. `initialization_correct = pair_structure_correct AND corner_localization_pass AND geometry_acceptable`。任何角点对数量变化仍先判 `wrong_initialization_topology`，高 IoU 不得覆盖。
5. `initialization_acceptable` 是“可作为人工编辑起点”的较宽松辅助口径：角点对数量一致、top-down 2D IoU ≥ 0.75、derived 3D IoU ≥ 0.65、归一化角点均值误差 ≤ 2%。它同样是分析者定义、非文献统一阈值；严格失败不自动等于不可用。
6. `nearly_no_difference` 是更严格的展示层：初始化严格正确、最大循环对齐角点误差不超过 2.56 px、布局 mask 差异不超过 0.01。

本数据中有 {high_iou_topology} 张拓扑错误图片的 top-down 2D IoU 仍 ≥ 0.95，{high_mask_iou_topology} 张拓扑错误图片的 layout mask IoU 仍 ≥ 0.95，直接证明面积 IoU 不能替代拓扑门。

`layout_depth_rmse_proxy` 与 `layout_depth_delta1_proxy` 比较的是由模型角点和 GT 角点各自合成的 layout depth，不是真实 Matterport depth map；仓库当前没有为这 648 张绑定真实 depth GT，因此不得把这两列解释成 LayoutNetv2 官方 depth RMSE/δ1。

## 汇总

| split | 总数 | 拓扑一致 | 可用初始化 | 严格正确 | mask diff≥.10 | 几乎无差异 |
|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(threshold_lines)}

这里的“严格正确”应完整表述为**事后定义的严格审计通过**：它是三道门的合取，不是 HoHoNet benchmark 的“成功率”。“可用初始化”也是辅助运营口径；两者都不得与连续 IoU 均值混写成同一种百分比。

## 与 HoHoNet 官方连续指标对照

| 口径 | N | 2D IoU(%) | 3D IoU(%) | layout-depth RMSE | delta1 |
|---|---:|---:|---:|---:|---:|
{chr(10).join(continuous_lines)}

Test 官方原始 GT 的 2D/3D IoU 已与仓库 `eval_layout.py` 对齐；v2 曾在计算前按 x 重排角点，破坏了全景布局的原始环序，现已改为保留 consecutive ceiling/floor pair 的原始 cyclic order。Test 的 81.97% 是 458 个连续 2D IoU 的均值，不是“458 张中 81.97% 严格成功”。

| split | GT角点对 | N | 2D IoU(%) | 3D IoU(%) |
|---|---:|---:|---:|---:|
{chr(10).join(corner_bin_lines)}

Validation 相对 Test 的优势在 4、6、8、10+ 每个复杂度层都存在，因此不是仅由角点数量构成造成。两个 split 的建筑 ID 完全不重叠；Validation 是开发/调参集，Test 才是最终泛化集，当前差距应解释为 split 难度与开发集选择偏差，而不是把 Validation 当作对 Test 成功率的先验保证。

## Test GT 修订前后敏感性

| Test GT 口径 | 拓扑错误 | 定位错误 | 几何错误 | 可用初始化 | 严格正确（含 nearly） | nearly |
|---|---:|---:|---:|---:|---:|---:|
| 全部官方 GT（旧敏感性口径） | {official_lane[0]} | {official_lane[1]} | {official_lane[2]} | {official_test_acceptable} | {official_lane[3]} | {official_lane[4]} |
| 30张人工 + 428张官方（当前主口径） | {hybrid_lane[0]} | {hybrid_lane[1]} | {hybrid_lane[2]} | {hybrid_test_acceptable} | {hybrid_lane[3]} | {hybrid_lane[4]} |

30 张人工 GT 中，`initialization_class` 相对官方敏感性口径改变 {manual_class_changed} 张，拓扑一致状态改变 {manual_topology_changed} 张。混合 GT 把 Test 严格正确从 {official_lane[3]} 张调整为 {hybrid_lane[3]} 张、可用初始化从 {official_test_acceptable} 张调整为 {hybrid_test_acceptable} 张。

## 为什么修订后仍有较多严格失败

- 其余 428 张完全沿用官方 GT，其中仍有 {unchanged_official_topology_errors} 张模型/GT 角点对数量不同；这部分与 30 张人工 GT 无关。
- 30 张人工修订在全官方敏感性口径下有 {manual_official_topology_errors} 张拓扑不一致；换成人工 GT 后为 {manual_hybrid_topology_errors} 张，其中修正 {manual_topology_resolved} 张、同时新增 {manual_topology_introduced} 张，净变化为 Test `168 → 171`。
- Test 中模型角点对多于 GT 的有 {model_more} 张、少于 GT 的有 {model_fewer} 张，方向基本对称，不像单纯误用 no-occ 所造成的单向删角。
- 独立复核确认：458 个模型 TXT 与 `output/layout_json` 逐点一致，均为 ep300；Label Studio import proposal 与这些输出的图片 ID/坐标绑定无误；模型与 GT 均在 1024×512 坐标系。未发现目录、尺度或图片错绑制造这些拓扑错误。v2 的**指标实现**确有环序重排错误，已在 v3 修复；它影响连续 IoU 与少量阈值边界分类，但不制造 model/GT 角点对数量差。
- 当前“严格失败”规则故意很严：任何多/少一个墙角对都直接失败。Test 的严格正确为 {hybrid_lane[3]}/458，但较宽松的可用初始化为 {hybrid_test_acceptable}/458；两者回答的问题不同。

全量类别计数：{dict(sorted(counts.items()))}

- Test：{dict(sorted(split_counts['test'].items()))}
- Validation：{dict(sorted(split_counts['validation'].items()))}

## 差异大代表图：拓扑错误

{_markdown_table(topology_examples) if topology_examples else '无。'}

## 差异大代表图：角点定位错误

{_markdown_table(localization_examples) if localization_examples else '无。'}

## 差异大代表图：角点层通过但几何门失败

{_markdown_table(geometry_examples) if geometry_examples else '无。'}

## 几乎无差异代表图

{_markdown_table(near) if near else '无。'}

## 指标依据

- [HorizonNet 官方仓库](https://github.com/sunset1995/HorizonNet)：2D IoU、3D IoU、Corner Error、Pixel Error。
- [LayoutNetv2 官方仓库](https://github.com/zouchuhang/LayoutNetv2)：Matterport3D/general Manhattan 使用 3D IoU、top-down 2D IoU、depth RMSE、delta1；其中官方 depth 指标读取真实深度，本报告只有明确标记的 layout-depth proxy。
- [Zillow Indoor Dataset, CVPR 2021](https://openaccess.thecvf.com/content/CVPR2021/papers/Cruz_Zillow_Indoor_Dataset_Annotated_Floor_Plans_With_360deg_Panoramas_and_CVPR_2021_paper.pdf)：角点以训练图宽 1% 为距离阈值并报告 Precision/Recall/F1；本文未规定本项目采用的 greedy 匹配算法。
- [ZInD 补充材料](https://openaccess.thecvf.com/content/CVPR2021/supplemental/Cruz_Zillow_Indoor_Dataset_CVPR_2021_supplemental.pdf)：给出 IoU 超过 95% 但未捕捉 bay-window 结构的反例，说明 IoU 不能覆盖拓扑错误。

## 数据与可复现性

- 全量逐图 CSV：`{manifest['outputs']['csv']}`
- 运行清单：`{manifest['output_dir']}/run_manifest.json`
- 坐标统一为 1024×512；仅可视化叠加到 2048×1024 原图时才放大 2 倍。
- Validation 模型 txt 在 `output/` 中缺失；本次使用 `analysis_results/c2b_validation_static_20260802_v16/validation_prediction_txt`。已用 GPU、同一 config/checkpoint 和 190 张原图独立重跑到 `analysis_results/model_initialization_validation_ep300_replay_20260823_v1/prediction_txt`：旧/新 188/190 张角点对数量一致，174/190 张的全点最大偏差不超过 2 px；官方 evaluator 的连续指标分别为旧产物 92.58/91.64、新重跑 93.48/92.79（2D/3D IoU）。因此旧产物来源得到实证支持，但二元后处理在少数近阈值样本上有环境敏感性。
- GPU 重跑命令、输入/输出聚合哈希与旧/新逐图对照：`{manifest.get('evidence', {}).get('gpu_replay_manifest', '未绑定')}`。
- checkpoint SHA-256：`{manifest['checkpoint_sha256']}`。
"""


def _topology_primary_report(rows: list[dict[str, Any]], manifest: dict[str, Any]) -> str:
    test_rows = [row for row in rows if row["split"] == "test"]
    validation_rows = [row for row in rows if row["split"] == "validation"]

    def official_topology(row: dict[str, Any]) -> bool:
        classification = str(row.get("official_gt_sensitivity_initialization_class", ""))
        return classification != "wrong_initialization_topology" if classification else bool(row["topology_exact"])

    def topology_line(label: str, scope: list[dict[str, Any]], *, official_test: bool = False) -> str:
        passed = sum(official_topology(row) if official_test else bool(row["topology_exact"]) for row in scope)
        return f"| {label} | {len(scope)} | {passed} | {len(scope) - passed} | {100 * passed / len(scope):.2f} |"

    def metric_line(label: str, scope: list[dict[str, Any]], *, official_test: bool = False) -> str:
        def value(row: dict[str, Any], key: str) -> float:
            sensitivity = row.get(f"official_gt_sensitivity_{key}", "") if official_test else ""
            return float(sensitivity if sensitivity != "" else row[key])
        return (
            f"| {label} | {len(scope)} | "
            f"{100 * np.mean([value(row, 'topdown_2d_iou') for row in scope]):.2f} | "
            f"{100 * np.mean([value(row, 'layoutnetv2_style_3d_iou') for row in scope]):.2f} | "
            f"{np.mean([value(row, 'layout_depth_rmse_proxy') for row in scope]):.2f} | "
            f"{np.mean([value(row, 'layout_depth_delta1_proxy') for row in scope]):.2f} |"
        )

    topology_test = [row for row in test_rows if bool(row["topology_exact"])]
    topology_validation = [row for row in validation_rows if bool(row["topology_exact"])]

    def distribution_line(label: str, key: str, scale: float = 1.0) -> str:
        def summary(scope: list[dict[str, Any]]) -> str:
            values = np.asarray([float(row[key]) * scale for row in scope], dtype=np.float64)
            q1, median, q3 = np.quantile(values, [.25, .50, .75])
            return f"{median:.2f} [{q1:.2f}, {q3:.2f}]"
        return f"| {label} | {summary(topology_test)} | {summary(topology_validation)} |"

    def sensitivity_line(label: str, key: str, threshold: float, *, at_least: bool) -> str:
        def summary(scope: list[dict[str, Any]]) -> str:
            passed = sum(
                float(row[key]) >= threshold if at_least else float(row[key]) <= threshold
                for row in scope
            )
            return f"{passed}/{len(scope)} ({100 * passed / len(scope):.2f}%)"
        return f"| {label} | {summary(topology_test)} | {summary(topology_validation)} |"

    topology_lines = [
        topology_line("Test 官方原始 GT（敏感性）", test_rows, official_test=True),
        topology_line("Test 混合 GT（当前）", test_rows),
        topology_line("Validation 官方原始 GT", validation_rows),
    ]
    continuous_lines = [
        metric_line("Test 官方原始 GT（benchmark 对照）", test_rows, official_test=True),
        metric_line("Test 混合 GT（30人工+428官方）", test_rows),
        metric_line("Validation 官方原始 GT", validation_rows),
    ]
    distribution_lines = [
        distribution_line("top-down 2D IoU (%)", "topdown_2d_iou", 100),
        distribution_line("derived 3D IoU (%)", "layoutnetv2_style_3d_iou", 100),
        distribution_line("平均角点误差 / 图像对角线 (%)", "corner_error_percent_diagonal"),
        distribution_line("layout mask difference (%)", "layout_mask_difference", 100),
    ]
    sensitivity_lines = [
        sensitivity_line(f"2D IoU ≥ {threshold:.2f}", "topdown_2d_iou", threshold, at_least=True)
        for threshold in (.75, .80, .85, .90, .95)
    ] + [
        sensitivity_line(f"3D IoU ≥ {threshold:.2f}", "layoutnetv2_style_3d_iou", threshold, at_least=True)
        for threshold in (.65, .70, .75, .80, .85)
    ] + [
        sensitivity_line(f"平均角点误差 ≤ {threshold:.0f}% 对角线", "corner_error_percent_diagonal", threshold, at_least=False)
        for threshold in (1.0, 2.0, 3.0)
    ] + [
        sensitivity_line(f"mask difference ≤ {threshold:.2f}", "layout_mask_difference", threshold, at_least=False)
        for threshold in (.01, .05, .10)
    ]

    return f"""# HoHoNet 模型布局初始化代理审计（角点数量主分析版）

## 主结论

本版只把**点对编码合法且模型/GT 角点对数量完全一致**作为硬二元门。它保留用户旧报告最关心的角点数量标准，同时不把尚未独立校准的 IoU、角点距离或 mask difference 数值强行合并成另一个“成功/失败”结论。

当前对象仍是 HoHoNet ep300 保存的最终布局，即 `final_layout_as_initialization_proxy`，不是未保存的网络原始峰值。Test 采用 30 张人工校准 GT + 428 张官方 GT；Validation 190 张采用官方 GT；未使用 `test_no_occ` 或 `valid_no_occ`。

| 口径 | N | 角点对数量一致 | 数量不一致 | 一致率 (%) |
|---|---:|---:|---:|---:|
{chr(10).join(topology_lines)}

因此 Test 混合 GT 的角点数量主结果是 **{len(topology_test)}/{len(test_rows)}（{100 * len(topology_test) / len(test_rows):.2f}%）**；Validation 是 **{len(topology_validation)}/{len(validation_rows)}（{100 * len(topology_validation) / len(validation_rows):.2f}%）**。这是逐图拓扑代理通过率，不是官方 2D/3D IoU benchmark，也不等于“无需人工修改”。

## 连续 benchmark 指标

| 口径 | N | 2D IoU (%) | 3D IoU (%) | layout-depth RMSE | delta1 |
|---|---:|---:|---:|---:|---:|
{chr(10).join(continuous_lines)}

Test 官方原始 GT 的 81.97% 2D IoU 是 458 个逐图 IoU 的均值；它与上面的角点数量一致率回答不同问题。`layout-depth` 两列由布局角点合成深度，只是 proxy，不是真实 Matterport depth 指标。

## 数量一致样本中的误差分布

以下均为“中位数 [Q1, Q3]”，不设置通过门槛。

| 指标 | Test 混合 GT（N={len(topology_test)}） | Validation（N={len(topology_validation)}） |
|---|---:|---:|
{chr(10).join(distribution_lines)}

## 非拓扑误差的多阈值敏感性

各行仅单独应用一个阈值，分母均为本 split 中角点对数量一致的样本；这些行不能相加，也不代表推荐阈值。

| 单项敏感性条件 | Test 混合 GT | Validation |
|---|---:|---:|
{chr(10).join(sensitivity_lines)}

旧版 `.90/.80/.05` 联合门、图宽 1% 角点门和 `.75/.65/2%` 可用门仍完整保存在 `MODEL_INITIALIZATION_AUDIT_LEGACY_V1_THRESHOLDS.md` 及共享 CSV 的原字段中。若以后要把其他误差重新变成硬门，应使用独立人工“可编辑性/返工量”结局前瞻校准；不能依据当前 Test 结果反向挑阈值，也不应把已用于开发的 Validation 当独立校准集。

## 数据与复现

- 全量逐图 CSV：`{manifest['outputs']['csv']}`
- 旧版阈值报告：`{manifest['output_dir']}/MODEL_INITIALIZATION_AUDIT_LEGACY_V1_THRESHOLDS.md`
- 运行清单：`{manifest['output_dir']}/run_manifest.json`
- GPU 重跑证据：`{manifest.get('evidence', {}).get('gpu_replay_manifest', '未绑定')}`
- checkpoint SHA-256：`{manifest['checkpoint_sha256']}`
"""


def materialize(
    *, test_model_dir: Path, validation_model_dir: Path, test_gt_dir: Path,
    validation_gt_dir: Path, test_image_dir: Path, validation_image_dir: Path,
    test_manual_gt: Path, checkpoint: Path, output_dir: Path,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    input_files: dict[str, list[Path]] = {}

    test_models = {path.stem: path for path in test_model_dir.glob("*.txt")}
    test_official = {path.stem: path for path in test_gt_dir.glob("*.txt")}
    test_manual = _read_test_gt(test_manual_gt)
    if not test_models or set(test_models) != set(test_official) or set(test_models) != set(test_manual):
        raise ValueError("Test model, official GT, and manual GT identities differ")
    confirmed_manual_ids, manual_pairs = identify_confirmed_manual_gt(test_manual, test_official, test_manual_gt)
    official_sensitivity: dict[str, dict[str, Any]] = {}
    for image_id in sorted(test_models):
        image_path = test_image_dir / f"{image_id}.png"
        if not image_path.is_file():
            raise FileNotFoundError(image_path)
        if image_id in confirmed_manual_ids:
            rows.append(_metric_row(
                "test", image_id, test_models[image_id], test_manual_gt, image_path,
                gt=test_manual[image_id], gt_pairs=manual_pairs[image_id],
                gt_source_type="confirmed_user_manual_gt_correction",
            ))
            official_sensitivity[image_id] = _metric_row(
                "test", image_id, test_models[image_id], test_official[image_id], image_path,
                gt_source_type="official_mp3d_layout_label_cor_raw_not_no_occ",
            )
        else:
            rows.append(_metric_row(
                "test", image_id, test_models[image_id], test_official[image_id], image_path,
                gt_source_type="official_mp3d_layout_label_cor_raw_not_no_occ",
            ))
    input_files["test_model"] = list(test_models.values())
    input_files["test_official_gt"] = list(test_official.values())

    validation_models = {path.stem: path for path in validation_model_dir.glob("*.txt")}
    validation_gt = {path.stem: path for path in validation_gt_dir.glob("*.txt")}
    if not validation_models or set(validation_models) != set(validation_gt):
        raise ValueError("Validation model and official GT identities differ")
    for image_id in sorted(validation_models):
        image_path = validation_image_dir / f"{image_id}.png"
        if not image_path.is_file():
            raise FileNotFoundError(image_path)
        rows.append(_metric_row(
            "validation", image_id, validation_models[image_id], validation_gt[image_id], image_path,
            gt_source_type="official_mp3d_layout_label_cor_raw_not_no_occ",
        ))
    input_files["validation_model"] = list(validation_models.values())
    input_files["validation_gt"] = list(validation_gt.values())

    for row in rows:
        sensitivity = official_sensitivity.get(str(row["image_id"]))
        row.update({
            "official_gt_sensitivity_initialization_class": sensitivity["initialization_class"] if sensitivity else "",
            "official_gt_sensitivity_initialization_correct": sensitivity["initialization_correct"] if sensitivity else "",
            "official_gt_sensitivity_initialization_acceptable": sensitivity["initialization_acceptable"] if sensitivity else "",
            "official_gt_sensitivity_gt_pair_count": sensitivity["gt_pair_count"] if sensitivity else "",
            "official_gt_sensitivity_topdown_2d_iou": sensitivity["topdown_2d_iou"] if sensitivity else "",
            "official_gt_sensitivity_layoutnetv2_style_3d_iou": sensitivity["layoutnetv2_style_3d_iou"] if sensitivity else "",
            "official_gt_sensitivity_layout_depth_rmse_proxy": sensitivity["layout_depth_rmse_proxy"] if sensitivity else "",
            "official_gt_sensitivity_layout_depth_delta1_proxy": sensitivity["layout_depth_delta1_proxy"] if sensitivity else "",
            "hybrid_vs_official_class_changed": bool(sensitivity and sensitivity["initialization_class"] != row["initialization_class"]),
            "hybrid_vs_official_topology_changed": bool(sensitivity and sensitivity["topology_exact"] != row["topology_exact"]),
        })

    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "model_initialization_metrics.csv"
    _write_csv(csv_path, rows, list(rows[0]))
    manifest = {
        "schema_version": "model_initialization_audit_hybrid_gt_v4_two_report_views",
        "created_date": "2026-08-23",
        "row_count": len(rows),
        "split_counts": dict(Counter(row["split"] for row in rows)),
        "coordinate_space": [WIDTH, HEIGHT],
        "metric_object": "final_layout_as_initialization_proxy",
        "output_dir": _repo_path(output_dir),
        "gt_variant": "Test: 30 confirmed manual corrections + 428 official raw; Validation: 190 official raw; no no-occ",
        "manual_test_gt_path": _repo_path(test_manual_gt),
        "manual_test_gt_sha256": _sha256(test_manual_gt),
        "manual_test_gt_count": len(confirmed_manual_ids),
        "manual_test_gt_ids": sorted(confirmed_manual_ids),
        "pair_encoding_rule": "even point count >=4; consecutive ceiling/floor x distance <=1px; nonzero vertical separation; not a full Manhattan polygon validity check",
        "corner_match_rule": "ZInD-inspired 1%-width threshold with project-defined deterministic point-level greedy exclusive seam-aware Euclidean matching; not wall-pair-aware",
        "corner_match_threshold_px": CORNER_MATCH_THRESHOLD_PX,
        "geometry_acceptable_rule": "topdown_2d_iou>=0.90 AND layoutnetv2_style_3d_iou>=0.80 AND layout_mask_difference<=0.05",
        "geometry_threshold_status": "analyst-defined post-hoc operational v1 after initial full-output semantic review; not literature-standard, preregistered, or independently calibrated",
        "initialization_correct_rule": "valid pair encoding AND exact pair count AND all ceiling/floor corners matched at 10.24px AND geometry_acceptable",
        "initialization_acceptable_rule": "valid pair encoding AND exact pair count AND topdown_2d_iou>=0.75 AND layoutnetv2_style_3d_iou>=0.65 AND corner_error_percent_diagonal<=2.0; analyst-defined operational aid, not literature-standard",
        "primary_hard_gate": "valid pair encoding AND exact model/GT corner-pair count",
        "non_topology_metric_policy": "continuous primary reporting plus independent multi-threshold sensitivity; no single calibrated cutoff claimed",
        "legacy_posthoc_v1_status": "retained unchanged for historical comparison in a separate report; not the topology-primary conclusion",
        "near_identical_rule": "initialization_correct AND max_corner_error_px<=2.56 AND layout_mask_difference<=0.01",
        "depth_metric_note": "layout depth synthesized from model/GT corners; proxy only; no real Matterport depth GT bound",
        "layout_metric_order_rule": "preserve original consecutive-pair cyclic order; do not sort panorama corners by x before official-style 2D/3D/depth metrics",
        "checkpoint_path": _repo_path(checkpoint),
        "checkpoint_sha256": _sha256(checkpoint),
        "input_aggregate_sha256": {name: _aggregate_sha256(paths) for name, paths in input_files.items()},
        "validation_model_source_note": "verified ep300 frozen artifact; validation predictions are absent from output/",
        "outputs": {"csv": _repo_path(csv_path)},
    }
    replay_evidence_dir = ROOT / "analysis_results/model_initialization_audit_hybrid_gt_20260823_v3"
    replay_manifest_path = replay_evidence_dir / "GPU_REPLAY_MANIFEST.json"
    replay_config_path = replay_evidence_dir / "inference_replay_config.yaml"
    manifest["evidence"] = {}
    if replay_manifest_path.is_file():
        manifest["evidence"]["gpu_replay_manifest"] = _repo_path(replay_manifest_path)
    if replay_config_path.is_file():
        manifest["evidence"]["inference_replay_config"] = _repo_path(replay_config_path)
    legacy_report_path = output_dir / "MODEL_INITIALIZATION_AUDIT_LEGACY_V1_THRESHOLDS.md"
    topology_report_path = output_dir / "MODEL_INITIALIZATION_AUDIT_TOPOLOGY_PRIMARY.md"
    legacy_report_path.write_text(_report(rows, manifest), encoding="utf-8")
    topology_report_path.write_text(_topology_primary_report(rows, manifest), encoding="utf-8")
    manifest["outputs"].update({
        "legacy_v1_threshold_report": _repo_path(legacy_report_path),
        "topology_primary_report": _repo_path(topology_report_path),
    })
    manifest["output_sha256"] = {
        name: _sha256(ROOT / path) for name, path in manifest["outputs"].items()
    }
    (output_dir / "run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit HoHoNet final layouts as initialization proxies against raw official MP3D GT.")
    parser.add_argument("--test-model-dir", type=Path, default=ROOT / "output/mp3d_layout/HOHO_layout_aug_efficienthc_Transen1_resnet34")
    parser.add_argument("--validation-model-dir", type=Path, default=ROOT / "analysis_results/c2b_validation_static_20260802_v16/validation_prediction_txt")
    parser.add_argument("--test-gt-dir", type=Path, default=ROOT / "data/mp3d_layout/test/label_cor")
    parser.add_argument("--test-manual-gt", type=Path, default=ROOT / "export_label/groudTruth.json")
    parser.add_argument("--validation-gt-dir", type=Path, default=ROOT / "data/mp3d_layout/valid/label_cor")
    parser.add_argument("--test-image-dir", type=Path, default=ROOT / "data/mp3d_layout/test/img")
    parser.add_argument("--validation-image-dir", type=Path, default=ROOT / "data/mp3d_layout/valid/img")
    parser.add_argument("--checkpoint", type=Path, default=ROOT / "ckpt/mp3d_layout_HOHO_layout_aug_efficienthc_Transen1_resnet34/ep300.pth")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "analysis_results/model_initialization_audit_hybrid_gt_20260823_v4")
    args = parser.parse_args()
    print(json.dumps(materialize(**vars(args)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
