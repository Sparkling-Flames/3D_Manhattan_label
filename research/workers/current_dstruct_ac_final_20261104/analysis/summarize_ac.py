"""Image/building summaries of registered current-DSTRUCT direct AC contrasts.

Every physical unordered pair enters once per cohort/condition. Six directed
views are algebraic reversals of those pairs, explicitly identified as such.
No new teams, fusion, scores, class labels, alliances or ABC estimands.
"""
from __future__ import annotations

import json
import warnings

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from ac_common import *

warnings.filterwarnings("ignore", message="The behavior of DataFrame concatenation")

BASE = ["analysis_cohort", "version", "scope", "condition", "n", "m", "class_pair"]
MAIN_METRICS = ["dQ", "abs_dQ", "Q_A", "Q_C", "midpoint_Q"]
COMPONENTS = list(METRIC_INFO)
COMP_DELTAS = ["delta_" + x for x in COMPONENTS]
_SUMMARY_CACHE = {}


def cohorts(d: pd.DataFrame) -> pd.DataFrame:
    combined = d.loc[d.analysis_cohort.isin([LEGACY, GAP]) & d.scope.eq("primary") & d.n.isin([14, 20]) & d.m.eq(7)].copy()
    combined["component_cohort"] = combined.analysis_cohort
    combined["analysis_cohort"] = COMBINED
    if combined.duplicated(["version", "canonical_physical_pair_id"]).any():
        raise ValueError("Supplement duplicates an existing physical pair")
    d = d.copy()
    d["component_cohort"] = d.analysis_cohort
    return pd.concat([d, combined], ignore_index=True)


def q_supports(g: pd.DataFrame):
    if g.version.iloc[0] == "automatic":
        yield "original_common", g.loc[g.original_common_Q & g.common_Q]
    else:
        yield "original_common", g.loc[g.original_common_Q & g.common_Q]
        yield "new_common_after_approved_order", g.loc[g.new_common_Q & g.common_Q]
        yield "expanded_common", g.loc[g.common_Q]


def directed_summary(image: pd.DataFrame, key, metric: str, sign: int = 1, ci: bool = True) -> dict:
    cache_key = (digest(key), metric, ci)
    if cache_key not in _SUMMARY_CACHE:
        if len(_SUMMARY_CACHE) > 8192:
            _SUMMARY_CACHE.clear()
        _SUMMARY_CACHE[cache_key] = summary(image[["image", "building", metric]], metric, key, with_ci=ci)
    ans = _SUMMARY_CACHE[cache_key].copy()
    signed = metric == "dQ" or metric.startswith("delta_") or metric.startswith("dT_") or metric.startswith("log_T_ratio")
    if sign == -1 and signed:
        original = ans.copy()
        for name in ["image_equal_mean", "image_median", "building_equal_mean"]:
            if name in original:
                ans[name] = -original[name]
        for a, b in [("image_p10", "image_p90"), ("image_min", "image_max"),
                     ("cluster_bootstrap_low", "cluster_bootstrap_high"),
                     ("building_equal_bootstrap_low", "building_equal_bootstrap_high"),
                     ("leave_one_building_out_min", "leave_one_building_out_max")]:
            if a in original and b in original:
                ans[a], ans[b] = -original[b], -original[a]
        for a, b in [("positive_images", "negative_images")] + [("up_gt_" + str(v).replace(".", "p") + "_images", "down_lt_minus_" + str(v).replace(".", "p") + "_images") for v in [.5, 1., 2.]]:
            if a in original and b in original:
                ans[a], ans[b] = original[b], original[a]
    if metric != "dQ":
        ans = {k: v for k, v in ans.items() if not k.startswith(("up_gt_", "down_lt_minus_", "within_pm_"))}
    return ans


def direction(pair: str, sign: int) -> str:
    a, c = pair.split("_")
    return a + "_to_" + c if sign == 1 else c + "_to_" + a


