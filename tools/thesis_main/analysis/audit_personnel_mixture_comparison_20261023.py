"""从已交付明细独立核对混合构成研究；不重跑融合、分类或哈希。"""
from pathlib import Path
import json

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT / "research/workers/personnel_mixture_comparison_20261022"
OUT = PACKAGE / "local_review_20261023"
CHECKS = []


def read(path, **kwargs):
    return pd.read_csv(PACKAGE / path, float_precision="round_trip", **kwargs)


def close(actual, expected, label):
    a, b = np.asarray(actual, dtype=float), np.asarray(expected, dtype=float)
    assert a.shape == b.shape, (label, a.shape, b.shape)
    assert np.allclose(a, b, rtol=1e-9, atol=1e-9, equal_nan=True), label


def members(value):
    return frozenset(str(value).split("|")) if pd.notna(value) and value else frozenset()


def record(name, **details):
    CHECKS.append(dict(check=name, status="passed", **details))
    print(name, details, flush=True)


def manifest():
    index = read("COMPLETE_FILE_INDEX.csv")
    assert index.path.is_unique
    for row in index.itertuples(index=False):
        path = ROOT / row.path
        if row.path.startswith("docs/"):
            path = PACKAGE / "source_report" / path.name
        else:
            original = OUT / "original" / path.relative_to(PACKAGE)
            if original.exists():
                path = original
        assert path.is_file(), str(path)
        assert path.stat().st_size == row.bytes, str(path)
    record("author_manifest_presence_and_bytes", files=len(index), hashes_recomputed=False)


def panels_and_distributions():
    panels = read("configurations/PANELS_USED.csv")
    teams = read("configurations/TEAM_MEMBERS.csv.gz")
    pt = read("configurations/PANEL_TEAMS.csv.gz")
    links = read("configurations/TEAM_CONFIGURATION_LINKS.csv.gz")
    assert teams.team_key.is_unique
    team_members = dict(zip(teams.team_key, teams.member_workers.map(members)))
    panel_index = panels.set_index("panel_id")
    for pid, group in pt.groupby("panel_id"):
        p = panel_index.loc[pid]
        variable, background = members(p.variable_workers), members(p.background_workers)
        chosen = group.selected_variable_workers.map(members)
        assert len(variable) == 12 and len(group) == len(set(chosen)) == 924
        assert not variable & background and group.team_key.is_unique
        for key, selected in zip(group.team_key, chosen):
            assert len(selected) == 6 and selected <= variable
            assert team_members[key] == background | selected
            assert len(team_members[key]) == p.n
    record("complete_12_choose_6_panels", panels=len(panels), links=len(pt), unique_teams=len(teams))
    endpoint_parts = []
    for condition in ("manual", "semi"):
        ep = read(f"configurations/ENDPOINT_OUTCOMES_{condition}.csv.gz", low_memory=False)
        endpoint_parts.append(ep)
        overview = read(f"configurations/CONFIGURATION_OVERVIEW_{condition}.csv.gz").set_index("configuration_id").sort_index()
        joined = links.merge(ep, on="team_key", validate="many_to_one")
        grouped = joined.groupby("configuration_id")
        assert set(grouped.groups) == set(overview.index)
        close(grouped.size().sort_index(), overview.teams, condition + " teams")
        failures = ~joined.complete_evaluable.astype(str).str.lower().eq("true")
        fail = failures.groupby(joined.configuration_id).sum().sort_index()
        close(fail, overview.failed_teams, condition + " failures")
        close(fail / grouped.size().sort_index(), overview.failure_rate, condition + " failure rate")
        for metric in ("B8L2", "D10", "fusion_turn_n"):
            values = grouped[metric]
            stat = values.agg(["count", "mean", "std", "min", "max"]).sort_index()
            for column, suffix in [("count", "valid_n"), ("mean", "mean"), ("std", "sd"), ("min", "minimum"), ("max", "maximum")]:
                close(stat[column], overview[f"{metric}_{suffix}"], f"{condition} {metric} {suffix}")
            q = values.quantile([.05, .25, .5, .75, .95]).unstack().sort_index()
            for value, suffix in [(.05, "p05"), (.25, "p25"), (.5, "median"), (.75, "p75"), (.95, "p95")]:
                close(q[value], overview[f"{metric}_{suffix}"], f"{condition} {metric} {suffix}")
        record("configuration_distributions_" + condition, cells=len(overview), metrics=["B8L2", "D10", "fusion_turn_n"], all_failure_denominators=True)
    return panels, pt, links, pd.concat(endpoint_parts).set_index("team_key")


