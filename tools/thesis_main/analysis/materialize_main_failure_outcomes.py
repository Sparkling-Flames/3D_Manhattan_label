"""Materialize complete C1 dispositions and resolved T1/V1 analysis units."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from tools.thesis_main.analysis.failure_disposition import (
    c1_failure_fields,
    incident_evidence_status,
    normalize_attribution,
    normalize_disposition,
    t1_outcome_fields,
    text,
    validate_external_incident,
    v1_outcome_fields,
)


C1_ID_FIELDS = ("project_id", "ls_runtime_task_id", "worker_id", "annotation_id")
C1_FIELDS = [
    *C1_ID_FIELDS, "task_id", "failure_attribution", "structural_validation_status",
    "adjudication_source", "analysis_disposition", "reason_code", "rule_version",
    "input_sha256", "incident_id", "incident_evidence_status",
    "failure_disposition_reason", "worker_caused_structural_failure", "policy_failure",
    "external_system_failure", "structural_failure_evaluable", "worker_reliability_eligible",
]
T1_FIELDS = [
    "task_id", "pair_id", "analysis_unit_pair_id", "condition", "worker_id", "image_id",
    "building_id", "block_id", "risk_route", "risk_bucket", "risk_score",
    "row_failure_attribution", "incident_id", "incident_evidence_status",
    "original_row_failure_attribution", "original_incident_id",
    "pair_analysis_disposition", "source_pair_id", "source_task_id", "rerun_sequence",
    "original_task_id", "rerun_task_id", "frozen_rule_version", "freeze_version",
    "delivery_status", "failure_attribution", "iou_to_gt", "structurally_valid",
    "delivery_adjusted_quality", "quality_evaluable", "risk_assist",
    "usable_pair_sensitivity_eligible", "usable_pair_sensitivity_delivery_adjusted_quality",
    "image_primary_disposition", "image_primary_censor_reason",
    "active_time_integrity_status", "active_time_source", "active_time_source_file",
    "active_time_annotation_id", "owner_valid_active_time", "active_time_seconds",
    "inference_cluster_id",
]
V1_FIELDS = [
    "task_id", "original_task_id", "resolved_task_id", "block_id", "policy_arm", "freeze_version",
    "failure_attribution", "incident_id", "incident_evidence_status",
    "original_failure_attribution", "original_incident_id",
    "analysis_disposition", "policy_terminal_status", "iou_to_gt", "rerun_task_id",
    "rerun_sequence", "reservation_id", "reservation_arm",
    "reservation_capacity_before", "reservation_capacity_after",
    "itt_included", "policy_failure", "delivery_adjusted_quality",
    "risk_route", "k_used", "active_time_seconds", "completion_time_seconds",
    "non_delivery", "policy_failure_reason", "selected_worker_id",
    "selected_annotation_id", "selected_geometry_sha256",
]


def _required(row: dict[str, Any], *fields: str) -> None:
    missing = [field for field in fields if not text(row.get(field))]
    if missing:
        raise ValueError(f"missing required fields: {', '.join(missing)}")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_manifest(path: Path) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8-sig"))
    if text(manifest.get("meta", {}).get("locked_round")) != "C2":
        raise ValueError("rule manifest must be frozen in C2")
    required = set(manifest.get("external_evidence_requirements", {}).get("required_fields", []))
    expected = {
        "incident_id", "incident_type", "occurred_at", "recovered_at",
        "affected_project_ids", "affected_task_ids_or_scope_rule", "evidence_path",
        "evidence_sha256", "recorded_at", "recorded_before_outcome_review",
    }
    if not expected <= required:
        raise ValueError("rule manifest does not contain the formal external incident contract")
    return manifest


def _unique(rows: list[dict[str, Any]], fields: tuple[str, ...], label: str) -> dict[tuple[str, ...], dict[str, Any]]:
    result: dict[tuple[str, ...], dict[str, Any]] = {}
    for row in rows:
        key = tuple(text(row.get(field)) for field in fields)
        if not all(key):
            raise ValueError(f"{label} missing identity: {fields}")
        if key in result:
            raise ValueError(f"duplicate {label} identity: {key}")
        result[key] = row
    return result


def _validate_main_external_rows(
    rows: list[dict[str, Any]],
    incident_rows: list[dict[str, Any]] | None,
    *,
    incident_base_dir: Path,
    stage: str,
) -> list[dict[str, Any]]:
    incidents = (
        _unique(incident_rows, ("incident_id",), "incident")
        if incident_rows is not None else {}
    )
    result = [dict(row) for row in rows]
    invalid_t1_pairs: set[str] = set()
    for row in result:
        attribution_field = "row_failure_attribution" if stage == "T1" else "failure_attribution"
        if normalize_attribution(row.get(attribution_field) or row.get("failure_attribution")) != "external_system_failure":
            continue
        if incident_rows is None:
            raise ValueError(f"{stage} external system failure requires --incident-registry-csv")
        incident_id = text(row.get("incident_id"))
        valid, reason = validate_external_incident(
            row, incidents.get((incident_id,)), evidence_base_dir=incident_base_dir
        )
        row["incident_evidence_status"] = "verified" if valid else "not_evaluable"
        row["failure_disposition_reason"] = reason
        if not valid:
            row[attribution_field] = "not_evaluable"
            if stage == "T1":
                invalid_t1_pairs.add(text(row.get("pair_id")))
            else:
                row["analysis_disposition"] = "not_evaluable"
    if invalid_t1_pairs:
        for row in result:
            if text(row.get("pair_id")) in invalid_t1_pairs:
                row["pair_analysis_disposition"] = "not_evaluable"
    return result


def materialize_complete_c1_dispositions(
    roster_rows: list[dict[str, Any]],
    adjudication_rows: list[dict[str, Any]],
    incident_rows: list[dict[str, Any]],
    structural_rows: list[dict[str, Any]] | None = None,
    *,
    incident_base_dir: Path,
    rule_version: str = "failure_disposition_v2",
    input_sha256: str = "",
    formal_closeout: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Expand sparse adjudication to exactly one fail-closed row per annotation."""
    roster = _unique(roster_rows, C1_ID_FIELDS, "canonical annotation")
    adjudications = _unique(adjudication_rows, C1_ID_FIELDS, "failure adjudication")
    extra = set(adjudications) - set(roster)
    if extra:
        raise ValueError(f"adjudication references unknown canonical annotation: {sorted(extra)[0]}")
    incidents = _unique(incident_rows, ("incident_id",), "incident")
    structural = (
        _unique(structural_rows, C1_ID_FIELDS, "structural validation")
        if structural_rows is not None else {}
    )
    output: list[dict[str, Any]] = []
    reasons: Counter[str] = Counter()

    for identity, annotation in roster.items():
        adjudication = adjudications.get(identity)
        if adjudication is None:
            validation = structural.get(identity)
            status = text((validation or {}).get("structural_validation_status")).lower()
            attributable = text((validation or {}).get("worker_attributable")).lower() in {"true", "1", "yes"}
            if status in {"passed", "valid"}:
                failure = c1_failure_fields({"failure_attribution": "none"})
                reason = "structural_validation_passed_no_exception"
            elif status in {"failed", "invalid"} and attributable:
                failure = c1_failure_fields({"failure_attribution": "worker_caused_structural_failure"})
                reason = "structural_validation_failed_worker_attributable"
            else:
                failure = c1_failure_fields({"failure_attribution": "not_evaluable"})
                reason = "structural_evidence_insufficient"
            adjudication_source = "structural_validator"
        else:
            raw = text(adjudication.get("failure_attribution"))
            if not raw:
                failure = c1_failure_fields({"failure_attribution": "not_evaluable"})
                reason = "adjudication_missing_attribution"
                adjudication_source = "human_adjudication"
            else:
                attribution = normalize_attribution(raw)
                incident_id = text(adjudication.get("incident_id"))
                if attribution == "external_system_failure":
                    valid, reason = validate_external_incident(
                        annotation,
                        incidents.get((incident_id,)),
                        evidence_base_dir=incident_base_dir,
                    )
                    failure = c1_failure_fields({
                        "failure_attribution": attribution if valid else "not_evaluable",
                        "incident_id": incident_id,
                        "incident_evidence_status": "verified" if valid else "not_evaluable",
                    })
                    adjudication_source = "human_adjudication+incident_registry"
                else:
                    failure = c1_failure_fields({
                        "failure_attribution": attribution,
                        "incident_evidence_status": "not_applicable",
                    })
                    reason = "adjudicated"
                    adjudication_source = "human_adjudication"
        reasons[reason] += 1
        validation = structural.get(identity) or {}
        output.append({
            **annotation, **failure,
            "task_id": text(annotation.get("task_id") or annotation.get("ls_runtime_task_id")),
            "structural_validation_status": text(validation.get("structural_validation_status")) or "not_available",
            "adjudication_source": adjudication_source,
            "analysis_disposition": "not_evaluable" if failure["failure_attribution"] == "not_evaluable" else "included",
            "reason_code": reason, "rule_version": rule_version, "input_sha256": input_sha256,
            "failure_disposition_reason": reason,
        })
    if formal_closeout and any(row["failure_attribution"] == "not_evaluable" for row in output):
        raise ValueError("formal C1 closeout blocked by not_evaluable disposition")
    return output, {"n_canonical_annotations": len(output), "reason_counts": dict(sorted(reasons.items()))}


