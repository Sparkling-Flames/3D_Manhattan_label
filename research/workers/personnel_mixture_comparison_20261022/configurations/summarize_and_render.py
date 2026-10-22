#!/usr/bin/env python3
"""Readable full-cell examples and difficulty summaries from the saved census.

Examples are explanatory selections from an explored v2 inventory, not a new
test set. Each chosen panel is displayed in full, including failed/singleton
cells. This script does not evaluate any new fusion endpoint.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/hohonet_mixture_matplotlib")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from build_configuration_distributions import HERE, META, SOURCE_MAIN, save, js

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False, "axes.spines.right": False, "savefig.dpi": 170})

ILLUSTRATIONS = [
    ("manual_structure", "manual", "V3_BEHAVIOR", "7y3sRwLe3Va-21", 20, 2, "完整六格说明结构配比、实际转折输出及类内长尾；探索解释例，不代表全库平均。"),
    ("manual_joint", "manual", "V3_JOINT_QT", "7y3sRwLe3Va-21", 20, 2, "与结构例相同端点支持，显示联合角色可同时区分质量、时间和同格成员波动。"),
    ("semi_structure", "semi", "V3_BEHAVIOR", "7y3sRwLe3Va-13", 20, 1, "同图完整十二格，转折数固定而Q分布改变；与n33的嵌套背景路径可一一关联。"),
    ("semi_joint", "semi", "V3_JOINT_QT", "B6ByNegPMKs-22", 16, 2, "完整二十四格，展示记录时间与质量低尾取舍；具体成员集中度由候选容量表保留。"),
    ("manual_small_separation", "manual", "V3_BEHAVIOR", "pa4otMbVnkk-18", 20, 2, "困难图中的较小配比Q均值差，同时保留少量结构变化；避免只选明显分离例。"),
    ("semi_null", "semi", "V3_BEHAVIOR", "X7HyMhZNoso-05", 20, 1, "简单图完整八格几乎无Q差异；作为无明显变化例。"),
    ("semi_failure", "semi", "V3_BEHAVIOR", "Z6MFQCViBuw-10", 20, 1, "完整九格包括失败；可评分Q接近不能代替对连接风险的评价。"),
]


def vector_sort(s):
    x = json.loads(s)
    return tuple(x[k] for k in sorted(x))


def overview():
    return pd.concat([pd.read_csv(HERE / f"CONFIGURATION_OVERVIEW_{c}.csv.gz") for c in ("manual", "semi")], ignore_index=True)


def summarize(x):
    """Concrete spread quantities, not a rerun of old variance decomposition."""
    rows = []
    metrics = ["B8L2", "D10", "IoU3D100", "fusion_turn_n", "fusion_short_turn_edges", "geometry_area_h2", "height_mean_h", "S_bottom_deg", "bottom_y_mean_px", "top_y_mean_px", "omission", "extension", "recorded_time_total_seconds"]
    for keys, g in x.groupby(["panel_id", "method", "tier"], sort=False):
        first = g.iloc[0]
        base = {k: first[k] for k in META}
        base.update(method=first.method, tier=first.tier, configurations=len(g), teams=int(g.teams.sum()),
                    failed_teams=int(g.failed_teams.sum()), singleton_cells=int(g.teams.eq(1).sum()))
        for metric in metrics:
            a = g[g[metric + "_valid_n"].gt(0)].copy()
            members = g[g[metric + "_valid_n"].ge(2)].copy()
            at_least_10 = g[g[metric + "_valid_n"].ge(10)].copy()
            r = dict(base, metric=metric, available_cells=len(a), available_teams=int(a[metric + "_valid_n"].sum()),
                     member_variation_cells=len(members), cell_mean_min=a[metric + "_mean"].min(), cell_mean_max=a[metric + "_mean"].max(),
                     cell_mean_span=a[metric + "_mean"].max() - a[metric + "_mean"].min() if len(a) >= 2 else np.nan,
                     median_within_cell_sd=members[metric + "_sd"].median(),
                     median_within_cell_iqr=members[metric + "_iqr"].median(),
                     median_within_cell_p05_p95_width=(members[metric + "_p95"] - members[metric + "_p05"]).median(),
                     cells_with_at_least_10_valid_members=len(at_least_10),
                     cell_mean_span_ge10=at_least_10[metric + "_mean"].max() - at_least_10[metric + "_mean"].min() if len(at_least_10) >= 2 else np.nan)
            rows.append(r)
    panels = pd.DataFrame(rows)
    save(panels, "PANEL_SPREAD_SUMMARY.csv.gz")
    value_fields = ["cell_mean_span", "median_within_cell_sd", "median_within_cell_iqr", "median_within_cell_p05_p95_width", "cell_mean_span_ge10"]
    keys = ["condition", "method", "tier", "n", "difficulty", "image", "building", "metric"]
    image = panels.groupby(keys, as_index=False)[value_fields].mean()
    image = image.merge(panels.groupby(keys, as_index=False).agg(panels=("panel_id", "nunique"), configurations=("configurations", "sum"), available_teams=("available_teams", "sum")), on=keys, validate="one_to_one")
    valid = panels.groupby(keys, as_index=False)[value_fields].count().rename(columns={f: f + "_valid_panels" for f in value_fields})
    image = image.merge(valid, on=keys, validate="one_to_one")
    save(image, "IMAGE_SPREAD_SUMMARY.csv.gz")
    bkeys = [k for k in keys if k != "image"]
    building = image.groupby(bkeys, as_index=False)[value_fields].mean()
    building = building.merge(image.groupby(bkeys, as_index=False).agg(images=("image", "nunique"), panels=("panels", "sum")), on=bkeys, validate="one_to_one")
    valid = image.groupby(bkeys, as_index=False)[value_fields].count().rename(columns={f: f + "_valid_images" for f in value_fields})
    building = building.merge(valid, on=bkeys, validate="one_to_one")
    save(building, "BUILDING_SPREAD_SUMMARY.csv.gz")
    dkeys = ["condition", "method", "tier", "n", "difficulty", "metric"]
    diff = building.groupby(dkeys, as_index=False)[value_fields].mean()
    diff = diff.merge(building.groupby(dkeys, as_index=False).agg(buildings=("building", "nunique"), images=("images", "sum"), panels=("panels", "sum")), on=dkeys, validate="one_to_one")
    for frame, suffix in [(building, "valid_buildings"), (image, "valid_images"), (panels, "valid_panels")]:
        valid = frame.groupby(dkeys, as_index=False)[value_fields].count().rename(columns={f: f + "_" + suffix for f in value_fields})
        diff = diff.merge(valid, on=dkeys, validate="one_to_one")
    save(diff, "DIFFICULTY_SPREAD_SUMMARY.csv")
    coverage = x.groupby(["condition", "method", "tier"], as_index=False).agg(
        configurations=("configuration_id", "size"), panels=("panel_id", "nunique"), images=("image", "nunique"), buildings=("building", "nunique"),
        team_panel_links=("teams", "sum"), scored_team_panel_links=("scorable_teams", "sum"), failed_team_panel_links=("failed_teams", "sum"),
        time_eligible_team_panel_links=("recorded_time_eligible_teams", "sum"), singleton_cells=("singleton_total_team", "sum"))
    save(coverage, "COMPLETE_COVERAGE_BY_METHOD.csv")
    return panels, coverage


def plot_all_cells(g, name, title):
    g = g.sort_values("class_counts", key=lambda z: z.map(vector_sort)).reset_index(drop=True)
    classes = sorted(json.loads(g.class_counts.iloc[0]))
    show_time = g.recorded_time_total_seconds_valid_n.fillna(0).gt(0).any()
    height = max(4.0, .30 * len(g) + 2.6)
    fig, axes = plt.subplots(1, 2 if show_time else 1, figsize=(15 if show_time else 11.5, height), squeeze=False,
                             gridspec_kw={"width_ratios": [1.4, 1]} if show_time else None)
    axes = axes[0]
    y = np.arange(len(g))
    labels = [" / ".join(str(json.loads(r.class_counts)[c]) for c in classes) + f"   N={r.teams}; fail={r.failed_teams}" for r in g.itertuples()]
    ax = axes[0]
    for yi, r in enumerate(g.itertuples()):
        if r.B8L2_valid_n:
            ax.plot([r.B8L2_p05, r.B8L2_p95], [yi, yi], color="#83b8d0", lw=2)
            ax.plot([r.B8L2_p25, r.B8L2_p75], [yi, yi], color="#24769b", lw=5, solid_capstyle="butt")
            ax.plot(r.B8L2_mean, yi, marker="o", ms=5, color="#143d59", markerfacecolor="white" if r.B8L2_valid_n == 1 else "#143d59")
        else:
            ax.text(0.02, yi, "no scorable team", va="center", transform=ax.get_yaxis_transform(), color="#b23c36")
    ax.set_yticks(y, labels)
    ax.invert_yaxis()
    ax.set_xlabel("B8L2 Q (mean dot; thick line p25-p75; thin line p05-p95)")
    ax.grid(axis="x", alpha=.2)
    ax.set_title("Complete team counts: " + " / ".join(classes), loc="left", fontsize=11)
    if show_time:
        ax = axes[1]
        for yi, r in enumerate(g.itertuples()):
            if pd.notna(r.recorded_time_total_seconds_valid_n) and r.recorded_time_total_seconds_valid_n > 0:
                ax.plot([r.recorded_time_total_seconds_p05 / 60, r.recorded_time_total_seconds_p95 / 60], [yi, yi], color="#88bcac", lw=2)
                ax.plot([r.recorded_time_total_seconds_p25 / 60, r.recorded_time_total_seconds_p75 / 60], [yi, yi], color="#318a70", lw=5, solid_capstyle="butt")
                ax.plot(r.recorded_time_total_seconds_mean / 60, yi, "o", ms=5, color="#165c48")
        ax.set_yticks(y, [])
        ax.invert_yaxis()
        ax.set_xlabel("Sum of recorded annotation times (min)")
        ax.grid(axis="x", alpha=.2)
        ax.set_title("Same-source complete inventory times", loc="left", fontsize=11)
    fig.suptitle(title, fontsize=14, x=.02, ha="left")
    fig.text(.02, .02, "All feasible labelled composition cells in this fixed D + choose(12,6) panel. Hollow Q dot: one scored team, variation unestimable.\nRecorded times are inherited records, not newly measured production duration. Different target folds may reuse class IDs with different meanings.", fontsize=9)
    fig.tight_layout(rect=(0, .055, 1, .95))
    fig.savefig(HERE / (name + ".png"))
    fig.savefig(HERE / (name + ".pdf"))
    plt.close(fig)


def examples(x):
    selections = []; rows = []
    panels = pd.read_csv(HERE / "PANELS_USED.csv")
    definitions = pd.read_csv(HERE / "FOLD_CLASS_DEFINITIONS.csv")
    all_definitions = []
    for name, condition, method, image, n, variable_panel, reason in ILLUSTRATIONS:
        g = x[x.condition.eq(condition) & x.method.eq(method) & x.tier.eq("fine") & x.image.eq(image) & x.n.eq(n) & x.variable_panel_no.eq(variable_panel)].copy()
        assert g.panel_id.nunique() == 1
        pid = g.panel_id.iloc[0]
        p = panels[panels.panel_id.eq(pid)].iloc[0]
        g.insert(0, "example_id", name)
        rows.append(g)
        save(g, f"EXAMPLE_{name}_ALL_CONFIGURATIONS.csv")
        d = definitions[definitions.method.eq(method) & definitions.condition.eq(condition) & definitions.heldout_building.eq(p.building) & definitions.tier.eq("fine")].copy()
        d.insert(0, "example_id", name)
        all_definitions.append(d)
        selections.append(dict(example_id=name, panel_id=pid, condition=condition, method=method, tier="fine", image=image, n=n,
                               variable_panel_no=variable_panel, configurations=len(g), labelled_team_sets=int(g.teams.sum()),
                               background_workers=p.background_workers, variable_workers=p.variable_workers,
                               background_class_counts=g.background_class_counts.iloc[0], class_mean_Q_min=g.B8L2_mean.min(),
                               class_mean_Q_max=g.B8L2_mean.max(), failed_team_sets=int(g.failed_teams.sum()),
                               selection_scope="exploratory_explanation_from_complete_coverage", reason_zh=reason))
        plot_all_cells(g, f"EXAMPLE_{name}_DISTRIBUTIONS", f"{condition.title()} | {method} | {image} | n={n}, member panel {variable_panel}")
    save(pd.DataFrame(selections), "EXAMPLE_SELECTION_AND_MEMBERS.csv")
    save(pd.concat(rows, ignore_index=True), "EXAMPLE_ALL_CONFIGURATION_ROWS.csv.gz")
    save(pd.concat(all_definitions, ignore_index=True), "EXAMPLE_FOLD_CLASS_DEFINITIONS.csv")


def background_path(x):
    """Every identical variable-member set is retained, not just a good pair."""
    panels = pd.read_csv(HERE / "PANELS_USED.csv")
    members = pd.read_csv(HERE / "PANEL_TEAMS.csv.gz")
    ep = pd.read_csv(HERE / "ENDPOINT_OUTCOMES_semi.csv.gz")
    p = panels[panels.image.eq("7y3sRwLe3Va-13") & panels.condition.eq("semi") & panels.variable_panel_no.eq(1)].set_index("n")
    assert p.loc[20, "variable_workers"] == p.loc[33, "variable_workers"]
    d20, d33 = set(p.loc[20, "background_workers"].split("|")), set(p.loc[33, "background_workers"].split("|"))
    assert d20 < d33
    metrics = ["B8L2", "D10", "nodes", "fusion_turn_n", "fusion_short_turn_edges", "height_mean_h", "geometry_area_h2", "bottom_y_mean_px", "top_y_mean_px", "omission", "extension", "S_bottom_deg", "minimum_support", "failure"]
    a = members[members.panel_id.eq(p.loc[20, "panel_id"])].merge(ep[["team_key"] + metrics], on="team_key", validate="one_to_one")
    b = members[members.panel_id.eq(p.loc[33, "panel_id"])].merge(ep[["team_key"] + metrics], on="team_key", validate="one_to_one")
    pairs = a.merge(b, on="selected_variable_workers", suffixes=("_n20", "_n33"), validate="one_to_one")
    assert len(pairs) == 924
    for metric in metrics:
        pairs["delta_" + metric] = pairs[metric + "_n33"] - pairs[metric + "_n20"]
    save(pairs, "CASE_7y13_BACKGROUND_ADDITION_PAIRS.csv.gz")
    cells = x[x.image.eq("7y3sRwLe3Va-13") & x.method.eq("V3_BEHAVIOR") & x.tier.eq("fine") & x.condition.eq("semi") & x.variable_panel_no.eq(1)]
    save(cells, "CASE_7y13_ALL_STRUCTURE_CONFIGURATIONS.csv")
    save(x[x.image.eq("X7HyMhZNoso-05") & x.condition.eq("semi") & x.method.eq("V3_BEHAVIOR") & x.tier.eq("fine") & x.n.eq(20)], "CASE_X7_05_ALL_STRUCTURE_CONFIGURATIONS.csv")
    report = dict(image="7y3sRwLe3Va-13", condition="semi", method="V3_BEHAVIOR", tier="fine", same_variable_12=p.loc[20, "variable_workers"],
                  same_selected_variable_6_sets=924, D_n20=p.loc[20, "background_workers"], D_n33=p.loc[33, "background_workers"],
                  added_background_13="|".join(sorted(d33 - d20)), minimum_support_n20=sorted(pairs.minimum_support_n20.unique().tolist()),
                  minimum_support_n33=sorted(pairs.minimum_support_n33.unique().tolist()),
                  matched_variable_sets_mean_Q_n33_minus_n20=pairs.delta_B8L2.mean(),
                  matched_variable_sets_positive_Q_n=int(pairs.delta_B8L2.gt(0).sum()), matched_variable_sets_negative_Q_n=int(pairs.delta_B8L2.lt(0).sum()),
                  description="同一12选6候选、同一924种变量成员集合。背景增加13人、n20→33、门槛10→17共同发生。不是纯人数效应，也未新增融合。")
    js("CASE_7y13_BACKGROUND_ADDITION.json", report)
    # Align rows by variable counts: the full team counts differ by the stated D.
    fig, axs = plt.subplots(1, 3, figsize=(15, 7), sharey=True)
    for ax, n in zip(axs, [12, 20, 33]):
        g = cells[cells.n.eq(n)].sort_values("selected_variable_counts", key=lambda s: s.map(vector_sort)).reset_index(drop=True)
        for yi, r in enumerate(g.itertuples()):
            ax.plot([r.B8L2_p05, r.B8L2_p95], [yi, yi], color="#83b8d0", lw=2)
            ax.plot([r.B8L2_p25, r.B8L2_p75], [yi, yi], color="#24769b", lw=5)
            ax.plot(r.B8L2_mean, yi, "o", color="#143d59", ms=5)
        ax.set_xlim(45, 100)
        ax.set_title(f"n={n}, fixed background={n - 6}\nD: " + g.background_class_counts.iloc[0], fontsize=9)
        ax.set_xlabel("B8L2 Q")
        ax.grid(axis="x", alpha=.2)
        ax.set_yticks(range(len(g)), [" / ".join(str(v) for v in json.loads(s).values()) for s in g.selected_variable_counts])
    axs[0].invert_yaxis()
    axs[0].set_ylabel("Selected variable 6 counts: S1.1 / S2.1 / S3.1 / S3.2")
    fig.suptitle("7y13 Semi: same 924 variable-member sets along an inherited background-addition path", fontsize=13)
    fig.text(.02, .02, "Full-team vectors, member sets, all component metrics and failures are in the companion CSV. Background members and vote thresholds change jointly with n.", fontsize=9)
    fig.tight_layout(rect=(0, .04, 1, .95))
    fig.savefig(HERE / "CASE_7y13_BACKGROUND_PATH.png")
    fig.savefig(HERE / "CASE_7y13_BACKGROUND_PATH.pdf")
    plt.close(fig)


def failure_status():
    rows = []
    for condition in ["manual", "semi"]:
        d = pd.read_csv(HERE / f"ENDPOINT_OUTCOMES_{condition}.csv.gz")
        for keys, g in d.groupby(["score_status", "geometry_status"], dropna=False):
            rows.append(dict(condition=condition, score_status=keys[0], geometry_status=keys[1], unique_endpoints=len(g),
                             incomplete_evaluable_endpoints=int(g.failure.sum()), scorable_endpoints=int(g.complete_evaluable.sum())))
    save(pd.DataFrame(rows), "ENDPOINT_STATUS_COUNTS.csv")


def fine_increment(x):
    """Every fine allocation inside each unchanged complete coarse vector."""
    def canonical(value):
        d = json.loads(value)
        return json.dumps({k: v for k, v in sorted(d.items()) if v}, separators=(",", ":"))
    coarse = x[x.tier.eq("coarse")].copy()
    fine = x[x.tier.eq("fine")].copy()
    coarse["parent_key"] = coarse.class_counts.map(canonical)
    fine["parent_key"] = fine.parent_class_counts.map(canonical)
    parent_lookup = coarse.set_index(["panel_id", "method", "parent_key"])
    rows = []
    for keys, g in fine.groupby(["panel_id", "method", "parent_key"], sort=False):
        p = parent_lookup.loc[keys]
        assert not isinstance(p, pd.DataFrame)
        assert g.teams.sum() == p.teams
        r = {k: p[k] for k in META if k != "panel_id"}
        r["panel_id"] = keys[0]
        r.update(method=keys[1], parent_configuration_id=p.configuration_id, parent_class_counts=p.class_counts,
                 coarse_teams=int(p.teams), fine_cells=len(g), fine_singletons=int(g.teams.eq(1).sum()),
                 fine_configuration_ids="|".join(g.configuration_id), refinement_present=len(g) > 1,
                 fine_failure_rate_min=g.failure_rate.min(), fine_failure_rate_max=g.failure_rate.max())
        for metric in ["B8L2", "D10", "fusion_turn_n", "fusion_short_turn_edges", "geometry_area_h2", "height_mean_h", "recorded_time_total_seconds"]:
            a = g[g[metric + "_valid_n"].gt(0)]
            a10 = g[g[metric + "_valid_n"].ge(10)]
            r[metric + "_fine_mean_min"] = a[metric + "_mean"].min()
            r[metric + "_fine_mean_max"] = a[metric + "_mean"].max()
            r[metric + "_fine_mean_span"] = a[metric + "_mean"].max() - a[metric + "_mean"].min() if len(a) >= 2 else np.nan
            r[metric + "_fine_mean_span_ge10"] = a10[metric + "_mean"].max() - a10[metric + "_mean"].min() if len(a10) >= 2 else np.nan
        rows.append(r)
    out = pd.DataFrame(rows)
    save(out, "PARENT_FIXED_FINE_CONFIGURATION_SUMMARY.csv.gz")
    simple = out.groupby(["condition", "method"], as_index=False).agg(parent_cells=("parent_configuration_id", "size"),
        refined_parent_cells=("refinement_present", "sum"), all_fine_cells=("fine_cells", "sum"),
        Q_refined_parent_cells_scored=("B8L2_fine_mean_span", "count"), time_refined_parent_cells_scored=("recorded_time_total_seconds_fine_mean_span", "count"),
        mean_Q_span_in_refined_cells=("B8L2_fine_mean_span", "mean"), median_Q_span_in_refined_cells=("B8L2_fine_mean_span", "median"),
        mean_time_span_seconds_in_refined_cells=("recorded_time_total_seconds_fine_mean_span", "mean"))
    save(simple, "FINE_INCREMENT_COVERAGE.csv")


def main():
    x = overview()
    summarize(x)
    examples(x)
    background_path(x)
    failure_status()
    fine_increment(x)
    js("PRESENTATION_COMPLETE.json", dict(status="complete", source_main=SOURCE_MAIN, underlying_data="true_v2", endpoint_calls=0,
                                          total_configuration_cells=len(x), representative_panels=len(ILLUSTRATIONS),
                                          explanatory_selection="All seven selected panels are shown in full; selections explain positive, weak, null and failed outcomes. They are internal exploratory examples.",
                                          code="summarize_and_render.py"))


if __name__ == "__main__":
    main()
