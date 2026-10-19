#!/usr/bin/env python3
"""Discovery-only count-vector search, effect directions and explicit counterexamples.

This does not refit personnel classes, score or fuse. It reads cell summaries
whose members and fixed references have already been checked. All observed
count-vector pairs are examined for coverage; groups with at least the stated
common-image support are retained, whether successful or not. Replicates and
teams are never interpreted as new independent buildings/images.
"""
from __future__ import annotations

import argparse
import collections
import itertools
import json
import math
import os
from pathlib import Path

for _key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_key, "1")
import numpy as np
import pandas as pd
from fusion_runner import read, write
from summarize_grid import compact_json, sha


def save_table(path, rows):
    frame = rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(rows)
    frame.to_csv(path, index=False, float_format="%.10g", compression={"method": "gzip", "mtime": 0} if str(path).endswith(".gz") else None)
    return frame


def finite(a):
    return np.asarray(a, dtype=float)[np.isfinite(a)]


def mean(a):
    x = finite(np.asarray(a, dtype=float))
    return float(x.mean()) if len(x) else np.nan


def dist(a, prefix):
    a = finite(np.asarray(a, dtype=float))
    return {prefix + "_" + key: float(fn(a)) if len(a) else np.nan for key, fn in (
        ("mean", np.mean), ("median", np.median), ("p10", lambda x: np.quantile(x, .1)),
        ("min", np.min), ("max", np.max))}


def support(g):
    return dict(images=int(g.image_id.nunique()), buildings=int(g.building.nunique()), pools=int(g.pool_id.nunique()),
                unique_teams=int(g.unique_team_n.sum()), requests=int(g.request_n.sum()),
                member_draw_pairs=int(g.within_unique_team_pair_n.sum()),
                missing_computations=int(g.missing_computation_n.sum()), scored_teams=int(g.score_available_n.sum()),
                complete_teams=int(g.complete_n.sum()))


def aggregate_compositions(cells):
    rows = []
    for (mid, dom, k, comp), g in cells.groupby(["method_id", "domain", "k", "composition"], sort=True):
        for difficulty in ["all"] + sorted(g.difficulty.unique()):
            h = g if difficulty == "all" else g[g.difficulty == difficulty]
            row = dict(method_id=mid, domain=dom, k=k, composition=comp, difficulty=difficulty, **support(h))
            row.update(active_classes=int(h.active_classes.iloc[0]),
                       image_ids="|".join(sorted(h.image.unique())), building_ids="|".join(sorted(h.building.unique())))
            row.update(dist(h.B8L2_mean, "image_cell_B8L2"))
            row.update(dist(h.groupby("building").B8L2_mean.mean(), "building_B8L2"))
            for metric in ("D10_mean", "B8L2_p10", "B8L2_worst", "complete_rate", "score_available_rate", "new_n_mean",
                           "nodes_mean", "iou_2d_mean", "IoU3D100_mean", "omission_mean", "extension_mean",
                           "diag_wall_coverage_03_mean", "diag_wall_coverage_05_mean", "diag_corner_recall_05_mean",
                           "within_abs_B8L2_change_mean", "within_abs_B8L2_change_max", "within_joint_stable_main_rate",
                           "within_floor_jaccard_difference_mean", "within_structure_bound_cyclic_deg_mean",
                           "within_mean_height_prism_pair_iou_mean", "within_turnover_mean"):
                row[metric] = mean(h[metric])
            row["complete_rate_pooled_teams"] = row["complete_teams"] / row["unique_teams"]
            rows.append(row)
    return rows


