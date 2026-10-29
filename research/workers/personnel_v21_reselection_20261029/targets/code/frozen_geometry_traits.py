"""Frozen repository functions, extracted unchanged at a476461d7ede8db95da43de4139e612c05e618bc.
See FROZEN_FUNCTION_SOURCES.json for original modules and hashes.
"""

import numpy as np

from shapely.geometry import Point, Polygon

EPS = 1e-8

def classify_ring_x(xs):
    x = np.asarray(xs, dtype=float) % 1024
    if x.ndim != 1 or len(x) < 3 or not np.isfinite(x).all():
        raise ValueError('invalid_ring_x')
    monotonic = lambda v: any(np.all(np.diff(np.roll(v, -j)) >= -1e-6) for j in range(len(v)))
    increasing, decreasing = monotonic(x), monotonic(x[::-1])
    kind = 'cyclic_increasing' if increasing else 'cyclic_decreasing' if decreasing else 'local_backtracking'
    delta = (np.roll(x, -1) - x + 512) % 1024 - 512
    direction = 1 if delta.sum() >= 0 else -1
    backward = direction * delta < -1e-6
    ties = [[i + 1, j + 1] for i in range(len(x)) for j in range(i + 1, len(x))
            if abs((x[i] - x[j] + 512) % 1024 - 512) <= 1e-6]
    return dict(x_order_class=kind, same_x_pairs=bool(ties), same_x_pair_indices_1based=ties,
                starts_at_min_x=bool(abs(x[0] - x.min()) <= 1e-6),
                x_sequence=x.tolist(), backward_edge_count=int(backward.sum()),
                backward_angular_degrees=float(-np.sum(direction * delta[backward]) * 360 / 1024),
                backward_edges_1based=[[i + 1, (i + 1) % len(x) + 1]
                                      for i in np.flatnonzero(backward).tolist()])

def cross(a, b):
    return float(a[0] * b[1] - a[1] * b[0])

def visibility_from_floor(floor):
    """相机原点→顶点：横穿非相邻边为遮挡；擦角／沿墙退化情况另列。"""
    xy = np.asarray(floor, dtype=float)
    if xy.ndim != 2 or xy.shape[1] != 2 or len(xy) < 3 or not np.isfinite(xy).all():
        raise ValueError('invalid_floor_array')
    poly = Polygon(xy)
    if not poly.is_valid or poly.area <= 0:
        return dict(status='invalid_polygon', hidden_vertices_1based=None, visibility=[])
    if not poly.contains(Point(0, 0)):
        return dict(status='camera_not_strictly_inside', hidden_vertices_1based=None, visibility=[])
    result = []
    for i, target in enumerate(xy):
        blockers, contacts = [], []
        for j, a in enumerate(xy):
            end = (j + 1) % len(xy)
            if i in (j, end):
                continue
            b = xy[end]
            edge = b - a
            denom = cross(target, edge)
            tolerance = EPS * np.linalg.norm(target) * np.linalg.norm(edge)
            if abs(denom) <= tolerance:
                if abs(cross(a, target)) <= EPS * np.linalg.norm(target) * max(np.linalg.norm(a), 1):
                    lo, hi = sorted([float(a @ target / (target @ target)), float(b @ target / (target @ target))])
                    if hi > EPS and lo < 1 - EPS:
                        contacts.append([j + 1, end + 1])
                continue
            t, s = cross(a, edge) / denom, cross(a, target) / denom
            if EPS < t < 1 - EPS and -EPS <= s <= 1 + EPS:
                if EPS < s < 1 - EPS:
                    blockers.append(dict(edge_1based=[j + 1, end + 1], ray_fraction=t, edge_fraction=s,
                                         intersection_xy=(t * target).tolist()))
                else:
                    contacts.append([j + 1, end + 1])
        blockers.sort(key=lambda z: z['ray_fraction'])
        status = 'occluded_by_boundary' if blockers else 'grazing_or_collinear' if contacts else 'visible_in_floor_model'
        result.append(dict(vertex_1based=i + 1, status=status, blockers=blockers, contacts=contacts))
    return dict(status='valid_camera_inside',
                hidden_vertices_1based=[v['vertex_1based'] for v in result if v['status'] == 'occluded_by_boundary'],
                grazing_vertices_1based=[v['vertex_1based'] for v in result if v['status'] == 'grazing_or_collinear'],
                visibility=result)

def floor_features(floor):
    p = np.asarray(floor, dtype=float)
    vis = visibility_from_floor(p)
    incoming, outgoing = p - np.roll(p, 1, axis=0), np.roll(p, -1, axis=0) - p
    lengths = np.linalg.norm(incoming, axis=1) * np.linalg.norm(outgoing, axis=1)
    assert np.all(lengths > 0), 'zero_length_edge'
    sine = np.abs(incoming[:, 0] * outgoing[:, 1] - incoming[:, 1] * outgoing[:, 0]) / lengths
    straight = np.flatnonzero((sine <= 1e-8) & ((incoming * outgoing).sum(axis=1) > 0))
    order = classify_ring_x((np.arctan2(p[:, 0], -p[:, 1]) / (2 * np.pi) + .5) * 1024)
    return dict(N_floor=len(p), N_turn=len(p)-len(straight),
                straight_vertices_1based=(straight+1).tolist(),
                H=None if vis['hidden_vertices_1based'] is None else len(vis['hidden_vertices_1based']),
                hidden_vertices_1based=vis['hidden_vertices_1based'],
                geometry_status=vis['status'], ring_class=order['x_order_class'])

def reference_traits(floor):
    p=np.asarray(floor,float)
    if len(p)<3 or not np.isfinite(p).all() or not Polygon(p).is_valid:
        return dict(ref_geometry_status='unavailable')
    edges=np.roll(p,-1,axis=0)-p;length=np.linalg.norm(edges,axis=1)
    if np.any(length<=1e-8):return dict(ref_geometry_status='zero_length_edge')
    turn=np.degrees(np.arccos(np.clip((edges*np.roll(edges,1,axis=0)).sum(1)/(length*np.roll(length,1)),-1,1)))
    short=(length/length.sum()<.04)&(turn>=15)&(np.roll(turn,-1)>=15)
    az=np.degrees(np.arctan2(p[:,0],p[:,1]));span=np.abs((np.roll(az,-1)-az+180)%360-180)
    geometry=floor_features(p)
    return dict(ref_geometry_status=geometry['geometry_status'],ref_vertices=len(p),
        ref_turn3=int((turn>3).sum()),ref_turn5=int((turn>5).sum()),ref_turn10=int((turn>10).sum()),
        ref_H=geometry['H'],ref_short_edges=int(short.sum()),
        ref_short_min_horizontal_deg=float(span[short].min()) if short.any() else np.nan,
        ref_min_horizontal_deg=float(span.min()),ref_radius_p90_h=float(np.quantile(np.linalg.norm(p,axis=1),.9)))
