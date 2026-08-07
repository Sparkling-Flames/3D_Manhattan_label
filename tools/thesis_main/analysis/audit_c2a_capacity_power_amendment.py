from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from statistics import NormalDist

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import lil_matrix

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.thesis_main.analysis.c1_live_collection_monitor import read_csv, truthy, write_json
from tools.thesis_main.analysis.c1_materialize_c2_gap_audits import _maximum_complete_block_count
from tools.thesis_main.analysis.vfinal_artifact_utils import sha256_file


def _reserve(tasks: list[dict], count: int) -> list[dict]:
    return tasks + [
        {
            "task_id": f"AMENDMENT_STRESS_{index:03d}",
            "base_task_id": f"AMENDMENT_STRESS_{index:03d}",
            "task_stratum": "stress",
            "c2a_rp_eligible": "true",
        }
        for index in range(1, count + 1)
    ]


def capacity_curve(
    workers: list[dict],
    tasks: list[dict],
    history: list[dict],
    *,
    max_task_support: int,
    max_new_stress: int,
) -> list[dict]:
    return [
        {
            "new_stress_tasks": count,
            "new_stress_slots": count * max_task_support,
            "maximum_block1_workers": _maximum_complete_block_count(
                workers,
                _reserve(tasks, count),
                history_rows=history,
                max_task_support=max_task_support,
                require_explicit_eligibility=True,
            ),
        }
        for count in range(max_new_stress + 1)
    ]


def _all_rounds_feasible(
    workers: list[dict],
    tasks: list[dict],
    history: list[dict],
    required_blocks: dict[str, int],
    max_task_support: int,
) -> bool:
    worker_ids = [str(row["worker_id"]) for row in workers]
    pools = [
        (str(row["task_id"]), str(row.get("base_task_id") or row["task_id"]), str(row["task_stratum"]).lower())
        for row in tasks
        if str(row.get("task_stratum", "")).lower() in {"ordinary", "stress"}
        and truthy(row.get("c2a_rp_eligible"))
    ]
    seen = {worker: set() for worker in worker_ids}
    support: dict[str, int] = {}
    for row in history:
        worker, task = str(row.get("worker_id", "")), str(row.get("task_id", ""))
        if worker in seen:
            seen[worker].update(filter(None, (task, str(row.get("base_task_id", "")))))
        if task and (not row.get("round_id") or row.get("round_id") == "C2-A-RP"):
            support[task] = support.get(task, 0) + 1
    edges = [
        (worker, task, base, stratum)
        for worker in worker_ids
        for task, base, stratum in pools
        if task not in seen[worker] and base not in seen[worker] and support.get(task, 0) < max_task_support
    ]
    constraints: list[tuple[dict[int, int], float, float]] = []
    for worker in worker_ids:
        for stratum in ("ordinary", "stress"):
            row = {index: 1 for index, edge in enumerate(edges) if edge[0] == worker and edge[3] == stratum}
            demand = required_blocks[worker]
            constraints.append((row, demand, demand))
        for base in {edge[2] for edge in edges if edge[0] == worker}:
            same_base = {index: 1 for index, edge in enumerate(edges) if edge[0] == worker and edge[2] == base}
            constraints.append((same_base, -np.inf, 1))
    for task in {edge[1] for edge in edges}:
        row = {index: 1 for index, edge in enumerate(edges) if edge[1] == task}
        constraints.append((row, -np.inf, max_task_support - support.get(task, 0)))
    matrix = lil_matrix((len(constraints), len(edges)), dtype=float)
    for row_index, (values, _low, _high) in enumerate(constraints):
        for column, value in values.items():
            matrix[row_index, column] = value
    result = milp(
        np.zeros(len(edges)),
        integrality=np.ones(len(edges)),
        bounds=Bounds(np.zeros(len(edges)), np.ones(len(edges))),
        constraints=LinearConstraint(
            matrix.tocsr(),
            np.array([low for _row, low, _high in constraints]),
            np.array([high for _row, _low, high in constraints]),
        ),
    )
    return bool(result.success)


