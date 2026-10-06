"""Unchanged region_mesh and tile_consensus excerpts from repository.
region_mesh: tools/thesis_main/analysis/audit_supervisor_gt_sensitivity_20260922.py
            Only region_mesh is reused; NONE of its legacy projection functions.
tile_consensus: tools/thesis_main/analysis/lee_tile_stage1_20261002.py
The present run invokes it ONCE at the existing e9z-19 N=24 endpoint.
"""
import warnings
import numpy as np
from shapely import contains_xy
from shapely.geometry import Polygon
from shapely.ops import polygonize, unary_union

def region_mesh(polygons):
    tiles = list(polygonize(unary_union([p.boundary for p in polygons])))
    xy = np.array([[p.representative_point().x, p.representative_point().y] for p in tiles])
    votes = np.array([contains_xy(p, xy[:, 0], xy[:, 1]) for p in polygons])
    keep = votes.any(axis=0)
    tiles = [p for p, use in zip(tiles, keep) if use]
    a = np.array([p.area for p in tiles])
    c = np.array([[p.centroid.x, p.centroid.y] for p in tiles])
    return dict(tiles=tiles, votes=votes[:, keep], area=a, moment=a[:, None]*c)

def tile_consensus(records):
    if not records:
        raise ValueError('empty_roster')
    for key in ('id', 'worker'):
        if len({r[key] for r in records}) != len(records):
            raise ValueError('duplicate_' + key)
    polygons = []
    for r in records:
        if r['footprint'] is None:
            raise ValueError('unavailable_footprint:' + r['id'])
        xy = np.asarray(r['footprint'], dtype=float)
        if xy.ndim != 2 or xy.shape[1] != 2 or len(xy) < 3 or not np.isfinite(xy).all():
            raise ValueError('invalid_footprint:' + r['id'])
        p = Polygon(xy)
        if not p.is_valid or not np.isfinite(p.area) or p.area <= 0:
            raise ValueError('invalid_footprint:' + r['id'])
        polygons.append(p)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always', RuntimeWarning)
        mesh = region_mesh(polygons)
        domain = unary_union(polygons)
        area = mesh['area']
        tolerance = 1e-9 * max(1., domain.area)
        if not np.isfinite(area).all() or np.any(area <= 0):
            raise ValueError('nonpositive_or_nonfinite_tile')
        if abs(area.sum() - domain.area) > tolerance:
            raise ValueError('tile_partition_area_mismatch')
        restored = mesh['votes'] @ area
        if np.any(abs(restored - np.array([p.area for p in polygons])) > tolerance):
            raise ValueError('tile_worker_area_mismatch')
        support = mesh['votes'].sum(axis=0)
        selections = dict(mv50=2 * support >= len(records), mv_strict=2 * support > len(records))
        regions = {method: unary_union([t for t, keep in zip(mesh['tiles'], selected) if keep])
                   for method, selected in selections.items()}
        if any(not g.is_valid or not np.isfinite(g.area) for g in regions.values()):
            raise ValueError('invalid_consensus_geometry')
    return dict(mesh=mesh, regions=regions, selections=selections,
                warnings=[str(w.message) for w in caught])
