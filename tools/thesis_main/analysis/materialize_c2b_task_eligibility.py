"""Materialize the sole formal C2-B task-eligibility evidence table."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.thesis_main.analysis.c1_live_collection_monitor import read_csv, write_csv
from tools.thesis_main.analysis.vfinal_artifact_utils import sha256_file


def _keyed(path: Path, label: str) -> dict[tuple[str, str], dict[str, str]]:
    rows: dict[tuple[str, str], dict[str, str]] = {}
    for row in read_csv(path):
        key = (row.get("image_id", ""), row.get("base_task_id", ""))
        if not all(key):
            raise ValueError(f"{label} contains a row without image_id + base_task_id")
        if key in rows:
            raise ValueError(f"{label} contains duplicate image_id + base_task_id: {key}")
        rows[key] = row
    return rows


def _truth(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "clear", "allowed", "ready", "reference_ready"}


def materialize(
    inventory_csv: Path,
    task_risk_csv: Path,
    source_split_evidence_csv: Path,
    future_holdout_evidence_csv: Path,
    history_overlap_audit_csv: Path,
    scope_registry_csv: Path,
    reference_registry_csv: Path,
    feature_manifest: Path,
    output_csv: Path,
) -> dict[str, Any]:
    """Join every mandatory gate on image/base-task identity; no prefilled fallback."""
    inventory = _keyed(inventory_csv, "candidate inventory")
    risk = _keyed(task_risk_csv, "task risk inventory")
    source = _keyed(source_split_evidence_csv, "source split evidence")
    holdout = _keyed(future_holdout_evidence_csv, "future holdout evidence")
    history = _keyed(history_overlap_audit_csv, "history overlap audit")
    scope = _keyed(scope_registry_csv, "scope registry")
    reference = _keyed(reference_registry_csv, "reference registry")
    feature_sha = sha256_file(feature_manifest)
    input_shas = {
        "inventory_sha256": sha256_file(inventory_csv),
        "task_risk_sha256": sha256_file(task_risk_csv),
        "source_split_evidence_sha256": sha256_file(source_split_evidence_csv),
        "future_holdout_evidence_sha256": sha256_file(future_holdout_evidence_csv),
        "history_overlap_audit_sha256": sha256_file(history_overlap_audit_csv),
        "scope_registry_sha256": sha256_file(scope_registry_csv),
        "reference_registry_sha256": sha256_file(reference_registry_csv),
        "feature_manifest_sha256": feature_sha,
    }

    rows: list[dict[str, Any]] = []
    for key, item in inventory.items():
        task = item.get("task_id", "")
        risk_row = risk.get(key)
        source_row = source.get(key)
        holdout_row = holdout.get(key)
        history_row = history.get(key)
        scope_row = scope.get(key)
        reference_row = reference.get(key)
        reasons: list[str] = []

        source_ok = bool(source_row) and str(source_row.get("allocation", source_row.get("source_split_allowed", ""))).lower() in {"c2", "true", "1", "allowed"}
        holdout_ok = bool(holdout_row) and _truth(holdout_row.get("future_holdout_clear", holdout_row.get("clear")))
        history_overlap = bool(history_row) and _truth(history_row.get("history_overlap", history_row.get("overlap")))
        history_ok = bool(history_row) and _truth(history_row.get("history_clear")) and not history_overlap
        scope_ok = bool(scope_row) and str(scope_row.get("final_scope", scope_row.get("scope_status", ""))).lower() == "in_scope"
        reference_ok = bool(reference_row) and _truth(reference_row.get("geometry_reference_ready", reference_row.get("reference_status")))
        feature_ok = bool(risk_row) and bool(risk_row.get("risk_design_vector_A")) and str(risk_row.get("risk_design_score_A", "")).strip() != "" and risk_row.get("feature_freeze_manifest_sha256") == feature_sha
        risk_ok = bool(risk_row) and risk_row.get("risk_status") == "frozen"
        building_id = str((risk_row or {}).get("building_id", "")).strip()

        if not risk_row: reasons.append("risk_row_missing")
        if not source_ok: reasons.append("source_split_not_clear")
        if not holdout_ok: reasons.append("future_holdout_not_clear")
        if not history_ok: reasons.append("history_overlap" if history_overlap else "history_evidence_not_clear")
        if not scope_ok: reasons.append("scope_not_in_scope")
        if not reference_ok: reasons.append("reference_not_ready")
        if not feature_ok: reasons.append("risk_feature_not_ready")
        if not risk_ok: reasons.append("risk_not_frozen")
        if not building_id: reasons.append("authoritative_building_missing")

        rows.append({
            "image_id": key[0], "base_task_id": key[1], "task_id": task,
            "building_id": building_id, "source_split_allowed": source_ok,
            "future_holdout_clear": holdout_ok, "history_overlap": history_overlap,
            "history_clear": history_ok, "scope_ready": scope_ok,
            "reference_ready": reference_ok, "feature_ready": feature_ok,
            "risk_ready": risk_ok, "assignment_eligible": not reasons,
            "exclusion_reason": ";".join(reasons), **input_shas,
        })

    write_csv(output_csv, rows)
    return {
        "n_tasks": len(rows),
        "n_eligible": sum(bool(row["assignment_eligible"]) for row in rows),
        "sha256": sha256_file(output_csv),
        "input_sha256": input_shas,
    }
