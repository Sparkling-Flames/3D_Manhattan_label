"""Fit provisional C1 worker-by-risk parameters used only for C2-B design simulation."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _number(row: dict[str, str], *fields: str) -> float | None:
    for field in fields:
        try:
            value = float(row.get(field, ""))
            if np.isfinite(value): return value
        except (TypeError, ValueError):
            pass
    return None


def materialize(quality_csv: Path, risk_csv: Path, structural_csv: Path, completion_csv: Path, output_dir: Path) -> dict:
    risk = {row.get("base_task_id", ""): row for row in _read(risk_csv)}
    by_worker: dict[str, list[tuple[float, float, str, str]]] = defaultdict(list)
    qgt_support: dict[str, int] = defaultdict(int)
    for row in _read(quality_csv):
        task = row.get("base_task_id", ""); risk_row = risk.get(task, {})
        # C2-B is designed from C1-only risk_design_A.  Assist and route risk
        # belong to later T1/V1 decisions and cannot be a prerequisite here.
        x = _number(risk_row, "risk_design_A", "d_cal_A")
        y = _number(row, "Q_GT_raw", "iou_2d", "iou")
        if y is not None and str(row.get("global_analysis_eligible", "")).lower() in {"true", "1"}:
            worker = row.get("worker_id", "")
            qgt_support[worker] += 1
            if x is not None:
                by_worker[worker].append((x, y, task, risk_row.get("building_id", "")))
    failures, opportunities = defaultdict(int), defaultdict(int)
    for row in _read(structural_csv):
        if str(row.get("structural_opportunity_eligible", "")).lower() in {"true", "1"}:
            worker = row.get("worker_id", ""); opportunities[worker] += 1
            failures[worker] += row.get("failure_attribution") == "worker_caused_structural_failure"
    completion = {row.get("worker_id", ""): row for row in _read(completion_csv)}
    all_observations = [item for values in by_worker.values() for item in values]
    group_slope = group_scale = ""
    if len(all_observations) >= 3 and len({item[0] for item in all_observations}) >= 2:
        x_all = np.asarray([item[0] for item in all_observations]); y_all = np.asarray([item[1] for item in all_observations])
        design_all = np.column_stack([np.ones(len(x_all)), x_all]); beta_all = np.linalg.lstsq(design_all, y_all, rcond=None)[0]
        residual_all = y_all - design_all @ beta_all
        group_slope = float(beta_all[1])
        group_scale = float(np.sqrt(max(0.0, residual_all @ residual_all / max(1, len(x_all) - 2))))
    rows = []
    for worker in sorted(completion):
        observations = by_worker[worker]
        slope = se = ""
        if len(observations) >= 3 and len({item[0] for item in observations}) >= 2:
            x = np.asarray([item[0] for item in observations]); y = np.asarray([item[1] for item in observations])
            design = np.column_stack([np.ones(len(x)), x]); beta = np.linalg.lstsq(design, y, rcond=None)[0]
            residual = y - design @ beta; variance = float(residual @ residual / max(1, len(x) - 2))
            slope = float(beta[1]); se = float(np.sqrt(variance * np.linalg.inv(design.T @ design)[1, 1]))
        assigned = int(float(completion[worker].get("assigned_total_count") or 0)); observed = int(float(completion[worker].get("observed_total_count") or 0))
        if slope != "":
            slope_status = "estimated_from_C1"
        elif observations:
            slope_status = "weak_C1_support"
        elif qgt_support[worker]:
            slope_status = "not_evaluable_but_C2B_eligible"
        else:
            slope_status = "group_prior_only"
        rows.append({
            "worker_id": worker, "risk_slope": slope, "risk_slope_se": se, "risk_support": len(observations), "Q_GT_support_for_slope": qgt_support[worker], "building_support": len({item[3] for item in observations if item[3]}),
            "group_prior_slope": group_slope, "group_prior_scale": group_scale,
            "risk_slope_for_simulation": slope if slope != "" else group_slope,
            "risk_slope_scale_for_simulation": se if se != "" else group_scale,
            "c1_risk_slope_status": slope_status,
            "missing_rate": (assigned - observed) / assigned if assigned else "", "F_struct": failures[worker] / opportunities[worker] if opportunities[worker] else "", "F_struct_numerator": failures[worker], "F_struct_denominator": opportunities[worker], "parameter_status": "estimated" if slope != "" else "group_prior_or_insufficient",
        })
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / "c1_c2_design_parameters.csv"
    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]) if rows else ["worker_id"]); writer.writeheader(); writer.writerows(rows)
    summary = {"n_workers": len(rows), "n_estimated": sum(row["parameter_status"] == "estimated" for row in rows), "group_prior_available": group_slope != "", "formal_design_input_ready": bool(rows) and group_slope != ""}
    (output_dir / "c1_c2_design_parameters.summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    for name in ("quality-csv", "risk-csv", "structural-csv", "completion-csv", "output-dir"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args(); print(json.dumps(materialize(args.quality_csv, args.risk_csv, args.structural_csv, args.completion_csv, args.output_dir), indent=2)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
