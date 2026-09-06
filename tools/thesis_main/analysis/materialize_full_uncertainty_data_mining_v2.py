"""Reviewed all-stage annotation-uncertainty materialisation.

Version 2 supersedes the first development run.  It removes time proxies from
active-time outcomes, uses only the declared high-support persistent-disagreement
strata, distinguishes supported modes from singleton dissent, and expands the
advisor-facing data dictionary and task case catalogue.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

from tools.thesis_main.analysis.full_uncertainty_common import (
    C1,
    PACKAGE,
    PERSISTENT,
    ROOT,
    V2,
    clean,
    git_head,
    load_raw_annotation_fact,
    load_unified_stage_submissions,
    manifest_for_directory,
    read_csv,
    sha256_file,
    truth,
    write_csv,
    write_json,
)
from tools.thesis_main.analysis.full_uncertainty_geometry import cross_stage_geometry_uncertainty
from tools.thesis_main.analysis.full_uncertainty_reviewed import (
    normalise_raw_stages,
    review_unified_timing,
    reviewed_crowd_gt_conflict,
    reviewed_meta_labels,
    reviewed_persistent_disagreement,
    reviewed_semi_mechanisms,
    reviewed_worker_viewpoints,
    semi_required_sample_projection,
)
from tools.thesis_main.analysis.materialize_full_uncertainty_data_mining import (
    coverage_summary,
    data_dictionary,
    deep_associations,
    semi_precision_projection,
    source_provenance,
    time_analysis,
)

DEFAULT_OUT = ROOT / "analysis_results" / "full_uncertainty_data_mining_20260821_v2"
SEED = 20260821


def force_c1_process_fields(unified: pd.DataFrame) -> pd.DataFrame:
    """Use the reviewed C1 classification for process/provenance descriptors."""
    classification = read_csv(V2 / "ROW_INCLUSION_CLASSIFICATION.csv")
    if classification.empty:
        return unified
    fields = [
        "canonical_annotation_id", "assignment_provenance", "primary_exclusion_class",
        "secondary_exclusion_flags", "worker_process_class", "formal_use_allowed",
        "task_final_scope", "geometry_reference_status", "iou_to_gt",
        "worker_caused_structural_failure",
    ]
    fields = [field for field in fields if field in classification]
    selected = classification[fields].drop_duplicates("canonical_annotation_id").copy()
    selected["canonical_annotation_id"] = selected["canonical_annotation_id"].map(clean)
    mask = unified["stage"].eq("C1")
    c1 = unified.loc[mask].copy()
    c1["canonical_annotation_id"] = c1["canonical_annotation_id"].map(clean)
    c1 = c1.merge(selected, how="left", on="canonical_annotation_id", suffixes=("", "_reviewed"))
    for field in fields:
        if field == "canonical_annotation_id":
            continue
        reviewed = f"{field}_reviewed"
        if reviewed not in c1:
            continue
        values = c1[reviewed].astype(str)
        usable = values.map(clean).ne("")
        if field not in c1:
            c1[field] = ""
        c1.loc[usable, field] = values.loc[usable]
        c1 = c1.drop(columns=[reviewed])
    return pd.concat([unified.loc[~mask], c1], ignore_index=True, sort=False)


def extend_dictionary() -> pd.DataFrame:
    base = data_dictionary()
    rows = [
        ("active_time_candidate_seconds", "活跃时间候选值", "阶段表原始提供的时间值；若来源是 lead_time fallback/proxy，仅保留审计，不进入 active-time 结果", "source field before proxy exclusion"),
        ("active_time_measurement_class", "活跃时间测量类别", "formal_frozen、direct_observed_nonformal、lead_time_proxy_excluded 或 missing", "classification from source and eligibility"),
        ("group_response_coverage", "元标签组响应覆盖率", "在同一任务条件下实际出现该元标签组的响应数除以全部响应数", "group_response_count / total_response_count"),
        ("positive_share_among_group_responders", "组内阳性选择比例", "选择该标签的响应数除以明确回答该元标签组的响应数", "positive_response_count / group_response_count"),
        ("unasserted_response_count", "未声明响应数", "该任务条件的全部响应中未出现相应元标签组的数量；不视为明确否定", "total_response_count - group_response_count"),
        ("supported_cluster_count", "受支持几何簇数量", "成员数至少为 2 的几何簇数量", "count_m(cluster_support_m >= 2)"),
        ("singleton_cluster_count", "单例几何簇数量", "只有 1 名工人支持的几何簇数量", "count_m(cluster_support_m == 1)"),
        ("crowd_gt_relationship", "人群簇与 GT 关系类别", "根据簇支持量及簇内 GT IoU 描述最大簇、受支持非最大簇和单例异议的关系", "descriptive rule; thresholds are displayed in table"),
        ("strong_persistent_split", "强持续分裂", "在最大已观察支持量下至少两个受支持簇，且最大簇占比低于 80%", "supported_multimodal AND largest_cluster_share < 0.8"),
        ("strong_at_all_thresholds", "跨阈值强分裂", "在 0.90、0.925、0.95 三个几何阈值下均为强分裂", "logical AND across three thresholds"),
        ("observed_worker_rate_variance", "工人观点比例方差", "各工人在重复任务中进入某模式的比例在工人间的方差", "Var_u(mean_t indicator_{u,t})"),
        ("permutation_p_value", "任务内置换 p 值", "在每个 task-condition 内随机重排模式成员后，模拟得到不小于观测工人间方差的概率", "(1 + extreme permutations)/(1 + permutations)"),
        ("median_split_half_spearman", "随机任务半分可靠性中位数", "随机将 Manual 任务分两半，比较工人最大模式率的 Spearman 相关并对重复分割取中位数", "median_b Spearman(rate_u,left_b, rate_u,right_b)"),
        ("approximate_total_independent_buildings_for_80pct_power", "约 80% 功效所需独立建筑总数", "使用当前 building-level 效应标准差的正态近似", "ceil(((z_.975+z_.80)*sd_building/effect)^2)"),
        ("probability_observe_at_least_two_minority", "至少观察两名少数模式的概率", "真实少数模式比例 p、独立抽样 k 人时得到至少两名少数模式", "1-(1-p)^k-kp(1-p)^(k-1)"),
    ]
    extra = pd.DataFrame(rows, columns=["variable_en", "variable_zh", "meaning_zh", "approximate_formula"])
    return pd.concat([base, extra], ignore_index=True).drop_duplicates("variable_en", keep="last")


def reviewed_provenance() -> pd.DataFrame:
    base = source_provenance()
    additions = [
        PERSISTENT / "PERSISTENT_DISAGREEMENT_THRESHOLD_ROBUSTNESS.csv",
        ROOT / "analysis_results" / "calibration_dual_track_processing_20260815_v3" / "task_feature_matrix.csv",
        V2 / "QUALITY_AUXILIARY.csv",
        V2 / "POPULATION_TASK_METRICS.csv",
    ]
    rows = []
    existing = set(base.get("path", pd.Series(dtype=str)))
    for path in additions:
        relative = path.relative_to(ROOT).as_posix()
        if relative in existing:
            continue
        rows.append({
            "path": relative, "exists": path.is_file(),
            "size_bytes": path.stat().st_size if path.is_file() else np.nan,
            "sha256": sha256_file(path) if path.is_file() else "",
        })
    return pd.concat([base, pd.DataFrame(rows)], ignore_index=True, sort=False)


def meta_group_summary(meta_tasks: pd.DataFrame) -> pd.DataFrame:
    if meta_tasks.empty:
        return pd.DataFrame()
    return meta_tasks.groupby(["stage", "condition", "meta_group"], dropna=False).agg(
        task_condition_count=("base_task_id", "size"),
        group_response_count=("group_response_count", "sum"),
        total_response_count=("total_response_count", "sum"),
        mean_group_response_coverage=("group_response_coverage", "mean"),
        mean_pairwise_jaccard=("pairwise_jaccard_mean", "mean"),
        median_pairwise_jaccard=("pairwise_jaccard_median", "median"),
        mean_label_entropy=("mean_label_entropy", "mean"),
        mean_label_cardinality=("mean_label_cardinality", "mean"),
    ).reset_index()


def geometry_stage_summary(geometry_tasks: pd.DataFrame) -> pd.DataFrame:
    if geometry_tasks.empty:
        return pd.DataFrame()
    return geometry_tasks.groupby(["stage", "condition"], dropna=False).agg(
        task_count=("base_task_id", "nunique"),
        geometry_computable_worker_count=("geometry_computable_worker_count", "sum"),
        geometry_missing_worker_count=("geometry_missing_worker_count", "sum"),
        multiple_topology_task_count=("geometry_uncertainty_class", lambda values: sum(value == "multiple_topologies" for value in values)),
        single_topology_task_count=("geometry_uncertainty_class", lambda values: sum(value == "single_topology_continuous_dispersion" for value in values)),
        not_evaluable_task_count=("geometry_uncertainty_class", lambda values: sum(value == "not_evaluable_lt2_geometry" for value in values)),
        median_topology_entropy=("topology_shannon_entropy", "median"),
        median_largest_topology_share=("largest_topology_share", "median"),
        median_same_topology_cyclic_rmse=("same_topology_cyclic_rmse_median", "median"),
    ).reset_index()


def append_task_risk_associations(associations: pd.DataFrame, task_table: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    features = read_csv(ROOT / "analysis_results" / "calibration_dual_track_processing_20260815_v3" / "task_feature_matrix.csv")
    if features.empty or task_table.empty:
        return associations, task_table
    keep = [column for column in ["base_task_id", "risk", "risk_design_score_A", "ordinary_stress", "design_stratum", "feature_timing"] if column in features]
    features = features[keep].drop_duplicates("base_task_id")
    for column in ("risk", "risk_design_score_A"):
        if column in features:
            features[column] = pd.to_numeric(features[column], errors="coerce")
    task = task_table.merge(features, how="left", on="base_task_id")
    rows = []
    for risk_column in ("risk", "risk_design_score_A"):
        if risk_column not in task:
            continue
        usable = task[[risk_column, "geometry_entropy"]].dropna()
        rho = float(stats.spearmanr(usable[risk_column], usable["geometry_entropy"]).statistic) if len(usable) >= 5 and usable[risk_column].nunique() > 1 and usable["geometry_entropy"].nunique() > 1 else np.nan
        rows.append({
            "analysis_level": "task", "predictor": risk_column, "outcome": "geometry_entropy",
            "spearman_rho": rho, "row_count": len(usable), "building_count": task.loc[usable.index, "building_id"].nunique() if "building_id" in task else np.nan,
            "status": "descriptive_association" if pd.notna(rho) else "not_evaluable",
            "interpretation_boundary": "frozen pre-task risk association; not worker specialization or causal effect",
        })
    return pd.concat([associations, pd.DataFrame(rows)], ignore_index=True, sort=False), task


def image_map(raw: pd.DataFrame) -> dict[str, str]:
    result: dict[str, str] = {}
    for row in raw.itertuples(index=False):
        task = clean(getattr(row, "base_task_id", ""))
        image = clean(getattr(row, "image_reference", ""))
        if task and image and task not in result:
            result[task] = image
    return result


def reviewed_case_catalog(
    raw: pd.DataFrame,
    high_persistent: pd.DataFrame,
    meta_tasks: pd.DataFrame,
    geometry_tasks: pd.DataFrame,
    gt_conflict: pd.DataFrame,
    memberships: pd.DataFrame,
    time_frame: pd.DataFrame,
    semi_task: pd.DataFrame,
) -> pd.DataFrame:
    images = image_map(raw)
    rows: list[dict[str, Any]] = []

    def add(category: str, task: str, stage: str, condition: str, values: dict[str, Any], detail: str) -> None:
        rows.append({
            "case_category": category,
            "base_task_id": task,
            "image_reference": images.get(task, f"{task}.jpg" if task else ""),
            "stage": stage, "condition": condition, "detail_zh": detail,
            "evidence_values_json": json.dumps(values, ensure_ascii=False, sort_keys=True, default=str),
        })

    population = read_csv(V2 / "POPULATION_TASK_METRICS.csv")
    if not population.empty:
        population["threshold"] = pd.to_numeric(population["threshold"], errors="coerce")
        population["delta_shannon_entropy"] = pd.to_numeric(population["delta_shannon_entropy"], errors="coerce")
        target = population[population["population"].eq("all_canonical_planned") & np.isclose(population["threshold"], 0.95)].dropna(subset=["delta_shannon_entropy"])
        for _, item in target.nsmallest(6, "delta_shannon_entropy").iterrows():
            add("semi_uncertainty_compression", item.base_task_id, "C1", "manual_vs_semi", item.to_dict(), "Semi 的等支持量模式熵低于 Manual；这表示分布集中，不自动表示质量提高。")
        for _, item in target.nlargest(6, "delta_shannon_entropy").iterrows():
            add("semi_uncertainty_expansion", item.base_task_id, "C1", "manual_vs_semi", item.to_dict(), "Semi 的等支持量模式熵高于 Manual；需结合初始 proposal、编辑和 GT 质量。")

    for _, item in high_persistent[high_persistent["strong_persistent_split"]].sort_values(["valid_k", "largest_cluster_share"], ascending=[False, True]).head(15).iterrows():
        add("high_support_persistent_split", item.base_task_id, item.stage, "manual", item.to_dict(), "在该阶段最大已观察支持量、q=.95 下仍有至少两个受支持几何簇。")

    conflict_priority = [
        "supported_multimodal_nonlargest_supported_cluster_better_gt_alignment",
        "supported_multimodal_multiple_gt_aligned_clusters",
        "dominant_with_singleton_dissent_singleton_better_gt_alignment",
        "diffuse_all_singletons_no_supported_crowd_mode",
        "unimodal_low_gt_alignment",
    ]
    if not gt_conflict.empty:
        selected = gt_conflict[gt_conflict["crowd_gt_relationship"].isin(conflict_priority)].copy()
        selected["gap_abs"] = pd.to_numeric(selected["crowd_gt_gap_best_minus_largest"], errors="coerce").abs()
        for _, item in selected.sort_values(["gap_abs", "largest_cluster_support"], ascending=[False, False]).head(18).iterrows():
            add("crowd_gt_relationship", item.base_task_id, "C1", item.condition, item.to_dict(), "Crowd 簇先 GT-blind 形成；该行描述簇支持与 GT 对齐，不自动改写 GT。")

    if not meta_tasks.empty:
        for group_name, group in meta_tasks[meta_tasks["group_response_count"] >= 3].groupby("meta_group"):
            for _, item in group.sort_values(["mean_label_entropy", "pairwise_jaccard_mean"], ascending=[False, True]).head(5).iterrows():
                add("meta_label_uncertainty", item.base_task_id, item.stage, item.condition, item.to_dict(), f"{group_name} 元标签选择分散。")

    if not geometry_tasks.empty:
        selected = geometry_tasks[geometry_tasks["geometry_computable_worker_count"] >= 3].sort_values(
            ["topology_shannon_entropy", "same_topology_cyclic_rmse_median"], ascending=False
        ).head(18)
        for _, item in selected.iterrows():
            add("geometry_uncertainty", item.base_task_id, item.stage, item.condition, item.to_dict(), "角点数量分布或同拓扑坐标离散较高；跨阶段指标为描述性公共尺度。")

    if not time_frame.empty:
        for category, column in (("active_time_long_tail", "active_time_observed_seconds"), ("lead_time_long_tail", "lead_time_seconds")):
            for _, item in time_frame.dropna(subset=[column]).sort_values(column, ascending=False).head(10).iterrows():
                add(category, item.base_task_id, item.stage, item.condition, {
                    "worker_id": item.worker_id, column: item[column],
                    "active_time_measurement_class": item.active_time_measurement_class,
                    "active_time_source": item.active_time_source,
                    "lead_time_source": item.lead_time_source,
                }, "时间长尾案例；active time 与 lead time 分开。")
        ratios = time_frame.dropna(subset=["active_to_lead_ratio"]).copy()
        ratios["ratio_log_abs"] = np.abs(np.log(np.clip(ratios["active_to_lead_ratio"], 1e-9, None)))
        for _, item in ratios.sort_values("ratio_log_abs", ascending=False).head(12).iterrows():
            add("active_lead_divergence", item.base_task_id, item.stage, item.condition, {
                "worker_id": item.worker_id, "active_time_seconds": item.active_time_observed_seconds,
                "lead_time_seconds": item.lead_time_seconds, "active_to_lead_ratio": item.active_to_lead_ratio,
            }, "活跃交互时间与界面经过时间明显不同。")

    if not memberships.empty:
        selected = memberships[memberships["is_supported_minority_mode"]].groupby(
            ["base_task_id", "building_id", "condition"], as_index=False
        ).agg(
            minority_worker_ids=("worker_id", lambda values: ";".join(sorted(set(values)))),
            minority_member_count=("worker_id", "size"), cluster_count=("cluster_count", "max"),
        ).sort_values("minority_member_count", ascending=False).head(12)
        for _, item in selected.iterrows():
            add("supported_nonlargest_viewpoint", item.base_task_id, "C1", item.condition, item.to_dict(), "至少两名工人持续支持非最大几何模式；不判断对错。")

    if not semi_task.empty:
        for _, item in semi_task.sort_values("harmful_rate_001", ascending=False).head(8).iterrows():
            add("semi_harmful_revision_concentration", item.base_task_id, "C1", "semi", item.to_dict(), "Semi 编辑中负效用变化比例较高。")

    for task, detail in (
        ("q9vSo1VnCiC_1cd414875b9b4311bc6a179d91e6270d", "高质量初始 proposal 被四名工人全部修改，Semi 最终形成 1/1/1/1；用于 over-correction 与扩散审计。"),
        ("B6ByNegPMKs_5b5bd1eac4e6462d8c6677b90a4cf9a9", "Semi 在 q=.95 下仍单峰，但一名工人的大幅编辑造成明显质量下降；低模式熵不排除个体伤害。"),
        ("wc2JMjhGNzB_55b45b0f19c2460bbcd1fb1c86c6610d", "Manual 为 2/1/1/1，Semi 为 4/4；共享初始化压缩了模式，但部分编辑仍降低质量。"),
    ):
        add("proposal_conditioned_revision", task, "C1", "semi", {}, detail)
    return pd.DataFrame(rows).drop_duplicates(["case_category", "base_task_id", "stage", "condition"]).reset_index(drop=True)


def _md(frame: pd.DataFrame, columns: list[str] | None = None, limit: int | None = None) -> str:
    if frame is None or frame.empty:
        return "无可评价记录。"
    selected = frame.copy()
    if columns:
        selected = selected[[column for column in columns if column in selected]]
    if limit:
        selected = selected.head(limit)
    return selected.to_markdown(index=False)


def build_report(
    coverage: pd.DataFrame,
    active_source: pd.DataFrame,
    current_semi: pd.DataFrame,
    projection: pd.DataFrame,
    required: pd.DataFrame,
    rare: pd.DataFrame,
    meta_summary: pd.DataFrame,
    meta_labels: pd.DataFrame,
    choice_dictionary: pd.DataFrame,
    geometry_summary: pd.DataFrame,
    persistent_summary: pd.DataFrame,
    time_summary: pd.DataFrame,
    time_paired: pd.DataFrame,
    time_relation: pd.DataFrame,
    gt_conflict: pd.DataFrame,
    worker_view: pd.DataFrame,
    viewpoint_tests: pd.DataFrame,
    associations: pd.DataFrame,
    semi_assoc: pd.DataFrame,
    cases: pd.DataFrame,
    provenance: pd.DataFrame,
) -> str:
    q95 = current_semi[current_semi.get("metric", pd.Series(dtype=str)).eq("shannon_entropy")]
    q95_row = q95.iloc[0] if not q95.empty else None
    conflict_counts = gt_conflict["crowd_gt_relationship"].value_counts().rename_axis("crowd_gt_relationship").reset_index(name="task_condition_count") if not gt_conflict.empty else pd.DataFrame()
    paired_summary = time_paired.groupby(["stage", "metric"], dropna=False).agg(
        paired_task_count=("base_task_id", "size"),
        mean_semi_minus_manual_seconds=("semi_minus_manual_seconds", "mean"),
        median_semi_minus_manual_seconds=("semi_minus_manual_seconds", "median"),
        median_semi_to_manual_ratio=("semi_to_manual_ratio", "median"),
    ).reset_index() if not time_paired.empty else pd.DataFrame()
    direct_summary = active_source.groupby(["stage", "condition", "active_time_measurement_class"], dropna=False).agg(
        record_count=("record_count", "sum"), active_direct_count=("active_direct_count", "sum"),
        active_formal_count=("active_formal_count", "sum"), lead_time_count=("lead_time_count", "sum"),
    ).reset_index() if not active_source.empty else pd.DataFrame()

    lines = [
        "# 360° 全景布局标注完整数据整理与不确定性分析报告",
        "",
        "## 1. 数据边界与保留规则",
        "",
        "本报告保留中途退出、行政退出、outside assignment、未进入后续阶段以及旧论文资格不足的记录。每个分析只因其所需变量不可计算而排除。原论文资格、行政身份和 assignment provenance 仍保留为描述字段，但不作为全局删除条件。",
        "",
        "raw annotation version 与 selected/canonical evidence 分开：raw 版本用于元标签、lead time 和修订过程；同一工人的多个版本不作为多个独立工人。任务级几何分布每名工人在同一 task-condition 只贡献一条选定/可审计记录。",
        "",
        "### 1.1 覆盖盘点",
        "",
        _md(coverage),
        "",
        "## 2. Manual 与 Semi-Auto：总体几何不确定性",
        "",
    ]
    if q95_row is not None:
        lines += [
            f"在 q=.95、25 个 paired tasks、9 个 buildings 的全量描述性总体中，任务等权 Shannon 模式熵差（Semi−Manual）为 {float(q95_row['mean_difference']):.6f}，building-cluster 95% CI [{float(q95_row['ci_lower']):.6f}, {float(q95_row['ci_upper']):.6f}]，building exact sign-flip p={float(q95_row['building_exact_sign_flip_p']):.6f}。区间覆盖零。",
            "",
        ]
    lines += [
        _md(current_semi, ["population", "inference_role", "n_tasks", "n_buildings", "metric", "mean_difference", "ci_lower", "ci_upper", "building_exact_sign_flip_p"]),
        "",
        "### 2.1 补充 Semi 数据能否使结论更明确",
        "",
        "同一图增加 Semi 工人数主要改善低频模式的发现概率和每图模式比例估计；总体 Manual/Semi 平均差的区间主要由独立 task/building 数决定。下表使用当前 building-level 方差作正态近似，不是阳性结果保证。",
        "",
        _md(required),
        "",
        _md(projection[projection["assumed_true_absolute_effect"].eq(0.10)], ["projected_independent_building_count", "projected_paired_task_count_if_current_tasks_per_building", "projected_95ci_half_width", "approximate_80pct_minimum_detectable_absolute_effect", "approximate_two_sided_power"]),
        "",
        "若未来数据与当前结构相近，而真实平均效应仍接近当前点估计，增加数据会使结论更精确地接近零附近，而不会机械地产生显著降低。",
        "",
        "### 2.2 少数模式发现",
        "",
        _md(rare[rare["true_minority_mode_share"].isin([0.10, 0.20, 0.30]) & rare["annotation_count_k"].isin([4, 8, 12, 20])]),
        "",
        "## 3. 不同元标签的不确定性",
        "",
        _md(meta_summary),
        "",
        "Pairwise Jaccard 是两名工人标签集合交集/并集的平均；mean label entropy 是各二元标签 Bernoulli 熵的平均。`unasserted_response_count` 单独保留，未声明不被静默编码为明确否定。",
        "",
        "### 3.1 高熵标签实例",
        "",
        _md(meta_labels.sort_values("bernoulli_entropy_among_group_responders", ascending=False), ["stage", "condition", "base_task_id", "meta_group", "choice_code", "choice_label_zh", "positive_response_count", "group_response_count", "total_response_count", "unasserted_response_count", "positive_share_among_group_responders", "bernoulli_entropy_among_group_responders"], 30),
        "",
        "### 3.2 raw choice 映射审计",
        "",
        _md(choice_dictionary, ["meta_group", "choice_code", "choice_label_zh", "from_name", "choice_raw", "response_count", "worker_count", "task_count"], 40),
        "",
        "## 4. 几何标注不确定性",
        "",
        _md(geometry_summary),
        "",
        "跨阶段公共指标使用角点数量作为粗拓扑签名，并在相同角点数内计算循环/反向对齐坐标 RMSE。它用于阶段盘点；C1 模式结论仍使用冻结 boundary/wall-wall similarity 和 complete-link 分区。",
        "",
        "### 4.1 最大已观察支持量下的持续分歧",
        "",
        _md(persistent_summary),
        "",
        "这里的 persistent 只指在当前最大已观察高支持量下仍存在分裂，不表示无限增加工人永不变化。Calibration cap-5 任务没有混入本表。",
        "",
        "## 5. Active time 与 Lead time",
        "",
        "Active time 是脚本记录的活跃交互；Lead time 是 Label Studio 从打开到提交的经过时间。任何 `lead_time_fallback` 或 proxy 值只保留在候选审计字段，不进入 active-time 结果。",
        "",
        "### 5.1 时间来源与覆盖",
        "",
        _md(direct_summary),
        "",
        "### 5.2 分布",
        "",
        _md(time_summary),
        "",
        "### 5.3 同阶段同图 Manual/Semi 配对",
        "",
        _md(paired_summary),
        "",
        "### 5.4 Active/Lead 关系",
        "",
        _md(time_relation),
        "",
        "跨阶段合并仅在模型中显式保留 stage/source；不同脚本版本不被假定为完全同质。时间模型是调整后的关联，不是随机化因果效应。",
        "",
        "## 6. 工人共识与 GT 冲突",
        "",
        _md(conflict_counts),
        "",
        "Crowd 几何簇先在不读取 GT 的情况下形成，再计算簇成员相对 operational GT 的 IoU。支持量至少 2 才称为受支持簇；全单例和单例异议不再称作‘少数模式’。多数簇不自动替换 GT。",
        "",
        _md(gt_conflict.sort_values("crowd_gt_gap_best_minus_largest", ascending=False), ["base_task_id", "condition", "task_crowd_structure_status", "largest_cluster_support", "second_cluster_support", "supported_cluster_count", "singleton_cluster_count", "largest_cluster_median_iou", "best_cluster_rank", "best_cluster_support", "best_cluster_median_iou", "crowd_gt_gap_best_minus_largest", "crowd_gt_relationship"], 30),
        "",
        "## 7. 工人是否形成稳定不同观点",
        "",
        _md(viewpoint_tests),
        "",
        _md(worker_view.sort_values("task_count", ascending=False), ["worker_id", "task_count", "building_count", "manual_task_count", "semi_task_count", "largest_mode_rate", "supported_minority_mode_rate", "mean_task_centered_n_pairs", "median_task_centered_n_pairs"], 30),
        "",
        "观点倾向检验不判断哪种模式正确，也不能自动区分协议理解、视觉策略和能力。随机任务半分只用于内部重复性描述，不是独立外部验证。",
        "",
        "## 8. 其他值得关注的数据关系",
        "",
        _md(associations),
        "",
        "### 8.1 模型 proposal、编辑与不确定性变化",
        "",
        _md(semi_assoc),
        "",
        "这些关系均为描述性关联。edit magnitude、active time、risk、meta labels 与几何熵受到 task、worker、building 和阶段组成影响，不能由相关系数推断因果。",
        "",
        "## 9. 具体图片/任务案例",
        "",
        _md(cases, ["case_category", "base_task_id", "image_reference", "stage", "condition", "detail_zh", "evidence_values_json"], 80),
        "",
        "完整案例目录见 `TASK_CASE_CATALOG.csv`。每个案例保存任务/图片 ID、阶段、条件、计算值和中性说明。",
        "",
        "## 10. 当前数据不能支持的结论",
        "",
        "1. C1 Manual/Semi 分配不是完整图像级随机试验，因此差异是关联而非因果。",
        "2. 25 个 paired tasks 只覆盖 9 个 buildings；目前不能声称高难度图上的 Semi 效应，因为冻结 pre-assignment difficulty 特征没有形成可用分层。",
        "3. 多峰可能混合图像可观测性、协议、工人错误、表示限制和聚类阈值效应；本报告没有把多峰自动命名为固有 aleatoric uncertainty。",
        "4. Active time 与 lead time 是不同构念；lead-time fallback 已从 active outcome 中删除。",
        "5. 工人 viewpoint 倾向不能自动转化为质量排名。",
        "6. Crowd majority 与 operational GT 均可能受协议或参考问题影响；冲突只触发独立审查。",
        "7. 任何增加 Semi 数据的功效投影依赖当前方差和未来独立 building 的可比性。",
        "",
        "## 11. 变量、计算和可复现性",
        "",
        "全部英文变量的中文名称、含义和近似公式见 `DATA_DICTIONARY_ZH.csv`；输入文件 SHA 见 `INPUT_PROVENANCE.csv`；输出 SHA 见 `OUTPUT_MANIFEST.csv`。",
        "",
        _md(provenance),
    ]
    return "\n".join(lines) + "\n"


def make_reviewed_plots(out: Path, required: pd.DataFrame, meta_summary: pd.DataFrame, geometry_summary: pd.DataFrame, time_summary: pd.DataFrame) -> None:
    if not required.empty:
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.plot(required["assumed_true_absolute_entropy_effect"], required["approximate_total_independent_buildings_for_80pct_power"], marker="o")
        ax.set_xlabel("Assumed true absolute entropy effect")
        ax.set_ylabel("Approximate independent buildings")
        ax.set_title("Semi uncertainty effect: approximate sample requirement")
        fig.tight_layout()
        fig.savefig(out / "SEMI_REQUIRED_BUILDINGS.png", dpi=180)
        plt.close(fig)
    if not meta_summary.empty:
        summary = meta_summary.groupby("meta_group", as_index=False)["mean_label_entropy"].mean()
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.bar(summary["meta_group"], summary["mean_label_entropy"])
        ax.set_ylabel("Mean label entropy")
        ax.set_title("Meta-label uncertainty by group")
        ax.tick_params(axis="x", rotation=30)
        fig.tight_layout()
        fig.savefig(out / "META_LABEL_UNCERTAINTY.png", dpi=180)
        plt.close(fig)
    if not geometry_summary.empty:
        fig, ax = plt.subplots(figsize=(10, 5))
        labels = geometry_summary["stage"].astype(str) + "/" + geometry_summary["condition"].astype(str)
        ax.bar(labels, geometry_summary["median_topology_entropy"])
        ax.set_ylabel("Median topology entropy")
        ax.set_title("Cross-stage geometry uncertainty")
        ax.tick_params(axis="x", rotation=45)
        fig.tight_layout()
        fig.savefig(out / "GEOMETRY_UNCERTAINTY_BY_STAGE.png", dpi=180)
        plt.close(fig)
    if not time_summary.empty:
        active = time_summary[time_summary["metric"].eq("active_time")]
        fig, ax = plt.subplots(figsize=(11, 5))
        labels = active["stage"].astype(str) + "/" + active["condition"].astype(str)
        ax.bar(labels, active["median_seconds"])
        ax.set_ylabel("Median active seconds")
        ax.set_title("Direct observed active time by stage and mode")
        ax.tick_params(axis="x", rotation=45)
        fig.tight_layout()
        fig.savefig(out / "ACTIVE_TIME_STAGE_MODE.png", dpi=180)
        plt.close(fig)


def materialize(out: Path) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    raw = normalise_raw_stages(load_raw_annotation_fact())
    unified, active_source = review_unified_timing(load_unified_stage_submissions(), raw)
    unified = force_c1_process_fields(unified)

    coverage = coverage_summary(unified, raw)
    geometry_tasks, geometry_pairs = cross_stage_geometry_uncertainty(unified)
    geometry_summary = geometry_stage_summary(geometry_tasks)
    meta_long, meta_responses, meta_tasks, meta_labels, choice_dictionary = reviewed_meta_labels(raw)
    meta_summary = meta_group_summary(meta_tasks)
    persistent_high, persistent_robust, persistent_summary = reviewed_persistent_disagreement()
    gt_conflict, gt_clusters = reviewed_crowd_gt_conflict()
    memberships, worker_view, cotendency, viewpoint_tests, excluded_view = reviewed_worker_viewpoints()
    time_frame, time_summary, time_paired, time_relation, time_outliers_models = time_analysis(unified)
    projection, rare, current_semi = semi_precision_projection()
    required = semi_required_sample_projection(projection)
    associations, task_table, mechanism = deep_associations(unified, meta_tasks, gt_conflict)
    associations, task_table = append_task_risk_associations(associations, task_table)
    semi_task, semi_assoc, semi_review_task = reviewed_semi_mechanisms()
    cases = reviewed_case_catalog(raw, persistent_high, meta_tasks, geometry_tasks, gt_conflict, memberships, time_frame, semi_task)
    dictionary = extend_dictionary()
    provenance = reviewed_provenance()

    outputs = {
        "UNIFIED_SUBMISSION_EVIDENCE_REVIEWED.csv": unified,
        "DATA_COVERAGE_BY_STAGE_MODE.csv": coverage,
        "ACTIVE_TIME_SOURCE_AUDIT.csv": active_source,
        "RAW_META_LABEL_RESPONSE_LONG.csv": meta_long,
        "RAW_META_LABEL_RESPONSE_SETS.csv": meta_responses,
        "META_LABEL_TASK_UNCERTAINTY.csv": meta_tasks,
        "META_LABEL_TASK_LABEL_COUNTS.csv": meta_labels,
        "META_LABEL_CHOICE_DICTIONARY.csv": choice_dictionary,
        "META_LABEL_STAGE_MODE_SUMMARY.csv": meta_summary,
        "GEOMETRY_TASK_UNCERTAINTY_ALL_STAGES.csv": geometry_tasks,
        "GEOMETRY_PAIRWISE_DISPERSION_ALL_STAGES.csv": geometry_pairs,
        "GEOMETRY_STAGE_MODE_SUMMARY.csv": geometry_summary,
        "PERSISTENT_DISAGREEMENT_HIGH_SUPPORT_Q095.csv": persistent_high,
        "PERSISTENT_DISAGREEMENT_HIGH_SUPPORT_ROBUSTNESS.csv": persistent_robust,
        "PERSISTENT_DISAGREEMENT_HIGH_SUPPORT_SUMMARY.csv": persistent_summary,
        "C1_CROWD_GT_CONFLICT_TASKS.csv": gt_conflict,
        "C1_CROWD_GT_CLUSTER_METRICS.csv": gt_clusters,
        "C1_WORKER_TASK_MODE_MEMBERSHIP.csv": memberships,
        "WORKER_VIEWPOINT_STABILITY.csv": worker_view,
        "WORKER_VIEWPOINT_COTENDENCY.csv": cotendency,
        "WORKER_VIEWPOINT_TESTS.csv": viewpoint_tests,
        "EXCLUDED_WORKER_PEER_EVIDENCE.csv": excluded_view,
        "TIME_SUBMISSION_EVIDENCE_REVIEWED.csv": time_frame,
        "TIME_STAGE_MODE_SUMMARY.csv": time_summary,
        "TIME_MANUAL_SEMI_TASK_PAIRS.csv": time_paired,
        "TIME_ACTIVE_LEAD_RELATION.csv": time_relation,
        "TIME_OUTLIERS_AND_MODELS.csv": time_outliers_models,
        "CURRENT_MANUAL_SEMI_UNCERTAINTY_SUMMARY.csv": current_semi,
        "SEMI_DATA_PRECISION_PROJECTION.csv": projection,
        "SEMI_REQUIRED_BUILDINGS_BY_EFFECT.csv": required,
        "RARE_MODE_DETECTION_PROBABILITY.csv": rare,
        "DEEP_MINING_ASSOCIATIONS.csv": associations,
        "DEEP_MINING_TASK_TABLE.csv": task_table,
        "DEEP_MINING_WORKER_AND_LEGACY_MECHANISM_TABLES.csv": mechanism,
        "SEMI_PROPOSAL_TASK_TABLE.csv": semi_task,
        "SEMI_PROPOSAL_ASSOCIATIONS.csv": semi_assoc,
        "SEMI_REVIEW_TASK_SUMMARY.csv": semi_review_task,
        "TASK_CASE_CATALOG.csv": cases,
        "DATA_DICTIONARY_ZH.csv": dictionary,
        "INPUT_PROVENANCE.csv": provenance,
    }
    for name, frame in outputs.items():
        write_csv(out / name, frame)

    report = build_report(
        coverage, active_source, current_semi, projection, required, rare,
        meta_summary, meta_labels, choice_dictionary, geometry_summary,
        persistent_summary, time_summary, time_paired, time_relation,
        gt_conflict, worker_view, viewpoint_tests, associations, semi_assoc,
        cases, provenance,
    )
    (out / "FULL_UNCERTAINTY_DATA_REPORT_ZH.md").write_text(report, encoding="utf-8")
    make_reviewed_plots(out, required, meta_summary, geometry_summary, time_summary)

    c1 = unified[unified["stage"].eq("C1")]
    run_summary = {
        "git_head": git_head(),
        "selected_or_auditable_record_count": len(unified),
        "raw_annotation_version_count": len(raw),
        "worker_count": int(unified["worker_id"].nunique()),
        "base_task_count": int(unified["base_task_id"].nunique()),
        "stage_count": int(unified["stage"].nunique()),
        "c1_context_count": len(c1),
        "c1_worker_count": int(c1["worker_id"].nunique()),
        "c1_w014_context_count": int(c1["worker_id"].eq("14").sum()),
        "c1_outside_assignment_count": int(c1["assignment_provenance"].eq("outside_assignment_submission").sum()),
        "active_direct_observed_count": int(unified["active_time_observed_seconds"].notna().sum()),
        "active_proxy_excluded_count": int(unified["active_time_proxy_excluded"].sum()),
        "lead_time_observed_count": int(unified["lead_time_seconds"].notna().sum()),
        "meta_label_choice_count": len(meta_long),
        "geometry_task_condition_count": len(geometry_tasks),
        "high_support_persistent_task_count": int(persistent_high["base_task_id"].nunique()),
        "crowd_gt_task_condition_count": len(gt_conflict),
        "worker_viewpoint_supported_worker_count": int((worker_view["task_count"] >= 5).sum()) if not worker_view.empty else 0,
        "data_mining_population_rule": "retain all records; exclude only if requested variable is not computable",
        "lead_time_used_as_active_time_fallback": False,
        "lead_time_proxy_values_retained_for_audit_only": True,
        "later_stage_eligibility_used_as_global_filter": False,
        "report_version": "reviewed_v2",
    }
    if run_summary["c1_outside_assignment_count"] < 6:
        raise AssertionError(f"outside-assignment evidence not fully retained: {run_summary['c1_outside_assignment_count']}")
    if run_summary["lead_time_observed_count"] < 2400:
        raise AssertionError("Label Studio lead-time coverage unexpectedly low")
    write_json(out / "RUN_SUMMARY.json", run_summary)
    write_csv(out / "OUTPUT_MANIFEST.csv", manifest_for_directory(out))
    print(json.dumps(run_summary, indent=2, sort_keys=True))
    return run_summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    materialize(args.output_dir.resolve())


if __name__ == "__main__":
    main()
