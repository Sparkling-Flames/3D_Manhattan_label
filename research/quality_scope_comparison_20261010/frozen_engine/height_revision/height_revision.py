#!/usr/bin/env python3
"""Small height-error candidates, independent of grades and image identities.

The moments are exact integrals of linearly interpolated heights weighted by
floor perimeter.  The optional spatial candidate is an explicitly numerical
integral, with exact nearest-point projection onto each finite target floor
segment. Neither routine repairs geometry; callers must validate rings first.
"""
import math
import numpy as np


def height_moments(record):
    b = np.asarray(record['bottom3d'], dtype=float)
    t = np.asarray(record['top3d'], dtype=float)
    if b.shape != t.shape or b.ndim != 2 or b.shape[1] != 3 or len(b) < 3:
        raise ValueError('height_input_requires_paired_rings')
    if not np.isfinite(b).all() or not np.isfinite(t).all():
        raise ValueError('height_input_nonfinite')
    ell = np.linalg.norm(np.roll(b[:, [0, 2]], -1, axis=0) - b[:, [0, 2]], axis=1)
    if np.any(ell <= 0):
        raise ValueError('height_input_zero_floor_edge')
    height = t[:, 1] - b[:, 1]
    if np.any(height <= 0):
        raise ValueError('height_input_nonpositive_wall_height')
    nxt = np.roll(height, -1)
    perimeter = float(ell.sum())
    mean = float(np.dot(ell, (height + nxt) / 2) / perimeter)
    centered = height - mean
    centered_nxt = np.roll(centered, -1)
    variance = float(np.dot(ell, (centered**2 + centered*centered_nxt + centered_nxt**2)/3) / perimeter)
    return dict(height_mean_h=mean, height_std_h=math.sqrt(max(0.0, variance)),
                height_variance_h2=max(0.0, variance), floor_perimeter_h=perimeter,
                height_min_h=float(height.min()), height_max_h=float(height.max()))


def rms_about_level(record, level):
    """Independent direct centered-square expression, exact on every edge."""
    b = np.asarray(record['bottom3d'], dtype=float)
    t = np.asarray(record['top3d'], dtype=float)
    ell = np.linalg.norm(np.roll(b[:, [0, 2]], -1, axis=0) - b[:, [0, 2]], axis=1)
    d = t[:, 1] - b[:, 1] - float(level)
    dn = np.roll(d, -1)
    return math.sqrt(float(np.dot(ell, (d*d+d*dn+dn*dn)/3)/ell.sum()))


def floor_samples_with_height(record, n=4096, origin_xz=None):
    if not isinstance(n, int) or n < 1:
        raise ValueError('height_sample_count_must_be_positive_integer')
    b = np.asarray(record['bottom3d'], dtype=float)
    t = np.asarray(record['top3d'], dtype=float)
    q = b[:, [0, 2]]
    if origin_xz is not None:
        # A temporary shared computational frame prevents loss of precision
        # when a valid pair is far from the coordinate origin. It does not
        # change any source array or its geometric coordinates.
        q = q - np.asarray(origin_xz,dtype=float)
    edge = np.roll(q, -1, axis=0) - q
    ell = np.linalg.norm(edge, axis=1)
    if np.any(ell <= 0):
        raise ValueError('height_input_zero_floor_edge')
    cum = np.r_[0.0, np.cumsum(ell)]
    s = (np.arange(n) + 0.5) * cum[-1] / n
    index = np.searchsorted(cum, s, side='right') - 1
    u = (s - cum[index]) / ell[index]
    h = t[:, 1] - b[:, 1]
    return q[index] + u[:, None]*edge[index], h[index] + u*(np.roll(h, -1)[index]-h[index])


def directed_nearest_footprint_height_mse(source, target, n=4096, tie_rule='max'):
    """Perimeter mean of vertical residual at nearest target floor point.

    With multiple equidistant closest floor points, take the largest vertical
    residual. This conservative tie convention avoids vertex-order dependence;
    the fraction of samples with genuinely distinct tied target heights is
    returned explicitly. It does not establish semantic wall correspondence.
    """
    # The closest-floor operation is invariant to a common XZ translation.
    # Work in a shared local frame BEFORE constructing sample coordinates;
    # otherwise q+u*edge at coordinates 1e8 can lose local precision and a
    # tolerance based on those global coordinates can treat all edges as ties.
    source_b = np.asarray(source['bottom3d'],dtype=float)
    origin = source_b[0,[0,2]].copy()
    x, source_h = floor_samples_with_height(source, n, origin_xz=origin)
    b = np.asarray(target['bottom3d'], dtype=float)
    t = np.asarray(target['top3d'], dtype=float)
    q = b[:, [0, 2]] - origin
    e = np.roll(q, -1, axis=0) - q
    e2 = np.sum(e*e, axis=1)
    if np.any(e2 <= 0):
        raise ValueError('height_input_zero_floor_edge')
    vec = x[:, None, :] - q[None, :, :]
    u = np.clip(np.sum(vec*e[None, :, :], axis=2)/e2[None, :], 0, 1)
    distance2 = np.sum((vec-u[:, :, None]*e[None, :, :])**2, axis=2)
    min_distance2 = distance2.min(axis=1)
    # Floating arithmetic tolerance, not a geometric acceptance threshold.
    # Based on LOCAL represented coordinate magnitude after a common origin
    # subtraction. No source/target coordinates are snapped or modified.
    roundoff = 64*np.finfo(float).eps*max(1.0, float(np.abs(x).max())**2, float(np.abs(q).max())**2)
    tie = distance2 <= min_distance2[:, None] + roundoff
    target_h = t[:, 1]-b[:, 1]
    matched_h = target_h[None, :] + u*(np.roll(target_h, -1)-target_h)[None, :]
    residual2 = (source_h[:, None]-matched_h)**2
    if tie_rule == 'max':
        selected = np.max(np.where(tie, residual2, -np.inf), axis=1)
    elif tie_rule == 'min':
        selected = np.min(np.where(tie, residual2, np.inf), axis=1)
    else:
        raise ValueError('height_nearest_tie_rule_must_be_min_or_max')
    smallest_h = np.min(np.where(tie, matched_h, np.inf), axis=1)
    largest_h = np.max(np.where(tie, matched_h, -np.inf), axis=1)
    ambiguous = (largest_h-smallest_h) > 1e-10
    return dict(mse_h2=float(selected.mean()),
                distinct_tied_height_fraction=float(ambiguous.mean()),
                max_distinct_tied_height_range_h=float((largest_h-smallest_h).max()),
                footprint_distance_mean_h=float(np.sqrt(min_distance2).mean()),
                arithmetic_tie_tolerance_h2=float(roundoff))


