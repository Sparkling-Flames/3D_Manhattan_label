from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import median
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.thesis_main.analysis.c1_live_collection_monitor import safe, truthy
from tools.thesis_main.analysis.prescreen_worker_gold_alignment_audit import (
    _load_final_gold,
    _points_from_final_gold,
)
from tools.thesis_main.analysis.quality_core.geometry_metrics import analyze_layout_pairing, compute_layout_mask_iou


RULE_VERSION = "p1_post_closeout_geometry_score_v1"
MIN_FORMAL_VERTICAL_PAIRS = 4
TASK_FIELDS = [
    "worker_id",
    "project_id",
    "task_id",
    "base_task_id",
    "dataset_group",
    "condition",
    "annotation_id",
    "geometry_reference_status",
    "reference_id",
    "reference_count",
    "winning_reference_id",
    "independence_status",
    "process_failure_observed",
    "worker_geometry_valid",
    "worker_point_count",
    "worker_pair_count",
    "worker_pairing_coverage",
    "worker_odd_points",
    "worker_unpaired_point_count",
    "worker_pairing_ambiguous",
    "worker_pairing_best_cost",
    "worker_pairing_second_best_cost",
    "worker_pairing_optimal_matching_count",
    "worker_pairing_ambiguity_reason",
    "reference_point_count",
    "reference_pair_count",
    "reference_pairing_coverage",
    "reference_odd_points",
    "reference_pairing_ambiguous",
    "reference_pairing_best_cost",
    "reference_pairing_second_best_cost",
    "reference_pairing_optimal_matching_count",
    "reference_pairing_ambiguity_reason",
    "geometry_score_gate_passed",
    "geometry_score_gate_reason",
    "reference_cardinality_valid",
    "geometry_metric_name",
    "geometry_metric_direction",
    "geometry_normalization_rule",
    "geometry_component_name",
    "geometry_component_value",
    "geometry_component_support",
    "geometry_component_stage",
    "geometry_component_pool",
    "geometry_score_raw",
    "geometry_score_task_percentile",
    "included_in_p1_geometry_profile",
    "exclusion_reason",
    "source_final_gold_sha256",
    "source_canonical_sha256",
    "scoring_rule_version",
]
PROFILE_FIELDS = [
    "worker_id",
    "stage",
    "pool",
    "n_p1_geometry_eligible",
    "p1_geometry_iou_median",
    "p1_geometry_iou_mean",
    "p1_geometry_iou_q25",
    "p1_geometry_iou_q75",
    "p1_geometry_component",
    "p1_geometry_support_status",
    "p1_geometry_excluded_count",
    "geometry_component_name",
    "geometry_metric_name",
    "geometry_metric_direction",
    "geometry_normalization_rule",
    "geometry_component_value",
    "geometry_component_support",
    "geometry_component_stage",
    "geometry_component_pool",
    "source_canonical_sha256",
    "source_final_gold_sha256",
    "scoring_rule_version",
]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: str(row.get(field, "")).lower() if isinstance(row.get(field, ""), bool) else row.get(field, "") for field in fields})


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _points(value: str) -> list[tuple[float, float]]:
    try:
        payload = json.loads(value)
        return [(float(point[0]), float(point[1])) for point in payload]
    except (TypeError, ValueError, json.JSONDecodeError, IndexError):
        return []


def _reference_status(row: dict[str, str]) -> str:
    explicit = safe(row.get("geometry_reference_status")).lower()
    if explicit in {"expert_hard_single", "hard_single_gt"}:
        return "expert_hard_single"
    if explicit in {"expert_hard_multi", "hard_multi_gt"}:
        return "expert_hard_multi"
    if explicit in {"soft_ambiguous", "scope_ambiguous", "audit_only", "unavailable"}:
        return explicit
    role = safe(row.get("gold_reference_role")).lower()
    if "multi" in role:
        return "expert_hard_multi"
    if safe(row.get("gold_status_for_alignment")) == "ready_for_alignment" and safe(row.get("validation_status")) == "final_gold_geometry_checked":
        return "expert_hard_single"
    return "unavailable"


def _quantile(values: list[float], fraction: float) -> float:
    values = sorted(values)
    if not values:
        return 0.0
    index = (len(values) - 1) * fraction
    low = int(index)
    high = min(low + 1, len(values) - 1)
    return values[low] + (values[high] - values[low]) * (index - low)


def _support(n: int) -> str:
    if n < 3:
        return "insufficient"
    if n < 5:
        return "weak"
    if n < 10:
        return "moderate"
    return "sufficient"


