"""Bind frozen C1 task labels and GT geometry without inventing missing review."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.thesis_main.analysis.quality_core.geometry_metrics import compute_layout_mask_iou
from tools.thesis_main.analysis.geometry_consensus.representation import normalize_geometry


OUTCOME_FIELDS = [
    "project_id", "ls_runtime_task_id", "task_id", "base_task_id", "condition",
    "final_scope", "scope_resolution_status", "oos_subtype", "scope_reference_mode",
    "geometry_reference_mode", "geometry_reference_status", "reference_identity",
    "reference_sha256", "reference_worker_excluded", "reference_evidence_status",
    "adjudication_status", "reviewed_by", "reviewed_at", "notes",
    "operational_reference_status", "submission_informed_reference_revision",
    "geometry_reference_ready", "task_outcome_reference_ready", "estimand_specific_closeout_ready",
]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _write(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _sha_payload(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _scope(inventory: dict[str, str]) -> tuple[str, str, str, str]:
    status = inventory.get("expert_review_status", "")
    if status == "latest_human_reviewed":
        raw, reviewer = inventory.get("expert_scope_confirmed", "").strip().lower(), "latest_human_reviewed"
        return ("in_scope", "", "expert_adjudicated", reviewer) if raw.startswith("inscope") else (
            ("oos", raw, "expert_adjudicated", reviewer) if raw.startswith("oos") else ("", "", "", "")
        )
    if status == "legacy_labeled_proxy":
        # Historical labels are useful migration evidence, but are not the frozen
        # operational task-outcome reference required by the current protocol.
        return "", "", "legacy_proxy_pending_review", "legacy_human_label"
    return "", "", "", ""


def _gt_references(path: Path) -> dict[str, dict[str, Any]]:
    references = {}
    for task in json.loads(path.read_text(encoding="utf-8-sig")):
        stem = Path(str((task.get("data") or {}).get("title") or (task.get("data") or {}).get("image", ""))).stem
        annotations = [row for row in task.get("annotations", []) if row.get("ground_truth")]
        if not stem or len(annotations) != 1:
            continue
        annotation = annotations[0]
        points = []
        for result in annotation.get("result", []):
            if result.get("type") != "keypointlabels":
                continue
            value = result.get("value") or {}
            points.append([float(value["x"]) * 10.24, float(value["y"]) * 5.12])
        references[stem] = {
            "identity": f"gt:{task.get('project')}:{task.get('id')}:{annotation.get('id')}",
            "points": points,
            "sha256": _sha_payload(annotation.get("result", [])),
        }
    return references


def materialize(
    canonical_csv: Path, geometry_jsonl: Path, inventory_csv: Path, gt_export: Path, output_dir: Path,
    *, scope_adjudication_csv: Path | None = None, reference_amendment: Path | None = None,
) -> dict[str, Any]:
    canonical = _read_csv(canonical_csv)
    inventory = {row.get("base_task_id", ""): row for row in _read_csv(inventory_csv)}
    geometry = {
        row.get("canonical_annotation_id", ""): row
        for line in geometry_jsonl.read_text(encoding="utf-8").splitlines() if line.strip()
        for row in [json.loads(line)]
    }
    references = _gt_references(gt_export)
    amendments: dict[str, dict[str, Any]] = {}
    invalid_amendments = 0
    canonical_ids_by_base = {
        base: {row.get("canonical_annotation_id", "") for row in canonical if row.get("base_task_id", "") == base}
        for base in {row.get("base_task_id", "") for row in canonical}
    }
    for row in _read_csv(reference_amendment) if reference_amendment and reference_amendment.exists() else []:
        base = row.get("base_task_id", "")
        try:
            points = json.loads(row.get("corrected_points_json", ""))
            triggers = set(json.loads(row.get("triggering_canonical_annotation_ids_json", "[]") or "[]"))
        except (json.JSONDecodeError, TypeError):
            invalid_amendments += 1
            continue
        public_sha = references.get(base, {}).get("sha256", "")
        expected_public_sha = row.get("source_public_gt_sha256", "")
        valid = (
            bool(base and isinstance(points, list) and points)
            and base not in amendments
            and row.get("reference_status") == "reference_corrected"
            and all(row.get(field, "").strip() for field in ("reviewed_by", "reviewed_at"))
            and expected_public_sha == public_sha
            and triggers.issubset(canonical_ids_by_base.get(base, set()))
            and normalize_geometry(points)["valid"]
        )
        if not valid:
            invalid_amendments += 1
            continue
        reference_sha = _sha_payload(points)
        references[base] = {"identity": row.get("reference_identity") or f"corrected_gt:{base}:{reference_sha[:12]}", "points": points, "sha256": reference_sha}
        amendments[base] = {**row, "triggers": triggers}
    contexts = {}
    audit = []
    scope_queue_by_base = {}
    for row in canonical:
        base = row.get("base_task_id", "")
        item = inventory.get(base, {})
        final_scope, _oos, _mode, _reviewer = _scope(item)
        if base and not final_scope:
            scope_queue_by_base.setdefault(base, {
                "base_task_id": base,
                "pending_reason": "unreviewed_or_ambiguous_scope",
                "inventory_review_status": item.get("expert_review_status", "missing"),
            })
    scope_queue = list(scope_queue_by_base.values())
    queue_path = output_dir / "c1_scope_base_task_review_queue.csv"
    _write(output_dir / "c1_scope_review_queue.csv", scope_queue, ["base_task_id", "pending_reason", "inventory_review_status"])
    _write(queue_path, scope_queue, ["base_task_id", "pending_reason", "inventory_review_status"])
    queue_sha = hashlib.sha256(queue_path.read_bytes()).hexdigest()
    _write(output_dir / "c1_scope_adjudication_template.csv", [
        {**row, "final_scope": "", "oos_subtype": "", "reviewed_by": "", "reviewed_at": "", "source_queue_sha256": queue_sha}
        for row in scope_queue
    ], ["base_task_id", "pending_reason", "inventory_review_status", "final_scope", "oos_subtype", "reviewed_by", "reviewed_at", "source_queue_sha256"])
    raw_scope_decisions = _read_csv(scope_adjudication_csv) if scope_adjudication_csv and scope_adjudication_csv.exists() else []
    valid_scope_decisions = [row for row in raw_scope_decisions if row.get("source_queue_sha256") == queue_sha]
    scope_decisions = {row.get("base_task_id", ""): row for row in valid_scope_decisions}
    for row in canonical:
        key = tuple(row.get(field, "") for field in ("project_id", "ls_runtime_task_id", "task_id", "base_task_id", "condition"))
        if key in contexts:
            continue
        item = inventory.get(row.get("base_task_id", ""), {})
        final_scope, oos_subtype, scope_mode, reviewer = _scope(item)
        decision = scope_decisions.get(key[3], {})
        if decision and decision.get("final_scope", "").lower() in {"in_scope", "oos"} and all(decision.get(field) for field in ("reviewed_by", "reviewed_at")):
            final_scope, oos_subtype, scope_mode, reviewer = decision["final_scope"].lower(), decision.get("oos_subtype", ""), "sha_bound_base_task_adjudication", decision["reviewed_by"]
        reference = references.get(row.get("base_task_id", ""), {})
        amendment = amendments.get(row.get("base_task_id", ""), {})
        status = "resolved" if final_scope else "pending"
        geometry_ready = bool(reference.get("points"))
        reference_status = "oos_geometry_not_applicable" if final_scope == "oos" else "reference_corrected" if amendment else "reference_ready" if geometry_ready else "pending_adjudication"
        audit.append({
            **dict(zip(("project_id", "ls_runtime_task_id", "task_id", "base_task_id", "condition"), key)),
            "inventory_review_status": item.get("expert_review_status", "missing"),
            "scope_source": scope_mode, "task_outcome_status": status,
            "gt_reference_present": bool(reference), "geometry_reference_ready": geometry_ready,
            "pending_reason": "" if status == "resolved" else "unreviewed_or_ambiguous_scope",
        })
        contexts[key] = {
                **dict(zip(("project_id", "ls_runtime_task_id", "task_id", "base_task_id", "condition"), key)),
                "final_scope": final_scope, "scope_resolution_status": status,
                "oos_subtype": oos_subtype, "scope_reference_mode": scope_mode,
                "geometry_reference_mode": "expert_corrected_frozen_gt" if amendment else "public_frozen_gt" if reference else "not_required_oos" if final_scope == "oos" else "",
                "geometry_reference_status": "reference_ready_corrected_gt" if amendment else "reference_ready_public_gt" if reference else "not_required" if final_scope == "oos" else "reference_missing",
                "reference_identity": reference.get("identity", ""),
                "reference_sha256": reference.get("sha256", ""),
                "reference_worker_excluded": "false", "reference_evidence_status": "evaluable" if reference else "not_required" if final_scope == "oos" else "not_evaluable",
                "adjudication_status": status, "reviewed_by": amendment.get("reviewed_by", reviewer),
                "operational_reference_status": reference_status,
                "submission_informed_reference_revision": bool(amendment.get("triggers")),
                "geometry_reference_ready": geometry_ready or final_scope == "oos",
                "task_outcome_reference_ready": status == "resolved",
                "estimand_specific_closeout_ready": status == "resolved" and (geometry_ready or final_scope == "oos"),
                "reviewed_at": amendment.get("reviewed_at", ""), "notes": amendment.get("notes", "review time absent in frozen candidate inventory; formal mode must fail closed"),
            }
    quality = []
    outcomes_by_key = contexts
    for row in canonical:
        key = tuple(row.get(field, "") for field in ("project_id", "ls_runtime_task_id", "task_id", "base_task_id", "condition"))
        outcome = outcomes_by_key.get(key, {})
        geom = geometry.get(row.get("canonical_annotation_id", ""), {})
        reference = references.get(row.get("base_task_id", ""), {})
        amendment = amendments.get(row.get("base_task_id", ""), {})
        score, meta = None, {"reason": "reference_geometry_missing"}
        structural_status = row.get("structural_validation_status", "")
        structurally_valid = structural_status == "passed" or (not structural_status and bool(geom.get("corners_px")))
        if row.get("canonical_annotation_id", "") in amendment.get("triggers", set()):
            meta = {"reason": "submission_informed_reference_revision"}
        elif not structurally_valid:
            meta = {"reason": "annotation_geometry_invalid"}
        elif geom.get("corners_px") and reference.get("points"):
            score, meta = compute_layout_mask_iou(np.asarray(geom["corners_px"], dtype=float), np.asarray(reference["points"], dtype=float))
        quality.append({
            "project_id": row.get("project_id", ""), "ls_runtime_task_id": row.get("ls_runtime_task_id", ""),
            "task_id": row.get("task_id", ""), "base_task_id": row.get("base_task_id", ""),
            "worker_id": row.get("worker_id", ""), "annotation_id": row.get("annotation_id", ""),
            "canonical_annotation_id": row.get("canonical_annotation_id", ""), "condition": row.get("condition", ""),
            "dataset_group": row.get("dataset_group", ""), "iou_to_gt": "" if score is None else score,
            "quality_evaluable": score is not None, "structurally_valid": structurally_valid,
            "independence_status": row.get("independence_status", ""),
            "failure_attribution": row.get("failure_attribution", ""),
            "outside_assignment_submission": row.get("outside_assignment_submission", ""),
            "duplicate_worker_task_submission": row.get("duplicate_worker_task_submission", ""),
            "worker_caused_structural_failure": row.get("worker_caused_structural_failure", ""),
            "task_outcome_status": outcome.get("adjudication_status", "pending"),
            "geometry_reference_status": outcome.get("geometry_reference_status", "reference_missing"),
            "quality_interpretation_status": "provisional_pending_task_outcome" if score is not None and outcome.get("adjudication_status") != "resolved" else "resolved" if score is not None else "not_evaluable",
            "reference_identity": reference.get("identity", ""), "reference_sha256": reference.get("sha256", ""),
            "submission_informed_reference_revision": row.get("canonical_annotation_id", "") in amendment.get("triggers", set()),
            "score_reason": "" if score is not None else meta.get("reason", "not_evaluable"),
        })
    outcome_rows = list(contexts.values())
    _write(output_dir / "c1_task_outcome_reference.csv", outcome_rows, OUTCOME_FIELDS)
    audit_fields = list(audit[0]) if audit else ["task_id"]
    _write(output_dir / "c1_task_outcome_reference_audit.csv", audit, audit_fields)
    quality_fields = list(quality[0]) if quality else ["task_id"]
    _write(output_dir / "c1_gt_quality_evidence.csv", quality, quality_fields)
    pending_by_base = {}
    for row in audit:
        if row["task_outcome_status"] == "pending":
            pending_by_base.setdefault(row["base_task_id"], {"base_task_id": row["base_task_id"], "pending_reason": row["pending_reason"], "inventory_review_status": row["inventory_review_status"]})
    amendment_candidates = sorted({row["base_task_id"] for row in audit if not row["gt_reference_present"]})
    _write(output_dir / "c1_reference_amendment_template.csv", [{
        "base_task_id": base, "reference_status": "", "corrected_points_json": "",
        "triggering_canonical_annotation_ids_json": "[]", "source_public_gt_sha256": "",
        "reference_identity": "", "reviewed_by": "", "reviewed_at": "", "notes": "",
    } for base in amendment_candidates], ["base_task_id", "reference_status", "corrected_points_json", "triggering_canonical_annotation_ids_json", "source_public_gt_sha256", "reference_identity", "reviewed_by", "reviewed_at", "notes"])
    support_after_exclusion = [{
        "worker_id": worker,
        "resolved_in_scope_support": sum(row.get("worker_id") == worker and row.get("task_outcome_status") == "resolved" for row in quality),
        "pending_scope_excluded_support": sum(row.get("worker_id") == worker and row.get("task_outcome_status") == "pending" for row in quality),
    } for worker in sorted({row.get("worker_id", "") for row in quality})]
    _write(output_dir / "c1_scope_support_after_exclusion_audit.csv", support_after_exclusion, ["worker_id", "resolved_in_scope_support", "pending_scope_excluded_support"])
    status_counts = {status: sum(row.get("operational_reference_status") == status for row in outcome_rows) for status in ("reference_ready", "reference_corrected", "pending_adjudication", "oos_geometry_not_applicable")}
    unresolved = status_counts["pending_adjudication"]
    summary = {
        "n_task_contexts": len(audit), "n_resolved_contexts": sum(row["adjudication_status"] == "resolved" for row in outcome_rows),
        "n_pending_contexts": sum(row["task_outcome_status"] == "pending" for row in audit),
        "n_gt_quality_evaluable": sum(bool(row["quality_evaluable"]) for row in quality),
        "reference_status_counts": status_counts,
        "geometry_reference_ready": bool(outcome_rows) and all(bool(row["geometry_reference_ready"]) for row in outcome_rows),
        "task_outcome_reference_ready": bool(outcome_rows) and all(bool(row["task_outcome_reference_ready"]) for row in outcome_rows),
        "estimand_specific_closeout_ready": bool(outcome_rows) and all(bool(row["estimand_specific_closeout_ready"]) for row in outcome_rows),
        "n_pending_base_tasks": len(pending_by_base),
        "reference_amendment_sha256": hashlib.sha256(reference_amendment.read_bytes()).hexdigest() if reference_amendment and reference_amendment.exists() else "",
        "scope_adjudication_sha256": hashlib.sha256(scope_adjudication_csv.read_bytes()).hexdigest() if scope_adjudication_csv and scope_adjudication_csv.exists() else "",
        "invalid_or_stale_scope_adjudication_count": len(raw_scope_decisions) - len(valid_scope_decisions),
        "applied_reference_amendment_count": len(amendments), "invalid_reference_amendment_count": invalid_amendments,
        "formal_ready": bool(outcome_rows) and all(bool(row["estimand_specific_closeout_ready"]) for row in outcome_rows),
        "formal_blocker": "" if outcome_rows and all(bool(row["estimand_specific_closeout_ready"]) for row in outcome_rows) else "pending_scope_or_geometry_reference",
    }
    (output_dir / "c1_operational_reference_audit.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--canonical-csv", type=Path, required=True)
    parser.add_argument("--geometry-jsonl", type=Path, required=True)
    parser.add_argument("--inventory-csv", type=Path, required=True)
    parser.add_argument("--gt-export", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--scope-adjudication-csv", type=Path)
    parser.add_argument("--reference-amendment", type=Path)
    args = parser.parse_args()
    print(json.dumps(materialize(args.canonical_csv, args.geometry_jsonl, args.inventory_csv, args.gt_export, args.output_dir, scope_adjudication_csv=args.scope_adjudication_csv, reference_amendment=args.reference_amendment), indent=2))


if __name__ == "__main__":
    main()
