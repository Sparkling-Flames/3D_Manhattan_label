"""Two-day fail-closed C1 closeout and C2-B launch orchestration."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.thesis_main.analysis import build_c2_assignment_manifest_from_c1_gaps as c2b
from tools.thesis_main.analysis.run_c1_precloseout_rehearsal import materialize as rehearse
from tools.thesis_main.analysis.materialize_c2_task_risk import materialize as materialize_task_risk
from tools.thesis_main.analysis.c1_c2_mainline import formal_git_state
from tools.thesis_main.analysis.vfinal_artifact_utils import sha256_file


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _write(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = list(dict.fromkeys(key for row in rows for key in row)) if rows else ["status"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore"); writer.writeheader(); writer.writerows(rows)


def day1_audit(args: argparse.Namespace) -> dict[str, Any]:
    if args.active_log_snapshot.name.casefold() == "new_server":
        raise ValueError("formal Day 1 requires a frozen C1 active-log snapshot, not active_logs/new_server")
    summary = rehearse(
        args.export_dir, args.active_log_snapshot, args.manual_assignment, args.semi_assignment,
        args.worker_distribution, args.gt_export, args.p1_closeout_dir, args.output_root,
        input_status="precloseout_rehearsal",
        c1_preannotation_feature_csv=getattr(args, "c1_preannotation_feature_csv", None),
    )
    return {"day": 1, "phase": "audit", "output_dir": summary["output_dir"], "formal_closeout_ready": False, "review_required": True}


def day1_formal_audit(args: argparse.Namespace) -> dict[str, Any]:
    manifest = json.loads(args.raw_snapshot_manifest.read_text(encoding="utf-8"))
    if manifest.get("input_status") not in {"precloseout_partial_c1", "precloseout_rehearsal", "formal"}:
        raise ValueError("unsupported raw snapshot manifest")
    snapshots = [Path(row["snapshot_path"]) for row in manifest.get("inputs", [])]
    if not snapshots or any(not path.exists() for path in snapshots):
        raise ValueError("raw snapshot manifest contains missing files")
    for row, path in zip(manifest["inputs"], snapshots):
        if sha256_file(path) != row.get("snapshot_sha256"):
            raise ValueError(f"raw snapshot SHA mismatch: {path}")
    by_name = {path.name.split("_", 1)[-1]: path for path in snapshots}
    required = {
        "manual_assignment": "assignment_manifest_C1_manual_draft_v3_1.csv",
        "semi_assignment": "assignment_manifest_C1_semi_draft_v3_1.csv",
        "worker_distribution": "worker_distribution_internal_manifest_v3_1.csv",
        "gt_export": "groudTruth.json",
    }
    missing = [name for name in required.values() if name not in by_name]
    if missing:
        raise ValueError(f"raw snapshot manifest missing formal inputs: {missing}")
    exports = sorted({path.parent for path in snapshots if path.parent.name == "exports"})
    active = next((path.parent for path in snapshots if path.parent.name == "active_logs"), None)
    p1 = next((path.parent for path in snapshots if path.parent.name == "p1_closeout"), None)
    if not exports or not active or not p1:
        raise ValueError("raw snapshot manifest lacks export, active-log, or P1 snapshot")
    feature_snapshot = getattr(args, "c1_preannotation_feature_snapshot", None)
    if feature_snapshot is not None and feature_snapshot.resolve() not in {path.resolve() for path in snapshots}:
        raise ValueError("pre-annotation feature evidence must be a file in the immutable raw snapshot bundle")
    summary = rehearse(
        exports, active, by_name[required["manual_assignment"]], by_name[required["semi_assignment"]],
        by_name[required["worker_distribution"]], by_name[required["gt_export"]], p1, args.output_root,
        input_status="formal", independence_disposition=args.independence_disposition,
        project_independence_disposition=args.project_independence_provenance,
        structural_disposition=args.structural_disposition,
        duplicate_adjudication=args.duplicate_adjudication,
        scope_adjudication=args.scope_adjudication,
        reference_amendment=args.reference_amendment,
        outside_assignment_disposition=args.outside_assignment_disposition,
        completion_disposition=args.completion_disposition,
        c1_preannotation_feature_csv=feature_snapshot,
    )
    return {"day": 1, "phase": "formal-audit", "output_dir": summary["output_dir"], "formal_closeout_ready": False, "blockers": summary["blockers"]}


def day1_finalize(args: argparse.Namespace) -> dict[str, Any]:
    audit_path = args.output_dir / "formal_audit_summary.json"
    final_path = args.output_dir / "c1_final_canonical_closeout_summary.json"
    measurement_path = args.output_dir / "c1_measurement_freeze_manifest.json"
    if not all(path.exists() for path in (audit_path, final_path, measurement_path)):
        raise ValueError("day1-finalize requires a complete formal audit bundle")
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
    if not approved: blockers.append("formal_closeout_adjudication_missing_invalid_or_stale")
    measurement_ready = canonical_ready and not blockers
    freeze = {"schema_version": "c1_measurement_freeze_envelope_v1", "method_contract": audit.get("method_contract", ""), "git_commit_sha": audit.get("git_commit_sha", ""), "C1_COLLECTION_INCOMPLETE": not measurement_ready, "C1_CANONICAL_CLOSED": canonical_ready, "C1_MEASUREMENT_FROZEN": measurement_ready, "C2B_DESIGN_READY": bool(measurement.get("C2B_DESIGN_READY")) and measurement_ready, "C2B_RISK_DESIGN_FROZEN": False, "C2B_DESIGN_FROZEN": False, "C2B_ASSIGNMENT_MATERIALIZED": False, "C2B_LAUNCH_READY": False, "routing_profile_frozen": False, "formal_closeout_ready": measurement_ready, "full_dependency_bundle_sha256": bundle_sha, "adjudication_sha256": sha256_file(args.adjudication_manifest), "blockers": blockers}
    freeze["state_machine"] = {name: bool(freeze[name]) for name in ("C1_COLLECTION_INCOMPLETE", "C1_CANONICAL_CLOSED", "C1_MEASUREMENT_FROZEN", "C2B_RISK_DESIGN_FROZEN", "C2B_DESIGN_FROZEN", "C2B_ASSIGNMENT_MATERIALIZED", "C2B_LAUNCH_READY")}
    (args.output_dir / "c1_evidence_freeze_manifest.json").write_text(json.dumps(freeze, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"day": 1, "phase": "measurement-freeze", "formal_closeout_ready": not blockers, "C1_CANONICAL_CLOSED": freeze["C1_CANONICAL_CLOSED"], "C1_MEASUREMENT_FROZEN": freeze["C1_MEASUREMENT_FROZEN"], "C2B_DESIGN_READY": freeze["C2B_DESIGN_READY"], "routing_profile_frozen": False, "blockers": blockers}


def day2_risk_plan(args: argparse.Namespace) -> dict[str, Any]:
    git_state = formal_git_state(_PROJECT_ROOT)
    if not git_state["clean"]:
        raise ValueError("formal C2-B design requires a committed clean worktree")
    closeout = json.loads(args.c1_closeout_summary.read_text(encoding="utf-8"))
    if closeout.get("method_contract") != "Pilot->P1->C1->C2-B->C2-A-RP->T1->V1" or not closeout.get("git_commit_sha"):
        raise ValueError("C1 freeze lacks the vFinal method contract or clean commit identity")
    if not closeout.get("C1_MEASUREMENT_FROZEN"):
        raise ValueError("C1 measurement evidence is not formally frozen")
    source_rows, holdout_rows = _read(args.source_split_manifest), _read(args.future_holdout_manifest)
    c2_images = {row.get("image_id") for row in source_rows if row.get("allocation") == "C2"}
    held_images = {row.get("image_id") for row in holdout_rows}
    if c2_images & held_images:
        raise ValueError("C2 source split overlaps future holdout")
    risk = materialize_task_risk(
        args.inventory_csv, args.layout_dir, args.c1_task_feature_csv, args.output_dir,
        input_status="formal", checkpoint=args.checkpoint, reference_dir=args.reference_dir,
        extract_lhfeat=True, c1_risk_reference_csv=args.c1_risk_reference_csv,
        c1_freeze_manifest=args.c1_closeout_summary,
    )
    risk["git_commit_sha"] = git_state["git_commit_sha"]
    risk["worktree_clean"] = True
    (args.output_dir / "c2_task_risk.summary.json").write_text(json.dumps(risk, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    rows = _read(args.output_dir / "c2_task_risk_inventory.csv")
    _write(args.output_dir / "c2_selected_task_review_queue.csv", [row for row in rows if row.get("assignment_eligible", "").lower() in {"true", "1"}])
    return {"day": 2, "phase": "risk-plan", "risk_pool_formal_ready": risk["formal_ready"], "assignment_materialized": False, "state_machine": risk["state_machine"], "blockers": [] if risk["formal_ready"] else ["risk_pool_insufficient"]}


def day2_build(args: argparse.Namespace) -> dict[str, Any]:
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
    approvals = [json.loads(path.read_text(encoding="utf-8")) for path in (args.selected_task_reference_manifest, args.future_holdout_manifest, args.source_split_manifest, args.selected_design_approval)]
    if any(item.get("approved") is not True for item in approvals):
        raise ValueError("approved task/reference/holdout manifests are required")
    if risk.get("output_inventory_sha256") != sha256_file(args.task_pool):
        raise ValueError("C2 task pool is not the inventory bound by the frozen risk summary")
    design_approval = approvals[-1]
    if design_approval.get("design_manifest_sha256") != sha256_file(args.design_manifest):
        raise ValueError("selected C2-B design approval is stale or bound to another manifest")
    capacities = {row.get("worker_id", ""): row for row in _read(args.capacity_manifest)}
    if not capacities or len(capacities) != len(_read(args.capacity_manifest)):
        raise ValueError("C2-B capacity manifest requires unique worker rows")
    evidence = args.task_pool.parent / "c2b_task_eligibility_evidence.csv"
    design = c2b.materialize(
        args.task_pool, args.worker_profile, args.design_manifest, args.output_dir,
        input_status="formal", c1_closeout_summary=args.c1_closeout_summary,
        eligibility_evidence_csv=evidence if evidence.exists() else None,
        selected_task_approval=args.selected_design_approval,
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
    distribution = [{**row, "image_path": tasks.get(row["task_id"], {}).get("image_path", "")} for row in assignments]
    _write(args.output_dir / "worker_distribution_C2B.csv", distribution)
    worker_dir = args.output_dir / "worker_facing_distribution_C2B"; worker_dir.mkdir(parents=True, exist_ok=True)
    for worker in sorted({row["worker_id"] for row in distribution}):
        _write(worker_dir / f"worker_{worker}_C2B.csv", [row for row in distribution if row["worker_id"] == worker])
    imports = [{"data": {"image": row.get("image_path", ""), "title": task_id}, "meta": {"round_id": "C2-B"}} for task_id, row in sorted(tasks.items()) if task_id in {edge["task_id"] for edge in assignments}]
    import_path = args.output_dir / "label_studio_import_C2B.json"
    import_path.write_text(json.dumps(imports, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    support = Counter(row["task_id"] for row in assignments)
    audit = {
        "method_contract": risk["method_contract"], "git_commit_sha": risk["git_commit_sha"],
        "assignment_sha256": sha256_file(assignment_path), "import_sha256": sha256_file(import_path),
        "n_assignments": len(assignments), "n_workers": len({row["worker_id"] for row in assignments}),
        "n_tasks": len(support), "min_task_support": min(support.values(), default=0),
        "duplicate_worker_task_count": len(assignments) - len({(row["worker_id"], row["task_id"]) for row in assignments}),
        "import_smoke_passed": isinstance(json.loads(import_path.read_text(encoding="utf-8")), list),
        "capacity_manifest_sha256": sha256_file(args.capacity_manifest),
    }
    audit["launch_ready"] = bool(design.get("launch_ready")) and audit["duplicate_worker_task_count"] == 0 and audit["import_smoke_passed"]
    (args.output_dir / "c2b_launch_ready_report.json").write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"day": 2, "phase": "build", "state_machine": design.get("state_machine", {}), **audit}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    audit = sub.add_parser("day1-canonical-audit")
    audit.add_argument("--export-dir", action="append", type=Path, required=True)
    audit.add_argument("--active-log-snapshot", type=Path, required=True)
    for name in ("manual-assignment", "semi-assignment", "worker-distribution", "gt-export"):
        audit.add_argument(f"--{name}", type=Path, required=True)
    audit.add_argument("--p1-closeout-dir", type=Path, required=True); audit.add_argument("--output-root", type=Path, required=True)
    audit.add_argument("--c1-preannotation-feature-csv", type=Path)
    formal = sub.add_parser("day1-formal-audit")
    formal.add_argument("--raw-snapshot-manifest", type=Path, required=True)
    formal.add_argument("--output-root", type=Path, required=True)
    formal.add_argument("--c1-preannotation-feature-snapshot", type=Path)
    formal.add_argument("--annotation-independence-disposition", dest="independence_disposition", type=Path)
    for name in ("duplicate-adjudication", "structural-disposition", "project-independence-provenance", "scope-adjudication", "reference-amendment", "outside-assignment-disposition", "completion-disposition"):
        formal.add_argument(f"--{name}", type=Path, required=True)
    finalize = sub.add_parser("day1-measurement-freeze"); finalize.add_argument("--output-dir", type=Path, required=True); finalize.add_argument("--adjudication-manifest", type=Path, required=True)
    plan = sub.add_parser("day2-c2b-design")
    for name in ("c1-closeout-summary", "inventory-csv", "layout-dir", "c1-task-feature-csv", "checkpoint", "reference-dir", "c1-risk-reference-csv", "source-split-manifest", "future-holdout-manifest", "output-dir"):
        plan.add_argument(f"--{name}", type=Path, required=True)
    build = sub.add_parser("day2-c2b-build")
    for name in ("c1-closeout-summary", "risk-summary", "task-pool", "worker-profile", "design-manifest", "selected-task-reference-manifest", "future-holdout-manifest", "source-split-manifest", "selected-design-approval", "capacity-manifest", "output-dir"):
        build.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args(argv)
    result = {"day1-canonical-audit": day1_audit, "day1-formal-audit": day1_formal_audit, "day1-measurement-freeze": day1_finalize, "day2-c2b-design": day2_risk_plan, "day2-c2b-build": day2_build}[args.command](args)
    print(json.dumps(result, ensure_ascii=False, indent=2)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
