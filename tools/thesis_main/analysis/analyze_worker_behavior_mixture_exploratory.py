"""Explore one narrow worker behavior stratum and finite-roster mixtures.

This is development-only replay.  It does not create a formal worker taxonomy,
change worker eligibility, or modify the Paper A method contract.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from itertools import combinations, product
from pathlib import Path
from statistics import mean
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from tools.thesis_main.analysis import materialize_historical_uncertainty_k_curves_20260829 as historical


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUT = (
    ROOT
    / "analysis_results"
    / "worker_behavior_mixture_exploratory_20260904_v1"
)
PROPOSAL_ROWS = (
    ROOT
    / "analysis_results"
    / "uncertainty_threshold_anchoring_worker_types_20260823"
    / "PROPOSAL_RESPONSE_ROWS_FOR_WORKER_ANALYSIS.csv"
)
SEED = 20260904
POSTERIOR_DRAWS = 200_000
BOOTSTRAP_REPLICATES = 4_000

A = "A_selective_corrector_u095"
C = "C_overmodifier_u095_sensitivity"
U = "U_unclassified"
NON_A = "B_non_A_comparison_pool"


def classify_behavior_counts(
    *, fixes: int, wrong_n: int, harms: int, correct_n: int
) -> str:
    """Apply the fixed 18-task count rule, allowing an abstention class."""

    if min(wrong_n, correct_n) <= 0:
        return U
    if fixes >= 3 and harms <= 1:
        return A
    if harms >= 3 and fixes <= 1:
        return C
    return U


def _posterior_fix_exceeds_harm(
    *, fixes: int, wrong_n: int, harms: int, correct_n: int, seed: int
) -> float:
    rng = np.random.default_rng(seed)
    fix_draws = rng.beta(fixes + 0.5, wrong_n - fixes + 0.5, POSTERIOR_DRAWS)
    harm_draws = rng.beta(harms + 0.5, correct_n - harms + 0.5, POSTERIOR_DRAWS)
    return float(np.mean(fix_draws > harm_draws))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _initial_final(row: Mapping[str, Any]) -> tuple[float, float]:
    initial = historical.number(row.get("U_initial"))
    final = historical.number(row.get("U_final"))
    if initial is None or final is None:
        raise AssertionError("P1 classification row is missing U_initial/U_final")
    return initial, final


def _counts(rows: Sequence[Mapping[str, Any]], cutoff: float = 0.95) -> tuple[int, int, int, int]:
    values = [_initial_final(row) for row in rows]
    correct = [(initial, final) for initial, final in values if initial >= cutoff]
    wrong = [(initial, final) for initial, final in values if initial < cutoff]
    harms = sum(final < cutoff for _, final in correct)
    fixes = sum(final >= cutoff for _, final in wrong)
    return fixes, len(wrong), harms, len(correct)


def build_worker_strata() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = [
        row
        for row in historical.read_csv(PROPOSAL_ROWS)
        if row.get("stage") == "P1"
        and historical.truth(row.get("current20_bool"))
        and historical.truth(row.get("analysis_eligible_bool"))
        and historical.truth(row.get("proposal_correctness_observed_095"))
    ]
    by_worker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_worker[str(row["worker_id"])].append(row)

    assert len(rows) == 360
    assert len(by_worker) == 20
    assert all(len(items) == 18 for items in by_worker.values())
    assert all(len({row["base_task_id"] for row in items}) == 18 for items in by_worker.values())

    output: list[dict[str, Any]] = []
    for worker_id, items in sorted(by_worker.items(), key=lambda item: int(item[0])):
        fixes, wrong_n, harms, correct_n = _counts(items)
        assert (wrong_n, correct_n) == (7, 11)
        label = classify_behavior_counts(
            fixes=fixes, wrong_n=wrong_n, harms=harms, correct_n=correct_n
        )
        loto_labels = []
        for omitted in sorted({row["base_task_id"] for row in items}):
            subset = [row for row in items if row["base_task_id"] != omitted]
            sub_fixes, sub_wrong_n, sub_harms, sub_correct_n = _counts(subset)
            loto_labels.append(
                classify_behavior_counts(
                    fixes=sub_fixes,
                    wrong_n=sub_wrong_n,
                    harms=sub_harms,
                    correct_n=sub_correct_n,
                )
            )
        output.append(
            {
                "worker_id": worker_id,
                "classification_stage": "P1",
                "classification_task_count": len(items),
                "classification_building_count": len({row["building_id"] for row in items}),
                "u_threshold": 0.95,
                "correct_proposal_n": correct_n,
                "correct_proposal_harm_count": harms,
                "correct_proposal_harm_rate": harms / correct_n,
                "wrong_proposal_n": wrong_n,
                "wrong_proposal_fix_count": fixes,
                "wrong_proposal_fix_rate": fixes / wrong_n,
                "posterior_p_fix_rate_gt_harm_rate": _posterior_fix_exceeds_harm(
                    fixes=fixes,
                    wrong_n=wrong_n,
                    harms=harms,
                    correct_n=correct_n,
                    seed=SEED + int(worker_id),
                ),
                "sensitivity_stratum": label,
                "primary_stratum": A if label == A else NON_A,
                "leave_one_task_same_stratum_count": sum(item == label for item in loto_labels),
                "leave_one_task_total": len(loto_labels),
                "interpretation": {
                    A: "U=.95标准下的选择性纠错候选；不是一般意义的good worker",
                    C: "U=.95标准下的过度修改倾向；仅作敏感性，不是sloppy人格",
                    U: "证据不足或混合反应；不视为一种机制类型",
                }[label],
            }
        )

    counts = Counter(row["sensitivity_stratum"] for row in output)
    assert counts == Counter({A: 9, C: 5, U: 6})

    cutoff_sensitivity: list[dict[str, Any]] = []
    for cutoff in (0.925, 0.93, 0.95, 0.97):
        labels: dict[str, list[str]] = defaultdict(list)
        for worker_id, items in by_worker.items():
            fixes, wrong_n, harms, correct_n = _counts(items, cutoff=cutoff)
            labels[
                classify_behavior_counts(
                    fixes=fixes, wrong_n=wrong_n, harms=harms, correct_n=correct_n
                )
            ].append(worker_id)
        cutoff_sensitivity.append(
            {
                "u_threshold": cutoff,
                "A_count": len(labels[A]),
                "C_count": len(labels[C]),
                "U_count": len(labels[U]),
                "A_worker_ids": sorted(labels[A], key=int),
                "C_worker_ids": sorted(labels[C], key=int),
                "U_worker_ids": sorted(labels[U], key=int),
            }
        )

    metadata = {
        "classification_row_count": len(rows),
        "classification_task_count": len({row["base_task_id"] for row in rows}),
        "classification_building_count": len({row["building_id"] for row in rows}),
        "classification_task_ids": sorted({row["base_task_id"] for row in rows}),
        "classification_building_ids": sorted({row["building_id"] for row in rows}),
        "class_counts": dict(counts),
        "cutoff_sensitivity": cutoff_sensitivity,
    }
    return output, metadata


def _pooled_target(
    candidates: Sequence[Mapping[str, Any]],
    task: str,
    pair_map: Mapping[tuple[str, str], Mapping[str, Any]],
) -> tuple[bool, str]:
    cluster = historical._cluster(candidates, task, pair_map)
    resolved = str(cluster.get("task_crowd_structure_status")) in historical.RESOLVED_STATUSES
    selected = historical._selected(candidates, cluster) if resolved else None
    return resolved, historical.candidate_id(selected or {})


def _evaluate_sample(
    sample: Sequence[Mapping[str, Any]],
    *,
    task: str,
    pair_map: Mapping[tuple[str, str], Mapping[str, Any]],
    target_resolved: bool,
    target_id: str,
) -> dict[str, float | None]:
    cluster = historical._cluster(sample, task, pair_map)
    status = str(cluster.get("task_crowd_structure_status"))
    resolved = status in historical.RESOLVED_STATUSES
    selected = historical._selected(sample, cluster) if resolved else None
    selected_id = historical.candidate_id(selected or {})
    quality = historical.number(selected.get("quality")) if selected else None
    recovered: float | None = None
    if target_resolved:
        compatible = False
        if resolved:
            compatible, _ = historical._compatible(selected_id, target_id, pair_map)
        recovered = float(compatible is True)
    return {
        "resolved": float(resolved),
        "supported_multimodal": float(status == "supported_multimodal"),
        "not_evaluable": float(status == "not_evaluable"),
        "resolved_quality": quality,
        "delivery_adjusted_quality": quality if quality is not None else 0.0,
        "pooled_full_output_recovered": recovered,
    }


def _mean_present(values: Iterable[float | None]) -> float | None:
    usable = [float(value) for value in values if value is not None]
    return mean(usable) if usable else None


def replay_subgroups_exact(
    pools: Mapping[str, Sequence[Mapping[str, Any]]],
    pair_maps: Mapping[str, Mapping[tuple[str, str], Mapping[str, Any]]],
    worker_sets: Mapping[str, set[str]],
    current20: set[str],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for task, all_candidates in sorted(pools.items()):
        pair_map = pair_maps[task]
        pooled = [row for row in all_candidates if str(row["worker_id"]) in current20]
        target_resolved, target_id = _pooled_target(pooled, task, pair_map)
        for population, worker_ids in worker_sets.items():
            candidates = [row for row in all_candidates if str(row["worker_id"]) in worker_ids]
            for k in range(3, min(6, len(candidates)) + 1):
                metrics = [
                    _evaluate_sample(
                        sample,
                        task=task,
                        pair_map=pair_map,
                        target_resolved=target_resolved,
                        target_id=target_id,
                    )
                    for sample in combinations(candidates, k)
                ]
                output.append(
                    {
                        "analysis_kind": "subgroup_curve_exact",
                        "population_or_scenario": population,
                        "base_task_id": task,
                        "building_id": task.split("_", 1)[0],
                        "stage": candidates[0]["stage"],
                        "reference_regime": "public_frozen_GT" if candidates[0]["stage"] == "C1" else "expert_hard_single_reference",
                        "k_total": k,
                        "n_A": "",
                        "n_B": "",
                        "available_population_n": len(candidates),
                        "available_A_n": "",
                        "available_B_n": "",
                        "sampling_method": "exact_all_worker_subsets_without_replacement",
                        "samples_or_replicates": len(metrics),
                        "resolved_rate": mean(item["resolved"] for item in metrics),
                        "supported_multimodal_rate": mean(
                            item["supported_multimodal"] for item in metrics
                        ),
                        "not_evaluable_rate": mean(item["not_evaluable"] for item in metrics),
                        "resolved_only_quality": _mean_present(
                            item["resolved_quality"] for item in metrics
                        ),
                        "delivery_adjusted_quality": mean(
                            item["delivery_adjusted_quality"] for item in metrics
                        ),
                        "pooled_full_output_recovery_rate": _mean_present(
                            item["pooled_full_output_recovered"] for item in metrics
                        ),
                        "pooled_full_target_resolved": target_resolved,
                        "mechanical_population_full_roster_endpoint": k == len(candidates),
                    }
                )
    return output


def replay_mixtures(
    pools: Mapping[str, Sequence[Mapping[str, Any]]],
    pair_maps: Mapping[str, Mapping[tuple[str, str], Mapping[str, Any]]],
    *,
    a_workers: set[str],
    b_pools: Mapping[str, set[str]],
    current20: set[str],
) -> list[dict[str, Any]]:
    scenarios = ((4, 2), (3, 3), (2, 4))
    output: list[dict[str, Any]] = []
    for task, all_candidates in sorted(pools.items()):
        pair_map = pair_maps[task]
        pooled = [row for row in all_candidates if str(row["worker_id"]) in current20]
        target_resolved, target_id = _pooled_target(pooled, task, pair_map)
        a_candidates = [row for row in all_candidates if str(row["worker_id"]) in a_workers]
        for pool_name, b_workers in b_pools.items():
            b_candidates = [row for row in all_candidates if str(row["worker_id"]) in b_workers]
            assert len(a_candidates) >= 4 and len(b_candidates) >= 4
            for n_a, n_b in scenarios:
                metrics = [
                    _evaluate_sample(
                        list(a_sample) + list(b_sample),
                        task=task,
                        pair_map=pair_map,
                        target_resolved=target_resolved,
                        target_id=target_id,
                    )
                    for a_sample, b_sample in product(
                        combinations(a_candidates, n_a), combinations(b_candidates, n_b)
                    )
                ]
                output.append(
                    {
                        "analysis_kind": "mixture_k6_exact",
                        "population_or_scenario": f"{pool_name}|{n_a}A+{n_b}B",
                        "base_task_id": task,
                        "building_id": task.split("_", 1)[0],
                        "stage": all_candidates[0]["stage"],
                        "reference_regime": "public_frozen_GT" if all_candidates[0]["stage"] == "C1" else "expert_hard_single_reference",
                        "k_total": n_a + n_b,
                        "n_A": n_a,
                        "n_B": n_b,
                        "available_population_n": "",
                        "available_A_n": len(a_candidates),
                        "available_B_n": len(b_candidates),
                        "sampling_method": "exact_all_worker_compositions_without_replacement",
                        "samples_or_replicates": len(metrics),
                        "resolved_rate": mean(item["resolved"] for item in metrics),
                        "supported_multimodal_rate": mean(
                            item["supported_multimodal"] for item in metrics
                        ),
                        "not_evaluable_rate": mean(item["not_evaluable"] for item in metrics),
                        "resolved_only_quality": _mean_present(
                            item["resolved_quality"] for item in metrics
                        ),
                        "delivery_adjusted_quality": mean(
                            item["delivery_adjusted_quality"] for item in metrics
                        ),
                        "pooled_full_output_recovery_rate": _mean_present(
                            item["pooled_full_output_recovered"] for item in metrics
                        ),
                        "pooled_full_target_resolved": target_resolved,
                        "mechanical_population_full_roster_endpoint": False,
                    }
                )
    return output


def build_paired_contrasts(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    metrics = (
        "resolved_rate",
        "supported_multimodal_rate",
        "not_evaluable_rate",
        "resolved_only_quality",
        "delivery_adjusted_quality",
        "pooled_full_output_recovery_rate",
    )
    specs = [
        ("subgroup_curve_exact", A, NON_A, "subgroup_contrast_exact", "A_minus_non_A"),
        ("subgroup_curve_exact", A, C, "subgroup_contrast_exact", "A_minus_C"),
        (
            "mixture_k6_exact",
            "primary_A_vs_non_A|4A+2B",
            "primary_A_vs_non_A|2A+4B",
            "mixture_extreme_contrast_exact",
            "primary_A_vs_non_A|4A2B_minus_2A4B",
        ),
        (
            "mixture_k6_exact",
            "sensitivity_A_vs_C|4A+2B",
            "sensitivity_A_vs_C|2A+4B",
            "mixture_extreme_contrast_exact",
            "sensitivity_A_vs_C|4A2B_minus_2A4B",
        ),
    ]
    output: list[dict[str, Any]] = []
    for source_kind, left_name, right_name, output_kind, output_name in specs:
        left = {
            (row["base_task_id"], int(row["k_total"])): row
            for row in rows
            if row["analysis_kind"] == source_kind
            and row["population_or_scenario"] == left_name
        }
        right = {
            (row["base_task_id"], int(row["k_total"])): row
            for row in rows
            if row["analysis_kind"] == source_kind
            and row["population_or_scenario"] == right_name
        }
        for key in sorted(set(left) & set(right)):
            left_row, right_row = left[key], right[key]
            row = {
                "analysis_kind": output_kind,
                "population_or_scenario": output_name,
                "base_task_id": left_row["base_task_id"],
                "building_id": left_row["building_id"],
                "stage": left_row["stage"],
                "reference_regime": left_row["reference_regime"],
                "k_total": left_row["k_total"],
                "n_A": "",
                "n_B": "",
                "available_population_n": "",
                "available_A_n": "",
                "available_B_n": "",
                "sampling_method": "paired_task_difference_left_minus_right",
                "samples_or_replicates": "",
                "pooled_full_target_resolved": left_row["pooled_full_target_resolved"],
                "mechanical_population_full_roster_endpoint": False,
            }
            for metric in metrics:
                left_value = historical.number(left_row.get(metric))
                right_value = historical.number(right_row.get(metric))
                row[metric] = (
                    left_value - right_value
                    if left_value is not None and right_value is not None
                    else None
                )
            output.append(row)
    return output


def _analysis_strata(rows: Sequence[Mapping[str, Any]]) -> list[tuple[str, list[Mapping[str, Any]]]]:
    return [
        ("C1_primary_12", [row for row in rows if row["stage"] == "C1"]),
        ("P1_reference_sensitivity_29", [row for row in rows if row["stage"] == "P1"]),
        ("pooled_reference_sensitivity_41", list(rows)),
    ]


def summarize_replay(
    rows: Sequence[Mapping[str, Any]],
    *,
    metrics: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    metrics = metrics or (
        "resolved_rate",
        "supported_multimodal_rate",
        "resolved_only_quality",
        "delivery_adjusted_quality",
        "pooled_full_output_recovery_rate",
    )
    output: list[dict[str, Any]] = []
    keys = sorted(
        {
            (str(row["analysis_kind"]), str(row["population_or_scenario"]), int(row["k_total"]))
            for row in rows
        }
    )
    for analysis_kind, population, k in keys:
        matched = [
            row
            for row in rows
            if row["analysis_kind"] == analysis_kind
            and row["population_or_scenario"] == population
            and int(row["k_total"]) == k
        ]
        for stratum, subset in _analysis_strata(matched):
            if not subset:
                continue
            for metric_index, metric in enumerate(metrics):
                values = [historical.number(row.get(metric)) for row in subset]
                values = [value for value in values if value is not None]
                lower, upper = historical.building_cluster_bootstrap_ci(
                    subset,
                    value_field=metric,
                    replicates=BOOTSTRAP_REPLICATES,
                    seed=SEED + len(output) + metric_index,
                )
                output.append(
                    {
                        "analysis_kind": analysis_kind,
                        "population_or_scenario": population,
                        "analysis_stratum": stratum,
                        "k_total": k,
                        "metric": metric,
                        "estimate_task_equal": mean(values) if values else None,
                        "ci95_lower_building_bootstrap": lower,
                        "ci95_upper_building_bootstrap": upper,
                        "task_count": len(subset),
                        "task_count_with_metric": len(values),
                        "building_count": len({row["building_id"] for row in subset}),
                    }
                )
    return output


def _summary_value(
    summary: Sequence[Mapping[str, Any]],
    *,
    analysis_kind: str,
    population: str,
    stratum: str,
    k: int,
    metric: str,
) -> Mapping[str, Any]:
    matches = [
        row
        for row in summary
        if row["analysis_kind"] == analysis_kind
        and row["population_or_scenario"] == population
        and row["analysis_stratum"] == stratum
        and int(row["k_total"]) == k
        and row["metric"] == metric
    ]
    if len(matches) != 1:
        raise AssertionError((analysis_kind, population, stratum, k, metric, len(matches)))
    return matches[0]


def _fmt(row: Mapping[str, Any]) -> str:
    estimate = historical.number(row.get("estimate_task_equal"))
    lower = historical.number(row.get("ci95_lower_building_bootstrap"))
    upper = historical.number(row.get("ci95_upper_building_bootstrap"))
    if estimate is None:
        return "NA"
    return f"{estimate:.3f} [{lower:.3f}, {upper:.3f}]" if lower is not None and upper is not None else f"{estimate:.3f}"


def build_report(
    workers: Sequence[Mapping[str, Any]],
    metadata: Mapping[str, Any],
    summary: Sequence[Mapping[str, Any]],
    qa: Mapping[str, Any],
) -> str:
    counts = Counter(row["sensitivity_stratum"] for row in workers)
    a_ids = [row["worker_id"] for row in workers if row["sensitivity_stratum"] == A]
    c_ids = [row["worker_id"] for row in workers if row["sensitivity_stratum"] == C]
    u_ids = [row["worker_id"] for row in workers if row["sensitivity_stratum"] == U]
    a_loto = [int(row["leave_one_task_same_stratum_count"]) for row in workers if row["sensitivity_stratum"] == A]
    c_loto = [int(row["leave_one_task_same_stratum_count"]) for row in workers if row["sensitivity_stratum"] == C]
    subgroup_lines = []
    for population in (A, NON_A, C):
        for k in (3, 4, 5):
            row = _summary_value(
                summary,
                analysis_kind="subgroup_curve_exact",
                population=population,
                stratum="pooled_reference_sensitivity_41",
                k=k,
                metric="delivery_adjusted_quality",
            )
            subgroup_lines.append(
                f"| {population} | {k} | {row['task_count']} | {_fmt(row)} |"
            )

    mixture_lines = []
    for pool_name in ("primary_A_vs_non_A", "sensitivity_A_vs_C"):
        for n_a, n_b in ((4, 2), (3, 3), (2, 4)):
            population = f"{pool_name}|{n_a}A+{n_b}B"
            delivery = _summary_value(
                summary,
                analysis_kind="mixture_k6_exact",
                population=population,
                stratum="pooled_reference_sensitivity_41",
                k=6,
                metric="delivery_adjusted_quality",
            )
            resolved = _summary_value(
                summary,
                analysis_kind="mixture_k6_exact",
                population=population,
                stratum="pooled_reference_sensitivity_41",
                k=6,
                metric="resolved_rate",
            )
            mixture_lines.append(
                f"| {pool_name} | {n_a}A+{n_b}B | {_fmt(delivery)} | {_fmt(resolved)} |"
            )

    subgroup_contrast_lines = []
    for contrast in ("A_minus_non_A", "A_minus_C"):
        for k in (3, 4, 5):
            delivery = _summary_value(
                summary,
                analysis_kind="subgroup_contrast_exact",
                population=contrast,
                stratum="pooled_reference_sensitivity_41",
                k=k,
                metric="delivery_adjusted_quality",
            )
            quality = _summary_value(
                summary,
                analysis_kind="subgroup_contrast_exact",
                population=contrast,
                stratum="pooled_reference_sensitivity_41",
                k=k,
                metric="resolved_only_quality",
            )
            subgroup_contrast_lines.append(
                f"| {contrast} | {k} | {delivery['task_count']} | {_fmt(delivery)} | {_fmt(quality)} |"
            )

    mixture_contrast_lines = []
    for pool_name in ("primary_A_vs_non_A", "sensitivity_A_vs_C"):
        contrast = f"{pool_name}|4A2B_minus_2A4B"
        for stratum in (
            "C1_primary_12",
            "P1_reference_sensitivity_29",
            "pooled_reference_sensitivity_41",
        ):
            delivery = _summary_value(
                summary,
                analysis_kind="mixture_extreme_contrast_exact",
                population=contrast,
                stratum=stratum,
                k=6,
                metric="delivery_adjusted_quality",
            )
            resolved = _summary_value(
                summary,
                analysis_kind="mixture_extreme_contrast_exact",
                population=contrast,
                stratum=stratum,
                k=6,
                metric="resolved_rate",
            )
            quality = _summary_value(
                summary,
                analysis_kind="mixture_extreme_contrast_exact",
                population=contrast,
                stratum=stratum,
                k=6,
                metric="resolved_only_quality",
            )
            mixture_contrast_lines.append(
                f"| {pool_name} | {stratum} | {_fmt(delivery)} | {_fmt(resolved)} | {_fmt(quality)} |"
            )

    sensitivity_lines = [
        f"| {item['u_threshold']:.3f} | {item['A_count']} | {item['C_count']} | {item['U_count']} |"
        for item in metadata["cutoff_sensitivity"]
    ]
    primary_pooled_delivery = _summary_value(
        summary,
        analysis_kind="mixture_extreme_contrast_exact",
        population="primary_A_vs_non_A|4A2B_minus_2A4B",
        stratum="pooled_reference_sensitivity_41",
        k=6,
        metric="delivery_adjusted_quality",
    )
    primary_pooled_quality = _summary_value(
        summary,
        analysis_kind="mixture_extreme_contrast_exact",
        population="primary_A_vs_non_A|4A2B_minus_2A4B",
        stratum="pooled_reference_sensitivity_41",
        k=6,
        metric="resolved_only_quality",
    )
    primary_p1_delivery = _summary_value(
        summary,
        analysis_kind="mixture_extreme_contrast_exact",
        population="primary_A_vs_non_A|4A2B_minus_2A4B",
        stratum="P1_reference_sensitivity_29",
        k=6,
        metric="delivery_adjusted_quality",
    )
    return f"""# Worker 行为分层与混合重放：探索性报告

