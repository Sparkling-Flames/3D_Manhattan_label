#!/usr/bin/env python3
"""History-building-only forward personnel types for composition experiments.

Scientific feature estimators are reused unchanged from the pinned repository.
No target-building quality, geometry, membership votes or fusion outcome enters
the fit. This file only writes small training features, labels and a ledger.
"""
from __future__ import annotations
import os
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
import argparse
import ast
import gzip
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, cut_tree
from scipy.spatial.distance import squareform
from sklearn.cluster import KMeans
from sklearn.mixture import GaussianMixture
from sklearn.decomposition import PCA
from sklearn.metrics import adjusted_mutual_info_score, silhouette_score

SEED = 20261019
DIFFS = ("easy", "medium", "hard")
KS = (2, 3, 4, 5, 6, 8)
FEATURE_SOURCE = "research/workers/personnel_type_discovery_next_20261019/work_personnel_typing_A_20261019/forward/build_features.py"
PROFILE_SOURCE = "research/workers/pro_personnel_v2_archive_20261019/work_v2_20261019/profiles/run_profiles.py"
RECORD_SOURCE = "research/statistics/v2_evidence_audit_20261019/records.json.gz"
DOMAINS = {
    "Q": ["q_beta", "q_abs_mean", "q_abs_p10", "q_abs_sd", "q_residual_p10", "q_residual_sd"],
    "T": ["t_source_origin_effect", "t_log_residual_tail"],
    "difficulty": ["hard_minus_easy", "hard_minus_medium"],
    "structure": ["pair_count_effect", "pair_count_residual_sd", "bottom_y_effect", "top_y_effect", "height_log_effect"],
    "semi": ["semi_old_error_nonedit_effect", "semi_new_error_nonedit_effect", "semi_old_edit_effect", "semi_new_edit_effect"],
    "scope": ["scope_out_effect"],
}


def clean(x):
    if isinstance(x, dict):
        return {str(k): clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple, np.ndarray)):
        return [clean(v) for v in x]
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    if isinstance(x, (float, np.floating)):
        return float(x) if np.isfinite(x) else None
    return x


def js(path, x):
    Path(path).write_text(json.dumps(clean(x), ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def upstream_functions(repo):
    """Import pure functions without depending on the old recovery path layout."""
    spec = importlib.util.spec_from_file_location("frozen_profile_estimators", repo / PROFILE_SOURCE)
    native = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(native)
    wanted = {"safe_num", "key", "extra_frame", "numeric_group_stats", "effect", "_training_features"}
    tree = ast.parse((repo / FEATURE_SOURCE).read_text())
    nodes = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in wanted]
    assert {node.name for node in nodes} == wanted
    env = {"np": np, "pd": pd, "NATIVE": native, "DIFFS": DIFFS, "json": json}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(repo / FEATURE_SOURCE), "exec"), env)
    return native, env


def flatten(evidence):
    """Same upstream scalar contract, without unrelated old-version tables."""
    scalar = ["object_id", "worker_id", "image_id", "image_code", "building_id", "room_id", "condition", "origin", "current_class", "quality_usable", "quality_use", "pool_analysis_eligible", "independent_vote_eligible", "B8L2", "D10", "source_active_time_seconds", "target_matched_time_seconds", "reference_id", "reference_version", "point_count", "declared_pair_count", "is_doorway", "is_oos", "cleaning_disposition", "calculation_class", "IoU3D100", "binding_status", "ring_confirmed"]
    rows = []
    for e in evidence:
        r = {k: e.get(k) for k in scalar}
        r["ordinary_difficulty_eligible"] = (e.get("binding_evidence") or {}).get("ordinary_difficulty_eligible", False)
        r["difficulty_reference_match"] = (e.get("binding_evidence") or {}).get("chosen_target_is_current", False)
        r["time_source_kind"] = (e.get("time_evidence") or {}).get("source_kind")
        m = (e.get("measurements") or {}).get("same_reference_measurements") or {}
        for c in ["iou_2d", "S_bottom_deg", "dir", "Hmean", "Hcenter", "height_mean_ratio"]:
            r[c] = m.get(c)
        dr = (e.get("image_evidence") or {}).get("difficulty_record") or {}
        r["reference_pair_count"] = dr.get("N_floor")
        r["reference_hidden_count"] = dr.get("H")
        rows.append(r)
    d = pd.DataFrame(rows)
    d["difficulty"] = d.current_class.map({"简单": "easy", "中等": "medium", "困难": "hard"}).fillna("special_or_unknown")
    d["task"] = d[["image_id", "condition", "reference_id", "reference_version"]].fillna("").apply(lambda r: json.dumps(r.tolist(), ensure_ascii=False, separators=(",", ":")), axis=1)
    d["source_task"] = d[["image_id", "condition"]].fillna("").apply(lambda r: json.dumps(r.tolist(), ensure_ascii=False, separators=(",", ":")), axis=1)
    assert d.object_id.is_unique
    return d