def finite_pairs(panels, pt, links, ep):
    fields = ["same_mean", "changed_mean", "changed_minus_same"]
    keys = ["condition", "method", "classification_view", "n", "actual_m", "metric"]
    for condition in ("manual", "semi"):
        data = read(f"exchanges/finite_pair_comparison/{condition}_PANEL_MATCHED_PAIR_METRICS.csv.gz")
        images = data.groupby(keys + ["building", "image"], dropna=False)[fields].mean()
        buildings = images.groupby(keys + ["building"], dropna=False)[fields].mean()
        calculated = buildings.groupby(keys, dropna=False)[fields].mean().sort_index()
        saved = read(f"exchanges/finite_pair_comparison/{condition}_SUMMARY.csv").set_index(keys).sort_index()
        close(calculated, saved[fields], "finite summary " + condition)
        record("finite_pair_summary_" + condition, rows=len(saved), starts_from="panel means", aggregation="image then building equal")
    # 一个完整面板从团队集合重建全部端点对，独立检验精确共同背景的分组。
    sample = panels.loc[panels.condition.eq("manual") & panels.n.eq(20)].iloc[0]
    group = pt.loc[pt.panel_id.eq(sample.panel_id)].sort_values("team_key")
    selected = group.selected_variable_workers.map(members).tolist()
    universe = sorted(members(sample.variable_workers))
    masks = np.array([sum(1 << universe.index(w) for w in s) for s in selected])
    ii, jj = np.triu_indices(len(group), 1)
    shared = masks[ii] & masks[jj]
    replacement = 6 - np.array([int(v).bit_count() for v in shared])
    endpoints = ep.loc[group.team_key]
    q = endpoints.B8L2.to_numpy()
    difference = np.abs(q[jj] - q[ii])
    label = links.loc[links.panel_id.eq(sample.panel_id) & links.method.eq("V3_JOINT_QT") & links.tier.eq("coarse")].set_index("team_key").configuration_id.reindex(group.team_key)
    assert label.notna().all()
    changed = label.to_numpy()[ii] != label.to_numpy()[jj]
    pairs = pd.DataFrame(dict(background=shared, m=replacement, changed=changed, value=difference))
    means = pairs.groupby(["m", "background", "changed"]).value.mean().unstack().dropna()
    calculated = means.groupby("m").mean()
    saved = read("exchanges/finite_pair_comparison/manual_PANEL_MATCHED_PAIR_METRICS.csv.gz")
    saved = saved.loc[saved.panel_id.eq(sample.panel_id) & saved.method.eq("V3_JOINT_QT") & saved.classification_view.eq("coarse") & saved.metric.eq("abs_B8L2")].set_index("actual_m")
    close(calculated[False], saved.loc[calculated.index, "same_mean"], "one panel same")
    close(calculated[True], saved.loc[calculated.index, "changed_mean"], "one panel changed")
    record("finite_one_panel_raw_pairs", panel=sample.panel_id, pairs=len(pairs), method="V3_JOINT_QT", metric="abs_B8L2")


def difficulty():
    images = read("exchanges/ALL_IMAGE_EFFECTS.csv.gz")
    scope = pd.read_csv(ROOT / "research/difficulty/difficulty_mechanisms_v2_20261020/scope_closeout_20261022/image_scope_support.csv")
    images = images.merge(scope[["image", "coarse_class"]].rename(columns={"coarse_class": "current_difficulty"}), on="image", validate="many_to_one")
    saved = read("difficulty/exchange_difficulty_full.csv.gz")
    metrics = saved.metric.unique().tolist()
    keys = ["condition_id", "current_difficulty"]
    records = []
    for key, group in images.groupby(keys):
        bs = group.groupby("building")[metrics].mean()
        for metric in metrics:
            x, b = group[metric].dropna(), bs[metric].dropna()
            records.append(dict(zip(keys, key)) | dict(metric=metric, images=len(x), buildings=len(b), image_equal_mean=x.mean(), building_equal_mean=b.mean(), image_median=x.median(), positive_images=int(x.gt(1e-9).sum()), negative_images=int(x.lt(-1e-9).sum()), positive_buildings=int(b.gt(1e-9).sum()), negative_buildings=int(b.lt(-1e-9).sum())))
    index = keys + ["metric"]
    calculated = pd.DataFrame(records).set_index(index).sort_index()
    expected = saved.set_index(index).sort_index()
    assert calculated.index.equals(expected.index)
    close(calculated, expected[calculated.columns], "difficulty from current image scope")
    record("difficulty_all_metrics", rows=len(expected), conditions=expected.index.droplevel("metric").nunique(), starts_from="delivered image effects and current mainline difficulty")


