"""Balanced condition, background/member, continuous-policy and n-path results.

All estimates are read-only reaggregations of the saved complete event table.
Panel -> image -> building averaging prevents a larger finite reservoir or the
reuse of one target endpoint from manufacturing independent evidence.
"""
from __future__ import annotations

import math
import json
import argparse
from pathlib import Path
import numpy as np
import pandas as pd

from register_design import HERE, h, sha, write, save

ID = ["panel_id", "pool_id", "image", "building", "difficulty", "training_QT_direction", "n", "m_AB"]
CORE = ["same_B8L2", "cross_B8L2", "net_B8L2", "same_D10", "cross_D10", "net_D10",
        "common_quality_within_abs", "common_quality_cross_abs", "abs_Q_change_advantage",
        "same_recorded_time_logratio", "cross_recorded_time_logratio", "net_recorded_time_logratio",
        "A_failure", "B_failure", "C_failure", "net_failure_difference", "same_loss_gt5", "cross_loss_gt5",
        "net_loss_gt5", "net_loss_gt10", "C_failure_or_net_loss_gt5", "C_failure_or_net_loss_gt10",
        "net_Q_up", "net_time_down", "net_QT_both_improve", "net_IoU3D100", "net_iou_2d",
        "net_S_bottom_deg", "net_dir", "net_Hmean", "net_Hcenter", "net_omission", "net_extension",
        "net_nodes", "net_height_mean_h", "net_height_mean_ratio", "net_top_y_mean_px", "net_bottom_y_mean_px",
        "net_fusion_turn_n", "net_fusion_short_turn_edges", "net_fusion_redundancy_n",
        "net_ref_node_recall_9", "net_ref_edge_recall_9",
        "common_geometry_within_floor_jaccard_difference", "common_geometry_cross_floor_jaccard_difference",
        "common_geometry_advantage_floor_jaccard_difference",
        "common_geometry_within_mean_height_prism_pair_difference", "common_geometry_cross_mean_height_prism_pair_difference",
        "common_geometry_advantage_mean_height_prism_pair_difference",
        "within_corner_bottom_rms_deg", "cross_corner_bottom_rms_deg", "net_corner_bottom_rms_deg"]
CORE += ["sym_B8L2", "sym_D10", "sym_recorded_time_logratio", "sym_cross_abs_B8L2", "sym_abs_Q_change_advantage",
         "sym_loss_gt5", "sym_loss_gt10", "sym_C_failure_or_loss_gt5", "sym_C_failure_or_loss_gt10"]


def safe_numeric(data, columns):
    for c in columns:
        if data[c].dtype == "object":
            data[c] = data[c].replace({"True": 1, "False": 0})
        data[c] = pd.to_numeric(data[c], errors="coerce")


def ci(values, label):
    values = np.asarray(values, float)
    values = values[np.isfinite(values)]
    if len(values) < 2:
        return [None, None]
    rng = np.random.default_rng(int(h("bootstrap", label)[:16], 16))
    means = values[rng.integers(len(values), size=(3000, len(values)))].mean(axis=1)
    return list(np.quantile(means, [.025, .975]))


def views(data):
    for (direction, n, m), g in data.groupby(["training_QT_direction", "n", "m_AB"], sort=True):
        yield f"{direction};n{n};m{m}", dict(direction=direction, n=n, m=m, difficulty="ALL", scope="exact_n_m"), g
    preferred = data[data.training_QT_direction.eq("q_up__faster")]
    for n, g in preferred.groupby("n", sort=True):
        yield f"q_up__faster;n{n};all_m", dict(direction="q_up__faster", n=n, m="ALL", difficulty="ALL", scope="all_registered_scales"), g
    for (n, m, difficulty), g in preferred.groupby(["n", "m_AB", "difficulty"], sort=True):
        yield f"q_up__faster;n{n};m{m};{difficulty}", dict(direction="q_up__faster", n=n, m=m, difficulty=difficulty, scope="difficulty"), g
    verified = preferred[preferred.n.eq(20) & (preferred.available_history_delta_logT < 0) & preferred.m_AB.ge(3)]
    for m, g in verified.groupby("m_AB", sort=True):
        yield f"q_up__faster;n20;m{m};available_history_faster", dict(direction="q_up__faster", n=20, m=m, difficulty="ALL", scope="available_history_faster"), g
    # This semantic split was selected after Phase A outcome inspection.  It
    # identifies an interpretable fold-local role; raw class IDs are never
    # pooled across folds.  Phase B independently freezes new backgrounds.
    eligible = data[data.n.eq(20) & data.training_QT_direction.isin(["q_up__faster", "q_up__slower"])]
    for (direction, m, top), g in eligible.groupby(["training_QT_direction", "m_AB", "target_is_fold_Q_max"]):
        scope = "exploratory_target_top_training_Q" if top else "exploratory_target_not_top_training_Q"
        yield f"{direction};n20;m{m};{scope}", dict(direction=direction, n=20, m=m, difficulty="ALL", scope=scope), g