def robust(a):
    a = np.asarray(a, float)
    med = np.nanmedian(a, axis=0)
    scale = np.nanpercentile(a, 75, axis=0) - np.nanpercentile(a, 25, axis=0)
    scale = np.where(scale > 1e-10, scale, 1.4826 * np.nanmedian(np.abs(a - med), axis=0))
    scale = np.where(scale > 1e-10, scale, np.nanstd(a, axis=0))
    scale = np.where(scale > 1e-10, scale, 1.0)
    return np.clip((a - med) / scale, -3, 3), med, scale


def domain_distance(f, domain_names):
    n = len(f)
    summed = np.zeros((n, n))
    weights = np.zeros((n, n))
    metadata = {}
    euclidean = []
    for name in domain_names:
        cols = [col for col in DOMAINS[name] if f[col].notna().sum() >= 6 and f[col].std() > 1e-10]
        if not cols:
            continue
        a, center, scale = robust(f[cols].to_numpy(float))
        metadata[name] = {"features": cols, "center": center, "scale": scale, "nonmissing_workers": f[cols].notna().sum().to_dict()}
        diff = (a[:, None, :] - a[None, :, :]) ** 2
        mask = np.isfinite(diff)
        w = mask.sum(axis=2)
        val = np.nansum(diff, axis=2) / np.maximum(w, 1)
        summed += np.where(w > 0, val, 0)
        weights += w > 0
        if np.isfinite(a).all():
            euclidean.append(a / np.sqrt(len(cols)))
    dist = np.sqrt(summed / np.maximum(weights, 1))
    dist[weights == 0] = np.nan
    np.fill_diagonal(dist, 0)
    assert np.isfinite(dist).all(), "No common feature domain: do not silently impute distance"
    x = np.column_stack(euclidean) / np.sqrt(len(euclidean)) if len(euclidean) == len(metadata) and euclidean else None
    return dist, x, metadata, weights


def medoid_cluster(d, k, seed):
    """Deterministic multistart alternate K-medoids over masked distances."""
    rng = np.random.default_rng(seed)
    n = len(d)
    best = None
    for _ in range(16):
        med = [int(rng.integers(n))]
        while len(med) < k:
            p = d[:, med].min(1) ** 2
            p[med] = 0
            cand = int(rng.choice(n, p=p / p.sum())) if p.sum() else min(set(range(n)) - set(med))
            med.append(cand)
        for _step in range(80):
            labels = np.argmin(d[:, med], axis=1)
            # A medoid keeps its own class even when workers have equal profiles.
            labels[med] = np.arange(k)
            updated = []
            for j in range(k):
                ix = np.flatnonzero(labels == j)
                updated.append(int(ix[np.argmin(d[np.ix_(ix, ix)].sum(1))]))
            if updated == med:
                break
            med = updated
        score = float(d[np.arange(n), np.asarray(med)[labels]].sum())
        tie = tuple(med)
        if best is None or (score, tie) < (best[0], best[1]):
            best = score, tie, labels.copy()
    return best[2], {"within_medoid_distance_sum": best[0], "medoid_indices": best[1], "starts": 16, "max_iterations": 80}


def canonical(labels, f):
    """Numerical IDs ordered by training mean Q, with member IDs tie-breaking."""
    labels = np.asarray(labels)
    order = sorted(np.unique(labels), key=lambda lab: (float(f.loc[labels == lab, "q_beta"].mean()), tuple(f.loc[labels == lab, "worker_id"])))
    mapping = {lab: f"C{i+1:02d}" for i, lab in enumerate(order)}
    return np.array([mapping[x] for x in labels])