## 结论先行

当前数据**不支持把 20 人宣布为稳定的 good/sloppy 或 2--3 种自然类型**。但在固定 6 人的事后重组中，把 A 从 2 人提高到 4 人，与 delivery-adjusted quality 提高 {_fmt(primary_pooled_delivery)}、resolved-only quality 提高 {_fmt(primary_pooled_quality)} 同向关联。这个信号偏小且并不完整：P1 单层的 delivery-adjusted 差值为 {_fmt(primary_p1_delivery)}，区间仍跨 0。

因此可以保留一个明确但窄的候选问题：在既有 `U=0.95` 交付标准下，是否存在一批能修正错误 proposal、同时较少破坏正确 proposal 的标注者；以及提高这批人在组合中的比例是否改变聚合表现。它还不是稳定 worker taxonomy。

主分组只有两层：A（按 `U=0.95` 规则识别的选择性纠错候选）与非 A 比较池。第三层 C（过度修改倾向）只作机制敏感性；另有 U 为拒绝分类，不是第三种人格类型。

## 分类规则与人数

- 分类数据：P1 Semi 的 18 张共同校准图，20 人每人恰好 11 个正确 proposal 与 7 个错误 proposal。
- A：错误 proposal 至少修正 3/7，且正确 proposal 最多破坏 1/11。
- C：正确 proposal 至少破坏 3/11，且错误 proposal 最多修正 1/7；仅作敏感性。
- U：其余反应，保持未分类。
- 分类图与 Manual 评价图的 base task 重叠为 0；building 仍重叠 {qa['classification_evaluation_building_overlap_count']} 个，所以区间按 building 聚类。

