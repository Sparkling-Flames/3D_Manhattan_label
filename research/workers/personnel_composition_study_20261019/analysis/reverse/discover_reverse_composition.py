#!/usr/bin/env python3
"""Historical-only reverse personnel candidates for composition experiments.

The task-level local partitions are retained frozen measurements. Their labels
are NEVER reused as personnel labels on an evaluation image. Cross-image worker
relations and role features below use only the declared history buildings. Q,
reference geometry and fusion quality are not read. Evaluation-side geometric
measurements are discarded before any relation or role feature is constructed.
The emitted personnel labels are then fixed for both discovery and validation.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from collections import Counter
from itertools import combinations
from pathlib import Path

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import cut_tree, linkage
from scipy.linalg import eigh
from scipy.spatial.distance import squareform
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score

K_VALUES = (2, 3, 4, 5, 6, 8)
DIFFICULTIES = ("easy", "medium", "hard")
DIFF_MAP = {"简单": "easy", "中等": "medium", "困难": "hard"}
SEED = 2026101903
MIN_IMAGES, MIN_BUILDINGS = 6, 3
RECORD_FIELDS = ["pool_id", "image_id", "image_code", "building_id", "condition",
                 "layer", "difficulty", "N", "object_id", "worker_id", "origin",
                 "pair_count", "mean_height", "minimum_bottom_depression_deg"]
ASSIGNMENT_FIELDS = ["pool_id", "worker_id", "method", "threshold_deg", "cluster_id",
                     "cluster_size", "cluster_diameter_deg", "close_neighbors"]
ROLE_FEATURES = ["coassign9_mean", "coassign9_p10", "dominant9_rate", "singleton9_rate",
                 "coassign12_mean", "count_gap_mean", "count_gap_sd", "count_below_rate",
                 "count_above_rate", "logheight_gap_mean", "logheight_gap_sd",
                 "depression_gap_mean", "depression_gap_sd"]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, obj) -> None:
    def conv(x):
        if isinstance(x, (np.integer, np.floating, np.bool_)):
            return x.item()
        if isinstance(x, np.ndarray):
            return x.tolist()
        if isinstance(x, Path):
            return str(x)
        raise TypeError(type(x).__name__)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=conv) + "\n")


def load_inputs(records_path: Path, assignments_path: Path, history_buildings: list[str]):
    # Reading only the metadata and frozen behavioral measurements prevents Q or
    # target reference information from entering this route even by accident.
    all_records = pd.read_csv(records_path, usecols=RECORD_FIELDS)
    all_records = all_records[all_records.layer.eq("ordinary_manual")].copy()
    assert len(all_records) == 5719 and all_records.image_id.nunique() == 177
    assert not all_records.duplicated(["pool_id", "worker_id"]).any()
    all_records["difficulty"] = all_records.difficulty.replace(DIFF_MAP)
    all_records = all_records.rename(columns={"building_id": "building"})
    workers = sorted(all_records.worker_id.unique())
    origins = all_records.groupby("worker_id").origin.agg(lambda z: "|".join(sorted(set(z)))).to_dict()
    assert all("|" not in x for x in origins.values())
    rec = all_records[all_records.building.isin(history_buildings)].copy()
    assignments = pd.read_csv(assignments_path, usecols=ASSIGNMENT_FIELDS)
    assignments = assignments[assignments.method.eq("affinity") & assignments.pool_id.isin(rec.pool_id)].copy()
    for t in (9, 12):
        a = assignments[assignments.threshold_deg.eq(t)].drop(columns=["method", "threshold_deg"])
        a = a.rename(columns={x: x + str(t) for x in a if x not in ("pool_id", "worker_id")})
        rec = rec.merge(a, on=["pool_id", "worker_id"], validate="one_to_one")
    assert set(rec.building) == set(history_buildings)
    assert len(rec) == len(all_records[all_records.building.isin(history_buildings)])
    # Evaluation-side structural values are dropped now. The returned metadata
    # can be used only for category-support/feasibility, not fitting or ranking.
    meta = all_records[["pool_id", "image_id", "image_code", "building", "difficulty",
                        "object_id", "worker_id", "origin"]].copy()
    return rec, meta, workers, origins


def support(rec, workers, domain="global"):
    g = rec if domain == "global" else rec[rec.difficulty.eq(domain)]
    s = g.groupby("worker_id").agg(n_images=("image_id", "nunique"),
                                    n_buildings=("building", "nunique"),
                                    n_records=("object_id", "nunique"))
    s = s.reindex(workers).fillna(0).astype(int)
    s["supported"] = s.n_images.ge(MIN_IMAGES) & s.n_buildings.ge(MIN_BUILDINGS)
    return s


def pair_observations(rec):
    rows = []
    for pool_id, g in rec.groupby("pool_id", sort=True):
        entries = g.sort_values("worker_id").to_dict("records")
        for a, b in combinations(entries, 2):
            rows.append(dict(pool_id=pool_id, image_id=a["image_id"], building=a["building"],
                             difficulty=a["difficulty"], worker_a=a["worker_id"], worker_b=b["worker_id"],
                             origin_pair="|".join(sorted([a["origin"], b["origin"]])),
                             same9=float(a["cluster_id9"] == b["cluster_id9"]),
                             same12=float(a["cluster_id12"] == b["cluster_id12"]),
                             count_distance=abs(a["pair_count"] - b["pair_count"])))
    pairs = pd.DataFrame(rows)
    assert not pairs.duplicated(["pool_id", "worker_a", "worker_b"]).any()
    for t in (9, 12):
        # This baseline controls image difficulty AND old/new pair opportunity.
        # Its purpose is a sensitivity candidate, not to erase the raw signal.
        baseline = pairs.groupby(["pool_id", "origin_pair"])[f"same{t}"].transform("mean")
        pairs[f"source_residual{t}"] = pairs[f"same{t}"] - baseline
    return pairs


def relation_matrices(pairs, workers, prior_buildings):
    metrics = ["same9", "same12", "source_residual9", "source_residual12", "count_distance"]
    image = pairs.groupby(["worker_a", "worker_b", "building", "image_id"], sort=False)[metrics].mean().reset_index()
    build = image.groupby(["worker_a", "worker_b", "building"], sort=False)[metrics].mean().reset_index()
    observed = build.groupby(["worker_a", "worker_b"])[metrics].mean()
    sizes = image.groupby(["worker_a", "worker_b"]).agg(n_images=("image_id", "nunique"), n_buildings=("building", "nunique"))
    prior = pairs.groupby(["building", "image_id"])[["same9", "same12", "count_distance"]].mean().groupby("building").mean().mean().to_dict()
    prior.update(source_residual9=0., source_residual12=0.)
    matrices = {x: np.zeros((len(workers), len(workers))) for x in metrics}
    rows = []
    for i, a in enumerate(workers):
        for j in range(i + 1, len(workers)):
            b = workers[j]
            key = (a, b)
            ni = int(sizes.loc[key, "n_images"]) if key in sizes.index else 0
            nb = int(sizes.loc[key, "n_buildings"]) if key in sizes.index else 0
            row = dict(worker_a=a, worker_b=b, n_images=ni, n_buildings=nb,
                       observed=bool(ni), supported=ni >= 3 and nb >= 2,
                       prior_buildings=float(prior_buildings))
            for metric in metrics:
                val = float(observed.loc[key, metric]) if nb else np.nan
                if nb:
                    posterior = (nb * val + prior_buildings * prior[metric]) / (nb + prior_buildings)
                else:
                    posterior = prior[metric]
                row[metric + "_observed"] = val
                row[metric + "_prior"] = prior[metric]
                row[metric + "_posterior"] = posterior
                matrices[metric][i, j] = matrices[metric][j, i] = posterior
            rows.append(row)
    return matrices, pd.DataFrame(rows)


def weighted_quantile(values, weights, q):
    ok = np.isfinite(values) & np.isfinite(weights) & (weights > 0)
    values, weights = np.asarray(values)[ok], np.asarray(weights)[ok]
    if not len(values):
        return np.nan
    order = np.argsort(values, kind="stable")
    values, weights = values[order], weights[order]
    cdf = (np.cumsum(weights) - .5 * weights) / weights.sum()
    return float(np.interp(q, cdf, values))


def wmean(values, weights):
    ok = np.isfinite(values)
    return float(np.average(np.asarray(values)[ok], weights=np.asarray(weights)[ok])) if np.any(ok) else np.nan


def wsd(values, weights):
    ok = np.isfinite(values)
    if np.sum(ok) < 2:
        return np.nan
    v, w = np.asarray(values)[ok], np.asarray(weights)[ok]
    return float(np.sqrt(np.average((v - np.average(v, weights=w)) ** 2, weights=w)))


def role_features(rec, workers, domain="global"):
    r = rec.copy()
    for t in (9, 12):
        size = r.groupby("pool_id").worker_id.transform("size")
        r[f"coassign{t}"] = (r[f"cluster_size{t}"] - 1) / (size - 1)
        r[f"dominant{t}"] = r[f"cluster_size{t}"].eq(r.groupby("pool_id")[f"cluster_size{t}"].transform("max")).astype(float)
        r[f"singleton{t}"] = r[f"cluster_size{t}"].eq(1).astype(float)
    r["count_gap"] = r.pair_count - r.groupby("pool_id").pair_count.transform("median")
    r["count_below"] = r.count_gap.lt(0).astype(float)
    r["count_above"] = r.count_gap.gt(0).astype(float)
    r["logheight"] = np.log(r.mean_height.where(r.mean_height.gt(0)))
    r["logheight_gap"] = r.logheight - r.groupby("pool_id").logheight.transform("median")
    r["depression_gap"] = r.minimum_bottom_depression_deg - r.groupby("pool_id").minimum_bottom_depression_deg.transform("median")
    if domain != "global":
        r = r[r.difficulty.eq(domain)].copy()
    rows = []
    for w in workers:
        g = r[r.worker_id.eq(w)]
        # All observed buildings contribute equally to this worker's role.
        weights = 1. / g.groupby("building").image_id.transform("size").to_numpy() if len(g) else np.array([])
        row = dict(worker_id=w, domain=domain)
        for raw in ("coassign9", "coassign12", "count_gap", "logheight_gap", "depression_gap"):
            vals = g[raw].to_numpy()
            row[raw + "_mean"] = wmean(vals, weights)
            row[raw + "_sd"] = wsd(vals, weights)
            row[raw + "_p10"] = weighted_quantile(vals, weights, .1)
            row[raw + "_known_n"] = int(np.isfinite(vals).sum())
        for raw in ("dominant9", "singleton9", "count_below", "count_above"):
            row[raw + "_rate"] = wmean(g[raw].to_numpy(), weights)
        rows.append(row)
    return pd.DataFrame(rows).set_index("worker_id")


def canonical(workers, labels):
    groups = {}
    for w, c in zip(workers, labels):
        groups.setdefault(int(c), []).append(w)
    groups = sorted(groups.values(), key=min)
    return {w: f"C{i + 1:02d}" for i, group in enumerate(groups) for w in group}


def fit_hierarchy(matrix, workers, eligible, k, algorithm):
    ix = [workers.index(w) for w in eligible]
    if len(ix) < k:
        return {}, {"fit_failure": "fewer_supported_workers_than_requested_classes"}
    d = 1. - matrix[np.ix_(ix, ix)]
    np.fill_diagonal(d, 0.)
    d = np.clip(d, 0, 1)
    z = linkage(squareform(d, checks=True), method=algorithm)
    labels = cut_tree(z, n_clusters=[k]).ravel()
    return canonical(eligible, labels), {}


def fit_spectral(matrix, workers, eligible, k, signed=False):
    ix = [workers.index(w) for w in eligible]
    if len(ix) < k:
        return {}, {"fit_failure": "fewer_supported_workers_than_requested_classes"}
    affinity = matrix[np.ix_(ix, ix)].copy()
    np.fill_diagonal(affinity, 0.)
    degree = np.abs(affinity).sum(axis=1) if signed else affinity.sum(axis=1)
    ok = degree > 1e-12
    eligible = [w for w, keep in zip(eligible, ok) if keep]
    affinity = affinity[np.ix_(ok, ok)]
    degree = degree[ok]
    if len(eligible) < k:
        return {}, {"fit_failure": "insufficient_informative_relation_degree"}
    norm = affinity / np.sqrt(degree[:, None] * degree[None, :])
    vals, vecs = eigh(norm, subset_by_index=[len(degree) - k, len(degree) - 1])
    emb = vecs[:, ::-1]
    emb /= np.maximum(np.linalg.norm(emb, axis=1, keepdims=True), 1e-12)
    km = KMeans(n_clusters=k, n_init=40, random_state=SEED + k).fit(emb)
    return canonical(eligible, km.labels_), {"largest_eigenvalues": vals[::-1].tolist(),
                                            "zero_degree_workers": [w for w, keep in zip([workers[i] for i in ix], ok) if not keep]}


def fit_roles(features, eligible, k, algorithm):
    if len(eligible) < k:
        return {}, {"fit_failure": "fewer_supported_workers_than_requested_classes"}
    raw = features.loc[eligible, ROLE_FEATURES]
    median = raw.median()
    scale = (raw.quantile(.75) - raw.quantile(.25)).replace(0, np.nan)
    scale = scale.fillna(raw.std()).replace(0, 1).fillna(1)
    x = ((raw.fillna(median) - median) / scale).fillna(0).clip(-5, 5).to_numpy()
    if algorithm == "ward":
        labels = cut_tree(linkage(x, method="ward"), n_clusters=[k]).ravel()
    else:
        labels = KMeans(n_clusters=k, n_init=40, random_state=SEED + k).fit(x).labels_
    return canonical(eligible, labels), dict(feature_names=ROLE_FEATURES,
                                            median=median.to_dict(), scale=scale.to_dict(),
                                            per_feature_missing=raw.isna().sum().to_dict())


def specifications():
    out = []
    for prior in (0., 2.):
        for algorithm in ("average", "complete"):
            for k in K_VALUES:
                out.append(dict(method_id=f"R_geo9_{algorithm}_p{int(prior)}_K{k}", family="geometry_relation",
                                algorithm=algorithm, threshold=9, prior=prior, k=k, conditional=False))
    for k in K_VALUES:
        out.extend([
            dict(method_id=f"R_geo12_average_p2_K{k}", family="geometry_relation", algorithm="average", threshold=12, prior=2., k=k, conditional=False),
            dict(method_id=f"R_geo9_spectral_p2_K{k}", family="geometry_spectral", algorithm="spectral", threshold=9, prior=2., k=k, conditional=False),
            dict(method_id=f"R_geo9_source_signed_p2_K{k}", family="source_residual_relation", algorithm="signed_spectral", threshold=9, prior=2., k=k, conditional=False),
        ])
        for algorithm in ("ward", "kmeans"):
            out.append(dict(method_id=f"R_role_{algorithm}_K{k}", family="historical_role", algorithm=algorithm, k=k, conditional=False))
    for k in (2, 3, 4, 6):
        for algorithm in ("ward", "kmeans"):
            out.append(dict(method_id=f"R_role_{algorithm}_difficulty_K{k}", family="historical_role", algorithm=algorithm, k=k, conditional=True))
    return out


def fit_one(spec, workers, supports, roles, matrices, domain):
    eligible = supports[domain].query("supported").index.tolist()
    if spec["family"] == "historical_role":
        return fit_roles(roles[domain], eligible, spec["k"], spec["algorithm"])
    matrix = matrices[spec["prior"]]
    if spec["algorithm"] in ("average", "complete"):
        return fit_hierarchy(matrix[f"same{spec['threshold']}"], workers, eligible, spec["k"], spec["algorithm"])
    signed = spec["algorithm"] == "signed_spectral"
    return fit_spectral(matrix["source_residual9" if signed else "same9"], workers, eligible, spec["k"], signed=signed)


def candidate_summary(spec, lab, domain, origins, rel):
    groups = {c: sorted(w for w, v in lab.items() if v == c) for c in sorted(set(lab.values()))}
    sizes = sorted([len(g) for g in groups.values()])
    covered = sorted(lab)
    labels = [lab[w] for w in covered]
    origin = [origins[w] for w in covered]
    same = rel.worker_a.map(lab).eq(rel.worker_b.map(lab)) & rel.worker_a.isin(lab) & rel.worker_b.isin(lab)
    within = rel[same]
    supported = within[within.supported]
    return dict(method_id=spec["method_id"], domain=domain, family=spec["family"], requested_k=spec["k"],
                n_classes=len(groups), n_known=len(covered), min_class=min(sizes) if sizes else 0,
                max_class=max(sizes) if sizes else 0, class_sizes="|".join(map(str, sizes)),
                n_singleton_classes=sum(n == 1 for n in sizes), n_doubleton_classes=sum(n == 2 for n in sizes),
                workers_in_classes_ge3=sum(n for n in sizes if n >= 3),
                source_nmi=normalized_mutual_info_score(origin, labels) if len(lab) else np.nan,
                possible_within_pairs=len(within), supported_within_pairs=len(supported),
                supported_within_pair_fraction=len(supported) / len(within) if len(within) else np.nan,
                observed_within_same9_mean=supported.same9_observed.mean(),
                observed_within_same9_p10=supported.same9_observed.quantile(.1),
                observed_within_same9_min=supported.same9_observed.min())


def feasibility(labels, meta, split):
    rows = []
    phase_map = {b: phase for phase in ("history", "discovery", "validation") for b in split[f"{phase}_buildings"]}
    for (method, domain), g in labels.groupby(["method_id", "domain"], sort=True):
        mp = g[g.known].set_index("worker_id").class_id.to_dict()
        target = meta if domain == "global" else meta[meta.difficulty.eq(domain)]
        for pool_id, pool in target.groupby("pool_id", sort=True):
            counts = Counter(mp[w] for w in pool.worker_id if w in mp)
            ms = [int(x) for x in counts.values()]
            row = dict(method_id=method, domain=domain, pool_id=pool_id, image_id=pool.image_id.iloc[0],
                       building=pool.building.iloc[0], phase=phase_map[pool.building.iloc[0]],
                       difficulty=pool.difficulty.iloc[0], pool_n=len(pool), known_n=sum(ms),
                       available_classes=len(counts), largest_class_n=max(ms) if ms else 0,
                       classes_ge2=sum(n >= 2 for n in ms), classes_ge3=sum(n >= 3 for n in ms),
                       classes_ge4=sum(n >= 4 for n in ms), counts=json.dumps(dict(sorted(counts.items()))))
            rows.append(row)
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--records", type=Path, required=True)
    ap.add_argument("--assignments", type=Path, required=True)
    ap.add_argument("--split", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    split = json.loads(args.split.read_text())
    history = split["history_buildings"]
    assert not (set(history) & (set(split["discovery_buildings"]) | set(split["validation_buildings"])))
    train_key = "history_" + hashlib.sha256("|".join(sorted(history)).encode()).hexdigest()[:16]
    rec, meta, workers, origins = load_inputs(args.records, args.assignments, history)
    pairs = pair_observations(rec)
    matrices, relations = {}, {}
    for p in (0., 2.):
        matrices[p], relations[p] = relation_matrices(pairs, workers, p)
    domain_relations = {"global": relations[2.]}
    for domain in DIFFICULTIES:
        _, domain_relations[domain] = relation_matrices(pairs[pairs.difficulty.eq(domain)], workers, 2.)
    supports = {d: support(rec, workers, d) for d in ("global",) + DIFFICULTIES}
    roles = {d: role_features(rec, workers, d) for d in ("global",) + DIFFICULTIES}
    specs = specifications()
    labels, summaries, manifest, class_rows = [], [], {}, []
    for spec in specs:
        mid = spec["method_id"]
        manifest[mid] = dict(spec, train_key=train_key, domains={})
        domains = DIFFICULTIES if spec["conditional"] else ["global"]
        for domain in domains:
            lab, diagnostics = fit_one(spec, workers, supports, roles, matrices, domain)
            manifest[mid]["domains"][domain] = dict(diagnostics, groups={c: sorted(w for w, v in lab.items() if v == c) for c in sorted(set(lab.values()))})
            for w in workers:
                s = supports[domain].loc[w]
                labels.append(dict(method_id=mid, domain=domain, worker_id=w, class_id=lab.get(w, "unknown"),
                                   origin=origins[w], train_key=train_key, known=w in lab,
                                   reason="" if w in lab else "history_fewer_than_6_images_or_3_buildings" if not s.supported else "no_informative_fit",
                                   n_images=int(s.n_images), n_buildings=int(s.n_buildings), n_records=int(s.n_records),
                                   information_stage="history_before_discovery_and_validation", layer="ordinary_manual"))
            summaries.append(candidate_summary(spec, lab, domain, origins, domain_relations[domain]))
            for c, mem in manifest[mid]["domains"][domain]["groups"].items():
                rr = dict(method_id=mid, domain=domain, class_id=c, n_workers=len(mem), members="|".join(mem),
                          old_n=sum(origins[w] == "v1" for w in mem), new_n=sum(origins[w] == "new" for w in mem))
                for f in ROLE_FEATURES:
                    rr[f] = roles[domain].loc[mem, f].mean()
                class_rows.append(rr)
    label_frame = pd.DataFrame(labels)
    assert not label_frame.duplicated(["method_id", "domain", "worker_id"]).any()
    label_frame.to_csv(args.output / "worker_labels.csv.gz", index=False,
                       compression={"method": "gzip", "mtime": 0})
    pd.DataFrame(summaries).to_csv(args.output / "candidate_support.csv", index=False)
    pd.DataFrame(class_rows).to_csv(args.output / "class_roles.csv", index=False)
    f = feasibility(label_frame, meta, split)
    f.to_csv(args.output / "pool_class_feasibility.csv.gz", index=False)
    feas_summary = f.groupby(["method_id", "domain", "phase"]).agg(
        pools=("pool_id", "nunique"), buildings=("building", "nunique"),
        mean_known_n=("known_n", "mean"), pools_two_classes_ge3=("classes_ge3", lambda z: int(z.ge(2).sum())),
        pools_two_classes_ge4=("classes_ge4", lambda z: int(z.ge(2).sum())),
        pools_three_classes_ge3=("classes_ge3", lambda z: int(z.ge(3).sum()))).reset_index()
    feas_summary.to_csv(args.output / "candidate_feasibility.csv", index=False)
    role_frame = pd.concat([roles[d].reset_index().merge(supports[d].reset_index(), on="worker_id") for d in roles], ignore_index=True)
    role_frame.to_csv(args.output / "historical_roles.csv.gz", index=False)
    pd.concat([r.assign(prior_buildings=p) for p, r in relations.items()], ignore_index=True).to_csv(args.output / "historical_pair_relations.csv.gz", index=False)
    pd.concat([r.assign(domain=d) for d, r in domain_relations.items() if d != "global"], ignore_index=True).to_csv(args.output / "historical_pair_relations_conditional.csv.gz", index=False)
    write_json(args.output / "CANDIDATE_MANIFEST.json", manifest)
    receipt = dict(schema="reverse_composition_history_candidates_v1", train_key=train_key,
                   history_buildings=history, records=len(rec), images=rec.image_id.nunique(),
                   buildings=rec.building.nunique(), workers=len(workers),
                   history_supported_workers={d: int(s.supported.sum()) for d, s in supports.items()},
                   pair_observations=len(pairs), supported_pairs=int(relations[2.].supported.sum()),
                   possible_pairs=len(relations[2.]), n_methods=len(specs), n_global_methods=sum(not s["conditional"] for s in specs),
                   n_conditional_methods=sum(s["conditional"] for s in specs), label_rows=len(label_frame),
                   label_sha256=sha(args.output / "worker_labels.csv.gz"),
                   label_content_sha256=hashlib.sha256(label_frame.to_csv(index=False).encode()).hexdigest(), seed=SEED,
                   inputs={str(p): sha(p) for p in (args.records, args.assignments, args.split)},
                   code_sha256=sha(Path(__file__)), classification_Q_used=False, target_geometries_used=False,
                   target_Q_or_reference_used=False, new_fusion_calls=0,
                   known_imputation="Unobserved relation is separately flagged; unsigned clustering alone uses training-global prior. Source-residual relation uses zero absence of edge; not an observed similarity.",
                   source_residual="Subtract within-history-image same-source-pair coassignment baseline, then image/building equal aggregation and two-building shrinkage to zero.",
                   missing_roles="Median imputation after preserving counts; missingness indicators do not enter roles.",
                   classification_scope="ordinary_manual only; unknown is not a class; target metadata only used for composition feasibility",
                   comparisons_not_yet_run="No fusion-outcome comparisons or discovery/validation quality scores read by this script.")
    write_json(args.output / "RUN_RECEIPT.json", receipt)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
