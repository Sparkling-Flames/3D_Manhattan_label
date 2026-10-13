"""Length-supported direction descriptors and a jointly optimized hinge metric.

All angles are degrees.  Lengths are in camera-height units, while weights sum
to one.  Descriptors on the unchanged L2 axis can jump when that optimal axis
switches.  The jointly minimized hinge loss is continuous; its chosen axis can
still switch.  This module never chooses a reference and never changes a ring.
"""
from __future__ import annotations
import math
import numpy as np


def direction_descriptors(points, thresholds=(2., 5., 10., 15., 20.)):
    p = np.asarray(points, dtype=float)
    if p.ndim != 2 or p.shape[1] not in (2, 3) or len(p) < 3:
        raise ValueError('at_least_three_ordered_2d_or_3d_points_required')
    if p.shape[1] == 3:
        p = p[:, [0, 2]]
    if not np.isfinite(p).all():
        raise ValueError('nonfinite_floor_coordinate')
    edges = np.roll(p, -1, axis=0) - p
    lengths = np.linalg.norm(edges, axis=1)
    if np.any(lengths <= 1e-12):
        raise ValueError('zero_length_edge_no_repair')
    weights = lengths / lengths.sum()
    theta = np.degrees(np.arctan2(edges[:, 1], edges[:, 0]))

    def signed_residual(axis):
        return (theta - axis + 45.) % 90. - 45.

    def objective(axis):
        return float(np.dot(weights, signed_residual(axis) ** 2))

    # Exact piecewise-quadratic global minimization, same definition as the
    # frozen engine's radians implementation.  Axis ties are made explicit.
    cuts = np.unique(np.r_[0., (theta + 45.) % 90., 90.])
    candidates = list(cuts)
    for lo, hi in zip(cuts[:-1], cuts[1:]):
        mid = (lo + hi) / 2
        optimum = mid + float(np.dot(weights, signed_residual(mid)))
        if lo <= optimum <= hi:
            candidates.append(optimum)
    values = np.array([objective(x) for x in candidates])
    minimum = float(values.min())
    tied = sorted(set(float(candidates[i] % 90.) for i in range(len(candidates))
                      if abs(values[i] - minimum) <= 1e-10))
    axis = tied[0]
    signed = signed_residual(axis)
    residual = np.abs(signed)
    moments = {f'p{p}': float(np.dot(weights, residual ** p)) for p in (1, 2, 3, 4, 5, 6)}
    excess = {}
    for threshold in thresholds:
        above = np.maximum(residual - threshold, 0.)
        key = f'{threshold:g}'
        excess[key] = {
            'threshold_deg': float(threshold),
            'fraction_above': float(weights[residual > threshold].sum()),
            'positive_part_mean_deg': float(np.dot(weights, above)),
            'positive_part_m2_deg2': float(np.dot(weights, above ** 2)),
            'positive_part_m4_deg4': float(np.dot(weights, above ** 4)),
            'normalized_excess_p2': float(np.dot(weights, (above / threshold) ** 2)),
            'normalized_excess_p4': float(np.dot(weights, (above / threshold) ** 4)),
        }
    tied_descriptors = []
    for ax in tied:
        r = np.abs(signed_residual(ax))
        tied_descriptors.append({'axis_deg': ax,
                                 'weighted_abs_moment_p4_deg4': float(np.dot(weights, r ** 4))})
    return {
        'status': 'available', 'D_rms_deg': math.sqrt(max(0., minimum)),
        'axis_deg': axis, 'axis_tie_count': len(tied),
        'axis_tie_candidates': tied_descriptors,
        'edge_direction_deg': theta.tolist(), 'signed_residual_deg': signed.tolist(),
        'abs_residual_deg': residual.tolist(), 'edge_length_h': lengths.tolist(),
        'length_weight': weights.tolist(), 'perimeter_h': float(lengths.sum()),
        'Dmax_deg': float(residual.max()), 'weighted_abs_moments_deg_power': moments,
        'excess_by_threshold_deg': excess,
        'descriptor_axis': 'annotation_optimized_common_orthogonal_L2_axes',
        'reference_independent': True,
    }


