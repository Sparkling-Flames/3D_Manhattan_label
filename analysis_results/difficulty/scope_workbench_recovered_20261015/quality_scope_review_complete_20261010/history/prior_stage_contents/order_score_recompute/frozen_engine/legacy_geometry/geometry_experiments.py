#!/usr/bin/env python3
"""Reproduce geometric component comparisons and known-geometry controls.

python geometry_experiments.py --source ../../../source/oct8-pro-quality-handoff --out results
All paths are command-line inputs. Original inputs are read only. All controls
are separate synthetic/perturbed copies; they are never new human labels.
"""
import argparse
import copy
import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

from audit_geometry import (
    area_metrics, compare_metrics, own_metrics, ring_status, write_csv, write_json,
)
from geometric_components import additional_components, spherical_sym_distance


def ring_only(record):
    return {k: copy.deepcopy(record[k]) for k in ("top3d", "bottom3d")}


def room(foot, top=1.0):
    foot = np.asarray(foot, dtype=float)
    y = np.full(len(foot), top) if np.isscalar(top) else np.asarray(top, dtype=float)
    return {
        "bottom3d": np.column_stack([foot[:, 0], np.full(len(foot), -1.0), foot[:, 1]]).tolist(),
        "top3d": np.column_stack([foot[:, 0], y, foot[:, 1]]).tolist(),
    }


def map_rings(record, fun):
    return {k: fun(np.array(record[k], dtype=float), k).tolist() for k in ("top3d", "bottom3d")}


def xz_scale(record, factor):
    def transform(p, key):
        p[:, [0, 2]] *= factor
        return p
    return map_rings(record, transform)


def translate(record, dx, dz=0):
    return map_rings(record, lambda p, key: p + np.array([dx, 0.0, dz]))


def top_shift(record, delta):
    return map_rings(record, lambda p, key: p + np.array([0.0, delta if key == "top3d" else 0.0, 0.0]))


def top_warp(record, amplitude, local=False):
    def transform(p, key):
        if key == "top3d":
            if local:
                p[0, 1] += amplitude
            else:
                p[:, 1] += amplitude * np.where(np.arange(len(p)) % 2, 1, -1)
        return p
    return map_rings(record, transform)


def subdivision(record, factor=2):
    return map_rings(record, lambda p, key: np.array([a + t * (b-a) for a, b in zip(p, np.roll(p, -1, axis=0)) for t in np.arange(factor) / factor]))


def zigzag_square(amplitude, subdivisions_per_wall):
    """Real noncollinear perturbation; NOT a segmentation-invariance example.

    Use a1h-square to keep tiny amplitudes visible to directional regularity at
    modest node counts. Alternating signed offsets are normal to each wall;
    original corners remain fixed. There are at most64total vertices.
    """
    foot = np.array([[-.5,-.5],[.5,-.5],[.5,.5],[-.5,.5]])
    vertices = []
    for a,b in zip(foot, np.roll(foot,-1,axis=0)):
        e=b-a
        normal=np.array([e[1],-e[0]])/np.linalg.norm(e)
        for k in range(subdivisions_per_wall):
            delta = 0. if k==0 else amplitude * (-1 if k%2 else 1)
            vertices.append(a + k/subdivisions_per_wall*e + delta*normal)
    return room(vertices)


def uniform_angular_top_shift(record, delta_deg):
    def transform(p, key):
        if key == "top3d":
            radius = np.linalg.norm(p[:, [0, 2]], axis=1)
            elevation = np.arctan2(p[:, 1], radius) + np.deg2rad(delta_deg)
            if np.any(np.abs(elevation) >= np.pi/2 - 1e-6):
                raise ValueError("perturbation_crosses_pole")
            p[:, 1] = radius * np.tan(elevation)
        return p
    return map_rings(record, transform)


