#!/usr/bin/env python3
"""Mean-centered nearest-floor height residual, a diagnostic/candidate input.

Requires the frozen height_revision module to be importable, or explicitly
passed as height_module. The original records are never changed. This
temporary profile centering does not create or approve a new 3D layout.
"""
from __future__ import annotations
import math
import numpy as np


def centered_height_components(annotation, reference, samples=4096, height_module=None):
    if height_module is None:
        import height_revision as height_module
    am = height_module.height_moments(annotation)
    gm = height_module.height_moments(reference)
    delta = am["height_mean_h"] - gm["height_mean_h"]
    # Only a temporary vertical profile is shifted; XZ, ring order, source
    # sample positions and nearest target floor sets remain exactly fixed.
    centered = {
        "bottom3d": np.asarray(annotation["bottom3d"], dtype=float).copy(),
        "top3d": np.asarray(annotation["top3d"], dtype=float).copy(),
    }
    centered["top3d"][:, 1] -= delta
    ag = height_module.directed_nearest_footprint_height_mse(centered, reference, samples, "max")
    ga = height_module.directed_nearest_footprint_height_mse(reference, centered, samples, "max")
    hcenter = math.sqrt((ag["mse_h2"] + ga["mse_h2"]) / 2) / gm["height_mean_h"]
    min_height = float((centered["top3d"][:, 1] - centered["bottom3d"][:, 1]).min())
    return {
        "Hcenter": hcenter,
        "height_center_shift_h": -delta,
        "height_center_signed_global_relative": delta / gm["height_mean_h"],
        "height_centered_min_wall_height_h": min_height,
        "height_centered_profile_positive": min_height > 0,
        "height_center_AG_distinct_tied_height_fraction": ag["distinct_tied_height_fraction"],
        "height_center_GA_distinct_tied_height_fraction": ga["distinct_tied_height_fraction"],
        "height_center_samples_per_direction": samples,
        "height_center_tie_rule": "max_squared_residual_within_unchanged_nearest_floor_set",
        "height_center_is_statistical_profile_only": True,
    }
