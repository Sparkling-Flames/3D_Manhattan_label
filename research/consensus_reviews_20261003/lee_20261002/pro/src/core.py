"""Minimal, standalone extraction of the current region_mesh/tile/replay kernels.
Source b1ebab888fe8ac736548897f126a8bce7292c114; paths in README.
No old coordinate loader or preprocessing is imported. No raw-data writeback.
"""
from __future__ import annotations
from collections import Counter
from itertools import combinations
import warnings
import numpy as np
from shapely import contains_xy
from shapely.errors import GEOSException
from shapely.geometry import Polygon, mapping
from shapely.ops import polygonize, unary_union
METHODS = ('mv50','mv_strict')

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

def region_iou(a, b):
    intersection = a.intersection(b).area
    tolerance = 1e-12 * max(1., a.area, b.area)
    if (not np.isfinite(intersection) or intersection < -tolerance
            or intersection > min(a.area, b.area) + tolerance):
        raise ValueError('nonfinite_or_inconsistent_intersection')
    union = a.area + b.area - intersection
    return float(np.clip(intersection / union, 0., 1.)) if union else 1.0

def _summary(values):
    valid = [v for v in values if v is not None]
    return (float(np.mean(valid)), float(np.quantile(valid, .1)), float(np.quantile(valid, .9))) if valid else (None, None, None)

def replay_group(group, *, permutations, seed):
    if permutations < 1:
        raise ValueError('positive_permutations_required')
    records = sorted(group['records'], key=lambda r: r['id'])
    for key in ('id', 'worker'):
        if len({r[key] for r in records}) != len(records):
            raise ValueError('duplicate_' + key)
    rng = np.random.default_rng(seed)
    by_id = {r['id']: r for r in records}
    references = {v: Polygon(p) for v, p in group['references'].items() if p is not None}
    if any(not p.is_valid or p.area <= 0 for p in references.values()):
        raise ValueError('invalid_reference_footprint')
    cache, rows, notices = {}, [], []
    for draw in range(permutations):
        order = rng.permutation(len(records))
        previous = dict.fromkeys(METHODS)
        for k in range(1, len(records) + 1):
            members = tuple(sorted(records[i]['id'] for i in order[:k]))
            if members not in cache:
                try:
                    cache[members] = tile_consensus([by_id[i] for i in members])
                except (ValueError, GEOSException) as exc:
                    cache[members] = dict(error=str(exc))
                for note in cache[members].get('warnings', []):
                    notices.append(dict(stage='tiling', members=list(members), message=note))
            result = cache[members]
            for method in METHODS:
                row = dict(draw=draw, k=k, method=method, members='|'.join(members),
                           status='unavailable' if 'error' in result else 'ok', reason=result.get('error'),
                           tile_count=None, area_h2=None, empty=None, original_iou=None,
                           manual_revision_iou=None, change_from_previous=None)
                if 'error' not in result:
                    region = result['regions'][method]
                    row.update(tile_count=len(result['mesh']['tiles']), area_h2=float(region.area), empty=region.is_empty)
                    with warnings.catch_warnings(record=True) as caught:
                        warnings.simplefilter('always', RuntimeWarning)
                        for version, reference in references.items():
                            row[version + '_iou'] = region_iou(region, reference)
                        if previous[method] is not None:
                            row['change_from_previous'] = 1 - region_iou(region, previous[method])
                    for note in caught:
                        notices.append(dict(stage='evaluation', draw=draw, k=k, method=method,
                                            members=list(members), message=str(note.message)))
                    previous[method] = region
                else:
                    previous[method] = None
                rows.append(row)
    summary = []
    for method in METHODS:
        for k in range(1, len(records) + 1):
            observed = [r for r in rows if r['method'] == method and r['k'] == k]
            unique = {r['members']: r for r in observed if r['status'] == 'ok'}
            row = dict(method=method, k=k, roster_n=len(records), draws=len(observed),
                       valid_draws=sum(r['status'] == 'ok' for r in observed), unique_subsets=len(unique),
                       empty_subsets=sum(r['empty'] for r in unique.values()))
            for version in ('original', 'manual_revision'):
                values = [r[version + '_iou'] for r in unique.values()]
                row[version + '_n'] = sum(v is not None for v in values)
                for stat, value in zip(('mean', 'p10', 'p90'), _summary(values)):
                    row[version + '_' + stat] = value
            row['change_mean'] = _summary([r['change_from_previous'] for r in observed])[0]
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always', RuntimeWarning)
                distances = [1 - region_iou(cache[tuple(a.split('|'))]['regions'][method],
                                            cache[tuple(b.split('|'))]['regions'][method])
                             for a, b in combinations(unique, 2)]
            notices.extend(dict(stage='member_distance', k=k, method=method, message=str(w.message)) for w in caught)
            row['member_pairs'] = len(distances)
            row['member_distance_mean'] = float(np.mean(distances)) if distances else (0. if k == len(records) and unique else None)
            summary.append(row)
    return dict(rows=rows, summary=summary, warnings=notices, cache=cache)
