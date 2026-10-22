"""复核旧 n20 保存事件及楼级指标；不运行融合、评分或分型。

输出合同：directional 为逐事件重聚合；building_checks 仅为保存楼级表
重聚合。失败引用与可评分分母分别保留，不能把后者冒称全事件复算。
"""
from pathlib import Path
import json

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "research/workers/personnel_composition_n20_20261021/matched_n20"
OUT = ROOT / "research/workers/personnel_mixture_audit_20261022/OLD_N20_CHECK.json"


def run():
    sources = []

    def read(relative):
        path = BASE / relative
        sources.append(path.relative_to(ROOT).as_posix())
        return pd.read_csv(path)

    events = read("checkpointed_manual/time_analysis/N20_QTD_LOWQ_SLOW_CLASS_DIRECTIONAL_EVENTS.csv")
    summary = read("checkpointed_manual/time_analysis/N20_QTD_LOWQ_SLOW_CLASS_DIRECTIONAL_SUMMARY.csv")
    assert len(events) == 875 and events.event_id.is_unique
    assert events.n.eq(20).all() and events.m_AB.between(4, 8).all()
    metrics = ["net_time_percent", "net_B8L2", "net_D10", "B_failure", "C_failure",
               "time_direction_matches_training", "m_BC", "slow_QL2_count_change"]
    directional, directional_error = [], 0.0
    for direction, group in events.groupby("direction"):
        pools = group.groupby(["building", "image", "pool_id"])[metrics].mean()
        images = pools.groupby(level=["building", "image"]).mean()
        buildings = images.groupby(level="building").mean()
        sign = 1 if direction == "increase_slow_QL2" else -1
        assert (sign * group.slow_QL2_count_change > 0).all()
        assert group.net_time_percent.notna().all()
        assert np.array_equal(group.time_direction_matches_training,
                              (sign * group.net_time_percent > 0).astype(float))
        values = {metric: float(buildings[metric].mean()) for metric in metrics}
        for metric, value in values.items():
            reference = summary[(summary.direction == direction) & (summary.metric == metric)]
            assert len(reference) == 1
            directional_error = max(directional_error, abs(value - float(reference.iloc[0]["mean"])))
        directional.append({
            "direction": direction, "events": len(group), "images": len(images),
            "buildings": len(buildings), "m_AB_range": [int(group.m_AB.min()), int(group.m_AB.max())],
            "m_BC_range": [int(group.m_BC.min()), int(group.m_BC.max())],
            "valid_quality_events": int(group.net_B8L2.notna().sum()),
            "failed_B_event_references": int(group.B_failure.sum()),
            "failed_C_event_references": int(group.C_failure.sum()),
            "time_direction_agree_images": int((sign * images.net_time_percent > 0).sum()),
            "time_direction_agree_buildings": int((sign * buildings.net_time_percent > 0).sum()),
            "quality_positive_images": int((images.net_B8L2 > 0).sum()),
            "quality_positive_buildings": int((buildings.net_B8L2 > 0).sum()),
            "building_equal_means": values,
        })
    assert directional_error < 1e-10

    building_checks, building_error = [], 0.0
    specs = [
        ("manual", "checkpointed_manual/summary/N20_MATCHED_BUILDING_METRICS.csv.gz",
         "checkpointed_manual/summary/N20_MATCHED_PRIMARY_SUMMARY.csv"),
        ("semi", "results_semi/N20_ABC_BUILDING_METRICS.csv.gz",
         "results_semi/N20_ABC_METRIC_SUMMARY.csv"),
        ("manual_time", "checkpointed_manual/time_analysis/N20_MATCHED_TIME_BUILDING_METRICS.csv.gz",
         "checkpointed_manual/time_analysis/N20_MATCHED_TIME_SUMMARY.csv"),
    ]
    quality_metrics = ["common_quality_within_abs", "common_quality_cross_abs", "abs_Q_change_advantage",
                       "stable_advantage", "stable_D10_advantage", "B_failure", "C_failure"]
    scopes = ["all_composition_changes", "within_parent_fine_change", "difficulty_困难"]
    keys = ["method_id", "tier", "condition", "scope", "metric"]
    support = ["events", "images", "buildings", "m_min", "m_max", "all_scored_events", "valid_events"]
    for identity, data_path, summary_path in specs:
        data, reference = read(data_path), read(summary_path)
        assert not data.duplicated(keys + ["building"]).any()
        assert not reference.duplicated(keys).any()
        if identity == "manual_time":
            data = data[(data.method_id == "MV_QTD_manual_new") & (data.tier == "fine") &
                        (data.scope == "within_parent_fine_change")]
        else:
            data = data[data.scope.isin(scopes) & data.metric.isin(quality_metrics)]
        for key, group in data.groupby(keys):
            selected = reference
            for column, value in zip(keys, key):
                selected = selected[selected[column] == value]
            assert len(selected) == 1, key
            ref = selected.iloc[0]
            values = group.value.dropna().to_numpy(float)
            mean = float(values.mean())
            error = abs(mean - float(ref["mean"]))
            building_error = max(building_error, error)
            assert len(values) == int(ref.valid_buildings)
            row = dict(zip(keys, key))
            row.update({column: int(ref[column]) for column in support})
            row.update(mean=mean, valid_buildings=len(values),
                       positive_buildings=int((values > 0).sum()),
                       negative_buildings=int((values < 0).sum()),
                       summary_absolute_error=error)
            if key[-1] in ["abs_Q_change_advantage", "stable_advantage", "stable_D10_advantage"]:
                rng = np.random.default_rng(2026102131)
                boot = values[rng.integers(len(values), size=(10000, len(values)))].mean(axis=1)
                row["independent_building_bootstrap_95"] = np.quantile(boot, [.025, .975]).tolist()
            building_checks.append(row)
    assert building_error < 1e-10

    result = {
        "schema": "old_n20_mixture_audit_v1", "sources": sources,
        "aggregation": "事件→图片池→图片→建筑；最终建筑等权。楼级复核从已保存建筑值开始。",
        "directional_event_reaggregation": directional,
        "directional_max_summary_absolute_error": directional_error,
        "building_checks": building_checks,
        "building_max_summary_absolute_error": building_error,
        "limitations": [
            "875条QTD方向事件重新聚合；未重新计算原团队时间或评分。",
            "其余结果仅从保存楼级表重新聚合，未核对全部团队成员关系或逐事件字段。",
            "第二阶段269814条Manual完整697列分片与1517条Semi完整事件未纳入本次复核；不能凭边际楼表重新计算M父内×m4/m5。",
            "第一阶段ABC_EVENT_RESULTS_COMPLETE.csv.gz为12953条719列，不能替代第二阶段事件。",
            "旧n20的Y/Z允许重叠；A/B与A/C同m，但B/C真实净换人数另列，不适用全三块互斥的n+2m容量公式。",
            "失败为事件引用或建筑等权率；事件重复使用团队，不是独立样本。",
            "bootstrap仅为探索后建筑描述性重抽样。未重新拟合分类或运行原生融合。",
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": OUT.relative_to(ROOT).as_posix(), "directional_events": len(events),
                      "building_checks": len(building_checks), "max_error": max(directional_error, building_error)},
                     ensure_ascii=False))


if __name__ == "__main__":
    run()