人数：A={counts[A]}、C={counts[C]}、U={counts[U]}；主比较为 A={counts[A]} 与非 A={counts[C] + counts[U]}。

- A：{', '.join(map(str, a_ids))}
- C：{', '.join(map(str, c_ids))}
- U：{', '.join(map(str, u_ids))}

## 防止重演旧分类失败的检查

1. 不再搜索聚类数，也不使用旧 10 维聚类；旧结果的 silhouette≈0.201、split-half ARI 中位数≈0.120，不足以支持自然类型。
2. 分类只看 P1 proposal-response；Manual 质量完全留作评价，避免用同一结果既分组又证明分组有效。
3. 允许 U 拒绝分类，不把所有人强塞进三类。
4. 留一任务复算中，A 保持原组 {min(a_loto)}--{max(a_loto)}/18 次，C 保持 {min(c_loto)}--{max(c_loto)}/18 次；边界成员仍需前瞻复核。
5. 类型名称绑定 `U=0.95`。阈值敏感性如下，说明它不是跨定义稳定人格；其他阈值也会改变正确/错误题的数量，因此仅作定义敏感性，不是同支持正式比较：

| U 阈值 | A 人数 | C 人数 | U 人数 |
|---:|---:|---:|---:|
{chr(10).join(sensitivity_lines)}

