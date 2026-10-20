"""Small follow-up Semi candidates; never overwrite frozen fusion labels.

New-cohort final-geometry clustering is fitted separately because the first
mixed-cohort structure result did not reproduce within the new cohort. A
position/scale candidate and repeated-collinearity evidence are kept separate.
"""
from pathlib import Path
import itertools
import json

import numpy as np
import pandas as pd
from sklearn.cluster import AgglomerativeClustering
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import adjusted_rand_score, silhouette_score

from run_classification import HERE, ROOT, KEY, load_expression

OUT = HERE / "semi_new_candidate"


def write(x, name):
    x.to_csv(OUT / name, index=False, encoding="utf-8-sig")


def fit(d, features, kind):
    s = d.groupby("worker_id").agg(n_images=("image_id", "nunique"), n_buildings=("building_id", "nunique"))
    f = d.groupby(["worker_id", "building_id"])[features].mean().groupby("worker_id").mean().join(s)
    f = f[f.n_images.ge(12) & f.n_buildings.ge(4)]
    a = StandardScaler().fit_transform(f[features])
    k = 2 if kind == "semi_new_structure" else 3
    lab = AgglomerativeClustering(n_clusters=k, linkage="ward").fit_predict(a)
    means = pd.DataFrame(f[features]).assign(label=lab).groupby("label").mean()
    if kind == "semi_new_structure":
        order = means.iloc[:, 0].sort_values().index
        mapping = {v: "SN" + str(i) for i, v in enumerate(order)}
    else:
        lower = means.log_height_peer_delta.idxmin()
        other = means.drop(index=lower)
        larger = other.log_area_peer_delta.idxmax()
        typical = next(v for v in means.index if v not in [lower, larger])
        mapping = {lower: "SP_L", larger: "SP_A", typical: "SP_T"}
    f["class_id"] = [mapping[i] for i in lab]
    f["candidate"] = kind
    f["silhouette"] = silhouette_score(a, lab)
    return f.reset_index()


def contrasts(d, labels, kind):
    te = d.merge(labels[["worker_id", "heldout_building", "class_id"]],
                 left_on=["worker_id", "building_id"], right_on=["worker_id", "heldout_building"])
    rows = []
    metrics = ["turn_n", "short_turn_edges", "near_straight_nodes_5deg", "log_area", "log_height", "pair_n"]
    for source in ["all", "new", "v1"]:
        ds = te if source == "all" else te[te.origin.eq(source)]
        for key, g in ds.groupby(KEY, dropna=False):
            for a, b in itertools.combinations(sorted(g.class_id.unique()), 2):
                aa, bb = g[g.class_id.eq(a)], g[g.class_id.eq(b)]
                if len(aa) < 2 or len(bb) < 2:
                    continue
                row = dict(zip(KEY, key))
                row.update(candidate=kind, source=source, class_a=a, class_b=b,
                           building_id=g.iloc[0].building_id, image_code=g.iloc[0].image_code,
                           n_a=len(aa), n_b=len(bb))
                for m in metrics:
                    row[m + "_a_minus_b"] = aa[m].mean() - bb[m].mean()
                rows.append(row)
    return pd.DataFrame(rows)


