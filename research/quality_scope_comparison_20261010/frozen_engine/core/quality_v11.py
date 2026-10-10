#!/usr/bin/env python3
"""Fixed-reference geometric quality v1.1, with explicit unavailability.

No labels, sample-derived normalization, semantic room class, worker identity,
or image-dependent quality parameter is accepted by the scoring functions.
No geometry repair, point sorting, or alternative-reference selection occurs.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
for folder in ('legacy_geometry', 'validity', 'height_revision', 'traditional'):
    sys.path.insert(0, str(ROOT / folder))

from strict_geometry import validate_record
from audit_geometry import area_metrics, intersection_area, own_metrics, boundary_metrics, sym_distance
from geometric_components import spherical_sym_distance
from height_revision import height_components


VERSION = 'geom_quality_research_v1.1.0'


@dataclass(frozen=True)
class Parameters:
    boundary_half_deg: float = 4.0
    direction_half_deg: float = 5.0
    flatness_half_deg: float = 2.0
    intrinsic_max_discount: float = 0.15
    height_relative_half: float = 0.5

    def validate(self):
        for key, value in asdict(self).items():
            if not math.isfinite(float(value)):
                raise ValueError(key + ' must be finite')
            if key == 'intrinsic_max_discount':
                if not 0 <= value < 1:
                    raise ValueError(key + ' must be in [0,1)')
            elif value <= 0:
                raise ValueError(key + ' must be positive')


def scalar_score(iou, top_deg, bottom_deg, direction_deg, flatness_deg,
                 height_error, parameters=None):
    """Same scalar structure and five scales as v1; H is now Hstar."""
    p = parameters or Parameters()
    p.validate()
    args = (iou, top_deg, bottom_deg, direction_deg, flatness_deg, height_error)
    if any(v is None or not math.isfinite(float(v)) for v in args):
        raise ValueError('missing_or_nonfinite_required_feature')
    i, top, bot, dr, fl, he = map(float, args)
    if not -1e-12 <= i <= 1+1e-12 or min(top, bot, dr, fl, he) < 0:
        raise ValueError('feature_out_of_domain')
    i = min(1., max(0., i))  # explicitly bounded floating-point endpoint guard
    boundary = math.hypot(top, bot) / math.sqrt(2)
    dloss = (dr/math.hypot(dr, p.direction_half_deg))**2
    floss = (fl/math.hypot(fl, p.flatness_half_deg))**2
    intrinsic = 1 - p.intrinsic_max_discount*(dloss+floss)/2
    denom = math.hypot(1., boundary/p.boundary_half_deg, he/p.height_relative_half)
    ref_factor = (1/denom)**2
    bfactor = (1/math.hypot(1., boundary/p.boundary_half_deg))**2
    cap = 100*i
    after_b, after_h = cap*bfactor, cap*ref_factor
    q = after_h*intrinsic
    return {'quality_score': q, 'range_ceiling_points': cap,
            'boundary_rms_deg': boundary, 'height_error_used': he,
            'boundary_factor': bfactor, 'reference_factor': ref_factor,
            'direction_bounded_loss': dloss, 'flatness_bounded_loss': floss,
            'intrinsic_factor': intrinsic,
            'range_deduction_points': 100-cap,
            'boundary_deduction_points': cap-after_b,
            'height_deduction_points': after_b-after_h,
            'intrinsic_deduction_points': after_h-q}


def geometry_digest(record):
    """Provenance only; never used for scoring or candidate selection."""
    if not isinstance(record, dict):
        return None
    raw = {k: record.get(k) for k in ('top3d', 'bottom3d', 'points',
           'sourcePointIndices', 'sourcePairIndices', 'sourceExistingRingConnections')}
    try:
        encoded = json.dumps(raw, sort_keys=True, ensure_ascii=False,
                             separators=(',', ':'), allow_nan=True,
                             default=lambda value: value.tolist()).encode()
    except (TypeError, ValueError, AttributeError, OverflowError):
        # Unsupported Python objects are rejected by the geometry validator.
        # An unavailable optional digest must not crash the rejection response.
        return None
    return hashlib.sha256(encoded).hexdigest()


def _plain(value):
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(v) for v in value]
    if hasattr(value, 'tolist'):
        return _plain(value.tolist())
    if hasattr(value, 'item'):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def score_geometry(annotation, reference, parameters=None, *,
                   spherical_samples=2048, height_samples=4096,
                   target_applicability='conditional_geometry',
                   target_inapplicability_reason=None):
    """Score a single *fixed* reference and retain computable 2D information.

    External, evidence-based target/model inapplicability can be passed with
    an explicit reason. OOS/room/category labels are not evaluated here.
    'conditional_geometry' states that measured physical truth is unverified.
    The result keeps geometry validity separate from complete-score status.
    """
    p = parameters or Parameters()
    p.validate()
    va = validate_record(annotation, role='annotation')
    vg = validate_record(reference, role='reference')
    result = {
        'algorithm_version': VERSION, 'status': 'unavailable',
        'quality_score': None, 'reason_codes': [], 'failure_classes': [],
        'annotation_geometry_sha256': geometry_digest(annotation),
        'reference_geometry_sha256': geometry_digest(reference),
        'target_applicability': target_applicability,
        'annotation_validity': va, 'reference_validity': vg,
        'metrics': {}, 'metric_availability': {
            'iou_2d': 'unavailable', 'iou_3d_corner_mean': 'unavailable',
            'iou_3d_perimeter_mean': 'unavailable', 'complete_quality': 'unavailable'},
        'parameters': asdict(p),
        'numerical_settings': {'spherical_samples': spherical_samples,
                               'height_samples': height_samples},
    }
    result['geometry_digest_status'] = {
        role: ('available' if result[role+'_geometry_sha256'] is not None else
               'unavailable_for_missing_or_non_JSON_numeric_input')
        for role in ('annotation', 'reference')}
    issues = [*va['errors'], *vg['errors']]
    m = result['metrics']
    if va['valid_2d'] and vg['valid_2d']:
        try:
            m.update(area_metrics(annotation, reference))
            m['iou_2d'] = m['iou']
            result['metric_availability']['iou_2d'] = 'available'
        except (ValueError, ArithmeticError, FloatingPointError) as exc:
            issues.append({'code': 'area_computation_failed',
                           'category': 'numerical_computation_failed',
                           'message': str(exc), 'component': 'footprint_2d'})
    result['traditional_issues'] = []
    if va['valid_2d'] and vg['valid_2d'] and 'iou' in m:
        try:
            from traditional_metrics import traditional_metrics_detailed
            trad = traditional_metrics_detailed(annotation, reference, intersection_area_fn=intersection_area,
                                       annotation_validation=va, reference_validation=vg)
            m.update(trad)
            m['iou_3d_corner_mean'] = trad['hohonet_iou3d_vertex_mean']
            m['iou_3d_perimeter_mean'] = trad['conditional_iou3d_perimeter_mean']
            result['metric_availability']['iou_3d_corner_mean'] = ('available' if m['iou_3d_corner_mean'] is not None else 'unavailable')
            result['metric_availability']['iou_3d_perimeter_mean'] = ('available' if m['iou_3d_perimeter_mean'] is not None else 'unavailable')
            result['traditional_issues'] = trad['traditional_reason_codes']
        except ImportError:
            raise  # packaging/implementation defect must not masquerade as a bad annotation
        except (ValueError, ArithmeticError, FloatingPointError) as exc:
            result['traditional_issues'].append('traditional_volume_computation_failed:'+str(exc))
    if target_applicability in {'reference_not_applicable', 'model_not_applicable', 'data_missing'}:
        if not target_inapplicability_reason:
            raise ValueError('Explicit target inapplicability requires an evidence-based reason')
        issues.append({'code': target_applicability, 'category': target_applicability,
                       'message': target_inapplicability_reason, 'component': 'target_policy'})
    elif target_applicability != 'conditional_geometry':
        raise ValueError('Unrecognized target_applicability; never infer it from a scene label')
    if va['available'] and vg['available'] and 'iou' in m and not issues:
        try:
            m.update(own_metrics(annotation))
            m['S_top_deg'] = spherical_sym_distance(annotation['top3d'], reference['top3d'], spherical_samples)
            m['S_bottom_deg'] = spherical_sym_distance(annotation['bottom3d'], reference['bottom3d'], spherical_samples)
            hc = height_components(annotation, reference, samples=height_samples)
            m.update({k: v for k, v in hc.items() if not isinstance(v, dict)})
            result['height_diagnostics'] = hc.get('diagnostics', {})
            out = scalar_score(m['iou'], m['S_top_deg'], m['S_bottom_deg'],
                               m['dir'], m['flat'], hc['Hstar'], p)
            m.update(out)
            m['mean_height_only_score_same_parameters'] = scalar_score(m['iou'], m['S_top_deg'], m['S_bottom_deg'],
                                                                      m['dir'], m['flat'], hc['Hmean'], p)['quality_score']
            m['score_v1_recomputed'] = scalar_score(m['iou'], m['S_top_deg'], m['S_bottom_deg'],
                                                   m['dir'], m['flat'], hc['Hmean'], Parameters())['quality_score']
            result['status'] = 'available'
            result['quality_score'] = out['quality_score']
            result['metric_availability']['complete_quality'] = 'available'
        except (ValueError, ArithmeticError, FloatingPointError) as exc:
            issues.append({'code': 'required_quality_component_failed',
                           'category': 'numerical_computation_failed',
                           'message': str(exc), 'component': 'complete_quality'})
    # Auxiliary diagnostics have independent availability. Failure here never
    # changes a completed score, replaces a missing component, or changes Q's weights.
    result['auxiliary_issues'] = []
    if result['status'] == 'available':
        try:
            m.update(boundary_metrics(annotation, reference))
        except (ValueError, ArithmeticError, FloatingPointError) as exc:
            m.update(U=None, B=None)
            result['auxiliary_issues'].append('legacy_UB_failed:'+str(exc))
        for key, ring in [('T', 'top3d'), ('F', 'bottom3d')]:
            try:
                m[key] = sym_distance(annotation[ring], reference[ring])
            except (ValueError, ArithmeticError, FloatingPointError) as exc:
                m[key] = None
                result['auxiliary_issues'].append(key+'_failed:'+str(exc))
    result['issues'] = issues
    result['reason_codes'] = list(dict.fromkeys(x['code'] for x in issues))
    result['failure_classes'] = list(dict.fromkeys(x['category'] for x in issues))
    return _plain(result)


def load_parameters(path):
    data = json.loads(Path(path).read_text())
    return Parameters(**data.get('parameters', data))

