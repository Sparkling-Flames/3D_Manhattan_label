"""C1 worker structural failure rates with auditable beta-binomial shrinkage."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import minimize
from scipy.special import betaln
from scipy.stats import beta as beta_distribution


def _truth(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def estimate_structural_reliability(
    rows: list[dict[str, Any]], *, policy_manifest: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    counts: dict[str, list[int]] = {}
    for row in rows:
        if not _truth(row.get("structural_opportunity_eligible")):
            continue
        worker = str(row.get("worker_id", "")); counts.setdefault(worker, [0, 0])
        counts[worker][1] += 1
        counts[worker][0] += int(row.get("failure_attribution") == "worker_caused_structural_failure" or _truth(row.get("worker_caused_structural_failure")))
    if not counts:
        raise ValueError("no structural-evaluable opportunities")
    y = np.asarray([counts[worker][0] for worker in sorted(counts)], dtype=float)
    n = np.asarray([counts[worker][1] for worker in sorted(counts)], dtype=float)
    def objective(log_ab: np.ndarray) -> float:
        alpha, beta = np.exp(log_ab)
        return -float(np.sum(betaln(y + alpha, n - y + beta) - betaln(alpha, beta)))
    fitted = minimize(objective, np.log([.5, .5]), method="L-BFGS-B")
    identifiable = bool(fitted.success and np.isfinite(fitted.fun) and len(counts) >= 2 and len(set(zip(y, n))) > 1)
    alpha, beta = (np.exp(fitted.x) if identifiable else np.asarray([.5, .5])).tolist()
    fallback = "" if identifiable else "jeffreys_beta_0.5_0.5"
    thresholds = policy_manifest["thresholds"]
    output = []
    for worker in sorted(counts):
        failures, opportunities = counts[worker]
        post_a, post_b = alpha + failures, beta + opportunities - failures
        mean = post_a / (post_a + post_b)
        lower, upper = beta_distribution.ppf([.025, .975], post_a, post_b)
        recurrent = failures >= int(thresholds["serious_recurrent_failure_minimum_count"]) and mean >= float(thresholds["serious_recurrent_failure_minimum_rate"])
        output.append({
            "worker_id": worker, "failure_count": failures, "opportunity_count": opportunities,
            "raw_failure_rate": failures / opportunities, "F_struct_raw": failures / opportunities,
            "F_struct_EB": mean, "F_struct_interval_lower": float(lower), "F_struct_interval_upper": float(upper),
            "F_struct_support": opportunities, "F_struct_prior_alpha": alpha, "F_struct_prior_beta": beta,
            "serious_recurrent_failure_flag": recurrent, "fallback_status": fallback,
        })
    return output, {"status": "estimated", "prior_status": "marginal_likelihood" if identifiable else "fallback", "fallback_status": fallback, "alpha": alpha, "beta": beta}


def materialize(input_csv: Path, output_csv: Path, policy_manifest_path: Path) -> dict[str, Any]:
    with input_csv.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    manifest = json.loads(policy_manifest_path.read_text(encoding="utf-8"))
    try:
        output, audit = estimate_structural_reliability(rows, policy_manifest=manifest)
    except ValueError as exc:
        output, audit = [], {"status": "not_evaluable", "reason": str(exc), "fallback_status": ""}
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as stream:
        fields = list(output[0]) if output else ["worker_id", "failure_count", "opportunity_count", "raw_failure_rate", "F_struct_raw", "F_struct_EB", "F_struct_interval_lower", "F_struct_interval_upper", "F_struct_support", "F_struct_prior_alpha", "F_struct_prior_beta", "serious_recurrent_failure_flag", "fallback_status"]
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader(); writer.writerows(output)
    return audit


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--input-csv", type=Path, required=True); parser.add_argument("--output-csv", type=Path, required=True); parser.add_argument("--policy-manifest", type=Path, default=Path("docs/thesis_main/GLOBAL_POLICY_THRESHOLDS.json")); args = parser.parse_args()
    print(json.dumps(materialize(args.input_csv, args.output_csv, args.policy_manifest), indent=2))


if __name__ == "__main__": main()
