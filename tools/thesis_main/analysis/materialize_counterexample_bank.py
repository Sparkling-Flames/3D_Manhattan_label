"""Candidate-only counterexample bank; no training, prevalence or GT mutation."""

from __future__ import annotations

import csv
import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

TRIGGERS = {"gt_conflict", "supported_multimodality", "worker_structural_failure", "blind_trust_or_correction_failure", "undercoverage_or_overextension", "v1_unresolved"}
ADJUDICATIONS = {"confirmed_worker_failure", "confirmed_ambiguity", "reference_or_protocol_issue", "system_or_policy_issue", "not_counterexample", "unresolved"}


def materialize_counterexample_bank(events: list[dict[str, Any]], output_dir: Path) -> dict[str, Any]:
    candidates = []
    for index, event in enumerate(events, 1):
        trigger = str(event.get("trigger", ""))
        if trigger not in TRIGGERS: continue
        candidates.append({"candidate_id": f"CE-{index:05d}", "base_task_id": event.get("base_task_id", ""), "canonical_annotation_id": event.get("canonical_annotation_id", ""), "trigger": trigger, "candidate_only": True, "adjudicated_failure": False, "reference_modified": False, "profile_inclusion_allowed": False, "design_selection_allowed": False})
    output_dir.mkdir(parents=True, exist_ok=True)
    def write(name: str, rows: list[dict[str, Any]], fields: list[str]) -> None:
        with (output_dir / name).open("w", encoding="utf-8", newline="") as stream: writer=csv.DictWriter(stream, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    fields = list(candidates[0]) if candidates else ["candidate_id", "base_task_id", "canonical_annotation_id", "trigger", "candidate_only", "adjudicated_failure", "reference_modified", "profile_inclusion_allowed", "design_selection_allowed"]
    write("counterexample_candidates.csv", candidates, fields)
    templates = [{**row, "adjudication": "", "reviewed_by": "", "reviewed_at": "", "notes": ""} for row in candidates]
    write("counterexample_adjudication_template.csv", templates, list(templates[0]) if templates else fields + ["adjudication", "reviewed_by", "reviewed_at", "notes"])
    write("counterexample_adjudicated.csv", [], fields + ["adjudication", "reviewed_by", "reviewed_at", "notes"])
    write("representative_cases_manifest.csv", [], ["candidate_id", "representative_role", "approved_by", "approved_at"])
    summary = {"schema_version": "paper_a_counterexample_bank_v1", "candidate_count": len(candidates), "adjudicated_count": 0, "candidate_is_not_failure": True, "reference_modified": False, "profile_inclusion_allowed": False, "design_selection_allowed": False, "prevalence_estimation_allowed": False}
    (output_dir / "counterexample_bank.summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser=argparse.ArgumentParser(); parser.add_argument("--events-csv",type=Path,required=True); parser.add_argument("--output-dir",type=Path,required=True); args=parser.parse_args()
    with args.events_csv.open(encoding="utf-8-sig",newline="") as stream: events=list(csv.DictReader(stream))
    print(json.dumps(materialize_counterexample_bank(events,args.output_dir),indent=2))


if __name__ == "__main__": main()