def basic_support(g: pd.DataFrame, q: pd.DataFrame, sign: int = 1) -> dict:
    a, c = ("A", "C") if sign == 1 else ("C", "A")
    return dict(registered_physical_pairs=len(g), registered_method_event_aliases=int(g.method_event_aliases.sum()),
                registered_images=g.image.nunique(), registered_buildings=g.building.nunique(), registered_pools=g.pool_id.nunique(),
                registered_unique_teams=len(set(g.A_team_key) | set(g.C_team_key)),
                common_Q_physical_pairs=len(q), common_Q_unique_teams=len(set(q.A_team_key) | set(q.C_team_key)),
                A_Q_missing_physical_uses=int(g[a + "_B8L2"].isna().sum()), C_Q_missing_physical_uses=int(g[c + "_B8L2"].isna().sum()),
                A_only_Q_pairs=int((g[a + "_B8L2"].notna() & g[c + "_B8L2"].isna()).sum()),
                C_only_Q_pairs=int((g[a + "_B8L2"].isna() & g[c + "_B8L2"].notna()).sum()),
                neither_Q_pairs=int((g[a + "_B8L2"].isna() & g[c + "_B8L2"].isna()).sum()),
                A_no_connection_uses=int(g[a + "_score_status"].eq("no_connection").sum()),
                C_no_connection_uses=int(g[c + "_score_status"].eq("no_connection").sum()),
                A_invalid_geometry_uses=int(g[a + "_score_status"].isin(["invalid_floor", "invalid_full_geometry"]).sum()),
                C_invalid_geometry_uses=int(g[c + "_score_status"].isin(["invalid_floor", "invalid_full_geometry"]).sum()))


def main_quality(d: pd.DataFrame):
    rows, images, states, endpoints = [], [], [], []
    for key, g in d.groupby(BASE, dropna=False, sort=True, observed=True):
        meta = dict(zip(BASE, key))
        for support, q in q_supports(g):
            im = make_image_table(q, [], MAIN_METRICS) if len(q) else pd.DataFrame(columns=["image", "building"] + MAIN_METRICS)
            if len(im):
                image_out = im.copy()
                for k, v in meta.items():
                    image_out[k] = v
                image_out["support"] = support
                images.append(image_out)
            for sign in [1, -1]:
                out = dict(meta, support=support, direction=direction(meta["class_pair"], sign),
                           orientation_sign_view=sign, reverse_is_independent_replication=False,
                           **basic_support(g, q, sign))
                for metric in MAIN_METRICS:
                    source = "Q_C" if metric == "Q_A" and sign == -1 else "Q_A" if metric == "Q_C" and sign == -1 else metric
                    s = directed_summary(im, [key, support], source, sign=sign, ci=(metric == "dQ"))
                    prefix = "" if metric == "dQ" else metric + "_"
                    out.update({prefix + k: v for k, v in s.items()})
                rows.append(out)
        # Status transitions retain all physical pairs, including those with no Q.
        for sign in [1, -1]:
            a, c = ("A", "C") if sign == 1 else ("C", "A")
            z = g.copy()
            z["state_pair"] = z[a + "_score_status"].fillna("unrecorded") + " -> " + z[c + "_score_status"].fillna("unrecorded")
            for status in sorted(z.state_pair.unique()):
                z["status_indicator"] = z.state_pair.eq(status).astype(float)
                im = make_image_table(z, [], ["status_indicator"])
                states.append(dict(meta, direction=direction(meta["class_pair"], sign), state_transition=status,
                                   physical_pair_count=int(z.state_pair.eq(status).sum()),
                                   total_physical_pairs=len(z), images_with_transition=z.loc[z.state_pair.eq(status), "image"].nunique(),
                                   image_equal_transition_fraction=float(im.status_indicator.mean()),
                                   building_equal_transition_fraction=float(im.groupby("building").status_indicator.mean().mean())))
        # Unique endpoint counts are independent of repeated method events/pairs.
        for arm in ["A", "C"]:
            x = g.drop_duplicates(arm + "_team_key")
            for status, ss in x.groupby(arm + "_score_status", dropna=False):
                endpoints.append(dict(meta, canonical_arm=arm, score_status=status, unique_endpoints=len(ss),
                                      images=ss.image.nunique(), buildings=ss.building.nunique()))
    out = pd.DataFrame(rows)
    csv(HERE / "SIX_DIRECTION_Q_BY_BUDGET.csv", out)
    csv(HERE / "MAIN_IMAGE_EFFECTS.csv.gz", pd.concat(images, ignore_index=True))
    csv(HERE / "OUTPUT_STATE_TRANSITIONS.csv", pd.DataFrame(states))
    csv(HERE / "UNIQUE_ENDPOINT_STATUS_BY_BUDGET.csv", pd.DataFrame(endpoints))
    return out


