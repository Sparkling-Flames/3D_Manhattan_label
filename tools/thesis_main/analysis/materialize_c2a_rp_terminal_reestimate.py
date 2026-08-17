"""Re-fit the terminal C2-A-RP risk model after Block 2."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from tools.thesis_main.analysis.build_c2_assignment_manifest_from_c1_gaps import _resolve_fitted_worker_slope_distribution
from tools.thesis_main.analysis.c1_live_collection_monitor import read_csv, write_csv, write_json
from tools.thesis_main.analysis.materialize_c1_c2_design_parameters import _fit_crossed_model
from tools.thesis_main.analysis.paper_a_contracts import METHOD_CONTRACT, load_method_contract, sha256_file


def _truth(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def materialize(
    *, cumulative_through_block1: Path, block2_evidence: Path, base_profile: Path,
    threshold_manifest: Path, output_dir: Path,
) -> dict[str, Any]:
    inputs = [cumulative_through_block1, block2_evidence, base_profile, threshold_manifest]
    if any(not path.is_file() for path in inputs):
        raise ValueError("terminal C2-A-RP reestimate input is missing")
    if output_dir.exists():
        raise ValueError(f"output directory already exists:{output_dir}")
    threshold = json.loads(threshold_manifest.read_text(encoding="utf-8"))
    formula_id = threshold.get("derivation", {}).get("formula_ids", {}).get("risk_slope_ci_half_width")
    if formula_id != "normal_95_max_unified_slope_sd":
        raise ValueError("unexpected risk-slope interval formula")
    target = float(threshold["thresholds"]["risk_slope_ci_half_width"])
    rows = [*read_csv(cumulative_through_block1), *read_csv(block2_evidence)]
    identities = [str(row.get("canonical_annotation_id", "")) for row in rows]
    if any(not value for value in identities) or len(identities) != len(set(identities)):
        raise ValueError("terminal risk evidence canonical identities are missing or duplicated")
    eligible: list[dict[str, Any]] = []
    for row in rows:
        canonical = _truth(row.get("canonical_valid"))
        if str(row.get("risk_slope_estimand_eligible", "")).strip():
            accepted = _truth(row.get("risk_slope_estimand_eligible"))
        else:
            accepted = (_truth(row.get("formal_assignment_eligible"))
                        and _truth(row.get("routing_feature_analysis_eligible")))
        if accepted and canonical:
            # Historical C2-B evidence predates the split eligibility columns.
            # Its frozen composite gate is mapped deterministically for the
            # current closeout consumer; outcomes and task identities are not changed.
            row["formal_assignment_eligible"] = "true"
            row["routing_feature_analysis_eligible"] = "true"
            eligible.append(row)
    records = [{
        "worker_id": str(row["worker_id"]),
        "base_task_id": str(row["base_task_id"]),
        "building_id": str(row.get("building_id", "")),
        "risk": float(row.get("risk_design_score_A") or row["risk"]),
        "quality": float(row.get("Q_GT_raw") or row["quality"]),
    } for row in eligible]
    fit = _fit_crossed_model(records)
    if fit.get("status") != "estimated":
        raise ValueError(f"terminal risk model is not estimated:{fit.get('status')}")
    support = Counter(row["worker_id"] for row in eligible)
    strata = Counter((row["worker_id"], row.get("task_stratum", "")) for row in eligible)
    profiles = read_csv(base_profile)
    workers: dict[str, Any] = {}
    for row in profiles:
        worker = str(row.get("worker_id", ""))
        if worker not in fit["worker_slopes"]:
            row.update({
                "risk_slope_status": "not_evaluable",
                "risk_precision_terminal_state": "not_evaluable",
                "risk_model_scope": "C2B_PLUS_C2A_RP_TERMINAL_REESTIMATE",
                "profile_purpose": "FINAL_CALIBRATION_PROFILE_INPUT",
            })
            workers[worker] = {
                "estimate": None, "worker_se": None, "unified_slope_sd": None,
                "unified_slope_source": "not_identified", "unified_ci_half_width": None,
                "support": support[worker], "terminal_state": "not_evaluable",
            }
            continue
        distribution = _resolve_fitted_worker_slope_distribution(fit, worker, support[worker])
        if not distribution.get("valid"):
            raise ValueError(f"worker slope distribution is not identified:{worker}")
        worker_se = float(fit["worker_slope_ses"][worker])
        half_width = 1.96 * float(distribution["total_sd"])
        status = "target_met" if half_width <= target else "fallback_strong_global"
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
            "risk_precision_terminal_state": status,
            "support": support[worker],
            "ci_half_width": half_width,
            "risk_model_scope": "C2B_PLUS_C2A_RP_TERMINAL_REESTIMATE",
            "profile_purpose": "FINAL_CALIBRATION_PROFILE_INPUT",
        })
        workers[worker] = {
            "estimate": float(fit["worker_slopes"][worker]),
            "worker_se": worker_se,
            "unified_slope_sd": distribution["total_sd"],
            "unified_slope_source": distribution["source"],
            "unified_ci_half_width": half_width,
            "support": support[worker],
            "terminal_state": status,
        }
    output_dir.mkdir(parents=True)
    evidence_out = output_dir / "c2b_plus_c2a_rp_terminal_risk_slope_evidence.csv"
    submissions_out = output_dir / "c2a_rp_terminal_canonical_submissions.csv"
    profile_out = output_dir / "post_c2a_rp_terminal_worker_profile.csv"
    write_csv(evidence_out, rows)
    write_csv(submissions_out, [row for row in rows if str(row.get("evidence_stage", "")).startswith("C2A_RP")])
    write_csv(profile_out, profiles)
    summary = {
        "schema_version": "c2a_rp_terminal_reestimate_v1",
        "artifact_role": "C2A_RP_TERMINAL_REESTIMATE_FROZEN",
        "formal_ready": True,
        "method_contract_version": load_method_contract()["contract_version"],
        "method_contract_sha256": sha256_file(METHOD_CONTRACT),
        "interval_formula_id": formula_id,
        "target_ci_half_width": target,
        "combined_evidence_rows": len(rows),
        "eligible_model_rows": len(eligible),
        "model_diagnostics": {key: value for key, value in fit.items() if key not in {"worker_slopes", "worker_slope_ses"}},
        "workers": workers,
        "input_sha256": {str(path): sha256_file(path) for path in inputs},
        "output_sha256": {
            evidence_out.name: sha256_file(evidence_out),
            submissions_out.name: sha256_file(submissions_out),
            profile_out.name: sha256_file(profile_out),
        },
    }
    write_json(output_dir / "c2a_rp_terminal_reestimate_summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cumulative-through-block1", type=Path, required=True)
    parser.add_argument("--block2-evidence", type=Path, required=True)
    parser.add_argument("--base-profile", type=Path, required=True)
    parser.add_argument("--threshold-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(materialize(
        cumulative_through_block1=args.cumulative_through_block1,
        block2_evidence=args.block2_evidence, base_profile=args.base_profile,
        threshold_manifest=args.threshold_manifest, output_dir=args.output_dir,
    ), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
