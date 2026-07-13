from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from tools.thesis_main.analysis.vfinal_artifact_utils import COMMON_SIDEcar_FIELDS, sha256_file, sidecar_common, write_csv_rows


RULE_VERSION = "meta_label_three_state_v3"
DIFFICULTY_TAGS = ("occlusion", "low_texture", "seam", "reflection", "low_quality")
MODEL_ISSUE_TAGS = ("overextend_adjacent", "underextend", "over_parsing", "corner_drift", "corner_duplicate", "topology_failure", "fail")
NA_BUCKETS = ("n_missing", "n_invalid", "n_nonindependent_excluded", "n_schema_uninterpretable")


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _tokens(value: Any) -> set[str]:
    text = _text(value)
    if not text:
        return set()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = text.replace(",", ";").split(";")
    return {str(item).strip().lower() for item in (parsed if isinstance(parsed, list) else [parsed]) if str(item).strip()}


def _na_reason(row: dict[str, Any]) -> str:
    if "canonical_eligibility_status" in row and _text(row.get("canonical_eligibility_status")).lower() not in {"valid", "eligible"}:
        reason = _text(row.get("canonical_eligibility_reason") or row.get("exclusion_reason")).lower()
        return "n_nonindependent_excluded" if "non_independent_confirmed" in reason else "n_invalid"
    if _text(row.get("parse_error")) or _text(row.get("schema_error")) or _text(row.get("schema_interpretable")).lower() == "false":
        return "n_schema_uninterpretable"
    if _text(row.get("assigned_expected")).lower() == "false" or _text(row.get("outside_assignment_submission")).lower() == "true":
        return "n_nonindependent_excluded"
    return ""


def _field_present(row: dict[str, Any], field: str) -> bool:
    marker = _text(row.get(f"{field}_present"))
    return marker.lower() != "false"


def _assertion(row: dict[str, Any], field: str, tag: str) -> tuple[str, str]:
    reason = _na_reason(row)
    if reason:
        return "NA", reason
    if not _field_present(row, field):
        return "NA", "n_missing"
    if field == "model_issue" and _text(row.get("assertion_source")) in {"legacy_behavior_inferred", "not_evaluable"} and _text(row.get("harmonization_validity_status")) != "valid_behavior_inferred":
        return "NA", "n_invalid"
    selected = _tokens(row.get(field))
    allowed = set(DIFFICULTY_TAGS if field == "difficulty" else MODEL_ISSUE_TAGS)
    negative = "trivial" if field == "difficulty" else "acceptable"
    if selected - allowed - {negative} or negative in selected and len(selected) > 1:
        return "NA", "n_schema_uninterpretable"
    if tag in selected:
        return "+", ""
    if negative in selected:
        return "-", ""
    return "0", ""


def _replication_state(count: int) -> str:
    return "high_replication" if count >= 4 else "convergent" if count == 3 else "replicated" if count == 2 else "isolated" if count == 1 else "none"


def _state(a: int, e: int) -> str:
    if a >= 2 and e >= 2:
        return "replicated_explicit_conflict"
    if a:
        return {1: "isolated_positive", 2: "replicated_positive", 3: "convergent_positive"}.get(a, "high_replication_positive")
    if e:
        return {1: "isolated_negative", 2: "replicated_negative", 3: "convergent_negative"}.get(e, "high_replication_negative")
    return "none_observed"


