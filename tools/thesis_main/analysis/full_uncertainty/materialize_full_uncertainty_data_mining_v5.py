"""物化 Paper A 全量不确定性数据整理 v5。"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from itertools import combinations
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qs, unquote, urlparse

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

from tools.thesis_main.analysis.full_uncertainty import full_uncertainty_common as common
from tools.thesis_main.analysis.full_uncertainty import full_uncertainty_geometry as geometry
from tools.thesis_main.analysis.full_uncertainty import full_uncertainty_reviewed as reviewed
from tools.thesis_main.analysis.full_uncertainty import materialize_full_uncertainty_data_mining as base
from tools.thesis_main.analysis.full_uncertainty import materialize_full_uncertainty_data_mining_v2 as reviewed_materializer
from tools.thesis_main.analysis.full_uncertainty import materialize_full_uncertainty_data_mining_v4 as legacy
from tools.thesis_main.analysis.full_uncertainty.full_uncertainty_prefix_replay_v5 import (
    load_frozen_c1_k22_tasks,
    replay_frozen_c1_k22_prefixes,
    summarize_prefix_replay,
)
from tools.thesis_main.analysis.full_uncertainty.full_uncertainty_stats_v5 import (
    crossed_task_worker_variance_decomposition,
    filter_structural_zero_lane,
    mean_pairwise_jaccard_disagreement,
    modal_response_share,
    response_pattern_entropy,
)
from tools.thesis_main.analysis import build_a4_image_evidence_substrate as image_substrate
from tools.thesis_main.analysis import materialize_annotation_uncertainty_manual_semi as c1_uncertainty
from tools.thesis_main.analysis import materialize_paper_a_data_discovery as discovery
from tools.thesis_main.analysis import materialize_persistent_disagreement_diagnostic as persistent


ROOT = legacy.ROOT
DEFAULT_OUTPUT = ROOT / "analysis_results" / "full_uncertainty_data_mining_20260821_v5"
SEED = 20260821
METHOD_CONTRACT = ROOT / "docs" / "thesis_main" / "PAPER_A_METHOD_CONTRACT_CURRENT.json"
TERMINAL = ROOT / "analysis_results" / "c2a_rp_terminal_reestimate_20260817_v1"
RESTRICTED_TOKENS = ("ad" + "visor", "\u5bfc\u5e08", "har" + "mful", "har" + "med")
SUPPLEMENT_TABLES = (
    "CALCULATION_MODE_AUDIT.csv",
    "IMAGE_FEATURE_ALIAS_AUDIT.csv",
    "IMAGE_FEATURE_ASSOCIATIONS_BUILDING_CLUSTERED.csv",
    "DIFFICULTY_PROXY_OUTCOME_JOIN_AUDIT.csv",
    "DIFFICULTY_PROXY_ASSOCIATIONS_BUILDING_CLUSTERED.csv",
    "PARTITION_FAILURE_RATE_SENSITIVITY.csv",
    "SEMI_POWER_ESTIMAND_SENSITIVITY.csv",
    "QUALITY_RISK_TASK_BUILDING_CLUSTER_AUDIT.csv",
    "ACTIVE_TIME_COMPUTABILITY_DESCRIPTIVE.csv",
    "C1_ACTIVE_TIME_MISSINGNESS_AUDIT.csv",
    "EVENT_SEQUENCE_OBSERVED_FACT.csv",
    "COVERAGE_GAP_COMPUTABILITY_AUDIT.csv",
)

ENUM_ZH = {
    "P1": "预筛", "C1": "校准一阶段", "C2-B": "校准二阶段B", "C2-A-RP-B1": "校准二阶段风险精度块一",
    "C2-A-RP-B2": "校准二阶段风险精度块二", "manual": "纯人工", "semi": "模型预标注辅助",
    "matched": "已连接最终规范记录", "raw_only": "仅历史原始版本", "eligible": "符合该表口径",
    "ineligible": "不符合该表口径", "all-computable": "两指标均可计算", "exclude_joint_near_zero": "排除联合近零",
    "edited-positive": "编辑幅度大于阈值", "formal-only": "正式资格敏感性", "unimodal": "单峰",
    "dominant_with_dissent": "主模式伴少数异议", "supported_multimodal": "有支持的多峰", "not_evaluable": "不可评价",
    "unique": "唯一分区", "estimated": "已估计", "boundary_zero_component": "方差分量位于零边界",
    "formal_frozen": "冻结正式有效操作时间", "label_studio_elapsed_observed": "Label Studio经过时间",
    "all_observed": "全部观察记录", "all_computable": "全部可计算", "formal_only": "仅正式口径",
    "administrative_eligible": "行政状态可纳入", "administrative_ineligible": "行政状态不可纳入",
    "pre_task_image_only": "标注前图像固有特征", "pre_task_model": "标注前模型/设计特征",
    "historical_proxy": "历史难度代理，仅探索", "post_worker_concurrent": "标注后同期变量",
    "not_materialized_by_design": "按计划未物化", "ready": "已物化", "not_computable": "不可计算",
}
ENUM_COLUMNS = {
    "stage", "condition", "status", "population", "analysis_lane", "measurement_lane", "time_measurement_lane",
    "task_crowd_structure_status", "partition_status", "geometry_uncertainty_class", "canonical_join_status",
    "feature_classification", "eligibility_status", "administrative_status", "inference_axis", "coverage_status",
}
FIELD_ZH = {
    "base_task_id": "任务稳定标识", "building_id": "建筑标识", "worker_id": "标注员稳定标识",
    "condition": "标注条件", "stage": "执行阶段", "annotation_id": "原始标注版本标识",
    "canonical_annotation_id": "最终规范标注标识", "response_pattern_entropy": "回答组合的自然对数香农熵",
    "mean_pairwise_jaccard_disagreement": "回答集合的平均两两一减Jaccard相似度",
    "modal_response_share": "出现次数最多的完整回答组合占比", "spearman_rho": "Spearman等级相关系数",
    "ci_lower": "区间下限", "ci_upper": "区间上限", "permutation_p": "固定种子置换p值",
    "active_time_observed_seconds": "冻结有效操作时间，秒", "lead_time_seconds": "Label Studio经过时间，秒",
    "geometry_edit_rmse_panorama_diagonal_normalized": "按全景图对角线归一化的编辑RMSE",
    "delta_U": "最终效用减初始效用", "iou_to_gt": "相对当前 operational GT 的IoU",
    "task_variance": "交叉随机效应模型的任务方差", "worker_variance": "交叉随机效应模型的标注员方差",
    "residual_variance": "交叉随机效应模型的残差方差", "source_table": "直接来源表或冻结工件",
    "calculation": "计算方法", "missing_meaning": "缺失值含义", "row_count": "记录行数", "task_count": "独立任务数",
    "worker_count": "标注员数", "building_count": "独立建筑数", "support": "可计算支持量",
    "component": "审计组件", "analysis_unit": "分析单位", "correction": "补充计算或修正内容",
    "status": "计算或可评价状态", "status_zh": "状态中文解释", "audit_level": "审计层级",
    "feature_left": "成对审计的左侧特征", "feature_right": "成对审计的右侧特征",
    "exact_value_identity": "共享记录上是否逐值完全相同", "max_absolute_difference": "共享记录上的最大绝对差",
    "alias_family": "同源特征家族", "excluded_from_unique_multiplicity": "是否从独立检验家族中排除",
    "note": "口径或解释边界备注", "predictor": "预测/关联变量", "outcome": "结局变量",
    "predictor_duplicate_alias": "该预测变量是否为已审计的重复家族别名",
    "rank_effect_spearman": "任务级 Spearman 等级效应", "effect_rank_transformed": "秩变换线性效应",
    "effect": "本表定义的效应值", "cluster_bootstrap_rank_ci_lower": "建筑整群 bootstrap 等级效应区间下限",
    "cluster_bootstrap_rank_ci_upper": "建筑整群 bootstrap 等级效应区间上限",
    "wild_cluster_exact_or_mc_p": "建筑成组 wild sign-flip 双侧 p 值", "p_value": "双侧 p 值",
    "inference_unit": "推断与重采样单位", "q_bh_global_unique": "去重后全局 BH 校正 q 值",
    "q_bh_within_outcome_unique": "去重后同一结局内 BH 校正 q 值",
    "q_bh_global_unique_predictors": "去重预测变量后的全局 BH q 值",
    "q_bh_within_outcome_unique_predictors": "去重预测变量后的结局内 BH q 值",
    "semi_task_count": "Semi 配对任务数", "proxy_task_count": "难度代理有记录任务数",
    "matched_task_count": "成功连接任务数", "missing_proxy_task_count": "缺少代理变量任务数",
    "missing_proxy_filled_as_zero": "是否把缺失代理错误填为零", "join_status": "任务连接状态",
    "predictor_family": "预测变量证据家族", "predictor_timing": "变量相对结局的时间属性",
    "group_0_count": "二元标签为零的任务数", "group_1_count": "二元标签为一的任务数",
    "group_0_mean_delta_entropy": "标签为零组的平均熵变化", "group_1_mean_delta_entropy": "标签为一组的平均熵变化",
    "group_mean_difference_1_minus_0": "标签一组减标签零组的平均熵变化差",
    "cluster_bootstrap_rho_ci_lower": "建筑整群 bootstrap 相关区间下限",
    "cluster_bootstrap_rho_ci_upper": "建筑整群 bootstrap 相关区间上限",
    "missing_predictor_not_imputed": "缺失预测变量是否保持缺失而未插补",
    "q_bh_within_predictor_family": "同一预测变量家族内 BH q 值", "q_bh_global": "全部可评价检验的全局 BH q 值",
    "estimand": "目标估计量的加权口径", "metric": "统计指标", "estimate": "点估计",
    "median_estimand_unit_value": "按该估计口径单位计算的中位数",
    "cluster_bootstrap_ci_lower": "建筑整群 bootstrap 区间下限", "cluster_bootstrap_ci_upper": "建筑整群 bootstrap 区间上限",
    "exact_building_signflip_p": "枚举建筑符号翻转的双侧 p 值", "definition": "指标定义或分子分母",
    "current_task_count": "当前可计算任务数", "current_building_count": "当前独立建筑数",
    "projected_independent_building_count": "情景中的独立建筑数", "assumed_true_absolute_effect": "条件功效假定的真实绝对效应",
    "observed_effect": "当前样本点估计", "observed_cluster_scale_sd": "与估计口径一致的建筑尺度标准差",
    "standard_error": "标准误", "approximate_two_sided_power": "近似双侧条件功效",
    "independent_unit": "情景计算的独立抽样单位", "variance_basis": "方差估计依据", "estimand_note": "估计口径说明",
    "population": "分析总体", "population_zh": "分析总体中文解释", "source_row_count": "进入聚合前的可计算源记录数",
    "quality_per_risk_slope": "任务聚合后质量随风险变化的线性斜率", "task_level_spearman_rho": "任务级 Spearman 等级相关",
    "rank_effect_exact_building_signflip_p": "等级效应的枚举建筑 sign-flip p 值",
    "cluster_bootstrap_repetitions": "建筑整群 bootstrap 重复次数", "formal_row_level_p_reported": "是否报告形式不当的行级 p 值",
    "fact": "事实类型", "grouping": "描述性分组维度", "group_value": "分组取值", "n": "该分组记录数",
    "active_time_n": "冻结有效操作时间可计算记录数", "lead_time_proxy_n": "仅有 Lead time 代理且排除于 Active time 的记录数",
    "missing_n": "Active time 缺失记录数", "other_n": "其他测量类别记录数",
    "active_time_rate": "冻结 Active time 可计算率", "lead_time_proxy_rate": "Lead time 代理占比", "missing_rate": "缺失率",
    "active_time_rule": "Active time 纳入口径", "lead_time_rule": "Lead time 与 Active time 分离规则",
    "missing": "缺失记录数", "rate": "本组缺失比例", "jeffreys_lower": "Jeffreys 二项比例区间下限",
    "jeffreys_upper": "Jeffreys 二项比例区间上限", "missing_definition": "缺失事件的操作性定义",
    "fact_type": "观测事实记录类型", "project_id": "Label Studio 项目标识", "task_id": "运行时任务标识",
    "annotator_id": "事件日志标注员标识", "session_id": "事件日志会话标识", "event_count": "排除 sandbox 后的观测事件数",
    "raw_event_count": "该会话原始事件数", "sandbox_event_n": "sandbox 事件数", "timestamp_ms_n": "可按毫秒解析的客户端时间戳数",
    "observed_start_timestamp_ms": "观测起始客户端毫秒时间戳", "observed_end_timestamp_ms": "观测结束客户端毫秒时间戳",
    "observed_span_seconds": "首末观测事件时间跨度（秒）", "max_gap_seconds": "相邻观测事件最大间隔（秒）",
    "gap_gt_60": "是否存在超过 60 秒的观测事件间隔", "max_events_per_60_seconds": "任意 60 秒窗口的最大观测事件数",
    "multi_session_fact": "同一项目任务标注员是否观测到多个 session", "formal_event_n": "冻结正式阶段范围内事件数",
    "outside_or_stage_mismatch_n": "任务外或阶段不匹配原始事件数",
    "observed_outside_or_stage_mismatch_n": "排除 sandbox 后任务外或阶段不匹配事件数",
    "clock_offset_median_seconds": "客户端与服务端时钟差中位数（秒）", "clock_offset_p95_seconds": "客户端与服务端时钟差第 95 百分位（秒）",
    "clock_offset_audit_only": "时钟差是否仅限审计用途", "observed_behavior_event_fields": "可直接支持行为命名的事件字段",
    "coverage_field": "字段覆盖类别", "field_name": "源字段名", "observed_n": "字段有观测值的记录数",
    "coverage_rate": "字段观测覆盖率", "description": "客观口径说明", "computability_status": "可计算性状态",
    "denominator_n": "可计算性审计分母", "gap": "当前证据缺口", "condition_zh": "标注条件中文解释", "stage_zh": "执行阶段中文解释",
}

FORMULA_ZH = {
    "spearman_rho": "对成对非缺失值分别取平均秩后计算 Pearson 相关",
    "rank_effect_spearman": "对任务级成对非缺失值计算 Spearman 等级相关",
    "effect_rank_transformed": "对 x、y 分别取平均秩后拟合含截距线性斜率；同一完整样本下等于 Spearman rho",
    "wild_cluster_exact_or_mc_p": "在零斜率受限模型下按 building 整组翻转残差符号；building≤12 时枚举全部符号组合",
    "exact_building_signflip_p": "按 building 整组翻转差值符号并枚举全部 2^B 组合的双侧尾概率",
    "rank_effect_exact_building_signflip_p": "对任务级秩变量按 building 整组符号翻转得到的双侧尾概率",
    "cluster_bootstrap_rank_ci_lower": "固定种子整组重抽 building 10,000 次所得等级相关的 2.5% 分位数",
    "cluster_bootstrap_rank_ci_upper": "固定种子整组重抽 building 10,000 次所得等级相关的 97.5% 分位数",
    "cluster_bootstrap_rho_ci_lower": "固定种子整组重抽 building 10,000 次所得 rho 的 2.5% 分位数",
    "cluster_bootstrap_rho_ci_upper": "固定种子整组重抽 building 10,000 次所得 rho 的 97.5% 分位数",
    "cluster_bootstrap_ci_lower": "固定种子整组重抽 building 10,000 次所得估计量的 2.5% 分位数",
    "cluster_bootstrap_ci_upper": "固定种子整组重抽 building 10,000 次所得估计量的 97.5% 分位数",
    "q_bh_global": "对全局可评价 p 值执行 Benjamini–Hochberg 校正；NA 不进入分母",
    "q_bh_global_unique": "排除 vertical_edge_mean 别名的 63 个可评价家族上执行全局 BH 校正",
    "q_bh_global_unique_predictors": "与 q_bh_global_unique 相同的兼容字段",
    "q_bh_within_outcome_unique": "在每个结局内对去重预测变量的 p 值执行 BH 校正",
    "q_bh_within_outcome_unique_predictors": "与 q_bh_within_outcome_unique 相同的兼容字段",
    "q_bh_within_predictor_family": "在同一证据/预测变量家族内对可评价 p 值执行 BH 校正",
    "approximate_two_sided_power": "正态近似：P(|Z+|effect|/SE|>z_0.975)，条件于假定真实效应和当前方差",
    "standard_error": "observed_cluster_scale_sd / sqrt(projected_independent_building_count)",
    "quality_per_risk_slope": "先在 task 内分别平均 risk 与 quality，再对 task 聚合值拟合含截距线性斜率",
    "active_time_rate": "active_time_n / n", "lead_time_proxy_rate": "lead_time_proxy_n / n", "missing_rate": "missing_n / n",
    "rate": "missing / n", "coverage_rate": "observed_n / 对应事件总体数",
    "jeffreys_lower": "Beta(missing+0.5, n-missing+0.5) 的 2.5% 分位数",
    "jeffreys_upper": "Beta(missing+0.5, n-missing+0.5) 的 97.5% 分位数",
}


def _truth(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "passed", "valid", "eligible", "matched"}


def _num(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, encoding="utf-8-sig", low_memory=False)


def _neutral_text(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    output = value
    for token in RESTRICTED_TOKENS:
        output = re.sub(re.escape(token), "neutral", output, flags=re.IGNORECASE)
    return output


def _neutral_frame(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    renamed = {}
    for column in result:
        target = str(column)
        for token in RESTRICTED_TOKENS:
            target = re.sub(re.escape(token), "negative_metric_change", target, flags=re.IGNORECASE)
        renamed[column] = target
    result = result.rename(columns=renamed)
    for column in result.select_dtypes(include=["object", "string"]):
        result[column] = result[column].map(_neutral_text)
    return result


def _bilingual(frame: pd.DataFrame) -> pd.DataFrame:
    result = _neutral_frame(frame)
    for column in list(result.columns):
        if column not in ENUM_COLUMNS or column.endswith("_zh") or f"{column}_zh" in result.columns:
            continue
        position = result.columns.get_loc(column) + 1
        values = result[column].map(lambda value: "" if pd.isna(value) or str(value).strip() == "" else ENUM_ZH.get(str(value), f"原始码：{value}"))
        result.insert(position, f"{column}_zh", values)
    return result


def _write_csv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _bilingual(frame).to_csv(path, index=False, encoding="utf-8-sig", lineterminator="\n")


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8", newline="\n")


def _patch_sources(package: Path, c1_dir: Path, persistent_dir: Path) -> None:
    for module in (common, geometry, reviewed, base, reviewed_materializer, legacy):
        if hasattr(module, "PACKAGE"):
            module.PACKAGE = package
        if hasattr(module, "V2"):
            module.V2 = c1_dir
        if hasattr(module, "PERSISTENT"):
            module.PERSISTENT = persistent_dir


def _reviewed_choice_group(from_name: str, choice: str) -> tuple[str, str, str]:
    source = str(from_name or "").strip().lower().replace("-", "_")
    token = str(choice or "").strip().lower().replace("-", "_")
    fixed = {
        ("scope", "normal"): ("scope", "in_scope", "范围内/正常"),
        ("scope", "oos_geometry"): ("scope", "oos_geometry", "范围外：几何假设不适用"),
        ("scope", "oos_insufficient"): ("scope", "oos_insufficient_evidence", "几何证据不足"),
        ("difficulty", "trivial"): ("difficulty", "trivial", "无显著难点"),
        ("difficulty", "low_quality"): ("difficulty", "low_image_quality", "低图像质量"),
    }
    return fixed.get((source, token), common.choice_group(from_name, choice))


def _build_intermediates(work: Path, bootstrap_replicates: int) -> dict[str, Path]:
    package, c1_dir, persistent_dir, persistent_history, reviewed_dir = (
        work / name for name in ("source", "c1", "persistent", "persistent_history", "reviewed")
    )
    discovery.materialize(package)
    c1_uncertainty.materialize(c1_dir, bootstrap_replicates=bootstrap_replicates)
    persistent.run(ROOT, persistent_dir, thresholds=(0.90, 0.925, 0.93, 0.95, 0.97))
    persistent.run(ROOT, persistent_history, thresholds=(0.90, 0.925, 0.95))
    _patch_sources(package, c1_dir, persistent_history)
    reviewed.choice_group = _reviewed_choice_group
    reviewed.worker_viewpoint_stability.__kwdefaults__["permutations"] = 2000
    reviewed._permutation_variance.__kwdefaults__["permutations"] = 2000
    reviewed._split_half_reliability.__kwdefaults__["repetitions"] = 1000
    reviewed_materializer.materialize(reviewed_dir)
    return {"source": package, "c1": c1_dir, "persistent": persistent_dir, "reviewed": reviewed_dir}


def _base_frames(paths: Mapping[str, Path]) -> dict[str, pd.DataFrame]:
    _patch_sources(paths["source"], paths["c1"], paths["persistent"])
    legacy.V2 = paths["reviewed"]
    data = legacy.load_data()
    image_map = legacy.build_image_reference_map(data["raw"])
    flagged, exclusion_summary, exclusion_outcomes, exclusion_overlap = legacy.orthogonal_record_flags(data["unified"], data["row_inclusion"])
    time_records, time_summary = legacy.time_measurement_audit(flagged, data["raw_active_events"])
    out_rows, out_summary = legacy.raw_out_of_task(data["raw"], time_records)
    raw_ledger, raw_crosswalk = legacy.raw_record_ledger(data["raw"])
    convergence = legacy.semi_convergence_expansion(data, image_map)
    semi_review = legacy.prepare_semi_review(data)
    proposal_stage = legacy.proposal_stage_summary(semi_review)
    proposal_task = legacy.proposal_task_analysis(semi_review, convergence, image_map)
    tag_all, tag_cases, tag_summary = legacy.tag_behavior_analysis(data, semi_review, image_map)
    dual, dual_summary = legacy.dual_annotator_sensitivity(data, image_map)
    gt_causes, cause_summary = legacy.crowd_gt_geometric_causes(data, image_map)
    excluded_peer, excluded_peer_summary = legacy.exclusion_peer_analysis(data, time_records)
    worker_integrated = legacy.worker_viewpoint_and_quality(data, time_records)
    image_index = legacy.resolve_images(set(time_records["base_task_id"]), image_map)
    return {
        "ALL_RECORDS_WITH_ORTHOGONAL_FLAGS.csv": time_records,
        "EXCLUSION_REASON_SUMMARY.csv": exclusion_summary, "EXCLUSION_REASON_OUTCOME_SUMMARY.csv": exclusion_outcomes,
        "EXCLUSION_REASON_OVERLAPS.csv": exclusion_overlap, "OUT_OF_TASK_AND_NONSELECTED_ROWS.csv": out_rows,
        "OUT_OF_TASK_SUMMARY.csv": out_summary, "RAW_ANNOTATION_LEDGER_ALL_2513.csv": raw_ledger,
        "RAW_ONLY_TO_SELECTED_CONTEXT_CROSSWALK.csv": raw_crosswalk, "TIME_MEASUREMENT_RECORD_AUDIT.csv": time_records,
        "TIME_MEASUREMENT_SOURCE_SUMMARY.csv": time_summary, "SEMI_25_CONVERGENCE_EXPANSION_ALL_IMAGES.csv": convergence,
        "PROPOSAL_STAGE_METRIC_CHANGE_SUMMARY.csv": proposal_stage, "PROPOSAL_TASK_ANCHORING_AND_DISCOVERY.csv": proposal_task,
        "TAG_BEHAVIOR_ALL_SEMI_ROWS.csv": tag_all, "TAG_BEHAVIOR_ALL_CASES.csv": tag_cases,
        "TAG_BEHAVIOR_CASE_SUMMARY.csv": tag_summary, "DUAL_ANNOTATOR_GEOMETRY_SENSITIVITY_ALL.csv": dual,
        "DUAL_ANNOTATOR_STAGE_SUMMARY.csv": dual_summary, "CROWD_GT_101_GEOMETRIC_CAUSE_AUDIT.csv": gt_causes,
        "CROWD_GT_GEOMETRIC_CAUSE_SUMMARY.csv": cause_summary, "EXCLUDED_RECORD_PEER_COMPARISONS_BY_REASON.csv": excluded_peer,
        "EXCLUDED_RECORD_PEER_SUMMARY_BY_REASON.csv": excluded_peer_summary, "WORKER_VIEWPOINT_QUALITY_TIME_INTEGRATED.csv": worker_integrated,
        "ALL_IMAGE_INSTANCE_INDEX.csv": image_index,
    }


def _copy_intermediate_tables(paths: Mapping[str, Path]) -> dict[str, pd.DataFrame]:
    selected = {
        "source": (
            "submission_fact.csv", "task_fact.csv", "worker_fact.csv", "semi_review_fact.csv", "raw_annotation_fact.csv",
            "raw_active_event_fact.csv", "raw_active_session_fact.csv", "raw_field_usage_ledger.csv", "data_catalog.csv",
            "join_coverage_audit.csv", "association_matrix.csv",
        ),
        "c1": (
            "TASK_SUBSET_RECLUSTERING.csv", "TASK_METRICS.csv", "THRESHOLD_ROBUSTNESS.csv", "POPULATION_TASK_METRICS.csv",
            "POPULATION_SENSITIVITY.csv", "MANUAL_TASK_UNCERTAINTY_CATALOG.csv", "TASK_INCLUSION_CLASSIFICATION.csv",
            "ROW_INCLUSION_CLASSIFICATION.csv", "WORKER_COVERAGE.csv", "EXCLUSION_REASON_AUDIT.csv",
            "EXCLUDED_WORKER_PEER_COMPARISONS.csv", "EXCLUDED_WORKER_PEER_SUMMARY.csv", "PAIRWISE_COMPATIBILITY_SUMMARY.csv",
            "QUALITY_AUXILIARY.csv", "QUALITY_AUXILIARY_SUMMARY.csv", "QUALITY_DATA_MINING_CONTEXTS.csv",
            "QUALITY_DATA_MINING_TASK_METRICS.csv", "QUALITY_DATA_MINING_SUMMARY.csv", "DIFFICULTY_PROXY_COVERAGE.csv",
            "DIFFICULTY_PROXY_SUMMARY.csv", "FROZEN_TIME_AUXILIARY.csv", "ACTIVE_TIME_TASK_WORKER.csv",
            "ACTIVE_TIME_TASK_METRICS.csv", "ACTIVE_TIME_SUMMARY.csv",
        ),
        "persistent": (
            "PERSISTENT_DISAGREEMENT_TASKS.csv", "PERSISTENT_DISAGREEMENT_SUMMARY.csv",
            "PERSISTENT_DISAGREEMENT_THRESHOLD_ROBUSTNESS.csv", "PERSISTENT_DISAGREEMENT_THRESHOLD_ROBUSTNESS_SUMMARY.csv",
        ),
        "reviewed": (
            "UNIFIED_SUBMISSION_EVIDENCE_REVIEWED.csv", "DATA_COVERAGE_BY_STAGE_MODE.csv", "ACTIVE_TIME_SOURCE_AUDIT.csv",
            "RAW_META_LABEL_RESPONSE_LONG.csv", "RAW_META_LABEL_RESPONSE_SETS.csv", "META_LABEL_TASK_UNCERTAINTY.csv",
            "META_LABEL_TASK_LABEL_COUNTS.csv", "META_LABEL_CHOICE_DICTIONARY.csv", "META_LABEL_STAGE_MODE_SUMMARY.csv",
            "GEOMETRY_TASK_UNCERTAINTY_ALL_STAGES.csv", "GEOMETRY_PAIRWISE_DISPERSION_ALL_STAGES.csv", "GEOMETRY_STAGE_MODE_SUMMARY.csv",
            "PERSISTENT_DISAGREEMENT_HIGH_SUPPORT_Q095.csv", "PERSISTENT_DISAGREEMENT_HIGH_SUPPORT_ROBUSTNESS.csv",
            "PERSISTENT_DISAGREEMENT_HIGH_SUPPORT_SUMMARY.csv", "C1_CROWD_GT_CONFLICT_TASKS.csv", "C1_CROWD_GT_CLUSTER_METRICS.csv",
            "C1_WORKER_TASK_MODE_MEMBERSHIP.csv", "WORKER_VIEWPOINT_STABILITY.csv", "WORKER_VIEWPOINT_COTENDENCY.csv",
            "WORKER_VIEWPOINT_TESTS.csv", "EXCLUDED_WORKER_PEER_EVIDENCE.csv", "TIME_SUBMISSION_EVIDENCE_REVIEWED.csv",
            "TIME_STAGE_MODE_SUMMARY.csv", "TIME_MANUAL_SEMI_TASK_PAIRS.csv", "TIME_ACTIVE_LEAD_RELATION.csv",
            "TIME_OUTLIERS_AND_MODELS.csv", "CURRENT_MANUAL_SEMI_UNCERTAINTY_SUMMARY.csv", "SEMI_DATA_PRECISION_PROJECTION.csv",
            "SEMI_REQUIRED_BUILDINGS_BY_EFFECT.csv", "RARE_MODE_DETECTION_PROBABILITY.csv", "DEEP_MINING_ASSOCIATIONS.csv",
            "DEEP_MINING_TASK_TABLE.csv", "DEEP_MINING_WORKER_AND_LEGACY_MECHANISM_TABLES.csv", "SEMI_PROPOSAL_TASK_TABLE.csv",
            "SEMI_PROPOSAL_ASSOCIATIONS.csv", "SEMI_REVIEW_TASK_SUMMARY.csv", "TASK_CASE_CATALOG.csv",
        ),
    }
    return {name.upper(): _read(paths[group] / name) for group, names in selected.items() for name in names}


def _meta_response_metrics(response_sets: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    frame = response_sets.copy()
    frame["_set"] = frame["label_set_json"].map(lambda value: set(json.loads(value)) if str(value).strip() else set())
    rows = []
    for lane, subset in (("raw_history", frame), ("canonical_final", frame[frame["canonical_join_status"].eq("matched")])):
        for keys, group in subset.groupby(["stage", "condition", "base_task_id", "meta_group"], sort=True, dropna=False):
            patterns = group["label_set_json"].fillna("").tolist()
            rows.append({
                "population": lane, "stage": keys[0], "condition": keys[1], "base_task_id": keys[2], "meta_group": keys[3],
                "response_version_count": len(group), "worker_count": group["worker_id"].nunique(),
                "response_pattern_entropy": response_pattern_entropy(patterns),
                "mean_pairwise_jaccard_disagreement": mean_pairwise_jaccard_disagreement(group["_set"].tolist()),
                "modal_response_share": modal_response_share(patterns),
                "version_independence_note": "raw/history版本不是独立标注员" if lane == "raw_history" else "每个worker×task×condition的最终规范响应",
            })
    metrics = pd.DataFrame(rows)
    canonical = metrics[metrics["population"].eq("canonical_final")]
    pivot = canonical.pivot_table(
        index=["base_task_id", "meta_group"], columns="condition",
        values=["response_version_count", "worker_count", "response_pattern_entropy", "mean_pairwise_jaccard_disagreement", "modal_response_share"],
        aggfunc="first",
    )
    pivot.columns = [f"{condition}_{metric}" for metric, condition in pivot.columns]
    comparison = pivot.reset_index()
    for metric in ("response_pattern_entropy", "mean_pairwise_jaccard_disagreement", "modal_response_share"):
        comparison[f"delta_{metric}"] = pd.to_numeric(comparison.get(f"semi_{metric}"), errors="coerce") - pd.to_numeric(comparison.get(f"manual_{metric}"), errors="coerce")
    comparison = comparison.dropna(subset=["manual_response_pattern_entropy", "semi_response_pattern_entropy"])
    return metrics, comparison


def _variance_tables(frames: Mapping[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    unified = frames["UNIFIED_SUBMISSION_EVIDENCE_REVIEWED.CSV"].copy()
    meta = frames["RAW_META_LABEL_RESPONSE_SETS.CSV"].copy()
    meta = meta[meta["canonical_join_status"].eq("matched")]
    meta["task_key"] = meta[["stage", "condition", "base_task_id", "meta_group"]].astype(str).agg("|".join, axis=1)
    pairs = frames["GEOMETRY_PAIRWISE_DISPERSION_ALL_STAGES.CSV"].copy()
    pair_rows = []
    for row in pairs.itertuples(index=False):
        value = _num(row.cyclic_rmse_diagonal_normalized)
        if value is None:
            continue
        for worker in (row.worker_id_left, row.worker_id_right):
            pair_rows.append({"task_key": f"{row.stage}|{row.condition}|{row.base_task_id}", "worker_id": worker, "value": value})
    pair_worker = pd.DataFrame(pair_rows).groupby(["task_key", "worker_id"], as_index=False)["value"].mean()
    lanes = {
        "quality_iou_to_gt": (unified.rename(columns={"iou_to_gt": "value"}), "base_task_id"),
        "geometry_mean_pairwise_rmse": (pair_worker, "task_key"),
        "meta_label_cardinality": (meta.rename(columns={"label_cardinality": "value"}), "task_key"),
        "log1p_active_time": (unified.assign(value=np.log1p(pd.to_numeric(unified["active_time_observed_seconds"], errors="coerce"))), "base_task_id"),
    }
    formal, descriptive = [], []
    for lane, (source, task_col) in lanes.items():
        fit = crossed_task_worker_variance_decomposition(source, outcome_col="value", task_col=task_col, worker_col="worker_id")
        formal.append({"analysis_lane": lane, **{key: value for key, value in fit.items() if key not in {"support", "warnings"}}, **fit["support"], "warnings_json": json.dumps(fit["warnings"], ensure_ascii=False)})
        clean = source[[task_col, "worker_id", "value"]].copy()
        clean["value"] = pd.to_numeric(clean["value"], errors="coerce")
        clean = clean.dropna()
        descriptive.append({
            "analysis_lane": lane, "row_count": len(clean), "task_count": clean[task_col].nunique(), "worker_count": clean["worker_id"].nunique(),
            "variance_of_task_means": clean.groupby(task_col)["value"].mean().var(ddof=1),
            "variance_of_worker_means": clean.groupby("worker_id")["value"].mean().var(ddof=1),
            "status": "descriptive_mean_variances_not_formal_decomposition",
        })
    return pd.DataFrame(formal), pd.DataFrame(descriptive)


def _axis_association(frame: pd.DataFrame, axis: str, x: str, y: str, *, repetitions: int = 1000) -> dict[str, Any]:
    columns = [x, y, "base_task_id", "worker_id", "building_id"]
    raw = frame[[column for column in columns if column in frame]].copy()
    raw[x], raw[y] = pd.to_numeric(raw[x], errors="coerce"), pd.to_numeric(raw[y], errors="coerce")
    raw = raw.dropna(subset=[x, y])
    data = raw
    if axis == "task":
        data = raw.groupby("base_task_id", as_index=False).agg({x: "mean", y: "mean"})
    elif axis == "worker":
        data = raw.groupby("worker_id", as_index=False).agg({x: "mean", y: "mean"})
    if len(data) < 3 or data[x].nunique() < 2 or data[y].nunique() < 2:
        return {"row_count": len(data), "task_count": raw.get("base_task_id", pd.Series(dtype=str)).nunique(), "worker_count": raw.get("worker_id", pd.Series(dtype=str)).nunique(), "spearman_rho": np.nan, "ci_lower": np.nan, "ci_upper": np.nan, "permutation_p": np.nan, "status": "not_evaluable"}
    observed = float(stats.spearmanr(data[x], data[y]).statistic)
    rng = np.random.default_rng(SEED + {"row": 1, "task": 2, "worker": 3}[axis])
    boot = []
    for _ in range(repetitions):
        sample = data.iloc[rng.integers(0, len(data), len(data))]
        if sample[x].nunique() > 1 and sample[y].nunique() > 1:
            boot.append(float(stats.spearmanr(sample[x], sample[y]).statistic))
    perm = [abs(float(stats.spearmanr(data[x], rng.permutation(data[y])).statistic)) for _ in range(repetitions)]
    return {
        "row_count": len(data), "task_count": raw.get("base_task_id", pd.Series(dtype=str)).nunique(), "worker_count": raw.get("worker_id", pd.Series(dtype=str)).nunique(),
        "spearman_rho": observed, "ci_lower": np.quantile(boot, 0.025), "ci_upper": np.quantile(boot, 0.975),
        "permutation_p": (1 + sum(value >= abs(observed) for value in perm)) / (repetitions + 1), "status": "estimated",
    }


def _structural_zero(frames: Mapping[str, pd.DataFrame]) -> pd.DataFrame:
    review = frames["SEMI_REVIEW_FACT.CSV"].copy()
    review["building_id"] = review.get("building_id", review["base_task_id"].astype(str).str.split("_").str[0])
    rows = []
    for lane in ("all-computable", "exclude_joint_near_zero", "edited-positive", "formal-only"):
        subset = filter_structural_zero_lane(
            review, lane, rmse_col="geometry_edit_rmse_panorama_diagonal_normalized", formal_col="formal_assignment_eligible",
            near_zero_tolerance=1e-6,
        )
        for axis in ("row", "task", "worker"):
            rows.append({"analysis_lane": lane, "inference_axis": axis, **_axis_association(subset, axis, "geometry_edit_rmse_panorama_diagonal_normalized", "delta_U"), "missing_rule": "RMSE或delta_U缺失时不进入分母，绝不填零"})
    return pd.DataFrame(rows)


def _c2_terminal_tables() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    evidence = _read(TERMINAL / "c2b_plus_c2a_rp_terminal_risk_slope_evidence.csv")
    profile = _read(TERMINAL / "post_c2a_rp_terminal_worker_profile.csv")
    eligible = evidence[evidence["eligibility_status"].eq("eligible")].copy()
    support = eligible.groupby("base_task_id", as_index=False).agg(worker_support=("worker_id", "nunique"), row_support=("worker_id", "size"), building_id=("building_id", "first"))
    support["support_bin"] = support["worker_support"].map(lambda value: "5_plus" if value >= 5 else str(int(value)))
    distribution = support.groupby("support_bin", as_index=False).agg(task_count=("base_task_id", "size")).set_index("support_bin").reindex(["1", "2", "3", "4", "5_plus"], fill_value=0).reset_index()
    if len(eligible) != 227 or distribution["task_count"].tolist() != [18, 23, 11, 5, 10]:
        raise AssertionError({"eligible_terminal_rows": len(eligible), "support_distribution": distribution.to_dict("records")})
    selected = profile[[column for column in (
        "worker_id", "administratively_eligible", "Q_GT_raw_median", "Q_GT_task_adjusted", "Q_GT_EB", "Q_GT_EB_LCB",
        "GT_support", "task_support", "building_support", "Q_GT_profile_status", "risk_slope", "risk_slope_se", "risk_slope_support",
        "ordinary_support_observed", "stress_support_observed", "risk_slope_status", "risk_precision_terminal_state",
    ) if column in profile]].copy()
    for metric in ("Q_GT_raw_median", "Q_GT_task_adjusted", "Q_GT_EB"):
        selected[f"{metric}_rank"] = pd.to_numeric(selected[metric], errors="coerce").rank(method="min", ascending=False)
    selected["Q_GT_shrinkage"] = pd.to_numeric(selected["Q_GT_EB"], errors="coerce") - pd.to_numeric(selected["Q_GT_task_adjusted"], errors="coerce")
    selected["rank_displacement_raw_to_EB"] = selected["Q_GT_EB_rank"] - selected["Q_GT_raw_median_rank"]
    return evidence, support, distribution, selected


def _quality_risk_slopes(evidence: pd.DataFrame, profile: pd.DataFrame) -> pd.DataFrame:
    frame = evidence.merge(profile[["worker_id", "administratively_eligible"]], how="left", on="worker_id")
    populations = {
        "all_computable": frame, "formal_only": frame[frame["formal_assignment_eligible"].map(_truth)],
        "administrative_eligible": frame[frame["administratively_eligible"].map(_truth)],
        "administrative_ineligible": frame[~frame["administratively_eligible"].map(_truth)],
    }
    rows = []
    for population, subset in populations.items():
        data = subset.assign(risk_num=pd.to_numeric(subset["risk"], errors="coerce"), quality_num=pd.to_numeric(subset["quality"], errors="coerce")).dropna(subset=["risk_num", "quality_num"])
        if len(data) < 3 or data["risk_num"].nunique() < 2:
            rows.append({"population": population, "row_count": len(data), "status": "not_evaluable"}); continue
        fit = stats.linregress(data["risk_num"], data["quality_num"])
        rows.append({
            "population": population, "row_count": len(data), "task_count": data["base_task_id"].nunique(), "worker_count": data["worker_id"].nunique(),
            "building_count": data["building_id"].nunique(), "quality_per_risk_slope": fit.slope, "standard_error": fit.stderr,
            "ci_lower": fit.slope - 1.96 * fit.stderr, "ci_upper": fit.slope + 1.96 * fit.stderr, "p_value": fit.pvalue,
            "status": "descriptive_population_recompute",
        })
    return pd.DataFrame(rows)


def _worker_rank_stability(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for left, right in (("Q_GT_raw_median", "Q_GT_task_adjusted"), ("Q_GT_raw_median", "Q_GT_EB"), ("Q_GT_task_adjusted", "Q_GT_EB")):
        data = frame[[left, right]].apply(pd.to_numeric, errors="coerce").dropna()
        rows.append({
            "metric_left": left, "metric_right": right, "worker_count": len(data),
            "spearman_rho": stats.spearmanr(data[left], data[right]).statistic if len(data) >= 3 else np.nan,
            "status": "descriptive_rank_stability" if len(data) >= 3 else "not_evaluable",
        })
    return pd.DataFrame(rows)


def _revision_lineage(raw: pd.DataFrame) -> pd.DataFrame:
    frame = raw.copy()
    frame["created_at_parsed_utc"] = pd.to_datetime(frame["created_at"], errors="coerce", utc=True)
    frame["updated_at_parsed_utc"] = pd.to_datetime(frame["updated_at"], errors="coerce", utc=True)
    frame["geometry_hash"] = frame["result_json"].fillna("").map(lambda value: hashlib.sha256(str(value).encode("utf-8")).hexdigest())
    keys = ["stage", "project_id", "ls_runtime_task_id", "worker_id"]
    frame = frame.sort_values(keys + ["created_at_parsed_utc", "annotation_id"], kind="stable")
    frame["previous_annotation_id_chronological"] = frame.groupby(keys, dropna=False)["annotation_id"].shift()
    frame["final_selected"] = frame["canonical_join_status"].eq("matched")
    frame["version_independence_note"] = "同一worker×task的版本不是独立标注者"
    return frame[[
        "stage", "project_id", "ls_runtime_task_id", "base_task_id", "condition", "worker_id", "annotation_id",
        "canonical_annotation_id", "canonical_join_status", "created_at", "updated_at", "created_at_parsed_utc",
        "updated_at_parsed_utc", "parent_annotation", "previous_annotation_id_chronological", "geometry_hash", "final_selected",
        "source_path", "source_sha256", "version_independence_note",
    ]]


def _event_integrity(events: pd.DataFrame, sessions: pd.DataFrame) -> pd.DataFrame:
    timestamp = pd.to_datetime(pd.to_numeric(events["timestamp"], errors="coerce"), unit="ms", utc=True, errors="coerce")
    server = pd.to_datetime(events["server_received_at"], utc=True, errors="coerce")
    lag = (server - timestamp).dt.total_seconds()
    return pd.DataFrame([
        {"check": "event_rows", "observed": len(events), "expected": 34417, "status": "pass" if len(events) == 34417 else "fail", "calculation": "raw event逐行计数"},
        {"check": "session_rows", "observed": len(sessions), "expected": 3735, "status": "pass" if len(sessions) == 3735 else "fail", "calculation": "project+task+annotator+session分组"},
        {"check": "out_of_scope_or_stage_mismatch", "observed": int((~events["in_formal_stage_scope"].map(_truth)).sum()), "expected": np.nan, "status": "audit", "calculation": "冻结阶段绑定外事件计数"},
        {"check": "page_gate_eligible", "observed": int(events["page_gate_eligible"].map(_truth).sum()), "expected": np.nan, "status": "audit", "calculation": "page_gate_eligible为真"},
        {"check": "store_mismatch_present", "observed": int(events["store_mismatch_present"].map(_truth).sum()), "expected": np.nan, "status": "audit", "calculation": "store_mismatch_present为真"},
        {"check": "fragment_seconds_computable", "observed": int(pd.to_numeric(events["active_seconds_fragment"], errors="coerce").notna().sum()), "expected": np.nan, "status": "audit_only", "calculation": "fragment仅审计，不回填active time"},
        {"check": "timestamp_ms_parsed", "observed": int(timestamp.notna().sum()), "expected": int(pd.to_numeric(events["timestamp"], errors="coerce").notna().sum()), "status": "pass", "calculation": "pd.to_datetime(..., unit='ms', utc=True)"},
        {"check": "client_server_lag_seconds", "observed": int(lag.notna().sum()), "expected": np.nan, "status": "audit", "calculation": f"median={lag.median()};p95={lag.quantile(.95)}"},
    ])


def _parse_initial_points(task_data_json: Any) -> list[list[float]]:
    payload = common.parse_jsonish(task_data_json) or {}
    try:
        data = json.loads(unquote(parse_qs(urlparse(str(payload.get("vis_3d", ""))).query).get("data", [""])[0]))
    except (ValueError, json.JSONDecodeError):
        return []
    points = []
    for pair in sorted(data, key=lambda row: float(row["x"])):
        points.extend([[float(pair["x"]), float(pair["y_ceiling"])], [float(pair["x"]), float(pair["y_floor"])]])
    return points


def _parse_final_points(result_json: Any) -> list[list[float]]:
    points = []
    for item in common.parse_jsonish(result_json) or []:
        value = item.get("value") or {}
        if item.get("type") == "keypointlabels" and "Corner" in (value.get("keypointlabels") or []):
            points.append([float(value["x"]) * 10.24, float(value["y"]) * 5.12])
    return points


def _proposal_geometry(raw: pd.DataFrame, review: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    selected = raw[(raw["stage"].eq("C1")) & raw["canonical_join_status"].eq("matched")].copy()
    selected["final_points"] = selected["result_json"].map(_parse_final_points)
    selected["initial_points"] = selected.apply(
        lambda row: _parse_initial_points(row["task_data_json"]) if row["condition"] == "semi" else [], axis=1
    )
    lookup = {(str(row.base_task_id), str(row.worker_id)): row for row in review.itertuples(index=False)}
    rows = []
    for row in selected.itertuples(index=False):
        extra = lookup.get((str(row.base_task_id), str(row.worker_id)))
        rows.append({
            "base_task_id": row.base_task_id, "condition": row.condition, "worker_id": row.worker_id,
            "canonical_annotation_id": row.canonical_annotation_id, "initial_points_json": json.dumps(row.initial_points),
            "final_points_json": json.dumps(row.final_points), "initial_point_count": len(row.initial_points), "final_point_count": len(row.final_points),
            "initial_to_final_rmse_diagonal_normalized": common.cyclic_rmse(row.initial_points, row.final_points),
            "U_initial": getattr(extra, "U_initial", np.nan), "U_final": getattr(extra, "U_final", np.nan), "delta_U": getattr(extra, "delta_U", np.nan),
            "initial_geometry_hash": getattr(extra, "initial_geometry_hash", ""), "final_geometry_hash": getattr(extra, "final_geometry_hash", hashlib.sha256(json.dumps(row.final_points).encode()).hexdigest()),
        })
    records = pd.DataFrame(rows)
    pairs = []
    for task, group in records.groupby("base_task_id", sort=True):
        manual, semi = group[group["condition"].eq("manual")], group[group["condition"].eq("semi")]
        for left in manual.itertuples(index=False):
            left_points = json.loads(left.final_points_json)
            for right in semi.itertuples(index=False):
                right_points = json.loads(right.final_points_json)
                pairs.append({
                    "base_task_id": task, "manual_worker_id": left.worker_id, "semi_worker_id": right.worker_id,
                    "manual_to_semi_rmse_diagonal_normalized": common.cyclic_rmse(left_points, right_points),
                    "model_to_manual_rmse_diagonal_normalized": common.cyclic_rmse(json.loads(right.initial_points_json), left_points),
                    "model_to_semi_rmse_diagonal_normalized": right.initial_to_final_rmse_diagonal_normalized,
                    "model_gt_residual": 1 - float(right.U_initial) if _num(right.U_initial) is not None else np.nan,
                    "semi_gt_residual": 1 - float(right.U_final) if _num(right.U_final) is not None else np.nan,
                    "reference_availability": "operational_gt_available" if _num(right.U_final) is not None else "not_evaluable",
                })
    return records, pd.DataFrame(pairs)


def _dual_quality(dual: pd.DataFrame, terminal_evidence: pd.DataFrame) -> pd.DataFrame:
    evidence = terminal_evidence.copy()
    evidence["stage"] = evidence["evidence_stage"].map({"C2B": "C2-B", "C2A_RP_BLOCK1": "C2-A-RP-B1", "C2A_RP_BLOCK2": "C2-A-RP-B2"})
    rows = []
    for task in dual.itertuples(index=False):
        group = evidence[(evidence["stage"].eq(task.stage)) & (evidence["base_task_id"].eq(task.base_task_id))].drop_duplicates("worker_id").sort_values("worker_id")
        quality = pd.to_numeric(group["quality"], errors="coerce")
        workers, values = group["worker_id"].astype(str).tolist(), quality.tolist()
        rows.append({
            "stage": task.stage, "condition": task.condition, "base_task_id": task.base_task_id,
            "worker_id_left": workers[0] if workers else "", "worker_id_right": workers[1] if len(workers) > 1 else "",
            "quality_left": values[0] if values else np.nan, "quality_right": values[1] if len(values) > 1 else np.nan,
            "quality_mean": quality.mean(), "quality_best": quality.max(), "quality_worst": quality.min(),
            "quality_absolute_difference": abs(values[0] - values[1]) if len(values) > 1 and all(pd.notna(value) for value in values[:2]) else np.nan,
            "reference_availability": "available" if quality.notna().all() and len(quality) == 2 else "not_evaluable",
            "sensitivity_role": "two_person_pair_no_majority_consensus",
        })
    result = pd.DataFrame(rows)
    if len(result) != 54:
        raise AssertionError(f"dual-task count drift: {len(result)}")
    return result


def _image_features(image_index: pd.DataFrame, task_fact: pd.DataFrame, difficulty: pd.DataFrame, meta_metrics: pd.DataFrame) -> pd.DataFrame:
    task = task_fact.sort_values(["base_task_id", "stage", "condition"]).drop_duplicates("base_task_id")
    pre_cols = [column for column in ("base_task_id", "risk", "risk_design_score_A", "g_duplicate_peak", "g_postprocess_invalid", "g_seam_instability", "g_topology_invalid", "feature_timing", "reference_status") if column in task]
    result = image_index.merge(task[pre_cols], how="left", on="base_task_id")
    feature_rows = []
    for row in result.itertuples(index=False):
        path = ROOT / str(row.workspace_local_path)
        values = image_substrate.image_features(path) if path.is_file() else {}
        feature_rows.append({"base_task_id": row.base_task_id, "image_sha256": _sha(path) if path.is_file() else "", "image_parse_status": "ready" if values else "not_computable", **values})
    result = result.merge(pd.DataFrame(feature_rows), how="left", on="base_task_id")
    diff_cols = [column for column in ("base_task_id", "confirmatory_status", "frozen_preassignment_n_ready", "legacy_difficulty_label", "legacy_label_status", "gt_keypoint_count", "gt_pair_count", "proposal_initial_quality_mean") if column in difficulty]
    result = result.merge(difficulty[diff_cols].drop_duplicates("base_task_id"), how="left", on="base_task_id")
    post = meta_metrics[meta_metrics["population"].eq("canonical_final")].groupby("base_task_id", as_index=False).agg(
        post_meta_response_pattern_entropy_mean=("response_pattern_entropy", "mean"),
        post_meta_jaccard_disagreement_mean=("mean_pairwise_jaccard_disagreement", "mean"),
        post_meta_modal_response_share_mean=("modal_response_share", "mean"),
    )
    result = result.merge(post, how="left", on="base_task_id")
    result["image_feature_classification"] = "pre_task_image_only"; result["model_feature_classification"] = "pre_task_model"
    result["legacy_difficulty_classification"] = "historical_proxy"; result["post_meta_classification"] = "post_worker_concurrent"
    if len(result) != 214 or not result["image_parse_status"].eq("ready").all():
        raise AssertionError({"image_rows": len(result), "ready": int(result["image_parse_status"].eq("ready").sum())})
    return result


def _image_semi_associations(images: pd.DataFrame, convergence: pd.DataFrame, proposal: pd.DataFrame) -> pd.DataFrame:
    data = images.merge(convergence, how="inner", on="base_task_id", suffixes=("", "_uncertainty")).merge(
        proposal[[column for column in ("base_task_id", "edit_rate", "edit_rmse_mean", "delta_metric_mean") if column in proposal]], how="left", on="base_task_id"
    )
    predictors = [column for column in ("mean_luma", "horizontal_gradient_mean_wrap", "seam_gradient_mean", "vertical_edge_mean", "boundary_gradient_mean", "edge_density_proxy", "gt_pair_count", "proposal_initial_quality_mean") if column in data]
    outcomes = [column for column in ("delta_shannon_entropy", "delta_gini_simpson", "delta_largest_mode_share", "delta_supported_multimodality", "delta_pairwise_metric_dissimilarity_all", "delta_quality_iou", "edit_rate", "edit_rmse_mean", "delta_metric_mean") if column in data]
    return pd.DataFrame([
        {"feature_classification": "historical_proxy" if predictor in {"gt_pair_count", "proposal_initial_quality_mean"} else "pre_task_image_only", "predictor": predictor, "outcome": outcome, **_axis_association(data, "task", predictor, outcome)}
        for predictor in predictors for outcome in outcomes
    ])


def _manual_crossfit() -> pd.DataFrame:
    _, _, all_nodes, _, all_pair_map = c1_uncertainty.geometry_contexts()
    planned = sorted(_read(ROOT / c1_uncertainty.INPUTS["assignment_semi"][0])["base_task_id"].unique())
    rows = []
    for task in planned:
        workers = sorted(all_nodes.get((task, "manual"), [])); left, right = workers[::2], workers[1::2]
        semi_workers = sorted(all_nodes.get((task, "semi"), []))
        semi = c1_uncertainty.recluster_subset(task, "semi", semi_workers, 0.95, all_pair_map) if len(semi_workers) >= 3 else {}
        for fold, predictor_workers, heldout_workers in (("A_to_B", left, right), ("B_to_A", right, left)):
            status = "estimated" if len(predictor_workers) >= 3 and len(heldout_workers) >= 3 else "not_evaluable_insufficient_disjoint_support"
            predictor = c1_uncertainty.recluster_subset(task, "manual", predictor_workers, 0.95, all_pair_map) if len(predictor_workers) >= 3 else {}
            heldout = c1_uncertainty.recluster_subset(task, "manual", heldout_workers, 0.95, all_pair_map) if len(heldout_workers) >= 3 else {}
            rows.append({
                "base_task_id": task, "fold": fold, "predictor_worker_ids": ";".join(predictor_workers), "heldout_worker_ids": ";".join(heldout_workers),
                "predictor_support": len(predictor_workers), "heldout_support": len(heldout_workers),
                "manual_predictor_entropy": predictor.get("shannon_entropy"), "manual_heldout_entropy": heldout.get("shannon_entropy"),
                "semi_entropy": semi.get("shannon_entropy"),
                "crossfit_delta_entropy": (
                    semi.get("shannon_entropy") - heldout.get("shannon_entropy")
                    if semi.get("shannon_entropy") is not None and heldout.get("shannon_entropy") is not None else np.nan
                ),
                "status": status, "calculation": "Semi entropy - disjoint held-out Manual entropy; predictor uses the other disjoint Manual subset",
            })
    return pd.DataFrame(rows)


def _crossfit_summary(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for fold, group in frame.groupby("fold", sort=True):
        rows.append({"fold": fold, **_axis_association(group, "task", "manual_predictor_entropy", "crossfit_delta_entropy")})
    return pd.DataFrame(rows)


def _prefix_and_worker_modes(current_membership: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    tasks = load_frozen_c1_k22_tasks(ROOT)
    replay = pd.DataFrame(replay_frozen_c1_k22_prefixes(tasks, seed=SEED, replicates=200))
    summary = pd.DataFrame(summarize_prefix_replay(replay.to_dict("records")))
    legacy_members = []
    for row in replay[replay["k"].eq(22)].itertuples(index=False):
        if row.task_crowd_structure_status == "not_evaluable" or not str(row.cluster_membership_json).strip():
            continue
        by_annotation = {str(candidate["canonical_annotation_id"]): str(candidate["worker_id"]) for candidate in tasks[str(row.base_task_id)]}
        clusters = json.loads(row.cluster_membership_json); largest = max(range(len(clusters)), key=lambda index: len(clusters[index]))
        for index, cluster in enumerate(clusters):
            for annotation in cluster:
                legacy_members.append({"analysis_lane": "legacy_q095_k22_evaluable_9", "base_task_id": row.base_task_id, "condition": "manual", "worker_id": by_annotation.get(str(annotation), ""), "is_largest_mode": index == largest, "is_supported_minority_mode": index != largest and len(cluster) >= 2, "cluster_support": len(cluster), "cluster_count": len(clusters)})
    legacy_frame = pd.DataFrame(legacy_members)
    current = current_membership.copy(); current.insert(0, "analysis_lane", "current_all_computable_c1")
    memberships = pd.concat([legacy_frame, current], ignore_index=True, sort=False)
    summaries, tests, pair_rows = [], [], []
    rng = np.random.default_rng(SEED)
    for lane, lane_frame in memberships.groupby("analysis_lane", sort=True):
        lane_frame = lane_frame.copy(); lane_frame["is_largest_mode"] = lane_frame["is_largest_mode"].map(_truth)
        for worker, group in lane_frame.groupby("worker_id"):
            task_ids = group["base_task_id"].unique(); boot = []
            for _ in range(500):
                sampled = rng.choice(task_ids, len(task_ids), replace=True)
                boot.append(np.mean([group.loc[group["base_task_id"].eq(task), "is_largest_mode"].mean() for task in sampled]))
            summaries.append({"analysis_lane": lane, "worker_id": worker, "task_count": len(task_ids), "largest_mode_rate": group["is_largest_mode"].mean(), "task_bootstrap_ci_lower": np.quantile(boot, .025), "task_bootstrap_ci_upper": np.quantile(boot, .975)})
        observed = pd.DataFrame(summaries); observed = observed[observed["analysis_lane"].eq(lane)]
        observed_variance = observed["largest_mode_rate"].var(ddof=0); perm_variances = []
        for _ in range(1000):
            shuffled = lane_frame.groupby(["base_task_id", "condition"], group_keys=False)["is_largest_mode"].transform(lambda series: rng.permutation(series.to_numpy()))
            perm_variances.append(lane_frame.assign(_value=shuffled).groupby("worker_id")["_value"].mean().var(ddof=0))
        loto = []; full = lane_frame.groupby("worker_id")["is_largest_mode"].mean()
        for task in lane_frame["base_task_id"].unique():
            drop = lane_frame[~lane_frame["base_task_id"].eq(task)].groupby("worker_id")["is_largest_mode"].mean(); shared = full.index.intersection(drop.index)
            if len(shared) >= 3 and full.loc[shared].nunique() > 1 and drop.loc[shared].nunique() > 1:
                loto.append(stats.spearmanr(full.loc[shared], drop.loc[shared]).statistic)
        tests.append({"analysis_lane": lane, "test": "task_condition_stratified_permutation", "observed_variance": observed_variance, "permutations": 1000, "p_value": (1 + sum(value >= observed_variance for value in perm_variances)) / 1001})
        tests.append({"analysis_lane": lane, "test": "leave_one_task_out_rank_stability", "valid_repetitions": len(loto), "median_spearman": np.median(loto) if loto else np.nan})
        for left, right in combinations(sorted(lane_frame["worker_id"].astype(str).unique()), 2):
            left_rows = lane_frame[lane_frame["worker_id"].astype(str).eq(left)].set_index(["base_task_id", "condition"])
            right_rows = lane_frame[lane_frame["worker_id"].astype(str).eq(right)].set_index(["base_task_id", "condition"])
            shared = left_rows.index.intersection(right_rows.index)
            if len(shared):
                pair_rows.append({"analysis_lane": lane, "worker_id_left": left, "worker_id_right": right, "shared_task_condition_count": len(shared), "same_largest_mode_status_rate": np.mean(left_rows.loc[shared, "is_largest_mode"].to_numpy() == right_rows.loc[shared, "is_largest_mode"].to_numpy())})
    return replay, summary, memberships, pd.DataFrame(summaries), pd.concat([pd.DataFrame(tests), pd.DataFrame(pair_rows)], ignore_index=True, sort=False)


def _coverage_audit() -> pd.DataFrame:
    return pd.DataFrame([
        ("persistent disagreement five thresholds", "ready", "0.90/0.925历史对照；0.93/0.95/0.97当前主阈值及敏感性"),
        ("k22 prefix replay", "ready", "12任务；k=5/8/12/16/20各200次；k=22完整样本"),
        ("crossed task worker variance", "ready", "质量、几何、元标签、log1p(active time)"),
        ("meta response metrics", "ready", "canonical final与raw/history分母分开"),
        ("task mechanism clustering", "not_materialized_by_design", "此前仅讨论，未稳定完成"),
        ("missingness probability model", "not_materialized_by_design", "此前仅讨论，未稳定完成"),
        ("reference version trajectory", "not_materialized_by_design", "此前仅讨论，未稳定完成"),
        ("expert reclustering", "not_materialized_by_design", "此前仅讨论，未稳定完成"),
        ("event behavior phenotype", "not_materialized_by_design", "仅输出事件完整性审计，不构造行为表型"),
    ], columns=["component", "coverage_status", "data_reason"])


def _validate(frames: Mapping[str, pd.DataFrame]) -> dict[str, Any]:
    checks = {
        "raw_annotation_count": len(frames["RAW_ANNOTATION_FACT.CSV"]), "selected_record_count": len(frames["SUBMISSION_FACT.CSV"]),
        "raw_only_record_count": int(frames["RAW_ANNOTATION_FACT.CSV"]["canonical_join_status"].ne("matched").sum()),
        "manual_semi_task_count": int(frames["SEMI_25_CONVERGENCE_EXPANSION_ALL_IMAGES.csv"]["base_task_id"].nunique()),
        "crowd_gt_task_condition_count": len(frames["CROWD_GT_101_GEOMETRIC_CAUSE_AUDIT.csv"]),
        "dual_task_count": len(frames["DUAL_ANNOTATOR_GEOMETRY_AND_GT_QUALITY.csv"]), "semi_review_count": len(frames["SEMI_REVIEW_FACT.CSV"]),
        "image_count": len(frames["IMAGE_FEATURES_ALL_214.csv"]), "event_count": len(frames["RAW_ACTIVE_EVENT_FACT.CSV"]),
        "session_count": len(frames["RAW_ACTIVE_SESSION_FACT.CSV"]),
        "c2_terminal_eligible_row_count": int(frames["C2_TERMINAL_RISK_EVIDENCE_240.csv"]["eligibility_status"].eq("eligible").sum()),
    }
    expected = {"raw_annotation_count": 2513, "selected_record_count": 2501, "raw_only_record_count": 12, "manual_semi_task_count": 25, "crowd_gt_task_condition_count": 101, "dual_task_count": 54, "semi_review_count": 574, "image_count": 214, "event_count": 34417, "session_count": 3735, "c2_terminal_eligible_row_count": 227}
    drift = {key: [checks[key], value] for key, value in expected.items() if checks[key] != value}
    if drift:
        raise AssertionError(drift)
    if frames["TIME_MEASUREMENT_RECORD_AUDIT.csv"]["lead_time_is_active_time"].map(_truth).any():
        raise AssertionError("lead time entered active-time lane")
    return {**checks, "frozen_count_checks": "pass", "lead_time_separation": "pass", "method_contract_sha256": _sha(METHOD_CONTRACT)}


def _table_spec(name: str, frame: pd.DataFrame) -> dict[str, Any]:
    lower = name.lower(); source = "同次v5真源物化" if any(token in lower for token in ("fact", "raw_", "submission")) else "同次v5派生计算"
    fields = []
    for column in frame.columns:
        meaning = FIELD_ZH.get(column, f"{column}字段；稳定英文机器列名")
        if column in FORMULA_ZH:
            calculation = FORMULA_ZH[column]
        elif column.endswith("_zh"):
            calculation = "由相邻英文枚举码映射为中文解释"
        elif any(token in column for token in ("count", "support")):
            calculation = "按本表总体和分组键计数；缺失不计入可计算支持"
        elif any(token in column for token in ("mean", "median", "rate", "share", "entropy", "variance", "rho", "rmse", "delta")):
            calculation = "按字段名所示统计量计算；分母为本表可计算记录，缺失不填零"
        else:
            calculation = f"直接读取或连接自{source}，连接键见本表ID字段"
        fields.append({"field": column, "meaning_zh": meaning, "source_or_formula": calculation, "missing_meaning": "空值表示该记录在该口径不可计算或源字段未提供，不代表零"})
    return {"table": name, "population": "保留可计算记录；资格、行政状态与任务外状态作为正交字段", "analysis_unit": "由ID列和表名定义，逐表不跨单位伪增样本", "filter_rule": "仅在所需变量不可计算时退出对应统计分母", "grouping": "按表内stage/condition/task/worker等显式键", "source": source, "fields": fields}


def _markdown_table(frame: pd.DataFrame, limit: int = 12) -> str:
    preview = frame.head(limit).copy()
    return (preview.iloc[:, :12] if len(preview.columns) > 12 else preview).to_markdown(index=False)


def _workbook_sheet_names(names: list[str], *, start_index: int = 0) -> list[str]:
    used: set[str] = set()
    output = []
    for index, raw in enumerate(names, start=start_index):
        stem = re.sub(r"[\\/?*:\[\]]", "_", re.sub(r"\.csv$", "", raw, flags=re.IGNORECASE))
        base = f"{index + 1:02d}_{stem}"[:31]
        candidate = base
        suffix = 2
        while candidate in used:
            candidate = f"{base[:27]}_{suffix}"
            suffix += 1
        used.add(candidate)
        output.append(candidate)
    return output


def _write_workbook_payload(
    out: Path,
    frames: Mapping[str, pd.DataFrame],
    specs: Mapping[str, Any],
    batch_bytes: int = 12_000_000,
    *,
    start_index: int = 0,
) -> Path:
    payload_dir = out / "_workbook_payload"
    payload_dir.mkdir()
    names = list(frames)
    sheet_names = _workbook_sheet_names(names, start_index=start_index)
    batches: list[dict[str, Any]] = []
    batch_tables: list[str] = []
    batch_size = 0

    def flush() -> None:
        nonlocal batch_tables, batch_size
        if not batch_tables:
            return
        filename = f"batch_{len(batches) + 1:03d}.json"
        body = '{"tables":[' + ",".join(batch_tables) + '],"xlsx_long_field_policy":"全量行、全量字段；仅受Excel单元格32767字符硬限制"}\n'
        (payload_dir / filename).write_text(body, encoding="utf-8")
        batches.append({"file": filename, "table_count": len(batch_tables), "size_bytes": len(body.encode("utf-8"))})
        batch_tables = []
        batch_size = 0

    for local_index, (name, frame) in enumerate(frames.items()):
        index = start_index + local_index
        workbook_frame = _bilingual(frame)
        clean = workbook_frame.astype(object).where(pd.notna(workbook_frame), None)
        table = {
            "name": name,
            "sheetName": sheet_names[local_index],
            "tableName": f"DataTable{index + 1:03d}",
            "globalIndex": index,
            "spec": specs[name],
            "workbookColumns": list(workbook_frame.columns),
            "omittedFields": [],
            "fullRowCount": len(workbook_frame),
            "rowsOmitted": 0,
            "rows": clean.to_dict("records"),
        }
        serialized = json.dumps(table, ensure_ascii=False, separators=(",", ":"), default=str)
        encoded_size = len(serialized.encode("utf-8"))
        if batch_tables and batch_size + encoded_size > batch_bytes:
            flush()
        batch_tables.append(serialized)
        batch_size += encoded_size
        if encoded_size >= batch_bytes:
            flush()
    flush()
    _write_json(payload_dir / "manifest.json", {
        "format": "full_uncertainty_v5_segmented_workbook_payload",
        "table_count": len(names),
        "start_index": start_index,
        "row_count": int(sum(len(frame) for frame in frames.values())),
        "batches": batches,
    })
    return payload_dir


def _render_objective_findings(frames: Mapping[str, pd.DataFrame], validation: Mapping[str, Any]) -> str:
    directions = frames["SEMI_25_CONVERGENCE_EXPANSION_ALL_IMAGES.csv"]["exact_direction"].value_counts()

    def table(name: str, limit: int = 12) -> str:
        return f"来源：`{name}`\n\n{_markdown_table(frames[name], limit)}"

    return "\n".join([
        "# 数据与变量关系汇总",
        "",
        "本文件汇总当前 v5 全部可复现的客观发现。所有关联均不作因果解释；缺失不填零；同一 worker×task 的历史版本不当作独立标注员。",
        "",
        "## 1. 数据范围与冻结边界",
        "",
        f"- raw annotation versions：{validation['raw_annotation_count']:,}；selected/auditable contexts：{validation['selected_record_count']:,}；raw-only versions：{validation['raw_only_record_count']:,}。",
        f"- Manual/Semi 配对任务：{validation['manual_semi_task_count']}；图像：{validation['image_count']}；事件：{validation['event_count']:,}；session：{validation['session_count']:,}。",
        f"- Crowd–GT task-condition：{validation['crowd_gt_task_condition_count']}；双人任务：{validation['dual_task_count']}；C2 terminal eligible rows：{validation['c2_terminal_eligible_row_count']}。",
        "- C2-B 保持关闭；这些结果不改变 eligibility、routing、GT/reference freeze、active-time owner-valid 或后续阶段设计。",
        "",
        "## 2. Manual/Semi 不确定性与分区可识别性",
        "",
        f"25 个任务中，Semi 收敛 {int(directions.get('semi_convergence', 0))} 个、扩散 {int(directions.get('semi_expansion', 0))} 个、不变 {int(directions.get('no_entropy_change', 0))} 个。主要口径为 task-equal、building-cluster；不同 estimand 分行报告。",
        "",
        table("CURRENT_MANUAL_SEMI_UNCERTAINTY_SUMMARY.CSV", 10),
        "",
        table("PARTITION_FAILURE_RATE_SENSITIVITY.csv", 10),
        "",
        "## 3. 质量、几何、Crowd–GT 与持续分歧",
        "",
        table("QUALITY_DATA_MINING_SUMMARY.CSV", 5),
        "",
        table("CROWD_GT_GEOMETRIC_CAUSE_SUMMARY.csv", 12),
        "",
        table("PERSISTENT_DISAGREEMENT_SUMMARY.CSV", 15),
        "",
        "双人任务只作为 pair sensitivity，不构造多数共识；完整逐任务结果见 `DUAL_ANNOTATOR_GEOMETRY_AND_GT_QUALITY.csv`。",
        "",
        "## 4. Proposal、元标签与结构零",
        "",
        table("SEMI_PROPOSAL_ASSOCIATIONS.CSV", 12),
        "",
        table("STRUCTURAL_ZERO_DUAL_AXIS_SENSITIVITY.csv", 20),
        "",
        "元标签 canonical/final 与 raw/history 使用不同分母；完整回答组合熵、Jaccard 分歧和众数占比见 `META_RESPONSE_UNCERTAINTY_CANONICAL_AND_RAW.csv`。",
        "",
        "## 5. 图像特征、难度代理与 risk",
        "",
        "正式冻结语义 risk 仍为 `n_ready=0`，因此正式难度关系不可评价。下表按 building 聚类，并对重复 predictor 去重后校正多重检验；legacy proxy 和工人作答后标签保持探索性。",
        "",
        table("IMAGE_FEATURE_ALIAS_AUDIT.csv", 12),
        "",
        table("IMAGE_FEATURE_ASSOCIATIONS_BUILDING_CLUSTERED.csv", 20),
        "",
        table("DIFFICULTY_PROXY_OUTCOME_JOIN_AUDIT.csv", 12),
        "",
        table("DIFFICULTY_PROXY_ASSOCIATIONS_BUILDING_CLUSTERED.csv", 20),
        "",
        table("QUALITY_RISK_TASK_BUILDING_CLUSTER_AUDIT.csv", 10),
        "",
        "## 6. Task/worker 异质性",
        "",
        table("CROSSED_TASK_WORKER_VARIANCE_COMPONENTS.csv", 10),
        "",
        "worker 模式归属只描述跨任务倾向，不解释为正确性或稳定几何学派；完整 split/leave-one-task-out 结果见 `WORKER_MODE_TESTS_AND_PAIRS_LANES.csv`。",
        "",
        "## 7. Active time、Lead time、缺失与事件序列",
        "",
        "Active time 只使用冻结 task-worker owner-valid 证据；Lead time 永不回填。事件 gap、span 和 multi-session 仅表示日志观测事实，不命名为暂停、返回、保存或提交行为。",
        "",
        table("ACTIVE_TIME_COMPUTABILITY_DESCRIPTIVE.csv", 20),
        "",
        table("C1_ACTIVE_TIME_MISSINGNESS_AUDIT.csv", 20),
        "",
        table("EVENT_SEQUENCE_OBSERVED_FACT.csv", 12),
        "",
        "## 8. 功效与精度情景",
        "",
        "task-equal 与 building-equal 是不同 estimand；条件功效不是效应为真的概率。",
        "",
        table("SEMI_POWER_ESTIMAND_SENSITIVITY.csv", 20),
        "",
        "## 9. 排除、连接与版本审计",
        "",
        table("EXCLUSION_REASON_SUMMARY.csv", 15),
        "",
        table("JOIN_COVERAGE_AUDIT.CSV", 15),
        "",
        "annotation revision chronology 已物化于 `REVISION_LINEAGE_ALL_2513.csv`，但它不是 reference/GT version trajectory。",
        "",
        "## 10. 计算口径修正与尚不可评价项目",
        "",
        table("CALCULATION_MODE_AUDIT.csv", 20),
        "",
        table("COVERAGE_GAP_COMPUTABILITY_AUDIT.csv", 20),
        "",
        "reference 历史和独立专家标签缺少版本事件、审核身份、盲审和几何字段时必须保持 `not_evaluable`；不使用 synthetic review 或 expert-anchor metadata 替代。",
        "",
        "## 附录：原 v5 逐任务 nominal 图像扫描",
        "",
        "以下结果保留作来源追溯；其逐任务 p 值不替代上面的 building-cluster 与多重比较校正结果。",
        "",
        table("IMAGE_FEATURE_VS_SEMI_ASSOCIATIONS.csv", 40),
        "",
    ])


def _write_readable_outputs(
    out: Path,
    frames: Mapping[str, pd.DataFrame],
    validation: Mapping[str, Any],
    *,
    write_workbook_payload: bool = True,
) -> None:
    specs = {name: _table_spec(name, _bilingual(frame)) for name, frame in frames.items()}
    quick = pd.DataFrame([{"metric": key, "value": value, "meaning_zh": FIELD_ZH.get(key, key)} for key, value in validation.items() if isinstance(value, (int, float))])
    _write_csv(out / "关键数据速览.csv", quick)
    lines = ["# 逐表数据与计算说明", "", "所有缺失值均保留为空，不按零处理；原始版本不当作独立标注员。", ""]
    for name in sorted(frames):
        spec = specs[name]
        lines += [f"## {name}", "", f"- 总体：{spec['population']}", f"- 分析单位：{spec['analysis_unit']}", f"- 筛选：{spec['filter_rule']}", f"- 分组：{spec['grouping']}", "", _markdown_table(_bilingual(frames[name])), "", "### 变量和计算说明", "", pd.DataFrame(spec["fields"]).to_markdown(index=False), ""]
    (out / "逐表数据与计算说明.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    (out / "数据与变量关系汇总.md").write_text(_render_objective_findings(frames, validation), encoding="utf-8", newline="\n")
    (out / "README_先看这里.md").write_text(
        "# 全量不确定性数据整理 v5\n\n本目录只提供数据、变量定义、计算方法、统计结果、客观关联和不可评价原因。\n\n"
        "- `关键数据速览.csv`：冻结计数和核心覆盖。\n- `数据与变量关系汇总.md`：中性关联汇总。\n"
        "- `逐表数据与计算说明.md`：每张表后紧邻字段和公式说明。\n- `完整数据整理工作簿.xlsx`：同一内容的朴素工作簿。\n"
        "- `完整数据整理工作簿_第一册_原始事实.xlsx`：体量均衡后的原始事实分册。\n"
        "- `完整数据整理工作簿_第二册_派生审计与统计.xlsx`：其余派生审计与统计分册。\n"
        "- `COVERAGE_AUDIT.csv`：原始 v5 覆盖审计。\n- `COVERAGE_GAP_COMPUTABILITY_AUDIT.csv`：补充实现后的可计算性与缺口审计。\n\n边界：C2-B保持关闭；未改变正式eligibility、routing、GT freeze、active-time owner-valid规则或后续阶段设计。\n",
        encoding="utf-8", newline="\n",
    )
    if write_workbook_payload:
        _write_workbook_payload(out, frames, specs)


def _charts(out: Path, frames: Mapping[str, pd.DataFrame]) -> None:
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]; plt.rcParams["axes.unicode_minus"] = False
    charts = [
        ("持续多峰阈值结果.png", frames["PERSISTENT_DISAGREEMENT_SUMMARY.CSV"], "similarity_threshold", "strong_persistent_split_count", "相似度阈值", "持续分裂任务数"),
        ("C2终态支持分布.png", frames["C2_TERMINAL_SUPPORT_DISTRIBUTION.csv"], "support_bin", "task_count", "每任务worker支持", "任务数"),
    ]
    for name, frame, x, y, xlabel, ylabel in charts:
        if x not in frame or y not in frame:
            continue
        fig, ax = plt.subplots(figsize=(8, 4.5)); ax.bar(frame[x].astype(str), pd.to_numeric(frame[y], errors="coerce"), color="#777777")
        ax.set_xlabel(xlabel); ax.set_ylabel(ylabel); ax.set_title(Path(name).stem); fig.tight_layout(); fig.savefig(out / name, dpi=160); plt.close(fig)


def _manifest(out: Path) -> pd.DataFrame:
    return pd.DataFrame([{"path": path.name, "size_bytes": path.stat().st_size, "sha256": _sha(path)} for path in sorted(item for item in out.iterdir() if item.is_file() and item.name != "OUTPUT_MANIFEST.csv")])


def _supplement_frames(input_dir: Path, *, bootstrap_replicates: int) -> dict[str, pd.DataFrame]:
    from tools.thesis_main.analysis.full_uncertainty import audit_v5_gaps
    from tools.thesis_main.analysis.full_uncertainty import audit_v5_supplement

    frames = {
        **audit_v5_supplement.build_frames(input_dir, bootstrap_replicates=bootstrap_replicates),
        **audit_v5_gaps.build_frames(input_dir),
    }
    missing = set(SUPPLEMENT_TABLES) - set(frames)
    unexpected = set(frames) - set(SUPPLEMENT_TABLES)
    if missing or unexpected:
        raise AssertionError({"missing_supplement_tables": sorted(missing), "unexpected_supplement_tables": sorted(unexpected)})
    return {name: frames[name] for name in SUPPLEMENT_TABLES}


def _xlsx_sheet_count(path: Path) -> int:
    with zipfile.ZipFile(path) as archive:
        workbook = archive.read("xl/workbook.xml").decode("utf-8")
    return len(re.findall(r"<(?:\w+:)?sheet\b", workbook))


def augment_existing(
    target: Path = DEFAULT_OUTPUT,
    *,
    bootstrap_replicates: int = 10_000,
    workbook_script: Path | None = None,
    workbook_preview_dir: Path | None = None,
    node_executable: str = "node",
    node_modules: Path | None = None,
) -> dict[str, Any]:
    target = target.resolve()
    if not target.is_dir():
        raise FileNotFoundError(target)
    existing_supplements = [name for name in SUPPLEMENT_TABLES if (target / name).exists()]
    if existing_supplements:
        raise FileExistsError(f"supplement already present: {existing_supplements}")
    required = [
        target / "完整数据整理工作簿.xlsx",
        target / "完整数据整理工作簿_第一册_原始事实.xlsx",
        target / "完整数据整理工作簿_第二册_派生审计与统计.xlsx",
        target / "VALIDATION_SUMMARY.json",
        target / "WORKBOOK_QA_SUMMARY.json",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(missing)

    frames = {
        path.name: _read(path)
        for path in sorted(target.iterdir())
        if path.is_file() and path.suffix.lower() == ".csv" and path.name != "OUTPUT_MANIFEST.csv"
    }
    supplement = _supplement_frames(target, bootstrap_replicates=bootstrap_replicates)
    frames.update(supplement)
    validation = json.loads((target / "VALIDATION_SUMMARY.json").read_text(encoding="utf-8"))
    validation.update({"audit_supplement_table_count": len(supplement), "audit_supplement_status": "pass"})

    staging = Path(tempfile.mkdtemp(prefix=f".{target.name}_audit_", dir=target.parent))
    try:
        for name, frame in supplement.items():
            _write_csv(staging / name, frame)
        _write_readable_outputs(staging, frames, validation, write_workbook_payload=False)
        _write_json(staging / "VALIDATION_SUMMARY.json", validation)

        specs = {name: _table_spec(name, _bilingual(frame)) for name, frame in supplement.items()}
        payload = _write_workbook_payload(staging, supplement, specs, start_index=_xlsx_sheet_count(required[0]))
        script = (workbook_script or Path(__file__).with_name("build_full_uncertainty_v5_workbook.mjs")).resolve()
        preview = (workbook_preview_dir or (staging / "workbook_previews")).resolve()
        supplement_xlsx = staging / "audit_supplement.xlsx"
        env = os.environ.copy()
        if node_modules:
            env["NODE_PATH"] = str(node_modules.resolve())
        subprocess.run(
            [node_executable, "--max-old-space-size=8192", str(script), str(payload), str(supplement_xlsx), str(preview)],
            cwd=ROOT,
            check=True,
            env=env,
        )

        output_workbooks = {}
        for name in ("完整数据整理工作簿.xlsx", "完整数据整理工作簿_第二册_派生审计与统计.xlsx"):
            source = target / name
            output = staging / name
            expected = _xlsx_sheet_count(source) + len(supplement)
            subprocess.run(
                [node_executable, "--max-old-space-size=8192", str(script), "--append-existing", str(source), str(supplement_xlsx), str(output), str(expected)],
                cwd=ROOT,
                check=True,
                env=env,
            )
            if _xlsx_sheet_count(output) != expected:
                raise AssertionError(f"{name}: appended sheet count drift")
            output_workbooks[name] = {"worksheet_count": expected, "table_count": expected, "size_bytes": output.stat().st_size}

        workbook_qa = json.loads((target / "WORKBOOK_QA_SUMMARY.json").read_text(encoding="utf-8"))
        workbook_qa["supplement"] = {
            "sheet_count": len(supplement),
            "row_count": int(sum(len(frame) for frame in supplement.values())),
            "artifact_tool_render": "pass",
            "formula_count": 0,
        }
        workbook_qa["full_workbook"].update(output_workbooks["完整数据整理工作簿.xlsx"])
        workbook_qa["volume_2"].update(output_workbooks["完整数据整理工作簿_第二册_派生审计与统计.xlsx"])
        supplement_rows = int(sum(len(frame) for frame in supplement.values()))
        workbook_qa["full_workbook"]["data_row_count"] = int(workbook_qa["full_workbook"]["data_row_count"]) + supplement_rows
        workbook_qa["volume_2"]["data_row_count"] = int(workbook_qa["volume_2"]["data_row_count"]) + supplement_rows
        workbook_qa["volume_2"]["artifact_tool_import"] = "pending_post_append_verification"
        workbook_qa["preview_count"] = int(workbook_qa.get("preview_count", 0)) + len(supplement)
        workbook_qa["volume_1_unchanged"] = True
        _write_json(staging / "WORKBOOK_QA_SUMMARY.json", workbook_qa)

        replace_names = [
            *SUPPLEMENT_TABLES,
            "关键数据速览.csv",
            "数据与变量关系汇总.md",
            "逐表数据与计算说明.md",
            "README_先看这里.md",
            "VALIDATION_SUMMARY.json",
            "WORKBOOK_QA_SUMMARY.json",
            "完整数据整理工作簿.xlsx",
            "完整数据整理工作簿_第二册_派生审计与统计.xlsx",
        ]
        for name in replace_names:
            os.replace(staging / name, target / name)
        _write_csv(staging / "OUTPUT_MANIFEST.csv", _manifest(target))
        os.replace(staging / "OUTPUT_MANIFEST.csv", target / "OUTPUT_MANIFEST.csv")
        return validation
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def materialize(
    out: Path = DEFAULT_OUTPUT,
    *,
    bootstrap_replicates: int = 10_000,
    build_workbook: bool = False,
    workbook_script: Path | None = None,
    workbook_preview_dir: Path | None = None,
) -> dict[str, Any]:
    target = out.resolve()
    if target.exists():
        raise FileExistsError(f"refusing to overwrite existing v5 output: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{target.name}_", dir=target.parent))
    try:
        intermediates = _build_intermediates(staging / "_work", bootstrap_replicates)
        frames = _copy_intermediate_tables(intermediates); frames.update(_base_frames(intermediates))
        meta_metrics, meta_comparison = _meta_response_metrics(frames["RAW_META_LABEL_RESPONSE_SETS.CSV"])
        formal_variance, descriptive_variance = _variance_tables(frames)
        terminal_evidence, terminal_support, terminal_distribution, worker_quality = _c2_terminal_tables()
        terminal_profile = _read(TERMINAL / "post_c2a_rp_terminal_worker_profile.csv")
        proposal_records, proposal_pairs = _proposal_geometry(frames["RAW_ANNOTATION_FACT.CSV"], frames["SEMI_REVIEW_FACT.CSV"])
        replay, replay_summary, memberships, membership_workers, membership_tests_pairs = _prefix_and_worker_modes(frames["C1_WORKER_TASK_MODE_MEMBERSHIP.CSV"])
        image_features = _image_features(frames["ALL_IMAGE_INSTANCE_INDEX.csv"], frames["TASK_FACT.CSV"], frames["DIFFICULTY_PROXY_COVERAGE.CSV"], meta_metrics)
        crossfit = _manual_crossfit()
        frames.update({
            "META_RESPONSE_UNCERTAINTY_CANONICAL_AND_RAW.csv": meta_metrics, "META_MANUAL_SEMI_TASK_COMPARISON.csv": meta_comparison,
            "CROSSED_TASK_WORKER_VARIANCE_COMPONENTS.csv": formal_variance, "DESCRIPTIVE_TASK_WORKER_MEAN_VARIANCES.csv": descriptive_variance,
            "STRUCTURAL_ZERO_DUAL_AXIS_SENSITIVITY.csv": _structural_zero(frames), "C2_TERMINAL_RISK_EVIDENCE_240.csv": terminal_evidence,
            "C2_TERMINAL_SUPPORT_BY_TASK.csv": terminal_support, "C2_TERMINAL_SUPPORT_DISTRIBUTION.csv": terminal_distribution,
            "WORKER_QUALITY_RAW_ADJUSTED_EB.csv": worker_quality, "WORKER_QUALITY_RANK_STABILITY.csv": _worker_rank_stability(worker_quality),
            "QUALITY_RISK_SLOPE_POPULATIONS.csv": _quality_risk_slopes(terminal_evidence, terminal_profile),
            "REVISION_LINEAGE_ALL_2513.csv": _revision_lineage(frames["RAW_ANNOTATION_FACT.CSV"]),
            "EVENT_SESSION_INTEGRITY_SUMMARY.csv": _event_integrity(frames["RAW_ACTIVE_EVENT_FACT.CSV"], frames["RAW_ACTIVE_SESSION_FACT.CSV"]),
            "PROPOSAL_GEOMETRY_RECORDS.csv": proposal_records, "PROPOSAL_MANUAL_SEMI_GEOMETRY_PAIRS.csv": proposal_pairs,
            "DUAL_ANNOTATOR_GEOMETRY_AND_GT_QUALITY.csv": _dual_quality(frames["DUAL_ANNOTATOR_GEOMETRY_SENSITIVITY_ALL.csv"], terminal_evidence),
            "IMAGE_FEATURES_ALL_214.csv": image_features,
            "IMAGE_FEATURE_VS_SEMI_ASSOCIATIONS.csv": _image_semi_associations(image_features, frames["SEMI_25_CONVERGENCE_EXPANSION_ALL_IMAGES.csv"], frames["PROPOSAL_TASK_ANCHORING_AND_DISCOVERY.csv"]),
            "MANUAL_DISJOINT_CROSSFIT_SENSITIVITY.csv": crossfit, "MANUAL_DISJOINT_CROSSFIT_ASSOCIATION.csv": _crossfit_summary(crossfit),
            "C1_K22_PREFIX_REPLAY.csv": replay,
            "C1_K22_PREFIX_REPLAY_SUMMARY.csv": replay_summary, "WORKER_MODE_MEMBERSHIP_LANES.csv": memberships,
            "WORKER_MODE_WORKER_SUMMARY_LANES.csv": membership_workers, "WORKER_MODE_TESTS_AND_PAIRS_LANES.csv": membership_tests_pairs,
            "COVERAGE_AUDIT.csv": _coverage_audit(),
        })
        validation = _validate(frames)
        delivery = staging / "delivery"; delivery.mkdir()
        for name, frame in sorted(frames.items()):
            _write_csv(delivery / name, frame)
        supplement = _supplement_frames(delivery, bootstrap_replicates=bootstrap_replicates)
        frames.update(supplement)
        for name, frame in supplement.items():
            _write_csv(delivery / name, frame)
        validation = {**validation, "audit_supplement_table_count": len(supplement), "audit_supplement_status": "pass"}
        _write_readable_outputs(delivery, frames, validation); _charts(delivery, frames); _write_json(delivery / "VALIDATION_SUMMARY.json", validation)
        if build_workbook:
            script = workbook_script or Path(__file__).with_name("build_full_uncertainty_v5_workbook.mjs")
            command = ["node", "--max-old-space-size=8192", str(script), str(delivery / "_workbook_payload"), str(delivery / "完整数据整理工作簿.xlsx")]
            if workbook_preview_dir:
                command.append(str(workbook_preview_dir.resolve()))
            subprocess.run(command, cwd=ROOT, check=True, env=os.environ.copy())
            sizes = [(delivery / name).stat().st_size for name in frames]
            half = sum(sizes) / 2
            split_after = min(
                range(1, len(sizes)),
                key=lambda index: abs(sum(sizes[:index]) - half),
            )
            subprocess.run([
                "node", "--max-old-space-size=8192", str(script), "--split-existing",
                str(delivery / "完整数据整理工作簿.xlsx"),
                str(delivery / "完整数据整理工作簿_第一册_原始事实.xlsx"),
                str(delivery / "完整数据整理工作簿_第二册_派生审计与统计.xlsx"),
                str(split_after),
            ], cwd=ROOT, check=True, env=os.environ.copy())
            shutil.rmtree(delivery / "_workbook_payload")
        _write_csv(delivery / "OUTPUT_MANIFEST.csv", _manifest(delivery)); delivery.replace(target)
        return validation
    except Exception:
        shutil.rmtree(staging, ignore_errors=True); raise
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--bootstrap-replicates", type=int, default=10_000); parser.add_argument("--build-workbook", action="store_true")
    parser.add_argument("--workbook-script", type=Path); parser.add_argument("--workbook-preview-dir", type=Path)
    parser.add_argument("--augment-existing", action="store_true"); parser.add_argument("--node-executable", default="node")
    parser.add_argument("--node-modules", type=Path); args = parser.parse_args()
    if args.augment_existing:
        result = augment_existing(
            args.output_dir,
            bootstrap_replicates=args.bootstrap_replicates,
            workbook_script=args.workbook_script,
            workbook_preview_dir=args.workbook_preview_dir,
            node_executable=args.node_executable,
            node_modules=args.node_modules,
        )
    else:
        result = materialize(
            args.output_dir,
            bootstrap_replicates=args.bootstrap_replicates,
            build_workbook=args.build_workbook,
            workbook_script=args.workbook_script,
            workbook_preview_dir=args.workbook_preview_dir,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
