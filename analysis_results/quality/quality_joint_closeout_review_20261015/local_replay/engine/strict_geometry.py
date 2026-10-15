#!/usr/bin/env python3
"""Strict, non-repairing validation of frozen paired top/bottom wall rings.

Input contract: implicit closure; >=3 paired [x,y,z] vertices; camera-height
units; horizontal floor y=-1; vertical pairs; strictly positive wall heights.
This is NOT a Manhattan, flat-ceiling, camera-inside, or star-shape filter.

No vertex is moved, dropped, re-ordered, snapped, or merged. The return value
contains no corrected geometry. All vertex/edge indices are zero-based and
refer to the ORIGINAL arrays. Edge i is (i, (i+1) mod n).

Segment topology uses a filtered exact orientation predicate: uncertain
float64 determinants are recomputed exactly for the supplied binary floats
with fractions.Fraction. Near-but-disjoint edges are not called touching.
Lengths, area, floor and pair checks use reported float64 roundoff guards,
not physical-quality tolerances. Numerically unresolved input is unavailable,
not silently repaired. Existing spherical metric numerical limits are reported
separately from the validity of the actual paired wall geometry.

Public API: validate_layout(top, bottom, role='annotation', source=None).
Only NumPy and the Python standard library are required.
"""
from __future__ import annotations

from copy import deepcopy
from fractions import Fraction
import math
from typing import Any

import numpy as np


VALIDATOR_VERSION = "strict_geometry_v1.1.0"
EPS64 = np.finfo(np.float64).eps
ROUNDOFF_MULTIPLIER = 64.0
# These two guards match the frozen spherical-arc implementation, not a
# geometry-quality threshold. A collapsed radial edge can be valid in 3-D.
SPHERICAL_MIN_ARC_RAD = 1e-12
SPHERICAL_ANTIPODAL_MARGIN_RAD = 1e-10


def _category(kind: str, role: str) -> str:
    if kind == "data_missing":
        return "data_missing"
    if kind == "model_contract":
        return "model_not_applicable"
    if kind == "metric_domain":
        return "metric_domain_not_applicable"
    if kind == "numerical_resolution":
        return "numerical_resolution"
    return "reference_not_applicable" if role == "reference" else "annotation_geometry_invalid"


def _issue(code: str, message: str, role: str, *, kind: str = "invalid_geometry",
           component: str = "paired_wall_ring_3d", **evidence: Any) -> dict:
    return {"code": code, "category": _category(kind, role), "kind": kind,
            "role": role, "component": component, "message": message,
            "evidence": evidence}


def _orient_sign(a, b, c) -> int:
    """Exact sign of det(b-a,c-a) for the original binary64 coordinates."""
    ax, ay = float(a[0]), float(a[1])
    bx, by = float(b[0]), float(b[1])
    cx, cy = float(c[0]), float(c[1])
    left, right = (bx-ax)*(cy-ay), (by-ay)*(cx-ax)
    det = left-right
    # A deliberately conservative filter; the fallback is exact, not epsilon.
    error = 16.0 * EPS64 * (abs(left)+abs(right))
    if math.isfinite(det) and abs(det) > error:
        return 1 if det > 0 else -1
    aa, ab, ba, bb, ca, cb = map(Fraction.from_float, (ax, ay, bx, by, cx, cy))
    exact = (ba-aa)*(cb-ab)-(bb-ab)*(ca-aa)
    return (exact > 0) - (exact < 0)


def _point_on_segment(p, a, b) -> bool:
    return (_orient_sign(a, b, p) == 0 and
            min(a[0], b[0]) <= p[0] <= max(a[0], b[0]) and
            min(a[1], b[1]) <= p[1] <= max(a[1], b[1]))


def _exact_signed_area(points) -> Fraction:
    q = [[Fraction.from_float(float(x)) for x in p] for p in points]
    return sum((q[i][0]*q[(i+1) % len(q)][1] -
                q[i][1]*q[(i+1) % len(q)][0] for i in range(len(q))), Fraction(0))/2