def component_summaries(d: pd.DataFrame):
    rows, image_parts, native_support = [], [], []
    for key, g in d.groupby(BASE, sort=True, dropna=False, observed=True):
        meta = dict(zip(BASE, key))
        for support, q in q_supports(g):
            if not len(q):
                continue
            metrics = COMP_DELTAS + GEOMETRY + ["A_matched_ref_pair_fraction", "C_matched_ref_pair_fraction"]
            im = make_image_table(q, [], metrics)
            rec = im.copy()
            for k, v in meta.items():
                rec[k] = v
            rec["support"] = support
            image_parts.append(rec)
            core = (meta["n"], meta["m"]) in CORE_BUDGETS
            for metric in metrics:
                finite = np.isfinite(pd.to_numeric(q[metric], errors="coerce"))
                for sign in [1, -1]:
                    ans = directed_summary(im, [key, support], metric, sign, ci=core and metric.startswith("delta_"))
                    if not ans.get("images", 0):
                        continue
                    source_name = metric.removeprefix("delta_")
                    info = METRIC_INFO.get(source_name, (metric, "see_metric_dictionary", "descriptive_distance"))
                    rows.append(dict(meta, support=support, direction=direction(meta["class_pair"], sign), metric=metric,
                                     metric_name=info[0], unit=info[1], improvement_direction=info[2],
                                     metric_physical_pairs=int(finite.sum()), Q_common_physical_pairs=len(q),
                                     component_denominator="Q_common_and_component_available", **ans))
        # Native component availability is useful for incomplete-output states;
        # these counts are not substituted for the formal common-Q estimand.
        for metric in COMPONENTS:
            count = (g["A_" + metric].notna() & g["C_" + metric].notna()).sum()
            native_support.append(dict(meta, metric=metric, native_component_pair_count=int(count),
                                       all_registered_physical_pairs=len(g), Q_common_physical_pairs=int(g.common_Q.sum())))
    csv(HERE / "COMPONENT_SUMMARIES.csv.gz", pd.DataFrame(rows))
    csv(HERE / "COMPONENT_IMAGE_EFFECTS.csv.gz", pd.concat(image_parts, ignore_index=True))
    csv(HERE / "COMPONENT_NATIVE_SUPPORT.csv", pd.DataFrame(native_support))


def current_q_support(d: pd.DataFrame):
    """Automatic and assisted-expanded side by side without duplicate common rows."""
    return d.loc[d.common_Q].copy()