def _t1_pair_disposition(rows: list[dict[str, Any]], pair_id: str) -> str:
    values = {text(row.get("pair_analysis_disposition")) or "included" for row in rows}
    if len(values) != 1:
        raise ValueError(f"T1 pair {pair_id} has inconsistent pair_analysis_disposition")
    value = values.pop()
    if value not in {"included", "rerun", "administrative_censor", "not_evaluable"}:
        raise ValueError(f"unknown pair_analysis_disposition: {value}")
    external_rows = [
        row for row in rows
        if normalize_attribution(row.get("row_failure_attribution") or row.get("failure_attribution"))
        == "external_system_failure"
    ]
    if any(
        incident_evidence_status(
            "external_system_failure", row.get("incident_evidence_status"), row.get("incident_id")
        ) != "verified"
        for row in external_rows
    ):
        return "not_evaluable"
    external = bool(external_rows)
    if external and value == "included":
        raise ValueError(f"T1 external incident requires whole pair rerun or administrative censor: {pair_id}")
    if not external and value in {"rerun", "administrative_censor"} and not text(rows[0].get("rerun_of_pair_id")):
        raise ValueError(f"T1 pair {pair_id} cannot rerun/censor without external incident")
    return value


def _validate_t1_pair(rows: list[dict[str, Any]], pair_id: str) -> None:
    if len(rows) != 2 or Counter(text(row.get("condition")).lower() for row in rows) != {"manual": 1, "semi": 1}:
        raise ValueError(f"T1 pair {pair_id} must contain exactly one manual and one semi")
    for row in rows:
        _required(row, "task_id", "pair_id", "condition")