def build_tag_observations(rows: Iterable[dict[str, Any]], *, source_artifact: str, source_sha256: str, input_status: str = "dry_run") -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    for row in rows:
        for family, tags in (("difficulty", DIFFICULTY_TAGS), ("model_issue", MODEL_ISSUE_TAGS)):
            for tag in tags:
                symbol, reason = _assertion(row, family, tag)
                observations.append({
                    **sidecar_common(source_artifact=source_artifact, source_sha256=source_sha256, stage="C1", pool=_text(row.get("dataset_group")), condition=_text(row.get("condition")), validity_status="dry_run" if input_status != "formal" else ("valid" if symbol != "NA" else "not_evaluable"), rule_version=RULE_VERSION),
                    "task_id": _text(row.get("task_id")), "base_task_id": _text(row.get("base_task_id")), "scene_id": _text(row.get("scene_id") or row.get("scene_label")), "dataset_group": _text(row.get("dataset_group")), "worker_id": _text(row.get("worker_id") or row.get("annotator_id")), "canonical_annotation_id": _text(row.get("canonical_annotation_id")), "tag_family": family, "tag_name": tag,
                    "raw_response": _text(row.get("raw_response") or row.get("raw_result_json") or row.get("choice_map_json")), "harmonized_state": _text(row.get("harmonized_state")), "assertion_source": _text(row.get("assertion_source")), "provenance_status": _text(row.get("provenance_status")), "prediction_selection_status": _text(row.get("prediction_selection_status")), "ui_schema_version": _text(row.get("ui_schema_version") or row.get("schema_version")), "model_artifact_id": _text(row.get("model_artifact_id")), "exclusion_reason": reason or _text(row.get("canonical_eligibility_reason")), "independence_status": _text(row.get("independence_status")), "assertion": symbol, "assertion_status": {"+": "positive_assertion", "-": "explicit_negative", "0": "unasserted", "NA": "not_evaluable"}[symbol], "na_reason": reason, "positive_assertion": str(symbol == "+").lower(), "explicit_negative": str(symbol == "-").lower(), "unasserted": str(symbol == "0").lower(), "replicated_conflict": "false",
                })
    return observations


