"""Manifest-bound cluster bootstrap inference for T1 and V1."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any, Callable

import numpy as np

from tools.thesis_main.analysis.vfinal_artifact_utils import parse_bool, sha256_file, write_csv_rows


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _num(value: Any) -> float | None:
    try:
        return float(value) if str(value).strip() else None
    except (TypeError, ValueError):
        return None


def _mean(rows: list[dict[str, Any]], field: str) -> float:
    values = [_num(row.get(field)) for row in rows]
    present = [value for value in values if value is not None]
    if not present:
        raise ValueError(f"no evaluable values for {field}")
    return float(np.mean(present))


def _bootstrap(
    rows: list[dict[str, Any]], statistic: Callable[[list[dict[str, Any]]], float], *,
    cluster_field: str, draws: int, seed: int, confidence: float,
) -> tuple[float, float, float, int]:
    estimate = statistic(rows)
    groups: dict[str, list[dict[str, Any]]] = {}
    for index, row in enumerate(rows):
        key = str(row.get(cluster_field) or row.get("image_id") or row.get("task_id") or index)
        groups.setdefault(key, []).append(row)
    keys = sorted(groups)
    if len(keys) < 2:
        raise ValueError(f"inference requires at least two {cluster_field} clusters")
    rng, values = np.random.default_rng(seed), []
    for _ in range(draws):
        sample = [row for key in rng.choice(keys, len(keys), replace=True) for row in groups[str(key)]]
        try:
            values.append(statistic(sample))
        except ValueError:
            pass
    if len(values) < max(20, draws // 2):
        raise ValueError("too few evaluable bootstrap draws")
    alpha = (1 - confidence) / 2
    lower, upper = np.quantile(values, [alpha, 1 - alpha])
    return estimate, float(lower), float(upper), len(values)


def infer_t1(rows: list[dict[str, str]], config: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    required = {"image_id", "risk_assist", "delivery_adjusted_quality_diff_semi_minus_manual"}
    if not rows or not required.issubset(rows[0]):
        raise ValueError("T1 inference requires the image-level primary table")
    cluster = str(config.get("cluster_field") or ("building_id" if any(row.get("building_id") for row in rows) else "image_id"))
    draws, seed, confidence = int(config["bootstrap_replicates"]), int(config["bootstrap_seed"]), float(config["confidence_level"])
    specs = [
        ("delivery_adjusted_quality", "delivery_adjusted_quality_diff_semi_minus_manual", "quality_noninferiority_margin", "primary"),
        ("structural_validity", "structurally_valid_diff_semi_minus_manual", "structural_noninferiority_margin", "primary"),
        ("active_time", "owner_valid_active_time_diff_semi_minus_manual", "", "primary"),
        ("valid_only_iou", "valid_only_iou_diff_semi_minus_manual", "", "sensitivity"),
    ]
    output = []
    for index, (name, field, margin_field, role) in enumerate(specs):
        evaluable = [row for row in rows if _num(row.get(field)) is not None]
        estimate, lower, upper, used = _bootstrap(evaluable, lambda sample, f=field: _mean(sample, f), cluster_field=cluster, draws=draws, seed=seed + index, confidence=confidence)
        decision = "" if not margin_field else ("pass" if lower > -float(config[margin_field]) else "fail")
        output.append({"stage": "T1", "estimand": name, "effect_estimate": estimate, "ci_lower": lower, "ci_upper": upper, "n_units": len(evaluable), "n_missing": len(rows) - len(evaluable), "bootstrap_draws": used, "gate_decision": decision, "analysis_role": role})
    if {row.get("risk_assist") for row in rows} >= {"ordinary", "stress_assist"}:
        def interaction(sample: list[dict[str, str]]) -> float:
            return _mean([row for row in sample if row.get("risk_assist") == "stress_assist"], "delivery_adjusted_quality_diff_semi_minus_manual") - _mean([row for row in sample if row.get("risk_assist") == "ordinary"], "delivery_adjusted_quality_diff_semi_minus_manual")
        estimate, lower, upper, used = _bootstrap(rows, interaction, cluster_field=cluster, draws=draws, seed=seed + 20, confidence=confidence)
        output.append({"stage": "T1", "estimand": "mode_x_risk_assist", "effect_estimate": estimate, "ci_lower": lower, "ci_upper": upper, "n_units": len(rows), "n_missing": 0, "bootstrap_draws": used, "gate_decision": "", "analysis_role": "interaction"})
    return output, {"stage": "T1", "cluster_field": cluster, "n_images": len(rows)}


def infer_v1(rows: list[dict[str, str]], config: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    included = [row for row in rows if parse_bool(row.get("itt_included"))]
    arms = {arm: [row for row in included if row.get("policy_arm") == arm] for arm in ("strong_global", "full_integrated")}
    if not included or not all(arms.values()):
        raise ValueError("V1 inference requires both randomized ITT arms")
    draws, seed, confidence = int(config["bootstrap_replicates"]), int(config["bootstrap_seed"]), float(config["confidence_level"])
    def contrast(field: str = "", transform: Callable[[dict[str, str]], float] | None = None):
        def statistic(sample: list[dict[str, str]]) -> float:
            split = {arm: [row for row in sample if row.get("policy_arm") == arm] for arm in arms}
            if not all(split.values()): raise ValueError("bootstrap arm missing")
            metric = lambda subset: float(np.mean([transform(row) for row in subset])) if transform else _mean(subset, field)
            return metric(split["full_integrated"]) - metric(split["strong_global"])
        return statistic
    specs = [
        ("severe_failure", "", lambda row: float(row.get("policy_terminal_status") == "severe_failure"), "severe_failure_noninferiority_margin"),
        ("non_delivery", "", lambda row: float(parse_bool(row.get("non_delivery")) or row.get("policy_terminal_status") != "resolved"), "non_delivery_noninferiority_margin"),
        ("delivery_adjusted_quality", "delivery_adjusted_quality", None, ""),
        ("k_used", "k_used", None, ""), ("active_time", "active_time_seconds", None, ""),
        ("completion_time", "completion_time_seconds", None, ""),
    ]
    output = []
    for index, (name, field, transform, margin_field) in enumerate(specs):
        evaluable = included if transform else [row for row in included if _num(row.get(field)) is not None]
        estimate, lower, upper, used = _bootstrap(evaluable, contrast(field, transform), cluster_field="task_id", draws=draws, seed=seed + index, confidence=confidence)
        decision = "" if not margin_field else ("pass" if upper < float(config[margin_field]) else "fail")
        output.append({"stage": "V1", "estimand": f"full_minus_global_{name}", "effect_estimate": estimate, "ci_lower": lower, "ci_upper": upper, "n_units": len(evaluable), "n_missing": len(included) - len(evaluable), "bootstrap_draws": used, "gate_decision": decision, "analysis_role": "primary"})
    resolved = [row for row in included if row.get("policy_terminal_status") == "resolved" and _num(row.get("iou_to_gt")) is not None]
    if {row.get("policy_arm") for row in resolved} == set(arms):
        estimate, lower, upper, used = _bootstrap(resolved, contrast("iou_to_gt"), cluster_field="task_id", draws=draws, seed=seed + 30, confidence=confidence)
        output.append({"stage": "V1", "estimand": "full_minus_global_resolved_only_quality", "effect_estimate": estimate, "ci_lower": lower, "ci_upper": upper, "n_units": len(resolved), "n_missing": len(included) - len(resolved), "bootstrap_draws": used, "gate_decision": "", "analysis_role": "sensitivity"})
    counts = Counter("administrative_censor" if row.get("analysis_disposition") == "administrative_censor" else "external_rerun" if parse_bool(row.get("rerun_used")) else "policy_failure" if parse_bool(row.get("policy_failure")) else "non_delivery" if parse_bool(row.get("non_delivery")) else "other" for row in rows)
    return output, {"stage": "V1", "n_itt": len(included), **dict(counts)}


def materialize(stage: str, input_csv: Path, manifest_path: Path, output_dir: Path, *, input_sha256: str, manifest_sha256: str) -> dict[str, Any]:
    if sha256_file(input_csv) != input_sha256.lower() or sha256_file(manifest_path) != manifest_sha256.lower():
        raise ValueError("formal inference input or manifest SHA mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    config = manifest.get(stage.upper())
    if not isinstance(config, dict) or not {"confidence_level", "bootstrap_replicates", "bootstrap_seed"}.issubset(config):
        raise ValueError(f"frozen {stage} analysis manifest is incomplete")
    results, audit = infer_t1(_read(input_csv), config) if stage.upper() == "T1" else infer_v1(_read(input_csv), config)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv_rows(output_dir / f"{stage.lower()}_formal_inference.csv", results)
    audit.update({"input_sha256": input_sha256.lower(), "analysis_manifest_sha256": manifest_sha256.lower()})
    (output_dir / f"{stage.lower()}_formal_inference.audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("T1", "V1"), required=True)
    parser.add_argument("--input-csv", type=Path, required=True)
    parser.add_argument("--analysis-manifest", type=Path, required=True)
    parser.add_argument("--input-sha256", required=True)
    parser.add_argument("--analysis-manifest-sha256", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(materialize(args.stage, args.input_csv, args.analysis_manifest, args.output_dir, input_sha256=args.input_sha256, manifest_sha256=args.analysis_manifest_sha256), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