def _line_intersection(a, b, c, d) -> list[float]:
    # Used only for a known proper intersection, so the denominator is nonzero.
    aa, bb, cc, dd = [[Fraction.from_float(float(x)) for x in p] for p in (a, b, c, d)]
    e, f = [bb[k]-aa[k] for k in range(2)], [dd[k]-cc[k] for k in range(2)]
    den = e[0]*f[1]-e[1]*f[0]
    ca = [cc[k]-aa[k] for k in range(2)]
    t = (ca[0]*f[1]-ca[1]*f[0])/den
    return [float(aa[k]+t*e[k]) for k in range(2)]


def _segment_relation(a, b, c, d) -> dict | None:
    """Return true overlap/cross/contact only; no tolerance-based snapping."""
    s = [_orient_sign(a, b, c), _orient_sign(a, b, d),
         _orient_sign(c, d, a), _orient_sign(c, d, b)]
    if s[0]*s[1] < 0 and s[2]*s[3] < 0:
        return {"relation": "proper_crossing", "point_xz": _line_intersection(a, b, c, d)}
    if s == [0, 0, 0, 0]:
        axis = 0 if abs(b[0]-a[0]) >= abs(b[1]-a[1]) else 1
        lo = max(min(a[axis], b[axis]), min(c[axis], d[axis]))
        hi = min(max(a[axis], b[axis]), max(c[axis], d[axis]))
        if hi < lo:
            return None
        # Endpoints of a collinear overlap are among the original endpoints;
        # returning those avoids reconstructing or modifying coordinates.
        endpoints = [np.asarray(p, float) for p in (a, b, c, d)]
        ends = []
        for u in (lo, hi):
            ends.append(next(p.tolist() for p in endpoints if p[axis] == u))
        if hi > lo:
            return {"relation": "collinear_overlap", "overlap_segment_xz": ends,
                    "overlap_length_h": math.dist(ends[0], ends[1])}
        return {"relation": "endpoint_contact", "points_xz": [ends[0]]}
    contacts = []
    for p, x, y, sign in ((c, a, b, s[0]), (d, a, b, s[1]),
                          (a, c, d, s[2]), (b, c, d, s[3])):
        if sign == 0 and _point_on_segment(p, x, y):
            q = [float(v) for v in p]
            if q not in contacts:
                contacts.append(q)
    return {"relation": "endpoint_contact", "points_xz": contacts} if contacts else None


def _camera_location(points) -> tuple[str, bool]:
    origin = np.array([0., 0.])
    if any(_point_on_segment(origin, a, b) for a, b in zip(points, np.roll(points, -1, axis=0))):
        return "boundary", False
    winding = 0
    for a, b in zip(points, np.roll(points, -1, axis=0)):
        if a[1] <= 0 < b[1] and _orient_sign(a, b, origin) > 0:
            winding += 1
        elif b[1] <= 0 < a[1] and _orient_sign(a, b, origin) < 0:
            winding -= 1
    location = "inside" if winding else "outside"
    area_sign = 1 if _exact_signed_area(points) > 0 else -1
    in_kernel = location == "inside" and all(
        area_sign*_orient_sign(a, b, origin) >= 0
        for a, b in zip(points, np.roll(points, -1, axis=0)))
    return location, bool(in_kernel)


