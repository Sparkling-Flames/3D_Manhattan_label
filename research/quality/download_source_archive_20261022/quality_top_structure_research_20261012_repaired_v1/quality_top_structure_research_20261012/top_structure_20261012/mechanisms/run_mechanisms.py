#!/usr/bin/env python3
"""Controlled audit of frozen height/top-boundary mechanisms; no source edits.

Run from a workspace containing previous_research/ and study_quality/:
    python top_structure_20261012/mechanisms/run_mechanisms.py --root .
Only writes beneath --out (default: this script's directory/results).
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import math
import platform
from pathlib import Path
import sys

import numpy as np


def clean(value):
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [clean(v) for v in value]
    if isinstance(value, np.ndarray):
        return clean(value.tolist())
    if isinstance(value, np.generic):
        return clean(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean(value), ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def csvwrite(path, rows):
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(clean(rows))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def geometry(xz, heights=2.4):
    q = np.asarray(xz, dtype=float)
    h = np.broadcast_to(np.asarray(heights, dtype=float), (len(q),))
    b = np.c_[q[:, 0], -np.ones(len(q)), q[:, 1]]
    t = b.copy()
    t[:, 1] = h - 1.0
    return {"bottom3d": b.tolist(), "top3d": t.tolist()}


def subdivide(g, edge, n):
    out = {}
    for key in ("top3d", "bottom3d"):
        a = np.asarray(g[key], float)
        result = []
        for k, p in enumerate(a):
            result.append(p)
            if k == edge:
                result.extend((1 - u) * p + u * a[(k + 1) % len(a)] for u in np.arange(1, n + 1) / (n + 1))
        out[key] = np.asarray(result).tolist()
    return out


def rotate_start(g, k):
    return {key: np.roll(np.asarray(g[key]), -k, axis=0).tolist() for key in ("top3d", "bottom3d")}


def erp_points(g):
    top = np.asarray(g["top3d"], float)
    bot = np.asarray(g["bottom3d"], float)
    result = np.empty((2 * len(bot), 2))
    for offset, ring in [(0, top), (1, bot)]:
        radius = np.linalg.norm(ring[:, [0, 2]], axis=1)
        result[offset::2, 0] = (np.arctan2(-ring[:, 0], ring[:, 2]) % (2 * np.pi)) * 1024 / (2 * np.pi)
        result[offset::2, 1] = 256 - np.arctan2(ring[:, 1], radius) * 512 / np.pi
    return result


def from_erp(points):
    p = np.asarray(points, float)
    yt = p[::2, 1]
    yb = p[1::2, 1]
    if np.any(yb <= 256) or np.any(yb >= 512):
        return None, "bottom_at_or_above_horizon_or_at_pole"
    if np.any(yt < 0) or np.any(yt > 512):
        return None, "top_outside_erp_vertical_domain"
    delta = ((p[1::2, 0] - p[::2, 0] + 512) % 1024) - 512
    if np.max(np.abs(delta)) > 1e-10:
        return None, "controlled_projection_requires_explicit_vertical_pairs"
    angle = np.pi * (yb / 512 - 0.5)
    radius = 1 / np.tan(angle)
    theta = p[1::2, 0] / 1024 * 2 * np.pi
    xz = np.c_[-radius * np.sin(theta), radius * np.cos(theta)]
    heights = 1 + radius * np.tan(np.pi * (0.5 - yt / 512))
    if np.any(heights <= 0):
        return None, "top_at_or_below_floor"
    return geometry(xz, heights), None


RECT = np.array([[-2.0, -1.0], [2.0, -1.0], [2.0, 1.0], [-2.0, 1.0]])


def spike(amplitude, support_fraction, center_x=0.0):
    width = 12.0 * support_fraction
    q = [[-2.0, -1.0], [center_x - width / 2, -1.0], [center_x, -1.0],
         [center_x + width / 2, -1.0], [2.0, -1.0], [2.0, 1.0], [-2.0, 1.0]]
    return geometry(q, [2.4, 2.4, 2.4 + amplitude, 2.4, 2.4, 2.4, 2.4])


def design():
    cases = []

    def add(case_id, family, a, g, **metadata):
        c = {"case_id": case_id, "family": family, "annotation": a, "reference": g,
             "evidence_class": "synthetic_no_assigned_human_grade", **metadata}
        if a is not None:
            c["annotation_erp_1024x512"] = erp_points(a).tolist()
        c["reference_erp_1024x512"] = erp_points(g).tolist()
        cases.append(c)

    for scale in [0.5, 2.0, 10.0]:
        for ratio in [0.8, 1.2]:
            add(f"uniform_scale{scale:g}_ratio{ratio:g}", "uniform_height_repeated_subset",
                geometry(RECT * scale, 2.4 * ratio), geometry(RECT * scale),
                horizontal_scale=scale, wall_height_ratio=ratio)

    patterns = {
        "tilted_plane": np.array([-1., -1., 1., 1.]),
        "alternating_corners": np.array([-1., 1., -1., 1.]),
        "one_high_mean_compensated": np.array([1., -1/3, -1/3, -1/3]),
    }
    for name, pattern in patterns.items():
        for amp in [0.24, 0.72, 1.2]:
            a = geometry(RECT, 2.4 + amp * pattern)
            add(f"equal_mean_{name}_amp{amp:g}", "equal_mean_different_local_profile", a, geometry(RECT),
                amplitude_h=amp, profile=name)
        a = geometry(RECT, 2.4 + 0.72 * pattern)
        add(f"nonflat_reference_perfect_{name}", "perfect_nonflat_reference_applicability", a, copy.deepcopy(a),
            profile=name, note="Synthetic nonflat reference only; no real alternative reference is approved or changed.")

    for support in [0.002, 0.02, 0.2]:
        for amp in [0.24, 0.72, 1.44]:
            add(f"spike_support{support:g}_amp{amp:g}", "localized_spike", spike(amp, support), geometry(RECT),
                amplitude_h=amp, support_perimeter_fraction=support,
                analytic_Hmean=amp * support / (2 * 2.4),
                analytic_Hlocal=amp * math.sqrt(support / 3) / 2.4)
    for support in [0.0002, 0.00002]:
        add(f"spike_narrow_support{support:g}", "narrow_spike_quadrature_probe", spike(1.44, support), geometry(RECT),
            amplitude_h=1.44, support_perimeter_fraction=support,
            analytic_Hmean=1.44 * support / (2 * 2.4),
            analytic_Hlocal=1.44 * math.sqrt(support / 3) / 2.4)
    center_on_4096_sample = (682.5 * 12 / 4096) - 2
    add("spike_narrow_sample_aligned", "narrow_spike_quadrature_probe", spike(1.44, 0.00002, center_on_4096_sample), geometry(RECT),
        amplitude_h=1.44, support_perimeter_fraction=0.00002,
        spike_center_x_h=center_on_4096_sample,
        analytic_Hmean=1.44 * 0.00002 / (2 * 2.4),
        analytic_Hlocal=1.44 * math.sqrt(0.00002 / 3) / 2.4)

    tilted = geometry(RECT, [1.68, 1.68, 3.12, 3.12])
    for edge in [0, 2]:
        for n in [1, 40]:
            add(f"same_tilt_curve_edge{edge}_plus{n}", "collinear_same_curve", subdivide(tilted, edge, n), geometry(RECT),
                control_parent="equal_mean_tilted_plane_amp0.72", inserted_points=n)
    narrow = spike(1.44, 0.00002)
    for k in range(1, 7):
        add(f"same_narrow_spike_start{k}", "cyclic_start_same_curve", rotate_start(narrow, k), geometry(RECT),
            control_parent="spike_narrow_support2e-05", cyclic_start=k)
    add("same_narrow_spike_added40", "collinear_same_curve", subdivide(narrow, 4, 40), geometry(RECT),
        control_parent="spike_narrow_support2e-05", inserted_points=40)

    for scale in [0.5, 2.0, 10.0]:
        g = geometry(RECT * scale)
        p = erp_points(g)
        for mode in ["bottom_toward_horizon", "top_and_bottom_both_minus1", "bottom_minus1_top_plus1", "height_preserving_compensation"]:
            q = p.copy()
            q[1::2, 1] -= 1.0
            if mode == "top_and_bottom_both_minus1":
                q[::2, 1] -= 1.0
            elif mode == "bottom_minus1_top_plus1":
                q[::2, 1] += 1.0
            elif mode == "height_preserving_compensation":
                rnew = 1 / np.tan(np.pi * (q[1::2, 1] / 512 - 0.5))
                q[::2, 1] = 256 - np.arctan2(1.4, rnew) * 512 / np.pi
            a, reason = from_erp(q)
            add(f"joint_y_scale{scale:g}_{mode}", "top_bottom_compensation", a, g,
                horizontal_scale=scale, pixel_mode=mode, input_pixels=q.tolist(), projection_failure=reason)

    for scale in [0.5, 2.0, 10.0, 50.0]:
        g = geometry(RECT * scale)
        p = erp_points(g)
        for delta in [-1.0, 1.0]:
            q = p.copy()
            q[1, 1] += delta
            a, reason = from_erp(q)
            add(f"far_corner_scale{scale:g}_bottom_delta{delta:g}", "near_horizon_fixed_pixel",
                a, g, horizontal_scale=scale, bottom_delta_px=delta,
                reference_bottom_horizon_margin_px=float(p[1, 1] - 256),
                input_pixels=q.tolist(), projection_failure=reason)
    g = geometry(RECT * 50)
    q = erp_points(g)
    q[1, 1] -= 2
    a, reason = from_erp(q)
    add("far_corner_horizon_crossing_invalid", "explicit_invalid_projection", a, g,
        input_pixels=q.tolist(), bottom_delta_px=-2, projection_failure=reason,
        note="Retained missing score; no negative radius or invented valid geometry.")

    sloped = geometry(RECT, 2.4 + RECT[:, 1])
    for shift in [-0.5, 0.5]:
        q = RECT + [0, shift]
        add(f"range_shift{shift:g}_transported_heights", "changed_footprint_matching",
            geometry(q, 2.4 + RECT[:, 1]), sloped, shift_z_h=shift,
            correspondence_truth="Constructed same vertex roles retain identical heights; nearest floor need not retain those roles.")
        add(f"range_shift{shift:g}_same_spatial_roof", "changed_footprint_matching",
            geometry(q, 2.4 + q[:, 1]), sloped, shift_z_h=shift,
            correspondence_truth="Both profiles lie on identical sloped plane h(x,z)=2.4+z, but have different boundaries.")
    L = np.array([[-3., -2.], [3., -2.], [3., 0.], [1., 0.], [1., 2.], [-3., 2.]])
    smaller = np.array([[-3., -2.], [1., -2.], [1., 2.], [-3., 2.]])
    add("range_omitted_branch_same_sloped_roof", "changed_footprint_matching",
        geometry(smaller, 2.4 + 0.3 * smaller[:, 0]), geometry(L, 2.4 + 0.3 * L[:, 0]),
        correspondence_truth="Same spatial tilted roof over different floor domain. This is not an approved real nonflat GT.")
    for shift in [-1e-6, 0.0, 1e-6]:
        a = geometry(np.array([[-1.5, -0.2], [1.5, -0.2], [1.5, 0.0], [-1.5, 0.0]]) + [0, shift], 1.4)
        add(f"nearest_tie_shift{shift:g}", "nearest_wall_tie", a, sloped,
            shift_z_h=shift, note="Partial inner footprint used only to diagnose matching; camera enclosure is not asserted.")
    tiecase = next(c for c in cases if c["case_id"] == "nearest_tie_shift0")
    add("nearest_tie_reference_rotated_start", "nearest_wall_tie", copy.deepcopy(tiecase["annotation"]), rotate_start(sloped, 2),
        note="Same represented reference; max squared-residual tie convention should preserve order invariance.")
    return cases


def scores_from_metrics(m):
    i = m["iou_2d"]
    s = m["S_top_deg"] ** 2 / 32
    b = m["S_bottom_deg"] ** 2 / 32
    h = (m["Hstar"] / 0.5) ** 2
    c = 1 - 0.075 * (m["dir"] ** 2 / (m["dir"] ** 2 + 25) + m["flat"] ** 2 / (m["flat"] ** 2 + 4))
    return {"Q_v11": 100 * i * c / (1 + s + b + h),
            "Q_no_topS": 100 * i * c / (1 + b + h),
            "Q_mean_height_only_no_topS": 100 * i * c / (1 + b + (m["Hmean"] / 0.5) ** 2),
            "Q_floor_iou": 100 * i,
            "Q_official_iou3d": 100 * m["iou_3d_corner_mean"] if m["iou_3d_corner_mean"] is not None else None,
            "term_top_S": s, "term_bottom_S": b, "term_Hstar": h, "intrinsic_C": c}


def local_diagnostics(a, g, height_revision):
    am = height_revision.height_moments(a)
    gm = height_revision.height_moments(g)
    d = {"annotation_" + k: v for k, v in am.items()}
    d.update({"reference_" + k: v for k, v in gm.items()})
    mu = gm["height_mean_h"]
    d["annotation_height_std_over_gt_mean"] = am["height_std_h"] / mu
    d["reference_height_std_over_gt_mean"] = gm["height_std_h"] / mu
    d["height_mean_signed_relative"] = (am["height_mean_h"] - mu) / mu
    for prefix, source, target in [("AG", a, g), ("GA", g, a)]:
        z = height_revision.directed_nearest_footprint_height_mse(source, target, 4096, "max")
        d.update({prefix + "_" + k: v for k, v in z.items()})
    hmin = height_revision.height_candidates(a, g, 4096, True, "min")
    d["Hlocal_min_tie_diagnostic"] = hmin["H_nearest_footprint"]
    d["Hstar_min_tie_diagnostic"] = hmin["H_mean_nearest_max"]
    from shapely.geometry import Polygon
    pa, pg = Polygon(np.asarray(a["bottom3d"])[:, [0, 2]]), Polygon(np.asarray(g["bottom3d"])[:, [0, 2]])
    same_floor = pa.symmetric_difference(pg).area < 1e-12
    constant_gt = gm["height_std_h"] < 1e-12
    d["same_footprint_and_constant_gt_height"] = same_floor and constant_gt
    d["exact_Hlocal_same_floor_constant_gt"] = height_revision.rms_about_level(a, mu) / mu if same_floor and constant_gt else None
    d["Hlocal_exact_decomposition_candidate"] = math.hypot(am["height_mean_h"] - mu, am["height_std_h"]) / mu
    # The last value equals Hlocal only on a common floor with constant GT.
    return d


def numerical_probe(case, height_revision, audit_geometry, geom_components):
    a, g = case["annotation"], case["reference"]
    rows = []
    for n in [512, 4096, 32768]:
        hc = height_revision.height_components(a, g, samples=n)
        rows.append({"case_id": case["case_id"], "component": "Hlocal", "sample_count": n,
                     "value": hc["Hlocal"], "Hmean": hc["Hmean"], "Hstar": hc["Hstar"]})
    for n in [128, 512, 4096, 32768]:
        m = audit_geometry.flatness(a, n=n)
        rows.append({"case_id": case["case_id"], "component": "F", "sample_count": n, "value": m["flat"]})
    for n in [512, 2048, 8192]:
        s = geom_components.spherical_sym_distance(a["top3d"], g["top3d"], n=n)
        rows.append({"case_id": case["case_id"], "component": "S_top", "sample_count": n, "value": s})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path.cwd())
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "results")
    args = ap.parse_args()
    root = args.root.resolve()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    b = root / "previous_research/quality_calibration_research_20261011/inputs_extracted/quality_cloud_compute_review_20261010"
    core = b / "frozen/scope_engine"
    sys.path.insert(0, str(core / "core"))
    import quality_v11
    import height_revision
    import audit_geometry
    import geometric_components

    sources = [core / "height_revision/height_revision.py", core / "core/quality_v11.py",
               core / "legacy_geometry/audit_geometry.py", core / "legacy_geometry/geometric_components.py",
               core / "validity/strict_geometry.py", core / "traditional/traditional_metrics.py"]
    design_cases = design()
    dump(out / "synthetic_design.json", {"protocol_sha256": sha(Path(__file__).with_name("protocol_before_results.json")),
                                        "case_count": len(design_cases), "cases": design_cases})
    rows, details, probes = [], [], []
    probe_ids = {"spike_support0.002_amp1.44", "spike_narrow_support0.0002", "spike_narrow_support2e-05",
                 "spike_narrow_sample_aligned", "same_narrow_spike_start2", "nearest_tie_shift0",
                 "equal_mean_tilted_plane_amp0.72"}
    for i, case in enumerate(design_cases):
        row = {k: v for k, v in case.items() if k not in {"annotation", "reference", "annotation_erp_1024x512", "reference_erp_1024x512", "input_pixels"}}
        if case["annotation"] is None:
            row.update(status="unavailable", unavailable_reason=case["projection_failure"], Q_v11=None, Q_no_topS=None)
            rows.append(row)
            details.append({"case_id": case["case_id"], "engine": None, "projection_failure": case["projection_failure"]})
            continue
        sc = quality_v11.score_geometry(case["annotation"], case["reference"])
        row["status"] = sc["status"]
        if sc["status"] != "available":
            row["unavailable_reason"] = "|".join(sc["reason_codes"])
            rows.append(row)
            details.append({"case_id": case["case_id"], "engine": sc})
            continue
        m = sc["metrics"]
        row.update({k: m[k] for k in ["iou_2d", "iou_3d_corner_mean", "Hmean", "Hlocal", "Hstar", "S_top_deg", "S_bottom_deg", "dir", "flat"]})
        row.update(scores_from_metrics(m))
        row.update(local_diagnostics(case["annotation"], case["reference"], height_revision))
        row["engine_Q_absolute_parity_error"] = abs(row["Q_v11"] - sc["quality_score"])
        rows.append(row)
        details.append({"case_id": case["case_id"], "engine": sc})
        if case["case_id"] in probe_ids:
            probes.extend(numerical_probe(case, height_revision, audit_geometry, geometric_components))
        if (i + 1) % 10 == 0:
            print(f"controls computed {i+1}/{len(design_cases)}", flush=True)
    csvwrite(out / "synthetic_components.csv", rows)
    dump(out / "synthetic_details.json", details)
    csvwrite(out / "numerical_sampling_probes.csv", probes)

    real_file = root / "study_quality/results/candidate_scores.json"
    real = json.loads(real_file.read_text())
    geometries = json.loads((b / "inputs/current_geometry_compact.json").read_text())["geometries"]
    real_rows, real_probe = [], []
    real_probe_ids = {"T20", "T09", "T22", "T03", "T18", "S071", "S107", "S034"}
    for i, rec in enumerate(real):
        a, g = geometries[rec["object_id"]], geometries[rec["reference_object_id"]]
        cid = rec.get("old_case_id") or rec.get("new_case_id")
        row = {k: rec.get(k) for k in ["record_id", "object_id", "reference_object_id", "image_id", "old_case_id", "new_case_id", "worker_id"]}
        row.update(case_id=cid, evidence_class="existing_development_fixed_reference_conditional_geometry", **local_diagnostics(a, g, height_revision))
        hc = height_revision.height_components(a, g)
        row.update(Hmean=hc["Hmean"], Hlocal=hc["Hlocal"], Hstar=hc["Hstar"],
                   frozen_Hmean_error=abs(hc["Hmean"] - rec["Hmean"]),
                   frozen_Hlocal_error=abs(hc["Hlocal"] - rec["Hlocal"]),
                   frozen_Hstar_error=abs(hc["Hstar"] - rec["Hstar"]))
        row.update({k: rec.get(k) for k in ["S_top_deg", "S_bottom_deg", "dir", "flat", "Q_v11", "Q_no_topS"]})
        real_rows.append(row)
        if cid in real_probe_ids:
            real_probe.extend(numerical_probe({"case_id": cid, "annotation": a, "reference": g}, height_revision, audit_geometry, geometric_components))
    csvwrite(out / "real_39_height_components.csv", real_rows)
    csvwrite(out / "real_selected_numerical_probes.csv", real_probe)
    dump(out / "run_manifest.json", {"python": sys.version, "platform": platform.platform(), "numpy": np.__version__,
                                    "source_hashes": {str(p.relative_to(root)): sha(p) for p in sources},
                                    "real_input_sha256": sha(real_file), "geometry_sha256": sha(b / "inputs/current_geometry_compact.json"),
                                    "protocol_sha256": sha(Path(__file__).with_name("protocol_before_results.json")),
                                    "script_sha256": sha(Path(__file__)), "control_count": len(rows),
                                    "control_available": sum(r["status"] == "available" for r in rows),
                                    "real_count": len(real_rows), "synthetic_human_grades_assigned": 0,
                                    "new_holdout_validation": False, "source_eligibility_or_labels_changed": False})
    print(json.dumps({"controls": len(rows), "available": sum(r["status"] == "available" for r in rows),
                      "real_records": len(real_rows), "max_real_H_error": max(r["frozen_Hstar_error"] for r in real_rows)}, indent=2))


if __name__ == "__main__":
    main()
