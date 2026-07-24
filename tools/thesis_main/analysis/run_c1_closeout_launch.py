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
from tools.thesis_main.analysis import run_c1_closeout_dryrun_chain
from tools.thesis_main.analysis.run_c1_precloseout_rehearsal import materialize as rehearse
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
    summary = rehearse(
        exports, active, by_name[required["manual_assignment"]], by_name[required["semi_assignment"]],
        by_name[required["worker_distribution"]], by_name[required["gt_export"]], p1, args.output_root,
        input_status="formal", independence_disposition=args.independence_disposition,
        project_independence_disposition=args.project_independence_disposition,
        structural_disposition=args.structural_disposition,
    )
    return {"day": 1, "phase": "formal-audit", "output_dir": summary["output_dir"], "formal_closeout_ready": False, "blockers": summary["blockers"]}


def day1_finalize(args: argparse.Namespace) -> dict[str, Any]:
    summary = run_c1_closeout_dryrun_chain.finalize_existing_closeout(args.output_dir, args.adjudication_manifest)
    return {"day": 1, "phase": "finalize", "formal_closeout_ready": summary["formal_closeout_ready"], "blockers": summary["blockers"]}


def day2_build(args: argparse.Namespace) -> dict[str, Any]:
    closeout = json.loads(args.c1_closeout_summary.read_text(encoding="utf-8"))
    risk = json.loads(args.risk_summary.read_text(encoding="utf-8"))
    if not closeout.get("formal_closeout_ready") or closeout.get("profile_freeze_status") != "C1_frozen":
        raise ValueError("C1 closeout is not formally frozen")
    if not risk.get("formal_ready"):
        raise ValueError("C2 task risk is not formally frozen")
    if risk.get("output_inventory_sha256") != sha256_file(args.task_pool):
        raise ValueError("C2 task pool is not the inventory bound by the frozen risk summary")
    design = c2b.materialize(args.task_pool, args.worker_profile, args.design_manifest, args.output_dir, input_status="formal", c1_closeout_summary=args.c1_closeout_summary)
    assignment_path = args.output_dir / "assignment_manifest_C2B.csv"
    assignments, tasks = _read(assignment_path), {row["task_id"]: row for row in _read(args.task_pool)}
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
        "assignment_sha256": sha256_file(assignment_path), "import_sha256": sha256_file(import_path),
        "n_assignments": len(assignments), "n_workers": len({row["worker_id"] for row in assignments}),
        "n_tasks": len(support), "min_task_support": min(support.values(), default=0),
        "duplicate_worker_task_count": len(assignments) - len({(row["worker_id"], row["task_id"]) for row in assignments}),
        "import_smoke_passed": isinstance(json.loads(import_path.read_text(encoding="utf-8")), list),
    }
    audit["launch_ready"] = bool(design.get("launch_ready")) and audit["duplicate_worker_task_count"] == 0 and audit["import_smoke_passed"]
    (args.output_dir / "c2b_launch_ready_report.json").write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"day": 2, "phase": "build", **audit}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    audit = sub.add_parser("day1-audit")
    audit.add_argument("--export-dir", action="append", type=Path, required=True)
    audit.add_argument("--active-log-snapshot", type=Path, required=True)
    for name in ("manual-assignment", "semi-assignment", "worker-distribution", "gt-export"):
        audit.add_argument(f"--{name}", type=Path, required=True)
    audit.add_argument("--p1-closeout-dir", type=Path, required=True); audit.add_argument("--output-root", type=Path, required=True)
    formal = sub.add_parser("day1-formal-audit")
    formal.add_argument("--raw-snapshot-manifest", type=Path, required=True)
    formal.add_argument("--output-root", type=Path, required=True)
    formal.add_argument("--independence-disposition", type=Path)
    formal.add_argument("--project-independence-disposition", type=Path, required=True)
    formal.add_argument("--structural-disposition", type=Path, required=True)
    finalize = sub.add_parser("day1-finalize"); finalize.add_argument("--output-dir", type=Path, required=True); finalize.add_argument("--adjudication-manifest", type=Path, required=True)
    build = sub.add_parser("day2-build")
    for name in ("c1-closeout-summary", "risk-summary", "task-pool", "worker-profile", "design-manifest", "output-dir"):
        build.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args(argv)
    result = {"day1-audit": day1_audit, "day1-formal-audit": day1_formal_audit, "day1-finalize": day1_finalize, "day2-build": day2_build}[args.command](args)
    print(json.dumps(result, ensure_ascii=False, indent=2)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
