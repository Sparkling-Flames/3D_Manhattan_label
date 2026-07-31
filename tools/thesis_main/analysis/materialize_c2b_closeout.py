"""Bind completed C2-B submissions to the post-C2-B worker profile consumed by C2-A-RP."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from tools.thesis_main.analysis.paper_a_contracts import METHOD_CONTRACT, load_method_contract
from tools.thesis_main.analysis.vfinal_artifact_utils import sha256_file


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _truth(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def materialize(
    submissions_csv: Path,
    post_profile_csv: Path,
    profile_manifest: Path,
    design_summary: Path,
    c1_closeout_summary: Path,
    assignment_csv: Path,
    worker_roster_csv: Path,
    rule_config: Path,
    output_summary: Path,
    *,
    input_status: str = "formal",
) -> dict[str, Any]:
    manifest = json.loads(profile_manifest.read_text(encoding="utf-8"))
    method = load_method_contract()
    method_sha = sha256_file(METHOD_CONTRACT)
    if manifest.get("manifest_version") != "c2b_post_profile_v1":
        raise ValueError("unsupported C2-B post-profile manifest")
    design = json.loads(design_summary.read_text(encoding="utf-8"))
    if not design.get("c2b_design_ready") and input_status == "formal":
        raise ValueError("C2-B design was not ready")

    actual = {
        "c2b_submissions_csv": sha256_file(submissions_csv),
        "post_c2b_worker_profile_csv": sha256_file(post_profile_csv),
        "c2b_design_summary": sha256_file(design_summary),
        "c1_closeout_summary": sha256_file(c1_closeout_summary),
        "c2b_assignment_csv": sha256_file(assignment_csv),
        "worker_roster_csv": sha256_file(worker_roster_csv),
        "rule_config": sha256_file(rule_config),
    }
    declared = {
        **(manifest.get("input_sha256") or {}),
        **(manifest.get("output_sha256") or {}),
    }
    for name, digest in actual.items():
        if declared.get(name) != digest:
            raise ValueError(f"stale_or_unbound:{name}")

    if input_status != "formal":
        summary = {
            "closeout_version": "c2b_closeout_v2", "c2b_design_ready": bool(design.get("c2b_design_ready")),
            "c2b_closeout_ready": False, "candidate_only": True,
            "post_c2b_worker_profile_sha256": actual["post_c2b_worker_profile_csv"],
            "post_c2b_profile_manifest_sha256": sha256_file(profile_manifest),
        }
        output_summary.parent.mkdir(parents=True, exist_ok=True)
        output_summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return summary

    closeout = json.loads(c1_closeout_summary.read_text(encoding="utf-8"))
    if not closeout.get("formal_closeout_ready") or closeout.get("profile_freeze_status") != "C1_frozen":
        raise ValueError("C1 closeout is not formal-ready and frozen")
    if design.get("candidate_only") or not design.get("launch_ready", True):
        raise ValueError("C2-B assignment is not a formal frozen design")
    assignments, submissions, roster, profiles = (_rows(path) for path in (assignment_csv, submissions_csv, worker_roster_csv, post_profile_csv))
    assigned = [(row.get("worker_id", ""), row.get("task_id", "")) for row in assignments]
    submitted = [(row.get("worker_id", ""), row.get("task_id", "")) for row in submissions]
    if not assigned or any(not all(key) for key in assigned) or len(assigned) != len(set(assigned)):
        raise ValueError("C2-B assignment requires unique worker-task rows")
    if any(key not in set(assigned) for key in submitted):
        raise ValueError("C2-B contains unassigned submission")
    if len(submitted) != len(set(submitted)):
        raise ValueError("C2-B duplicate/revision disposition is unresolved")
    missing = set(assigned) - set(submitted)
    if missing:
        raise ValueError("C2-B required submissions are missing")
    roster_ids = {row.get("worker_id", "") for row in roster}
    profile_ids = {row.get("worker_id", "") for row in profiles}
    assignment_ids = {worker for worker, _task in assigned}
    if not roster_ids or "" in roster_ids or roster_ids != assignment_ids or profile_ids != roster_ids:
        raise ValueError("C2-B worker roster/profile coverage mismatch")
    if any(str(row.get("evaluation_status", row.get("status", ""))).lower() == "not_evaluable" for row in profiles):
        raise ValueError("post-C2-B profile contains unresolved not_evaluable")
    rules = json.loads(rule_config.read_text(encoding="utf-8"))
    min_anchor, min_bridge, min_task = (int(rules.get(name, 1)) for name in ("min_common_anchor_per_worker", "min_bridge_per_worker", "min_task_support"))
    by_worker = {worker: {"common_anchor": 0, "diverse_bridge": 0} for worker in roster_ids}
    task_support: dict[str, int] = {}
    for row in assignments:
        component = row.get("c2_component", "")
        if component not in {"common_anchor", "diverse_bridge"}:
            raise ValueError("C2-B assignment has invalid component")
        by_worker[row["worker_id"]][component] += 1
        task_support[row["task_id"]] = task_support.get(row["task_id"], 0) + 1
    if any(counts["common_anchor"] < min_anchor or counts["diverse_bridge"] < min_bridge for counts in by_worker.values()):
        raise ValueError("C2-B worker anchor/bridge support is below threshold")
    if min(task_support.values(), default=0) < min_task:
        raise ValueError("C2-B task support is below threshold")

    batch_id = "C2B_BATCH_B" if any(row.get("assignment_batch_id") == "C2B_BATCH_B" or row.get("assignment_batch") == "C2B_BATCH_B" for row in assignments) else "C2B_BATCH_A"
    summary = {
        "schema_version": "c2b_closeout_v2",
        "artifact_role": f"{batch_id}_CLOSEOUT_FROZEN",
        "contract_role": "generated_subordinate",
        "method_contract_version": method["contract_version"],
        "method_contract_sha256": method_sha,
        "profile_version": manifest.get("profile_version", ""),
        "cohort_id": manifest.get("cohort_id", ""),
        "closeout_version": "c2b_closeout_v2",
        "c2b_design_ready": True,
        "c2b_closeout_ready": True,
        "candidate_only": False,
        "design_manifest_sha256": design.get("design_manifest_sha256"),
        "c2b_design_summary_path": str(design_summary),
        "c2b_design_summary_sha256": actual["c2b_design_summary"],
        "c1_closeout_sha256": actual["c1_closeout_summary"],
        "c2b_assignment_sha256": actual["c2b_assignment_csv"],
        "worker_roster_sha256": actual["worker_roster_csv"],
        "rule_config_sha256": actual["rule_config"],
        "c2b_submissions_path": str(submissions_csv),
        "c2b_submissions_sha256": actual["c2b_submissions_csv"],
        "post_c2b_worker_profile_path": str(post_profile_csv),
        "post_c2b_worker_profile_sha256": actual["post_c2b_worker_profile_csv"],
        "post_c2b_profile_manifest_path": str(profile_manifest),
        "post_c2b_profile_manifest_sha256": sha256_file(profile_manifest),
    }
    output_summary.parent.mkdir(parents=True, exist_ok=True)
    output_summary.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize the formal C2-B closeout SHA chain.")
    parser.add_argument("--submissions-csv", type=Path, required=True)
    parser.add_argument("--post-profile-csv", type=Path, required=True)
    parser.add_argument("--profile-manifest", type=Path, required=True)
    parser.add_argument("--design-summary", type=Path, required=True)
    parser.add_argument("--c1-closeout-summary", type=Path, required=True)
    parser.add_argument("--assignment-csv", type=Path, required=True)
    parser.add_argument("--worker-roster-csv", type=Path, required=True)
    parser.add_argument("--rule-config", type=Path, required=True)
    parser.add_argument("--output-summary", type=Path, required=True)
    parser.add_argument("--input-status", choices=("dry_run", "precloseout_rehearsal", "formal"), default="formal")
    args = parser.parse_args(argv)
    print(json.dumps(materialize(
        args.submissions_csv, args.post_profile_csv, args.profile_manifest,
        args.design_summary, args.c1_closeout_summary, args.assignment_csv,
        args.worker_roster_csv, args.rule_config, args.output_summary, input_status=args.input_status,
    ), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
