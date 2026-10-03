"""Independent finite-pool identities and targeted inferential diagnostics.

Read-only with respect to the supplied package. This is not a second full replay.
Outputs are finite-data descriptions, not population confidence intervals.
"""
from __future__ import annotations

import argparse
from itertools import combinations
from math import comb
from pathlib import Path
import hashlib
import json

import numpy as np
import pandas as pd
from scipy.stats import spearmanr


ROOT = Path(__file__).resolve().parent
DEFAULT_PACKAGE = ROOT.parent / "worker-audit-inputs/extracted/worker_consensus_independent_20261003"


def table(n, k, values):
    members = np.asarray(list(combinations(range(n), k)), dtype=int)
    x = np.zeros((len(members), n), dtype=float)
    x[np.arange(len(members))[:, None], members] = 1
    q = values(members, x)
    return members, x, np.asarray(q, dtype=float)


def direct_swap(members, q, n, a, b):
    lookup = {tuple(row): value for row, value in zip(members, q)}
    others = [j for j in range(n) if j not in (a, b)]
    return np.asarray([
        lookup[tuple(sorted((*t, a)))] - lookup[tuple(sorted((*t, b)))]
        for t in combinations(others, members.shape[1] - 1)
    ])


def projection(x, q):
    n = x.shape[1]
    k = int(x[0].sum())
    mean = float(q.mean())
    mu = (x.T @ q) / x.sum(0)
    alpha = (n - 1) / (n - k) * (mu - mean)
    predicted = mean + x @ alpha
    residual = q - predicted
    return mu, alpha, residual, {
        "n": n, "k": k, "subset_n": len(q),
        "mean": mean,
        "additive_residual_sum": float(residual.sum()),
        "conditional_residual_max_abs": float(np.max(abs(x.T @ residual / x.sum(0)))),
        "additive_explained_finite_score_variance": float(1 - np.var(residual) / np.var(q)) if np.var(q) > 0 else None,
        "residual_rmse": float(np.sqrt(np.mean(residual ** 2))),
        "residual_max_abs": float(np.max(abs(residual))),
    }


def check_general_identity():
    rng = np.random.default_rng(40217)
    checks = []
    for n in range(3, 10):
        for k in range(1, n):
            members, x, q = table(n, k, lambda m, x: rng.normal(size=len(m)))
            mu, alpha, residual, summary = projection(x, q)
            discrepancy = max(abs(direct_swap(members, q, n, a, b).mean() - (alpha[a] - alpha[b]))
                              for a, b in combinations(range(n), 2))
            assert discrepancy < 1e-12
            assert summary["conditional_residual_max_abs"] < 1e-12
            checks.append({"n": n, "k": k, "max_abs_identity_error": float(discrepancy)})
    return checks


def synthetic_examples():
    n, k = 24, 4
    members, x, pure = table(n, k, lambda m, x: .5 + .25 * (x[:, 0] - x[:, 1]) * (x[:, 2] - x[:, 3]))
    additive = .5 + .02 * (x[:, 0] - x[:, 1])
    interactive = additive + .20 * (x[:, 0] - x[:, 1]) * (x[:, 2] - x[:, 3])
    outputs = {}
    mus = []
    for label, q in [("pure_interaction", pure), ("additive", additive), ("same_means_with_interaction", interactive)]:
        mu, alpha, residual, summary = projection(x, q)
        delta = direct_swap(members, q, n, 0, 1)
        vals, counts = np.unique(np.round(delta, 12), return_counts=True)
        outputs[label] = {
            **summary,
            "score_min": float(q.min()), "score_max": float(q.max()),
            "mu_range": [float(mu.min()), float(mu.max())],
            "pair_0_1": {"mean": float(delta.mean()), "sd": float(delta.std()),
                "positive_fraction": float(np.mean(delta > 1e-12)),
                "negative_fraction": float(np.mean(delta < -1e-12)),
                "zero_fraction": float(np.mean(abs(delta) <= 1e-12)),
                "distribution": [{"delta": float(v), "n": int(c)} for v, c in zip(vals, counts)]},
        }
        mus.append(mu)
    assert np.max(abs(mus[0] - .5)) < 1e-12
    assert np.max(abs(mus[1] - mus[2])) < 1e-12
    assert outputs["additive"]["pair_0_1"]["negative_fraction"] == 0
    assert outputs["same_means_with_interaction"]["pair_0_1"]["negative_fraction"] > .12
    # A difference of swaps cancels all additive membership terms.
    lookup = {tuple(row): value for row, value in zip(members, interactive)}
    second = [lookup[tuple(sorted((*t, 0, 2)))] - lookup[tuple(sorted((*t, 1, 2)))]
              - lookup[tuple(sorted((*t, 0, 3)))] + lookup[tuple(sorted((*t, 1, 3)))]
              for t in combinations(range(4, n), k-2)]
    assert np.max(abs(np.asarray(second) - .8)) < 1e-12
    outputs["second_swap_interaction"] = {"background_n": len(second), "value": float(np.mean(second))}
    return outputs


