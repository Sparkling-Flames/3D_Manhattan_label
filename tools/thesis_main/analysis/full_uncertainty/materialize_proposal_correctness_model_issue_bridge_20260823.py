"""Join the current HoHoNet proposal audit to existing Semi-Auto evidence.

This materializer is deliberately descriptive.  It does not retrofit a causal
correct/wrong-proposal effect into P1/C1, and it does not promote analyst-defined
post-hoc thresholds to a confirmatory correctness definition.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / "analysis_results" / "proposal_correctness_model_issue_bridge_20260823"
AUDIT = ROOT / "analysis_results" / "model_initialization_audit_hybrid_gt_20260823_v4" / "model_initialization_metrics.csv"
TASK = ROOT / "analysis_results" / "full_uncertainty_data_mining_20260821_v5" / "SEMI_PROPOSAL_TASK_TABLE.CSV"
ROWS = ROOT / "analysis_results" / "full_uncertainty_data_mining_20260821_v5" / "SEMI_REVIEW_FACT.CSV"

SEED = 20260823

ISSUE_TOKENS = {
    "acceptable",
    "overextend_adjacent",
    "underextend",
    "over_parsing",
    "corner_drift",
    "corner_duplicate",
    "topology_failure",
    "fail",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def truth(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "eligible", "passed"}


def numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def write_csv(path: Path, frame: pd.DataFrame) -> None:
    frame.to_csv(path, index=False, encoding="utf-8-sig", lineterminator="\n")


def parse_issue_tokens(value: Any) -> list[str]:
    text = str(value or "").strip().lower()
    if not text or text == "nan":
        return []
    for separator in (",", "|", ";"):
        text = text.replace(separator, ";")
    tokens = [token.strip() for token in text.split(";") if token.strip()]
    return sorted(set(token for token in tokens if token in ISSUE_TOKENS))


def audit_family(row: pd.Series) -> str:
    if not truth(row.get("model_pair_encoding_valid")):
        return "invalid_pair_encoding"
    delta = int(float(row.get("pair_count_delta", 0)))
    if delta > 0:
        return "model_has_more_corner_pairs"
    if delta < 0:
        return "model_has_fewer_corner_pairs"
    if not truth(row.get("corner_localization_pass")):
        return "same_pair_count_corner_localization_difference"
    if not truth(row.get("geometry_acceptable")):
        return "same_pair_count_posthoc_geometry_gate_fail"
    return "posthoc_strict_pass"


def topology_relation(row: pd.Series) -> str:
    if not truth(row.get("model_pair_encoding_valid")):
        return "invalid_pair_encoding"
    delta = int(float(row.get("pair_count_delta", 0)))
    if delta > 0:
        return "model_more_pairs"
    if delta < 0:
        return "model_fewer_pairs"
    return "pair_count_exact"


def compatible_issue_family(audit: str, tokens: list[str]) -> tuple[bool | None, str]:
    observed = set(tokens)
    if not observed:
        return None, "worker_issue_response_missing"
    expected: set[str]
    if audit == "model_has_more_corner_pairs":
        expected = {"overextend_adjacent", "over_parsing", "corner_duplicate", "topology_failure", "fail"}
    elif audit == "model_has_fewer_corner_pairs":
        expected = {"underextend", "topology_failure", "fail"}
    elif audit == "same_pair_count_corner_localization_difference":
        expected = {"corner_drift", "topology_failure", "fail"}
    elif audit == "same_pair_count_posthoc_geometry_gate_fail":
        expected = {"corner_drift", "overextend_adjacent", "underextend", "over_parsing", "fail"}
    elif audit == "posthoc_strict_pass":
        expected = {"acceptable"}
    else:
        expected = {"fail", "topology_failure"}
    overlap = observed & expected
    return bool(overlap), ";".join(sorted(overlap))


def summarise_group(frame: pd.DataFrame, by: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for key, group in frame.groupby(by, dropna=False, sort=True):
        rows.append(
            {
                by: key,
                "task_count": int(group["base_task_id"].nunique()),
                "building_count": int(group["building_id"].nunique()),
                "mean_delta_shannon_entropy": numeric(group["delta_shannon_entropy"]).mean(),
                "median_delta_shannon_entropy": numeric(group["delta_shannon_entropy"]).median(),
                "mean_delta_iou_to_gt": numeric(group["delta_iou_to_gt"]).mean(),
                "mean_edit_rate": numeric(group["edit_rate"]).mean(),
                "mean_issue_report_rate": numeric(group["issue_report_rate"]).mean(),
                "mean_delta_u": numeric(group["delta_u_mean"]).mean(),
                "interpretation": "descriptive_existing_C1_only_not_randomized_by_proposal_correctness",
            }
        )
    return pd.DataFrame(rows)


def detection_summary(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    outcomes = {
        "pair_count_mismatch": ~frame["topology_exact_bool"],
        "posthoc_not_strict_pass": ~frame["initialization_correct_bool"],
        "posthoc_not_acceptable": ~frame["initialization_acceptable_bool"],
    }
    for name, objective in outcomes.items():
        evaluable = frame["worker_issue_response_observed"] & objective.notna()
        current = frame[evaluable].copy()
        y = objective[evaluable].astype(bool)
        reported = current["worker_any_issue_reported"].astype(bool)
        tp = int((y & reported).sum())
        fn = int((y & ~reported).sum())
        fp = int((~y & reported).sum())
        tn = int((~y & ~reported).sum())
        sensitivity = tp / (tp + fn) if tp + fn else np.nan
        specificity = tn / (tn + fp) if tn + fp else np.nan
        ppv = tp / (tp + fp) if tp + fp else np.nan
        npv = tn / (tn + fn) if tn + fn else np.nan
        rows.append(
            {
                "audit_outcome": name,
                "row_count": len(current),
                "task_count": current["base_task_id"].nunique(),
                "worker_count": current["worker_id"].nunique(),
                "tp": tp,
                "fn": fn,
                "fp": fp,
                "tn": tn,
                "sensitivity": sensitivity,
                "specificity": specificity,
                "positive_predictive_value": ppv,
                "negative_predictive_value": npv,
                "status": (
                    "primary_descriptive_topology_proxy" if name == "pair_count_mismatch"
                    else "legacy_posthoc_threshold_sensitivity_only"
                ),
                "boundary": "not_independent_validation_and_not_causal",
            }
        )
    return pd.DataFrame(rows)


def split_summary(audit: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for split, group in audit.groupby("split", sort=True):
        exact = group["topology_exact_bool"]
        rows.append(
            {
                "split": split,
                "n": len(group),
                "topology_pair_count_exact_n": int(exact.sum()),
                "topology_pair_count_exact_rate": float(exact.mean()),
                "mean_topdown_2d_iou": numeric(group["topdown_2d_iou"]).mean(),
                "mean_derived_3d_iou": numeric(group["layoutnetv2_style_3d_iou"]).mean(),
                "posthoc_strict_pass_n": int(group["initialization_correct_bool"].sum()),
                "posthoc_acceptable_n": int(group["initialization_acceptable_bool"].sum()),
                "confirmed_manual_reference_n": int(group["gt_source_type"].eq("confirmed_user_manual_gt_correction").sum()),
            }
        )
    return pd.DataFrame(rows)


def build_sampling_frame(audit: pd.DataFrame, existing_tasks: set[str]) -> pd.DataFrame:
    test = audit[audit["split"].eq("test")].copy()
    test["already_exposed_in_existing_C1_semi"] = test["image_id"].isin(existing_tasks)
    test["reference_tier"] = np.where(
        test["gt_source_type"].eq("confirmed_user_manual_gt_correction"),
        "confirmed_manual_correction",
        "official_reference_requires_prospective_task_audit",
    )
    exact = test[test["topology_exact_bool"]].copy()
    values = numeric(exact["topdown_2d_iou"]).dropna()
    q1, q2, q3 = (values.quantile(q) for q in (0.25, 0.50, 0.75))

    def severity(row: pd.Series) -> str:
        if not row["topology_exact_bool"]:
            return row["proposal_topology_relation"]
        value = float(row["topdown_2d_iou"])
        if value <= q1:
            return "same_pair_count_lowest_2d_iou_quartile"
        if value <= q2:
            return "same_pair_count_q2"
        if value <= q3:
            return "same_pair_count_q3"
        return "same_pair_count_highest_2d_iou_quartile"

    test["development_sampling_stratum"] = test.apply(severity, axis=1)
    test["confirmatory_candidate_not_yet_semi_exposed"] = ~test["already_exposed_in_existing_C1_semi"]
    test["natural_model_output_role"] = np.select(
        [
            test["proposal_topology_relation"].eq("model_more_pairs"),
            test["proposal_topology_relation"].eq("model_fewer_pairs"),
            test["topology_exact_bool"] & test["initialization_acceptable_bool"],
            test["topology_exact_bool"],
        ],
        [
            "candidate_extra_structure_natural_error",
            "candidate_missing_structure_natural_error",
            "candidate_same_topology_operationally_acceptable_posthoc",
            "candidate_same_topology_geometry_difference",
        ],
        default="invalid_or_unclassified",
    )
    test["experimental_role_warning"] = (
        "natural outputs are sampling candidates only; experimental correct/wrong status must be frozen by independent reference review or controlled perturbation"
    )
    keep = [
        "image_id", "split", "building_id", "image_path", "model_path", "gt_path",
        "gt_source_type", "reference_tier", "model_sha256", "gt_sha256",
        "proposal_topology_relation", "pair_count_delta", "model_pair_count", "gt_pair_count",
        "topdown_2d_iou", "layoutnetv2_style_3d_iou", "corner_error_percent_diagonal",
        "corner_f1_1pct", "layout_mask_difference", "boundary_rmse_px",
        "operational_initialization_band", "initialization_class",
        "development_sampling_stratum", "natural_model_output_role",
        "already_exposed_in_existing_C1_semi", "confirmatory_candidate_not_yet_semi_exposed",
        "experimental_role_warning",
    ]
    return test[keep].sort_values(["development_sampling_stratum", "building_id", "image_id"]).reset_index(drop=True)


def markdown_table(frame: pd.DataFrame, columns: list[str], max_rows: int = 30) -> str:
    subset = frame[columns].head(max_rows).copy()
    if subset.empty:
        return "(no rows)"
    lines = ["| " + " | ".join(columns) + " |", "|" + "|".join(["---"] * len(columns)) + "|"]
    for row in subset.itertuples(index=False, name=None):
        cells = []
        for value in row:
            if isinstance(value, float):
                cells.append("" if math.isnan(value) else f"{value:.4f}")
            else:
                cells.append(str(value))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    audit = pd.read_csv(AUDIT, encoding="utf-8-sig", low_memory=False)
    task = pd.read_csv(TASK, encoding="utf-8-sig", low_memory=False)
    response = pd.read_csv(ROWS, encoding="utf-8-sig", low_memory=False)

    audit["topology_exact_bool"] = audit["topology_exact"].map(truth)
    audit["initialization_correct_bool"] = audit["initialization_correct"].map(truth)
    audit["initialization_acceptable_bool"] = audit["initialization_acceptable"].map(truth)
    audit["proposal_topology_relation"] = audit.apply(topology_relation, axis=1)
    audit["audit_problem_family"] = audit.apply(audit_family, axis=1)
    audit["building_id"] = audit["image_id"].astype(str).str.split("_", n=1).str[0]

    if len(audit) != 648 or set(audit["split"]) != {"test", "validation"}:
        raise AssertionError("model audit population drift")
    if task["base_task_id"].nunique() != 25:
        raise AssertionError("expected 25 existing Semi tasks")

    audit_columns = [
        "image_id", "split", "metric_object", "gt_variant", "gt_source_type",
        "model_sha256", "gt_sha256", "model_pair_encoding_valid", "model_pair_count",
        "gt_pair_count", "pair_count_delta", "topology_exact_bool", "proposal_topology_relation",
        "audit_problem_family", "corner_f1_1pct", "corner_localization_pass",
        "corner_error_percent_diagonal", "topdown_2d_iou", "layoutnetv2_style_3d_iou",
        "layout_mask_difference", "boundary_rmse_px", "geometry_acceptable",
        "initialization_acceptable_bool", "initialization_correct_bool",
        "operational_initialization_band", "initialization_class", "difference_band",
        "image_path", "model_path", "gt_path",
    ]
    task_join = task.merge(
        audit[audit_columns], left_on="base_task_id", right_on="image_id", how="left", validate="one_to_one"
    )
    task_join["audit_join_status"] = np.where(task_join["image_id"].notna(), "matched", "missing")
    if not task_join["audit_join_status"].eq("matched").all():
        raise AssertionError("not all existing C1 Semi tasks joined to the current model audit")
    task_join["old_initial_quality_vs_current_audit_warning"] = (
        "historical U_initial is retained but is not interchangeable with current topology/continuous proposal audit"
    )
    task_join = task_join.drop(columns=["image_id"])

    c1 = response[response["stage"].eq("C1")].copy()
    c1["issue_tokens"] = c1["model_issue_choice"].map(parse_issue_tokens)
    c1["worker_issue_response_observed"] = c1["issue_tokens"].map(bool)
    c1["worker_acceptable_reported"] = c1["issue_tokens"].map(lambda values: "acceptable" in values)
    c1["worker_any_issue_reported"] = c1["issue_tokens"].map(
        lambda values: bool(set(values) - {"acceptable"})
    )
    c1["worker_issue_tokens"] = c1["issue_tokens"].map(lambda values: ";".join(values))
    row_join = c1.merge(
        task_join[
            [
                "base_task_id", "split", "gt_source_type", "model_sha256", "gt_sha256",
                "model_pair_count", "gt_pair_count", "pair_count_delta", "topology_exact_bool",
                "proposal_topology_relation", "audit_problem_family", "corner_f1_1pct",
                "topdown_2d_iou", "layoutnetv2_style_3d_iou", "layout_mask_difference",
                "boundary_rmse_px", "initialization_acceptable_bool", "initialization_correct_bool",
                "operational_initialization_band",
            ]
        ],
        on="base_task_id", how="inner", validate="many_to_one",
    )
    compatibility = row_join.apply(
        lambda row: compatible_issue_family(row["audit_problem_family"], row["issue_tokens"]), axis=1
    )
    row_join["worker_issue_family_compatible_with_audit_proxy"] = [item[0] for item in compatibility]
    row_join["compatible_issue_overlap"] = [item[1] for item in compatibility]
    row_join["family_compatibility_boundary"] = (
        "semantic worker tags and geometric audit families are not identical constructs; descriptive bridge only"
    )
    row_join = row_join.drop(columns=["issue_tokens"])

    topology_summary = summarise_group(task_join, "proposal_topology_relation")
    band_summary = summarise_group(task_join, "operational_initialization_band")
    detect = detection_summary(row_join)
    family = (
        row_join.groupby(["audit_problem_family", "worker_issue_tokens"], dropna=False)
        .agg(
            row_count=("canonical_annotation_id", "size"),
            task_count=("base_task_id", "nunique"),
            worker_count=("worker_id", "nunique"),
            mean_delta_U=("delta_U", lambda x: numeric(x).mean()),
            compatible_rate=("worker_issue_family_compatible_with_audit_proxy", lambda x: pd.to_numeric(x, errors="coerce").mean()),
        )
        .reset_index()
        .sort_values(["audit_problem_family", "row_count"], ascending=[True, False])
    )
    split = split_summary(audit)
    sample = build_sampling_frame(audit, set(task["base_task_id"].astype(str)))

    write_csv(OUT / "C1_EXISTING_SEMI_TASKS_JOINED_WITH_CURRENT_MODEL_AUDIT.csv", task_join)
    write_csv(OUT / "C1_EXISTING_SEMI_RESPONSE_ROWS_JOINED_WITH_CURRENT_MODEL_AUDIT.csv", row_join)
    write_csv(OUT / "C1_TASK_SUMMARY_BY_TOPOLOGY_RELATION.csv", topology_summary)
    write_csv(OUT / "C1_TASK_SUMMARY_BY_LEGACY_OPERATIONAL_BAND.csv", band_summary)
    write_csv(OUT / "MODEL_ISSUE_DETECTION_DESCRIPTIVE_SUMMARY.csv", detect)
    write_csv(OUT / "MODEL_ISSUE_FAMILY_COMPATIBILITY.csv", family)
    write_csv(OUT / "MODEL_INITIALIZATION_SPLIT_SUMMARY.csv", split)
    write_csv(OUT / "FUTURE_PROPOSAL_SAMPLING_FRAME_TEST.csv", sample)

    report = f"""# Proposal correctness × Model Issue 数据桥接（2026-08-23）

