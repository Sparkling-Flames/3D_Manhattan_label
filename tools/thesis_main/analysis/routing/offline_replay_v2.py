from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Iterable

from tools.thesis_main.analysis.routing.crossfit import build_crossfit_folds
from tools.thesis_main.analysis.routing.sequential_rule import candidate_rule_config, decide_candidate_action
from tools.thesis_main.analysis.vfinal_artifact_utils import COMMON_SIDEcar_FIELDS, sha256_file, sidecar_common, write_csv_rows


RULE_VERSION = "routing_replay_scaffold_v1"


def routing_replay_scaffold(
    snapshot_rows: Iterable[dict[str, Any]],
    *,
    risk_bucket: str = "low_risk",
    n_folds: int = 2,
    input_status: str = "dry_run",
) -> list[dict[str, Any]]:
    config = candidate_rule_config(risk_bucket)
    rows = []
    for row in build_crossfit_folds(snapshot_rows, n_folds=n_folds):
        decision = decide_candidate_action(row, config)
        rows.append(
            {
                **sidecar_common(source_artifact=str(row.get("source_artifact", "")), source_sha256=str(row.get("source_sha256", "")), stage=str(row.get("stage", "C1")), pool=str(row.get("pool", "")), condition=str(row.get("condition", "")), validity_status="dry_run" if input_status != "formal" else "candidate_only", rule_version=RULE_VERSION),
                "task_id": row.get("task_id", ""), "base_task_id": row.get("base_task_id", ""),
                "snapshot_id": row.get("snapshot_id", ""),
                "crossfit_fold": row.get("crossfit_fold", ""),
                "risk_bucket": risk_bucket,
                **decision,
                "artifact_role": "static_evidence_scaffold",
                "temporal_replay": "false",
                "formal_assignment_generated": "false",
            }
        )
    return rows


def offline_replay_v2(snapshot_csv: Path, output_csv: Path, *, risk_bucket: str = "low_risk", input_status: str = "dry_run") -> dict[str, Any]:
    """Deprecated compatibility wrapper; this is not a temporal replay."""
    with snapshot_csv.open("r", newline="", encoding="utf-8-sig") as handle:
        snapshot_rows = list(csv.DictReader(handle))
    rows = routing_replay_scaffold(snapshot_rows, risk_bucket=risk_bucket, input_status=input_status)
    write_csv_rows(output_csv, rows, COMMON_SIDEcar_FIELDS + ["task_id", "base_task_id", "snapshot_id", "crossfit_fold", "crossfit_group_key", "risk_bucket", "action", "observed_k", "k_dispatch_initial", "k_min_for_stop", "standard_cap", "escalation_cap", "candidate_only", "routing_eligible", "artifact_role", "temporal_replay", "formal_assignment_generated"])
    return {"n_snapshots": len(rows), "artifact_role": "static_evidence_scaffold", "temporal_replay": False, "deprecated_name": "offline_replay_v2", "risk_bucket": risk_bucket, "dry_run": input_status != "formal", "formal_assignment_generated": False, "routing_eligible": False}


# Compatibility for callers that imported the old function directly.
replay_sequential_routing = routing_replay_scaffold


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Replay sequential routing v2 offline; never materialize assignment.")
    parser.add_argument("--snapshot-csv", required=True, type=Path)
    parser.add_argument("--output-csv", required=True, type=Path)
    parser.add_argument("--risk-bucket", default="low_risk")
    args = parser.parse_args(argv)
    print(json.dumps(offline_replay_v2(args.snapshot_csv, args.output_csv, risk_bucket=args.risk_bucket), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
