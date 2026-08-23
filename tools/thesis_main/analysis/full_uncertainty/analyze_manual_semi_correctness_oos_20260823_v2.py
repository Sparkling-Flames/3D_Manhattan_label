from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from tools.thesis_main.analysis.full_uncertainty import analyze_manual_semi_correctness_oos_20260823 as v1


ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / "analysis_results" / "manual_semi_correctness_oos_20260823"
V5 = ROOT / "analysis_results" / "full_uncertainty_data_mining_20260821_v5"


def observed(series: pd.Series) -> pd.Series:
    text = series.astype(str).str.strip().str.lower()
    return series.notna() & ~text.isin({"", "nan", "none", "null"})


def summarize(frame: pd.DataFrame, mask: pd.Series, stage: str, lane: str, definition: str) -> dict[str, object]:
    sub = frame.loc[mask].copy()
    return {
        "stage": stage,
        "lane": lane,
        "definition": definition,
        "row_count": int(len(sub)),
        "task_count": int(sub["base_task_id"].nunique()) if len(sub) else 0,
        "worker_count": int(sub["worker_id"].nunique()) if len(sub) else 0,
        "median_delta_U": float(sub["delta_U_num"].median()) if len(sub) else np.nan,
        "median_edit_rmse_px": float(sub["edit_rmse_num"].median()) if len(sub) else np.nan,
        "median_U_initial": float(sub["U_initial_num"].median()) if len(sub) else np.nan,
        "median_U_final": float(sub["U_final_num"].median()) if len(sub) else np.nan,
    }


