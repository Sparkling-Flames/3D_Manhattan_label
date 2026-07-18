from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from tools.thesis_main.analysis.geometry_consensus.pairwise import pairwise_similarity
from tools.thesis_main.analysis.geometry_consensus.representation import normalize_geometry
from tools.thesis_main.analysis.vfinal_artifact_utils import sha256_file, write_csv_rows


RULE_VERSION = "v1_policy_execution_v1"
ARMS = ("strong_global", "full_integrated")


def _truth(value: Any) -> bool:
    return value is True or str(value).strip().lower() in {"1", "true", "yes"}


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _items(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    text = str(value or "").strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = text.replace(";", ",").split(",")
    return [str(item).strip() for item in (parsed if isinstance(parsed, list) else [parsed]) if str(item).strip()]


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(str(value or "{}"))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def load_frozen_manifest(path: Path, declared_sha256: str, *, input_status: str) -> dict[str, Any]:
    if input_status != "formal":
        raise ValueError("V1 execution requires input_status=formal; dry-run cannot launch")
    if not path.exists() or sha256_file(path) != str(declared_sha256).lower():
        raise ValueError("freeze manifest SHA mismatch")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    required = {"manifest_version", "freeze_version", "profile_version", "scoring", "scheduler", "aggregation", "feasibility", "dependencies"}
    if not required.issubset(manifest) or manifest["manifest_version"] != RULE_VERSION:
        raise ValueError("freeze manifest contract is incomplete")
    for dependency in manifest["dependencies"]:
        dependency_path = Path(str(dependency.get("path", "")))
        if not dependency_path.is_absolute():
            dependency_path = (path.parent / dependency_path).resolve()
        if not dependency_path.exists() or sha256_file(dependency_path) != str(dependency.get("sha256", "")).lower():
            raise ValueError(f"frozen dependency is missing or stale: {dependency_path}")
    scheduler = manifest["scheduler"]
    if not {
        "offer_timeout", "completion_timeout", "max_offer_attempts", "k_initial",
        "standard_cap", "exceptional_cap", "per_worker_arm_quota", "seed",
    }.issubset(scheduler):
        raise ValueError("scheduler contract is incomplete")
    if int(scheduler["exceptional_cap"]) < int(scheduler["standard_cap"]) or int(scheduler["standard_cap"]) < int(scheduler["k_initial"]):
        raise ValueError("scheduler caps are inconsistent")
    return manifest


def _family_activation(task: dict[str, Any], scoring: dict[str, Any]) -> tuple[str, bool]:
    scores = sorted(
        ((str(family), _number(score)) for family, score in _mapping(task.get("family_scores")).items()),
        key=lambda item: (-item[1], item[0]),
    )
    if not scores:
        return "", False
    second = scores[1][1] if len(scores) > 1 else float("-inf")
    active = scores[0][1] >= _number(scoring["family_activation_threshold"]) and scores[0][1] - second >= _number(scoring["family_activation_margin"])
    return (scores[0][0], True) if active else ("", False)


def rank_candidates(
    candidates: Iterable[dict[str, Any]],
    task: dict[str, Any],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    scoring = manifest["scoring"]
    profile_version = str(manifest["profile_version"])
    eligible = [
        dict(candidate)
        for candidate in candidates
        if _truth(candidate.get("eligible", True)) and _truth(candidate.get("available", True))
    ]
    for candidate in eligible:
        candidate["_global"] = _number(candidate.get("global_lcb"), float("-inf"))
    tie_hash = lambda row: hashlib.sha256(f"{manifest['scheduler']['seed']}|{task.get('task_id')}|{row.get('worker_id')}".encode()).hexdigest()
    global_rank = sorted(
        eligible,
        key=lambda row: (
            -row["_global"],
            -_number(row.get("loo_lcb")),
            -_number(row.get("capacity_available")),
            tie_hash(row),
        ),
    )
    fallback_reasons: list[str] = []
    d_cal_f = _number(task.get("d_cal_F"), float("nan"))
    if not (_number(scoring["d_cal_F_min"]) <= d_cal_f <= _number(scoring["d_cal_F_max"])):
        fallback_reasons.append("d_cal_F_out_of_support")
    if any(str(row.get("profile_version", "")) != profile_version for row in eligible):
        fallback_reasons.append("profile_version_incompatible")
    family, family_active = _family_activation(task, scoring)
    if _mapping(task.get("family_scores")) and not family_active:
        fallback_reasons.append("task_family_activation_ambiguous")

    minimum_supported = int(scoring["min_conditional_supported"])
    if (
        _truth(task.get("risk_route"))
        and sum(_truth(row.get("B_u_routing_eligible")) for row in eligible) < minimum_supported
    ) or (
        family_active
        and sum(family in set(_items(row.get("p1_supported_families"))) for row in eligible) < minimum_supported
    ):
        fallback_reasons.append("conditional_supported_workers_below_minimum")

    full_rank = []
    for candidate in eligible:
        adjustment = 0.0
        if _truth(task.get("risk_route")) and _truth(candidate.get("B_u_routing_eligible")):
            adjustment += _number(scoring["lambda_B"]) * _number(candidate.get("B_u_risk"))
        family_profiles = _mapping(candidate.get("p1_family_scores"))
        if family_active and family in set(_items(candidate.get("p1_supported_families"))) and family in family_profiles:
            adjustment += _number(scoring["lambda_P"]) * _number(family_profiles[family])
        cap = abs(_number(scoring["max_total_adjustment"]))
        candidate["_full"] = candidate["_global"] + max(-cap, min(cap, adjustment))
        full_rank.append(candidate)
    full_rank.sort(key=lambda row: (-row["_full"], -row["_global"], -_number(row.get("loo_lcb")), tie_hash(row)))
    if len(full_rank) > 1 and full_rank[0]["_full"] - full_rank[1]["_full"] < _number(scoring["ranking_stability_margin"]):
        fallback_reasons.append("ranking_unstable")
    fallback = bool(fallback_reasons)
    if fallback:
        full_rank = list(global_rank)
    return {
        "strong_global": [str(row["worker_id"]) for row in global_rank],
        "full_integrated": [str(row["worker_id"]) for row in full_rank],
        "full_fallback": fallback,
        "fallback_reasons": fallback_reasons,
        "active_family": family,
        "risk_route_active": _truth(task.get("risk_route")),
    }


def _components(records: list[dict[str, Any]], aggregation: dict[str, Any]) -> tuple[list[list[int]], dict[tuple[int, int], float]]:
    adjacency = {index: set() for index in range(len(records))}
    similarities: dict[tuple[int, int], float] = {}
    for left in range(len(records)):
        for right in range(left + 1, len(records)):
            similarity = pairwise_similarity(records[left]["_geometry"], records[right]["_geometry"])
            score = min(
                _number(similarity.get("q_boundary"), -1.0),
                _number(similarity.get("q_wallwall"), -1.0),
            )
            similarities[left, right] = score
            if (
                similarity["metric_compatible"]
                and _number(similarity["q_boundary"]) >= _number(aggregation["min_q_boundary"])
                and _number(similarity["q_wallwall"]) >= _number(aggregation["min_q_wallwall"])
            ):
                adjacency[left].add(right)
                adjacency[right].add(left)
    components: list[list[int]] = []
    unseen = set(adjacency)
    while unseen:
        clique = next(
            list(group)
            for size in range(len(unseen), 0, -1)
            for group in itertools.combinations(sorted(unseen), size)
            if all(right in adjacency[left] for left, right in itertools.combinations(group, 2))
        )
        components.append(clique)
        unseen.difference_update(clique)
    return sorted(components, key=lambda value: (-len(value), value)), similarities


def aggregate_submissions(
    submissions: Iterable[dict[str, Any]],
    manifest: dict[str, Any],
    *,
    at_cap: bool,
    seed_key: str = "",
) -> dict[str, Any]:
    aggregation = manifest["aggregation"]
    legal: list[dict[str, Any]] = []
    for submission in submissions:
        if str(submission.get("outcome", "")) != "completed_valid" or not _truth(submission.get("structurally_valid", True)):
            continue
        geometry = _mapping(submission.get("geometry"))
        if not isinstance(geometry, dict) or "valid" not in geometry:
            corners = submission.get("corners_px") or []
            if isinstance(corners, str):
                try:
                    corners = json.loads(corners)
                except json.JSONDecodeError:
                    corners = []
            geometry = normalize_geometry(
                corners,
                width=int(submission.get("width") or 1024),
                height=int(submission.get("height") or 512),
            )
        if geometry.get("valid"):
            legal.append({**submission, "_geometry": geometry})
    if not legal:
        return {
            "terminal_status": "severe_failure" if at_cap else "needs_more",
            "selected_worker_id": "", "valid_k": 0, "largest_cluster_support": 0,
            "second_cluster_support": 0, "medoid_margin": "", "multimodal": False,
        }
    components, similarities = _components(legal, aggregation)
    largest = components[0]
    second_size = len(components[1]) if len(components) > 1 else 0
    medoid_scores = []
    for index in largest:
        peer_scores = [
            similarities[min(index, peer), max(index, peer)]
            for peer in largest
            if peer != index
        ]
        medoid_scores.append((sum(peer_scores) / len(peer_scores) if peer_scores else 1.0, index))
    medoid_scores.sort(key=lambda item: (-item[0], -_number(legal[item[1]].get("global_lcb")), str(legal[item[1]].get("worker_id", ""))))
    margin = medoid_scores[0][0] - medoid_scores[1][0] if len(medoid_scores) > 1 else 1.0
    multimodal = second_size == len(largest) or second_size >= int(aggregation["multimodal_second_cluster_min"])
    stable = (
        len(largest) >= int(aggregation["min_cluster_size"])
        and not multimodal
        and margin >= _number(aggregation["min_medoid_margin"])
    )
    if stable:
        tied = [index for score, index in medoid_scores if abs(score - medoid_scores[0][0]) <= 1e-12]
        best_global = max(_number(legal[index].get("global_lcb")) for index in tied)
        tied = [index for index in tied if _number(legal[index].get("global_lcb")) == best_global]
        if len(tied) > 1:
            tied.sort(key=lambda index: hashlib.sha256(f"{manifest['scheduler']['seed']}|{seed_key}|{legal[index]['worker_id']}".encode()).hexdigest())
        selected = legal[tied[0]]
        terminal = "resolved"
    else:
        selected, terminal = None, "unresolved" if at_cap else "needs_more"
    return {
        "terminal_status": terminal,
        "selected_worker_id": str(selected.get("worker_id", "")) if selected else "",
        "selected_annotation_id": str(selected.get("annotation_id", "")) if selected else "",
        "selected_geometry_sha256": (
            hashlib.sha256(json.dumps(selected["_geometry"], sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            if selected else ""
        ),
        "valid_k": len(legal),
        "largest_cluster_support": len(largest),
        "second_cluster_support": second_size,
        "medoid_margin": margin,
        "multimodal": multimodal,
    }


def feasibility_report(
    tasks: Iterable[dict[str, Any]],
    candidates_by_task: dict[str, list[dict[str, Any]]],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    task_rows = list(tasks)
    reports = [
        rank_candidates(candidates_by_task.get(str(task["task_id"]), []), task, manifest)
        for task in task_rows
    ]
    total = len(reports)
    initial_k = int(manifest["scheduler"]["k_initial"])
    rates = {
        "activation_rate": sum(bool(row["active_family"]) or row["risk_route_active"] for row in reports) / total if total else 0.0,
        "fallback_rate": sum(row["full_fallback"] for row in reports) / total if total else 1.0,
        "first_choice_divergence": sum(row["strong_global"][:1] != row["full_integrated"][:1] for row in reports) / total if total else 0.0,
        "initial_set_divergence": sum(set(row["strong_global"][:initial_k]) != set(row["full_integrated"][:initial_k]) for row in reports) / total if total else 0.0,
    }
    rates["capacity_adjusted_divergence"] = _capacity_divergence(task_rows, reports, manifest)
    thresholds = manifest["feasibility"]
    passed = (
        rates["activation_rate"] >= _number(thresholds["min_activation_rate"])
        and rates["fallback_rate"] <= _number(thresholds["max_fallback_rate"])
        and rates["first_choice_divergence"] >= _number(thresholds["min_first_choice_divergence"])
        and rates["initial_set_divergence"] >= _number(thresholds["min_initial_set_divergence"])
        and rates["capacity_adjusted_divergence"] >= _number(thresholds["min_capacity_adjusted_divergence"])
    )
    return {
        **rates,
        "n_tasks": total,
        "launch_status": "launchable" if passed else "not_launched_policy_indistinguishable",
    }


def _capacity_divergence(tasks: list[dict[str, Any]], rankings: list[dict[str, Any]], manifest: dict[str, Any]) -> float:
    quota = int(manifest["scheduler"]["per_worker_arm_quota"])
    ledgers: dict[tuple[str, str], defaultdict[str, int]] = {}
    choices: list[tuple[str, str]] = []
    for task, ranking in zip(tasks, rankings):
        block = str(task["block_id"])
        pair = []
        for arm in ARMS:
            ledger = ledgers.setdefault((block, arm), defaultdict(lambda: quota))
            worker = next((worker for worker in ranking[arm] if ledger[worker] > 0), "")
            if worker:
                ledger[worker] -= 1
            pair.append(worker)
        choices.append((pair[0], pair[1]))
    return sum(left != right for left, right in choices) / len(choices) if choices else 0.0


def _randomized_arms(tasks: list[dict[str, Any]], seed: int) -> dict[str, str]:
    assignments: dict[str, str] = {}
    by_block: dict[str, list[str]] = defaultdict(list)
    for task in tasks:
        by_block[str(task["block_id"])].append(str(task["task_id"]))
    for block_id, task_ids in sorted(by_block.items()):
        shuffled = sorted(task_ids)
        random.Random(f"{seed}|{block_id}").shuffle(shuffled)
        offset = random.Random(f"{seed}|{block_id}|offset").randrange(2)
        assignments.update({task_id: ARMS[(index + offset) % 2] for index, task_id in enumerate(shuffled)})
    return assignments


def run_v1_trial(
    tasks: Iterable[dict[str, Any]],
    candidates_by_task: dict[str, list[dict[str, Any]]],
    outcomes_by_task_worker: dict[tuple[str, str], dict[str, Any]],
    manifest: dict[str, Any],
    *,
    allow_preassigned_arms: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    task_rows = list(tasks)
    task_ids = [str(task.get("task_id", "")) for task in task_rows]
    if not all(task_ids) or len(task_ids) != len(set(task_ids)):
        raise ValueError("V1 task identities must be non-empty and unique")
    snapshots: dict[str, set[str]] = defaultdict(set)
    for task in task_rows:
        if not task.get("block_id") or not task.get("availability_snapshot_id"):
            raise ValueError("V1 task is missing its block or availability snapshot")
        snapshots[str(task["block_id"])].add(str(task["availability_snapshot_id"]))
    if any(len(values) != 1 for values in snapshots.values()):
        raise ValueError("each V1 block must bind one frozen availability snapshot")
    for task_id, candidates in candidates_by_task.items():
        worker_ids = [str(row.get("worker_id", "")) for row in candidates]
        if not all(worker_ids) or len(worker_ids) != len(set(worker_ids)):
            raise ValueError(f"candidate identities must be non-empty and unique within task {task_id}")
    assignments = _randomized_arms(task_rows, int(manifest["scheduler"]["seed"]))
    quota = int(manifest["scheduler"]["per_worker_arm_quota"])
    ledgers: dict[tuple[str, str], defaultdict[str, int]] = {}
    for block_id in snapshots:
        for arm in ARMS:
            ledgers[block_id, arm] = defaultdict(lambda: quota)
    offer_rows: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    for task in task_rows:
        task_id = str(task["task_id"])
        block_id = str(task["block_id"])
        arm = str(task.get("arm") or assignments[task_id]) if allow_preassigned_arms else assignments[task_id]
        if arm not in ARMS:
            raise ValueError(f"unknown V1 arm: {arm}")
        realtime_candidates = [
            row for row in candidates_by_task.get(task_id, [])
            if ledgers[block_id, arm][str(row.get("worker_id", ""))] > 0
        ]
        ranking = rank_candidates(realtime_candidates, task, manifest)
        candidate_set = ranking[arm]
        submissions: list[dict[str, Any]] = []
        completed_workers: set[str] = set()
        attempted_workers: set[str] = set()
        final = aggregate_submissions([], manifest, at_cap=False, seed_key=task_id)
        cap = int(manifest["scheduler"]["exceptional_cap"] if _truth(task.get("exceptional_cap_eligible")) else manifest["scheduler"]["standard_cap"])
        max_attempts = int(manifest["scheduler"]["max_offer_attempts"])
        offer_sequence = 0
        for worker in candidate_set:
            if final["terminal_status"] == "resolved" or offer_sequence >= max_attempts or len(submissions) >= cap:
                break
            if ledgers[block_id, arm][worker] <= 0:
                continue
            offer_sequence += 1
            attempted_workers.add(worker)
            before = ledgers[block_id, arm][worker]
            outcome = dict(outcomes_by_task_worker.get((task_id, worker), {"outcome": "no_response"}))
            outcome_name = str(outcome.get("outcome", "no_response"))
            accepted = worker if outcome_name not in {"declined", "no_response"} else ""
            completed = worker if outcome_name.startswith("completed_") or outcome_name == "external_system_failure_pending_disposition" else ""
            if accepted:
                ledgers[block_id, arm][worker] -= 1
            if completed:
                completed_workers.add(worker)
            if outcome_name == "completed_valid":
                submissions.append({**outcome, "worker_id": worker, "global_lcb": next((_number(row.get("global_lcb")) for row in candidates_by_task[task_id] if str(row.get("worker_id")) == worker), 0.0)})
            replacement_reason = {
                "declined": "offered_declined",
                "no_response": "offer_timeout",
                "accepted_not_completed": "completion_timeout",
                "completed_invalid": "completed_invalid",
                "external_system_failure_pending_disposition": "external_pending_replacement",
            }.get(outcome_name, "")
            offer_rows.append({
                "rule_version": RULE_VERSION,
                "freeze_version": manifest["freeze_version"],
                "block_id": task["block_id"],
                "task_id": task_id,
                "policy_arm": arm,
                "candidate_set": json.dumps(candidate_set),
                "availability_snapshot_id": task["availability_snapshot_id"],
                "policy_recommended_worker": candidate_set[0] if candidate_set else "",
                "recommendation_rank": candidate_set.index(worker) + 1,
                "offered_worker": worker,
                "offer_sequence": offer_sequence,
                "accepted_worker": accepted,
                "completed_worker": completed,
                "outcome": outcome_name,
                "replacement_reason": replacement_reason,
                "recommendation_outcome": (
                    "recommended_offered"
                    if offer_sequence == 1 and worker == candidate_set[0]
                    else "recommended_not_offered"
                    if offer_sequence == 1
                    else ""
                ),
                "timeout": outcome_name in {"no_response", "accepted_not_completed"},
                "offer_timeout": manifest["scheduler"]["offer_timeout"],
                "completion_timeout": manifest["scheduler"]["completion_timeout"],
                "capacity_before": before,
                "capacity_after": ledgers[block_id, arm][worker],
                "capacity_remaining": ledgers[block_id, arm][worker],
            })
            at_cap = len(submissions) >= cap or offer_sequence >= max_attempts
            final = aggregate_submissions(submissions, manifest, at_cap=at_cap, seed_key=task_id)
            if len(submissions) < int(manifest["scheduler"]["k_initial"]):
                final["terminal_status"] = "needs_more" if not at_cap else ("unresolved" if submissions else "severe_failure")
        if final["terminal_status"] == "needs_more":
            final = aggregate_submissions(submissions, manifest, at_cap=True, seed_key=task_id)
        remaining_candidate = any(
            worker not in attempted_workers and ledgers[block_id, arm][worker] > 0
            for worker in candidate_set
        )
        candidate_exhausted = final["terminal_status"] != "resolved" and not remaining_candidate
        policy_failure_reason = ""
        if final["terminal_status"] != "resolved":
            if candidate_set and all(ledgers[block_id, arm][worker] <= 0 for worker in candidate_set):
                policy_failure_reason = "capacity_exhaustion"
            elif offer_sequence >= max_attempts:
                policy_failure_reason = "replacement_failure"
            elif candidate_exhausted:
                policy_failure_reason = "candidate_exhaustion"
        summaries.append({
            "rule_version": RULE_VERSION,
            "freeze_version": manifest["freeze_version"],
            "block_id": task["block_id"],
            "task_id": task_id,
            "policy_arm": arm,
            "risk_route": "stress_route" if _truth(task.get("risk_route")) else "ordinary",
            "availability_snapshot_id": task["availability_snapshot_id"],
            "candidate_set": json.dumps(candidate_set),
            "full_fallback": ranking["full_fallback"],
            "fallback_reasons": json.dumps(ranking["fallback_reasons"]),
            "candidate_exhausted": candidate_exhausted,
            "non_delivery": final["terminal_status"] != "resolved",
            "policy_failure": bool(policy_failure_reason),
            "policy_failure_reason": policy_failure_reason,
            "failure_attribution": "policy_caused_failure" if policy_failure_reason else "none",
            "analysis_disposition": "included",
            "policy_terminal_status": final["terminal_status"],
            "k_used": final["valid_k"],
            "offers_used": offer_sequence,
            "completed_workers": json.dumps(sorted(completed_workers)),
            **final,
        })
    return offer_rows, summaries


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def materialize_v1_policy(
    tasks_csv: Path,
    candidates_csv: Path,
    outcomes_csv: Path,
    output_dir: Path,
    *,
    freeze_manifest: Path,
    freeze_manifest_sha256: str,
    input_status: str,
) -> dict[str, Any]:
    manifest = load_frozen_manifest(freeze_manifest, freeze_manifest_sha256, input_status=input_status)
    tasks = _read_csv(tasks_csv)
    candidates_by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in _read_csv(candidates_csv):
        candidates_by_task[str(row["task_id"])].append(row)
    outcomes = {(str(row["task_id"]), str(row["worker_id"])): row for row in _read_csv(outcomes_csv)}
    feasibility = feasibility_report(tasks, candidates_by_task, manifest)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "v1_policy_feasibility.json").write_text(json.dumps(feasibility, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    if feasibility["launch_status"] != "launchable":
        return {**feasibility, "formal_assignment_generated": False}
    offers, summaries = run_v1_trial(tasks, candidates_by_task, outcomes, manifest)
    if input_status == "formal" and any(
        row["terminal_status"] == "resolved"
        and (not row.get("selected_annotation_id") or not row.get("selected_geometry_sha256"))
        for row in summaries
    ):
        raise ValueError("formal resolved V1 output requires annotation and geometry identity")
    write_csv_rows(output_dir / "v1_policy_offer_ledger.csv", offers)
    write_csv_rows(output_dir / "v1_policy_task_summary.csv", summaries)
    audit = {
        **feasibility,
        "formal_assignment_generated": True,
        "freeze_manifest_sha256": freeze_manifest_sha256,
        "tasks_sha256": sha256_file(tasks_csv),
        "candidates_sha256": sha256_file(candidates_csv),
        "outcomes_sha256": sha256_file(outcomes_csv),
        "n_offer_events": len(offers),
        "n_tasks_materialized": len(summaries),
    }
    (output_dir / "v1_policy_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return audit


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize the frozen prospective V1 policy trial.")
    parser.add_argument("--tasks-csv", type=Path, required=True)
    parser.add_argument("--candidates-csv", type=Path, required=True)
    parser.add_argument("--outcomes-csv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--freeze-manifest", type=Path, required=True)
    parser.add_argument("--freeze-manifest-sha256", required=True)
    parser.add_argument("--input-status", choices=("dry_run", "formal"), default="dry_run")
    args = parser.parse_args(argv)
    print(json.dumps(materialize_v1_policy(
        args.tasks_csv, args.candidates_csv, args.outcomes_csv, args.output_dir,
        freeze_manifest=args.freeze_manifest,
        freeze_manifest_sha256=args.freeze_manifest_sha256,
        input_status=args.input_status,
    ), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
