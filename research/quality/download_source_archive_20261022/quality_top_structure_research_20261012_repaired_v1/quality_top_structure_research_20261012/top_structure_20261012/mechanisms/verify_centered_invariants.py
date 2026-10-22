#!/usr/bin/env python3
"""Mathematical input invariants of the new centered-height component.

These are temporary deterministic transforms, not data augmentation, quality
labels, or a new human-error experiment. Original geometries are not changed.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
from centered_height import centered_height_components
from run_mechanisms import dump, csvwrite


def digest(x):
    return hashlib.sha256(json.dumps(x, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def height_transform(g, scale=1., shift=0.):
    b = np.asarray(g["bottom3d"], float)
    t = np.asarray(g["top3d"], float).copy()
    t[:, 1] = b[:, 1] + scale*(t[:, 1]-b[:, 1]) + shift
    return {"bottom3d": b.tolist(), "top3d": t.tolist()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path.cwd())
    ap.add_argument("--results", type=Path, default=Path(__file__).resolve().parent / "results")
    args = ap.parse_args()
    root, out = args.root.resolve(), args.results.resolve()
    b = root / "previous_research/quality_calibration_research_20261011/inputs_extracted/quality_cloud_compute_review_20261010"
    sys.path.insert(0, str(b / "frozen/scope_engine/height_revision"))
    import height_revision
    controls = json.loads((out / "synthetic_design.json").read_text())["cases"]
    cases = [{"case_id": c["case_id"], "annotation": c["annotation"], "reference": c["reference"], "cohort": "synthetic"} for c in controls if c["annotation"] is not None]
    real = json.loads((root / "study_quality/results/candidate_scores.json").read_text())
    gs = json.loads((b / "inputs/current_geometry_compact.json").read_text())["geometries"]
    cases.extend({"case_id": c.get("old_case_id") or c.get("new_case_id"), "annotation": gs[c["object_id"]], "reference": gs[c["reference_object_id"]], "cohort": "real_existing_development"} for c in real)
    rows = []
    for c in cases:
        a, g = c["annotation"], c["reference"]
        before = digest([a, g])
        h = centered_height_components(a, g, height_module=height_revision)["Hcenter"]
        shift = centered_height_components(height_transform(a, shift=0.3), g, height_module=height_revision)["Hcenter"]
        scale = centered_height_components(height_transform(a, scale=1.7), height_transform(g, scale=1.7), height_module=height_revision)["Hcenter"]
        unchanged = before == digest([a, g])
        rows.append({"case_id": c["case_id"], "cohort": c["cohort"], "Hcenter": h,
                     "global_annotation_height_shift_0p3h_absolute_error": abs(h-shift),
                     "both_wall_heights_scaled_1p7_absolute_error": abs(h-scale),
                     "source_arrays_unchanged": unchanged})
    csvwrite(out / "centered_invariant_checks.csv", rows)
    summary = {"cases_checked": len(rows), "max_global_shift_absolute_error": max(r["global_annotation_height_shift_0p3h_absolute_error"] for r in rows),
               "max_common_height_scale_absolute_error": max(r["both_wall_heights_scaled_1p7_absolute_error"] for r in rows),
               "all_original_arrays_unchanged": all(r["source_arrays_unchanged"] for r in rows),
               "temporary_transforms_are_not_human_error_distribution": True,
               "checks_passed": all(r["source_arrays_unchanged"] and r["global_annotation_height_shift_0p3h_absolute_error"] < 1e-12 and r["both_wall_heights_scaled_1p7_absolute_error"] < 1e-12 for r in rows)}
    dump(out / "centered_invariant_summary.json", summary)
    assert summary["checks_passed"], summary
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