## 核心裁决

1. 当前 648 张审计的主硬门只是 `valid pair encoding + exact corner-pair count`；它是拓扑数量代理，不是完整 topology 正确性，也不是可直接提交性。
2. `.90/.80/.05` strict gate 与 `.75/.65/2%` acceptable gate 都是历史 post-hoc operational thresholds。本报告保留它们作为敏感性字段，不把它们升级为确认性 correctness 标签。
3. 现有 25 张 C1 Semi 任务已全部连接到当前审计；历史 `U_initial` 与当前 proposal audit 不是同一个量，禁止静默替换或混用。
4. `model_issue` worker response 与几何审计 family 不是同一构念；本报告只提供描述性 crosswalk，不把它解释成独立验证或因果机制。
5. Validation/Test 差距在同一 checkpoint 和同一推理配置下仍存在；Validation 是开发集，Test 是最终泛化集。不能用 Validation 的高通过率规划确认性“正确 proposal”比例。

## 输入覆盖

- Model audit: {len(audit)} images; Test={int((audit['split']=='test').sum())}, Validation={int((audit['split']=='validation').sum())}.
- Existing C1 paired Semi tasks: {task['base_task_id'].nunique()}.
- Joined C1 response rows: {len(row_join)}; workers={row_join['worker_id'].nunique()}.
- Test sampling frame after excluding already exposed C1 Semi images: {int(sample['confirmatory_candidate_not_yet_semi_exposed'].sum())}/{len(sample)}.

