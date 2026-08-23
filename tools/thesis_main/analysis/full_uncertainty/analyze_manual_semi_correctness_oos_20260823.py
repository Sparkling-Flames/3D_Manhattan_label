from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm


ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / "analysis_results" / "manual_semi_correctness_oos_20260823"
V5 = ROOT / "analysis_results" / "full_uncertainty_data_mining_20260821_v5"
MODEL = ROOT / "analysis_results" / "model_initialization_audit_hybrid_gt_20260823_v4"
SEED = 20260823


def read_csv(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    frame.columns = [str(c).lstrip("\ufeff") for c in frame.columns]
    return frame


def write_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(path, index=False, encoding="utf-8-sig", lineterminator="\n")


def boolish(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series.fillna(False)
    return series.astype(str).str.strip().str.lower().isin({"true", "1", "yes", "y"})


def numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def one_way_icc(frame: pd.DataFrame, outcome: str, group: str) -> dict[str, float | int | None]:
    data = frame[[outcome, group]].dropna().copy()
    if data.empty:
        return {"n": 0, "groups": 0, "icc1": None}
    grouped = data.groupby(group)[outcome]
    sizes = grouped.size()
    means = grouped.mean()
    k = int(len(sizes))
    n = int(len(data))
    if k < 2 or n <= k:
        return {"n": n, "groups": k, "icc1": None}
    grand = float(data[outcome].mean())
    ss_between = float(sum(sizes[g] * (means[g] - grand) ** 2 for g in sizes.index))
    ss_within = float(sum(((part[outcome] - part[outcome].mean()) ** 2).sum() for _, part in data.groupby(group)))
    ms_between = ss_between / (k - 1)
    ms_within = ss_within / (n - k)
    n0 = (n - float((sizes.astype(float) ** 2).sum()) / n) / (k - 1)
    denom = ms_between + (n0 - 1.0) * ms_within
    icc = (ms_between - ms_within) / denom if denom else np.nan
    return {
        "n": n,
        "groups": k,
        "icc1": float(icc) if np.isfinite(icc) else None,
        "ms_between": float(ms_between),
        "ms_within": float(ms_within),
        "n0": float(n0),
    }


def summarize_mask(frame: pd.DataFrame, mask: pd.Series, label: str, stage: str, lane: str) -> dict[str, object]:
    sub = frame.loc[mask].copy()
    return {
        "stage": stage,
        "lane": lane,
        "definition": label,
        "row_count": int(len(sub)),
        "task_count": int(sub["base_task_id"].nunique()) if len(sub) else 0,
        "worker_count": int(sub["worker_id"].nunique()) if len(sub) else 0,
        "median_delta_U": float(numeric(sub["delta_U"]).median()) if len(sub) else np.nan,
        "median_edit_rmse_px": float(numeric(sub["geometry_edit_rmse_px"]).median()) if len(sub) else np.nan,
        "median_U_initial": float(numeric(sub["U_initial"]).median()) if len(sub) else np.nan,
        "median_U_final": float(numeric(sub["U_final"]).median()) if len(sub) else np.nan,
    }


def two_sided_power(delta: float, sigma: float, n: int, design_effect: float = 1.0, alpha: float = 0.05) -> float:
    se = sigma * math.sqrt(design_effect / n)
    if se <= 0:
        return float("nan")
    mu = delta / se
    crit = norm.ppf(1 - alpha / 2)
    return float(norm.sf(crit - mu) + norm.cdf(-crit - mu))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    rows = read_csv(V5 / "TAG_BEHAVIOR_ALL_SEMI_ROWS.csv")
    task_scope = read_csv(V5 / "TASK_INCLUSION_CLASSIFICATION.CSV")
    task_effects = read_csv(V5 / "SEMI_PROPOSAL_TASK_TABLE.CSV")
    model = read_csv(MODEL / "model_initialization_metrics.csv")

    scope_cols = ["base_task_id", "task_final_scope", "scope_resolution_status", "task_analysis_class"]
    rows = rows.merge(task_scope[scope_cols].drop_duplicates("base_task_id"), on="base_task_id", how="left")

    for col in [
        "analysis_eligible", "edited_bool", "geometry_hash_changed", "topology_changed", "material_edit",
        "acceptable_tag", "explicit_model_problem_tag", "initial_structurally_valid", "final_structurally_valid",
        "issue_reported", "exact_geometry_equal",
    ]:
        if col not in rows.columns:
            rows[col] = False
        rows[col + "__bool"] = boolish(rows[col])

    for col in ["U_initial", "U_final", "delta_U", "geometry_edit_rmse_px"]:
        rows[col + "__num"] = numeric(rows[col])

    rows["quality_evaluable"] = rows["U_initial__num"].notna() & rows["U_final__num"].notna()
    rows["edited_recomputed"] = rows["edited_bool__bool"] | rows["geometry_hash_changed__bool"] | (~rows["exact_geometry_equal__bool"])
    rows["negative_metric_change_001"] = rows["delta_U__num"] < -0.01
    rows["positive_metric_change_001"] = rows["delta_U__num"] > 0.01
    rows["same_topology_explicit"] = ~rows["topology_changed__bool"]
    rows["micro_same_topology_edit"] = (
        rows["edited_recomputed"]
        & rows["same_topology_explicit"]
        & ~rows["material_edit__bool"]
    )
    issue_text = (rows.get("model_issue_choice", "").fillna("").astype(str) + ";" + rows.get("tag_codes", "").fillna("").astype(str)).str.lower()
    rows["corner_drift_reported"] = issue_text.str.contains("corner_drift", regex=False)
    rows["scope_in_scope"] = rows["task_final_scope"].fillna("").astype(str).str.lower().eq("in_scope")
    rows["structurally_valid_both"] = rows["initial_structurally_valid__bool"] & rows["final_structurally_valid__bool"]

    measured = []
    for stage in ["P1", "C1"]:
        stage_mask = rows["stage"].eq(stage)
        lanes = {
            "all_stage": stage_mask,
            "analysis_eligible": stage_mask & rows["analysis_eligible__bool"],
            "task_in_scope": stage_mask & rows["scope_in_scope"],
            "analysis_eligible_and_in_scope": stage_mask & rows["analysis_eligible__bool"] & rows["scope_in_scope"],
        }
        for lane, base in lanes.items():
            valid = base & rows["quality_evaluable"] & rows["structurally_valid_both"]
            definitions = {
                "all_evaluable_structurally_valid_rows": valid,
                "edited_rows": valid & rows["edited_recomputed"],
                "edited_negative_metric_change": valid & rows["edited_recomputed"] & rows["negative_metric_change_001"],
                "same_topology_edited_negative_metric_change": valid & rows["edited_recomputed"] & rows["same_topology_explicit"] & rows["negative_metric_change_001"],
                "micro_same_topology_negative_metric_change": valid & rows["micro_same_topology_edit"] & rows["negative_metric_change_001"],
                "acceptable_tag_edited_negative_metric_change": valid & rows["acceptable_tag__bool"] & rows["edited_recomputed"] & rows["negative_metric_change_001"],
                "acceptable_tag_micro_same_topology_negative_metric_change": valid & rows["acceptable_tag__bool"] & rows["micro_same_topology_edit"] & rows["negative_metric_change_001"],
                "corner_drift_micro_same_topology_negative_metric_change": valid & rows["corner_drift_reported"] & rows["micro_same_topology_edit"] & rows["negative_metric_change_001"],
                "explicit_model_problem_micro_same_topology_negative_metric_change": valid & rows["explicit_model_problem_tag__bool"] & rows["micro_same_topology_edit"] & rows["negative_metric_change_001"],
            }
            for definition, mask in definitions.items():
                measured.append(summarize_mask(rows, mask, definition, stage, lane))

    measured_df = pd.DataFrame(measured)
    write_csv(measured_df, OUT / "MEASURED_CANDIDATE_COUNTS.csv")

    candidate_mask = (
        rows["stage"].eq("C1")
        & rows["analysis_eligible__bool"]
        & rows["scope_in_scope"]
        & rows["quality_evaluable"]
        & rows["structurally_valid_both"]
        & rows["micro_same_topology_edit"]
        & rows["negative_metric_change_001"]
    )
    candidate_cols = [
        "base_task_id", "building_id", "worker_id", "canonical_annotation_id", "model_issue_choice", "tag_codes",
        "acceptable_tag", "corner_drift_reported", "U_initial", "U_final", "delta_U", "geometry_edit_rmse_px",
        "edit_magnitude_band", "topology_changed", "material_edit", "task_final_scope", "image_reference",
    ]
    write_csv(
        rows.loc[candidate_mask, [c for c in candidate_cols if c in rows.columns]].sort_values(
            ["base_task_id", "worker_id"]
        ),
        OUT / "C1_MICRO_EDIT_NEGATIVE_METRIC_CANDIDATES.csv",
    )

    transitions = []
    for stage in ["P1", "C1"]:
        base = rows[rows["stage"].eq(stage) & rows["quality_evaluable"]].copy()
        for cutoff in [0.90, 0.95, 0.99]:
            initial = base["U_initial__num"] >= cutoff
            final = base["U_final__num"] >= cutoff
            for initial_correct in [False, True]:
                sub = base.loc[initial.eq(initial_correct)]
                sub_final = final.loc[sub.index]
                transitions.append({
                    "stage": stage,
                    "cutoff": cutoff,
                    "initial_correct": initial_correct,
                    "n": int(len(sub)),
                    "final_correct_n": int(sub_final.sum()),
                    "final_correct_rate": float(sub_final.mean()) if len(sub) else np.nan,
                    "exact_retention_rate": float(sub["exact_geometry_equal__bool"].mean()) if len(sub) else np.nan,
                    "issue_report_rate": float(sub["issue_reported__bool"].mean()) if len(sub) else np.nan,
                    "mean_delta_U": float(sub["delta_U__num"].mean()) if len(sub) else np.nan,
                    "median_delta_U": float(sub["delta_U__num"].median()) if len(sub) else np.nan,
                })
    transitions_df = pd.DataFrame(transitions)
    write_csv(transitions_df, OUT / "PROPOSAL_CORRECTNESS_TRANSITIONS_RECOMPUTED.csv")

    # Difficulty and model-issue label coverage. These are response outcomes, not frozen pre-treatment predictors.
    difficulty_codes = ["trivial", "occlusion", "low_texture", "seam", "reflection", "low_image_quality"]
    tag_text = rows.get("tag_codes", pd.Series("", index=rows.index)).fillna("").astype(str).str.lower()
    coverage = []
    for stage in ["P1", "C1"]:
        sub = rows[rows["stage"].eq(stage)]
        for code in difficulty_codes:
            present = tag_text.loc[sub.index].str.contains(code, regex=False)
            coverage.append({
                "stage": stage,
                "field_family": "difficulty_response",
                "code": code,
                "row_count": int(present.sum()),
                "row_rate": float(present.mean()) if len(sub) else np.nan,
                "task_count": int(sub.loc[present, "base_task_id"].nunique()),
                "worker_count": int(sub.loc[present, "worker_id"].nunique()),
                "causal_predictor_allowed": False,
            })
        model_issue = sub.get("model_issue_choice", pd.Series("", index=sub.index)).fillna("").astype(str)
        for code in sorted({part for value in model_issue for part in value.split(";") if part}):
            present = model_issue.str.split(";").apply(lambda xs: code in xs)
            coverage.append({
                "stage": stage,
                "field_family": "model_issue_response",
                "code": code,
                "row_count": int(present.sum()),
                "row_rate": float(present.mean()) if len(sub) else np.nan,
                "task_count": int(sub.loc[present, "base_task_id"].nunique()),
                "worker_count": int(sub.loc[present, "worker_id"].nunique()),
                "causal_predictor_allowed": False,
            })
    write_csv(pd.DataFrame(coverage), OUT / "CURRENT_DIFFICULTY_AND_MODEL_ISSUE_COVERAGE.csv")

    # Existing paired task variation: descriptive reference only, not a correctness-interaction variance estimate.
    effect_rows = []
    for outcome in ["delta_iou_to_gt", "delta_shannon_entropy"]:
        temp = task_effects[["base_task_id", "building_id", outcome]].copy()
        temp[outcome] = numeric(temp[outcome])
        temp = temp.dropna(subset=[outcome])
        icc = one_way_icc(temp, outcome, "building_id")
        effect_rows.append({
            "outcome": outcome,
            "task_count": int(len(temp)),
            "building_count": int(temp["building_id"].nunique()),
            "mean": round(float(temp[outcome].mean()), 12),
            "sample_sd": round(float(temp[outcome].std(ddof=1)), 12),
            "building_icc1_descriptive": round(float(icc["icc1"]), 12) if icc.get("icc1") is not None else None,
            "interpretation": "descriptive single-effect variation; not the future correct-vs-wrong interaction variance",
        })
    write_csv(pd.DataFrame(effect_rows), OUT / "CURRENT_TASK_EFFECT_VARIATION_REFERENCE.csv")

    # Model split and building composition.
    model["building_id"] = model["image_id"].astype(str).str.split("_").str[0]
    split_rows = []
    building_rows = []
    for split, sub in model.groupby("split"):
        by_building = sub.groupby("building_id").size().sort_values(ascending=False)
        split_rows.append({
            "split": split,
            "image_count": int(len(sub)),
            "building_count": int(sub["building_id"].nunique()),
            "images_per_building_min": int(by_building.min()),
            "images_per_building_median": float(by_building.median()),
            "images_per_building_max": int(by_building.max()),
            "task_level_scope_fields_present": any(c in model.columns for c in ["task_final_scope", "scope_terminal", "reference_status"]),
        })
        for building, count in by_building.items():
            building_rows.append({"split": split, "building_id": building, "image_count": int(count)})
    write_csv(pd.DataFrame(split_rows), OUT / "MODEL_SPLIT_BUILDING_SUMMARY.csv")
    write_csv(pd.DataFrame(building_rows), OUT / "MODEL_SPLIT_BUILDING_COUNTS.csv")

    # Conditional power only: no claim about the true effect or success probability.
    zsum = norm.ppf(0.975) + norm.ppf(0.80)
    power_rows = []
    for n in [40, 56, 60, 80, 100]:
        for sigma in [0.05, 0.08, 0.10, 0.12]:
            mde = float(zsum * sigma / math.sqrt(n))
            for delta in [0.02, 0.03, 0.04, 0.05]:
                power_rows.append({
                    "n_primary_images": n,
                    "interaction_sd_assumed": sigma,
                    "building_icc_assumed": 0.0,
                    "mean_images_per_building_assumed": 1.0,
                    "design_effect": 1.0,
                    "mde_80pct_two_sided_005": mde,
                    "true_interaction_assumed": delta,
                    "conditional_power": two_sided_power(delta, sigma, n),
                    "status": "conditional_only_no_empirical_interaction_variance",
                })
            for rho in [0.05, 0.10, 0.20]:
                for mean_m in [3.0, 4.0, 5.0]:
                    deff = 1.0 + (mean_m - 1.0) * rho
                    power_rows.append({
                        "n_primary_images": n,
                        "interaction_sd_assumed": sigma,
                        "building_icc_assumed": rho,
                        "mean_images_per_building_assumed": mean_m,
                        "design_effect": deff,
                        "mde_80pct_two_sided_005": float(mde * math.sqrt(deff)),
                        "true_interaction_assumed": 0.04,
                        "conditional_power": two_sided_power(0.04, sigma, n, deff),
                        "status": "building_sensitivity_not_empirical_interaction_icc",
                    })
    write_csv(pd.DataFrame(power_rows), OUT / "CONDITIONAL_INTERACTION_POWER.csv")

    designs = [
        {
            "design": "A_natural_correctness_stratified_two_arm",
            "images": 100,
            "arms": "Manual;Natural-Semi",
            "workers_per_image_per_arm": 5,
            "total_worker_actions": 1000,
            "workers": 20,
            "manual_per_worker_mean": 25.0,
            "semi_per_worker_mean": 25.0,
            "primary_estimand": "within-image Semi-Manual effect, interacted with independently audited natural proposal correctness",
            "causal_strength": "randomized assistance effect within image; correctness is a pre-treatment moderator, not randomized",
            "uncertainty_resolution": "limited at k=5 per arm",
        },
        {
            "design": "B_same_image_counterfactual_three_arm",
            "images": 60,
            "arms": "Manual;Correct-Semi;Wrong-Semi",
            "workers_per_image_per_arm": 5,
            "total_worker_actions": 900,
            "workers": 20,
            "manual_per_worker_mean": 15.0,
            "semi_per_worker_mean": 30.0,
            "primary_estimand": "(Correct-Semi - Manual) - (Wrong-Semi - Manual) within image",
            "causal_strength": "strongest if correct/wrong variants are frozen and randomized",
            "uncertainty_resolution": "limited at k=5 per arm",
        },
        {
            "design": "C_nested_uncertainty_hybrid",
            "images": 56,
            "arms": "Manual;Correct-Semi;Wrong-Semi",
            "workers_per_image_per_arm": 5,
            "total_worker_actions": 960,
            "workers": 20,
            "manual_per_worker_mean": 16.0,
            "semi_per_worker_mean": 32.0,
            "primary_estimand": "three-arm interaction on 56 images; 8 prespecified images receive +5 workers/arm to k=10",
            "causal_strength": "strong same-image contrast plus nested distribution mechanism subset",
            "uncertainty_resolution": "k=10 on 8 prespecified ambiguity-rich images only; no prevalence claim",
        },
        {
            "design": "D_60_image_plus_6_high_k_sentinels",
            "images": 60,
            "arms": "Manual;Correct-Semi;Wrong-Semi",
            "workers_per_image_per_arm": 5,
            "total_worker_actions": 990,
            "workers": 20,
            "manual_per_worker_mean": 16.5,
            "semi_per_worker_mean": 33.0,
            "primary_estimand": "three-arm interaction on 60 images; 6 images receive +5 workers/arm to k=10",
            "causal_strength": "strong same-image contrast",
            "uncertainty_resolution": "small high-k mechanism subset",
        },
    ]
    write_csv(pd.DataFrame(designs), OUT / "DESIGN_OPTIONS_RESOURCE_ACCOUNTING.csv")

    # Report selected exact numbers.
    def metric(stage: str, lane: str, definition: str) -> dict[str, object]:
        item = measured_df[(measured_df.stage == stage) & (measured_df.lane == lane) & (measured_df.definition == definition)]
        return item.iloc[0].to_dict() if len(item) else {}

    c1_all_neg = metric("C1", "task_in_scope", "acceptable_tag_edited_negative_metric_change")
    c1_micro_neg = metric("C1", "task_in_scope", "acceptable_tag_micro_same_topology_negative_metric_change")
    c1_any_micro_neg = metric("C1", "task_in_scope", "micro_same_topology_negative_metric_change")
    p1_all_neg = metric("P1", "all_stage", "acceptable_tag_edited_negative_metric_change")
    p1_micro_neg = metric("P1", "all_stage", "acceptable_tag_micro_same_topology_negative_metric_change")

    split_summary = pd.DataFrame(split_rows).set_index("split")
    report = f"""# Manual–Semi、Proposal Correctness、OOS 与条件功效复核（2026-08-23）

## 结论

1. 未来主效应必须比较最终 Semi 与独立 Manual；initial-to-final 变化只属于机制与安全结果。
2. `visual closer` 在现有数据中没有独立专家真值字段，不能由 `delta_U<0` 反推。当前只能给出候选数量。
3. 对 60 张 primary images 的条件功效计算成立，但没有真实 correctness-interaction 方差，因此不得将显著结果概率写成“高”。
4. Building 不应作为新的科学自变量堆入主模型，但相关性不能忽略；最简处理是图内随机化、限制每 building 图片数，并报告 building-cluster sensitivity。
5. 648 张模型审计表没有 task-level Scope/reference 字段；正式刺激池必须先做独立 OOS/unresolved/reference audit。

## 现有候选计数

C1、任务终态 in-scope 中：

- 工人报告 proposal acceptable、发生编辑且 GT-based `delta_U<-0.01`：**{int(c1_all_neg.get('row_count', 0))} 行 / {int(c1_all_neg.get('task_count', 0))} 张任务**。
- 上述条件进一步限制为同 topology、非 material micro-edit：**{int(c1_micro_neg.get('row_count', 0))} 行 / {int(c1_micro_neg.get('task_count', 0))} 张任务**。
- 不要求 acceptable 标签的全部同 topology、非 material micro-edit 且指标下降：**{int(c1_any_micro_neg.get('row_count', 0))} 行 / {int(c1_any_micro_neg.get('task_count', 0))} 张任务**。

P1 开发数据中：

- acceptable + edited + negative metric change：**{int(p1_all_neg.get('row_count', 0))} 行 / {int(p1_all_neg.get('task_count', 0))} 张任务**。
- acceptable + micro same-topology edit + negative metric change：**{int(p1_micro_neg.get('row_count', 0))} 行 / {int(p1_micro_neg.get('task_count', 0))} 张任务**。

这些是“GT 指标下降但可能属于视觉/局部修订”的候选，不是视觉更接近真实的已确认案例。正式确认需要盲法 overlay 审查或独立 visual-boundary reference。

## 数据域与 Building

- Test：{int(split_summary.loc['test','image_count'])} 张，{int(split_summary.loc['test','building_count'])} 个 buildings；每 building 中位数 {float(split_summary.loc['test','images_per_building_median']):.1f} 张。
- Validation：{int(split_summary.loc['validation','image_count'])} 张，{int(split_summary.loc['validation','building_count'])} 个 buildings；每 building 中位数 {float(split_summary.loc['validation','images_per_building_median']):.1f} 张。
- 模型审计表是否带正式 Scope/reference 字段：{bool(split_summary['task_level_scope_fields_present'].any())}。

## 建议的标签角色

- Difficulty：继续收集，但只作为 worker-perceived difficulty / mechanism outcome；不要作为 proposal correctness 真值或同任务首次分配变量。
- Model Issue：必须在编辑前收集，拆分为 `material issue yes/no/unsure`、issue family、required correction severity、confidence。
- Assignment truth：独立 researcher/expert manifest，不能由 worker 的 Model Issue 反推。

## 复现

```bash
python -m tools.thesis_main.analysis.full_uncertainty.analyze_manual_semi_correctness_oos_20260823
```
"""
    (OUT / "ANALYSIS_REPORT_ZH.md").write_text(report, encoding="utf-8", newline="\n")

    validation = {
        "seed": SEED,
        "tag_rows": int(len(rows)),
        "c1_rows": int(rows["stage"].eq("C1").sum()),
        "p1_rows": int(rows["stage"].eq("P1").sum()),
        "paired_task_rows": int(len(task_effects)),
        "model_rows": int(len(model)),
        "model_split_counts": model.groupby("split").size().astype(int).to_dict(),
        "c1_micro_candidate_rows": int(candidate_mask.sum()),
        "all_required_outputs_nonempty": all((OUT / name).exists() and (OUT / name).stat().st_size > 0 for name in [
            "MEASURED_CANDIDATE_COUNTS.csv",
            "C1_MICRO_EDIT_NEGATIVE_METRIC_CANDIDATES.csv",
            "PROPOSAL_CORRECTNESS_TRANSITIONS_RECOMPUTED.csv",
            "CURRENT_DIFFICULTY_AND_MODEL_ISSUE_COVERAGE.csv",
            "CURRENT_TASK_EFFECT_VARIATION_REFERENCE.csv",
            "MODEL_SPLIT_BUILDING_SUMMARY.csv",
            "MODEL_SPLIT_BUILDING_COUNTS.csv",
            "CONDITIONAL_INTERACTION_POWER.csv",
            "DESIGN_OPTIONS_RESOURCE_ACCOUNTING.csv",
            "ANALYSIS_REPORT_ZH.md",
        ]),
    }
    (OUT / "VALIDATION.json").write_text(
        json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n",
    )


if __name__ == "__main__":
    main()