def main():
    global HERE
    ap = argparse.ArgumentParser()
    ap.add_argument("--study-dir", type=Path, default=HERE)
    args = ap.parse_args()
    HERE = args.study_dir.resolve()
    data = pd.read_csv(HERE / "EVENTS_COMPLETE.csv.gz", low_memory=False)
    assert not data.event_id.duplicated().any()
    center_file = HERE / "TRAINING_CLASS_CENTERS.csv"
    if not center_file.exists():
        center_file = HERE.parent / "TRAINING_CLASS_CENTERS.csv"
    centers = pd.read_csv(center_file)
    maxima = centers.loc[centers.groupby("heldout_building").q_history.idxmax()].set_index("heldout_building").coarse_label
    data["target_is_fold_Q_max"] = data.target_class.eq(data.building.map(maxima))
    history = pd.read_csv(HERE / "ACTUAL_DIRECTION_HISTORY.csv").rename(columns={"m": "m_AB"})
    data = data.merge(history[["pool_id", "source_class", "target_class", "n", "m_AB", "available_history_delta_Q", "available_history_delta_logT"]],
                      on=["pool_id", "source_class", "target_class", "n", "m_AB"], how="left", validate="many_to_one")
    complete = data.all_scored.astype(bool) & data.recorded_time_single_source.astype(bool)
    data["joint_common_net_Q"] = data.net_B8L2.where(complete)
    data["joint_common_net_logT"] = data.net_recorded_time_logratio.where(complete)
    data["joint_common_sym_Q"] = data.sym_B8L2.where(complete)
    data["joint_common_sym_logT"] = data.sym_recorded_time_logratio.where(complete)
    data["cross_abs_larger"] = (data.common_quality_cross_abs > data.common_quality_within_abs).where(data.all_scored)
    metrics = [c for c in data.columns if c.startswith(("same_", "within_", "cross_", "net_", "sym_", "common_geometry_", "common_expression_"))
               and pd.api.types.is_numeric_dtype(data[c])]
    metrics += [c for c in CORE + ["joint_common_net_Q", "joint_common_net_logT", "joint_common_sym_Q", "joint_common_sym_logT", "cross_abs_larger"] if c in data]
    metrics = list(dict.fromkeys(metrics))
    safe_numeric(data, metrics)
    panels = data.groupby(ID, dropna=False)[metrics].mean().reset_index()
    ps = data.groupby("panel_id").agg(events=("event_id", "size"), source_partitions=("source_partition_id", "nunique"),
                                     source_A_endpoints=("team_A", "nunique"), source_B_endpoints=("team_B", "nunique"),
                                     target_endpoints=("team_C", "nunique"), all_scored_events=("all_scored", "sum"),
                                     time_comparable_events=("recorded_time_single_source", "sum")).reset_index()
    panels = panels.merge(ps, on="panel_id", validate="one_to_one")
    write(HERE / "PANEL_EFFECTS.csv.gz", panels)
    conditions, long, image_rows, building_rows = [], [], [], []
    for view, meta, g in views(data):
        gp = panels[panels.panel_id.isin(g.panel_id)]
        images = gp.groupby(["building", "image"], dropna=False)[metrics].mean().reset_index()
        buildings = images.groupby("building")[metrics].mean().reset_index()
        images.insert(0, "view", view)
        buildings.insert(0, "view", view)
        image_rows.append(images)
        building_rows.append(buildings)
        rr = dict(view=view, **meta, events=len(g), finite_panels=len(gp), unique_backgrounds=g.background_id.nunique(),
                  images=g.image.nunique(), buildings=g.building.nunique(), actual_m_min=int(g.m_AB.min()), actual_m_max=int(g.m_AB.max()),
                  unique_source_endpoints=len(set(g.team_A) | set(g.team_B)), unique_target_endpoints=g.team_C.nunique(),
                  all_scored_events=int(g.all_scored.sum()), time_comparable_events=int(g.recorded_time_single_source.sum()))
        for metric in metrics:
            bv = buildings[metric].dropna()
            iv = images[metric].dropna()
            rr[metric] = float(bv.mean()) if len(bv) else None
            rr[metric + "_image_equal"] = float(iv.mean()) if len(iv) else None
            long.append(dict(view=view, **meta, metric=metric, mean_building_equal=rr[metric], mean_image_equal=rr[metric + "_image_equal"],
                             known_events=int(g[metric].notna().sum()), known_panels=int(gp[metric].notna().sum()),
                             known_images=len(iv), known_buildings=len(bv), positive_images=int((iv > 0).sum()),
                             negative_images=int((iv < 0).sum()), positive_buildings=int((bv > 0).sum()), negative_buildings=int((bv < 0).sum())))
        for metric, prefix, sign in [("net_B8L2", "quality", 1), ("net_recorded_time_logratio", "time", -1),
                                     ("abs_Q_change_advantage", "cross_abs_larger", 1), ("sym_B8L2", "sym_quality", 1),
                                     ("sym_recorded_time_logratio", "sym_time", -1), ("sym_abs_Q_change_advantage", "sym_cross_abs_larger", 1)]:
            for level, frame in [("image", images), ("building", buildings), ("panel", gp)]:
                vv = frame[metric].dropna()
                rr[level + "_" + prefix + "_improved"] = int((sign * vv > 0).sum())
                rr[level + "_" + prefix + "_known"] = len(vv)
        for level, frame in [("image", images), ("building", buildings), ("panel", gp)]:
            common = frame[["joint_common_net_Q", "joint_common_net_logT"]].dropna()
            rr[level + "_QT_both_improved"] = int(((common.joint_common_net_Q > 0) & (common.joint_common_net_logT < 0)).sum())
            rr[level + "_QT_known"] = len(common)
            sym = frame[["joint_common_sym_Q", "joint_common_sym_logT"]].dropna()
            rr[level + "_sym_QT_both_improved"] = int(((sym.joint_common_sym_Q > 0) & (sym.joint_common_sym_logT < 0)).sum())
            rr[level + "_sym_QT_known"] = len(sym)
        for pre in ["same", "cross", "net"]:
            value = rr[pre + "_recorded_time_logratio"]
            rr[pre + "_recorded_time_geomean_pct"] = 100 * math.expm1(value) if value is not None else None
        value = rr["joint_common_net_logT"]
        rr["joint_common_net_recorded_time_geomean_pct"] = 100 * math.expm1(value) if value is not None else None
        for key in ["sym_recorded_time_logratio", "joint_common_sym_logT"]:
            value = rr[key]
            rr[key + "_geomean_pct"] = 100 * math.expm1(value) if value is not None else None
        for metric in ["net_B8L2", "abs_Q_change_advantage", "net_recorded_time_logratio", "sym_B8L2", "sym_abs_Q_change_advantage", "sym_recorded_time_logratio"]:
            lo, hi = ci(buildings[metric], view + metric)
            rr[metric + "_building_bootstrap_low"] = lo
            rr[metric + "_building_bootstrap_high"] = hi
        # Endpoint failure denominators are distinct from combinatorial events.
        for arm in ["A", "B", "C"]:
            ep = g[["team_" + arm, arm + "_failure"]].drop_duplicates()
            rr[arm + "_unique_endpoints"] = len(ep)
            rr[arm + "_failed_unique_endpoints"] = int(ep[arm + "_failure"].sum())
        conditions.append(rr)
    write(HERE / "CONDITION_SUMMARY.csv", pd.DataFrame(conditions))
    write(HERE / "ALL_COMPONENTS_AND_DENOMINATORS.csv.gz", pd.DataFrame(long))
    write(HERE / "IMAGE_EFFECTS.csv.gz", pd.concat(image_rows, ignore_index=True))
    write(HERE / "BUILDING_EFFECTS.csv.gz", pd.concat(building_rows, ignore_index=True))

    # Across-background reproducibility at the same image, direction, n, m.
    repeat = []
    for key, g in panels.groupby(["pool_id", "image", "building", "difficulty", "training_QT_direction", "n", "m_AB"]):
        r = dict(zip(["pool_id", "image", "building", "difficulty", "direction", "n", "m"], key))
        r.update(backgrounds=len(g))
        for f in ["net_B8L2", "net_recorded_time_logratio", "abs_Q_change_advantage", "C_failure_or_net_loss_gt5", "sym_B8L2", "sym_recorded_time_logratio"]:
            v = g[f].dropna()
            r.update({f + "_mean": v.mean(), f + "_min": v.min(), f + "_max": v.max(), f + "_sd": v.std(),
                      f + "_positive_backgrounds": int((v > 0).sum()), f + "_negative_backgrounds": int((v < 0).sum()), f + "_known_backgrounds": len(v)})
        repeat.append(r)
    write(HERE / "BACKGROUND_REPETITION.csv", pd.DataFrame(repeat))
    n_paths(data)
    policies()
    member_contrasts(data)
    nominate_cases(data, panels)
    preferred = pd.DataFrame(conditions)
    cols = ["view", "events", "images", "buildings", "net_B8L2", "sym_B8L2", "sym_recorded_time_logratio_geomean_pct", "common_quality_within_abs", "sym_cross_abs_B8L2", "image_sym_quality_improved", "image_sym_quality_known", "building_sym_quality_improved", "building_sym_quality_known", "image_sym_QT_both_improved", "image_sym_QT_known", "C_failed_unique_endpoints", "C_unique_endpoints"]
    print(preferred.loc[preferred.direction.eq("q_up__faster") & preferred.scope.eq("exact_n_m"), cols].to_string(index=False), flush=True)
    evaluation = json.loads((HERE / "EVALUATION_RECEIPT.json").read_text())
    save(HERE / "SUMMARY_RECEIPT.json", dict(complete=evaluation["complete"], registered_events=evaluation["registered_events"],
              events=len(data), images=data.image.nunique(), buildings=data.building.nunique(),
              events_sha256=sha(HERE / "EVENTS_COMPLETE.csv.gz"), mean_order="event within finite panel -> image -> building",
              event_reuse_not_independent_evidence=True, source_and_target_member_support_separate=True,
              inferential_status="internal registered extension after earlier v2 exploration", quality_failures_not_assigned_zero=True,
              native_fusion_calls=0))