因此，后续若采用这一路线，必须先冻结 `U=0.95` 的业务/交付含义；不能看过 Manual 结果再换阈值。

## 子群自身曲线（41 图 pooled 仅作敏感性）

以下是 GT-blind 聚合的 delivery-adjusted quality，区间为 building-cluster bootstrap。C1 12 图和 P1 29 图的分层结果在 `replay_summary.csv` 中，不能只引用 pooled 值。

| 人群 | k | 图数 | delivery-adjusted quality [95% CI] |
|---|---:|---:|---:|
{chr(10).join(subgroup_lines)}

共同任务上的配对差值如下；正值表示 A 更高：

| 配对差值 | k | 共同图数 | Δ delivery-adjusted quality | Δ resolved-only quality |
|---|---:|---:|---:|---:|
{chr(10).join(subgroup_contrast_lines)}

只能把它称为“现有有限 roster 的支持曲线”。A 在所有 41 图只保证到 k=4；更高 k 会改变图像分母。任何用完该组全部成员后趋近 1 的恢复率都是机械端点，不是总体质量上限。

## 固定总人数 k=6 的混合重放

每次按 worker ID 无放回抽取，同一人每图最多一票；聚合器不读取 GT、worker 分组或 worker 质量。`B` 在主分析中是非 A 比较池，在敏感性中是 C 组。

