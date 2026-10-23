"""从已核 v2 结果提取人员主文 F4；只重聚合图表，不重新融合或评分。"""
from pathlib import Path
import json

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "research/workers/personnel_mixture_comparison_20261022"
OUT = ROOT / "research/workers/personnel_main_figures_v2_20261023/data"
DIFFICULTIES = ["简单", "中等", "困难"]
CHECKS = []


def check(actual, expected, label):
    assert np.allclose(actual, expected, rtol=1e-10, atol=1e-9, equal_nan=True), label
    CHECKS.append(label)


def save(frame, name):
    OUT.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUT / name, index=False, encoding="utf-8-sig")


def validate_difficulty(frame, image, difficulty):
    source = pd.read_csv(ROOT / "research/difficulty/difficulty_mechanisms_v2_20261020/scope_closeout_20261022/image_scope_support.csv")
    linked = frame[[image, difficulty]].drop_duplicates().merge(
        source[["image", "coarse_class", "is_oos", "is_doorway"]].rename(columns={"image": image}),
        on=image, how="left", validate="many_to_one")
    assert linked.coarse_class.notna().all()
    assert linked[difficulty].eq(linked.coarse_class).all()
    assert not linked.is_oos.any() and not linked.is_doorway.any()
    CHECKS.append(f"human_difficulty_source/{image}/{len(linked)}")


def stats(frame, metric, building="building", image="image"):
    valid = frame[[building, image, metric]].dropna()
    iv = valid.groupby([building, image])[metric].mean()
    bv = iv.groupby(level=0).mean()
    return dict(images=len(iv), buildings=len(bv), image_equal_mean=iv.mean(),
                building_equal_mean=bv.mean(), positive_images=int((iv > 1e-9).sum()),
                negative_images=int((iv < -1e-9).sum()), zero_images=int((iv.abs() <= 1e-9).sum()),
                positive_buildings=int((bv > 1e-9).sum()), negative_buildings=int((bv < -1e-9).sum()),
                zero_buildings=int((bv.abs() <= 1e-9).sum()))


def raw_expression():
    raw = pd.read_csv(SOURCE / "difficulty/role_image_contrasts.csv.gz")
    saved = pd.read_csv(SOURCE / "difficulty/role_difficulty_summary.csv")
    raw = raw[(raw.method == "V3_BEHAVIOR") & (raw.tier == "coarse_label") &
              (raw.role == "turn_expression") & raw.source.isin(["all", "v1"]) &
              raw.current_difficulty.isin(DIFFICULTIES)].copy()
    validate_difficulty(raw, "image_code", "current_difficulty")
    metrics = {"turn_n": "个", "short_turn_edges": "条", "near_straight_nodes_5deg": "个",
               "B8L2": "Q分", "unmatched_ref_9": "比例"}
    rows = []
    for condition in ("manual", "semi"):
        for source in ("all", "v1"):
            for difficulty in DIFFICULTIES:
                group = raw[(raw.condition == condition) & (raw.source == source) &
                            (raw.current_difficulty == difficulty)]
                for metric, unit in metrics.items():
                    values = stats(group, metric + "_difference", "building_id", "image_id")
                    row = dict(condition=condition, method="V3_BEHAVIOR", tier="coarse_label",
                               source=source, difficulty=difficulty, metric=metric, unit=unit,
                               contrast="楼外较多转折角色−较少转折角色", **values,
                               status="available" if values["images"] else "no_support")
                    expected = saved[(saved.method == row["method"]) & (saved.condition == condition) &
                                     (saved.tier == row["tier"]) & (saved.source == source) &
                                     (saved.role == "turn_expression") &
                                     (saved.stratification == "current_difficulty") &
                                     (saved.current_difficulty == difficulty) & (saved.metric == metric)]
                    if len(expected):
                        assert len(expected) == 1
                        check(list(values.values()), expected.iloc[0][list(values)].to_numpy(float),
                              f"raw/{condition}/{source}/{difficulty}/{metric}")
                    else:
                        assert values["images"] == 0
                    rows.append(row)
    save(pd.DataFrame(rows), "DIFFICULTY_RAW_EXPRESSION.csv")
    save(raw, "DIFFICULTY_RAW_IMAGE_CONTRASTS.csv")


