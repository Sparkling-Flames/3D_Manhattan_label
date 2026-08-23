"""Deterministic C1 k=22 prefix replay for the v5 uncertainty audit.

This is a development helper only.  It consumes the frozen historical C1
candidate pool and never writes an analysis artifact.
"""
from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from tools.thesis_main.analysis import run_topology_sequential_preflight as topology


PREFIX_KS = (5, 8, 12, 16, 20, 22)
REPLICATES = 200
FULL_K = 22
EXPECTED_FULL_TASK_COUNT = 12
STATUS_VALUES = (
    "unimodal",
    "dominant_with_dissent",
    "supported_multimodal",
    "not_evaluable",
)


def _truth(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "passed", "valid"}


def _candidate_id(row: Mapping[str, Any]) -> str:
    return str(row.get("canonical_annotation_id") or row.get("annotation_id") or "")


def _frozen_historical(row: Mapping[str, Any]) -> bool:
    return all(
        _truth(row.get(field))
        for field in ("frozen_geometry_pool_member", "historical_replay_admitted", "replay_geometry_admissible")
    ) and (row.get("_geometry") or {}).get("valid") is True


def frozen_c1_k22_tasks(historical_candidates: Mapping[str, Sequence[Mapping[str, Any]]]) -> dict[str, tuple[Mapping[str, Any], ...]]:
    """Return exactly the twelve frozen C1 tasks with full historical k=22."""
    selected = {
        str(task): tuple(rows)
        for task, rows in sorted(historical_candidates.items(), key=lambda item: str(item[0]))
        if len(rows) == FULL_K
    }
    if len(selected) != EXPECTED_FULL_TASK_COUNT:
        raise ValueError(f"expected {EXPECTED_FULL_TASK_COUNT} frozen C1 k=22 tasks, got {len(selected)}")
    for task, rows in selected.items():
        if len({_candidate_id(row) for row in rows}) != FULL_K or not all(_frozen_historical(row) for row in rows):
            raise ValueError(f"task {task} is not a complete frozen historical candidate set")
    return selected


def load_frozen_c1_k22_tasks(root: Path = topology.ROOT) -> dict[str, tuple[Mapping[str, Any], ...]]:
    """Load only the frozen historical k=22 C1 candidate sets."""
    return frozen_c1_k22_tasks(topology.load_frozen_inputs(root)["historical_candidates"])


def _sample_rank(seed: int, task: str, k: int, replicate: int, candidate_id: str) -> str:
    payload = f"{derive_sample_seed(seed, task, k, replicate)}|{candidate_id}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def derive_sample_seed(seed: int, task: str, k: int, replicate: int) -> int:
    """Derive an auditable integer seed for one task/prefix/replicate."""
    payload = f"{seed}|{task}|{k}|{replicate}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def sample_without_replacement(
    candidates: Sequence[Mapping[str, Any]], *, task: str, k: int, replicate: int, seed: int,
) -> list[Mapping[str, Any]]:
    """Take a stable seed-derived sample without replacement."""
    if not 0 < k <= len(candidates):
        raise ValueError(f"k must be in 1..{len(candidates)}, got {k}")
    ordered = sorted(candidates, key=lambda row: (_candidate_id(row), str(row.get("worker_id", ""))))
    ranked = sorted(
        ordered,
        key=lambda row: (_sample_rank(seed, task, k, replicate, _candidate_id(row)), _candidate_id(row)),
    )
    return ranked[:k]


