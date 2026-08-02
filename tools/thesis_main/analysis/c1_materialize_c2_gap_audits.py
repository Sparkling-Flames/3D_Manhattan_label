from __future__ import annotations

import argparse
import json
import math
import random
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.thesis_main.analysis.c1_live_collection_monitor import read_csv, safe, truthy, write_csv, write_json
from tools.thesis_main.analysis.paper_a_contracts import METHOD_CONTRACT, load_method_contract
from tools.thesis_main.analysis.vfinal_artifact_utils import sha256_file


PRECISION_FIELDS = [
    "worker_id", "current_support", "current_ci_half_width", "target_ci_half_width",
    "additional_blocks", "ordinary_tasks", "stress_tasks", "projected_ci_half_width",
    "precision_target_met", "routing_eligibility", "unmet_reason", "design_manifest_sha256",
]
C2A_ASSIGNMENT_FIELDS = [
    "round_id", "worker_id", "task_id", "base_task_id", "task_stratum",
    "assignment_sequence", "c2_component", "target_component", "gap_reason",
    "precision_before", "support_before", "support_after", "selection_probability",
    "conditional_inclusion_probability", "selection_seed", "selection_draw_id", "eligible_count_at_draw",
    "task_support_before", "task_support_after", "paired_block_support_before", "paired_block_support_after",
    "effective_risk_slope_support_before", "effective_risk_slope_support_after",
    "design_manifest_sha256",
    "c2b_summary_sha256", "post_c2b_worker_profile_sha256",
]


def _c2a_rp_limits() -> tuple[int, int, str]:
    method = load_method_contract()
    max_tasks = int(method["c2"]["c2_a_rp_max_tasks_per_worker"])
    if max_tasks != 4 or max_tasks < 0 or max_tasks % 2:
        raise ValueError(f"invalid normative C2-A-RP cap:{max_tasks}")
    return max_tasks, max_tasks // 2, sha256_file(METHOD_CONTRACT)


def _validate_c2a_rp_counts(
    additional_blocks: int,
    ordinary_tasks: int,
    stress_tasks: int,
    *,
    max_tasks: int,
    max_additional_blocks: int,
) -> None:
    if not 0 <= additional_blocks <= max_additional_blocks:
        raise ValueError("C2-A-RP additional blocks exceed the normative cap")
    if ordinary_tasks != stress_tasks or ordinary_tasks != additional_blocks:
        raise ValueError("C2-A-RP requires one ordinary and one stress task per block")
    if 2 * additional_blocks > max_tasks:
        raise ValueError("C2-A-RP tasks exceed the normative per-worker cap")


def _number(row: dict[str, str], *fields: str) -> float | None:
    for field in fields:
        value = safe(row.get(field))
        if value:
            return float(value)
    return None


def build_precision_plan(
    worker_rows: list[dict[str, str]],
    *,
    target_half_width: float,
    max_additional_blocks: int,
    manifest_sha: str,
) -> list[dict[str, Any]]:
    max_tasks, contract_max_blocks, _method_sha = _c2a_rp_limits()
    if max_additional_blocks < 0 or max_additional_blocks > contract_max_blocks:
        raise ValueError("design manifest max_additional_blocks exceeds the normative C2-A-RP cap")
    out = []
    for row in sorted(worker_rows, key=lambda value: safe(value.get("worker_id"))):
        worker = safe(row.get("worker_id"))
        support_raw = _number(row, "support", "n_support", "n_calib_completed")
        half_width = _number(row, "ci_half_width", "r_u_h")
        blocked = truthy(row.get("process_blocker")) or truthy(row.get("independence_blocker"))
        blocks = 0
        projected = half_width
        reason = ""
        if blocked:
            reason = "process_or_independence_blocker"
        elif not worker or support_raw is None or support_raw <= 0 or half_width is None:
            reason = "precision_not_evaluable"
        else:
            support = int(support_raw)
            while projected > target_half_width and blocks < max_additional_blocks:
                blocks += 1
                projected = half_width * math.sqrt(support / (support + 2 * blocks))
            if projected > target_half_width:
                reason = "target_not_met_at_frozen_cap"
        met = not reason and projected is not None and projected <= target_half_width
        _validate_c2a_rp_counts(
            blocks, blocks, blocks,
            max_tasks=max_tasks, max_additional_blocks=contract_max_blocks,
        )
        out.append({
            "worker_id": worker,
            "target_component": safe(row.get("target_component") or row.get("component_id")) or "risk_slope",
            "gap_reason": safe(row.get("gap_reason")) or ("target_not_met" if blocks else "target_already_met"),
            "current_support": "" if support_raw is None else int(support_raw),
            "current_ci_half_width": "" if half_width is None else half_width,
            "target_ci_half_width": target_half_width,
            "additional_blocks": blocks,
            "ordinary_tasks": blocks,
            "stress_tasks": blocks,
            "projected_ci_half_width": "" if projected is None else projected,
            "precision_target_met": met,
            "routing_eligibility": "eligible" if met else "uncertain_fallback_global",
            "unmet_reason": reason,
            "design_manifest_sha256": manifest_sha,
        })
    return out


