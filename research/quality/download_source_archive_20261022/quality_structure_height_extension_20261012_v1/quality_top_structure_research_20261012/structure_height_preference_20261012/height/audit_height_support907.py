#!/usr/bin/env python3
"""Exact descriptive height profiles on explicitly gated development records.

No new labels, no representation repairs and no statistical prevalence claims.
"""
from pathlib import Path
import importlib.util
import json
import math
import sys
import time
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from score_existing import dump, csvwrite, sha, gates
from candidate_functions import score


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


support = module("prior_exact_support", ROOT / "top_structure_20261012/exploration/exact_height_support.py")
center = module("prior_center_height", ROOT / "top_structure_20261012/mechanisms/centered_height.py")
BASE = ROOT / "previous_research/quality_calibration_research_20261011/inputs_extracted/quality_cloud_compute_review_20261010"
sys.path.insert(0, str(BASE / "frozen/scope_engine/core"))
import quality_v11
import height_revision


def main():
    out = HERE / "results"
    out.mkdir(exist_ok=True)
    held, proof = gates()
    gate_file = ROOT / "structure_height_preference_20261012/evidence/results/development_907_filter.json"
    component_file = BASE / "results/current_components.json"
    geometry_file = BASE / "inputs/current_geometry_compact.json"
    raw_gates = json.loads(gate_file.read_text())
    eligible = [r for r in raw_gates if r["new_descriptive_development_allowed"] and not r["explicit_exposure_barriers"]]
    assert len(eligible) == 907
    assert not {r["record_id"] for r in eligible} & held
    geom = json.loads(geometry_file.read_text())["geometries"]
    components = {r["record_id"]: r for r in json.loads(component_file.read_text())}
    rows, scores, elapsed_support, elapsed_center = [], [], 0., 0.
    for i, r in enumerate(eligible):
        a, g = geom[r["object_id"]], geom[r["reference_object_id"]]
        m = dict(components[r["record_id"]])
        assert m["object_id"] == r["object_id"] and m["reference_object_id"] == r["reference_object_id"]
        start = time.perf_counter()
        z = support.paired_height_diagnostics(a, g)
        am, gm = height_revision.height_moments(a), height_revision.height_moments(g)
        elapsed_support += time.perf_counter() - start
        mu = gm["height_mean_h"]
        start = time.perf_counter()
        c = center.centered_height_components(a, g, height_module=height_revision)
        elapsed_center += time.perf_counter() - start
        m.update(c)
        m.update(annotation_height_mean_h=am["height_mean_h"], reference_height_mean_h=gm["height_mean_h"],
                 height_mean_ratio=am["height_mean_h"] / gm["height_mean_h"])
        q = score(m)
        row = {k: r.get(k) for k in ["record_id", "object_id", "reference_object_id", "image_id", "image_code", "worker_id", "room_id", "room_group", "building_id", "applicability_confirmed", "unknown_oos_pending"]}
        row.update({k: v for k, v in z.items() if k != "display_levels"})
        row.update({k: m[k] for k in ["iou_2d", "iou_3d_corner_mean", "Hmean", "Hlocal", "Hstar", "Hcenter", "dir", "flat", "S_top_deg", "S_bottom_deg"]})
        row.update(annotation_own_height_std_over_gt_mean=am["height_std_h"] / mu,
                   reference_own_height_std_over_gt_mean=gm["height_std_h"] / mu,
                   annotation_own_height_std_h=am["height_std_h"],
                   annotation_own_height_variance_h2=am["height_variance_h2"],
                   reference_own_height_std_h=gm["height_std_h"],
                   reference_own_height_variance_h2=gm["height_variance_h2"],
                   pair_count=len(a["bottom3d"]),
                   annotation_min_bottom_horizon_margin_px=float(np.min(np.arctan2(1., np.linalg.norm(np.asarray(a["bottom3d"])[:, [0,2]], axis=1))*512/math.pi)),
                   no_human_quality_label_added=True)
        peak = row["annotation_max_abs_deviation_from_own_mean_over_gt_mean"]
        p10 = row["annotation_support_gtmean_10"]
        row["very_narrow_predeclared_condition"] = peak > .2 and 0 < p10 < .01
        row["narrow_up_to5pct_condition"] = peak > .2 and 0 < p10 < .05
        row["broad_height_condition"] = peak > .2 and p10 > .5
        rows.append(row)
        scores.append({**{k: row[k] for k in ["record_id", "image_code", "image_id", "worker_id", "room_group", "applicability_confirmed"]}, **m, **q})
        if (i+1) % 200 == 0:
            print(f"height profiles and candidates {i+1}/907", flush=True)
    csvwrite(out / "development907_height_profiles.csv", rows)
    # Full score table is descriptive; unknown applicability is explicit in each row.
    # No ranking against unreviewed human labels is computed.
    dump(out / "development907_candidates.json", scores)
    diagnostic_counts = []
    for name, subset in [("all_conditional_development", rows), ("explicit_applicability", [r for r in rows if r["applicability_confirmed"]]),
                         ("applicability_not_confirmed", [r for r in rows if not r["applicability_confirmed"]])]:
        for peak_threshold in [.1, .2, .4]:
            for support_threshold in [.001, .01, .05]:
                hits = [r for r in subset if r["annotation_max_abs_deviation_from_own_mean_over_gt_mean"] > peak_threshold
                        and 0 < r["annotation_support_gtmean_10"] < support_threshold]
                diagnostic_counts.append({"subset": name, "denominator": len(subset), "peak_relative_threshold": peak_threshold,
                    "support_of_above10pct_height_below_fraction": support_threshold, "records": len(hits),
                    "images": len({r["image_id"] for r in hits}), "record_ids": [r["record_id"] for r in hits],
                    "interpretation": "numeric condition frequency, not human severity or population prevalence"})
    csvwrite(out / "height_support_condition_counts.csv", diagnostic_counts)
    narrow = [r for r in rows if r["very_narrow_predeclared_condition"]]
    broader = [r for r in rows if r["narrow_up_to5pct_condition"]]
    broad = [r for r in rows if r["broad_height_condition"]]
    summary = {"rows": len(rows), "images": len({r["image_id"] for r in rows}), "buildings": len({r["building_id"] for r in rows}),
               "explicit_applicability": sum(r["applicability_confirmed"] for r in rows),
               "unknown_applicability": sum(not r["applicability_confirmed"] for r in rows),
               "gates": proof, "new_human_labels": 0,
               "predeclared_very_narrow_peak_gt20pct_support_gt10pct_lt1pct": len(narrow),
               "predeclared_narrow_record_ids": [r["record_id"] for r in narrow],
               "narrow_with_support_up_to5pct": len(broader),
               "narrow_up_to5pct_record_ids": [r["record_id"] for r in broader],
               "broad_peak_gt20pct_support_gt10pct_gt50pct": len(broad),
               "maximum_centered_height_peak_relative": max(r["annotation_max_abs_deviation_from_own_mean_over_gt_mean"] for r in rows),
               "support_diagnostic_elapsed_seconds": elapsed_support,
               "centered_height_elapsed_seconds": elapsed_center,
               "runtime_is_single_run_not_benchmark": True,
               "visual_status": "No claim of visually inspecting all907; specific selected images must be reviewed separately.",
               "input_sha256": {str(p.relative_to(ROOT)): sha(p) for p in [gate_file, component_file, geometry_file]},
               "script_sha256": sha(Path(__file__)), "candidate_config_sha256": sha(HERE / "candidate_config.json")}
    summary["log_addendum_sha256"] = sha(HERE / "candidate_config_log_addendum.json")
    dump(out / "height_support907_summary.json", summary)
    dump(out / "narrow_height_selected_records.json", broader)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