def replay_task_prefixes(
    task: str,
    candidates: Sequence[Mapping[str, Any]],
    *,
    cluster_fn: Callable[[list[Mapping[str, Any]], str], Mapping[str, Any]] = topology._cluster,
    seed: int = 20260821,
    replicates: int = REPLICATES,
    k_values: Sequence[int] = PREFIX_KS,
) -> list[dict[str, Any]]:
    """Replay one k=22 task at each requested prefix, reclustering each draw."""
    if len(candidates) != FULL_K:
        raise ValueError(f"{task} must have exactly {FULL_K} frozen candidates")
    if len({_candidate_id(row) for row in candidates}) != FULL_K or not all(_frozen_historical(row) for row in candidates):
        raise ValueError(f"{task} is not a complete frozen historical candidate set")
    if replicates <= 0:
        raise ValueError("replicates must be positive")
    requested = tuple(k_values)
    if requested != PREFIX_KS:
        raise ValueError(f"k_values must be exactly {PREFIX_KS}")
    if any(k <= 0 or k > FULL_K for k in requested):
        raise ValueError("prefix k is outside the frozen k=22 support")

    rows: list[dict[str, Any]] = []
    for k in requested:
        draws = 1 if k == FULL_K else replicates
        for replicate in range(draws):
            sample = (
                sorted(candidates, key=lambda row: (_candidate_id(row), str(row.get("worker_id", ""))))
                if k == FULL_K else sample_without_replacement(
                    candidates, task=task, k=k, replicate=replicate, seed=seed,
                )
            )
            cluster = dict(cluster_fn(sample, task))
            status = str(cluster.get("task_crowd_structure_status") or "").strip()
            if status not in STATUS_VALUES:
                raise ValueError(f"unknown frozen geometry status {status!r} for {task} k={k}")
            rows.append({
                "base_task_id": task,
                "k": k,
                "replicate": replicate,
                "seed": seed,
                "derived_sample_seed": derive_sample_seed(seed, task, k, replicate),
                "sample_annotation_ids": ";".join(sorted(_candidate_id(row) for row in sample)),
                "valid_k": cluster.get("valid_k", k),
                "task_crowd_structure_status": status,
                "partition_status": cluster.get("partition_status", ""),
                "structure_reason": cluster.get("structure_reason", ""),
                "cluster_membership_json": cluster.get("cluster_membership_json", ""),
                "sampling_mode": "full_sample_once" if k == FULL_K else "without_replacement_fixed_seed",
                "requested_replicates": replicates,
                "full_sample_equivalent_to_requested_replicates": k == FULL_K,
            })
    return rows


def replay_frozen_c1_k22_prefixes(
    historical_candidates: Mapping[str, Sequence[Mapping[str, Any]]], *,
    cluster_fn: Callable[[list[Mapping[str, Any]], str], Mapping[str, Any]] = topology._cluster,
    seed: int = 20260821,
    replicates: int = REPLICATES,
) -> list[dict[str, Any]]:
    """Replay all and only the twelve frozen C1 k=22 tasks."""
    tasks = frozen_c1_k22_tasks(historical_candidates)
    return [
        row
        for task, candidates in tasks.items()
        for row in replay_task_prefixes(task, candidates, cluster_fn=cluster_fn, seed=seed, replicates=replicates)
    ]


def summarize_prefix_replay(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Summarize status counts while retaining not_evaluable as uncertainty."""
    groups: dict[int, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        k = int(row["k"])
        status = str(row.get("task_crowd_structure_status") or "").strip()
        if status not in STATUS_VALUES:
            raise ValueError(f"unknown frozen geometry status {status!r}")
        groups[k].append(row)

    output: list[dict[str, Any]] = []
    for k in sorted(groups):
        values = groups[k]
        tasks = {str(row["base_task_id"]) for row in values}
        status_counts = Counter(str(row["task_crowd_structure_status"]) for row in values)
        expected_values = {int(row.get("requested_replicates") or REPLICATES) for row in values}
        if len(expected_values) != 1:
            raise ValueError(f"requested replicate count drifted for k={k}")
        expected = expected_values.pop()
        per_task_counts = Counter(str(row["base_task_id"]) for row in values)
        if len(set(per_task_counts.values())) != 1:
            raise ValueError(f"replicate count is not task-balanced for k={k}")
        per_task = next(iter(per_task_counts.values()), 0)
        expected_per_task = 1 if k == FULL_K else expected
        if per_task != expected_per_task:
            raise ValueError(f"unexpected replicate count for k={k}: {per_task} != {expected_per_task}")
        output.append({
            "k": k,
            "task_count": len(tasks),
            "replay_row_count": len(values),
            "requested_replicates": expected,
            "observed_replicates_per_task": per_task,
            "full_sample_equivalent_to_requested_replicates": k == FULL_K,
            "unimodal_count": status_counts["unimodal"],
            "dominant_with_dissent_count": status_counts["dominant_with_dissent"],
            "supported_multimodal_count": status_counts["supported_multimodal"],
            "not_evaluable_count": status_counts["not_evaluable"],
            "status_counts": {status: status_counts[status] for status in STATUS_VALUES},
            "status_contract": "unimodal|dominant_with_dissent|supported_multimodal|not_evaluable",
        })
    return output
