#!/usr/bin/env python3
"""Assemble report tables from completed 20261026 analyses only.

No fusion, resampling, model fitting, seed generation, or partial-stage fallback.
English analytical fields are preserved and Chinese labels are appended.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys

import numpy as np
import pandas as pd

COMMIT = "b9bcec809fbaec8ab055931a1abb7baa5db44dac"
NATURAL = "analysis_precision26/results_stage2"
POLICY = "analysis_policy26/results"
PRESENTATION = "analysis_policy26/presentation"
COHORTS = ["old48", "new208", "pooled256"]
VERSIONS = ["old16", "new16", "pooled32"]
KEY_K = [1, 3, 6, 10, 20, 27, 30, 34, 35]
PRECISION_K = [3, 6, 10, 20, 30]
INTERVALS = ["3_to_6", "6_to_10", "10_to_20", "20_to_30", "30_to_35",
             "3_to_full", "10_to_full", "20_to_full", "30_to_full", "leave_one_out_to_full"]
IMETRICS = ["marginal_Q_delta", "paired_Q_delta", "paired_D10_delta", "Q_p10_delta",
            "Q_sd_delta", "actual_consensus_failure_delta", "output_unscoreable_delta",
            "failure_delta", "paired_Q_loss_gt5_rate", "floor_turn5_delta", "nodes_delta"]
PMETRICS = ["paired_Q_delta", "paired_D10_delta", "Q_p10_delta_common", "Q_sd_delta_common_ddof1",
            "QT_paired_Q_delta", "labor_ratio_legal", "actual_consensus_failure_delta",
            "output_generated_unscorable_delta", "failure_delta", "Q_loss_gt5_rate"]
META = ["pool_id", "image", "image_id", "building", "condition", "layer", "difficulty",
        "pool_n", "reference_id", "reference_version"]
ROLE_ZH = {"joint_highq_first": "历史联合高Q优先",
           "structure_moreturn_first": "历史较多转折优先",
           "joint_fast_first": "历史联合快速优先",
           "structure_dominant_first": "历史人数最多结构类优先"}
METRIC_ZH = {
    "Q_mean": "可评团队平均B8L2", "D10_mean": "可评团队平均D10",
    "Q_p10": "样本linear P10", "Q_p10_inverse_cdf": "经验逆CDF P10",
    "Q_sd_ddof1": "换同人数成员的Q标准差", "failure_rate": "非延期不可评分率（旧广义口径）",
    "actual_consensus_failure_rate": "真实共识失败率", "output_unscoreable_rate": "输出不可评分率",
    "reference_unavailable_rate": "参考不可用率", "not_executed_rate": "未执行率",
    "nodes_mean": "平均共识节点数", "floor_turn5_mean": "平均实际转折数",
    "floor_redundant5_mean": "平均近共线冗余点数",
    "marginal_Q_delta": "边际平均Q变化", "paired_Q_delta": "共同可评路径Q变化",
    "paired_D10_delta": "共同可评路径D10变化", "Q_p10_delta": "两个边际P10之差",
    "Q_sd_delta": "换组Q标准差变化", "actual_consensus_failure_delta": "真实共识失败率变化",
    "output_unscoreable_delta": "输出不可评分率变化",
    "output_generated_unscorable_delta": "输出不可评分率变化",
    "failure_delta": "非延期不可评分率变化（旧广义口径）",
    "paired_Q_loss_gt5_rate": "同路径Q损失超过5分比例", "floor_turn5_delta": "实际转折数变化",
    "nodes_delta": "节点数变化", "Q_p10_delta_common": "配对可评支持的P10变化",
    "Q_sd_delta_common_ddof1": "配对可评支持的换组SD变化",
    "QT_paired_Q_delta": "同源Q/T共同支持的Q变化",
    "labor_ratio_legal": "同源Q/T共同支持的逐路径劳动比均值",
    "Q_loss_gt5_rate": "策略比自然Q低超过5分的比例",
}
METRIC_LOWER_BETTER = {"Q_sd_delta", "actual_consensus_failure_delta", "output_unscoreable_delta",
                       "output_generated_unscorable_delta", "failure_delta", "Q_sd_delta_common_ddof1"}
METRIC_HIGHER_BETTER = {"marginal_Q_delta", "paired_Q_delta", "paired_D10_delta", "Q_p10_delta",
                        "Q_p10_delta_common", "QT_paired_Q_delta"}

# These names and required fields are taken from the completed-analysis code,
# not guessed from older reports or partially compiled tables.
INPUTS = {
    "curves": (f"{NATURAL}/NATURAL_CURVES.csv.gz", META + ["cohort", "k", "Q_mean", "Q_p10",
        "Q_sd_ddof1", "D10_mean", "paths_attempted", "quality_valid_paths", "unique_teams",
        "Q_mean_MCSE_analytic", "P10_linear_boot_halfwidth", "P10_order_halfwidth",
        "actual_executed_nondeferred_paths", "actual_consensus_failure_paths", "output_unscoreable_paths",
        "actual_consensus_failure_rate", "output_unscoreable_rate", "failure_rate", "fullN_single_known_team"]),
    "whole_curve": (f"{NATURAL}/FIXED_IMAGE_AGGREGATE_CURVE_BANDS.csv.gz", ["cohort", "panel", "layer",
        "difficulty", "metric", "weighting", "uncertainty", "k", "estimate", "images", "buildings",
        "capacity_images", "excluded_pool_ids", "pointwise_low", "pointwise_high", "pointwise_MCSE",
        "pointwise_valid_draws", "complete_bootstrap_draws", "support_rule"]),
    "pointwise": (f"{NATURAL}/COMMON_SUPPORT_CURVE_SUMMARY.csv.gz", ["cohort", "panel", "layer",
        "difficulty", "metric", "weighting", "k", "estimate", "images", "buildings",
        "path95_low", "path95_high", "building95_low", "building95_high", "support_rule"]),
    "precision": (f"{NATURAL}/PRECISION_REACH_BY_LAYER_K.csv.gz", ["cohort", "panel", "layer",
        "difficulty", "k", "images", "buildings", "mean_mcse_estimable_images", "mean_mcse_gt1_images",
        "P10_boot_estimable_images", "P10_boot_halfwidth_gt2_images", "P10_rank_estimable_images",
        "P10_rank_halfwidth_gt2_images", "actual_failure_estimable_images",
        "consensus_failure_CP_halfwidth_median", "output_unscoreable_CP_halfwidth_median"]),
    "intervals": (f"{NATURAL}/COMMON_SUPPORT_INTERVAL_SUMMARY.csv.gz", ["cohort", "panel", "layer",
        "difficulty", "interval", "metric", "weighting", "estimate", "images", "buildings",
        "positive_images", "negative_images", "near_zero_images", "path95_low", "path95_high",
        "path_valid_draws", "path_requested_draws", "building95_low", "building95_high", "support_rule"]),
    "image_intervals": (f"{NATURAL}/NATURAL_INTERVALS.csv.gz", META + ["cohort", "interval", "k_from",
        "k_to", "paths_attempted", "paired_Q_valid_paths", "from_Q_valid_paths", "to_Q_valid_paths"]),
    "common_keys": (f"{NATURAL}/COMMON_SUPPORT_KEYS.csv.gz", ["kind", "pool_id", "k", "interval", "metric", "common_cohorts"]),
    "interval_repetition": (f"{NATURAL}/INDEPENDENT_INTERVAL_REPETITION_SUMMARY.csv", ["older_cohort",
        "newer_cohort", "interval", "metric", "threshold", "layer", "difficulty", "images", "buildings",
        "both_near_zero", "one_active_one_near_zero", "both_active_same_direction", "both_active_opposite_direction"]),
    "old_new": (f"{NATURAL}/PER_IMAGE_OLD_NEW_COMPARISONS.csv.gz", META + ["k", "older_cohort", "newer_cohort",
        "old_paths", "new_paths", "old_Q_valid", "new_Q_valid", "old_actual_consensus_failures",
        "new_actual_consensus_failures", "old_output_unscoreable", "new_output_unscoreable",
        "new_consensus_failure_seen_after_zero_old", "new_output_unscoreable_seen_after_zero_old",
        "Q_mean_difference", "Q_p10_difference", "Q_sd_ddof1_difference"]),
    "curve_changes": (f"{NATURAL}/PER_IMAGE_FULL_CURVE_BATCH_DIFFERENCES.csv.gz", META + ["older_cohort",
        "newer_cohort", "metric", "comparable_k_n", "max_absolute_change", "k_at_max_absolute_change",
        "signed_change_at_max", "mean_absolute_change_over_k"]),
    "policy_summary": (f"{POLICY}/POLICY_PRECISION_SUMMARY.csv", ["version", "policy", "phase", "difficulty",
        "metric", "weighting", "estimate", "images", "candidate_images", "buildings", "positive_images",
        "negative_images", "nearzero_images", "path_lo", "path_hi", "path_valid_replicates",
        "path_invalid_replicates", "path_interval_status", "building_lo", "building_hi"]),
    "policy_support": (f"{POLICY}/FIXED_SUPPORT.csv.gz", ["pool_id", "image", "policy", "version", "phase",
        "metric", "candidate_k", "adopted_old16_k", "matched_k", "lost_k", "matched_k_list", "point",
        "valid_bootstraps", "invalid_bootstraps"]),
    "policy_k": (f"{POLICY}/POLICY_IMAGE_K.csv.gz", ["pool_id", "image", "building", "difficulty", "pool_n",
        "policy", "version", "k", "base_paths", "both_Q_paths", "legal_QT_paths"]),
    "policy_repeat": (f"{PRESENTATION}/POLICY_INDEPENDENT_BATCH_SUMMARY.csv", ["policy", "role_zh", "phase",
        "images", "buildings", "old16_mean", "new16_mean", "pooled32_mean", "both_positive_images",
        "both_negative_images", "opposite_nonzero_images", "both_nearzero_images", "one_nearzero_images"]),
    "policy_precision": (f"{PRESENTATION}/POLICY_PRECISION_COUNTS.csv", ["policy", "role_zh", "phase", "version",
        "candidate_images", "Q_images", "buildings", "median_Q_path_MCSE", "images_MCSE_gt1",
        "median_Q_path95_halfwidth", "images_incomplete_bootstrap_support"]),
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def read_json(path: Path) -> dict:
    require(path.is_file(), f"Required completion receipt missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def check_complete(root: Path, include_policy: bool) -> list[str]:
    """No ready-only or stage1 fallback. Check before creating an output dir."""
    names = [f"{NATURAL}/NATURAL_FINALIZATION_COMPLETE.json", f"{NATURAL}/ANALYSIS_RECEIPT.json",
             f"{NATURAL}/SUMMARY_RECEIPT.json"]
    final, analysis, summary = [read_json(root / x) for x in names]
    require(final.get("complete") is True and final.get("pools") == 194,
            "Full stage2 natural finalization of all 194 pools is required.")
    for name, receipt in [("analysis", analysis), ("summary", summary)]:
        require(receipt.get("complete_requested_pool_support") is True and receipt.get("pools") == 194,
                f"{name} receipt still has partial pool support.")
        require(receipt.get("stage") == 2, f"Wrong {name} stage.")
        require(receipt.get("source_commit") == COMMIT, f"Unexpected {name} source commit.")
    require(set(COHORTS) <= set(summary.get("cohorts", [])), "Final natural cohorts incomplete.")
    if include_policy:
        names += [f"{POLICY}/RECEIPT.json", f"{PRESENTATION}/RECEIPT.json"]
        policy, presentation = [read_json(root / x) for x in names[-2:]]
        require(policy.get("completed") is True and policy.get("images") == 157,
                "All 157 historical policy pools must be aggregated.")
        require(set(VERSIONS) <= set(policy.get("versions", [])), "Policy 16/16/32 versions incomplete.")
        require(presentation.get("complete") is True and presentation.get("images") == 157,
                "Full policy presentation summaries are not complete.")
    return names


def read_frame(root: Path, name: str, ledger: list, usecols=None) -> pd.DataFrame:
    rel, required = INPUTS[name]
    path = root / rel
    require(path.is_file(), f"Required finalized table missing: {path}")
    header = pd.read_csv(path, nrows=0).columns.tolist()
    require(set(required) <= set(header), f"Schema mismatch in {rel}: missing {sorted(set(required)-set(header))}")
    chosen = header if usecols is None else list(dict.fromkeys([*required, *[x for x in usecols if x in header]]))
    # Never let a 64-bit bootstrap/random seed pass through float inference.
    dtype = {c: "string" for c in chosen if c == "seed" or c.endswith("_seed") or c.endswith("_seed64")}
    frame = pd.read_csv(path, usecols=chosen, dtype=dtype, low_memory=False)
    ledger.append(dict(table=name, source=rel, rows=len(frame), fields=header,
                       bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    return frame


def bool_values(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)
    return series.fillna(False).astype(str).str.lower().isin(["true", "1", "1.0"])


def annotations(frame: pd.DataFrame) -> pd.DataFrame:
    f = frame.copy()
    maps = {
        "layer": {"ordinary_manual": "普通Manual", "doorway_manual": "门洞Manual"},
        "cohort": {"old48": "旧48条", "new208": "独立新208条", "pooled256": "合并256条",
                   "stage1_104": "独立新A104条", "stage2_104": "独立新B104条"},
        "version": {"old16": "旧16对", "new16": "独立新16对", "pooled32": "合并32对"},
        "weighting": {"image_equal": "图片等权", "building_equal": "建筑等权"},
        "uncertainty": {"paths_fixed_images": "固定图片的路径抽样范围",
                        "buildings_fixed_path_estimates": "固定单图估计的建筑重抽范围"},
        "metric": METRIC_ZH,
        "policy": ROLE_ZH,
        "phase": {"early_3_to_half": "3人至半池", "low_3_to_6": "3至6人",
                  "late_20_to_Nminus1": "20人至缺一人", "full": "实际满员"},
    }
    for column, mapping in maps.items():
        if column in f:
            label = "role_zh" if column == "policy" else column + "_zh"
            if label not in f:
                f[label] = f[column].map(mapping).fillna(f[column])
    if "policy" in f:
        require(set(f.policy.dropna()) <= set(ROLE_ZH), "Unexpected policy identity; do not relabel new classes.")
        f["role_version"] = "historical V3_BEHAVIOR / V3_JOINT_QT; not DSTRUCT / RFUSE"
    if "panel" in f:
        f["panel_zh"] = f.panel.map({"fixed_N_ge_27": "固定N≥27候选集",
            "fixed_N_ge_30": "固定N≥30候选集", "fixed_N_ge_35": "固定N≥35候选集",
            "all_available_at_k": "该k容量足够的候选集", "interval_eligible": "该区间容量合格候选集"}).fillna(f.panel)
    if "metric" in f and "positive_images" in f:
        f["favorable_images"] = np.where(f.metric.isin(METRIC_HIGHER_BETTER), f.positive_images,
            np.where(f.metric.isin(METRIC_LOWER_BETTER), f.negative_images, np.nan))
        f["unfavorable_images"] = np.where(f.metric.isin(METRIC_HIGHER_BETTER), f.negative_images,
            np.where(f.metric.isin(METRIC_LOWER_BETTER), f.positive_images, np.nan))
    if "metric" in f:
        probability = f.metric.str.contains("failure|unscoreable|unscorable|unavailable|not_executed|loss_gt5", regex=True)
        f["raw_unit_zh"] = np.where(probability, "比例或比例差（0至1尺度）",
            np.where(f.metric.eq("labor_ratio_legal"), "劳动比（1为相同劳动）", "沿原字段单位"))
        f["sign_reference"] = np.where(f.metric.eq("labor_ratio_legal"), 1.0, 0.0)
        f["sign_note_zh"] = np.where(f.metric.eq("labor_ratio_legal"),
            "原positive_images按0计号，不能当作费时图数；节时/费时图数见T04C与1比较", "正负图数沿原零阈值定义")
    return f


def keep_panels(frame: pd.DataFrame, interval=False, precision=False) -> pd.Series:
    ordinary = frame.layer.eq("ordinary_manual") & frame.panel.isin(["fixed_N_ge_30", "fixed_N_ge_35"])
    door = frame.layer.eq("doorway_manual")
    allowed = ["interval_eligible", "fixed_N_ge_30", "fixed_N_ge_35"] if interval else (
        ["all_available_at_k", "fixed_N_ge_30", "fixed_N_ge_35"] if precision else
        ["fixed_N_ge_27", "fixed_N_ge_30", "fixed_N_ge_35"])
    return ordinary | (door & frame.panel.isin(allowed))


def output_table(frame: pd.DataFrame, out: Path, name: str, source: str, manifest: list,
                 derived: str = "selection and Chinese labels only") -> pd.DataFrame:
    f = annotations(frame)
    f["source_table"] = source
    path = out / name
    raw = f.to_csv(index=False, lineterminator="\n").encode("utf-8")
    payload = gzip.compress(raw, compresslevel=6, mtime=0) if name.endswith(".gz") else raw
    temp = path.with_name(path.name + ".writing")
    temp.write_bytes(payload)
    temp.replace(path)
    op = gzip.open if name.endswith(".gz") else open
    with op(path, "rt", encoding="utf-8", newline="") as stream:
        rows = csv.reader(stream); fields = next(rows); n = 0
        require(fields == list(f.columns), f"Output header mismatch: {name}")
        for n, row in enumerate(rows, 1):
            require(len(row) == len(fields), f"Output row width mismatch: {name}:{n}")
    require(n == len(f), f"Output row count mismatch: {name}")
    manifest.append(dict(file=name, rows=n, fields=len(fields), bytes=path.stat().st_size,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(), source=source, transformation=derived,
        csv_and_gzip_read_to_EOF=True))
    return f


def difficulty_subsets(frame: pd.DataFrame):
    for layer, g in frame.groupby("layer", sort=True):
        yield layer, "全部" if layer == "ordinary_manual" else "单列", g
        if layer == "ordinary_manual":
            for difficulty, h in g.groupby("difficulty", dropna=False, sort=True):
                yield layer, str(difficulty), h


def add_candidate_flags(frame: pd.DataFrame) -> pd.DataFrame:
    f = frame.copy()
    f["ordinary_fixed_N_ge_30"] = f.layer.eq("ordinary_manual") & f.pool_n.ge(30)
    f["ordinary_fixed_N_ge_35"] = f.layer.eq("ordinary_manual") & f.pool_n.ge(35)
    f["doorway_all"] = f.layer.eq("doorway_manual")
    return f


def summary_support_mask(frame: pd.DataFrame, row) -> pd.Series:
    m = frame.layer.eq(row.layer)
    if row.difficulty not in ["全部", "单列"]:
        m &= frame.difficulty.astype(str).eq(str(row.difficulty))
    if row.panel.startswith("fixed_N_ge_"):
        m &= frame.pool_n.ge(int(row.panel.rsplit("_", 1)[1]))
    return m


def natural_tables(root: Path, out: Path, ledger: list, outputs: list) -> dict[str, pd.DataFrame]:
    extra = ["Q_p10_inverse_cdf", "failure_paths", "nondeferred_attempts", "reference_unavailable_paths",
             "not_executed_paths", "policy_deferred_paths", "actual_consensus_failure_CP_low",
             "actual_consensus_failure_CP_high", "actual_consensus_failure_one_sided_CP_high",
             "output_unscoreable_CP_low", "output_unscoreable_CP_high", "Q_p10_boot_low", "Q_p10_boot_high",
             "P10_order_low", "P10_order_high", "finite_population_teams", "empirical_constant_Q_nonfull"]
    curves = read_frame(root, "curves", ledger, extra)
    require(curves.pool_id.nunique() == 194, "NATURAL_CURVES does not contain all 194 pools.")
    require(not curves.duplicated(["pool_id", "cohort", "k"]).any(), "Duplicate natural curve keys.")
    meta = curves[META].drop_duplicates("pool_id")
    require(len(meta[meta.layer.eq("ordinary_manual")]) == 177 and len(meta[meta.layer.eq("doorway_manual")]) == 17,
            "Unexpected frozen Manual inventory.")
    inventory = []
    for layer, difficulty, g in difficulty_subsets(meta):
        for minimum in [0, 27, 30, 35]:
            h = g[g.pool_n.ge(minimum)]
            if h.empty:
                continue
            inventory.append(dict(layer=layer, difficulty=difficulty, minimum_pool_n=minimum,
                capacity_images=len(h), buildings=h.building.nunique(), min_N=int(h.pool_n.min()),
                max_N=int(h.pool_n.max()), pool_n_distribution=json.dumps({str(k):int(v) for k,v in h.pool_n.value_counts().sort_index().items()}),
                support_kind="capacity only; not quality-valid denominator"))
    output_table(pd.DataFrame(inventory), out, "T00_CAPACITY_INVENTORY.csv", INPUTS["curves"][0], outputs,
                 "pool metadata counts, no quality selection")
    whole = read_frame(root, "whole_curve", ledger)
    whole = whole[whole.cohort.isin(COHORTS) & whole.k.isin(KEY_K) & keep_panels(whole)].copy()
    whole["curve_support_scope"] = "same images over every legal k and every main cohort"
    t1 = output_table(whole, out, "T01A_FIXED_WHOLE_CURVE_KEYPOINTS.csv", INPUTS["whole_curve"][0], outputs)
    point = read_frame(root, "pointwise", ledger)
    point_metrics = ["D10_mean", "Q_p10_inverse_cdf", "nodes_mean", "floor_turn5_mean", "floor_redundant5_mean",
                     "failure_rate", "output_unscoreable_rate", "reference_unavailable_rate", "not_executed_rate"]
    point = point[point.cohort.isin(COHORTS) & point.k.isin(KEY_K) & point.metric.isin(point_metrics)
                  & keep_panels(point, precision=True)].copy()
    point["curve_support_scope"] = "common cohorts at this k; images may change across k"
    output_table(point, out, "T01B_POINTWISE_COMPONENTS_AND_STATES.csv", INPUTS["pointwise"][0], outputs)
    full = add_candidate_flags(curves[curves.cohort.isin(COHORTS) & curves.k.eq(curves.pool_n)])
    full["fullN_interpretation_zh"] = "每池唯一团队；相应指标可用才可记换组波动0；失败不填Q=0"
    output_table(full, out, "T01C_ACTUAL_FULL_PER_IMAGE.csv.gz", INPUTS["curves"][0], outputs)

    precision = read_frame(root, "precision", ledger)
    precision = precision[precision.cohort.isin(COHORTS) & precision.k.isin(PRECISION_K)
                          & keep_panels(precision, precision=True)].copy()
    for kind, estimable, exceed in [("mean_mcse_le1", "mean_mcse_estimable_images", "mean_mcse_gt1_images"),
            ("P10_boot_halfwidth_le2", "P10_boot_estimable_images", "P10_boot_halfwidth_gt2_images"),
            ("P10_rank_halfwidth_le2", "P10_rank_estimable_images", "P10_rank_halfwidth_gt2_images")]:
        precision[kind + "_images"] = precision[estimable] - precision[exceed]
        precision[kind + "_unestimable_images"] = precision.images - precision[estimable]
        precision[kind + "_fraction_of_estimable"] = precision[kind + "_images"].div(precision[estimable].replace(0, np.nan))
        precision[kind + "_fraction_of_candidate_images"] = precision[kind + "_images"] / precision.images
    t2 = output_table(precision, out, "T02A_SINGLE_IMAGE_PRECISION_REACH.csv", INPUTS["precision"][0], outputs,
        "pass=estimable minus exceeds target; unavailable retained, two P10 intervals separate")
    per = add_candidate_flags(curves[curves.cohort.isin(COHORTS) & curves.k.isin(PRECISION_K)])
    per = per[per.ordinary_fixed_N_ge_30 | per.doorway_all].copy()
    for label, col, threshold in [("mean_target_status", "Q_mean_MCSE_analytic", 1.),
             ("P10_boot_target_status", "P10_linear_boot_halfwidth", 2.),
             ("P10_rank_target_status", "P10_order_halfwidth", 2.)]:
        per[label] = np.where(per[col].isna(), "unestimable", np.where(per[col].le(threshold), "within_work_target", "exceeds_work_target"))
    output_table(per, out, "T02B_SINGLE_IMAGE_PRECISION_KEYPOINTS.csv.gz", INPUTS["curves"][0], outputs,
                 "individual existing estimates and explicit target status")

    intervals = read_frame(root, "intervals", ledger)
    intervals = intervals[intervals.cohort.isin(COHORTS) & intervals.interval.isin(INTERVALS)
                          & intervals.metric.isin(IMETRICS) & keep_panels(intervals, interval=True)].copy()
    ip = read_frame(root, "image_intervals", ledger, [])
    ip = ip[ip.cohort.isin(COHORTS)]
    keys = read_frame(root, "common_keys", ledger)
    keys = keys[keys.kind.eq("interval") & keys.metric.isin(IMETRICS)]
    keymap = {(name, metric): set(g.pool_id) for (name, metric), g in keys.groupby(["interval", "metric"])}
    summaries = []
    for row in intervals.itertuples(index=False):
        possible = ip[ip.cohort.eq(row.cohort) & ip.interval.eq(row.interval)]
        possible = possible[summary_support_mask(possible, row)]
        shared = possible[possible.pool_id.isin(keymap.get((row.interval, row.metric), set()))]
        require(len(shared) == row.images, f"Interval support mismatch: {row.interval}/{row.metric}/{row.panel}/{row.cohort}")
        r = row._asdict()
        r.update(candidate_images=len(possible), candidate_buildings=possible.building.nunique(),
            actual_k_from_min=possible.k_from.min(), actual_k_from_max=possible.k_from.max(),
            actual_k_to_min=possible.k_to.min(), actual_k_to_max=possible.k_to.max(),
            common_same_endpoint_images=int(shared.k_from.eq(shared.k_to).sum()),
            matched_path_occurrences=int(shared.paths_attempted.sum()),
            paired_Q_path_occurrences=int(shared.paired_Q_valid_paths.sum()),
            from_Q_path_occurrences=int(shared.from_Q_valid_paths.sum()),
            to_Q_path_occurrences=int(shared.to_Q_valid_paths.sum()),
            occurrence_interpretation="path counts summed over images; not independent rooms or persons")
        summaries.append(r)
    t3 = output_table(pd.DataFrame(summaries), out, "T03A_NATURAL_INTERVALS.csv", INPUTS["intervals"][0], outputs,
        "unchanged effect/ranges; candidate and path-support accounting joined from exact interval keys")
    repeat = read_frame(root, "interval_repetition", ledger)
    repeat = repeat[repeat.interval.isin(INTERVALS)].copy()
    repeat["panel"] = "interval_eligible"
    output_table(repeat, out, "T03B_INDEPENDENT_INTERVAL_DIRECTIONS.csv", INPUTS["interval_repetition"][0], outputs)
    return {"curves": curves, "meta": meta, "whole": t1, "precision": t2, "intervals": t3}


def policy_tables(root: Path, out: Path, ledger: list, outputs: list) -> dict[str, pd.DataFrame]:
    s = read_frame(root, "policy_summary", ledger)
    s = s[s.version.isin(VERSIONS) & s.phase.eq("early_3_to_half") & s.metric.isin(PMETRICS)].copy()
    t4 = output_table(s, out, "T04A_HISTORICAL_POLICY_EARLY_SUMMARY.csv", INPUTS["policy_summary"][0], outputs)
    support = read_frame(root, "policy_support", ledger)
    support = support[support.version.isin(VERSIONS) & support.phase.eq("early_3_to_half") & support.metric.isin(PMETRICS)]
    ktable = read_frame(root, "policy_k", ledger, [])
    ktable = ktable[ktable.version.isin(VERSIONS)]
    km = {key: g for key,g in ktable.groupby(["pool_id", "policy", "version"], sort=False)}
    rows = []
    for row in support.itertuples(index=False):
        g = km[(row.pool_id, row.policy, row.version)]
        ks = [int(x) for x in str(row.matched_k_list).split("|") if x and x != "nan"]
        q = g[g.k.isin(ks)]
        require(len(q) == row.matched_k, "Policy fixed-k support disagrees with key table.")
        r = row._asdict()
        r.update(building=g.building.iloc[0], difficulty=g.difficulty.iloc[0], pool_n=g.pool_n.iloc[0],
                 base_paths_per_image=int(g.base_paths.iloc[0]),
                 matched_path_k_occurrences=int(q.base_paths.sum()),
                 both_Q_path_k_occurrences=int(q.both_Q_paths.sum()),
                 legal_QT_path_k_occurrences=int(q.legal_QT_paths.sum()))
        rows.append(r)
    support = pd.DataFrame(rows)
    output_table(support, out, "T04B_POLICY_EARLY_EXACT_SUPPORT.csv.gz", INPUTS["policy_support"][0], outputs,
                 "unchanged fixed-k supports plus direct counts from POLICY_IMAGE_K; not new bootstrap")
    qt = support[support.metric.isin(["QT_paired_Q_delta", "labor_ratio_legal"])]
    a = qt[qt.metric.eq("QT_paired_Q_delta")].set_index(["pool_id", "policy", "version", "phase"])
    b = qt[qt.metric.eq("labor_ratio_legal")].set_index(["pool_id", "policy", "version", "phase"])
    require(a.index.equals(b.index), "Q/T metric support indexes differ; do not combine silently.")
    require(a.matched_k_list.fillna("").equals(b.matched_k_list.fillna("")), "Q/T fixed-k supports differ.")
    qt_common = a.copy()
    qt_common["labor_ratio_point"] = b.point
    qt_common = qt_common.reset_index()
    qt_rows = []
    for (policy,version), g in qt_common.groupby(["policy","version"]):
        for difficulty, h in [("全部",g), *[(str(d), z) for d,z in g.groupby("difficulty", dropna=False)]]:
            h = h[h.point.notna() & h.matched_k.gt(0)]
            qt_rows.append(dict(policy=policy,version=version,phase="early_3_to_half",difficulty=difficulty,
                images=len(h),buildings=h.building.nunique(),
                legal_QT_path_k_occurrences=int(h.legal_QT_path_k_occurrences.sum()),
                matched_path_k_occurrences=int(h.matched_path_k_occurrences.sum()),
                retained_k_min=h.matched_k.min(),retained_k_max=h.matched_k.max(),
                images_losing_old_k=int(h.lost_k.gt(0).sum()),
                images_with_inestimable_bootstrap_draws=int(h.invalid_bootstraps.gt(0).sum()),
                labor_saving_images=int(h.labor_ratio_point.lt(1-1e-9).sum()),
                labor_increasing_images=int(h.labor_ratio_point.gt(1+1e-9).sum()),
                labor_equal_images=int(h.labor_ratio_point.sub(1).abs().le(1e-9).sum()),
                Q_improving_and_labor_saving_images=int((h.point.gt(1e-9)&h.labor_ratio_point.lt(1-1e-9)).sum()),
                time_semantics="same source; complete positive times; both endpoints Q valid",
                ratio_estimand="arithmetic mean of legal paired-path ratios; not ratio of total labor"))
    output_table(pd.DataFrame(qt_rows), out, "T04C_POLICY_QT_COMMON_SUPPORT.csv", INPUTS["policy_support"][0], outputs,
                 "exact common Q/T support counts; no effects or uncertainty recomputed")
    for key, name in [("policy_repeat", "T04D_POLICY_INDEPENDENT_REPETITION.csv"),
                      ("policy_precision", "T04E_POLICY_SINGLE_IMAGE_PRECISION.csv")]:
        d = read_frame(root, key, ledger)
        output_table(d[d.phase.eq("early_3_to_half")], out, name, INPUTS[key][0], outputs)
    return {"policy": t4}


def change_tables(root: Path, out: Path, ledger: list, outputs: list, curves: pd.DataFrame) -> dict[str, pd.DataFrame]:
    d = read_frame(root, "old_new", ledger)
    comparison = ((d.older_cohort.eq("old48") & d.newer_cohort.isin(["new208", "pooled256"])) |
                  (d.older_cohort.eq("stage1_104") & d.newer_cohort.eq("stage2_104")))
    d = d[comparison & d.k.ne(2)].copy()
    # Attach actual attempt denominators; a requested or deferred zero is not a zero-event opportunity.
    attempt = curves[["pool_id", "cohort", "k", "actual_executed_nondeferred_paths"]]
    for suffix, cohortcol in [("old", "older_cohort"), ("new", "newer_cohort")]:
        lookup = attempt.rename(columns={"cohort":cohortcol, "actual_executed_nondeferred_paths":suffix+"_actual_attempts"})
        d = d.merge(lookup,on=["pool_id",cohortcol,"k"],how="left",validate="many_to_one")
    flags = ["new_consensus_failure_seen_after_zero_old", "new_output_unscoreable_seen_after_zero_old"]
    for col in flags:
        d[col] = bool_values(d[col])
    newly = add_candidate_flags(d[d[flags].any(axis=1)])
    newly["interpretation_zh"] = "旧样本零次、新样本出现；描述模式被观察到，不表示固定算法发生变化"
    output_table(newly, out, "T05A_NEWLY_OBSERVED_FAILURE_CASES.csv.gz", INPUTS["old_new"][0], outputs)
    rows = []
    for (older,newer), part in d.groupby(["older_cohort","newer_cohort"],sort=False):
        for panel,minimum in [("all_legal_k",0),("fixed_N_ge_30",30),("fixed_N_ge_35",35)]:
            q = part if minimum == 0 else part[part.pool_n.ge(minimum) & part.k.le(minimum)]
            for layer,difficulty,g in difficulty_subsets(q):
                g = g[g.old_actual_attempts.gt(0) & g.new_actual_attempts.gt(0)]
                for state,oldcount,flag in [("actual_consensus_failure","old_actual_consensus_failures",flags[0]),
                                          ("output_unscoreable","old_output_unscoreable",flags[1])]:
                    opportunities = g[g[oldcount].eq(0)]
                    hit = opportunities[opportunities[flag]]
                    rows.append(dict(older_cohort=older,newer_cohort=newer,panel=panel,layer=layer,difficulty=difficulty,
                        state=state,state_zh="真实共识失败" if state=="actual_consensus_failure" else "输出不可评分",
                        comparable_pool_k=len(g),comparable_images=g.pool_id.nunique(),comparable_buildings=g.building.nunique(),
                        old_zero_event_pool_k=len(opportunities),old_zero_event_images=opportunities.pool_id.nunique(),
                        newly_observed_event_pool_k=len(hit),newly_observed_event_images=hit.pool_id.nunique(),
                        newly_observed_event_buildings=hit.building.nunique(),
                        new_event_fraction_of_old_zero_pool_k=len(hit)/len(opportunities) if len(opportunities) else np.nan,
                        denominator_note="pool-k are dependent; no interval or independent-image claim for this fraction"))
    t5 = output_table(pd.DataFrame(rows), out, "T05B_NEWLY_OBSERVED_FAILURE_SUMMARY.csv", INPUTS["old_new"][0], outputs,
        "descriptive state-specific zero-to-observed counts; all comparison opportunities retained")
    full = read_frame(root,"curve_changes",ledger)
    keep = ((full.older_cohort.eq("old48") & full.newer_cohort.isin(["new208","pooled256"])) |
            (full.older_cohort.eq("stage1_104") & full.newer_cohort.eq("stage2_104")))
    full = add_candidate_flags(full[keep])
    full["curve_scope"] = "each image's full comparable legal k up to actual N; capacity flags do not truncate k"
    output_table(full,out,"T05C_PER_IMAGE_FULL_CURVE_CHANGES.csv.gz",INPUTS["curve_changes"][0],outputs)
    summary=[]
    for (older,newer,metric), part in full.groupby(["older_cohort","newer_cohort","metric"],sort=False):
        for layer,difficulty,g in difficulty_subsets(part):
            summary.append(dict(older_cohort=older,newer_cohort=newer,metric=metric,layer=layer,difficulty=difficulty,
                images=g.pool_id.nunique(),buildings=g.building.nunique(),
                median_max_absolute_change=g.max_absolute_change.median(),p90_max_absolute_change=g.max_absolute_change.quantile(.9),
                images_any_k_change_gt1=int(g.max_absolute_change.gt(1).sum()),
                images_any_k_change_gt2=int(g.max_absolute_change.gt(2).sum()),
                images_any_k_change_gt5=int(g.max_absolute_change.gt(5).sum()),
                median_mean_absolute_change_over_k=g.mean_absolute_change_over_k.median(),
                curve_scope="each image's complete comparable k range; descriptive distribution, not a simultaneous confidence test"))
    output_table(pd.DataFrame(summary),out,"T05D_FULL_CURVE_CHANGE_SUMMARY.csv",INPUTS["curve_changes"][0],outputs,
                 "descriptive summaries of saved per-image whole-curve comparisons; no resampling")
    return {"new_failures":t5}


def md_table(frame: pd.DataFrame, columns: list[str]) -> str:
    """Small readable preview; CSV retains full precision and all rows."""
    def value(x):
        if pd.isna(x): return "NA"
        if isinstance(x,(float,np.floating)): return f"{x:.4f}".rstrip("0").rstrip(".")
        return str(x).replace("|","／").replace("\n"," ")
    if frame.empty: return "该选择没有可用行；查看来源状态与支持。\n"
    selected=frame[columns]
    return "|"+"|".join(columns)+"|\n|"+"|".join(["---"]*len(columns))+"|\n"+"\n".join(
        "|"+"|".join(value(x) for x in row)+"|" for row in selected.itertuples(index=False,name=None))+"\n"


def write_preview(out: Path, tables: dict, include_policy: bool) -> None:
    sections=["# 完整追加结果：主表阅读入口\n",
        "本文件从全部194池自然分析完成后的正式表生成；四策略另要求157池完成。这里没有新增bootstrap、融合或分类。CSV保留英文精确字段，中文映射用于阅读。\n",
        "Q_SD是换组差异，MCSE是均值估计误差。增加顺序改善估计，不改变固定k的真实团队分布。精度达标是工作尺；P10的经验bootstrap与逆CDF秩区间不是同一种区间。\n",
        "## 固定图集关键人数（合256、图片等权）\n"]
    c=tables["whole"]
    c=c[c.cohort.eq("pooled256") & c.weighting.eq("image_equal") & c.uncertainty.eq("paths_fixed_images")
        & c.difficulty.isin(["全部","单列"]) & c.metric.eq("Q_mean")]
    sections.append(md_table(c,["layer_zh","panel","k","capacity_images","images","buildings","estimate","pointwise_MCSE"]))
    sections.append("## 单图精度（合256，各P10定义分别显示）\n")
    q=tables["precision"];q=q[q.cohort.eq("pooled256") & q.difficulty.isin(["全部","单列"])
        & ((q.layer.eq("ordinary_manual") & q.panel.eq("fixed_N_ge_30")) | (q.layer.eq("doorway_manual") & q.panel.eq("all_available_at_k")))]
    sections.append(md_table(q,["layer_zh","panel","k","images","mean_mcse_le1_images","mean_mcse_le1_unestimable_images",
        "P10_boot_halfwidth_le2_images","P10_rank_halfwidth_le2_images"]))
    sections.append("## 各难度人数区间\n完整Q／P10／SD／失败以及路径和建筑范围见T03A；正负图数不把近零计作同向。\n")
    if include_policy:
        sections.append("## 历史四策略：3人至半池（图片等权）\n")
        p=tables["policy"];p=p[p.difficulty.eq("全部") & p.weighting.eq("image_equal")
            & p.metric.isin(["paired_Q_delta","QT_paired_Q_delta","labor_ratio_legal"])]
        sections.append(md_table(p,["role_zh","version","metric_zh","images","buildings","estimate","path_lo","path_hi","building_lo","building_hi"]))
    sections += ["## 文件与口径\n",
        "- T01A固定整段图片；T01B是逐点共同支持，不能将两者无说明拼成一条曲线。T01C保存实际满员逐图状态。\n",
        "- T02A保留可估、超目标、达标和不可估分母；T02B可定位每张图。两人延期不变成零失败。\n",
        "- T03A原样保留标准汇总的效应、正负图数、路径范围与建筑范围，另接容量和实际路径支持。门洞20→30可能少于17图，30→35可能只7图，实际支持见表。\n",
        "- T04使用历史V3角色，Q/T同来源且固定共同k；劳动比是合法逐路径比值的算术均值，不是总劳动之比。\n" if include_policy else "- 本次显式使用--natural-only，未生成策略表；不能称为全部主表完成。\n",
        "- T05记录旧零事件的新发现及所有单图全曲线变化。新增被观察到的失败不是算法改变；图×人数格不是独立图片。\n",
        "- 所有输出CSV/gzip均读至EOF；来源表SHA、行数与生成范围见KEY_TABLES_MANIFEST.json。\n"]
    (out/"README_ZH.md").write_text("\n".join(sections),encoding="utf-8")


def main() -> None:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base",type=Path,default=Path(__file__).resolve().parent.parent)
    ap.add_argument("--out",type=Path)
    ap.add_argument("--natural-only",action="store_true",help="Explicitly omit policies; still requires all194 natural finalization")
    ap.add_argument("--describe-inputs",action="store_true",help="Print static schemas only; reads no results")
    ap.add_argument("--check-only",action="store_true",help="Check completion receipts and table headers; write no output")
    args=ap.parse_args()
    if args.describe_inputs:
        print(json.dumps({k:{"path":v[0],"required_fields":v[1]} for k,v in INPUTS.items()},ensure_ascii=False,indent=2));return
    root=args.base.resolve();include_policy=not args.natural_only
    completion=check_complete(root,include_policy)
    names=[k for k in INPUTS if include_policy or not k.startswith("policy_")]
    for name in names:
        rel,required=INPUTS[name]
        require((root/rel).is_file(),f"Final table missing: {rel}")
        columns=pd.read_csv(root/rel,nrows=0).columns
        require(set(required)<=set(columns),f"Schema mismatch {rel}: {sorted(set(required)-set(columns))}")
    if args.check_only:
        print(json.dumps(dict(complete=True,checked_headers=len(names),policy_included=include_policy,written_files=0)));return
    out=(args.out or root/"report26/key_tables").resolve();out.mkdir(parents=True,exist_ok=True)
    ledger=[];outputs=[]
    tables=natural_tables(root,out,ledger,outputs)
    if include_policy:tables.update(policy_tables(root,out,ledger,outputs))
    tables.update(change_tables(root,out,ledger,outputs,tables["curves"]))
    write_preview(out,tables,include_policy)
    manifest=dict(complete=True,scope="all five requested groups" if include_policy else "natural groups only, policies explicitly omitted",
        source_commit=COMMIT,new_fusion=0,new_paths=0,new_bootstrap=0,new_models=0,
        completion_receipts=completion,inputs=ledger,outputs=outputs,
        count_interpretation="Images/buildings and dependent path/k occurrences separately retained",
        natural_cohorts=COHORTS,policy_versions=VERSIONS if include_policy else [],
        natural_full_pool_gate=194,policy_pool_gate=157 if include_policy else None)
    (out/"KEY_TABLES_MANIFEST.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(dict(output=str(out),tables=len(outputs),rows=sum(x["rows"] for x in outputs),
        new_fusion=0,new_bootstrap=0,policy_included=include_policy),ensure_ascii=False))


if __name__ == "__main__":
    main()
