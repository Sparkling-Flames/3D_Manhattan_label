"""Summarize exact panel team, composition, and strict ABC cross-score support."""

from __future__ import annotations

import numpy as np
import pandas as pd

from tools.thesis_main.analysis.personnel_d10_formation_sensitivity_20261024 import OUT
from tools.thesis_main.analysis.personnel_d10_panel_response_20261024 import ARMS, METRICS



def composition_eta2(between, within, count):
    # Constant scores can acquire rounding-scale variance during grouped averaging.
    total = between + within
    return between / total if total > float(np.sum(count)) * 1e-20 else np.nan


def main() -> None:
    selected = pd.read_csv(OUT / "SELECTED_TEAMS.csv.gz")
    base = selected[selected.formation_arm.eq(ARMS[0])]
    pairs = []
    for arm in ARMS[1:]:
        other = selected[selected.formation_arm.eq(arm)]
        joined = base.merge(other, on=["panel_id", "tier", "policy"], suffixes=("_B8", "_D10"), validate="one_to_one")
        joined["compared_arm"] = arm
        joined["shared_members"] = [len(set(a.split("|")) & set(b.split("|"))) for a, b in
                                    zip(joined.selected_workers_B8, joined.selected_workers_D10)]
        joined["replacements"] = 6 - joined.shared_members
        joined["failure_delta"] = joined.failure_D10.astype(int) - joined.failure_B8.astype(int)
        scored = joined[[f"{m}_{side}" for m in METRICS[:8] for side in ("B8", "D10")]].notna().all(axis=1)
        joined["all_score_metrics_common"] = scored
        for metric in METRICS:
            joined[f"{metric}_delta"] = (joined[f"{metric}_D10"] - joined[f"{metric}_B8"]).where(scored)
        time_ok = joined.recorded_time_eligible_B8.astype(bool) & joined.recorded_time_eligible_D10.astype(bool) & \
            joined.time_source_kinds_B8.eq(joined.time_source_kinds_D10) & \
            ~joined.time_source_kinds_B8.fillna("").str.contains("|", regex=False)
        joined["recorded_time_comparable"] = time_ok
        joined["recorded_time_logratio"] = np.log(joined.recorded_time_total_seconds_D10 /
                                                    joined.recorded_time_total_seconds_B8).where(time_ok)
        pairs.append(joined)
    pair = pd.concat(pairs, ignore_index=True)
    assert pair.groupby(["panel_id", "tier", "policy", "compared_arm"]).size().eq(1).all()
    pair.to_csv(OUT / "SELECTED_TEAM_CROSS_EVALUATION.csv.gz", index=False, compression="gzip")
    metrics = ["B8L2", "D10", "iou_2d", "IoU3D100", "S_bottom_deg", "dir", "Hmean", "Hcenter",
               "fusion_turn_n", "fusion_short_turn_edges", "recorded_time_logratio"]
    long = []
    for metric in metrics:
        col = metric if metric == "recorded_time_logratio" else f"{metric}_delta"
        d = pair[["panel_id", "image_B8", "building_B8", "condition_B8", "difficulty_B8", "source_domain_B8", "n_B8",
                  "tier", "policy", "compared_arm", "replacements", "failure_delta", "all_score_metrics_common", col]].copy()
        d["metric"] = metric
        d["delta"] = d.pop(col)
        long.append(d)
    long = pd.concat(long, ignore_index=True)
    image = long.groupby(["image_B8", "building_B8", "condition_B8", "difficulty_B8", "source_domain_B8", "tier", "policy",
                          "compared_arm", "metric"]).agg(
        panels=("panel_id", "nunique"), scored_panels=("delta", "count"), mean_delta=("delta", "mean"),
        mean_replacements=("replacements", "mean"), changed_panels=("replacements", lambda x: int((x > 0).sum())),
        failure_delta=("failure_delta", "mean")).reset_index()
    image.to_csv(OUT / "SELECTED_TEAM_IMAGE_EFFECTS.csv", index=False)
    building = image.groupby(["building_B8", "condition_B8", "difficulty_B8", "source_domain_B8", "tier", "policy",
                              "compared_arm", "metric"]).agg(
        images=("image_B8", "nunique"), mean_delta=("mean_delta", "mean"),
        positive_images=("mean_delta", lambda x: int((x > 0).sum())),
        mean_replacements=("mean_replacements", "mean"), failure_delta=("failure_delta", "mean")).reset_index()
    building.to_csv(OUT / "SELECTED_TEAM_BUILDING_EFFECTS.csv", index=False)
    building.groupby(["condition_B8", "difficulty_B8", "source_domain_B8", "tier", "policy", "compared_arm", "metric"]).agg(
        buildings=("building_B8", "nunique"), images=("images", "sum"), building_equal_mean=("mean_delta", "mean"),
        positive_buildings=("mean_delta", lambda x: int((x > 0).sum())),
        mean_replacements=("mean_replacements", "mean"), failure_delta=("failure_delta", "mean")).reset_index().to_csv(
            OUT / "SELECTED_TEAM_SUMMARY.csv", index=False)

    cells = pd.read_csv(OUT / "COMPOSITION_CELLS.csv.gz")
    rows = []
    for key, group in cells.groupby(["panel_id", "image", "building", "condition", "difficulty", "source_domain", "n", "formation_arm", "tier"]):
        row = dict(zip(["panel_id", "image", "building", "condition", "difficulty", "source_domain", "n", "formation_arm", "tier"], key))
        row.update(cells=len(group), teams=int(group.teams.sum()), failed=int(group.failed.sum()))
        assert 0 < row["teams"] <= 924
        for metric in ("B8L2", "D10"):
            count = group[f"{metric}_valid"].to_numpy()
            mean = group[f"{metric}_mean"].to_numpy()
            sd = group[f"{metric}_sd"].fillna(0).to_numpy()
            good = count > 0
            overall = np.average(mean[good], weights=count[good])
            between = np.sum(count[good] * (mean[good] - overall) ** 2)
            within = np.sum(np.maximum(count[good] - 1, 0) * sd[good] ** 2)
            row[f"{metric}_valid"] = int(count.sum())
            row[f"{metric}_eta2"] = composition_eta2(between, within, count)
            row[f"{metric}_cell_mean_span"] = float(np.ptp(mean[good]))
        rows.append(row)
    composition = pd.DataFrame(rows)
    composition.to_csv(OUT / "COMPOSITION_PANEL_SUMMARY.csv", index=False)
    coverage = pd.read_csv(OUT / "PANEL_LABEL_COVERAGE.csv")
    assert set(composition.panel_id) <= set(coverage.panel_id)
    matched_coverage = composition.merge(coverage[["panel_id", "formation_arm", "known_teams"]],
                                         on=["panel_id", "formation_arm"], validate="many_to_one")
    assert matched_coverage.teams.eq(matched_coverage.known_teams).all()

    links = pd.read_csv(OUT / "COMPOSITION_TEAM_LINKS.csv.gz",
                        usecols=["panel_id", "condition", "building", "formation_arm", "tier", "team_key", "class_counts"],
                        dtype={"class_counts": "string"})
    wide = links.pivot(index=["panel_id", "condition", "building", "tier", "team_key"],
                       columns="formation_arm", values="class_counts").reset_index()
    assert len(wide) == 310464 * 2
    endpoint = pd.concat([pd.read_csv(OUT.parent / "personnel_mixture_comparison_20261022/configurations" /
                                     f"ENDPOINT_OUTCOMES_{condition}.csv.gz", usecols=["team_key", "B8L2", "D10", "failure"])
                          for condition in ("manual", "semi")], ignore_index=True)
    assert endpoint.team_key.is_unique
    common_cells, common_panels = [], []
    for arm in ARMS[1:]:
        common = wide.dropna(subset=[ARMS[0], arm]).merge(endpoint, on="team_key", validate="many_to_one")
        for key, group in common.groupby(["panel_id", "condition", "building", "tier"]):
            for scheme in (ARMS[0], arm):
                row = dict(panel_id=key[0], condition=key[1], building=key[2], tier=key[3],
                           compared_arm=arm, formation_arm=scheme, matched_teams=len(group), failed=int(group.failure.sum()))
                for metric in ("B8L2", "D10"):
                    cells_here = group.groupby(scheme, dropna=False)[metric].agg(["count", "mean", "std"])
                    count, mean, sd = (cells_here[field].to_numpy() for field in ("count", "mean", "std"))
                    valid = count > 0
                    grand = np.average(mean[valid], weights=count[valid])
                    between = np.sum(count[valid] * (mean[valid] - grand) ** 2)
                    within = np.sum(np.maximum(count[valid] - 1, 0) * np.nan_to_num(sd[valid]) ** 2)
                    row[f"{metric}_valid"] = int(count.sum())
                    row[f"{metric}_eta2"] = composition_eta2(between, within, count)
                    row[f"{metric}_cell_mean_span"] = float(np.ptp(mean[valid]))
                row["cells"] = group[scheme].nunique()
                common_panels.append(row)
                for counts, cgroup in group.groupby(scheme):
                    common_cells.append(dict(panel_id=key[0], condition=key[1], building=key[2], tier=key[3],
                                             compared_arm=arm, formation_arm=scheme, class_counts=counts,
                                             teams=len(cgroup), failed=int(cgroup.failure.sum()),
                                             B8L2_mean=cgroup.B8L2.mean(), B8L2_sd=cgroup.B8L2.std(),
                                             D10_mean=cgroup.D10.mean(), D10_sd=cgroup.D10.std()))
    pd.DataFrame(common_panels).to_csv(OUT / "COMPOSITION_COMMON_PANEL_SUMMARY.csv", index=False)
    pd.DataFrame(common_cells).to_csv(OUT / "COMPOSITION_COMMON_CELLS.csv.gz", index=False, compression="gzip")

    common_panel = pd.DataFrame(common_panels)
    comparison = []
    for (condition, arm, tier), group in common_panel.groupby(["condition", "compared_arm", "tier"]):
        old = group[group.formation_arm.eq(ARMS[0])].set_index("panel_id", verify_integrity=True)
        new = group[group.formation_arm.eq(arm)].set_index("panel_id", verify_integrity=True)
        assert old.index.equals(new.index) and old.matched_teams.equals(new.matched_teams)
        for metric in ("B8L2", "D10"):
            before, after = old[f"{metric}_eta2"], new[f"{metric}_eta2"]
            paired = before.notna() & after.notna()
            comparison.append(dict(condition=condition, compared_arm=arm, tier=tier, metric=metric,
                                   panels=len(old), comparable_panels=int(paired.sum()), buildings=old.building.nunique(),
                                   matched_teams=int(old.matched_teams.sum()), old_eta2_mean=before[paired].mean(),
                                   new_eta2_mean=after[paired].mean(), positive_panels=int((after[paired] > before[paired]).sum())))
    pd.DataFrame(comparison).to_csv(OUT / "COMPOSITION_COMMON_COMPARISON.csv", index=False)

    coverage = pd.read_csv(OUT / "ABC_COVERAGE.csv")
    legality = []
    for arm in ARMS[1:]:
        for key, group in coverage.groupby(["condition", "difficulty", "source_domain", "n", "m", "tier"]):
            old = group[f"{ARMS[0]}_status"].eq("strict_ABC")
            new = group[f"{arm}_status"].eq("strict_ABC")
            weight = group.attempts
            legality.append(dict(zip(["condition", "difficulty", "source_domain", "n", "m", "tier"], key),
                                 compared_arm=arm, panels=group.panel_id.nunique(), images=group.image.nunique(),
                                 buildings=group.building.nunique(), attempts=int(weight.sum()),
                                 old_legal=int(weight[old].sum()), new_legal=int(weight[new].sum()),
                                 both=int(weight[old & new].sum()), old_only=int(weight[old & ~new].sum()),
                                 new_only=int(weight[~old & new].sum()),
                                 old_unknown=int(weight[group[f"{ARMS[0]}_status"].eq("unknown_labels")].sum()),
                                 new_unknown=int(weight[group[f"{arm}_status"].eq("unknown_labels")].sum())))
    pd.DataFrame(legality).to_csv(OUT / "ABC_LEGALITY_SUMMARY.csv", index=False)

    events = pd.read_csv(OUT / "ABC_EVENTS.csv.gz")
    assert events.groupby(["panel_id", "formation_arm", "tier", "m", "team_A", "team_B", "team_C"]).size().eq(1).all()
    old_events = events[events.formation_arm.eq(ARMS[0])]
    paired_events = []
    for arm in ARMS[1:]:
        newer = events[events.formation_arm.eq(arm)]
        paired = old_events.merge(newer, on=["panel_id", "tier", "m", "attempt"],
                                  suffixes=("_B8", "_D10"), validate="one_to_one")
        assert all(sorted((a, b, c)) == sorted((x, y, z)) for a, b, c, x, y, z in zip(
            paired.team_A_B8, paired.team_B_B8, paired.team_C_B8,
            paired.team_A_D10, paired.team_B_D10, paired.team_C_D10))
        paired["compared_arm"] = arm
        paired["same_orientation"] = paired.team_A_B8.eq(paired.team_A_D10) & \
            paired.team_B_B8.eq(paired.team_B_D10) & paired.team_C_B8.eq(paired.team_C_D10)
        paired["B8L2_extra_change"] = paired.B8L2_extra_abs_D10 - paired.B8L2_extra_abs_B8
        paired["D10_extra_change"] = paired.D10_extra_abs_D10 - paired.D10_extra_abs_B8
        paired_events.append(paired)
    paired_events = pd.concat(paired_events, ignore_index=True)
    paired_events.to_csv(OUT / "ABC_COMMON_PHYSICAL_TRIPLES.csv.gz", index=False, compression="gzip")
    paired_events.groupby(["condition_B8", "difficulty_B8", "m", "tier", "compared_arm"]).agg(
        common_legal_events=("attempt", "size"), scored=("all_scored_B8", "sum"),
        same_orientation=("same_orientation", "sum"), images=("image_B8", "nunique"),
        B8L2_extra_change=("B8L2_extra_change", "mean"),
        D10_extra_change=("D10_extra_change", "mean")).reset_index().to_csv(
            OUT / "ABC_COMMON_PHYSICAL_SUMMARY.csv", index=False)
    event_metrics = ["B8L2", "D10", "iou_2d", "IoU3D100", "S_bottom_deg", "dir", "Hmean", "Hcenter",
                     "fusion_turn_n", "fusion_short_turn_edges"]
    details = []
    for metric in event_metrics:
        col = f"{metric}_extra_abs"
        d = events[["panel_id", "image", "building", "condition", "difficulty", "source_domain", "n", "m",
                    "formation_arm", "tier", "all_scored", "A_failure", "B_failure", "C_failure", col,
                    f"{metric}_net_C_minus_B"]].copy()
        d["metric"] = metric
        d["extra_abs"] = d.pop(col)
        d["net_C_minus_B"] = d.pop(f"{metric}_net_C_minus_B")
        details.append(d)
    detail = pd.concat(details, ignore_index=True)
    panel = detail.groupby(["panel_id", "image", "building", "condition", "difficulty", "source_domain", "n", "m",
                            "formation_arm", "tier", "metric"]).agg(
        attempts=("all_scored", "size"), scored=("extra_abs", "count"), extra_abs=("extra_abs", "mean"),
        net_C_minus_B=("net_C_minus_B", "mean"), B_failures=("B_failure", "sum"), C_failures=("C_failure", "sum")).reset_index()
    panel.to_csv(OUT / "ABC_PANEL_EFFECTS.csv", index=False)
    image = panel.groupby(["image", "building", "condition", "difficulty", "source_domain", "n", "m", "formation_arm", "tier", "metric"]).agg(
        panels=("panel_id", "nunique"), attempts=("attempts", "sum"), scored=("scored", "sum"),
        extra_abs=("extra_abs", "mean"), net_C_minus_B=("net_C_minus_B", "mean"),
        B_failures=("B_failures", "sum"), C_failures=("C_failures", "sum")).reset_index()
    image.to_csv(OUT / "ABC_IMAGE_EFFECTS.csv", index=False)
    building = image.groupby(["building", "condition", "difficulty", "source_domain", "n", "m", "formation_arm", "tier", "metric"]).agg(
        images=("image", "nunique"), attempts=("attempts", "sum"), scored=("scored", "sum"),
        extra_abs=("extra_abs", "mean"), net_C_minus_B=("net_C_minus_B", "mean"),
        positive_images=("extra_abs", lambda x: int((x > 0).sum())),
        B_failures=("B_failures", "sum"), C_failures=("C_failures", "sum")).reset_index()
    building.to_csv(OUT / "ABC_BUILDING_EFFECTS.csv", index=False)
    building.groupby(["condition", "difficulty", "source_domain", "n", "m", "formation_arm", "tier", "metric"]).agg(
        buildings=("building", "nunique"), images=("images", "sum"), attempts=("attempts", "sum"), scored=("scored", "sum"),
        extra_abs=("extra_abs", "mean"), net_C_minus_B=("net_C_minus_B", "mean"),
        positive_buildings=("extra_abs", lambda x: int((x > 0).sum())), positive_images=("positive_images", "sum"),
        B_failures=("B_failures", "sum"), C_failures=("C_failures", "sum")).reset_index().to_csv(
            OUT / "ABC_SUMMARY.csv", index=False)
    print("summary", len(pair), len(composition), len(events), flush=True)


if __name__ == "__main__":
    main()
