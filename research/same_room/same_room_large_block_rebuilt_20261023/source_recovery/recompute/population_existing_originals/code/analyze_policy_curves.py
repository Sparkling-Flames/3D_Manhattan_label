"""Matched category-priority versus natural-prefix process effects.

The endpoint engine owns fusion. This module joins its actual saved results,
keeps every paired prefix and aggregates with image/building denominators.
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import os
from pathlib import Path

import numpy as np
import pandas as pd

from register_population_orders import save_csv, write_bytes


METRICS = [
    "B8L2", "D10", "IoU3D100", "iou_2d", "S_bottom_deg", "dir", "Hmean", "Hcenter",
    "omission", "extension", "height_mean_ratio", "nodes", "reference_node_shortfall",
    "floor_turn5_n", "floor_redundant5_n", "floor_short_edge_03_n", "floor_short_edge_05_n",
    "ref_node_recall_5", "ref_node_recall_9", "ref_edge_recall_5", "ref_edge_recall_9",
    "floor_area_camera_h2", "centroid_x_h", "centroid_z_h", "height_mean_h", "height_sd_h",
    "top_y_mean_px", "bottom_y_mean_px", "boundary_loss", "direction_loss",
    "global_height_loss", "local_height_loss", "source_time_total_seconds", "target_time_total_seconds",
    "B8_floor_block", "B8_direction_block", "B8_global_height_block", "B8_local_height_block", "B8_height_block", "D10_direction_block",
    "ref_top_pair_mean_deg", "ref_bottom_pair_mean_deg", "ref_top_pair_max_deg", "ref_bottom_pair_max_deg",
    "ref_assigned_pair_n", "ref_unassigned_pair_n", "candidate_unassigned_pair_n",
]
FLAGS = ["score_available", "score_failure_nonpolicy", "incomplete_nonpolicy", "policy_deferred", "complete_evaluable"]
META = ["pool_id", "image", "image_id", "building", "condition", "layer", "difficulty", "pool_n", "reference_id", "reference_version"]


def numeric(series):
    return pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)


def asbool(series):
    return series.map(lambda x: x in (True, 1, "True", "true", "1") if pd.notna(x) else np.nan)


def add_support_metadata(d, annotations):
    if not annotations:
        return d
    a = pd.read_csv(annotations)
    keep = [x for x in ["image", "difficulty_coarse", "difficulty_conditional", "structure_opportunity", "image_layer", "is_doorway", "fixed_six_turn_opportunity", "ref_short_edges", "ref_H"] if x in a]
    d = d.merge(a[keep].drop_duplicates("image"), on="image", how="left", validate="many_to_one")
    if "difficulty_coarse" in d:
        d["difficulty_original_snapshot"] = d["difficulty"]
        d["difficulty"] = d["difficulty_coarse"].fillna(d["difficulty"])
    return d


def make_member_differences(orders):
    bases = orders[orders.policy == "natural_random"].set_index("path_id")
    rows = []
    for r in orders[orders.policy != "natural_random"].to_dict("records"):
        natural = bases.loc[r["base_path_id"], "worker_order"].split("|")
        priority = r["worker_order"].split("|")
        target = set(str(r["target_members"]).split("|")) - {"", "nan"}
        a, b = set(), set()
        for k, (wa, wb) in enumerate(zip(natural, priority), 1):
            a.add(wa); b.add(wb)
            rows.append(dict(path_id=r["path_id"], k=k, actual_m=len(b-a), shared_n=len(a&b),
                             natural_target_n=len(a&target), priority_target_n=len(b&target),
                             target_seat_change=len(b&target)-len(a&target),
                             target_capacity=r["target_capacity"], unknown_pool_n=r.get("unknown_capacity", np.nan)))
    return pd.DataFrame(rows)


def paired_events(results, orders, annotations=None):
    d = add_support_metadata(results, annotations)
    metrics = [x for x in METRICS if x in d]
    for m in metrics:
        d[m] = numeric(d[m])
    for f in FLAGS:
        if f in d:
            d[f] = asbool(d[f]).astype(float)
    if "score_available" not in d:
        d["score_available"] = d.B8L2.notna().astype(float)
    if "policy_deferred" not in d:
        d["policy_deferred"] = d.k.eq(2).astype(float)
    if "score_failure_nonpolicy" not in d:
        d["score_failure_nonpolicy"] = (d.B8L2.isna() & d.k.ne(2)).astype(float)
    if "incomplete_nonpolicy" not in d:
        d["incomplete_nonpolicy"] = (d.complete_evaluable.eq(0) & d.k.ne(2)).astype(float)
    for prefix in ["source", "target"]:
        time_col = prefix + "_time_total_seconds"
        known_col = prefix + "_time_known_n"
        if time_col in d and known_col in d:
            d.loc[numeric(d[known_col]) != numeric(d.k), time_col] = np.nan
    flags = [x for x in FLAGS if x in d]
    outputs = metrics + flags
    base = d[d.policy == "natural_random"][["path_id", "k", "team_key", *outputs]].copy()
    base = base.rename(columns={"path_id":"base_path_id", "team_key":"natural_team_key", **{x:x+"_natural" for x in outputs}})
    keep = [x for x in META + ["path_id", "base_path_id", "policy", "replicate", "k", "team_key", "sample_kind", "target_class", "method", "tier", "structure_opportunity", "image_layer", "difficulty_original_snapshot", "ref_short_edges", "ref_H"] if x in d]
    p = d[d.policy != "natural_random"][keep + outputs].copy()
    p = p.rename(columns={"team_key":"priority_team_key", **{x:x+"_priority" for x in outputs}})
    p = p.merge(base, on=["base_path_id", "k"], how="left", validate="many_to_one")
    if p.natural_team_key.isna().any():
        raise ValueError("Priority prefixes are missing their exact paired natural endpoint")
    diffs = make_member_differences(orders)
    p = p.merge(diffs, on=["path_id", "k"], how="left", validate="one_to_one")
    pool_times = orders[["pool_id", "pool_n", "source_time_known_n"]].drop_duplicates("pool_id")
    pool_times["pool_source_time_complete"] = numeric(pool_times.source_time_known_n).eq(numeric(pool_times.pool_n))
    p = p.merge(pool_times[["pool_id", "pool_source_time_complete"]],on="pool_id",how="left",validate="many_to_one")
    p["pool_fraction"] = p.k / p.pool_n
    p["policy_pair_sample_kind"] = np.select(
        [p.pool_n.eq(3),p.pool_n.eq(4)],
        ["all_6_natural_permutations_transformed","8_seeded_paths_from_exact_24_natural_catalogue"],
        default="8_uniform_natural_paths_transformed")
    p["at_full_pool"] = p.k.eq(p.pool_n)
    p["actual_replacement_fraction"] = p.actual_m / p.k
    p["target_seat_fraction_change"] = p.target_seat_change / p.k
    for m in outputs:
        p[m+"_delta"] = p[m+"_priority"] - p[m+"_natural"]
    p["abs_B8L2_change"] = p.B8L2_delta.abs()
    p["Q_loss_gt5"] = p.B8L2_delta.lt(-5).where(p.B8L2_delta.notna()).astype(float)
    p["Q_gain_gt5"] = p.B8L2_delta.gt(5).where(p.B8L2_delta.notna()).astype(float)
    for goal in (80, 90):
        for side in ("priority", "natural"):
            p[f"achieved_Q{goal}_{side}"] = p[f"B8L2_{side}"].ge(goal).astype(float)
        p[f"achieved_Q{goal}_delta"] = p[f"achieved_Q{goal}_priority"] - p[f"achieved_Q{goal}_natural"]
    for prefix in ("source", "target"):
        column = prefix + "_time_total_seconds"
        if column in metrics:
            good = p[column+"_priority"].gt(0) & p[column+"_natural"].gt(0)
            p[prefix+"_time_logratio"] = np.log(p[column+"_priority"] / p[column+"_natural"]).where(good)
    if "source_time_logratio" in p:
        qt = p.B8L2_delta.notna() & p.source_time_logratio.notna()
        p["QT_Q_delta"] = p.B8L2_delta.where(qt)
        p["QT_time_logratio"] = p.source_time_logratio.where(qt)
    final = p[p.at_full_pool]
    assert final.priority_team_key.equals(final.natural_team_key)
    assert (final.actual_m == 0).all()
    assert (final.B8L2_delta.dropna().abs() < 1e-10).all()
    return p, metrics, flags


def per_image_k(p, metrics, flags):
    """Vectorized aggregation preserves all per-metric denominators."""
    keys = ["pool_id", "image", "building", "condition", "layer", "difficulty", "pool_n", "policy", "k"]
    optional = [x for x in ("structure_opportunity", "image_layer") if x in p]
    p = p.copy()
    p["_q_positive"] = p.B8L2_delta.gt(0).where(p.B8L2_delta.notna()).astype(float)
    for m in metrics:
        p[m+"_absolute_delta"] = p[m+"_delta"].abs()
    gb = p.groupby(keys, dropna=False, sort=False)
    outputs = [c for m in metrics for c in [m+"_natural", m+"_priority", m+"_delta", m+"_absolute_delta"]]
    outputs += [c for f in flags+["achieved_Q80","achieved_Q90"] for c in [f+"_natural",f+"_priority",f+"_delta"]]
    outputs += [c for c in ["_q_positive","Q_loss_gt5","Q_gain_gt5","actual_m","target_seat_change","natural_target_n","priority_target_n","source_time_logratio","target_time_logratio","QT_Q_delta","QT_time_logratio"] if c in p]
    means = gb[outputs].mean();counts = gb[outputs].count()
    numerical = [c for m in metrics for c in [m+"_natural", m+"_priority", m+"_delta"]]
    medians = gb[numerical].median()
    q10 = gb[numerical].quantile(.1);q90 = gb[numerical].quantile(.9)
    sds = gb[numerical].std(ddof=0)
    mins = gb[["B8L2_natural","B8L2_priority"]].min()
    maxs = gb[["B8L2_natural","B8L2_priority","actual_m"]].max()
    out = gb.size().to_frame("paired_paths")
    out["paired_Q"] = counts.B8L2_delta
    for side in ["natural","priority"]:
        out[side+"_scorable"] = counts["B8L2_"+side]
        out[side+"_unique_teams"] = gb[side+"_team_key"].nunique()
        valid_unique = p[p["B8L2_"+side].notna()].groupby(keys,dropna=False)[side+"_team_key"].nunique()
        out[side+"_scorable_unique_teams"] = valid_unique.reindex(out.index,fill_value=0)
        out[side+"_variance_estimable"] = out[side+"_scorable_unique_teams"].ge(2)
        out[side+"_fixed_membership"] = out[side+"_unique_teams"].eq(1)
        for dest,stat in [("mean",means),("p10",q10),("p50",medians),("p90",q90),("sd",sds)]:
            out["Q_"+side+"_"+dest] = stat["B8L2_"+side]
        out["Q_"+side+"_range"] = maxs["B8L2_"+side] - mins["B8L2_"+side]
    for c in ["at_full_pool","target_capacity","unknown_pool_n","pool_source_time_complete",*optional]:
        out[c] = gb[c].first()
    out["priority_exact_target_block"] = out.index.get_level_values("k").to_numpy() == out.target_capacity.to_numpy()
    out["priority_fixed_set_reason"] = np.select(
        [out.at_full_pool,out.priority_exact_target_block & out.priority_fixed_membership,out.priority_fixed_membership],
        ["full_actual_pool","all_members_of_selected_target_class","one_observed_member_set"],default="multiple_member_sets")
    for target,source in [("actual_m_mean","actual_m"),("target_seat_change_mean","target_seat_change"),
                          ("natural_target_n_mean","natural_target_n"),("priority_target_n_mean","priority_target_n"),
                          ("Q_mean_delta","B8L2_delta"),("Q_abs_change_mean","B8L2_absolute_delta"),
                          ("Q_positive_fraction","_q_positive"),("Q_loss_gt5_fraction","Q_loss_gt5"),
                          ("Q_gain_gt5_fraction","Q_gain_gt5")]:
        out[target] = means[source]
    out["actual_m_max"] = maxs.actual_m
    kval=out.index.get_level_values("k").to_numpy()
    out["actual_replacement_fraction_mean"] = out.actual_m_mean/kval
    out["target_seat_fraction_change_mean"] = out.target_seat_change_mean/kval
    out["natural_target_proportion_mean"] = out.natural_target_n_mean/kval
    out["priority_target_proportion_mean"] = out.priority_target_n_mean/kval
    out["Q_median_delta"] = medians.B8L2_delta
    out["Q_p10_delta"] = out.Q_priority_p10 - out.Q_natural_p10
    out["Q_sd_delta"] = out.Q_priority_sd - out.Q_natural_sd
    for f in flags+["achieved_Q80","achieved_Q90"]:
        for side in ("natural","priority"):
            out[f+"_"+side+"_rate"] = means[f+"_"+side]
        out[f+"_delta"] = means[f+"_delta"]
    for prefix in ("source","target"):
        f=prefix+"_time_logratio"
        if f in means:
            out[f] = means[f]
            out[prefix+"_time_pct_change"] = 100*np.expm1(out[f])
            out[prefix+"_time_pairs"] = counts[f]
    if "QT_Q_delta" in means:
        out["QT_Q_delta"] = means.QT_Q_delta
        out["QT_time_logratio"] = means.QT_time_logratio
        out["QT_pairs"] = counts.QT_Q_delta
    metric_tables = []
    for m in metrics:
        frame = pd.DataFrame(index=out.index)
        frame["metric"] = m;frame["attempted"] = out.paired_paths
        frame["paired"] = counts[m+"_delta"]
        frame["natural_valid"] = counts[m+"_natural"]
        frame["priority_valid"] = counts[m+"_priority"]
        frame["natural_mean"] = means[m+"_natural"]
        frame["priority_mean"] = means[m+"_priority"]
        frame["paired_mean_delta"] = means[m+"_delta"]
        frame["paired_median_delta"] = medians[m+"_delta"]
        frame["paired_abs_delta"] = means[m+"_absolute_delta"]
        for side in ("natural","priority"):
            for dest,stat in [("p10",q10),("p50",medians),("p90",q90),("sd",sds)]:
                frame[side+"_"+dest] = stat[m+"_"+side]
        metric_tables.append(frame.reset_index())
    return out.reset_index(), pd.concat(metric_tables,ignore_index=True)


def focal_rows(perk):
    rows = []
    keys = ["pool_id", "image", "building", "condition", "layer", "difficulty", "pool_n", "policy"]
    optional = [x for x in ("structure_opportunity", "image_layer", "pool_source_time_complete") if x in perk]
    numerical = [x for x in perk.select_dtypes(include=[np.number]) if x not in keys + ["k"]]
    for key, g in perk.groupby(keys, dropna=False, sort=False):
        meta = dict(zip(keys, key));meta.update({x:g[x].iloc[0] for x in optional})
        n = int(meta["pool_n"])
        selections = {}
        for k in (3, 6, 10, 20):
            selections[f"k{k}"] = g[g.k == k]
        for fraction, name in [(.25,"quarter_pool"),(.5,"half_pool"),(.75,"threequarter_pool")]:
            k = max(3, math.ceil(fraction*n))
            if k <= n:
                selections[name] = g[g.k == k]
        selections["first_half_average_k3plus"] = g[g.k.between(3, math.floor(n/2))]
        selections["whole_path_nonterminal_k3plus"] = g[g.k.between(3, n-1)]
        selections["terminal_full_pool"] = g[g.k == n]
        for name, h in selections.items():
            if h.empty:
                continue
            row = dict(meta, landmark=name, k_min=int(h.k.min()), k_max=int(h.k.max()), k_values=len(h),
                       k_mean=float(h.k.mean()),includes_full_pool=bool(h.at_full_pool.any()))
            row.update({x:h[x].mean() for x in numerical})
            row["attempted_prefix_pairs_total"] = int(h.paired_paths.sum())
            row["scorable_prefix_pairs_total"] = int(h.paired_Q.sum())
            if "source_time_pairs" in h:
                row["source_time_prefix_pairs_total"] = int(h.source_time_pairs.sum())
                row["source_time_k_values"] = int(h.source_time_pairs.gt(0).sum())
            if "QT_pairs" in h:
                row["QT_prefix_pairs_total"] = int(h.QT_pairs.sum())
                row["QT_k_values"] = int(h.QT_pairs.gt(0).sum())
            for prefix in ("source","target"):
                logkey = prefix+"_time_logratio"
                if logkey in row:
                    row[prefix+"_time_pct_change"] = 100*np.expm1(row[logkey])
            rows.append(row)
    return pd.DataFrame(rows)


def aggregate_focal(focal, common_pool_ids=None):
    keys = ["condition", "layer", "landmark", "policy"]
    outcome_cols = [x for x in ["Q_mean_delta", "Q_median_delta", "Q_abs_change_mean", "Q_p10_delta", "Q_sd_delta", "Q_positive_fraction", "Q_loss_gt5_fraction", "Q_gain_gt5_fraction", "score_failure_nonpolicy_delta", "incomplete_nonpolicy_delta", "achieved_Q80_delta", "achieved_Q90_delta", "actual_m_mean", "target_seat_change_mean", "source_time_logratio", "target_time_logratio", "QT_Q_delta", "QT_time_logratio",
        "actual_replacement_fraction_mean","target_seat_fraction_change_mean","natural_target_n_mean","priority_target_n_mean",
        "natural_target_proportion_mean","priority_target_proportion_mean","target_capacity","k_mean"] if x in focal]
    summaries, buildings = [], []
    common = (focal[focal.groupby(["pool_id","landmark"]).policy.transform("nunique")==4]
              if common_pool_ids is None else focal[focal.pool_id.isin(common_pool_ids)])
    cohorts = [("own_supported_pools",focal), ("all_four_policies_common_pools",common)]
    cohorts += [("all_four_common_Nge20",common[common.pool_n.ge(20)])]
    if "pool_source_time_complete" in focal:
        cohorts += [("own_supported_full_pool_time_complete",focal[focal.pool_source_time_complete]),
                    ("all_four_common_full_pool_time_complete",common[common.pool_source_time_complete]),
                    ("all_four_common_Nge20_time_complete",common[common.pool_source_time_complete & common.pool_n.ge(20)])]
    for cohort, frame in cohorts:
        for terminal_scope, f in [("all_supported",frame),("nonterminal_only",frame[~frame.includes_full_pool])]:
            for stratum in ["all", "difficulty", "structure_opportunity"]:
                groupkeys = keys if stratum=="all" else keys+[stratum]
                if any(k not in f for k in groupkeys):
                    continue
                if f.empty:continue
                work=f.copy()
                flags={"images_with_Q":work.Q_mean_delta.notna(),"images_Q_up":work.Q_mean_delta.gt(0),
                    "images_Q_down":work.Q_mean_delta.lt(0),"images_absQ_le1":work.Q_mean_delta.abs().le(1),
                    "images_Q_up_gt2":work.Q_mean_delta.gt(2),"images_Q_down_ltminus2":work.Q_mean_delta.lt(-2),
                    "images_Q_down_ltminus5":work.Q_mean_delta.lt(-5),"images_p10_up":work.Q_p10_delta.gt(0),
                    "images_variation_smaller":work.Q_sd_delta.lt(0)}
                if "source_time_k_values" in work:flags["images_with_time_at_all_selected_k"]=work.source_time_k_values.eq(work.k_values)
                if "QT_k_values" in work:flags["images_with_QT_at_all_selected_k"]=work.QT_k_values.eq(work.k_values)
                if "source_time_logratio" in work:
                    flags.update(images_with_time=work.source_time_logratio.notna(),images_time_down=work.source_time_logratio.lt(0),
                        images_Qup_Tdown_separate_metric_support=work.Q_mean_delta.gt(0)&work.source_time_logratio.lt(0))
                if "QT_Q_delta" in work:
                    flags.update(images_joint_QT=work.QT_Q_delta.notna()&work.QT_time_logratio.notna(),
                        images_joint_Qup_Tdown=work.QT_Q_delta.gt(0)&work.QT_time_logratio.lt(0))
                for name,value in flags.items():work['_'+name]=value.astype(int)
                gb=work.groupby(groupkeys,dropna=False,sort=False)
                spec=dict(images=('image','nunique'),buildings=('building','nunique'),pools=('pool_id','nunique'),
                          images_with_terminal=('includes_full_pool','sum'))
                spec.update({name:('_'+name,'sum') for name in flags})
                for count_field in ["attempted_prefix_pairs_total","scorable_prefix_pairs_total","source_time_prefix_pairs_total","QT_prefix_pairs_total"]:
                    if count_field in work:spec[count_field]=(count_field,'sum')
                row=gb.agg(**spec)
                stats={"image_mean":gb[outcome_cols].mean(),"image_median":gb[outcome_cols].median(),
                       "image_p10":gb[outcome_cols].quantile(.1),"image_p90":gb[outcome_cols].quantile(.9)}
                bgb=work.groupby(groupkeys+['building'],dropna=False,sort=False)
                brow=bgb.agg(images=('image','nunique'),images_with_Q=('_images_with_Q','sum'),
                    images_Q_up=('_images_Q_up','sum'),images_Q_down=('_images_Q_down','sum')).join(bgb[outcome_cols].mean()).reset_index()
                brow['_valid_q']=brow.Q_mean_delta.notna().astype(int);brow['_up_q']=brow.Q_mean_delta.gt(0).astype(int);brow['_down_q']=brow.Q_mean_delta.lt(0).astype(int)
                bt=brow.groupby(groupkeys,dropna=False,sort=False)
                row['buildings_with_Q']=bt['_valid_q'].sum();row['buildings_Q_up']=bt['_up_q'].sum();row['buildings_Q_down']=bt['_down_q'].sum()
                stats['building_mean']=bt[outcome_cols].mean()
                columns={c+'_'+suffix:values[c] for suffix,values in stats.items() for c in outcome_cols}
                row=row.join(pd.DataFrame(columns))
                if 'source_time_logratio' in work:
                    row['source_time_pct_change_image_equal']=100*np.expm1(stats['image_mean'].source_time_logratio)
                    row['source_time_pct_change_building_equal']=100*np.expm1(stats['building_mean'].source_time_logratio)
                if 'QT_time_logratio' in work:row['QT_time_pct_change_image_equal']=100*np.expm1(stats['image_mean'].QT_time_logratio)
                row=row.reset_index();brow=brow.drop(columns=['_valid_q','_up_q','_down_q'])
                for frame in [row,brow]:frame['cohort']=cohort;frame['terminal_scope']=terminal_scope;frame['stratum']=stratum
                summaries.append(row);buildings.append(brow)
    return pd.concat(summaries,ignore_index=True),pd.concat(buildings,ignore_index=True)


def policy_attainments(p):
    """Posterior first-hit and all-remaining-prefix attainment, not a stop rule."""
    rows=[]
    meta_cols=[x for x in META+["policy","path_id","base_path_id","replicate","pool_source_time_complete","structure_opportunity"] if x in p]
    for path,g in p.groupby("path_id",sort=False):
        g=g.sort_values("k");ks=g.k.to_numpy(int);n=int(g.pool_n.iloc[0])
        assert np.array_equal(ks,np.arange(1,n+1)),("incomplete_prefix_path",path)
        meta={c:g.iloc[0][c] for c in meta_cols}
        for threshold in (80,90):
            hits={};terminal={}
            for side in ("natural","priority"):
                q=g["B8L2_"+side].to_numpy(float);good=np.isfinite(q)&(q>=threshold)
                terminal[side]=bool(good[-1])
                all_hits=np.flatnonzero(good);from3=np.flatnonzero(good&(ks>=3));bad=np.flatnonzero(~good)
                stable_index=(int(bad[-1])+1 if len(bad) else 0) if good[-1] else None
                hits[side]={"first_hit_all_k":int(all_hits[0]) if len(all_hits) else None,
                            "first_hit_k_ge3":int(from3[0]) if len(from3) else None,
                            "sustained_to_full_pool":stable_index}
            assert terminal["natural"]==terminal["priority"]
            for kind in ("first_hit_all_k","first_hit_k_ge3","sustained_to_full_pool"):
                a,b=hits["natural"][kind],hits["priority"][kind]
                row=dict(meta,Q_threshold=threshold,attainment_kind=kind,full_pool_meets=terminal["natural"],
                         natural_reached=a is not None,priority_reached=b is not None,
                         both_reached=a is not None and b is not None,
                         only_priority_reached=a is None and b is not None,
                         only_natural_reached=a is not None and b is None,
                         neither_reached=a is None and b is None,
                         natural_hit_k=ks[a] if a is not None else np.nan,
                         priority_hit_k=ks[b] if b is not None else np.nan)
                row["k_delta"]=(ks[b]-ks[a]) if row["both_reached"] else np.nan
                for side,index in [("natural",a),("priority",b)]:
                    col="source_time_total_seconds_"+side
                    row["source_time_at_hit_"+side]=g[col].iloc[index] if index is not None and col in g else np.nan
                ta,tb=row["source_time_at_hit_natural"],row["source_time_at_hit_priority"]
                comparable=pd.notna(ta) and pd.notna(tb) and ta>0 and tb>0
                row["source_time_at_hit_both_complete"]=comparable
                row["source_time_at_hit_delta_seconds"]=tb-ta if comparable else np.nan
                row["source_time_at_hit_logratio"]=math.log(tb/ta) if comparable else np.nan
                rows.append(row)
    paths=pd.DataFrame(rows)
    keys=["pool_id","image","building","condition","layer","difficulty","pool_n","policy","Q_threshold","attainment_kind"]
    image_rows=[]
    for key,g in paths.groupby(keys,dropna=False,sort=False):
        row=dict(zip(keys,key),paired_paths=len(g),pool_source_time_complete=bool(g.pool_source_time_complete.iloc[0]))
        if "structure_opportunity" in g:row["structure_opportunity"]=g.structure_opportunity.iloc[0]
        for col in ["natural_reached","priority_reached","both_reached","only_priority_reached","only_natural_reached","neither_reached","source_time_at_hit_both_complete"]:
            row[col+"_n"]=int(g[col].sum());row[col+"_rate"]=g[col].mean()
        row["final_meets"]=bool(g.full_pool_meets.iloc[0])
        for col in ["natural_hit_k","priority_hit_k","k_delta","source_time_at_hit_delta_seconds","source_time_at_hit_logratio"]:
            v=g[col].dropna();row[col+"_mean"]=v.mean() if len(v) else np.nan
            row[col+"_median"]=v.median() if len(v) else np.nan
        d=g.k_delta.dropna();row["priority_earlier_fraction_given_both"]=d.lt(0).mean() if len(d) else np.nan
        row["priority_later_fraction_given_both"]=d.gt(0).mean() if len(d) else np.nan
        row["source_time_at_hit_pct_change"]=100*np.expm1(row["source_time_at_hit_logratio_mean"])
        image_rows.append(row)
    images=pd.DataFrame(image_rows)
    summary=[];building_rows=[]
    fields=["k_delta_mean","source_time_at_hit_delta_seconds_mean","source_time_at_hit_logratio_mean","natural_reached_rate","priority_reached_rate","only_priority_reached_rate","only_natural_reached_rate","both_reached_rate","neither_reached_rate","priority_earlier_fraction_given_both","priority_later_fraction_given_both"]
    common_pools=set(images.groupby("pool_id").policy.nunique().loc[lambda v:v.eq(4)].index)
    common=images[images.pool_id.isin(common_pools)]
    cohorts=[("own_supported_pools",images),
             ("all_four_policies_common_pools",common),
             ("all_four_common_Nge20",common[common.pool_n.ge(20)]),
             ("own_supported_full_pool_time_complete",images[images.pool_source_time_complete]),
             ("all_four_common_full_pool_time_complete",common[common.pool_source_time_complete]),
             ("all_four_common_Nge20_time_complete",common[common.pool_source_time_complete&common.pool_n.ge(20)])]
    for cohort,frame in cohorts:
        for stratum in ["all","difficulty","structure_opportunity"]:
            groupkeys=["condition","layer","policy","Q_threshold","attainment_kind"]+([] if stratum=="all" else [stratum])
            if any(c not in frame for c in groupkeys):continue
            for key,g in frame.groupby(groupkeys,dropna=False,sort=False):
                meta=dict(zip(groupkeys,key),cohort=cohort,stratum=stratum)
                row=dict(meta,images=g.image.nunique(),buildings=g.building.nunique(),
                         images_with_both_reached=int(g.k_delta_mean.notna().sum()),
                         images_priority_earlier=int(g.k_delta_mean.lt(0).sum()),images_priority_later=int(g.k_delta_mean.gt(0).sum()))
                for c in ["paired_paths","both_reached_n","only_priority_reached_n","only_natural_reached_n","neither_reached_n","source_time_at_hit_both_complete_n"]:
                    row[c]=int(g[c].sum())
                bg=g.groupby("building")[fields].mean()
                for f in fields:row[f+"_image_mean"]=g[f].mean();row[f+"_building_mean"]=bg[f].mean()
                row["buildings_with_both_reached"]=int(bg.k_delta_mean.notna().sum())
                row["buildings_priority_earlier"]=int(bg.k_delta_mean.lt(0).sum())
                row["source_time_at_hit_pct_change_image_equal"]=100*np.expm1(g.source_time_at_hit_logratio_mean.mean())
                summary.append(row)
                for building,h in g.groupby("building"):
                    br=dict(meta,building=building,images=h.image.nunique())
                    br.update({f:h[f].mean() for f in fields});building_rows.append(br)
    return paths,images,pd.DataFrame(summary),pd.DataFrame(building_rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--orders", required=True)
    ap.add_argument("--annotations")
    ap.add_argument("--out", required=True)
    args=ap.parse_args()
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    needed=set(METRICS+FLAGS+META+["path_id","base_path_id","policy","replicate","k","team_key",
        "sample_kind","target_class","method","tier","source_time_known_n","target_time_known_n"])
    d=pd.read_csv(args.results,low_memory=False,usecols=lambda c:c in needed)
    orders=pd.read_csv(args.orders,keep_default_na=False)
    observed=set(d.path_id)
    orders=orders[orders.path_id.isin(observed)]
    paired,metrics,flags=paired_events(d,orders,args.annotations)
    save_csv(paired,out/"POLICY_PAIRED_PREFIX_EVENTS.csv.gz")
    print("paired events saved",len(paired),flush=True)
    perk,metric_table=per_image_k(paired,metrics,flags)
    save_csv(perk,out/"POLICY_PER_IMAGE_K.csv.gz")
    save_csv(metric_table,out/"POLICY_PER_IMAGE_K_METRICS.csv.gz")
    fixed_membership = perk.groupby(["condition","layer","difficulty","policy","k"],dropna=False).agg(
        images=("image","nunique"),priority_fixed_member_set_images=("priority_fixed_membership","sum"),
        natural_fixed_member_set_images=("natural_fixed_membership","sum"),
        priority_Q_variance_estimable_images=("priority_variance_estimable","sum"),
        natural_Q_variance_estimable_images=("natural_variance_estimable","sum"),
        exact_target_class_block_images=("priority_exact_target_block","sum"),
        full_pool_images=("at_full_pool","sum")).reset_index()
    save_csv(fixed_membership,out/"POLICY_FIXED_MEMBERSHIP_SUMMARY.csv")
    print("image k and metrics saved",len(perk),len(metric_table),flush=True)
    focal=focal_rows(perk)
    save_csv(focal,out/"POLICY_FOCAL_PER_IMAGE.csv")
    summary,building=aggregate_focal(focal)
    save_csv(summary,out/"POLICY_FOCAL_SUMMARY.csv")
    save_csv(building,out/"POLICY_FOCAL_PER_BUILDING.csv.gz")
    attainment_paths,attainment_images,attainment_summary,attainment_buildings=policy_attainments(paired)
    save_csv(attainment_paths,out/"POLICY_ATTAINMENT_PATHS.csv.gz")
    save_csv(attainment_images,out/"POLICY_ATTAINMENT_PER_IMAGE.csv")
    save_csv(attainment_summary,out/"POLICY_ATTAINMENT_SUMMARY.csv")
    save_csv(attainment_buildings,out/"POLICY_ATTAINMENT_PER_BUILDING.csv.gz")
    receipt=dict(paired_prefixes=len(paired),pools=paired.pool_id.nunique(),images=paired.image.nunique(),
                 per_image_k_rows=len(perk),metric_rows=len(metric_table),focal_image_rows=len(focal),
                 focal_summary_rows=len(summary),attainment_paths=len(attainment_paths),metrics=metrics,full_pool_identity_checked=True,
                 natural_comparator="exact paired base_path_id, same k and same full actual pool",
                 quality="paired defined values; independent denominators per component",
                 failure="all attempted paired prefixes; n2 policy-deferred separately retained",
                 time="fully supported historical source record sums; log ratios then image/building equal aggregation",
                 interpretation="internal v2 historical-label evaluation; no target outcome role selection")
    write_bytes(out/"POLICY_ANALYSIS_RECEIPT.json",json.dumps(receipt,ensure_ascii=False,indent=2).encode())
    print(json.dumps(receipt,ensure_ascii=False),flush=True)


if __name__=="__main__":
    main()