def ordinal(f, col, k):
    """Training quantiles are rank levels, not a claim of natural clusters."""
    good = f[col].notna()
    vals = f.loc[good, col].to_numpy()
    edges = np.unique(np.quantile(vals, np.arange(1, k) / k))
    labels = np.searchsorted(edges, vals, side="left")
    return good, labels, {"column": col, "edges": edges, "requested_k": k, "actual_k": int(len(np.unique(labels))), "meaning": "training quantile ordinal bin; no natural-cluster claim"}


def conditional_features(d, f, buildings, fn, metric):
    """Additional history estimates for their own qualified condition only.

    The smaller doorway/Semi panels use a declared 4-task/3-building gate;
    these features are only admitted to their conditional methods, never to the
    ordinary Manual multiview classes.
    """
    f = f.copy()
    panels = {
        "doorway": d.quality_usable & d.condition.eq("manual") & d.quality_use.eq("doorway_quality"),
        "semi_v1": d.quality_usable & d.condition.eq("semi") & d.quality_use.eq("ordinary_primary") & d.origin.eq("v1"),
        "semi_new": d.quality_usable & d.condition.eq("semi") & d.quality_use.eq("ordinary_primary") & d.origin.eq("new"),
        "special_manual": d.quality_usable & d.condition.eq("manual") & d.quality_use.eq("special_conditional_only"),
        "special_semi": d.quality_usable & d.condition.eq("semi") & d.quality_use.eq("special_conditional_only"),
    }
    meta = {}
    for name, mask in panels.items():
        a = d[mask & d.building_id.isin(buildings)].copy()
        beta, fit = fn["effect"](a, metric)
        detail, _ = fn["effect"](a, "declared_pair_count", ridge=5)
        groups = dict(tuple(a.groupby("worker_id")))
        for i, r in f.iterrows():
            g = groups.get(r.worker_id, a.iloc[:0])
            supported = g.task.nunique() >= 4 and g.building_id.nunique() >= 3
            for col, val in {"records": len(g), "tasks": g.task.nunique(), "buildings": g.building_id.nunique(), "supported": supported, "q_effect": beta.get(r.worker_id, np.nan) if supported else np.nan, "q_abs_mean": g[metric].mean(), "pair_effect": detail.get(r.worker_id, np.nan) if supported else np.nan}.items():
                f.loc[i, name + "_" + col] = val
        f[name + "_supported"] = f[name + "_supported"].astype(bool)
        meta[name] = {"training_records": len(a), "training_images": a.image_id.nunique(), "training_buildings": a.building_id.nunique(), "supported_workers": int(f[name + "_supported"].sum()), "gate": {"tasks": 4, "buildings": 3}, "q_fit": fit}
    return f, meta