def actual_single_image(package):
    geometry = json.loads((package / "inputs/one_image_geometry.json").read_text())
    workers = [r["worker"] for r in geometry["records"]]
    summaries, profiles = {}, []
    for method in ("mv50", "mv_strict"):
        with np.load(package / f"results/one_image_k4_{method}.npz", allow_pickle=False) as z:
            members, q = z["members"], z["iou"]
        x = np.zeros((len(members), len(workers)))
        x[np.arange(len(members))[:, None], members] = 1
        mu, alpha, residual, summary = projection(x, q)
        published = pd.read_csv(package / f"results/paired_replacements/{method}.csv")
        errors = []
        for row in published.itertuples():
            a, b = workers.index(row.worker_a), workers.index(row.worker_b)
            errors.append(abs(row.mean_a_minus_b - (alpha[a] - alpha[b])))
        # Independent direct swaps at selected pairs; avoid duplicating full ten-image replay.
        direct_errors = []
        for a, b in [(0, 1), (0, 13), (1, 11), (12, 13), (20, 23)]:
            delta = direct_swap(members, q, len(workers), a, b)
            direct_errors.append(abs(delta.mean() - (alpha[a] - alpha[b])))
        summary.update({"image": geometry["image"], "paired_csv_row_n": len(published),
            "max_identity_error_against_published_pair_means": float(max(errors)),
            "independent_direct_pair_n": len(direct_errors),
            "independent_direct_max_error": float(max(direct_errors)),
            "pairs_with_both_positive_and_negative_contexts": int(((published.a_better_fraction > 0) & (published.b_better_fraction > 0)).sum()),
            "pairs_with_p10_below_minus_001_and_p90_above_001": int(((published.p10 < -.001) & (published.p90 > .001)).sum()),
            "pairs_with_p10_below_minus_005_and_p90_above_005": int(((published.p10 < -.005) & (published.p90 > .005)).sum()),
            "scope": "One-image fixed-roster descriptive projection; not transfer or causal evidence."})
        assert max(errors + direct_errors) < 1e-12
        assert summary["conditional_residual_max_abs"] < 1e-12
        summaries[method] = summary
        profiles += [{"method": method, "worker": w, "conditional_inclusion_mean": float(mu[j]),
            "centered_additive_coefficient": float(alpha[j])} for j, w in enumerate(workers)]
    pd.DataFrame(profiles).to_csv(ROOT / "one_image_additive_profiles.csv", index=False)
    return summaries


