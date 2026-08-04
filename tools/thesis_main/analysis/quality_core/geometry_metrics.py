"""Diagnostic geometry metrics for analyze_quality.

These metrics are analysis diagnostics, not admission or routing decisions.
"""

import numpy as np
from scipy.optimize import linear_sum_assignment
from scipy.signal import savgol_filter
from shapely.geometry import Polygon
from shapely.validation import make_valid

from lib.misc import panostretch


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


def analyze_layout_pairing(
    corners: np.ndarray,
    width: int = 1024,
    height: int = 512,
    threshold_ratio: float = 0.05,
    min_vertical_separation: float = 1.0,
    ambiguity_abs_epsilon: float = 1e-6,
    ambiguity_relative_margin: float = 0.01,
    maximum_search_nodes: int = 10_000,
) -> tuple[list[dict[str, float]], dict[str, object]]:
    """Return a strict, seam-aware pairing and diagnostics for formal scoring."""
    try:
        array = np.asarray(corners, dtype=np.float64)
    except Exception:
        array = np.empty((0, 2), dtype=np.float64)
    n_points = int(array.shape[0]) if array.ndim == 2 and array.shape[1:] == (2,) else 0
    finite_in_bounds = bool(
        n_points
        and np.isfinite(array).all()
        and (array[:, 0] >= 0).all()
        and (array[:, 0] < width).all()
        and (array[:, 1] >= 0).all()
        and (array[:, 1] < height).all()
    )
    base = {
        "n_points": n_points,
        "n_pairs": 0,
        "coverage": 0.0,
        "odd_points": bool(n_points % 2),
        "unpaired_point_count": n_points,
        "pairing_ambiguous": False,
        "best_cost": None,
        "second_best_cost": None,
        "optimal_matching_count": 0,
        "ambiguity_reason": "",
        "finite_in_bounds": finite_in_bounds,
    }
    if not finite_in_bounds or n_points < 2 or n_points % 2:
        return [], base

    threshold = float(width) * float(threshold_ratio)

    def circular_dx(i: int, j: int) -> float:
        delta = abs(float(array[i, 0]) - float(array[j, 0]))
        return min(delta, float(width) - delta)

    candidates = {
        i: [j for j in range(n_points) if j != i and circular_dx(i, j) < threshold and abs(array[i, 1] - array[j, 1]) >= min_vertical_separation]
        for i in range(n_points)
    }
    matchings: list[tuple[float, list[tuple[int, int]]]] = []
    search_nodes = 0
    search_exhausted = False

    def search(remaining: tuple[int, ...], pairs: list[tuple[int, int]], cost: float) -> None:
        nonlocal search_nodes, search_exhausted
        search_nodes += 1
        if search_nodes > maximum_search_nodes:
            search_exhausted = True
            return
        if not remaining:
            matchings.append((cost, list(pairs)))
            return
        i = min(remaining, key=lambda value: sum(candidate in remaining for candidate in candidates[value]))
        rest = set(remaining)
        rest.remove(i)
        for j in candidates[i]:
            if j not in rest:
                continue
            next_remaining = tuple(sorted(rest - {j}))
            search(next_remaining, pairs + [(i, j)], cost + circular_dx(i, j))

    search(tuple(range(n_points)), [], 0.0)
    if search_exhausted:
        base.update(pairing_search_exhausted=True, pairing_search_nodes=search_nodes)
        return [], base
    if not matchings:
        greedy, greedy_stats = _pair_keypoints_to_layout(array, width=width, threshold_ratio=threshold_ratio, return_stats=True)
        base.update(
            n_pairs=int(greedy_stats["n_pairs"]),
            coverage=float(greedy_stats["coverage"]),
            unpaired_point_count=n_points - 2 * int(greedy_stats["n_pairs"]),
        )
        return greedy, base
    matchings.sort(key=lambda item: item[0])
    best_cost = matchings[0][0]
    optimal = [item for item in matchings if abs(item[0] - best_cost) <= ambiguity_abs_epsilon]
    second_cost = next((cost for cost, _pairs in matchings if cost > best_cost + ambiguity_abs_epsilon), None)
    near_margin = max(ambiguity_abs_epsilon, abs(best_cost) * ambiguity_relative_margin)
    ambiguous = len(optimal) > 1 or (second_cost is not None and second_cost - best_cost <= near_margin)
    reason = "exact_tied_optimum" if len(optimal) > 1 else "near_equivalent_matching" if ambiguous else ""
    matching = optimal[0][1]
    pairs = []
    for i, j in matching:
        x1, x2 = float(array[i, 0]), float(array[j, 0])
        if abs(x1 - x2) > width / 2:
            low, high = sorted((x1, x2))
            x = ((high + low + width) / 2.0) % width
        else:
            x = (x1 + x2) / 2.0
        pairs.append({"x": x, "y_ceiling": min(float(array[i, 1]), float(array[j, 1])), "y_floor": max(float(array[i, 1]), float(array[j, 1]))})
    pairs.sort(key=lambda item: item["x"])
    base.update(
        n_pairs=len(pairs),
        coverage=1.0,
        unpaired_point_count=0,
        pairing_ambiguous=ambiguous,
        best_cost=best_cost,
        second_best_cost=second_cost,
        optimal_matching_count=len(optimal),
        ambiguity_reason=reason,
        pairing_search_exhausted=False,
        pairing_search_nodes=search_nodes,
    )
    return pairs, base


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


