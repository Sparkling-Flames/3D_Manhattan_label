#!/usr/bin/env python3
"""Low-complexity, deterministic components on frozen conditional 3-D rings.

The additional spherical metric compares all declared boundary arcs, including
arcs from azimuthally multivalued rings. It does not infer visibility, pair
vertices, choose a front envelope, or turn missing U/B into observations.
"""
import math
import numpy as np

from audit_geometry import area_metrics, own_metrics, sym_distance


def unit(v):
    v = np.asarray(v, dtype=float)
    norm = np.linalg.norm(v, axis=-1, keepdims=True)
    if np.any(norm < 1e-12):
        raise ValueError("spherical_projection_has_camera_origin")
    return v / norm


def spherical_arc_basis(ring):
    """Unit start, end, tangent, normal and minor-arc lengths of each 3-D edge."""
    a = unit(ring)
    b = np.roll(a, -1, axis=0)
    cross = np.cross(a, b)
    sin_angle = np.linalg.norm(cross, axis=1)
    cos_angle = np.sum(a * b, axis=1)
    theta = np.arctan2(sin_angle, cos_angle)
    if np.any(theta < 1e-12):
        raise ValueError("zero_angular_length_edge")
    if np.any(np.pi - theta < 1e-10):
        raise ValueError("antipodal_or_origin_crossing_edge")
    normal = cross / sin_angle[:, None]
    tangent = np.cross(normal, a)
    return a, b, tangent, normal, theta


def sample_spherical_ring(ring, n=2048):
    a, b, tangent, normal, length = spherical_arc_basis(ring)
    cum = np.r_[0.0, np.cumsum(length)]
    s = (np.arange(n) + 0.5) * cum[-1] / n
    ix = np.searchsorted(cum, s, side="right") - 1
    alpha = s - cum[ix]
    return a[ix] * np.cos(alpha)[:, None] + tangent[ix] * np.sin(alpha)[:, None]


def spherical_point_to_arcs_distance(points, target_ring):
    """Exact angular distance to the union of target minor arcs, in radians.

    The integral is numerical, but each sampled point's nearest-arc distance is
    analytic. atan2 avoids a spurious ~1e-6 degree floor from arccos near 1.
    """
    p = unit(points)
    a, b, tangent, normal, length = spherical_arc_basis(target_ring)
    x = p @ a.T
    y = p @ tangent.T
    normal_projection = p @ normal.T
    phase = np.arctan2(y, x)
    inside = (phase >= -1e-12) & (phase <= length[None, :] + 1e-12)
    arc_distance = np.arctan2(np.abs(normal_projection), np.hypot(x, y))
    end_a = np.arctan2(np.linalg.norm(np.cross(p[:, None, :], a[None, :, :]), axis=-1), x)
    end_b = np.arctan2(
        np.linalg.norm(np.cross(p[:, None, :], b[None, :, :]), axis=-1), p @ b.T
    )
    edge_distance = np.where(inside, arc_distance, np.minimum(end_a, end_b))
    return edge_distance.min(axis=1)


def spherical_directed_distance(source_ring, target_ring, n=2048):
    return float(spherical_point_to_arcs_distance(sample_spherical_ring(source_ring, n), target_ring).mean())


def spherical_sym_distance(a, b, n=2048):
    return math.degrees((spherical_directed_distance(a, b, n) + spherical_directed_distance(b, a, n)) / 2)


def additional_components(a, g, n=2048, base=None):
    """Components only; no quality weights or human rating fit."""
    base = dict(base) if base is not None else {**area_metrics(a, g), **own_metrics(a)}
    if "T" not in base:
        base["T"] = sym_distance(a["top3d"], g["top3d"])
    if "F" not in base:
        base["F"] = sym_distance(a["bottom3d"], g["bottom3d"])
    if "reference_area_h2" not in base:
        base.update(area_metrics(a, g))
    # Use the same floor-perimeter-weighted mean-height definition as the
    # independent audit. It is a conditional height, not measured metres.
    ref_height = own_metrics(g)["height_mean_h"]
    if "height_mean_h" not in base:
        base["height_mean_h"] = own_metrics(a)["height_mean_h"]
    if not math.isfinite(ref_height) or ref_height <= 0:
        raise ValueError("nonpositive_reference_mean_height")
    size = math.sqrt(base["reference_area_h2"])
    top = spherical_sym_distance(a["top3d"], g["top3d"], n)
    bottom = spherical_sym_distance(a["bottom3d"], g["bottom3d"], n)
    base.update(
        reference_size_h=size,
        T_over_sqrt_reference_area=base["T"] / size,
        F_over_sqrt_reference_area=base["F"] / size,
        TF_mean_h=(base["T"] + base["F"]) / 2,
        TF_mean_over_sqrt_reference_area=(base["T"] + base["F"]) / (2 * size),
        S_top_deg=top,
        S_bottom_deg=bottom,
        S_mean_deg=(top + bottom) / 2,
        S_rms_deg=math.hypot(top, bottom) / math.sqrt(2),
        S_max_deg=max(top, bottom),
        reference_height_mean_h=ref_height,
        height_mean_relative_error=abs(base["height_mean_h"] - ref_height) / ref_height,
        spherical_samples_per_direction=n,
    )
    return base