def lowest_elevation_pixel_shift(record, canonical_pixels):
    """Move only deepest lower vertex's elevation toward horizon, keep top ray.

    One canonical pixel is 180/512 degrees and two source-image pixels.
    The paired upper point keeps its old angular elevation: its inferred radius
    and height change with the lower point, exactly as the conditional model.
    """
    b = np.asarray(record["bottom3d"], dtype=float).copy()
    t = np.asarray(record["top3d"], dtype=float).copy()
    radius = np.linalg.norm(b[:, [0, 2]], axis=1)
    ix = int(np.argmax(radius))
    old_phi = np.arctan2(-1.0, radius[ix])
    new_phi = old_phi + canonical_pixels * np.pi / 512
    if new_phi >= -1e-4:
        raise ValueError("perturbation_reaches_horizon")
    new_radius = -1.0 / np.tan(new_phi)
    factor = new_radius / radius[ix]
    b[ix, [0, 2]] *= factor
    t[ix] *= factor
    return dict(bottom3d=b.tolist(), top3d=t.tolist()), dict(
        altered_vertex=ix,
        point_radius_before_h=float(radius[ix]),
        point_radius_delta_h=float(new_radius-radius[ix]),
        point_elevation_delta_deg=float(canonical_pixels * 180 / 512),
        canonical_pixel_delta=canonical_pixels,
    )


def numeric_main(row):
    fields = ["iou", "C", "U", "B", "T", "F", "dir", "flat", "omission", "extension", "height_mean_h", "height_internal_rms_h", "height_internal_relative_rms"]
    return {k: float(row[k]) if row.get(k, "") != "" else None for k in fields}


