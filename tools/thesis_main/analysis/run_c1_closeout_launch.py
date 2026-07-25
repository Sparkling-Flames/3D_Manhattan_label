"""Two-day fail-closed C1 closeout and C2-B launch orchestration."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.thesis_main.analysis import build_c2_assignment_manifest_from_c1_gaps as c2b
from tools.thesis_main.analysis.active_log_utils import freeze_active_log_snapshot, validate_active_log_freeze_manifest
from tools.thesis_main.analysis.run_c1_precloseout_rehearsal import _aggregate_sha, _manifest_rows, materialize as materialize_c1
from tools.thesis_main.analysis.materialize_c2b_task_eligibility import materialize as materialize_c2b_task_eligibility
from tools.thesis_main.analysis.materialize_c2_task_risk import materialize_formal as materialize_task_risk
from tools.thesis_main.analysis.c1_c2_mainline import formal_git_state
from tools.thesis_main.analysis.c1_c2_mainline import materialize_c2b_design_worker_profile
from tools.thesis_main.analysis.materialize_c1_c2_design_parameters import materialize as materialize_design_parameters
from tools.thesis_main.analysis.vfinal_artifact_utils import sha256_file


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _write(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = list(dict.fromkeys(key for row in rows for key in row)) if rows else ["status"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore"); writer.writeheader(); writer.writerows(rows)


def _source_identity_aggregate(rows: list[dict[str, Any]]) -> str:
    """Hash source identity only; raw-snapshot bookkeeping must not change it."""
    return _aggregate_sha([{name: row[name] for name in ("path", "size", "sha256")} for row in rows])


def _require_approval(path: Path, evidence: Path, sha_field: str) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("approved") is not True or payload.get(sha_field) != sha256_file(evidence):
        raise ValueError(f"approval_invalid_or_stale:{sha_field}")
    return payload


def _c2_source_images(rows: list[dict[str, str]]) -> set[str]:
    return {
        row.get("image_id", "") for row in rows
        if str(row.get("allocation", row.get("source_split_allowed", ""))).lower() in {"c2", "true", "1", "allowed"}
        and row.get("image_id")
    }


def _future_heldout_images(rows: list[dict[str, str]]) -> set[str]:
    return {
        row.get("image_id", "") for row in rows
        if row.get("image_id") and (
            str(row.get("allocation", "")).lower() in {"future_holdout", "t1", "v1", "holdout"}
            or str(row.get("future_holdout_clear", row.get("clear", ""))).lower() in {"false", "0", "held", "holdout", "blocked"}
        )
    }


def rehearse_c1(args: argparse.Namespace) -> dict[str, Any]:
    summary = materialize_c1(
        args.export_dir, args.active_log, args.manual_assignment, args.semi_assignment,
        args.worker_distribution, args.gt_export, args.p1_closeout_dir, args.output_root,
        input_status="precloseout_rehearsal",
        c1_preannotation_feature_csv=getattr(args, "c1_preannotation_feature_csv", None),
    )
    return {"stage": "C1", "phase": "rehearsal", "output_dir": summary["output_dir"], "formal_closeout_ready": False, "review_required": True}


def freeze_c1(args: argparse.Namespace) -> dict[str, Any]:
    active = freeze_active_log_snapshot(
        args.source_live_root, args.frozen_root, args.collection_cutoff_server_time,
        args.operator, args.active_log_freeze_manifest,
    )
    closure_args = argparse.Namespace(
        export_dir=args.export_dir,
        manual_assignment=args.manual_assignment,
        semi_assignment=args.semi_assignment,
        c1_active_log_freeze_manifest=args.active_log_freeze_manifest,
        closure_time=args.collection_cutoff_server_time,
        operator=args.operator,
        late_submission_policy=args.late_submission_policy,
        output=args.collection_closure_manifest,
    )
    closure = build_collection_closure(closure_args)
    return {"stage": "C1", "phase": "freeze", "active_log": active, "collection_closure": closure}


def build_collection_closure(args: argparse.Namespace) -> dict[str, Any]:
    freeze_payload = json.loads(args.c1_active_log_freeze_manifest.read_text(encoding="utf-8"))
    frozen_root = Path(str(freeze_payload.get("frozen_root", "")))
    validate_active_log_freeze_manifest(args.c1_active_log_freeze_manifest, frozen_root)
    cutoff = datetime.fromisoformat(str(freeze_payload.get("collection_cutoff_server_time", "")).replace("Z", "+00:00"))
    closure = datetime.fromisoformat(str(args.closure_time).replace("Z", "+00:00"))
    cutoff = cutoff if cutoff.tzinfo else cutoff.replace(tzinfo=timezone.utc)
    closure = closure if closure.tzinfo else closure.replace(tzinfo=timezone.utc)
    if cutoff.astimezone(timezone.utc) != closure.astimezone(timezone.utc):
        raise ValueError("closure_time must equal the active-log collection cutoff")
    export_files = [path for directory in args.export_dir for path in directory.rglob("*.json")]
    assignment_files = [args.manual_assignment, args.semi_assignment]
    payload = {
        "schema_version": "paper_a_c1_collection_closure_v1",
        "c1_export_aggregate_sha256": _aggregate_sha(_manifest_rows(export_files)),
        "c1_active_log_freeze_manifest_sha256": sha256_file(args.c1_active_log_freeze_manifest),
        "c1_assignment_sha256": _aggregate_sha(_manifest_rows(assignment_files)),
        "collection_window_closed": True, "closure_time": args.closure_time,
        "operator": args.operator, "late_submission_policy": args.late_submission_policy,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def audit_c1(args: argparse.Namespace) -> dict[str, Any]:
    validate_active_log_freeze_manifest(args.c1_active_log_freeze_manifest, args.active_log)
    summary = materialize_c1(
        args.export_dir, args.active_log, args.manual_assignment, args.semi_assignment,
        args.worker_distribution, args.gt_export, args.p1_closeout_dir, args.output_root,
        input_status="formal", independence_disposition=args.independence_disposition,
        project_independence_disposition=args.project_independence_disposition,
        structural_disposition=args.structural_disposition,
        duplicate_adjudication=args.duplicate_adjudication,
        scope_adjudication=args.scope_adjudication,
        reference_amendment=args.reference_amendment,
        outside_assignment_disposition=args.outside_assignment_disposition,
        completion_disposition=args.completion_disposition,
        c1_preannotation_feature_csv=getattr(args, "c1_preannotation_feature_csv", None),
        c1_active_log_freeze_manifest=args.c1_active_log_freeze_manifest,
        collection_closure_manifest=args.collection_closure_manifest,
    )
    return {
        "stage": "C1", "phase": "audit", "output_dir": summary["output_dir"],
        "formal_closeout_ready": bool(summary["formal_closeout_ready"]), "blockers": summary["blockers"],
    }


def finalize_c1(args: argparse.Namespace) -> dict[str, Any]:
    audit_path = args.output_dir / "formal_audit_summary.json"
    final_path = args.output_dir / "c1_final_canonical_closeout_summary.json"
    measurement_path = args.output_dir / "c1_measurement_freeze_manifest.json"
    if not all(path.exists() for path in (audit_path, final_path, measurement_path)):
        raise ValueError("finalize-c1 requires a complete formal audit bundle")
    audit, final, measurement = (json.loads(path.read_text(encoding="utf-8")) for path in (audit_path, final_path, measurement_path))
    adjudication = json.loads(args.adjudication_manifest.read_text(encoding="utf-8"))
    bundle_sha = audit.get("full_dependency_bundle_sha256", "")
    approved = adjudication.get("approved") is True and adjudication.get("input_bundle_sha256") == bundle_sha
    canonical_ready = bool(audit.get("C1_CANONICAL_CLOSED")) and bool(final.get("C1_CANONICAL_CLOSED", True))
    blockers = []
    if audit.get("input_status") != "formal": blockers.append("rehearsal_bundle_refused")
    if audit.get("method_contract") != "Pilot->P1->C1->C2-B->C2-A-RP->T1->V1" or not audit.get("git_commit_sha") or not audit.get("worktree_clean"):
        blockers.append("formal_method_contract_or_clean_commit_missing")
    if not canonical_ready: blockers.extend(final.get("canonical_blockers", []) or ["c1_canonical_not_closed"])
    if not measurement.get("C1_MEASUREMENT_FROZEN"): blockers.append("c1_measurement_not_frozen")
    if audit.get("collection_closure", {}).get("status") != "validated": blockers.append("collection_closure_missing_or_invalid")
    if audit.get("formal_closeout_ready") is not True or final.get("formal_closeout_ready") is not True or audit.get("blockers") or final.get("blockers"):
        blockers.append("formal_audit_or_closeout_blocked")
    if not approved: blockers.append("formal_closeout_adjudication_missing_invalid_or_stale")
    measurement_ready = canonical_ready and not blockers
    freeze = {"schema_version": "c1_measurement_freeze_envelope_v1", "method_contract": audit.get("method_contract", ""), "git_commit_sha": audit.get("git_commit_sha", ""), "C1_COLLECTION_INCOMPLETE": not measurement_ready, "C1_CANONICAL_CLOSED": canonical_ready, "C1_MEASUREMENT_FROZEN": measurement_ready, "C2B_DESIGN_READY": bool(measurement.get("C2B_DESIGN_READY")) and measurement_ready, "C2B_RISK_DESIGN_FROZEN": False, "C2B_DESIGN_FROZEN": False, "C2B_ASSIGNMENT_MATERIALIZED": False, "C2B_LAUNCH_READY": False, "routing_profile_frozen": False, "formal_closeout_ready": measurement_ready, "full_dependency_bundle_sha256": bundle_sha, "adjudication_sha256": sha256_file(args.adjudication_manifest), "blockers": blockers}
    freeze["state_machine"] = {name: bool(freeze[name]) for name in ("C1_COLLECTION_INCOMPLETE", "C1_CANONICAL_CLOSED", "C1_MEASUREMENT_FROZEN", "C2B_RISK_DESIGN_FROZEN", "C2B_DESIGN_FROZEN", "C2B_ASSIGNMENT_MATERIALIZED", "C2B_LAUNCH_READY")}
    (args.output_dir / "c1_evidence_freeze_manifest.json").write_text(json.dumps(freeze, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"day": 1, "phase": "measurement-freeze", "formal_closeout_ready": not blockers, "C1_CANONICAL_CLOSED": freeze["C1_CANONICAL_CLOSED"], "C1_MEASUREMENT_FROZEN": freeze["C1_MEASUREMENT_FROZEN"], "C2B_DESIGN_READY": freeze["C2B_DESIGN_READY"], "routing_profile_frozen": False, "blockers": blockers}


def design_c2b(args: argparse.Namespace) -> dict[str, Any]:
    git_state = formal_git_state(_PROJECT_ROOT)
    if not git_state["clean"]:
        raise ValueError("formal C2-B design requires a committed clean worktree")
    closeout = json.loads(args.c1_closeout_summary.read_text(encoding="utf-8"))
    if closeout.get("method_contract") != "Pilot->P1->C1->C2-B->C2-A-RP->T1->V1" or not closeout.get("git_commit_sha"):
        raise ValueError("C1 freeze lacks the vFinal method contract or clean commit identity")
    if not closeout.get("C1_MEASUREMENT_FROZEN"):
        raise ValueError("C1 measurement evidence is not formally frozen")
    source_rows, holdout_rows = _read(args.source_split_evidence), _read(args.future_holdout_evidence)
    c2_images = _c2_source_images(source_rows)
    held_images = _future_heldout_images(holdout_rows)
    if c2_images & held_images:
        raise ValueError("C2 source split overlaps future holdout")
    risk = materialize_task_risk(
        args.inventory_csv, args.layout_dir, args.c1_task_feature_csv, args.output_dir,
        checkpoint=args.checkpoint,
        c1_freeze_manifest=args.c1_closeout_summary, feature_freeze_manifest=args.feature_freeze_manifest,
        building_registry_csv=args.building_registry, device=args.device,
    )
    risk["git_commit_sha"] = git_state["git_commit_sha"]
    risk["worktree_clean"] = True
    (args.output_dir / "c2_task_risk.summary.json").write_text(json.dumps(risk, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    evidence = materialize_c2b_task_eligibility(
        args.inventory_csv, args.output_dir / "c2_task_risk_inventory.csv",
        args.source_split_evidence, args.future_holdout_evidence,
        args.history_overlap_audit, args.scope_registry, args.reference_registry,
        args.feature_freeze_manifest, args.output_dir / "c2b_task_eligibility_evidence.csv",
    )
    evidence_rows = _read(args.output_dir / "c2b_task_eligibility_evidence.csv")
    _write(args.output_dir / "c2_selected_task_review_queue.csv", [row for row in evidence_rows if row.get("assignment_eligible", "").lower() in {"true", "1"}])
    ready = bool(risk["formal_ready"]) and evidence["n_eligible"] >= 12
    risk["task_eligibility_evidence"] = evidence
    risk["formal_ready"] = ready
    risk["state_machine"]["C2B_RISK_DESIGN_FROZEN"] = ready
    (args.output_dir / "c2_task_risk.summary.json").write_text(json.dumps(risk, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    design_summary: dict[str, Any] = {"candidate_only": True, "n_feasible_candidate_designs": 0}
    if ready:
        c1_dir = args.c1_closeout_summary.parent
        parameter_summary = materialize_design_parameters(
            c1_dir / "c1_gt_quality_analysis.csv", args.output_dir / "c1_task_risk_reference.csv",
            c1_dir / "structural_validation_analysis.csv", c1_dir / "c1_worker_completion_audit.csv",
            args.output_dir,
        )
        profile_summary = materialize_c2b_design_worker_profile(
            c1_dir / "c1_worker_completion_audit.csv", c1_dir / "c1_three_track_worker_state_formal.csv",
            args.output_dir / "c1_c2_design_parameters.csv", c1_dir / "c1_measurement_readiness_by_worker.csv",
            args.output_dir,
        )
        if not parameter_summary["formal_design_input_ready"] or not profile_summary["n_eligible"]:
            return {"day": 2, "phase": "risk-plan", "risk_pool_formal_ready": True, "assignment_materialized": False, "design": design_summary, "state_machine": risk["state_machine"], "blockers": ["c1_design_parameters_or_worker_profile_insufficient"]}
        worker_profile = args.output_dir / "c2b_design_worker_profile.csv"
        design_manifest = c2b.build_candidate_design_manifest(
            args.output_dir / "c2_task_risk_inventory.csv", worker_profile,
            args.c1_closeout_summary, args.output_dir / "c2b_candidate_design_manifest.json",
            threshold_manifest=args.threshold_manifest,
            risk_summary=args.output_dir / "c2_task_risk.summary.json",
        )
        design_summary = c2b.enumerate_candidates(
            args.output_dir / "c2_task_risk_inventory.csv", worker_profile,
            design_manifest, args.output_dir / "c2_candidates",
            c1_closeout_summary=args.c1_closeout_summary,
            risk_summary=args.output_dir / "c2_task_risk.summary.json",
            threshold_manifest=args.threshold_manifest,
            eligibility_evidence_csv=args.output_dir / "c2b_task_eligibility_evidence.csv",
        )
    return {"day": 2, "phase": "risk-plan", "risk_pool_formal_ready": ready, "assignment_materialized": False, "design": design_summary, "state_machine": risk["state_machine"], "blockers": [] if ready else ["risk_or_task_eligibility_pool_insufficient"]}


def build_c2b(args: argparse.Namespace) -> dict[str, Any]:
    if not formal_git_state(_PROJECT_ROOT)["clean"]:
        raise ValueError("formal C2-B build requires a committed clean worktree")
    closeout = json.loads(args.c1_closeout_summary.read_text(encoding="utf-8"))
    risk = json.loads(args.risk_summary.read_text(encoding="utf-8"))
    if not closeout.get("C1_MEASUREMENT_FROZEN") or not closeout.get("C2B_DESIGN_READY"):
        raise ValueError("C1 measurement or C2-B design inputs are not formally frozen")
    if risk.get("method_contract") != "Pilot->P1->C1->C2-B->C2-A-RP->T1->V1" or not risk.get("git_commit_sha") or not risk.get("worktree_clean"):
        raise ValueError("C2 task risk lacks the vFinal method contract or clean commit identity")
    if not risk.get("formal_ready") or not risk.get("state_machine", {}).get("C2B_RISK_DESIGN_FROZEN"):
        raise ValueError("C2 task risk is not formally frozen")
    _require_approval(args.source_split_approval, args.source_split_evidence, "source_split_evidence_sha256")
    _require_approval(args.future_holdout_approval, args.future_holdout_evidence, "future_holdout_evidence_sha256")
    task_approval = _require_approval(
        args.selected_task_reference_manifest, args.task_eligibility_evidence,
        "task_eligibility_evidence_sha256",
    )
    if task_approval.get("reference_registry_sha256") != sha256_file(args.reference_registry):
        raise ValueError("selected_task_reference_approval_invalid_or_stale:reference_registry_sha256")
    if risk.get("output_inventory_sha256") != sha256_file(args.task_pool):
        raise ValueError("C2 task pool is not the inventory bound by the frozen risk summary")
    capacities = {row.get("worker_id", ""): row for row in _read(args.capacity_manifest)}
    if not capacities or len(capacities) != len(_read(args.capacity_manifest)):
        raise ValueError("C2-B capacity manifest requires unique worker rows")
    design = c2b.materialize_approved_assignment(
        args.candidate_dir, args.design_manifest, args.threshold_manifest,
        args.selected_design_approval, args.selected_task_reference_manifest,
        args.task_eligibility_evidence, args.c1_closeout_summary,
        args.risk_summary, args.output_dir,
    )
    assignment_path = args.output_dir / "assignment_manifest_C2B.csv"
    assignments, tasks = _read(assignment_path), {row["task_id"]: row for row in _read(args.task_pool)}
    assigned_by_worker = Counter(row["worker_id"] for row in assignments)
    for worker, count in assigned_by_worker.items():
        try:
            available = int(float(capacities[worker]["c2b_capacity"]))
        except (KeyError, TypeError, ValueError):
            raise ValueError(f"C2-B capacity is missing or invalid for worker {worker}")
        if count > available:
            raise ValueError(f"C2-B assignment exceeds frozen capacity for worker {worker}")
    distribution = [{
        **row,
        "image_path": row.get("image_path") or tasks.get(row["task_id"], {}).get("image_path") or tasks.get(row["task_id"], {}).get("source_path", ""),
    } for row in assignments]
    if any(not row.get("image_path") for row in distribution):
        raise ValueError("C2-B assigned task lacks a materializable image path")
    _write(args.output_dir / "worker_distribution_C2B.csv", distribution)
    worker_dir = args.output_dir / "worker_facing_distribution_C2B"; worker_dir.mkdir(parents=True, exist_ok=True)
    for worker in sorted({row["worker_id"] for row in distribution}):
        _write(worker_dir / f"worker_{worker}_C2B.csv", [row for row in distribution if row["worker_id"] == worker])
    selected_distribution = {row["task_id"]: row for row in distribution}
    imports = [{"data": {"image": row["image_path"], "title": task_id}, "meta": {"round_id": "C2-B"}} for task_id, row in sorted(selected_distribution.items())]
    import_path = args.output_dir / "label_studio_import_C2B.json"
    import_path.write_text(json.dumps(imports, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    support = Counter(row["task_id"] for row in assignments)
    audit = {
        "method_contract": risk["method_contract"], "git_commit_sha": risk["git_commit_sha"],
        "assignment_sha256": sha256_file(assignment_path), "import_sha256": sha256_file(import_path),
        "n_assignments": len(assignments), "n_workers": len({row["worker_id"] for row in assignments}),
        "n_tasks": len(support), "min_task_support": min(support.values(), default=0),
        "duplicate_worker_task_count": len(assignments) - len({(row["worker_id"], row["task_id"]) for row in assignments}),
        "import_smoke_passed": bool(imports) and all(item.get("data", {}).get("image") for item in json.loads(import_path.read_text(encoding="utf-8"))),
        "capacity_manifest_sha256": sha256_file(args.capacity_manifest),
    }
    audit["launch_ready"] = bool(design.get("launch_ready")) and audit["duplicate_worker_task_count"] == 0 and audit["import_smoke_passed"]
    (args.output_dir / "c2b_launch_ready_report.json").write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"day": 2, "phase": "build", "state_machine": design.get("state_machine", {}), **audit}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Paper A C1 closeout and C2-B launch")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_c1_inputs(command: argparse.ArgumentParser, *, active_name: str) -> None:
        command.add_argument("--export-dir", action="append", type=Path, required=True)
        command.add_argument(active_name, type=Path, required=True)
        for name in ("manual-assignment", "semi-assignment", "worker-distribution", "gt-export"):
            command.add_argument(f"--{name}", type=Path, required=True)
        command.add_argument("--p1-closeout-dir", type=Path, required=True)
        command.add_argument("--output-root", type=Path, required=True)
        command.add_argument("--c1-preannotation-feature-csv", type=Path)

    rehearsal = sub.add_parser("rehearse-c1")
    add_c1_inputs(rehearsal, active_name="--active-log")

    freeze = sub.add_parser("freeze-c1")
    freeze.add_argument("--source-live-root", type=Path, required=True)
    freeze.add_argument("--frozen-root", type=Path, required=True)
    freeze.add_argument("--collection-cutoff-server-time", required=True)
    freeze.add_argument("--operator", required=True)
    freeze.add_argument("--late-submission-policy", required=True)
    freeze.add_argument("--active-log-freeze-manifest", type=Path, required=True)
    freeze.add_argument("--collection-closure-manifest", type=Path, required=True)
    freeze.add_argument("--export-dir", action="append", type=Path, required=True)
    freeze.add_argument("--manual-assignment", type=Path, required=True)
    freeze.add_argument("--semi-assignment", type=Path, required=True)

    audit = sub.add_parser("audit-c1")
    add_c1_inputs(audit, active_name="--active-log")
    audit.add_argument("--c1-active-log-freeze-manifest", type=Path, required=True)
    audit.add_argument("--collection-closure-manifest", type=Path, required=True)
    audit.add_argument("--annotation-independence-disposition", dest="independence_disposition", type=Path)
    for name in ("duplicate-adjudication", "structural-disposition", "project-independence-disposition", "scope-adjudication", "reference-amendment", "outside-assignment-disposition", "completion-disposition"):
        audit.add_argument(f"--{name}", type=Path, required=True)

    finalize = sub.add_parser("finalize-c1")
    finalize.add_argument("--output-dir", type=Path, required=True)
    finalize.add_argument("--adjudication-manifest", type=Path, required=True)

    plan = sub.add_parser("design-c2b")
    for name in ("c1-closeout-summary", "inventory-csv", "layout-dir", "c1-task-feature-csv", "checkpoint", "building-registry", "source-split-evidence", "future-holdout-evidence", "history-overlap-audit", "scope-registry", "reference-registry", "feature-freeze-manifest", "threshold-manifest", "output-dir"):
        plan.add_argument(f"--{name}", type=Path, required=True)
    plan.add_argument("--device", default="auto")

    build = sub.add_parser("build-c2b")
    for name in ("c1-closeout-summary", "risk-summary", "task-pool", "task-eligibility-evidence", "candidate-dir", "design-manifest", "threshold-manifest", "source-split-evidence", "source-split-approval", "future-holdout-evidence", "future-holdout-approval", "reference-registry", "selected-task-reference-manifest", "selected-design-approval", "capacity-manifest", "output-dir"):
        build.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args(argv)
    command = {
        "rehearse-c1": rehearse_c1,
        "freeze-c1": freeze_c1,
        "audit-c1": audit_c1,
        "finalize-c1": finalize_c1,
        "design-c2b": design_c2b,
        "build-c2b": build_c2b,
    }[args.command]
    print(json.dumps(command(args), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