def validate_footprint(points, *, role: str = "annotation") -> dict:
    """Validate an implicitly closed XZ [n,2] ring without changing it."""
    errors: list[dict] = []
    result = {"status": "unavailable", "available": False, "simple_ring": False,
              "vertex_count": None, "area_h2": None, "signed_area_h2": None,
              "perimeter_h": None, "errors": errors, "diagnostics": {}, "tolerances": {}}
    if points is None:
        errors.append(_issue("missing_footprint", "未提供可检查的地面 XZ 顶点。", role,
                             kind="data_missing", component="footprint_2d"))
        return result
    try:
        raw = np.asarray(points)
        if raw.dtype.kind not in "iuf":
            errors.append(_issue("nonnumeric_or_nonreal_footprint_coordinate", "地面坐标必须是实数；不把字符串或复数隐式改写为坐标。", role,
                                 component="footprint_2d", observed_dtype=str(raw.dtype)))
            return result
        p = np.array(raw, dtype=np.float64, copy=True)
    except (ValueError, TypeError, OverflowError) as e:
        errors.append(_issue("malformed_footprint_array", "地面 XZ 顶点无法按数值数组读取。", role,
                             component="footprint_2d", detail=str(e)))
        return result
    if p.ndim != 2 or p.shape[1] != 2:
        errors.append(_issue("malformed_footprint_shape", "地面 XZ 环必须为 [n,2] 数组。", role,
                             component="footprint_2d", observed_shape=list(p.shape)))
        return result
    n = len(p)
    result["vertex_count"] = n
    if n < 3:
        errors.append(_issue("too_few_footprint_vertices", "闭环至少需要 3 个顶点。", role,
                             component="footprint_2d", vertex_count=n))
    if not np.isfinite(p).all():
        errors.append(_issue("nonfinite_footprint_coordinate", "地面 XZ 含非有限坐标。", role,
                             component="footprint_2d", indices=np.argwhere(~np.isfinite(p)).tolist()))
    if errors:
        return result
    try:
        with np.errstate(over="ignore", invalid="ignore"):
            extent = [float(np.max(p[:, k])-np.min(p[:, k])) for k in range(2)]
            scale = max(1., float(np.max(np.abs(p))), *extent)
            length_tol = ROUNDOFF_MULTIPLIER*EPS64*scale
            edges = np.roll(p, -1, axis=0)-p
            lengths = np.array([math.hypot(*e) for e in edges])
            relative = p-p[0]
            products = [(float(a[0]*b[1]), float(a[1]*b[0]))
                        for a, b in zip(relative, np.roll(relative, -1, axis=0))]
            if not (math.isfinite(scale) and np.isfinite(lengths).all() and np.isfinite(products).all()):
                raise ArithmeticError("nonfinite intermediate")
            area = math.fsum(a-b for a, b in products)/2
            absolute_products = math.fsum(abs(a)+abs(b) for a, b in products)
            area_tol = ROUNDOFF_MULTIPLIER*EPS64*max(1., absolute_products)/2
    except (ArithmeticError, ValueError):
        errors.append(_issue("unresolved_numeric_dynamic_range", "当前坐标动态范围超出本浮点计算的稳定范围。", role,
                             kind="numerical_resolution", component="footprint_2d"))
        return result
    result["tolerances"] = {"coordinate_scale_h": scale, "length_roundoff_h": length_tol,
                            "area_roundoff_h2": area_tol,
                            "topology_predicate": "filtered_exact_binary64_orientation_no_snapping"}
    if not (np.isfinite(lengths).all() and math.isfinite(area) and math.isfinite(area_tol)):
        errors.append(_issue("unresolved_numeric_dynamic_range", "当前坐标动态范围超出本浮点计算的稳定范围。", role,
                             kind="numerical_resolution", component="footprint_2d"))
        return result
    result.update(area_h2=abs(area), signed_area_h2=area, perimeter_h=float(math.fsum(lengths)))
    for i, length in enumerate(lengths):
        if length == 0:
            code = "repeated_closure_vertex" if i == n-1 and np.array_equal(p[0], p[-1]) else "zero_length_edge"
            errors.append(_issue(code, "闭环包含零长度边；接口采用隐式闭合，不删除重复端点。", role,
                                 component="footprint_2d", edge_index=i,
                                 vertex_indices=[i, (i+1) % n], point_xz=p[i].tolist()))
        elif length <= length_tol:
            errors.append(_issue("numerically_unresolved_edge", "边长不超过已声明的浮点分辨率保护值。", role,
                                 kind="numerical_resolution", component="footprint_2d", edge_index=i,
                                 vertex_indices=[i, (i+1) % n], length_h=float(length), tolerance_h=length_tol))
    for i in range(n):
        for j in range(i+1, n):
            if j == i+1 or (i == 0 and j == n-1):
                continue
            if np.array_equal(p[i], p[j]):
                errors.append(_issue("repeated_nonadjacent_vertex", "非相邻顶点重复。", role,
                                     component="footprint_2d", vertex_indices=[i, j], point_xz=p[i].tolist()))
    # Include adjacent edges: their intersection may contain MORE than the
    # single shared endpoint (the old implementation missed backtracking).
    for i in range(n):
        if lengths[i] == 0:
            continue
        a, b = p[i], p[(i+1) % n]
        for j in range(i+1, n):
            if lengths[j] == 0:
                continue
            adjacent = j == i+1 or (i == 0 and j == n-1)
            c, d = p[j], p[(j+1) % n]
            rel = _segment_relation(a, b, c, d)
            if rel is None:
                continue
            evidence = {"edge_indices": [i, j], "edge_vertices": [[i, (i+1) % n], [j, (j+1) % n]], **rel}
            if rel["relation"] == "collinear_overlap":
                code = "overlapping_backtrack_edges" if adjacent else "overlapping_nonadjacent_edges"
                errors.append(_issue(code, "边沿同一直线正长度重叠；不是合法的共线前进分段。", role,
                                     component="footprint_2d", **evidence))
            elif not adjacent and rel["relation"] == "proper_crossing":
                errors.append(_issue("self_intersection", "非相邻边发生严格交叉。", role,
                                     component="footprint_2d", **evidence))
            elif not adjacent:
                touches = []
                for vi, v, ej, x, y in ((i, a, j, c, d), ((i+1) % n, b, j, c, d),
                                       (j, c, i, a, b), ((j+1) % n, d, i, a, b)):
                    if _point_on_segment(v, x, y) and not np.array_equal(v, x) and not np.array_equal(v, y):
                        touches.append({"vertex_index": vi, "edge_index": ej, "point_xz": v.tolist()})
                code = "nonadjacent_vertex_touches_edge" if touches else "nonadjacent_edges_touch"
                errors.append(_issue(code, "非相邻边或顶点相接；闭环不是简单环。", role,
                                     component="footprint_2d", touches=touches, **evidence))
    if abs(area) <= area_tol:
        exact = _exact_signed_area(p)
        if exact == 0:
            errors.append(_issue("zero_signed_area", "闭环有向面积为零。", role,
                                 component="footprint_2d", signed_area_h2=0.))
        else:
            errors.append(_issue("numerically_unresolved_area", "非零面积不超过已声明的浮点分辨率保护值。", role,
                                 kind="numerical_resolution", component="footprint_2d",
                                 signed_area_h2=float(exact), tolerance_h2=area_tol))
    result["simple_ring"] = not errors
    result["available"] = not errors
    result["status"] = "available" if not errors else "unavailable"
    if not errors:
        location, in_kernel = _camera_location(p)
        result["diagnostics"] = {"orientation": "counterclockwise" if area > 0 else "clockwise",
                                 "camera_xz_location": location,
                                 "camera_in_visibility_kernel": in_kernel,
                                 "azimuth_single_valued_geometric_condition": location == "inside" and in_kernel}
    return result


