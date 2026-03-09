#可以运行脚本时指定 --metric corner 或 --metric manual。
import json
import csv
import argparse
import os
import sys
import glob
from datetime import datetime
import itertools
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
from scipy.optimize import linear_sum_assignment
from scipy.signal import savgol_filter
from collections import defaultdict
from shapely.geometry import Polygon
from shapely.validation import make_valid

# 添加项目根目录到 sys.path，确保无论从何处运行都能找到 lib 包
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from lib.misc import panostretch


_LABEL_STUDIO_CONFIG_PATH = Path(_project_root) / "tools" / "label_studio_view_config.xml"


def _load_label_studio_choice_alias_map(xml_path: Path) -> dict[str, dict[str, str]]:
    """Load Choice value->alias mappings per field name from Label Studio view config.

    We use aliases as stable IDs to:
    - Keep CSV fields concise and reproducible.
    - Align with perturbation operators (operator_id == alias).

    Returns:
      {"scope": {"In-scope：...": "normal", ...}, "model_issue": {...}, ...}
    """
    try:
        if not xml_path.exists():
            return {}
        root = ET.parse(str(xml_path)).getroot()
        out: dict[str, dict[str, str]] = {}
        for choices_node in root.iter():
            if choices_node.tag != "Choices":
                continue
            field_name = choices_node.attrib.get("name")
            if not field_name:
                continue
            mapping: dict[str, str] = out.setdefault(field_name, {})
            for choice_node in list(choices_node):
                if choice_node.tag != "Choice":
                    continue
                value_text = (choice_node.attrib.get("value") or "").strip()
                alias = (choice_node.attrib.get("alias") or "").strip()
                if value_text and alias:
                    mapping[value_text] = alias
        return out
    except Exception:
        return {}


_CHOICE_VALUE_TO_ALIAS_BY_FIELD: dict[str, dict[str, str]] = _load_label_studio_choice_alias_map(_LABEL_STUDIO_CONFIG_PATH)


def _map_choice_value_to_alias(field_name: str, value: str) -> str:
    """Map a Label Studio exported choice value to the configured alias when possible."""
    if not isinstance(value, str):
        return value
    v = value.strip()
    if not v:
        return ""
    mapping = _CHOICE_VALUE_TO_ALIAS_BY_FIELD.get(str(field_name), {})
    # If already an alias (common in hand-edited CSVs), keep it.
    if v in set(mapping.values()):
        return v
    return mapping.get(v, v)


def _normalize_choice_values(field_name: str, values) -> list[str]:
    """Split + map values to aliases with deterministic ordering and de-dup."""
    out: list[str] = []
    for v in _split_choice_values(values):
        v2 = _map_choice_value_to_alias(field_name, v)
        if v2 and v2 not in out:
            out.append(v2)
    return out


def _split_choice_values(values) -> list:
    """Split multi-choice strings like 'a;b;c' into a clean list.

    Label Studio v2 exports are lists already (from extract_data). We keep this
    helper to safely handle legacy/hand-edited CSV-like strings.
    """
    if values is None:
        return []
    if isinstance(values, (list, tuple)):
        out = []
        for v in values:
            if isinstance(v, str) and v.strip():
                out.append(v.strip())
        return out
    if isinstance(values, str):
        s = values.strip()
        if not s:
            return []
        return [x.strip() for x in s.split(";") if x.strip()]
    return []


_MODEL_ISSUE_TAG_REMAP = {
    # Legacy UI option kept in historical CSVs; replaced by the new ontology.
    "corner_mismatch": "topology_failure",
}


def _normalize_model_issue_values(values) -> list[str]:
    """Normalize model_issue tags to the current ontology.

    - Keeps ordering.
    - Removes empties.
    - Remaps legacy tags (e.g., corner_mismatch -> topology_failure).
    """
    out: list[str] = []
    for v in _split_choice_values(values):
        v2 = _MODEL_ISSUE_TAG_REMAP.get(v, v)
        if v2 and v2 not in out:
            out.append(v2)
    return out


_MODEL_ISSUE_PRIMARY_PRIORITY = [
    # Higher = more severe / more diagnostic; deterministic if multiple selected.
    "fail",
    "topology_failure",
    "corner_duplicate",
    "corner_drift",
    "over_parsing",
    "overextend_adjacent",
    "underextend",
]


def _pick_primary_model_issue(issue_types: list[str]) -> str:
    if not issue_types:
        return ""
    issue_set = set([str(x).strip() for x in issue_types if str(x).strip()])
    for t in _MODEL_ISSUE_PRIMARY_PRIORITY:
        if t in issue_set:
            return t
    return sorted(issue_set)[0] if issue_set else ""


def _scope_is_oos(scope_values: list) -> bool:
    """Decide OOS purely from structured scope field when present."""
    for s in _split_choice_values(scope_values):
        sl = s.lower()
        if sl.startswith("oos") or ("out-of-scope" in sl) or ("out of scope" in sl) or ("oos：" in s) or ("oos:" in sl):
            return True
        if "边界不可判定" in s or "几何假设不成立" in s or "错层" in s or "多平面" in s or "证据不足" in s:
            return True
    return False


def _has_token_in_choices(choice_values: list, tokens: list) -> bool:
    q = ";".join(_split_choice_values(choice_values)).lower()
    return any((t.lower() in q) for t in tokens)


def _has_prediction_fail(choice_values: list) -> bool:
    """Strictly detect prediction-failure tags from model_issue.

    NOTE:
    - Do NOT use generic substring 'fail' matching, otherwise tags like
      'Topological failure' would be misclassified as prediction failure.
    - Keep backward compatibility for legacy compact value 'fail'.
    """
    for s in _split_choice_values(choice_values):
        sl = s.strip().lower()
        if sl == "fail":
            return True
        if "prediction failure" in sl:
            return True
        if "预标注失效" in s or "模型预标注失效" in s:
            return True
    return False


def parse_quality_flags_v2(choice_map: dict, quality_all: str = "", mode: str = "v2") -> dict:
    """Parse flags using v2 structured fields.

    This repo is v2-only: we do NOT fall back to legacy free-text keyword parsing.
    If v2 structured fields are missing, we return tri-state unknowns and mark
    scope_missing=True so downstream filtering can make an explicit choice.
    """
    choice_map = choice_map or {}

    mode_norm = str(mode or "v2").strip().lower()
    if mode_norm != "v2":
        raise ValueError(f"quality_mode must be 'v2' (got: {mode!r})")

    scope_vals = _normalize_choice_values("scope", choice_map.get("scope", []))
    diff_vals = _normalize_choice_values("difficulty", choice_map.get("difficulty", []))
    model_vals = _normalize_model_issue_values(_normalize_choice_values("model_issue", choice_map.get("model_issue", [])))
    tool_vals = _normalize_choice_values("tool_issue", choice_map.get("tool_issue", []))

    has_structured = bool(scope_vals or diff_vals or model_vals or tool_vals)
    scope_missing = not bool(_split_choice_values(scope_vals))
    difficulty_missing = not bool(_split_choice_values(diff_vals))
    model_issue_missing = not bool(_split_choice_values(model_vals))

    difficulty_conflict = ("trivial" in set([str(x).strip().lower() for x in diff_vals]) and len(diff_vals) > 1)
    model_issue_conflict = ("acceptable" in set([str(x).strip().lower() for x in model_vals]) and len(model_vals) > 1)

    if has_structured:
        # IMPORTANT: if structured fields exist but scope is empty, treat it as UNKNOWN.
        # Do not silently fold it into in-scope; downstream filtering/plots can decide.
        is_oos = None if scope_missing else _scope_is_oos(scope_vals)
        # Difficulty: only set coarse booleans; keep the raw strings in CSV for detailed analysis.
        is_occlusion = _has_token_in_choices(diff_vals, ["occlusion", "遮挡"])
        is_residual = _has_token_in_choices(diff_vals, ["residual", "尽力调整", "仍不佳", "hard to align", "对齐困难"])
        # Model init failure: from model_issue choices only (strict matching).
        is_fail = _has_prediction_fail(model_vals)

        # In-scope flag is the complement of OOS within scope selections.
        scope_text = ";".join(_split_choice_values(scope_vals)).lower()
        is_normal = None if scope_missing else (
            ("in-scope" in scope_text or "camera room" in scope_text or "normal" in scope_text or "只标相机房间" in scope_text)
            and not bool(is_oos)
        )

        return {
            "scope_missing": bool(scope_missing),
            "difficulty_missing": bool(difficulty_missing),
            "model_issue_missing": bool(model_issue_missing),
            "difficulty_conflict": bool(difficulty_conflict),
            "model_issue_conflict": bool(model_issue_conflict),
            "is_oos": is_oos,
            "is_occlusion": bool(is_occlusion),
            "is_fail": bool(is_fail),
            "is_residual": bool(is_residual),
            "is_normal": is_normal,
        }

    # No structured fields found.
    # IMPORTANT (paper/reproducibility): do NOT infer scope from legacy free-text.
    return {
        "scope_missing": True,
        "difficulty_missing": True,
        "model_issue_missing": True,
        "difficulty_conflict": False,
        "model_issue_conflict": False,
        "is_oos": None,
        "is_occlusion": False,
        "is_fail": False,
        "is_residual": False,
        "is_normal": None,
    }


def _safe_float(x):
    try:
        if x is None:
            return None
        if isinstance(x, bool):
            return float(x)
        s = str(x).strip()
        if s == "" or s.lower() in {"none", "nan"}:
            return None
        return float(s)
    except Exception:
        return None


def _mean(values: list):
    vals = [v for v in values if v is not None]
    return float(np.mean(vals)) if vals else None


def _summarize_by_tag(rows: list, tag_field: str, multi: bool, metrics: list, title: str, top_k: int = 20):
    """Print per-tag summary so UI options become interpretable outputs.

    This is intentionally console-only to keep the pipeline lightweight.
    """
    tag_to_rows = defaultdict(list)
    for r in rows:
        raw = r.get(tag_field, "")
        if multi:
            tags = _split_choice_values(raw)
        else:
            tags = _split_choice_values(raw)[:1] if raw else []
        if not tags:
            tag_to_rows["(empty)"].append(r)
            continue
        for t in tags:
            tag_to_rows[t].append(r)

    # Build sortable items
    items = []
    for tag, rs in tag_to_rows.items():
        item = {"tag": tag, "n": len(rs)}
        for m in metrics:
            item[m] = _mean([_safe_float(x.get(m)) for x in rs])
        items.append(item)

    items.sort(key=lambda d: (d["n"], (d.get(metrics[0]) is not None), (d.get(metrics[0]) or -1e9)), reverse=True)

    print(f"\n--- {title} ---")
    header = ["tag", "n"] + [f"mean_{m}" for m in metrics]
    print(" | ".join([f"{h:<22}" for h in header]))
    for it in items[: int(max(1, top_k))]:
        parts = [f"{it['tag'][:22]:<22}", f"{it['n']:<22d}"]
        for m in metrics:
            v = it.get(m)
            parts.append(f"{('' if v is None else f'{v:.4f}'):<22}")
        print(" | ".join(parts))


def _postproc_coorx2u(coorx: np.ndarray, coorW: int = 1024) -> np.ndarray:
    return ((coorx + 0.5) / float(coorW) - 0.5) * 2.0 * np.pi


