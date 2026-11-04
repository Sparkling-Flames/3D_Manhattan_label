"""Exact five-input finite-change decomposition of the existing Q formula.

All 5! orders of substituting A's inputs by C's inputs receive equal weight
(calculated by the equivalent 32-subset Shapley formula). The resulting terms
sum to the saved C-A Q difference. This is an algebraic score decomposition,
not a causal mediation estimate, a new endpoint, or a new geometry evaluation.
No decomposition is assigned to an unavailable original Q.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from ac_common import *
from summarize_ac import cohorts, BASE, direction

FIELDS = ["iou_2d", "S_bottom_deg", "dir", "Hmean", "Hcenter"]
TERMS = ["range_2d_IoU", "bottom_boundary", "direction", "global_height", "local_height"]


def quality(x):
    I, S, D, Hm, Hc = x.T
    b = S ** 2 / 32.
    direction_term = 1.5 * D ** 2 / (D ** 2 + 8. ** 2)
    h = (Hm / .8) ** 2 + (Hc / .25) ** 2
    denominator = I + np.hypot(1. - I + I * b, I * direction_term) + I * h
    return np.divide(100. * I, denominator, out=np.zeros_like(I), where=I != 0)


def explain(d):
    a = d[["A_" + c for c in FIELDS]].to_numpy(float)
    c = d[["C_" + c for c in FIELDS]].to_numpy(float)
    if not np.isfinite(a).all() or not np.isfinite(c).all():
        raise ValueError("Scored endpoint lacks a required Q input")
    scores = []
    for mask in range(32):
        use = np.array([bool(mask & (1 << j)) for j in range(5)])
        scores.append(quality(np.where(use[None, :], c, a)))
    value = np.stack(scores, axis=1)
    result = np.zeros_like(a)
    for j in range(5):
        for mask in range(32):
            if mask & (1 << j):
                continue
            k = mask.bit_count()
            weight = math.factorial(k) * math.factorial(4 - k) / math.factorial(5)
            result[:, j] += weight * (value[:, mask | (1 << j)] - value[:, mask])
    parity = max(float(np.max(np.abs(value[:, 0] - d.Q_A))), float(np.max(np.abs(value[:, 31] - d.Q_C))))
    residual = float(np.max(np.abs(result.sum(axis=1) - d.dQ)))
    if parity > 1e-8 or residual > 1e-8:
        raise ValueError("Q formula or finite-change decomposition failed")
    out = d.copy()
    for i, term in enumerate(TERMS):
        out["Q_term_" + term] = result[:, i]
    out["Q_formula_decomposition_residual"] = result.sum(axis=1) - d.dQ
    return out, parity, residual


def main():
    sources = [read_csv(HERE / name) for name in ["PHYSICAL_PAIRS_AUTOMATIC.csv.gz", "PHYSICAL_PAIRS_ASSISTED.csv.gz"]]
    d = pd.concat(sources, ignore_index=True)
    d = d.loc[truth(d.common_Q)].copy()
    decomposed, parity, residual = explain(d)
    keep = ["analysis_cohort", "version", "scope", "condition", "n", "m", "class_pair", "canonical_physical_pair_id", "event_id", "pool_id", "image", "building", "A_team_key", "C_team_key", "D_workers", "X_workers", "Z_workers", "Q_A", "Q_C", "dQ", "same_node_count", "original_common_Q", "new_common_Q"]
    keep += ["Q_term_" + t for t in TERMS] + ["Q_formula_decomposition_residual"]
    csv(HERE / "Q_FORMULA_ATTRIBUTION_PAIRS.csv.gz", decomposed[keep])
    d = cohorts(decomposed)
    metrics = ["dQ"] + ["Q_term_" + t for t in TERMS]
    images, rows = [], []
    for key, g in d.groupby(BASE, dropna=False, observed=True, sort=True):
        im = make_image_table(g, [], metrics)
        z = im.copy()
        for k, v in dict(zip(BASE, key)).items():
            z[k] = v
        images.append(z)
        for sign in [1, -1]:
            row = dict(zip(BASE, key), direction=direction(key[-1], sign), images=len(im), buildings=im.building.nunique(), physical_pairs=len(g))
            for metric in metrics:
                row[metric + "_image_equal_mean"] = sign * float(im[metric].mean())
                row[metric + "_building_equal_mean"] = sign * float(im.groupby("building")[metric].mean().mean())
            rows.append(row)
    image = pd.concat(images, ignore_index=True)
    image["sum_Q_terms"] = image[["Q_term_" + t for t in TERMS]].sum(axis=1)
    if not np.allclose(image.dQ, image.sum_Q_terms, atol=1e-8, rtol=0):
        raise ValueError("Weights broke attribution additivity")
    csv(HERE / "Q_FORMULA_ATTRIBUTION_IMAGES.csv.gz", image)
    csv(HERE / "Q_FORMULA_ATTRIBUTION_SUMMARY.csv", pd.DataFrame(rows))
    write_json(HERE / "Q_FORMULA_ATTRIBUTION_CHECKS.json", dict(status="passed", scored_pair_versions=len(decomposed),
               score_formula_max_absolute_residual=parity, attribution_max_absolute_residual=residual,
               feature_inputs=FIELDS, interpretation="algebraic finite-change decomposition, not causal, not structural mediation",
               unchanged_missing_Q_policy=True, physical_endpoint_scores_replaced=0, new_physical_endpoints=0,
               score_definition="Q=100 I/[I+hypot(1-I+I*(S^2/32),I*(1.5 D^2/(D^2+64)))+I*((Hm/0.8)^2+(Hc/0.25)^2)]"))
    print("quality decomposition passed", parity, residual, flush=True)


if __name__ == "__main__":
    main()
