#!/usr/bin/env python3
"""Reproducible geometric controls; no human labels, no point repairs."""
from pathlib import Path
import importlib.util
import math
import sys
import json
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from score_existing import dump, csvwrite, sha, actual_mean_ratio
from candidate_functions import score, parameter_terms


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


helper = module("prior_height_geometry_helpers", ROOT / "top_structure_20261012/mechanisms/run_mechanisms.py")
center = module("prior_centered_height", ROOT / "top_structure_20261012/mechanisms/centered_height.py")
core = ROOT / "previous_research/quality_calibration_research_20261011/inputs_extracted/quality_cloud_compute_review_20261010/frozen/scope_engine"
sys.path.insert(0, str(core / "core"))
import quality_v11
import height_revision


def displacement_rms(annotation, reference):
    """Top boundary 3-D displacement over unchanged reference-edge parameter.

    This control correspondence is known by construction, never obtained by
    GT-nearest matching on real annotations. Horizontal shear affects both
    floor and top; height controls affect top only. Thus this is not an
    equality of all raw annotation point errors or a human severity claim.
    """
    b = np.asarray(reference["bottom3d"])
    ell = np.linalg.norm(np.roll(b[:, [0, 2]], -1, axis=0) - b[:, [0, 2]], axis=1)
    d = np.asarray(annotation["top3d"]) - np.asarray(reference["top3d"])
    dn = np.roll(d, -1, axis=0)
    integral = np.sum(ell * (np.sum(d*d, axis=1) + np.sum(d*dn, axis=1) + np.sum(dn*dn, axis=1)) / 3)
    return math.sqrt(float(integral / ell.sum()))


def design():
    cases = []
    mu = 2.4
    rectangle = helper.RECT
    z_rms_at_scale1 = math.sqrt(7) / 3
    def add(cid, family, a, g, **meta):
        cases.append({"case_id": cid, "family": family, "annotation": a, "reference": g,
                      "evidence_class": "synthetic_geometric_control_no_human_grade", **meta})
    for floor_scale in [0.5, 2., 10.]:
        q = rectangle * floor_scale
        g = helper.geometry(q, mu)
        for eps in [.05, .1, .2]:
            delta = eps * mu
            k = delta / (floor_scale * z_rms_at_scale1)
            sheared = q.copy()
            sheared[:, 0] += k * sheared[:, 1]
            profiles = {
                "structure_shear": helper.geometry(sheared, mu),
                "global_up": helper.geometry(q, mu + delta),
                "global_down": helper.geometry(q, mu - delta),
                "local_tilt": helper.geometry(q, mu + delta/z_rms_at_scale1*np.array([-1., -1., 1., 1.])),
                "local_alternating": helper.geometry(q, mu + delta*math.sqrt(3)*np.array([-1., 1., -1., 1.])),
            }
            for mode, a in profiles.items():
                measured = displacement_rms(a, g) / mu
                assert abs(measured - eps) < 1e-14
                add(f"matched_s{floor_scale:g}_e{eps:g}_{mode}", "matched_reference_top_boundary_displacement", a, g,
                    horizontal_scale=floor_scale, target_relative_rms_displacement=eps,
                    exact_relative_rms_displacement=measured, mode=mode,
                    shear_corner_departure_deg=math.degrees(math.atan(k)) if mode == "structure_shear" else None,
                    comparison_caveat="Equal reference-top-boundary 3D RMS displacement divided by GT wall height; not a human grade equivalence; shear also moves bottom.")
    for floor_scale in [.5, 10.]:
        q = rectangle * floor_scale
        for ratio in [.1, .25, .5, 1., 1.5, 2., 3., 5.]:
            add(f"global_extreme_s{floor_scale:g}_r{ratio:g}", "global_height_extreme", helper.geometry(q, mu*ratio), helper.geometry(q, mu),
                horizontal_scale=floor_scale, wall_height_ratio=ratio,
                camera_above_annotation_roof=mu*ratio < 1,
                note="Positive wall height ensures mathematical geometric availability; if roof is below camera, annotation is an extreme scene error, not an accepted room reference.")
    q = rectangle * 2
    g = helper.geometry(q, mu)
    local = .1 * mu / z_rms_at_scale1 * np.array([-1., -1., 1., 1.])
    for mode, bias, variation in [("global_only", .2*mu, 0*local), ("local_only", 0., local),
                                  ("both_up", .2*mu, local), ("both_down", -.2*mu, local)]:
        add("independent_height_"+mode, "global_and_local_independent_controls", helper.geometry(q, mu+bias+variation), g,
            mode=mode, intended_Hmean=abs(bias)/mu, intended_own_Hlocal_centered=.1 if np.any(variation) else 0,
            interpretation="These have identical footprint and constant GT, so global bias and centered profile variance have exact orthogonal squared-error identity.")
    return cases


