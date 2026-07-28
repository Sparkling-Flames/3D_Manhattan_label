"""Mechanically derive C2-B selection thresholds from frozen pre-enumeration inputs."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

from tools.thesis_main.analysis.build_c2_assignment_manifest_from_c1_gaps import _resolve_slope_distribution
from tools.thesis_main.analysis.vfinal_artifact_utils import sha256_file


REQUIRED_THRESHOLDS = (
    "q_gt_ci_half_width", "risk_slope_ci_half_width", "minimum_worker_rank_spearman",
    "minimum_top_k_overlap", "maximum_mean_rank_displacement", "minimum_worker_support",
    "minimum_task_support", "graph_connectivity_probability", "minimum_building_coverage",
    "building_coverage_probability", "ordinary_coverage_probability", "stress_coverage_probability",
    "minimum_eligible_task_count", "minimum_eligible_building_count",
    "minimum_ordinary_task_count", "minimum_stress_task_count",
)
EXPECTED_FORMULAS = {
    "q_gt_ci_half_width": "normal_95_max_worker_se",
    "risk_slope_ci_half_width": "normal_95_max_unified_slope_sd",
    "minimum_worker_support": "min_constant_and_min_capacity",
    **{name: "frozen_constant" for name in REQUIRED_THRESHOLDS if name not in {
        "q_gt_ci_half_width", "risk_slope_ci_half_width", "minimum_worker_support",
    }},
}
EXPECTED_DIRECTIONS = {
    "q_gt_ci_half_width": "maximum", "risk_slope_ci_half_width": "maximum",
    "maximum_mean_rank_displacement": "maximum",
    **{name: "minimum" for name in REQUIRED_THRESHOLDS if name not in {
        "q_gt_ci_half_width", "risk_slope_ci_half_width", "maximum_mean_rank_displacement",
    }},
}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _truth(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def validate_formula_contract(payload: dict[str, Any]) -> None:
    if payload.get("schema_version") != "paper_a_c2b_design_threshold_formula_contract_v1":
        raise ValueError("unsupported C2-B threshold formula contract")
    if payload.get("status") != "frozen_before_c1_closeout" or payload.get("formula_contract_frozen") is not True:
        raise ValueError("C2-B threshold formula contract is not frozen")
    if not all(str(payload.get(field, "")).strip() for field in ("frozen_by", "frozen_at")):
        raise ValueError("C2-B threshold formula freeze identity is incomplete")
    rules = payload.get("threshold_rules", {})
    if set(rules) != set(REQUIRED_THRESHOLDS):
        raise ValueError("C2-B threshold formula set is incomplete")
    for name in REQUIRED_THRESHOLDS:
        rule = rules[name]
        if rule.get("formula_id") != EXPECTED_FORMULAS[name] or rule.get("direction") != EXPECTED_DIRECTIONS[name]:
            raise ValueError(f"unsupported C2-B threshold formula:{name}")
        if rule.get("formula_id") in {"frozen_constant", "min_constant_and_min_capacity"}:
            key = str(rule.get("constant_key", ""))
            value = payload.get("constants", {}).get(key)
            if not key or value in {None, ""} or not math.isfinite(float(value)):
                raise ValueError(f"missing C2-B threshold constant:{name}")
    multiplier = payload.get("constants", {}).get("normal_95_multiplier")
    if multiplier in {None, ""} or not math.isfinite(float(multiplier)) or float(multiplier) <= 0:
        raise ValueError("invalid normal_95_multiplier")
    anchors = payload.get("common_anchor_requirements", {})
    if int(anchors.get("minimum_count", 0)) < 2 or set(anchors.get("required_strata", [])) < {"ordinary", "stress"}:
        raise ValueError("invalid common-anchor formula contract")


def _approved_inputs(
    approval_path: Path, formula_contract: Path, c1_design_parameters: Path, capacity_manifest: Path,
) -> dict[str, Any]:
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    if approval.get("schema_version") != "paper_a_c2b_threshold_input_approval_v1" or approval.get("approved") is not True:
        raise ValueError("C2-B threshold input approval is missing or unapproved")
    expected = {
        "formula_contract_sha256": sha256_file(formula_contract),
        "c1_design_parameters_sha256": sha256_file(c1_design_parameters),
        "capacity_manifest_sha256": sha256_file(capacity_manifest),
    }
    stale = [field for field, value in expected.items() if approval.get(field) != value]
    if stale:
        raise ValueError("stale C2-B threshold input approval:" + ",".join(stale))
    if not all(str(approval.get(field, "")).strip() for field in ("reviewed_by", "reviewed_at")):
        raise ValueError("C2-B threshold input reviewer identity is incomplete")
    return approval


def derive_threshold_manifest(
    formula_contract: Path,
    c1_design_parameters: Path,
    capacity_manifest: Path,
    reviewer_approval: Path,
    output: Path,
) -> dict[str, Any]:
    """Derive approved values without reading candidates, simulations, or feasibility."""
    contract = json.loads(formula_contract.read_text(encoding="utf-8"))
    validate_formula_contract(contract)
    approval = _approved_inputs(reviewer_approval, formula_contract, c1_design_parameters, capacity_manifest)
    workers = [row for row in _read_csv(c1_design_parameters) if _truth(row.get("c2b_baseline_eligible"))]
    if not workers:
        raise ValueError("no C2-B baseline-eligible C1 workers for threshold derivation")
    try:
        qgt_ses = [float(row["Q_GT_baseline_se"]) for row in workers]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("C1 Q_GT baseline SE is missing for threshold derivation") from exc
    if any(not math.isfinite(value) or value < 0 for value in qgt_ses):
        raise ValueError("C1 Q_GT baseline SE is nonfinite or negative for threshold derivation")
    slope_distributions = [_resolve_slope_distribution(row) for row in workers]
    if any(not distribution["valid"] for distribution in slope_distributions):
        raise ValueError("C1 slope distribution is missing for threshold derivation")
    capacities = _read_csv(capacity_manifest)
    if not capacities or len({row.get("worker_id", "") for row in capacities}) != len(capacities):
        raise ValueError("capacity manifest requires unique worker rows")
    capacity_by_worker: dict[str, int] = {}
    try:
        for row in capacities:
            capacity_by_worker[str(row["worker_id"])] = int(float(row["c2b_capacity"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("capacity manifest has a missing or invalid c2b_capacity") from exc
    worker_ids = {str(row.get("worker_id", "")) for row in workers}
    if not worker_ids <= capacity_by_worker.keys() or any(capacity_by_worker[worker] < 1 for worker in worker_ids):
        raise ValueError("capacity manifest does not cover every eligible C1 worker")

    constants = contract["constants"]
    multiplier = float(constants["normal_95_multiplier"])
    values: dict[str, float | int] = {}
    for name in REQUIRED_THRESHOLDS:
        rule = contract["threshold_rules"][name]
        formula_id = rule["formula_id"]
        if formula_id == "normal_95_max_worker_se":
            value: float | int = multiplier * max(qgt_ses)
        elif formula_id == "normal_95_max_unified_slope_sd":
            value = multiplier * max(float(distribution["total_sd"]) for distribution in slope_distributions)
        elif formula_id == "min_constant_and_min_capacity":
            value = min(int(float(constants[rule["constant_key"]])), min(capacity_by_worker[worker] for worker in worker_ids))
        else:  # validate_formula_contract admits only this remaining identifier.
            value = float(constants[rule["constant_key"]])
            if value.is_integer():
                value = int(value)
        if not math.isfinite(float(value)):
            raise ValueError(f"nonfinite derived C2-B threshold:{name}")
        values[name] = value

    payload = {
        "schema_version": "paper_a_c2b_design_selection_thresholds_v2",
        "status": "approved", "formal_selection_allowed": True,
        "approved_by": approval["reviewed_by"], "approved_at": approval["reviewed_at"],
        "thresholds": values,
        "common_anchor_requirements": contract["common_anchor_requirements"],
        "selection_rule": contract.get("selection_rule", "select_only_approved_non_dominated_design"),
        "derivation": {
            "formula_contract_sha256": sha256_file(formula_contract),
            "c1_design_parameters_sha256": sha256_file(c1_design_parameters),
            "capacity_manifest_sha256": sha256_file(capacity_manifest),
            "reviewer_approval_sha256": sha256_file(reviewer_approval),
            "formula_ids": {name: contract["threshold_rules"][name]["formula_id"] for name in REQUIRED_THRESHOLDS},
            "input_fields": [
                "worker_id", "c2b_baseline_eligible", "Q_GT_baseline_se", "risk_slope_for_simulation",
                "risk_slope_se", "risk_support", "group_slope_mean", "group_slope_se",
                "between_worker_slope_sd", "slope_model_form", "c2b_capacity",
            ],
            "derived_before_candidate_enumeration": True,
            "post_feasibility_inputs_consumed": False,
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Derive SHA-bound C2-B selection thresholds.")
    parser.add_argument("--formula-contract", type=Path, required=True)
    parser.add_argument("--c1-design-parameters", type=Path, required=True)
    parser.add_argument("--capacity-manifest", type=Path, required=True)
    parser.add_argument("--reviewer-approval", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(derive_threshold_manifest(
        args.formula_contract, args.c1_design_parameters, args.capacity_manifest,
        args.reviewer_approval, args.output,
    ), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
