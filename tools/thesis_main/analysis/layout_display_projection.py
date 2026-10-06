"""Display-only continuous-ERP projection of stored layout geometry.

Projection samples and SVG rounding are for display, not metric computation.
No fusion, observer selection, fitting or reference scoring is performed here.
"""
from __future__ import annotations

import numpy as np

from tools.label_studio.panorama_studio.geometry import pixel_ray, project_pixel


def projected_edge(a, b):
    """沿Studio既有3D直边投影采样；增加精确接缝端点，禁止跨全图连线。"""
    a, b = np.asarray(a, float), np.asarray(b, float)
    cuts = [0., 1.]
    if a[0] != b[0]:
        t = -a[0]/(b[0]-a[0])
        if 0 < t < 1 and (a+t*(b-a))[2] > 0:
            cuts.insert(1, float(t))
    paths = []
    for lo, hi in zip(cuts, cuts[1:]):
        xyz = a+(b-a)*np.linspace(lo,hi,65)[:,None]
        p = np.array([project_pixel(v,1024,512,coordinate_convention='continuous') for v in xyz])
        for edge, inner in ((0,1),(-1,-2)):
            if abs(xyz[edge,0]) < 1e-12 and xyz[edge,2] > 0:
                p[edge,0] = 1024. if p[inner,0] > 512 else 0.
        split = np.flatnonzero(abs(np.diff(p[:,0])) > 512)+1
        paths.extend(piece.tolist() for piece in np.split(p,split) if len(piece)>1)
    return paths


def region_projection(geometry):
    """所有区域外环、孔洞与断片的地面几何边；不化为可见包络，不推测上边。"""
    if geometry['type'] == 'Polygon':
        polygons = [geometry['coordinates']]
    elif geometry['type'] == 'MultiPolygon':
        polygons = geometry['coordinates']
    elif geometry['type'] == 'GeometryCollection' and not geometry['geometries']:
        return []
    else:
        raise ValueError('unexpected_consensus_geometry_type')
    result = []
    for component, polygon in enumerate(polygons):
        for ring_index, ring in enumerate(polygon):
            xyz = [[x,-1.,z] for x,z in ring]
            result.append(dict(component=component, hole=ring_index>0,
                vertices=[project_pixel(p,1024,512,coordinate_convention='continuous') for p in xyz],
                paths=[path for a,b in zip(xyz,xyz[1:]) for path in projected_edge(a,b)]))
    return result


def annotation_projection(record):
    points = np.asarray(record['points'], float)
    if points.ndim != 2 or points.shape[1] != 2 or len(points)%2 or not np.isfinite(points).all():
        raise ValueError('invalid_annotation_points')
    pairs=points.reshape(-1,2,2); floor=[]; top=[]
    for ceiling, bottom in pairs:
        ray=pixel_ray(*bottom,1024,512,coordinate_convention='continuous')
        if ray[1] >= 0: raise ValueError('floor_not_below_horizon')
        f=-ray/ray[1]; floor.append(f)
        rt=pixel_ray(*ceiling,1024,512,coordinate_convention='continuous')
        horizontal=np.linalg.norm(rt[[0,2]])
        if horizontal<=1e-12: raise ValueError('top_proxy_unavailable_at_pole')
        top.append(rt*np.linalg.norm(f[[0,2]])/horizontal)
    expected=np.asarray(record['footprint'],float)
    if len(expected)==len(floor)+1 and np.array_equal(expected[0],expected[-1]): expected=expected[:-1]
    if expected.shape!=(len(floor),2): raise ValueError('pair_and_footprint_count_mismatch')
    footprint_error=float(np.max(abs(np.asarray(floor)[:,[0,2]]-expected)))
    if footprint_error>1e-10: raise ValueError('display_and_frozen_footprint_mismatch')
    back=np.array([project_pixel(p,1024,512,coordinate_convention='continuous') for p in floor])
    delta=back-pairs[:,1];delta[:,0]=(delta[:,0]+512)%1024-512
    return dict(points=record['points'], source_point_indices=record.get('source_point_indices'),
        source_pair_indices=record.get('source_pair_indices'), source_point_labels=record.get('source_point_labels'),
        footprint_max_error_h=footprint_error, floor_roundtrip_max_px=float(np.max(abs(delta))),
        top_paths=[p for a,b in zip(top,top[1:]+top[:1]) for p in projected_edge(a,b)],
        bottom_paths=[p for a,b in zip(floor,floor[1:]+floor[:1]) for p in projected_edge(a,b)],
        vertical_paths=[p for a,b in zip(top,floor) for p in projected_edge(a,b)])


def compact_paths(paths):
    # 仅缩小显示工件：<=0.0005px舍入；原点和计算几何均保持完整精度。
    return ['M'+'L'.join(f'{x:.3f},{y:.3f}' for x,y in path) for path in paths]


def project_display_record(record):
    projected=annotation_projection(record)
    for key in ('top_paths','bottom_paths','vertical_paths'):
        projected[key]=compact_paths(projected[key])
    return projected