| 分析 | 组成 | delivery-adjusted quality [95% CI] | resolved rate [95% CI] |
|---|---|---:|---:|
{chr(10).join(mixture_lines)}

极端组成差值 `4A+2B − 2A+4B`：

| 分析 | 分层 | Δ delivery-adjusted quality | Δ resolved rate | Δ resolved-only quality |
|---|---|---:|---:|---:|
{chr(10).join(mixture_contrast_lines)}

这些差异是**有限历史 roster 的事后重组关联**，不是把人随机变成 A/C 的因果效应，也不能外推成每类 12--20 人的平台。

## 可以怎样继续

- 若 A 富集从 `2A+4B → 3A+3B → 4A+2B` 呈稳定同向变化，并且在 C1、P1 分层方向一致，可把该规则冻结后拿新图/新 building 做前瞻验证。
- 若 pooled 有差异但 C1/P1 方向相反，或排除边界成员后消失，只能判定历史组成混杂，不建立类型结论。
- 若没有稳定差异，就停止离散分类路线，改用连续的 proposal-response 分数建模；不要继续调阈值找显著性。
- 现有类内支持不足以回答“某类 12--20 人是否收敛”。要回答该问题必须新增同类 worker，而不是复制已有标注。

## 口径

- resolved：唯一主簇可交付；supported multimodal 与 not evaluable 均不算 resolved。
- resolved-only quality：只在已交付输出中计算的 reference IoU。
- delivery-adjusted quality：未交付记 0；这里的 0 表示没有交付输出，不表示真实几何 IoU 为 0。
- pooled full output recovery：相对当前 20 人完整聚合输出的兼容概率；仅在完整目标本身 resolved 的图上定义。