class Catalog:
    def __init__(self, f, train_key):
        self.f = f.reset_index(drop=True)
        self.train_key = train_key
        self.rows = []
        self.methods = {}
        self.fingerprints = {}

    def add(self, method_id, labels, subset=None, domain="all", route="forward", params=None, features=None, description="", distance=None):
        if subset is None:
            subset = np.ones(len(self.f), bool)
        subset = np.asarray(subset, bool)
        g = self.f.loc[subset].copy()
        labels = canonical(labels, g)
        assert len(labels) == len(g)
        full = np.full(len(self.f), "unknown", object)
        full[subset] = labels
        fp = hashlib.sha256(json.dumps([domain, sorted(zip(self.f.worker_id, full))], separators=(",", ":")).encode()).hexdigest()
        alias = self.fingerprints.get(fp)
        if alias is None:
            self.fingerprints[fp] = method_id
        sizes = pd.Series(labels).value_counts().sort_index().to_dict()
        classinfo = {}
        focus = list(dict.fromkeys(["q_beta", "q_abs_mean", "q_abs_p10", "q_residual_sd", "pair_count_effect", "bottom_y_effect", "height_log_effect", "t_source_origin_effect", "hard_minus_easy", "hard_minus_medium", *[v for vals in DOMAINS.values() for v in vals], *[v for v in (features or []) if v in self.f.columns]]))
        for lab in sorted(sizes):
            h = g.loc[labels == lab]
            traits = []
            for col, low, high in [("q_beta", "相对质量较低", "相对质量较高"), ("pair_count_effect", "历史点数偏少", "历史点数偏多"), ("q_residual_sd", "质量波动较小", "质量波动较大")]:
                delta = h[col].median() - self.f[col].median()
                scale = self.f[col].quantile(.75) - self.f[col].quantile(.25)
                if scale > 0 and abs(delta) > .25 * scale:
                    traits.append(high if delta > 0 else low)
            classinfo[lab] = {"n": len(h), "members": h.worker_id.tolist(), "name_zh": "；".join(traits) if traits else "训练画像居中", "origin_counts": h.person_origin.fillna("unknown").value_counts().to_dict(), "feature_means": h[focus].mean().to_dict(), "feature_medians": h[focus].median().to_dict(), "core_tasks_min": h.core_tasks.min(), "core_buildings_min": h.core_buildings.min()}
        ami = adjusted_mutual_info_score(g.person_origin.fillna("unknown"), labels) if len(g) else None
        sil = None
        if distance is not None and 1 < len(sizes) < len(g):
            sil = silhouette_score(distance, labels, metric="precomputed")
        self.methods[method_id] = {"method_id": method_id, "route": route, "domain": domain, "description": description, "parameters": params or {}, "features": features or [], "known_workers": int(subset.sum()), "unknown_workers": int((~subset).sum()), "actual_classes": len(sizes), "class_sizes": sizes, "classes": classinfo, "origin_adjusted_mutual_information": ami, "intrinsic_silhouette_descriptive_only": sil, "partition_sha256": fp, "alias_of": alias, "status": "candidate_frozen_without_discovery_or_validation_results" if len(sizes) >= 2 else "not_fit_insufficient_supported_history"}
        for (_, r), lab in zip(self.f.iterrows(), full):
            self.rows.append({"method_id": method_id, "domain": domain, "worker_id": r.worker_id, "class_id": lab, "origin": r.person_origin, "train_key": self.train_key, "known": lab != "unknown", "reason": "supported_history" if lab != "unknown" else "insufficient_required_history_opportunity"})


