"""Full policy scoring constrained to risk plus at most one family adjustment."""

from __future__ import annotations

from typing import Any
import argparse
import csv
import json
import hashlib
import math
from pathlib import Path


def _truth(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _approved(manifest: dict[str, Any] | None) -> bool:
    return bool(manifest and manifest.get("status") == "approved" and manifest.get("interpretation_allowed") is True and manifest.get("approved_by") and manifest.get("approved_at") and manifest.get("input_sha256"))


def _first(manifest: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in manifest:
            return manifest[key]
    return None


def _interval(row: dict[str, Any]) -> tuple[float | None, float | None]:
    return _finite(_first(row, "component_interval_lower", "adjustment_lower")), _finite(_first(row, "component_interval_upper", "adjustment_upper"))


def _validated_family_activation(task: dict[str, Any], threshold: float, margin: float, *, formal: bool) -> tuple[str, bool]:
    raw = task.get("family_scores")
    if not isinstance(raw, dict) or not raw:
        if formal:
            raise ValueError("formal Full requires all family_scores")
        declared = str(task.get("activated_failure_family", ""))
        return declared, bool(declared)
    scores = []
    for family, value in raw.items():
        score = _finite(value)
        if score is None:
            raise ValueError("Full family_scores must be finite")
        scores.append((str(family), score))
    scores.sort(key=lambda item: (-item[1], item[0]))
    second = scores[1][1] if len(scores) > 1 else float("-inf")
    active = scores[0][1] >= threshold and scores[0][1] - second >= margin
    declared = str(task.get("activated_failure_family", ""))
    if formal and declared != (scores[0][0] if active else ""):
        raise ValueError("activated_failure_family conflicts with frozen family_scores")
    return (scores[0][0] if active else ""), active


def _validate_formal_contract(policy_manifest, profile_manifest, component_manifest, task, components):
    errors = []
    if not _approved(policy_manifest): errors.append("policy_manifest")
    if not _approved(profile_manifest): errors.append("profile_manifest")
    if not _approved(component_manifest): errors.append("component_manifest")
    policy = policy_manifest or {}
    profile = profile_manifest or {}
    component = component_manifest or {}
    whitelist = _first(policy, "allowed_family_whitelist", "allowed_p1_families")
    weights = policy.get("allowed_component_weights")
    if not isinstance(whitelist, list) or not whitelist: errors.append("allowed_family_whitelist")
    if not isinstance(weights, list) or not weights: errors.append("allowed_component_weights")
    for field in ("minimum_component_worker_support", "minimum_component_task_support", "symmetric_adjustment_cap", "activation_threshold", "activation_margin"):
        if field not in policy: errors.append(field)
    if not str(profile.get("profile_version", "")).strip(): errors.append("profile_version")
    required = _first(component, "required_component_fields", "component_required_fields")
    if not isinstance(required, list):
        errors.append("required_component_fields")
        required = []
    required_set = set(required)
    for field in ("component_status", "full_component_eligible", "combined_effect", "worker_support", "task_support", "shrinkage", "weight", "profile_version"):
        if field not in required_set: errors.append(f"component_contract:{field}")
    if not (({"component_interval_lower", "component_interval_upper"} <= required_set) or ({"adjustment_lower", "adjustment_upper"} <= required_set)):
        errors.append("component_contract:interval")
    if not isinstance(task.get("family_scores"), dict): errors.append("family_scores")
    for index, row in enumerate(components):
        for field in required_set:
            if field in {"component_interval_lower", "component_interval_upper", "adjustment_lower", "adjustment_upper"}: continue
            if field not in row or str(row.get(field, "")).strip() == "": errors.append(f"component_row_{index}:{field}")
        lower, upper = _interval(row)
        if lower is None or upper is None or lower > upper: errors.append(f"component_row_{index}:interval")
    try:
        min_worker = int(policy["minimum_component_worker_support"])
        min_task = int(policy["minimum_component_task_support"])
        cap = float(policy["symmetric_adjustment_cap"])
        activation_threshold = float(policy["activation_threshold"])
        activation_margin = float(policy["activation_margin"])
    except (KeyError, TypeError, ValueError):
        errors.append("numeric_contract")
        min_worker, min_task, cap, activation_threshold, activation_margin = 0, 0, 0.0, 0.0, 0.0
    if not all(math.isfinite(value) for value in (cap, activation_threshold, activation_margin)) or cap < 0 or activation_margin < 0:
        errors.append("numeric_contract")
    if errors: raise ValueError("formal Full contract missing or invalid: " + ";".join(dict.fromkeys(errors)))
    return [str(value) for value in whitelist], [float(value) for value in weights], min_worker, min_task, cap, activation_threshold, activation_margin


def build_full_policy(
    global_rows: list[dict[str, Any]], task: dict[str, Any], components: list[dict[str, Any]], *,
    policy_manifest: dict[str, Any] | None = None, profile_manifest: dict[str, Any] | None = None,
    component_manifest: dict[str, Any] | None = None, formal: bool = False,
) -> list[dict[str, Any]]:
    if formal:
        whitelist, allowed_weights, min_worker_support, min_task_support, cap, activation_threshold, activation_margin = _validate_formal_contract(policy_manifest, profile_manifest, component_manifest, task, components)
    else:
        policy = policy_manifest or {}
        whitelist = [str(value) for value in _first(policy, "allowed_family_whitelist", "allowed_p1_families") or []]
        allowed_weights = [float(value) for value in policy.get("allowed_component_weights", [])]
        min_worker_support = int(policy.get("minimum_component_worker_support", 2))
        min_task_support = int(policy.get("minimum_component_task_support", 1))
        cap = float(policy.get("symmetric_adjustment_cap", task.get("symmetric_adjustment_cap", float("inf"))))
        activation_threshold = float(policy.get("activation_threshold", task.get("activation_threshold", 0)))
        activation_margin = float(policy.get("activation_margin", task.get("activation_margin", 0)))
    activated_family, family_active = _validated_family_activation(task, activation_threshold, activation_margin, formal=formal)
    supported = [row for row in components if row.get("component_status") == "cross_stage_supported" and _truth(row.get("full_component_eligible", True)) and str(row.get("component_family", "")) == activated_family and (not formal or activated_family in whitelist) and str(row.get("worker_id", "")) and int(float(row.get("worker_support") or min_worker_support)) >= min_worker_support and int(float(row.get("task_support") or min_task_support)) >= min_task_support]
    if allowed_weights:
        supported = [row for row in supported if _finite(row.get("weight")) in allowed_weights]
    families = {row.get("component_family") for row in supported}
    if len(families) > 1: raise ValueError("a task may activate at most one failure family")
    by_worker = {str(row["worker_id"]): row for row in supported}
    in_support = _truth(task.get("calibration_support", False))
    conditional_workers = {str(row.get("worker_id", "")) for row in supported if str(row.get("worker_id", ""))}
    ambiguity = bool(task.get("family_scores")) and not family_active
    profile_version = str((profile_manifest or {}).get("profile_version", ""))
    version_conflict = bool(profile_version and any(str(row.get("profile_version", profile_version)) != profile_version for row in supported))
    global_fallback = not in_support or ambiguity or version_conflict or (bool(activated_family) and len(conditional_workers) < 2)
    output = []
    for row in global_rows:
        worker = str(row.get("worker_id", "")); base = _finite(row.get("S_G"))
        if formal and base is None: raise ValueError("formal Full requires finite S_G for every global worker")
        base = 0.0 if base is None else base
        worker_global_eligible = _truth(row.get("global_policy_eligible", row.get("global_eligible", False)))
        risk_supported = not global_fallback and str(row.get("risk_activation_status", "")) == "supported"
        if formal and risk_supported:
            required_risk = ("risk_estimate", "risk_support", "risk_shrinkage", "risk_adjustment_lower", "risk_adjustment_upper", "risk_weight", "risk_profile_version")
            missing_risk = [field for field in required_risk if str(row.get(field, "")).strip() == "" or (_finite(row.get(field)) is None and field != "risk_profile_version")]
            if missing_risk:
                raise ValueError("formal Full risk component incomplete:" + ",".join(missing_risk))
        risk_adjustment = float(row.get("risk_adjustment") or 0) if risk_supported else 0.0
        component = by_worker.get(worker, {}) if not global_fallback else {}
        family_adjustment = float(component.get("adjustment") or 0) if component else 0.0
        raw_adjustment = risk_adjustment + family_adjustment
        capped_adjustment = max(-cap, min(cap, raw_adjustment)) if cap != float("inf") else raw_adjustment
        risk_lower = float(row.get("risk_adjustment_lower", risk_adjustment) or 0) if risk_supported else 0.0
        risk_upper = float(row.get("risk_adjustment_upper", risk_adjustment) or 0) if risk_supported else 0.0
        family_lower, family_upper = _interval(component) if component else (0.0, 0.0)
        family_lower = family_adjustment if family_lower is None else family_lower
        family_upper = family_adjustment if family_upper is None else family_upper
        lower = max(-cap, min(cap, risk_lower + family_lower)) if cap != float("inf") else risk_lower + family_lower
        upper = max(-cap, min(cap, risk_upper + family_upper)) if cap != float("inf") else risk_upper + family_upper
        if lower > upper: lower, upper = upper, lower
        fallback_reason = "global_policy_ineligible" if not worker_global_eligible else "outside_calibration_support" if not in_support else "activation_ambiguous" if ambiguity else "profile_version_conflict" if version_conflict else "conditional_supported_workers_lt_2" if global_fallback else ""
        score = base if global_fallback or not worker_global_eligible else base + capped_adjustment
        output.append({**row, "S_F": score, "raw_adjustment": raw_adjustment, "capped_adjustment": capped_adjustment, "adjustment_interval_lower": lower, "adjustment_interval_upper": upper, "risk_component_id": row.get("risk_component_id", "risk_route"), "risk_estimate": row.get("risk_estimate", ""), "risk_support": row.get("risk_support", ""), "risk_shrinkage": row.get("risk_shrinkage", ""), "risk_activation_status": "supported" if risk_supported else "inactive", "risk_adjustment_applied": risk_adjustment if not global_fallback else 0.0, "family_component_id": component.get("component_family", ""), "family_estimate": component.get("combined_effect", ""), "family_support": component.get("worker_support", ""), "family_shrinkage": component.get("shrinkage", ""), "family_activation_status": "supported" if component else "inactive", "family_adjustment_applied": family_adjustment if not global_fallback else 0.0, "full_fallback_global": bool(global_fallback or not worker_global_eligible), "full_exclusion_reason": fallback_reason})
    eligible = [row for row in output if _truth(row.get("global_policy_eligible", row.get("global_eligible", False)))]
    if eligible and not global_fallback:
        nominal_winner = max(eligible, key=lambda row: (float(row["S_F"]), -int(row.get("global_rank_S_G") or row.get("global_rank_EB") or 10**9)))
        winner_min = float(nominal_winner.get("S_G") or 0) + float(nominal_winner["adjustment_interval_lower"])
        competing_max = max((float(row.get("S_G") or 0) + float(row["adjustment_interval_upper"]) for row in eligible if row is not nominal_winner), default=float("-inf"))
        if winner_min <= competing_max:
            global_fallback = True
            for row in output:
                row["S_F"] = float(row.get("S_G") or 0)
                row["risk_adjustment_applied"] = 0.0
                row["family_adjustment_applied"] = 0.0
                row["full_fallback_global"] = True
                row["full_exclusion_reason"] = "ranking_unstable_endpoint"
    ranked = sorted((row for row in output if _truth(row.get("global_policy_eligible", row.get("global_eligible", False)))), key=lambda row: (-float(row["S_F"]), int(row.get("global_rank_S_G") or row.get("global_rank_EB") or 10**9)))
    for index, row in enumerate(ranked, 1): row["full_rank"] = index
    for row in output:
        row.setdefault("full_rank", "")
        try: global_rank = int(row.get("global_rank_S_G") or row.get("global_rank_EB"))
        except (TypeError, ValueError): global_rank = None
        row["full_global_rank_difference"] = "" if global_rank is None or row["full_rank"] == "" else int(row["full_rank"]) - global_rank
        row["policy_diverged_from_global"] = row["full_global_rank_difference"] not in {"", 0}
    return output


def materialize(
    global_csv: Path, task_json: Path, components_csv: Path, output_csv: Path, *,
    policy_manifest_path: Path | None = None, profile_manifest_path: Path | None = None,
    component_manifest_path: Path | None = None, formal: bool = False,
) -> dict[str, Any]:
    def read(path: Path) -> list[dict[str, str]]:
        with path.open(encoding="utf-8-sig", newline="") as stream: return list(csv.DictReader(stream))
    def load(path: Path | None) -> dict[str, Any] | None:
        return json.loads(path.read_text(encoding="utf-8")) if path else None
    policy, profile, component = load(policy_manifest_path), load(profile_manifest_path), load(component_manifest_path)
    inputs = {"global_csv": global_csv, "task_json": task_json, "components_csv": components_csv}
    if formal:
        for name, manifest in (("policy", policy), ("profile", profile), ("component", component)):
            if not _approved(manifest): raise ValueError(f"formal Full requires approved {name} manifest")
            expected = manifest.get("input_sha256", {})
            for input_name, path in inputs.items():
                if expected.get(input_name) != hashlib.sha256(path.read_bytes()).hexdigest():
                    raise ValueError(f"stale_or_unbound:{name}:{input_name}")
    rows = build_full_policy(read(global_csv), json.loads(task_json.read_text(encoding="utf-8")), read(components_csv), policy_manifest=policy, profile_manifest=profile, component_manifest=component, formal=formal)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]) if rows else ["worker_id"]); writer.writeheader(); writer.writerows(rows)
    audit = {"rows": len(rows), "formal": formal, "fallback_count": sum(_truth(row.get("full_fallback_global")) for row in rows), "policy_divergence_count": sum(_truth(row.get("policy_diverged_from_global")) for row in rows)}
    output_csv.with_suffix(".audit.json").write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return audit


def main() -> None:
    parser=argparse.ArgumentParser(); parser.add_argument("--global-csv",type=Path,required=True); parser.add_argument("--task-json",type=Path,required=True); parser.add_argument("--components-csv",type=Path,required=True); parser.add_argument("--output-csv",type=Path,required=True); parser.add_argument("--policy-manifest",type=Path); parser.add_argument("--profile-manifest",type=Path); parser.add_argument("--component-manifest",type=Path); parser.add_argument("--formal",action="store_true"); args=parser.parse_args()
    print(json.dumps(materialize(args.global_csv, args.task_json, args.components_csv, args.output_csv, policy_manifest_path=args.policy_manifest, profile_manifest_path=args.profile_manifest, component_manifest_path=args.component_manifest, formal=args.formal), indent=2))


if __name__ == "__main__": main()