def main():
    OUT.mkdir(exist_ok=True)
    x = load_expression(ROOT)
    d = x[x.classification_observation & x.condition.eq("semi")].copy()
    final_all, lobo_all, panels_all, stability = [], [], [], []
    for kind, source, features in [
        ("semi_new_structure", "new", ["turn_n_peer_delta", "short_turn_edges_peer_delta"]),
        ("semi_position_scale", "all", ["log_area_peer_delta", "log_height_peer_delta"]),
    ]:
        ds = d if source == "all" else d[d.origin.eq(source)].copy()
        if source != "all":
            # The new cohort has its own same-task peer baseline.
            counts = ds.groupby(KEY, dropna=False).object_id.transform("size")
            ds = ds[counts.ge(3)].copy()
            for f in ["turn_n", "short_turn_edges"]:
                ds[f + "_peer_delta"] = ds[f] - ds.groupby(KEY, dropna=False)[f].transform("median")
        full = fit(ds, features, kind)
        full["heldout_building"] = "ALL_DATA"
        final_all.append(full)
        lb = []
        for b in sorted(ds.building_id.unique()):
            f = fit(ds[ds.building_id.ne(b)], features, kind)
            f["heldout_building"] = b
            lb.append(f)
            merge = f.merge(full[["worker_id", "class_id"]], on="worker_id", suffixes=("_lobo", "_full"))
            stability.append(dict(candidate=kind, heldout_building=b, n_people=len(merge),
                agreement=float(merge.class_id_lobo.eq(merge.class_id_full).mean()),
                ari=adjusted_rand_score(merge.class_id_lobo, merge.class_id_full)))
        labels = pd.concat(lb, ignore_index=True)
        lobo_all.append(labels)
        panels_all.append(contrasts(ds, labels, kind))
    final, lobo = pd.concat(final_all, ignore_index=True), pd.concat(lobo_all, ignore_index=True)
    panels = pd.concat(panels_all, ignore_index=True)
    write(final, "final_labels.csv")
    write(lobo, "lobo_labels.csv")
    write(pd.DataFrame(stability), "label_stability.csv")
    write(panels, "heldout_panels.csv")
    stats = []
    for keys, g in panels.groupby(["candidate", "source", "class_a", "class_b"]):
        row = dict(zip(["candidate", "source", "class_a", "class_b"], keys))
        row.update(n_images=g.image_id.nunique(), n_buildings=g.building_id.nunique())
        for m in [c for c in panels if c.endswith("_a_minus_b")]:
            by_b = g.groupby("building_id")[m].mean()
            row[m] = by_b.mean()
            row[m + "_positive_buildings"] = int(by_b.gt(1e-10).sum())
            row[m + "_negative_buildings"] = int(by_b.lt(-1e-10).sum())
        stats.append(row)
    write(pd.DataFrame(stats), "heldout_summary.csv")
    # This is a behaviour-evidence tag, not a new fitted fusion classification.
    cols = []
    for w, g in d.groupby("worker_id"):
        pos = g[g.near_straight_nodes_5deg.gt(0)]
        cols.append(dict(worker_id=w, condition="semi", images=g.image_id.nunique(),
            collinear_images=pos.image_id.nunique(), collinear_buildings=pos.building_id.nunique(),
            near_collinear_record_rate=len(pos) / len(g),
            repeated_tag=pos.image_id.nunique() >= 2 and pos.building_id.nunique() >= 2,
            contributing_images="|".join(sorted(pos.image_code.unique())),
            contributing_objects="|".join(pos.object_id)))
    write(pd.DataFrame(cols), "repeated_collinearity.csv")
    original_labels = pd.read_csv(HERE / "final_labels.csv")
    sem = x[x.condition.eq("semi") & x.primary_expression].merge(
        original_labels[["worker_id", "condition", "fine_class"]], on=["worker_id", "condition"])
    sem = sem[sem.fine_class.ne("unassigned")]
    evidence_cols = ["object_id", "worker_id", "image_id", "image_code", "building_id", "origin", "fine_class",
        "quality_usable", "personal_comparison", "semi_exact_initialization", "semi_raw_pair_delta",
        "semi_error_confirmed", "semi_known_error_unchanged", "semi_error_reported", "semi_reported_error_unchanged"]
    write(sem[evidence_cols], "semi_initialization_opportunities.csv")
    aux = []
    for (origin, fine), g in sem.groupby(["origin", "fine_class"]):
        err = g[g.semi_error_confirmed.eq(True)]
        reported = g[g.semi_error_reported.eq(True)]
        aux.append(dict(origin=origin, fine_class=fine, people=g.worker_id.nunique(), records=len(g),
            images=g.image_id.nunique(), exact_initialization=int(g.semi_exact_initialization.sum()),
            removed_pairs=int(g.semi_raw_pair_delta.lt(0).sum()), added_pairs=int(g.semi_raw_pair_delta.gt(0).sum()),
            confirmed_error_opportunities=len(err), confirmed_error_images=err.image_id.nunique(),
            confirmed_error_unchanged=int(err.semi_known_error_unchanged.eq(True).sum()),
            reported_error_opportunities=len(reported), reported_error_images=reported.image_id.nunique(),
            reported_error_unchanged=int(reported.semi_reported_error_unchanged.eq(True).sum())))
    write(pd.DataFrame(aux), "semi_initialization_by_class.csv")
    manifest = {
        "status": "small_followup_candidates_not_frozen_fusion_labels",
        "new_cohort": "35 workers new Semi separately; same-task peer medians recalculated within new origin; Ward2 on turn and short-turn residuals; building equal; >=12 images/4 buildings",
        "position": "Semi independently on log_area and log_height peer residuals; Ward3, semantic names ordered by lowest log_height then highest log_area",
        "collinearity": "descriptive repeated evidence tag: at least two independent images in two buildings, not a fitted personnel cluster",
        "geometry_scoring_reference_fusion_changes": False,
        "validation": "whole target building excluded for every lobo row; selection is exploratory follow-up to mixed-cohort results, not untouched confirmation",
    }
    (OUT / "MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf8")
    print(final.groupby(["candidate", "class_id"]).worker_id.apply(lambda s: "|".join(s)).to_string())
    print(pd.DataFrame(stats)[["candidate", "source", "class_a", "class_b", "n_images", "n_buildings", "short_turn_edges_a_minus_b", "log_area_a_minus_b", "log_height_a_minus_b"]].to_string(index=False))


if __name__ == "__main__":
    main()
