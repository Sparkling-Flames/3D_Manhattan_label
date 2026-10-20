"""Frozen parallel pair diagnostics; never changes fusion, scoring or eligibility.

See METRIC_CONTRACT.json.  ``pair_metrics(a, b, fe=None, cache=None)`` retains
the old same-pool/reference/k contract and all old fields. ``geometry_metrics``
can also compare a nested different-k pair, without inventing old joint flags.
Optional caches contain geometry signatures only and should be cleared per pool.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np
import shapely
from shapely.geometry import Point, Polygon, LineString

_OLD = Path(__file__).resolve().parents[2] / "analysis/composition"
if not _OLD.is_dir():
    raise ImportError("Expected frozen analysis/composition beside interchangeability_20261020")
sys.path.insert(0, str(_OLD))
import summarize_grid as _old
import geometry_diagnostics as _diag

SCHEMA = "interchangeability_pair_diagnostics_v1"
THRESHOLDS = (("strict", 1., .02, 2., .98),
              ("main", 2., .05, 3., .95),
              ("wide", 5., .10, 5., .90))
AZIMUTH_SAMPLES = 1024
BOUNDARY_SAMPLES = 512
WIDTH, HEIGHT = 1024., 512.


def _clean(value):
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    if isinstance(value, (tuple, list, np.ndarray)):
        return [_clean(v) for v in value]
    if isinstance(value, np.generic):
        return _clean(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _number(value):
    return _old.number(value)


def _stats(value, prefix):
    v = np.asarray(value, float)
    v = v[np.isfinite(v)]
    return {prefix + "_n": int(len(v)),
            prefix + "_mean": float(v.mean()) if len(v) else None,
            prefix + "_p95": float(np.quantile(v, .95)) if len(v) else None,
            prefix + "_max": float(v.max()) if len(v) else None}


def _profile(ring, top_y):
    """Nearest positive ray hit; 3D top edge is linearly interpolated on wall."""
    phi = 2 * np.pi * ((np.arange(AZIMUTH_SAMPLES) + .5) / AZIMUTH_SAMPLES - .5)
    ray = np.column_stack((np.sin(phi), -np.cos(phi)))
    end = np.roll(ring, -1, axis=0)
    edge = end - ring
    # cross(ray, edge), cross(start, edge), cross(start, ray)
    den = ray[:, None, 0] * edge[None, :, 1] - ray[:, None, 1] * edge[None, :, 0]
    num_r = ring[:, 0] * edge[:, 1] - ring[:, 1] * edge[:, 0]
    num_t = ring[None, :, 0] * ray[:, None, 1] - ring[None, :, 1] * ray[:, None, 0]
    with np.errstate(divide="ignore", invalid="ignore"):
        radii, along = num_r[None, :] / den, num_t / den
    valid = (np.abs(den) > 1e-12) & (radii > 0) & (along >= -1e-10) & (along <= 1 + 1e-10)
    radii = np.where(valid, radii, np.inf)
    chosen = np.argmin(radii, axis=1)
    r = radii[np.arange(len(ray)), chosen]
    w = along[np.arange(len(ray)), chosen]
    ty = (1 - w) * top_y[chosen] + w * top_y[(chosen + 1) % len(top_y)]
    good = np.isfinite(r) & np.isfinite(ty) & (ty > 0)
    return {"radius": r, "top_y": ty, "valid": good,
            "bottom_angle_deg": np.degrees(np.arctan2(-1., r)),
            "top_angle_deg": np.degrees(np.arctan2(ty, r))}


def _signature(row, cache=None):
    geometry = row.get("geometry") or {}
    key = hashlib.sha256(json.dumps(geometry, sort_keys=True, separators=(",", ":"), allow_nan=True).encode()).hexdigest()
    if cache is not None and key in cache:
        return cache[key]
    floor = _diag._prepare_ring(geometry.get("footprint"))
    s = {"floor": floor, "polygon": None, "profile": None, "top_y": None,
         "ray_status": "floor_unavailable", "flat_prism_height": None,
         "flat_prism_reason": "floor_unavailable"}
    if floor["status"] == "ok":
        p = floor["points"]
        s["polygon"] = Polygon(p)
        s["corners"], s["turns"] = _diag._corners(p)
        before, after = p - np.roll(p, 1, axis=0), np.roll(p, -1, axis=0) - p
        signed_turn = before[:, 0] * after[:, 1] - before[:, 1] * after[:, 0]
        signed_area = np.sum(p[:, 0] * np.roll(p[:, 1], -1) - p[:, 1] * np.roll(p[:, 0], -1))
        s["reflex"] = signed_turn * signed_area < 0
        line = LineString(np.vstack((p, p[0])))
        d = (np.arange(BOUNDARY_SAMPLES) + .5) * line.length / BOUNDARY_SAMPLES
        s["boundary_line"] = line
        s["boundary_samples"] = shapely.line_interpolate_point(line, d)
        raw = geometry.get("points")
        points = np.asarray(raw, float) if raw is not None else None
        if points is None or points.ndim != 2 or points.shape[1:] != (2,) or len(points) % 2 or not np.isfinite(points).all():
            s["ray_status"] = "missing_or_invalid_point_pairs"
        elif len(points) // 2 != floor["input_n"]:
            s["ray_status"] = "floor_point_pair_count_mismatch"
        else:
            selected = floor["input_indices"]
            top, bottom = points[2 * selected], points[2 * selected + 1]
            du = (top[:, 0] - bottom[:, 0] + WIDTH / 2) % WIDTH - WIDTH / 2
            beta = np.pi * (.5 - bottom[:, 1] / HEIGHT)
            alpha = np.pi * (.5 - top[:, 1] / HEIGHT)
            phi = 2 * np.pi * (bottom[:, 0] / WIDTH - .5)
            with np.errstate(divide="ignore", invalid="ignore"):
                radius = -1. / np.tan(beta)
                derived = radius[:, None] * np.column_stack((np.sin(phi), -np.cos(phi)))
                top_y = radius * np.tan(alpha)
            error = float(np.max(np.abs(derived - p)))
            s["bottom_ray_floor_max_abs_error"] = error
            if np.max(np.abs(du)) > 1e-6:
                s["ray_status"] = "vertical_pair_mismatch"
            elif np.any(beta >= -math.radians(.5)) or np.any(alpha <= math.radians(.5)) or np.any(alpha >= math.pi / 2 - 1e-8):
                s["ray_status"] = "invalid_or_near_horizon_paired_rays"
            elif not np.isfinite(top_y).all() or np.any(top_y <= 0):
                s["ray_status"] = "nonfinite_or_nonpositive_ceiling"
            elif error > 1e-7 * max(1., float(np.max(np.abs(p)))):
                s["ray_status"] = "floor_differs_from_frozen_bottom_rays"
            else:
                s["top_y"] = top_y
                spread = float(np.ptp(top_y))
                tolerance = 1e-10 + 1e-8 * max(1., float(np.max(np.abs(top_y))))
                if spread <= tolerance:
                    s["flat_prism_height"] = float(1 + np.mean(top_y))
                    s["flat_prism_reason"] = "identified_horizontal_ceiling_prism"
                else:
                    s["flat_prism_reason"] = "nonflat_ceiling_interior_surface_not_identified"
                if not s["polygon"].contains(Point(0., 0.)):
                    s["ray_status"] = "camera_not_strictly_inside_floor"
                else:
                    s["profile"] = _profile(p, top_y)
                    s["ray_status"] = "ok"
        if s["flat_prism_height"] is None and s["flat_prism_reason"] == "floor_unavailable":
            s["flat_prism_reason"] = s["ray_status"]
    if cache is not None:
        cache[key] = s
    return s


def geometry_metrics(a, b, *, cache=None):
    """Scalar geometry supplement; no score or original node-count requirement."""
    assert a["pool_id"] == b["pool_id"] and a["reference_id"] == b["reference_id"]
    sa, sb = _signature(a, cache), _signature(b, cache)
    fa, fb = sa["floor"], sb["floor"]
    out = {"pair_metric_schema": SCHEMA, "shape_floor_status_a": fa["status"], "shape_floor_status_b": fb["status"],
           "shape_ray_status_a": sa["ray_status"], "shape_ray_status_b": sb["ray_status"],
           "shape_pair_scale": None, "shape_floor_jaccard_difference": None,
           "true_corner_n_a": None, "true_corner_n_b": None, "true_corner_count_difference": None,
           "true_reflex_corner_n_a": None, "true_reflex_corner_n_b": None,
           "boundary_common_azimuth_fraction": None, "exact_flat_prism_pair_iou": None,
           "exact_flat_prism_status_a": sa["flat_prism_reason"], "exact_flat_prism_status_b": sb["flat_prism_reason"],
           "inferred_total_height_mean_a": None, "inferred_total_height_mean_b": None,
           "inferred_total_height_mean_abs_logratio": None}
    for prefix in ["boundary_distance_normalized", "bottom_y_absdiff_deg", "top_y_absdiff_deg", "radius_abs_logratio", "boundary_total_height_abs_logratio"]:
        out.update(_stats([], prefix))
    for name, _, _, _, _ in THRESHOLDS:
        out.update({"wall_coverage_a_by_b_" + name: None, "wall_coverage_b_by_a_" + name: None,
                    "wall_coverage_symmetric_min_" + name: None, "true_corner_matched_n_" + name: None,
                    "true_corner_F1_" + name: None, "true_corner_max_matched_distance_normalized_" + name: None,
                    "matched_corner_reflex_disagreement_n_" + name: None,
                    "matched_corner_turn_absdiff_deg_max_" + name: None,
                    "geometry_shape_" + name: False})
    for suffix, s in (("a", sa), ("b", sb)):
        if s["top_y"] is not None:
            heights = s["top_y"] + 1
            out["inferred_total_height_mean_" + suffix] = float(heights.mean())
            out["inferred_total_height_min_" + suffix] = float(heights.min())
            out["inferred_total_height_max_" + suffix] = float(heights.max())
            out["inferred_ceiling_y_range_" + suffix] = float(np.ptp(s["top_y"]))
    ha, hb = out["inferred_total_height_mean_a"], out["inferred_total_height_mean_b"]
    if ha and hb:
        out["inferred_total_height_mean_abs_logratio"] = abs(math.log(ha / hb))
    if fa["status"] != "ok" or fb["status"] != "ok":
        return _clean(out)
    pa, pb = fa["points"], fb["points"]
    poly_a, poly_b = sa["polygon"], sb["polygon"]
    scale = math.sqrt((fa["area"] + fb["area"]) / 2)
    inter = float(poly_a.intersection(poly_b).area)
    union = fa["area"] + fb["area"] - inter
    floor_diff = max(0., 1 - inter / union)
    out.update(shape_pair_scale=scale, shape_floor_jaccard_difference=floor_diff,
               true_corner_n_a=len(sa["corners"]), true_corner_n_b=len(sb["corners"]),
               true_reflex_corner_n_a=int(sa["reflex"][sa["corners"]].sum()),
               true_reflex_corner_n_b=int(sb["reflex"][sb["corners"]].sum()),
               true_corner_count_difference=abs(len(sa["corners"]) - len(sb["corners"])))
    distances = np.concatenate((shapely.distance(sa["boundary_samples"], sb["boundary_line"]),
                                shapely.distance(sb["boundary_samples"], sa["boundary_line"]))) / scale
    out.update(_stats(distances, "boundary_distance_normalized"))
    if sa["profile"] is not None and sb["profile"] is not None:
        x, y = sa["profile"], sb["profile"]
        common = x["valid"] & y["valid"]
        out["boundary_common_azimuth_fraction"] = float(common.mean())
        for field, prefix in (("bottom_angle_deg", "bottom_y_absdiff_deg"), ("top_angle_deg", "top_y_absdiff_deg")):
            out.update(_stats(np.abs(x[field][common] - y[field][common]), prefix))
        out.update(_stats(np.abs(np.log(x["radius"][common] / y["radius"][common])), "radius_abs_logratio"))
        out.update(_stats(np.abs(np.log((x["top_y"][common] + 1) / (y["top_y"][common] + 1))), "boundary_total_height_abs_logratio"))
    if sa["flat_prism_height"] and sb["flat_prism_height"]:
        ha, hb = sa["flat_prism_height"], sb["flat_prism_height"]
        volume_inter = inter * min(ha, hb)
        out["exact_flat_prism_pair_iou"] = volume_inter / (fa["area"] * ha + fb["area"] * hb - volume_inter)
    for name, _, fraction, degrees, retained in THRESHOLDS:
        ca = _diag._wall_coverage(pb, pa, fraction * scale)["coverage"]
        cb = _diag._wall_coverage(pa, pb, fraction * scale)["coverage"]
        matches = _diag._maximum_cardinality_min_distance(pa[sa["corners"]], pb[sb["corners"]], fraction * scale)
        total = len(sa["corners"]) + len(sb["corners"])
        f1 = 2 * len(matches) / total if total else None
        out.update({"wall_coverage_a_by_b_" + name: ca, "wall_coverage_b_by_a_" + name: cb,
                    "wall_coverage_symmetric_min_" + name: min(ca, cb), "true_corner_matched_n_" + name: len(matches),
                    "true_corner_F1_" + name: f1,
                    "matched_corner_reflex_disagreement_n_" + name: sum(sa["reflex"][sa["corners"][i]] != sb["reflex"][sb["corners"][j]] for i, j, _ in matches),
                    "matched_corner_turn_absdiff_deg_max_" + name: max((abs(sa["turns"][sa["corners"][i]] - sb["turns"][sb["corners"][j]]) for i, j, _ in matches), default=None),
                    "true_corner_max_matched_distance_normalized_" + name: max((v[2] for v in matches), default=0.) / scale if matches else None})
        coverage = out["boundary_common_azimuth_fraction"]
        bottom, top = out["bottom_y_absdiff_deg_p95"], out["top_y_absdiff_deg_p95"]
        out["geometry_shape_" + name] = bool(a.get("complete_evaluable") and b.get("complete_evaluable") and
            floor_diff <= fraction and min(ca, cb) >= retained and f1 is not None and f1 >= retained and
            coverage is not None and coverage >= .99 and bottom is not None and top is not None and
            bottom <= degrees and top <= degrees)
    return _clean(out)


def pair_metrics(a, b, *, fe=None, cache=None):
    """Old exact fields plus frozen parallel shape/boundary/height diagnostics.

    ``fe`` is accepted for caller compatibility; this function never fuses or
    scores. Primary same-k legacy metrics are imported unchanged.
    """
    out = _old.pair_metrics(a, b)
    out.update(geometry_metrics(a, b, cache=cache))
    for name, q, fraction, degrees, _ in THRESHOLDS:
        dq, floor, bound = out["abs_B8L2_change"], out["floor_jaccard_difference"], out["structure_bound_cyclic_deg"]
        out["geometry_noQ_" + name] = bool(out["both_complete"] and out["node_count_difference"] == 0 and
            floor is not None and floor <= fraction and bound is not None and bound <= degrees)
        out["quality_only_" + name] = bool(out["both_complete"] and dq is not None and dq <= q)
    out["geometry_main"] = out["geometry_noQ_main"]
    out["quality_main"] = out["quality_only_main"]
    out["prism_proxy_pair_iou"] = out["mean_height_prism_pair_iou"]
    proxy = out["prism_proxy_pair_iou"]
    out["geometry_shape_main_and_prism_proxy_iou_lt_095"] = bool(out["geometry_shape_main"] and proxy is not None and proxy < .95)
    out["legacy_main_rejects_shape_main_passes"] = bool(out["geometry_shape_main"] and not out["joint_stable_main"])
    out["different_original_nodes_shape_main_passes"] = bool(out["geometry_shape_main"] and out["node_count_difference"] != 0)
    return _clean(out)