def stratified_patterns(d: pd.DataFrame):
    q = current_q_support(d)
    strata = ["official_difficulty", "structural_condition", "room_type", "difficulty_x_room_type", "D_category", "design_status"]
    rows, components, image_rows = [], [], []
    # Full budget/direction tables are above. Detailed interpretation keeps exact
    # n/m; headline budgets were fixed before inspecting the complete outcomes.
    q = q.loc[[tuple(x) in CORE_BUDGETS for x in q[["n", "m"]].to_numpy()]].copy()
    for axis in strata:
        group = BASE + [axis]
        for key, g in q.groupby(group, dropna=False, observed=True, sort=True):
            meta = dict(zip(group, key))
            value = meta.pop(axis)
            metrics = MAIN_METRICS + COMP_DELTAS + GEOMETRY
            im = make_image_table(g, [], metrics)
            z = im.copy()
            for k, v in meta.items():
                z[k] = v
            z["stratum_type"], z["stratum"] = axis, value
            image_rows.append(z)
            for sign in [1, -1]:
                s = directed_summary(im, [key, axis], "dQ", sign)
                a = directed_summary(im, [key, axis], "abs_dQ", sign, ci=False)
                rows.append(dict(meta, stratum_type=axis, stratum=value, direction=direction(meta["class_pair"], sign),
                                 physical_pairs=len(g), **s, mean_absolute_pair_effect_image_equal=a.get("image_equal_mean", np.nan)))
                for metric in COMP_DELTAS + GEOMETRY:
                    s = directed_summary(im, [key, axis], metric, sign, ci=False)
                    if s.get("images", 0):
                        components.append(dict(meta, stratum_type=axis, stratum=value, direction=direction(meta["class_pair"], sign),
                                               metric=metric, physical_pairs=int(g[metric].notna().sum()), **s))
    csv(HERE / "CONDITION_STRATIFIED_Q.csv", pd.DataFrame(rows))
    csv(HERE / "CONDITION_STRATIFIED_COMPONENTS.csv.gz", pd.DataFrame(components))
    csv(HERE / "CONDITION_IMAGE_EFFECTS.csv.gz", pd.concat(image_rows, ignore_index=True))


def high_score_patterns(d: pd.DataFrame):
    q = current_q_support(d)
    # This is not a threshold or class-effect model. Both endpoints determine M;
    # the algebraic score bound is reported explicitly alongside associations.
    q["both_ge90_stratum"] = np.where(q.both_Q_ge90, "both_endpoints_ge90", "at_least_one_below90")
    rows, correl, concentration = [], [], []
    for axis in ["symmetric_Q_band", "both_ge90_stratum"]:
        for key, g in q.groupby(BASE + [axis], observed=True, sort=True, dropna=False):
            meta = dict(zip(BASE + [axis], key))
            value = meta.pop(axis)
            im = make_image_table(g, [], ["dQ", "abs_dQ", "midpoint_Q", "ceiling_abs_bound", "abs_difference_fraction_of_bound"] + GEOMETRY)
            for sign in [1, -1]:
                s = directed_summary(im, [key, axis], "abs_dQ", sign, ci=False)
                out = dict(meta, stratum_type=axis, stratum=value, direction=direction(meta["class_pair"], sign), physical_pairs=len(g), **s,
                           midpoint_Q_image_mean=float(im.midpoint_Q.mean()), ceiling_bound_image_mean=float(im.ceiling_abs_bound.mean()),
                           normalized_absolute_difference_image_mean=float(im.abs_difference_fraction_of_bound.mean()))
                rows.append(out)
    for key, g in q.groupby(BASE + ["image", "building"], observed=True, sort=True, dropna=False):
        meta = dict(zip(BASE + ["image", "building"], key))
        if len(g) >= 5 and g.midpoint_Q.nunique() > 1 and g.abs_dQ.nunique() > 1:
            rho = float(spearmanr(g.midpoint_Q, g.abs_dQ).statistic)
            correl.append(dict(meta, physical_pairs=len(g), rho_midpoint_vs_abs_dQ=rho,
                               midpoint_range=float(g.midpoint_Q.max() - g.midpoint_Q.min())))
        levels = np.concatenate([g.Q_A.to_numpy(float), g.Q_C.to_numpy(float)])
        concentration.append(dict(meta, physical_pairs=len(g), mean_abs_dQ=float(g.abs_dQ.mean()),
                                  midpoint_Q_mean=float(g.midpoint_Q.mean()), both_Q_ge90_fraction=float(g.both_Q_ge90.mean()),
                                  pooled_endpoints_Q_p05=float(np.quantile(levels, .05)), pooled_endpoints_Q_p95=float(np.quantile(levels, .95)),
                                  pooled_endpoints_Q_p95_minus_p05=float(np.quantile(levels, .95) - np.quantile(levels, .05))))
    cor = pd.DataFrame(correl)
    agg = []
    for key, g in cor.groupby(BASE, observed=True, sort=True, dropna=False):
        s = summary(g.rename(columns={"rho_midpoint_vs_abs_dQ": "rho"}), "rho", key, with_ci=False)
        agg.append(dict(zip(BASE, key), metric="within_image_n_m_pair_Spearman_midpoint_vs_abs_difference", **s))
    csv(HERE / "HIGH_SCORE_BAND_EFFECTS.csv", pd.DataFrame(rows))
    csv(HERE / "WITHIN_IMAGE_CEILING_ASSOCIATIONS.csv.gz", cor)
    csv(HERE / "WITHIN_IMAGE_CEILING_ASSOCIATION_SUMMARY.csv", pd.DataFrame(agg))
    csv(HERE / "IMAGE_SCORE_CONCENTRATION.csv.gz", pd.DataFrame(concentration))


