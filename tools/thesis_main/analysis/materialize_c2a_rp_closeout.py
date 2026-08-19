"""Materialize the formal, SHA-bound C2-A-RP closeout."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from tools.thesis_main.analysis.c1_materialize_c2_gap_audits import _c2a_rp_csv_schemas, _c2a_rp_limits
from tools.thesis_main.analysis.build_c2_assignment_manifest_from_c1_gaps import _resolve_fitted_worker_slope_distribution
from tools.thesis_main.analysis.materialize_c1_c2_design_parameters import _fit_crossed_model
from tools.thesis_main.analysis.materialize_c2b_closeout import (
    NONCOMPLETED_TERMINAL_STATUSES,
    _default_missing_reason,
    _missing_dispositions,
)
from tools.thesis_main.analysis.paper_a_contracts import METHOD_CONTRACT, load_method_contract, sha256_file
from tools.thesis_main.analysis.worker_identity import normalize_worker_id


ROOT = METHOD_CONTRACT.parents[2]


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _fieldnames(path: Path) -> set[str]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return set(csv.DictReader(stream).fieldnames or ())


def _validate_csv_schema(path: Path, rows: list[dict[str, str]], expected: str, required: set[str]) -> None:
    fields = _fieldnames(path)
    if not required.issubset(fields):
        raise ValueError(f"C2-A-RP CSV schema is incomplete:{path.name}")
    if any(_text(row.get("schema_version")) != expected for row in rows):
        raise ValueError(f"C2-A-RP CSV schema is stale:{path.name}")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _truth(value: Any) -> bool:
    return _text(value).lower() in {"true", "1", "yes", "y"}


def _int(row: dict[str, str], field: str) -> int:
    try:
        value = int(_text(row.get(field)))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"C2-A-RP missing integer field:{field}") from exc
    return value


def _float(row: dict[str, Any], *fields: str) -> float | None:
    for field in fields:
        try:
            value = float(row.get(field, ""))
        except (TypeError, ValueError):
            continue
        if value == value and abs(value) != float("inf"):
            return value
    return None


def _risk_slope_evidence(path: Path, workers: set[str]) -> tuple[list[dict[str, Any]], set[tuple[str, str]]]:
    """Return only canonical, valid, risk-slope-eligible rows and their task keys."""
    rows = _rows(path)
    seen_annotations: set[str] = set()
    records: list[dict[str, Any]] = []
    keys: set[tuple[str, str]] = set()
    for row in rows:
        worker = normalize_worker_id(row.get("worker_id", ""))
        annotation = _text(row.get("canonical_annotation_id") or row.get("annotation_id"))
        task = _text(row.get("task_id") or row.get("base_task_id"))
        if not worker or worker not in workers or not annotation or not task:
            continue
        if annotation in seen_annotations:
            raise ValueError("C2-A-RP risk-slope evidence has duplicate canonical annotation identity")
        seen_annotations.add(annotation)
        if not _truth(row.get("formal_assignment_eligible")) or not _truth(row.get("routing_feature_analysis_eligible")):
            continue
        valid_token = row.get("canonical_valid", row.get("valid", row.get("structurally_valid", True)))
        if not _truth(valid_token):
            continue
        risk = _float(row, "risk_design_score_A", "risk")
        outcome = _float(row, "Q_GT_raw", "quality", "outcome")
        building = _text(row.get("building_id") or row.get("building"))
        base_task = _text(row.get("base_task_id") or task)
        if risk is None or outcome is None or not building:
            raise ValueError("C2-A-RP risk-slope evidence lacks model fields for an eligible row")
        records.append({
            "worker_id": worker,
            "task_id": task,
            "base_task_id": base_task,
            "building_id": building,
            "risk": risk,
            "quality": outcome,
            "task_stratum": _text(row.get("task_stratum") or row.get("risk_bucket")).lower(),
        })
        keys.add((worker, task))
    return records, keys


def _actual_worker_slope(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    model = _fit_crossed_model(records)
    slopes = model.get("worker_slopes", {}) if model.get("status") == "estimated" else {}
    ses = model.get("worker_slope_ses", {}) if model.get("status") == "estimated" else {}
    out: dict[str, dict[str, Any]] = {}
    for worker in sorted({str(row["worker_id"]) for row in records}):
        estimate = _float({"value": slopes.get(worker)}, "value")
        se = _float({"value": ses.get(worker)}, "value")
        distribution = _resolve_fitted_worker_slope_distribution(
            model, worker, sum(row["worker_id"] == worker for row in records),
        ) if model.get("status") == "estimated" else {"valid": False}
        unified_sd = float(distribution["total_sd"]) if distribution.get("valid") else None
        out[worker] = {
            "estimate": estimate,
            "se": se,
            "unified_slope_sd": unified_sd,
            "ci_half_width": 1.96 * unified_sd if unified_sd is not None else None,
            "support": sum(row["worker_id"] == worker for row in records),
            "model_status": model.get("status", "not_evaluable"),
            "model_form": model.get("slope_model_form", ""),
        }
    return out


def _profile_terminal(row: dict[str, str]) -> str:
    return next((_text(row.get(field)) for field in ("terminal_status", "completion_status", "final_completion_disposition") if _text(row.get(field))), "")


def _dependency(role: str, path: Path) -> dict[str, str]:
    return {"role": role, "path": str(path.resolve()), "sha256": sha256_file(path)}


def _safe_sha(path: Path | None) -> str:
    try:
        return sha256_file(path) if path is not None and path.is_file() else ""
    except OSError:
        return ""


def _validate_historical_c2b_acceptance(method: dict[str, Any], c2b_closeout: Path) -> Path:
    binding = method.get("c2b_historical_evidence_acceptance", {})
    path = Path(_text(binding.get("path")))
    path = path if path.is_absolute() else ROOT / path
    if not path.is_file() or sha256_file(path) != _text(binding.get("sha256")):
        raise ValueError("historical C2-B acceptance is missing or stale")
    payload = json.loads(path.read_text(encoding="utf-8"))
    source = payload.get("source_c2b", {})
    if (payload.get("schema_version") != "paper_a_c2b_historical_evidence_acceptance_v1"
            or payload.get("status") != "normative"
            or payload.get("collection_closed") is not True
            or payload.get("outcome_reopening_allowed") is not False
            or not {"C2A_RP_closeout", "final_pooled_profile"}.issubset(payload.get("accepted_for", []))
            or source.get("candidate_only") is not True
            or sha256_file(c2b_closeout) != _text(source.get("sha256"))):
        raise ValueError("historical C2-B acceptance does not authorize this closeout")
    for role in ("corrected_reestimate", "reference_review"):
        item = payload.get(role, {})
        dependency = Path(_text(item.get("path")))
        dependency = dependency if dependency.is_absolute() else ROOT / dependency
        if not dependency.is_file() or sha256_file(dependency) != _text(item.get("sha256")):
            raise ValueError(f"historical C2-B acceptance {role} dependency is stale")
    return path


def _historical_c2b_worker_summaries(acceptance_path: Path) -> list[dict[str, str]]:
    acceptance = json.loads(acceptance_path.read_text(encoding="utf-8"))
    item = acceptance.get("corrected_reestimate", {})
    source = Path(_text(item.get("path")))
    source = source if source.is_absolute() else ROOT / source
    if not source.is_file() or sha256_file(source) != _text(item.get("sha256")):
        raise ValueError("historical C2-B corrected reestimate roster is missing or stale")
    payload = json.loads(source.read_text(encoding="utf-8"))
    workers = payload.get("workers")
    if not isinstance(workers, dict) or not workers:
        raise ValueError("historical C2-B corrected reestimate lacks worker roster")
    return [{"worker_id": normalize_worker_id(worker)} for worker in workers if normalize_worker_id(worker)]


def _write_blocked_summary(output_json: Path, reason: str, hashes: dict[str, str] | None = None) -> Path:
    method = load_method_contract()
    path = output_json.with_name("c2a_rp_closeout_blocked_summary.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "schema_version": "c2a_rp_blocked_summary_v1",
        "artifact_role": "C2A_RP_BLOCKED_SUMMARY",
        "method_contract_version": method["contract_version"],
        "method_contract_sha256": sha256_file(METHOD_CONTRACT),
        "formal_ready": False,
        "C2_A_RP_CLOSED": False,
        "reason_code": reason,
        "input_hashes": hashes or {},
    }, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def materialize(
    precision_plan_csv: Path,
    assignment_manifest_csv: Path,
    assignment_history_csv: Path,
    submissions_csv: Path,
    post_c2a_profile_csv: Path,
    c2b_closeout: Path,
    output_json: Path,
    *,
    terminal_disposition_csv: Path | None = None,
    risk_slope_evidence_csv: Path | None = None,
    threshold_manifest: Path | None = None,
    stage_terminal_declaration: Path | None = None,
) -> dict[str, Any]:
    method = load_method_contract()
    max_tasks, max_blocks, method_sha = _c2a_rp_limits()
    precision_schema, assignment_schema = _c2a_rp_csv_schemas(method)
    c2b = json.loads(c2b_closeout.read_text(encoding="utf-8"))
    current_c2b = (c2b.get("schema_version") == "c2b_closeout_v2"
                   and c2b.get("c2b_closeout_ready") is True
                   and c2b.get("formal_ready") is True
                   and c2b.get("method_contract_version") == method["contract_version"]
                   and c2b.get("method_contract_sha256") == method_sha)
    historical_acceptance = None
    if current_c2b:
        if (c2b.get("reference_conflict_review_closed") is not True
                or not _text(c2b.get("reference_conflict_review_record_sha256"))):
            raise ValueError("C2-A-RP requires closed reference conflict review")
    else:
        historical_acceptance = _validate_historical_c2b_acceptance(method, c2b_closeout)

    plan = _rows(precision_plan_csv)
    assignments = _rows(assignment_manifest_csv)
    history = _rows(assignment_history_csv)
    submissions = _rows(submissions_csv)
    profiles = _rows(post_c2a_profile_csv)
    _validate_csv_schema(
        precision_plan_csv, plan, precision_schema,
        {"schema_version", "worker_id", "target_component", "gap_reason", "formal_goal", "additional_blocks", "ordinary_tasks", "stress_tasks", "interval_level", "target_ci_half_width", "threshold_manifest_sha256"},
    )
    _validate_csv_schema(
        assignment_manifest_csv, assignments, assignment_schema,
        {"schema_version", "worker_id", "task_id", "base_task_id", "task_stratum", "block_index", "target_component", "gap_reason", "formal_goal"},
    )
    profile_by_worker = {normalize_worker_id(row.get("worker_id", "")): row for row in profiles}
    if len(profile_by_worker) != len(profiles):
        raise ValueError("C2-A-RP post-profile worker identities are not unique")

    plan_by_worker: dict[str, dict[str, str]] = {}
    threshold_shas: set[str] = set()
    threshold_targets: set[float] = set()
    for row in plan:
        worker = normalize_worker_id(row.get("worker_id", ""))
        if not worker or worker in plan_by_worker:
            raise ValueError("C2-A-RP precision plan worker identities are not unique")
        blocks = _int(row, "additional_blocks")
        ordinary = _int(row, "ordinary_tasks")
        stress = _int(row, "stress_tasks")
        if _text(row.get("target_component")) != "risk_slope" or _text(row.get("formal_goal")) != method["c2"]["c2_a_rp_formal_target"]:
            raise ValueError("C2-A-RP formal closeout target is not risk_slope_precision")
        if _text(row.get("ci_method")) != "normal_95_max_unified_slope_sd":
            raise ValueError("C2-A-RP closeout interval method is not the frozen normal interval")
        try:
            interval_level = float(row.get("interval_level", ""))
        except (TypeError, ValueError) as exc:
            raise ValueError("C2-A-RP closeout interval level is missing") from exc
        if interval_level != float(method["c2"]["c2_a_rp_interval"]["level"]):
            raise ValueError("C2-A-RP closeout interval level is not the frozen 95% level")
        threshold_sha = _text(row.get("threshold_manifest_sha256"))
        if not threshold_sha:
            raise ValueError("C2-A-RP closeout lacks frozen threshold manifest SHA")
        threshold_shas.add(threshold_sha)
        target_value = _float(row, "target_ci_half_width")
        if target_value is None:
            raise ValueError("C2-A-RP closeout lacks a target interval width")
        threshold_targets.add(target_value)
        if not 0 <= blocks <= max_blocks or ordinary != blocks or stress != blocks or 2 * blocks > max_tasks:
            raise ValueError("C2-A-RP precision plan exceeds the normative cap")
        plan_by_worker[worker] = row
        if worker not in profile_by_worker:
            raise ValueError(f"C2-A-RP post-profile is missing worker:{worker}")

    if len(threshold_shas) != 1 or len(threshold_targets) != 1:
        raise ValueError("C2-A-RP precision plan has inconsistent threshold binding")
    threshold_sha = next(iter(threshold_shas))
    if threshold_manifest is None:
        raise ValueError("C2-A-RP closeout requires the frozen threshold manifest")
    threshold_path = threshold_manifest
    if not threshold_path.is_file() or sha256_file(threshold_path) != threshold_sha:
        raise ValueError("C2-A-RP closeout threshold manifest is missing or stale")
    payload = json.loads(threshold_path.read_text(encoding="utf-8"))
    if payload.get("status") != "approved" or payload.get("formal_selection_allowed") is not True:
        raise ValueError("C2-A-RP closeout threshold manifest is not formally approved")
    formula_id = payload.get("derivation", {}).get("formula_ids", {}).get("risk_slope_ci_half_width")
    if formula_id != "normal_95_max_unified_slope_sd":
        raise ValueError("C2-A-RP closeout threshold manifest uses an unsupported risk-slope formula")
    try:
        target_value = float(payload["thresholds"]["risk_slope_ci_half_width"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("C2-A-RP closeout threshold manifest lacks risk-slope target") from exc
    if target_value != next(iter(threshold_targets)):
        raise ValueError("C2-A-RP closeout target differs from the threshold manifest")

    c2b_worker_summaries = c2b.get("worker_summaries")
    if (not isinstance(c2b_worker_summaries, list) or not c2b_worker_summaries) and historical_acceptance:
        c2b_worker_summaries = _historical_c2b_worker_summaries(historical_acceptance)
    if not isinstance(c2b_worker_summaries, list) or not c2b_worker_summaries:
        raise ValueError("C2-A-RP requires the complete C2-B worker roster")
    if any(not isinstance(row, dict) for row in c2b_worker_summaries):
        raise ValueError("C2-A-RP C2-B worker roster contains a non-object row")
    c2b_workers = {
        normalize_worker_id(row.get("worker_id", ""))
        for row in c2b_worker_summaries
        if normalize_worker_id(row.get("worker_id", ""))
    }
    plan_workers = set(plan_by_worker)
    if len(c2b_workers) != len(c2b_worker_summaries) or set(profile_by_worker) != plan_workers:
        raise ValueError("C2-A-RP precision plan/profile does not cover the complete C2-B roster")
    if historical_acceptance:
        if not c2b_workers.issubset(plan_workers):
            raise ValueError("historical C2-B fitted roster is outside the precision plan")
        for worker in plan_workers - c2b_workers:
            row = plan_by_worker[worker]
            zero_block_target_met = (_int(row, "additional_blocks") == 0
                                     and _truth(row.get("precision_target_met")))
            zero_block_not_evaluable = (
                _int(row, "additional_blocks") == 0
                and _text(row.get("terminal_state")) == "not_evaluable"
                and _text(row.get("routing_eligibility")) == "not_evaluable"
                and _text(row.get("fallback_action")) == "STRONG_GLOBAL"
            )
            if not (zero_block_target_met or zero_block_not_evaluable):
                raise ValueError("historical C2-B roster omission lacks a frozen zero-block terminal state")
    elif c2b_workers != plan_workers:
        raise ValueError("C2-A-RP precision plan does not match the current C2-B roster")

    history_seen: set[tuple[str, str, str]] = set()
    history_worker_tasks: set[tuple[str, str]] = set()
    history_worker_bases: set[tuple[str, str]] = set()
    history_task_support: Counter[str] = Counter()
    block1_task_support: Counter[str] = Counter()
    for row in history:
        worker = normalize_worker_id(row.get("worker_id", ""))
        task = _text(row.get("task_id"))
        base = _text(row.get("base_task_id"))
        if not worker or not task or not base:
            raise ValueError("C2-A-RP assignment history has incomplete identity")
        key = (worker, task, base)
        if key in history_seen:
            raise ValueError("C2-A-RP assignment history contains duplicate task identity")
        if (worker, task) in history_worker_tasks or (worker, base) in history_worker_bases:
            raise ValueError("C2-A-RP assignment history repeats a worker task/base identity")
        history_seen.add(key)
        history_worker_tasks.add((worker, task))
        history_worker_bases.add((worker, base))
        round_id = _text(row.get("round_id"))
        if (not round_id or round_id == "C2-A-RP"
                or _text(row.get("schema_version")) == assignment_schema):
            history_task_support[task] += 1
            if not _text(row.get("block_index")) or _int(row, "block_index") == 1:
                block1_task_support[task] += 1
    block1_cap = int(method["c2"]["c2_a_rp_task_support_cap"]["block1_historical"])
    later_cap = int(method["c2"]["c2_a_rp_task_support_cap"]["blocks2_to_5"])
    if any(count > block1_cap for count in block1_task_support.values()):
        raise ValueError("C2-A-RP assignment history exceeds the frozen task support cap")

    assignment_keys: set[tuple[str, str]] = set()
    assignment_bases: set[tuple[str, str]] = set()
    assignment_task_support: Counter[str] = Counter(history_task_support)
    assignment_by_worker: dict[str, list[dict[str, str]]] = {}
    assignment_strata: dict[tuple[str, int], Counter[str]] = {}
    for row in assignments:
        worker = normalize_worker_id(row.get("worker_id", ""))
        task = _text(row.get("task_id"))
        base = _text(row.get("base_task_id")) or task
        stratum = _text(row.get("task_stratum") or row.get("risk_bucket")).lower()
        if not worker or not task or stratum not in {"ordinary", "stress"}:
            raise ValueError("C2-A-RP assignment has incomplete identity or stratum")
        if worker not in plan_by_worker:
            raise ValueError("C2-A-RP assignment references a worker outside the precision plan")
        block_index = _int(row, "block_index")
        if block_index < 1 or block_index > max_blocks:
            raise ValueError("C2-A-RP assignment block index is outside the normative cap")
        if (_text(row.get("target_component")) != "risk_slope"
                or _text(row.get("formal_goal")) != method["c2"]["c2_a_rp_formal_target"]):
            raise ValueError("C2-A-RP assignment target contract is invalid")
        key = (worker, task)
        base_key = (worker, base)
        if key in assignment_keys or base_key in assignment_bases:
            raise ValueError("C2-A-RP task_id/base_task_id is repeated for a worker")
        if (worker, task) in history_worker_tasks or (worker, base) in history_worker_bases:
            raise ValueError("C2-A-RP assignment repeats a task already seen by the worker")
        assignment_keys.add(key)
        assignment_bases.add(base_key)
        assignment_task_support[task] += 1
        if block_index == 1:
            block1_task_support[task] += 1
        declared_after = _text(row.get("task_support_after"))
        row_cap = block1_cap if block_index == 1 else later_cap
        if declared_after and _int(row, "task_support_after") > row_cap:
            raise ValueError("C2-A-RP declared task support exceeds the frozen cap")
        assignment_by_worker.setdefault(worker, []).append(row)
        assignment_strata.setdefault((worker, block_index), Counter())[stratum] += 1

    if any(count > block1_cap for count in block1_task_support.values()) or any(count > later_cap for count in assignment_task_support.values()):
        raise ValueError("C2-A-RP task support exceeds the block-specific frozen cap")
    current_block = max((_int(row, "block_index") for row in assignments), default=0)
    expected_workers = {worker for worker, row in plan_by_worker.items() if _int(row, "additional_blocks")}
    terminal_declaration: dict[str, Any] | None = None
    if stage_terminal_declaration is not None:
        terminal_declaration = json.loads(stage_terminal_declaration.read_text(encoding="utf-8"))
        if (terminal_declaration.get("schema_version") != "c2a_rp_stage_terminal_declaration_v1"
                or terminal_declaration.get("status") != "authorized"
                or terminal_declaration.get("stage_closed") is not True
                or terminal_declaration.get("future_blocks_allowed") is not False
                or int(terminal_declaration.get("last_completed_block", -1)) != current_block
                or terminal_declaration.get("fallback_action") != "STRONG_GLOBAL"):
            raise ValueError("C2-A-RP stage terminal declaration is invalid")
    current_block_workers = {
        normalize_worker_id(row.get("worker_id", ""))
        for row in assignments
        if _int(row, "block_index") == current_block
    }
    if expected_workers != current_block_workers:
        raise ValueError("C2-A-RP current precision plan does not match the current block roster")
    dispatched_blocks_by_worker = {
        worker: max((_int(item, "block_index") for item in rows), default=0)
        for worker, rows in assignment_by_worker.items()
    }
    for worker, row in plan_by_worker.items():
        rows = assignment_by_worker.get(worker, [])
        planned_blocks = _int(row, "additional_blocks")
        dispatched_blocks = dispatched_blocks_by_worker.get(worker, 0)
        if planned_blocks and (not rows or dispatched_blocks < 1 or dispatched_blocks > max_blocks):
            raise ValueError(f"C2-A-RP assignment block sequence is incomplete:{worker}")
        expected = 2 * dispatched_blocks
        if len(rows) != expected:
            raise ValueError(f"C2-A-RP assignment count mismatch:{worker}")
        counts = Counter(_text(item.get("task_stratum") or item.get("risk_bucket")).lower() for item in rows)
        if counts["ordinary"] != counts["stress"] or counts["ordinary"] != dispatched_blocks:
            raise ValueError(f"C2-A-RP ordinary/stress pairing mismatch:{worker}")
        for block_index in range(1, dispatched_blocks + 1):
            block_counts = assignment_strata.get((worker, block_index), Counter())
            if block_counts["ordinary"] != 1 or block_counts["stress"] != 1:
                raise ValueError(f"C2-A-RP block pairing mismatch:{worker}:{block_index}")

    submitted = [(normalize_worker_id(row.get("worker_id", "")), _text(row.get("task_id"))) for row in submissions]
    if any(key not in assignment_keys for key in submitted):
        raise ValueError("C2-A-RP contains an unassigned submission")
    if len(submitted) != len(set(submitted)):
        raise ValueError("C2-A-RP duplicate/revision disposition is unresolved")
    submitted_set = set(submitted)
    missing = assignment_keys - submitted_set
    exact_dispositions, worker_dispositions = _missing_dispositions(terminal_disposition_csv)
    for key in exact_dispositions:
        if key not in missing:
            raise ValueError("C2-A-RP terminal disposition does not identify a missing task")
    assignment_workers = {worker for worker, _task in assignment_keys}
    if any(worker not in assignment_workers for worker in worker_dispositions):
        raise ValueError("C2-A-RP terminal disposition references an unknown worker")
    missing_dispositions: dict[tuple[str, str], dict[str, str]] = {}
    for worker, task in sorted(missing):
        disposition = exact_dispositions.get((worker, task)) or worker_dispositions.get(worker)
        if disposition is None:
            status = _profile_terminal(profile_by_worker[worker])
            if status in NONCOMPLETED_TERMINAL_STATUSES:
                disposition = {"terminal_status": status, "missing_reason": ""}
        if disposition is None or disposition.get("terminal_status") not in NONCOMPLETED_TERMINAL_STATUSES:
            raise ValueError("C2-A-RP missing task has no valid terminal disposition")
        status = disposition["terminal_status"]
        missing_dispositions[(worker, task)] = {
            "terminal_status": status,
            "missing_reason": disposition.get("missing_reason") or _default_missing_reason(status),
        }

    plan_workers = set(plan_by_worker)
    evidence_records: list[dict[str, Any]] = []
    evidence_keys: set[tuple[str, str]] = set()
    block_reestimates: dict[int, dict[str, dict[str, Any]]] = {}
    complete_nonzero_workers = [
        worker for worker, row in plan_by_worker.items()
        if _int(row, "additional_blocks") > 0
        and not any((worker, _text(item.get("task_id"))) in missing for item in assignment_by_worker.get(worker, []))
    ]
    if complete_nonzero_workers:
        if risk_slope_evidence_csv is None:
            raise ValueError("C2-A-RP requires canonical risk-slope evidence for nonzero assignments")
        evidence_records, evidence_keys = _risk_slope_evidence(risk_slope_evidence_csv, plan_workers)
        evidence_records = [
            row for row in evidence_records
            if (row["worker_id"], row["task_id"]) not in assignment_keys
            or (row["worker_id"], row["task_id"]) in submitted_set
        ]
        evidence_keys = {(row["worker_id"], row["task_id"]) for row in evidence_records}

        # Fit the same crossed model after each completed block so the stop
        # decision is based on observed canonical evidence, not projection.
        max_observed_block = max(
            (_int(row, "block_index") for row in assignments if _text(row.get("block_index"))),
            default=0,
        )
        c2a_task_blocks = {
            (normalize_worker_id(row.get("worker_id", "")), _text(row.get("task_id"))): _int(row, "block_index")
            for row in assignments
        }
        for block_index in range(1, max_observed_block + 1):
            cumulative = [
                row for row in evidence_records
                if c2a_task_blocks.get((row["worker_id"], row["task_id"]), 0) <= block_index
            ]
            block_reestimates[block_index] = _actual_worker_slope(cumulative)
    elif risk_slope_evidence_csv is not None:
        evidence_records, evidence_keys = _risk_slope_evidence(risk_slope_evidence_csv, plan_workers)
        evidence_records = [
            row for row in evidence_records
            if (row["worker_id"], row["task_id"]) not in assignment_keys
            or (row["worker_id"], row["task_id"]) in submitted_set
        ]
        evidence_keys = {(row["worker_id"], row["task_id"]) for row in evidence_records}
    worker_outcomes: list[dict[str, Any]] = []
    support_discrepancies: list[dict[str, Any]] = []
    n_workers_target_met = 0
    n_workers_fallback = 0
    n_workers_not_evaluable = 0
    n_workers_pending = 0
    for worker in sorted(plan_workers):
        plan_row = plan_by_worker[worker]
        profile = profile_by_worker[worker]
        planned_blocks = _int(plan_row, "additional_blocks")
        blocks = dispatched_blocks_by_worker.get(worker, 0)
        target = _float(plan_row, "target_ci_half_width")
        declared_support = _float(plan_row, "declared_support_after", "support_after", "current_support")
        assigned_rows = assignment_by_worker.get(worker, [])
        assigned_keys = {(worker, _text(row.get("task_id"))) for row in assigned_rows}
        missing_worker_tasks = {key for key in missing if key[0] == worker}
        current_half_width = _float(profile, "risk_slope_ci_half_width", "ci_half_width", "r_u_h")
        if current_half_width is None:
            current_se = _float(profile, "risk_slope_se")
            current_half_width = 1.96 * current_se if current_se is not None else _float(plan_row, "current_ci_half_width")
        observed_rows = [row for row in evidence_records if row["worker_id"] == worker]
        observed_support = len(observed_rows)
        observed_ordinary = sum(row["worker_id"] == worker and row["task_stratum"] == "ordinary" for row in observed_rows)
        observed_stress = sum(row["worker_id"] == worker and row["task_stratum"] == "stress" for row in observed_rows)
        state = "not_evaluable"
        reason = ""
        estimate = se = ci_half_width = None
        reestimate_history: list[dict[str, Any]] = []
        if blocks == 0:
            withdrawn_workers = {
                normalize_worker_id(value) for value in (terminal_declaration or {}).get("withdrawn_worker_ids", [])
            }
            if worker in withdrawn_workers:
                reason = "researcher_confirmed_withdrawal_not_evaluable"
            elif _truth(plan_row.get("precision_target_met")) and current_half_width is not None and target is not None and current_half_width <= target:
                state = "target_met"
                n_workers_target_met += 1
            else:
                reason = _text(plan_row.get("unmet_reason")) or "zero_block_not_evaluable"
        elif missing_worker_tasks:
            reason = "incomplete_block_terminalized"
        elif any(key not in evidence_keys for key in assigned_keys):
            reason = "submitted_task_not_canonical_risk_eligible"
        else:
            actual = block_reestimates.get(blocks, {}).get(worker, {})
            estimate, se, ci_half_width = actual.get("estimate"), actual.get("se"), actual.get("ci_half_width")
            for block_index in range(1, blocks + 1):
                block = block_reestimates.get(block_index, {}).get(worker, {})
                reestimate_history.append({
                    "block_index": block_index,
                    "estimate": block.get("estimate"),
                    "se": block.get("se"),
                    "ci_half_width": block.get("ci_half_width"),
                    "support": block.get("support", 0),
                    "model_status": block.get("model_status", "not_evaluable"),
                })
            if ci_half_width is not None and target is not None and ci_half_width <= target:
                state = "target_met"
                n_workers_target_met += 1
            else:
                reason = "target_not_met_at_actual_reestimate" if ci_half_width is not None else "risk_slope_reestimate_not_evaluable"
                if blocks < max_blocks and ci_half_width is not None:
                    state = "awaiting_next_block"
                    n_workers_pending += 1
        if state == "awaiting_next_block" and terminal_declaration is not None:
            state = "fallback_strong_global"
            n_workers_pending -= 1
            reason = "researcher_declared_terminal_after_completed_block"
        if state != "target_met" and state != "awaiting_next_block":
            if reason in {"incomplete_block_terminalized", "risk_slope_reestimate_not_evaluable", "zero_block_not_evaluable"} or "not_evaluable" in reason or "terminalized" in reason:
                state = "not_evaluable"
                n_workers_not_evaluable += 1
            else:
                state = "fallback_strong_global"
                n_workers_fallback += 1
        observed_support_value = observed_support if blocks else _float(profile, "risk_slope_support", "support")
        if declared_support is not None and observed_support_value is not None and blocks:
            if int(declared_support) != int(observed_support_value):
                support_discrepancies.append({"worker_id": worker, "declared_support_after": int(declared_support), "observed_support_after": int(observed_support_value)})
        worker_outcomes.append({
            "worker_id": worker,
            "additional_blocks": blocks,
            "blocks_completed": blocks,
            "planned_additional_blocks": planned_blocks,
            "authorized_blocks_in_current_plan": planned_blocks,
            "max_total_blocks": max_blocks,
            "terminal_state": state,
            "target_component": "risk_slope",
            "target_ci_half_width": target,
            "current_ci_half_width": current_half_width,
            "observed_ci_half_width": ci_half_width,
            "risk_slope_estimate": estimate,
            "risk_slope_se": se,
            "declared_support_after": declared_support,
            "observed_support_after": observed_support_value,
            "ordinary_support_observed_after": observed_ordinary,
            "stress_support_observed_after": observed_stress,
            "risk_adjustment": 0 if state != "target_met" else _text(profile.get("risk_adjustment")),
            "fallback_action": "STRONG_GLOBAL" if state == "fallback_strong_global" else "",
            "reason": reason,
            "submitted_task_count": sum(key not in missing for key in assigned_keys),
            "missing_task_count": len(missing_worker_tasks),
            "reestimate_history": reestimate_history,
        })

    if n_workers_target_met + n_workers_fallback + n_workers_not_evaluable + n_workers_pending != len(plan_workers):
        raise ValueError("C2-A-RP worker states are not mutually exclusive or complete")

    summary = {
        "schema_version": "c2a_rp_closeout_v2",
        "artifact_role": "C2A_RP_CLOSEOUT_FROZEN",
        "contract_role": "generated_subordinate",
        "method_contract_version": method["contract_version"],
        "method_contract_sha256": method_sha,
        "profile_version": c2b.get("profile_version", "") or (_text(profiles[0].get("profile_version")) if profiles else ""),
        "cohort_id": c2b.get("cohort_id", "") or (_text(profiles[0].get("cohort_id")) if profiles else ""),
        "formal_ready": True,
        "C2_A_RP_CLOSED": True,
        "n_workers_assigned": len(assignment_by_worker),
        "n_workers_planned": len(plan_by_worker),
        "n_workers_completed": sum(all((worker, _text(row.get("task_id"))) in submitted_set for row in assignment_by_worker[worker]) for worker in assignment_by_worker),
        "n_workers_partial": sum(any((worker, _text(row.get("task_id"))) not in submitted_set for row in assignment_by_worker[worker]) for worker in assignment_by_worker),
        "n_assignments": len(assignments),
        "n_submissions": len(submitted),
        "n_missing": len(missing),
        "n_workers_target_met": n_workers_target_met,
        "n_workers_fallback": n_workers_fallback,
        "n_workers_not_evaluable": n_workers_not_evaluable,
        "n_workers_pending": n_workers_pending,
        "block_closed": True,
        "stage_closed": n_workers_pending == 0,
        "next_block_required": n_workers_pending > 0,
        "current_block_index": current_block,
        "worker_outcomes": worker_outcomes,
        "support_discrepancies": support_discrepancies,
        "risk_slope_evidence_path": str(risk_slope_evidence_csv or ""),
        "risk_slope_evidence_sha256": sha256_file(risk_slope_evidence_csv) if risk_slope_evidence_csv else "",
        "threshold_manifest_path": str(threshold_path or ""),
        "threshold_manifest_sha256": threshold_sha,
        "formal_target": method["c2"]["c2_a_rp_formal_target"],
        "interval_definition": method["c2"]["c2_a_rp_interval"],
        "missing_worker_tasks": [
            {"worker_id": worker, "task_id": task, **missing_dispositions[(worker, task)]}
            for worker, task in sorted(missing)
        ],
        "closure_reason": (
            "awaiting_next_block" if n_workers_pending
            else "researcher_declared_terminal_after_completed_block" if terminal_declaration is not None
            else "all_precision_targets_met_or_unsupported_adjustments_fallback" if not assignments
            else "all_assigned_tasks_completed_or_terminalized_at_frozen_cap"
        ),
        "precision_plan_path": str(precision_plan_csv),
        "precision_plan_sha256": sha256_file(precision_plan_csv),
        "assignment_manifest_path": str(assignment_manifest_csv),
        "assignment_manifest_sha256": sha256_file(assignment_manifest_csv),
        "assignment_history_path": str(assignment_history_csv),
        "assignment_history_sha256": sha256_file(assignment_history_csv),
        "submissions_path": str(submissions_csv),
        "submissions_sha256": sha256_file(submissions_csv),
        "post_c2a_rp_profile_path": str(post_c2a_profile_csv),
        "post_c2a_rp_profile_sha256": sha256_file(post_c2a_profile_csv),
        "c2b_closeout_path": str(c2b_closeout),
        "c2b_closeout_sha256": sha256_file(c2b_closeout),
        "historical_c2b_acceptance_path": str(historical_acceptance or ""),
        "historical_c2b_acceptance_sha256": sha256_file(historical_acceptance) if historical_acceptance else "",
        "terminal_disposition_path": str(terminal_disposition_csv or ""),
        "terminal_disposition_sha256": sha256_file(terminal_disposition_csv) if terminal_disposition_csv else "",
        "stage_terminal_declaration_path": str(stage_terminal_declaration or ""),
        "stage_terminal_declaration_sha256": sha256_file(stage_terminal_declaration) if stage_terminal_declaration else "",
        "dispatch_status": "awaiting_next_block" if n_workers_pending else "closed",
        "next_block_index": min((row["blocks_completed"] + 1 for row in worker_outcomes if row["terminal_state"] == "awaiting_next_block"), default=0),
        "blockers": ["awaiting_next_block"] if n_workers_pending else [],
        "dependencies": [
            _dependency("C2A_PRECISION_PLAN", precision_plan_csv),
            _dependency("C2A_ASSIGNMENT_MANIFEST", assignment_manifest_csv),
            _dependency("C2A_ASSIGNMENT_HISTORY", assignment_history_csv),
            _dependency("C2A_SUBMISSIONS", submissions_csv),
            _dependency("POST_C2A_RP_PROFILE", post_c2a_profile_csv),
            _dependency("C2B_CLOSEOUT", c2b_closeout),
            _dependency("METHOD_CONTRACT", METHOD_CONTRACT),
        ],
    }
    if historical_acceptance:
        summary["dependencies"].append(_dependency("C2B_HISTORICAL_EVIDENCE_ACCEPTANCE", historical_acceptance))
    if terminal_disposition_csv:
        summary["dependencies"].append(_dependency("C2A_TERMINAL_DISPOSITION", terminal_disposition_csv))
    if stage_terminal_declaration:
        summary["dependencies"].append(_dependency("C2A_STAGE_TERMINAL_DECLARATION", stage_terminal_declaration))
    if risk_slope_evidence_csv:
        summary["dependencies"].append(_dependency("C2A_RISK_SLOPE_EVIDENCE", risk_slope_evidence_csv))
    output_json.parent.mkdir(parents=True, exist_ok=True)
    if n_workers_pending:
        summary["artifact_role"] = "C2A_RP_BLOCK_CLOSEOUT_FROZEN"
        summary["formal_ready"] = False
        summary["C2_A_RP_CLOSED"] = False
    output_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize the formal C2-A-RP closeout.")
    parser.add_argument("--precision-plan", type=Path, required=True)
    parser.add_argument("--assignment-manifest", type=Path, required=True)
    parser.add_argument("--assignment-history", type=Path, required=True)
    parser.add_argument("--submissions", type=Path, required=True)
    parser.add_argument("--post-c2a-rp-profile", type=Path, required=True)
    parser.add_argument("--c2b-closeout", type=Path, required=True)
    parser.add_argument("--terminal-disposition", type=Path)
    parser.add_argument("--risk-slope-evidence", type=Path)
    parser.add_argument("--threshold-manifest", type=Path)
    parser.add_argument("--stage-terminal-declaration", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = materialize(
            args.precision_plan, args.assignment_manifest, args.assignment_history,
            args.submissions, args.post_c2a_rp_profile, args.c2b_closeout, args.output,
            terminal_disposition_csv=args.terminal_disposition,
            risk_slope_evidence_csv=args.risk_slope_evidence,
            threshold_manifest=args.threshold_manifest,
            stage_terminal_declaration=args.stage_terminal_declaration,
        )
    except (OSError, KeyError, TypeError, ValueError) as exc:
        blocked = _write_blocked_summary(
            args.output, f"{type(exc).__name__}:{exc}",
            {
                "precision_plan": _safe_sha(args.precision_plan),
                "assignment_manifest": _safe_sha(args.assignment_manifest),
                "assignment_history": _safe_sha(args.assignment_history),
                "submissions": _safe_sha(args.submissions),
                "post_c2a_rp_profile": _safe_sha(args.post_c2a_rp_profile),
                "c2b_closeout": _safe_sha(args.c2b_closeout),
                "terminal_disposition": _safe_sha(args.terminal_disposition),
                "risk_slope_evidence": _safe_sha(args.risk_slope_evidence),
                "threshold_manifest": _safe_sha(args.threshold_manifest),
                "stage_terminal_declaration": _safe_sha(args.stage_terminal_declaration),
            },
        )
        print(json.dumps({"formal_ready": False, "C2_A_RP_CLOSED": False, "blocked_summary": str(blocked), "reason_code": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