def mixture_spread():
    panels = pd.read_csv(SOURCE / "configurations/PANEL_SPREAD_SUMMARY.csv.gz")
    saved = pd.read_csv(SOURCE / "configurations/DIFFICULTY_SPREAD_SUMMARY.csv")
    panels = panels[(panels.method == "V3_BEHAVIOR") & (panels.n == 20) &
                    panels.metric.isin(["B8L2", "D10", "fusion_turn_n", "fusion_short_turn_edges"]) &
                    panels.difficulty.isin(DIFFICULTIES)].copy()
    validate_difficulty(panels, "image", "difficulty")
    values = ["cell_mean_span", "median_within_cell_sd", "median_within_cell_iqr",
              "median_within_cell_p05_p95_width", "cell_mean_span_ge10"]
    keys = ["condition", "method", "tier", "n", "difficulty", "metric"]
    images = panels.groupby(keys + ["building", "image"], as_index=False)[values].mean()
    buildings = images.groupby(keys + ["building"], as_index=False)[values].mean()
    rows = []
    for key, group in panels.groupby(keys):
        base = dict(zip(keys, key))
        ig = images
        bg = buildings
        expected = saved
        for k, v in base.items():
            ig, bg, expected = ig[ig[k] == v], bg[bg[k] == v], expected[expected[k] == v]
        assert len(expected) == 1
        for measure in values:
            value = bg[measure].mean()
            check(value, expected.iloc[0][measure], f"spread/{key}/{measure}")
            counts = dict(images=int(ig[measure].notna().sum()), buildings=int(bg[measure].notna().sum()),
                          panels=int(group[measure].notna().sum()))
            for k, v in counts.items():
                check(v, expected.iloc[0][measure + "_valid_" + k], f"spread_count/{key}/{measure}/{k}")
            rows.append(dict(**base, measure=measure, building_equal_mean=value,
                             image_equal_mean=ig[measure].mean(), **counts,
                             status="available" if counts["images"] else "not_identifiable"))
    save(pd.DataFrame(rows), "DIFFICULTY_MIXTURE_SPREAD.csv")
    save(images, "DIFFICULTY_MIXTURE_IMAGES.csv")
    # 每个面板出现一次；不把跨面板重复团队称为独立团队。
    failure = panels[panels.metric == "B8L2"].copy()
    assert not failure.duplicated(["panel_id", "method", "tier"]).any()
    failure["failure_rate"] = failure.failed_teams / failure.teams
    rows = []
    for key, group in failure.groupby(["condition", "method", "tier", "n", "difficulty"]):
        row = dict(zip(["condition", "method", "tier", "n", "difficulty"], key))
        row.update(stats(group, "failure_rate"))
        row.update(panel_count=group.panel_id.nunique(), team_appearances=int(group.teams.sum()),
                   failed_team_appearances=int(group.failed_teams.sum()),
                   pooled_failure_rate=group.failed_teams.sum() / group.teams.sum())
        rows.append(row)
    save(pd.DataFrame(rows), "DIFFICULTY_MIXTURE_FAILURE.csv")