def candidates(f, train_key):
    cat = Catalog(f, train_key)
    core = f.core_supported.fillna(False).astype(bool)
    # Quality only and structural ordinal baselines.
    for col, short in [("q_beta", "Q"), ("q_abs_mean", "Qabs"), ("q_residual_p10", "Qtail"), ("pair_count_effect", "Detail")]:
        for k in KS:
            g = f.loc[core & f[col].notna()]
            valid, lab, par = ordinal(g, col, k)
            cat.add(f"F_rule_{short}_quantile_K{k}", lab, core & f[col].notna(), params=par, features=[col], description="历史训练分位组；分位数不代表天然人群")
    for threshold in [0, 3]:
        good = core & f.q_beta.notna()
        q = f.loc[good, "q_beta"].to_numpy()
        lab = (q >= 0).astype(int) if threshold == 0 else np.where(q <= -3, 0, np.where(q >= 3, 2, 1))
        cat.add(f"F_rule_Q_threshold_K{2 if threshold==0 else 3}", lab, good, features=["q_beta"], params={"thresholds": [0] if threshold == 0 else [-3, 3]}, description="相对同任务同伴质量方向分组")
    # Q crossed with independently interpretable tendency, no aggregate score.
    for qk in [2, 3]:
        for feature, short in [("pair_count_effect", "Detail"), ("q_residual_sd", "Volatility"), ("t_source_origin_effect", "Time"), ("hard_minus_easy", "HardLift")]:
            good = core & f.q_beta.notna() & f[feature].notna()
            g = f.loc[good]
            _, qlab, qparams = ordinal(g, "q_beta", qk)
            split = float(g[feature].median()) if feature == "q_residual_sd" else 0.
            sec = (g[feature].to_numpy() >= split).astype(int)
            cat.add(f"F_rule_Q{qk}x{short}2", qlab * 2 + sec, good, params={"quality": qparams, "second_column": feature, "second_threshold": split}, features=["q_beta", feature], description="质量层级与历史倾向交叉，未将变量相加")
    for diff in DIFFS:
        for k in [2, 3, 4]:
            col = "theta_" + diff
            good = core & f[col].notna()
            _, lab, par = ordinal(f.loc[good], col, k)
            cat.add(f"F_cond_{diff}_Q_K{k}", lab, good, domain=diff, params=par, features=[col], description="该难度有支持的历史任务调整质量；仅当难度采集前已知时可用于选人")
        good = core & f["theta_"+diff].notna() & f.q_beta.notna()
        g = f.loc[good]
        qlab = (g.q_beta.to_numpy() >= 0).astype(int)
        adapt = (g["theta_"+diff].to_numpy() - g.q_beta.to_numpy() >= 0).astype(int)
        cat.add(f"F_cond_{diff}_Q2xAdapt2", qlab * 2 + adapt, good, domain=diff, params={"Q_threshold": 0, "adaptation_threshold": 0}, features=["q_beta", "theta_"+diff], description="总体质量与该难度相对本人总体的适应交叉")
    families = {"Q": ["Q"], "QS": ["Q", "structure"], "S": ["structure"], "QTDS": ["Q", "T", "difficulty", "structure"], "AllMasked": list(DOMAINS)}
    for family, domains in families.items():
        good = core.copy()
        g = f.loc[good]
        dist, x, meta, weights = domain_distance(g, domains)
        for k in KS:
            if len(g) <= k:
                continue
            for algorithm in ["average", "medoids"]:
                if algorithm == "average":
                    lab = cut_tree(linkage(squareform(dist, checks=True), method="average"), n_clusters=k).ravel()
                    par = {"linkage": "average"}
                else:
                    lab, par = medoid_cluster(dist, k, SEED + 101 * k)
                par.update({"k": k, "seed": SEED + 101 * k, "distance": "equal-domain RMS; unavailable pairwise feature opportunities masked", "domain_transforms": meta, "common_domains_min": weights[np.triu_indices(len(g), 1)].min(), "common_domains_median": np.median(weights[np.triu_indices(len(g), 1)])})
                cat.add(f"F_{algorithm}_{family}_K{k}", lab, good, params=par, features=domains, description="训练画像域等权分组；缺机会不补零", distance=dist)
            if x is not None:
                lab = KMeans(n_clusters=k, n_init=40, random_state=SEED).fit_predict(x)
                cat.add(f"F_kmeans_{family}_K{k}", lab, good, params={"k": k, "n_init": 40, "seed": SEED, "domain_transforms": meta}, features=domains, description="完整支持域的稳健标准化K均值", distance=dist)
        if x is not None:
            # A small PCA space limits mixture covariance complexity at N<=60.
            comp = min(4, x.shape[1])
            pc = PCA(n_components=comp, svd_solver="full").fit_transform(x)
            for k in [2, 3, 4, 5, 6]:
                gm = GaussianMixture(n_components=k, covariance_type="diag", n_init=10, reg_covar=.025, random_state=SEED).fit(pc)
                lab = gm.predict(pc)
                cat.add(f"F_gmm_{family}_K{k}", lab, good, params={"k": k, "components": comp, "covariance": "diag", "n_init": 10, "reg_covar": .025, "seed": SEED, "BIC_descriptive_only": gm.bic(pc), "domain_transforms": meta}, features=domains, description="低维训练画像混合模型候选；BIC不代替实际融合效用", distance=dist)
    # Source-specific Semi opportunities keep their distinct evidence strength.
    for source, short in [("v1", "old"), ("new", "new")]:
        col = f"semi_{short}_error_nonedit_effect"
        good = f[col].notna() & f.person_origin.eq(source)
        for k in [2, 3]:
            if good.sum() > k:
                _, lab, par = ordinal(f.loc[good], col, k)
                cat.add(f"F_semi_{short}_nonedit_K{k}", lab, good, domain=f"semi_{source}", features=[col], params=par, description="旧确认错误/新报告错误分层的历史未修改倾向；不是确认纠正能力")
            else:
                cat.add(f"F_semi_{short}_nonedit_K{k}", [], np.zeros(len(f), bool), domain=f"semi_{source}", features=[col], params={"requested_k": k, "supported_workers": int(good.sum()), "gate": {"error_opportunities": 3, "buildings": 2}}, description="历史确认/报告错误机会不足，未拟合；未知不归为同一人员类别")
        col = f"semi_{short}_edit_effect"
        good = f[col].notna() & f.person_origin.eq(source)
        if good.sum() >= 6:
            _, lab, par = ordinal(f.loc[good], col, 2)
            cat.add(f"F_semi_{short}_edit_K2", lab, good, domain=f"semi_{source}", features=[col], params=par, description="对应来源的历史编辑倾向；编辑不等于纠正")
    good = core & f.scope_out_effect.notna()
    if good.sum() >= 6:
        for k in [2, 3]:
            _, lab, par = ordinal(f.loc[good], "scope_out_effect", k)
            cat.add(f"F_scope_propensity_K{k}", lab, good, features=["scope_out_effect"], params=par, description="scope回答倾向，未知不并入一类；不能视作裁定正确率")
    for condition in ["doorway", "semi_v1", "semi_new", "special_manual", "special_semi"]:
        col = condition + "_q_effect"
        if col not in f:
            continue
        good = f[col].notna()
        for k in [2, 3]:
            if good.sum() > k:
                _, lab, par = ordinal(f.loc[good], col, k)
                par["support_gate"] = {"qualified_condition_tasks": 4, "buildings": 3}
                cat.add(f"F_{condition}_finalQ_K{k}", lab, good, domain=condition, features=[col], params=par, description="本条件质量合格历史最终Q，不推断逐份净改善；与普通Manual支持分开")
            else:
                cat.add(f"F_{condition}_finalQ_K{k}", [], np.zeros(len(f), bool), domain=condition, features=[col], params={"requested_k": k, "supported_workers": int(good.sum()), "gate": {"tasks": 4, "buildings": 3}}, description="本条件历史任务不足，未拟合")
    return cat