def fixed_baseline_skill(package):
    people, buildings_out, summaries = [], [], {}
    for policy in ("original", "revised_where_available"):
        frame = pd.read_csv(package / f"inputs/matrix_{policy}_iou.csv", float_precision="round_trip")
        y = frame.iloc[:, 2:].to_numpy(float)
        workers, buildings = list(frame.columns[2:]), frame.building.to_numpy()
        r = y - y.mean(1, keepdims=True)
        p = np.empty_like(r)
        for b in sorted(set(buildings)):
            p[buildings == b] = r[buildings != b].mean(0)
        square_zero, square_model = r ** 2, (r-p) ** 2
        gain = square_zero - square_model
        total_gain, total_zero = float(gain.sum()), float(square_zero.sum())
        for j, worker in enumerate(workers):
            people.append({"policy": policy, "worker": worker,
                "fixed_baseline_zero_sse": float(square_zero[:, j].sum()),
                "fixed_baseline_prediction_sse": float(square_model[:, j].sum()),
                "fixed_baseline_error_improvement": float(gain[:, j].sum()),
                "fraction_of_net_error_improvement": float(gain[:, j].sum() / total_gain)})
        for b in sorted(set(buildings)):
            keep = buildings == b
            buildings_out.append({"policy": policy, "building": b,
                "image_n": int(keep.sum()), "zero_sse": float(square_zero[keep].sum()),
                "prediction_sse": float(square_model[keep].sum()),
                "error_improvement": float(gain[keep].sum()),
                "building_skill": float(gain[keep].sum() / square_zero[keep].sum()),
                "lobo_rank_correlation": float(spearmanr(y[~keep].mean(0), y[keep].mean(0)).statistic)})
        influence = pd.read_csv(package / "results/leave_one_worker_influence.csv")
        lookup = influence[influence.policy == policy].set_index("omitted").relative_prediction_skill
        refits = {}
        for omitted in ["P017", "P002"]:
            retained = [w != omitted for w in workers]
            yy = y[:, retained]
            rr = yy - yy.mean(1, keepdims=True)
            pp = np.empty_like(rr)
            for b in sorted(set(buildings)):
                pp[buildings == b] = rr[buildings != b].mean(0)
            refits[omitted] = float(1 - np.sum((rr-pp)**2) / np.sum(rr**2))
            assert abs(refits[omitted] - lookup.loc[omitted]) < 1e-12
        j = workers.index("P017")
        summaries[policy] = {"S": total_gain / total_zero,
            "SST": total_zero, "net_error_improvement": total_gain,
            "P017_fraction_of_net_error_improvement": float(gain[:, j].sum() / total_gain),
            "fixed_original_baseline_eval_only_without_P017": float((total_gain-gain[:, j].sum()) / (total_zero-square_zero[:, j].sum())),
            "recentered_refit_without_P017": refits["P017"],
            "recentered_refit_without_P002": refits["P002"],
            "positive_gain_building_n": int(sum(gain[buildings == b].sum() > 0 for b in set(buildings))),
            "positive_rank_correlation_building_n": int(sum(row["lobo_rank_correlation"] > 0 for row in buildings_out if row["policy"] == policy)),
            "scope": "Additive decomposition under the original full-roster baseline; not causal attribution."}
    pd.DataFrame(people).to_csv(ROOT / "fixed_baseline_worker_contributions.csv", index=False)
    pd.DataFrame(buildings_out).to_csv(ROOT / "fixed_baseline_building_contributions.csv", index=False)
    return summaries


def matrix_source_checks(package):
    result = []
    source = ROOT.parent / "worker-audit-original/analysis_results/worker_profiles_20261003"
    checks = json.loads((package / "inputs/transfer_checks.json").read_text())
    for item in checks:
        raw = (package / "inputs" / item["file"]).read_bytes()
        sha = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        assert sha == item["expected_git_blob_sha"]
        equal = None
        if (source / item["file"]).exists():
            equal = raw == (source / item["file"]).read_bytes()
            assert equal
        result.append({"file": item["file"], "git_blob_sha": sha,
            "agrees_with_returned_manifest": True,
            "byte_equal_to_locally_available_full_source": equal})
    return result