def exchange_directions():
    definitions = {
        "ca2a651478a2ab2966a4": ("联合：较低历史Q、较快", "main"),
        "81a9856eb2855547a6ff": ("联合：较高历史Q、较慢", "main"),
        "214f58a11c554f2656d1": ("结构：常规→较多转折", "supplement"),
        "31838b69575a07dea212": ("结构：常规→较多转折", "supplement"),
        "bb6b7809045aa48f22a9": ("Semi联合：较高历史Q、更快、较多转折", "semi_comparison"),
    }
    full = pd.read_csv(SOURCE / "difficulty/exchange_difficulty_full.csv.gz")
    images = pd.read_csv(SOURCE / "exchanges/ALL_IMAGE_EFFECTS.csv.gz")
    join = pd.read_csv(SOURCE / "difficulty/exchange_difficulty_join.csv")
    images = images.merge(join[["condition_id", "image", "current_difficulty", "is_oos", "is_doorway"]],
                          on=["condition_id", "image"], validate="one_to_one")
    images = images[images.condition_id.isin(definitions) & images.current_difficulty.isin(DIFFICULTIES)]
    validate_difficulty(images, "image", "current_difficulty")
    assert not images.is_oos.any() and not images.is_doorway.any()
    metrics = ["net_B8L2", "net_D10", "net_iou_2d", "net_dir", "net_fusion_turn_n",
               "net_fusion_short_turn_edges", "net_fusion_redundancy_n", "net_recorded_time_logratio",
               "A_failure", "B_failure", "C_failure", "net_loss_gt5", "net_loss_gt10",
               "within_abs_B8L2", "cross_abs_B8L2"]
    selected = full[full.condition_id.isin(definitions) & full.current_difficulty.isin(DIFFICULTIES) &
                    full.metric.isin(metrics)].copy()
    for _, row in selected.iterrows():
        group = images[(images.condition_id == row.condition_id) &
                       (images.current_difficulty == row.current_difficulty)]
        values = stats(group, row.metric)
        check(list(values.values()), row[list(values)].to_numpy(float),
              f"exchange/{row.condition_id}/{row.current_difficulty}/{row.metric}")
    selected["direction_zh"] = selected.condition_id.map(lambda k: definitions[k][0])
    selected["figure_role"] = selected.condition_id.map(lambda k: definitions[k][1])
    selected["display_value"] = selected.building_equal_mean
    selected["display_unit"] = "原单位"
    conversions = {
        "net_recorded_time_logratio": (lambda x: 100 * np.expm1(x), "%（楼均log比还原）"),
        "net_iou_2d": (lambda x: 100 * x, "百分点"),
        **{m: (lambda x: 100 * x, "%（楼等权）") for m in ["A_failure", "B_failure", "C_failure", "net_loss_gt5", "net_loss_gt10"]},
    }
    for metric, (convert, unit) in conversions.items():
        mask = selected.metric == metric
        selected.loc[mask, "display_value"] = convert(selected.loc[mask, "building_equal_mean"])
        selected.loc[mask, "display_unit"] = unit
    selected.loc[selected.metric.isin(["net_B8L2", "net_D10", "within_abs_B8L2", "cross_abs_B8L2"]), "display_unit"] = "分"
    selected.loc[selected.metric == "net_dir", "display_unit"] = "度"
    selected.loc[selected.metric.isin(["net_fusion_turn_n", "net_fusion_short_turn_edges", "net_fusion_redundancy_n"]), "display_unit"] = "个/条"
    save(selected, "DIFFICULTY_EXCHANGE_DIRECTIONS.csv")
    save(images, "DIFFICULTY_EXCHANGE_IMAGES.csv")
    coverage = selected[selected.metric == "net_B8L2"][["condition_id", "condition", "n", "actual_m_AB", "current_difficulty", "images", "buildings"]].copy()
    assert set(coverage.condition_id) == set(definitions)
    save(coverage, "DIFFICULTY_EXCHANGE_SUPPORT.csv")


def main():
    raw_expression()
    mixture_spread()
    exchange_directions()
    (OUT / "DIFFICULTY_PREPARATION_CHECKS.json").write_text(json.dumps({
        "source": SOURCE.relative_to(ROOT).as_posix(), "data_version": "real_v2",
        "checks": len(CHECKS), "status": "passed", "recomputed": "原答角色对照、配比面板和逐图换类结果的再聚合",
        "new_fusion": 0, "new_scoring": 0, "new_classification": 0,
        "check_names": CHECKS}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"F4 数据提取完成：{len(CHECKS)} 项断言通过。")


if __name__ == "__main__":
    main()
