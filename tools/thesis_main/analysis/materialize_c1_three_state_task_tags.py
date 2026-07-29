"""Materialize canonical three-state C1 task-tag observations and aggregates."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

ALLOWED = {"positive", "explicit_negative", "unasserted", "not_evaluable"}
TAG_FAMILIES = {
    "difficulty": ("trivial", ("occlusion", "low_texture", "seam", "reflection", "low_quality")),
    "model_issue": ("acceptable", ("overextend_adjacent", "underextend", "over_parsing", "corner_drift", "corner_duplicate", "topology_failure", "fail")),
}
FORMAL_PROVENANCE = {"original_assignment", "authorized_replacement_assignment", "late_entry_calibration_assignment"}


def _truth(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def build_observation_rows(meta_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in meta_rows:
        try:
            choice_map = json.loads(str(row.get("choice_map_json") or "{}"))
        except json.JSONDecodeError as exc:
            raise ValueError("invalid canonical choice_map_json") from exc
        formal = (
            str(row.get("assignment_provenance", "")) in FORMAL_PROVENANCE
            and not _truth(row.get("outside_assignment_submission"))
            and str(row.get("canonical_eligibility_status", "")) == "valid"
            and _truth(row.get("schema_interpretable"))
        )
        for family, (negative, tags) in TAG_FAMILIES.items():
            selected = {str(value) for value in choice_map.get(family, [])}
            if negative in selected and selected - {negative}:
                raise ValueError(f"conflicting canonical {family} choices")
            for tag in tags:
                state = "not_evaluable" if not formal else "explicit_negative" if negative in selected else "positive" if tag in selected else "unasserted"
                output.append({
                    "base_task_id": str(row.get("base_task_id", "")),
                    "condition": str(row.get("condition", "")),
                    "tag_family": family,
                    "tag_name": tag,
                    "worker_id": str(row.get("worker_id", "")),
                    "canonical_annotation_id": str(row.get("canonical_annotation_id", "")),
                    "assignment_provenance": str(row.get("assignment_provenance", "")),
                    "assertion_state": state,
                })
    return output


def aggregate_three_state_tags(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str, str], dict[str, str]] = defaultdict(dict)
    for row in rows:
        state = str(row.get("assertion_state", ""))
        if state not in ALLOWED:
            raise ValueError(f"unknown assertion_state:{state}")
        worker = str(row.get("worker_id", ""))
        key = (str(row.get("base_task_id", "")), str(row.get("condition", "")), str(row.get("tag_family", "")), str(row.get("tag_name", "")))
        if not worker or not key[0] or not key[2] or not key[3]:
            raise ValueError("three-state tag rows require task, tag and worker identity")
        if worker in groups[key]:
            raise ValueError(f"duplicate/conflicting worker task-tag observation:{key}|{worker}")
        groups[key][worker] = state
    output = []
    for key, worker_states in sorted(groups.items()):
        counts = {state: sum(value == state for value in worker_states.values()) for state in ALLOWED}
        a, e, u = (counts[name] for name in ("positive", "explicit_negative", "unasserted"))
        denominator = a + e + u
        output.append({
            "base_task_id": key[0], "condition": key[1], "tag_family": key[2], "tag_name": key[3],
            "positive_assertion_count": a, "explicit_negative_count": e, "unasserted_count": u,
            "not_evaluable_count": counts["not_evaluable"], "formal_denominator": denominator,
            "positive_assertion_share": a / denominator if denominator else "",
            "explicit_negative_share": e / denominator if denominator else "",
            "unasserted_share": u / denominator if denominator else "",
            "repeated_opposing_claims": a >= 2 and e >= 2,
        })
    return output


def _write(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = list(dict.fromkeys(key for row in rows for key in row)) or ["base_task_id"]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def materialize(meta_csv: Path, output_dir: Path) -> dict[str, Any]:
    observations = build_observation_rows(_read(meta_csv))
    aggregates = aggregate_three_state_tags(observations)
    output_dir.mkdir(parents=True, exist_ok=True)
    observation_path = output_dir / "c1_three_state_task_tag_observations.csv"
    aggregate_path = output_dir / "c1_three_state_task_tag_aggregates.csv"
    _write(observation_path, observations)
    _write(aggregate_path, aggregates)
    summary = {
        "schema_version": "c1_three_state_task_tags_v1",
        "observation_count": len(observations), "task_tag_count": len(aggregates),
        "meta_input_sha256": hashlib.sha256(meta_csv.read_bytes()).hexdigest(),
        "aggregate_sha256": hashlib.sha256(aggregate_path.read_bytes()).hexdigest(),
    }
    (output_dir / "c1_three_state_task_tags.summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--canonical-meta", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(materialize(args.canonical_meta, args.output_dir), indent=2))


if __name__ == "__main__":
    main()
