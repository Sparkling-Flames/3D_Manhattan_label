from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import NormalDist

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import lil_matrix

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.thesis_main.analysis.c1_live_collection_monitor import read_csv, truthy
from tools.thesis_main.analysis.c1_materialize_c2_gap_audits import (
    _maximum_complete_block_count,
    build_assignments_with_capacity_fallback,
)
from tools.thesis_main.analysis.vfinal_artifact_utils import sha256_file
from tools.thesis_main.analysis.paper_a_contracts import METHOD_CONTRACT, load_method_contract


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


def _write_text(path: Path, value: str) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(value)


def _write_json(path: Path, value: dict) -> None:
    _write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def select_real_reserve(
    tasks: list[dict], inventory: list[dict], eligibility: list[dict], stage3: list[dict], *, primary_count: int = 3,
) -> list[dict]:
    used = {row["base_task_id"] for row in tasks}
    test = {row["base_task_id"] for row in stage3}
    evidence = {row["base_task_id"]: row for row in eligibility}
    candidates = []
    for row in inventory:
        task_id = row.get("base_task_id", "")
        gate = evidence.get(task_id, {})
        if (
            task_id and task_id not in used and task_id not in test
            and row.get("formal_dataset_split") == "mp3d_validation"
            and row.get("risk_design_stratum") == "stress"
            and all(truthy(gate.get(field)) for field in (
                "history_clear", "scope_ready", "reference_ready", "feature_ready", "risk_ready", "leakage_clear",
            ))
            and "future_holdout_not_clear" in gate.get("exclusion_reason", "")
        ):
            candidates.append({
                "task_id": task_id, "base_task_id": task_id, "image_id": task_id,
                "building_id": row["building_id"], "source_split": "mp3d_validation",
                "task_stratum": "stress", "c2a_rp_eligible": "true",
                "vis_3d": row["image_path"], "image_path": row["image_path"],
                "risk_design_score_A": row["risk_design_score_A"], "task_risk_sha256": gate["task_risk_sha256"],
                "reference_review_status": "not_flagged", "formal_use_blocked_until_review": "false",
                "history_clear": "true", "scope_ready": "true", "reference_ready": "true",
            })
    candidates.sort(key=lambda row: (-float(row["risk_design_score_A"]), row["task_id"]))
    for rank, row in enumerate(candidates, 1):
        primary = rank <= primary_count
        row.update({
            "selection_rank": rank,
            "capacity_role": "block1_primary" if primary else "reserve_backup",
            "future_holdout_action": "consume_for_c2a_rp" if primary else "remain_unexposed_reserve",
            "C2A_RP_exposed_after_dispatch": str(primary).lower(),
            "T1_eligible_after_dispatch": str(not primary).lower(),
        })
    return candidates


