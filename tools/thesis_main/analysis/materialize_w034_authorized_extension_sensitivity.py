"""Compare and materialize W034 original-only versus authorized-augmented profiles."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from tools.thesis_main.analysis.paper_a_contracts import METHOD_CONTRACT, sha256_file

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


def _one_w034(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        all_rows = list(csv.DictReader(stream))
    rows = [row for row in all_rows if str(row.get("worker_id", "")).lstrip("W0") == "34"]
    if len(rows) != 1:
        raise ValueError(f"expected exactly one W034 profile row:{path}")
    row = dict(rows[0])
    score_field = "S_G" if _number(row, "S_G") is not None else "Q_GT_EB"
    ranked = sorted(
        ((candidate, _number(candidate, score_field)) for candidate in all_rows),
        key=lambda item: (item[1] is None, -(item[1] or 0.0), str(item[0].get("worker_id", ""))),
    )
    rank = next((index for index, (candidate, value) in enumerate(ranked, 1) if value is not None and str(candidate.get("worker_id", "")).lstrip("W0") == "34"), None)
    if rank is None:
        raise ValueError(f"W034 profile has no finite {score_field}:{path}")
    row["global_rank"] = rank
    return row


def materialize(original_csv: Path, augmented_csv: Path, thresholds_json: Path | None, output_json: Path, *, profile_version: str | None = None, cohort_id: str | None = None, status: str = "frozen", authorized_completed_count: int = 17, expected_authorized_count: int = 17) -> dict[str, Any]:
    if status not in {"pending_authorized_completion", "provisional_augmented", "frozen"}:
        raise ValueError("unsupported W034 sensitivity status")
    if expected_authorized_count != 17 or not 0 <= authorized_completed_count <= expected_authorized_count:
        raise ValueError("W034 authorized completion count must be within the frozen 17-row repair set")
    if status == "pending_authorized_completion" and authorized_completed_count != 0:
        raise ValueError("pending W034 sensitivity requires zero authorized completions")
    if status == "provisional_augmented" and not 0 < authorized_completed_count < expected_authorized_count:
        raise ValueError("provisional W034 sensitivity requires partial authorized completion")
    if status == "frozen" and authorized_completed_count != expected_authorized_count:
        raise ValueError("frozen W034 sensitivity requires all authorized rows")
    original, augmented = _one_w034(original_csv), _one_w034(augmented_csv)
    thresholds = json.loads(thresholds_json.read_text(encoding="utf-8")) if thresholds_json else None
    result = compare_w034_profiles(original, augmented, thresholds) if thresholds else {
        "worker_id": "34", "profile_comparison": "original_only_vs_current_augmented",
        "comparison_status": "thresholds_not_provided",
    }
    result.update({
        "schema_version": "w034_authorized_extension_sensitivity_freeze_v1",
        "status": status,
        "artifact_role": "W034_SENSITIVITY_FROZEN" if status == "frozen" else "W034_SENSITIVITY_PROVISIONAL",
        "authorized_completed_count": authorized_completed_count,
        "expected_authorized_count": expected_authorized_count,
        "profile_version": profile_version or augmented.get("profile_version") or "paper_a_worker_profile_v2",
        "cohort_id": cohort_id or augmented.get("cohort_id") or "paper_a_calibration_pooled",
        "method_contract_sha256": sha256_file(METHOD_CONTRACT),
    })
    result["input_sha256"] = {
        "original_profile": sha256_file(original_csv),
        "augmented_profile": sha256_file(augmented_csv),
        "thresholds": sha256_file(thresholds_json) if thresholds_json else "",
    }
    result["dependencies"] = [
        {"role": "W034_ORIGINAL_PROFILE", "path": str(original_csv.resolve()), "sha256": sha256_file(original_csv)},
        {"role": "W034_AUTHORIZED_PROFILE", "path": str(augmented_csv.resolve()), "sha256": sha256_file(augmented_csv)},
        {"role": "METHOD_CONTRACT", "path": str(METHOD_CONTRACT.resolve()), "sha256": sha256_file(METHOD_CONTRACT)},
    ]
    if thresholds_json:
        result["dependencies"].append({"role": "W034_SENSITIVITY_THRESHOLDS", "path": str(thresholds_json.resolve()), "sha256": sha256_file(thresholds_json)})
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