def same_nodes(d: pd.DataFrame):
    q = current_q_support(d)
    rows = []
    metrics = ["dQ", "abs_dQ"] + COMP_DELTAS + GEOMETRY + ["A_matched_ref_pair_fraction", "C_matched_ref_pair_fraction"]
    for key, g in q.groupby(BASE + ["node_count_group"], observed=True, sort=True, dropna=False):
        meta = dict(zip(BASE + ["node_count_group"], key))
        im = make_image_table(g, [], metrics)
        for metric in metrics:
            s = directed_summary(im, key, metric, 1, ci=False)
            if s.get("images", 0):
                rows.append(dict(meta, metric=metric, physical_pairs=len(g), **s))
    csv(HERE / "SAME_NODE_COUNT_COMPONENTS.csv.gz", pd.DataFrame(rows))
    proportions = []
    for key, g in q.groupby(BASE, observed=True, sort=True, dropna=False):
        z = g.copy()
        z["same_node_indicator"] = z.same_node_count.astype(float)
        z["large_Q_jump"] = z.abs_dQ.gt(10).astype(float)
        z["large_Q_jump_same_nodes"] = (z.abs_dQ.gt(10) & z.same_node_count).astype(float)
        im = make_image_table(z, [], ["same_node_indicator", "large_Q_jump", "large_Q_jump_same_nodes"])
        proportions.append(dict(zip(BASE, key), Q_common_pairs=len(g), same_node_pairs=int(g.same_node_count.sum()),
                                large_Q_jump_pairs=int(g.abs_dQ.gt(10).sum()), large_Q_jump_same_nodes_pairs=int((g.abs_dQ.gt(10) & g.same_node_count).sum()),
                                images=im.image.nunique(), buildings=im.building.nunique(),
                                image_equal_same_node_fraction=float(im.same_node_indicator.mean()),
                                image_equal_large_Q_jump_fraction=float(im.large_Q_jump.mean()),
                                image_equal_large_Q_jump_same_nodes_fraction=float(im.large_Q_jump_same_nodes.mean())))
    csv(HERE / "SAME_NODE_COUNT_SUPPORT.csv", pd.DataFrame(proportions))


