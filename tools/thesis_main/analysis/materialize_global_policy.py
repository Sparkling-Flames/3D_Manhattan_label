"""Materialize Strong Global audit ranks; formal output is manifest-gated."""

from __future__ import annotations

import csv
import argparse
import hashlib
import json
import random
from pathlib import Path
from typing import Any

import numpy as np


def _truth(value: Any) -> bool: return str(value).strip().lower() in {"1", "true", "yes"}
def _number(row: dict[str, Any], key: str) -> float | None:
    try: return float(row[key])
    except (KeyError, TypeError, ValueError): return None


def build_global_policy(rows: list[dict[str, Any]], manifest: dict[str, Any], *, formal: bool = False) -> list[dict[str, Any]]:
    approved = manifest.get("status") == "approved" and bool(manifest.get("interpretation_allowed")) and manifest.get("approved_by") and manifest.get("approved_at")
    if formal and not approved: raise ValueError("candidate GLOBAL_POLICY_THRESHOLDS cannot produce formal policy")
    thresholds = manifest["thresholds"]
    eb = [_number(row, "Q_GT_EB") for row in rows]
    finite = [value for value in eb if value is not None]
    if len(finite) < 2: raise ValueError("formal Global requires estimable Q_GT_EB for at least two workers")
    mean, sd = float(np.mean(finite)), float(np.std(finite, ddof=1))
    if sd <= 0: raise ValueError("Q_GT_EB cannot be standardized")
    rng = random.Random(int(thresholds["frozen_random_seed"])); random_keys = {str(row.get("worker_id", "")): rng.random() for row in sorted(rows, key=lambda item: str(item.get("worker_id", "")))}
    output = []
    for row in rows:
        value = _number(row, "Q_GT_EB"); reasons = []
        if value is None: reasons.append("q_gt_eb_missing")
        if int(float(row.get("Q_GT_support") or 0)) < int(thresholds["minimum_GT_support"]): reasons.append("gt_support")
        if int(float(row.get("task_support") or 0)) < int(thresholds["minimum_task_support"]): reasons.append("task_support")
        if int(float(row.get("building_support") or 0)) < int(thresholds["minimum_building_support"]): reasons.append("building_support")
        if value is not None and value < float(thresholds["quality_floor"]): reasons.append("quality_floor")
        if _number(row, "F_struct_EB") is not None and float(row["F_struct_EB"]) > float(thresholds["maximum_structural_failure_eb"]): reasons.append("structural_safety")
        if thresholds["require_process_eligible"] and not _truth(row.get("process_eligible", row.get("process_support"))): reasons.append("process")
        if thresholds["require_independence_eligible"] and not _truth(row.get("independence_eligible", row.get("independence_support"))): reasons.append("independence")
        output.append({**row, "S_G": "" if value is None else (value - mean) / sd, "global_policy_eligible": not reasons, "global_exclusion_reason": ";".join(reasons), "policy_status": "formal" if formal else "candidate", "formal_use_allowed": bool(formal and approved), "_random_key": random_keys[str(row.get("worker_id", ""))]})
    def rank(field: str, target: str, ties: bool = False) -> None:
        eligible = [row for row in output if row["global_policy_eligible"] and _number(row, field) is not None]
        eligible.sort(key=lambda row: (-float(row[field]), -float(row.get("R_LOO_medoid") or -1), -float(row.get("R_peer_median") or -1), -float(row.get("availability") or 0), -float(row.get("capacity") or 0), row["_random_key"]))
        for index, row in enumerate(eligible, 1): row[target] = index
    rank("Q_GT_EB", "global_rank_EB"); rank("Q_GT_task_adjusted_FE", "global_rank_FE"); rank("Q_GT_EB_LCB", "global_rank_LCB")
    for row in output:
        row.setdefault("global_rank_EB", ""); row.setdefault("global_rank_FE", ""); row.setdefault("global_rank_LCB", ""); row.pop("_random_key", None)
    return output


def materialize(input_csv: Path, output_csv: Path, manifest_path: Path, *, formal: bool = False) -> dict[str, Any]:
    with input_csv.open(encoding="utf-8-sig", newline="") as stream: rows = list(csv.DictReader(stream))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")); output = build_global_policy(rows, manifest, formal=formal)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as stream: writer=csv.DictWriter(stream, fieldnames=list(output[0])); writer.writeheader(); writer.writerows(output)
    return {"rows": len(output), "formal": formal, "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest()}


def main() -> None:
    parser=argparse.ArgumentParser(); parser.add_argument("--input-csv",type=Path,required=True); parser.add_argument("--output-csv",type=Path,required=True); parser.add_argument("--manifest",type=Path,default=Path("docs/thesis_main/GLOBAL_POLICY_THRESHOLDS.json")); parser.add_argument("--formal",action="store_true"); args=parser.parse_args()
    print(json.dumps(materialize(args.input_csv,args.output_csv,args.manifest,formal=args.formal),indent=2))


if __name__ == "__main__": main()
