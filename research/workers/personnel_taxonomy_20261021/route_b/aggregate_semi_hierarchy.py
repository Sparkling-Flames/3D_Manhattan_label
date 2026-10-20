"""Publish adopted Semi hierarchy by aggregating frozen position labels.

No model is refitted: SP_L -> SP_LOW, SP_A/SP_T -> SP_OTHER.  The original
candidate files used by the actual fusion experiment remain byte-for-byte
unchanged.  Held-out contrasts use only the frozen target-building-excluded
labels and the existing quality gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from run_classification import HERE, ROOT, KEY, load_expression
from evaluate_classification import SOURCE, load_metadata, summaries_from_panels

CANDIDATE = "semi_position_scale"
COARSE = {"SP_L": "SP_LOW", "SP_A": "SP_OTHER", "SP_T": "SP_OTHER"}
NAMES = {"SP_LOW": "较低推导高度", "SP_OTHER": "其余尺度表达",
         "SP_L": "较低推导高度", "SP_A": "较大推导底面积",
         "SP_T": "其余尺度表达", "unassigned": "证据不足"}


def write(d, name):
    d.to_csv(HERE / name, index=False, encoding="utf-8-sig")


def labels_with_inventory(labels, inventory, observations, origins, fold):
    history = observations if fold == "ALL_DATA" else observations[observations.building_id.ne(fold)]
    support = history.groupby("worker_id").agg(n_records=("object_id", "size"),
        n_images=("image_id", "nunique"), n_buildings=("building_id", "nunique"),
        n_quality_usable=("quality_usable", "sum"),
        n_independent_vote_eligible=("independent_vote_eligible", "sum"))
    features = labels[["worker_id", "class_id", "log_area_peer_delta", "log_height_peer_delta"]]
    out = pd.DataFrame({"worker_id": inventory}).merge(features, on="worker_id", how="left")
    out = out.merge(support, on="worker_id", how="left").merge(origins, on="worker_id", how="left")
    out["condition"] = "semi"
    out["heldout_building"] = fold
    out["fit_scope"] = "all_data_descriptive" if fold == "ALL_DATA" else "leave_one_building_out"
    out["training_layer"] = "ordinary"
    out["source_candidate"] = CANDIDATE
    out["fine_class"] = out.class_id.fillna("unassigned")
    out["coarse_class"] = out.fine_class.map(COARSE).fillna("unassigned")
    out["coarse_name_zh"] = out.coarse_class.map(NAMES)
    out["fine_name_zh"] = out.fine_class.map(NAMES)
    for c in support:
        out[c] = out[c].fillna(0).astype(int)
    out["label_status"] = np.where(out.class_id.notna(), "assigned", "insufficient_support")
    out.loc[out.n_records.eq(0), "label_status"] = "no_comparable_ordinary_history"
    out["missing_reason"] = np.where(out.class_id.notna(), "", "fewer_than_12_comparable_images_or_4_buildings")
    out.loc[out.n_records.eq(0), "missing_reason"] = "no_comparable_ordinary_history_in_this_condition"
    out["coarse_adoption_status"] = out.coarse_class.map({
        "SP_LOW": "recommended_conditional_height_type", "SP_OTHER": "relative_scale_comparison_parent",
        "unassigned": "unassigned"})
    out["fine_adoption_status"] = out.fine_class.map({
        "SP_L": "recommended_conditional_height_type", "SP_A": "old_origin_supported_scale_subtype",
        "SP_T": "relative_scale_comparison_group", "unassigned": "unassigned"})
    out.loc[out.fine_class.eq("SP_A") & out.origin.ne("v1"), "fine_adoption_status"] = "not_supported_as_new_origin_repeatable_subtype"
    out["hierarchy_method"] = "deterministic_aggregation_of_frozen_ward3_labels_no_refit"
    return out.drop(columns="class_id")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-root", type=Path, default=ROOT)
    args = ap.parse_args()
    paths = {k: HERE / "semi_new_candidate" / f"{k}_labels.csv" for k in ["final", "lobo"]}
    hashes_before = {k: hashlib.sha256(p.read_bytes()).hexdigest() for k, p in paths.items()}
    frozen = {k: pd.read_csv(p).query("candidate == @CANDIDATE") for k, p in paths.items()}
    x = load_expression(ROOT)
    observations = x[x.classification_observation & x.condition.eq("semi")].copy()
    inventory = sorted(x.worker_id.unique())
    origins = x.groupby("worker_id").origin.agg(lambda s: "|".join(sorted(s.unique()))).reset_index()
    final = labels_with_inventory(frozen["final"], inventory, observations, origins, "ALL_DATA")
    lobo = pd.concat([labels_with_inventory(g, inventory, observations, origins, fold)
        for fold, g in frozen["lobo"].groupby("heldout_building")], ignore_index=True)
    joined = lobo.merge(final[["worker_id", "coarse_class", "fine_class"]], on="worker_id", suffixes=("_lobo", "_final"))
    stability = []
    for level in ["coarse_class", "fine_class"]:
        known = joined[joined[level + "_lobo"].ne("unassigned") & joined[level + "_final"].ne("unassigned")].copy()
        known["same"] = known[level + "_lobo"].eq(known[level + "_final"])
        by_person = known.groupby("worker_id").agg(**{level + "_lobo_agreement": ("same", "mean"), level + "_lobo_support": ("same", "size")})
        final = final.merge(by_person, on="worker_id", how="left")
        for b, g in known.groupby("heldout_building"):
            stability.append(dict(level=level, heldout_building=b, n_people=len(g), agreement=g.same.mean()))
    write(final, "semi_adopted_labels.csv")
    write(lobo, "semi_adopted_lobo_labels.csv")
    write(pd.DataFrame(stability), "semi_adopted_label_stability.csv")
    for kind, semi in [("final", final), ("lobo", lobo)]:
        manual = pd.read_csv(HERE / f"{kind}_labels.csv").query("condition == 'manual'").copy()
        manual["source_candidate"] = "manual_structure_ward_hierarchy"
        manual["coarse_adoption_status"] = np.where(manual.coarse_class.ne("unassigned"),
            "recommended_current_structural_working_type", "unassigned")
        manual["fine_adoption_status"] = np.where(manual.fine_class.ne("unassigned"),
            "conditional_member_sensitive_structural_subtype", "unassigned")
        semi = semi.copy()
        semi["target_condition_observed"] = True
        recommended = pd.concat([manual, semi], ignore_index=True)
        write(recommended, "recommended_labels.csv" if kind == "final" else "recommended_lobo_labels.csv")
    member_cols = ["coarse_class", "fine_class", "coarse_name_zh", "fine_name_zh", "origin", "fine_adoption_status"]
    members = final.groupby(member_cols, dropna=False).agg(people=("worker_id", "size"),
        members=("worker_id", lambda s: "|".join(s)),
        log_area_peer_delta=("log_area_peer_delta", "mean"),
        log_height_peer_delta=("log_height_peer_delta", "mean")).reset_index()
    write(members, "semi_adopted_members.csv")

    # The previously frozen fine-class result gains a coarse summary only.
    meta = load_metadata(args.source_root / SOURCE)
    d = observations.merge(meta, on="object_id", how="left")
    d.loc[~d.quality_usable, ["B8L2", "D10"]] = np.nan
    te = d.merge(lobo[["worker_id", "heldout_building", "coarse_class"]],
        left_on=["worker_id", "building_id"], right_on=["worker_id", "heldout_building"], how="inner")
    metrics = ["log_height", "log_area", "top_y_mean", "bottom_y_mean", "turn_n",
               "short_turn_edges", "near_straight_nodes_5deg", "pair_n", "B8L2", "D10"]
    rows = []
    for source in ["all", "v1", "new"]:
        ds = te if source == "all" else te[te.origin.eq(source)]
        for key, g in ds.groupby(KEY, dropna=False):
            a = g[g.coarse_class.eq("SP_LOW")]
            b = g[g.coarse_class.eq("SP_OTHER")]
            if min(a.worker_id.nunique(), b.worker_id.nunique()) < 2:
                continue
            row = dict(zip(KEY, key))
            row.update(source=source, building_id=g.iloc[0].building_id, image_code=g.iloc[0].image_code,
                class_a="SP_LOW", class_b="SP_OTHER", n_a=len(a), n_b=len(b),
                a_members="|".join(sorted(a.worker_id.unique())), b_members="|".join(sorted(b.worker_id.unique())))
            for m in metrics:
                aa, bb = a.dropna(subset=[m]), b.dropna(subset=[m])
                qualified = min(aa.worker_id.nunique(), bb.worker_id.nunique()) >= 2
                row[m + "_difference"] = aa[m].mean() - bb[m].mean() if qualified else np.nan
                row[m + "_n_a"], row[m + "_n_b"] = len(aa), len(bb)
            rows.append(row)
    panels = pd.DataFrame(rows)
    summary = summaries_from_panels(panels, ["source", "class_a", "class_b"], [m + "_difference" for m in metrics])
    write(panels, "semi_adopted_lobo_panels.csv")
    write(summary, "semi_adopted_lobo_summary.csv")
    hashes_after = {k: hashlib.sha256(p.read_bytes()).hexdigest() for k, p in paths.items()}
    assert hashes_after == hashes_before
    manifest = dict(schema="semi_adopted_hierarchy_v1", candidate=CANDIDATE,
        mapping=COARSE, frozen_source_sha256=hashes_before, refitted=False,
        validation="frozen K3 labels exclude complete target building; then aggregate SP_A/SP_T; source-specific same-image/reference panels require >=2 people on each side",
        adoption="SP_LOW conditionally supported; SP_OTHER is comparison parent, SP_A supported only old origin; SP_T is relative comparison, not uniform quality",
        preserved_contracts=["original_annotation", "reference", "ring_order", "quality_eligibility", "fusion"],
        counts={"all_data_inventory":len(final), "all_data_assigned":int(final.fine_class.ne("unassigned").sum()),
                "lobo_buildings":lobo.heldout_building.nunique(), "lobo_inventory_rows":len(lobo)})
    (HERE / "SEMI_ADOPTED_CONTRACT.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf8")
    print(members.to_string(index=False))
    print(summary[["source", "n_images", "n_buildings", "log_height_difference_building_mean",
                   "log_height_difference_negative_buildings", "log_area_difference_building_mean",
                   "B8L2_difference_building_mean"]].to_string(index=False))
    print(pd.DataFrame(stability).groupby("level").agreement.mean())


if __name__ == "__main__":
    main()
