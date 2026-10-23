"""Reference-free planar cells and per-observer membership for region voting.

Preserves every observer and every polygonized cell in the source union.
No consensus threshold, reference geometry or coordinate conversion is applied.
"""
from __future__ import annotations

import numpy as np
from shapely import contains_xy
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
