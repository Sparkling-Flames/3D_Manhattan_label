"""Audit whether Manual-only evidence supports reusable worker strata.

The classifier is trained on C1 Calibration_core Manual tasks.  Every dense
Manual evaluation building is excluded from its own classifier.  H/L/U are
fold-specific evidence strata, not worker personalities or formal tiers.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from itertools import combinations, product
from pathlib import Path
from statistics import mean
from typing import Any, Mapping, Sequence

import numpy as np
from scipy.stats import spearmanr

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.thesis_main.analysis import analyze_worker_behavior_mixture_exploratory as replay
from tools.thesis_main.analysis import materialize_historical_uncertainty_k_curves_20260829 as historical


ROOT = _PROJECT_ROOT
DEFAULT_OUT = ROOT / "analysis_results" / "worker_manual_strata_audit_20260904_v1"
C1_AUDIT = (
    ROOT
    / "analysis_results"
    / "c1_formal_audit_20260802_v16_final"
    / "c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03"
)
CORE_VARIANTS = {
    "augmented_authorized": C1_AUDIT / "c1_gt_quality_analysis.csv",
    "w034_original_only": C1_AUDIT / "w034_original_only_branch" / "c1_gt_quality_original_only.csv",
}
STRUCTURAL_SOURCE = C1_AUDIT / "structural_validation_analysis.csv"
CURRENT20 = tuple(
    str(value)
    for value in (1, 2, 6, 8, 10, 11, 12, 13, 15, 17, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37)
)
HIGH = "H_higher_manual_quality_evidence"
LOW = "L_lower_manual_quality_evidence"
UNCLASSIFIED = "U_unclassified"
CLASSIFICATION_BOOTSTRAPS = 1_000
EVIDENCE_PROBABILITY = 0.80
SEED = 20260904
METRICS = (
    "resolved_rate",
    "all_three_votes_usable_rate",
    "mean_valid_vote_count",
    "supported_multimodal_rate",
    "not_evaluable_rate",
    "resolved_only_quality",
    "delivery_adjusted_quality",
    "pooled_full_output_recovery_rate",
)


def classify_probability(probability_positive: float) -> str:
    if probability_positive > EVIDENCE_PROBABILITY or math.isclose(
        probability_positive, EVIDENCE_PROBABILITY, rel_tol=1e-12, abs_tol=1e-12
    ):
        return HIGH
    lower = 1.0 - EVIDENCE_PROBABILITY
    if probability_positive < lower or math.isclose(
        probability_positive, lower, rel_tol=1e-12, abs_tol=1e-12
    ):
        return LOW
    return UNCLASSIFIED


def _design(
    rows: Sequence[Mapping[str, Any]], workers: Sequence[str]
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    tasks = sorted({str(row["base_task_id"]) for row in rows})
    worker_index = {worker: index for index, worker in enumerate(workers)}
    task_index = {task: index for index, task in enumerate(tasks)}
    matrix = np.zeros((len(rows), len(workers) + len(tasks)), dtype=float)
    for row_index, row in enumerate(rows):
        matrix[row_index, worker_index[str(row["worker_id"])]] = 1.0
        matrix[row_index, len(workers) + task_index[str(row["base_task_id"])]] = 1.0
    quality = np.asarray([float(row["quality"]) for row in rows], dtype=float)
    return matrix, quality, [str(row["building_id"]) for row in rows]


def _effects_from_design(
    matrix: np.ndarray,
    quality: np.ndarray,
    worker_count: int,
    weights: np.ndarray | None = None,
) -> np.ndarray:
    if weights is not None:
        root_weights = np.sqrt(weights)
        matrix = matrix * root_weights[:, None]
        quality = quality * root_weights
    effects = np.linalg.lstsq(matrix, quality, rcond=None)[0][:worker_count]
    return effects - effects.mean()


def fit_worker_task_effects(
    rows: Sequence[Mapping[str, Any]], workers: Sequence[str] = CURRENT20
) -> dict[str, float]:
    if not rows:
        raise ValueError("Manual worker model requires non-empty rows")
    observed = {str(row["worker_id"]) for row in rows}
    if observed != set(workers):
        raise ValueError(f"worker support mismatch: missing={sorted(set(workers) - observed)}")
    matrix, quality, _ = _design(rows, workers)
    effects = _effects_from_design(matrix, quality, len(workers))
    return {worker: float(effects[index]) for index, worker in enumerate(workers)}


def _connected(rows: Sequence[Mapping[str, Any]], workers: Sequence[str]) -> bool:
    adjacency: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        worker = f"w:{row['worker_id']}"
        task = f"t:{row['base_task_id']}"
        adjacency[worker].add(task)
        adjacency[task].add(worker)
    start = f"w:{workers[0]}"
    reached, stack = {start}, [start]
    while stack:
        node = stack.pop()
        for neighbour in adjacency[node] - reached:
            reached.add(neighbour)
            stack.append(neighbour)
    return all(f"w:{worker}" in reached for worker in workers)


def _seed(*parts: str) -> int:
    payload = "|".join(parts).encode("utf-8")
    return SEED + int(hashlib.sha256(payload).hexdigest()[:8], 16)


def _resample_building_then_task(
    rows: Sequence[Mapping[str, Any]], rng: np.random.Generator
) -> list[dict[str, Any]]:
    by_building: dict[str, dict[str, list[Mapping[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for row in rows:
        by_building[str(row["building_id"])][str(row["base_task_id"])].append(row)
    buildings = sorted(by_building)
    if len(buildings) < 2:
        raise ValueError("building-then-task bootstrap requires at least two buildings")
    sampled_buildings: list[str] = []
    while len(set(sampled_buildings)) < 2:
        sampled_buildings = [str(value) for value in rng.choice(buildings, size=len(buildings), replace=True)]
    sampled_rows: list[dict[str, Any]] = []
    for building_index, building in enumerate(sampled_buildings):
        tasks = sorted(by_building[building])
        sampled_tasks = [str(value) for value in rng.choice(tasks, size=len(tasks), replace=True)]
        for task_index, task in enumerate(sampled_tasks):
            instance = f"bootstrap_building_{building_index}_task_{task_index}"
            sampled_rows.extend(
                {**row, "building_id": f"bootstrap_building_{building_index}", "base_task_id": instance}
                for row in by_building[building][task]
            )
    return sampled_rows


def classify_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    seed: int,
    bootstraps: int = CLASSIFICATION_BOOTSTRAPS,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not _connected(rows, CURRENT20):
        raise AssertionError("worker-task graph is disconnected")
    matrix, quality, _ = _design(rows, CURRENT20)
    full_effects = _effects_from_design(matrix, quality, len(CURRENT20))
    buildings = sorted({str(row["building_id"]) for row in rows})
    rng = np.random.default_rng(seed)
    draws: list[np.ndarray] = []
    attempts = 0
    while len(draws) < bootstraps and attempts < bootstraps * 20:
        attempts += 1
        sampled_rows = _resample_building_then_task(rows, rng)
        if {str(row["worker_id"]) for row in sampled_rows} != set(CURRENT20) or not _connected(
            sampled_rows, CURRENT20
        ):
            continue
        sampled_matrix, sampled_quality, _ = _design(sampled_rows, CURRENT20)
        draws.append(_effects_from_design(sampled_matrix, sampled_quality, len(CURRENT20)))
    if len(draws) != bootstraps:
        raise AssertionError(f"only {len(draws)}/{bootstraps} connected bootstrap draws")

    draw_matrix = np.asarray(draws)
    output: list[dict[str, Any]] = []
    for index, worker in enumerate(CURRENT20):
        worker_rows = [row for row in rows if str(row["worker_id"]) == worker]
        probability = float(np.mean(draw_matrix[:, index] > 0.0))
        output.append(
            {
                "worker_id": worker,
                "worker_effect_centered": float(full_effects[index]),
                "probability_effect_positive_building_bootstrap": probability,
                "evidence_stratum": classify_probability(probability),
                "quality_task_support": len(worker_rows),
                "quality_building_support": len({row["building_id"] for row in worker_rows}),
            }
        )
    return output, {
        "training_row_count": len(rows),
        "training_task_count": len({row["base_task_id"] for row in rows}),
        "training_building_count": len(buildings),
        "bootstrap_replicates": len(draws),
        "bootstrap_attempts": attempts,
        "bootstrap_cluster": (
            "building_then_task_conditioned_on_two_outer_clusters_"
            "complete_worker_support_and_connected_graph"
        ),
        "worker_task_graph_connected": True,
        "class_counts": dict(Counter(row["evidence_stratum"] for row in output)),
    }


def _load_core(path: Path) -> list[dict[str, Any]]:
    rows = []
    for row in historical.read_csv(path):
        if (
            row.get("dataset_group") == "Calibration_core"
            and row.get("condition") == "manual"
            and str(row.get("worker_id")) in CURRENT20
            and historical.truth(row.get("gt_primary_analysis_eligible"))
        ):
            rows.append(
                {
                    "worker_id": str(row["worker_id"]),
                    "base_task_id": row["base_task_id"],
                    "building_id": row["building_id"],
                    "quality": float(row["iou_to_gt"]),
                }
            )
    if {row["worker_id"] for row in rows} != set(CURRENT20):
        raise AssertionError("C1 Core does not cover current20")
    return rows


def _unavailable_sample(target_resolved: bool) -> dict[str, float | None]:
    return {
        "resolved": 0.0,
        "supported_multimodal": 0.0,
        "not_evaluable": 1.0,
        "resolved_quality": None,
        "delivery_adjusted_quality": 0.0,
        "pooled_full_output_recovered": 0.0 if target_resolved else None,
    }


def _mixture_rows(
    pools: Mapping[str, Sequence[Mapping[str, Any]]],
    pair_maps: Mapping[str, Mapping[tuple[str, str], Mapping[str, Any]]],
    fold_groups: Mapping[tuple[str, str], Mapping[str, set[str]]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    current = set(CURRENT20)
    for variant in CORE_VARIANTS:
        for task, candidates in sorted(pools.items()):
            building = task.split("_", 1)[0]
            groups = fold_groups[(variant, building)]
            high_workers, low_workers = groups[HIGH], groups[LOW]
            if min(len(high_workers), len(low_workers)) < 2:
                raise AssertionError(f"k=3 composition unsupported: {variant} {building}")
            candidate_by_worker = {
                str(candidate["worker_id"]): candidate
                for candidate in candidates
                if str(candidate["worker_id"]) in current
            }
            pooled = list(candidate_by_worker.values())
            target_resolved, target_id = replay._pooled_target(pooled, task, pair_maps[task])
            for high_n, low_n in ((2, 1), (1, 2)):
                metrics = []
                valid_vote_counts = []
                for high_sample, low_sample in product(
                    combinations(sorted(high_workers, key=int), high_n),
                    combinations(sorted(low_workers, key=int), low_n),
                ):
                    selected_workers = high_sample + low_sample
                    sample = [candidate_by_worker[w] for w in selected_workers if w in candidate_by_worker]
                    valid_vote_counts.append(len(sample))
                    metrics.append(
                        replay._evaluate_sample(
                            sample,
                            task=task,
                            pair_map=pair_maps[task],
                            target_resolved=target_resolved,
                            target_id=target_id,
                        )
                        if len(sample) >= 3
                        else _unavailable_sample(target_resolved)
                    )
                scenario = f"{variant}|{high_n}H+{low_n}L"
                output.append(
                    {
                        "analysis_kind": "manual_crossfit_mixture_k3_exact",
                        "population_or_scenario": scenario,
                        "classification_variant": variant,
                        "base_task_id": task,
                        "building_id": building,
                        "stage": candidates[0]["stage"],
                        "reference_regime": "public_frozen_GT" if candidates[0]["stage"] == "C1" else "expert_hard_single_reference",
                        "k_total": 3,
                        "n_H": high_n,
                        "n_L": low_n,
                        "available_H_worker_n": len(high_workers),
                        "available_L_worker_n": len(low_workers),
                        "sampling_method": "exact_assigned_worker_compositions_without_replacement",
                        "samples_or_replicates": len(metrics),
                        "mean_valid_vote_count": mean(valid_vote_counts),
                        "all_three_votes_usable_rate": mean(value == 3 for value in valid_vote_counts),
                        "resolved_rate": mean(item["resolved"] for item in metrics),
                        "supported_multimodal_rate": mean(item["supported_multimodal"] for item in metrics),
                        "not_evaluable_rate": mean(item["not_evaluable"] for item in metrics),
                        "resolved_only_quality": replay._mean_present(item["resolved_quality"] for item in metrics),
                        "delivery_adjusted_quality": mean(item["delivery_adjusted_quality"] for item in metrics),
                        "pooled_full_output_recovery_rate": replay._mean_present(
                            item["pooled_full_output_recovered"] for item in metrics
                        ),
                        "pooled_full_target_resolved": target_resolved,
                        "mechanical_population_full_roster_endpoint": False,
                    }
                )
    return output


def _contrast_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for variant in CORE_VARIANTS:
        left = {
            row["base_task_id"]: row
            for row in rows
            if row["population_or_scenario"] == f"{variant}|2H+1L"
        }
        right = {
            row["base_task_id"]: row
            for row in rows
            if row["population_or_scenario"] == f"{variant}|1H+2L"
        }
        if set(left) != set(right):
            raise AssertionError("mixture scenarios have different task denominators")
        for task in sorted(left):
            first, second = left[task], right[task]
            row = {
                "analysis_kind": "manual_crossfit_mixture_contrast_exact",
                "population_or_scenario": f"{variant}|2H1L_minus_1H2L",
                "classification_variant": variant,
                "base_task_id": task,
                "building_id": first["building_id"],
                "stage": first["stage"],
                "reference_regime": first["reference_regime"],
                "k_total": 3,
                "sampling_method": "paired_task_difference_left_minus_right",
                "pooled_full_target_resolved": first["pooled_full_target_resolved"],
                "mechanical_population_full_roster_endpoint": False,
            }
            for metric in METRICS:
                a, b = historical.number(first.get(metric)), historical.number(second.get(metric))
                row[metric] = a - b if a is not None and b is not None else None
            output.append(row)
    return output


def structural_failure_audit(
    rows: Sequence[Mapping[str, Any]], core_task_ids: set[str]
) -> dict[str, int]:
    opportunities = [
        row
        for row in rows
        if row.get("condition") == "manual"
        and str(row.get("worker_id")) in CURRENT20
        and str(row.get("base_task_id")) in core_task_ids
        and historical.truth(row.get("structural_opportunity_eligible"))
    ]
    failures = [
        row
        for row in opportunities
        if historical.truth(row.get("worker_structural_failure_numerator"))
    ]
    return {
        "opportunity_count": len(opportunities),
        "worker_caused_failure_count": len(failures),
        "worker_with_recurrent_failures_count": sum(
            count >= 2 for count in Counter(str(row["worker_id"]) for row in failures).values()
        ),
    }


def _summary_row(
    summary: Sequence[Mapping[str, Any]], variant: str, stratum: str, metric: str
) -> Mapping[str, Any]:
    matches = [
        row
        for row in summary
        if row["analysis_kind"] == "manual_crossfit_mixture_contrast_exact"
        and row["population_or_scenario"] == f"{variant}|2H1L_minus_1H2L"
        and row["analysis_stratum"] == stratum
        and row["metric"] == metric
    ]
    if len(matches) != 1:
        raise AssertionError((variant, stratum, metric, len(matches)))
    return matches[0]


def _format_effect(row: Mapping[str, Any]) -> str:
    value = float(row["estimate_task_equal"])
    lower = float(row["ci95_lower_building_bootstrap"])
    upper = float(row["ci95_upper_building_bootstrap"])
    return f"{value:+.4f} [{lower:+.4f}, {upper:+.4f}]"


def _build_report(
    qa: Mapping[str, Any], summary: Sequence[Mapping[str, Any]], full_profiles: Sequence[Mapping[str, Any]]
) -> str:
    augmented = [row for row in full_profiles if row["classification_variant"] == "augmented_authorized"]
    original = [row for row in full_profiles if row["classification_variant"] == "w034_original_only"]
    class_counts = Counter(row["evidence_stratum"] for row in augmented)
    original_counts = Counter(row["evidence_stratum"] for row in original)
    lines = []
    for variant, label in (("augmented_authorized", "当前授权版本"), ("w034_original_only", "W034 original-only")):
        for stratum in ("C1_primary_12", "P1_reference_sensitivity_29", "pooled_reference_sensitivity_41"):
            delivery = _summary_row(summary, variant, stratum, "delivery_adjusted_quality")
            resolved = _summary_row(summary, variant, stratum, "resolved_rate")
            quality = _summary_row(summary, variant, stratum, "resolved_only_quality")
            usable = _summary_row(summary, variant, stratum, "all_three_votes_usable_rate")
            lines.append(
                f"| {label} | {stratum} | {_format_effect(usable)} | {_format_effect(resolved)} | "
                f"{_format_effect(delivery)} | {_format_effect(quality)} "
                f"(n={quality['task_count_with_metric']}/{quality['task_count']}) |"
            )
    return f"""# Manual-only worker 分层审计