def main():
    out = HERE / "results"
    out.mkdir(exist_ok=True)
    cases = design()
    for c in cases:
        c["annotation_erp_1024x512"] = helper.erp_points(c["annotation"]).tolist()
        c["reference_erp_1024x512"] = helper.erp_points(c["reference"]).tolist()
        wall_heights = np.asarray(c["annotation"]["top3d"])[:, 1] - np.asarray(c["annotation"]["bottom3d"])[:, 1]
        c["camera_inside_height_assumption"] = bool(np.all(wall_heights > 1.0))
        c["physical_scope_note"] = "Boundary tops all above fixed camera height" if c["camera_inside_height_assumption"] else "Computable positive walls, but annotated top lies below fixed camera; domain-extrapolation diagnosis only"
    dump(out / "matched_control_design.json", {"protocol_sha256": sha(HERE / "protocol_before_results.json"), "cases": cases})
    rows, details, terms = [], [], []
    for i, case in enumerate(cases):
        a, g = case["annotation"], case["reference"]
        computed = quality_v11.score_geometry(a, g)
        row = {k: v for k, v in case.items() if k not in ("annotation", "reference", "annotation_erp_1024x512", "reference_erp_1024x512")}
        row["status"] = computed["status"]
        if row["status"] == "available":
            m = computed["metrics"]
            row.update({k: m[k] for k in ["iou_2d", "iou_3d_corner_mean", "Hmean", "Hlocal", "Hstar", "dir", "flat", "S_top_deg", "S_bottom_deg"]})
            row.update(center.centered_height_components(a, g, height_module=height_revision))
            row.update(actual_mean_ratio(a, g))
            row.update(score(row))
            terms.append({"case_id": case["case_id"], "parameters": parameter_terms(row)})
        else:
            row["reason_codes"] = computed["reason_codes"]
        rows.append(helper.clean(row))
        details.append({"case_id": case["case_id"], "engine": helper.clean(computed)})
        if (i+1) % 10 == 0:
            print(f"matched controls {i+1}/{len(cases)}", flush=True)
    csvwrite(out / "matched_control_scores.csv", rows)
    dump(out / "matched_control_details.json", details)
    dump(out / "matched_control_terms.json", terms)
    dump(out / "matched_control_manifest.json", {"rows": len(rows), "available": sum(r["status"] == "available" for r in rows),
         "camera_inside_height_assumption_count": sum(r["camera_inside_height_assumption"] for r in rows),
         "computability_does_not_mean_physical_scope_acceptance": True,
         "new_synthetic_human_labels": 0, "new_original_data_changes": 0, "script_sha256": sha(Path(__file__)),
         "candidate_function_sha256": sha(HERE / "candidate_functions.py"), "config_sha256": sha(HERE / "candidate_config.json"),
         "log_addendum_sha256": sha(HERE / "candidate_config_log_addendum.json"),
         "unchanged_geometry_engine_sha256": sha(core / "core/quality_v11.py")})
    print(json.dumps({"controls": len(rows), "available": sum(r["status"] == "available" for r in rows)}))


if __name__ == "__main__":
    main()