def labor_summaries(d: pd.DataFrame):
    rows, images, support_rows = [], [], []
    for key, g in d.groupby(BASE, observed=True, sort=True, dropna=False):
        meta = dict(zip(BASE, key))
        for support, flag, seconds, logratio in [
            ("whole_team_single_source", "time_whole_single_source", "dT_whole", "log_T_ratio_whole"),
            ("replacement_blocks_single_source", "time_blocks_single_source", "dT_blocks", "log_T_ratio_blocks"),
        ]:
            t = g.loc[g[flag]].copy()
            for regime, z in [("labor_available", t), ("same_pairs_Q_and_labor", t.loc[t.common_Q])]:
                im = make_image_table(z, [], [seconds, logratio, "dQ", "abs_dQ"]) if len(z) else pd.DataFrame(columns=["image", "building", seconds, logratio, "dQ", "abs_dQ"])
                if regime == "labor_available":
                    # T-only support includes no-Q pairs; its T mean must never
                    # be paired with a Q mean from a different event subset.
                    im["dQ"] = np.nan
                    im["abs_dQ"] = np.nan
                if len(im):
                    saved = im.copy()
                    for k, v in meta.items():
                        saved[k] = v
                    saved["labor_support"], saved["Q_labor_support"] = support, regime
                    images.append(saved)
                for sign in [1, -1]:
                    s = directed_summary(im, [key, support, regime], seconds, sign, ci=(meta["n"], meta["m"]) in CORE_BUDGETS)
                    out = dict(meta, direction=direction(meta["class_pair"], sign), labor_support=support, Q_labor_support=regime,
                               registered_physical_pairs=len(g), eligible_physical_pairs=len(z),
                               complete_D_labor_pairs=int(z.D_labor_complete.sum()) if len(z) else 0,
                               source_record_time_not_full_workflow=True, **s)
                    out["Q_labor_same_physical_pairs"] = regime == "same_pairs_Q_and_labor"
                    if len(im):
                        out["geometric_mean_labor_ratio"] = float(np.exp(sign * im[logratio].mean()))
                    if len(im) and regime == "same_pairs_Q_and_labor":
                        qans = directed_summary(im, [key, support, regime], "dQ", sign, ci=False)
                        out.update({"Q_" + k: v for k, v in qans.items()})
                        valid = im.dQ.notna() & im[seconds].notna()
                        dq, dt = sign * im.loc[valid, "dQ"], sign * im.loc[valid, seconds]
                        out.update(joint_images=int(valid.sum()), Q_up_T_not_up_images=int(((dq > 0) & (dt <= 0)).sum()),
                                   Q_up_T_up_images=int(((dq > 0) & (dt > 0)).sum()),
                                   Q_down_T_down_images=int(((dq < 0) & (dt < 0)).sum()), Q_down_T_not_down_images=int(((dq < 0) & (dt >= 0)).sum()))
                    rows.append(out)
            support_rows.append(dict(meta, labor_support=support, all_physical_pairs=len(g), eligible_labor_pairs=len(t),
                                     eligible_labor_images=t.image.nunique(), eligible_labor_buildings=t.building.nunique(),
                                     same_Q_labor_pairs=int(t.common_Q.sum()),
                                     labor_eligible_without_complete_D_pairs=int((~t.D_labor_complete).sum())))
    csv(HERE / "RECORDED_LABOR_AND_JOINT_Q.csv", pd.DataFrame(rows))
    csv(HERE / "RECORDED_LABOR_IMAGE_EFFECTS.csv.gz", pd.concat(images, ignore_index=True))
    csv(HERE / "RECORDED_LABOR_SUPPORT.csv", pd.DataFrame(support_rows))


def manual_decomposition(d: pd.DataFrame):
    a = d.loc[d.version.eq("automatic")].copy()
    h = d.loc[d.version.eq("manual_order_assisted")].copy()
    keys = [k for k in BASE if k != "version"]
    rows = []
    hgroups = dict(tuple(h.groupby(keys, observed=True, sort=True, dropna=False)))
    for key, g in a.groupby(keys, observed=True, sort=True, dropna=False):
        z = hgroups[key]
        expected = g.set_index("canonical_physical_pair_id")["dQ"]
        current = z.set_index("canonical_physical_pair_id")["dQ"]
        finite = expected.notna()
        max_change = float(np.max(np.abs(expected[finite] - current[finite]))) if finite.any() else 0.
        parts = [("automatic_original_common", g.loc[g.common_Q]),
                 ("assisted_original_common", z.loc[z.original_common_Q & z.common_Q]),
                 ("assisted_new_common", z.loc[z.new_common_Q & z.common_Q]),
                 ("assisted_expanded_common", z.loc[z.common_Q])]
        old_images = set(g.loc[g.common_Q, "image"])
        for label, p in parts:
            im = make_image_table(p, [], ["dQ", "abs_dQ"]) if len(p) else pd.DataFrame(columns=["image", "building", "dQ", "abs_dQ"])
            for sign in [1, -1]:
                out = dict(zip(keys, key), direction=direction(key[-1], sign), support_component=label,
                           physical_pairs=len(p), wholly_new_images=len(set(p.image) - old_images),
                           original_common_max_abs_Q_delta_change=max_change,
                           **directed_summary(im, [key, label], "dQ", sign, ci=False))
                rows.append(out)
    csv(HERE / "MANUAL_ORDER_SUPPORT_DECOMPOSITION.csv", pd.DataFrame(rows))


