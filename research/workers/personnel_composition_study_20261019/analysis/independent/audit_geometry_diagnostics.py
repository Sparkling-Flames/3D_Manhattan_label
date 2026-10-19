#!/usr/bin/env python3
"""Small geometric specification probes; not new research/validation evidence."""
import os
for variable in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[variable] = "1"
import hashlib
import importlib.util
import json
import math
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "analysis/composition/geometry_diagnostics.py"
spec = importlib.util.spec_from_file_location("audited_geometry_diagnostics", MODULE)
gd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gd)


def subdivide(ring):
    result = []
    for p, q in zip(ring, np.roll(ring, -1, axis=0)):
        result.extend([p.tolist(), ((p + q) / 2).tolist()])
    return np.asarray(result)


def close(a, b, tolerance=1e-12):
    assert abs(a - b) <= tolerance, (a, b)


def main():
    square = np.asarray([[-2, -2], [2, -2], [2, 2], [-2, 2]], dtype=float)
    bump = np.asarray([[-2, -2], [2, -2], [2, -1], [3, -1], [3, 1], [2, 1], [2, 2], [-2, 2]], dtype=float)
    notch = np.asarray([[-2, -2], [2, -2], [2, 2], [1, 2], [1, 1], [-1, 1], [-1, 2], [-2, 2]], dtype=float)
    angle = math.radians(5)
    rotation = np.asarray([[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]])
    rotated = square @ rotation.T
    bowtie = np.asarray([[-2, -2], [2, 2], [-2, 2], [2, -2]], dtype=float)
    inputs = [
        ("identical_square", square, square),
        ("candidate_collinear_subdivision", subdivide(square), square),
        ("reference_collinear_subdivision", square, subdivide(square)),
        ("winding_cycle_closing_duplicate", np.vstack([np.roll(square[::-1], 1, axis=0), np.roll(square[::-1], 1, axis=0)[0]]), square),
        ("convex_bump_missing", square, bump),
        ("concave_notch_filled", square, notch),
        ("near_parallel_rotated", rotated, square),
        ("near_parallel_rotated_subdivided", subdivide(rotated), square),
        ("same_geometry_scaled_translated", rotated * 7.5 + [12.3, -5.7], square * 7.5 + [12.3, -5.7]),
        ("self_intersection_candidate", bowtie, square),
        ("missing_candidate", None, square),
        ("self_intersection_reference", square, bowtie),
    ]
    rows = {}
    for name, candidate, reference in inputs:
        result = gd.diagnose(candidate, reference)
        # The full evidence is JSON-safe: failures remain null, not NaN or zero.
        json.dumps(result, allow_nan=False)
        rows[name] = {
            "candidate_floor": candidate.tolist() if candidate is not None else None,
            "reference_floor": reference.tolist(), "result": result,
        }
        if result["diag_status"] == "ok":
            assert 0 <= result["diag_wall_coverage_03"] <= result["diag_wall_coverage_05"] <= 1
    scalar_keys = ("diag_wall_coverage_03", "diag_wall_coverage_05", "diag_corner_recall_05")
    for name in ("identical_square", "candidate_collinear_subdivision", "reference_collinear_subdivision", "winding_cycle_closing_duplicate"):
        result = rows[name]["result"]
        assert result["diag_status"] == "ok"
        for key in scalar_keys:
            close(result[key], 1)
        assert result["diag_reference_corner_n"] == result["diag_candidate_corner_n"] == 4
    for name in ("convex_bump_missing", "concave_notch_filled"):
        result = rows[name]["result"]
        close(result["diag_wall_coverage_03"], 14 / 18)
        close(result["diag_wall_coverage_05"], 14 / 18)
        close(result["diag_corner_recall_05"], 0.5)
        assert result["diag_reference_corner_n"] == 8 and result["diag_matched_corner_n"] == 4
    for name in ("near_parallel_rotated_subdivided", "same_geometry_scaled_translated"):
        for key in scalar_keys:
            close(rows[name]["result"][key], rows["near_parallel_rotated"]["result"][key])
    expected_status = {"self_intersection_candidate": "invalid_candidate", "missing_candidate": "missing_candidate", "self_intersection_reference": "invalid_reference"}
    for name, status in expected_status.items():
        result = rows[name]["result"]
        assert result["diag_status"] == status
        assert all(result[key] is None for key in scalar_keys)
    # Geometric counterexample to minimize-sum-then-threshold matching. This
    # private matcher probe isolates the requested lexicographic optimization.
    r = np.asarray([[0, 0], [5, 0], [50, 50]], dtype=float)
    c = np.asarray([[0.5, math.sqrt(4 * 4 - 0.5 * 0.5)], [1, 0], [50, 50]], dtype=float)
    distances = np.linalg.norm(r[:, None, :] - c[None, :, :], axis=2)
    ii, jj = linear_sum_assignment(distances)
    legacy_pairs = [(int(i), int(j), float(distances[i, j])) for i, j in zip(ii, jj)]
    pairs = gd._maximum_cardinality_min_distance(r, c, 5.0)
    assert sum(distance <= 5 for _, _, distance in legacy_pairs) == 2
    assert len(pairs) == 3
    close(sum(distance for _, _, distance in pairs), 8)
    result = {
        "scope": "12 deterministic synthetic geometry specification probes plus one isolated assignment counterexample; no real new validation output read",
        "module_sha256": hashlib.sha256(MODULE.read_bytes()).hexdigest(),
        "all_probes_passed": True,
        "geometry_probes": rows,
        "maximum_cardinality_probe": {"reference": r.tolist(), "candidate": c.tolist(), "tolerance": 5.0,
                                     "distance_matrix": distances.tolist(), "minimum_sum_pairs": legacy_pairs,
                                     "requested_lexicographic_pairs": pairs},
    }
    output = ROOT / "analysis/independent/GEOMETRY_DIAGNOSTIC_PROBES.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"geometry_probes": len(rows), "maximum_cardinality_probe": "pass", "all_passed": True,
                      "selected_scalars": {name: {key: item["result"][key] for key in ("diag_status",) + scalar_keys} for name, item in rows.items()}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
