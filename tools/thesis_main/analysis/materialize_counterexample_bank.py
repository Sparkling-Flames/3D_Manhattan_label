"""Candidate-only counterexample bank; no training, prevalence or GT mutation."""

from __future__ import annotations

import csv
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TRIGGERS = {"gt_conflict", "supported_multimodality", "worker_structural_failure", "process_integrity", "blind_trust_or_correction_failure", "undercoverage_or_overextension", "v1_unresolved"}
ADJUDICATIONS = {"confirmed_worker_failure", "confirmed_ambiguity", "reference_or_protocol_issue", "system_or_policy_issue", "not_counterexample", "unresolved"}


def materialize_counterexample_bank(events: list[dict[str, Any]], output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    def read_existing(name: str) -> list[dict[str, str]]:
        path = output_dir / name
        if not path.exists(): return []
        with path.open(encoding="utf-8-sig", newline="") as stream: return list(csv.DictReader(stream))
    existing_adjudicated = {row.get("candidate_id", ""): row for row in read_existing("counterexample_adjudicated.csv")}
    existing_candidates = {row.get("candidate_id", ""): row for row in read_existing("counterexample_candidates.csv")}
    existing_representatives = read_existing("representative_cases_manifest.csv")
    candidates_by_id: dict[str, dict[str, Any]] = {}
    for event in events:
        trigger = str(event.get("trigger", ""))
        if trigger not in TRIGGERS: continue
        identity = {key: str(event.get(key, "")) for key in ("stage", "base_task_id", "canonical_annotation_id", "trigger", "trigger_rule_version")}
        digest = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        candidate_id = f"CE-{digest[:16]}"
        frozen_created_at = event.get("frozen_created_at", "") or existing_candidates.get(candidate_id, {}).get("frozen_created_at", "") or datetime.now(timezone.utc).isoformat()
        candidates_by_id[candidate_id] = {"candidate_id": candidate_id, **identity, "source_artifact": event.get("source_artifact", ""), "source_artifact_sha256": event.get("source_artifact_sha256", ""), "evidence_identity": event.get("evidence_identity", event.get("canonical_annotation_id", "")), "evidence_sha256": event.get("evidence_sha256", ""), "denominator_definition": event.get("denominator_definition", ""), "frozen_created_at": frozen_created_at, "candidate_only": True, "adjudicated_failure": False, "reference_modified": False, "profile_inclusion_allowed": False, "design_selection_allowed": False}
    candidates = [candidates_by_id[key] for key in sorted(candidates_by_id)]
    def write(name: str, rows: list[dict[str, Any]], fields: list[str]) -> None:
        with (output_dir / name).open("w", encoding="utf-8", newline="") as stream: writer=csv.DictWriter(stream, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    fields = list(candidates[0]) if candidates else ["candidate_id", "base_task_id", "canonical_annotation_id", "trigger", "candidate_only", "adjudicated_failure", "reference_modified", "profile_inclusion_allowed", "design_selection_allowed"]
    write("counterexample_candidates.csv", candidates, fields)
    templates = [{**row, "adjudication": existing_adjudicated.get(row["candidate_id"], {}).get("adjudication", ""), "reviewed_by": existing_adjudicated.get(row["candidate_id"], {}).get("reviewed_by", ""), "reviewed_at": existing_adjudicated.get(row["candidate_id"], {}).get("reviewed_at", ""), "notes": existing_adjudicated.get(row["candidate_id"], {}).get("notes", "")} for row in candidates]
    write("counterexample_adjudication_template.csv", templates, list(templates[0]) if templates else fields + ["adjudication", "reviewed_by", "reviewed_at", "notes"])
    preserved_adjudicated = [existing_adjudicated[key] for key in sorted(existing_adjudicated) if key in candidates_by_id]
    adjudicated_fields = list(dict.fromkeys(fields + ["adjudication", "reviewed_by", "reviewed_at", "notes"] + [key for row in preserved_adjudicated for key in row]))
    write("counterexample_adjudicated.csv", preserved_adjudicated, adjudicated_fields)
    representative_fields = list(existing_representatives[0]) if existing_representatives else ["candidate_id", "representative_role", "approved_by", "approved_at"]
    write("representative_cases_manifest.csv", [row for row in existing_representatives if row.get("candidate_id", "") in candidates_by_id], representative_fields)
    summary = {"schema_version": "paper_a_counterexample_bank_v2", "candidate_count": len(candidates), "adjudicated_count": len(preserved_adjudicated), "candidate_is_not_failure": True, "reference_modified": False, "profile_inclusion_allowed": False, "design_selection_allowed": False, "prevalence_estimation_allowed": False}
    (output_dir / "counterexample_bank.summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser=argparse.ArgumentParser(); parser.add_argument("--events-csv",type=Path,required=True); parser.add_argument("--output-dir",type=Path,required=True); args=parser.parse_args()
    with args.events_csv.open(encoding="utf-8-sig",newline="") as stream: events=list(csv.DictReader(stream))
    print(json.dumps(materialize_counterexample_bank(events,args.output_dir),indent=2))


if __name__ == "__main__": main()