## 裁决

**当前 Manual 数据不支持冻结成稳定的 good/sloppy worker 类型。**

上一版 9/5/6 使用 P1 Semi proposal-response，只能回答预标注反应差异，不能作为本问题的 worker 分类；该结果在这里不再使用。

本审计只使用 Manual：

- 分类：C1 `Calibration_core`，当前20人共 {qa['augmented_training']['raw_current20_row_count']} 条 Manual，正式 Q_GT 可用 {qa['augmented_training']['eligible_row_count']} 条、{qa['augmented_training']['eligible_task_count']} 题、{qa['augmented_training']['eligible_building_count']} 个 building。
- 评价：41张有 reference 的高密度 Manual 图；C1 12张 public frozen GT 为主，P1 29张 expert hard-single reference 为敏感性。
- 每个评价 building 都从自己的分类训练集中排除；分类题与评价题重叠为0。

## 分类规则

对每一评价 building，使用其他 building 的 Core Manual 拟合：

`Q_GT = worker fixed effect + task fixed effect + error`

沿用既有 Q_GT 合同的 building→task 两层 bootstrap；每个重采样还须保留20人支持齐全且 worker–task 图连通：

- `P(相对当前20人均值的中心化 worker effect > 0) >= 0.80`：H，较高 Manual 参考质量证据；
- 上述概率 `<= 0.20`：L，较低 Manual 参考质量证据；
- 其余：U，暂不分类。

