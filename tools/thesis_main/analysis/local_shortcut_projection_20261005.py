"""Local shortcut diagnostics at a removed pair's longitude; no GT or ring sorting.

Each measurement compares the proposed 3D chord with its removed observation at
one longitude only. It is neither a maximum curve error nor a visible silhouette.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

import numpy as np

from tools.thesis_main.analysis.layout_reliability_20261005.arc_consensus import (
    paired_wall_proxy, pairs, project, W, TAU,
)

ARCHIVE = Path(__file__).resolve().parents[3]/'research/layout_reliability_20261005/pro_original'
# Fixed mechanism panel, matching the five-source deletion pilot.
SELECTION = {'rPc6DW4iMge-06': ['R00020', 'R01518', 'R01557'],
             'uNb9QFRL6hY-67': ['R02928', 'R02929']}

NUMERIC_TOL = 1e-10  # Floating-point intersection classification, not a matching tolerance.


def segment_at_longitude(start, end, x):
    """Intersect a finite 3D segment with the positive horizontal ray at ERP x."""
    a, b = np.asarray(start, float), np.asarray(end, float)
    if a.shape != (3,) or b.shape != (3,) or not np.isfinite(np.r_[a, b, x]).all():
        raise ValueError('finite_3d_endpoints_and_longitude_required')
    edge = b-a
    scale = max(1., float(np.linalg.norm(a)), float(np.linalg.norm(b)))
    if np.linalg.norm(edge) <= NUMERIC_TOL*scale:
        return dict(status='degenerate', reason='zero_or_numerically_zero_length')
    ah, bh, eh = a[[0, 2]], b[[0, 2]], edge[[0, 2]]
    u = TAU*(float(x)/W-.5)
    ray = np.array([np.sin(u), -np.cos(u)])
    matrix = np.column_stack((ray, -eh))
    if abs(np.linalg.det(matrix)) <= NUMERIC_TOL*max(1., float(np.linalg.norm(eh))):
        # A whole radial interval is not a unique intersection, even if some
        # points on it happen to share the same projected elevation.
        if abs(ray[0]*ah[1]-ray[1]*ah[0]) > NUMERIC_TOL*scale:
            return dict(status='not_covered', reason='parallel_offset_segment')
        depths = np.array([ray@ah, ray@bh])
        if max(np.linalg.norm(ah), np.linalg.norm(bh)) <= NUMERIC_TOL*scale:
            return dict(status='degenerate', reason='longitude_undefined_on_vertical_axis')
        if np.max(depths) <= NUMERIC_TOL*scale:
            return dict(status='not_covered', reason='no_positive_horizontal_depth')
        return dict(status='non_unique', reason='collinear_positive_ray_interval')
    depth, t = np.linalg.solve(matrix, ah)
    if depth <= NUMERIC_TOL*scale or t < -NUMERIC_TOL or t > 1.+NUMERIC_TOL:
        return dict(status='not_covered', reason='ray_intersection_outside_positive_finite_segment')
    t = float(np.clip(t, 0., 1.))
    point = a+t*edge
    pixel = project(point)
    return dict(status='ok', segment_parameter=t, horizontal_depth_h=float(depth),
                point_3d_h=point.tolist(), projected_xy_px=pixel.tolist())


def diagnose_shortcut(record, index):
    q = pairs(record); n = len(q)
    if n < 4 or type(index) is not int or not 0 <= index < n:
        raise ValueError('deletion_requires_at_least_four_pairs_and_valid_index')
    top, bottom = paired_wall_proxy(record)
    prev, nxt = (index-1)%n, (index+1)%n
    result = dict(source_record=record['id'], removed_pair_index=index,
                  removed_source_pair_index=record['source_pair_indices'][index],
                  shortcut_source_pair_indices=[record['source_pair_indices'][i] for i in (prev, nxt)],
                  removed_longitude_x_px=float(q[index, 0, 0]),
                  measurement='new_chord_minus_removed_point_at_removed_longitude_only')
    for side, points, j in [('top', top, 0), ('bottom', bottom, 1)]:
        hit = segment_at_longitude(points[prev], points[nxt], q[index, j, 0])
        hit['removed_y_px'] = float(q[index, j, 1])
        hit['signed_dy_px'] = (float(hit['projected_xy_px'][1]-q[index, j, 1])
                               if hit['status']=='ok' else None)
        hit['abs_dy_px'] = abs(hit['signed_dy_px']) if hit['status']=='ok' else None
        result[side] = hit
    return result


def run(out):
    rows = []
    for image, ids in SELECTION.items():
        roster = json.loads((ARCHIVE/'inputs'/f'{image}.json').read_text(encoding='utf-8'))['records']
        for rid in ids:
            record = next(r for r in roster if r['id']==rid)
            # Keep every local operation, including those whose complete new
            # polygon is invalid; local projection does not certify that polygon.
            for index in range(len(record['points'])//2):
                row = diagnose_shortcut(record, index)
                row['image'] = image
                rows.append(row)
    assert len(rows)==51
    result = dict(schema='local_shortcut_projection_v1', candidates=rows,
                  status_counts={s:dict(Counter(r[s]['status'] for r in rows)) for s in ('top', 'bottom')},
                  gt_read=False, source_mutation=False, numeric_intersection_tolerance=NUMERIC_TOL,
                  coordinate_convention='continuous_1024x512',
                  limitations=['one longitude only, not maximum curve error',
                               'same-longitude local path comparison, not visibility or semantic identity',
                               'top uses the existing floor-depth wall proxy',
                               'no whole-ring single-valued condition or candidate-validity filter',
                               'non-unique and uncovered intersections retain null discrepancies'])
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    (out/'results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n',
                                   encoding='utf-8', newline='\n')
    return result


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    result = run(parser.parse_args().out)
    print(json.dumps(dict(candidates=len(result['candidates']), status_counts=result['status_counts'])))