def _postproc_coory2v(coory: np.ndarray, coorH: int = 512) -> np.ndarray:
    # Match lib.misc.post_proc.np_coory2v sign convention
    return -((coory + 0.5) / float(coorH) - 0.5) * np.pi


def _postproc_coor2xy(
    coor: np.ndarray,
    z: float,
    coorW: int = 1024,
    coorH: int = 512,
    floorW: float = 1.0,
    floorH: float = 1.0,
) -> np.ndarray:
    coor = np.asarray(coor, dtype=np.float32)
    u = _postproc_coorx2u(coor[:, 0], coorW)
    v = _postproc_coory2v(coor[:, 1], coorH)
    c = z / np.tan(v)
    x = c * np.sin(u) + floorW / 2.0 - 0.5
    y = -c * np.cos(u) + floorH / 2.0 - 0.5
    return np.stack([x, y], axis=1).astype(np.float32)


def _postproc_get_z1(coory0: np.ndarray, coory1: np.ndarray, z0: float, coorH: int = 512) -> np.ndarray:
    v0 = _postproc_coory2v(np.asarray(coory0, dtype=np.float32), coorH)
    v1 = _postproc_coory2v(np.asarray(coory1, dtype=np.float32), coorH)
    c0 = z0 / np.tan(v0)
    z1 = c0 * np.tan(v1)
    return z1.astype(np.float32)


def _dataset_v_from_y(y_px: np.ndarray, H: int) -> np.ndarray:
    # Match lib.dataset.dataset_layout.cor_2_1d: ((y+0.5)/H - 0.5) * pi
    y_px = np.asarray(y_px, dtype=np.float32)
    return ((y_px + 0.5) / float(H) - 0.5) * np.pi


def _layout_depth_from_cor_id(cor_id: np.ndarray, H: int, W: int) -> np.ndarray:
    # Equivalent to eval_layout.layout_2_depth, but avoids importing torch/sklearn.
    y_ceil, y_floor = _boundary_from_cor_id_connect(cor_id, width=W, height=H)
    if y_ceil is None or y_floor is None:
        return None
    vc = _dataset_v_from_y(y_ceil, H)[None, :]  # [1, W]
    vf = _dataset_v_from_y(y_floor, H)[None, :]  # [1, W]

    vs = ((np.arange(H, dtype=np.float32) + 0.5) / float(H) - 0.5) * np.pi
    vs = np.repeat(vs[:, None], W, axis=1)  # [H, W]

    floor_h = 1.6
    floor_d = np.abs(floor_h / np.sin(vs))
    cs = floor_h / np.tan(vf)
    ceil_h = np.abs(cs * np.tan(vc))
    ceil_d = np.abs(ceil_h / np.sin(vs))
    wall_d = np.abs(cs / np.cos(vs))

    floor_mask = (vs > vf)
    ceil_mask = (vs < vc)
    wall_mask = (~floor_mask) & (~ceil_mask)
    depth = np.zeros((H, W), dtype=np.float32)
    depth[floor_mask] = floor_d[floor_mask]
    depth[ceil_mask] = ceil_d[ceil_mask]
    depth[wall_mask] = wall_d[wall_mask]
    # 检测无效值：零、无穷大、NaN（三角函数在边界情况下会产生 inf）
    if (depth == 0).any() or np.isinf(depth).any() or np.isnan(depth).any():
        return None
    return depth


def compute_layout_standard_metrics(
    pred_corners: np.ndarray,
    ann_corners: np.ndarray,
    width: int = 1024,
    height: int = 512,
    min_coverage: float = 0.9,
    threshold_ratio: float = 0.05,
) -> tuple:
    """Compute HoHoNet/HorizonNet-style metrics: 2D/3D IoU on floor plane + depth RMSE/delta_1.

    Returns:
      (iou2d, iou3d, depth_rmse, delta_1, used:bool, meta)
    """
    meta = {"gate_reason": ""}

    pred_cor_id, pred_stats = _normalize_to_cor_id_pairs(pred_corners, width=width, threshold_ratio=threshold_ratio)
    ann_cor_id, ann_stats = _normalize_to_cor_id_pairs(ann_corners, width=width, threshold_ratio=threshold_ratio)

    if pred_cor_id is None or ann_cor_id is None:
        meta["gate_reason"] = "normalize_failed"
        return None, None, None, None, False, meta
    if bool(pred_stats.get("odd_points", False)) or bool(ann_stats.get("odd_points", False)):
        meta["gate_reason"] = "odd_points"
        return None, None, None, None, False, meta
    if float(pred_stats.get("coverage", 0.0)) < float(min_coverage) or float(ann_stats.get("coverage", 0.0)) < float(min_coverage):
        meta["gate_reason"] = "low_coverage"
        return None, None, None, None, False, meta

    dt_floor = pred_cor_id[1::2]
    dt_ceil = pred_cor_id[0::2]
    gt_floor = ann_cor_id[1::2]
    gt_ceil = ann_cor_id[0::2]
    if (dt_floor[:, 0] != dt_ceil[:, 0]).any() or (gt_floor[:, 0] != gt_ceil[:, 0]).any():
        meta["gate_reason"] = "x_inconsistent"
        return None, None, None, None, False, meta

    # 2D/3D IoU on floor plane (matches eval_layout.test_general formulation)
    ch = -1.6
    try:
        dt_xy = _postproc_coor2xy(dt_floor, z=ch, coorW=width, coorH=height, floorW=1.0, floorH=1.0)
        gt_xy = _postproc_coor2xy(gt_floor, z=ch, coorW=width, coorH=height, floorW=1.0, floorH=1.0)
        dt_poly = Polygon(dt_xy)
        gt_poly = Polygon(gt_xy)
        if (not dt_poly.is_valid) or (not gt_poly.is_valid) or dt_poly.area <= 0 or gt_poly.area <= 0:
            raise ValueError("invalid_polygon")
        area_dt = float(dt_poly.area)
        area_gt = float(gt_poly.area)
        area_inter = float(dt_poly.intersection(gt_poly).area)
        denom = (area_gt + area_dt - area_inter)
        iou2d = float(area_inter / denom) if denom > 0 else 0.0
    except Exception:
        iou2d = 0.0
        area_dt = None
        area_gt = None
        area_inter = None

    try:
        cch_dt = _postproc_get_z1(dt_floor[:, 1], dt_ceil[:, 1], z0=ch, coorH=height)
        cch_gt = _postproc_get_z1(gt_floor[:, 1], gt_ceil[:, 1], z0=ch, coorH=height)
        h_dt = float(abs(float(np.mean(cch_dt)) - ch))
        h_gt = float(abs(float(np.mean(cch_gt)) - ch))
        if area_inter is None or area_dt is None or area_gt is None:
            raise ValueError("missing_area")
        area3d_inter = float(area_inter) * min(h_dt, h_gt)
        area3d_dt = float(area_dt) * h_dt
        area3d_gt = float(area_gt) * h_gt
        denom = (area3d_dt + area3d_gt - area3d_inter)
        iou3d = float(area3d_inter / denom) if denom > 0 else 0.0
    except Exception:
        iou3d = 0.0

    # depth RMSE / delta_1 (matches eval_layout.layout_2_depth behavior)
    gt_depth = _layout_depth_from_cor_id(ann_cor_id, H=height, W=width)
    dt_depth = _layout_depth_from_cor_id(pred_cor_id, H=height, W=width)
    if gt_depth is None or dt_depth is None:
        meta["gate_reason"] = "depth_failed"
        return iou2d, iou3d, None, None, True, meta

    depth_rmse = float(np.sqrt(np.mean((gt_depth - dt_depth) ** 2)))
    eps = 1e-6
    thres = np.maximum(gt_depth / np.maximum(dt_depth, eps), dt_depth / np.maximum(gt_depth, eps))
    delta_1 = float(np.mean(thres < 1.25))
    meta["gate_reason"] = ""
    return iou2d, iou3d, depth_rmse, delta_1, True, meta


def _bootstrap_ci(values, stat_fn, n_iters: int = 1000, ci: float = 0.95, seed: int = 0):
    """Percentile bootstrap CI for a statistic.

    Returns (stat, ci_low, ci_high). If values is empty or all-NaN, returns (None, None, None).
    """
    vals = np.asarray(values, dtype=np.float32)
    vals = vals[~np.isnan(vals)]  # 过滤 NaN，避免统计函数返回 nan
    if vals.size == 0:
        return None, None, None

    stat = float(stat_fn(vals))
    if vals.size == 1:
        return stat, stat, stat

    n_iters = int(max(1, n_iters))
    ci = float(ci)
    ci = min(max(ci, 0.0), 1.0)
    alpha = 0.5 * (1.0 - ci)
    lo_q = 100.0 * alpha
    hi_q = 100.0 * (1.0 - alpha)

    rng = np.random.default_rng(int(seed))
    n = int(vals.size)
    boot = np.empty((n_iters,), dtype=np.float32)
    for i in range(n_iters):
        sample = rng.choice(vals, size=n, replace=True)
        boot[i] = float(stat_fn(sample))

    ci_low, ci_high = np.percentile(boot, [lo_q, hi_q]).astype(np.float32).tolist()
    return stat, float(ci_low), float(ci_high)


def _pair_keypoints_to_layout(corners: np.ndarray, width: int, threshold_ratio: float = 0.05, return_stats: bool = False):
    """Pair raw keypoints into layout columns (x, y_ceiling, y_floor).

    Label Studio may store corners as an unordered set of keypoints.
    HoHoNet layout uses paired ceiling/floor points at similar x.

    Returns:
      - by default: a list of dicts: {x, y_ceiling, y_floor}
      - if return_stats=True: (paired, stats)
    """
    if corners is None:
        if return_stats:
            return [], {"n_points": 0, "n_pairs": 0, "coverage": 0.0, "odd_points": False}
        return []
    corners = np.asarray(corners)
    if corners.ndim != 2 or corners.shape[0] < 2:
        n_points = int(corners.shape[0]) if corners.ndim == 2 else 0
        if return_stats:
            return [], {"n_points": n_points, "n_pairs": 0, "coverage": 0.0, "odd_points": (n_points % 2 == 1)}
        return []

    pts = [{"x": float(x), "y": float(y)} for x, y in corners.tolist()]
    pts.sort(key=lambda p: p["x"])
    used = [False] * len(pts)
    threshold = float(width) * float(threshold_ratio)

    paired = []
    for i in range(len(pts)):
        if used[i]:
            continue
        best_j = -1
        for j in range(i + 1, len(pts)):
            if used[j]:
                continue
            if abs(pts[j]["x"] - pts[i]["x"]) < threshold:
                best_j = j
                break
        if best_j == -1:
            continue
        used[i] = True
        used[best_j] = True
        p1 = pts[i]
        p2 = pts[best_j]
        paired.append(
            {
                "x": 0.5 * (p1["x"] + p2["x"]),
                "y_ceiling": min(p1["y"], p2["y"]),
                "y_floor": max(p1["y"], p2["y"]),
            }
        )
    if not return_stats:
        return paired

    n_points = len(pts)
    n_pairs = len(paired)
    coverage = (2.0 * float(n_pairs) / float(n_points)) if n_points > 0 else 0.0
    stats = {
        "n_points": int(n_points),
        "n_pairs": int(n_pairs),
        "coverage": float(coverage),
        "odd_points": (n_points % 2 == 1),
    }
    return paired, stats