def materialize_scores(
    correction_csv: Path,
    canonical_csv: Path,
    gold_status_csv: Path,
    final_gold_jsonl: Path,
    output_dir: Path,
) -> dict[str, Any]:
    correction = _read_csv(correction_csv)
    canonical = _read_csv(canonical_csv)
    gold_status = {_safe_key(row.get("task_id")): row for row in _read_csv(gold_status_csv)}
    final_gold = _load_final_gold(final_gold_jsonl)
    canonical_sha = _sha256(canonical_csv)
    final_gold_sha = _sha256(final_gold_jsonl)
    canonical_by_annotation = {
        (_safe_key(row.get("project_id")), _safe_key(row.get("task_id")), _safe_key(row.get("annotation_id"))): row
        for row in canonical
    }
    rows: list[dict[str, Any]] = []
    for correction_row in correction:
        key = (_safe_key(correction_row.get("project_id")), _safe_key(correction_row.get("task_id")), _safe_key(correction_row.get("annotation_id")))
        canonical_row = canonical_by_annotation.get(key, {})
        gold = gold_status.get(_safe_key(correction_row.get("task_id")), {})
        ref_status = _reference_status(gold)
        reference_id = safe(gold.get("geometry_gold_task_id"))
        references = []
        seen_references = set()
        for ref_key in ([reference_id] if ":" in reference_id else [f"task_id:{reference_id}", f"base_task_id:{reference_id}"]):
            for reference in final_gold.get(ref_key, []):
                identity = json.dumps(reference, sort_keys=True, ensure_ascii=False)
                if identity not in seen_references:
                    seen_references.add(identity)
                    references.append(reference)
        reference_points: list[tuple[str, list[tuple[float, float]]]] = []
        for ref_index, reference in enumerate(references, start=1):
            points, reason = _points_from_final_gold(reference)
            if points and not reason:
                ref_identity = safe(reference.get("reference_id") or reference.get("record_id") or reference.get("task_id") or f"{reference_id}#{ref_index}")
                reference_points.append((ref_identity, points))
        worker_points = _points(safe(canonical_row.get("canonical_geometry")))
        worker_pairs, worker_pairing = analyze_layout_pairing(worker_points)
        geometry_valid = bool(worker_points) and not safe(canonical_row.get("parse_error")) and bool(worker_pairing.get("finite_in_bounds"))
        cardinality_valid = (ref_status == "expert_hard_single" and len(reference_points) == 1) or (ref_status == "expert_hard_multi" and len(reference_points) >= 2)
        raw_score = None
        winning_reference_id = ""
        winning_reference_pairing: dict[str, Any] = {}
        gate_reason = ""
        worker_gate = (
            geometry_valid
            and not worker_pairing.get("odd_points")
            and float(worker_pairing.get("coverage", 0)) == 1.0
            and int(worker_pairing.get("unpaired_point_count", 0)) == 0
            and not worker_pairing.get("pairing_ambiguous")
            and len(worker_pairs) >= MIN_FORMAL_VERTICAL_PAIRS
        )
        if not cardinality_valid:
            gate_reason = "hard_single_reference_cardinality_invalid" if ref_status == "expert_hard_single" else "hard_multi_reference_cardinality_invalid" if ref_status == "expert_hard_multi" else "reference_status_not_hard"
        elif not worker_gate:
            gate_reason = "worker_geometry_pairing_invalid" if len(worker_pairs) >= MIN_FORMAL_VERTICAL_PAIRS else "worker_geometry_insufficient_vertical_pairs"
        else:
            scored: list[tuple[float, str, dict[str, Any]]] = []
            for ref_identity, reference in reference_points:
                ref_pairs, ref_pairing = analyze_layout_pairing(reference)
                if not winning_reference_pairing:
                    winning_reference_pairing = ref_pairing
                ref_gate = (
                    bool(ref_pairing.get("finite_in_bounds"))
                    and not ref_pairing.get("odd_points")
                    and float(ref_pairing.get("coverage", 0)) == 1.0
                    and int(ref_pairing.get("unpaired_point_count", 0)) == 0
                    and not ref_pairing.get("pairing_ambiguous")
                    and len(ref_pairs) >= MIN_FORMAL_VERTICAL_PAIRS
                )
                if not ref_gate:
                    continue
                score, _meta = compute_layout_mask_iou(worker_points, reference)
                if score is not None:
                    scored.append((score, ref_identity, ref_pairing))
            if scored:
                raw_score, winning_reference_id, winning_reference_pairing = max(scored, key=lambda value: value[0])
            else:
                gate_reason = "reference_geometry_pairing_invalid"
        gate_passed = raw_score is not None and not gate_reason
        independent = safe(correction_row.get("independence_status")) == "independent"
        process_ok = not truthy(correction_row.get("process_failure_observed"))
        scope_ok = safe(gold.get("task_final_scope")).lower() == "in_scope"
        eligible = bool(gate_passed and independent and process_ok and scope_ok and safe(correction_row.get("condition")).lower() == "manual")
        exclusion = []
        if raw_score is None:
            exclusion.append("geometry_score_unavailable")
        if not independent:
            exclusion.append("non_independent_submission")
        if not process_ok:
            exclusion.append("process_failure")
        if not scope_ok:
            exclusion.append("not_in_scope")
        if safe(correction_row.get("condition")).lower() != "manual":
            exclusion.append("not_manual")
        rows.append(
            {
                "worker_id": safe(correction_row.get("worker_id")),
                "project_id": safe(correction_row.get("project_id")),
                "task_id": safe(correction_row.get("task_id")),
                "base_task_id": safe(correction_row.get("base_task_id")),
                "dataset_group": safe(correction_row.get("dataset_group")),
                "condition": safe(correction_row.get("condition")),
                "annotation_id": safe(correction_row.get("annotation_id")),
                "geometry_reference_status": ref_status,
                "reference_id": reference_id,
                "reference_count": len(reference_points),
                "winning_reference_id": winning_reference_id,
                "independence_status": safe(correction_row.get("independence_status")),
                "process_failure_observed": truthy(correction_row.get("process_failure_observed")),
                "worker_geometry_valid": geometry_valid,
                "worker_point_count": worker_pairing.get("n_points", 0),
                "worker_pair_count": worker_pairing.get("n_pairs", 0),
                "worker_pairing_coverage": worker_pairing.get("coverage", 0),
                "worker_odd_points": worker_pairing.get("odd_points", False),
                "worker_unpaired_point_count": worker_pairing.get("unpaired_point_count", 0),
                "worker_pairing_ambiguous": worker_pairing.get("pairing_ambiguous", False),
                "worker_pairing_best_cost": worker_pairing.get("best_cost", ""),
                "worker_pairing_second_best_cost": worker_pairing.get("second_best_cost", ""),
                "worker_pairing_optimal_matching_count": worker_pairing.get("optimal_matching_count", 0),
                "worker_pairing_ambiguity_reason": worker_pairing.get("ambiguity_reason", ""),
                "reference_point_count": winning_reference_pairing.get("n_points", 0),
                "reference_pair_count": winning_reference_pairing.get("n_pairs", 0),
                "reference_pairing_coverage": winning_reference_pairing.get("coverage", 0),
                "reference_odd_points": winning_reference_pairing.get("odd_points", False),
                "reference_pairing_ambiguous": winning_reference_pairing.get("pairing_ambiguous", False),
                "reference_pairing_best_cost": winning_reference_pairing.get("best_cost", ""),
                "reference_pairing_second_best_cost": winning_reference_pairing.get("second_best_cost", ""),
                "reference_pairing_optimal_matching_count": winning_reference_pairing.get("optimal_matching_count", 0),
                "reference_pairing_ambiguity_reason": winning_reference_pairing.get("ambiguity_reason", ""),
                "geometry_score_gate_passed": gate_passed,
                "geometry_score_gate_reason": gate_reason,
                "reference_cardinality_valid": cardinality_valid,
                "geometry_metric_name": "equirectangular_layout_mask_iou" if raw_score is not None else "",
                "geometry_metric_direction": "higher_is_better" if raw_score is not None else "",
                "geometry_normalization_rule": "unit_interval_identity" if raw_score is not None else "",
                "geometry_component_name": "P1_expert_layout_mask_iou" if raw_score is not None else "",
                "geometry_component_value": "" if raw_score is None else f"{raw_score:.8f}",
                "geometry_component_support": 1 if raw_score is not None else 0,
                "geometry_component_stage": "P1",
                "geometry_component_pool": safe(correction_row.get("dataset_group")),
                "geometry_score_raw": "" if raw_score is None else f"{raw_score:.8f}",
                "geometry_score_task_percentile": "",
                "included_in_p1_geometry_profile": eligible,
                "exclusion_reason": ";".join(dict.fromkeys(exclusion)),
                "source_final_gold_sha256": final_gold_sha,
                "source_canonical_sha256": canonical_sha,
                "scoring_rule_version": RULE_VERSION,
            }
        )

    by_task: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        if row["geometry_score_raw"] and row["independence_status"] == "independent" and not row["process_failure_observed"]:
            by_task[row["task_id"]].append(float(row["geometry_score_raw"]))
    for row in rows:
        raw = row["geometry_score_raw"]
        scores = by_task[row["task_id"]]
        if not raw or len(scores) < 2:
            continue
        value = float(raw)
        less = sum(score < value for score in scores)
        equal = sum(score == value for score in scores)
        rank = 1 + less + (equal - 1) / 2
        row["geometry_score_task_percentile"] = f"{(rank - 1) / (len(scores) - 1):.8f}"

    profiles: list[dict[str, Any]] = []
    by_worker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_worker[row["worker_id"]].append(row)
    for worker, group in sorted(by_worker.items()):
        included = [float(row["geometry_score_raw"]) for row in group if row["included_in_p1_geometry_profile"]]
        profiles.append(
            {
                "worker_id": worker,
                "stage": "P1",
                "pool": "PreScreen_manual",
                "n_p1_geometry_eligible": len(included),
                "p1_geometry_iou_median": f"{median(included):.8f}" if included else "",
                "p1_geometry_iou_mean": f"{sum(included) / len(included):.8f}" if included else "",
                "p1_geometry_iou_q25": f"{_quantile(included, 0.25):.8f}" if included else "",
                "p1_geometry_iou_q75": f"{_quantile(included, 0.75):.8f}" if included else "",
                "p1_geometry_component": f"{median(included):.8f}" if included else "",
                "p1_geometry_support_status": _support(len(included)),
                "p1_geometry_excluded_count": len(group) - len(included),
                "geometry_component_name": "P1_expert_layout_mask_iou",
                "geometry_metric_name": "equirectangular_layout_mask_iou",
                "geometry_metric_direction": "higher_is_better",
                "geometry_normalization_rule": "unit_interval_identity",
                "geometry_component_value": f"{median(included):.8f}" if included else "",
                "geometry_component_support": len(included),
                "geometry_component_stage": "P1",
                "geometry_component_pool": "PreScreen_manual",
                "source_canonical_sha256": canonical_sha,
                "source_final_gold_sha256": final_gold_sha,
                "scoring_rule_version": RULE_VERSION,
            }
        )

    task_path = output_dir / "p1_geometry_task_scores_v1.csv"
    profile_path = output_dir / "p1_worker_geometry_profile_v1.csv"
    summary_path = output_dir / "p1_geometry_score_summary_v1.json"
    report_path = output_dir / "p1_geometry_score_audit_v1.md"
    _write_csv(task_path, rows, TASK_FIELDS)
    _write_csv(profile_path, profiles, PROFILE_FIELDS)
    summary = {
        "scoring_rule_version": RULE_VERSION,
        "geometry_metric_name": "equirectangular_layout_mask_iou",
        "reference_policy": "hard_single_or_max_over_hard_multi",
        "n_task_rows": len(rows),
        "n_raw_scores": sum(bool(row["geometry_score_raw"]) for row in rows),
        "n_included_scores": sum(truthy(row["included_in_p1_geometry_profile"]) for row in rows),
        "n_workers": len(profiles),
        "source_canonical_sha256": canonical_sha,
        "source_final_gold_sha256": final_gold_sha,
        "task_scores_csv": str(task_path),
        "worker_profile_csv": str(profile_path),
        "post_closeout_only": True,
        "r_u_calib_writeback": False,
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# P1 Post-Closeout Geometry Score Audit",
                "",
                f"Metric: `{summary['geometry_metric_name']}`.",
                "Hard single references use one score; hard multi references use max-over-reference.",
                "Non-independent rows retain raw audit scores but are excluded from capability profile.",
                "",
                f"Task rows: {summary['n_task_rows']}",
                f"Raw scores: {summary['n_raw_scores']}",
                f"Included capability scores: {summary['n_included_scores']}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    summary.update({"summary_json": str(summary_path), "audit_md": str(report_path)})
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def _safe_key(value: Any) -> str:
    return "" if value is None else str(value).strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize read-only P1 post-closeout geometry scores.")
    parser.add_argument("--correction-csv", type=Path, required=True)
    parser.add_argument("--canonical-csv", type=Path, required=True)
    parser.add_argument("--gold-status-csv", type=Path, required=True)
    parser.add_argument("--final-gold-jsonl", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(materialize_scores(args.correction_csv, args.canonical_csv, args.gold_status_csv, args.final_gold_jsonl, args.output_dir), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