def effect_row(a, b, key):
    """Same pool/image/k, separate actual member resamples on each side."""
    q = b.B8L2_mean.to_numpy() - a.B8L2_mean.to_numpy()
    ca, cb = json.loads(a.counts_json.iloc[0]), json.loads(b.counts_json.iloc[0])
    row = dict(method_id=key[0], domain=key[1], k=key[2], composition_a=a.composition.iloc[0],
               composition_b=b.composition.iloc[0], difficulty="all", images=len(a),
               buildings=int(a.building.nunique()), unique_teams=int(a.unique_team_n.sum() + b.unique_team_n.sum()),
               count_vector_turnover=sum(abs(ca.get(c, 0) - cb.get(c, 0)) for c in set(ca) | set(cb)) // 2,
               both_all_teams_scored_images=int(((a.score_available_n == a.unique_team_n).to_numpy() & (b.score_available_n == b.unique_team_n).to_numpy()).sum()),
               min_replicates_a=int(a.unique_team_n.min()), min_replicates_b=int(b.unique_team_n.min()),
               mean_replicates_a=mean(a.unique_team_n), mean_replicates_b=mean(b.unique_team_n),
               pure_a=int(a.active_classes.iloc[0]) == 1, pure_b=int(b.active_classes.iloc[0]) == 1,
               image_ids="|".join(a.image), building_ids="|".join(sorted(a.building.unique())))
    row.update(dist(q, "B8L2_change"))
    valid = np.isfinite(q)
    row["quality_comparable_images"] = int(valid.sum())
    for tol in (0, 2, 5):
        row[f"improved_gt{tol}_images"] = int((q[valid] > tol).sum())
        row[f"worsened_ltminus{tol}_images"] = int((q[valid] < -tol).sum())
    row["positive_fraction"] = float((q[valid] > 0).mean()) if valid.any() else np.nan
    row["negative_fraction"] = float((q[valid] < 0).mean()) if valid.any() else np.nan
    building_changes = pd.DataFrame({"building": a.building.to_numpy(), "q": q}).groupby("building").q.mean()
    row.update(dist(building_changes, "building_B8L2_change"))
    row["improved_buildings"] = int((building_changes > 0).sum())
    row["worsened_buildings"] = int((building_changes < 0).sum())
    for metric in ("D10_mean", "B8L2_p10", "B8L2_worst", "complete_rate", "score_available_rate", "new_n_mean",
                   "nodes_mean", "iou_2d_mean", "IoU3D100_mean", "omission_mean", "extension_mean",
                   "diag_wall_coverage_03_mean", "diag_wall_coverage_05_mean", "diag_corner_recall_05_mean"):
        row[metric + "_change"] = mean(b[metric].to_numpy() - a[metric].to_numpy())
    for metric in ("B8L2_mean", "B8L2_p10", "B8L2_worst", "complete_rate", "score_available_rate", "new_n_mean",
                   "within_abs_B8L2_change_mean", "within_joint_stable_main_rate", "within_turnover_mean"):
        row[metric + "_a"] = mean(a[metric])
        row[metric + "_b"] = mean(b[metric])
    row["mean_abs_shift_to_within_abs_change_ratio"] = abs(row["B8L2_change_mean"]) / max(.1, (row["within_abs_B8L2_change_mean_a"] + row["within_abs_B8L2_change_mean_b"]) / 2)
    if valid.any():
        for tag, i in (("most_positive", int(np.nanargmax(q))), ("most_negative", int(np.nanargmin(q)))):
            row[tag + "_pool"] = a.pool_id.iloc[i]
            row[tag + "_image"] = a.image.iloc[i]
            row[tag + "_B8L2_change"] = float(q[i])
    return row


