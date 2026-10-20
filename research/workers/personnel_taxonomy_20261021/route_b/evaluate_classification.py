"""Held-building expression checks and descriptive auxiliary interpretation.

Taxonomy is read from already frozen label files. This program does not choose
classes using any fusion outcome, change eligibility, or rescore annotations.
"""
from __future__ import annotations

import argparse
import gzip
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

from run_classification import HERE, ROOT, NAMES, DESCRIPTORS, KEY, load_expression

SOURCE = "research/statistics/v2_evidence_audit_20261019/records.json.gz"
CONDITIONS = "research/difficulty/difficulty_mechanisms_v2_20261020/record_conditions.csv.gz"


def write(df, path):
    df.to_csv(path, index=False, encoding="utf-8-sig")


def load_metadata(source):
    records = json.load(gzip.open(source, "rt", encoding="utf8"))["records"]
    rows = []
    for r in records:
        scope, attr, ref = r["scope_evidence"], r["exclusion_attribution"], r["reference_evidence"]
        p = r.get("points_1024x512")
        pts = np.asarray(p, dtype=float) if p else np.empty((0, 2))
        rows.append(dict(object_id=r["object_id"], B8L2=r.get("B8L2"), D10=r.get("D10"),
            target_matched_time_seconds=r.get("target_matched_time_seconds"),
            source_active_time_seconds=r.get("source_active_time_seconds"),
            time_source_kind=r["time_evidence"].get("source_kind"),
            scope_response=scope.get("response"), scope_response_recorded=scope.get("response_recorded"),
            scope_judgement_opportunity=scope.get("judgement_opportunity"), scope_correct=scope.get("correct"),
            historical_worker_exclusion=attr.get("historical_worker_exclusion"),
            exclusion_attribution=attr.get("category"),
            top_y_mean=float(np.mean(pts[::2, 1])) if len(pts) else np.nan,
            bottom_y_mean=float(np.mean(pts[1::2, 1])) if len(pts) else np.nan))
    return pd.DataFrame(rows)