def materialize_t1_rows(source_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    pairs: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in source_rows:
        pair_id = text(row.get("pair_id"))
        if not pair_id:
            raise ValueError("missing required fields: pair_id")
        pairs[pair_id].append(row)
    for pair_id, rows in pairs.items():
        _validate_t1_pair(rows, pair_id)

    original_by_image: dict[str, list[dict[str, Any]]] = defaultdict(list)
    all_runs_by_image: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for rows in pairs.values():
        image_ids = {text(row.get("image_id")) for row in rows}
        if len(image_ids) != 1 or not next(iter(image_ids), ""):
            raise ValueError("T1 pair must bind exactly one non-empty image_id")
        all_runs_by_image[next(iter(image_ids))].extend(rows)
        if not text(rows[0].get("rerun_of_pair_id")):
            original_by_image[text(rows[0].get("image_id"))].extend(rows)
    for image_id, rows in all_runs_by_image.items():
        worker_counts: Counter[str] = Counter()
        for row in rows:
            _required(row, "worker_id")
            worker_counts[text(row.get("worker_id"))] += 1
        if any(count > 1 for count in worker_counts.values()):
            raise ValueError(f"T1 image {image_id} must use each worker at most once across all runs")

    reruns: dict[str, str] = {}
    for pair_id, rows in pairs.items():
        original = text(rows[0].get("rerun_of_pair_id"))
        if not original:
            continue
        if original in reruns:
            raise ValueError(f"T1 pair {original} has more than one rerun")
        if original not in pairs:
            raise ValueError(f"T1 rerun references unknown pair: {original}")
        if text(rows[0].get("rerun_sequence")) != "1":
            raise ValueError("T1 rerun_sequence must be 1")
        if any(text(row.get("rerun_of_pair_id")) != original for row in rows):
            raise ValueError(f"T1 rerun pair {pair_id} has inconsistent provenance")
        reruns[original] = pair_id

    output: list[dict[str, Any]] = []
    resolved_originals: set[str] = set()
    pair_counts: Counter[str] = Counter()
    for pair_id, original_rows in pairs.items():
        if text(original_rows[0].get("rerun_of_pair_id")):
            continue
        disposition = _t1_pair_disposition(original_rows, pair_id)
        selected_rows = original_rows
        source_pair_id = pair_id
        if disposition == "rerun":
            rerun_pair_id = reruns.get(pair_id)
            if not rerun_pair_id:
                disposition = "administrative_censor"
            else:
                selected_rows = pairs[rerun_pair_id]
                source_pair_id = rerun_pair_id
                _validate_t1_rerun(
                    original_rows, selected_rows, pair_id,
                    original_image_rows=original_by_image[text(original_rows[0].get("image_id"))],
                )
                if _t1_pair_disposition(selected_rows, rerun_pair_id) != "included":
                    raise ValueError(f"T1 rerun pair {rerun_pair_id} must be included")
                resolved_originals.add(pair_id)
                disposition = "included"
        elif pair_id in reruns:
            raise ValueError(f"T1 pair {pair_id} has rerun output but is not marked rerun")

        pair_counts[disposition] += 1
        original_by_condition = {text(row.get("condition")).lower(): row for row in original_rows}
        for row in selected_rows:
            condition = text(row.get("condition")).lower()
            attribution = normalize_attribution(row.get("row_failure_attribution") or row.get("failure_attribution"))
            row_for_outcome = {
                **row,
                "failure_attribution": attribution,
                "analysis_disposition": "included",
            }
            if disposition == "included":
                fields = t1_outcome_fields(row_for_outcome)
            else:
                fields = {
                    "analysis_disposition": disposition, "structurally_valid": "",
                    "delivery_adjusted_quality": "", "quality_evaluable": False,
                }
            delivery_status = "valid" if fields.get("quality_evaluable") else "invalid" if attribution == "worker_caused_structural_failure" else "unavailable"
            output.append({
                **row, **fields,
                "delivery_status": delivery_status, "failure_attribution": "worker" if attribution == "worker_caused_structural_failure" else "external" if attribution == "external_system_failure" else "unknown" if attribution == "not_evaluable" else "none",
                "analysis_unit_pair_id": pair_id,
                "row_failure_attribution": attribution,
                "pair_analysis_disposition": disposition,
                "source_pair_id": source_pair_id,
                "source_task_id": text(row.get("task_id")),
                "task_id": text(original_by_condition[condition].get("task_id")),
                "original_row_failure_attribution": normalize_attribution(
                    original_by_condition[condition].get("row_failure_attribution")
                    or original_by_condition[condition].get("failure_attribution")
                ),
                "original_incident_id": text(original_by_condition[condition].get("incident_id")),
            })
    censored_images = {str(row.get("image_id", "")) for row in output if row.get("pair_analysis_disposition") != "included"}
    for row in output:
        if str(row.get("image_id", "")) in censored_images:
            sensitivity_eligible = row.get("pair_analysis_disposition") == "included" and bool(row.get("quality_evaluable"))
            row.update({
                "usable_pair_sensitivity_eligible": sensitivity_eligible,
                "usable_pair_sensitivity_delivery_adjusted_quality": row.get("delivery_adjusted_quality") if sensitivity_eligible else "",
                "pair_analysis_disposition": "administrative_censor", "analysis_disposition": "administrative_censor",
                "delivery_adjusted_quality": "", "quality_evaluable": False,
            })
        else:
            row.update({"usable_pair_sensitivity_eligible": False, "usable_pair_sensitivity_delivery_adjusted_quality": ""})
        censored = str(row.get("image_id", "")) in censored_images
        row["image_primary_disposition"] = "administrative_censor" if censored else "included"
        row["image_primary_censor_reason"] = "pre_frozen_pair_not_evaluable_after_single_rerun" if censored else ""
    return output, {
        "n_analysis_pairs": sum(pair_counts.values()),
        "pair_disposition_counts": dict(sorted(pair_counts.items())),
        "resolved_rerun_pairs": len(resolved_originals), "administratively_censored_images": len(censored_images),
        "usable_pair_sensitivity_rows": sum(bool(row.get("usable_pair_sensitivity_eligible")) for row in output),
        "image_primary_censor_audit": [
            {"image_id": image_id, "image_primary_disposition": "administrative_censor" if image_id in censored_images else "included", "image_primary_censor_reason": "pre_frozen_pair_not_evaluable_after_single_rerun" if image_id in censored_images else ""}
            for image_id in sorted({str(row.get("image_id", "")) for row in output})
        ],
    }


def _validate_t1_rerun(
    originals: list[dict[str, Any]],
    reruns: list[dict[str, Any]],
    original_pair_id: str,
    *,
    original_image_rows: list[dict[str, Any]] | None = None,
) -> None:
    original_by_condition = {text(row.get("condition")).lower(): row for row in originals}
    rerun_by_condition = {text(row.get("condition")).lower(): row for row in reruns}
    for condition, original in original_by_condition.items():
        rerun = rerun_by_condition[condition]
        _required(original, "worker_id", "image_id", "frozen_rule_version")
        _required(rerun, "worker_id", "image_id", "frozen_rule_version")
        if text(original.get("image_id")) != text(rerun.get("image_id")):
            raise ValueError(f"T1 rerun pair {original_pair_id} changed image")
        if text(original.get("worker_id")) == text(rerun.get("worker_id")):
            raise ValueError(f"T1 rerun pair {original_pair_id} violates worker-image isolation")
        if text(original.get("frozen_rule_version")) != text(rerun.get("frozen_rule_version")):
            raise ValueError(f"T1 rerun pair {original_pair_id} changed freeze version")
    original_workers = {
        text(row.get("worker_id")) for row in (original_image_rows or originals)
    }
    rerun_workers = {text(row.get("worker_id")) for row in reruns}
    if original_workers & rerun_workers:
        raise ValueError(f"T1 rerun pair {original_pair_id} violates full-image worker isolation")


def _capacity(value: Any, field: str) -> int:
    try:
        parsed = int(text(value))
    except ValueError as exc:
        raise ValueError(f"{field} must be an integer") from exc
    if parsed < 0:
        raise ValueError(f"{field} must be nonnegative")
    return parsed


def materialize_v1_rows(
    source_rows: list[dict[str, Any]],
    reservation_rows: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    originals: dict[str, dict[str, Any]] = {}
    reruns: dict[str, dict[str, Any]] = {}
    reservations: set[str] = set()
    reservation_registry = (
        _unique(reservation_rows, ("reservation_id",), "V1 reservation")
        if reservation_rows is not None else {}
    )
    for row in source_rows:
        task_id = text(row.get("task_id"))
        _required(row, "task_id", "policy_arm", "failure_attribution", "analysis_disposition", "freeze_version")
        original_id = text(row.get("original_task_id"))
        if not original_id:
            if task_id in originals:
                raise ValueError(f"duplicate V1 original task: {task_id}")
            originals[task_id] = row
            continue
        if original_id in reruns:
            raise ValueError(f"V1 task {original_id} has more than one rerun")
        _required(
            row, "rerun_task_id", "rerun_sequence", "reservation_id", "reservation_arm",
            "reservation_capacity_before", "reservation_capacity_after",
        )
        if text(row.get("rerun_task_id")) != task_id or text(row.get("rerun_sequence")) != "1":
            raise ValueError("V1 rerun_task_id must equal task_id and rerun_sequence must be 1")
        if task_id == original_id:
            raise ValueError("V1 rerun_task_id must differ from original_task_id")
        reservation_id = text(row.get("reservation_id"))
        if reservation_id in reservations:
            raise ValueError(f"duplicate V1 reservation_id: {reservation_id}")
        reservations.add(reservation_id)
        if reservation_rows is not None:
            registered = reservation_registry.get((reservation_id,))
            if registered is None:
                raise ValueError(f"V1 reservation_id not found in reservation registry: {reservation_id}")
            _required(
                registered, "original_task_id", "rerun_task_id", "block_id", "freeze_version",
                "availability_snapshot_id", "reserved_at", "consumed_at",
            )
            checks = {
                "reservation_arm": row.get("reservation_arm"),
                "reservation_capacity_before": row.get("reservation_capacity_before"),
                "reservation_capacity_after": row.get("reservation_capacity_after"),
                "original_task_id": original_id,
                "rerun_task_id": task_id,
                "block_id": row.get("block_id"),
                "freeze_version": row.get("freeze_version"),
                "availability_snapshot_id": row.get("availability_snapshot_id"),
            }
            if any(text(registered.get(field)) != text(value) for field, value in checks.items()):
                raise ValueError(f"V1 reservation registry mismatch: {reservation_id}")
            if text(registered.get("reservation_status")) != "consumed":
                raise ValueError(f"V1 reservation is not consumed: {reservation_id}")
            if text(registered.get("consumed_at")) < text(registered.get("reserved_at")):
                raise ValueError(f"V1 reservation consumed before it was reserved: {reservation_id}")
        reruns[original_id] = row
    if reruns and reservation_rows is None:
        raise ValueError("V1 rerun requires reservation registry")

    output: list[dict[str, Any]] = []
    policy_failure_by_arm: Counter[str] = Counter()
    disposition_by_arm: dict[str, Counter[str]] = defaultdict(Counter)
    resolved_reruns = 0
    for task_id, original in originals.items():
        disposition = text(original.get("analysis_disposition")) or "included"
        selected = original
        if disposition == "rerun":
            if normalize_attribution(original.get("failure_attribution")) != "external_system_failure":
                raise ValueError("only external system failure may use analysis rerun")
            normalized = normalize_disposition(
                disposition,
                attribution=original.get("failure_attribution"),
                evidence_status=original.get("incident_evidence_status"),
                incident_id=original.get("incident_id"),
            )
            if normalized != "rerun":
                disposition = "not_evaluable"
                rerun = None
            else:
                rerun = reruns.get(task_id)
            if rerun is None:
                if disposition == "rerun":
                    disposition = "administrative_censor"
            else:
                _validate_v1_rerun(original, rerun)
                selected = rerun
                disposition = "included"
                resolved_reruns += 1
        elif task_id in reruns:
            raise ValueError(f"V1 task {task_id} has rerun output but is not marked rerun")

        if text(selected.get("policy_terminal_status")) == "external_system_failure_pending_disposition":
            raise ValueError("external_system_failure_pending_disposition cannot enter final V1 analysis")
        row_for_outcome = {**selected, "analysis_disposition": disposition}
        if disposition != "included":
            row_for_outcome["failure_attribution"] = "external_system_failure"
            row_for_outcome["incident_evidence_status"] = "verified"
            row_for_outcome["incident_id"] = text(original.get("incident_id")) or "validated-upstream"
        fields = v1_outcome_fields(row_for_outcome)
        arm = text(original.get("policy_arm"))
        result = {
            **selected, **fields,
            "task_id": task_id,
            "original_task_id": task_id,
            "resolved_task_id": text(selected.get("task_id")),
            "policy_arm": arm,
            "original_failure_attribution": normalize_attribution(original.get("failure_attribution")),
            "original_incident_id": text(original.get("incident_id")),
        }
        output.append(result)
        disposition_by_arm[arm][text(fields["analysis_disposition"])] += 1
        if fields["policy_failure"]:
            policy_failure_by_arm[arm] += 1

    unknown = set(reruns) - set(originals)
    if unknown:
        raise ValueError(f"V1 rerun references unknown original task: {sorted(unknown)[0]}")
    return output, {
        "n_randomized_tasks": len(output),
        "resolved_reruns": resolved_reruns,
        "policy_failure_by_arm": dict(sorted(policy_failure_by_arm.items())),
        "disposition_by_arm": {
            arm: dict(sorted(counts.items())) for arm, counts in sorted(disposition_by_arm.items())
        },
    }


def _validate_v1_rerun(original: dict[str, Any], rerun: dict[str, Any]) -> None:
    if text(original.get("policy_arm")) != text(rerun.get("policy_arm")):
        raise ValueError("V1 rerun changed policy arm")
    if text(original.get("freeze_version")) != text(rerun.get("freeze_version")):
        raise ValueError("V1 rerun changed freeze version")
    if text(rerun.get("reservation_arm")) != text(original.get("policy_arm")):
        raise ValueError("V1 reservation arm does not match policy arm")
    before = _capacity(rerun.get("reservation_capacity_before"), "reservation_capacity_before")
    after = _capacity(rerun.get("reservation_capacity_after"), "reservation_capacity_after")
    if after != before - 1:
        raise ValueError("V1 reservation must consume exactly one unit of same-arm capacity")
    if text(rerun.get("analysis_disposition")) != "included":
        raise ValueError("V1 rerun result must have analysis_disposition=included")


def materialize(
    stage: str,
    input_csv: Path,
    output_dir: Path,
    *,
    rule_manifest: Path,
    adjudication_csv: Path | None = None,
    incident_registry_csv: Path | None = None,
    reservation_registry_csv: Path | None = None,
    structural_validator_csv: Path | None = None,
    input_status: str = "dry_run",
) -> dict[str, Any]:
    normalized_stage = stage.upper()
    manifest = _load_manifest(rule_manifest)
    rows = _read_csv(input_csv)
    dependencies = {"input_csv": _sha256(input_csv), "rule_manifest": _sha256(rule_manifest)}
    if normalized_stage == "C1":
        if adjudication_csv is None or incident_registry_csv is None:
            raise ValueError("C1 requires --adjudication-csv and --incident-registry-csv")
        output_rows, audit = materialize_complete_c1_dispositions(
            rows, _read_csv(adjudication_csv), _read_csv(incident_registry_csv),
            _read_csv(structural_validator_csv) if structural_validator_csv else None,
            incident_base_dir=incident_registry_csv.parent,
            rule_version=manifest["meta"]["rule_version"],
            input_sha256=_sha256(input_csv),
            formal_closeout=input_status == "formal",
        )
        output_csv, fields = output_dir / "failure_disposition.csv", C1_FIELDS
        dependencies.update({
            "adjudication_csv": _sha256(adjudication_csv),
            "incident_registry_csv": _sha256(incident_registry_csv),
            **({"structural_validator_csv": _sha256(structural_validator_csv)} if structural_validator_csv else {}),
        })
    elif normalized_stage == "T1":
        incident_rows = _read_csv(incident_registry_csv) if incident_registry_csv else None
        rows = _validate_main_external_rows(
            rows, incident_rows,
            incident_base_dir=incident_registry_csv.parent if incident_registry_csv else input_csv.parent,
            stage="T1",
        )
        output_rows, audit = materialize_t1_rows(rows)
        output_csv, fields = output_dir / "t1_outcome_disposition.csv", T1_FIELDS
    elif normalized_stage == "V1":
        incident_rows = _read_csv(incident_registry_csv) if incident_registry_csv else None
        rows = _validate_main_external_rows(
            rows, incident_rows,
            incident_base_dir=incident_registry_csv.parent if incident_registry_csv else input_csv.parent,
            stage="V1",
        )
        output_rows, audit = materialize_v1_rows(
            rows, _read_csv(reservation_registry_csv) if reservation_registry_csv else None
        )
        output_csv, fields = output_dir / "v1_itt_outcome_disposition.csv", V1_FIELDS
        if reservation_registry_csv:
            dependencies["reservation_registry_csv"] = _sha256(reservation_registry_csv)
    else:
        raise ValueError("stage must be C1, T1, or V1")
    if incident_registry_csv:
        dependencies["incident_registry_csv"] = _sha256(incident_registry_csv)
        for incident in _read_csv(incident_registry_csv):
            evidence = Path(text(incident.get("evidence_path")))
            if not evidence.is_absolute():
                evidence = incident_registry_csv.parent / evidence
            if evidence.is_file():
                dependencies[f"incident_evidence:{text(incident.get('incident_id'))}"] = _sha256(evidence)
    _write_csv(output_csv, output_rows, fields)
    image_censor_audit_path: Path | None = None
    if normalized_stage == "T1":
        image_censor_audit_path = output_dir / "t1_image_primary_censor_audit.csv"
        _write_csv(
            image_censor_audit_path,
            list(audit.get("image_primary_censor_audit", [])),
            ["image_id", "image_primary_disposition", "image_primary_censor_reason"],
        )
    summary = {
        "stage": normalized_stage,
        "rule_version": manifest["meta"]["rule_version"],
        "rule_manifest": str(rule_manifest),
        "dependency_sha256": dependencies,
        "output_csv": str(output_csv),
        **({"image_primary_censor_audit_csv": str(image_censor_audit_path)} if image_censor_audit_path else {}),
        "audit": audit,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / f"{normalized_stage.lower()}_failure_disposition_audit.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize frozen C1/T1/V1 failure outcomes.")
    parser.add_argument("--stage", required=True, choices=("C1", "T1", "V1", "c1", "t1", "v1"))
    parser.add_argument("--input-csv", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--rule-manifest", required=True, type=Path)
    parser.add_argument("--adjudication-csv", type=Path)
    parser.add_argument("--incident-registry-csv", type=Path)
    parser.add_argument("--reservation-registry-csv", type=Path)
    parser.add_argument("--structural-validator-csv", type=Path)
    parser.add_argument("--input-status", choices=("dry_run", "formal"), default="dry_run")
    args = parser.parse_args(argv)
    print(json.dumps(materialize(
        args.stage, args.input_csv, args.output_dir,
        rule_manifest=args.rule_manifest,
        adjudication_csv=args.adjudication_csv,
        incident_registry_csv=args.incident_registry_csv,
        reservation_registry_csv=args.reservation_registry_csv,
        structural_validator_csv=args.structural_validator_csv,
        input_status=args.input_status,
    ), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
