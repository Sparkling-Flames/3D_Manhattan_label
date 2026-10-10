#!/usr/bin/env python3
"""Traditional IoU metrics for unchanged, strictly checked frozen geometry.

The 2-D score is the raw XZ footprint IoU. The HoHoNet-compatible 3-D IoU
uses the arithmetic mean of vertex wall heights, exactly the height estimator
in HoHoNet eval_layout.test_general for positive-height canonical inputs.
The older perimeter-weighted conditional-prism IoU is separately named.

This module neither imposes Manhattan/flat ceilings nor repairs geometry.
Invalid/missing inputs return null metric values and concrete reason codes;
it intentionally does not copy the official script's exception-to-zero policy.
It does not implement the official depth/RMSE/delta1 evaluation pipeline.

The caller supplies a polygon intersection function, operating on the same
unmodified, already strictly validated XZ arrays. This avoids silently using
polygon repair in an external geometry package.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import math
import numpy as np

try:
    from strict_geometry import validate_record
except ImportError:
    _path = Path(__file__).resolve().parent.parent / 'validity/strict_geometry.py'
    _spec = importlib.util.spec_from_file_location('_traditional_strict_geometry', _path)
    _strict = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_strict)
    validate_record = _strict.validate_record

VERSION = 'traditional_geometry_iou_v1.1.0'
HOHONET_WIDTH = 1024
HOHONET_HEIGHT = 512
HOHONET_CAMERA_HEIGHT = 1.6


def _wall_heights(record):
    t = np.asarray(record['top3d'], dtype=float)
    b = np.asarray(record['bottom3d'], dtype=float)
    # The canonical floor is y=-1. This expression keeps the official
    # estimator algebra literal, with only the validator's roundoff allowance.
    return t[:, 1] + 1.0, b


def vertex_mean_height_h(record):
    """Corner-count weighted height: the official HoHoNet height convention."""
    heights, _ = _wall_heights(record)
    return float(heights.mean())


def perimeter_mean_height_h(record):
    """Exact line integral along the floor ring of linearly varying height."""
    heights, bottom = _wall_heights(record)
    lengths = np.linalg.norm(np.roll(bottom[:, [0, 2]], -1, axis=0)-bottom[:, [0, 2]], axis=1)
    return float(np.dot(lengths, (heights+np.roll(heights, -1))/2.0)/lengths.sum())


def frozen_to_hohonet_pixels(record):
    """Represent the SAME paired 3-D rays in official 1024x512 pixel centers.

    HoHoNet np_coorx2u/np_coory2v add +0.5 before converting to angles.
    The inverse therefore subtracts 0.5. Simply passing the frozen annotation
    canvas coordinates into the official function changes every ray.
    Pair/ring order and all stored coordinates remain untouched.
    """
    top = np.asarray(record['top3d'], dtype=float)
    bottom = np.asarray(record['bottom3d'], dtype=float)
    if top.shape != bottom.shape or top.ndim != 2 or top.shape[1] != 3:
        raise ValueError('invalid_paired_arrays_for_official_projection')
    radius = np.linalg.norm(bottom[:, [0, 2]], axis=1)
    if np.any(radius == 0):
        raise ValueError('hohonet_pole_pair_height_unidentifiable')
    u = np.arctan2(bottom[:, 0], -bottom[:, 2])
    x = (u/(2*np.pi)+0.5)*HOHONET_WIDTH-0.5
    v_floor = np.arctan2(bottom[:, 1], radius)
    v_top = np.arctan2(top[:, 1], radius)
    y_top = (-v_top/np.pi+0.5)*HOHONET_HEIGHT-0.5
    y_floor = (-v_floor/np.pi+0.5)*HOHONET_HEIGHT-0.5
    corners = np.empty((len(top)*2, 2), dtype=float)
    corners[0::2, 0] = corners[1::2, 0] = x
    corners[0::2, 1], corners[1::2, 1] = y_top, y_floor
    return corners


def prism_iou(area_pred, area_ref, intersection_area, height_pred, height_ref):
    """Common-floor uniform-prism formula; not nonflat polyhedron overlap."""
    v_inter = intersection_area*min(height_pred, height_ref)
    union = area_pred*height_pred+area_ref*height_ref-v_inter
    if not math.isfinite(union) or union <= 0:
        raise ValueError('nonpositive_or_nonfinite_prism_union')
    return float(v_inter/union)


def traditional_metrics_detailed(annotation, reference, *, intersection_area_fn=None, areas=None,
                        annotation_validation=None, reference_validation=None):
    """Return separate traditional metrics and availability, without a Q score.

    intersection_area_fn receives two original [n,2] XZ arrays. It must not
    mutate, repair, snap or relabel them. It may triangulate the same domain.
    Cached strict_geometry validations can be supplied by a caller that has
    just validated these exact unchanged arrays.
    """
    va = annotation_validation or validate_record(annotation, role='annotation')
    vg = reference_validation or validate_record(reference, role='reference')
    result = dict(traditional_metric_version=VERSION, traditional_status='unavailable',
        iou2d_bev=None, hohonet_iou3d_vertex_mean=None, conditional_iou3d_perimeter_mean=None,
        height_vertex_mean_h=None, reference_height_vertex_mean_h=None,
        height_perimeter_mean_h=None, reference_height_perimeter_mean_h=None,
        hohonet_height_pred_at_camera1p6=None, hohonet_height_ref_at_camera1p6=None,
        area_pred_h2=None, area_ref_h2=None, intersection_area_h2=None,
        traditional_reason_codes=[], hohonet_complete_pipeline_run=False)
    reasons = result['traditional_reason_codes']
    if not (va['valid_2d'] and vg['valid_2d']):
        for label, val in [('annotation', va), ('reference', vg)]:
            if not val['valid_2d']:
                reasons.extend(label+':'+e['code'] for e in val['footprint_2d']['errors'])
                if not val['footprint_2d']['errors']:
                    reasons.append(label+':missing_or_invalid_footprint')
        return result

    bottom_a = np.asarray(annotation['bottom3d'], dtype=float)
    bottom_g = np.asarray(reference['bottom3d'], dtype=float)
    pa, pg = bottom_a[:, [0, 2]], bottom_g[:, [0, 2]]
    aa, ag = float(va['footprint_2d']['area_h2']), float(vg['footprint_2d']['area_h2'])
    try:
        if areas is not None:
            ai = float(areas['intersection_area_h2'])
            for actual, supplied in ((aa, areas['area_h2']), (ag, areas['reference_area_h2'])):
                if not math.isclose(actual, float(supplied), rel_tol=1e-10, abs_tol=1e-12):
                    raise ValueError('supplied_area_does_not_match_unchanged_geometry')
        elif intersection_area_fn is not None:
            ai = float(intersection_area_fn(pa, pg))
        else:
            raise ValueError('supply_verified_areas_or_intersection_area_function')
        area_guard = 1024*np.finfo(float).eps*max(1., aa, ag)
        if not math.isfinite(ai) or ai < -area_guard or ai > min(aa, ag)+area_guard:
            raise ValueError('polygon_intersection_outside_area_bounds')
        # Arithmetic endpoint guard only; it never changes source coordinates.
        ai = min(min(aa, ag), max(0., ai))
        iou = ai/(aa+ag-ai)
        result.update(iou2d_bev=float(iou), area_pred_h2=aa, area_ref_h2=ag, intersection_area_h2=ai,
                      traditional_status='partial')
    except (ValueError, ArithmeticError) as exc:
        reasons.append('area_calculation:'+str(exc))
        return result

    if not (va['valid_3d'] and vg['valid_3d']):
        for label, val in [('annotation', va), ('reference', vg)]:
            if not val['valid_3d']:
                reasons.extend(label+':'+e['code'] for e in val['errors']
                               if e['kind'] != 'metric_domain')
        return result

    hm_a, hm_g = vertex_mean_height_h(annotation), vertex_mean_height_h(reference)
    hp_a, hp_g = perimeter_mean_height_h(annotation), perimeter_mean_height_h(reference)
    result.update(height_vertex_mean_h=hm_a, reference_height_vertex_mean_h=hm_g,
        height_perimeter_mean_h=hp_a, reference_height_perimeter_mean_h=hp_g,
        conditional_iou3d_perimeter_mean=prism_iou(aa, ag, ai, hp_a, hp_g))
    # A vertical pair on the camera's pole does not identify a height from the
    # official two ERP rays, even when the source 3-D geometry is well-defined.
    if np.any(np.linalg.norm(pa, axis=1) == 0) or np.any(np.linalg.norm(pg, axis=1) == 0):
        reasons.append('hohonet_pole_pair_height_unidentifiable')
        return result
    result.update(hohonet_iou3d_vertex_mean=prism_iou(aa, ag, ai, hm_a, hm_g),
        hohonet_height_pred_at_camera1p6=HOHONET_CAMERA_HEIGHT*hm_a,
        hohonet_height_ref_at_camera1p6=HOHONET_CAMERA_HEIGHT*hm_g,
        traditional_status='available')
    return result


def traditional_metrics(annotation, reference, *, areas=None, intersection_area_fn=None,
                        annotation_validation=None, reference_validation=None):
    """Flat numeric adapter for the quality pipeline's already-valid 3-D pair.

    For partially evaluable input, use traditional_metrics_detailed instead;
    this adapter raises so a complete metric cannot be silently fabricated.
    ``areas`` keys follow the frozen area_metrics interface: area_h2,
    reference_area_h2, intersection_area_h2.
    """
    r = traditional_metrics_detailed(annotation, reference, areas=areas,
        intersection_area_fn=intersection_area_fn,
        annotation_validation=annotation_validation, reference_validation=reference_validation)
    if r['traditional_status'] != 'available':
        raise ValueError(';'.join(r['traditional_reason_codes']) or 'traditional_metrics_unavailable')
    return dict(iou_2d_traditional=r['iou2d_bev'],
        iou_3d_corner_mean=r['hohonet_iou3d_vertex_mean'],
        iou_3d_perimeter_mean=r['conditional_iou3d_perimeter_mean'],
        annotation_height_corner_mean_h=r['height_vertex_mean_h'],
        reference_height_corner_mean_h=r['reference_height_vertex_mean_h'],
        annotation_height_perimeter_mean_h=r['height_perimeter_mean_h'],
        reference_height_perimeter_mean_h=r['reference_height_perimeter_mean_h'],
        hohonet_assumed_camera_height=HOHONET_CAMERA_HEIGHT,
        hohonet_annotation_height_camera1p6=r['hohonet_height_pred_at_camera1p6'],
        hohonet_reference_height_camera1p6=r['hohonet_height_ref_at_camera1p6'])
