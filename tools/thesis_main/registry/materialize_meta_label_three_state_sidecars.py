from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from tools.thesis_main.analysis.vfinal_artifact_utils import COMMON_SIDEcar_FIELDS, sha256_file, sidecar_common, write_csv_rows


RULE_VERSION = "meta_label_three_state_v1"
DESIGN_GROUPS = {
    "Calibration_anchor": "high_k_common_anchor",
    "C1_anchor": "high_k_common_anchor",
    "Calibration_core": "core_k5",
    "C1_core": "core_k5",
    "Calibration_semi": "semi_core",
    "C1_semi": "semi_core",
}


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _tokens(value: Any) -> list[str]:
    if isinstance(value, list):
        raw = value
    else:
        text = _text(value)
        if not text:
            return []
        try:
            parsed = json.loads(text)
        except Exception:
            parsed = text.replace(",", ";").split(";")
        raw = parsed if isinstance(parsed, list) else [parsed]
    return [str(item).strip() for item in raw if str(item).strip() and str(item).strip().lower() not in {"nan", "none", "na"}]


def _assertion(tag_name: str, value: Any, row: dict[str, Any]) -> tuple[str, bool, bool, bool]:
    if _text(row.get("parse_error")) or _text(row.get("schema_error")):
        return "not_evaluable", False, False, False
    tokens = {token.lower() for token in _tokens(value)}
    if not tokens:
        return "unasserted", False, False, True
    if tag_name == "model_issue":
        negatives = {"acceptable", "none", "no_issue", "no issue"}
    else:
        negatives = {"trivial", "none", "no_difficulty", "no difficulty"}
    if tokens & negatives and len(tokens) > 1:
        return "not_evaluable", False, False, False
    if tokens & negatives:
        return "explicit_negative", False, True, False
    return "positive_assertion", True, False, False


def _design_group(dataset_group: str) -> str:
    return DESIGN_GROUPS.get(dataset_group, "unknown")


def build_tag_observations(
    rows: Iterable[dict[str, Any]],
    *,
    source_artifact: str,
    source_sha256: str,
    input_status: str = "dry_run",
) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    for row in rows:
        for tag_name in ("difficulty", "model_issue"):
            status, positive, explicit_negative, unasserted = _assertion(tag_name, row.get(tag_name, ""), row)
            observations.append(
                {
                    **sidecar_common(source_artifact=source_artifact, source_sha256=source_sha256, stage="C1", pool=_text(row.get("dataset_group")), condition=_text(row.get("condition")), validity_status="dry_run" if input_status != "formal" else status, rule_version=RULE_VERSION),
                    "task_id": _text(row.get("task_id")),
                    "base_task_id": _text(row.get("base_task_id")),
                    "dataset_group": _text(row.get("dataset_group")),
                    "design_group": _design_group(_text(row.get("dataset_group"))),
                    "worker_id": _text(row.get("worker_id") or row.get("annotator_id")),
                    "canonical_annotation_id": _text(row.get("canonical_annotation_id")),
                    "tag_name": tag_name,
                    "tag_value": ";".join(_tokens(row.get(tag_name, ""))),
                    "assertion_status": status,
                    "positive_assertion": str(positive).lower(),
                    "explicit_negative": str(explicit_negative).lower(),
                    "unasserted": str(unasserted).lower(),
                    "replicated_conflict": "false",
                }
            )
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for observation in observations:
        groups[(observation["task_id"], observation["worker_id"], observation["tag_name"])].append(observation)
    for group in groups.values():
        states = {row["assertion_status"] for row in group}
        if "positive_assertion" in states and "explicit_negative" in states:
            for row in group:
                row["assertion_status"] = "not_evaluable"
                row["replicated_conflict"] = "true"
                row["validity_status"] = "not_evaluable" if input_status == "formal" else "dry_run"
                row["positive_assertion"] = "false"
                row["explicit_negative"] = "false"
                row["unasserted"] = "false"
    return observations


def _candidate_status(design_group: str, positive: int, negative: int, unasserted: int, conflicts: int) -> str:
    if conflicts or design_group == "unknown":
        return "not_evaluable"
    total = positive + negative + unasserted
    if total == 0:
        return "not_evaluable"
    positive_coverage = positive / total
    negative_coverage = negative / total
    unasserted_rate = unasserted / total
    if design_group == "core_k5":
        return "candidate_pass_broad" if positive >= 2 and negative <= 1 else "candidate_fail_broad"
    if design_group == "high_k_common_anchor":
        if positive >= 3 and positive_coverage >= 0.6 and negative_coverage <= 0.2 and unasserted_rate <= 0.4:
            return "candidate_pass_strict"
        if positive >= 2 and positive_coverage >= 0.4 and negative_coverage < 0.4 and unasserted_rate <= 0.6:
            return "candidate_pass_broad"
        return "candidate_fail"
    return "candidate_descriptive_only"


