from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from tools.thesis_main.registry.perturbation_operators import (
    OPERATOR_REGISTRY,
    PerturbationEngine,
    canonical_corners_to_runtime_pairs,
    freeze_plan,
    ls_keypoints_to_canonical_corners,
)

FAMILY_ORDER = [
    "acceptable",
    "overextend_adjacent",
    "underextend",
    "over_parsing",
    "corner_drift",
    "corner_duplicate",
    "topology_failure",
    "fail",
]

FAMILY_STRATEGY = {
    "synthetic_first": ["underextend", "corner_drift", "corner_duplicate"],
    "exemplar_first": ["overextend_adjacent", "over_parsing"],
    "intentional_invalid_small_quota": ["topology_failure", "fail"],
}

APPENDIX_PERTURBATION_SECTION = "app:perturbation-operators"

REJECT_LIFECYCLE_FIELDNAMES = [
    "task_id",
    "family",
    "reject_stage",
    "reject_reason",
    "recoverable",
    "fallback_strategy",
    "resolution_status",
    "manifest_row_id",
    "base_task_id",
    "target_dataset_group",
    "source_type",
    "lambda_level",
    "source_corner_count",
    "failure_code",
    "resolution_action",
    "reason_chain",
    "thesis_family_impact",
]

FAMILY_COVERAGE_FIELDNAMES = [
    "family",
    "status",
    "count_tasks",
    "linked_appendix_section",
    "realized_count",
    "reject_count",
    "planned_count",
    "status_reason",
]

MANUAL_RESOLUTION_QUEUE_FIELDNAMES = [
    "manifest_row_id",
    "task_id",
    "family",
    "failure_code",
    "required_action",
    "priority",
    "notes",
]

XML_MODEL_ISSUE_OPERATOR_CROSSWALK_FIELDNAMES = [
    "xml_alias",
    "xml_label_text",
    "operator_family_id",
    "operator_class",
    "operator_status",
    "current_bundle_status",
    "thesis_facing_role",
    "appendix_section",
    "notes",
]

DEFAULT_PRESCREEN_TRAP_FAMILIES = [
    "over_parsing",
    "corner_drift",
    "corner_duplicate",
    "overextend_adjacent",
]

NATURAL_FAILURE_PRIORITY_FAMILIES = [
    "over_parsing",
    "corner_drift",
    "corner_duplicate",
    "overextend_adjacent",
    "fail",
]

EXTENSION_ONLY_TRAP_FAMILIES = ["underextend", "topology_failure"]

SOURCE_OF_TRUTH_DOCS = [
    "docs/thesis_main/实验集设定与用途.md",
    "docs/thesis_main/实验设置执行细则_20260213.md",
]


def _stable_hash(payload: Any) -> str:
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def load_stage1_task_sources(import_json_path: Path) -> dict[str, dict[str, Any]]:
    payload = json.loads(import_json_path.read_text(encoding="utf-8"))
    task_sources: dict[str, dict[str, Any]] = {}
    for item in payload:
        title = str(item.get("data", {}).get("title", "")).strip()
        if not title:
            continue
        base_task_id = title.rsplit(".", 1)[0]
        prediction_list = item.get("predictions") or []
        prediction = prediction_list[0] if prediction_list else {}
        prediction_result = prediction.get("result") or []
        corners_norm, stats = ls_keypoints_to_canonical_corners(prediction_result)
        prediction_hash = _stable_hash(prediction_result)
        task_sources[base_task_id] = {
            "base_task_id": base_task_id,
            "title": title,
            "image": item.get("data", {}).get("image"),
            "dataset_group": item.get("data", {}).get("dataset_group"),
            "init_type": item.get("data", {}).get("init_type"),
            "image_width": stats.get("width", 1024),
            "image_height": stats.get("height", 512),
            "n_keypoints": stats.get("n_keypoints", 0),
            "n_corners": stats.get("n_corners", 0),
            "pair_coverage": stats.get("pair_coverage", 0.0),
            "prediction_hash": prediction_hash,
            "corners_norm": corners_norm,
            "runtime_pairs": canonical_corners_to_runtime_pairs(corners_norm, stats.get("width", 1024), stats.get("height", 512)),
        }
    return task_sources


def read_csv_rows(csv_path: Path) -> list[dict[str, Any]]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _reject_reason_taxonomy(*, materialization_status: str, failure_code: str | None) -> str:
    if materialization_status == "reject" and failure_code:
        return f"operator_reject.{failure_code}"
    if materialization_status == "blocked_by_dependency" and failure_code:
        return f"dependency_block.{failure_code}"
    if materialization_status == "invalid" and failure_code:
        return f"operator_invalid.{failure_code}"
    return "operator_reject.unknown"


def _recoverable_subedge(*, family: str, lambda_level: str, source_corner_count: int, failure_code: str | None) -> bool:
    return (
        family == "underextend"
        and lambda_level == "medium"
        and source_corner_count == 4
        and failure_code == "transform_degenerate"
    )