## Split 审计

{markdown_table(split, ['split','n','topology_pair_count_exact_rate','mean_topdown_2d_iou','mean_derived_3d_iou','posthoc_strict_pass_n','posthoc_acceptable_n'])}

## 现有 C1 任务按角点数量关系

{markdown_table(topology_summary, ['proposal_topology_relation','task_count','building_count','mean_delta_shannon_entropy','mean_delta_iou_to_gt','mean_edit_rate','mean_issue_report_rate'])}

这些均是自然发生、观察性的小样本结果。它们不能估计“正确 proposal 的帮助”或“错误 proposal 的伤害”。

## Model Issue 检出桥接

{markdown_table(detect, ['audit_outcome','row_count','task_count','worker_count','sensitivity','specificity','status'])}

解释边界：

- `pair_count_mismatch` 只表示模型/GT 角点对数量不等；它不等于 UI 中的 `topology_failure`（配对、闭合、自交等非法结构）。
- `posthoc_not_strict_pass` 和 `posthoc_not_acceptable` 使用分析者定义阈值，只能作为敏感性。
- Worker 在编辑过程中可随时看到并修改 Model Issue 回答；当前 UI 没有锁定 pre-edit 判断，因此不能把它当成纯粹的 issue-recognition 测量。

## 后续实验所需 correctness 状态