H/L/U 是**折内证据状态**，不是人格标签。不会为了凑人数降低阈值。全 Core 当前授权版本的描述性人数为 H={class_counts[HIGH]}、L={class_counts[LOW]}、U={class_counts[UNCLASSIFIED]}；W034 original-only 后为 H={original_counts[HIGH]}、L={original_counts[LOW]}、U={original_counts[UNCLASSIFIED]}。这种整体变化本身说明固定类型不稳定；重放使用逐 building 重新计算的标签。

## k=3 无放回混合重放

下表为 `2H+1L` 减去 `1H+2L`；每图枚举现有 worker ID 的全部组合，每人最多一票。质量池外的历史票不会被另一名工人顶替，少于3个合格几何时记为本重放不可评价。这里的“合格”包含独立性与质量门，**不等于真实未提交或标注失败**。

| 分类版本 | 分层 | Δ 三票全合格率 | Δ eligibility-resolved | Δ eligibility-adjusted quality | Δ resolved-only quality |
|---|---|---:|---:|---:|---:|
{chr(10).join(lines)}

C1 主层与 P1 敏感性层都没有显示“增加 H 占比可稳定改善实际交付质量”。P1 的 {qa['evaluation_eligibility_audit']['P1']['current20_rows']} 条历史行中有 {qa['evaluation_eligibility_audit']['P1']['quality_pool_excluded_rows']} 条不进入质量池，其中 {qa['evaluation_eligibility_audit']['P1']['excluded_for_non_independence_rows']} 条涉及 non-independent；P1 的负 eligibility-resolved/adjusted 差与三票合格率差高度一致，但这不是正式因果分解，也不得解释成 H 工人更差或更少交付。pooled resolved-only quality 约有1个百分点的小幅正差，但不足以冻结类型。W034 original-only 是必报敏感性，不用于结果后挑选版本。