def _read_ring(value, name: str, role: str) -> tuple[np.ndarray | None, list[dict]]:
    if value is None:
        return None, [_issue("missing_"+name, f"未提供 {name} 坐标。", role, kind="data_missing", ring=name)]
    try:
        raw = np.asarray(value)
        if raw.dtype.kind not in "iuf":
            missing = raw.dtype.kind == "O" and any(x is None for x in raw.flat)
            code = "missing_coordinate_in_"+name if missing else "nonnumeric_or_nonreal_"+name+"_coordinate"
            return None, [_issue(code, f"{name} 必须提供实数坐标；不将字符串、复数或对象隐式改写为几何。", role,
                                 kind="data_missing" if missing else "invalid_geometry", ring=name,
                                 observed_dtype=str(raw.dtype))]
        a = np.array(raw, dtype=np.float64, copy=True)
    except (ValueError, TypeError, OverflowError) as e:
        return None, [_issue("malformed_"+name, f"{name} 无法按数值数组读取。", role, ring=name, detail=str(e))]
    if a.ndim != 2 or a.shape[1] != 3:
        return None, [_issue("malformed_"+name+"_shape", f"{name} 必须为 [n,3] 数组。", role,
                            ring=name, observed_shape=list(a.shape))]
    return a, []


def _spherical_projectability(ring: np.ndarray, ring_name: str, role: str) -> tuple[list[dict], dict]:
    errors = []
    norms = np.array([math.hypot(*p) for p in ring])
    min_theta, min_margin = math.inf, math.inf
    for i, norm in enumerate(norms):
        if norm == 0:
            errors.append(_issue("spherical_vertex_at_camera_origin", "顶点位于相机原点，球面投影未定义。", role,
                                 kind="metric_domain", component="spherical_boundary", ring=ring_name,
                                 vertex_index=i, point_xyz=ring[i].tolist()))
    if errors:
        return errors, {"min_vertex_camera_distance_h": float(norms.min())}
    unit = ring/norms[:, None]
    for i, (a, b) in enumerate(zip(unit, np.roll(unit, -1, axis=0))):
        sin_angle = math.hypot(*np.cross(a, b))
        cos_angle = float(np.dot(a, b))
        theta = math.atan2(sin_angle, cos_angle)
        min_theta, min_margin = min(min_theta, theta), min(min_margin, math.pi-theta)
        if theta < SPHERICAL_MIN_ARC_RAD:
            code = "zero_angular_length_edge" if theta == 0 else "numerically_unresolved_spherical_arc"
            errors.append(_issue(code, "该 3D 边的球面弧为零或小于当前球面计算的数值保护值。", role,
                                 kind="metric_domain", component="spherical_boundary", ring=ring_name,
                                 edge_index=i, vertex_indices=[i, (i+1) % len(ring)], angle_rad=theta,
                                 threshold_rad=SPHERICAL_MIN_ARC_RAD,
                                 explanation="3D 墙环本身可有效；该完整分数的球面分量当前不可计算。"))
        elif math.pi-theta < SPHERICAL_ANTIPODAL_MARGIN_RAD:
            code = "edge_passes_camera_origin" if sin_angle == 0 and cos_angle < 0 else "antipodal_or_unresolved_spherical_arc"
            errors.append(_issue(code, "该边经过或数值上接近相机原点，不能唯一使用当前球面短弧。", role,
                                 kind="metric_domain", component="spherical_boundary", ring=ring_name,
                                 edge_index=i, vertex_indices=[i, (i+1) % len(ring)], angle_rad=theta,
                                 antipodal_margin_rad=math.pi-theta,
                                 threshold_rad=SPHERICAL_ANTIPODAL_MARGIN_RAD))
    return errors, {"min_vertex_camera_distance_h": float(norms.min()),
                    "min_edge_arc_rad": min_theta, "min_edge_antipodal_margin_rad": min_margin}