def _interp_periodic(x_nodes: np.ndarray, y_nodes: np.ndarray, width: int) -> np.ndarray:
    """Periodic 1D interpolation to integer x grid [0, width)."""
    if x_nodes.size == 0:
        return np.array([], dtype=np.float32)

    x_nodes = np.asarray(x_nodes, dtype=np.float32) % float(width)
    y_nodes = np.asarray(y_nodes, dtype=np.float32)

    order = np.argsort(x_nodes)
    x_nodes = x_nodes[order]
    y_nodes = y_nodes[order]

    # Deduplicate x to avoid np.interp warnings/undefined behavior.
    # Keep the last value for each x.
    uniq_x = []
    uniq_y = []
    last_x = None
    for x, y in zip(x_nodes.tolist(), y_nodes.tolist()):
        if last_x is not None and abs(x - last_x) < 1e-6:
            uniq_y[-1] = y
        else:
            uniq_x.append(x)
            uniq_y.append(y)
            last_x = x

    x_nodes = np.asarray(uniq_x, dtype=np.float32)
    y_nodes = np.asarray(uniq_y, dtype=np.float32)

    xq = np.arange(width, dtype=np.float32)
    if x_nodes.size == 1:
        return np.full((width,), float(y_nodes[0]), dtype=np.float32)

    # np.interp supports `period` for circular domains.
    return np.interp(xq, x_nodes, y_nodes, period=float(width)).astype(np.float32)


def _sort_xy_filter_unique(xs, ys, y_small_first: bool = True):
    xs = np.array(xs, dtype=np.float32)
    ys = np.array(ys, dtype=np.float32)
    if xs.size == 0:
        return xs, ys
    # Tie-break by y to keep deterministic ordering when xs collide.
    idx_sort = np.argsort(xs + ys / (ys.max() + 1e-6) * ((int(y_small_first) * 2) - 1))
    xs, ys = xs[idx_sort], ys[idx_sort]
    _, idx_unique = np.unique(xs, return_index=True)
    xs, ys = xs[idx_unique], ys[idx_unique]
    return xs, ys


def _normalize_to_cor_id_pairs(corners: np.ndarray, width: int, threshold_ratio: float = 0.05):
    """Try to normalize unordered points into HoHoNet-style cor_id (ceil/floor paired, sorted by x).

    Returns (cor_id, stats) or (None, stats) if not possible.
    """
    paired, stats = _pair_keypoints_to_layout(corners, width=width, threshold_ratio=threshold_ratio, return_stats=True)
    if stats.get("n_pairs", 0) < 2:
        return None, stats

    # Build HoHoNet-style cor_id: [ceil0, floor0, ceil1, floor1, ...] sorted by x
    paired_sorted = sorted(paired, key=lambda p: p["x"])
    cor_id = np.zeros((len(paired_sorted) * 2, 2), dtype=np.float32)
    for i, p in enumerate(paired_sorted):
        x = float(p["x"]) % float(width)
        cor_id[i * 2] = [x, float(p["y_ceiling"])]
        cor_id[i * 2 + 1] = [x, float(p["y_floor"])]

    # Extra validity checks similar to HoHoNet expectations
    xs = cor_id[::2, 0]
    if np.any(np.diff(xs) < 0):
        # Should not happen after sorting, but keep safe.
        return None, stats
    if np.any(np.abs(cor_id[::2, 0] - cor_id[1::2, 0]) > 1e-3):
        return None, stats

    return cor_id, stats