def n_paths(data):
    d = data[data.training_QT_direction.eq("q_up__faster") & data.n.isin([19, 20, 21])].copy()
    join = ["pool_id", "image", "building", "difficulty", "member_path", "m_AB", "source_class", "target_class", "outgoing_block_X", "same_count_block_Y", "changed_count_block_Z"]
    cols = ["event_id", "n", "team_A", "team_B", "team_C", "common_background", "A_counts", "B_counts", "C_counts",
            "net_B8L2", "sym_B8L2", "cross_B8L2", "same_B8L2", "C_failure", "B_failure",
            "A_nodes", "B_nodes", "C_nodes", "net_ref_node_recall_9", "net_recorded_time_logratio", "net_fusion_turn_n",
            "common_quality_within_abs", "sym_cross_abs_B8L2", "sym_abs_Q_change_advantage", "sym_recorded_time_logratio"]
    rows = []
    for left, right in [(19, 20), (20, 21)]:
        a, b = d[d.n.eq(left)][join + cols], d[d.n.eq(right)][join + cols]
        merged = a.merge(b, on=join, suffixes=["_from", "_to"], validate="one_to_one")
        merged["threshold_from"] = math.ceil(left / 2)
        merged["threshold_to"] = math.ceil(right / 2)
        merged["background_added_workers"] = ["|".join(sorted(set(b.split("|")) - set(a.split("|")))) for a, b in zip(merged.common_background_from, merged.common_background_to)]
        merged["background_removed_workers"] = ["|".join(sorted(set(a.split("|")) - set(b.split("|")))) for a, b in zip(merged.common_background_from, merged.common_background_to)]
        assert merged.background_removed_workers.eq("").all()
        merged["net_Q_effect_change"] = merged.net_B8L2_to - merged.net_B8L2_from
        merged["sym_Q_effect_change"] = merged.sym_B8L2_to - merged.sym_B8L2_from
        for metric in ["common_quality_within_abs", "sym_cross_abs_B8L2", "sym_abs_Q_change_advantage", "sym_recorded_time_logratio"]:
            merged[metric + "_change"] = merged[metric + "_to"] - merged[metric + "_from"]
        merged["net_Q_positive_to_negative"] = (merged.net_B8L2_from > 0) & (merged.net_B8L2_to < 0)
        merged["net_Q_negative_to_positive"] = (merged.net_B8L2_from < 0) & (merged.net_B8L2_to > 0)
        rows.append(merged)
    if rows:
        path = pd.concat(rows, ignore_index=True)
        write(HERE / "NESTED_N_PATHS_COMPLETE.csv.gz", path)
        num = ["net_Q_effect_change", "sym_Q_effect_change", "net_Q_positive_to_negative", "net_Q_negative_to_positive",
               "common_quality_within_abs_change", "sym_cross_abs_B8L2_change", "sym_abs_Q_change_advantage_change", "sym_recorded_time_logratio_change"]
        pan = path.groupby(["n_from", "n_to", "m_AB", "building", "image", "member_path"])[num].mean().reset_index()
        img = pan.groupby(["n_from", "n_to", "m_AB", "building", "image"])[num].mean().reset_index()
        bu = img.groupby(["n_from", "n_to", "m_AB", "building"])[num].mean().reset_index()
        write(HERE / "N_PATH_BUILDING_EFFECTS.csv", bu)