def build_precision_assignments(
    precision_rows: list[dict[str, Any]],
    task_rows: list[dict[str, str]],
    *,
    manifest_sha: str,
    c2b_sha: str,
    profile_sha: str,
    history_rows: list[dict[str, str]] | None = None,
    max_task_support: int = 2,
    selection_seed: int = 0,
    require_explicit_eligibility: bool = False,
) -> list[dict[str, Any]]:
    max_tasks, contract_max_blocks, _method_sha = _c2a_rp_limits()
    if max_task_support < 1:
        raise ValueError("C2-A-RP max_task_support must be positive")
    for plan in precision_rows:
        _validate_c2a_rp_counts(
            int(plan["additional_blocks"]), int(plan["ordinary_tasks"]), int(plan["stress_tasks"]),
            max_tasks=max_tasks, max_additional_blocks=contract_max_blocks,
        )
    pools: dict[str, list[dict[str, str]]] = {"ordinary": [], "stress": []}
    for task in task_rows:
        stratum = safe(task.get("task_stratum") or task.get("risk_bucket")).lower()
        task_id = safe(task.get("task_id"))
        eligible = task.get("c2a_rp_eligible")
        if task_id and stratum in pools and (truthy(eligible) if require_explicit_eligibility else eligible is None or safe(eligible) == "" or truthy(eligible)):
            pools[stratum].append(task)
    for rows in pools.values():
        rows.sort(key=lambda row: safe(row.get("task_id")))

    assignments: list[dict[str, Any]] = []
    seen_by_worker = defaultdict(set)
    for history in history_rows or []:
        worker = safe(history.get("worker_id"))
        seen_by_worker[worker].update(filter(None, (
            safe(history.get("task_id")), safe(history.get("base_task_id")),
        )))
    task_support: dict[str, int] = defaultdict(int)
    for history in history_rows or []:
        task_id = safe(history.get("task_id"))
        if task_id:
            task_support[task_id] += 1
    for plan in precision_rows:
        worker = safe(plan.get("worker_id"))
        sequence = 0
        for stratum, count_field in (("ordinary", "ordinary_tasks"), ("stress", "stress_tasks")):
            count = int(plan[count_field])
            eligible = [
                task for task in pools[stratum]
                if safe(task.get("task_id")) not in seen_by_worker[worker]
                and safe(task.get("base_task_id")) not in seen_by_worker[worker]
                and task_support[safe(task.get("task_id"))] < max_task_support
            ]
            if count > len(eligible):
                raise ValueError(f"insufficient C2-A-RP {stratum} tasks for worker {worker}")
            if not count:
                continue
            rng = random.Random(f"{selection_seed}|{worker}|{stratum}")
            for draw in range(count):
                eligible_count = len(eligible)
                task = eligible.pop(rng.randrange(eligible_count))
                task_id = safe(task.get("task_id"))
                base_task_id = safe(task.get("base_task_id")) or task_id
                support_before = task_support[task_id]
                task_support[task_id] += 1
                seen_by_worker[worker].update((task_id, base_task_id))
                sequence += 1
                assignments.append({
                    "round_id": "C2-A-RP", "worker_id": worker,
                    "task_id": safe(task.get("task_id")),
                    "base_task_id": base_task_id,
                    "task_stratum": stratum, "assignment_sequence": sequence,
                    "c2_component": "precision_completion",
                    "target_component": plan["target_component"],
                    "gap_reason": plan["gap_reason"],
                    "precision_before": plan["current_ci_half_width"],
                    "support_before": plan["current_support"],
                    "support_after": int(plan["current_support"]) + sequence,
                    "selection_probability": 1 / eligible_count,
                    "conditional_inclusion_probability": 1 / eligible_count,
                    "selection_seed": selection_seed,
                    "selection_draw_id": f"{worker}:{stratum}:{sequence}",
                    "eligible_count_at_draw": eligible_count,
                    "task_support_before": support_before,
                    "task_support_after": support_before + 1,
                    "paired_block_support_before": int(plan.get("paired_block_support_before") or 0),
                    "paired_block_support_after": int(plan.get("paired_block_support_before") or 0) + int(plan["additional_blocks"]),
                    "effective_risk_slope_support_before": int(plan["current_support"]),
                    "effective_risk_slope_support_after": int(plan["current_support"]) + int(plan["additional_blocks"]),
                    "design_manifest_sha256": manifest_sha,
                    "c2b_summary_sha256": c2b_sha,
                    "post_c2b_worker_profile_sha256": profile_sha,
                })
    return assignments


