"""CI runner for the append-only topology preflight v4 audit.

Two v3 input sidecars are not committed on ``codex/paper``:
``c1_geometry_pool_eligibility.csv`` and
``geometry_pairwise_similarity_C1.csv``.  The frozen task crowd-structure
sidecar does contain the complete 594 candidate identities.  This runner:

1. reconstructs the geometry-pool identity allowlist by flattening the frozen
   cluster membership of the 78 manual tasks with ``valid_k >= 5``;
2. binds those identities one-to-one to frozen canonical geometry;
3. recomputes a temporary pairwise sidecar with the currently committed C1
   normalizer and pairwise code;
4. validates current cluster status and membership against the frozen C1
   task sidecar before running the append-only v4 audit.

The temporary pairwise scores are *not* represented as the missing historical
frozen sidecar.  Their provenance and every resulting mismatch are emitted.
No original artifact is overwritten in Git history.
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
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


def _truth(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "passed", "valid"}


def _key(row: dict[str, Any]) -> str:
    return str(row.get("canonical_annotation_id") or row.get("annotation_id") or "")


def _serialise(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def _normalised_geometry(
    canonical: dict[str, Any],
    repair: dict[str, Any],
) -> dict[str, Any]:
    repair_applied = _truth(repair.get("geometry_repair_applied"))
    points = (
        json.loads(str(repair.get("repaired_points_json") or "[]"))
        if repair_applied
        else canonical.get("corners_px") or []
    )
    result = v3.normalize_geometry_for_c1_calculation(
        points,
        width=_int(canonical.get("width")) or 1024,
        height=_int(canonical.get("height")) or 512,
    )
    result.update({
        "base_task_id": str(canonical.get("base_task_id") or ""),
        "worker_id": _int(canonical.get("worker_id")),
        "canonical_annotation_id": _key(canonical),
    })
    return result


def _flatten_membership(row: dict[str, str]) -> list[str]:
    membership = json.loads(str(row.get("cluster_membership_json") or "[]"))
    identities = [str(annotation) for group in membership for annotation in group]
    if len(identities) != len(set(identities)):
        raise AssertionError(f"duplicate frozen membership identity: {row.get('base_task_id')}")
    return identities


def materialize_missing_sidecars(root: Path) -> dict[str, Any]:
    base = v3.c1_root(root)
    pool_target = base / "c1_geometry_pool_eligibility.csv"
    pairwise_target = base / "geometry_pairwise_similarity_C1.csv"

    task_rows = [
        row for row in _read_csv(base / "geometry_task_crowd_structure_C1.csv")
        if row.get("condition") == "manual" and (_int(row.get("valid_k")) or 0) >= 5
    ]
    if len(task_rows) != 78:
        raise AssertionError(f"manual k>=5 task denominator drifted: {len(task_rows)} != 78")
    task_by_id = {str(row["base_task_id"]): row for row in task_rows}
    if len(task_by_id) != len(task_rows):
        raise AssertionError("duplicate manual k>=5 task rows")

    identities_by_task: dict[str, list[str]] = {}
    for task, row in task_by_id.items():
        identities = _flatten_membership(row)
        valid_k = _int(row.get("valid_k"))
        if valid_k != len(identities):
            raise AssertionError(
                f"frozen membership does not cover valid_k for {task}: "
                f"{len(identities)} != {valid_k}"
            )
        identities_by_task[task] = identities

    distribution = Counter(len(values) for values in identities_by_task.values())
    if distribution != Counter({5: 66, 22: 12}):
        raise AssertionError(f"frozen membership distribution drifted: {dict(distribution)}")
    if sum(map(len, identities_by_task.values())) != 594:
        raise AssertionError("frozen membership candidate total is not 594")

    canonical_rows = _read_jsonl(base / "c1_canonical_geometry.jsonl")
    canonical_by_id: dict[str, dict[str, Any]] = {}
    for row in canonical_rows:
        annotation = _key(row)
        if annotation:
            if annotation in canonical_by_id:
                raise AssertionError(f"duplicate canonical annotation identity: {annotation}")
            canonical_by_id[annotation] = row

    repair_by_id = {
        _key(row): row
        for row in _read_csv(base / "c1_geometry_repair_audit.csv")
        if _key(row)
    }

    pool_rows: list[dict[str, Any]] = []
    normalised_by_id: dict[str, dict[str, Any]] = {}
    workers_by_task: dict[str, set[int]] = defaultdict(set)
    for task in sorted(identities_by_task):
        for annotation in identities_by_task[task]:
            canonical = canonical_by_id.get(annotation)
            if canonical is None:
                raise AssertionError(f"frozen membership has no canonical geometry: {annotation}")
            if str(canonical.get("base_task_id") or "") != task:
                raise AssertionError(f"frozen membership/canonical task conflict: {annotation}")
            worker = _int(canonical.get("worker_id"))
            if worker is None or worker in workers_by_task[task]:
                raise AssertionError(f"non-unique task-worker candidate: {task}/{worker}")
            workers_by_task[task].add(worker)
            pool_rows.append({
                "base_task_id": task,
                "condition": "manual",
                "worker_id": worker,
                "canonical_annotation_id": annotation,
                "annotation_id": annotation,
                "geometry_pool_eligible": True,
                "identity_derivation": "flattened_frozen_cluster_membership",
            })
            normalised_by_id[annotation] = _normalised_geometry(
                canonical,
                repair_by_id.get(annotation, {}),
            )

    with pool_target.open("w", encoding="utf-8", newline="") as stream:
        fields = list(pool_rows[0])
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in pool_rows:
            writer.writerow({key: _serialise(value) for key, value in row.items()})

    pairwise_rows: list[dict[str, Any]] = []
    for task in sorted(identities_by_task):
        identities = identities_by_task[task]
        for left_id, right_id in itertools.combinations(identities, 2):
            left = canonical_by_id[left_id]
            right = canonical_by_id[right_id]
            left_worker = _int(left.get("worker_id"))
            right_worker = _int(right.get("worker_id"))
            if left_worker is None or right_worker is None:
                raise AssertionError("pairwise worker identity is incomplete")
            metric = v3.pairwise_similarity(
                normalised_by_id[left_id],
                normalised_by_id[right_id],
            )
            pairwise_rows.append({
                "base_task_id": task,
                "condition": "manual",
                "canonical_annotation_id_left": left_id,
                "canonical_annotation_id_right": right_id,
                "worker_id_left": left_worker,
                "worker_id_right": right_worker,
                "metric_compatible": bool(metric.get("metric_compatible")),
                "pointwise_correspondence_compatible": bool(metric.get("pointwise_correspondence_compatible")),
                "q_boundary": metric.get("q_boundary", metric.get("boundary_similarity")),
                "q_wallwall": metric.get("q_wallwall", metric.get("wallwall_similarity")),
                "pairwise_derivation": "current_committed_normalizer_and_pairwise_code",
            })

    expected_pairs = 66 * math.comb(5, 2) + 12 * math.comb(22, 2)
    if len(pairwise_rows) != expected_pairs:
        raise AssertionError(f"derived pairwise coverage drifted: {len(pairwise_rows)} != {expected_pairs}")
    with pairwise_target.open("w", encoding="utf-8", newline="") as stream:
        fields = list(pairwise_rows[0])
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in pairwise_rows:
            writer.writerow({key: _serialise(value) for key, value in row.items()})

    return {
        "status": "temporary_missing_sidecars_materialized",
        "task_count": len(task_rows),
        "pool_row_count": len(pool_rows),
        "pairwise_row_count": len(pairwise_rows),
        "candidate_distribution": {str(key): value for key, value in sorted(distribution.items())},
        "pool_identity_source": "frozen geometry_task_crowd_structure_C1 cluster_membership_json",
        "pairwise_source": "current committed normalizer and pairwise implementation",
        "pairwise_is_historical_frozen_sidecar": False,
        "permitted_interpretation": "current-code development replay with frozen terminal medoid binding; not exact source-level replay of the missing historical pairwise sidecar",
    }


def validate_current_clusters(data: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for task, candidates in sorted(data["candidates"].items()):
        frozen = data["tasks"][task]
        current = v3._cluster(candidates, task)
        frozen_members = audit._normalise_membership(frozen.get("cluster_membership_json"))
        current_members = audit._normalise_membership(current.get("cluster_membership_json"))
        rows.append({
            "base_task_id": task,
            "building_id": frozen.get("building_id", ""),
            "candidate_n": len(candidates),
            "cluster_status_match": str(frozen.get("task_crowd_structure_status") or "") == str(current.get("task_crowd_structure_status") or ""),
            "cluster_membership_match": frozen_members == current_members,
            "frozen_status": frozen.get("task_crowd_structure_status"),
            "current_status": current.get("task_crowd_structure_status"),
            "frozen_medoid_annotation_id": frozen.get("largest_cluster_medoid_annotation_id"),
            "current_medoid_annotation_id": current.get("largest_cluster_medoid_annotation_id"),
            "medoid_match": str(frozen.get("largest_cluster_medoid_annotation_id") or "") == str(current.get("largest_cluster_medoid_annotation_id") or ""),
        })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--replicates", type=int, default=audit.REPLICATES)
    args = parser.parse_args()

    root = args.root.resolve()
    output = args.output_dir.resolve()
    provenance = materialize_missing_sidecars(root)
    data = v3.load_frozen_inputs(root)
    validation_rows = validate_current_clusters(data)

    result = audit.run(root, output, args.replicates)
    provenance["cluster_validation"] = {
        "task_count": len(validation_rows),
        "status_mismatch_count": sum(not row["cluster_status_match"] for row in validation_rows),
        "membership_mismatch_count": sum(not row["cluster_membership_match"] for row in validation_rows),
        "medoid_mismatch_count": sum(not row["medoid_match"] for row in validation_rows),
        "exact_k5_status_mismatch_count": sum(
            row["candidate_n"] == 5 and not row["cluster_status_match"] for row in validation_rows
        ),
        "exact_k5_membership_mismatch_count": sum(
            row["candidate_n"] == 5 and not row["cluster_membership_match"] for row in validation_rows
        ),
        "exact_k5_medoid_mismatch_count": sum(
            row["candidate_n"] == 5 and not row["medoid_match"] for row in validation_rows
        ),
    }
    (result / "DERIVED_SIDECAR_PROVENANCE.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    audit._write_csv(result / "DERIVED_PAIRWISE_CLUSTER_VALIDATION.csv", validation_rows)

    manifest_path = result / "analysis_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["derived_sidecar_provenance"] = "DERIVED_SIDECAR_PROVENANCE.json"
    manifest["derived_pairwise_cluster_validation"] = "DERIVED_PAIRWISE_CLUSTER_VALIDATION.csv"
    manifest["output_files"] = sorted(path.name for path in result.iterdir())
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(result)


if __name__ == "__main__":
    main()