def strict_and_background():
    total = 0
    for batch in ("manual_joint_A", "manual_joint_B", "manual_structure", "semi_joint"):
        events = read(f"exchanges/{batch}/EVENT_OUTCOMES.csv.gz", low_memory=False)
        links = read(f"exchanges/{batch}/EXACT_EVENT_LINKS.csv.gz", low_memory=False)
        assert events.event_id.is_unique and set(events.event_id) == set(links.event_id)
        valid = events.three_scores_available.astype(str).str.lower().eq("true")
        for metric in ("B8L2", "D10"):
            a, b, c = (events[f"{arm}_{metric}"] for arm in "ABC")
            close(events[f"net_{metric}"], (c-b).where(valid), batch + " net " + metric)
            close(events[f"symmetric_cross_abs_{metric}"], ((c-a).abs()+(c-b).abs()).div(2).where(valid), batch + " absolute " + metric)
        for row in links.itertuples(index=False):
            a, b, c = (members(getattr(row, f"{arm}_member_workers")) for arm in "ABC")
            d, x, y, z = (members(getattr(row, f)) for f in ("common_background", "outgoing_block_X", "same_count_block_Y", "changed_count_block_Z"))
            assert a == d | x and b == d | y and c == d | z
            assert len(a) == len(b) == len(c) == row.n
            assert len(a-b) == row.actual_m_AB and len(a-c) == row.actual_m_AC and len(b-c) == row.actual_m_BC
            assert len(d | x | y | z) == sum(map(len, [d, x, y, z]))
        total += len(events)
        record("strict_events_" + batch, rows=len(events), members_and_Q_D10=True)
    paths = read("configurations/CASE_7y13_BACKGROUND_ADDITION_PAIRS.csv.gz")
    close(paths.delta_B8L2, paths.B8L2_n33 - paths.B8L2_n20, "7y13 delta")
    record("7y13_background_paths", rows=len(paths), mean=float(paths.delta_B8L2.mean()), median=float(paths.delta_B8L2.median()), positive=int(paths.delta_B8L2.gt(0).sum()), negative=int(paths.delta_B8L2.lt(0).sum()), strict_total=total)
    ac = read("direct_ac/EXACT_AC_EVENTS_AND_OUTCOMES.csv.gz")
    for row in ac.itertuples(index=False):
        a, c, d = (members(getattr(row, f)) for f in ("A_member_workers", "C_member_workers", "common_background"))
        assert a & c == d and len(a) == len(c) == row.n
        assert len(a-c) == row.actual_m_AC
    valid = ac.both_scored.astype(str).str.lower().eq("true")
    for metric in ("B8L2", "D10", "fusion_turn_n"):
        expected = ac[f"C_{metric}"] - ac[f"A_{metric}"]
        if metric != "fusion_turn_n":
            expected = expected.where(valid)
        close(ac[f"delta_{metric}"], expected, "direct AC " + metric)
    record("direct_AC_members_and_deltas", events=len(ac), m_min=int(ac.actual_m_AC.min()), m_max=int(ac.actual_m_AC.max()))


def main():
    OUT.mkdir(exist_ok=True)
    manifest()
    data = panels_and_distributions()
    finite_pairs(*data)
    difficulty()
    strict_and_background()
    (OUT / "INDEPENDENT_CHECKS.json").write_text(json.dumps(dict(checks=CHECKS, not_checked=["all native fusion", "raw-coordinate rescoring", "classification refitting", "all 143279136 pair reconstruction", "hashes"]), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