def search_all_count_vector_pairs(cells, minimum_images):
    """Coverage uses all observed cells; finite-Q support is separately recorded."""
    rows, ledger = [], []
    for key, g in cells.groupby(["method_id", "domain", "k"], sort=True):
        lookup = {comp: h.set_index("pool_id", drop=False).sort_index() for comp, h in g.groupby("composition")}
        # Count every observed within-image pair, including candidates that lack
        # enough independent image support for aggregate discovery ranking.
        pair_occurrences = int(sum(n * (n - 1) // 2 for n in g.groupby("pool_id").size()))
        compositions = sorted(lookup)
        supported = any_common = 0
        for ca, cb in itertools.combinations(compositions, 2):
            aa, bb = lookup[ca], lookup[cb]
            common = sorted(set(aa.index) & set(bb.index))
            if not common:
                continue
            any_common += 1
            if len(common) < minimum_images:
                continue
            a, b = aa.loc[common], bb.loc[common]
            rows.append(effect_row(a, b, key))
            supported += 1
        ledger.append(dict(method_id=key[0], domain=key[1], k=int(key[2]), observed_composition_cells=len(g),
                           unique_count_vectors=len(compositions), observed_within_image_count_vector_pairs=pair_occurrences,
                           count_vector_pair_groups_any_image=any_common, retained_pair_groups=supported,
                           omitted_pair_groups_below_image_support=any_common - supported,
                           minimum_common_images=minimum_images,
                           reason="every observed count-vector pair examined; low image support omitted only from compact aggregate table, all source cells retained"))
        print(compact_json(ledger[-1]), flush=True)
    return rows, ledger


def aggregate_mixtures(table):
    rows = []
    for key, g in table.groupby(["method_id", "domain", "k", "composition"], sort=True):
        complete = g[g.all_active_pures_scored == True]
        row = dict(method_id=key[0], domain=key[1], k=key[2], composition=key[3],
                   images_any_related_pure=int(g.image_id.nunique()), images_all_active_pures_scored=int(complete.image_id.nunique()),
                   buildings_all_active_pures_scored=int(complete.building.nunique()),
                   mixed_teams=int(g.mixed_unique_teams.sum()),
                   excluded_missing_pure_or_pure_score_images=int(g.image_id.nunique() - complete.image_id.nunique()))
        for name, h in (("all_active_pure_support", complete), ("available_pure_support", g)):
            metric = "mixed_minus_best_available_pure_B8L2_mean"
            x = h[metric]
            row.update(dist(x, name + "_gain_over_best"))
            row[name + "_beat_best_gt2_images"] = int((x > 2).sum())
            row[name + "_below_best_ltminus2_images"] = int((x < -2).sum())
            row[name + "_positive_fraction"] = float((x.dropna() > 0).mean()) if x.notna().any() else np.nan
        row.update(dist(complete.mixed_minus_weighted_pure_B8L2_mean, "gain_over_weighted"))
        for key2 in ("mixed_B8L2_mean", "mixed_B8L2_p10", "mixed_B8L2_worst", "mixed_complete_rate", "mixed_minus_weighted_pure_complete_rate"):
            row[key2] = mean(complete[key2])
        if len(complete) and complete.mixed_minus_best_available_pure_B8L2_mean.notna().any():
            metric = "mixed_minus_best_available_pure_B8L2_mean"
            for name, i in (("largest_gain", complete[metric].idxmax()), ("largest_loss", complete[metric].idxmin())):
                row[name + "_pool"] = complete.loc[i, "pool_id"]
                row[name + "_value"] = complete.loc[i, metric]
        rows.append(row)
    return rows


def method_coverage(cells):
    rows = []
    for key, g in cells.groupby(["method_id", "domain", "k"]):
        row = dict(method_id=key[0], domain=key[1], k=key[2], composition_cells=len(g),
                   distinct_count_vectors=int(g.composition.nunique()), **support(g))
        row.update(dist(g.within_abs_B8L2_change_mean, "cell_within_abs_Q"))
        row.update(dist(g.groupby("pool_id").B8L2_mean.agg(lambda x: x.max() - x.min()), "image_composition_mean_Q_range"))
        row["image_mean_within_joint_stable_main_rate"] = mean(g.groupby("pool_id").within_joint_stable_main_rate.mean())
        row["cells_4plus_unique_teams"] = int((g.unique_team_n >= 4).sum())
        row["exhaustive_member_cells"] = int(g.exhaustive_members.sum())
        rows.append(row)
    return rows


def choose_candidates(pairs, mixtures, cells, minimum_images=8, minimum_buildings=3, minimum_mixture_images=5):
    """Exploratory candidates plus counterexamples; no validation has been read."""
    rows = []
    if pairs.empty:
        return pd.DataFrame(columns=["kind", "method_id", "domain", "k", "composition_a", "composition_b", "images", "buildings",
                                     "mean_signed_B8L2_change", "directional_fraction", "positive_case_pool", "counterexample_pool",
                                     "counterexample_signed_B8L2_change"])
    all_supported = pairs[(pairs.quality_comparable_images >= minimum_images) & (pairs.buildings >= minimum_buildings)].copy()
    supported = all_supported.copy()
    # Orient only the reporting ranking, retaining original class labels and
    # signed A->B comparisons in the comprehensive table.
    supported["strength"] = supported.B8L2_change_mean.abs() * np.sqrt(supported.quality_comparable_images)
    supported["direction_fraction"] = np.where(supported.B8L2_change_mean >= 0,
                                               supported.positive_fraction, supported.negative_fraction)
    supported = supported[(supported.B8L2_change_mean.abs() >= 3) & (supported.direction_fraction >= .65)]
    for (mid, k), g in supported.groupby(["method_id", "k"]):
        # Keep one broad strongest shift and a genuinely one-count change,
        # avoiding a table filled with near-identical neighboring ratios.
        choices = [("broad_quality_shift", g.nlargest(1, "strength"))]
        adjacent = g[g.count_vector_turnover == 1]
        if len(adjacent):
            choices.append(("one_count_ratio_change", adjacent.nlargest(1, "strength")))
        for kind, h in choices:
            for _, r in h.iterrows():
                sign = 1 if r.B8L2_change_mean >= 0 else -1
                rows.append(dict(kind=kind, method_id=mid, domain=r.domain, k=k,
                                 composition_a=r.composition_a, composition_b=r.composition_b,
                                 recommended_direction="A_to_B" if sign > 0 else "B_to_A",
                                 images=r.images, buildings=r.buildings, mean_signed_B8L2_change=r.B8L2_change_mean,
                                 quality_comparable_images=r.quality_comparable_images, all_teams_scored_images=r.both_all_teams_scored_images,
                                 median_signed_B8L2_change=r.B8L2_change_median, directional_fraction=r.direction_fraction,
                                 within_Q_a=r.within_abs_B8L2_change_mean_a, within_Q_b=r.within_abs_B8L2_change_mean_b,
                                 within_joint_a=r.within_joint_stable_main_rate_a, within_joint_b=r.within_joint_stable_main_rate_b,
                                 new_n_change=r.new_n_mean_change, complete_rate_change=r.complete_rate_change,
                                 node_count_change=r.nodes_mean_change, corner_recall_change=r.diag_corner_recall_05_mean_change,
                                 wall_coverage_change=r.diag_wall_coverage_05_mean_change,
                                 positive_case_pool=r.most_positive_pool if sign > 0 else r.most_negative_pool,
                                 counterexample_pool=r.most_negative_pool if sign > 0 else r.most_positive_pool,
                                 counterexample_signed_B8L2_change=r.most_negative_B8L2_change if sign > 0 else r.most_positive_B8L2_change,
                                 status="discovered_not_validated"))
    structural = all_supported[(all_supported.B8L2_change_mean.abs() <= 2) &
          (all_supported.both_all_teams_scored_images >= .8 * all_supported.images) &
          ((all_supported.nodes_mean_change.abs() >= .75) | (all_supported.diag_corner_recall_05_mean_change.abs() >= .1) |
           (all_supported.diag_wall_coverage_05_mean_change.abs() >= .1))].copy()
    structural["strength"] = np.maximum(structural.nodes_mean_change.abs(),
                                        structural.diag_corner_recall_05_mean_change.abs() * 8)
    for (mid, k), g in structural.groupby(["method_id", "k"]):
        r = g.loc[g.strength.idxmax()]
        rows.append(dict(kind="similar_Q_different_structure", method_id=mid, domain=r.domain, k=k,
                         composition_a=r.composition_a, composition_b=r.composition_b, images=r.images, buildings=r.buildings,
                         quality_comparable_images=r.quality_comparable_images, all_teams_scored_images=r.both_all_teams_scored_images,
                         mean_signed_B8L2_change=r.B8L2_change_mean, median_signed_B8L2_change=r.B8L2_change_median,
                         within_Q_a=r.within_abs_B8L2_change_mean_a, within_Q_b=r.within_abs_B8L2_change_mean_b,
                         within_joint_a=r.within_joint_stable_main_rate_a, within_joint_b=r.within_joint_stable_main_rate_b,
                         new_n_change=r.new_n_mean_change, complete_rate_change=r.complete_rate_change,
                         node_count_change=r.nodes_mean_change, corner_recall_change=r.diag_corner_recall_05_mean_change,
                         wall_coverage_change=r.diag_wall_coverage_05_mean_change,
                         positive_case_pool=r.most_positive_pool, counterexample_pool=r.most_negative_pool,
                         counterexample_signed_B8L2_change=r.most_negative_B8L2_change, status="descriptive_structural_candidate; not_necessary_structure_GT"))
    if len(mixtures):
        eligible = mixtures[(mixtures.images_all_active_pures_scored >= minimum_mixture_images) & (mixtures.buildings_all_active_pures_scored >= 2)]
        for mid, g in eligible.groupby("method_id"):
            best = g.nlargest(1, "all_active_pure_support_gain_over_best_mean")
            for _, r in best.iterrows():
                rows.append(dict(kind="best_supported_mixture_even_if_not_successful", method_id=mid, domain=r.domain, k=r.k,
                                 composition_b=r.composition, images=r.images_all_active_pures_scored,
                                 buildings=r.buildings_all_active_pures_scored,
                                 mean_signed_B8L2_change=r.all_active_pure_support_gain_over_best_mean,
                                 directional_fraction=r.all_active_pure_support_positive_fraction,
                                 positive_case_pool=r.get("largest_gain_pool"), counterexample_pool=r.get("largest_loss_pool"),
                                 counterexample_signed_B8L2_change=r.get("largest_loss_value"),
                                 status="versus_all_active_pures_available; discovery_only; negative_winner_retained"))
    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=["kind", "method_id", "domain", "k", "composition_a", "composition_b", "images", "buildings",
                                     "mean_signed_B8L2_change", "directional_fraction", "positive_case_pool", "counterexample_pool",
                                     "counterexample_signed_B8L2_change"])


def case_candidates(cells, candidates, mixtures):
    rows = []
    index = cells.set_index(["method_id", "domain", "k", "pool_id", "composition"])
    for candidate in candidates.itertuples(index=False):
        if not isinstance(getattr(candidate, "composition_a", None), str):
            continue
        for kind, pid in (("representative_effect", candidate.positive_case_pool), ("counterexample", candidate.counterexample_pool)):
            ka = (candidate.method_id, candidate.domain, candidate.k, pid, candidate.composition_a)
            kb = (candidate.method_id, candidate.domain, candidate.k, pid, candidate.composition_b)
            if ka not in index.index or kb not in index.index:
                continue
            a, b = index.loc[ka], index.loc[kb]
            row = dict(kind=kind, method_id=candidate.method_id, domain=candidate.domain, k=candidate.k,
                       pool_id=pid, image=a.image, building=a.building, difficulty=a.difficulty,
                       composition_a=candidate.composition_a, composition_b=candidate.composition_b,
                       B8L2_change=b.B8L2_mean-a.B8L2_mean, B8L2_a=a.B8L2_mean, B8L2_b=b.B8L2_mean,
                       within_Q_a=a.within_abs_B8L2_change_mean, within_Q_b=b.within_abs_B8L2_change_mean,
                       joint_a=a.within_joint_stable_main_rate, joint_b=b.within_joint_stable_main_rate,
                       nodes_a=a.nodes_mean, nodes_b=b.nodes_mean,
                       corner_a=a.diag_corner_recall_05_mean, corner_b=b.diag_corner_recall_05_mean,
                       wall_a=a.diag_wall_coverage_05_mean, wall_b=b.diag_wall_coverage_05_mean,
                       team_keys_a=a.team_keys, team_keys_b=b.team_keys)
            rows.append(row)
    # Deliberately preserve stable-but-low-quality cells and visually different
    # cells with similar aggregate quality, even if they oppose an easy story.
    stable_wrong = cells[(cells.unique_team_n >= 4) & (cells.within_joint_stable_main_rate == 1) & (cells.B8L2_mean < 65)]
    for _, a in stable_wrong.nsmallest(8, "B8L2_mean").iterrows():
        choices = cells[(cells.method_id == a.method_id) & (cells.domain == a.domain) & (cells.k == a.k) & (cells.pool_id == a.pool_id)]
        b = choices.loc[choices.B8L2_mean.idxmax()]
        rows.append(dict(kind="stable_but_low_Q", method_id=a.method_id, domain=a.domain, k=a.k, pool_id=a.pool_id,
                         image=a.image, building=a.building, difficulty=a.difficulty, composition_a=a.composition,
                         composition_b=b.composition, B8L2_change=b.B8L2_mean-a.B8L2_mean, B8L2_a=a.B8L2_mean, B8L2_b=b.B8L2_mean,
                         within_Q_a=a.within_abs_B8L2_change_mean, within_Q_b=b.within_abs_B8L2_change_mean,
                         joint_a=a.within_joint_stable_main_rate, joint_b=b.within_joint_stable_main_rate,
                         nodes_a=a.nodes_mean, nodes_b=b.nodes_mean, corner_a=a.diag_corner_recall_05_mean,
                         corner_b=b.diag_corner_recall_05_mean, wall_a=a.diag_wall_coverage_05_mean,
                         wall_b=b.diag_wall_coverage_05_mean, team_keys_a=a.team_keys, team_keys_b=b.team_keys))
    keys = ["kind", "method_id", "domain", "k", "pool_id", "composition_a", "composition_b"]
    return pd.DataFrame(rows).drop_duplicates(keys) if rows else pd.DataFrame(columns=keys)


def report(path, receipt, coverage, pairs, mixtures, candidates, cases):
    lines = ["# 发现侧类别构成搜索：待冻结验证的结果", "", "本文件只读取 discovery 建筑，类别与历史训练特征保持冻结。下文为探索发现，不是新外部盲测；同构成的 3–4 个具体团队用于观察成员波动，不能当成 3–4 张独立图片。", "",
             f"已验证 {receipt['request_rows']:,} 个请求、{receipt['observed_unique_teams']:,} 个实际不同团队、{receipt['cells']:,} 个构成单元，覆盖 {receipt['images']} 张图片、{receipt['buildings']} 栋建筑、{receipt['workers']} 人；未计算请求 {receipt['missing_computations']}。", "",
             "主表保留所有失败/缺分。质量均值、分位数只在有分队伍上计算，同时另列完整/可评分分母；不补零。每对类构成均在同池、同参考、同总人数下比较。", "",
             "## 搜索与支持", "", "`discovery_pair_aggregate.csv.gz` 考察所有已采样构成对，并保留达到最低共同图片支持的每一个构成对，包括弱效应、反向与失败。未达支持的数量见 `discovery_pair_search_ledger.csv`，原始构成单元仍可重算。原设计没有穷举所有具体成员；采用样本的部分明确保留抽样/穷举标记。", "",
             "| 方法 | 人数 | 图片/楼 | 构成单元 | 单元内平均绝对 Q 差的中位数 | 同图构成均值范围中位数 | 单元内联合稳定率均值 |", "|---|---:|---:|---:|---:|---:|---:|"]
    for r in coverage.itertuples():
        lines.append(f"| {r.method_id} | {r.k} | {r.images}/{r.buildings} | {r.composition_cells} | {r.cell_within_abs_Q_median:.2f} | {r.image_composition_mean_Q_range_median:.2f} | {r.image_mean_within_joint_stable_main_rate:.3f} |")
    lines += ["", "上表仅用于覆盖与尺度定位。具体类别对没有压成一个类内/类间均值；下节及小表保持精确的类别计数。联合稳定沿用 Q≤2、floor 1−IoU≤0.05、绑定环≤3°、同节点数且均完整，不把低 Q 的稳定视为正确。", "", "## 具体构成候选（未经验证）", "", "A→B 的符号始终保留；建议方向只用于提示，未重命名原类别。", "", "| 方法/人数 | A | B | 图片/楼 | B−A 均值 | 同构成内 | 稳定率 A/B | 最强反例变化 |", "|---|---|---|---:|---:|---:|---:|---:|"]
    shown = candidates[candidates.kind == "broad_quality_shift"]
    for r in shown.itertuples():
        lines.append(f"| {r.method_id} / {r.k} | {r.composition_a} | {r.composition_b} | {int(r.images)}/{int(r.buildings)} | {r.mean_signed_B8L2_change:.2f} | {r.within_Q_a:.2f}/{r.within_Q_b:.2f} | {r.within_joint_a:.3f}/{r.within_joint_b:.3f} | {r.counterexample_signed_B8L2_change:.2f} |")
    lines += ["", "配比变化可能同时改变历史 Q、来源比例和具体成员。上表是整体分类效用；Q/来源控制后的预测增量由独立 screen 表报告。本格点的相同 replicate ID 不保证最少换人数，因此没有把格点差异宣称为严格相同核心的因果替换。后续匹配 block 需保持同一核心与相同换入人数。", "", "## 混类是否超过相关纯类", "", "只有所有参与混类的纯类、在同图同人数确实存在且有分，才进入主混类超额表。纯类不可行或失败缺分时，不能把已有的一个纯类称为全部纯类。", "", "| 方法 | 人数/混类 | 图片/楼（完整纯类支持） | 超过最佳纯类均值 | 获益图片比例 | 最差反例 |", "|---|---|---:|---:|---:|---:|"]
    for r in candidates[candidates.kind == "best_supported_mixture_even_if_not_successful"].itertuples():
        lines.append(f"| {r.method_id} | {int(r.k)} / {r.composition_b} | {int(r.images)}/{int(r.buildings)} | {r.mean_signed_B8L2_change:.2f} | {r.directional_fraction:.3f} | {r.counterexample_signed_B8L2_change:.2f} |")
    lines += ["", "每个方法均保留其最有支持的混类候选，即使其超额为负。这是发现搜索结果，最终应在未参与选择的楼和新的具体成员组合中检验。`discovery_mixture_aggregate.csv.gz` 保存所有被测试混类的可行性、超额、失败和反例，而不是仅保存赢家。", "", "## 机制、反例与人工复核", "", "`discovery_case_candidates.csv` 按精确方法/人数/图片/构成给出正例、同规则最强反例及稳定但低 Q 的反例，并列每个构成的所有实际 team keys。它们可直接连接请求清单与融合缓存重建。", "", "墙线覆盖与转角召回使用同一冻结参考，仅作几何诊断：墙线覆盖不惩罚多画墙，转角匹配不证明凸/凹类型或连接方向正确；原 5°/9° 节点/边匹配也不是必要结构真值。三维比较为同参考平均高度棱柱 IoU，不是完整三维体积重建。", "", "没有把缺机会当作低能力；类解释、来源计数与历史变量见正反向 class explanations。历史 FULL 画像与当前目标图的局部簇未进入类别训练。", "", "## 可复现", "", "先运行 `summarize_grid.py`（精确 manifest、两路线 frozen labels、SPLIT 与 INPUT_SNAPSHOT 参数），再运行本脚本。质量方向与异常均从实际融合结果生成；本脚本没有改变参考、融合或评分。", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--grid", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--minimum-pair-images", type=int, default=5)
    ap.add_argument("--minimum-pattern-images", type=int, default=8)
    ap.add_argument("--minimum-pattern-buildings", type=int, default=3)
    ap.add_argument("--minimum-mixture-images", type=int, default=5)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    receipt = read(args.grid / "GRID_SUMMARY_RECEIPT.json")
    assert receipt["phase"] == "discovery" and receipt["missing_computations"] == 0
    cells = pd.read_csv(args.grid / "cell_summary.csv.gz")
    assert set(cells.phase) == {"discovery"}
    assert not cells.duplicated(["method_id", "domain", "pool_id", "k", "composition"]).any()
    mixture = pd.read_csv(args.grid / "mixture_vs_pure.csv.gz")
    coverage = save_table(args.out / "discovery_method_coverage.csv", method_coverage(cells))
    save_table(args.out / "discovery_composition_aggregate.csv.gz", aggregate_compositions(cells))
    pair_rows, ledger = search_all_count_vector_pairs(cells, args.minimum_pair_images)
    pairs = save_table(args.out / "discovery_pair_aggregate.csv.gz", pair_rows)
    save_table(args.out / "discovery_pair_search_ledger.csv", ledger)
    mixtures = save_table(args.out / "discovery_mixture_aggregate.csv.gz", aggregate_mixtures(mixture))
    candidates = save_table(args.out / "discovery_pattern_candidates.csv", choose_candidates(pairs, mixtures, cells,
                           args.minimum_pattern_images, args.minimum_pattern_buildings, args.minimum_mixture_images))
    cases = save_table(args.out / "discovery_case_candidates.csv", case_candidates(cells, candidates, mixtures))
    report(args.out / "DISCOVERY_GRID_FINDINGS_ZH.md", receipt, coverage, pairs, mixtures, candidates, cases)
    write(args.out / "DISCOVERY_SEARCH_RECEIPT.json", dict(schema="count_vector_discovery_search_v1", phase="discovery",
          grid_receipt_sha256=sha(args.grid / "GRID_SUMMARY_RECEIPT.json"), source_code_sha256=sha(Path(__file__)),
          minimum_pair_images=args.minimum_pair_images, all_observed_pair_occurrences=sum(r["observed_within_image_count_vector_pairs"] for r in ledger),
          minimum_pattern_images=args.minimum_pattern_images, minimum_pattern_buildings=args.minimum_pattern_buildings,
          minimum_mixture_images=args.minimum_mixture_images,
          retained_aggregate_count_vector_pairs=len(pairs), candidate_rows=len(candidates), case_rows=len(cases),
          results_are_exploratory=True, validation_outcomes_read=False, omission_rule="compact pair aggregates require configured common-image support; every observed count-vector pair considered, all source cells retained"))


if __name__ == "__main__":
    main()
