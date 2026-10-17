"""Read-only reconstruction adapter for the simulated annotation review page."""
from __future__ import annotations

import math

from tools.label_studio.panorama_studio.geometry import analyze


def reconstruct_for_review(row, group):
    """Retain source order and separate ray availability from surface validity."""
    result = dict(schema='annotation_review_3d_v1', status='unavailable', issues=[],
                  floor=[], top=[], camera_height=1, coordinate_convention='continuous',
                  order_confirmed=row.get('ring_confirmed') is True,
                  pairing_status=('current_loader_verified' if row.get('pairing_verified') is True else
                                  'assumed_adjacent_unverified' if group == 'human' else 'declared_adjacent'),
                  assumptions=['horizontal_floor', 'ceiling_range_from_paired_floor'])
    points = row.get('points')
    if (not isinstance(points, (list, tuple)) or len(points) < 6 or len(points) % 2
            or any(not isinstance(p, (list, tuple)) or len(p) != 2
                   or any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in p)
                   for p in points)):
        result['issues'] = ['invalid_point_array']
        return result
    payload = dict(width=1024, height=512, coordinate_mode='pixels', ordered_pairs=[
        dict(source_pair_id=str(i // 2), top=dict(zip(('x', 'y'), points[i])),
             bottom=dict(zip(('x', 'y'), points[i + 1]))) for i in range(0, len(points), 2)])
    identities = row.get('source_pair_indices', list(range(len(points) // 2)))
    if identities is None:
        identities = list(range(len(points) // 2))
    if len(identities) != len(points) // 2 or len(set(identities)) != len(identities):
        result['issues'] = ['invalid_source_pair_identity']
        return result
    for pair, identity in zip(payload['ordered_pairs'], identities):
        pair['source_pair_id'] = str(identity)
    try:
        raw = analyze(payload, compute_fit=False, coordinate_convention='continuous')['raw']
    except ValueError as error:
        result['issues'] = [str(error)]
        return result
    result.update(floor=raw['declared_floor'], top=raw['ceiling'],
                  source_pair_indices=identities,
                  polygon_valid=raw['polygon_valid'], camera_relation=raw['camera_relation'],
                  issues=list(raw['issues']),
                  bottom_horizon_margin_deg=raw['bottom_horizon_margin_deg'],
                  top_horizon_margin_deg=raw['top_horizon_margin_deg'])
    if not result['order_confirmed']:
        result['issues'].append('ring_order_unconfirmed')
    if group == 'human' and row.get('pairing_verified') is not True:
        result['issues'].append('adjacent_pairing_unverified')
    if any(p is None for p in result['floor']):
        result['status'] = 'unavailable'
    elif any(p is None for p in result['top']):
        result['status'] = 'floor_only'
    else:
        result['status'] = 'wireframe_warning' if result['issues'] else 'available'
    return result