def design_link_sensitivity(d: pd.DataFrame):
    links = read_csv(OUT / "registry/LEGAL_CURRENT_AC_DESIGN_LINKS.csv.gz")
    # A physical pair may have several historical design links. Each design
    # condition is analysed separately, and duplicate links never add weight.
    links = links.loc[(pd.to_numeric(links.current_n).isin([14, 20])) & pd.to_numeric(links.current_m).eq(7)].copy()
    gcols = ["design_family", "background_profile", "background_rule_current", "original_design_current_valid"]
    pairs = d.loc[d.analysis_cohort.eq(LEGACY) & d.n.isin([14, 20]) & d.m.eq(7)]
    rows = []
    for key, l in links.groupby(gcols, observed=True, sort=True, dropna=False):
        ids = set(l.canonical_physical_pair_id)
        matched = pairs.loc[pairs.canonical_physical_pair_id.isin(ids) & pairs.common_Q]
        for condition, z in matched.groupby(BASE, observed=True, sort=True, dropna=False):
            im = make_image_table(z, [], ["dQ", "abs_dQ"])
            rows.append(dict(zip(gcols, key), **dict(zip(BASE, condition)), historical_links=len(l),
                             physical_pairs=len(z), **summary(im, "dQ", [key, condition], with_ci=False),
                             mean_absolute_pair_effect=float(im.abs_dQ.mean())))
    csv(HERE / "CORE_LEGACY_DESIGN_LINK_SENSITIVITY.csv", pd.DataFrame(rows))


def capacity_completion(summary_frame: pd.DataFrame):
    core = summary_frame.loc[summary_frame.scope.eq("primary") & summary_frame.n.isin([14, 20]) & summary_frame.m.eq(7)].copy()
    csv(HERE / "CORE_SIX_DIRECTION_Q.csv", core)
    current = core.loc[(core.version.eq("manual_order_assisted") & core.support.eq("expanded_common")) |
                       (core.version.eq("automatic") & core.support.eq("original_common"))]
    fields = ["analysis_cohort", "version", "support", "n", "m", "direction", "registered_physical_pairs", "registered_images", "registered_buildings",
              "registered_unique_teams", "common_Q_physical_pairs", "common_Q_unique_teams", "images", "buildings", "image_equal_mean", "cluster_bootstrap_low", "cluster_bootstrap_high",
              "building_equal_mean", "positive_images", "negative_images", "up_gt_1p0_images", "down_lt_minus_1p0_images", "within_pm_1p0_images",
              "abs_dQ_image_equal_mean", "support_tier", "reverse_is_independent_replication"]
    csv(HERE / "CORE_READABLE_RESULTS.csv", current.reindex(columns=fields))


