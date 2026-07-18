"""Materialize descriptive T1/V1 analyses from resolver-finalized CSVs only."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import fmean
from typing import Any


T1_PAIR_FIELDS = [
    "analysis_unit_pair_id", "risk_assist", "pair_analysis_disposition", "source_pair_id",
    "rerun_used", "delivery_adjusted_quality_manual", "delivery_adjusted_quality_semi",
    "delivery_adjusted_quality_diff_semi_minus_manual", "structurally_valid_manual",
    "structurally_valid_semi", "structurally_valid_diff_semi_minus_manual",
    "valid_only_iou_manual", "valid_only_iou_semi", "valid_only_iou_diff_semi_minus_manual",
    "owner_valid_active_time_manual", "owner_valid_active_time_semi",
    "owner_valid_active_time_diff_semi_minus_manual",
]
T1_SUMMARY_FIELDS = [
    "risk_assist", "n_pairs", "delivery_adjusted_quality_diff_mean",
    "structurally_valid_diff_mean", "valid_only_iou_diff_mean",
    "owner_valid_active_time_diff_mean", "active_time_pair_coverage",
]
V1_SUMMARY_FIELDS = [
    "policy_arm", "risk_route", "n_itt", "unresolved_rate", "severe_failure_rate",
    "delivery_adjusted_quality_mean", "resolved_only_quality_mean", "k_used_mean",
    "active_time_seconds_mean", "completion_time_seconds_mean", "policy_failure_rate",
]
V1_STANDARDIZED_FIELDS = [
    "policy_arm", "standardization", "ordinary_weight", "stress_route_weight",
    "weight_source_sha256", "unresolved_rate", "severe_failure_rate",
    "delivery_adjusted_quality_mean", "resolved_only_quality_mean", "k_used_mean",
    "active_time_seconds_mean", "completion_time_seconds_mean", "policy_failure_rate",
]


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _number(value: Any, *, field: str, required: bool = False) -> float | None:
    raw = _text(value)
    if not raw:
        if required:
            raise ValueError(f"missing numeric field: {field}")
        return None
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{field} must be numeric") from exc


def _bool(value: Any, *, field: str) -> bool:
    raw = _text(value).lower()
    if raw in {"true", "1", "yes"}:
        return True
    if raw in {"false", "0", "no"}:
        return False
    raise ValueError(f"{field} must be boolean")


def _mean(values: list[float | None]) -> float | str:
    present = [value for value in values if value is not None]
    return fmean(present) if present else ""


def _risk(value: Any, *, stage: str) -> str:
    raw = _text(value).lower()
    mapping = (
        {"ordinary": "ordinary", "stress_assist": "stress_assist", "false": "ordinary", "0": "ordinary", "true": "stress_assist", "1": "stress_assist"}
        if stage == "T1"
        else {"ordinary": "ordinary", "stress_route": "stress_route", "false": "ordinary", "0": "ordinary", "true": "stress_route", "1": "stress_route"}
    )
    if raw not in mapping:
        raise ValueError(f"invalid {stage} risk field: {raw}")
    return mapping[raw]


def _owner_valid_time(row: dict[str, Any]) -> float | None:
    status = _text(row.get("active_time_integrity_status")).lower()
    explicit = _text(row.get("owner_valid_active_time"))
    if explicit:
        return _number(explicit, field="owner_valid_active_time")
    if status not in {"exact_annotation_valid", "primary_exact_owner_valid"}:
        return None
    return _number(row.get("active_time_seconds"), field="active_time_seconds")


def analyze_t1(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    if not rows:
        raise ValueError("T1 resolver-finalized input is empty")
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        pair_id = _text(row.get("analysis_unit_pair_id"))
        if not pair_id or not _text(row.get("pair_analysis_disposition")) or not _text(row.get("source_pair_id")):
            raise ValueError("T1 input must be resolver-finalized and include analysis_unit_pair_id, pair_analysis_disposition, source_pair_id")
        grouped[pair_id].append(row)

    pair_rows: list[dict[str, Any]] = []
    dispositions: Counter[str] = Counter()
    active_eligible = 0
    for pair_id, members in grouped.items():
        conditions = Counter(_text(row.get("condition")).lower() for row in members)
        if len(members) != 2 or conditions != {"manual": 1, "semi": 1}:
            raise ValueError(f"T1 pair {pair_id} must contain exactly one Manual and one Semi")
        values = {_text(row.get("pair_analysis_disposition")) for row in members}
        risks = {_risk(row.get("risk_assist"), stage="T1") for row in members}
        sources = {_text(row.get("source_pair_id")) for row in members}
        if len(values) != 1 or len(risks) != 1 or len(sources) != 1:
            raise ValueError(f"T1 pair {pair_id} has inconsistent resolver fields")
        disposition, risk, source = values.pop(), risks.pop(), sources.pop()
        if disposition not in {"included", "administrative_censor", "not_evaluable"}:
            raise ValueError(f"T1 pair {pair_id} is not resolver-finalized: {disposition}")
        dispositions[disposition] += 1
        if disposition != "included":
            continue
        by_condition = {_text(row.get("condition")).lower(): row for row in members}
        manual, semi = by_condition["manual"], by_condition["semi"]
        da_m = _number(manual.get("delivery_adjusted_quality"), field="delivery_adjusted_quality", required=True)
        da_s = _number(semi.get("delivery_adjusted_quality"), field="delivery_adjusted_quality", required=True)
        sv_m = float(_bool(manual.get("structurally_valid"), field="structurally_valid"))
        sv_s = float(_bool(semi.get("structurally_valid"), field="structurally_valid"))
        iou_m = _number(manual.get("iou_to_gt"), field="iou_to_gt") if sv_m else None
        iou_s = _number(semi.get("iou_to_gt"), field="iou_to_gt") if sv_s else None
        time_m, time_s = _owner_valid_time(manual), _owner_valid_time(semi)
        if time_m is not None and time_s is not None:
            active_eligible += 1
        pair_rows.append({
            "analysis_unit_pair_id": pair_id, "risk_assist": risk,
            "pair_analysis_disposition": disposition, "source_pair_id": source,
            "rerun_used": source != pair_id,
            "delivery_adjusted_quality_manual": da_m, "delivery_adjusted_quality_semi": da_s,
            "delivery_adjusted_quality_diff_semi_minus_manual": da_s - da_m,
            "structurally_valid_manual": sv_m, "structurally_valid_semi": sv_s,
            "structurally_valid_diff_semi_minus_manual": sv_s - sv_m,
            "valid_only_iou_manual": "" if iou_m is None else iou_m,
            "valid_only_iou_semi": "" if iou_s is None else iou_s,
            "valid_only_iou_diff_semi_minus_manual": "" if iou_m is None or iou_s is None else iou_s - iou_m,
            "owner_valid_active_time_manual": "" if time_m is None else time_m,
            "owner_valid_active_time_semi": "" if time_s is None else time_s,
            "owner_valid_active_time_diff_semi_minus_manual": "" if time_m is None or time_s is None else time_s - time_m,
        })

    summary = []
    for risk in ("ordinary", "stress_assist"):
        subset = [row for row in pair_rows if row["risk_assist"] == risk]
        if not subset:
            continue
        active = [row for row in subset if row["owner_valid_active_time_diff_semi_minus_manual"] != ""]
        summary.append({
            "risk_assist": risk, "n_pairs": len(subset),
            "delivery_adjusted_quality_diff_mean": _mean([row["delivery_adjusted_quality_diff_semi_minus_manual"] for row in subset]),
            "structurally_valid_diff_mean": _mean([row["structurally_valid_diff_semi_minus_manual"] for row in subset]),
            "valid_only_iou_diff_mean": _mean([None if row["valid_only_iou_diff_semi_minus_manual"] == "" else row["valid_only_iou_diff_semi_minus_manual"] for row in subset]),
            "owner_valid_active_time_diff_mean": _mean([None if row["owner_valid_active_time_diff_semi_minus_manual"] == "" else row["owner_valid_active_time_diff_semi_minus_manual"] for row in subset]),
            "active_time_pair_coverage": len(active) / len(subset),
        })
    audit = {
        "n_original_pairs": len(grouped),
        "n_final_included_pairs": len(pair_rows),
        "n_rerun_pairs": sum(bool(row["rerun_used"]) for row in pair_rows),
        "pair_disposition_counts": dict(sorted(dispositions.items())),
        "active_time_pair_coverage": active_eligible / len(pair_rows) if pair_rows else 0.0,
    }
    return pair_rows, summary, audit


def _v1_group(rows: list[dict[str, Any]], arm: str, risk: str) -> dict[str, Any]:
    subset = [row for row in rows if row["_arm"] == arm and row["_risk"] == risk and row["_itt"]]
    resolved = [row for row in subset if row["_terminal"] == "resolved"]
    return {
        "policy_arm": arm, "risk_route": risk, "n_itt": len(subset),
        "unresolved_rate": _mean([float(row["_terminal"] == "unresolved") for row in subset]),
        "severe_failure_rate": _mean([float(row["_terminal"] == "severe_failure") for row in subset]),
        "delivery_adjusted_quality_mean": _mean([row["_da"] for row in subset]),
        "resolved_only_quality_mean": _mean([row["_iou"] for row in resolved]),
        "k_used_mean": _mean([row["_k"] for row in subset]),
        "active_time_seconds_mean": _mean([row["_active"] for row in subset]),
        "completion_time_seconds_mean": _mean([row["_completion"] for row in subset]),
        "policy_failure_rate": _mean([float(row["_policy_failure"]) for row in subset]),
    }


def _weights(rows: list[dict[str, Any]] | None) -> tuple[list[tuple[str, float, float, str]], str]:
    scenarios = [
        ("scenario_80_20", .8, .2, ""), ("scenario_60_40", .6, .4, ""),
        ("scenario_50_50", .5, .5, ""), ("scenario_30_70", .3, .7, ""),
    ]
    if rows is None:
        return scenarios, "pre_registered_scenarios"
    if len(rows) != 2:
        raise ValueError("production weights must contain exactly two rows")
    parsed = {_risk(row.get("risk_route"), stage="V1"): _number(row.get("weight"), field="weight", required=True) for row in rows}
    hashes = {_text(row.get("source_sha256")).lower() for row in rows}
    if set(parsed) != {"ordinary", "stress_route"} or abs(sum(parsed.values()) - 1) > 1e-9:
        raise ValueError("production weights must contain ordinary and stress_route and sum to 1")
    if len(hashes) != 1 or len(next(iter(hashes), "")) != 64 or any(ch not in "0123456789abcdef" for ch in next(iter(hashes), "")):
        raise ValueError("production weights require one valid source_sha256")
    source = hashes.pop()
    return [("production", parsed["ordinary"], parsed["stress_route"], source)], "independent_production_weights"


def analyze_v1(
    rows: list[dict[str, Any]], production_weights: list[dict[str, Any]] | None = None
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    if not rows:
        raise ValueError("V1 resolver-finalized input is empty")
    seen: set[str] = set()
    prepared = []
    dispositions: Counter[str] = Counter()
    for raw in rows:
        row = dict(raw)
        task_id, original = _text(row.get("task_id")), _text(row.get("original_task_id"))
        if not task_id or task_id != original or task_id in seen or not _text(row.get("resolved_task_id")):
            raise ValueError("V1 input must contain one resolver-finalized row per original randomized task")
        seen.add(task_id)
        arm = _text(row.get("policy_arm")).lower()
        if arm not in {"strong_global", "full_integrated"}:
            raise ValueError(f"invalid policy_arm: {arm}")
        disposition = _text(row.get("analysis_disposition"))
        if disposition not in {"included", "administrative_censor", "not_evaluable"}:
            raise ValueError(f"V1 task {task_id} is not resolver-finalized")
        dispositions[disposition] += 1
        itt = _bool(row.get("itt_included"), field="itt_included")
        if disposition == "included" and not itt or disposition != "included" and itt:
            raise ValueError(f"V1 task {task_id} has inconsistent ITT disposition")
        terminal = _text(row.get("policy_terminal_status")).lower()
        if itt and terminal not in {"resolved", "unresolved", "severe_failure"}:
            raise ValueError(f"invalid final policy_terminal_status: {terminal}")
        policy_failure = _bool(row.get("policy_failure"), field="policy_failure")
        da = _number(row.get("delivery_adjusted_quality"), field="delivery_adjusted_quality", required=itt)
        if itt and policy_failure and da != 0:
            raise ValueError("policy failure must remain in ITT with delivery_adjusted_quality=0")
        row.update({
            "_arm": arm, "_risk": _risk(row.get("risk_route"), stage="V1"), "_itt": itt,
            "_terminal": terminal, "_policy_failure": policy_failure, "_da": da,
            "_iou": _number(row.get("iou_to_gt"), field="iou_to_gt") if terminal == "resolved" else None,
            "_k": _number(row.get("k_used") or row.get("primary_k_used"), field="k_used"),
            "_active": _number(row.get("active_time_seconds"), field="active_time_seconds"),
            "_completion": _number(row.get("completion_time_seconds"), field="completion_time_seconds"),
        })
        prepared.append(row)

    summary = [
        _v1_group(prepared, arm, risk)
        for arm in ("strong_global", "full_integrated")
        for risk in ("ordinary", "stress_route")
        if any(row["_arm"] == arm and row["_risk"] == risk and row["_itt"] for row in prepared)
    ]
    by_key = {(row["policy_arm"], row["risk_route"]): row for row in summary}
    weight_sets, weight_mode = _weights(production_weights)
    standardized = []
    metrics = V1_SUMMARY_FIELDS[3:]
    for arm in ("strong_global", "full_integrated"):
        ordinary, stress = by_key.get((arm, "ordinary")), by_key.get((arm, "stress_route"))
        if not ordinary or not stress:
            continue
        for name, ordinary_weight, stress_weight, source_sha in [("design_50_50", .5, .5, ""), *weight_sets]:
            result = {
                "policy_arm": arm, "standardization": name,
                "ordinary_weight": ordinary_weight, "stress_route_weight": stress_weight,
                "weight_source_sha256": source_sha,
            }
            for metric in metrics:
                left, right = ordinary[metric], stress[metric]
                result[metric] = "" if left == "" or right == "" else ordinary_weight * left + stress_weight * right
            standardized.append(result)
    audit = {
        "n_original_randomized_tasks": len(prepared),
        "n_administrative_censor": dispositions["administrative_censor"],
        "n_not_evaluable": dispositions["not_evaluable"],
        "disposition_counts": dict(sorted(dispositions.items())),
        "production_standardization_mode": weight_mode,
    }
    task_rows = [{key: value for key, value in row.items() if not key.startswith("_")} for row in prepared]
    return task_rows, summary, standardized, audit


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_formal_inputs(
    input_path: Path, freeze_manifest: Path, rule_manifest: Path, *,
    input_sha256: str, freeze_manifest_sha256: str, rule_manifest_sha256: str,
) -> dict[str, str]:
    expected = (
        ("input", input_path, input_sha256),
        ("freeze manifest", freeze_manifest, freeze_manifest_sha256),
        ("rule manifest", rule_manifest, rule_manifest_sha256),
    )
    result = {}
    for label, path, declared in expected:
        actual = _sha256(path)
        if actual != declared.lower():
            raise ValueError(f"{label} SHA256 mismatch")
        result[label.replace(" ", "_") + "_sha256"] = actual
    return result


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = fields or list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("T1", "V1"), required=True)
    parser.add_argument("--resolved-input-csv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--production-weights-csv", type=Path)
    parser.add_argument("--production-weights-sha256")
    parser.add_argument("--input-status", choices=("dryrun", "formal"), default="dryrun")
    parser.add_argument("--freeze-manifest", type=Path)
    parser.add_argument("--rule-manifest", type=Path)
    parser.add_argument("--input-sha256")
    parser.add_argument("--freeze-manifest-sha256")
    parser.add_argument("--rule-manifest-sha256")
    args = parser.parse_args()
    hashes = {}
    if args.input_status == "formal":
        required = (
            args.output_dir, args.freeze_manifest, args.rule_manifest, args.input_sha256,
            args.freeze_manifest_sha256, args.rule_manifest_sha256,
        )
        if not all(required):
            raise ValueError("formal analysis requires output-dir and input/freeze/rule manifests with declared SHA256")
        hashes = verify_formal_inputs(
            args.resolved_input_csv, args.freeze_manifest, args.rule_manifest,
            input_sha256=args.input_sha256,
            freeze_manifest_sha256=args.freeze_manifest_sha256,
            rule_manifest_sha256=args.rule_manifest_sha256,
        )
    rows = _read_csv(args.resolved_input_csv)
    production_weights = None
    if args.production_weights_csv:
        actual_weights_sha = _sha256(args.production_weights_csv)
        if args.input_status == "formal" and actual_weights_sha != _text(args.production_weights_sha256).lower():
            raise ValueError("production weights SHA256 mismatch")
        hashes["production_weights_csv_sha256"] = actual_weights_sha
        production_weights = _read_csv(args.production_weights_csv)
    if args.stage == "T1":
        units, summary, audit = analyze_t1(rows)
        outputs = [("t1_pair_analysis.csv", units, T1_PAIR_FIELDS), ("t1_summary.csv", summary, T1_SUMMARY_FIELDS)]
    else:
        units, summary, standardized, audit = analyze_v1(
            rows, production_weights
        )
        outputs = [
            ("v1_itt_tasks.csv", units, None), ("v1_summary.csv", summary, V1_SUMMARY_FIELDS),
            ("v1_standardized.csv", standardized, V1_STANDARDIZED_FIELDS),
        ]
    audit = {"stage": args.stage, "input_status": args.input_status, **hashes, **audit}
    if args.input_status == "dryrun":
        print(json.dumps(audit, ensure_ascii=False, sort_keys=True))
        return
    for name, data, fields in outputs:
        _write_csv(args.output_dir / name, data, fields)
    (args.output_dir / f"{args.stage.lower()}_analysis_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
