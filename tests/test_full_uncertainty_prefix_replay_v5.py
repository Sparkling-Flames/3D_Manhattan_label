from __future__ import annotations

from tools.thesis_main.analysis.full_uncertainty.full_uncertainty_prefix_replay_v5 import (
    PREFIX_KS,
    frozen_c1_k22_tasks,
    replay_task_prefixes,
    sample_without_replacement,
    summarize_prefix_replay,
)


def _candidate(index: int) -> dict:
    return {
        "canonical_annotation_id": f"a{index:02d}",
        "worker_id": index,
        "frozen_geometry_pool_member": True,
        "historical_replay_admitted": True,
        "replay_geometry_admissible": True,
        "_geometry": {"valid": True},
    }


def _cluster(sample: list[dict], task: str) -> dict:
    return {
        "valid_k": len(sample),
        "task_crowd_structure_status": "not_evaluable" if len(sample) <= 12 else "unimodal",
    }


def test_k22_selection_requires_exactly_twelve_frozen_tasks() -> None:
    pool = {f"t{i}": [_candidate(index) for index in range(22)] for i in range(12)}
    selected = frozen_c1_k22_tasks(pool)
    assert sorted(selected, key=lambda task: int(task[1:])) == [f"t{i}" for i in range(12)]


def test_sampling_is_deterministic_and_without_replacement() -> None:
    candidates = [_candidate(index) for index in range(22)]
    first = sample_without_replacement(candidates, task="t0", k=8, replicate=3, seed=17)
    second = sample_without_replacement(list(reversed(candidates)), task="t0", k=8, replicate=3, seed=17)
    assert [row["canonical_annotation_id"] for row in first] == [row["canonical_annotation_id"] for row in second]
    assert len({row["canonical_annotation_id"] for row in first}) == 8


def test_prefix_replay_reclusters_each_subsample_and_full_k22_once() -> None:
    rows = replay_task_prefixes("t0", [_candidate(index) for index in range(22)], cluster_fn=_cluster, replicates=4, seed=17)
    assert [row["k"] for row in rows].count(5) == 4
    assert [row["k"] for row in rows].count(22) == 1
    assert rows[-1]["sampling_mode"] == "full_sample_once"
    summary = {row["k"]: row for row in summarize_prefix_replay(rows)}
    assert summary[5]["replay_row_count"] == 4
    assert summary[22]["full_sample_equivalent_to_requested_replicates"] is True
    assert summary[12]["not_evaluable_count"] == 4
    assert tuple(summary) == PREFIX_KS
