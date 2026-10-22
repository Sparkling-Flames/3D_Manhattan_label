#!/usr/bin/env python3
"""Exact amplitude/support diagnostics on an existing linear wall profile.

No labels, scoring weights, semantic decisions, reference selection or new
pairing are performed. Caller retains the original geometry qualification.
"""
from __future__ import annotations
import math
import numpy as np


DISPLAY_LEVELS = (0.10, 0.20, 0.40)


def profile(record):
    b = np.asarray(record["bottom3d"], dtype=float)
    t = np.asarray(record["top3d"], dtype=float)
    if b.shape != t.shape or b.ndim != 2 or b.shape[1] != 3 or len(b) < 3:
        raise ValueError("existing_complete_paired_rings_required")
    if not np.isfinite(b).all() or not np.isfinite(t).all():
        raise ValueError("nonfinite_profile_input")
    heights = t[:, 1] - b[:, 1]
    ell = np.linalg.norm(np.roll(b[:, [0, 2]], -1, axis=0) - b[:, [0, 2]], axis=1)
    if np.any(heights <= 0) or np.any(ell <= 0):
        raise ValueError("positive_wall_heights_and_floor_edges_required")
    perimeter = math.fsum(float(x) for x in ell)
    hn = np.roll(heights, -1)
    mean = math.fsum(float(w * (a + z) / 2) for w, a, z in zip(ell, heights, hn)) / perimeter
    return heights, ell, perimeter, mean


def linear_above_fraction(start, end, threshold):
    """Lebesgue fraction of u in [0,1] with (1-u)*start+u*end > threshold."""
    slope = end - start
    if slope == 0:
        return float(start > threshold)
    crossing = (threshold - start) / slope
    clipped = min(1.0, max(0.0, crossing))
    return 1.0 - clipped if slope > 0 else clipped


def amplitude_support(record, reference_mean_height, levels=DISPLAY_LEVELS):
    h, ell, perimeter, own_mean = profile(record)
    scale = float(reference_mean_height)
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError("positive_reference_mean_height_required")
    d = h - own_mean
    dn = np.roll(d, -1)
    supports = {}
    for level in levels:
        if not math.isfinite(level) or level < 0:
            raise ValueError("finite_nonnegative_display_scale_required")
        cutoff = float(level) * scale
        fractions = [linear_above_fraction(float(a), float(z), cutoff)
                     + linear_above_fraction(float(-a), float(-z), cutoff)
                     for a, z in zip(d, dn)]
        support = math.fsum(float(w * f) for w, f in zip(ell, fractions)) / perimeter
        supports[f"support_gtmean_{int(round(level*100)):02d}"] = min(1., max(0., support))
    return {
        "wall_height_mean_h": own_mean,
        "wall_height_min_h": float(h.min()),
        "wall_height_max_h": float(h.max()),
        "floor_perimeter_h": perimeter,
        "height_range_over_gt_mean": float((h.max() - h.min()) / scale),
        "max_abs_deviation_from_own_mean_over_gt_mean": float(np.max(np.abs(d)) / scale),
        **supports,
    }


def paired_height_diagnostics(annotation, reference, levels=DISPLAY_LEVELS):
    _, _, _, mu_g = profile(reference)
    a = amplitude_support(annotation, mu_g, levels)
    g = amplitude_support(reference, mu_g, levels)
    return {
        **{"annotation_" + k: v for k, v in a.items()},
        **{"reference_" + k: v for k, v in g.items()},
        "global_mean_height_relative_error": abs(a["wall_height_mean_h"] - mu_g) / mu_g,
        "display_levels": list(levels),
        "support_center": "each_profile_own_floor_perimeter_mean",
        "normalization": "reference_floor_perimeter_mean_wall_height",
        "score_modified": False,
    }