def gap_weighting_sensitivity(d: pd.DataFrame):
    g = d.loc[d.analysis_cohort.isin([GAP, COMBINED]) & d.common_Q]
    rows, block_support, image_rows = [], [], []
    for key, z in g.groupby(BASE, observed=True, sort=True, dropna=False):
        for scheme in ["frozen_XZ_block_equal", "remaining_physical_pair_equal_sensitivity"]:
            im = make_image_table(z, [], ["dQ", "abs_dQ"], gap_pair_equal=scheme != "frozen_XZ_block_equal")
            image_out = im.copy()
            for k, v in dict(zip(BASE, key)).items():
                image_out[k] = v
            image_out["weighting"] = scheme
            image_rows.append(image_out)
            for sign in [1, -1]:
                rows.append(dict(zip(BASE, key), weighting=scheme, direction=direction(key[-1], sign),
                                 physical_pairs=len(z), **directed_summary(im, [key, scheme], "dQ", sign),
                                 mean_absolute_pair_effect=float(im.abs_dQ.mean())))
    gap = d.loc[d.analysis_cohort.eq(GAP)]
    for key, z in gap.groupby(BASE + ["pool_id", "image", "building", "block_id"], observed=True, sort=True, dropna=False):
        block_support.append(dict(zip(BASE + ["pool_id", "image", "building", "block_id"], key), registered_backgrounds=z.background_id.nunique(),
                                  Q_common_backgrounds=z.loc[z.common_Q, "background_id"].nunique(),
                                  Q_common_mean=float(z.loc[z.common_Q, "dQ"].mean()),
                                  labor_whole_backgrounds=int(z.time_whole_single_source.sum()), labor_block_backgrounds=int(z.time_blocks_single_source.sum())))
    csv(HERE / "GAP_WEIGHTING_SENSITIVITY.csv", pd.DataFrame(rows))
    csv(HERE / "GAP_WEIGHTING_IMAGE_EFFECTS.csv.gz", pd.concat(image_rows, ignore_index=True))
    csv(HERE / "GAP_BLOCK_SUPPORT.csv.gz", pd.DataFrame(block_support))


def main():
    a = read_csv(HERE / "PHYSICAL_PAIRS_AUTOMATIC.csv.gz")
    h = read_csv(HERE / "PHYSICAL_PAIRS_ASSISTED.csv.gz")
    d = cohorts(pd.concat([a, h], ignore_index=True))
    for col in ["common_Q", "original_common_Q", "new_common_Q", "same_node_count", "both_Q_ge90", "time_whole_single_source", "time_blocks_single_source", "D_labor_complete"]:
        d[col] = truth(d[col])
    print("main_quality", flush=True)
    main_q = main_quality(d)
    capacity_completion(main_q)
    print("components", flush=True)
    component_summaries(d)
    print("stratified_patterns", flush=True)
    stratified_patterns(d)
    print("high_score_patterns", flush=True)
    high_score_patterns(d)
    print("same_node_count", flush=True)
    same_nodes(d)
    print("labor", flush=True)
    labor_summaries(d)
    print("manual_support", flush=True)
    manual_decomposition(d)
    print("design_link_sensitivity", flush=True)
    design_link_sensitivity(d)
    print("gap_weighting_sensitivity", flush=True)
    gap_weighting_sensitivity(d)
    from harmonize_intervals import harmonize_all
    harmonize_all()
    # Exact reversal is a display identity, not two independent datasets.
    f = main_q.loc[main_q.orientation_sign_view.eq(1)].set_index(BASE + ["support"])
    r = main_q.loc[main_q.orientation_sign_view.eq(-1)].set_index(BASE + ["support"])
    good = f.image_equal_mean.notna() & r.image_equal_mean.notna()
    residual = float(np.max(np.abs(f.loc[good, "image_equal_mean"] + r.loc[good, "image_equal_mean"])))
    ci_residual = float(np.nanmax(np.abs(f.loc[good, "cluster_bootstrap_low"] + r.loc[good, "cluster_bootstrap_high"])))
    if residual > 1e-10 or ci_residual > 1e-8:
        raise ValueError("Reversal display check failed")
    checks = dict(status="passed", summary_rows=len(main_q), image_building_weighting="legacy physical_pair_then_target_then_image; gap D_then_XZ_block_then_target_then_image; building_cluster_uncertainty",
                  reversed_mean_residual=residual, reversed_interval_residual=ci_residual,
                  resampling_clusters="buildings", bootstrap_draws=BOOTSTRAP, bootstrap_seed=SEED,
                  no_missing_Q_or_time_imputation=True, new_teams_in_statistics_module=0, new_scores=0, new_fusions=0)
    write_json(HERE / "STATISTICAL_CHECKS.json", checks)
    print(json.dumps(checks), flush=True)


if __name__ == "__main__":
    main()
