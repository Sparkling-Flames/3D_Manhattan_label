"""全景二维墙带研究入口；不读取 GT、不重新配对、不推断三维环序。

输入采用 1024×512 像素中心坐标。水平排序仅定义单值二维包络。
curve 使用既有 pano_connect_points；linear 只作为表示敏感性对照。
EM / greedy 是显式项目适配，不是 Lee 原算法的完整复现。
"""
import importlib.util

import numpy as np
from scipy.special import expit, logit

from lib.misc.panostretch import pano_connect_points


def wall_mask(pairs, width=512, height=256, mode="curve"):
    """已审核 (N,2,2) 上下点对 -> 全幅布尔墙带；不可表示时显式失败。"""
    p = np.asarray(pairs, dtype=float)
    if mode not in ("curve", "linear"):
        raise ValueError("unknown_boundary_mode")
    if not isinstance(width, int) or not isinstance(height, int) or min(width, height) < 2:
        raise ValueError("invalid_resolution")
    if p.ndim != 3 or p.shape[1:] != (2, 2) or len(p) < 3:
        raise ValueError("insufficient_or_invalid_pairs")
    if not np.isfinite(p).all():
        raise ValueError("nonfinite_coordinates")
    dx = (p[:, 0, 0] - p[:, 1, 0] + 512) % 1024 - 512
    if np.any(np.abs(dx) > 1e-6):
        raise ValueError("pairs_not_shared_x")
    if np.any(p[:, :, 1] < -.5) or np.any(p[:, :, 1] >= 511.5):
        raise ValueError("vertical_coordinates_outside_image")
    if np.any(p[:, 0, 1] >= p[:, 1, 1]):
        raise ValueError("inverted_pair")
    p = (p + .5) * np.array([width / 1024, height / 512]) - .5
    p[:, :, 0] %= width
    p = p[np.argsort(p[:, 0, 0])]
    gaps = np.diff(np.r_[p[:, 0, 0], p[0, 0, 0] + width])
    if np.any(gaps < 1e-6):
        raise ValueError("duplicate_longitude_envelope_unresolved")
    if np.any(gaps >= width / 2 - 1e-8):
        raise ValueError("longitude_span_at_least_half_circle")
    boundaries = np.full((2, width), np.nan)
    if mode == "linear":
        for side in range(2):
            boundaries[side] = np.interp(np.arange(width), p[:, side, 0],
                                         p[:, side, 1], period=width)
    else:
        horizon = height / 2 - .5
        if np.any(p[:, 0, 1] >= horizon) or np.any(p[:, 1, 1] <= horizon):
            raise ValueError("curve_requires_ceiling_above_and_floor_below_horizon")
        for side, z in enumerate((-50, 50)):
            for i in range(len(p)):
                with np.errstate(divide="ignore", invalid="ignore"):
                    samples = pano_connect_points(p[i, side], p[(i + 1) % len(p), side],
                                                  z=z, w=width, h=height)
                if not np.isfinite(samples).all():
                    raise ValueError("nonfinite_curve_branch")
                xs = samples[:, 0].astype(int)
                ys = samples[:, 1]
                if np.any(ys < -.5) or np.any(ys >= height - .5):
                    raise ValueError("curve_outside_image")
                previous = boundaries[side, xs]
                if np.any(np.isfinite(previous) & (np.abs(previous - ys) > 1e-5)):
                    raise ValueError("ambiguous_curve_branch")
                boundaries[side, xs] = ys
        if not np.isfinite(boundaries).all():
            raise ValueError("curve_has_uncovered_columns")
    if np.any(boundaries[0] >= boundaries[1]):
        raise ValueError("inverted_envelope")
    yy = np.arange(height)[:, None]
    mask = (yy >= boundaries[0]) & (yy <= boundaries[1])
    if not mask.any():
        raise ValueError("empty_rasterized_region")
    return mask


def _mask(mask):
    a = np.asarray(mask)
    if a.ndim != 2 or min(a.shape) < 1 or not np.isin(a, [0, 1]).all():
        raise ValueError("expected_nonempty_2d_binary_mask")
    return a.astype(bool)


def centroid(mask):
    """面积质心；ERP 坐标依赖接缝，圆周方向在 R≈0 时没有定义。"""
    a = _mask(mask)
    h, w = a.shape
    area = int(a.sum())
    if not area:
        return dict(area_pixels=0, erp_x_px=None, erp_y_px=None,
                    circular_angle_rad=None, circular_R=None, moment_cos=None, moment_sin=None)
    xs = (np.arange(w) + .5) * 1024 / w - .5
    ys = (np.arange(h) + .5) * 512 / h - .5
    angles = ((np.arange(w) + .5) / w - .5) * 2 * np.pi
    moment = np.dot(a.sum(axis=0), np.exp(1j * angles)) / area
    return dict(area_pixels=area, erp_x_px=float(np.dot(a.sum(0), xs) / area),
                erp_y_px=float(np.dot(a.sum(1), ys) / area),
                circular_angle_rad=float(np.angle(moment)) if abs(moment) > 1e-12 else None,
                circular_R=float(abs(moment)), moment_cos=float(moment.real), moment_sin=float(moment.imag))