def read_history(split):
    for key in ["history_buildings", "train_buildings", "history"]:
        if key in split:
            a = split[key]
            return sorted(a.get("buildings", a) if isinstance(a, dict) else a)
    if "splits" in split:
        return read_history(split["splits"])
    raise KeyError("split JSON must expose history_buildings / train_buildings / history")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=Path, required=True)
    ap.add_argument("--split", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--metric", choices=["B8L2", "D10"], default="B8L2")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    split = json.loads(args.split.read_text())
    buildings = read_history(split)
    train_key = "history_" + hashlib.sha256("|".join(buildings).encode()).hexdigest()[:16]
    native, fn = upstream_functions(args.repo)
    evidence = json.load(gzip.open(args.repo / RECORD_SOURCE, "rt"))["records"]
    d = flatten(evidence)
    extras = fn["extra_frame"](evidence)
    workers = sorted(d.loc[d.quality_usable, "worker_id"].unique())
    f, fitmeta = fn["_training_features"](d, extras, workers, buildings, args.metric)
    f, conditionalmeta = conditional_features(d, f, buildings, fn, args.metric)
    fitmeta["conditional_history"] = conditionalmeta
    f.insert(0, "train_key", train_key)
    f.to_csv(args.out / "features_train.csv.gz", index=False)
    cat = candidates(f, train_key)
    labels = pd.DataFrame(cat.rows)
    labels.to_csv(args.out / "worker_labels.csv.gz", index=False)
    flat = []
    for mid, m in cat.methods.items():
        flat.append({k: m[k] for k in ["method_id", "domain", "description", "known_workers", "unknown_workers", "actual_classes", "origin_adjusted_mutual_information", "intrinsic_silhouette_descriptive_only", "partition_sha256", "alias_of", "status"]} | {"class_sizes": ";".join(f"{c}:{n}" for c, n in m["class_sizes"].items())})
    pd.DataFrame(flat).to_csv(args.out / "candidate_ledger.csv", index=False)
    js(args.out / "method_manifest.json", {"seed": SEED, "history_buildings": buildings, "train_key": train_key, "metric": args.metric, "features_train_sha256": sha(args.out / "features_train.csv.gz"), "prohibited_target_inputs": ["discovery/validation Q", "discovery/validation geometry", "target votes or clusters", "fusion results"], "methods": cat.methods})
    js(args.out / "feature_fit_receipt.json", {"fit": fitmeta, "train_key": train_key, "metric": args.metric, "source_hashes": {p: sha(args.repo / p) for p in [RECORD_SOURCE, PROFILE_SOURCE, FEATURE_SOURCE]}, "split_sha256": sha(args.split), "code_sha256": sha(__file__), "workers": len(workers), "known_core": int(f.core_supported.sum()), "candidate_count": len(cat.methods), "unique_partition_count": sum(m["alias_of"] is None for m in cat.methods.values()), "reuse": "AST imports unchanged pure feature functions; only exact training buildings supplied"})
    print(json.dumps({"workers": len(f), "core_supported": int(f.core_supported.sum()), "candidates": len(cat.methods), "unique_partitions": sum(m["alias_of"] is None for m in cat.methods.values()), "labels": len(labels), "history_buildings": buildings}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