def compute_control(a, g, scales, n):
    base = compare_metrics(a, g, scales)
    return additional_components(a, g, n, base)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--sphere-samples", type=int, default=2048)
    args = parser.parse_args()
    source = args.source.resolve()
    out = args.out.resolve()
    if out == source or source in out.parents:
        raise ValueError("Output must be outside original source")
    out.mkdir(parents=True, exist_ok=True)
    n = args.sphere_samples
    geom_path = source / "inputs/frozen_geometry.json"
    data = json.loads(geom_path.read_text(encoding="utf-8"))
    main_rows = list(csv.DictReader((source / "data/unified36_existing_metrics.csv").open(encoding="utf-8-sig")))
    frozen48 = {(r["record_id"],r["reference_version"],r["reference_id"]): r
                for r in csv.DictReader((source / "data/all48_reference_specific_metrics.csv").open(encoding="utf-8-sig"))}
    main_by_id = {r["record_id"]: r for r in main_rows}
    scales = data["scales"]
    all_refs = []
    real = []
    controls = []
    control_geometry = []
    convergence = []
    invariance = []
    orientation = []
    height_checks = []
    used_refs = []

    for im in data["images"]:
        gt = {r["version"]: r for r in im["groundtruths"]}
        version = main_by_id[im["annotations"][0]["id"]]["reference_version"]
        gmain = gt[version]
        used_refs.append((im["code"], gmain))
        for a in im["annotations"]:
            original = main_by_id[a["id"]]
            for ref_version, g in gt.items():
                base = numeric_main(original) if ref_version == original["reference_version"] else compare_metrics(a, g, scales)
                m = additional_components(a, g, n, base)
                row = dict(
                    review_id=a["reviewId"], record_id=a["id"], image_code=im["code"],
                    reference_version=ref_version, reference_id=g["id"],
                    is_rating_reference=ref_version == original["reference_version"],
                    human_score_original=int(original["human_score_original"]),
                    pair_count=len(a["bottom3d"]), **m,
                )
                all_refs.append(row)
                frozen = frozen48[(a["id"],ref_version,g["id"])]
                expected_hrel = float(frozen["height_mean_relative_error"])
                expected_ref_height = float(frozen["height_mean_h"])-float(frozen["height_mean_signed_h"])
                height_checks.append(dict(review_id=a["reviewId"],record_id=a["id"],reference_version=ref_version,reference_id=g["id"],
                                          frozen_height_mean_relative_error=expected_hrel,
                                          computed_height_mean_relative_error=m["height_mean_relative_error"],
                                          frozen_reference_height_mean_h_from_mean_minus_signed_error=expected_ref_height,
                                          reference_height_mean_h=m["reference_height_mean_h"],
                                          reference_height_abs_delta=abs(expected_ref_height-m["reference_height_mean_h"]),
                                          abs_delta=abs(expected_hrel-m["height_mean_relative_error"])))
                if ref_version == original["reference_version"]:
                    real.append(row)
                    for ring in ["top3d", "bottom3d"]:
                        coarse = m["S_top_deg" if ring == "top3d" else "S_bottom_deg"]
                        fine = spherical_sym_distance(a[ring], g[ring], 2*n)
                        convergence.append(dict(review_id=a["reviewId"], ring=ring, n=n, estimate_deg=coarse, double_n_estimate_deg=fine, abs_delta_deg=abs(coarse-fine)))
                    split = subdivision(a, 3)
                    split_m = additional_components(split, g, n)
                    keys = ["iou", "C", "T", "F", "dir", "flat", "height_internal_relative_rms", "S_top_deg", "S_bottom_deg"]
                    for k in keys:
                        invariance.append(dict(review_id=a["reviewId"], metric=k, original=m[k], subdivision_3=split_m[k], abs_delta=abs(m[k]-split_m[k])))
                    for mode in ["reverse", "roll1", "rollhalf"]:
                        if mode == "reverse":
                            modified = map_rings(a, lambda p, key: p[::-1])
                        else:
                            shift = 1 if mode == "roll1" else len(a["bottom3d"])//2
                            modified = map_rings(a, lambda p, key: np.roll(p, shift, axis=0))
                        mod_metrics = additional_components(modified, g, n)
                        for k in keys:
                            orientation.append(dict(review_id=a["reviewId"], mode=mode, metric=k, original=m[k], variant=mod_metrics[k], abs_delta=abs(m[k]-mod_metrics[k])))
    write_csv(out / "real_metrics36.csv", real)
    write_csv(out / "reference_metrics48.csv", all_refs)
    write_csv(out / "spherical_quadrature_convergence72.csv", convergence)
    write_csv(out / "subdivision_invariance324.csv", invariance)
    write_csv(out / "orientation_start_sensitivity972.csv", orientation)
    write_csv(out / "height_component_frozen_comparison48.csv", height_checks)

    def add(case_id, family, a, g, severity, image_code="synthetic_rectangle", interpretation="", extra=None):
        metadata = dict(case_id=case_id, family=family, source_image=image_code, severity=severity,
                        kind="known_geometry_control_NOT_human_label", interpretation=interpretation)
        if extra:
            metadata.update(extra)
        try:
            metrics = compute_control(a, g, scales, n)
        except ValueError as error:
            controls.append(dict(**metadata, status="invalid_perturbation_not_repaired", error=str(error)))
            return
        controls.append(dict(**metadata, status="valid", **metrics))
        control_geometry.append(dict(**metadata, annotation=ring_only(a), reference=ring_only(g)))

    rect = room([[-3, -2], [3, -2], [3, 2], [-3, 2]])
    for factor in [1., .99, .95, .9, .75, .5, .25, .1, 1.01, 1.05, 1.1, 1.25, 1.5, 2., 4.]:
        add(f"rectangle_scale_{factor:g}", "symmetric_scale", xz_scale(rect, factor), rect, factor,
            interpretation="Perfectly regular shape. For factor<=1, coverage and IoU=factor^2 exactly; intrinsic regularity cannot certify quality.")
    for fraction in [0, .0025, .005, .01, .02, .05, .1, .2, .4, .8]:
        add(f"rectangle_translation_{fraction:g}", "translation_relative_room", translate(rect, fraction*math.sqrt(24)), rect, fraction,
            interpretation="Whole room shifted in x, top and floor move together; own regularity remains perfect.")
    for delta in [0., .005, .01, .02, .05, .1, .2, .4, .8, 1.6, 3.2, 10., 100.]:
        add(f"rectangle_top_shift_{delta:g}", "top_shift_h", top_shift(rect, delta), rect, delta,
            interpretation="Identical footprint and perfectly flat roof; systematic top height disagreement must be visible in reference component.")
    for amplitude in [.005, .01, .02, .05, .1, .2, .4, .8]:
        add(f"rectangle_warp_{amplitude:g}", "top_alternating_warp_h", top_warp(rect, amplitude), rect, amplitude,
            interpretation="Identical footprint and zero mean top warp; conditional volume IoU alone misses this deformation.")
        add(f"rectangle_local_top_{amplitude:g}", "top_one_vertex_warp_h", top_warp(rect, amplitude, True), rect, amplitude,
            interpretation="Identical footprint, one actual roof point displaced; local error, no change to node count.")
    base_shift = translate(rect, .2)
    for factor in [.25, .5, 1., 2., 4.]:
        add(f"xz_size_relative_shift_{factor:g}", "same_relative_xz_error_different_room_size", xz_scale(base_shift, factor), xz_scale(rect, factor), factor,
            interpretation="Camera-floor h remains1; shape and relative x-z displacement identical. T/F grow with room size, T/F/sqrt(A_GT) stays constant; spherical angular displacement changes with view geometry.")
        add(f"xz_size_fixed_top_shift_{factor:g}", "same_h_top_error_different_room_size", top_shift(xz_scale(rect, factor), .2), xz_scale(rect, factor), factor,
            interpretation="Same0.2h top error in rooms of different floor size; dividing3-D distance by sqrt(A_GT) reduces penalty in larger rooms.")
        add(f"xz_size_fixed_angle_top_shift_{factor:g}", "same_angular_top_error_different_room_size", uniform_angular_top_shift(xz_scale(rect, factor), 1.), xz_scale(rect, factor), factor,
            interpretation="At each corner, top point shifts by1degree in elevation; 3-D displacements grow in large/far rooms; arc interpolation means mean angular curve error need not equal1degree.")
    for factor in [1, 2, 3, 4, 8]:
        add(f"rectangle_subdivision_{factor:g}", "same_curves_redundant_vertices", subdivision(base_shift, factor), rect, factor,
            interpretation="Exact same3-D curve loci, more collinear vertices; quality must be identical apart from numerical precision.")
    zigzag_ref = room([[-.5,-.5],[.5,-.5],[.5,.5],[-.5,.5]])
    for amplitude in [.001, .005, .01]:
        for frequency in [2,8,16]:
            add(f"tiny_zigzag_a{amplitude:g}_vertices{4*frequency}", "tiny_high_frequency_real_zigzag", zigzag_square(amplitude, frequency), zigzag_ref, amplitude,
                interpretation="At fixed tiny displacement amplitude, added noncollinear bends can enlarge intrinsic angular direction residual; this is a real curve perturbation, not a collinear-node invariance check.",
                extra=dict(subdivisions_per_wall=frequency, node_count=4*frequency, wall_length_h=1.))
    # One filled recess erases real turns while remaining perfectly regular.
    for depth in [.005, .02, .05, .1, .25, .5, 1., 1.5]:
        notch = room([[-3, -2], [3, -2], [3, 2], [1, 2], [1, 2-depth], [-1, 2-depth], [-1, 2], [-3, 2]])
        add(f"filled_notch_depth_{depth:g}", "fill_reference_concavity", rect, notch, depth,
            interpretation="Omitting a concave turn adds floor area (extension), not omission; intrinsic direction and flatness are perfect. Tiny shallow turns may have tiny aggregate geometric effects.")
    for halfwidth in [.5, .2, .1, .05, .01]:
        notch = room([[-3,-2],[3,-2],[3,2],[halfwidth,2],[halfwidth,1],[-halfwidth,1],[-halfwidth,2],[-3,2]])
        add(f"filled_notch_width_{halfwidth:g}", "narrow_deep_missing_concavity", rect, notch, halfwidth,
            interpretation="A narrow1h-deep recess has little area but substantial local boundary depth; test the integrated-boundary blind spot and whether angular curves help.")

    # Real-reference perturbations preserve the actual fixed target model.
    for image_code, ref in used_refs:
        label = image_code.split("-")[0]
        add(f"{label}_reference_self", "real_reference_self", ref, ref, 0., image_code)
        size = math.sqrt(area_metrics(ref, ref)["reference_area_h2"])
        for factor in [.99, .95, .75, .5, .25]:
            add(f"{label}_shrink_{factor:g}", "real_reference_homothetic_shrink", xz_scale(ref, factor), ref, factor, image_code,
                "Preserves angular footprint directions about camera. Non-star polygons need not form exact nested subsets; use computed IoU.")
        for fraction in [.005, .02, .05, .1, .2]:
            add(f"{label}_translation_{fraction:g}", "real_reference_translation", translate(ref, fraction*size), ref, fraction, image_code)
        for delta in [.01, .05, .2, .5]:
            add(f"{label}_top_shift_{delta:g}", "real_reference_top_shift", top_shift(ref, delta), ref, delta, image_code)
        for delta in [.25, 1., 3.]:
            add(f"{label}_angular_top_shift_{delta:g}", "real_reference_angular_top_shift", uniform_angular_top_shift(ref, delta), ref, delta, image_code)
        for amplitude in [.01, .05, .2]:
            add(f"{label}_local_top_{amplitude:g}", "real_reference_local_top_warp", top_warp(ref, amplitude, True), ref, amplitude, image_code)
        for pixels in [.25, .5, 1., 2.]:
            a, meta = lowest_elevation_pixel_shift(ref, pixels)
            add(f"{label}_deepest_lower_pixel_{pixels:g}", "real_reference_horizon_pixel_shift", a, ref, pixels, image_code,
                "Same lower-point ERP offset can imply very different conditional depths. This diagnoses conditioning, not a difficulty penalty.", meta)
    # A GT-agnostic horizon test uses flat square rooms with prescribed radii.
    for radius in [1., 2., 4., 8., 16.]:
        gg = xz_scale(rect, radius / math.sqrt(13))
        aa, meta = lowest_elevation_pixel_shift(gg, 1.)
        add(f"horizon_radius_{radius:g}", "same_one_pixel_lower_error_vs_depth", aa, gg, radius,
            interpretation="Exactly one canonical lower pixel toward horizon at one corner, identical conditional construction across depths.", extra=meta)

    write_csv(out / "control_metrics.csv", controls)
    write_json(out / "control_geometries.json", control_geometry)
    keys = ["T", "F", "TF_mean_h", "T_over_sqrt_reference_area", "F_over_sqrt_reference_area", "S_top_deg", "S_bottom_deg", "S_mean_deg", "S_rms_deg", "S_max_deg"]
    correlations = []
    for i, left in enumerate(keys):
        for right in keys[i+1:]:
            correlations.append(dict(left=left, right=right, n=len(real), descriptive_spearman=float(spearmanr([r[left] for r in real], [r[right] for r in real]).statistic)))
    for sb, old in [("S_top_deg", "U"), ("S_bottom_deg", "B")]:
        subset = [r for r in real if r[old] is not None]
        correlations.append(dict(left=sb, right=old, n=len(subset), descriptive_spearman=float(spearmanr([r[sb] for r in subset], [r[old] for r in subset]).statistic)))
    write_csv(out / "component_correlations.csv", correlations)
    invariant_max = max(r["abs_delta"] for r in invariance)
    orientation_max = {k: max(r["abs_delta"] for r in orientation if r["metric"] == k) for k in set(r["metric"] for r in orientation)}
    convergence_max = max(r["abs_delta_deg"] for r in convergence)
    by_id = {r["case_id"]: r for r in controls if r["status"] == "valid"}
    shrink_controls = [r for r in controls if r["family"] == "symmetric_scale" and r["severity"] <= 1]
    sub = [r for r in controls if r["family"] == "same_curves_redundant_vertices"]
    invariant_keys = ["iou", "C", "T", "F", "dir", "flat", "S_top_deg", "S_bottom_deg"]
    control_checks = {
        "all_36_same_frozen_reference": len(real) == 36 and all(r["reference_id"] == main_by_id[r["record_id"]]["reference_id"] for r in real),
        "sphere_defined_for_all48": len(all_refs) == 48 and all(math.isfinite(r["S_mean_deg"]) for r in all_refs),
        "height_relative_error_matches_frozen48_at_1e-10":len(height_checks)==48 and max(r["abs_delta"] for r in height_checks)<1e-10,
        "reference_height_matches_frozen48_mean_minus_signed_error_at_1e-10":len(height_checks)==48 and max(r["reference_height_abs_delta"] for r in height_checks)<1e-10,
        "reversed_cyclic_spherical_deltas_below_0_001degree": max(orientation_max[k] for k in ["S_top_deg", "S_bottom_deg"]) < .001,
        "real_subdivision_max_error_below_1e-7": invariant_max < 1e-7,
        "spherical_quadrature_doubling_max_error_below_0_001degree": convergence_max < .001,
        "rectangle_shrink_iou_exact_factor_squared": all(abs(r["iou"]-r["severity"]**2) < 1e-10 for r in shrink_controls),
        "rectangle_uniform_top_shift_point4_detected": by_id["rectangle_top_shift_0.4"]["T"] > .399 and by_id["rectangle_top_shift_0.4"]["S_top_deg"] > 0.,
        "zero_mean_warp_missed_by_volume_but_boundary_detected": abs(by_id["rectangle_warp_0.4"]["conditional_volume_iou"] - 1) < 1e-10 and by_id["rectangle_warp_0.4"]["S_top_deg"] > .1,
        "synthetic_subdivision_components_unchanged": max(abs(r[k]-sub[0][k]) for r in sub for k in invariant_keys) < 1e-7,
        "same_relative_error_room_size_normalization_invariant": max(abs(by_id[f"xz_size_relative_shift_{factor:g}"]["TF_mean_over_sqrt_reference_area"] - by_id["xz_size_relative_shift_1"]["TF_mean_over_sqrt_reference_area"]) for factor in [.25,.5,2.,4.]) < 1e-10,
    }
    summary = dict(
        purpose="geometric_components_and_controls_only; no fit to historical subjective ratings",
        source_geometry_sha256=hashlib.sha256(geom_path.read_bytes()).hexdigest(),
        real_main_rows=len(real), reference_specific_rows=len(all_refs), controls=len(controls), valid_controls=sum(r["status"]=="valid" for r in controls),
        invalid_controls=[r["case_id"] for r in controls if r["status"]!="valid"],
        sphere_samples_per_direction=n,
        spherical_quadrature_doubling_max_abs_delta_deg=convergence_max,
        real_subdivision_max_abs_delta=invariant_max,
        height_relative_error_vs_frozen48_max_abs_delta=max(r["abs_delta"] for r in height_checks),
        reference_height_vs_frozen48_max_abs_delta=max(r["reference_height_abs_delta"] for r in height_checks),
        orientation_start_max_abs_delta_by_metric=orientation_max,
        checks=control_checks, all_checks_passed=all(control_checks.values()),
        warning="These are behavior and numerical checks, not calibrated human acceptability thresholds or independent building generalization.",
    )
    write_json(out / "geometry_experiment_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
