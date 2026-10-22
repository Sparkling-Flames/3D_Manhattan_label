#!/usr/bin/env python3
from __future__ import annotations
import argparse
import copy
import csv
import hashlib
import json
import math
from pathlib import Path
import sys
import time
import numpy as np

from exact_height_support import DISPLAY_LEVELS, paired_height_diagnostics


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def csvwrite(path, rows):
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def readcsv(path):
    return list(csv.DictReader(path.open(encoding="utf-8-sig")))


def fnum(row, key):
    return float(row[key]) if row.get(key) not in (None, "", "None") else None


def subdivide_first_edge(record, n=7):
    result = {}
    for key in ("top3d", "bottom3d"):
        q = np.asarray(record[key], float)
        inserted = [(1-u)*q[0] + u*q[1] for u in np.arange(1, n+1)/(n+1)]
        result[key] = np.asarray([q[0], *inserted, *q[1:]]).tolist()
    return result


def reorder(record, reverse=False):
    return {key: (np.asarray(record[key])[::-1] if reverse else np.roll(np.asarray(record[key]), -1, axis=0)).tolist()
            for key in ("top3d", "bottom3d")}


def geometry_digest(a, g):
    return hashlib.sha256(json.dumps([a, g], sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path.cwd())
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "results")
    args = ap.parse_args()
    root, out = args.root.resolve(), args.out.resolve()
    work = Path(__file__).resolve().parent
    out.mkdir(parents=True, exist_ok=True)
    marker = root / "top_structure_20261012/CORE_COMPLETION_BEFORE_EXPLORATION.json"
    assert marker.exists(), "core_completion_marker_required_before_free_exploration"
    mech = root / "top_structure_20261012/mechanisms/results"
    design = json.loads((mech / "synthetic_design.json").read_text())["cases"]
    raw_control_rows = {r["case_id"]: r for r in readcsv(mech / "synthetic_components.csv")}
    centered_controls = {r["case_id"]: r for r in readcsv(mech / "synthetic_centered_components.csv")}
    items = []
    for c in design:
        r = raw_control_rows[c["case_id"]]
        items.append({"case_id": c["case_id"], "cohort": "synthetic", "family": c["family"],
                      "annotation": c["annotation"], "reference": c["reference"], "status": r["status"],
                      "parent_metadata": c,
                      "baselines": {**{k: fnum(r, k) for k in ["Hmean", "Hlocal", "Hstar", "flat", "S_top_deg", "Q_v11", "Q_no_topS"]},
                                    "Hcenter": fnum(centered_controls[c["case_id"]], "Hcenter")}})
    real_file = root / "study_quality/results/candidate_scores.json"
    b = root / "previous_research/quality_calibration_research_20261011/inputs_extracted/quality_cloud_compute_review_20261010"
    geometry_file = b / "inputs/current_geometry_compact.json"
    gs = json.loads(geometry_file.read_text())["geometries"]
    real = json.loads(real_file.read_text())
    cr = {r["record_id"]: r for r in readcsv(mech / "real_39_centered_components.csv")}
    for c in real:
        cid = c.get("old_case_id") or c.get("new_case_id")
        items.append({"case_id": cid, "cohort": "real_development", "family": c["evidence_layer"],
                      "annotation": gs[c["object_id"]], "reference": gs[c["reference_object_id"]], "status": "available",
                      "parent_metadata": {k: c[k] for k in ["record_id", "object_id", "reference_object_id", "image_id", "image_code", "worker_id", "original_holdout", "scope_reference_acceptance"]},
                      "baselines": {**{k: c[k] for k in ["Hmean", "Hlocal", "Hstar", "flat", "S_top_deg", "Q_v11", "Q_no_topS"]},
                                    "Hcenter": fnum(cr[c["record_id"]], "Hcenter")}})
    rows, invariants, analytic = [], [], []
    elapsed = 0.0
    for c in items:
        a, g = c["annotation"], c["reference"]
        row = {"case_id": c["case_id"], "cohort": c["cohort"], "family": c["family"], "status": c["status"], **c["baselines"]}
        if c["cohort"] == "real_development":
            row.update(c["parent_metadata"])
        if c["status"] != "available" or a is None:
            row.update(annotation_height_range_over_gt_mean=None, annotation_support_gtmean_10=None,
                       unavailable_reason="controlled_bottom_crosses_horizon")
            rows.append(row)
            continue
        before = geometry_digest(a, g)
        start = time.perf_counter()
        features = paired_height_diagnostics(a, g)
        elapsed += time.perf_counter() - start
        row.update({k: v for k, v in features.items() if k != "display_levels"})
        rows.append(row)
        numeric_keys = [k for k, v in features.items() if isinstance(v, (int, float)) and not isinstance(v, bool)]
        variants = {"cyclic_start": reorder(a), "reversed_ring": reorder(a, reverse=True), "seven_collinear_points_on_first_edge": subdivide_first_edge(a)}
        for name, aa in variants.items():
            changed = paired_height_diagnostics(aa, g)
            invariants.append({"case_id": c["case_id"], "cohort": c["cohort"], "representation_variant": name,
                               "max_numeric_absolute_error": max(abs(features[k]-changed[k]) for k in numeric_keys),
                               "source_arrays_unchanged": before == geometry_digest(a, g)})
        if c["family"] in {"localized_spike", "narrow_spike_quadrature_probe"}:
            meta = c["parent_metadata"]
            amp = float(meta["amplitude_h"])/2.4
            support = float(meta["support_perimeter_fraction"])
            for level in DISPLAY_LEVELS:
                # All predefined peaks have A*p/2 below the smallest displayed
                # level; hence no negative-baseline region exceeds the cutoff.
                assert amp*support/2 < level
                expected = support * max(0., min(1., 1-level/amp-support/2))
                value = features[f"annotation_support_gtmean_{int(round(level*100)):02d}"]
                analytic.append({"case_id": c["case_id"], "display_level": level,
                                 "exact_piecewise_support": value, "independent_triangle_formula": expected,
                                 "absolute_error": abs(value-expected)})
    csvwrite(out / "amplitude_support_all_110_rows.csv", rows)
    csvwrite(out / "representation_invariance_327.csv", invariants)
    csvwrite(out / "triangular_spike_analytic_checks.csv", analytic)
    valid = [r for r in rows if r["status"] == "available"]
    summary = {
        "core_completion_marker_sha256": sha(marker), "core_completion_created_utc": json.loads(marker.read_text())["created_utc"],
        "free_exploration_actual_execution_utc": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "source_hashes": {str(p.relative_to(root)): sha(p) for p in [real_file, geometry_file, mech/"synthetic_design.json", work/"protocol_before_results.json", work/"exact_height_support.py", Path(__file__)]},
        "rows": len(rows), "valid_profiles": len(valid), "synthetic_valid": sum(r["cohort"] == "synthetic" for r in valid),
        "real_development": sum(r["cohort"] == "real_development" for r in valid), "missing_rows_retained": len(rows)-len(valid),
        "invariance_checks": len(invariants), "invariance_max_absolute_error": max(r["max_numeric_absolute_error"] for r in invariants),
        "all_source_arrays_unchanged": all(r["source_arrays_unchanged"] for r in invariants),
        "triangle_formula_checks": len(analytic), "triangle_formula_max_absolute_error": max(r["absolute_error"] for r in analytic),
        "display_support_monotone_for_all_profiles": all(r[f"{role}_support_gtmean_10"] + 1e-14 >= r[f"{role}_support_gtmean_20"] and r[f"{role}_support_gtmean_20"] + 1e-14 >= r[f"{role}_support_gtmean_40"] for r in valid for role in ["annotation", "reference"]),
        "actual_compute_seconds_for_109_profiles_excluding_io_and_verification": elapsed,
        "algorithmic_cost": "O(n) per profile for fixed three display levels; no nearest matching, global sampling grid or model fit",
        "new_score_penalties": 0, "human_thresholds_fitted": 0, "synthetic_human_grades_assigned": 0,
    }
    assert summary["invariance_max_absolute_error"] < 1e-12
    assert summary["triangle_formula_max_absolute_error"] < 1e-12
    assert summary["all_source_arrays_unchanged"] and summary["display_support_monotone_for_all_profiles"]
    dump(out / "summary.json", summary)
    selected = [r for r in rows if r["case_id"] in {"T20", "S071", "S107", "S034", "T19"} and r["cohort"] == "real_development"]
    dump(out / "selected_real_cases.json", selected)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