def metric_diagnostics(package):
    out = {}
    for policy in ("original", "revised_where_available"):
        scores = pd.read_csv(package/f"inputs/matrix_{policy}_iou.csv", float_precision="round_trip")
        centroid = pd.read_csv(package/f"inputs/matrix_{policy}_centroid_normalized.csv", float_precision="round_trip")
        y, c = scores.iloc[:, 2:].to_numpy(float), centroid.iloc[:, 2:].to_numpy(float)
        per_image = [{"image": scores.image.iloc[j],
            "rank_correlation_loss_and_centroid": float(spearmanr(1-y[j], c[j]).statistic),
            "fraction_of_centroid_total": float(c[j].sum()/c.sum())} for j in range(len(y))]
        out[policy] = {"worker_profile_correlation": float(spearmanr(1-y.mean(0), c.mean(0)).statistic),
            "per_image": per_image,
            "top_three_centroid_total_fraction": float(sum(sorted(c.sum(1)/c.sum())[-3:]))}
    return out


def risk_identity():
    # Entire masks have dependent pixels. Only the two independent draws matter.
    masks = np.array([[1, 0, 1, 0], [0, 1, 0, 1], [1, 1, 1, 1]], dtype=float)
    probabilities = np.array([.2, .3, .5])
    area = np.array([1., 2., 3., 4.])
    g = np.array([1., 1., 0., 0.])
    q = probabilities @ masks
    R = float(probabilities @ (abs(masks-g) @ area))
    B = float((q-g)**2 @ area)
    V = float((q*(1-q)) @ area)
    D = sum(float(probabilities[i]*probabilities[j]*(abs(masks[i]-masks[j])@area))
            for i in range(len(masks)) for j in range(len(masks)))
    assert abs(R-B-V) < 1e-12 and abs(D-2*V) < 1e-12
    return {"R": R, "B": B, "V": V, "independent_pair_disagreement": D,
        "pixels_are_not_independent": True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, default=DEFAULT_PACKAGE)
    args = parser.parse_args()
    package = args.package.resolve()
    result = {"general_identity_exhaustive_random_checks": check_general_identity(),
        "synthetic_examples": synthetic_examples(),
        "actual_single_image": actual_single_image(package),
        "fixed_baseline_skill": fixed_baseline_skill(package),
        "matrix_source_checks": matrix_source_checks(package),
        "metric_diagnostics": metric_diagnostics(package),
        "risk_identity_with_dependent_pixels": risk_identity(),
        "balanced_12_vs_12_partition_reference": {
            "expected_random_agreement": .5,
            "agreement_14_of_24": 14/24,
            "kappa_for_14_of_24": ((14/24)-.5)/.5,
            "upper_set_overlap": 7, "upper_set_jaccard": 7/17,
            "null_probability_at_least_14_agreements": sum(comb(12,j)*comb(12,12-j) for j in range(7,13))/comb(24,12),
            "caution": "Chance-scale illustration for one random balanced split; not a p-value for the 35 dependent data splits."}}
    (ROOT / "inference_checks.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    files = ["REPORT_zh.md", "src/paired_replacement.py", "src/analyze_profiles.py", "src/composition_kernel.py",
        "inputs/matrix_original_iou.csv", "inputs/matrix_revised_where_available_iou.csv",
        "inputs/one_image_geometry.json", "results/one_image_k4_mv50.npz", "results/one_image_k4_mv_strict.npz",
        "results/paired_replacements/mv50.csv", "results/paired_replacements/mv_strict.csv",
        "results/leave_one_worker_influence.csv"]
    manifest = {"source_package": str(package), "scope": "Read-only targeted inference audit; no full source replay.",
        "files": [{"path": f, "sha256": hashlib.sha256((package/f).read_bytes()).hexdigest()} for f in files]}
    (ROOT / "INPUT_MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "general_identity_exhaustive_random_checks"}, ensure_ascii=False, indent=2))
    print(f"PASS: {len(result['general_identity_exhaustive_random_checks'])} (N,k) identity cases, two actual score arrays, risk identity.")


if __name__ == "__main__":
    main()