def materialize(
    worker_profile_csv: Path,
    design_manifest: Path,
    output_dir: Path,
    *,
    c2b_summary: Path | None = None,
    c2b_summary_sha256: str | None = None,
    task_pool_csv: Path | None = None,
    assignment_history_csv: Path | None = None,
    input_status: str = "dry_run",
) -> dict[str, Any]:
    manifest = json.loads(design_manifest.read_text(encoding="utf-8"))
    if manifest.get("manifest_version") != "c2_design_v1":
        raise ValueError("unsupported C2 design manifest version")
    manifest_sha = sha256_file(design_manifest)
    expected = manifest.get("input_sha256") or {}
    actual_profile_sha = sha256_file(worker_profile_csv)
    binding_valid = expected.get("worker_profile_csv") == actual_profile_sha
    c2b_valid = input_status != "formal"
    c2b_sha = ""
    if c2b_summary:
        c2b_sha = sha256_file(c2b_summary)
        c2b = json.loads(c2b_summary.read_text(encoding="utf-8"))
        c2b_valid = (
            (input_status != "formal" or c2b_sha == safe(c2b_summary_sha256).lower())
            and
            c2b.get("design_manifest_sha256") == manifest_sha
            and bool(c2b.get("c2b_design_ready"))
            and bool(c2b.get("c2b_closeout_ready"))
            and bool(c2b.get("post_c2b_profile_manifest_sha256"))
            and (
                input_status != "formal"
                or c2b.get("post_c2b_worker_profile_sha256") == actual_profile_sha
            )
        )
    if input_status == "formal" and (not c2b_summary or not c2b_summary_sha256):
        c2b_valid = False
    precision = manifest.get("precision") or {}
    target = float(precision["target_ci_half_width"])
    max_blocks = int(precision["max_additional_blocks"])
    if target <= 0 or max_blocks < 0:
        raise ValueError("precision target must be positive and max_additional_blocks non-negative")
    max_tasks, contract_max_blocks, method_sha = _c2a_rp_limits()
    if max_blocks > contract_max_blocks:
        raise ValueError("design manifest max_additional_blocks exceeds the normative C2-A-RP cap")
    if not binding_valid or not c2b_valid:
        if input_status == "formal":
            raise ValueError("stale_or_unbound_c2a_rp_dependency")
    rows = build_precision_plan(
        read_csv(worker_profile_csv),
        target_half_width=target,
        max_additional_blocks=max_blocks,
        manifest_sha=manifest_sha,
    )
    assignments: list[dict[str, Any]] = []
    task_pool_valid = input_status != "formal"
    if task_pool_csv:
        expected_task_sha = safe(expected.get("c2a_task_pool_csv"))
        task_pool_valid = input_status != "formal" or expected_task_sha == sha256_file(task_pool_csv)
        if task_pool_valid:
            assignments = build_precision_assignments(
                rows, read_csv(task_pool_csv), manifest_sha=manifest_sha,
                c2b_sha=c2b_sha, profile_sha=actual_profile_sha,
                history_rows=read_csv(assignment_history_csv) if assignment_history_csv else None,
                max_task_support=int(precision.get("max_task_support", 2)),
                selection_seed=int(precision.get("selection_seed", 0)),
                require_explicit_eligibility=input_status == "formal",
            )
    history_valid = input_status != "formal"
    if assignment_history_csv:
        history_valid = input_status != "formal" or (
            safe(expected.get("assignment_history_csv")) == sha256_file(assignment_history_csv)
        )
    if input_status == "formal" and (not task_pool_csv or not task_pool_valid or not assignment_history_csv or not history_valid):
        raise ValueError("stale_or_unbound_c2a_rp_task_pool")
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "precision_plan_C2A_RP.csv", rows, PRECISION_FIELDS)
    write_csv(output_dir / "assignment_manifest_C2A_RP.csv", assignments, C2A_ASSIGNMENT_FIELDS)
    summary = {
        "design_manifest_sha256": manifest_sha,
        "worker_profile_sha256": actual_profile_sha,
        "dependency_binding_valid": binding_valid and c2b_valid and task_pool_valid and history_valid,
        "c2b_summary_sha256": c2b_sha,
        "task_pool_sha256": sha256_file(task_pool_csv) if task_pool_csv else "",
        "method_contract_version": load_method_contract()["contract_version"],
        "method_contract_sha256": method_sha,
        "c2_a_rp_max_tasks_per_worker": max_tasks,
        "max_additional_blocks": max_blocks,
        "max_task_support": int(precision.get("max_task_support", 2)),
        "n_workers": len(rows),
        "n_workers_with_precision_additions": sum(int(row["additional_blocks"]) > 0 for row in rows),
        "n_workers_unmet_at_cap": sum(bool(row["unmet_reason"]) for row in rows),
        "n_assignments": len(assignments),
        "c2a_rp_ready": binding_valid and c2b_valid and task_pool_valid and history_valid and bool(rows),
        "candidate_only": input_status != "formal",
        "launch_ready": input_status == "formal" and binding_valid and c2b_valid and task_pool_valid and history_valid and bool(rows),
        "searches_new_risk_family": False,
        "modifies_c1": False,
    }
    write_json(output_dir / "precision_plan_C2A_RP.summary.json", summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize C2-A-RP precision-only completion from post-C2-B worker uncertainty.")
    parser.add_argument("--worker-profile-csv", type=Path, required=True)
    parser.add_argument("--design-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--c2b-summary", type=Path)
    parser.add_argument("--c2b-summary-sha256")
    parser.add_argument("--task-pool-csv", type=Path)
    parser.add_argument("--assignment-history-csv", type=Path)
    parser.add_argument("--input-status", choices=("dry_run", "formal"), default="dry_run")
    args = parser.parse_args(argv)
    print(json.dumps(materialize(
        args.worker_profile_csv, args.design_manifest, args.output_dir,
        c2b_summary=args.c2b_summary, c2b_summary_sha256=args.c2b_summary_sha256,
        task_pool_csv=args.task_pool_csv, input_status=args.input_status,
        assignment_history_csv=args.assignment_history_csv,
    ), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