def policies():
    if not (HERE / "POLICIES_COMPLETE.csv.gz").exists():
        return
    p = pd.read_csv(HERE / "POLICIES_COMPLETE.csv.gz", low_memory=False)
    metrics = [c for c in p if c.startswith("change_") and pd.api.types.is_numeric_dtype(p[c])]
    metrics += ["P_failure", "P_failure_or_loss_gt5"]
    groups = ["policy", "m", "panel_id", "building", "image"]
    panel = p.groupby(groups)[metrics].mean().reset_index()
    images = panel.groupby(["policy", "m", "building", "image"])[metrics].mean().reset_index()
    buildings = images.groupby(["policy", "m", "building"])[metrics].mean().reset_index()
    write(HERE / "POLICY_PANEL_EFFECTS.csv.gz", panel)
    write(HERE / "POLICY_IMAGE_EFFECTS.csv", images)
    write(HERE / "POLICY_BUILDING_EFFECTS.csv", buildings)
    rows = []
    for (policy, m), g in buildings.groupby(["policy", "m"]):
        im = images[images.policy.eq(policy) & images.m.eq(m)]
        raw = p[p.policy.eq(policy) & p.m.eq(m)]
        row = dict(policy=policy, m=m, n=20, anchors=len(raw), images=len(im), buildings=len(g),
                   unique_A=raw.team_A.nunique(), unique_policy_teams=raw.team_P.nunique())
        row.update({k: g[k].mean() for k in metrics})
        row["recorded_time_geomean_pct"] = 100 * math.expm1(row["change_recorded_time_logratio"])
        for level, frame in [("image", im), ("building", g)]:
            co = frame[["change_B8L2", "change_recorded_time_logratio"]].dropna()
            row[level + "_QT_both_improved"] = int(((co.change_B8L2 > 0) & (co.change_recorded_time_logratio < 0)).sum())
            row[level + "_QT_known"] = len(co)
        rows.append(row)
    write(HERE / "POLICY_SUMMARY.csv", pd.DataFrame(rows))
    anchors = ["pool_id", "image", "building", "panel_id", "m", "team_A"]
    basecols = ["team_P", "P_member_workers", "change_B8L2", "change_D10", "change_recorded_time_logratio", "P_failure", "composition_turnover"]
    cls = p[p.policy.eq("class_QT_10")][anchors + basecols]
    exact = []
    for policy in ["continuous_Q_0", "continuous_QT_10", "continuous_QT_20"]:
        q = p[p.policy.eq(policy)][anchors + basecols]
        paired = cls.merge(q, on=anchors, suffixes=["_class", "_continuous"], validate="one_to_one")
        paired["continuous_policy"] = policy
        paired["same_selected_team"] = paired.team_P_class.eq(paired.team_P_continuous)
        paired["class_minus_continuous_Q"] = paired.change_B8L2_class - paired.change_B8L2_continuous
        paired["class_minus_continuous_D10"] = paired.change_D10_class - paired.change_D10_continuous
        paired["class_minus_continuous_logT"] = paired.change_recorded_time_logratio_class - paired.change_recorded_time_logratio_continuous
        paired["actual_policy_to_policy_m"] = [20 - len(set(a.split("|")) & set(b.split("|"))) for a, b in zip(paired.P_member_workers_class, paired.P_member_workers_continuous)]
        exact.append(paired)
    exact = pd.concat(exact, ignore_index=True)
    write(HERE / "CLASS_VS_CONTINUOUS_SAME_ANCHOR.csv.gz", exact)
    met = ["same_selected_team", "class_minus_continuous_Q", "class_minus_continuous_D10", "class_minus_continuous_logT", "actual_policy_to_policy_m"]
    pp = exact.groupby(["continuous_policy", "m", "panel_id", "building", "image"])[met].mean().reset_index()
    ii = pp.groupby(["continuous_policy", "m", "building", "image"])[met].mean().reset_index()
    bb = ii.groupby(["continuous_policy", "m", "building"])[met].mean().reset_index()
    write(HERE / "CLASS_VS_CONTINUOUS_IMAGE_EFFECTS.csv", ii)
    write(HERE / "CLASS_VS_CONTINUOUS_BUILDING_EFFECTS.csv", bb)
    out = bb.groupby(["continuous_policy", "m"])[met].mean().reset_index()
    out["class_minus_continuous_time_pct"] = 100 * np.expm1(out.class_minus_continuous_logT)
    write(HERE / "CLASS_VS_CONTINUOUS_SUMMARY.csv", out)