本报告为 exploratory replay，不修改 Q_GT/R_peer/F_struct、worker eligibility、routing、正式 SAP 或方法合同。
"""


def run(output_dir: Path = DEFAULT_OUT) -> dict[str, Any]:
    workers, metadata = build_worker_strata()
    by_label = {
        label: {str(row["worker_id"]) for row in workers if row["sensitivity_stratum"] == label}
        for label in (A, C, U)
    }
    current20 = set().union(*by_label.values())
    worker_sets = {
        A: by_label[A],
        NON_A: by_label[C] | by_label[U],
        C: by_label[C],
    }

    inputs = historical.load_inputs()
    pools, pair_maps = historical.build_quality_candidates(inputs)
    evaluation_tasks = set(pools)
    evaluation_buildings = {task.split("_", 1)[0] for task in evaluation_tasks}
    assert not (set(metadata["classification_task_ids"]) & evaluation_tasks)

    subgroup_rows = replay_subgroups_exact(pools, pair_maps, worker_sets, current20)
    mixture_rows = replay_mixtures(
        pools,
        pair_maps,
        a_workers=by_label[A],
        b_pools={
            "primary_A_vs_non_A": by_label[C] | by_label[U],
            "sensitivity_A_vs_C": by_label[C],
        },
        current20=current20,
    )
    contrast_rows = build_paired_contrasts(subgroup_rows + mixture_rows)
    replay_rows = subgroup_rows + mixture_rows + contrast_rows
    summary = summarize_replay(replay_rows)

    qa = {
        "schema_version": "worker_behavior_mixture_exploratory_v1",
        "status": "exploratory_replay_not_formal_taxonomy",
        "seed": SEED,
        "posterior_draws_per_worker": POSTERIOR_DRAWS,
        "mixture_sampling": "exact_all_worker_compositions_without_replacement",
        "building_bootstrap_replicates": BOOTSTRAP_REPLICATES,
        "classification": metadata,
        "classification_evaluation_base_task_overlap_count": 0,
        "classification_evaluation_building_overlap_count": len(
            set(metadata["classification_building_ids"]) & evaluation_buildings
        ),
        "evaluation_task_count": len(evaluation_tasks),
        "evaluation_building_count": len(evaluation_buildings),
        "evaluation_stage_counts": dict(
            Counter(candidates[0]["stage"] for candidates in pools.values())
        ),
        "subgroup_task_k_row_count": len(subgroup_rows),
        "mixture_task_scenario_row_count": len(mixture_rows),
        "paired_contrast_task_row_count": len(contrast_rows),
        "summary_row_count": len(summary),
        "input_files": {
            historical.display_path(PROPOSAL_ROWS): _sha256(PROPOSAL_ROWS),
            historical.display_path(historical.METHOD_CONTRACT): _sha256(historical.METHOD_CONTRACT),
        },
        "invariants": {
            "classification_uses_p1_only": True,
            "classification_and_evaluation_base_tasks_disjoint": True,
            "sampling_without_replacement": True,
            "same_worker_max_one_vote_per_image": True,
            "aggregator_gt_blind": True,
            "task_equal_summary": True,
            "building_cluster_bootstrap": True,
            "unresolved_delivery_adjusted_quality_zero": True,
            "formal_worker_contract_changed": False,
        },
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    historical.write_csv(output_dir / "worker_operational_strata.csv", workers)
    historical.write_csv(output_dir / "replay_task_results.csv", replay_rows)
    historical.write_csv(output_dir / "replay_summary.csv", summary)
    historical.write_json(output_dir / "QA.json", qa)
    (output_dir / "REPORT_ZH.md").write_text(
        build_report(workers, metadata, summary, qa), encoding="utf-8"
    )
    return qa


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    qa = run(args.output_dir)
    print(json.dumps(qa, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