`k=3` 时第二个模式不可能同时获得至少2票，supported-multimodal 恒为0是定义上的机械结果，不用于判断“没有多峰”。

## 为什么不能再硬分2–3类

- Core task-adjusted worker quality 与 dense41 Manual worker quality的 task-disjoint 描述性 Spearman 仅 {qa['task_disjoint_descriptive_rank_check']['augmented_authorized']['spearman_rho']:.3f}；两者仍有 building 重叠，不作独立验证或显著性检验解释。
- 跨11个留一 building 折和两个 W034 数据版本始终保持 H 的只有 {qa['crossfit_stability']['stable_H_count']} 人，始终保持 L 的只有 {qa['crossfit_stability']['stable_L_count']} 人；不足以形成可复用的人群类型。
- 若干折的 bootstrap 概率贴近0.80/0.20边界，具体成员和重放点估计必须保持探索性；不为凑人数移动阈值。
- Core 的 peer 与 Q_GT 不是同一维度；peer 若用于定义类别再检验共识，会形成循环。
- Core 的 {qa['structural_audit']['opportunity_count']} 次结构机会中只有 {qa['structural_audit']['worker_caused_failure_count']} 次 worker-caused failure，复发者为 {qa['structural_audit']['worker_with_recurrent_failures_count']} 人，不能据此造出“风险型”。
- 因此现有差异更适合保留为连续、任务依赖的 Q_GT/R_peer/F_struct，而不是固定 worker taxonomy。

