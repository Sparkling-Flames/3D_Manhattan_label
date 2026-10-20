"""Small scientific counterexamples for the fixed pair-diagnostic supplement."""
import copy
import hashlib
import json
from pathlib import Path
import time

import numpy as np
import pair_diagnostics as pd

ROOT = Path(__file__).resolve().parent


def row(ring, top=1., *, q=80., workers=("a", "b", "c"), complete=True):
    ring = np.asarray(ring, float)
    top = np.broadcast_to(np.asarray(top, float), (len(ring),))
    radius = np.linalg.norm(ring, axis=1)
    x = (np.arctan2(ring[:, 0], -ring[:, 1]) / (2 * np.pi) + .5) * 1024
    upper = (.5 - np.arctan2(top, radius) / np.pi) * 512
    lower = (.5 - np.arctan2(-1., radius) / np.pi) * 512
    points = np.empty((2 * len(ring), 2))
    points[::2] = np.column_stack((x, upper))
    points[1::2] = np.column_stack((x, lower))
    return dict(pool_id="synthetic", reference_id="fixed", k=len(workers), member_workers=list(workers),
                team_key="synthetic__" + hashlib.sha256(points.tobytes()).hexdigest()[:20],
                B8L2=q, D10=q, nodes=len(ring), new_n=len(workers),
                complete_evaluable=complete, complete_floor_evaluable=complete,
                height_mean_ratio=float(np.mean(top + 1)),
                geometry={"points": points.tolist(), "footprint": ring.tolist()})


def main():
    base = [[-5., -5.], [5., -5.], [5., 5.], [-5., 5.]]
    split = [[-5., -5.], [0., -5.], [5., -5.], [5., 5.], [-5., 5.]]
    cases = []
    def probe(name, a, b, predicate, explanation):
        out = pd.pair_metrics(a, b)
        passed = bool(predicate(out))
        cases.append(dict(name=name, passed=passed, explanation=explanation, a=a, b=b, metrics=out))
        assert passed, (name, out)
        return out
    a = row(base)
    probe("identical", a, copy.deepcopy(a), lambda x: x["joint_stable_main"] and x["geometry_shape_strict"] and abs(x["exact_flat_prism_pair_iou"] - 1) < 1e-12, "Same output must be identical in all criteria.")
    probe("extra_collinear_vertex", a, row(split), lambda x: not x["joint_stable_wide"] and x["geometry_shape_strict"] and x["true_corner_n_b"] == 4 and abs(x["prism_proxy_pair_iou"] - 1) < 1e-12, "Old node requirement rejects a genuinely redundant point; new geometry criterion remains invariant.")
    probe("cyclic_start", a, row(base[2:] + base[:2]), lambda x: x["joint_stable_main"] and x["geometry_shape_strict"], "Changing cyclic starting index does not change geometry.")
    probe("reverse_ring_diagnostic_only", a, row(base[::-1]), lambda x: x["geometry_shape_strict"] and x["true_reflex_corner_n_a"] == x["true_reflex_corner_n_b"], "New geometric diagnostics ignore ring orientation; frozen input ring is never edited.")
    notched = [[-5., -5.], [5., -5.], [5., 5.], [1., 5.], [1., 2.], [-1., 2.], [-1., 5.], [-5., 5.]]
    probe("missing_true_notch", a, row(notched), lambda x: not x["geometry_shape_main"] and x["true_corner_n_b"] == 8 and x["true_reflex_corner_n_b"] == 2, "Missing real concave structure is not treated as collinear redundancy.")
    probe("shape_pass_but_height_proxy_loss", a, row(base, 1.2), lambda x: x["geometry_shape_main"] and x["geometry_shape_main_and_prism_proxy_iou_lt_095"] and abs(x["exact_flat_prism_pair_iou"] - 2/2.2) < 1e-12, "A few angular degrees can encode meaningful height change in a wide room; retain separate proxy/exact height result.")
    b = row(base, [1., 1.7, 1., 1.7])
    probe("nonflat_ceiling_not_exact_solid", a, b, lambda x: x["exact_flat_prism_pair_iou"] is None and x["exact_flat_prism_status_b"] == "nonflat_ceiling_interior_surface_not_identified" and x["top_y_absdiff_deg_max"] > 0, "Nonflat endpoint heights do not determine an interior roof surface; report proxy and boundary profile only.")
    probe("same_mean_height_different_top_boundary", row(base, [1., 2., 1., 2.]), row(base, [2., 1., 2., 1.]), lambda x: abs(x["prism_proxy_pair_iou"] - 1) < 1e-12 and x["top_y_absdiff_deg_p95"] > 3 and not x["geometry_shape_main"], "Mean-height proxy alone can conceal large top boundary changes.")
    b = row((np.asarray(base) * 1.15).tolist(), 1.15)
    probe("same_erp_top_bottom_changes_depth", a, b, lambda x: x["bottom_y_absdiff_deg_p95"] > 0 and x["radius_abs_logratio_p95"] > .1 and x["inferred_total_height_mean_abs_logratio"] > 0, "Moving bottom-y changes inferred horizontal depth and total height even with unchanged top-y.")
    bad = row([[-5., -5.], [5., 5.], [5., -5.], [-5., 5.]], complete=False)
    probe("self_intersection_not_repaired", a, bad, lambda x: x["shape_floor_status_b"] == "invalid" and x["shape_floor_jaccard_difference"] is None and not x["geometry_shape_wide"], "Self-intersecting output remains invalid/missing, not buffered into a different polygon.")
    missing = copy.deepcopy(a); missing["geometry"] = None; missing["complete_evaluable"] = False; missing["complete_floor_evaluable"] = False; missing["B8L2"] = None
    probe("missing_geometry_retained", a, missing, lambda x: x["shape_floor_status_b"] == "missing" and x["floor_jaccard_difference"] is None and not x["geometry_shape_main"] and x["abs_B8L2_change"] is None, "Failure flags remain false and unavailable quantities remain null.")
    b = row(base, q=None)
    probe("Q_missing_is_separate_from_shape", a, b, lambda x: not x["joint_stable_main"] and x["geometry_noQ_main"] and x["geometry_shape_main"], "Q-free decomposition does not silently require a Q score.")
    # Symmetry of new geometry metrics, including non-square irregular outlines.
    left, right = pd.geometry_metrics(a, row(notched)), pd.geometry_metrics(row(notched), a)
    invariant = ["shape_pair_scale", "shape_floor_jaccard_difference", "wall_coverage_symmetric_min_main", "true_corner_F1_main", "bottom_y_absdiff_deg_p95", "top_y_absdiff_deg_p95", "geometry_shape_main"]
    symmetry = all(abs(float(left[k]) - float(right[k])) < 1e-12 for k in invariant)
    assert symmetry
    result = dict(schema="pair_diagnostic_counterexamples_v1", all_passed=all(c["passed"] for c in cases) and symmetry,
                  probes=cases, symmetry_fields=invariant, symmetric_geometry_passed=symmetry,
                  human_calibrated=False, scientific_fusion_executed=False,
                  source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(pd.__file__), ROOT/"METRIC_CONTRACT.json", Path(__file__)]})
    path = ROOT / "METRIC_PROBE_RESULTS.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print(json.dumps(dict(all_passed=result["all_passed"], probes=len(cases), output=str(path))))


if __name__ == "__main__":
    main()
