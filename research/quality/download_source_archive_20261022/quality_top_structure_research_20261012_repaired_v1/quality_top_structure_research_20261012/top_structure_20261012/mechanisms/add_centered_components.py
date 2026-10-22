#!/usr/bin/env python3
from __future__ import annotations
import argparse
import csv
import json
import math
from pathlib import Path
import sys

from centered_height import centered_height_components
from run_mechanisms import csvwrite, dump, sha


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path.cwd())
    ap.add_argument("--results", type=Path, default=Path(__file__).resolve().parent / "results")
    args = ap.parse_args()
    root, out = args.root.resolve(), args.results.resolve()
    b = root / "previous_research/quality_calibration_research_20261011/inputs_extracted/quality_cloud_compute_review_20261010"
    sys.path.insert(0, str(b / "frozen/scope_engine/height_revision"))
    import height_revision
    design = json.loads((out / "synthetic_design.json").read_text())["cases"]
    oldrows = {x["case_id"]: x for x in csv.DictReader((out / "synthetic_components.csv").open(encoding="utf-8-sig"))}
    rows = []
    for c in design:
        old = oldrows[c["case_id"]]
        row = {k: old.get(k) for k in ["case_id", "family", "status", "Hmean", "Hlocal", "Hstar", "annotation_height_std_over_gt_mean", "same_footprint_and_constant_gt_height"]}
        if old["status"] == "available":
            z = centered_height_components(c["annotation"], c["reference"], height_module=height_revision)
            row.update(z)
            row["Hlocal_squared_minus_mean_center_squared"] = float(old["Hlocal"]) ** 2 - float(old["Hmean"]) ** 2 - z["Hcenter"] ** 2
        else:
            row["Hcenter"] = None
        rows.append(row)
    csvwrite(out / "synthetic_centered_components.csv", rows)
    real = json.loads((root / "study_quality/results/candidate_scores.json").read_text())
    geometries = json.loads((b / "inputs/current_geometry_compact.json").read_text())["geometries"]
    rows_real = []
    for c in real:
        z = centered_height_components(geometries[c["object_id"]], geometries[c["reference_object_id"]], height_module=height_revision)
        row = {k: c.get(k) for k in ["record_id", "object_id", "reference_object_id", "image_id", "image_code", "worker_id", "old_case_id", "new_case_id", "Hmean", "Hlocal", "Hstar"]}
        row.update(case_id=c.get("old_case_id") or c.get("new_case_id"), **z)
        row["Hlocal_squared_minus_mean_center_squared"] = c["Hlocal"] ** 2 - c["Hmean"] ** 2 - z["Hcenter"] ** 2
        rows_real.append(row)
    csvwrite(out / "real_39_centered_components.csv", rows_real)
    summary = {"real_count": len(rows_real), "synthetic_count": len(rows),
               "nonpositive_centered_real_profiles": [r["case_id"] for r in rows_real if not r["height_centered_profile_positive"]],
               "max_real_absolute_decomposition_failure": max(abs(r["Hlocal_squared_minus_mean_center_squared"]) for r in rows_real),
               "source_hashes": {p.name: sha(p) for p in [Path(__file__), Path(__file__).with_name("centered_height.py"), Path(__file__).with_name("centering_protocol_before_results.json")]},
               "original_geometries_changed": False, "centered_profile_is_not_a_new_reconstruction": True}
    dump(out / "centered_summary.json", summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
