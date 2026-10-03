"""直接ERP墙带多数投票的小型对照；输出稠密轮廓，不宣称恢复物理角点。

输入点为continuous 1024×512上下点对，原环保持。仅支持各环按经度
单向绕行一周、每列唯一上下边且共同跨地平线的表示；其他情况明确unsupported。
不消费GT或BEV，不取最近墙/外包络、不重排点、不静默移除人员。
"""
from __future__ import annotations

import numpy as np

from tools.label_studio.panorama_studio.geometry import pixel_ray

WIDTH, HEIGHT = 1024., 512.


def annotation_band(record, *, samples=512):
    """按原环边两端射线所在平面，在共同列中心精确采样投影曲线。"""
    if not isinstance(samples, int) or samples < 2:
        raise ValueError('samples_must_be_integer_at_least_two')

    def unsupported(reason):
        return dict(status='unsupported', id=record.get('id'), worker=record.get('worker'), reason=reason)

    points = np.asarray(record['points'], dtype=float)
    if (points.ndim != 2 or points.shape[1] != 2 or len(points) < 6 or len(points) % 2
            or not np.isfinite(points).all()):
        return unsupported('invalid_finite_paired_points')
    pairs = points.reshape(-1, 2, 2)
    if np.any(points[:, 0] < 0) or np.any(points[:, 0] > WIDTH):
        return unsupported('coordinates_outside_continuous_canvas')
    if np.any(abs((pairs[:,0,0]-pairs[:,1,0]+WIDTH/2)%WIDTH-WIDTH/2) > 1e-8):
        return unsupported('top_bottom_not_shared_longitude')
    if (np.any(pairs[:,0,1] <= 0) or np.any(pairs[:,0,1] >= HEIGHT/2)
            or np.any(pairs[:,1,1] <= HEIGHT/2) or np.any(pairs[:,1,1] >= HEIGHT)):
        return unsupported('boundaries_must_strictly_straddle_horizon_away_from_poles')
    longitude = pairs[:,1,0] % WIDTH
    delta = (np.roll(longitude,-1)-longitude+WIDTH/2)%WIDTH-WIDTH/2
    if np.any(abs(delta) < 1e-8) or np.any(abs(delta) >= WIDTH/2-1e-8):
        return unsupported('zero_or_half_circle_edge_longitude_span')
    if not (np.all(delta > 0) or np.all(delta < 0)) or abs(abs(delta.sum())-WIDTH) > 1e-7:
        return unsupported('original_ring_not_single_valued_one_turn')
    direction = 1 if delta[0] > 0 else -1
    x = (np.arange(samples)+.5)*WIDTH/samples
    theta = 2*np.pi*(x/WIDTH-.5)
    horizontal = np.c_[np.sin(theta), -np.cos(theta)]
    coverage = np.zeros(samples, dtype=int)
    boundaries = np.full((2, samples), np.nan)
    rays = [[pixel_ray(*pair[side], int(WIDTH), int(HEIGHT), coordinate_convention='continuous')
             for pair in pairs] for side in (0, 1)]
    for i, span in enumerate(delta):
        progress = (direction*(x-longitude[i])) % WIDTH
        # Only stabilize machine-level endpoint equality; no interpolation across missing branches.
        progress[np.isclose(progress, WIDTH, rtol=0, atol=1e-8)] = 0.
        at_end = np.isclose(progress, abs(span), rtol=0, atol=1e-8)
        active = (progress < abs(span)) & ~at_end
        coverage[active] += 1
        for side in (0, 1):
            normal = np.cross(rays[side][i], rays[side][(i+1)%len(pairs)])
            if abs(normal[1]) < 1e-12:
                return unsupported('singular_projected_edge_plane')
            tan_elevation = -(horizontal[active] @ normal[[0,2]]) / normal[1]
            boundaries[side, active] = HEIGHT*(.5-np.arctan(tan_elevation)/np.pi)
    if np.any(coverage != 1) or not np.isfinite(boundaries).all():
        return unsupported('missing_or_multiple_column_branches')
    if np.any(boundaries[0] >= HEIGHT/2) or np.any(boundaries[1] <= HEIGHT/2):
        return unsupported('projected_boundaries_do_not_straddle_horizon')
    return dict(status='ok', id=record.get('id'), worker=record.get('worker'), samples=samples,
                x=x.tolist(), top=boundaries[0].tolist(), bottom=boundaries[1].tolist(),
                source_order='unchanged', winding_direction=direction)


def aggregate_records(records, *, samples=512):
    """当前k人输入→两规则稠密C坐标；任何不适用成员使整组unsupported。"""
    if not records:
        raise ValueError('empty_roster')
    for key in ('id', 'worker'):
        if any(not r.get(key) for r in records) or len({r[key] for r in records}) != len(records):
            raise ValueError('missing_or_duplicate_' + key)
    bands = [annotation_band(r, samples=samples) for r in records]
    unavailable = [dict(id=b['id'], worker=b['worker'], reason=b['reason'])
                   for b in bands if b['status'] != 'ok']
    result = dict(status='unsupported' if unavailable else 'ok', n=len(records), samples=samples,
                  record_ids=[r['id'] for r in records], unsupported=unavailable, methods={},
                  coordinate_frame='continuous 1024x512; samples at column centres',
                  representation='periodic ERP wall-band region; dense contours, not recovered layout corners')
    if unavailable:
        return result
    x = np.array(bands[0]['x'])
    top, bottom = [np.array([b[key] for b in bands]) for key in ('top','bottom')]
    sorted_top, sorted_bottom = np.sort(top, axis=0), np.sort(bottom, axis=0)
    n = len(records)
    for method, threshold in [('mv50', (n+1)//2), ('mv_strict', n//2+1)]:
        upper, lower = sorted_top[threshold-1], sorted_bottom[n-threshold]
        result['methods'][method] = dict(threshold=threshold,
            top_points=np.c_[x,upper].tolist(), bottom_points=np.c_[x,lower].tolist(),
            top_support=np.count_nonzero(top<=upper,axis=0).tolist(),
            bottom_support=np.count_nonzero(bottom>=lower,axis=0).tolist())
    return result
