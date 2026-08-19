"""Materialize the latest Calibration-only Q_GT and pooled worker profile."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

from tools.thesis_main.analysis.c1_task_adjusted_quality import estimate_task_adjusted_qgt
from tools.thesis_main.analysis.paper_a_contracts import METHOD_CONTRACT, load_method_contract, sha256_file


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _truth(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def _write(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty profile table:{path.name}")
    fields: list[str] = []
    for row in rows:
        fields.extend(key for key in row if key not in fields)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def materialize(
    *, c1_quality: Path, c2_risk_evidence: Path, c1_profile: Path,
    c2a_terminal_profile: Path, c2a_closeout: Path, output_dir: Path,
) -> dict[str, Any]:
    inputs = [c1_quality, c2_risk_evidence, c1_profile, c2a_terminal_profile, c2a_closeout]
    if any(not path.is_file() for path in inputs):
        raise ValueError("final Calibration profile input is missing")
    if output_dir.exists():
        raise ValueError(f"output directory already exists:{output_dir}")
    closeout = json.loads(c2a_closeout.read_text(encoding="utf-8"))
    if (closeout.get("artifact_role") != "C2A_RP_CLOSEOUT_FROZEN"
            or closeout.get("formal_ready") is not True
            or closeout.get("stage_closed") is not True
            or closeout.get("next_block_required") is not False):
        raise ValueError("C2-A-RP is not formally terminal")

    quality_rows: list[dict[str, Any]] = [dict(row, stage="C1") for row in _rows(c1_quality)]
    for row in _rows(c2_risk_evidence):
        eligible = (_truth(row.get("formal_assignment_eligible"))
                    and _truth(row.get("routing_feature_analysis_eligible"))
                    and _truth(row.get("canonical_valid")))
        quality_rows.append({
            "worker_id": row.get("worker_id", ""),
            "base_task_id": row.get("base_task_id", ""),
            "building_id": row.get("building_id", ""),
            "condition": "manual",
            "stage": row.get("evidence_stage", "C2"),
            "Q_GT_raw": row.get("Q_GT_raw") or row.get("quality"),
            "quality_evaluable": str(eligible),
            "gt_primary_analysis_eligible": str(eligible),
        })
    estimator = {
        "model_mode": "c1_c2_final",
        "profile_purpose": "post_c2_routing",
        "formal_eligibility": True,
        "bootstrap_replicates": 1000,
        "bootstrap_seed": 20260817,
        "confidence_level": 0.95,
        "minimum_successful_bootstrap_fraction": 0.75,
    }
    qgt_rows, task_effects, audit = estimate_task_adjusted_qgt(quality_rows, estimator_contract=estimator)
    qgt = {str(row["worker_id"]): row for row in qgt_rows}
    base = _rows(c1_profile)
    base_workers = {str(row.get("worker_id", "")) for row in base}
    missing_qgt = base_workers - set(qgt)
    allowed_missing = {
        str(row.get("worker_id", "")) for row in base
        if not _truth(row.get("administratively_eligible"))
        and str(row.get("completion_status", "")) == "administrative_exclusion"
    }
    if set(qgt) - base_workers or missing_qgt - allowed_missing:
        raise ValueError(f"final Q_GT roster mismatch:missing={sorted(missing_qgt)},extra={sorted(set(qgt)-base_workers)}")
    risk = {str(row.get("worker_id", "")): row for row in _rows(c2a_terminal_profile)}
    terminal = {str(row.get("worker_id", "")): row for row in closeout.get("worker_outcomes", [])}
    values = [float(row["Q_GT_EB"]) for row in qgt_rows]
    mean = sum(values) / len(values)
    sd = math.sqrt(sum((value - mean) ** 2 for value in values) / (len(values) - 1))
    if not math.isfinite(sd) or sd <= 0:
        raise ValueError("final Q_GT_EB standardization is not identified")
    profile_rows: list[dict[str, Any]] = []
    for row in base:
        worker = str(row.get("worker_id", ""))
        if worker in qgt:
            row.update(qgt[worker])
        row.update({
            "schema_version": "worker_profile_v2",
            "profile_version": "paper_a_worker_profile_v2",
            "cohort_id": "paper_a_calibration_pooled",
            "profile_scope": "C1_C2B_C2A_RP_TERMINAL_CALIBRATION_ONLY",
            "S_G": (float(qgt[worker]["Q_GT_EB"]) - mean) / sd if worker in qgt else "",
            "strong_global_score_definition": "z(Q_GT_EB)",
            "c2a_rp_terminal_state": terminal.get(worker, {}).get("terminal_state", "not_evaluable"),
            "c2a_rp_fallback_action": terminal.get(worker, {}).get("fallback_action", ""),
            "c2a_rp_completion_status": (
                "withdrawn" if "withdrawal" in str(terminal.get(worker, {}).get("reason", ""))
                else "completed" if worker in terminal else "not_applicable"
            ),
        })
        if worker not in qgt:
            row["Q_GT_profile_status"] = "not_evaluable_administrative_exclusion"
        if worker in risk:
            for field in (
                "risk_slope", "risk_slope_se", "risk_slope_ci_half_width", "risk_slope_support",
                "ordinary_support_observed", "stress_support_observed", "risk_slope_status",
                "risk_precision_terminal_state", "risk_model_scope",
            ):
                row[field] = risk[worker].get(field, "")
        profile_rows.append(row)

    output_dir.mkdir(parents=True)
    evidence_path = output_dir / "final_c1_c2_qgt_worker_evidence.csv"
    task_path = output_dir / "final_c1_c2_qgt_task_effects.csv"
    profile_path = output_dir / "pooled_worker_profile_v2.csv"
    _write(evidence_path, qgt_rows)
    _write(task_path, task_effects)
    _write(profile_path, profile_rows)
    common = {
        "contract_role": "generated_subordinate",
        "formal_ready": True,
        "profile_version": "paper_a_worker_profile_v2",
        "cohort_id": "paper_a_calibration_pooled",
        "method_contract_version": load_method_contract()["contract_version"],
        "method_contract_sha256": sha256_file(METHOD_CONTRACT),
        "calibration_only": True,
        "T1_or_V1_outcomes_used": False,
        "dependencies": [{"path": str(path.resolve()), "sha256": sha256_file(path)} for path in inputs],
    }
    qgt_artifact = {
        **common,
        "schema_version": "final_c1_c2_qgt_model_v1",
        "artifact_role": "FINAL_C1_C2_Q_GT_MODEL_FROZEN",
        "worker_evidence_path": str(evidence_path.resolve()),
        "worker_evidence_sha256": sha256_file(evidence_path),
        "task_effects_path": str(task_path.resolve()),
        "task_effects_sha256": sha256_file(task_path),
        "model_audit": audit,
    }
    qgt_json = output_dir / "final_c1_c2_qgt_model_v1.json"
    qgt_json.write_text(json.dumps(qgt_artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    profile_artifact = {
        **common,
        "schema_version": "worker_profile_v2",
        "artifact_role": "POOLED_WORKER_PROFILE_FROZEN",
        "profile_csv_path": str(profile_path.resolve()),
        "profile_csv_sha256": sha256_file(profile_path),
        "worker_count": len(profile_rows),
        "Q_GT_EB_standardization_mean": mean,
        "Q_GT_EB_standardization_sd": sd,
        "Q_GT_model_sha256": sha256_file(qgt_json),
    }
    profile_json = output_dir / "pooled_worker_profile_frozen.json"
    profile_json.write_text(json.dumps(profile_artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {
        "schema_version": "final_calibration_profile_manifest_v1",
        "artifact_role": "FINAL_CALIBRATION_PROFILE_MATERIALIZATION",
        "formal_ready": True,
        "worker_count": len(profile_rows),
        "bootstrap_replicates": estimator["bootstrap_replicates"],
        "bootstrap_seed": estimator["bootstrap_seed"],
        "outputs": {path.name: sha256_file(path) for path in (evidence_path, task_path, profile_path, qgt_json, profile_json)},
    }
    (output_dir / "analysis_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("c1-quality", "c2-risk-evidence", "c1-profile", "c2a-terminal-profile", "c2a-closeout", "output-dir"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(materialize(
        c1_quality=args.c1_quality, c2_risk_evidence=args.c2_risk_evidence,
        c1_profile=args.c1_profile, c2a_terminal_profile=args.c2a_terminal_profile,
        c2a_closeout=args.c2a_closeout, output_dir=args.output_dir,
    ), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