def summaries_from_panels(panels, group_cols, metrics):
    rows = []
    for keys, d in panels.groupby(group_cols, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = dict(zip(group_cols, keys))
        row.update(n_panels=len(d), n_images=d.image_id.nunique(), n_buildings=d.building_id.nunique())
        for m in metrics:
            bs = d.groupby(["building_id", "image_id"])[m].mean().groupby("building_id").mean().dropna()
            valid = d[d[m].notna()]
            row[m + "_building_mean"] = bs.mean()
            row[m + "_image_mean"] = d.groupby("image_id")[m].mean().mean()
            row[m + "_positive_buildings"] = int(bs.gt(1e-10).sum())
            row[m + "_negative_buildings"] = int(bs.lt(-1e-10).sum())
            row[m + "_building_n"] = len(bs)
            row[m + "_panel_n"] = len(valid)
            row[m + "_image_n"] = valid.image_id.nunique()
        rows.append(row)
    return pd.DataFrame(rows)


def matched_contrasts(d):
    metrics = DESCRIPTORS + ["B8L2", "D10", "reduced_qualified", "unmatched_ref_9_qualified", "bottom_bias_9_qualified"]
    rows = []
    for source in ["all", "v1", "new"]:
        ds = d if source == "all" else d[d.origin.eq(source)]
        for (condition, layer, image, reference), g in ds.groupby(KEY, dropna=False):
            for level in ["coarse_class", "fine_class"]:
                known = g[g[level].ne("unassigned")]
                for lo, hi in itertools.combinations(sorted(known[level].unique()), 2):
                    a, b = known[known[level].eq(hi)], known[known[level].eq(lo)]
                    if len(a) < 2 or len(b) < 2:
                        continue
                    row = dict(condition=condition, layer=layer, image_id=image, reference_id=reference,
                        image_code=g.iloc[0].image_code, building_id=g.iloc[0].building_id,
                        difficulty=g.iloc[0].difficulty, mechanism=g.iloc[0].mechanism,
                        ref_turn5=g.iloc[0].ref_turn5, source=source, level=level,
                        class_high=hi, class_low=lo, n_high=len(a), n_low=len(b))
                    for m in metrics:
                        aa, bb = a[m].dropna(), b[m].dropna()
                        matched = len(aa) >= 2 and len(bb) >= 2
                        row[m + "_difference"] = aa.mean() - bb.mean() if matched else np.nan
                        row[m + "_high"] = aa.mean() if matched else np.nan
                        row[m + "_low"] = bb.mean() if matched else np.nan
                        row[m + "_n_high"] = len(aa)
                        row[m + "_n_low"] = len(bb)
                    rows.append(row)
    panels = pd.DataFrame(rows)
    group = ["condition", "layer", "source", "level", "class_high", "class_low"]
    summary = summaries_from_panels(panels, group, [m + "_difference" for m in metrics])
    difficulty = summaries_from_panels(panels, group + ["difficulty"], [m + "_difference" for m in metrics])
    # Fixed reference turn count plus geometric condition; reference-dependent rates keep original gate.
    fixed6 = panels[panels.ref_turn5.eq(6)].copy()
    fixed6_summary = summaries_from_panels(fixed6, group + ["mechanism"],
        ["reduced_qualified_difference", "reduced_qualified_high", "reduced_qualified_low",
         "turn_n_difference", "short_turn_edges_difference"])
    return panels, summary, difficulty, fixed6_summary


def profile_people(x, final):
    rows = []
    for (worker, condition), g in x.groupby(["worker_id", "condition"]):
        ordinary = g[g.layer.eq("ordinary")]
        q = ordinary[ordinary.quality_usable & ordinary.B8L2.notna()]
        t = ordinary[ordinary.primary_expression & ordinary.source_active_time_seconds.gt(0)]
        target_t = ordinary[ordinary.primary_expression & ordinary.target_matched_time_seconds.gt(0)]
        v = ordinary[ordinary.classification_observation]
        row = dict(worker_id=worker, condition=condition, n_inventory=len(g), n_ordinary=len(ordinary),
            n_quality=len(q), n_time=len(t),
            n_historical_not_accepted=int(g.cleaning_disposition.eq("historical_not_accepted").sum()),
            n_excluded_by_review=int(g.cleaning_disposition.eq("excluded_by_review").sum()),
            n_retained_pending=int(g.cleaning_disposition.eq("retained_pending").sum()),
            n_not_quality_usable=int((~g.quality_usable).sum()),
            n_historical_worker_exclusion=int(g.historical_worker_exclusion.eq(True).sum()),
            n_scope_recorded=int(g.scope_response_recorded.eq(True).sum()),
            n_scope_non_in_scope=int((g.scope_response_recorded.eq(True) & g.scope_response.ne("in_scope")).sum()),
            n_scope_judged=int(g.scope_judgement_opportunity.eq(True).sum()),
            n_scope_correct=int(g.scope_correct.eq(True).sum()),
            q_mean=q.B8L2.mean(), q_p10=q.B8L2.quantile(.1), d10_mean=q.D10.mean(),
            q_building_mean=q.groupby("building_id").B8L2.mean().mean(),
            q_peer_adjusted=q.groupby("building_id").q_peer_delta.mean().mean(),
            t_median_seconds=t.source_active_time_seconds.median(),
            t_measurement="source_active_time_seconds_within_origin",
            time_source_kind="|".join(sorted(t.time_source_kind.dropna().unique())),
            target_time_median_seconds=target_t.target_matched_time_seconds.median(),
            n_target_time=len(target_t),
            t_log_peer_adjusted=t.groupby("building_id").t_log_peer_delta.mean().mean(),
            n_near_collinear_images=int(v.near_straight_nodes_5deg.gt(0).sum()),
            n_near_collinear_buildings=v[v.near_straight_nodes_5deg.gt(0)].building_id.nunique(),
            n_exact_initialization=int(g.semi_exact_initialization.eq(True).sum()),
            n_edit_known=int(g.semi_edited.notna().sum()), n_edited=int(g.semi_edited.eq(True).sum()),
            n_raw_pairs_removed=int(g.semi_raw_pair_delta.lt(0).sum()),
            n_raw_pairs_added=int(g.semi_raw_pair_delta.gt(0).sum()),
            n_confirmed_error_opportunities=int(g.semi_error_confirmed.eq(True).sum()),
            n_confirmed_error_unchanged=int((g.semi_error_confirmed.eq(True) & g.semi_known_error_unchanged.eq(True)).sum()),
            n_reported_error_opportunities=int(g.semi_error_reported.eq(True).sum()),
            n_reported_error_unchanged=int((g.semi_error_reported.eq(True) & g.semi_reported_error_unchanged.eq(True)).sum()))
        for diff, gg in q.groupby("difficulty"):
            row[f"q_mean_{diff}"] = gg.B8L2.mean()
            row[f"q_n_{diff}"] = len(gg)
            row[f"q_peer_{diff}"] = gg.groupby("building_id").q_peer_delta.mean().mean()
        for metric in [c + "_peer_delta" for c in DESCRIPTORS] + ["top_y_mean_peer_delta", "bottom_y_mean_peer_delta"]:
            b = v.groupby("building_id")[metric].mean()
            row[metric + "_mean"] = b.mean()
            row[metric + "_positive_buildings"] = int(b.gt(0).sum())
            row[metric + "_negative_buildings"] = int(b.lt(0).sum())
        rows.append(row)
    fields = ["worker_id", "condition", "coarse_class", "fine_class", "coarse_name_zh", "fine_name_zh", "fine_status", "origin"]
    return final[fields].merge(pd.DataFrame(rows), on=["worker_id", "condition"], how="left")


def aggregate_profiles(profiles):
    rows = []
    means = ["q_mean", "q_p10", "d10_mean", "q_building_mean", "q_peer_adjusted", "t_median_seconds", "t_log_peer_adjusted", "q_mean_简单", "q_mean_中等", "q_mean_困难", "q_peer_简单", "q_peer_中等", "q_peer_困难"]
    counts = [c for c in profiles if c.startswith("n_")]
    for (condition, fine, origin), g in profiles[profiles.fine_class.ne("unassigned")].groupby(["condition", "fine_class", "origin"], dropna=False):
        row = dict(condition=condition, fine_class=fine, origin=origin, people=len(g), members="|".join(g.worker_id))
        for m in means:
            if m in g:
                row[m + "_person_mean"] = g[m].mean()
                row[m + "_person_median"] = g[m].median()
                row[m + "_person_n"] = int(g[m].notna().sum())
        for c in counts:
            row[c] = g[c].sum()
        rows.append(row)
    return pd.DataFrame(rows)


def model_design(d, version, levels, qcenter):
    cols = [np.ones(len(d))]
    if "origin" in version:
        cols.append(d.origin.eq("new").astype(float).to_numpy())
    if "q" in version:
        q = d.q_history.to_numpy(dtype=float)
        cols += [np.where(np.isfinite(q), q - qcenter, 0) / 10, (~np.isfinite(q)).astype(float)]
    if "class" in version:
        for level in levels[1:]:
            cols.append(d.coarse_class.eq(level).astype(float).to_numpy())
    return np.column_stack(cols)


def incremental_prediction(x, lobo):
    rows = []
    metrics = ["turn_n_peer_delta", "short_turn_edges_peer_delta", "log_area_peer_delta", "log_height_peer_delta"]
    versions = ["origin", "q_origin", "class", "q_origin_class"]
    for condition in ["manual", "semi"]:
        d = x[x.classification_observation & x.condition.eq(condition)].copy()
        for building in sorted(d.building_id.unique()):
            labs = lobo[(lobo.condition == condition) & (lobo.heldout_building == building)]
            labs = labs[labs.coarse_class.ne("unassigned")][["worker_id", "coarse_class"]]
            train = d[d.building_id.ne(building)].merge(labs, on="worker_id")
            test = d[d.building_id.eq(building)].merge(labs, on="worker_id")
            if not len(test):
                continue
            q = x[x.condition.eq(condition) & x.layer.eq("ordinary") & x.building_id.ne(building) & x.quality_usable]
            qh = q.groupby(["worker_id", "building_id"]).B8L2.mean().groupby("worker_id").mean().rename("q_history")
            train, test = train.merge(qh, on="worker_id", how="left"), test.merge(qh, on="worker_id", how="left")
            qcenter = float(qh.mean())
            levels = sorted(train.coarse_class.unique())
            for metric in metrics:
                tr, te = train[train[metric].notna()].copy(), test[test[metric].notna()].copy()
                if not len(te):
                    continue
                panel_size = tr.groupby(KEY, dropna=False).object_id.transform("size").to_numpy(dtype=float)
                panel_per_building = tr.groupby("building_id").image_id.transform("nunique").to_numpy(dtype=float)
                w = 1 / (panel_size * panel_per_building)
                for version in versions:
                    a = model_design(tr, version, levels, qcenter)
                    b = model_design(te, version, levels, qcenter)
                    beta = np.linalg.lstsq(a * np.sqrt(w)[:, None], tr[metric].to_numpy() * np.sqrt(w), rcond=None)[0]
                    prediction = b @ beta
                    for i, (_, r) in enumerate(te.iterrows()):
                        rows.append(dict(condition=condition, heldout_building=building, image_id=r.image_id,
                            object_id=r.object_id, worker_id=r.worker_id, model=version, metric=metric,
                            observed=r[metric], predicted=float(prediction[i]),
                            absolute_error=float(abs(prediction[i] - r[metric])),
                            squared_error=float((prediction[i] - r[metric]) ** 2)))
    p = pd.DataFrame(rows)
    buildings = p.groupby(["condition", "metric", "model", "heldout_building", "image_id"])[["absolute_error", "squared_error"]].mean().groupby(["condition", "metric", "model", "heldout_building"]).mean().reset_index()
    summary = buildings.groupby(["condition", "metric", "model"]).agg(buildings=("heldout_building", "nunique"), mae=("absolute_error", "mean"), mse=("squared_error", "mean")).reset_index()
    summary["rmse"] = np.sqrt(summary.mse)
    rng = np.random.default_rng(20261021)
    increments = []
    for (condition, metric), g in buildings.groupby(["condition", "metric"]):
        t = g.pivot(index="heldout_building", columns="model", values="absolute_error")
        for baseline in ["origin", "q_origin"]:
            z = (t[baseline] - t.q_origin_class).dropna()
            boot = rng.choice(z.to_numpy(), size=(3000, len(z)), replace=True).mean(axis=1)
            increments.append(dict(condition=condition, metric=metric, baseline=baseline,
                model="q_origin_class", buildings=len(z), mae_reduction=z.mean(),
                relative_mae_reduction=z.mean() / t[baseline].mean(), positive_buildings=int(z.gt(0).sum()),
                bootstrap_low=float(np.quantile(boot, .025)), bootstrap_high=float(np.quantile(boot, .975))))
    return p, buildings, summary, pd.DataFrame(increments)


def feature_alternatives(x):
    """Save a compact descriptive comparison, never select from fusion results."""
    from sklearn.cluster import AgglomerativeClustering
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import silhouette_score, adjusted_rand_score
    from run_classification import worker_features, MIN_IMAGES, MIN_BUILDINGS
    final = pd.read_csv(HERE / "final_labels.csv")
    rows = []
    for condition in ["manual", "semi"]:
        d = x[x.classification_observation & x.condition.eq(condition)]
        f = worker_features(d)
        f = f[f.n_images.ge(MIN_IMAGES) & f.n_buildings.ge(MIN_BUILDINGS)]
        final_l = final[final.condition.eq(condition)].set_index("worker_id").loc[f.index].coarse_class
        for variant, cols in {
            "selected_structural": ["turn_n_peer_delta", "short_turn_edges_peer_delta"],
            "structural_plus_collinearity": ["turn_n_peer_delta", "short_turn_edges_peer_delta", "near_straight_nodes_5deg_peer_delta"],
            "structural_plus_position": ["turn_n_peer_delta", "short_turn_edges_peer_delta", "near_straight_nodes_5deg_peer_delta", "log_area_peer_delta", "log_height_peer_delta"],
        }.items():
            a = StandardScaler().fit_transform(f[cols])
            for k in [2, 3, 4]:
                lab = AgglomerativeClustering(n_clusters=k, linkage="ward").fit_predict(a)
                counts = pd.Series(lab).value_counts()
                rows.append(dict(condition=condition, variant=variant, k=k, n_people=len(f),
                    silhouette=silhouette_score(a, lab), min_class_n=int(counts.min()),
                    class_sizes="|".join(map(str, sorted(counts))),
                    selected_coarse_ari=adjusted_rand_score(final_l, lab),
                    adopted=variant == "selected_structural" and k == 2))
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--source-root", type=Path)
    ap.add_argument("--profiles-only", action="store_true")
    ap.add_argument("--contrasts-only", action="store_true")
    args = ap.parse_args()
    source_root = args.source_root or args.root
    x = load_expression(args.root)
    x = x.merge(load_metadata(source_root / SOURCE), on="object_id", validate="one_to_one")
    conds = pd.read_csv(args.root / CONDITIONS, low_memory=False)
    fields = ["object_id", "ref_turn5", "ref_H", "ref_short_edges", "mechanism", "reference_sample", "reduced", "unmatched_ref_9", "bottom_bias_9"]
    x = x.merge(conds[fields], on="object_id", validate="one_to_one")
    x["B8L2"] = x.B8L2.where(x.quality_usable)
    x["D10"] = x.D10.where(x.quality_usable)
    for m in ["reduced", "unmatched_ref_9", "bottom_bias_9"]:
        x[m + "_qualified"] = x[m].astype(float).where(x.reference_sample)
    qualified = x.quality_usable & x.B8L2.notna()
    med = x.loc[qualified].groupby(KEY, dropna=False).B8L2.transform("median")
    x["q_peer_delta"] = x.B8L2 - med
    x["t_log"] = np.log(x.source_active_time_seconds.where(x.source_active_time_seconds.gt(0)))
    tgate = x.primary_expression & x.t_log.notna()
    med = x.loc[tgate].groupby(KEY + ["origin"], dropna=False).t_log.transform("median")
    x["t_log_peer_delta"] = x.t_log - med
    for m in ["top_y_mean", "bottom_y_mean"]:
        med = x.loc[x.personal_comparison].groupby(KEY, dropna=False)[m].transform("median")
        x[m + "_peer_delta"] = x[m] - med
    final, lobo = pd.read_csv(HERE / "final_labels.csv"), pd.read_csv(HERE / "lobo_labels.csv")
    profiles = profile_people(x, final)
    write(profiles, HERE / "person_class_explanations.csv")
    write(aggregate_profiles(profiles), HERE / "class_qt_auxiliary_by_source.csv")
    if args.profiles_only:
        return
    lab_fields = ["worker_id", "condition", "heldout_building", "coarse_class", "fine_class"]
    d = x[x.personal_comparison & x.peer_n.ge(3)].merge(lobo[lab_fields],
        left_on=["worker_id", "condition", "building_id"],
        right_on=["worker_id", "condition", "heldout_building"], validate="many_to_one")
    panels, summary, difficulty, fixed6 = matched_contrasts(d)
    write(panels, HERE / "lobo_expression_panels.csv.gz")
    write(summary, HERE / "lobo_expression_summary.csv")
    write(difficulty, HERE / "lobo_expression_by_difficulty.csv")
    write(fixed6, HERE / "lobo_fixed6_mechanisms.csv")
    if args.contrasts_only:
        return
    write(feature_alternatives(x), HERE / "feature_candidate_comparison.csv")
    predictions, buildings, predicted, increments = incremental_prediction(x, lobo)
    write(predictions, HERE / "lobo_incremental_predictions.csv.gz")
    write(buildings, HERE / "lobo_incremental_buildings.csv")
    write(predicted, HERE / "lobo_incremental_summary.csv")
    write(increments, HERE / "lobo_incremental_beyond_q_source.csv")
    print(summary.query("source=='all' and level=='coarse_class'")[["condition", "layer", "class_high", "class_low", "n_images", "n_buildings", "turn_n_difference_building_mean", "short_turn_edges_difference_building_mean", "B8L2_difference_building_mean"]].to_string(index=False))
    print(increments.query("baseline=='q_origin'").to_string(index=False))


if __name__ == "__main__":
    main()