def raw_vertical_alignment(source_layer):
    """Raw pair longitude gap, retaining the local X = 2 Pro E convention."""
    points = np.asarray(source_layer['before_preprocessing_points'], dtype=float)
    links = np.asarray(source_layer['links_zero_based'], dtype=int)
    if points.ndim != 2 or points.shape[1] != 2 or links.ndim != 2 or links.shape[1] != 2:
        raise ValueError('raw_points_or_explicit_links_malformed')
    if not np.isfinite(points).all() or links.min() < 0 or links.max() >= len(points):
        raise ValueError('raw_points_or_links_out_of_domain')
    delta_px = (points[links[:, 0], 0] - points[links[:, 1], 0] + 512.) % 1024. - 512.
    delta_deg = delta_px * 360. / 1024.
    x = float(np.sqrt(np.mean(delta_deg ** 2)))
    return {'status': 'available', 'X_rms_deg': x, 'Eperp_deg': x / 2.,
            'max_pair_gap_deg': float(np.max(np.abs(delta_deg))),
            'signed_pair_gap_deg': delta_deg.tolist(),
            'coordinate_frame': 'source_before_preprocessing_1024x512',
            'pair_basis': 'source_explicit_links_no_repair',
            'definition': 'X_rms_deg=RMS(wrapped_top_bottom_longitude_gap); Eperp_deg=X_rms_deg/2'}


def tail_loss(descriptor, threshold_deg, scale_deg, power):
    if scale_deg <= 0 or threshold_deg < 0 or power <= 0:
        raise ValueError('invalid_tail_parameters')
    r = np.asarray(descriptor['abs_residual_deg'], float)
    w = np.asarray(descriptor['length_weight'], float)
    return float(np.dot(w, (np.maximum(r-threshold_deg, 0.)/scale_deg) ** power))


def jointly_optimized_hinge(descriptor, threshold_deg=10., excess_weight=2.):
    """Exact min_axis E[r^2 + gamma*(|r|-threshold)_+^2], in degrees^2.

    Unlike evaluating a different loss on an L2-selected axis, its minimized
    value is continuous at axis switches.  This is a separate direction metric:
    its chosen axis need not equal the original D axis.  Gamma is dimensionless.
    """
    if not (0 <= threshold_deg < 45) or excess_weight < 0:
        raise ValueError('invalid_joint_hinge_parameters')
    theta=np.asarray(descriptor['edge_direction_deg'],float)
    w=np.asarray(descriptor['length_weight'],float)
    def residual(axis):return (theta-axis+45.)%90.-45.
    def value(axis):
        r=residual(axis)
        return float(np.dot(w,r*r+excess_weight*np.maximum(abs(r)-threshold_deg,0.)**2))
    cuts=np.unique(np.r_[0.,90.,(theta+45)%90.,(theta-threshold_deg)%90.,(theta+threshold_deg)%90.])
    candidates=list(cuts)
    for lo,hi in zip(cuts[:-1],cuts[1:]):
        mid=(lo+hi)/2;r=residual(mid);active=abs(r)>threshold_deg
        coeff=1.+excess_weight*active
        numerator=np.dot(w,coeff*(r+mid)-excess_weight*active*np.sign(r)*threshold_deg)
        optimum=float(numerator/np.dot(w,coeff))
        if lo<=optimum<=hi:candidates.append(optimum)
    best=min(candidates,key=value)
    return {'optimized_axis_deg':float(best%90.),'value_deg2':value(best),
        'threshold_deg':float(threshold_deg),'excess_weight':float(excess_weight),
        'L2_selected_axis_value_deg2':value(descriptor['axis_deg']),
        'definition':'min_axis sum(length_weight*(residual_deg^2+gamma*max(abs(residual_deg)-threshold_deg,0)^2))'}
