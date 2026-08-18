"""CI runner for the append-only topology preflight v4 audit.

The historical v3 loader expects c1_geometry_pool_eligibility.csv, but that
sidecar is not committed on codex/paper.  This runner reconstructs only the
identity allowlist from two committed frozen sources:

1. the 78 manual tasks with valid_k >= 5 in geometry_task_crowd_structure_C1;
2. the complete task-worker universe in geometry_pairwise_similarity_C1,
   bound one-to-one to c1_canonical_geometry.jsonl.

No geometry, quality, pairwise score, structural state, or reference outcome is
recomputed.  The derived sidecar is temporary and its provenance is emitted in
the v4 output directory.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.thesis_main.analysis import audit_topology_preflight_v4 as audit
from tools.thesis_main.analysis import run_topology_sequential_preflight as v3


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _int(value: Any) -> int | None:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def _key(row: dict[str, Any]) -> str:
    return str(row.get("canonical_annotation_id") or row.get("annotation_id") or "")


def materialize_missing_identity_sidecar(root: Path) -> dict[str, Any]:
    base = v3.c1_root(root)
    target = base / "c1_geometry_pool_eligibility.csv"
    if target.exists():
        return {
            "status": "committed_sidecar_present",
            "path": str(target.relative_to(root)),
            "derived": False,
        }

    task_rows = _read_csv(base / "geometry_task_crowd_structure_C1.csv")
    tasks = {
        str(row["base_task_id"])
        for row in task_rows
        if row.get("condition") == "manual" and (_int(row.get("valid_k")) or 0) >= 5
    }
    if len(tasks) != 78:
        raise AssertionError(f"manual k>=5 task denominator drifted: {len(tasks)} != 78")

    pairwise_rows = _read_csv(base / "geometry_pairwise_similarity_C1.csv")
    workers_by_task: dict[str, set[int]] = defaultdict(set)
    pair_count_by_task: Counter[str] = Counter()
    for row in pairwise_rows:
        task = str(row.get("base_task_id") or "")
        if task not in tasks or row.get("condition") != "manual":
            continue
        left = _int(row.get("worker_id_left"))
        right = _int(row.get("worker_id_right"))
        if left is None or right is None:
            raise AssertionError(f"incomplete pairwise identity for task {task}")
        workers_by_task[task].update((left, right))
        pair_count_by_task[task] += 1

    if set(workers_by_task) != tasks:
        raise AssertionError("pairwise sidecar does not cover all 78 tasks")
    distribution = Counter(len(workers_by_task[task]) for task in tasks)
    if distribution != Counter({5: 66, 22: 12}):
        raise AssertionError(f"pairwise worker distribution drifted: {dict(distribution)}")
    for task, workers in workers_by_task.items():
        expected_pairs = len(workers) * (len(workers) - 1) // 2
        if pair_count_by_task[task] != expected_pairs:
            raise AssertionError(
                f"pairwise coverage is not complete for {task}: "
                f"{pair_count_by_task[task]} != {expected_pairs}"
            )

    canonical_by_task_worker: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in _read_jsonl(base / "c1_canonical_geometry.jsonl"):
        task = str(row.get("base_task_id") or "")
        worker = _int(row.get("worker_id"))
        if task in tasks and worker in workers_by_task[task]:
            canonical_by_task_worker[(task, worker)].append(row)

    output_rows: list[dict[str, Any]] = []
    for task in sorted(tasks):
        for worker in sorted(workers_by_task[task]):
            matches = canonical_by_task_worker.get((task, worker), [])
            if len(matches) != 1:
                raise AssertionError(
                    f"canonical task-worker binding is not one-to-one for "
                    f"{task}/W{worker}: {len(matches)}"
                )
            annotation_id = _key(matches[0])
            if not annotation_id:
                raise AssertionError(f"missing canonical annotation identity: {task}/W{worker}")
            output_rows.append({
                "base_task_id": task,
                "condition": "manual",
                "worker_id": worker,
                "canonical_annotation_id": annotation_id,
                "annotation_id": annotation_id,
                "geometry_pool_eligible": "true",
                "identity_derivation": "complete_pairwise_worker_universe_x_canonical_task_worker_binding",
            })

    if len(output_rows) != 594:
        raise AssertionError(f"derived geometry pool identity count drifted: {len(output_rows)} != 594")

    with target.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(output_rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(output_rows)

    return {
        "status": "derived_identity_sidecar_materialized",
        "path": str(target.relative_to(root)),
        "derived": True,
        "row_count": len(output_rows),
        "task_count": len(tasks),
        "candidate_distribution": {str(key): value for key, value in sorted(distribution.items())},
        "derivation": "complete frozen pairwise task-worker universe joined one-to-one to frozen canonical geometry",
        "excluded_recomputations": [
            "geometry",
            "pairwise scores",
            "quality",
            "structural validity",
            "reference status",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--replicates", type=int, default=audit.REPLICATES)
    args = parser.parse_args()

    root = args.root.resolve()
    output = args.output_dir.resolve()
    provenance = materialize_missing_identity_sidecar(root)
    result = audit.run(root, output, args.replicates)
    (result / "DERIVED_GEOMETRY_POOL_IDENTITY_PROVENANCE.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(result)


if __name__ == "__main__":
    main()