def build_operator_config(row: dict[str, Any], task_source: dict[str, Any]) -> dict[str, Any]:
    operator_id = row["operator_id"]
    corners = task_source.get("corners_norm", [])
    corner_count = len(corners)
    default_corner_index = 1 if corner_count > 1 else 0

    if operator_id == "underextend":
        return {"remove_index": default_corner_index}
    if operator_id == "corner_drift":
        return {"corner_index": default_corner_index}
    if operator_id == "corner_duplicate":
        return {"corner_index": default_corner_index, "new_points": 1 if row["lambda_level"] != "strong" else 2}
    if operator_id == "overextend_adjacent":
        return {"approved_edge_index": min(default_corner_index, max(corner_count - 1, 0)), "surrogate_mode": True}
    if operator_id == "over_parsing":
        return {"approved_edge_index": min(default_corner_index, max(corner_count - 1, 0)), "surrogate_mode": True}
    return {}


def materialize_bundle(
    *,
    draft_rows: list[dict[str, Any]],
    task_sources: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    plan_rows = []
    for row in draft_rows:
        task_source = task_sources.get(row["base_task_id"], {})
        if row["source_type"] == "natural_failure":
            continue
        plan_rows.append(
            {
                "manifest_row_id": row["manifest_row_id"],
                "target_registry_uid": row["target_registry_uid"],
                "base_task_id": row["base_task_id"],
                "title": row["title"],
                "operator_id": row["operator_id"],
                "source_type": row["source_type"],
                "lambda_level": row["lambda_level"],
                "seed": int(row["seed"]),
                "config": build_operator_config(row, task_source),
            }
        )

    frozen_plan = freeze_plan(plan_rows, task_sources)
    generated_rows = PerturbationEngine().generate_batch(frozen_plan, task_sources)
    generated_by_id = {item["manifest_row_id"]: item for item in generated_rows}

    materialized_rows: list[dict[str, Any]] = []
    generated_bank: list[dict[str, Any]] = []

    for row in draft_rows:
        base_task_id = row["base_task_id"]
        task_source = task_sources.get(base_task_id, {})
        source_corners = task_source.get("corners_norm", [])
        common = dict(row)
        common.update(
            {
                "source_prediction_hash": task_source.get("prediction_hash", ""),
                "source_corner_count": len(source_corners),
                "source_pair_coverage": task_source.get("pair_coverage", ""),
                "materialization_source": "natural_passthrough" if row["source_type"] == "natural_failure" else "synthetic_operator_engine",
            }
        )

        if row["source_type"] == "natural_failure":
            common.update(
                {
                    "manifest_status": "realized",
                    "realized_quota": "1",
                    "materialization_status": "realized",
                    "generated_corner_count": len(source_corners),
                    "generated_corner_delta": 0,
                    "audit_hash": task_source.get("prediction_hash", ""),
                }
            )
            materialized_rows.append(common)
            generated_bank.append(
                {
                    "manifest_row_id": row["manifest_row_id"],
                    "base_task_id": base_task_id,
                    "artifact_status": "natural_passthrough",
                    "family_id": row["operator_id"],
                    "source_type": row["source_type"],
                    "runtime_pairs": task_source.get("runtime_pairs", []),
                    "corners_norm": source_corners,
                    "audit": {"selection_rule": row.get("selection_rule", "")},
                }
            )
            continue

        generated = generated_by_id.get(row["manifest_row_id"], {})
        generated_corners = generated.get("corners_norm", [])
        realized = generated.get("status") == "success"
        common.update(
            {
                "manifest_status": "realized" if realized else "blocked_by_dependency",
                "realized_quota": "1" if realized else "0",
                "materialization_status": "realized" if realized else generated.get("status", "blocked_by_dependency"),
                "generated_corner_count": len(generated_corners),
                "generated_corner_delta": len(generated_corners) - len(source_corners),
                "audit_hash": _stable_hash(generated.get("audit", {})) if generated else "",
            }
        )
        materialized_rows.append(common)
        generated_bank.append(
            {
                "manifest_row_id": row["manifest_row_id"],
                "base_task_id": base_task_id,
                "artifact_status": "generated_synthetic" if realized else generated.get("status", "blocked_by_dependency"),
                "family_id": row["operator_id"],
                "source_type": row["source_type"],
                "runtime_pairs": canonical_corners_to_runtime_pairs(generated_corners, task_source.get("image_width", 1024), task_source.get("image_height", 512)),
                "corners_norm": generated_corners,
                "audit": generated.get("audit", {}),
                "failure_code": generated.get("failure_code"),
                "source_runtime_pairs": task_source.get("runtime_pairs", []),
            }
        )

    return frozen_plan, materialized_rows, generated_bank


def build_reject_lifecycle_rows(
    *,
    materialized_rows: list[dict[str, Any]],
    generated_bank: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    bank_by_id = {row["manifest_row_id"]: row for row in generated_bank}
    reject_rows: list[dict[str, Any]] = []

    for row in materialized_rows:
        if row.get("materialization_status") != "reject":
            continue

        bank_row = bank_by_id.get(row["manifest_row_id"], {})
        failure_code = bank_row.get("failure_code")
        source_corner_count = _as_int(row.get("source_corner_count"))
        recoverable = _recoverable_subedge(
            family=row["operator_id"],
            lambda_level=row["lambda_level"],
            source_corner_count=source_corner_count,
            failure_code=failure_code,
        )
        fallback_strategy = "manual_resolution_required" if recoverable else None
        resolution_status = "pending_manual_resolution" if recoverable else "open_unresolved"
        resolution_action = "hold_for_manual_resolution" if recoverable else "hold_open"
        thesis_family_impact = (
            "underextend_family_partially_realized_but_medium_4corner_subedge_unresolved"
            if recoverable
            else "family_unresolved_in_current_bundle"
        )
        reason_chain = ";".join(
            [
                f"family:{row['operator_id']}",
                f"lambda_level:{row['lambda_level']}",
                f"source_corner_count:{source_corner_count}",
                f"failure_code:{failure_code or 'unknown'}",
                f"materialization_status:{row['materialization_status']}",
            ]
        )
        reject_rows.append(
            {
                "task_id": row["target_registry_uid"],
                "family": row["operator_id"],
                "reject_stage": f"{row['target_stage']}_materialization",
                "reject_reason": _reject_reason_taxonomy(
                    materialization_status=row["materialization_status"],
                    failure_code=failure_code,
                ),
                "recoverable": recoverable,
                "fallback_strategy": fallback_strategy,
                "resolution_status": resolution_status,
                "manifest_row_id": row["manifest_row_id"],
                "base_task_id": row["base_task_id"],
                "target_dataset_group": row["target_dataset_group"],
                "source_type": row["source_type"],
                "lambda_level": row["lambda_level"],
                "source_corner_count": source_corner_count,
                "failure_code": failure_code,
                "resolution_action": resolution_action,
                "reason_chain": reason_chain,
                "thesis_family_impact": thesis_family_impact,
            }
        )

    return reject_rows


def build_fallback_registry(
    *,
    materialized_rows: list[dict[str, Any]],
    reject_lifecycle_rows: list[dict[str, Any]],
    source_manifest: str,
    source_materialized_bundle: str,
) -> dict[str, Any]:
    exemplar_fill_manifest_ids = [
        row["manifest_row_id"]
        for row in materialized_rows
        if row["operator_id"] in FAMILY_STRATEGY["exemplar_first"]
        and row["source_type"] == "synthetic_operator"
        and row["selection_rule"] == "ascending_registry_uid_fill"
    ]
    reject_manual_ids = [
        row["manifest_row_id"]
        for row in reject_lifecycle_rows
        if row.get("fallback_strategy") == "manual_resolution_required"
    ]

    fallback_rules = [
        {
            "fallback_id": "fb_001",
            "fallback_type": "natural_failure_shortfall_to_synthetic_operator_fill",
            "rule_status": "active_applied_in_current_bundle",
            "trigger_condition": {
                "all": [
                    {"field": "operator_id", "op": "in", "value": FAMILY_STRATEGY["exemplar_first"]},
                    {"field": "source_type", "op": "==", "value": "synthetic_operator"},
                    {"field": "selection_rule", "op": "==", "value": "ascending_registry_uid_fill"},
                ]
            },
            "applied_scope": {
                "target_stage": "prescreen_semi",
                "target_dataset_group": "PreScreen_semi",
                "family_strategy": "exemplar_first",
            },
            "linkage_to_tasks": exemplar_fill_manifest_ids,
        },
        {
            "fallback_id": "fb_002",
            "fallback_type": "operator_reject_to_manual_resolution",
            "rule_status": "registered_for_open_rejects_not_auto_applied",
            "trigger_condition": {
                "all": [
                    {"field": "materialization_status", "op": "==", "value": "reject"},
                    {"field": "operator_id", "op": "==", "value": "underextend"},
                    {"field": "lambda_level", "op": "==", "value": "medium"},
                    {"field": "source_corner_count", "op": "==", "value": 4},
                    {"field": "failure_code", "op": "==", "value": "transform_degenerate"},
                ]
            },
            "applied_scope": {
                "target_stage": "prescreen_semi",
                "target_dataset_group": "PreScreen_semi",
                "resolution_channel": "manual_resolution_required",
            },
            "linkage_to_tasks": reject_manual_ids,
        },
    ]

    return {
        "registry_name": "fallback_registry_v1",
        "rule_version": "c-fallback-registry-v1",
        "status": "partial_explicitized",
        "source_artifacts": {
            "trap_manifest_draft": source_manifest,
            "trap_manifest_materialized": source_materialized_bundle,
            "appendix_reference": APPENDIX_PERTURBATION_SECTION,
        },
        "fallback_rules": fallback_rules,
    }


def build_family_coverage_rows(materialized_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    coverage_rows: list[dict[str, Any]] = []
    planned_only_families = set(FAMILY_STRATEGY["intentional_invalid_small_quota"])

    for family in FAMILY_ORDER:
        family_rows = [row for row in materialized_rows if row["operator_id"] == family]
        realized_count = sum(1 for row in family_rows if row["materialization_status"] == "realized")
        reject_count = sum(1 for row in family_rows if row["materialization_status"] == "reject")
        planned_count = 1 if family in planned_only_families and not family_rows else 0

        if reject_count:
            status = "reject"
            status_reason = "family has unresolved reject rows in current materialized bundle"
        elif realized_count:
            status = "realized"
            status_reason = "family has realized rows in current materialized bundle"
        elif family in planned_only_families:
            status = "planned"
            status_reason = "family is frozen under intentional_invalid_small_quota but not selected in current bundle"
        else:
            status = "appendix_only"
            status_reason = "family exists in appendix/operator library but is absent from current bundle and planned quota"

        coverage_rows.append(
            {
                "family": family,
                "status": status,
                "count_tasks": len(family_rows),
                "linked_appendix_section": APPENDIX_PERTURBATION_SECTION,
                "realized_count": realized_count,
                "reject_count": reject_count,
                "planned_count": planned_count,
                "status_reason": status_reason,
            }
        )

    return coverage_rows


def build_family_appendix_notes(family_coverage_rows: list[dict[str, Any]]) -> dict[str, Any]:
    notes = []
    for row in family_coverage_rows:
        family = row["family"]
        status = row["status"]
        if family == "acceptable":
            appendix_role = "appendix_operator_reference_only"
            thesis_facing_status = "appendix_only_not_in_current_bundle"
            why_not_fully_closed = "acceptable is defined in Appendix A/operator library, but the current PreScreen_semi bundle carries no acceptable rows and no current planned quota."
        elif status == "planned":
            appendix_role = "intentional_invalid_small_quota"
            thesis_facing_status = "planned_not_materialized"
            why_not_fully_closed = "family remains locked as intentional_invalid_small_quota in the schema, but the current bundle has not materialized rows for it."
        elif family == "underextend":
            appendix_role = "materialized_bundle_family"
            thesis_facing_status = "partial_realized_with_unresolved_subedge"
            why_not_fully_closed = "underextend has realized weak rows, but the 4-corner + medium subedge remains open reject and still requires manual resolution."
        else:
            appendix_role = "materialized_bundle_family"
            thesis_facing_status = "bundle_realized_but_not_thesis_complete"
            why_not_fully_closed = "family is realized in the current bundle, but C-line family coverage remains bundle-local and does not by itself close the thesis-facing PreScreen_semi target."

        notes.append(
            {
                "family": family,
                "appendix_role": appendix_role,
                "current_bundle_status": status,
                "thesis_facing_status": thesis_facing_status,
                "why_not_fully_closed": why_not_fully_closed,
            }
        )

    return {
        "note_name": "family_appendix_note_v1",
        "appendix_section": APPENDIX_PERTURBATION_SECTION,
        "family_notes": notes,
    }


def build_manual_resolution_queue(reject_lifecycle_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    queue_rows = []
    for row in reject_lifecycle_rows:
        if row.get("fallback_strategy") != "manual_resolution_required":
            continue
        queue_rows.append(
            {
                "manifest_row_id": row["manifest_row_id"],
                "task_id": row["task_id"],
                "family": row["family"],
                "failure_code": row["failure_code"],
                "required_action": row["fallback_strategy"],
                "priority": "high",
                "notes": row["reason_chain"],
            }
        )
    return queue_rows


def build_materialization_summary_v2(
    *,
    materialized_rows: list[dict[str, Any]],
    reject_lifecycle_rows: list[dict[str, Any]],
    fallback_registry: dict[str, Any],
    family_coverage_rows: list[dict[str, Any]],
    source_manifest: str,
    source_import_json: str,
) -> dict[str, Any]:
    status_counts = Counter(row["materialization_status"] for row in materialized_rows)
    resolution_status_counts = Counter(row["resolution_status"] for row in reject_lifecycle_rows)
    thesis_family_impact_counts = Counter(row["thesis_family_impact"] for row in reject_lifecycle_rows)
    family_status_counts = Counter(row["status"] for row in family_coverage_rows)
    appendix_family_coverage_status = {row["family"]: row["status"] for row in family_coverage_rows}
    manual_resolution_queue = build_manual_resolution_queue(reject_lifecycle_rows)
    active_fallback_rules = [
        rule["fallback_id"]
        for rule in fallback_registry.get("fallback_rules", [])
        if rule.get("rule_status") == "active_applied_in_current_bundle"
    ]

    return {
        "bundle_version": "c-materialized-v2-audit-summary",
        "source_manifest": source_manifest,
        "source_import_json": source_import_json,
        "n_rows": len(materialized_rows),
        "n_realized_rows": status_counts.get("realized", 0),
        "n_reject_rows": status_counts.get("reject", 0),
        "n_open_reject_rows": sum(1 for row in reject_lifecycle_rows if not row["resolution_status"].startswith("resolved")),
        "n_manual_resolution_required": len(manual_resolution_queue),
        "n_active_fallback_rules": len(active_fallback_rules),
        "status_counts": dict(status_counts),
        "family_status_counts": dict(family_status_counts),
        "resolution_status_counts": dict(resolution_status_counts),
        "thesis_family_impact_counts": dict(thesis_family_impact_counts),
        "appendix_family_coverage_status": appendix_family_coverage_status,
        "active_fallback_rule_ids": active_fallback_rules,
        "important_note": "This v2 summary is appendix-facing aggregation over lifecycle/fallback/coverage outputs. It does not change the existing bundle contract and does not claim thesis-facing completion.",
    }


def build_c_manifest_consistency_audit(
    *,
    materialized_rows: list[dict[str, Any]],
    reject_lifecycle_rows: list[dict[str, Any]],
    fallback_registry: dict[str, Any],
    family_coverage_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    bundle_reject_rows = [row for row in materialized_rows if row["materialization_status"] == "reject"]
    reject_count_passed = len(bundle_reject_rows) == len(reject_lifecycle_rows)
    reject_mismatch_examples = []
    if not reject_count_passed:
        reject_mismatch_examples = [
            {
                "bundle_reject_manifest_row_ids": [row["manifest_row_id"] for row in bundle_reject_rows],
                "lifecycle_manifest_row_ids": [row["manifest_row_id"] for row in reject_lifecycle_rows],
            }
        ]

    bundle_manifest_row_ids = {row["manifest_row_id"] for row in materialized_rows}
    missing_linkage_examples = []
    for rule in fallback_registry.get("fallback_rules", []):
        for manifest_row_id in rule.get("linkage_to_tasks", []):
            if manifest_row_id not in bundle_manifest_row_ids:
                missing_linkage_examples.append(
                    {
                        "fallback_id": rule["fallback_id"],
                        "missing_manifest_row_id": manifest_row_id,
                    }
                )
    fallback_linkage_passed = not missing_linkage_examples

    expected_family_status = {row["family"]: row["status"] for row in build_family_coverage_rows(materialized_rows)}
    observed_family_status = {row["family"]: row["status"] for row in family_coverage_rows}
    family_status_mismatch_examples = []
    for family in FAMILY_ORDER:
        if expected_family_status.get(family) != observed_family_status.get(family):
            family_status_mismatch_examples.append(
                {
                    "family": family,
                    "expected_status": expected_family_status.get(family),
                    "observed_status": observed_family_status.get(family),
                }
            )
    family_coverage_passed = not family_status_mismatch_examples

    mismatch_examples = reject_mismatch_examples + missing_linkage_examples + family_status_mismatch_examples
    consistency_gate_passed = reject_count_passed and fallback_linkage_passed and family_coverage_passed

    return {
        "audit_name": "c_manifest_consistency_audit_v1",
        "audit_version": "c-manifest-consistency-audit-v1",
        "consistency_gate_passed": consistency_gate_passed,
        "checks": {
            "reject_lifecycle_matches_materialized_reject_count": {
                "passed": reject_count_passed,
                "materialized_reject_count": len(bundle_reject_rows),
                "reject_lifecycle_count": len(reject_lifecycle_rows),
                "mismatch_examples": reject_mismatch_examples,
            },
            "fallback_registry_linkage_resolves_in_bundle": {
                "passed": fallback_linkage_passed,
                "mismatch_examples": missing_linkage_examples,
            },
            "family_coverage_matches_bundle_and_schema": {
                "passed": family_coverage_passed,
                "expected_status_by_family": expected_family_status,
                "observed_status_by_family": observed_family_status,
                "mismatch_examples": family_status_mismatch_examples,
            },
        },
        "mismatch_examples": mismatch_examples,
    }


def load_xml_model_issue_choices(xml_path: Path) -> list[dict[str, str]]:
    root = ET.fromstring(xml_path.read_text(encoding="utf-8"))
    model_issue_choices = root.findall(".//Choices[@name='model_issue']/Choice")
    rows = []
    for choice in model_issue_choices:
        rows.append(
            {
                "xml_alias": str(choice.attrib.get("alias", "")),
                "xml_label_text": str(choice.attrib.get("value", "")),
            }
        )
    return rows


def _thesis_facing_role_for_family(family: str) -> str:
    if family == "acceptable":
        return "normal_control"
    if family in DEFAULT_PRESCREEN_TRAP_FAMILIES:
        return "misleading_trap_default_family"
    if family in NATURAL_FAILURE_PRIORITY_FAMILIES:
        return "misleading_trap_priority_overflow_family"
    if family in EXTENSION_ONLY_TRAP_FAMILIES:
        return "misleading_trap_extension_family_not_required"
    return "appendix_reference_only"


def _crosswalk_note_for_family(family: str, current_bundle_status: str) -> str:
    if family == "acceptable":
        return "XML alias is frozen and the operator exists, but the current bundle has no acceptable control rows."
    if family in DEFAULT_PRESCREEN_TRAP_FAMILIES:
        return "Family is part of the current default misleading-trap allocation and is materialized in the current bundle."
    if family == "fail":
        return "Family stays in the natural-failure priority pool, but it is not part of the current default 12-task trap allocation and remains planned in the current bundle."
    if family in EXTENSION_ONLY_TRAP_FAMILIES and current_bundle_status == "planned":
        return "Family is kept as extension-only and is not required for the current thesis-facing PreScreen_semi target."
    if family == "underextend":
        return "Family is extension-only for thesis-facing targeting; the current bundle has partial rows but the medium 4-corner subedge remains open reject."
    return "Family is frozen in the XML/operator appendix chain, but the current bundle status remains partial."


def build_xml_model_issue_operator_crosswalk(
    *,
    xml_model_issue_choices: list[dict[str, str]],
    family_coverage_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    coverage_by_family = {row["family"]: row for row in family_coverage_rows}
    crosswalk_rows = []

    for choice in xml_model_issue_choices:
        family = choice["xml_alias"]
        operator = OPERATOR_REGISTRY.get(family)
        coverage_row = coverage_by_family.get(family, {})
        operator_status = "registered" if operator is not None else "missing"
        current_bundle_status = coverage_row.get("status", "missing_from_bundle_audit")
        crosswalk_rows.append(
            {
                "xml_alias": family,
                "xml_label_text": choice["xml_label_text"],
                "operator_family_id": family,
                "operator_class": operator.__class__.__name__ if operator is not None else "missing",
                "operator_status": operator_status,
                "current_bundle_status": current_bundle_status,
                "thesis_facing_role": _thesis_facing_role_for_family(family),
                "appendix_section": APPENDIX_PERTURBATION_SECTION,
                "notes": _crosswalk_note_for_family(family, current_bundle_status),
            }
        )

    return crosswalk_rows


def build_prescreen_semi_family_target() -> dict[str, Any]:
    family_target_allocations = []
    for family in FAMILY_ORDER:
        if family == "acceptable":
            family_target_allocations.append(
                {
                    "family": family,
                    "target_count": 6,
                    "target_role": "normal_control",
                    "allocation_status": "required_default_target",
                    "notes": "Recommended control subset for normal initialization samples.",
                }
            )
            continue

        if family in DEFAULT_PRESCREEN_TRAP_FAMILIES:
            family_target_allocations.append(
                {
                    "family": family,
                    "target_count": 3,
                    "target_role": "misleading_trap_default_family",
                    "allocation_status": "required_default_target",
                    "notes": "Part of the current default 12-task misleading-trap allocation.",
                }
            )
            continue

        if family == "fail":
            family_target_allocations.append(
                {
                    "family": family,
                    "target_count": 0,
                    "target_role": "misleading_trap_priority_overflow_family",
                    "allocation_status": "priority_pool_not_in_default_12",
                    "notes": "Listed as a current natural-failure priority family, but not assigned a default quota inside the 4-family x 3 target.",
                }
            )
            continue

        family_target_allocations.append(
            {
                "family": family,
                "target_count": 0,
                "target_role": "misleading_trap_extension_family_not_required",
                "allocation_status": "extension_only_not_required",
                "notes": "Current docs explicitly say this family should not be mandatory prescreen coverage before stable cases exist.",
            }
        )

    return {
        "target_name": "prescreen_semi_family_target_v1",
        "target_total_tasks": 18,
        "normal_control_target": {
            "target_count": 6,
            "xml_alias": "acceptable",
            "role": "normal_initialization_control",
        },
        "misleading_trap_target": {
            "target_count": 12,
            "default_target_family_count": 4,
            "target_per_family": 3,
            "default_target_families": DEFAULT_PRESCREEN_TRAP_FAMILIES,
            "notes": "This encodes the current thesis-facing default target. It does not assert that the current bundle already matches the target one-to-one.",
        },
        "family_target_allocations": family_target_allocations,
        "natural_failure_priority": {
            "priority_families": NATURAL_FAILURE_PRIORITY_FAMILIES,
            "notes": "These families are currently prioritized when natural failures are available.",
        },
        "operator_fill_policy": {
            "fill_trigger": "natural_failure_shortfall",
            "fill_action": "rule_based_perturbation_operator_fill",
            "notes": "If natural failures are insufficient for the default misleading-trap families, rule-based perturbation fills the gap.",
        },
        "oos_stress_policy": {
            "included_in_prescreen_semi_target": False,
            "role": "separate_oos_gate_pool",
            "notes": "OOS stress remains a separate pool and is not counted toward the current PreScreen_semi target.",
        },
        "source_of_truth_docs": SOURCE_OF_TRUTH_DOCS,
    }


def build_current_bundle_vs_prescreen_target_gap(
    *,
    materialized_rows: list[dict[str, Any]],
    reject_lifecycle_rows: list[dict[str, Any]],
    family_coverage_rows: list[dict[str, Any]],
    prescreen_semi_family_target: dict[str, Any],
) -> dict[str, Any]:
    coverage_by_family = {row["family"]: row for row in family_coverage_rows}
    target_allocations = {
        row["family"]: row
        for row in prescreen_semi_family_target.get("family_target_allocations", [])
    }
    target_family_counts = {
        family: int(allocation.get("target_count", 0))
        for family, allocation in target_allocations.items()
    }
    status_bucket_counts = Counter(row["status"] for row in family_coverage_rows)
    status_by_family = {row["family"]: row["status"] for row in family_coverage_rows}

    gap_by_family = {}
    for family in FAMILY_ORDER:
        family_rows = [row for row in materialized_rows if row["operator_id"] == family]
        current_realized_count = sum(1 for row in family_rows if row["materialization_status"] == "realized")
        current_reject_count = sum(1 for row in family_rows if row["materialization_status"] == "reject")
        target_count = target_family_counts.get(family, 0)
        gap_by_family[family] = {
            "current_row_count": len(family_rows),
            "current_realized_count": current_realized_count,
            "current_reject_count": current_reject_count,
            "current_bundle_status": status_by_family.get(family, "missing"),
            "target_count": target_count,
            "target_role": target_allocations.get(family, {}).get("target_role", "unassigned"),
            "realized_gap_to_target": target_count - current_realized_count,
            "notes": coverage_by_family.get(family, {}).get("status_reason", ""),
        }

    open_subedges = []
    for row in reject_lifecycle_rows:
        open_subedges.append(
            {
                "subedge_id": f"{row['family']}+{row['lambda_level']}+{row['source_corner_count']}-corner+{row['failure_code']}",
                "family": row["family"],
                "lambda_level": row["lambda_level"],
                "source_corner_count": row["source_corner_count"],
                "failure_code": row["failure_code"],
                "manifest_row_id": row["manifest_row_id"],
                "task_id": row["task_id"],
                "resolution_status": row["resolution_status"],
            }
        )

    blocked_reasons = [
        "current_bundle_row_count remains 15, below the thesis-facing PreScreen_semi target of about 18",
        "acceptable normal-control rows are still absent from the current bundle while the target requires 6",
        "current bundle family mix does not match the default 4-family x 3 misleading-trap allocation",
        "underextend medium 4-corner transform_degenerate remains an open manual-resolution subedge",
        "topology_failure and fail remain planned in the bundle, so appendix/operator freeze does not imply bundle-level realization",
    ]

    return {
        "gap_name": "current_bundle_vs_prescreen_target_gap_v1",
        "current_bundle_row_count": len(materialized_rows),
        "current_realized_count": sum(1 for row in materialized_rows if row["materialization_status"] == "realized"),
        "current_reject_count": sum(1 for row in materialized_rows if row["materialization_status"] == "reject"),
        "family_status_counts": {
            "status_bucket_counts": dict(status_bucket_counts),
            "status_by_family": status_by_family,
        },
        "target_family_counts": target_family_counts,
        "gap_by_family": gap_by_family,
        "open_subedges": open_subedges,
        "thesis_ready_for_prescreen_semi": False,
        "blocked_reasons": blocked_reasons,
    }


def build_appendix_a_operator_freeze_note(
    *,
    crosswalk_rows: list[dict[str, Any]],
    bundle_gap: dict[str, Any],
) -> str:
    lines = [
        "# Appendix A Operator Freeze Note v1",
        "",
        "This note freezes the XML `model_issue` aliases against the current C-line operator families and the current bundle status.",
        "It is appendix-facing and auditable, but thesis-facing completeness remains partial.",
        "",
        "## 1. XML alias to operator family",
        "",
        "| XML alias | Operator family | Current bundle status | Thesis-facing role |",
        "| --- | --- | --- | --- |",
    ]
    for row in crosswalk_rows:
        lines.append(
            f"| `{row['xml_alias']}` | `{row['operator_family_id']}` | `{row['current_bundle_status']}` | `{row['thesis_facing_role']}` |"
        )

    lines.extend(
        [
            "",
            "## 2. Current bundle status",
            "",
            "- Realized families: `overextend_adjacent`, `over_parsing`, `corner_drift`, `corner_duplicate`.",
            "- Reject family: `underextend` remains partial because the `medium + 4-corner + transform_degenerate` subedge is still open for manual resolution.",
            "- Planned families: `topology_failure`, `fail` remain frozen in the operator/appendix layer but are not materialized in the current bundle.",
            "- Appendix-only family: `acceptable` is frozen in the alias/operator chain, but the current bundle does not contain normal-control rows.",
            "",
            "## 3. What the paper can and cannot claim now",
            "",
            "- Can write: XML `model_issue` alias to C-line operator family mapping is frozen and auditable.",
            "- Can write: the current semi trap system has reproducible operator materialization capability.",
            "- Cannot write: C-line is complete.",
            "- Cannot write: Appendix A is fully closed.",
            "- Cannot write: the current bundle already satisfies the thesis-facing `PreScreen_semi ~= 18` target.",
            "",
            "Appendix A alias/operator freeze is auditable, but thesis-facing completeness remains partial.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_csv(csv_path: Path, rows: list[dict[str, Any]], *, fieldnames: list[str] | None = None) -> None:
    if fieldnames is None:
        if not rows:
            return
        fieldnames = list(rows[0].keys())
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        if rows:
            writer.writerows(rows)


def write_jsonl(jsonl_path: Path, rows: list[dict[str, Any]]) -> None:
    with jsonl_path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            handle.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Materialize Dev C trap bundle from current PreScreen_semi import predictions.")
    parser.add_argument("--draft", default="analysis_results/c_manifests_20260310/trap_manifest_draft_v1.csv")
    parser.add_argument("--import-json", default="import_json/outline_v2_seed20260228/stage1_prescreen_semi_import.json")
    parser.add_argument("--output-dir", default="analysis_results/c_manifests_20260311")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[3]
    draft_path = root / args.draft
    import_json_path = root / args.import_json
    output_dir = root / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    docs_dir = root / "docs"

    draft_rows = read_csv_rows(draft_path)
    task_sources = load_stage1_task_sources(import_json_path)
    frozen_plan, materialized_rows, generated_bank = materialize_bundle(draft_rows=draft_rows, task_sources=task_sources)

    write_csv(output_dir / "trap_manifest_materialized_v2.csv", materialized_rows)
    (output_dir / "perturbation_plan_frozen_v1.json").write_text(json.dumps(frozen_plan, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "synthetic_trap_bank_v1.json").write_text(json.dumps(generated_bank, ensure_ascii=False, indent=2), encoding="utf-8")
    reject_lifecycle_rows = build_reject_lifecycle_rows(materialized_rows=materialized_rows, generated_bank=generated_bank)
    write_csv(output_dir / "reject_lifecycle_v1.csv", reject_lifecycle_rows, fieldnames=REJECT_LIFECYCLE_FIELDNAMES)
    write_jsonl(output_dir / "reject_lifecycle_v1.jsonl", reject_lifecycle_rows)
    source_manifest = str(draft_path.relative_to(root)).replace("\\", "/")
    source_import_json = str(import_json_path.relative_to(root)).replace("\\", "/")
    source_materialized_bundle = str((output_dir / "trap_manifest_materialized_v2.csv").relative_to(root)).replace("\\", "/")
    fallback_registry = build_fallback_registry(
        materialized_rows=materialized_rows,
        reject_lifecycle_rows=reject_lifecycle_rows,
        source_manifest=source_manifest,
        source_materialized_bundle=source_materialized_bundle,
    )
    (output_dir / "fallback_registry_v1.json").write_text(json.dumps(fallback_registry, ensure_ascii=False, indent=2), encoding="utf-8")
    family_coverage_rows = build_family_coverage_rows(materialized_rows)
    write_csv(output_dir / "family_coverage_matrix_v1.csv", family_coverage_rows, fieldnames=FAMILY_COVERAGE_FIELDNAMES)
    family_appendix_note = build_family_appendix_notes(family_coverage_rows)
    (output_dir / "family_appendix_note_v1.json").write_text(json.dumps(family_appendix_note, ensure_ascii=False, indent=2), encoding="utf-8")
    manual_resolution_queue = build_manual_resolution_queue(reject_lifecycle_rows)
    write_csv(output_dir / "manual_resolution_queue_v1.csv", manual_resolution_queue, fieldnames=MANUAL_RESOLUTION_QUEUE_FIELDNAMES)
    consistency_audit = build_c_manifest_consistency_audit(
        materialized_rows=materialized_rows,
        reject_lifecycle_rows=reject_lifecycle_rows,
        fallback_registry=fallback_registry,
        family_coverage_rows=family_coverage_rows,
    )
    (output_dir / "c_manifest_consistency_audit_v1.json").write_text(json.dumps(consistency_audit, ensure_ascii=False, indent=2), encoding="utf-8")
    materialization_summary_v2 = build_materialization_summary_v2(
        materialized_rows=materialized_rows,
        reject_lifecycle_rows=reject_lifecycle_rows,
        fallback_registry=fallback_registry,
        family_coverage_rows=family_coverage_rows,
        source_manifest=source_manifest,
        source_import_json=source_import_json,
    )
    (output_dir / "materialization_summary_v2.json").write_text(json.dumps(materialization_summary_v2, ensure_ascii=False, indent=2), encoding="utf-8")
    xml_model_issue_choices = load_xml_model_issue_choices(root / "tools/label_studio/label_studio_view_config.xml")
    xml_model_issue_operator_crosswalk = build_xml_model_issue_operator_crosswalk(
        xml_model_issue_choices=xml_model_issue_choices,
        family_coverage_rows=family_coverage_rows,
    )
    write_csv(
        output_dir / "xml_model_issue_operator_crosswalk_v1.csv",
        xml_model_issue_operator_crosswalk,
        fieldnames=XML_MODEL_ISSUE_OPERATOR_CROSSWALK_FIELDNAMES,
    )
    prescreen_semi_family_target = build_prescreen_semi_family_target()
    (output_dir / "prescreen_semi_family_target_v1.json").write_text(
        json.dumps(prescreen_semi_family_target, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    current_bundle_vs_prescreen_target_gap = build_current_bundle_vs_prescreen_target_gap(
        materialized_rows=materialized_rows,
        reject_lifecycle_rows=reject_lifecycle_rows,
        family_coverage_rows=family_coverage_rows,
        prescreen_semi_family_target=prescreen_semi_family_target,
    )
    (output_dir / "current_bundle_vs_prescreen_target_gap_v1.json").write_text(
        json.dumps(current_bundle_vs_prescreen_target_gap, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    appendix_a_operator_freeze_note = build_appendix_a_operator_freeze_note(
        crosswalk_rows=xml_model_issue_operator_crosswalk,
        bundle_gap=current_bundle_vs_prescreen_target_gap,
    )
    (docs_dir / "appendix_a_operator_freeze_note_v1.md").write_text(appendix_a_operator_freeze_note, encoding="utf-8")

    status_counter = Counter(row["materialization_status"] for row in materialized_rows)
    family_counter = Counter(row["operator_id"] for row in materialized_rows)
    summary = {
        "bundle_version": "c-materialized-v1",
        "source_manifest": source_manifest,
        "source_import_json": source_import_json,
        "n_rows": len(materialized_rows),
        "n_realized_rows": sum(1 for row in materialized_rows if row["materialization_status"] == "realized"),
        "n_generated_synthetic_rows": sum(1 for row in materialized_rows if row["materialization_source"] == "synthetic_operator_engine" and row["materialization_status"] == "realized"),
        "status_counts": dict(status_counter),
        "family_counts": dict(family_counter),
        "important_note": "This bundle no longer stops at frozen_rule for synthetic rows. It materializes operator outputs from current PreScreen_semi import predictions, but it still depends on the current import JSON and does not claim that the revised thesis Stage 1 target quotas are already fulfilled.",
    }
    (output_dir / "materialization_summary_v1.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
