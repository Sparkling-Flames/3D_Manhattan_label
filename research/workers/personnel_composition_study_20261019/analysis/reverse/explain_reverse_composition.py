#!/usr/bin/env python3
"""Explain already-frozen reverse labels with independently fitted history traits.

Q and other traits enter descriptive tables only. They do not enter the reverse
classification or change its labels. A small shortlist covers algorithms/K and
usable composition opportunities, prior to discovery fusion-outcome selection.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
import discover_reverse_composition as d

TRAITS = ["q_beta", "q_abs_mean", "q_abs_p10", "q_abs_sd", "q_residual_p10", "q_residual_sd",
          "pair_count_effect", "pair_count_residual_sd", "bottom_y_effect", "top_y_effect",
          "height_log_effect", "t_source_origin_effect", "t_log_residual_tail",
          "theta_easy", "theta_medium", "theta_hard", "hard_minus_easy", "hard_minus_medium",
          "semi_old_error_nonedit_effect", "semi_new_error_nonedit_effect", "semi_old_edit_effect",
          "semi_new_edit_effect", "semi_gain_mean", "semi_initial_mean", "semi_final_mean", "scope_out_effect"]
OPPORTUNITIES = ["core_records", "core_images", "core_buildings", "t_records", "t_images", "t_buildings",
                 "easy_tasks", "medium_tasks", "hard_tasks", "semi_old_error_nonedit_records",
                 "semi_new_error_nonedit_records", "semi_old_error_nonedit_count", "semi_new_error_nonedit_count",
                 "semi_old_edit_records", "semi_new_edit_records", "semi_attributable_n", "scope_records", "scope_gold_n"]
SHORTLIST = [
    ("R_geo9_average_p0_K2", "smallest K and no-shrinkage average relation"),
    ("R_geo9_complete_p0_K3", "three sizeable classes; complete-linkage no-prior sensitivity"),
    ("R_geo9_complete_p2_K4", "four classes with at least ten supported members each"),
    ("R_geo9_spectral_p2_K2", "normalized spectral two-class source-association comparison"),
    ("R_geo9_spectral_p2_K3", "normalized spectral three-class representation"),
    ("R_geo9_spectral_p2_K6", "normalized spectral higher-resolution representation"),
    ("R_geo9_source_signed_p2_K2", "source-pair-residual two-class sensitivity"),
    ("R_geo9_source_signed_p2_K4", "source-pair-residual four-class representation"),
    ("R_geo9_source_signed_p2_K6", "source-pair-residual six-class representation"),
    ("R_geo9_source_signed_p2_K8", "source-pair-residual eight-class representation with no class below six"),
    ("R_role_ward_K3", "three-role agglomerative representation"),
    ("R_role_ward_K5", "five-role agglomerative representation"),
    ("R_role_kmeans_K3", "three-role centroid representation"),
    ("R_role_kmeans_K5", "five-role centroid representation"),
    ("R_role_ward_difficulty_K4", "difficulty-specific four-role labels; own supports"),
    ("R_role_ward_difficulty_K6", "difficulty-specific six-role labels; own supports"),
]


def explained_variance(group, value):
    g = group[group[value].notna()]
    if len(g) < 2:
        return np.nan
    overall = g[value].mean()
    total = float(((g[value] - overall) ** 2).sum())
    between = sum(len(x) * (x[value].mean() - overall) ** 2 for _, x in g.groupby("class_id"))
    return between / total if total > 0 else np.nan


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", type=Path, required=True)
    ap.add_argument("--records", type=Path, help="Frozen records_geometry.csv.gz; metadata only for actual class support")
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    labels_path = args.output / "worker_labels.csv.gz"
    label_hash_before = d.sha(labels_path)
    labels = pd.read_csv(labels_path)
    features = pd.read_csv(args.features)
    assert labels.train_key.nunique() == features.train_key.nunique() == 1
    assert labels.train_key.iloc[0] == features.train_key.iloc[0]
    run = json.loads((args.output / "RUN_RECEIPT.json").read_text())
    record_path = args.records or Path(next(p for p in run["inputs"] if p.endswith("records_geometry.csv.gz")))
    record_meta = pd.read_csv(record_path, usecols=["worker_id", "image_id", "building_id", "layer", "difficulty"])
    record_meta = record_meta[record_meta.layer.eq("ordinary_manual") & record_meta.building_id.isin(run["history_buildings"])].copy()
    record_meta["difficulty"] = record_meta.difficulty.replace(d.DIFF_MAP)
    known = labels[labels.known].merge(features, on=["worker_id", "train_key"], validate="many_to_one")
    rows = []
    for (mid, dom, cls), g in known.groupby(["method_id", "domain", "class_id"], sort=True):
        row = dict(method_id=mid, domain=dom, class_id=cls, n_workers=len(g), old_n=int(g.origin.eq("v1").sum()),
                   new_n=int(g.origin.eq("new").sum()), members="|".join(sorted(g.worker_id)))
        domain_records = record_meta if dom == "global" else record_meta[record_meta.difficulty.eq(dom)]
        observed_records = domain_records[domain_records.worker_id.isin(g.worker_id)]
        row.update(type_training_records=len(observed_records), type_training_images=observed_records.image_id.nunique(),
                   type_training_buildings=observed_records.building_id.nunique())
        for feature in TRAITS:
            if feature not in g:
                continue
            x = g[feature].dropna()
            row[feature + "__mean"] = x.mean()
            row[feature + "__p10"] = x.quantile(.1)
            row[feature + "__p90"] = x.quantile(.9)
            row[feature + "__known_workers"] = len(x)
        for feature in OPPORTUNITIES:
            if feature in g:
                row[feature + "__sum"] = g[feature].sum(min_count=1)
                row[feature + "__min_per_worker"] = g[feature].min()
        for feature in [c for c in g if c.endswith("_supported")]:
            row[feature + "__workers"] = int(g[feature].fillna(False).astype(bool).sum())
        rows.append(row)
    explanations = pd.DataFrame(rows)
    roles = pd.read_csv(args.output / "class_roles.csv")
    descriptions = [c for c in roles if c not in ["n_workers", "old_n", "new_n", "members"]]
    explanations = explanations.merge(roles[descriptions], on=["method_id", "domain", "class_id"], validate="one_to_one")
    explanations.to_csv(args.output / "class_explanations.csv", index=False)
    assoc = []
    for (mid, dom), g in known.groupby(["method_id", "domain"], sort=True):
        for source in ("all", "v1", "new"):
            z = g if source == "all" else g[g.origin.eq(source)]
            assoc.append(dict(method_id=mid, domain=dom, source=source, workers=len(z),
                              q_beta_variance_explained=explained_variance(z, "q_beta"),
                              pair_count_effect_variance_explained=explained_variance(z, "pair_count_effect"),
                              t_effect_variance_explained=explained_variance(z, "t_source_origin_effect")))
    pd.DataFrame(assoc).to_csv(args.output / "label_trait_association.csv", index=False)
    support = pd.read_csv(args.output / "candidate_support.csv")
    feasible = pd.read_csv(args.output / "candidate_feasibility.csv")
    history_screen = support.merge(feasible[feasible.phase.eq("discovery")], on=["method_id", "domain"])
    flags = []
    for row in history_screen.itertuples():
        messages = []
        if row.n_singleton_classes:
            messages.append("contains_singleton_class_no_within_class_replacement")
        if row.pools_two_classes_ge3 < .5 * row.pools:
            messages.append("two_classes_of_three_feasible_on_fewer_than_half_target_pools")
        if row.source_nmi > .4:
            messages.append("strong_observed_source_association")
        flags.append("|".join(messages))
    history_screen["pre_outcome_flags"] = flags
    history_screen["in_support_shortlist"] = history_screen.method_id.isin([m for m, _ in SHORTLIST])
    history_screen.to_csv(args.output / "pre_outcome_search_ledger.csv", index=False)
    if (args.output / "history_stability_summary.csv").exists():
        stability = pd.read_csv(args.output / "history_stability_summary.csv")
        history_screen[history_screen.in_support_shortlist].merge(stability, on=["method_id", "domain"], validate="one_to_one").to_csv(
            args.output / "shortlist_support_stability.csv", index=False)
    selected = []
    for mid, reason in SHORTLIST:
        assert mid in set(support.method_id)
        selected.append(dict(method_id=mid, basis=reason,
                             domains=support[support.method_id.eq(mid)].domain.tolist()))
    d.write_json(args.output / "SUPPORT_SHORTLIST.json", dict(
        stage="support_and_representation_screen_before_discovery_fusion_ranking",
        selection_uses_fusion_outcomes=False, selection_uses_target_Q=False,
        interpretation="Coverage-oriented heuristic shortlist, not a claimed optimum; all 62 candidates retained in labels and ledger.",
        selection_basis="Cover K2/3/4/5/6/8, relation and role families, algorithm and prior/source sensitivities, sizeable actual classes and feasible real memberships.",
        global_methods=14, conditional_methods=2, candidates=selected))
    assert d.sha(labels_path) == label_hash_before
    d.write_json(args.output / "EXPLANATION_RECEIPT.json", dict(
        labels_sha256=label_hash_before, features_sha256=d.sha(args.features),
        input_features=str(args.features), train_key=features.train_key.iloc[0],
        feature_stage="history_only", reverse_labels_unchanged=True,
        class_explanation_rows=len(rows), association_rows=len(assoc),
        q_description="Each class's Q columns average historical per-worker estimates; not target-image or fused-team Q.",
        sparse_traits="Known-worker counts accompany every mean; no-opportunity workers remain missing.",
        code_sha256=d.sha(Path(__file__))))
    print(json.dumps(dict(class_rows=len(rows), method_domains=len(support), shortlist=len(selected))))


if __name__ == "__main__":
    main()
