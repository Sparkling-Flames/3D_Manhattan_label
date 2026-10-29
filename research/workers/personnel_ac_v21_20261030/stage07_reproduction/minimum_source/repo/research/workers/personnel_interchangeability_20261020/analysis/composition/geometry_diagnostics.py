"""Separate footprint diagnostics against the existing fixed reference.

This module does not import or change the fusion engine, B8L2, D10, or N1.
Call ``diagnose(candidate['footprint'], reference['floor_xz_h'])``. Both
arguments are cyclic N x 2 coordinate rings in the same frozen floor frame.

Wall coverage: for each reference segment, accept candidate segments with
unoriented direction difference <= 10 degrees. Clip each candidate segment
pointwise to the +/- tolerance slab around the reference supporting line,
project the surviving part onto the reference segment, and take the union of
the projected intervals. Sum covered lengths / reference perimeter. Tolerances
are 0.03 and 0.05 times sqrt(reference area). Clipping pointwise (rather than
requiring both endpoints to be close) makes straight-segment subdivision
irrelevant to this calculation.

Corner retention: select vertices whose direction change is strictly > 10
degrees. Under Euclidean distance <= 0.05 * sqrt(reference area), first maximize
the number of one-to-one reference/candidate matches, then minimize their total
distance. The ratio is matched reference corners / eligible reference corners.

Missing, malformed, degenerate, or self-intersecting rings yield missing
diagnostics, never zero. A repeated closing vertex and exact consecutive
duplicates are harmlessly removed for these diagnostics, with original input
indices retained. No other repair, snapping, alignment, or reference change is
performed. Collinear points are kept in the wall representation and excluded
from the eligible-corner set by the turn threshold.

Interpretation: these are reference-relative geometric diagnostics, not a
validated necessary-structure score or a replacement quality score. Coverage
does not penalize additional walls; corner matching only checks location, not
convex/reflex type or incident wall directions. Reference visibility, scope
eligibility, height, and semantic necessity are not inferred here.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
from scipy.optimize import linear_sum_assignment
from shapely.geometry import Polygon
from shapely.validation import explain_validity

SCHEMA = "fixed_reference_geometry_diagnostics_v1"
DIRECTION_TOLERANCE_DEG = 10.0
TURN_MIN_DEG = 10.0
WALL_TOLERANCE_FRACTIONS = (("03", 0.03), ("05", 0.05))
CORNER_TOLERANCE_FRACTION = 0.05


def _prepare_ring(value: Any) -> dict[str, Any]:
    if value is None:
        return {"status": "missing", "reason": "no_floor"}
    try:
        a = np.asarray(value, dtype=float)
    except (TypeError, ValueError, OverflowError) as exc:
        return {"status": "invalid", "reason": "not_numeric: " + type(exc).__name__}
    if a.ndim != 2 or a.shape[1] != 2:
        return {"status": "invalid", "reason": "expected_N_by_2_ring"}
    if not np.isfinite(a).all():
        return {"status": "invalid", "reason": "nonfinite_coordinate"}
    input_n = len(a)
    if input_n < 3:
        return {"status": "invalid", "reason": "fewer_than_three_vertices"}
    keep = np.concatenate(([True], np.any(a[1:] != a[:-1], axis=1)))
    indices = np.flatnonzero(keep)
    p = a[indices]
    if len(p) > 1 and np.array_equal(p[0], p[-1]):
        p, indices = p[:-1], indices[:-1]
    if len(p) < 3:
        return {"status": "invalid", "reason": "fewer_than_three_distinct_consecutive_vertices"}
    polygon = Polygon(p)
    if not polygon.is_valid:
        return {"status": "invalid", "reason": explain_validity(polygon)}
    span = float(np.max(np.ptp(p, axis=0)))
    area, perimeter = float(polygon.area), float(polygon.length)
    area_epsilon = 64 * np.finfo(float).eps * span * span
    if not math.isfinite(area) or not math.isfinite(perimeter) or area <= area_epsilon or perimeter <= 0:
        return {"status": "invalid", "reason": "degenerate_or_numerically_zero_area"}
    return {
        "status": "ok", "reason": None, "points": p,
        "input_indices": indices, "input_n": input_n,
        "removed_exact_duplicate_n": input_n - len(p),
        "area": area, "perimeter": perimeter,
    }


def _cross2(a: np.ndarray, b: np.ndarray) -> float:
    return float(a[0] * b[1] - a[1] * b[0])


def _union_intervals(intervals: list[tuple[float, float]], epsilon: float) -> list[tuple[float, float]]:
    if not intervals:
        return []
    ordered = sorted(intervals)
    result = [ordered[0]]
    for low, high in ordered[1:]:
        old_low, old_high = result[-1]
        if low <= old_high + epsilon:
            result[-1] = (old_low, max(old_high, high))
        else:
            result.append((low, high))
    return result


def _wall_coverage(candidate: np.ndarray, reference: np.ndarray, tolerance: float) -> dict[str, Any]:
    candidate_end = np.roll(candidate, -1, axis=0)
    candidate_vectors = candidate_end - candidate
    candidate_lengths = np.linalg.norm(candidate_vectors, axis=1)
    cos_limit = math.cos(math.radians(DIRECTION_TOLERANCE_DEG))
    walls = []
    total_covered = total_length = 0.0
    for i, start in enumerate(reference):
        end = reference[(i + 1) % len(reference)]
        vector = end - start
        length = float(np.linalg.norm(vector))
        unit = vector / length
        epsilon = 64 * np.finfo(float).eps * max(length, tolerance)
        intervals = []
        for p, q, v, candidate_length in zip(candidate, candidate_end, candidate_vectors, candidate_lengths):
            cosine = abs(float(np.dot(unit, v))) / float(candidate_length)
            if cosine + 1e-12 < cos_limit:
                continue
            d0, d1 = _cross2(unit, p - start), _cross2(unit, q - start)
            slope = d1 - d0
            if abs(slope) <= epsilon:
                if abs(d0) > tolerance + epsilon:
                    continue
                low_t, high_t = 0.0, 1.0
            else:
                a, b = (-tolerance - d0) / slope, (tolerance - d0) / slope
                low_t, high_t = max(0.0, min(a, b)), min(1.0, max(a, b))
                if high_t <= low_t:
                    continue
            p0 = float(np.dot(p + low_t * v - start, unit))
            p1 = float(np.dot(p + high_t * v - start, unit))
            low, high = max(0.0, min(p0, p1)), min(length, max(p0, p1))
            if high > low:
                intervals.append((low, high))
        union = _union_intervals(intervals, epsilon)
        covered = min(length, sum(high - low for low, high in union))
        walls.append({
            "reference_ring_edge_index": i, "length": length,
            "covered_length": covered, "coverage": covered / length,
            "covered_intervals": [[float(low), float(high)] for low, high in union],
        })
        total_covered += covered
        total_length += length
    return {
        "covered_length": total_covered, "reference_length": total_length,
        "coverage": min(1.0, max(0.0, total_covered / total_length)), "walls": walls,
    }


def _corners(points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    incoming = points - np.roll(points, 1, axis=0)
    outgoing = np.roll(points, -1, axis=0) - points
    cross = incoming[:, 0] * outgoing[:, 1] - incoming[:, 1] * outgoing[:, 0]
    dot = np.sum(incoming * outgoing, axis=1)
    turns = np.degrees(np.arctan2(np.abs(cross), dot))
    return np.flatnonzero(turns > TURN_MIN_DEG), turns


def _maximum_cardinality_min_distance(reference: np.ndarray, candidate: np.ndarray,
                                     tolerance: float) -> list[tuple[int, int, float]]:
    """Lexicographic cardinality/distance assignment, with unmatched dummy columns."""
    nref, ncandidate = len(reference), len(candidate)
    if not nref or not ncandidate:
        return []
    distances = np.linalg.norm(reference[:, None, :] - candidate[None, :, :], axis=2)
    allowed = distances <= tolerance * (1.0 + 64 * np.finfo(float).eps)
    # Every real allowed edge costs <= about 1. A single unmatched penalty
    # exceeds the sum of all possible allowed-edge costs, guaranteeing the
    # number of matches is optimized before distance. There are nref dummies,
    # so assigning an ineligible real edge is never necessary or optimal.
    unmatched_penalty = 2.0 * (nref + 1)
    forbidden_penalty = unmatched_penalty * (nref + ncandidate + 1)
    cost = np.full((nref, ncandidate + nref), unmatched_penalty, dtype=float)
    cost[:, :ncandidate] = np.where(allowed, distances / tolerance, forbidden_penalty)
    ii, jj = linear_sum_assignment(cost)
    return [(int(i), int(j), float(distances[i, j]))
            for i, j in zip(ii, jj) if j < ncandidate and allowed[i, j]]


def diagnose(candidate_floor: Any, reference_floor: Any) -> dict[str, Any]:
    """Return JSON-safe scalar diagnostics and exact per-wall/corner details.

    Main scalars: ``diag_wall_coverage_03``, ``diag_wall_coverage_05``, and
    ``diag_corner_recall_05``. Inspect ``diag_status`` before aggregation.
    Detailed arrays may be retained only for representative cases if size
    matters; they contain all intervals and pairings used by these scalars.
    """
    candidate, reference = _prepare_ring(candidate_floor), _prepare_ring(reference_floor)
    result: dict[str, Any] = {
        "diag_schema": SCHEMA, "diag_status": None,
        "diag_candidate_status": candidate["status"], "diag_candidate_reason": candidate["reason"],
        "diag_reference_status": reference["status"], "diag_reference_reason": reference["reason"],
        "diag_wall_direction_tolerance_deg": DIRECTION_TOLERANCE_DEG,
        "diag_corner_turn_min_deg": TURN_MIN_DEG,
        "diag_reference_area": None, "diag_reference_perimeter": None, "diag_reference_scale": None,
        "diag_reference_corner_n": None, "diag_candidate_corner_n": None,
        "diag_matched_corner_n": None, "diag_corner_recall_05": None,
        "diag_corner_tolerance_05": None, "diag_corner_matches": None,
    }
    for tag, _ in WALL_TOLERANCE_FRACTIONS:
        result.update({f"diag_wall_coverage_{tag}": None, f"diag_wall_covered_length_{tag}": None,
                       f"diag_wall_tolerance_{tag}": None, f"diag_wall_details_{tag}": None})
    if reference["status"] != "ok":
        result["diag_status"] = reference["status"] + "_reference"
        return result
    scale = math.sqrt(reference["area"])
    result.update(diag_reference_area=reference["area"], diag_reference_perimeter=reference["perimeter"],
                  diag_reference_scale=scale,
                  diag_reference_removed_exact_duplicate_n=reference["removed_exact_duplicate_n"],
                  diag_reference_input_vertex_n=reference["input_n"])
    for tag, fraction in WALL_TOLERANCE_FRACTIONS:
        result[f"diag_wall_tolerance_{tag}"] = fraction * scale
    result["diag_corner_tolerance_05"] = CORNER_TOLERANCE_FRACTION * scale
    if candidate["status"] != "ok":
        result["diag_status"] = candidate["status"] + "_candidate"
        return result
    p, r = candidate["points"], reference["points"]
    result.update(diag_status="ok", diag_candidate_removed_exact_duplicate_n=candidate["removed_exact_duplicate_n"],
                  diag_candidate_input_vertex_n=candidate["input_n"])
    for tag, fraction in WALL_TOLERANCE_FRACTIONS:
        coverage = _wall_coverage(p, r, fraction * scale)
        for wall in coverage["walls"]:
            i = wall["reference_ring_edge_index"]
            wall["reference_input_start_index"] = int(reference["input_indices"][i])
            wall["reference_input_end_index"] = int(reference["input_indices"][(i + 1) % len(r)])
        result[f"diag_wall_coverage_{tag}"] = coverage["coverage"]
        result[f"diag_wall_covered_length_{tag}"] = coverage["covered_length"]
        result[f"diag_wall_details_{tag}"] = coverage["walls"]
    ri, rturn = _corners(r)
    pi, pturn = _corners(p)
    pairs = _maximum_cardinality_min_distance(r[ri], p[pi], CORNER_TOLERANCE_FRACTION * scale)
    result.update(diag_reference_corner_n=len(ri), diag_candidate_corner_n=len(pi),
                  diag_matched_corner_n=len(pairs), diag_corner_recall_05=len(pairs) / len(ri) if len(ri) else None,
                  diag_corner_status="ok" if len(ri) else "no_reference_turn_above_threshold")
    result["diag_corner_matches"] = [{
        "reference_input_index": int(reference["input_indices"][ri[i]]),
        "candidate_input_index": int(candidate["input_indices"][pi[j]]),
        "reference_ring_index": int(ri[i]), "candidate_ring_index": int(pi[j]),
        "distance": distance, "distance_over_reference_scale": distance / scale,
        "reference_turn_deg": float(rturn[ri[i]]), "candidate_turn_deg": float(pturn[pi[j]]),
    } for i, j, distance in pairs]
    return result
