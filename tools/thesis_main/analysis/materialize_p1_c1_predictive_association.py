"""Summarize worker-level P1→C1 predictive association without C2 confirmation."""

from __future__ import annotations

import argparse
import csv
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import kendalltau, spearmanr


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def build_source(
    p1_closeout_dir: Path, c1_worker_state_csv: Path, output_csv: Path, *, correction_dir: Path | None = None,
) -> dict[str, Any]:
    """Join frozen P1 worker evidence to the three independent C1 axes."""
    r0_path = next(iter(sorted(p1_closeout_dir.glob("*prescreen_r0_snapshot.csv"))), None)
    scope_path = next(iter(sorted(p1_closeout_dir.glob("*prescreen_worker_scope_summary.csv"))), None)
    if not r0_path or not scope_path:
        raise FileNotFoundError("P1 closeout lacks r0 or scope worker evidence")
    r0 = {row.get("worker_id", ""): row for row in _rows(r0_path) if str(row.get("admission_status", "")).startswith("pass")}
    scope = {row.get("annotator_id", ""): row for row in _rows(scope_path)}
    integrity_status = {}
    corrected_geometry = {}
    if correction_dir:
        status_path = next(iter(sorted(correction_dir.glob("*p1_worker_evidence_status_v1.csv"))), correction_dir / "p1_worker_evidence_status_v1.csv")
        geometry_path = next(iter(sorted(correction_dir.glob("*p1_worker_geometry_profile_v1.csv"))), correction_dir / "p1_worker_geometry_profile_v1.csv")
        if status_path.exists(): integrity_status = {row.get("worker_id", ""): row for row in _rows(status_path)}
        if geometry_path.exists(): corrected_geometry = {row.get("worker_id", ""): row for row in _rows(geometry_path)}
        r0 = {
            worker: {**row, "r_u_0": corrected_geometry.get(worker, {}).get("p1_geometry_component", "")}
            for worker, row in r0.items()
            if str(integrity_status.get(worker, {}).get("p1_predictive_capability_eligible", "")).lower() in {"true", "1"}
            and corrected_geometry.get(worker, {}).get("p1_geometry_component", "") != ""
        }
        # No corrected numeric Scope component is currently materialized.  Do
        # not let the legacy aggregate pass through the integrity amendment.
        scope = {}
    c1 = {row.get("worker_id", ""): row for row in _rows(c1_worker_state_csv)}
    checks = (
        ("p1_r_u_0_to_c1_q_gt", r0, "r_u_0", "Q_GT_task_adjusted", False),
        ("p1_r_u_0_to_c1_loo", r0, "r_u_0", "R_LOO_compatible", False),
        ("p1_scope_to_c1_q_gt", scope, "scope_accuracy_on_adjudicated_tasks", "Q_GT_task_adjusted", False),
        ("p1_r_u_0_to_c1_structural_success", r0, "r_u_0", "F_struct", True),
    )
    rows = []
    for worker in sorted(set(c1) & (set(r0) | set(scope))):
        for check, p1_rows, p1_field, c1_field, invert in checks:
            if worker not in p1_rows:
                continue
            value = c1.get(worker, {}).get(c1_field, "")
            try:
                value = 1 - float(value) if invert else float(value)
            except (TypeError, ValueError):
                value = ""
            rows.append({
                "worker_id": worker, "check_name": check,
                "p1_metric_value": p1_rows[worker].get(p1_field, ""),
                "c1_metric_value": value,
                "c1_axis_status": c1.get(worker, {}).get("worker_state_status", "missing_c1_worker"),
                "p1_integrity_source": "retrospective_correction" if correction_dir else "legacy_closeout_unamended",
            })
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]) if rows else ["worker_id", "check_name", "p1_metric_value", "c1_metric_value", "c1_axis_status"])
        writer.writeheader(); writer.writerows(rows)
    return {"n_join_rows": len(rows), "n_workers": len({row["worker_id"] for row in rows}), "n_evaluable_rows": sum(row["p1_metric_value"] not in (None, "") and row["c1_metric_value"] not in (None, "") for row in rows), "p1_integrity_amendment_applied": correction_dir is not None}


def materialize(source_csv: Path, output_dir: Path, *, seed: int = 20260724, draws: int = 2000) -> dict[str, Any]:
    source = _rows(source_csv)
    grouped: dict[str, list[tuple[str, float, float]]] = defaultdict(list)
    missing = 0
    for row in source:
        try:
            grouped[row.get("check_name", "")].append((row.get("worker_id", ""), float(row["p1_metric_value"]), float(row["c1_metric_value"])))
        except (KeyError, TypeError, ValueError):
            missing += 1
    rng = random.Random(seed); rows = []
    for check, values in sorted(grouped.items()):
        p1 = np.asarray([value[1] for value in values]); c1 = np.asarray([value[2] for value in values])
        spearman = float(spearmanr(p1, c1).statistic) if len(values) >= 3 else float("nan")
        kendall = float(kendalltau(p1, c1).statistic) if len(values) >= 3 else float("nan")
        boot = []
        if len(values) >= 3:
            for _ in range(draws):
                sample = [values[rng.randrange(len(values))] for _ in values]
                coefficient = spearmanr([value[1] for value in sample], [value[2] for value in sample]).statistic
                if np.isfinite(coefficient): boot.append(float(coefficient))
        rows.append({
            "component_family": check, "support": len(values), "spearman": spearman, "kendall": kendall,
            "bootstrap_ci_lower": float(np.quantile(boot, .025)) if boot else "", "bootstrap_ci_upper": float(np.quantile(boot, .975)) if boot else "",
            "directional_consistency": "positive" if np.isfinite(spearman) and spearman > 0 else "negative_or_uncertain",
            "range_restriction_p1": float(np.ptp(p1)) if len(p1) else "", "range_restriction_c1": float(np.ptp(c1)) if len(c1) else "",
            "discrepancy_workers": ";".join(worker for worker, left, right in values if (left >= np.median(p1)) != (right >= np.median(c1))),
            "evidence_status": "pending_c2b_confirmation", "full_component_eligible": False,
        })
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "p1_to_c1_predictive_association.csv"
    fields = list(rows[0]) if rows else ["component_family"]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    summary = {"n_components": len(rows), "n_source_rows": len(source), "missing_or_not_evaluable": missing, "bootstrap_seed": seed, "bootstrap_draws": draws, "component_status": "pending_c2b_confirmation"}
    (output_dir / "p1_to_c1_predictive_association.summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--source-csv", type=Path, required=True); parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(); print(json.dumps(materialize(args.source_csv, args.output_dir), indent=2)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