def main() -> None:
    # Preserve the v1 outputs for split composition, power and design accounting, then replace the candidate audit with stricter observed-field rules.
    v1.main()

    rows = v1.read_csv(V5 / "TAG_BEHAVIOR_ALL_SEMI_ROWS.csv")
    scope = v1.read_csv(V5 / "TASK_INCLUSION_CLASSIFICATION.CSV")
    rows = rows.merge(
        scope[["base_task_id", "task_final_scope", "scope_resolution_status", "task_analysis_class"]].drop_duplicates("base_task_id"),
        on="base_task_id",
        how="left",
    )

    for col in [
        "analysis_eligible", "edited_bool", "topology_changed", "material_edit", "acceptable_tag",
        "explicit_model_problem_tag", "initial_structurally_valid", "final_structurally_valid", "issue_reported",
        "exact_geometry_equal",
    ]:
        if col not in rows.columns:
            rows[col] = np.nan
        rows[col + "_bool"] = v1.boolish(rows[col])
        rows[col + "_observed"] = observed(rows[col])

    rows["U_initial_num"] = v1.numeric(rows["U_initial"])
    rows["U_final_num"] = v1.numeric(rows["U_final"])
    rows["delta_U_num"] = v1.numeric(rows["delta_U"])
    rows["edit_rmse_num"] = v1.numeric(rows["geometry_edit_rmse_px"])
    rows["quality_evaluable"] = rows["U_initial_num"].notna() & rows["U_final_num"].notna()
    rows["structurally_valid_both"] = rows["initial_structurally_valid_bool"] & rows["final_structurally_valid_bool"]
    rows["scope_in_scope"] = rows["task_final_scope"].fillna("").astype(str).str.lower().eq("in_scope")
    rows["negative_metric_change_001"] = rows["delta_U_num"] < -0.01
    rows["same_topology_observed"] = rows["topology_changed_observed"] & ~rows["topology_changed_bool"]
    rows["material_flag_observed"] = rows["material_edit_observed"]
    rows["measured_edit"] = rows["edited_bool"] & rows["edit_rmse_num"].notna()
    rows["micro_same_topology_measured_edit"] = (
        rows["measured_edit"]
        & rows["same_topology_observed"]
        & rows["material_flag_observed"]
        & ~rows["material_edit_bool"]
    )
    issue_text = (
        rows.get("model_issue_choice", pd.Series("", index=rows.index)).fillna("").astype(str)
        + ";"
        + rows.get("tag_codes", pd.Series("", index=rows.index)).fillna("").astype(str)
    ).str.lower()
    rows["corner_drift_reported"] = issue_text.str.contains("corner_drift", regex=False)

    summary_rows = []
    for stage in ["P1", "C1"]:
        stage_mask = rows["stage"].eq(stage)
        lanes = {
            "all_stage": stage_mask,
            "task_in_scope": stage_mask & rows["scope_in_scope"],
            "analysis_eligible": stage_mask & rows["analysis_eligible_bool"],
            "analysis_eligible_and_in_scope": stage_mask & rows["analysis_eligible_bool"] & rows["scope_in_scope"],
        }
        for lane, base in lanes.items():
            valid = base & rows["quality_evaluable"] & rows["structurally_valid_both"]
            definitions = {
                "all_evaluable_structurally_valid_rows": valid,
                "edited_rows": valid & rows["edited_bool"],
                "edited_negative_metric_change": valid & rows["edited_bool"] & rows["negative_metric_change_001"],
                "same_topology_observed_edited_negative_metric_change": valid & rows["edited_bool"] & rows["same_topology_observed"] & rows["negative_metric_change_001"],
                "micro_same_topology_measured_negative_metric_change": valid & rows["micro_same_topology_measured_edit"] & rows["negative_metric_change_001"],
                "acceptable_tag_edited_negative_metric_change": valid & rows["acceptable_tag_bool"] & rows["edited_bool"] & rows["negative_metric_change_001"],
                "acceptable_tag_micro_same_topology_measured_negative_metric_change": valid & rows["acceptable_tag_bool"] & rows["micro_same_topology_measured_edit"] & rows["negative_metric_change_001"],
                "corner_drift_micro_same_topology_measured_negative_metric_change": valid & rows["corner_drift_reported"] & rows["micro_same_topology_measured_edit"] & rows["negative_metric_change_001"],
            }
            for name, mask in definitions.items():
                summary_rows.append(summarize(rows, mask, stage, lane, name))

    summary = pd.DataFrame(summary_rows)
    v1.write_csv(summary, OUT / "MEASURED_CANDIDATE_COUNTS.csv")

    candidate_mask = (
        rows["stage"].eq("C1")
        & rows["analysis_eligible_bool"]
        & rows["scope_in_scope"]
        & rows["quality_evaluable"]
        & rows["structurally_valid_both"]
        & rows["micro_same_topology_measured_edit"]
        & rows["negative_metric_change_001"]
    )
    cols = [
        "base_task_id", "building_id", "worker_id", "canonical_annotation_id", "model_issue_choice", "tag_codes",
        "acceptable_tag", "corner_drift_reported", "U_initial", "U_final", "delta_U", "geometry_edit_rmse_px",
        "edit_magnitude_band", "topology_changed", "material_edit", "task_final_scope", "image_reference",
    ]
    v1.write_csv(
        rows.loc[candidate_mask, [c for c in cols if c in rows.columns]].sort_values(["base_task_id", "worker_id"]),
        OUT / "C1_MICRO_EDIT_NEGATIVE_METRIC_CANDIDATES.csv",
    )

    coverage_rows = []
    for stage in ["P1", "C1"]:
        sub = rows[rows["stage"].eq(stage)]
        coverage_rows.append({
            "stage": stage,
            "row_count": int(len(sub)),
            "topology_changed_observed_n": int(sub["topology_changed_observed"].sum()),
            "material_edit_observed_n": int(sub["material_edit_observed"].sum()),
            "edit_rmse_observed_n": int(sub["edit_rmse_num"].notna().sum()),
            "edited_n": int(sub["edited_bool"].sum()),
            "micro_same_topology_measured_edit_n": int(sub["micro_same_topology_measured_edit"].sum()),
        })
    v1.write_csv(pd.DataFrame(coverage_rows), OUT / "EDIT_MEASUREMENT_COVERAGE.csv")

    transitions = []
    for stage in ["P1", "C1"]:
        stage_rows = rows[rows["stage"].eq(stage) & rows["quality_evaluable"]].copy()
        lane_masks = {"all_evaluable": pd.Series(True, index=stage_rows.index)}
        if stage == "C1":
            lane_masks["analysis_eligible"] = stage_rows["analysis_eligible_bool"]
        for lane, lane_mask in lane_masks.items():
            base = stage_rows.loc[lane_mask].copy()
            for cutoff in [0.90, 0.95, 0.99]:
                initial = base["U_initial_num"] >= cutoff
                final = base["U_final_num"] >= cutoff
                for initial_correct in [False, True]:
                    sub = base.loc[initial.eq(initial_correct)]
                    sub_final = final.loc[sub.index]
                    transitions.append({
                        "stage": stage,
                        "lane": lane,
                        "cutoff": cutoff,
                        "initial_correct": initial_correct,
                        "n": int(len(sub)),
                        "final_correct_n": int(sub_final.sum()),
                        "final_correct_rate": float(sub_final.mean()) if len(sub) else np.nan,
                        "exact_retention_rate": float(sub["exact_geometry_equal_bool"].mean()) if len(sub) else np.nan,
                        "issue_report_rate": float(sub["issue_reported_bool"].mean()) if len(sub) else np.nan,
                        "mean_delta_U": float(sub["delta_U_num"].mean()) if len(sub) else np.nan,
                        "median_delta_U": float(sub["delta_U_num"].median()) if len(sub) else np.nan,
                    })
    v1.write_csv(pd.DataFrame(transitions), OUT / "PROPOSAL_CORRECTNESS_TRANSITIONS_RECOMPUTED.csv")

    def get(stage: str, lane: str, definition: str) -> dict[str, object]:
        hit = summary[(summary.stage == stage) & (summary.lane == lane) & (summary.definition == definition)]
        return hit.iloc[0].to_dict() if len(hit) else {}

    c1_formal_acceptable = get("C1", "analysis_eligible_and_in_scope", "acceptable_tag_edited_negative_metric_change")
    c1_all_acceptable = get("C1", "task_in_scope", "acceptable_tag_edited_negative_metric_change")
    c1_formal_micro = get("C1", "analysis_eligible_and_in_scope", "acceptable_tag_micro_same_topology_measured_negative_metric_change")
    c1_formal_any_micro = get("C1", "analysis_eligible_and_in_scope", "micro_same_topology_measured_negative_metric_change")
    p1_acceptable = get("P1", "all_stage", "acceptable_tag_edited_negative_metric_change")
    p1_micro = get("P1", "all_stage", "acceptable_tag_micro_same_topology_measured_negative_metric_change")

    split_summary = pd.read_csv(OUT / "MODEL_SPLIT_BUILDING_SUMMARY.csv", encoding="utf-8-sig").set_index("split")
    report = f"""# Manual–Semi、Proposal Correctness、OOS 与条件功效复核（严格测量版）

## 核心结论

1. 正式 efficacy estimand 必须比较最终 Semi 与独立 Manual；model-initial-to-Semi-final 只属于机制和安全分析。
2. 现有数据没有“视觉更接近真实”的独立专家变量，因此 `delta_U<0` 不能被解释成视觉更差，也不能被解释成视觉更好。
3. 对方给出的 n=60 条件功效计算成立；由于当前没有真实 correctness-interaction 方差，显著结果概率不能定量称为高。
4. Building 不是要加入的额外科学解释变量，但属于相关性单位：图内随机化可消除主要图片难度，仍应限制每 building 图片数并做 cluster sensitivity。
5. 648 张模型审计没有正式 Scope/reference 字段，Main 前必须完成 OOS/unresolved/reference gate。

## 协议边界

`DESIGN_OPTIONS_RESOURCE_ACCOUNTING.csv` 中的两臂/三臂资源方案仅是未来独立研究的探索性资源算术，尚未生成 worker–image assignment manifest，**不是当前正式 T1**。正式 T1 仍遵循冻结合同：`Manual/Semi × ordinary/stress_assist`、每图 `2 Manual + 2 Semi`、image-level paired estimand；本审计不改变其分配、estimand、margin 或 gate。

## GT 指标下降候选

C1、正式 analysis-eligible 且 task-level in-scope：

- proposal 被工人标为 acceptable、发生编辑、`delta_U<-0.01`：**{int(c1_formal_acceptable.get('row_count', 0))} 行 / {int(c1_formal_acceptable.get('task_count', 0))} 张任务**。
- 同一口径不限制 formal eligibility：**{int(c1_all_acceptable.get('row_count', 0))} 行 / {int(c1_all_acceptable.get('task_count', 0))} 张任务**。
- 进一步要求 topology_changed 和 material_edit 均有显式记录、同 topology、edit RMSE 可计算、且为非-material micro edit：**{int(c1_formal_micro.get('row_count', 0))} 行 / {int(c1_formal_micro.get('task_count', 0))} 张任务**。
- 不要求 acceptable 标签的全部 formal micro same-topology negative candidates：**{int(c1_formal_any_micro.get('row_count', 0))} 行 / {int(c1_formal_any_micro.get('task_count', 0))} 张任务**。

P1 开发数据：

- acceptable + edited + negative：**{int(p1_acceptable.get('row_count', 0))} 行 / {int(p1_acceptable.get('task_count', 0))} 张任务**。
- 严格可测的 acceptable + micro same-topology + negative：**{int(p1_micro.get('row_count', 0))} 行 / {int(p1_micro.get('task_count', 0))} 张任务**。

这些只是“GT-based metric decline after editing”的可复核候选。要确认“Manhattan 强制拟合使 GT 偏离视觉墙角、人工微调视觉更合理”，必须对 candidate overlays 做 outcome-blind 双专家视觉边界审查，或建立独立 visual-boundary reference。

## Building 与数据域

- Test：{int(split_summary.loc['test','image_count'])} 张，{int(split_summary.loc['test','building_count'])} 个 buildings；每 building 中位数 {float(split_summary.loc['test','images_per_building_median']):.1f} 张。
- Validation：{int(split_summary.loc['validation','image_count'])} 张，{int(split_summary.loc['validation','building_count'])} 个 buildings；每 building 中位数 {float(split_summary.loc['validation','images_per_building_median']):.1f} 张。

## 标签角色

- Difficulty 继续收集，但其正式名称应是 worker-perceived difficulty。它是 post-response mechanism/outcome，不能作为 proposal correctness truth，也不能用于同一任务首次分配。
- Model Issue 必须在编辑前填写，并拆成：material issue yes/no/unsure、issue family、required correction severity、confidence。
- Correct/Wrong treatment truth 必须来自独立、结果不可见的 researcher/expert stimulus manifest。
"""
    (OUT / "ANALYSIS_REPORT_ZH.md").write_text(report, encoding="utf-8", newline="\n")

    validation_path = OUT / "VALIDATION.json"
    validation = json.loads(validation_path.read_text(encoding="utf-8")) if validation_path.exists() else {}
    validation.update({
        "analysis_version": "strict_observed_fields_v2",
        "c1_formal_micro_candidate_rows": int(candidate_mask.sum()),
        "edit_measurement_coverage_output": "EDIT_MEASUREMENT_COVERAGE.csv",
    })
    validation_path.write_text(
        json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n",
    )


if __name__ == "__main__":
    main()