def compute_layout_mask_iou(
    pred_corners: np.ndarray,
    ref_corners: np.ndarray,
    width: int = 1024,
    height: int = 512,
) -> tuple[float | None, dict[str, object]]:
    """Compute seam-aware 2D layout-region IoU from ceiling/floor corner pairs."""
    pred_pairs, pred_stats = analyze_layout_pairing(pred_corners, width=width, height=height)
    ref_pairs, ref_stats = analyze_layout_pairing(ref_corners, width=width, height=height)
    meta: dict[str, object] = {
        "pred_pair_count": int(pred_stats.get("n_pairs", 0)),
        "ref_pair_count": int(ref_stats.get("n_pairs", 0)),
        "width": int(width),
        "height": int(height),
        "pred_pairing": pred_stats,
        "ref_pairing": ref_stats,
    }
    if (
        len(pred_pairs) < 2
        or len(ref_pairs) < 2
        or pred_stats.get("pairing_ambiguous")
        or ref_stats.get("pairing_ambiguous")
        or float(pred_stats.get("coverage", 0)) < 1.0
        or float(ref_stats.get("coverage", 0)) < 1.0
    ):
        meta["reason"] = "insufficient_pairs"
        return None, meta

    return compute_layout_mask_iou_from_normalized_pairs(pred_pairs, ref_pairs, width=width, height=height)


def compute_layout_mask_iou_from_normalized_pairs(
    pred_pairs: list[dict[str, float]],
    ref_pairs: list[dict[str, float]],
    width: int = 1024,
    height: int = 512,
) -> tuple[float | None, dict[str, object]]:
    """Compute layout IoU from already validated pairs without pairing again."""
    meta: dict[str, object] = {"pred_pair_count": len(pred_pairs), "ref_pair_count": len(ref_pairs), "width": width, "height": height}
    if len(pred_pairs) < 2 or len(ref_pairs) < 2:
        meta["reason"] = "insufficient_pairs"
        return None, meta

    def _mask(pairs: list[dict[str, float]]) -> np.ndarray:
        xs = np.asarray([p["x"] for p in pairs], dtype=np.float32)
        y_ceil = np.asarray([p["y_ceiling"] for p in pairs], dtype=np.float32)
        y_floor = np.asarray([p["y_floor"] for p in pairs], dtype=np.float32)
        dense_ceil = np.clip(np.rint(_interp_periodic(xs, y_ceil, width)), 0, height - 1).astype(np.int32)
        dense_floor = np.clip(np.rint(_interp_periodic(xs, y_floor, width)), 0, height - 1).astype(np.int32)
        mask = np.zeros((height, width), dtype=bool)
        for x, (top, bottom) in enumerate(zip(dense_ceil, dense_floor)):
            if bottom < top:
                top, bottom = bottom, top
            mask[top : bottom + 1, x] = True
        return mask

    pred_mask = _mask(pred_pairs)
    ref_mask = _mask(ref_pairs)
    union = np.logical_or(pred_mask, ref_mask).sum()
    if union == 0:
        meta["reason"] = "empty_union"
        return None, meta
    meta["reason"] = ""
    return float(np.logical_and(pred_mask, ref_mask).sum() / union), meta


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