def build_three_state_summary(observations: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in observations:
        groups[(row["task_id"], row["tag_family"], row["tag_name"])].append(row)
    summaries = []
    for (_task_id, _family, _tag), rows in sorted(groups.items()):
        a = sum(row["assertion"] == "+" for row in rows)
        e = sum(row["assertion"] == "-" for row in rows)
        u = sum(row["assertion"] == "0" for row in rows)
        k = a + e + u
        conflict = a >= 2 and e >= 2
        first = rows[0]
        summaries.append({
            **{key: first.get(key, "") for key in COMMON_SIDEcar_FIELDS}, "task_id": first["task_id"], "base_task_id": first["base_task_id"], "scene_id": first["scene_id"], "dataset_group": first["dataset_group"], "tag_family": first["tag_family"], "tag_name": first["tag_name"], "a": a, "e": e, "u": u, "k": k,
            "canonical_annotation_ids_json": json.dumps(sorted({row.get("canonical_annotation_id", "") for row in rows if row.get("canonical_annotation_id", "")}), ensure_ascii=False), "raw_responses_json": json.dumps([row.get("raw_response", "") for row in rows], ensure_ascii=False), "assertion_sources_json": json.dumps(sorted({row.get("assertion_source", "") for row in rows if row.get("assertion_source", "")}), ensure_ascii=False), "ui_schema_versions_json": json.dumps(sorted({row.get("ui_schema_version", "") for row in rows if row.get("ui_schema_version", "")}), ensure_ascii=False), "model_artifact_ids_json": json.dumps(sorted({row.get("model_artifact_id", "") for row in rows if row.get("model_artifact_id", "")}), ensure_ascii=False), "exclusion_reasons_json": json.dumps(sorted({row.get("exclusion_reason", "") for row in rows if row.get("exclusion_reason", "")}), ensure_ascii=False),
            **{name: sum(row["na_reason"] == name for row in rows) for name in NA_BUCKETS}, "coverage": round((a + e) / k, 6) if k else 0.0, "positive_coverage": round(a / k, 6) if k else 0.0, "explicit_negative_coverage": round(e / k, 6) if k else 0.0, "unasserted_rate": round(u / k, 6) if k else 0.0, "explicit_balance": round(a / (a + e), 6) if a + e else 0.0,
            "positive_replication_state": _replication_state(a), "explicit_negative_replication_state": _replication_state(e), "explicit_conflict_state": "replicated_conflict" if conflict else "none", "task_tag_state": _state(a, e), "replicated_explicit_conflict": str(conflict).lower(), "loo_positive_nonempty": str(a >= 2).lower(), "loo_positive_replicated": str(a >= 3).lower(), "coverage_design_group": first.get("dataset_group", ""), "profile_rule_id": RULE_VERSION, "descriptive": str(a >= 1).lower(), "broad": str(a >= 2 and e < 2).lower(), "strict": str(a >= 3 and e <= 1).lower(), "routing_eligible": "false", "scene_profile_primary": "false",
        })
    return summaries


def build_response_style_diagnostics(rows: Iterable[dict[str, Any]], *, source_artifact: str, source_sha256: str) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        worker = _text(row.get("worker_id") or row.get("annotator_id"))
        if worker:
            for family in ("difficulty", "model_issue"):
                groups[(worker, family)].append(row)
    output = []
    for (worker, family), values in sorted(groups.items()):
        specific = set(DIFFICULTY_TAGS if family == "difficulty" else MODEL_ISSUE_TAGS)
        negative = "trivial" if family == "difficulty" else "acceptable"
        counts, combinations = [], defaultdict(int)
        for row in values:
            selected = _tokens(row.get(family))
            chosen = sorted(selected & specific)
            counts.append(len(chosen))
            combinations[";".join(chosen) if chosen else negative if negative in selected else "none"] += 1
        n_specific = sum(count > 0 for count in counts)
        output.append({**sidecar_common(source_artifact=source_artifact, source_sha256=source_sha256, stage="C1", validity_status="dry_run", rule_version=RULE_VERSION, interpretation_allowed=False), "worker_id": worker, "label_family": family, "n_responses": len(values), "trivial_rate": round(sum("trivial" in _tokens(row.get(family)) for row in values) / len(values), 6) if values else 0.0, "acceptable_rate": round(sum("acceptable" in _tokens(row.get(family)) for row in values) / len(values), 6) if values else 0.0, "any_specific_label_rate": round(n_specific / len(values), 6) if values else 0.0, "multi_select_rate_given_specific": round(sum(count > 1 for count in counts) / n_specific, 6) if n_specific else 0.0, "mean_specific_label_count": round(sum(counts) / len(values), 6) if values else 0.0, "frequent_label_combinations": json.dumps(dict(sorted(combinations.items())), ensure_ascii=False), "routing_eligible": "false"})
    return output


def materialize_meta_label_three_state(quality_csv: Path, output_dir: Path, *, input_status: str = "dry_run") -> dict[str, Any]:
    with quality_csv.open("r", newline="", encoding="utf-8-sig") as handle:
        quality_rows = list(csv.DictReader(handle))
    observations = build_tag_observations(quality_rows, source_artifact=str(quality_csv), source_sha256=sha256_file(quality_csv), input_status=input_status)
    summaries = build_three_state_summary(observations)
    response_style = build_response_style_diagnostics(quality_rows, source_artifact=str(quality_csv), source_sha256=sha256_file(quality_csv))
    fields = COMMON_SIDEcar_FIELDS
    write_csv_rows(output_dir / "worker_task_tag_observations_C1.csv", observations, fields + ["task_id", "base_task_id", "scene_id", "dataset_group", "worker_id", "canonical_annotation_id", "tag_family", "tag_name", "raw_response", "harmonized_state", "assertion_source", "provenance_status", "prediction_selection_status", "ui_schema_version", "model_artifact_id", "exclusion_reason", "independence_status", "assertion", "assertion_status", "na_reason", "positive_assertion", "explicit_negative", "unasserted", "replicated_conflict"])
    write_csv_rows(output_dir / "task_tag_three_state_summary_C1.csv", summaries, fields + ["task_id", "base_task_id", "scene_id", "dataset_group", "tag_family", "tag_name", "a", "e", "u", "k", "canonical_annotation_ids_json", "raw_responses_json", "assertion_sources_json", "ui_schema_versions_json", "model_artifact_ids_json", "exclusion_reasons_json", "n_missing", "n_invalid", "n_nonindependent_excluded", "n_schema_uninterpretable", "coverage", "positive_coverage", "explicit_negative_coverage", "unasserted_rate", "explicit_balance", "positive_replication_state", "explicit_negative_replication_state", "explicit_conflict_state", "task_tag_state", "replicated_explicit_conflict", "loo_positive_nonempty", "loo_positive_replicated", "coverage_design_group", "profile_rule_id", "descriptive", "broad", "strict", "routing_eligible", "scene_profile_primary"])
    write_csv_rows(output_dir / "worker_response_style_C1.csv", response_style, fields + ["worker_id", "label_family", "n_responses", "trivial_rate", "acceptable_rate", "any_specific_label_rate", "multi_select_rate_given_specific", "mean_specific_label_count", "frequent_label_combinations", "routing_eligible"])
    return {"n_observations": len(observations), "n_task_tag_summaries": len(summaries), "n_response_style_rows": len(response_style), "dry_run": input_status != "formal", "interpretation_allowed": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize concrete-tag C1 three-state sidecars.")
    parser.add_argument("--quality-csv", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(materialize_meta_label_three_state(args.quality_csv, args.output_dir), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