def build_three_state_summary(observations: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in observations:
        groups[(row.get("task_id", ""), row.get("tag_name", ""))].append(row)
    summaries = []
    for (task_id, tag_name), rows in sorted(groups.items()):
        positive = sum(row.get("assertion_status") == "positive_assertion" for row in rows)
        negative = sum(row.get("assertion_status") == "explicit_negative" for row in rows)
        unasserted = sum(row.get("assertion_status") == "unasserted" for row in rows)
        not_eval = sum(row.get("assertion_status") == "not_evaluable" for row in rows)
        conflicts = sum(row.get("replicated_conflict") == "true" for row in rows)
        total = positive + negative + unasserted
        if not_eval or conflicts or total == 0:
            consensus = "not_evaluable"
        elif positive == negative and positive > 0:
            consensus = "not_evaluable"
        elif positive > negative and positive > 0:
            consensus = "positive_assertion"
        elif negative > 0:
            consensus = "explicit_negative"
        else:
            consensus = "unasserted"
        first = rows[0]
        summaries.append(
            {
                **{key: first.get(key, "") for key in COMMON_SIDEcar_FIELDS},
                "task_id": task_id,
                "base_task_id": first.get("base_task_id", ""),
                "dataset_group": first.get("dataset_group", ""),
                "design_group": first.get("design_group", ""),
                "tag_name": tag_name,
                "n_observations": len(rows),
                "n_positive_assertions": positive,
                "n_explicit_negatives": negative,
                "n_unasserted": unasserted,
                "n_not_evaluable": not_eval,
                "n_replicated_conflicts": conflicts,
                "positive_coverage": round(positive / total, 6) if total else 0.0,
                "explicit_negative_coverage": round(negative / total, 6) if total else 0.0,
                "unasserted_rate": round(unasserted / total, 6) if total else 0.0,
                "consensus_three_state": consensus,
                "candidate_status": _candidate_status(first.get("design_group", ""), positive, negative, unasserted, conflicts),
                "routing_eligible": "false",
                "scene_profile_primary": "false",
            }
        )
    return summaries


def build_worker_response_style(observations: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in observations:
        groups[row.get("worker_id", "")].append(row)
    rows = []
    for worker_id, values in sorted(groups.items()):
        positive = sum(row.get("assertion_status") == "positive_assertion" for row in values)
        negative = sum(row.get("assertion_status") == "explicit_negative" for row in values)
        unasserted = sum(row.get("assertion_status") == "unasserted" for row in values)
        not_eval = sum(row.get("assertion_status") == "not_evaluable" for row in values)
        denom = positive + negative + unasserted
        style = "not_evaluable" if not denom else "assertive" if positive / denom >= 0.6 else "negative_explicit" if negative / denom >= 0.6 else "sparse_or_mixed"
        first = values[0]
        rows.append(
            {
                **{key: first.get(key, "") for key in COMMON_SIDEcar_FIELDS},
                "worker_id": worker_id,
                "n_task_tag_observations": len(values),
                "n_positive_assertions": positive,
                "n_explicit_negatives": negative,
                "n_unasserted": unasserted,
                "n_not_evaluable": not_eval,
                "positive_rate": round(positive / denom, 6) if denom else 0.0,
                "explicit_negative_rate": round(negative / denom, 6) if denom else 0.0,
                "unasserted_rate": round(unasserted / denom, 6) if denom else 0.0,
                "response_style_candidate": style,
                "interpretation_allowed": "false",
            }
        )
    return rows


def materialize_meta_label_three_state(
    quality_csv: Path,
    output_dir: Path,
    *,
    input_status: str = "dry_run",
) -> dict[str, Any]:
    import csv

    with quality_csv.open("r", newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    observations = build_tag_observations(rows, source_artifact=str(quality_csv), source_sha256=sha256_file(quality_csv), input_status=input_status)
    summaries = build_three_state_summary(observations)
    styles = build_worker_response_style(observations)
    common = COMMON_SIDEcar_FIELDS
    write_csv_rows(output_dir / "worker_task_tag_observations_C1.csv", observations, common + ["task_id", "base_task_id", "dataset_group", "design_group", "worker_id", "canonical_annotation_id", "tag_name", "tag_value", "assertion_status", "positive_assertion", "explicit_negative", "unasserted", "replicated_conflict"])
    write_csv_rows(output_dir / "task_tag_three_state_summary_C1.csv", summaries, common + ["task_id", "base_task_id", "dataset_group", "design_group", "tag_name", "n_observations", "n_positive_assertions", "n_explicit_negatives", "n_unasserted", "n_not_evaluable", "n_replicated_conflicts", "positive_coverage", "explicit_negative_coverage", "unasserted_rate", "consensus_three_state", "candidate_status", "routing_eligible", "scene_profile_primary"])
    write_csv_rows(output_dir / "worker_response_style_C1.csv", styles, common + ["worker_id", "n_task_tag_observations", "n_positive_assertions", "n_explicit_negatives", "n_unasserted", "n_not_evaluable", "positive_rate", "explicit_negative_rate", "unasserted_rate", "response_style_candidate"])
    return {"n_observations": len(observations), "n_task_tag_summaries": len(summaries), "n_workers": len(styles), "dry_run": input_status != "formal", "interpretation_allowed": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize candidate-only three-state meta-label sidecars.")
    parser.add_argument("--quality-csv", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(materialize_meta_label_three_state(args.quality_csv, args.output_dir), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
