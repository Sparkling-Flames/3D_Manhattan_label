"""Compare and materialize W034 original-only versus authorized-augmented profiles."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

METRICS = ("Q_GT_EB", "R_peer_all", "F_struct_EB")


def _number(row: dict[str, Any], field: str) -> float | None:
    try:
        return float(row[field])
    except (KeyError, TypeError, ValueError):
        return None


def compare_w034_profiles(original: dict[str, Any], augmented: dict[str, Any], thresholds: dict[str, Any]) -> dict[str, Any]:
    if str(original.get("worker_id", "")).lstrip("W0") != "34" or str(augmented.get("worker_id", "")).lstrip("W0") != "34":
        raise ValueError("W034 sensitivity requires worker 34 in both profiles")
    required = {"maximum_rank_displacement", "maximum_absolute_metric_change", "version"}
    if not required.issubset(thresholds):
        raise ValueError("W034 sensitivity thresholds are not frozen")
    output: dict[str, Any] = {"worker_id": "34", "profile_comparison": "original_only_vs_original_plus_authorized"}
    metric_sensitive = False
    for metric in METRICS:
        left, right = _number(original, metric), _number(augmented, metric)
        if left is None or right is None:
            raise ValueError(f"W034 sensitivity metric missing:{metric}")
        output[f"original_{metric}"] = left
        output[f"augmented_{metric}"] = right
        output[f"difference_{metric}"] = right - left
        if abs(right - left) > float(thresholds["maximum_absolute_metric_change"]):
            metric_sensitive = True
    original_rank = _number(original, "global_rank")
    augmented_rank = _number(augmented, "global_rank")
    original_support = _number(original, "task_support")
    augmented_support = _number(augmented, "task_support")
    if None in {original_rank, augmented_rank, original_support, augmented_support}:
        raise ValueError("W034 sensitivity rank/support fields are incomplete")
    displacement = abs(float(augmented_rank) - float(original_rank))
    output.update({
        "original_rank": original_rank, "augmented_rank": augmented_rank,
        "rank_displacement": displacement,
        "support_difference": float(augmented_support) - float(original_support),
        "authorized_extension_sensitive": metric_sensitive or displacement > float(thresholds["maximum_rank_displacement"]),
        "sensitivity_threshold_version": thresholds["version"],
    })
    return output


def _one_w034(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = [row for row in csv.DictReader(stream) if str(row.get("worker_id", "")).lstrip("W0") == "34"]
    if len(rows) != 1:
        raise ValueError(f"expected exactly one W034 profile row:{path}")
    return rows[0]


def materialize(original_csv: Path, augmented_csv: Path, thresholds_json: Path, output_json: Path) -> dict[str, Any]:
    thresholds = json.loads(thresholds_json.read_text(encoding="utf-8"))
    result = compare_w034_profiles(_one_w034(original_csv), _one_w034(augmented_csv), thresholds)
    result["input_sha256"] = {
        "original_profile": hashlib.sha256(original_csv.read_bytes()).hexdigest(),
        "augmented_profile": hashlib.sha256(augmented_csv.read_bytes()).hexdigest(),
        "thresholds": hashlib.sha256(thresholds_json.read_bytes()).hexdigest(),
    }
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--original-profile", type=Path, required=True)
    parser.add_argument("--augmented-profile", type=Path, required=True)
    parser.add_argument("--thresholds", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(materialize(args.original_profile, args.augmented_profile, args.thresholds, args.output), indent=2))


if __name__ == "__main__":
    main()
