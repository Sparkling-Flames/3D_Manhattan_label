"""Materialize task-condition-estimand-specific C1 support.

The original assignment fixes k_target. Authorized replacements restore that
target; late entrants expand the pooled cohort. Outside submissions are
observable audit evidence but never formal support.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


ESTIMANDS: dict[str, tuple[str, ...]] = {
    "GT": ("gt_primary_analysis_eligible", "global_analysis_eligible"),
    "peer": ("peer_analysis_eligible",),
    "LOO": ("loo_analysis_eligible", "strict_loo_analysis_eligible"),
    "structural": ("structural_opportunity_eligible",),
    "time": ("time_analysis_eligible",),
    "semi_correction": ("semi_correction_analysis_eligible",),
    "predictive_validity": ("predictive_validity_analysis_eligible",),
    "routing_feature": ("routing_feature_analysis_eligible",),
}


def _truth(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def _read(path: Path | None) -> list[dict[str, str]]:
    if path is None or not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _write(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(key for row in rows for key in row))
    if not fields:
        fields = ["base_task_id", "condition", "dataset_group", "k_target"]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _condition(row: dict[str, Any], source: Path | None = None) -> str:
    value = str(row.get("condition", "")).strip().lower()
    if value:
        return value
    return "semi" if source and "semi" in source.name.lower() else "manual"


def _assignment_sets(
    original_paths: Iterable[Path], authorized_path: Path | None, late_path: Path | None,
) -> tuple[dict[tuple[str, str], set[str]], dict[tuple[str, str], set[str]], dict[tuple[str, str], set[str]], dict[tuple[str, str], set[str]]]:
    original: dict[tuple[str, str], set[str]] = defaultdict(set)
    authorized: dict[tuple[str, str], set[str]] = defaultdict(set)
    late: dict[tuple[str, str], set[str]] = defaultdict(set)
    groups: dict[tuple[str, str], set[str]] = defaultdict(set)
    for path in original_paths:
        for row in _read(path):
            key = (str(row.get("base_task_id", "")).strip(), _condition(row, path))
            worker = str(row.get("worker_id", "")).strip()
            if all((*key, worker)):
                original[key].add(worker)
                groups[key].add(str(row.get("dataset_group", "")).strip())
    for row in _read(authorized_path):
        key = (str(row.get("base_task_id", "")).strip(), _condition(row))
        worker = str(row.get("replacement_worker_id") or row.get("worker_id") or "").strip()
        if all((*key, worker)):
            authorized[key].add(worker)
            groups[key].add(str(row.get("dataset_group", "")).strip())
    for row in _read(late_path):
        key = (str(row.get("base_task_id", "")).strip(), _condition(row))
        worker = str(row.get("worker_id", "")).strip()
        if all((*key, worker)):
            late[key].add(worker)
            groups[key].add(str(row.get("dataset_group", "")).strip())
    return original, authorized, late, groups


def _eligible(row: dict[str, Any], estimand: str) -> bool:
    for field in ESTIMANDS[estimand]:
        if field in row and str(row.get(field, "")).strip() != "":
            return _truth(row.get(field))
    if estimand == "time":
        return _truth(row.get("active_time_expected")) and _truth(row.get("primary_active_time_eligible"))
    return False


def build_task_support_rows(
    original_paths: list[Path], authorized_path: Path | None, late_path: Path | None,
    canonical_rows: list[dict[str, str]], eligibility_rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    original, authorized, late, groups = _assignment_sets(original_paths, authorized_path, late_path)
    eligibility = {row.get("canonical_annotation_id", ""): row for row in eligibility_rows}
    observed: dict[tuple[str, str], set[str]] = defaultdict(set)
    eligible: dict[tuple[str, str], dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    seen: dict[tuple[str, str, str], str] = {}
    for canonical in canonical_rows:
        base = str(canonical.get("base_task_id", "")).strip()
        condition = _condition(canonical)
        worker = str(canonical.get("worker_id", "")).strip()
        annotation = str(canonical.get("canonical_annotation_id", "")).strip()
        if not all((base, condition, worker, annotation)):
            continue
        unique = (base, condition, worker)
        previous = seen.get(unique)
        if previous and previous != annotation:
            raise ValueError(f"duplicate canonical worker-base-condition:{unique}")
        seen[unique] = annotation
        key = (base, condition)
        observed[key].add(worker)
        groups[key].add(str(canonical.get("dataset_group", "")).strip())
        provenance = str(canonical.get("assignment_provenance", "")).strip()
        if provenance not in {
            "original_assignment", "authorized_replacement_assignment",
            "late_entry_calibration_assignment", "outside_assignment_submission",
        }:
            continue
        if provenance == "outside_assignment_submission" or _truth(canonical.get("outside_assignment_submission")):
            continue
        merged = {**canonical, **eligibility.get(annotation, {})}
        for estimand in ESTIMANDS:
            if _eligible(merged, estimand):
                eligible[key][estimand].add(worker)

    keys = sorted(set(original) | set(authorized) | set(late) | set(observed))
    rows: list[dict[str, Any]] = []
    for key in keys:
        a0 = set(original[key])
        ar = set(authorized[key]) - a0
        al = set(late[key]) - a0 - ar
        formal = a0 | ar | al
        outside = observed[key] - formal
        row: dict[str, Any] = {
            "base_task_id": key[0],
            "condition": key[1],
            "dataset_group": ";".join(sorted(value for value in groups[key] if value)),
            "k_target": len(a0),
            "k_observed_unique": len(observed[key]),
            "k_outside_observed": len(outside),
        }
        for estimand in ESTIMANDS:
            e = eligible[key][estimand]
            k0, kr, kl = len(a0 & e), len(ar & e), len(al & e)
            final = len(formal & e)
            row[f"k_original_{estimand}"] = k0
            row[f"k_authorized_{estimand}"] = kr
            row[f"k_late_{estimand}"] = kl
            row[f"k_final_{estimand}"] = final
            row[f"support_deficit_after_authorized_{estimand}"] = max(0, len(a0) - k0 - kr)
            row[f"pooled_support_excess_{estimand}"] = max(0, final - len(a0))
        row["support_deficit_after_authorized"] = row["support_deficit_after_authorized_GT"]
        row["pooled_support_excess"] = row["pooled_support_excess_GT"]
        rows.append(row)
    return rows


def materialize(
    original_paths: list[Path], canonical_csv: Path, eligibility_csv: Path, output_dir: Path,
    *, authorized_path: Path | None = None, late_path: Path | None = None,
) -> dict[str, Any]:
    rows = build_task_support_rows(
        original_paths, authorized_path, late_path, _read(canonical_csv), _read(eligibility_csv)
    )
    output = output_dir / "c1_estimand_specific_task_support.csv"
    _write(output, rows)
    summary = {
        "schema_version": "c1_estimand_specific_task_support_v1",
        "n_task_conditions": len(rows),
        "estimands": list(ESTIMANDS),
        "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "authorized_manifest_sha256": hashlib.sha256(authorized_path.read_bytes()).hexdigest() if authorized_path and authorized_path.exists() else "",
        "late_entry_manifest_sha256": hashlib.sha256(late_path.read_bytes()).hexdigest() if late_path and late_path.exists() else "",
    }
    (output_dir / "c1_estimand_specific_task_support.summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--original-assignment", action="append", type=Path, required=True)
    parser.add_argument("--authorized-reassignment", type=Path)
    parser.add_argument("--late-entry-assignment", type=Path)
    parser.add_argument("--canonical-csv", type=Path, required=True)
    parser.add_argument("--eligibility-csv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(materialize(
        args.original_assignment, args.canonical_csv, args.eligibility_csv, args.output_dir,
        authorized_path=args.authorized_reassignment, late_path=args.late_entry_assignment,
    ), indent=2))


if __name__ == "__main__":
    main()