def member_contrasts(data):
    """Finite, same-background inclusion contrasts from complete m-subsets."""
    d = data[data.training_QT_direction.eq("q_up__faster") & data.n.eq(20)]
    if d.empty:
        return
    rows, exclusions = [], []
    for panel_id, g in d.groupby("panel_id"):
        meta = g.iloc[0]
        for role, arms in [("source", ["A", "B"]), ("target", ["C"])]:
            endpoints = []
            for arm in arms:
                ep = g[["team_" + arm, arm + "_B8L2", arm + "_D10", arm + "_nodes", arm + "_source_time_total_seconds", arm + "_failure",
                        "outgoing_block_X" if arm == "A" else ("same_count_block_Y" if arm == "B" else "changed_count_block_Z")]].copy()
                ep.columns = ["team_key", "Q", "D10", "nodes", "recorded_seconds", "failure", "block"]
                endpoints.append(ep)
            ep = pd.concat(endpoints, ignore_index=True).drop_duplicates("team_key")
            workers = sorted(set("|".join(ep.block).split("|")))
            for worker in workers:
                present = ep.block.map(lambda s: worker in s.split("|"))
                a, b = ep[present], ep[~present]
                row = dict(panel_id=panel_id, pool_id=meta.pool_id, image=meta.image, building=meta.building, role=role,
                           source_class=meta.source_class, target_class=meta.target_class, n=20, m=meta.m_AB,
                           worker_id=worker, in_endpoints=len(a), out_endpoints=len(b), estimable=bool(len(a) and len(b)),
                           interpretation="finite same-background subset inclusion contrast; not a permanent individual causal effect")
                for f in ["Q", "D10", "nodes", "recorded_seconds", "failure"]:
                    row[f + "_in_mean"] = a[f].mean()
                    row[f + "_out_mean"] = b[f].mean()
                    row[f + "_in_minus_out"] = a[f].mean() - b[f].mean() if len(a) and len(b) else None
                rows.append(row)
                if role == "target":
                    contains = g.changed_count_block_Z.map(lambda s: worker in s.split("|"))
                    present_events, absent_events = g[contains], g[~contains]
                    erow = {k: row[k] for k in ["panel_id", "pool_id", "image", "building", "source_class", "target_class", "n", "m", "worker_id", "estimable", "in_endpoints", "out_endpoints"]}
                    for scope, sub in [("with", present_events), ("without", absent_events)]:
                        erow[scope + "_net_Q"] = sub.net_B8L2.mean()
                        erow[scope + "_sym_Q"] = sub.sym_B8L2.mean()
                        erow[scope + "_sym_logT"] = sub.sym_recorded_time_logratio.mean()
                        erow[scope + "_failure_rate"] = sub[["team_C", "C_failure"]].drop_duplicates().C_failure.mean()
                    exclusions.append(erow)
    result = pd.DataFrame(rows)
    write(HERE / "MEMBER_INCLUSION_CONTRASTS.csv.gz", result)
    gg = result[result.estimable].groupby(["role", "m", "worker_id", "building", "image"])
    cols = ["Q_in_minus_out", "D10_in_minus_out", "recorded_seconds_in_minus_out", "failure_in_minus_out"]
    image = gg[cols].mean().reset_index()
    build = image.groupby(["role", "m", "worker_id", "building"])[cols].mean().reset_index()
    write(HERE / "MEMBER_BUILDING_CONTRASTS.csv", build)
    exclusion = pd.DataFrame(exclusions)
    write(HERE / "TARGET_MEMBER_EXCLUSION_PANELS.csv", exclusion)
    ec = ["with_net_Q", "without_net_Q", "with_sym_Q", "without_sym_Q", "with_sym_logT", "without_sym_logT", "with_failure_rate", "without_failure_rate"]
    ex_image = exclusion[exclusion.estimable].groupby(["m", "worker_id", "building", "image"])[ec].mean().reset_index()
    ex_building = ex_image.groupby(["m", "worker_id", "building"])[ec].mean().reset_index()
    write(HERE / "TARGET_MEMBER_EXCLUSION_IMAGES.csv", ex_image)
    write(HERE / "TARGET_MEMBER_EXCLUSION_BUILDINGS.csv", ex_building)
    exsummary = []
    for (m, worker), gg in ex_building.groupby(["m", "worker_id"]):
        ii = ex_image[(ex_image.m == m) & (ex_image.worker_id == worker)]
        erow = dict(m=m, worker_id=worker, images=len(ii), buildings=len(gg),
                    without_quality_positive_images=int((ii.without_sym_Q > 0).sum()),
                    without_quality_known_images=int(ii.without_sym_Q.notna().sum()),
                    without_quality_positive_buildings=int((gg.without_sym_Q > 0).sum()),
                    without_quality_known_buildings=int(gg.without_sym_Q.notna().sum()))
        erow.update({c: gg[c].mean() for c in ec})
        exsummary.append(erow)
    write(HERE / "TARGET_MEMBER_EXCLUSION_SUMMARY.csv", pd.DataFrame(exsummary))