def _boundary_from_cor_id_connect(cor_id: np.ndarray, width: int, height: int):
    """HoHoNet-style boundary generation using pano_connect_points (more geometric than direct interp).

    cor_id: (2N,2) [ceil0,floor0,ceil1,floor1,...], sorted by x.
    Returns y_ceil, y_floor in pixel y (length=width).
    """
    cor_id = np.asarray(cor_id, dtype=np.float32)
    if cor_id.ndim != 2 or cor_id.shape[0] < 4 or cor_id.shape[0] % 2 != 0:
        return None, None

    n_cor = int(cor_id.shape[0])
    # Build dense ceiling boundary samples by connecting adjacent ceiling corners.
    bon_ceil_x, bon_ceil_y = [], []
    bon_floor_x, bon_floor_y = [], []
    for i in range(n_cor // 2):
        xys = panostretch.pano_connect_points(
            cor_id[i * 2],
            cor_id[(i * 2 + 2) % n_cor],
            z=-50,
            w=width,
            h=height,
        )
        bon_ceil_x.extend(xys[:, 0].tolist())
        bon_ceil_y.extend(xys[:, 1].tolist())
    for i in range(n_cor // 2):
        xys = panostretch.pano_connect_points(
            cor_id[i * 2 + 1],
            cor_id[(i * 2 + 3) % n_cor],
            z=50,
            w=width,
            h=height,
        )
        bon_floor_x.extend(xys[:, 0].tolist())
        bon_floor_y.extend(xys[:, 1].tolist())

    bon_ceil_x, bon_ceil_y = _sort_xy_filter_unique(bon_ceil_x, bon_ceil_y, y_small_first=True)
    bon_floor_x, bon_floor_y = _sort_xy_filter_unique(bon_floor_x, bon_floor_y, y_small_first=False)
    if bon_ceil_x.size < 2 or bon_floor_x.size < 2:
        return None, None

    xq = np.arange(width, dtype=np.float32)
    y_ceil = np.interp(xq, bon_ceil_x, bon_ceil_y, period=float(width)).astype(np.float32)
    y_floor = np.interp(xq, bon_floor_x, bon_floor_y, period=float(width)).astype(np.float32)
    return y_ceil, y_floor


def _smooth_piecewise(y: np.ndarray, height: int, window: int = 31, poly: int = 3, jump_ratio: float = 0.25) -> np.ndarray:
    """Piecewise smoothing to avoid blurring across large discontinuities.

    The layout boundary on panorama can have seam-related discontinuities.
    We split segments at large jumps and apply Savitzky-Golay per segment.
    """
    y = np.asarray(y, dtype=np.float32)
    if y.size < 3:
        return y

    jump_thresh = float(height) * float(jump_ratio)
    jumps = np.where(np.abs(np.diff(y)) > jump_thresh)[0]
    # segment boundaries: [0, j+1), ...
    splits = [0] + (jumps + 1).tolist() + [y.size]

    out = y.copy()
    for a, b in zip(splits[:-1], splits[1:]):
        seg = out[a:b]
        if seg.size < max(5, poly + 2):
            continue
        win = int(window)
        if win % 2 == 0:
            win += 1
        win = min(win, seg.size if seg.size % 2 == 1 else seg.size - 1)
        if win < poly + 2:
            continue
        try:
            out[a:b] = savgol_filter(seg, window_length=win, polyorder=min(poly, win - 2)).astype(np.float32)
        except Exception:
            # Fallback: no smoothing on failure
            continue
    return out


def compute_boundary_mse_rmse(
    a_corners: np.ndarray,
    b_corners: np.ndarray,
    width: int = 1024,
    height: int = 512,
    smooth: bool = True,
    min_coverage: float = 0.8,
    method: str = 'auto',
) -> tuple:
    """Compute boundary MSE/RMSE between two annotations.

    We convert unordered keypoints into paired ceiling/floor layout columns,
    resample to dense per-pixel boundaries y(x), optionally smooth piecewise,
    then compute MSE and RMSE.

    Returns:
      (mse, rmse, meta)
        - mse/rmse: pixel space, or None if not computable
        - meta: pairing stats + warning flags
    """
    # First, collect pairing stats (used for both methods and warnings)
    a_pairs, a_stats = _pair_keypoints_to_layout(a_corners, width=width, return_stats=True)
    b_pairs, b_stats = _pair_keypoints_to_layout(b_corners, width=width, return_stats=True)

    meta = {
        "pred_n_points": a_stats.get("n_points", 0),
        "pred_n_pairs": a_stats.get("n_pairs", 0),
        "pred_pair_coverage": a_stats.get("coverage", 0.0),
        "pred_odd_points": bool(a_stats.get("odd_points", False)),
        "ann_n_points": b_stats.get("n_points", 0),
        "ann_n_pairs": b_stats.get("n_pairs", 0),
        "ann_pair_coverage": b_stats.get("coverage", 0.0),
        "ann_odd_points": bool(b_stats.get("odd_points", False)),
    }
    meta["pairing_warning"] = bool(
        meta["pred_odd_points"]
        or meta["ann_odd_points"]
        or meta["pred_pair_coverage"] < float(min_coverage)
        or meta["ann_pair_coverage"] < float(min_coverage)
    )

    # Decide boundary generation method
    method = (method or 'auto').lower()
    meta['boundary_method_used'] = 'heuristic'

    a_cor_id, _ = _normalize_to_cor_id_pairs(a_corners, width=width)
    b_cor_id, _ = _normalize_to_cor_id_pairs(b_corners, width=width)

    use_connect = False
    if method == 'connect':
        use_connect = (a_cor_id is not None and b_cor_id is not None)
    elif method == 'heuristic':
        use_connect = False
    else:  # auto
        use_connect = (a_cor_id is not None and b_cor_id is not None)

    if len(a_pairs) < 2 or len(b_pairs) < 2:
        meta["pairing_failure_reason"] = "insufficient_pairs"
        return None, None, meta

    if use_connect:
        a_yc, a_yf = _boundary_from_cor_id_connect(a_cor_id, width=width, height=height)
        b_yc, b_yf = _boundary_from_cor_id_connect(b_cor_id, width=width, height=height)
        if a_yc is None or b_yc is None:
            # Fallback to heuristic if connect failed unexpectedly
            use_connect = False
        else:
            meta['boundary_method_used'] = 'connect'

    if not use_connect:
        ax = np.array([p["x"] for p in a_pairs], dtype=np.float32)
        ayc = np.array([p["y_ceiling"] for p in a_pairs], dtype=np.float32)
        ayf = np.array([p["y_floor"] for p in a_pairs], dtype=np.float32)

        bx = np.array([p["x"] for p in b_pairs], dtype=np.float32)
        byc = np.array([p["y_ceiling"] for p in b_pairs], dtype=np.float32)
        byf = np.array([p["y_floor"] for p in b_pairs], dtype=np.float32)

        a_yc = _interp_periodic(ax, ayc, width=width)
        a_yf = _interp_periodic(ax, ayf, width=width)
        b_yc = _interp_periodic(bx, byc, width=width)
        b_yf = _interp_periodic(bx, byf, width=width)
        if a_yc.size == 0 or b_yc.size == 0:
            meta["pairing_failure_reason"] = "interp_empty"
            return None, None, meta

    if smooth:
        a_yc = _smooth_piecewise(a_yc, height=height)
        a_yf = _smooth_piecewise(a_yf, height=height)
        b_yc = _smooth_piecewise(b_yc, height=height)
        b_yf = _smooth_piecewise(b_yf, height=height)

    diff2 = (a_yc - b_yc) ** 2 + (a_yf - b_yf) ** 2
    mse = float(np.mean(diff2))
    rmse = float(np.sqrt(mse))
    meta["pairing_failure_reason"] = ""
    return mse, rmse, meta

def load_active_logs(log_dir):
    """
    Load active time logs from a directory of JSONL files.
    Logic: max within a session, sum across sessions.

    Returns:
      dict[(task_id, annotator_id)] -> {
        active_time_value,
        active_time_source_file,
        active_time_session_count,
        active_time_event_count,
      }
    """
    session_maxes = defaultdict(float)
    session_files = defaultdict(set)
    session_events = defaultdict(int)

    if not log_dir or not os.path.exists(log_dir):
        return {}

    files = glob.glob(os.path.join(log_dir, "active_times_*.jsonl"))
    print(f"Found {len(files)} log files in {log_dir}")

    for fpath in files:
        with open(fpath, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    t_id = str(data.get('task_id'))
                    a_id = str(data.get('annotator_id', 'unknown'))
                    s_id = str(data.get('session_id', 'default'))
                    sec = float(data.get('active_seconds', 0))

                    key = (t_id, a_id, s_id)
                    if sec > session_maxes[key]:
                        session_maxes[key] = sec
                    session_files[key].add(os.path.basename(fpath))
                    session_events[key] += 1
                except Exception:
                    pass

    final_logs = defaultdict(lambda: {
        'active_time_value': 0.0,
        'active_time_source_file': set(),
        'active_time_session_count': 0,
        'active_time_event_count': 0,
    })
    for (t_id, a_id, _s_id), max_sec in session_maxes.items():
        bucket = final_logs[(t_id, a_id)]
        bucket['active_time_value'] += max_sec
        bucket['active_time_source_file'].update(session_files[(t_id, a_id, _s_id)])
        bucket['active_time_session_count'] += 1
        bucket['active_time_event_count'] += session_events[(t_id, a_id, _s_id)]

    serialized = {}
    for key, value in final_logs.items():
        serialized[key] = {
            'active_time_value': float(value['active_time_value']),
            'active_time_source_file': ";".join(sorted(value['active_time_source_file'])),
            'active_time_session_count': int(value['active_time_session_count']),
            'active_time_event_count': int(value['active_time_event_count']),
        }
    return serialized

def extract_data(results, width=1024, height=512):
    """Extract geometry and choice fields from Label Studio results.

    Returns:
      corners_px: np.ndarray (N,2)
      poly_points_px: list[[x,y], ...]
    choice_map: dict[str, list[str]]  (from_name -> selected choice aliases when available)
      quality_all: str  (all selected choice texts joined by ';')

    Notes:
      - Old configs used a single Choices name='quality'.
            - New rigorous configs split into multiple fields: scope/difficulty/model_issue.
            - Label Studio exports the displayed Choice value text (not alias).
                We map it to the XML-configured alias when possible.
    """
    corners = []
    poly_points = []
    choice_map = defaultdict(list)

    for r in results:
        r_type = r.get('type')
        val = r.get('value', {})

        # 1. Extract Corners
        if r_type in ['keypointlabels', 'keypointregion']:
            x = val.get('x')
            y = val.get('y')
            if x is not None and y is not None:
                corners.append([x * width / 100.0, y * height / 100.0])

        # 2. Extract Polygon
        elif r_type in ['polygonlabels', 'polygonregion']:
            points = val.get('points', [])
            for p in points:
                poly_points.append([p[0] * width / 100.0, p[1] * height / 100.0])

        # 3. Extract choice fields
        elif r_type == 'choices':
            choices = val.get('choices', []) or []
            from_name = r.get('from_name') or r.get('name') or 'quality'
            for c in choices:
                if isinstance(c, str) and c:
                    choice_map[str(from_name)].append(_map_choice_value_to_alias(str(from_name), c))

    # Flatten all choices (dedup) for backward-compatible parsing
    all_choices = []
    for items in choice_map.values():
        all_choices.extend(items)
    # Keep deterministic ordering for logs/CSVs
    quality_all = ";".join(sorted(set(all_choices))) if all_choices else "unknown"

    return np.array(corners), poly_points, dict(choice_map), quality_all


def compute_iou(pred_poly_points, ann_poly_points):
    """
    Compute Intersection over Union (IoU) between two polygons.
    """
    if not pred_poly_points or not ann_poly_points:
        return 0.0
        
    try:
        p1 = Polygon(pred_poly_points)
        p2 = Polygon(ann_poly_points)
        
        if not p1.is_valid: p1 = make_valid(p1)
        if not p2.is_valid: p2 = make_valid(p2)
        
        if p1.area == 0 or p2.area == 0:
            return 0.0
            
        intersection = p1.intersection(p2).area
        union = p1.union(p2).area
        
        if union == 0:
            return 0.0
            
        return intersection / union
    except Exception as e:
        # print(f"IoU Error: {e}")
        return 0.0

def compute_rmse(pred_corners, ann_corners):
    """
    Compute RMSE between matched corners.
    """
    n_pred = len(pred_corners)
    n_ann = len(ann_corners)
    
    if n_pred == 0 or n_ann == 0:
        return None
        
    dists = np.linalg.norm(pred_corners[:, None, :] - ann_corners[None, :, :], axis=2)
    row_ind, col_ind = linear_sum_assignment(dists)
    
    matched_dists = dists[row_ind, col_ind]
    rmse = np.sqrt(np.mean(matched_dists ** 2))
    
    return rmse


def compute_pointwise_rmse_cyclic(
    pred_corners: np.ndarray,
    ann_corners: np.ndarray,
    width: int = 1024,
    min_coverage: float = 0.9,
    threshold_ratio: float = 0.05,
):
    """Pointwise RMSE with cyclic shift alignment (panorama seam).

    This metric is only meaningful when we can trust a 1-1 correspondence between corners.
    We therefore:
      1) normalize unordered points into HoHoNet-style cor_id (ceil/floor paired, sorted by x)
      2) require sufficient pairing coverage and no odd-point issue
      3) require equal number of corner pairs
      4) align by cyclic shift over pairs and take the minimum RMSE

    Returns: (rmse_px | None, used:bool, meta:dict)
      meta contains best_shift and gate_reason.
    """
    meta = {"best_shift": None, "gate_reason": ""}

    pred_cor_id, pred_stats = _normalize_to_cor_id_pairs(pred_corners, width=width, threshold_ratio=threshold_ratio)
    ann_cor_id, ann_stats = _normalize_to_cor_id_pairs(ann_corners, width=width, threshold_ratio=threshold_ratio)

    if pred_cor_id is None or ann_cor_id is None:
        meta["gate_reason"] = "normalize_failed"
        return None, False, meta

    if bool(pred_stats.get("odd_points", False)) or bool(ann_stats.get("odd_points", False)):
        meta["gate_reason"] = "odd_points"
        return None, False, meta

    if float(pred_stats.get("coverage", 0.0)) < float(min_coverage) or float(ann_stats.get("coverage", 0.0)) < float(min_coverage):
        meta["gate_reason"] = "low_coverage"
        return None, False, meta

    if pred_cor_id.shape != ann_cor_id.shape:
        meta["gate_reason"] = "n_pairs_mismatch"
        return None, False, meta

    n_pairs = int(pred_cor_id.shape[0] // 2)
    if n_pairs < 2:
        meta["gate_reason"] = "too_few_pairs"
        return None, False, meta

    a = np.asarray(pred_cor_id, dtype=np.float32)
    b = np.asarray(ann_cor_id, dtype=np.float32)
    best_rmse = None
    best_shift = 0

    for shift in range(n_pairs):
        b_shift = np.roll(b, shift * 2, axis=0)
        diff = a - b_shift
        mse = float(np.mean(np.sum(diff * diff, axis=1)))
        rmse = float(np.sqrt(mse))
        if best_rmse is None or rmse < best_rmse:
            best_rmse = rmse
            best_shift = shift

    meta["best_shift"] = int(best_shift)
    meta["gate_reason"] = ""
    return float(best_rmse) if best_rmse is not None else None, True, meta

def compute_consistency(annotations, width=1024, height=512):
    """
    Compute pairwise IoU between multiple annotators for the same task.
    Returns: average_consistency_iou, details_list
    """
    if len(annotations) < 2:
        return 0.0, []
    
    # Extract polygons for all annotators
    # NOTE: For reliability/IAA we exclude OOS/unknown-scope annotations by default
    # because their boundaries are often definition-ambiguous, inflating disagreement.
    user_polys = []
    for ann in annotations:
        u_id = 'unknown'
        if 'completed_by' in ann:
            if isinstance(ann['completed_by'], dict):
                u_id = str(ann['completed_by'].get('id', 'unknown'))
            else:
                u_id = str(ann['completed_by'])
        
        corners, poly, choice_map, quality_all = extract_data(ann.get('result', []), width, height)
        qflags = parse_quality_flags_v2(choice_map, quality_all=quality_all, mode='v2')
        # Keep only explicit In-scope.
        if qflags.get('scope_missing') or (qflags.get('is_oos') is not False):
            continue

        # NOTE: Current annotation plan primarily uses Corner keypoints (no wall polygon).
        # For consistency/consensus we therefore default to corner-derived polygons.
        # If you later run a legacy export that contains manual wall polygons, those
        # are still preserved in separate columns (iou_manual) and can be opted into
        # via --metric manual.
        final_poly = []
        if corners is not None and len(corners) > 2:
            try:
                final_poly = list(Polygon(corners).convex_hull.exterior.coords)
            except Exception:
                final_poly = []
        elif poly:
            # Fallback only if corners are missing
            final_poly = poly

        if final_poly:
            user_polys.append({'uid': u_id, 'poly': final_poly})
    
    if len(user_polys) < 2:
        return 0.0, []
        
    # Calculate pairwise IoU
    ious = []
    details = []
    for p1, p2 in itertools.combinations(user_polys, 2):
        iou = compute_iou(p1['poly'], p2['poly'])
        ious.append(iou)
        details.append(f"{p1['uid']} vs {p2['uid']}: {iou:.4f}")
        
    return np.mean(ious), details


def _poly_is_valid(poly_points: list) -> bool:
    if not poly_points or len(poly_points) < 3:
        return False
    try:
        p = Polygon(poly_points)
        if not p.is_valid:
            p = make_valid(p)
        return (p.area is not None) and (p.area > 0)
    except Exception:
        return False

def main():
    parser = argparse.ArgumentParser(description="Analyze annotation quality and efficiency")
    parser.add_argument('export_json', help="Path to Label Studio export JSON file")
    parser.add_argument('--active-logs', help="Path to active_logs directory", default="active_logs")
    parser.add_argument('--output_dir', help="Directory to save output files", default="analysis_results")
    parser.add_argument('--metric', choices=['auto', 'manual', 'corner'], default='corner', 
                        help="Primary metric for 'iou' column (recommended: corner; auto: prefer manual if exists)")
    parser.add_argument('--no_smooth', action='store_true', help='Disable boundary curve smoothing for boundary RMSE')
    parser.add_argument('--pair_warn_min_coverage', type=float, default=0.8, help='Min pairing coverage before warning (0-1)')
    parser.add_argument('--boundary_method', choices=['auto', 'heuristic', 'connect'], default='auto',
                        help='Boundary curve generation method: connect uses HoHoNet-style pano_connect_points when possible')
    parser.add_argument('--no_pointwise', action='store_true', help='Disable pointwise RMSE (cyclic shift aligned)')
    parser.add_argument('--pointwise_min_coverage', type=float, default=0.9, help='Min pairing coverage to enable pointwise RMSE (0-1)')
    parser.add_argument('--ru_min_tasks', type=int, default=5, help='Min multi-annotator tasks required to report r_u for a user')
    parser.add_argument('--ru_bootstrap_iters', type=int, default=1000, help='Bootstrap iterations for r_u confidence interval')
    parser.add_argument('--ru_ci', type=float, default=0.95, help='CI level for r_u bootstrap (e.g., 0.95)')
    parser.add_argument('--ru_seed', type=int, default=0, help='Random seed for r_u bootstrap')
    parser.add_argument('--dataset_group', type=str, default="Unknown", 
                        help="Dataset role: Manual_Test, SemiAuto_Test, Calibration_manual, etc.")
    parser.add_argument('--project_version', type=str, default="v1.0", 
                        help="Version tag for the analysis run.")
    parser.add_argument('--analysis_role', type=str, default="performance",
                        help="Analysis role: performance or reliability (used for manifest categorization)")
    parser.add_argument('--output', type=str, help="Path to save the output CSV (overrides default naming)")
    parser.add_argument('--append', action='store_true', help="Append to the output file if it exists")
    parser.add_argument(
        '--quality_mode',
        choices=['v2'],
        default='v2',
        help='How to parse Label Studio choice fields (v2 only).',
    )
    args = parser.parse_args()

    # Create output directory if not exists
    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)
        print(f"Created directory: {args.output_dir}")

    date_str = datetime.now().strftime("%Y%m%d")
    output_csv = args.output if args.output else os.path.join(args.output_dir, f"quality_report_{date_str}.csv")

    # 1. Load Active Logs
    print("Loading active logs...")
    active_times = load_active_logs(args.active_logs)
    
    # 2. Process Tasks
    rows = []
    consistency_stats = [] # Store consistency data
    # For reliability / consensus
    task_user_poly = defaultdict(dict)  # task_id -> user_id -> poly_points(list)
    # Task-level scope vote stats (handle mixed in-scope vs OOS)
    task_scope_counts = defaultdict(lambda: {"n_total": 0, "n_in_scope": 0, "n_oos": 0, "n_unknown": 0})
    
    print(f"Processing {args.export_json}...")
    
    try:
        with open(args.export_json, 'r', encoding='utf-8') as f:
            tasks = json.load(f)
            
        # Handle list or dict (Label Studio export format varies)
        if isinstance(tasks, dict):
            tasks = [tasks] # Single task
            
        for task in tasks:
            t_id = str(task.get('id'))
            # NEW: Extract title and image metadata for cross-project pairing
            t_data = task.get('data', {})
            t_title = str(t_data.get('title', ''))
            t_image = str(t_data.get('image', ''))
            
            # Get Prediction (Model)
            # Label Studio JSON can have 'predictions' (list of objects or IDs) 
            # or 'prediction' (single object)
            preds_list = task.get('predictions', [])
            pred_obj = None
            
            # 1. Try 'prediction' key first (often contains the full object)
            if task.get('prediction') and isinstance(task.get('prediction'), dict):
                pred_obj = task.get('prediction')
            # 2. If not, check the first element of 'predictions' list
            elif preds_list and isinstance(preds_list[0], dict):
                pred_obj = preds_list[0]
            # 3. If 'predictions' is a list of IDs, we might not have the full object 
            # unless it's also in the annotation (Label Studio sometimes does this)
            
            # Get Annotations (User)
            anns = task.get('annotations', [])
            if not anns:
                continue

            export_source_path = os.path.abspath(args.export_json)
            export_source_file = os.path.basename(export_source_path)
            export_project_id = str(task.get('project', ''))
            export_dataset_group = str(t_data.get('dataset_group', '')).strip()
            export_init_type = str(t_data.get('init_type', '')).strip()
            export_is_anchor = t_data.get('is_anchor', '')
            export_has_expert_ref = t_data.get('has_expert_ref', '')

            # Infer condition (manual vs semi) from presence of predictions
            task_has_prediction = False
            if task.get('prediction') and isinstance(task.get('prediction'), dict):
                task_has_prediction = True
            elif preds_list:
                task_has_prediction = True
            if not task_has_prediction:
                for ann in anns:
                    if ann.get('prediction') and isinstance(ann.get('prediction'), dict):
                        task_has_prediction = True
                        break
                    for r in ann.get('result', []) or []:
                        if str(r.get('origin', '')).lower() == 'prediction':
                            task_has_prediction = True
                            break
                    if task_has_prediction:
                        break
            condition = 'semi' if task_has_prediction else 'manual'
            runtime_condition_source = 'derived_from_prediction_presence'

            # --- Consistency Check (Inter-Annotator Agreement) ---
            if len(anns) > 1:
                avg_consistency, cons_details = compute_consistency(anns)
                consistency_stats.append({
                    'task_id': t_id,
                    'n_annotators': len(anns),
                    'iaa_t': avg_consistency,
                    'details': cons_details
                })

            for ann in anns:
                # If we still don't have a prediction object, check if it's inside the annotation
                current_pred_obj = pred_obj
                if not current_pred_obj and ann.get('prediction') and isinstance(ann.get('prediction'), dict):
                    current_pred_obj = ann.get('prediction')
                
                # Extract prediction data
                if current_pred_obj:
                    pred_corners, pred_poly, _pred_choice_map, _pred_quality = extract_data(current_pred_obj.get('result', []))
                else:
                    pred_corners, pred_poly, _pred_choice_map, _pred_quality = (np.array([]), [], {}, "")
                
                # Prepare prediction polygons
                # - manual: directly from prediction polygon region if present
                # - corner: convex-hull polygon derived from predicted corners
                pred_manual_poly = pred_poly or []
                pred_corner_poly = []
                if pred_corners is not None and len(pred_corners) > 2:
                    try:
                        pred_corner_poly = list(Polygon(pred_corners).convex_hull.exterior.coords)
                    except Exception:
                        pred_corner_poly = []

                # Try to get user info
                u_id = 'unknown'
                if 'completed_by' in ann:
                    if isinstance(ann['completed_by'], dict):
                        u_id = str(ann['completed_by'].get('id', 'unknown'))
                    else:
                        u_id = str(ann['completed_by'])
                
                # Get active time from logs, fallback to lead_time
                active_log_entry = active_times.get((t_id, u_id))
                active_time = 0
                active_time_source = 'missing'
                active_time_source_file = ''
                active_time_session_count = 0
                active_time_event_count = 0
                active_time_match_status = 'missing'
                lead_time_seconds = float(ann.get('lead_time', 0) or 0)
                if active_log_entry:
                    active_time = float(active_log_entry.get('active_time_value', 0.0))
                    active_time_source = 'log'
                    active_time_source_file = str(active_log_entry.get('active_time_source_file', ''))
                    active_time_session_count = int(active_log_entry.get('active_time_session_count', 0))
                    active_time_event_count = int(active_log_entry.get('active_time_event_count', 0))
                    active_time_match_status = 'task+annotator'
                elif lead_time_seconds > 0:
                    active_time = lead_time_seconds
                    active_time_source = 'lead_time_fallback'
                    active_time_match_status = 'fallback_no_direct_log'
                
                ann_corners, ann_poly, ann_choice_map, quality = extract_data(ann.get('result', []))
                # Prefer deterministic v2 parsing from structured fields (scope/difficulty/model_issue).
                qflags = parse_quality_flags_v2(ann_choice_map, quality_all=quality, mode=str(args.quality_mode))

                # Track task-level scope votes.
                # NOTE: missing/unknown scope should not be silently counted as in-scope.
                task_scope_counts[t_id]["n_total"] += 1
                if bool(qflags.get('scope_missing')) or (qflags.get('is_oos') is None):
                    task_scope_counts[t_id]["n_unknown"] += 1
                elif qflags.get('is_oos') is True:
                    task_scope_counts[t_id]["n_oos"] += 1
                else:
                    task_scope_counts[t_id]["n_in_scope"] += 1

                # Prepare final_ann_poly (candidate geometry to be used for consensus/reliability)
                final_ann_poly = []
                if len(ann_corners) > 2:
                    try:
                        final_ann_poly = list(Polygon(ann_corners).convex_hull.exterior.coords)
                    except Exception:
                        final_ann_poly = []
                elif ann_poly:
                    final_ann_poly = ann_poly
                
                # --- Dual IoU Calculation ---
                # IMPORTANT: if IoU is not computable (missing pred/ann geometry), keep it as None.
                # Do not use 0.0 as a placeholder; that would be interpreted as "very low quality".
                
                # 1) Manual Polygon IoU (only meaningful if manual wall polygons are present)
                iou_manual = None
                if ann_poly and pred_manual_poly:
                    iou_manual = compute_iou(pred_manual_poly, ann_poly)
                
                # 2) Corner Polygon IoU (corner-derived layout polygon)
                iou_corner = None
                ann_corner_poly = []
                if len(ann_corners) > 2:
                    # Use Convex Hull for corners to ensure valid polygon
                    # [V2.0 Fix]: Initialize to 0.0 so that invalid predictions get penalized 
                    # instead of being excluded (Selection Bias).
                    iou_corner = 0.0 
                    try:
                        ann_corner_poly = list(Polygon(ann_corners).convex_hull.exterior.coords)
                        if pred_corner_poly:
                            iou_corner = compute_iou(pred_corner_poly, ann_corner_poly)
                    except:
                        # Fallback to 0.0 if calculation crashes
                        iou_corner = 0.0

                # Primary IoU based on selected metric mode
                if args.metric == 'manual':
                    iou_primary = iou_manual
                elif args.metric == 'corner':
                    iou_primary = iou_corner
                else:  # auto
                    iou_primary = iou_manual if (iou_manual is not None) else iou_corner
                
                rmse = compute_rmse(pred_corners, ann_corners)

                layout_iou2d = None
                layout_iou3d = None
                layout_depth_rmse = None
                layout_delta1 = None
                layout_used = False
                layout_gate_reason = "disabled"
                if bool(qflags.get('scope_missing')) or (qflags.get('is_oos') is None):
                    # Unknown scope: treat as not eligible for standard layout metrics.
                    layout_used = False
                    layout_gate_reason = "scope_missing"
                elif qflags.get('is_oos') is True:
                    # Out-of-scope cases violate the Manhattan/single-ceiling assumption;
                    # standard layout metrics are not meaningful as a quality signal.
                    layout_used = False
                    layout_gate_reason = "out_of_scope"
                else:
                    try:
                        layout_iou2d, layout_iou3d, layout_depth_rmse, layout_delta1, layout_used, layout_meta = compute_layout_standard_metrics(
                            pred_corners,
                            ann_corners,
                            width=1024,
                            height=512,
                            min_coverage=float(args.pointwise_min_coverage),
                        )
                        layout_gate_reason = str(layout_meta.get('gate_reason', ''))
                    except Exception:
                        layout_used = False
                        layout_gate_reason = "exception"

                pointwise_rmse = None
                pointwise_used = False
                pointwise_meta = {"best_shift": None, "gate_reason": "disabled"}
                if not args.no_pointwise:
                    pointwise_rmse, pointwise_used, pointwise_meta = compute_pointwise_rmse_cyclic(
                        pred_corners,
                        ann_corners,
                        width=1024,
                        min_coverage=float(args.pointwise_min_coverage),
                    )

                boundary_mse, boundary_rmse, boundary_meta = compute_boundary_mse_rmse(
                    pred_corners,
                    ann_corners,
                    width=1024,
                    height=512,
                    smooth=(not args.no_smooth),
                    min_coverage=float(args.pair_warn_min_coverage),
                    method=str(args.boundary_method),
                )

                # Limited warnings to keep console readable
                if boundary_meta.get('pairing_warning'):
                    # Print only for a few early cases
                    if len([r for r in rows if r.get('pairing_warning')]) < 10:
                        print(
                            f"[WARN][Pairing] task={t_id} user={u_id} "
                            f"pred_pts={boundary_meta.get('pred_n_points')} pred_pairs={boundary_meta.get('pred_n_pairs')} cov={boundary_meta.get('pred_pair_coverage'):.2f} "
                            f"ann_pts={boundary_meta.get('ann_n_points')} ann_pairs={boundary_meta.get('ann_n_pairs')} cov={boundary_meta.get('ann_pair_coverage'):.2f} "
                            f"reason={boundary_meta.get('pairing_failure_reason') or 'ok'}"
                        )
                
                # Store user geometry for consensus/reliability **after** computing layout gate.
                # Store user geometry for consensus/reliability.
                # Paper-facing consensus/reliability gate is intentionally separated from `layout_used`:
                # - `layout_used` is an engineering gate for HoHoNet-style layout metrics.
                # - reliability gate focuses on whether the annotation is in-scope and yields a valid polygon.
                # This avoids selection bias from prediction/depth/pairing failures while keeping the
                # consensus set geometrically valid.
                reliability_used = False
                reliability_gate_reason = ""
                try:
                    if bool(qflags.get('scope_missing')):
                        reliability_gate_reason = "scope_missing"
                    elif qflags.get('is_oos') is not False:
                        reliability_gate_reason = "oos_or_unknown"
                    elif not final_ann_poly:
                        reliability_gate_reason = "empty_poly"
                    elif not _poly_is_valid(final_ann_poly):
                        reliability_gate_reason = "invalid_poly"
                    else:
                        reliability_used = True
                        task_user_poly[t_id][u_id] = final_ann_poly
                except Exception:
                    pass
                scope_norm = _normalize_choice_values('scope', ann_choice_map.get('scope', [])) if isinstance(ann_choice_map, dict) else []
                diff_norm = _normalize_choice_values('difficulty', ann_choice_map.get('difficulty', [])) if isinstance(ann_choice_map, dict) else []
                model_norm = _normalize_model_issue_values(_normalize_choice_values('model_issue', ann_choice_map.get('model_issue', []))) if isinstance(ann_choice_map, dict) else []

                diff_norm_l = [str(x).strip().lower() for x in diff_norm if str(x).strip()]
                model_norm_l = [str(x).strip().lower() for x in model_norm if str(x).strip()]
                has_trivial = ('trivial' in set(diff_norm_l))
                has_acceptable = ('acceptable' in set(model_norm_l))

                difficulty_filled = bool(diff_norm_l)
                model_issue_filled = bool(model_norm_l)
                scope_filled = bool([str(x).strip() for x in scope_norm if str(x).strip()])

                difficulty_conflict = bool(has_trivial and len(diff_norm_l) > 1)
                model_issue_conflict = bool(has_acceptable and len(model_norm_l) > 1)

                # model_issue is only required for semi-auto conditions.
                condition_norm = str(condition or '').strip().lower()
                model_issue_required = ('semi' in condition_norm)
                model_issue_missing_required = bool(model_issue_required and (not model_issue_filled))

                rows.append({
                    'dataset_group': args.dataset_group,
                    'dataset_group_source': 'cli_argument',
                    'export_dataset_group': export_dataset_group,
                    'project_version': args.project_version,
                    'task_id': t_id,
                    'title': t_title,
                    'image_url': t_image,
                    'export_project_id': export_project_id,
                    'export_source_file': export_source_file,
                    'export_source_path': export_source_path,
                    'export_init_type': export_init_type,
                    'export_is_anchor': export_is_anchor,
                    'export_has_expert_ref': export_has_expert_ref,
                    'condition': condition,
                    'runtime_condition_source': runtime_condition_source,
                    'annotator_id': u_id,
                    'active_time': active_time,
                    'active_time_source': active_time_source,
                    'active_time_source_file': active_time_source_file,
                    'active_time_match_status': active_time_match_status,
                    'active_time_session_count': active_time_session_count,
                    'active_time_event_count': active_time_event_count,
                    'lead_time_seconds': lead_time_seconds,
                    'iou': iou_primary,          # For compatibility
                    'iou_manual': iou_manual,    # Explicit Manual IoU
                    'iou_corner': iou_corner,    # Explicit Corner IoU
                    'rmse_px': rmse,
                    # Standard layout metrics (HoHoNet/HorizonNet style)
                    'layout_2d_iou': layout_iou2d,
                    'layout_3d_iou': layout_iou3d,
                    'layout_depth_rmse': layout_depth_rmse,
                    'layout_delta1': layout_delta1,
                    'layout_used': bool(layout_used),
                    'layout_gate_reason': layout_gate_reason,
                    'reliability_used': bool(reliability_used),
                    'reliability_gate_reason': reliability_gate_reason,
                    'pointwise_rmse_px': pointwise_rmse,
                    'pointwise_rmse_used': bool(pointwise_used),
                    'pointwise_best_shift': pointwise_meta.get('best_shift', None),
                    'pointwise_gate_reason': pointwise_meta.get('gate_reason', ''),
                    'boundary_mse': boundary_mse,
                    'boundary_rmse_px': boundary_rmse,
                    'pred_n_points': boundary_meta.get('pred_n_points', 0),
                    'pred_n_pairs': boundary_meta.get('pred_n_pairs', 0),
                    'pred_pair_coverage': boundary_meta.get('pred_pair_coverage', 0.0),
                    'pred_odd_points': boundary_meta.get('pred_odd_points', False),
                    'ann_n_points': boundary_meta.get('ann_n_points', 0),
                    'ann_n_pairs': boundary_meta.get('ann_n_pairs', 0),
                    'ann_pair_coverage': boundary_meta.get('ann_pair_coverage', 0.0),
                    'ann_odd_points': boundary_meta.get('ann_odd_points', False),
                    'pairing_warning': boundary_meta.get('pairing_warning', False),
                    'pairing_failure_reason': boundary_meta.get('pairing_failure_reason', ''),
                    'boundary_method_used': boundary_meta.get('boundary_method_used', 'heuristic'),
                    # Filled later if task has multiple annotators
                    'consensus_uid': '',
                    'iou_to_consensus': None,
                    # Leave-one-out (exclude self from consensus)
                    'consensus_uid_loo': '',
                    'iou_to_consensus_loo': None,
                    # Direct agreement summary without choosing a representative
                    'iou_to_others_median': None,
                    'quality': quality,
                    'scope': ";".join(scope_norm),
                    'difficulty': ";".join(diff_norm),
                    # Store raw (possibly including 'acceptable') for auditing UI usage.
                    'model_issue': ";".join(model_norm),
                    'tool_issue': ";".join(_normalize_choice_values('tool_issue', ann_choice_map.get('tool_issue', []))) if isinstance(ann_choice_map, dict) else "",
                    # Meta-label hygiene for auditing (do NOT silently filter).
                    'scope_filled': bool(scope_filled),
                    'difficulty_filled': bool(difficulty_filled),
                    'difficulty_has_trivial': bool(has_trivial),
                    'difficulty_conflict': bool(difficulty_conflict),
                    'model_issue_required': bool(model_issue_required),
                    'model_issue_filled': bool(model_issue_filled),
                    'model_issue_has_acceptable': bool(has_acceptable),
                    'model_issue_conflict': bool(model_issue_conflict),
                    'model_issue_missing_required': bool(model_issue_missing_required),
                    # Derived, deterministic fields for multi-select model_issue.
                    'has_model_issue': bool([t for t in model_norm_l if t != 'acceptable']),
                    'model_issue_types': ";".join([t for t in model_norm_l if t != 'acceptable']),
                    'model_issue_primary': _pick_primary_model_issue([t for t in model_norm_l if t != 'acceptable']),
                    # Keep tri-state for scope-derived fields: True / False / empty (unknown).
                    'scope_missing': bool(qflags.get('scope_missing')),
                    'difficulty_missing': bool(qflags.get('difficulty_missing')),
                    'model_issue_missing': bool(qflags.get('model_issue_missing')),
                    'difficulty_conflict_v2': bool(qflags.get('difficulty_conflict')),
                    'model_issue_conflict_v2': bool(qflags.get('model_issue_conflict')),
                    'is_oos': qflags.get('is_oos'),
                    'is_occlusion': bool(qflags.get('is_occlusion')),
                    'is_fail': bool(qflags.get('is_fail')),
                    'is_residual': bool(qflags.get('is_residual')),
                    'is_normal': qflags.get('is_normal'),
                    'n_corners': len(ann_corners),
                    'has_manual_poly': bool(ann_poly)
                })
                
    except Exception as e:
        print(f"Error processing JSON: {e}")

    # 3. Write CSV
    if rows:
        # --- Task-level scope conflict handling ---
        # If a task has mixed votes (some in-scope, some OOS), it indicates the task goal/boundary
        # definition is not stable/reproducible across annotators. By default we:
        #   - keep per-row metrics in the CSV
        #   - but EXCLUDE such tasks from consensus/LOO/ru computations to avoid contaminating reliability
        mixed_scope_tasks = set()
        scope_unknown_tasks = set()
        scope_majority_by_task = {}
        for t_id, c in task_scope_counts.items():
            n_in = int(c.get('n_in_scope', 0))
            n_oos = int(c.get('n_oos', 0))
            n_unk = int(c.get('n_unknown', 0))
            if n_in > 0 and n_oos > 0:
                mixed_scope_tasks.add(t_id)
            if n_unk > 0:
                scope_unknown_tasks.add(t_id)
            # majority label (ties are labeled as 'tie')
            if n_unk > 0 and n_in == 0 and n_oos == 0:
                scope_majority_by_task[t_id] = 'unknown'
            elif n_in > n_oos:
                scope_majority_by_task[t_id] = 'in_scope'
            elif n_oos > n_in:
                scope_majority_by_task[t_id] = 'oos'
            else:
                scope_majority_by_task[t_id] = 'tie'

        # Attach task-level scope stats to each row
        for r in rows:
            t_id = str(r.get('task_id'))
            c = task_scope_counts.get(t_id, {"n_total": 0, "n_in_scope": 0, "n_oos": 0, "n_unknown": 0})
            n_total = int(c.get('n_total', 0))
            n_in = int(c.get('n_in_scope', 0))
            n_oos = int(c.get('n_oos', 0))
            n_unk = int(c.get('n_unknown', 0))
            r['task_scope_n_total'] = n_total
            r['task_scope_n_in_scope'] = n_in
            r['task_scope_n_oos'] = n_oos
            r['task_scope_n_unknown'] = n_unk
            r['task_scope_oos_rate'] = (float(n_oos) / float(n_total)) if n_total > 0 else 0.0
            r['task_scope_unknown_rate'] = (float(n_unk) / float(n_total)) if n_total > 0 else 0.0
            r['task_scope_majority'] = scope_majority_by_task.get(t_id, '')
            r['task_scope_is_mixed'] = bool(t_id in mixed_scope_tasks)
            r['task_scope_has_unknown'] = bool(t_id in scope_unknown_tasks)

        # --- Consensus + reliability (r_u) ---
        # Consensus per task: medoid annotation that maximizes median IoU to others.
        consensus_uid_by_task = {}
        iou_to_consensus_map = {}  # (task_id, user_id) -> iou

        # Leave-one-out consensus per (task, user): consensus built from other annotators only.
        consensus_uid_loo_map = {}       # (task_id, user_id) -> consensus_uid (from others)
        iou_to_consensus_loo_map = {}    # (task_id, user_id) -> iou(user, consensus_from_others)
        iou_to_others_median_map = {}    # (task_id, user_id) -> median IoU to all others

        for t_id, user_polys in task_user_poly.items():
            # Exclude tasks with mixed scope votes from consensus/reliability.
            if str(t_id) in mixed_scope_tasks:
                continue
            # Also exclude tasks with any unknown-scope votes.
            if str(t_id) in scope_unknown_tasks:
                continue
            # Paper-facing consensus requires >=3 annotators per task.
            uids = sorted([str(x) for x in user_polys.keys()])
            if len(uids) < 3:
                continue
            # pairwise IoU matrix
            iou_mat = np.zeros((len(uids), len(uids)), dtype=np.float32)
            for i in range(len(uids)):
                for j in range(i + 1, len(uids)):
                    iou = compute_iou(user_polys[uids[i]], user_polys[uids[j]])
                    iou_mat[i, j] = iou
                    iou_mat[j, i] = iou
            # medoid by median agreement
            scores = []  # (median, mean, uid, idx)
            for i, uid in enumerate(uids):
                others = np.delete(iou_mat[i], i)
                med = float(np.median(others)) if others.size > 0 else 0.0
                mean = float(np.mean(others)) if others.size > 0 else 0.0
                scores.append((med, mean, uid, i))
            # Deterministic tie-break: median desc, mean desc, uid asc (str for determinism)
            best_idx = sorted(scores, key=lambda x: (-x[0], -x[1], str(x[2])))[0][3]
            consensus_uid = uids[best_idx]
            consensus_uid_by_task[t_id] = consensus_uid
            for i, uid in enumerate(uids):
                # iou to consensus (self gets 1.0)
                if uid == consensus_uid:
                    iou_to_consensus_map[(t_id, uid)] = 1.0
                else:
                    iou_to_consensus_map[(t_id, uid)] = float(iou_mat[i, best_idx])

            # --- Leave-one-out consensus per user ---
            # For each user k, build consensus from others only, using medoid among others.
            for k, uid_k in enumerate(uids):
                other_idx = [i for i in range(len(uids)) if i != k]
                if len(other_idx) == 0:
                    continue

                # Median IoU from uid_k to others (no representative needed)
                iou_to_others = iou_mat[k, other_idx]
                iou_to_others_median_map[(t_id, uid_k)] = float(np.median(iou_to_others)) if iou_to_others.size > 0 else 0.0

                # Choose medoid among others by median agreement within the others set.
                other_scores = []  # (median, mean, uid, idx)
                for cand in other_idx:
                    cand_others = [j for j in other_idx if j != cand]
                    vals = iou_mat[cand, cand_others]
                    med = float(np.median(vals)) if vals.size > 0 else 0.0
                    mean = float(np.mean(vals)) if vals.size > 0 else 0.0
                    other_scores.append((med, mean, uids[cand], cand))
                # Deterministic tie-break: median desc, mean desc, uid asc (str for determinism)
                c_idx = sorted(other_scores, key=lambda x: (-x[0], -x[1], str(x[2])))[0][3]
                consensus_uid_loo_map[(t_id, uid_k)] = uids[c_idx]
                iou_to_consensus_loo_map[(t_id, uid_k)] = float(iou_mat[k, c_idx])

        # Fill per-row consensus fields
        for r in rows:
            t_id = r.get('task_id')
            u_id = r.get('annotator_id')
            r['analysis_role'] = args.analysis_role
            
            if t_id in consensus_uid_by_task:
                r['consensus_uid'] = consensus_uid_by_task[t_id]
                r['iou_to_consensus'] = iou_to_consensus_map.get((t_id, u_id), None)
                r['consensus_uid_loo'] = consensus_uid_loo_map.get((t_id, u_id), '')
            
            if r.get('iou_to_consensus') is None:
                r['iou_to_consensus'] = iou_to_consensus_map.get((t_id, u_id), None)
            
            if (t_id, u_id) in iou_to_consensus_loo_map:
                r['iou_to_consensus_loo'] = iou_to_consensus_loo_map.get((t_id, u_id), None)
                r['iou_to_others_median'] = iou_to_others_median_map.get((t_id, u_id), None)
            else:
                # BUG-C01 Fix: If task excluded from consensus (mixed scope/unknown/n<3),
                # update reliability_used to False to maintain consistency.
                if r.get('reliability_used') is True:
                    r['reliability_used'] = False
                    if not r.get('reliability_gate_reason'):
                        r['reliability_gate_reason'] = 'excluded_from_consensus'

        if not rows:
            print("No rows to save.")
            return

        file_exists = os.path.exists(output_csv)
        mode = 'a' if (args.append and file_exists) else 'w'
        
        # [Robust Append]: If appending, read existing header to ensure column alignment
        keys = list(rows[0].keys())
        if mode == 'a':
            try:
                with open(output_csv, 'r', encoding='utf-8') as f_read:
                    reader = csv.reader(f_read)
                    existing_header = next(reader, None)
                    if existing_header:
                        # Check compatibility
                        missing_curr = set(existing_header) - set(keys)
                        missing_prev = set(keys) - set(existing_header)
                        
                        if missing_prev:
                            print(f"⚠️ [Warning] New columns found in this run but missing in CSV: {missing_prev}")
                            print("   (These will be dropped to maintain schema consistency)")
                        
                        # Use existing header order
                        final_keys = existing_header
                    else:
                        print("⚠️ [Warning] CSV exists but empty/no-header. Switching to 'w' mode.")
                        mode = 'w'
                        final_keys = keys
            except Exception as e:
                print(f"⚠️ [Error] Failed to read existing CSV header: {e}. Aborting append.")
                return
        else:
            final_keys = keys
        
        with open(output_csv, mode, newline='', encoding='utf-8') as f:
            # extrasaction='ignore' ensures we don't crash if new script version has extra cols
            writer = csv.DictWriter(f, fieldnames=final_keys, extrasaction='ignore')
            if mode == 'w':
                writer.writeheader()
            writer.writerows(rows)
            
        print(f"Analysis saved to {output_csv} (Mode: {mode})")
        
        # Print Summary
        print(f"\n--- Summary (Mode: {args.metric}) ---")
        
        ious = [v for v in (_safe_float(r.get('iou')) for r in rows) if v is not None]
        ious_manual = [v for v in (_safe_float(r.get('iou_manual')) for r in rows) if v is not None]
        ious_corner = [v for v in (_safe_float(r.get('iou_corner')) for r in rows) if v is not None]
        
        if ious: print(f"Average Primary IoU:  {np.mean(ious):.4f}")
        if ious_manual: print(f"Average Manual IoU:   {np.mean(ious_manual):.4f} (Semantic)")
        if ious_corner: print(f"Average Corner IoU:   {np.mean(ious_corner):.4f} (Layout)")

        # Standard layout metrics summary
        layout_rows = [r for r in rows if r.get('layout_used')]
        if layout_rows:
            l2d = [float(r['layout_2d_iou']) for r in layout_rows if r.get('layout_2d_iou') is not None]
            l3d = [float(r['layout_3d_iou']) for r in layout_rows if r.get('layout_3d_iou') is not None]
            lrmse = [float(r['layout_depth_rmse']) for r in layout_rows if r.get('layout_depth_rmse') is not None]
            ld1 = [float(r['layout_delta1']) for r in layout_rows if r.get('layout_delta1') is not None]
            print(f"\n--- Standard Layout Metrics (HoHoNet-style, gated) ---")
            print(f"Layout usable rows: {len(layout_rows)}/{len(rows)}")
            if l2d: print(f"Layout 2D IoU:       {np.mean(l2d):.4f}")
            if l3d: print(f"Layout 3D IoU:       {np.mean(l3d):.4f}")
            if lrmse: print(f"Layout depth RMSE:   {np.mean(lrmse):.4f}")
            if ld1: print(f"Layout delta_1:      {np.mean(ld1):.4f}")

        # Quality tag stratification (minimal, reviewer-friendly)
        n_total = len(rows)
        n_scope_missing = len([r for r in rows if r.get('scope_missing')])
        n_diff_missing = len([r for r in rows if r.get('difficulty_missing')])
        n_diff_conflict = len([r for r in rows if r.get('difficulty_conflict')])
        n_model_missing_required = len([r for r in rows if r.get('model_issue_missing_required')])
        n_model_conflict = len([r for r in rows if r.get('model_issue_conflict')])
        n_oos = len([r for r in rows if r.get('is_oos') is True])
        n_normal = len([r for r in rows if r.get('is_normal') is True])
        n_fail = len([r for r in rows if r.get('is_fail')])
        n_occl = len([r for r in rows if r.get('is_occlusion')])
        n_resid = len([r for r in rows if r.get('is_residual')])
        print(f"\n--- Difficulty/Issue Tags (counts) ---")
        print(f"Total rows: {n_total}")
        print(
            f"ScopeMissing: {n_scope_missing} | DiffMissing: {n_diff_missing} | DiffConflict(trivial+others): {n_diff_conflict} | "
            f"ModelMissing(required, semi): {n_model_missing_required} | ModelConflict(acceptable+others): {n_model_conflict} | "
            f"Normal: {n_normal} | Out-of-scope: {n_oos} | PredFail: {n_fail} | Occlusion: {n_occl} | Residual: {n_resid}"
        )

        # Task-level scope disagreement (mixed in-scope vs OOS)
        # Useful to diagnose ambiguous task definitions or insufficient instruction.
        multi_annotator_task_ids = {str(c.get('task_id')) for c in consistency_stats} if consistency_stats else set()
        mixed_multi = [t for t in mixed_scope_tasks if t in multi_annotator_task_ids] if multi_annotator_task_ids else []
        if mixed_scope_tasks:
            print(f"\n--- Scope Disagreement (task-level) ---")
            print(f"Tasks with mixed scope votes: {len(mixed_scope_tasks)}")
            if multi_annotator_task_ids:
                print(f"Mixed among multi-annotator tasks: {len(mixed_multi)}/{len(multi_annotator_task_ids)}")
            # Show a few examples for quick triage
            show = list(sorted(mixed_scope_tasks))[:10]
            if show:
                print("Example mixed-scope task_ids:", ", ".join(show))

        # Data hygiene: in OOS, model_issue is allowed to be empty.
        # But if many OOS rows still mark model_issue, it's likely the UI rule isn't followed.
        oos_rows = [r for r in rows if r.get('is_oos') is True]
        if oos_rows:
            oos_with_model_issue = [r for r in oos_rows if str(r.get('model_issue') or '').strip()]
            rate = float(len(oos_with_model_issue)) / float(len(oos_rows))
            print(f"OOS rows: {len(oos_rows)} | OOS rows with model_issue filled: {len(oos_with_model_issue)} ({rate*100:.1f}%)")
            if rate > 0.3:
                print("[WARN] Many OOS rows still set model_issue. Recommended: scope=OOS 时 model_issue 留空（除非明确存在额外初始化错误）。")

        # If you want to 'exclude but report': show separate primary IoU means.
        non_oos_rows = [r for r in rows if (r.get('is_oos') is False) and (not r.get('scope_missing'))]
        if non_oos_rows and oos_rows:
            non_oos_iou = [v for v in (_safe_float(r.get('iou')) for r in non_oos_rows) if v is not None]
            oos_iou = [v for v in (_safe_float(r.get('iou')) for r in oos_rows) if v is not None]
            print(f"Primary IoU mean (non-OOS): {np.mean(non_oos_iou):.4f}")
            print(f"Primary IoU mean (OOS):     {np.mean(oos_iou):.4f}")

        # Make choice options actionable: print per-tag summaries.
        # Metrics chosen to match the study goals: efficiency + change magnitude + geometry robustness.
        tag_metrics = [
            'active_time',
            'iou',
            'boundary_rmse_px',
        ]
        _summarize_by_tag(rows, tag_field='scope', multi=False, metrics=tag_metrics, title='Scope Breakdown (UI choices used)')
        _summarize_by_tag(rows, tag_field='difficulty', multi=True, metrics=tag_metrics, title='Difficulty Breakdown (multi-select)')
        # Prefer issue-only tags (exclude 'acceptable') for readability.
        tag_field_issue = 'model_issue_types' if any(('model_issue_types' in r) for r in rows) else 'model_issue'
        _summarize_by_tag(rows, tag_field=tag_field_issue, multi=True, metrics=tag_metrics, title='Model Issue Breakdown (semi only)')
        
        # Annotator Stats
        by_user = defaultdict(list)
        for r in rows:
            by_user[r['annotator_id']].append(r)
            
        print("\n--- Per Annotator Stats ---")
        print(f"{'User':<10} | {'Tasks':<5} | {'Avg Time(s)':<12} | {'Avg IoU':<8} | {'Avg RMSE':<8}")
        for uid, u_rows in by_user.items():
            n_tasks = len(u_rows)
            avg_time = np.mean([float(x['active_time']) for x in u_rows])
            u_ious = [v for v in (_safe_float(x.get('iou')) for x in u_rows) if v is not None]
            avg_u_iou = float(np.mean(u_ious)) if u_ious else 0.0

            # Filter valid RMSEs
            u_rmses = [float(x['rmse_px']) for x in u_rows if x['rmse_px'] is not None]
            avg_u_rmse = np.mean(u_rmses) if u_rmses else 0

            print(f"{uid:<10} | {n_tasks:<5} | {avg_time:<12.2f} | {avg_u_iou:<8.4f} | {avg_u_rmse:<8.2f}")

        # --- Consistency Report ---
        if consistency_stats:
            print("\n--- Inter-Annotator Consistency (Expert Validation) ---")
            print(f"Found {len(consistency_stats)} tasks with multiple annotators.")
            print(f"{'Task ID':<10} | {'Annotators':<10} | {'IAA_t (median pairwise IoU)':<24}")
            for c in consistency_stats:
                v = c.get('iaa_t', None)
                if v is None:
                    v = c.get('avg_iou', None)
                v = float(v) if v is not None else float('nan')
                print(f"{c['task_id']:<10} | {c['n_annotators']:<10} | {v:.4f}")

        # --- Reliability (r_u) ---
        # r_u (leave-one-out) = median over tasks of IoU(annotator, consensus_from_others(task))
        ru_values = defaultdict(list)
        ru_values_3plus = defaultdict(list)  # n>=3 only (true consensus)
        ru_values_2 = defaultdict(list)      # n=2 only (pairwise)
        
        for r in rows:
            iou_c = r.get('iou_to_consensus_loo')
            if iou_c is None:
                continue
            try:
                n_annotators = int(r.get('task_scope_n_total', 0))
                ru_values[r['annotator_id']].append(float(iou_c))
                if n_annotators >= 3:
                    ru_values_3plus[r['annotator_id']].append(float(iou_c))
                elif n_annotators == 2:
                    ru_values_2[r['annotator_id']].append(float(iou_c))
            except Exception:
                continue

        if ru_values:
            min_tasks = int(max(1, args.ru_min_tasks))
            ci_level = float(args.ru_ci)
            iters = int(max(1, args.ru_bootstrap_iters))
            seed = int(args.ru_seed)

            # Count tasks by n_annotators for transparency
            n_tasks_total = len(set(r['task_id'] for r in rows if r.get('iou_to_consensus_loo') is not None))
            n_tasks_3plus = len(set(r['task_id'] for r in rows 
                                   if r.get('iou_to_consensus_loo') is not None 
                                   and int(r.get('task_scope_n_total', 0)) >= 3))
            n_tasks_2 = len(set(r['task_id'] for r in rows 
                               if r.get('iou_to_consensus_loo') is not None 
                               and int(r.get('task_scope_n_total', 0)) == 2))
            
            print("\n--- Annotator Reliability (r_u) from Multi-Annotator Tasks (Leave-One-Out) ---")
            print(f"Total tasks with LOO: {n_tasks_total} (n≥3: {n_tasks_3plus}, n=2: {n_tasks_2})")
            if n_tasks_2 > 0:
                pct_2 = 100.0 * n_tasks_2 / n_tasks_total if n_tasks_total > 0 else 0.0
                print(f"⚠️  Warning: {n_tasks_2} tasks ({pct_2:.1f}%) have n=2 annotators.")
                print(f"   LOO reliability for n=2 degenerates to pairwise IoU (not true consensus).")
                print(f"   For paper-level rigor, consider reporting n≥3 subset separately.\n")
            
            print(
                f"{'User':<10} | {'n_tasks':<6} | {'r_u(median)':<11} | {'CI':<25} | {'mean IoU':<10}"
            )

            items = []
            for uid, vals in ru_values.items():
                if len(vals) < min_tasks:
                    continue
                if len(vals) < 5:
                    print(f"[WARN][r_u] user={uid} has only n_tasks={len(vals)}; CI may be unstable.")
                med, lo, hi = _bootstrap_ci(vals, stat_fn=lambda a: np.median(a), n_iters=iters, ci=ci_level, seed=seed)
                mean = float(np.mean(vals))
                items.append((uid, len(vals), float(med), float(lo), float(hi), mean))

            items.sort(key=lambda x: (x[2], x[1]), reverse=True)
            if not items:
                print(f"(No users meet ru_min_tasks={min_tasks}. Increase multi-annotator tasks or lower threshold.)")
            else:
                for uid, n, med, lo, hi, mean in items:
                    print(f"{uid:<10} | {n:<6d} | {med:<11.4f} | [{lo:.4f}, {hi:.4f}] (p{int(ci_level*100)}) | {mean:<10.4f}")

                # --- Stratified report: n≥3 vs n=2 ---
                if ru_values_3plus and ru_values_2:
                    print("\n--- Stratified LOO Reliability: n≥3 (true consensus) vs n=2 (pairwise) ---")
                    for uid in sorted(set(ru_values_3plus.keys()) | set(ru_values_2.keys())):
                        vals_3plus = ru_values_3plus.get(uid, [])
                        vals_2 = ru_values_2.get(uid, [])
                        r_3plus = f"{np.median(vals_3plus):.3f}" if vals_3plus else "N/A"
                        r_2 = f"{np.median(vals_2):.3f}" if vals_2 else "N/A"
                        print(f"{uid:<10} | n≥3: {len(vals_3plus):<3d} r_u={r_3plus:<6s} | n=2: {len(vals_2):<3d} r_u={r_2:<6s}")

                # Also save a per-user reliability report
                reliability_csv = os.path.join(args.output_dir, f"reliability_report_{date_str}.csv")
                with open(reliability_csv, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(
                        f,
                        fieldnames=[
                            'annotator_id',
                            'n_tasks',
                            'ru_median_iou',
                            'ru_ci_level',
                            'ru_ci_low',
                            'ru_ci_high',
                            'ru_mean_iou',
                            'bootstrap_iters',
                        ],
                    )
                    writer.writeheader()
                    for uid, n, med, lo, hi, mean in items:
                        writer.writerow(
                            {
                                'annotator_id': uid,
                                'n_tasks': int(n),
                                'ru_median_iou': float(med),
                                'ru_ci_level': float(ci_level),
                                'ru_ci_low': float(lo),
                                'ru_ci_high': float(hi),
                                'ru_mean_iou': float(mean),
                                'bootstrap_iters': int(iters),
                            }
                        )
                print(f"Reliability report saved to {reliability_csv}")

        # --- Outlier / Edge Case Report ---
        print("\n--- Edge Case Candidates (For Paper) ---")
        # 1. High Modification (Low IoU) - Potential "Hard Cases" or "Bad Predictions"
        # Only sort by IoU for rows where IoU is computable.
        rows_with_iou = [r for r in rows if _safe_float(r.get('iou')) is not None]
        sorted_by_iou = sorted(rows_with_iou, key=lambda x: float(_safe_float(x.get('iou'))))
        print("\n[Top 5 Most Modified Tasks (Lowest IoU)] -> Check for 'Major Corrections'")
        for r in sorted_by_iou[:5]:
            i = _safe_float(r.get('iou'))
            t = _safe_float(r.get('active_time'))
            i_str = "NA" if i is None else f"{float(i):.4f}"
            t_str = "NA" if t is None else f"{float(t):.1f}s"
            print(f"Task {r['task_id']} (User {r['annotator_id']}): IoU={i_str}, Time={t_str}")

        # 2. High RMSE (Geometric Deviation) - Potential "3D Deformity" candidates
        # Prefer boundary_rmse (robust to add/delete points); fallback to Hungarian rmse_px.
        valid_boundary = [r for r in rows if r.get('boundary_rmse_px') is not None]
        if valid_boundary:
            sorted_by_brmse = sorted(valid_boundary, key=lambda x: float(x['boundary_rmse_px']), reverse=True)
            print("\n[Top 5 High Geometric Error (Highest Boundary-RMSE)] -> Check for '3D Deformity'")
            for r in sorted_by_brmse[:5]:
                i = _safe_float(r.get('iou'))
                i_str = "NA" if i is None else f"{i:.4f}"
                print(
                    f"Task {r['task_id']} (User {r['annotator_id']}): BoundaryRMSE={float(r['boundary_rmse_px']):.2f}, IoU={i_str}"
                )
        else:
            valid_rmse = [r for r in rows if r['rmse_px'] is not None]
            sorted_by_rmse = sorted(valid_rmse, key=lambda x: float(x['rmse_px']), reverse=True)
            print("\n[Top 5 High Geometric Error (Highest RMSE)] -> Check for '3D Deformity'")
            for r in sorted_by_rmse[:5]:
                i = _safe_float(r.get('iou'))
                i_str = "NA" if i is None else f"{i:.4f}"
                print(f"Task {r['task_id']} (User {r['annotator_id']}): RMSE={r['rmse_px']:.2f}, IoU={i_str}")

        # 3. High Time but Low Change (Inefficient?)
        # Heuristic: Time > 75th percentile AND IoU > 0.9
        times = [float(r['active_time']) for r in rows if _safe_float(r.get('active_time')) is not None]
        if times:
            time_thresh = np.percentile(times, 75)
            inefficient = []
            for r in rows:
                t = _safe_float(r.get('active_time'))
                i = _safe_float(r.get('iou'))
                if t is None or i is None:
                    continue
                if t > time_thresh and i > 0.9:
                    inefficient.append(r)
            if inefficient:
                print("\n[High Effort, Low Change] -> Check for 'Hesitation' or 'Fine-tuning'")
                for r in inefficient[:5]:
                    t = _safe_float(r.get('active_time'))
                    i = _safe_float(r.get('iou'))
                    t_str = "NA" if t is None else f"{float(t):.1f}s"
                    i_str = "NA" if i is None else f"{float(i):.4f}"
                    print(f"Task {r['task_id']}: Time={t_str}, IoU={i_str}")
            
    else:
        print("No annotations found to process.")

if __name__ == "__main__":
    main()
