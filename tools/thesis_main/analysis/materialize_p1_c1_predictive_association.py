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


def materialize(source_csv: Path, output_dir: Path, *, seed: int = 20260724, draws: int = 2000) -> dict[str, Any]:
    with source_csv.open(encoding="utf-8-sig", newline="") as stream:
        source = list(csv.DictReader(stream))
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
