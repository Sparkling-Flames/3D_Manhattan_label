from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from tools.thesis_main.analysis.vfinal_artifact_utils import COMMON_SIDEcar_FIELDS, sha256_file, sidecar_common, write_csv_rows


RULE_VERSION = "meta_label_three_state_v2"
DIFFICULTY_TAGS = ("occlusion", "low_texture", "seam", "reflection", "low_quality")
MODEL_ISSUE_TAGS = ("overextend_adjacent", "underextend", "over_parsing", "corner_drift", "corner_duplicate", "topology_failure", "fail")


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _tokens(value: Any) -> set[str]:
    text = _text(value)
    if not text:
        return set()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        value = text.replace(",", ";").split(";")
    return {str(item).strip().lower() for item in (value if isinstance(value, list) else [value]) if str(item).strip()}


def _na_reason(row: dict[str, Any]) -> str:
    if _text(row.get("canonical_eligibility_status")).lower() not in {"", "valid", "eligible"}:
        reason = _text(row.get("canonical_eligibility_reason")).lower()
        return "n_nonindependent_excluded" if "independent" in reason else "n_invalid"
    if _text(row.get("parse_error")) or _text(row.get("schema_error")) or _text(row.get("schema_interpretable")).lower() == "false":
        return "n_schema_uninterpretable"
    if _text(row.get("assigned_expected")).lower() == "false" or _text(row.get("outside_assignment_submission")).lower() == "true":
        return "n_nonindependent_excluded"
    return ""


def _field_present(row: dict[str, Any], field: str) -> bool:
    marker = _text(row.get(f"{field}_present"))
    return marker.lower() != "false"  # legacy flat CSV has no marker; retain its explicit blank as 0.


def _assertion(row: dict[str, Any], field: str, tag: str) -> tuple[str, str]:
    reason = _na_reason(row)
    if reason:
        return "NA", reason
    if not _field_present(row, field):
        return "NA", "n_missing"
    selected = _tokens(row.get(field))
    allowed = set(DIFFICULTY_TAGS if field == "difficulty" else MODEL_ISSUE_TAGS)
    negative = "trivial" if field == "difficulty" else "acceptable"
    if selected - allowed - {negative}:
        return "NA", "n_schema_uninterpretable"
    if negative in selected and len(selected) > 1:
        return "NA", "n_schema_uninterpretable"
    if tag in selected:
        return "+", ""
    if negative in selected:
        return "-", ""
    return "0", ""


def _state(a: int, e: int, u: int) -> str:
    if a >= 2 and e >= 2:
        return "replicated_explicit_conflict"
    if a >= 3 and e <= 1:
        return "high_replication_positive"
    if a >= 2:
        return "convergent_positive"
    if a == 1:
        return "isolated_positive"
    if e >= 3 and a <= 1:
        return "high_replication_negative"
    if e >= 2:
        return "replicated_negative"
    if e == 1:
        return "isolated_negative"
    return "none_observed"


def build_tag_observations(rows: Iterable[dict[str, Any]], *, source_artifact: str, source_sha256: str, input_status: str = "dry_run") -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    for row in rows:
        for field, tags in (("difficulty", DIFFICULTY_TAGS), ("model_issue", MODEL_ISSUE_TAGS)):
            for tag in tags:
                symbol, reason = _assertion(row, field, tag)
                observations.append({
                    **sidecar_common(source_artifact=source_artifact, source_sha256=source_sha256, stage="C1", pool=_text(row.get("dataset_group")), condition=_text(row.get("condition")), validity_status="dry_run" if input_status != "formal" else ("valid" if symbol != "NA" else "not_evaluable"), rule_version=RULE_VERSION),
                    "task_id": _text(row.get("task_id")), "base_task_id": _text(row.get("base_task_id")), "scene_id": _text(row.get("scene_id") or row.get("scene_label")),
                    "dataset_group": _text(row.get("dataset_group")), "worker_id": _text(row.get("worker_id") or row.get("annotator_id")),
                    "canonical_annotation_id": _text(row.get("canonical_annotation_id")), "tag_family": field, "tag_name": tag,
                    "assertion": symbol, "assertion_status": {"+": "positive_assertion", "-": "explicit_negative", "0": "unasserted", "NA": "not_evaluable"}[symbol],
                    "na_reason": reason, "positive_assertion": str(symbol == "+").lower(), "explicit_negative": str(symbol == "-").lower(),
                    "unasserted": str(symbol == "0").lower(), "replicated_conflict": "false",
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
        na = {name: sum(row["na_reason"] == name for row in rows) for name in ("n_missing", "n_invalid", "n_nonindependent_excluded", "n_schema_uninterpretable")}
        conflict = a >= 2 and e >= 2
        first = rows[0]
        summaries.append({
            **{key: first.get(key, "") for key in COMMON_SIDEcar_FIELDS},
            "task_id": first["task_id"], "base_task_id": first["base_task_id"], "scene_id": first["scene_id"], "dataset_group": first["dataset_group"],
            "tag_family": first["tag_family"], "tag_name": first["tag_name"], "a": a, "e": e, "u": u, "k": a + e + u,
            **na, "coverage": round((a + e) / (a + e + u), 6) if a + e + u else 0.0,
            "explicit_balance": round((a - e) / (a + e), 6) if a + e else 0.0,
            "task_tag_state": _state(a, e, u), "replicated_explicit_conflict": str(conflict).lower(),
            "descriptive": str(a >= 1).lower(), "broad": str(a >= 2 and e < 2).lower(), "strict": str(a >= 3 and e <= 1).lower(),
            "routing_eligible": "false", "scene_profile_primary": "false",
        })
    return summaries


def materialize_meta_label_three_state(quality_csv: Path, output_dir: Path, *, input_status: str = "dry_run") -> dict[str, Any]:
    with quality_csv.open("r", newline="", encoding="utf-8-sig") as handle:
        observations = build_tag_observations(csv.DictReader(handle), source_artifact=str(quality_csv), source_sha256=sha256_file(quality_csv), input_status=input_status)
    summaries = build_three_state_summary(observations)
    fields = COMMON_SIDEcar_FIELDS
    write_csv_rows(output_dir / "worker_task_tag_observations_C1.csv", observations, fields + ["task_id", "base_task_id", "scene_id", "dataset_group", "worker_id", "canonical_annotation_id", "tag_family", "tag_name", "assertion", "assertion_status", "na_reason", "positive_assertion", "explicit_negative", "unasserted", "replicated_conflict"])
    write_csv_rows(output_dir / "task_tag_three_state_summary_C1.csv", summaries, fields + ["task_id", "base_task_id", "scene_id", "dataset_group", "tag_family", "tag_name", "a", "e", "u", "k", "n_missing", "n_invalid", "n_nonindependent_excluded", "n_schema_uninterpretable", "coverage", "explicit_balance", "task_tag_state", "replicated_explicit_conflict", "descriptive", "broad", "strict", "routing_eligible", "scene_profile_primary"])
    return {"n_observations": len(observations), "n_task_tag_summaries": len(summaries), "dry_run": input_status != "formal", "interpretation_allowed": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize concrete-tag C1 three-state sidecars.")
    parser.add_argument("--quality-csv", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(materialize_meta_label_three_state(args.quality_csv, args.output_dir), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