def validate_layout(top, bottom, *, role: str = "annotation", source: Any = None) -> dict:
    """Return structured validity and availability; never raises for bad arrays.

    ``role='reference'`` reports invalid reference geometry as
    ``reference_not_applicable``. A model/frame violation and missing data keep
    their own categories for either role. A valid non-star-shaped/non-Manhattan
    or non-flat ring is accepted. ``source`` is copied without interpretation.
    """
    if role not in {"annotation", "reference"}:
        raise ValueError("role must be 'annotation' or 'reference'")
    t, top_errors = _read_ring(top, "top3d", role)
    b, bottom_errors = _read_ring(bottom, "bottom3d", role)
    errors = [*top_errors, *bottom_errors]
    warnings: list[dict] = []
    fp = validate_footprint(b[:, [0, 2]], role=role) if b is not None else {
        "status": "unavailable", "available": False, "errors": [], "diagnostics": {}, "tolerances": {}}
    errors.extend(fp["errors"])
    pair_checks_available = t is not None and b is not None
    tol = {"float64_epsilon": float(EPS64), "roundoff_multiplier": ROUNDOFF_MULTIPLIER,
           "floor_y_expected_h": -1., "spherical_min_arc_rad": SPHERICAL_MIN_ARC_RAD,
           "spherical_antipodal_margin_rad": SPHERICAL_ANTIPODAL_MARGIN_RAD, **fp["tolerances"]}
    diag = dict(fp.get("diagnostics", {}))
    for ring_name, ring in (("top3d", t), ("bottom3d", b)):
        if ring is None:
            continue
        if len(ring) < 3:
            errors.append(_issue("too_few_"+ring_name+"_vertices", "闭环至少需要 3 个顶点。", role,
                                 ring=ring_name, vertex_count=len(ring)))
        if not np.isfinite(ring).all():
            errors.append(_issue("nonfinite_"+ring_name+"_coordinate", f"{ring_name} 含非有限坐标。", role,
                                 ring=ring_name, indices=np.argwhere(~np.isfinite(ring)).tolist()))
    if pair_checks_available:
        if t.shape != b.shape:
            errors.append(_issue("unequal_paired_ring_shapes", "上下环点数或数组形状不一致；不自动配对。", role,
                                 top_shape=list(t.shape), bottom_shape=list(b.shape)))
        elif (len(b) >= 3 and np.isfinite(b).all() and np.isfinite(t).all() and
              not any(e["code"] == "unresolved_numeric_dynamic_range" for e in fp["errors"])):
            y_scale = max(1., float(np.max(np.abs(b[:, 1]))), float(np.max(np.abs(t[:, 1]))))
            xz_scale = max(1., float(np.max(np.abs(b[:, [0, 2]]))), float(np.max(np.abs(t[:, [0, 2]]))))
            floor_tol = ROUNDOFF_MULTIPLIER*EPS64*max(1., float(np.max(np.abs(b[:, 1]))))
            pair_tol = ROUNDOFF_MULTIPLIER*EPS64*xz_scale
            height_tol = ROUNDOFF_MULTIPLIER*EPS64*y_scale
            tol.update(floor_roundoff_h=floor_tol, vertical_pair_roundoff_h=pair_tol,
                       positive_height_roundoff_h=height_tol)
            floor_err = np.abs(b[:, 1]+1)
            bad = np.flatnonzero(floor_err > floor_tol)
            if len(bad):
                errors.append(_issue("unsupported_floor_model_or_units", "底面不满足已冻结的 y=-1 相机高度单位模型；未重定标。", role,
                                     kind="model_contract", vertex_indices=bad.tolist(), observed_floor_y_h=b[bad, 1].tolist(),
                                     expected_floor_y_h=-1., tolerance_h=floor_tol))
            pair_err = np.max(np.abs(t[:, [0, 2]]-b[:, [0, 2]]), axis=1)
            bad = np.flatnonzero(pair_err > pair_tol)
            if len(bad):
                errors.append(_issue("unpaired_vertical_xz", "上下对应顶点 XZ 不一致；不自动换序或修成竖直点对。", role,
                                     vertex_indices=bad.tolist(), top_xz=t[bad][:, [0, 2]].tolist(),
                                     bottom_xz=b[bad][:, [0, 2]].tolist(),
                                     max_coordinate_mismatch_h=float(pair_err.max()), tolerance_h=pair_tol))
            elif fp["available"] and not np.array_equal(t[:, [0, 2]], b[:, [0, 2]]):
                # Roundoff-sized pair differences must NOT license replacing
                # actual top coordinates by bottom coordinates. Near a contact
                # this can conceal an actual top crossing/touch even with a
                # flat, positive-height top ring. Check its represented XZ
                # topology, and flag inconsistent numerical models separately.
                top_projection = validate_footprint(t[:, [0, 2]], role=role)
                diag["actual_top_xz_projection_checked"] = True
                diag["actual_top_xz_projection_available"] = top_projection["available"]
                if not top_projection["available"]:
                    errors.append(_issue("paired_topology_inconsistent_within_roundoff",
                                         "上下 XZ 差虽在舍入保护内，但实际顶环投影不是简单环；不能用底环替代顶环修形。", role,
                                         kind="numerical_resolution", component="paired_wall_ring_3d",
                                         max_pair_difference_h=float(pair_err.max()), pairing_tolerance_h=pair_tol,
                                         top_y_min_h=float(t[:, 1].min()), top_y_max_h=float(t[:, 1].max()),
                                         top_projection_errors=top_projection["errors"]))
            heights = t[:, 1]-b[:, 1]
            bad = np.flatnonzero(heights <= 0)
            if len(bad):
                errors.append(_issue("top_at_or_below_floor", "顶点不高于对应地面，不能形成正高度墙环。", role,
                                     vertex_indices=bad.tolist(), wall_heights_h=heights[bad].tolist()))
            tiny = np.flatnonzero((heights > 0) & (heights <= height_tol))
            if len(tiny):
                errors.append(_issue("numerically_unresolved_wall_height", "正墙高不超过当前浮点分辨率保护值。", role,
                                     kind="numerical_resolution", vertex_indices=tiny.tolist(),
                                     wall_heights_h=heights[tiny].tolist(), tolerance_h=height_tol))
            diag.update(vertex_count=len(b), max_pair_xz_difference_h=float(pair_err.max()),
                        min_wall_height_h=float(heights.min()), max_wall_height_h=float(heights.max()),
                        min_top_y_h=float(t[:, 1].min()), max_top_y_h=float(t[:, 1].max()),
                        top_vertices_below_camera=int(np.sum(t[:, 1] < 0)),
                        top_is_constant_height_within_roundoff=bool(np.ptp(t[:, 1]) <= height_tol))
    valid_3d = not errors
    sphere_diag = {}
    spherical_errors = []
    if valid_3d:
        for ring_name, ring in (("top3d", t), ("bottom3d", b)):
            err, info = _spherical_projectability(ring, ring_name, role)
            spherical_errors.extend(err)
            sphere_diag[ring_name] = info
        errors.extend(spherical_errors)
        location = diag.get("camera_xz_location")
        if location != "inside":
            warnings.append({"code": "camera_"+str(location)+"_footprint", "message":
                             "相机 XZ 不在地面环严格内部；几何仍按输入计算，该事实不自动判无效。"})
        elif not diag.get("camera_in_visibility_kernel"):
            warnings.append({"code": "non_star_shaped_about_camera", "message":
                             "地面环关于相机不是星形；完整球面边界仍可计算，逐方位单值 U/B 不适用。"})
        if diag.get("top_vertices_below_camera", 0):
            warnings.append({"code": "top_below_camera_but_above_floor", "message":
                             "存在低于相机但高于地面的顶点；这是可评价几何，不按平顶或相机包围规则排除。"})
    available = valid_3d and not spherical_errors
    return {"validator_version": VALIDATOR_VERSION, "status": "available" if available else "unavailable",
            "available": available, "valid_2d": bool(fp["available"]), "valid_3d": valid_3d,
            "spherical_boundary_available": available, "role": role, "source": deepcopy(source),
            "role_impact": None if available else ("reference_not_applicable" if role == "reference" else "annotation_not_evaluable"),
            "input_policy": "original coordinates, pairing, closure, order and source retained; no repair",
            "availability": {"footprint_2d": bool(fp["available"]), "paired_wall_ring_3d": valid_3d,
                             "spherical_full_boundary": available, "complete_quality_input": available},
            "reason_codes": list(dict.fromkeys(x["code"] for x in errors)),
            "failure_classes": list(dict.fromkeys(x["category"] for x in errors)),
            "errors": errors, "warnings": warnings, "footprint_2d": fp,
            "diagnostics": diag, "spherical_diagnostics": sphere_diag, "tolerances": tol}


def validate_record(record, *, role: str = "annotation", source: Any = None) -> dict:
    """Convenience adapter for existing {top3d,bottom3d,...} records."""
    if not isinstance(record, dict):
        return validate_layout(None, None, role=role, source=source)
    return validate_layout(record.get("top3d"), record.get("bottom3d"), role=role, source=source)
