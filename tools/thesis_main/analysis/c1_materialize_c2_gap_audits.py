from __future__ import annotations

import argparse
import itertools
import json
import math
import random
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import lil_matrix

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.thesis_main.analysis.c1_live_collection_monitor import read_csv, safe, truthy, write_csv, write_json
from tools.thesis_main.analysis.paper_a_contracts import METHOD_CONTRACT, load_method_contract
from tools.thesis_main.analysis.vfinal_artifact_utils import sha256_file
from tools.thesis_main.analysis.worker_identity import normalize_worker_id


PRECISION_FIELDS = [
    "schema_version", "worker_id", "target_component", "gap_reason", "formal_goal",
    "current_support", "current_ci_half_width", "target_ci_half_width", "interval_level", "ci_method",
    "additional_blocks", "ordinary_tasks", "stress_tasks", "projected_ci_half_width",
    "precision_target_met", "routing_eligibility", "unmet_reason", "terminal_state", "fallback_action",
    "declared_support_after", "observed_support_after", "ordinary_support_observed_after", "stress_support_observed_after",
    "threshold_manifest_sha256", "design_manifest_sha256",
]
C2A_ASSIGNMENT_FIELDS = [
    "schema_version", "round_id", "worker_id", "task_id", "base_task_id", "task_stratum",
    "assignment_sequence", "block_index", "c2_component", "target_component", "gap_reason",
    "formal_goal", "precision_before", "support_before", "support_after", "declared_support_after", "selection_probability",
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


def _formal_goal(method: dict[str, Any] | None = None) -> str:
    contract = method or load_method_contract()
    return safe(contract.get("c2", {}).get("c2_a_rp_formal_target")) or "risk_slope_precision"


def _c2a_rp_csv_schemas(method: dict[str, Any] | None = None) -> tuple[str, str]:
    contract = method or load_method_contract()
    schema = contract.get("c2", {}).get("c2_a_rp_csv_schema", {})
    precision = safe(schema.get("precision_plan"))
    assignment = safe(schema.get("assignment_manifest"))
    if not precision or not assignment or schema.get("schema_field") != "schema_version" or schema.get("formal_reject_legacy") is not True:
        raise ValueError("C2-A-RP CSV schema contract is incomplete")
    return precision, assignment


def _write_blocked_summary(output_dir: Path, reason: str, hashes: dict[str, str] | None = None) -> Path:
    method = load_method_contract()
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "c2a_rp_blocked_summary.json"
    write_json(path, {
        "schema_version": "c2a_rp_blocked_summary_v1",
        "artifact_role": "C2A_RP_BLOCKED_SUMMARY",
        "method_contract_version": method["contract_version"],
        "method_contract_sha256": sha256_file(METHOD_CONTRACT),
        "formal_ready": False,
        "launch_ready": False,
        "reason_code": reason,
        "input_hashes": hashes or {},
    })
    return path


def _resolve_formal_threshold(
    design_manifest: Path,
    manifest: dict[str, Any],
    precision: dict[str, Any],
    explicit_path: Path | None,
) -> tuple[float, Path, str]:
    path_value = explicit_path or precision.get("threshold_manifest_path") or manifest.get("threshold_manifest_path")
    declared_sha = safe(precision.get("threshold_manifest_sha256") or manifest.get("threshold_manifest_sha256"))
    if not path_value or not declared_sha:
        raise ValueError("C2-A-RP formal input lacks frozen threshold manifest binding")
    path = Path(path_value)
    if not path.is_absolute():
        path = (design_manifest.parent / path).resolve()
    if not path.is_file() or sha256_file(path) != declared_sha:
        raise ValueError("C2-A-RP frozen threshold manifest is missing or stale")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("status") != "approved" or payload.get("formal_selection_allowed") is not True:
        raise ValueError("C2-A-RP frozen threshold manifest is not formally approved")
    formula_id = (payload.get("derivation", {}).get("formula_ids", {})
                  .get("risk_slope_ci_half_width"))
    if formula_id != "normal_95_max_unified_slope_sd":
        raise ValueError("C2-A-RP threshold manifest uses an unsupported risk-slope formula")
    try:
        target = float(payload["thresholds"]["risk_slope_ci_half_width"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("C2-A-RP threshold manifest lacks risk_slope_ci_half_width") from exc
    if not math.isfinite(target) or target <= 0:
        raise ValueError("C2-A-RP risk-slope target is nonfinite or nonpositive")
    declared_target = precision.get("target_ci_half_width")
    if declared_target not in {None, ""} and not math.isclose(float(declared_target), target, rel_tol=1e-12, abs_tol=1e-12):
        raise ValueError("C2-A-RP design target disagrees with the frozen threshold manifest")
    return target, path, declared_sha


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
    threshold_sha: str = "",
    formal: bool = False,
) -> list[dict[str, Any]]:
    max_tasks, contract_max_blocks, _method_sha = _c2a_rp_limits()
    if max_additional_blocks < 0 or max_additional_blocks > contract_max_blocks:
        raise ValueError("design manifest max_additional_blocks exceeds the normative C2-A-RP cap")
    precision_schema, _assignment_schema = _c2a_rp_csv_schemas()
    out = []
    for row in sorted(worker_rows, key=lambda value: safe(value.get("worker_id"))):
        worker = safe(row.get("worker_id"))
        support_raw = _number(row, "support", "n_support", "n_calib_completed")
        target_component = safe(row.get("target_component") or row.get("component_id")) or "risk_slope"
        if formal and target_component != "risk_slope":
            raise ValueError("C2-A-RP formal target must be risk_slope")
        half_width = _number(row, "risk_slope_ci_half_width", "ci_half_width", "r_u_h")
        blocked = truthy(row.get("process_blocker")) or truthy(row.get("independence_blocker"))
        blocks = 0
        projected = half_width
        reason = ""
        if blocked:
            reason = "process_or_independence_blocker"
        elif not worker or support_raw is None or support_raw <= 0 or half_width is None:
            reason = "precision_not_evaluable"
        else:
            if formal:
                # Formal C2-A-RP decisions use the frozen width only.  The
                # observed risk-slope fit after each block, not a support
                # scaling projection, decides the terminal state.
                if half_width > target_half_width:
                    blocks = max_additional_blocks
                    projected = None
                    if blocks == 0:
                        reason = "candidate_cap_requires_actual_reestimate"
            else:
                support = int(support_raw)
                while projected > target_half_width and blocks < max_additional_blocks:
                    blocks += 1
                    projected = half_width * math.sqrt(support / (support + 2 * blocks))
                if projected > target_half_width:
                    reason = "target_not_met_at_frozen_cap"
        met = not reason and projected is not None and projected <= target_half_width and blocks == 0
        not_evaluable = reason in {"precision_not_evaluable", "process_or_independence_blocker"}
        terminal_state = "target_met" if met else "not_evaluable" if not_evaluable else "pending_actual_reestimate" if formal and blocks else "fallback_strong_global" if reason else "target_met"
        _validate_c2a_rp_counts(
            blocks, blocks, blocks,
            max_tasks=max_tasks, max_additional_blocks=contract_max_blocks,
        )
        out.append({
            "schema_version": precision_schema,
            "worker_id": worker,
            "target_component": target_component,
            "gap_reason": safe(row.get("gap_reason")) or reason or ("target_not_met" if blocks else "target_already_met"),
            "formal_goal": _formal_goal() if formal else safe(row.get("formal_goal")) or target_component,
            "current_support": "" if support_raw is None else int(support_raw),
            "current_ci_half_width": "" if half_width is None else half_width,
            "target_ci_half_width": target_half_width,
            "interval_level": 0.95,
            "ci_method": "normal_95_max_unified_slope_sd",
            "additional_blocks": blocks,
            "ordinary_tasks": blocks,
            "stress_tasks": blocks,
            "projected_ci_half_width": "" if projected is None else projected,
            "precision_target_met": met,
            "routing_eligibility": "eligible" if met else "not_evaluable" if not_evaluable else "pending_actual_reestimate" if formal and blocks else "uncertain_fallback_global",
            "unmet_reason": reason,
            "terminal_state": terminal_state,
            "fallback_action": "STRONG_GLOBAL" if terminal_state in {"fallback_strong_global", "not_evaluable"} else "",
            "declared_support_after": int(support_raw) + 2 * int(blocks) if support_raw is not None else "",
            "observed_support_after": "",
            "ordinary_support_observed_after": "",
            "stress_support_observed_after": "",
            "threshold_manifest_sha256": threshold_sha,
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
    formal: bool = False,
    dispatch_block_index: int | None = None,
) -> list[dict[str, Any]]:
    max_tasks, contract_max_blocks, _method_sha = _c2a_rp_limits()
    if max_task_support < 1:
        raise ValueError("C2-A-RP max_task_support must be positive")
    if dispatch_block_index is not None and not 1 <= int(dispatch_block_index) <= contract_max_blocks:
        raise ValueError("C2-A-RP dispatch block is outside the normative cap")
    _precision_schema, assignment_schema = _c2a_rp_csv_schemas()
    for plan in precision_rows:
        if formal and safe(plan.get("target_component")) != "risk_slope":
            raise ValueError("C2-A-RP formal assignment target must be risk_slope")
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
        round_id = safe(history.get("round_id"))
        if task_id and (
            not round_id
            or round_id == "C2-A-RP"
            or safe(history.get("schema_version")) == assignment_schema
        ):
            task_support[task_id] += 1
    for plan in precision_rows:
        worker = safe(plan.get("worker_id"))
        if int(plan["additional_blocks"]) == 0:
            continue
        prior_c2a_rows = [
            row for row in history_rows or []
            if safe(row.get("worker_id")) == worker and (
                safe(row.get("round_id")) == "C2-A-RP"
                or safe(row.get("schema_version")) == assignment_schema
            )
        ]
        sequence = len(prior_c2a_rows)
        new_sequence = 0
        eligible_by_stratum: dict[str, list[dict[str, str]]] = {}
        rng_by_stratum: dict[str, random.Random] = {}
        for stratum in ("ordinary", "stress"):
            eligible_by_stratum[stratum] = [
                task for task in pools[stratum]
                if safe(task.get("task_id")) not in seen_by_worker[worker]
                and safe(task.get("base_task_id")) not in seen_by_worker[worker]
                and task_support[safe(task.get("task_id"))] < max_task_support
            ]
            count = 1 if dispatch_block_index is not None else int(plan[f"{stratum}_tasks"])
            if count > len(eligible_by_stratum[stratum]):
                raise ValueError(f"insufficient C2-A-RP {stratum} tasks for worker {worker}")
            rng_by_stratum[stratum] = random.Random(f"{selection_seed}|{worker}|{stratum}")
        first_block = int(dispatch_block_index or 1)
        planned_last_block = max(int(plan["ordinary_tasks"]), int(plan["stress_tasks"]))
        if dispatch_block_index is not None and first_block > planned_last_block:
            raise ValueError(f"C2-A-RP dispatch block exceeds worker plan:{worker}")
        last_block = int(dispatch_block_index or planned_last_block)
        for block_index in range(first_block, last_block + 1):
            for stratum in ("ordinary", "stress"):
                if block_index > int(plan[f"{stratum}_tasks"]):
                    continue
                # Recompute the live candidate set after the paired draw.  The
                # same base task may occur in both strata; precomputing both
                # lists before the ordinary draw would silently allow reuse.
                for candidate_stratum in ("ordinary", "stress"):
                    eligible_by_stratum[candidate_stratum] = [
                        task for task in eligible_by_stratum[candidate_stratum]
                        if safe(task.get("task_id")) not in seen_by_worker[worker]
                        and safe(task.get("base_task_id")) not in seen_by_worker[worker]
                        and task_support[safe(task.get("task_id"))] < max_task_support
                    ]
                eligible = eligible_by_stratum[stratum]
                eligible_count = len(eligible)
                if not eligible_count:
                    raise ValueError(f"insufficient C2-A-RP {stratum} tasks for worker {worker}")
                task = eligible.pop(rng_by_stratum[stratum].randrange(eligible_count))
                task_id = safe(task.get("task_id"))
                base_task_id = safe(task.get("base_task_id")) or task_id
                support_before = task_support[task_id]
                task_support[task_id] += 1
                seen_by_worker[worker].update((task_id, base_task_id))
                sequence += 1
                new_sequence += 1
                block_offset = block_index - first_block
                assignments.append({
                    "schema_version": assignment_schema,
                    "round_id": "C2-A-RP", "worker_id": worker,
                    "task_id": safe(task.get("task_id")),
                    "base_task_id": base_task_id,
                    "task_stratum": stratum, "assignment_sequence": sequence, "block_index": block_index,
                    "c2_component": "precision_completion",
                    "target_component": plan["target_component"],
                    "gap_reason": plan["gap_reason"],
                    "formal_goal": plan.get("formal_goal", ""),
                    "precision_before": plan["current_ci_half_width"],
                    "support_before": plan["current_support"],
                    "support_after": int(plan["current_support"]) + new_sequence,
                    "declared_support_after": int(plan["current_support"]) + new_sequence,
                    "selection_probability": 1 / eligible_count,
                    "conditional_inclusion_probability": 1 / eligible_count,
                    "selection_seed": selection_seed,
                    "selection_draw_id": f"{worker}:{stratum}:{sequence}",
                    "eligible_count_at_draw": eligible_count,
                    "task_support_before": support_before,
                    "task_support_after": support_before + 1,
                    "paired_block_support_before": block_index - 1,
                    "paired_block_support_after": block_index,
                    "effective_risk_slope_support_before": int(plan["current_support"]) + 2 * block_offset,
                    "effective_risk_slope_support_after": int(plan["current_support"]) + 2 * (block_offset + 1),
                    "design_manifest_sha256": manifest_sha,
                    "c2b_summary_sha256": c2b_sha,
                    "post_c2b_worker_profile_sha256": profile_sha,
                })
    return assignments


def _maximum_complete_block_count(
    precision_rows: list[dict[str, Any]],
    task_rows: list[dict[str, str]],
    *,
    history_rows: list[dict[str, Any]] | None,
    max_task_support: int,
    require_explicit_eligibility: bool,
) -> int:
    workers = [safe(row.get("worker_id")) for row in precision_rows]
    pools: list[tuple[str, str, str]] = []
    for task in task_rows:
        stratum = safe(task.get("task_stratum") or task.get("risk_bucket")).lower()
        task_id = safe(task.get("task_id"))
        eligible = task.get("c2a_rp_eligible")
        if task_id and stratum in {"ordinary", "stress"} and (
            truthy(eligible) if require_explicit_eligibility
            else eligible is None or safe(eligible) == "" or truthy(eligible)
        ):
            pools.append((task_id, safe(task.get("base_task_id")) or task_id, stratum))
    seen_by_worker: dict[str, set[str]] = defaultdict(set)
    task_support: dict[str, int] = defaultdict(int)
    for history in history_rows or []:
        worker = safe(history.get("worker_id"))
        task_id = safe(history.get("task_id"))
        seen_by_worker[worker].update(filter(None, (task_id, safe(history.get("base_task_id")))))
        if task_id and (
            not safe(history.get("round_id"))
            or safe(history.get("round_id")) == "C2-A-RP"
            or safe(history.get("schema_version")) == _c2a_rp_csv_schemas()[1]
        ):
            task_support[task_id] += 1
    edges = [
        (worker, task_id, base_task_id, stratum)
        for worker in workers
        for task_id, base_task_id, stratum in pools
        if task_id not in seen_by_worker[worker]
        and base_task_id not in seen_by_worker[worker]
        and task_support[task_id] < max_task_support
    ]
    worker_var = {worker: index for index, worker in enumerate(workers)}
    edge_var = {edge: index + len(workers) for index, edge in enumerate(edges)}
    constraints: list[tuple[dict[int, int], float, float]] = []
    for worker in workers:
        for stratum in ("ordinary", "stress"):
            row = {worker_var[worker]: -1}
            row.update({edge_var[edge]: 1 for edge in edges if edge[0] == worker and edge[3] == stratum})
            constraints.append((row, 0, 0))
    for task_id in sorted({edge[1] for edge in edges}):
        constraints.append((
            {edge_var[edge]: 1 for edge in edges if edge[1] == task_id},
            -np.inf, max_task_support - task_support[task_id],
        ))
    for worker in workers:
        for base_task_id in {edge[2] for edge in edges if edge[0] == worker}:
            same_base = [edge for edge in edges if edge[0] == worker and edge[2] == base_task_id]
            if len(same_base) > 1:
                constraints.append(({edge_var[edge]: 1 for edge in same_base}, -np.inf, 1))
    n_variables = len(workers) + len(edges)
    matrix = lil_matrix((len(constraints), n_variables), dtype=float)
    for row_index, (values, _lower, _upper) in enumerate(constraints):
        for column_index, value in values.items():
            matrix[row_index, column_index] = value
    objective = np.zeros(n_variables)
    objective[:len(workers)] = -1
    result = milp(
        objective,
        integrality=np.ones(n_variables),
        bounds=Bounds(np.zeros(n_variables), np.ones(n_variables)),
        constraints=LinearConstraint(
            matrix.tocsr(),
            np.array([lower for _row, lower, _upper in constraints]),
            np.array([upper for _row, _lower, upper in constraints]),
        ),
    )
    if not result.success:
        raise ValueError("C2-A-RP complete-block capacity matching failed")
    return int(round(-result.fun))


def build_assignments_with_capacity_fallback(
    precision_rows: list[dict[str, Any]],
    task_rows: list[dict[str, str]],
    **kwargs: Any,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Maximize complete blocks, then use the frozen seed to choose a feasible worker subset."""
    candidates = [row for row in precision_rows if int(row.get("additional_blocks", 0) or 0) > 0]
    candidates.sort(key=lambda row: safe(row.get("worker_id")))
    maximum = _maximum_complete_block_count(
        candidates, task_rows,
        history_rows=kwargs.get("history_rows"),
        max_task_support=int(kwargs.get("max_task_support", 2)),
        require_explicit_eligibility=bool(kwargs.get("require_explicit_eligibility", False)),
    )
    # ponytail: exact subset enumeration is intentionally capped for the 20-worker C2 cohort;
    # replace it with integrated matching if a future cohort makes this search large.
    if math.comb(len(candidates), maximum) > 250_000:
        raise ValueError("C2-A-RP seeded maximum-subset search exceeds the local cohort ceiling")
    combinations = list(itertools.combinations(candidates, maximum))
    random.Random(int(kwargs.get("selection_seed", 0))).shuffle(combinations)
    assignments: list[dict[str, Any]] | None = None
    selected_workers: set[str] = set()
    for subset in combinations:
        try:
            assignments = build_precision_assignments(list(subset), task_rows, **kwargs)
        except ValueError as exc:
            if str(exc).startswith("insufficient C2-A-RP "):
                continue
            raise
        selected_workers = {safe(row.get("worker_id")) for row in subset}
        break
    if assignments is None:
        raise ValueError("C2-A-RP maximum worker subset is incompatible with the frozen task draw")
    fallback_workers = [
        safe(plan.get("worker_id")) for plan in candidates
        if safe(plan.get("worker_id")) not in selected_workers
    ]
    for plan in candidates:
        if safe(plan.get("worker_id")) in fallback_workers:
            plan.update({
                "additional_blocks": 0, "ordinary_tasks": 0, "stress_tasks": 0,
                "declared_support_after": plan.get("current_support", ""),
                "gap_reason": "pool_capacity_exhausted",
                "routing_eligibility": "uncertain_fallback_global",
                "unmet_reason": "pool_capacity_exhausted",
                "terminal_state": "fallback_strong_global",
                "fallback_action": "STRONG_GLOBAL",
            })
    return assignments, fallback_workers


def materialize(
    worker_profile_csv: Path,
    design_manifest: Path,
    output_dir: Path,
    *,
    c2b_summary: Path | None = None,
    c2b_summary_sha256: str | None = None,
    task_pool_csv: Path | None = None,
    assignment_history_csv: Path | None = None,
    existing_assignment_manifest_csv: Path | None = None,
    dispatch_state_json: Path | None = None,
    dispatch_block_index: int | None = None,
    threshold_manifest: Path | None = None,
    input_status: str = "dry_run",
) -> dict[str, Any]:
    method = load_method_contract()
    precision_schema, assignment_schema = _c2a_rp_csv_schemas(method)
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
    formal_goal = safe(precision.get("formal_goal") or precision.get("target_goal") or "risk_slope_precision")
    if input_status == "formal" and formal_goal != _formal_goal():
        raise ValueError(f"C2-A-RP formal goal is not allowed:{formal_goal}")
    threshold_path = None
    threshold_sha = ""
    if threshold_manifest is not None or input_status == "formal":
        target, threshold_path, threshold_sha = _resolve_formal_threshold(
            design_manifest, manifest, precision, threshold_manifest,
        )
    else:
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
        threshold_sha=threshold_sha,
        formal=input_status == "formal",
    )
    if input_status == "formal":
        if not isinstance(c2b.get("worker_summaries"), list) or not c2b["worker_summaries"]:
            raise ValueError("C2-A-RP formal input lacks the complete C2-B worker roster")
        c2b_workers = {normalize_worker_id(row.get("worker_id")) for row in c2b["worker_summaries"] if normalize_worker_id(row.get("worker_id"))}
        plan_workers = {normalize_worker_id(row.get("worker_id")) for row in rows if normalize_worker_id(row.get("worker_id"))}
        if len(c2b_workers) != len(c2b["worker_summaries"]) or c2b_workers != plan_workers or len(plan_workers) != len(rows):
            raise ValueError("C2-A-RP precision plan does not cover the complete C2-B roster")
    history_rows = read_csv(assignment_history_csv) if assignment_history_csv else []
    existing_assignments: list[dict[str, str]] = []
    if existing_assignment_manifest_csv:
        existing_assignments = read_csv(existing_assignment_manifest_csv)
        if any(safe(row.get("schema_version")) != assignment_schema for row in existing_assignments):
            raise ValueError("C2-A-RP existing assignment manifest schema is stale")
        existing_ids = {(safe(row.get("worker_id")), safe(row.get("task_id"))) for row in existing_assignments}
        if any(not worker or not task for worker, task in existing_ids) or len(existing_ids) != len(existing_assignments):
            raise ValueError("C2-A-RP existing assignment manifest is not unique")
    history_valid = input_status != "formal"
    if assignment_history_csv:
        history_valid = input_status != "formal" or safe(expected.get("assignment_history_csv")) == sha256_file(assignment_history_csv)
    dispatch_state_workers: set[str] = set()
    if dispatch_state_json:
        state = json.loads(dispatch_state_json.read_text(encoding="utf-8"))
        if state.get("schema_version") != "c2a_rp_closeout_v2" or state.get("method_contract_sha256") != method_sha:
            raise ValueError("C2-A-RP dispatch state is stale")
        outcomes = state.get("worker_outcomes")
        if not isinstance(outcomes, list):
            raise ValueError("C2-A-RP dispatch state lacks worker outcomes")
        dispatch_state_workers = {
            normalize_worker_id(row.get("worker_id", ""))
            for row in outcomes
            if row.get("terminal_state") in {"target_met", "fallback_strong_global", "not_evaluable"}
        }
    if input_status == "formal" and (not assignment_history_csv or not history_valid):
        raise ValueError("stale_or_unbound_c2a_rp_task_pool")
    if input_status == "formal":
        if max_blocks > 0:
            if dispatch_block_index is None:
                dispatch_block_index = 1
            if dispatch_block_index < 1 or dispatch_block_index > contract_max_blocks:
                raise ValueError("C2-A-RP dispatch block is outside the normative cap")
        else:
            dispatch_block_index = None
        if dispatch_block_index is not None and dispatch_block_index > 1 and not existing_assignment_manifest_csv:
            raise ValueError("C2-A-RP later dispatch requires the prior assignment manifest")
        if existing_assignments:
            existing_max = max(int(row.get("block_index", 0) or 0) for row in existing_assignments)
            if dispatch_block_index is None or existing_max != dispatch_block_index - 1:
                raise ValueError("C2-A-RP dispatch is not append-only by block")
            if any(int(row.get("block_index", 0) or 0) >= dispatch_block_index for row in existing_assignments):
                raise ValueError("C2-A-RP existing assignment contains a future block")
    dispatch_history_rows = [*history_rows, *existing_assignments]
    dispatch_rows = [
        row for row in rows
        if (input_status != "formal" or int(row.get("additional_blocks", 0) or 0) > 0)
        and (not dispatch_state_workers or normalize_worker_id(row.get("worker_id", "")) not in dispatch_state_workers)
    ]
    assignments: list[dict[str, Any]] = []
    capacity_fallback_workers: list[str] = []
    task_pool_valid = input_status != "formal"
    if task_pool_csv:
        expected_task_sha = safe(expected.get("c2a_task_pool_csv"))
        task_pool_valid = input_status != "formal" or expected_task_sha == sha256_file(task_pool_csv)
        if task_pool_valid:
            assignments, capacity_fallback_workers = build_assignments_with_capacity_fallback(
                dispatch_rows, read_csv(task_pool_csv), manifest_sha=manifest_sha,
                c2b_sha=c2b_sha, profile_sha=actual_profile_sha,
                history_rows=dispatch_history_rows,
                max_task_support=int(precision.get("max_task_support", 2)),
                selection_seed=int(precision.get("selection_seed", 0)),
                require_explicit_eligibility=input_status == "formal",
                formal=input_status == "formal",
                # An explicit block is also useful for a non-formal rehearsal:
                # it must exercise the same one-block operator path without
                # planning future tasks that have not yet been re-estimated.
                dispatch_block_index=dispatch_block_index,
            )
    if existing_assignments:
        assignments = [*existing_assignments, *assignments]
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
        "formal_goal": formal_goal,
        "precision_plan_schema_version": precision_schema,
        "assignment_manifest_schema_version": assignment_schema,
        "diagnostic_goals_not_dispatchable": ["top_k_boundary_precision", "component_eligibility_precision"],
        "interval_definition": {
            "level": 0.95,
            "multiplier": 1.96,
            "formula_id": "normal_95_max_unified_slope_sd",
            "reestimate_after_each_block": True,
        },
        "threshold_manifest_path": str(threshold_path or ""),
        "threshold_manifest_sha256": threshold_sha,
        "dispatch_block_index": dispatch_block_index or 0,
        "dispatch_mode": "append_only_sequential" if input_status == "formal" else "planned",
        "existing_assignment_manifest_path": str(existing_assignment_manifest_csv or ""),
        "existing_assignment_manifest_sha256": sha256_file(existing_assignment_manifest_csv) if existing_assignment_manifest_csv else "",
        "dispatch_state_path": str(dispatch_state_json or ""),
        "dispatch_state_sha256": sha256_file(dispatch_state_json) if dispatch_state_json else "",
        "n_workers": len(rows),
        "n_workers_with_precision_additions": sum(int(row["additional_blocks"]) > 0 for row in dispatch_rows),
        "n_workers_planned_with_precision_additions": sum(int(row["additional_blocks"]) > 0 for row in rows),
        "n_workers_unmet_at_cap": sum(bool(row["unmet_reason"]) for row in rows),
        "n_workers_capacity_fallback": len(capacity_fallback_workers),
        "capacity_fallback_workers": capacity_fallback_workers,
        "maximum_complete_blocks": len({safe(row.get("worker_id")) for row in assignments}),
        "capacity_selection_algorithm": "maximum_complete_blocks_seeded_feasible_subset",
        "capacity_selection_seed": int(precision.get("selection_seed", 0)),
        "capacity_selection_uses_performance_fields": False,
        "n_assignments": len(assignments),
        "c2a_rp_ready": binding_valid and c2b_valid and task_pool_valid and history_valid and bool(rows) and (formal_goal == _formal_goal() if input_status == "formal" else True),
        "candidate_only": input_status != "formal",
        "launch_ready": input_status == "formal" and binding_valid and c2b_valid and task_pool_valid and history_valid and bool(rows) and formal_goal == _formal_goal(),
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
    parser.add_argument("--existing-assignment-manifest-csv", type=Path)
    parser.add_argument("--dispatch-state-json", type=Path)
    parser.add_argument("--dispatch-block-index", type=int)
    parser.add_argument("--threshold-manifest", type=Path)
    parser.add_argument("--input-status", choices=("dry_run", "formal"), default="dry_run")
    args = parser.parse_args(argv)
    try:
        result = materialize(
            args.worker_profile_csv, args.design_manifest, args.output_dir,
            c2b_summary=args.c2b_summary, c2b_summary_sha256=args.c2b_summary_sha256,
            task_pool_csv=args.task_pool_csv, input_status=args.input_status,
            assignment_history_csv=args.assignment_history_csv,
            existing_assignment_manifest_csv=args.existing_assignment_manifest_csv,
            dispatch_state_json=args.dispatch_state_json,
            dispatch_block_index=args.dispatch_block_index,
            threshold_manifest=args.threshold_manifest,
        )
    except (OSError, KeyError, TypeError, ValueError) as exc:
        if args.input_status == "formal":
            blocked = _write_blocked_summary(
                args.output_dir, f"{type(exc).__name__}:{exc}",
                {
                    "worker_profile_csv": sha256_file(args.worker_profile_csv),
                    "design_manifest": sha256_file(args.design_manifest),
                    "c2b_summary": sha256_file(args.c2b_summary),
                    "task_pool_csv": sha256_file(args.task_pool_csv),
                    "assignment_history_csv": sha256_file(args.assignment_history_csv),
                    "threshold_manifest": sha256_file(args.threshold_manifest),
                    "declared_c2b_summary": args.c2b_summary_sha256 or "",
                },
            )
            print(json.dumps({"formal_ready": False, "launch_ready": False, "blocked_summary": str(blocked), "reason_code": str(exc)}, ensure_ascii=False), file=sys.stderr)
            return 2
        raise
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