def height_candidates(annotation, reference, samples=4096, include_spatial=True, tie_rule='max'):
    a = height_moments(annotation)
    g = height_moments(reference)
    mu = g['height_mean_h']
    delta = a['height_mean_h']-mu
    std_a = a['height_std_h']
    std_g = g['height_std_h']
    out = dict(annotation_height_mean_h=a['height_mean_h'],
               reference_height_mean_h=mu,
               annotation_height_std_h=std_a,
               reference_height_std_h=std_g,
               annotation_height_min_h=a['height_min_h'],
               annotation_height_max_h=a['height_max_h'],
               H_v1_mean=abs(delta)/mu,
               H_rms_about_gt_mean=math.hypot(delta, std_a)/mu,
               H_max_mean_std=max(abs(delta), std_a)/mu,
               H_mean_std_distance=math.hypot(delta, std_a-std_g)/mu,
               H_excess_std=math.hypot(delta, max(0.0, std_a-std_g))/mu,
               direct_rms_about_gt_mean_check=rms_about_level(annotation, mu)/mu)
    if include_spatial:
        ag = directed_nearest_footprint_height_mse(annotation, reference, samples, tie_rule)
        ga = directed_nearest_footprint_height_mse(reference, annotation, samples, tie_rule)
        out.update(H_nearest_footprint=math.sqrt((ag['mse_h2']+ga['mse_h2'])/2)/mu,
                   height_nearest_samples_per_direction=samples,
                   nearest_AG_tied_height_fraction=ag['distinct_tied_height_fraction'],
                   nearest_GA_tied_height_fraction=ga['distinct_tied_height_fraction'],
                   nearest_AG_tied_height_range_h=ag['max_distinct_tied_height_range_h'],
                   nearest_GA_tied_height_range_h=ga['max_distinct_tied_height_range_h'],
                   nearest_footprint_tie_rule=tie_rule)
        # Retains the v1 global mean-height guarantee when a changed footprint
        # causes the two directional height integrals to weight walls differently.
        out['H_mean_nearest_max'] = max(out['H_v1_mean'], out['H_nearest_footprint'])
    return out


def height_components(annotation, reference, samples=4096):
    """Recommended v1.1 component API, requiring already-validated geometry.

    Hmean preserves the v1 mean-height guard. Hlocal measures paired vertical
    discrepancy via a symmetric nearest-floor projection. Hstar is their max,
    with no new fitted scale or weighting parameter. The numerical sample
    count is a documented integration setting, not a subjective tolerance.
    """
    c = height_candidates(annotation, reference, samples=samples)
    return dict(Hmean=c['H_v1_mean'], Hlocal=c['H_nearest_footprint'],
                Hstar=c['H_mean_nearest_max'],
                height_mean_relative_error=c['H_v1_mean'],
                height_local_relative_rms=c['H_nearest_footprint'],
                height_guard_relative_error=c['H_mean_nearest_max'],
                diagnostics={k:v for k,v in c.items() if not k.startswith('H_')})


def score_from_components(row, height_key, height_scale=0.5):
    """Same five-parameter v1 structure; replace the named H component only."""
    values = [float(row[k]) for k in ['iou','S_top_deg','S_bottom_deg','dir','flat',height_key]]
    if not all(math.isfinite(x) for x in values):
        raise ValueError('required_component_nonfinite')
    i, top, bottom, direction, flat, h = values
    if not -1e-12 <= i <= 1+1e-12 or min(top,bottom,direction,flat,h)<0:
        raise ValueError('required_component_out_of_range')
    i = min(1.0,max(0.0,i))
    intrinsic = 1 - 0.075*((direction/math.hypot(direction,5))**2 + (flat/math.hypot(flat,2))**2)
    return 100*i*intrinsic/(1+(top*top+bottom*bottom)/32+(h/height_scale)**2)


HEIGHT_KEYS = ['H_v1_mean','H_rms_about_gt_mean','H_max_mean_std',
               'H_mean_std_distance','H_excess_std','H_nearest_footprint',
               'H_mean_nearest_max']