未来确认性实验不要从单个连续指标事后二分。每个 proposal 应在分配前保存：

```text
proposal_design_arm: manual / correct / wrong
proposal_generation_source: expert_reference / frozen_model / controlled_perturbation
proposal_error_family: none / localization / missing_structure / extra_structure / adjacent_space / invalid_topology
proposal_error_magnitude
reference_review_status
scope_terminal
proposal_manifest_sha256
```

`correct` 应表示在冻结 operational target 下，经独立 reference review 认可、无需实质结构修复；`wrong` 应由预先冻结的 error operator 与 magnitude 产生。自然模型输出可以用于选图，但不应在看到人工结果后才决定其实验身份。

## 直接复现

```bash
python -m tools.thesis_main.analysis.full_uncertainty.materialize_proposal_correctness_model_issue_bridge_20260823
```
"""
    (OUT / "ANALYSIS_REPORT_ZH.md").write_text(report, encoding="utf-8")

    input_rows = []
    for role, path in (("model_audit", AUDIT), ("semi_task_table", TASK), ("semi_response_rows", ROWS)):
        input_rows.append({"role": role, "path": path.relative_to(ROOT).as_posix(), "size_bytes": path.stat().st_size, "sha256": sha256(path)})
    write_csv(OUT / "INPUT_AUDIT.csv", pd.DataFrame(input_rows))

    output_rows = []
    for path in sorted(OUT.iterdir()):
        if path.name in {"OUTPUT_MANIFEST.csv", "RUN_MANIFEST.json"} or not path.is_file():
            continue
        output_rows.append({"path": path.name, "size_bytes": path.stat().st_size, "sha256": sha256(path)})
    write_csv(OUT / "OUTPUT_MANIFEST.csv", pd.DataFrame(output_rows))
    manifest = {
        "schema_version": "proposal_correctness_model_issue_bridge_v1",
        "created_date": "2026-08-23",
        "source_commit": git_head(),
        "seed": SEED,
        "input_sha256": {row["role"]: row["sha256"] for row in input_rows},
        "counts": {
            "model_audit_rows": len(audit),
            "c1_task_rows": len(task_join),
            "c1_response_rows": len(row_join),
            "test_sampling_frame_rows": len(sample),
            "unexposed_test_candidate_rows": int(sample["confirmatory_candidate_not_yet_semi_exposed"].sum()),
        },
        "assertions": {
            "all_25_c1_tasks_joined": bool(task_join["audit_join_status"].eq("matched").all()),
            "model_audit_648": len(audit) == 648,
            "split_counts": Counter(audit["split"]).copy(),
        },
        "interpretation_boundary": "descriptive bridge; no causal correct/wrong proposal effect estimated",
    }
    (OUT / "RUN_MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, default=int) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2, default=int))


if __name__ == "__main__":
    main()