def _normal_power(effect: float, sd: float, total_n: int, alpha: float = 0.05) -> float:
    se = sd * math.sqrt(1 / (total_n // 2) + 1 / (total_n - total_n // 2))
    return 1 - NormalDist().cdf(NormalDist().inv_cdf(1 - alpha) - effect / se)


def power_scenario(
    workers: list[dict],
    true_slopes: dict[str, float],
    *,
    target_half_width: float,
    stress_fraction: float,
    total_v1_tasks: int,
    outcome_sd: float,
    blocks: int,
    draws: int,
    seed: int,
    force_no_adjustment: bool = False,
) -> dict:
    qgt = np.array([float(row["Q_GT_EB"]) for row in workers])
    slopes = np.array([true_slopes[str(row["worker_id"])] for row in workers])
    global_pick = int(np.argmax(qgt))
    support = np.array([float(row["risk_slope_support"]) for row in workers])
    current_se = np.array([float(row["risk_slope_se"]) for row in workers])
    projected_se = current_se * np.sqrt(support / (support + 2 * blocks))
    active = 1.96 * projected_se <= target_half_width
    if force_no_adjustment:
        return {
            "blocks": blocks,
            "precision_active_workers": int(active.sum()),
            "risk_adjustment_active_workers": 0,
            "stress_policy_divergence_probability": 0.0,
            "policy_divergence": 0.0,
            "expected_quality_difference": 0.0,
            "quality_proxy_power": _normal_power(0.0, outcome_sd, total_v1_tasks),
        }
    rng = np.random.default_rng(seed + blocks)
    estimates = rng.normal(slopes, projected_se, size=(draws, len(workers)))
    scores = np.broadcast_to(qgt, estimates.shape).copy()
    scores[:, active] += estimates[:, active]
    picks = np.argmax(scores, axis=1)
    divergence = picks != global_pick
    true_quality = qgt + slopes
    effects = stress_fraction * (true_quality[picks] - true_quality[global_pick])
    expected_effect = float(np.mean(effects))
    return {
        "blocks": blocks,
        "precision_active_workers": int(active.sum()),
        "risk_adjustment_active_workers": int(active.sum()),
        "stress_policy_divergence_probability": float(np.mean(divergence)),
        "policy_divergence": float(stress_fraction * np.mean(divergence)),
        "expected_quality_difference": expected_effect,
        "quality_effect_p05": float(np.quantile(effects, 0.05)),
        "quality_effect_p95": float(np.quantile(effects, 0.95)),
        "quality_proxy_power": _normal_power(expected_effect, outcome_sd, total_v1_tasks),
    }


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        fields = list(dict.fromkeys(key for row in rows for key in row))
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def materialize(output_dir: Path) -> dict:
    workers_all = read_csv(ROOT / "analysis_results/c2a_rp_local_launch_20260807_v4/post_c2b_worker_profile.csv")
    workers = [
        row for row in workers_all
        if row.get("c2_risk_model_eligible", "").lower() == "true" and row.get("risk_slope_se")
    ]
    tasks = read_csv(ROOT / "analysis_results/c2a_rp_local_launch_20260807_inputs_v2/c2a_rp_task_pool_post_c2_local.csv")
    history = read_csv(ROOT / "analysis_results/c2b_closeout_20260806_inputs/c2a_rp_seen_history_through_c2b.csv")
    threshold = json.loads((ROOT / "analysis_results/c2b_validation_design_20260802_v17/output/c2b_derived_threshold_manifest.json").read_text(encoding="utf-8"))
    decision = json.loads((ROOT / "analysis_results/c2b_closeout_20260806_inputs/c2a_rp_decision_source_manifest.json").read_text(encoding="utf-8"))
    prior = json.loads((ROOT / "analysis_results/c2b_closeout_20260806_final/c2b_c2a_rp_analysis_manifest.json").read_text(encoding="utf-8"))
    stage3 = read_csv(ROOT / "analysis_results/stage3_test_preparation_20260804_v1/test_task_risk_candidate.csv")
    target = float(threshold["thresholds"]["risk_slope_ci_half_width"])
    max_support = int(decision["precision"]["max_task_support"])
    curve = capacity_curve(workers, tasks, history, max_task_support=max_support, max_new_stress=12)
    for row in curve:
        row["block1_20_of_20_feasible"] = row["maximum_block1_workers"] == len(workers)
    block1_min = next(row["new_stress_tasks"] for row in curve if row["block1_20_of_20_feasible"])
    required_blocks = {
        str(row["worker_id"]): 1 + int(1.96 * float(row["risk_slope_se"]) * math.sqrt(
            float(row["risk_slope_support"]) / (float(row["risk_slope_support"]) + 2)
        ) > target)
        for row in workers
    }
    for row in curve:
        row["projected_two_round_plan_feasible"] = _all_rounds_feasible(
            workers, _reserve(tasks, row["new_stress_tasks"]), history, required_blocks, max_support
        )
    two_round_min = next(
        row["new_stress_tasks"] for row in curve if row["projected_two_round_plan_feasible"]
    )
    stress_count = sum(row.get("risk_design_stratum") == "stress" for row in stage3)
    stress_fraction = stress_count / len(stage3)
    risk = prior["risk_model"]
    outcome_sd = math.sqrt(
        float(risk["outcome_residual_sd"]) ** 2 + float(risk["task_sd"]) ** 2 + float(risk["building_sd"]) ** 2
    )
    primary_slopes = {str(row["worker_id"]): float(row["risk_slope"]) for row in workers}
    sensitivity_slopes = {str(key): float(value) for key, value in risk["worker_slopes"].items()}
    power_rows = []
    for name, slopes, disabled in (
        ("current_boundary_primary", primary_slopes, True),
        ("prior_nonzero_heterogeneity_sensitivity", sensitivity_slopes, False),
    ):
        for blocks in (1, 2):
            power_rows.append({
                "scenario": name,
                **power_scenario(
                    workers, slopes,
                    target_half_width=target,
                    stress_fraction=stress_fraction,
                    total_v1_tasks=len(stage3),
                    outcome_sd=outcome_sd,
                    blocks=blocks,
                    draws=20_000,
                    seed=20260724,
                    force_no_adjustment=disabled,
                ),
            })
    result = {
        "schema_version": "c2a_rp_capacity_power_amendment_audit_v1",
        "status": "audit_only_not_launch_authorization",
        "current_v4_dispatch_status": "frozen_not_dispatched",
        "input_sha256": {
            "worker_profile": sha256_file(ROOT / "analysis_results/c2a_rp_local_launch_20260807_v4/post_c2b_worker_profile.csv"),
            "task_pool": sha256_file(ROOT / "analysis_results/c2a_rp_local_launch_20260807_inputs_v2/c2a_rp_task_pool_post_c2_local.csv"),
            "seen_history": sha256_file(ROOT / "analysis_results/c2b_closeout_20260806_inputs/c2a_rp_seen_history_through_c2b.csv"),
            "threshold_manifest": sha256_file(ROOT / "analysis_results/c2b_validation_design_20260802_v17/output/c2b_derived_threshold_manifest.json"),
            "sensitivity_model": sha256_file(ROOT / "analysis_results/c2b_closeout_20260806_final/c2b_c2a_rp_analysis_manifest.json"),
            "v1_candidate_tasks": sha256_file(ROOT / "analysis_results/stage3_test_preparation_20260804_v1/test_task_risk_candidate.csv"),
        },
        "active_workers": len(workers),
        "current_maximum_block1_workers": curve[0]["maximum_block1_workers"],
        "minimum_new_stress_tasks_for_block1_20_of_20": block1_min,
        "workers_projected_to_need_block2": sum(value == 2 for value in required_blocks.values()),
        "minimum_total_new_stress_tasks_for_projected_two_round_plan": two_round_min,
        "stress_task_support_cap": max_support,
        "v1_candidate_task_count": len(stage3),
        "v1_stress_task_count": stress_count,
        "v1_stress_fraction": stress_fraction,
        "v1_power_scope": "quality_only_proxy; policy divergence diagnostic; severe/unresolved endpoints not identifiable",
        "capacity_curve": curve,
        "power_scenarios": power_rows,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "c2a_rp_capacity_power_amendment.json", result)
    _write_csv(output_dir / "capacity_scenarios.csv", curve)
    _write_csv(output_dir / "v1_power_scenarios.csv", power_rows)
    report = f"""# C2-A-RP 显著性优先 capacity / power amendment（本地审计）

## 决策结论

- 当前 v4 保持冻结，未授权发放。
- Block 1 当前精确容量为 **{curve[0]['maximum_block1_workers']}/20**；新增 **{block1_min} 张**对全部 20 人未见、每图最多 2 人的 stress task 后，精确匹配达到 **20/20**。
- 按冻结 CI 投影，Block 1 后仍有 **{sum(value == 2 for value in required_blocks.values())} 人**可能需要 Block 2；若现在为这一路径一次性备足，累计至少新增 **{two_round_min} 张** stress task。
- 不建议现在新增工人：新工人不能直接提供已校准的 Full 画像，反而新增 P1/C1/C2 校准负担。

## V1 诊断结果

当前正式点估计的 worker slope 方差位于 0 边界，因此 Full 的风险个体化分量应禁用：Block 1/2 下 policy divergence 均为 0，质量优势效应为 0，质量代理功效仅为名义 alpha（约 0.05）。

以下非零异质性结果仅使用 C2-B 旧模型作敏感性诊断，不是正式预注册 power，也不用于反向选择 reserve 数量：

| 阶段 | 启用风险个体化人数 | stress 内政策分歧概率 | 全 V1 policy divergence | 期望质量差 | 质量代理功效 |
|---|---:|---:|---:|---:|---:|
"""
    for row in power_rows:
        if row["scenario"] == "prior_nonzero_heterogeneity_sensitivity":
            report += f"| Block {row['blocks']} | {row['risk_adjustment_active_workers']}/20 | {row['stress_policy_divergence_probability']:.3f} | {row['policy_divergence']:.3f} | {row['expected_quality_difference']:.5f} | {row['quality_proxy_power']:.3f} |\n"
    report += """

功效假定 458 个 V1 candidate task、1:1 分配、单侧 0.05 正态近似；只覆盖 delivery-adjusted quality 代理，不覆盖 V1 层级中的 severe failure、unresolved+severe failure、动态容量或聚合效应。

## 建议

先新增 {block1_min} 张 stress reserve 并完成 20/20 Block 1；随后用真实 Block 1 结果重估 slope 方差与 CI。只有非零异质性仍存在且 16 人确需 Block 2 时，再补至累计 {two_round_min} 张。现在一次性补足两轮 reserve 或招新工人都没有新增决策价值。

容量结论以新增图均为 validation-only、对 20 人全部未见、通过 scope/reference 审核且每图支持上限为 2 为条件；本审计不负责选择或导入这些图片。
"""
    (output_dir / "C2A_RP_CAPACITY_POWER_AMENDMENT_REPORT.md").write_text(report, encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "analysis_results/c2a_rp_capacity_power_amendment_20260807_v1")
    args = parser.parse_args()
    materialize(args.output_dir)