def nominate_cases(data, panels):
    d = data[data.training_QT_direction.eq("q_up__faster") & data.n.eq(20)].copy()
    rows = []
    criteria = [
        ("position_gain_same_nodes", d[(d.A_nodes == d.B_nodes) & (d.B_nodes == d.C_nodes) & (d.net_B8L2 > 3) & (d.net_S_bottom_deg < 0)], "net_B8L2", False),
        ("structure_gain", d[(d.net_ref_node_recall_9 > 0) & (d.net_nodes > 0) & (d.net_B8L2 > 3)], "net_B8L2", False),
        ("quality_loss", d[d.net_B8L2 < -5], "net_B8L2", True),
        ("fusion_failure", d[d.C_failure], "m_AB", False),
    ]
    for tag, sub, rank, ascending in criteria:
        chosen = sub.sort_values(rank, ascending=ascending).drop_duplicates(["image", "m_AB"]).head(8)
        for r in chosen.to_dict("records"):
            rows.append(dict(case_role=tag, **{k: r[k] for k in ["event_id", "pool_id", "image", "building", "n", "m_AB", "source_class", "target_class", "panel_id", "team_A", "team_B", "team_C", "same_B8L2", "cross_B8L2", "net_B8L2", "net_D10", "net_recorded_time_logratio", "A_nodes", "B_nodes", "C_nodes", "C_failure", "net_S_bottom_deg", "net_ref_node_recall_9"]}))
    write(HERE / "MECHANISM_CASE_CANDIDATES.csv", pd.DataFrame(rows))


if __name__ == "__main__":
    main()