def materialize_distribution(output_dir: Path, source_dir: Path, import_json_dir: Path | None = None) -> dict:
    from tools.thesis_main.analysis.run_c2b_c2a_rp_chain import _package_c2a_rp

    source_assignment = source_dir / "assignment_manifest_C2A_RP_block_1_amended_preview.csv"
    task_pool = source_dir / "c2a_rp_task_pool_amended.csv"
    capacity_amendment = source_dir / "c2a_rp_capacity_amendment_v1.json"
    cap_extension = ROOT / "docs/thesis_main/C2A_RP_PRECISION_CAP_EXTENSION_20260807_v1.json"
    deployment_manifest = ROOT / "analysis_results/c2b_runtime_binding_20260806_v18_d8/c2b_worker_deployment_manifest_v1.json"
    old_plan = ROOT / "analysis_results/c2a_rp_local_launch_20260807_v4/c2a_rp/precision_plan_C2A_RP.csv"
    model_layout_dir = ROOT / "analysis_results/c2b_validation_static_20260802_v16/inputs/model_layout_json"
    required = (source_assignment, task_pool, capacity_amendment, cap_extension, deployment_manifest, old_plan, model_layout_dir)
    if any(not path.exists() for path in required):
        raise ValueError("C2-A-RP Block 1 distribution input is missing")
    cap = json.loads(cap_extension.read_text(encoding="utf-8"))
    if cap["change"]["maximum_blocks_per_worker_after"] != 5:
        raise ValueError("C2-A-RP precision-cap extension is not the approved five-block rule")
    assignments = read_csv(source_assignment)
    workers = {str(row["worker_id"]) for row in assignments}
    if len(assignments) != 40 or len(workers) != 20 or any(sum(row["worker_id"] == worker for row in assignments) != 2 for worker in workers):
        raise ValueError("approved Block 1 assignment is not 20 workers x 2 tasks")

    output_dir.mkdir(parents=True, exist_ok=False)
    c2a_dir = output_dir / "c2a_rp"
    c2a_dir.mkdir()
    assignment_path = output_dir / "assignment_manifest_C2A_RP_block_1.csv"
    full_assignment_path = c2a_dir / "assignment_manifest_C2A_RP.csv"
    shutil.copyfile(source_assignment, assignment_path)
    shutil.copyfile(source_assignment, full_assignment_path)
    amendment_sha = sha256_file(capacity_amendment)
    plan_rows = []
    for row in read_csv(old_plan):
        if row.get("worker_id") not in workers:
            continue
        support = int(float(row["current_support"]))
        half_width = float(row["current_ci_half_width"])
        row.update({
            "formal_goal": "risk_slope_precision", "gap_reason": "target_not_met", "additional_blocks": 1,
            "ordinary_tasks": 1, "stress_tasks": 1,
            "projected_ci_half_width": half_width * math.sqrt(support / (support + 2)),
            "precision_target_met": "false", "routing_eligibility": "pending_block_1_reestimate",
            "unmet_reason": "", "terminal_state": "", "fallback_action": "",
            "declared_support_after": support + 2, "design_manifest_sha256": amendment_sha,
        })
        plan_rows.append(row)
    if len(plan_rows) != 20:
        raise ValueError("Block 1 precision plan does not cover the 20 assigned workers")
    plan_path = c2a_dir / "precision_plan_C2A_RP.csv"
    _write_csv(plan_path, plan_rows)
    first = assignments[0]
    summary_path = c2a_dir / "precision_plan_C2A_RP.summary.json"
    _write_json(summary_path, {
        "schema_version": "c2a_rp_precision_plan_summary_v2",
        "status": "planned_not_imported_not_dispatched",
        "dispatch_mode": "planned", "dispatch_block_index": 1,
        "design_manifest_sha256": amendment_sha,
        "c2b_summary_sha256": first["c2b_summary_sha256"],
        "worker_profile_sha256": first["post_c2b_worker_profile_sha256"],
        "threshold_manifest_sha256": plan_rows[0]["threshold_manifest_sha256"],
        "existing_assignment_manifest_sha256": "",
        "max_additional_blocks": 5,
    })
    deployment_payload = json.loads(deployment_manifest.read_text(encoding="utf-8"))
    deployments = {row["deployment_id"]: row for row in deployment_payload["deployments"]}
    worker_to_deployment = {
        str(worker): deployment_id
        for deployment_id, deployment in deployments.items()
        for worker in deployment["worker_ids"]
        if str(worker) in workers
    }
    if set(worker_to_deployment) != workers:
        raise ValueError("deployment manifest does not cover the 20 assigned workers")
    package = _package_c2a_rp(
        output_dir / "c2a_rp_operational", assignment_path, task_pool,
        deployments, worker_to_deployment, block_index=1,
        c2a_summary_path=summary_path, model_layout_dir=model_layout_dir,
    )
    package["status"] = "planned_not_imported_not_dispatched"
    mapping_rows = read_csv(Path(package["runtime_mapping_path"]))
    if {
        (row["worker_id"], row["planned_task_id"]) for row in mapping_rows
    } != {
        (row["worker_id"], row["task_id"]) for row in assignments
    }:
        raise ValueError("runtime mapping does not preserve assignment worker-task identity")
    private_files = sorted((output_dir / "c2a_rp_operational/private_lists").glob("*.csv"))
    manifest = {
        "schema_version": "c2a_rp_block1_distribution_manifest_v1",
        "status": "planned_not_imported_not_dispatched",
        "method_contract_version": load_method_contract()["contract_version"],
        "method_contract_sha256": sha256_file(METHOD_CONTRACT),
        "precision_cap_extension_path": str(cap_extension.resolve()),
        "precision_cap_extension_sha256": sha256_file(cap_extension),
        "capacity_amendment_path": str(capacity_amendment.resolve()),
        "capacity_amendment_sha256": amendment_sha,
        "assignment_source_sha256": sha256_file(source_assignment),
        "assignment_unchanged": sha256_file(source_assignment) == sha256_file(assignment_path),
        "worker_count": 20, "assignment_count": 40,
        "maximum_blocks_per_worker": 5,
        "future_blocks_preassigned": False,
        "operational_package": package,
        "private_list_sha256": {path.name: sha256_file(path) for path in private_files},
    }
    if import_json_dir:
        import_json_dir.mkdir(parents=True, exist_ok=True)
        import_names = {
            "c2b_en": "c2a_rp_block_1_import_foreign_https.json",
            "c2b_zh": "c2a_rp_block_1_import_zh.json",
        }
        manifest["import_json_outputs"] = {}
        for deployment_id, filename in import_names.items():
            source = Path(package["deployments"][deployment_id]["planned_import_path"])
            target = import_json_dir / filename
            shutil.copyfile(source, target)
            manifest["import_json_outputs"][deployment_id] = {
                "path": str(target.resolve()), "sha256": sha256_file(target),
            }
        _write_text(import_json_dir / "README.md", "# C2-A-RP Block 1 planned imports\n\n- `c2a_rp_block_1_import_foreign_https.json`: Project 76 / Project E\n- `c2a_rp_block_1_import_zh.json`: Project 77 / 任务5\n- 仅为计划导入包；导入后再回填 runtime task ID。\n")
    if not manifest["assignment_unchanged"] or len(private_files) != 20:
        raise ValueError("Block 1 distribution identity check failed")
    _write_json(output_dir / "C2A_RP_BLOCK1_DISTRIBUTION_MANIFEST.json", manifest)
    _write_text(output_dir / "READY_FOR_MANUAL_IMPORT.md", "# C2-A-RP Block 1\n\n状态：待人工导入，尚未导入、尚未发放。请分别导入 Project 76 英文 JSON 与 Project 77 中文 JSON；导入后回填 runtime mapping，再通知工人。Block 2--5 不得提前分配。\n")
    return manifest


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
    inventory = read_csv(ROOT / "analysis_results/c2b_validation_design_20260802_v17/output/c2_task_risk_inventory.csv")
    eligibility = read_csv(ROOT / "analysis_results/c2b_validation_design_20260802_v17/output/c2b_task_eligibility_evidence.csv")
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
    output_dir.mkdir(parents=True, exist_ok=True)
    reserve = select_real_reserve(tasks, inventory, eligibility, stage3)
    primary = [row for row in reserve if row["capacity_role"] == "block1_primary"]
    backup = [row for row in reserve if row["capacity_role"] == "reserve_backup"]
    if len(primary) != 3 or len(backup) != 1:
        raise ValueError(f"expected 3 primary + 1 backup, found {len(primary)} + {len(backup)}")
    pool_fields = list(tasks[0])
    amended_tasks = tasks + [{key: row.get(key, "") for key in pool_fields} for row in primary]
    real_capacity = _maximum_complete_block_count(
        workers, amended_tasks, history_rows=history, max_task_support=max_support, require_explicit_eligibility=True,
    )
    amendment = {
        "schema_version": "c2a_rp_capacity_amendment_v1",
        "status": "preview_not_dispatch_authorization",
        "c2b_collection": {"status": "closed", "cutoff": "2026-08-06", "planned": 176, "submitted": 160, "terminal_missing": 16, "no_further_c2b_worker_outcomes": True},
        "decision_timing": "after_C2B_collection_closure_before_any_C2A_RP_outcome",
        "selection_rule": "frozen_risk_score_desc_then_task_id; no worker performance or outcome fields",
        "primary_task_ids": [row["task_id"] for row in primary],
        "backup_task_ids": [row["task_id"] for row in backup],
        "future_holdout_consumed": 3, "future_holdout_backup_unexposed": 1,
        "t1_retired_task_ids": [row["task_id"] for row in primary],
        "v1_test_overlap_count": 0, "maximum_block1_workers": real_capacity,
        "input_sha256": {
            "task_pool": sha256_file(ROOT / "analysis_results/c2a_rp_local_launch_20260807_inputs_v2/c2a_rp_task_pool_post_c2_local.csv"),
            "task_inventory": sha256_file(ROOT / "analysis_results/c2b_validation_design_20260802_v17/output/c2_task_risk_inventory.csv"),
            "eligibility": sha256_file(ROOT / "analysis_results/c2b_validation_design_20260802_v17/output/c2b_task_eligibility_evidence.csv"),
            "seen_history": sha256_file(ROOT / "analysis_results/c2b_closeout_20260806_inputs/c2a_rp_seen_history_through_c2b.csv"),
            "v1_candidate_tasks": sha256_file(ROOT / "analysis_results/stage3_test_preparation_20260804_v1/test_task_risk_candidate.csv"),
        },
    }
    amendment_path = output_dir / "c2a_rp_capacity_amendment_v1.json"
    _write_json(amendment_path, amendment)
    plans = []
    for row in read_csv(ROOT / "analysis_results/c2a_rp_local_launch_20260807_v4/c2a_rp/precision_plan_C2A_RP.csv"):
        if row.get("current_ci_half_width"):
            row.update({"additional_blocks": 1, "ordinary_tasks": 1, "stress_tasks": 1, "gap_reason": "target_not_met", "formal_goal": "risk_slope_precision"})
            plans.append(row)
    assignments, fallback = build_assignments_with_capacity_fallback(
        plans, amended_tasks,
        manifest_sha=sha256_file(amendment_path),
        c2b_sha=sha256_file(ROOT / "analysis_results/c2a_rp_local_launch_20260807_v4/c2b_closeout_v2.json"),
        profile_sha=sha256_file(ROOT / "analysis_results/c2a_rp_local_launch_20260807_v4/post_c2b_worker_profile.csv"),
        history_rows=history, max_task_support=max_support, selection_seed=20260724,
        require_explicit_eligibility=True, formal=False, dispatch_block_index=1,
    )
    worker_counts = Counter(row["worker_id"] for row in assignments)
    worker_strata = defaultdict(Counter)
    task_counts = Counter(row["task_id"] for row in assignments)
    for row in assignments:
        worker_strata[row["worker_id"]][row["task_stratum"]] += 1
    primary_counts = {row["task_id"]: task_counts[row["task_id"]] for row in primary}
    if (
        fallback or len(assignments) != 40 or len(worker_counts) != 20
        or any(count != 2 for count in worker_counts.values())
        or any(counts != {"ordinary": 1, "stress": 1} for counts in worker_strata.values())
        or max(task_counts.values()) > max_support or any(count != 2 for count in primary_counts.values())
    ):
        raise ValueError("amended Block 1 preview failed the 20x2 paired-capacity audit")
    exposure_rows = [{
        "task_id": row["task_id"], "base_task_id": row["base_task_id"], "capacity_role": row["capacity_role"],
        "future_holdout_action": row["future_holdout_action"],
        "C2A_RP_exposed_after_dispatch": row["C2A_RP_exposed_after_dispatch"],
        "T1_eligible_after_dispatch": row["T1_eligible_after_dispatch"], "V1_test_overlap": "false",
    } for row in reserve]
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
        "real_reserve_candidate_count": len(reserve),
        "real_primary_task_count": len(primary),
        "real_backup_task_count": len(backup),
        "real_amended_block1_assignment_count": len(assignments),
        "stress_task_support_cap": max_support,
        "v1_candidate_task_count": len(stage3),
        "v1_stress_task_count": stress_count,
        "v1_stress_fraction": stress_fraction,
        "v1_power_scope": "quality_only_proxy; policy divergence diagnostic; severe/unresolved endpoints not identifiable",
        "capacity_curve": curve,
        "power_scenarios": power_rows,
    }
    _write_json(output_dir / "c2a_rp_capacity_power_amendment.json", result)
    _write_csv(output_dir / "capacity_scenarios.csv", curve)
    _write_csv(output_dir / "v1_power_scenarios.csv", power_rows)
    _write_csv(output_dir / "c2a_rp_new_stress_candidate_registry.csv", reserve)
    _write_csv(output_dir / "c2a_rp_task_pool_amended.csv", amended_tasks)
    _write_csv(output_dir / "c2a_rp_exposure_amendment.csv", exposure_rows)
    _write_csv(output_dir / "assignment_manifest_C2A_RP_block_1_amended_preview.csv", assignments)
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
    report += f"""

功效假定 458 个 V1 candidate task、1:1 分配、单侧 0.05 正态近似；只覆盖 delivery-adjusted quality 代理，不覆盖 V1 层级中的 severe failure、unresolved+severe failure、动态容量或聚合效应。

## 建议

先新增 {block1_min} 张 stress reserve 并完成 20/20 Block 1；随后用真实 Block 1 结果重估 slope 方差与 CI。只有非零异质性仍存在且 16 人确需 Block 2 时，再补至累计 {two_round_min} 张。现在一次性补足两轮 reserve 或招新工人都没有新增决策价值。

容量结论以新增图均为 validation-only、对 20 人全部未见、通过 scope/reference 审核且每图支持上限为 2 为条件；本审计不负责选择或导入这些图片。
"""
    report += f"""

## 实际 capacity amendment

- 已冻结 3 张 primary 与 1 张未暴露 backup；前三张从 future-holdout 永久退出 T1。
- amended pool 的精确容量为 {real_capacity}/20。
- Block 1 preview 为 {len(assignments)} 行、20 名工人，每人恰好 1 ordinary + 1 stress；单 task support 不超过 {max_support}。
- 当前产物仅供本地审核，不是导入或发放授权。
"""
    _write_text(output_dir / "C2A_RP_CAPACITY_POWER_AMENDMENT_REPORT.md", report)
    _write_text(
        output_dir / "PREVIEW_NOT_FOR_DISPATCH.md",
        "# NOT FOR DISPATCH\n\n该目录仅为 C2-A-RP Block 1 本地 preview；未生成正式导入授权，未导入 Label Studio，未发放。\n",
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "analysis_results/c2a_rp_capacity_power_amendment_20260807_v1")
    parser.add_argument("--distribution-output-dir", type=Path)
    parser.add_argument("--import-json-dir", type=Path)
    args = parser.parse_args()
    materialize(args.output_dir)
    if args.distribution_output_dir:
        materialize_distribution(args.distribution_output_dir, args.output_dir, args.import_json_dir)
