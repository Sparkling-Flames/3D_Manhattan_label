"""Materialize Strong Global audit ranks; formal output is manifest-gated."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
from pathlib import Path
from statistics import mean, stdev
from typing import Any


def _truth(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def _number(row: dict[str, Any], key: str) -> float | None:
    try:
        value = float(row[key])
    except (KeyError, TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _explicit_truth(row: dict[str, Any], keys: tuple[str, ...], default: bool = False) -> bool:
    for key in keys:
        if key in row and str(row.get(key, "")).strip() != "":
            return _truth(row.get(key))
    return default


def _administratively_eligible(row: dict[str, Any]) -> bool:
    return _explicit_truth(row, ("administratively_eligible", "administrative_eligible", "administrative_eligibility"))


def _q_gt_estimable(row: dict[str, Any]) -> bool:
    return _number(row, "Q_GT_EB") is not None and _explicit_truth(row, ("Q_GT_estimable", "q_gt_estimable"))


def _gate_signal(row: dict[str, Any], flag: str, support: str) -> bool:
    if flag in row and str(row.get(flag, "")).strip() != "":
        return _truth(row.get(flag))
    value = _number(row, support)
    return value is not None and value > 0


def _frozen_z_parameters(rows: list[dict[str, Any]]) -> tuple[float, float, int]:
    values = [_number(row, "Q_GT_EB") for row in rows if _administratively_eligible(row) and _q_gt_estimable(row)]
    finite = [value for value in values if value is not None]
    if len(finite) < 2:
        raise ValueError("Strong Global requires at least two administratively eligible Q_GT estimable workers")
    center = mean(finite)
    spread = stdev(finite)
    if not math.isfinite(center) or not math.isfinite(spread) or spread <= 0:
        raise ValueError("Strong Global z-score parameters are non-finite or have zero standard deviation")
    return float(center), float(spread), len(finite)


def build_global_policy(rows: list[dict[str, Any]], manifest: dict[str, Any], *, formal: bool = False) -> list[dict[str, Any]]:
    approved = manifest.get("status") == "approved" and manifest.get("interpretation_allowed") is True and manifest.get("approved_by") and manifest.get("approved_at")
    if formal and not approved:
        raise ValueError("candidate GLOBAL_POLICY_THRESHOLDS cannot produce formal policy")
    thresholds = manifest["thresholds"]
    z_center, z_spread, z_n = _frozen_z_parameters(rows)
    rng = random.Random(int(thresholds["frozen_random_seed"]))
    random_keys = {str(row.get("worker_id", "")): rng.random() for row in sorted(rows, key=lambda item: str(item.get("worker_id", "")))}
    quality_floor = float(thresholds["quality_floor"])
    output = []
    for row in rows:
        q_gt = _number(row, "Q_GT_EB")
        lcb = _number(row, "Q_GT_EB_LCB")
        s_g = None if q_gt is None else (q_gt - z_center) / z_spread
        reasons: list[str] = []
        if not _administratively_eligible(row):
            reasons.append("administrative")
        if q_gt is None or not _q_gt_estimable(row):
            reasons.append("q_gt_eb_missing")
        if math.isfinite(quality_floor) and lcb is None:
            reasons.append("quality_lcb_missing")
        if int(float(row.get("Q_GT_support") or 0)) < int(thresholds["minimum_GT_support"]):
            reasons.append("gt_support")
        if int(float(row.get("task_support") or 0)) < int(thresholds["minimum_task_support"]):
            reasons.append("task_support")
        if int(float(row.get("building_support") or 0)) < int(thresholds["minimum_building_support"]):
            reasons.append("building_support")
        if lcb is not None and lcb < quality_floor:
            reasons.append("quality_floor")
        structural_eb = _number(row, "F_struct_EB")
        maximum_structural = float(thresholds["maximum_structural_failure_eb"])
        if math.isfinite(maximum_structural) and structural_eb is None:
            reasons.append("structural_eb_missing")
        elif structural_eb is not None and structural_eb > maximum_structural:
            reasons.append("structural_safety")
        if not _explicit_truth(row, ("reference_evaluable",)):
            reasons.append("reference")
        if thresholds["require_process_eligible"] and not _gate_signal(row, "process_eligible", "process_support"):
            reasons.append("process")
        if thresholds["require_independence_eligible"] and not _gate_signal(row, "independence_eligible", "independence_support"):
            reasons.append("independence")
        if _truth(row.get("serious_recurrent_failure_flag")):
            reasons.append("serious_recurrent_failure")
        output.append({**row, "S_G": "" if s_g is None else s_g, "S_G_z_center": z_center, "S_G_z_scale": z_spread, "S_G_z_cohort_n": z_n, "S_G_z_parameters_frozen_before_gates": True, "global_policy_eligible": not reasons, "global_exclusion_reason": ";".join(reasons), "policy_status": "formal" if formal else "candidate", "formal_use_allowed": bool(formal and approved), "_random_key": random_keys[str(row.get("worker_id", ""))]})

    def rank(field: str, target: str) -> None:
        eligible = [row for row in output if row["global_policy_eligible"] and _number(row, field) is not None]
        eligible.sort(key=lambda row: (-float(row[field]), -float(row.get("Q_GT_EB") or float("-inf")), -float(row.get("R_LOO_LCB") or row.get("R_LOO_medoid") or -1), -float(row.get("availability") or 0), -float(row.get("capacity") or 0), row["_random_key"]))
        for index, row in enumerate(eligible, 1):
            row[target] = index

    rank("Q_GT_EB", "global_rank_EB")
    rank("Q_GT_task_adjusted_FE", "global_rank_FE")
    rank("S_G", "global_rank_S_G")
    for row in output:
        row.setdefault("global_rank_EB", "")
        row.setdefault("global_rank_FE", "")
        row.setdefault("global_rank_S_G", "")
        row["global_rank_LCB"] = row["global_rank_S_G"]
        row.pop("_random_key", None)
    return output


def materialize(input_csv: Path, output_csv: Path, manifest_path: Path, *, formal: bool = False) -> dict[str, Any]:
    with input_csv.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    output = build_global_policy(rows, manifest, formal=formal)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(output[0]))
        writer.writeheader()
        writer.writerows(output)
    return {"rows": len(output), "formal": formal, "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-csv", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=Path("docs/thesis_main/GLOBAL_POLICY_THRESHOLDS.json"))
    parser.add_argument("--formal", action="store_true")
    args = parser.parse_args()
    print(json.dumps(materialize(args.input_csv, args.output_csv, args.manifest, formal=args.formal), indent=2))


if __name__ == "__main__":
    main()
