"""Training-only multiview personnel partition, with auditable missingness.

This module consumes *historical training* worker features only. It never reads
target images, fusion scores or replacement outcomes. K selection is performed by
the shared training-building evaluator, outside this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import cut_tree, linkage
from scipy.spatial.distance import squareform
from sklearn.metrics import silhouette_score, adjusted_rand_score
from sklearn.tree import DecisionTreeClassifier, export_text


@dataclass
class PartitionResult:
    workers: list[str]
    eligible: list[str]
    labels: pd.DataFrame
    pairs: pd.DataFrame
    transforms: dict
    diagnostics: pd.DataFrame
    distances: np.ndarray


def robust_transform(frame: pd.DataFrame, columns: list[str]) -> tuple[pd.DataFrame, dict]:
    """Fit center/scale on this training set. Missing values stay missing.

    Scale falls back from IQR to robust MAD and then sample SD only when IQR is
    zero. No support counts, missing indicators, worker origin or batch enter.
    Entirely constant/too-sparse columns are explicitly omitted.
    """
    transformed = pd.DataFrame(index=frame.index)
    fit = {}
    for col in columns:
        vals = pd.to_numeric(frame[col], errors="coerce").replace([np.inf, -np.inf], np.nan)
        valid = vals.dropna()
        info = {"n_observed_workers": int(len(valid))}
        if len(valid) < 6 or valid.nunique() < 2:
            info.update(status="omitted", reason="fewer_than_six_observed_or_no_variation")
            fit[col] = info
            continue
        center = float(valid.median())
        scale = float(valid.quantile(.75) - valid.quantile(.25))
        source = "IQR"
        if not np.isfinite(scale) or scale < 1e-10:
            scale = float(np.median(np.abs(valid - center)) * 1.4826)
            source = "MAD"
        if not np.isfinite(scale) or scale < 1e-10:
            scale = float(valid.std(ddof=0))
            source = "SD_fallback"
        if not np.isfinite(scale) or scale < 1e-10:
            info.update(status="omitted", reason="no_scale")
            fit[col] = info
            continue
        transformed[col] = ((vals - center) / scale).clip(-3., 3.)
        info.update(status="included", center=center, scale=scale, scale_source=source, clip=[-3., 3.])
        fit[col] = info
    return transformed, fit


def multiview_distance(z: pd.DataFrame, domains: dict[str, list[str]], min_common_domains: int = 1):
    """Equal weight per observed domain; equal weight inside each domain.

    Pairwise missing domains are omitted rather than treated as zero/failure.
    The exact denominator is exported. This is a dissimilarity, not necessarily
    a Euclidean metric, and complete linkage is used without connectivity closure.
    """
    n = len(z)
    total = np.zeros((n, n), dtype=float)
    counts = np.zeros((n, n), dtype=int)
    shared = [[[] for _ in range(n)] for _ in range(n)]
    per_domain = {}
    for domain, wanted in domains.items():
        columns = [c for c in wanted if c in z]
        if not columns:
            continue
        x = z[columns].to_numpy(dtype=float)
        values = np.full((n, n), np.nan)
        for i in range(n):
            for j in range(i + 1, n):
                ok = np.isfinite(x[i]) & np.isfinite(x[j])
                if not ok.any():
                    continue
                d2 = float(np.mean((x[i, ok] - x[j, ok]) ** 2))
                total[i, j] += d2
                total[j, i] += d2
                counts[i, j] += 1
                counts[j, i] += 1
                shared[i][j].append(domain)
                shared[j][i].append(domain)
                values[i, j] = values[j, i] = np.sqrt(d2)
        per_domain[domain] = values
    bad = (counts < min_common_domains) & ~np.eye(n, dtype=bool)
    if bad.any():
        a, b = np.argwhere(bad)[0]
        raise ValueError(f"No adequate historical common domain for {z.index[a]}/{z.index[b]}")
    d = np.sqrt(np.divide(total, counts, out=np.zeros_like(total), where=counts > 0))
    np.fill_diagonal(d, 0.)
    return d, counts, shared, per_domain


def partition_features(frame: pd.DataFrame, domains: dict[str, list[str]], ks=(4, 6, 8, 10),
                       eligibility_col="core_supported", method_id="forward_full") -> PartitionResult:
    if frame.index.name != "worker_id":
        frame = frame.set_index("worker_id")
    frame = frame.sort_index()
    all_workers = list(frame.index)
    good = frame[eligibility_col].fillna(False).astype(bool)
    eligible = list(frame.index[good])
    if len(eligible) < min(ks) + 1:
        raise ValueError(f"Only {len(eligible)} supported workers")
    raw = frame.loc[eligible]
    wanted = list(dict.fromkeys(c for fields in domains.values() for c in fields if c in frame))
    z, transform = robust_transform(raw, wanted)
    d, n_common, shared, per_domain = multiview_distance(z, domains)
    tree = linkage(squareform(d, checks=True), method="complete", optimal_ordering=True)
    label_rows, diag_rows, pair_rows = [], [], []
    assignments = {}
    for k in ks:
        if k >= len(eligible):
            continue
        labels = cut_tree(tree, n_clusters=[k])[:, 0]
        # Canonical IDs by first worker: reproducible within a fold, no cross-fold semantics.
        groups = sorted((sorted(np.asarray(eligible)[labels == c]) for c in np.unique(labels)), key=lambda a: a[0])
        m = {w: f"C{n + 1:02d}" for n, ws in enumerate(groups) for w in ws}
        assignments[k] = m
        for w in all_workers:
            label_rows.append({"method_id": method_id, "K": k, "worker_id": w,
                               "class_id": m.get(w, "unknown"),
                               "unknown_reason": "" if w in m else "core_historical_support_below_gate"})
        sizes = np.array([len(g) for g in groups])
        within = [d[i, j] for i, j in combinations(range(len(eligible)), 2) if m[eligible[i]] == m[eligible[j]]]
        diag_rows.append({"method_id": method_id, "K": k, "n_workers": len(all_workers),
                          "n_supported": len(eligible), "n_unknown": len(all_workers)-len(eligible),
                          "n_singleton_classes": int(np.sum(sizes == 1)),
                          "n_doubleton_classes": int(np.sum(sizes == 2)),
                          "n_workers_in_singletons": int(np.sum(sizes[sizes == 1])),
                          "n_workers_in_reusable_classes": int(np.sum(sizes[sizes >= 2])),
                          "n_potential_within_pairs": int(sum(x*(x-1)//2 for x in sizes)),
                          "silhouette": float(silhouette_score(d, labels, metric="precomputed")),
                          "within_distance_median": float(np.median(within)) if within else None,
                          "within_distance_p95": float(np.quantile(within, .95)) if within else None,
                          "within_distance_max": float(max(within)) if within else None,
                          "class_sizes": json.dumps(sorted(sizes.tolist(), reverse=True))})
    for i, j in combinations(range(len(eligible)), 2):
        row = {"method_id": method_id, "worker_a": eligible[i], "worker_b": eligible[j],
               "historical_dissimilarity": float(d[i, j]), "common_domains": int(n_common[i, j]),
               "common_domain_names": "|".join(shared[i][j])}
        row.update({f"same_class_K{k}": int(m[eligible[i]] == m[eligible[j]]) for k, m in assignments.items()})
        row.update({f"distance_{name}": float(mat[i, j]) if np.isfinite(mat[i, j]) else None for name, mat in per_domain.items()})
        pair_rows.append(row)
    return PartitionResult(all_workers, eligible, pd.DataFrame(label_rows), pd.DataFrame(pair_rows),
                           {"columns": transform, "domains": domains, "missing": "pairwise_masked_no_indicator",
                            "linkage": "complete", "no_target_data": True},
                           pd.DataFrame(diag_rows), d)


def simple_explanation(frame: pd.DataFrame, labels: pd.DataFrame, columns: list[str], seed=20261019):
    """Shallow descriptive rules. Missing imputation here is explanation-only.

    This is fidelity to a discovered training partition, NOT independent outcome
    prediction. Historical-building perturbation fidelity is measured separately.
    """
    if frame.index.name != "worker_id":
        frame = frame.set_index("worker_id")
    m = labels[labels.class_id != "unknown"].set_index("worker_id").class_id
    x = frame.reindex(m.index)[[c for c in columns if c in frame]].apply(pd.to_numeric, errors="coerce")
    x = x.loc[:, x.notna().sum() >= 6]
    med = x.median()
    xfill = x.fillna(med)
    model = DecisionTreeClassifier(max_depth=3, min_samples_leaf=3, random_state=seed, class_weight=None)
    model.fit(xfill, m)
    prediction = model.predict(xfill)
    pairs_same_true, pairs_same_pred = [], []
    for i, j in combinations(range(len(m)), 2):
        pairs_same_true.append(m.iloc[i] == m.iloc[j])
        pairs_same_pred.append(prediction[i] == prediction[j])
    both = np.asarray(pairs_same_true) | np.asarray(pairs_same_pred)
    inter = np.asarray(pairs_same_true) & np.asarray(pairs_same_pred)
    return {
        "description": "training_partition_fidelity_only",
        "n_workers": int(len(m)), "max_depth": 3, "min_samples_leaf": 3,
        "accuracy": float(np.mean(prediction == m.to_numpy())),
        "adjusted_rand_index": float(adjusted_rand_score(m, prediction)),
        "same_pair_jaccard": float(inter.sum()/both.sum()) if both.sum() else None,
        "rules": export_text(model, feature_names=list(x.columns), decimals=4),
        "explanation_only_imputation": {k: float(v) for k,v in med.items()},
        "feature_importance": {k: float(v) for k,v in zip(x.columns, model.feature_importances_) if v > 0},
        "predictions": [{"worker_id": w, "class_id": str(m.loc[w]), "rule_class_id": str(p)} for w,p in zip(m.index,prediction)],
    }


def small_contract_check():
    """Concrete boundary: unknown masking and class-label invariance."""
    rng = np.random.default_rng(1729)
    f = pd.DataFrame({"worker_id": [f"T{i:02d}" for i in range(18)],
                      "q": np.r_[rng.normal(-2,.1,9),rng.normal(2,.1,9)],
                      "t": rng.normal(0,1,18), "s": np.r_[rng.normal(0,1,9),[np.nan]*9],
                      "core_supported": [True]*17+[False]})
    a = partition_features(f,{"Q":["q"],"T":["t"],"sparse":["s"]},ks=(4,6))
    b = partition_features(f.sample(frac=1,random_state=4),{"Q":["q"],"T":["t"],"sparse":["s"]},ks=(4,6))
    assert a.labels.equals(b.labels), "input order affected canonical labels"
    assert (a.labels[a.labels.worker_id == "T17"].class_id == "unknown").all()
    assert a.pairs.common_domains.min() == 2
    assert np.isfinite(a.distances).all()
    assert np.allclose(a.distances, a.distances.T)
    return {"passed": True, "boundaries": ["input_order", "unknown_gate", "sparse_domain_mask", "symmetric_finite_distance"]}


if __name__ == "__main__":
    print(json.dumps(small_contract_check(), indent=2))
