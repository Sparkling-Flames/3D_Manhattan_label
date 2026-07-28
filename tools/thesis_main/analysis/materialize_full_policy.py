"""Full policy scoring constrained to risk plus at most one family adjustment."""

from __future__ import annotations

from typing import Any
import argparse
import csv
import json
from pathlib import Path


def build_full_policy(global_rows: list[dict[str, Any]], task: dict[str, Any], components: list[dict[str, Any]]) -> list[dict[str, Any]]:
    supported = [row for row in components if row.get("component_status") == "cross_stage_supported" and str(row.get("component_family", "")) == str(task.get("activated_failure_family", "")) and str(row.get("worker_id", ""))]
    families = {row.get("component_family") for row in supported}
    if len(families) > 1: raise ValueError("a task may activate at most one failure family")
    by_worker = {str(row["worker_id"]): row for row in supported}
    in_support = bool(task.get("calibration_support", False))
    output = []
    for row in global_rows:
        worker = str(row.get("worker_id", "")); base = float(row.get("S_G") or 0)
        risk_supported = in_support and str(row.get("risk_activation_status", "")) == "supported"
        risk_adjustment = float(row.get("risk_adjustment") or 0) if risk_supported else 0.0
        component = by_worker.get(worker, {}) if in_support else {}
        family_adjustment = float(component.get("adjustment") or 0) if component else 0.0
        score = base + risk_adjustment + family_adjustment
        output.append({**row, "S_F": score, "risk_component_id": row.get("risk_component_id", "risk_route"), "risk_estimate": row.get("risk_estimate", ""), "risk_support": row.get("risk_support", ""), "risk_shrinkage": row.get("risk_shrinkage", ""), "risk_activation_status": "supported" if risk_supported else "inactive", "risk_adjustment_applied": risk_adjustment, "family_component_id": component.get("component_family", ""), "family_estimate": component.get("combined_effect", ""), "family_support": component.get("worker_support", ""), "family_shrinkage": component.get("shrinkage", ""), "family_activation_status": "supported" if component else "inactive", "family_adjustment_applied": family_adjustment, "full_exclusion_reason": "outside_calibration_support" if not in_support else "" if risk_supported or component else "no_supported_adjustment"})
    ranked = sorted(output, key=lambda row: (-float(row["S_F"]), int(row.get("global_rank_EB") or 10**9)))
    for index, row in enumerate(ranked, 1): row["full_rank"] = index
    return output


def main() -> None:
    parser=argparse.ArgumentParser(); parser.add_argument("--global-csv",type=Path,required=True); parser.add_argument("--task-json",type=Path,required=True); parser.add_argument("--components-csv",type=Path,required=True); parser.add_argument("--output-csv",type=Path,required=True); args=parser.parse_args()
    def read(path):
        with path.open(encoding="utf-8-sig",newline="") as stream: return list(csv.DictReader(stream))
    rows=build_full_policy(read(args.global_csv),json.loads(args.task_json.read_text(encoding="utf-8")),read(args.components_csv)); args.output_csv.parent.mkdir(parents=True,exist_ok=True)
    with args.output_csv.open("w",encoding="utf-8",newline="") as stream: writer=csv.DictWriter(stream,fieldnames=list(rows[0]) if rows else ["worker_id"]); writer.writeheader(); writer.writerows(rows)
    print(json.dumps({"rows":len(rows)},indent=2))


if __name__ == "__main__": main()