## 后续最小方案

如果还要模拟混合人群，可以保留这里的 cross-fitted H/L/U 作为探索性组成分析；若要在论文中主张稳定类型，必须在新 building 结果不可见前冻结 Manual 分类规则，并用新的独立 Manual 任务复核。现有证据不能证明某类人在12–20人处收敛。

本审计不修改正式 worker profile、eligibility、routing、SAP 或方法合同。
"""


def run(output_dir: Path = DEFAULT_OUT) -> dict[str, Any]:
    inputs = historical.load_inputs()
    pools, pair_maps = historical.build_quality_candidates(inputs)
    evaluation_tasks = set(pools)
    evaluation_buildings = sorted({task.split("_", 1)[0] for task in evaluation_tasks})
    fold_groups: dict[tuple[str, str], dict[str, set[str]]] = {}
    assignments: list[dict[str, Any]] = []
    full_profiles: list[dict[str, Any]] = []
    training_qa: dict[str, Any] = {}
    variant_effects: dict[str, dict[str, float]] = {}

    for variant, path in CORE_VARIANTS.items():
        core = _load_core(path)
        if {row["base_task_id"] for row in core} & evaluation_tasks:
            raise AssertionError("classification and evaluation tasks overlap")
        full, full_meta = classify_rows(core, seed=_seed(variant, "full"))
        variant_effects[variant] = fit_worker_task_effects(core)
        for row in full:
            full_profiles.append({"classification_variant": variant, **row})
        training_qa[variant] = {
            "source": historical.display_path(path),
            "sha256": historical.sha256(path),
            "eligible_row_count": len(core),
            "eligible_task_count": len({row["base_task_id"] for row in core}),
            "eligible_building_count": len({row["building_id"] for row in core}),
            "full_fit": full_meta,
        }
        raw_current20 = [
            row
            for row in historical.read_csv(path)
            if row.get("dataset_group") == "Calibration_core"
            and row.get("condition") == "manual"
            and str(row.get("worker_id")) in CURRENT20
        ]
        training_qa[variant]["raw_current20_row_count"] = len(raw_current20)
        for building in evaluation_buildings:
            training = [row for row in core if row["building_id"] != building]
            classified, meta = classify_rows(
                training,
                seed=_seed(variant, building),
            )
            groups = {
                label: {row["worker_id"] for row in classified if row["evidence_stratum"] == label}
                for label in (HIGH, LOW, UNCLASSIFIED)
            }
            fold_groups[(variant, building)] = groups
            for row in classified:
                assignments.append(
                    {
                        "classification_variant": variant,
                        "evaluation_building": building,
                        "evaluation_building_excluded_from_training": True,
                        **row,
                        **meta,
                    }
                )

    mixture = _mixture_rows(pools, pair_maps, fold_groups)
    contrasts = _contrast_rows(mixture)
    task_results = mixture + contrasts
    summary = replay.summarize_replay(task_results, metrics=METRICS)

    evaluation_rows = [candidate for candidates in pools.values() for candidate in candidates if str(candidate["worker_id"]) in CURRENT20]
    evaluation_effects = fit_worker_task_effects(
        [
            {
                "worker_id": str(row["worker_id"]),
                "base_task_id": row["base_task_id"],
                "building_id": row["base_task_id"].split("_", 1)[0],
                "quality": row["quality"],
            }
            for row in evaluation_rows
        ]
    )
    rank_validation = {}
    for variant, effects in variant_effects.items():
        statistic = spearmanr(
            [effects[worker] for worker in CURRENT20],
            [evaluation_effects[worker] for worker in CURRENT20],
        )
        rank_validation[variant] = {
            "spearman_rho": float(statistic.statistic),
            "naive_unclustered_p_value_not_inferential": float(statistic.pvalue),
            "worker_count": len(CURRENT20),
            "task_disjoint": True,
            "building_disjoint": False,
        }

    augmented_raw = [
        row
        for row in historical.read_csv(CORE_VARIANTS["augmented_authorized"])
        if row.get("dataset_group") == "Calibration_core"
        and row.get("condition") == "manual"
        and str(row.get("worker_id")) in CURRENT20
    ]
    structural_audit = structural_failure_audit(
        historical.read_csv(STRUCTURAL_SOURCE),
        {str(row["base_task_id"]) for row in augmented_raw},
    )
    structural_audit.update(
        {
            "source": historical.display_path(STRUCTURAL_SOURCE),
            "sha256": historical.sha256(STRUCTURAL_SOURCE),
        }
    )
    assignments_by_worker = {
        worker: [row for row in assignments if row["worker_id"] == worker]
        for worker in CURRENT20
    }
    stable_by_stratum = {
        stratum: [
            worker
            for worker, rows in assignments_by_worker.items()
            if rows and all(row["evidence_stratum"] == stratum for row in rows)
        ]
        for stratum in (HIGH, LOW, UNCLASSIFIED)
    }
    short_stratum = {HIGH: "H", LOW: "L", UNCLASSIFIED: "U"}
    full_by_key = {
        (row["classification_variant"], row["worker_id"]): row for row in full_profiles
    }
    simple_worker_rows = []
    for worker in CURRENT20:
        primary = full_by_key[("augmented_authorized", worker)]
        sensitivity = full_by_key[("w034_original_only", worker)]
        primary_folds = [
            row
            for row in assignments_by_worker[worker]
            if row["classification_variant"] == "augmented_authorized"
        ]
        all_fold_strata = {row["evidence_stratum"] for row in assignments_by_worker[worker]}
        simple_worker_rows.append(
            {
                "worker_id": worker,
                "Manual有效标注数": primary["quality_task_support"],
                "Manual覆盖building数": primary["quality_building_support"],
                "难度校正质量效应": round(float(primary["worker_effect_centered"]), 6),
                "高于20人均值概率": round(
                    float(primary["probability_effect_positive_building_bootstrap"]), 3
                ),
                "当前分组": short_stratum[primary["evidence_stratum"]],
                "留一building_H次数": sum(row["evidence_stratum"] == HIGH for row in primary_folds),
                "留一building_U次数": sum(
                    row["evidence_stratum"] == UNCLASSIFIED for row in primary_folds
                ),
                "留一building_L次数": sum(row["evidence_stratum"] == LOW for row in primary_folds),
                "W034_original_only分组": short_stratum[sensitivity["evidence_stratum"]],
                "跨11个building及两版本稳定类别": (
                    short_stratum[next(iter(all_fold_strata))]
                    if len(all_fold_strata) == 1
                    else "不稳定"
                ),
            }
        )
    assert len(simple_worker_rows) == len(CURRENT20)
    p1_evaluation_tasks = {
        task for task, candidates in pools.items() if candidates[0]["stage"] == "P1"
    }
    p1_evaluation_rows = [
        row
        for row in inputs["p1_scores"]
        if row["base_task_id"] in p1_evaluation_tasks
        and str(row.get("worker_id")) in CURRENT20
    ]
    p1_excluded = [
        row
        for row in p1_evaluation_rows
        if not historical.truth(row.get("included_in_p1_geometry_profile"))
    ]
    c1_evaluation_rows = [
        row for row in inputs["c1_quality"] if str(row.get("worker_id")) in CURRENT20
    ]
    evaluation_eligibility_audit = {
        "P1": {
            "current20_rows": len(p1_evaluation_rows),
            "quality_pool_eligible_rows": len(p1_evaluation_rows) - len(p1_excluded),
            "quality_pool_excluded_rows": len(p1_excluded),
            "excluded_for_non_independence_rows": sum(
                str(row.get("independence_status", "")).startswith("non_independent")
                for row in p1_excluded
            ),
            "excluded_while_independent_rows": sum(
                row.get("independence_status") == "independent" for row in p1_excluded
            ),
        },
        "C1": {
            "current20_rows": len(c1_evaluation_rows),
            "quality_pool_eligible_rows": sum(
                historical.truth(row.get("gt_primary_analysis_eligible"))
                for row in c1_evaluation_rows
            ),
            "quality_pool_excluded_rows": sum(
                not historical.truth(row.get("gt_primary_analysis_eligible"))
                for row in c1_evaluation_rows
            ),
        },
    }
    source_paths = [
        historical.P1_IMPORT,
        historical.P1_CLOSEOUT / "final_gold_records_v2_p1_closeout_corrected.jsonl",
        historical.P1_CLOSEOUT / "prescreen_canonical_annotations.csv",
        inputs["p1_scores_path"],
        C1_AUDIT / "c1_gt_quality_analysis.csv",
        C1_AUDIT / "c1_task_outcome_reference.csv",
        C1_AUDIT / "geometry_pairwise_similarity_C1.csv",
        STRUCTURAL_SOURCE,
        historical.HIGH_DENSITY,
        historical.METHOD_CONTRACT,
    ]
    qa = {
        "schema_version": "worker_manual_strata_audit_v1",
        "status": "discrete_worker_taxonomy_not_supported",
        "classification_source": "C1_Calibration_core_Manual_only",
        "evaluation_source": "dense41_Manual_reference_ready",
        "current_worker_count": len(CURRENT20),
        "classification_bootstraps_per_fit": CLASSIFICATION_BOOTSTRAPS,
        "classification_bootstrap_method": (
            "building_then_task_conditioned_on_two_outer_clusters_"
            "complete_worker_support_and_connected_graph"
        ),
        "classification_probability_threshold": EVIDENCE_PROBABILITY,
        "augmented_training": training_qa["augmented_authorized"],
        "training_variants": training_qa,
        "evaluation_task_count": len(evaluation_tasks),
        "evaluation_building_count": len(evaluation_buildings),
        "classification_evaluation_base_task_overlap_count": 0,
        "task_disjoint_descriptive_rank_check": rank_validation,
        "evaluation_eligibility_audit": evaluation_eligibility_audit,
        "crossfit_stability": {
            "evaluation_building_count": len(evaluation_buildings),
            "training_variant_count": len(CORE_VARIANTS),
            "assignments_required_per_worker": len(evaluation_buildings) * len(CORE_VARIANTS),
            "stable_H_workers": stable_by_stratum[HIGH],
            "stable_H_count": len(stable_by_stratum[HIGH]),
            "stable_L_workers": stable_by_stratum[LOW],
            "stable_L_count": len(stable_by_stratum[LOW]),
            "stable_U_workers": stable_by_stratum[UNCLASSIFIED],
            "stable_U_count": len(stable_by_stratum[UNCLASSIFIED]),
        },
        "structural_audit": structural_audit,
        "replay": {
            "k": 3,
            "scenarios": ["2H+1L", "1H+2L"],
            "sampling": "exact_assigned_worker_compositions_without_replacement",
            "task_result_row_count": len(task_results),
            "summary_row_count": len(summary),
            "unusable_selected_worker_is_not_replaced": True,
            "aggregator_is_gt_blind": True,
            "building_bootstrap_replicates": replay.BOOTSTRAP_REPLICATES,
            "building_bootstrap_seed_base": replay.SEED,
            "quality_pool_absence_interpretation": "eligibility_adjusted_not_actual_non_delivery",
            "supported_multimodal_at_k3_interpretation": "mechanically_zero_under_two_vote_secondary_support_rule",
        },
        "source_files": [
            {"path": historical.display_path(path), "sha256": historical.sha256(path)}
            for path in source_paths
        ],
        "formal_contract_changed": False,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    historical.write_csv(output_dir / "manual_core_full_profiles.csv", full_profiles)
    historical.write_csv(output_dir / "manual_worker_calculation_simple.csv", simple_worker_rows)
    historical.write_csv(output_dir / "manual_crossfit_assignments.csv", assignments)
    historical.write_csv(output_dir / "manual_crossfit_mixture_task_results.csv", task_results)
    historical.write_csv(output_dir / "manual_crossfit_mixture_summary.csv", summary)
    historical.write_json(output_dir / "QA.json", qa)
    (output_dir / "REPORT_ZH.md").write_text(_build_report(qa, summary, full_profiles), encoding="utf-8")
    return qa


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    print(json.dumps(run(args.output_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
