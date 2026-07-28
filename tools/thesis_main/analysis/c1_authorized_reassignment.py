"""Validate immutable C1 authorized-reassignment addenda."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any


FIELDS = (
    "round_id", "condition", "dataset_group", "task_id", "base_task_id",
    "displaced_worker_id", "replacement_worker_id",
    "original_assignment_manifest_sha256", "original_assignment_row_sha256",
    "authorization_reason", "authorized_by", "authorized_at",
    "replacement_project_id", "replacement_runtime_task_id", "active_time_expected",
)


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assignment_row_sha256(row: dict[str, Any]) -> str:
    identity = {key: str(row.get(key, "")).strip() for key in ("round_id", "worker_id", "task_id", "base_task_id", "dataset_group")}
    return hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _image_keys(row: dict[str, str]) -> set[str]:
    return {
        Path(str(row.get(field, "")).strip()).stem
        for field in ("image_id", "base_task_id", "task_id", "task_label", "base_image_key")
        if str(row.get(field, "")).strip()
    }


def validate_authorized_reassignments(
    manifest_csv: Path | None, assignment_csvs: list[Path], runtime_rows: list[dict[str, str]],
    inventory_csv: Path, p1_canonical_csv: Path, p1_admission_csv: Path,
    *, c1_observed_rows: list[dict[str, str]] | None = None,
) -> tuple[dict[tuple[str, str, str], dict[str, str]], dict[str, Any]]:
    if manifest_csv is None:
        return {}, {"status": "not_provided", "row_count": 0, "valid": True}
    rows = _read(manifest_csv)
    if not rows:
        return {}, {"status": "empty", "row_count": 0, "valid": True, "manifest_sha256": _sha(manifest_csv)}
    missing_fields = [field for field in FIELDS if field not in rows[0]]
    if missing_fields:
        raise ValueError(f"authorized reassignment schema missing:{','.join(missing_fields)}")
    assignment_sources: dict[tuple[str, str, str, str], tuple[dict[str, str], str]] = {}
    original_worker_bases: set[tuple[str, str]] = set()
    for path in assignment_csvs:
        digest = _sha(path)
        for item in _read(path):
            worker = str(item.get("worker_id", "")).strip()
            base = str(item.get("base_task_id", "")).strip()
            key = (worker, str(item.get("task_id", "")).strip(), base, str(item.get("dataset_group", "")).strip())
            if key in assignment_sources:
                raise ValueError(f"duplicate original assignment edge:{key}")
            assignment_sources[key] = (item, digest)
            original_worker_bases.add((worker, base))
    runtime = {
        (str(item.get("project_id", "")).strip(), str(item.get("ls_runtime_task_id", "")).strip()): item
        for item in runtime_rows
    }
    admitted = {
        str(item.get("worker_id", "")).strip()
        for item in _read(p1_admission_csv)
        if str(item.get("admission_status", "")).startswith("pass") and str(item.get("worker_id", "")).strip()
    }
    inventory = {str(item.get("base_task_id", "")).strip(): _image_keys(item) for item in _read(inventory_csv)}
    original_exposure = {
        (worker, identity)
        for worker, base in original_worker_bases
        for identity in inventory.get(base, {base})
    }
    observed_exposure: dict[tuple[str, str], set[tuple[str, str]]] = {}
    for item in c1_observed_rows or []:
        worker = str(item.get("worker_id") or item.get("annotator_id") or "").strip()
        runtime_identity = (
            str(item.get("project_id", "")).strip(),
            str(item.get("ls_runtime_task_id", "")).strip(),
        )
        identities = _image_keys(item)
        expanded = set(identities)
        for identity in identities:
            expanded.update(inventory.get(identity, {identity}))
        for identity in expanded:
            if worker and identity:
                observed_exposure.setdefault((worker, identity), set()).add(runtime_identity)
    p1_exposure: set[tuple[str, str]] = set()
    for item in _read(p1_canonical_csv):
        worker = str(item.get("annotator_id") or item.get("worker_id") or "").strip()
        for identity in _image_keys(item):
            p1_exposure.add((worker, identity))
    output: dict[tuple[str, str, str], dict[str, str]] = {}
    replacement_edges: set[tuple[str, str]] = set()
    displaced_edges: set[tuple[str, str]] = set()
    for row in rows:
        if any(not str(row.get(field, "")).strip() for field in FIELDS):
            raise ValueError("authorized reassignment rows require every field")
        if row["round_id"] != "C1" or row["replacement_worker_id"] == row["displaced_worker_id"]:
            raise ValueError("invalid C1 replacement worker identity")
        original_key = (row["displaced_worker_id"], row["task_id"], row["base_task_id"], row["dataset_group"])
        source = assignment_sources.get(original_key)
        if source is None:
            raise ValueError(f"displaced assignment edge missing:{original_key}")
        original, source_sha = source
        if source_sha != row["original_assignment_manifest_sha256"] or assignment_row_sha256(original) != row["original_assignment_row_sha256"]:
            raise ValueError("stale authorized reassignment assignment binding")
        expected_condition = "semi" if "semi" in row["dataset_group"].lower() else "manual"
        if row["condition"].lower() != expected_condition:
            raise ValueError("authorized reassignment condition mismatch")
        runtime_row = runtime.get((row["replacement_project_id"], row["replacement_runtime_task_id"]))
        if not runtime_row or any(str(runtime_row.get(field, "")).strip() != row[field] for field in ("task_id", "base_task_id", "dataset_group")) or str(runtime_row.get("condition", "")).strip().lower() != row["condition"].lower():
            raise ValueError("authorized reassignment runtime mapping mismatch")
        worker, base = row["replacement_worker_id"], row["base_task_id"]
        if worker not in admitted:
            raise ValueError(f"replacement worker is not P1 admitted:{worker}")
        image_identities = inventory.get(base, {base})
        if any((worker, identity) in original_exposure for identity in image_identities):
            raise ValueError(f"replacement worker already has C1 exposure:{worker}|{base}")
        replacement_runtime = (row["replacement_project_id"], row["replacement_runtime_task_id"])
        if any(
            any(observed_runtime != replacement_runtime for observed_runtime in observed_exposure.get((worker, identity), set()))
            for identity in image_identities
        ):
            raise ValueError(f"replacement worker already has observed C1 exposure:{worker}|{base}")
        if any((worker, identity) in p1_exposure for identity in image_identities):
            raise ValueError(f"replacement worker already has P1 exposure:{worker}|{base}")
        if any((worker, identity) in replacement_edges for identity in image_identities) or (row["displaced_worker_id"], base) in displaced_edges:
            raise ValueError("duplicate authorized reassignment edge")
        replacement_edges.update((worker, identity) for identity in image_identities); displaced_edges.add((row["displaced_worker_id"], base))
        identity = (row["replacement_project_id"], row["replacement_runtime_task_id"], worker)
        if identity in output:
            raise ValueError("duplicate authorized reassignment runtime identity")
        output[identity] = row
    return output, {
        "status": "validated", "valid": True, "row_count": len(rows),
        "manifest_sha256": _sha(manifest_csv),
        "replacement_worker_count": len({row["replacement_worker_id"] for row in rows}),
        "displaced_worker_count": len({row["displaced_worker_id"] for row in rows}),
    }