def compare_masks(a, b):
    """a 相对 b 的质心偏移；所有 px 指原始 1024×512，空区域不伪造质心。"""
    a, b = _mask(a), _mask(b)
    if a.shape != b.shape:
        raise ValueError("mask_shape_mismatch")
    union = int((a | b).sum())
    ca, cb = centroid(a), centroid(b)
    result = dict(iou=float((a & b).sum() / union) if union else None,
                  erp_dx_px=None, dy_px=None, erp_distance_px=None,
                  circular_dx_px=None, moment_distance=None)
    if ca["area_pixels"] and cb["area_pixels"]:
        dx, dy = ca["erp_x_px"] - cb["erp_x_px"], ca["erp_y_px"] - cb["erp_y_px"]
        result.update(erp_dx_px=dx, dy_px=dy, erp_distance_px=float(np.hypot(dx, dy)),
                      moment_distance=float(np.hypot(ca["moment_cos"] - cb["moment_cos"],
                                                     ca["moment_sin"] - cb["moment_sin"])))
        if ca["circular_angle_rad"] is not None and cb["circular_angle_rad"] is not None:
            delta = (ca["circular_angle_rad"] - cb["circular_angle_rad"] + np.pi) % (2*np.pi) - np.pi
            result["circular_dx_px"] = float(delta * 1024 / (2*np.pi))
    return result


def aggregate(masks, method="mv50", weights=None, max_iter=100, tol=1e-7):
    """固定全幅像素域聚合；无 GT 接口。权重仅适用于两种投票规则。

    medoid 最小平均 Jaccard 距离，平手选输入首位。
    EM 单正确率约束 (.5,1)，固定先验 .5，非标准 STAPLE。
    greedy 最大化期望交并面积之比，非期望 IoU，非原论文精确复现。
    """
    v = np.asarray(masks)
    if v.ndim != 3 or min(v.shape) < 1 or not np.isin(v, [0, 1]).all():
        raise ValueError("expected_worker_height_width_binary_masks")
    v = v.astype(bool)
    if not isinstance(max_iter, int) or max_iter < 1 or not np.isfinite(tol) or tol <= 0:
        raise ValueError("invalid_iteration_controls")
    if weights is not None and method not in ("mv50", "mv_strict"):
        raise ValueError("weights_only_supported_for_voting")
    w = np.ones(len(v)) if weights is None else np.asarray(weights, float)
    if (w.shape != (len(v),) or not np.isfinite(w).all() or (w < 0).any()
            or not np.isfinite(w.sum()) or w.sum() <= 0):
        raise ValueError("invalid_worker_weights")
    p = np.average(v, axis=0, weights=w)
    out = dict(method=method, status="ok", probability=p, support=v.mean(0))
    if method in ("mv50", "mv_strict"):
        selected = p >= .5 if method == "mv50" else p > .5
    elif method == "medoid":
        scores = []
        for a in v:
            union = (v | a).sum(axis=(1, 2))
            scores.append(np.divide((v & a).sum(axis=(1, 2)), union,
                                    out=np.ones(len(v)), where=union > 0).mean())
        idx = int(np.argmax(scores))
        selected = v[idx].copy()
        out.update(selected_worker_index=idx, probability=None)
    elif method == "em_correct_probability":
        flat = v.reshape(len(v), -1).astype(float)
        q = np.clip((flat == (p.ravel() >= .5)).mean(1), .500001, .999999)
        converged = False
        for iteration in range(max_iter):
            posterior = expit(((2*flat - 1) * logit(q)[:, None]).sum(0))
            nq = np.clip((flat*posterior + (1-flat)*(1-posterior)).mean(1), .500001, .999999)
            converged = bool(np.max(np.abs(nq-q)) < tol)
            q = nq
            if converged:
                break
        p = expit(((2*flat-1)*logit(q)[:, None]).sum(0)).reshape(v.shape[1:])
        selected = p >= .5
        out.update(probability=p, correct_probability=q, iterations=iteration+1,
                   converged=converged, status="ok" if converged else "max_iterations",
                   adaptation="full_domain_flat_prior_single_correct_probability")
    elif method == "greedy_empirical":
        selected = np.zeros(p.shape, bool)
        total, numerator, extra_union, best = p.sum(), 0., 0., 0.
        for level in np.unique(p[p > 0])[::-1]:
            group = p == level
            nn, nd = numerator + p[group].sum(), extra_union + (1-p[group]).sum()
            score = nn / (total+nd)
            if score + 1e-12 < best:
                break
            selected[group] = True
            numerator, extra_union, best = nn, nd, score
        out["adaptation"] = "empirical_ratio_of_expected_intersection_and_union"
    elif method == "staple":
        if importlib.util.find_spec("SimpleITK") is None:
            return dict(method=method, status="unavailable", reason="SimpleITK_not_installed",
                        mask=None, probability=None, support=v.mean(0))
        import SimpleITK as sitk
        filt = sitk.STAPLEImageFilter()
        filt.SetForegroundValue(1)
        filt.SetMaximumIterations(max_iter)
        try:
            p = sitk.GetArrayFromImage(filt.Execute([sitk.GetImageFromArray(a.astype(np.uint8)) for a in v]))
        except RuntimeError as exc:
            return dict(method=method, status="failed", reason=str(exc), mask=None, probability=None)
        if not np.isfinite(p).all():
            return dict(method=method, status="failed", reason="nonfinite_STAPLE_probability", mask=None, probability=None)
        selected = p >= .5
        elapsed = int(filt.GetElapsedIterations())
        out.update(probability=p, sensitivity=list(filt.GetSensitivity()), specificity=list(filt.GetSpecificity()),
                   iterations=elapsed, status="ok" if elapsed < max_iter else "max_iterations")
    else:
        raise ValueError("unknown_consensus_method")
    out["mask"] = selected
    return out
