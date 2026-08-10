"""Re-fit the post-Block1 C2-A-RP risk model from SHA-bound evidence."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, Callable

from tools.thesis_main.analysis.c1_live_collection_monitor import read_csv, write_csv, write_json
from tools.thesis_main.analysis.materialize_c1_c2_design_parameters import _fit_crossed_model
from tools.thesis_main.analysis.vfinal_artifact_utils import sha256_file


ROOT = Path(__file__).resolve().parents[3]
BAD_GT = "zsNo4HB9uLZ_4c0aab63a4434cf4878e6f5b3ce9a70b"
DEFAULT_C2B_EVIDENCE = ROOT / "analysis_results/c2b_closeout_20260806_final/c2b_canonical_risk_slope_evidence.csv"
DEFAULT_BLOCK1_EVIDENCE = ROOT / "analysis_results/c2a_rp_block1_reestimate_20260810_v1/c2a_rp_block1_risk_slope_evidence.csv"
DEFAULT_PROFILE = ROOT / "analysis_results/c2b_closeout_20260806_final/post_c2b_worker_profile.csv"
DEFAULT_THRESHOLD = ROOT / "analysis_results/c2b_validation_design_20260802_v17/output/c2b_derived_threshold_manifest.json"
DEFAULT_C2B_CLOSEOUT = ROOT / "analysis_results/c2a_rp_local_launch_20260807_v4/c2b_closeout_v2.json"
DEFAULT_OUTPUT = ROOT / "analysis_results/c2a_rp_block1_reestimate_20260810_v2"


def _truth(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def materialize(
    output_dir: Path = DEFAULT_OUTPUT,
    *,
    c2b_evidence: Path = DEFAULT_C2B_EVIDENCE,
    block1_evidence: Path = DEFAULT_BLOCK1_EVIDENCE,
    base_profile: Path = DEFAULT_PROFILE,
    threshold_path: Path = DEFAULT_THRESHOLD,
    c2b_closeout: Path = DEFAULT_C2B_CLOSEOUT,
    excluded_task_ids: set[str] | None = None,
    fit_model: Callable[[list[dict[str, Any]]], dict[str, Any]] = _fit_crossed_model,
) -> dict[str, Any]:
    inputs = (c2b_evidence, block1_evidence, base_profile, threshold_path, c2b_closeout)
    if any(not path.exists() for path in inputs):
        raise ValueError("post-Block1 reestimate input is missing")
    if output_dir.exists():
        raise ValueError(f"output directory already exists:{output_dir}")
    excluded = excluded_task_ids or {BAD_GT}
    threshold = json.loads(threshold_path.read_text(encoding="utf-8"))
    formula_id = threshold.get("derivation", {}).get("formula_ids", {}).get("risk_slope_ci_half_width")
    if formula_id != "normal_95_max_unified_slope_sd":
        raise ValueError("unexpected risk-slope interval formula")
    target = float(threshold["thresholds"]["risk_slope_ci_half_width"])

    rows = [dict(row) for row in [*read_csv(c2b_evidence), *read_csv(block1_evidence)]]
    for row in rows:
        task_id = row.get("base_task_id") or row.get("task_id") or row.get("planned_task_id")
        if task_id in excluded:
            row["risk_slope_estimand_eligible"] = "False"
            row["eligibility_status"] = "not_evaluable"
            row["ineligibility_reason"] = "researcher_confirmed_bad_gt"
    eligible = [row for row in rows if _truth(row.get("risk_slope_estimand_eligible"))]
    records = [{
        "worker_id": str(row["worker_id"]),
        "base_task_id": str(row["base_task_id"]),
        "building_id": str(row.get("building_id", "")),
        "risk": float(row["risk"]),
        "quality": float(row["quality"]),
    } for row in eligible]
    fit = fit_model(records)
    if fit.get("status") != "estimated":
        raise ValueError(f"post-Block1 risk model is not estimated:{fit.get('status')}")
    group_se = float(fit["group_slope_se"])
    between_sd = float(fit["between_worker_slope_sd"])
    support = Counter(row["worker_id"] for row in eligible)
    strata = Counter((row["worker_id"], row.get("task_stratum", "")) for row in eligible)

    profiles = read_csv(base_profile)
    workers: dict[str, Any] = {}
    for row in profiles:
        worker = str(row.get("worker_id", ""))
        if worker not in fit["worker_slopes"]:
            continue
        worker_se = float(fit["worker_slope_ses"][worker])
        half_width = 1.96 * max(worker_se, group_se, between_sd)
        row.update({
            "risk_slope": fit["worker_slopes"][worker],
            "risk_slope_for_simulation": fit["worker_slopes"][worker],
            "risk_slope_se": worker_se,
            "risk_slope_ci_half_width": half_width,
            "risk_slope_support": support[worker],
            "observed_risk_slope_support": support[worker],
            "ordinary_support_observed": strata[(worker, "ordinary")],
            "stress_support_observed": strata[(worker, "stress")],
            "risk_slope_status": "estimated",
            "support": support[worker],
            "ci_half_width": half_width,
            "risk_model_scope": "C2B_PLUS_C2A_RP_BLOCK1_CORRECTED_REESTIMATE",
            "profile_purpose": "C2A_RP_BLOCK2_ROUTING_INPUT",
        })
        workers[worker] = {
            "estimate": float(fit["worker_slopes"][worker]),
            "worker_se": worker_se,
            "unified_ci_half_width": half_width,
            "support": support[worker],
            "target_met": half_width <= target,
        }

    output_dir.mkdir(parents=True)
    evidence_out = output_dir / "c2b_plus_c2a_rp_block1_risk_slope_evidence.csv"
    profile_out = output_dir / "post_c2a_rp_block1_worker_profile.csv"
    write_csv(evidence_out, rows)
    write_csv(profile_out, profiles)
    summary = {
        "schema_version": "c2a_rp_block1_reestimate_v2",
        "artifact_role": "C2A_RP_BLOCK1_REESTIMATE_FROZEN",
        "formal_ready": True,
        "c2b_collection_status": "closed_historical_collection",
        "c2b_input_acceptance_scope": "C2A_RP_reestimate_only",
        "historical_c2b_closeout_candidate_only": True,
        "corrected_c2b_evidence_frozen": True,
        "interval_formula_id": formula_id,
        "interval_formula": "1.96 * max(worker_slope_se, group_slope_se, between_worker_slope_sd)",
        "target_ci_half_width": target,
        "reference_excluded_task_ids": sorted(excluded),
        "input_sha256": {path.name: sha256_file(path) for path in inputs},
        "combined_evidence_rows": len(rows),
        "eligible_model_rows": len(eligible),
        "excluded_rows_by_stage": dict(Counter(row.get("evidence_stage", "") for row in rows if (row.get("base_task_id") or row.get("task_id")) in excluded)),
        "model_diagnostics": {key: value for key, value in fit.items() if key not in {"worker_slopes", "worker_slope_ses"}},
        "workers": workers,
        "output_sha256": {
            evidence_out.name: sha256_file(evidence_out),
            profile_out.name: sha256_file(profile_out),
        },
    }
    write_json(output_dir / "c2a_rp_block1_reestimate_summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(materialize(args.output_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
