"""Reconstruct the missing C1 geometry-repair sidecar for the v4 audit.

This is a CI-only, append-only development helper. It uses the frozen
``structural_validation_analysis.csv`` disposition fields and frozen canonical
geometry. The only repair currently represented in the frozen ledger is the
removal of one recoverable orphan point at ``dropped_point_index``.

The file is created only in the ephemeral workflow checkout. It is not claimed
to be the unavailable historical producer output and it is never committed as
a frozen C1 artifact.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


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


def _truth(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "passed", "valid"}


def _int(value: Any) -> int | None:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def _key(row: dict[str, Any]) -> str:
    return str(row.get("canonical_annotation_id") or row.get("annotation_id") or "")


def materialize(root: Path) -> Path:
    base = (
        root
        / "analysis_results"
        / "c1_formal_audit_20260802_v16_final"
        / "c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03"
    )
    target = base / "c1_geometry_repair_audit.csv"
    if target.exists():
        return target

    structural_rows = _read_csv(base / "structural_validation_analysis.csv")
    structural_by_id = {_key(row): row for row in structural_rows if _key(row)}
    canonical_rows = _read_jsonl(base / "c1_canonical_geometry.jsonl")

    output: list[dict[str, Any]] = []
    repaired_count = 0
    for canonical in canonical_rows:
        annotation = _key(canonical)
        if not annotation:
            continue
        structural = structural_by_id.get(annotation)
        if structural is None:
            continue
        raw_points = list(canonical.get("corners_px") or [])
        repair_applied = _truth(structural.get("geometry_repair_applied"))
        dropped_index = _int(structural.get("dropped_point_index"))
        repaired_points: list[Any] = []
        if repair_applied:
            if dropped_index is None or dropped_index < 0 or dropped_index >= len(raw_points):
                raise AssertionError(
                    f"repair-applied row lacks a valid dropped_point_index: {annotation}"
                )
            repaired_points = [point for index, point in enumerate(raw_points) if index != dropped_index]
            repaired_count += 1
            expected = _int(structural.get("repaired_point_count"))
            if expected is not None and expected != len(repaired_points):
                raise AssertionError(
                    f"repaired point-count mismatch for {annotation}: "
                    f"{len(repaired_points)} != {expected}"
                )
        output.append({
            "base_task_id": structural.get("base_task_id") or canonical.get("base_task_id") or "",
            "condition": structural.get("condition") or canonical.get("condition") or "",
            "worker_id": structural.get("worker_id") or canonical.get("worker_id") or "",
            "canonical_annotation_id": annotation,
            "annotation_id": annotation,
            "geometry_repair_applied": repair_applied,
            "dropped_point_index": dropped_index if repair_applied else "",
            "repaired_points_json": json.dumps(repaired_points, separators=(",", ":")) if repair_applied else "",
            "raw_geometry_sha256": structural.get("raw_geometry_sha256") or structural.get("geometry_sha256") or "",
            "repaired_geometry_sha256": structural.get("repaired_geometry_sha256") or "",
            "geometry_repair_status": structural.get("geometry_repair_status") or (
                "reconstructed_orphan_point_removal" if repair_applied else "not_needed"
            ),
            "reconstruction_source": "frozen_structural_disposition_plus_canonical_geometry",
        })

    if not output:
        raise AssertionError("no repair-sidecar rows were reconstructed")
    for row in output:
        if row["geometry_repair_applied"] and not row["repaired_geometry_sha256"]:
            raise AssertionError(
                f"repair-applied row lacks frozen repaired geometry SHA: "
                f"{row['canonical_annotation_id']}"
            )
        if not row["geometry_repair_applied"] and not row["raw_geometry_sha256"]:
            raise AssertionError(
                f"unrepaired row lacks frozen raw geometry SHA: "
                f"{row['canonical_annotation_id']}"
            )

    with target.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(output[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(output)

    provenance = {
        "status": "temporary_repair_sidecar_materialized",
        "row_count": len(output),
        "repair_applied_count": repaired_count,
        "repair_rule": "remove the frozen dropped_point_index from canonical corners_px",
        "historical_producer_output_available": False,
    }
    (target.parent / "c1_geometry_repair_audit_v4_reconstruction_provenance.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return target


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    print(materialize(args.root.resolve()))


if __name__ == "__main__":
    main()
