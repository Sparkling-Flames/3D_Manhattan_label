"""Materialize the direction-neutral P1--C2-A-RP uncertainty substrate v1.

Raw Label Studio exports, raw active logs, and planned imports remain the fact
sources.  Frozen analysis artifacts are used only to reconcile canonical
selection, assignment, timing, and reference provenance.  Historical
eligibility is retained as data and never applied as a global row filter.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import parse_qs, unquote, urlparse

from tools.thesis_main.analysis import materialize_paper_a_data_discovery as discovery
from tools.thesis_main.analysis.full_uncertainty.full_uncertainty_common import (
    cyclic_rmse,
    extract_choice_records,
    extract_image_reference,
    geometry_points,
    parse_jsonish,
    valid_point_ring,
)
from tools.thesis_main.analysis.geometry_consensus.pairwise import pairwise_similarity
from tools.thesis_main.analysis.geometry_consensus.representation import (
    C1_ORPHAN_POINT_REPAIR_RULE_VERSION,
    normalize_geometry,
    normalize_geometry_for_c1_calculation,
)
from tools.thesis_main.analysis.quality_core.choice_parser import extract_data


ROOT = Path(__file__).resolve().parents[4]
SCHEMA_VERSION = "uncertainty_substrate_v1"
DEFAULT_OUTPUT = ROOT / "analysis_results" / "uncertainty_substrate_20260823_v1"
PACK = ROOT / "analysis_results" / "post_block2_analysis_pack_20260817_v4"
CANONICAL_SPINE = PACK / "post_block2_submission_master.csv"
CANONICAL_AUTHORITIES: tuple[tuple[str, int, Path, str, str], ...] = (
    ("P1", 0, ROOT / "analysis_results" / "prescreen_closeout_final_gold_v2_20260701" / "prescreen_canonical_annotations.csv", "task_id", "annotator_id"),
    ("C1", 0, ROOT / "analysis_results" / "c1_formal_audit_20260802_v16_final" / "c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03" / "c1_canonical_annotations.csv", "ls_runtime_task_id", "worker_id"),
    ("C2-B", 0, ROOT / "analysis_results" / "c2b_closeout_20260806_final" / "c2b_canonical_submissions.csv", "runtime_task_id", "worker_id"),
    ("C2-A-RP", 1, ROOT / "analysis_results" / "c2a_rp_block1_reestimate_20260810_v1" / "c2a_rp_block1_canonical_submissions.csv", "runtime_task_id", "worker_id"),
    ("C2-A-RP", 2, ROOT / "analysis_results" / "c2a_rp_block2_reestimate_20260814_v1" / "c2a_rp_block2_canonical_submissions.csv", "runtime_task_id", "worker_id"),
)
REVIEW = ROOT / "analysis_results" / "reviewer_profile_dual_stage_processing_20260819_v2" / "SEMI_ROW_LEVEL_REVIEWER_EVIDENCE.csv"
C1_ROOT = ROOT / "analysis_results" / "c1_formal_audit_20260802_v16_final" / "c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03"
C1_ACTIVE_TIME = C1_ROOT / "c1_task_worker_active_time.csv"
C1_ACTIVE_TIME_SUMMARY = C1_ROOT / "c1_task_worker_active_time.summary.json"
TERMINAL_REFERENCE = ROOT / "analysis_results" / "c2a_rp_terminal_reestimate_20260817_v1" / "c2b_plus_c2a_rp_terminal_risk_slope_evidence.csv"
REFERENCE_REVIEW = ROOT / "analysis_results" / "c2a_rp_reference_review_20260811_v1" / "reference_review_provenance.json"
METHOD_CONTRACT = ROOT / "docs" / "thesis_main" / "PAPER_A_METHOD_CONTRACT_CURRENT.json"
C2B_ACCEPTANCE = ROOT / "docs" / "thesis_main" / "C2B_HISTORICAL_EVIDENCE_ACCEPTANCE_20260811_v1.json"
C2B_BOUND_CLOSEOUT = ROOT / "analysis_results" / "c2a_rp_local_launch_20260807_v4" / "c2b_closeout_v2.json"
C2A_CLOSEOUT = ROOT / "analysis_results" / "c2a_rp_terminal_closeout_20260817_v1" / "c2a_rp_closeout_v2.json"
C2A_TERMINAL_DECLARATION = ROOT / "analysis_results" / "c2a_rp_terminal_declaration_20260817_v1" / "C2A_RP_STAGE_TERMINAL_DECLARATION.json"
C2A_PRECISION_PLAN = ROOT / "analysis_results" / "c2a_rp_block2_distribution_20260810_v1" / "c2a_rp" / "precision_plan_C2A_RP.csv"
WORKBOOK_BUILDER = Path(__file__).with_name("build_full_uncertainty_v5_workbook.mjs")
BAD_GT_TASK = "zsNo4HB9uLZ_4c0aab63a4434cf4878e6f5b3ce9a70b"
STRICT_GEOMETRY_VERSION = "geometry_consensus_strict_seam_aware_current"
RAW_GEOMETRY_VERSION = "label_studio_keypoint_export_1024x512_v1"
FROZEN_CANONICAL_VARIANT_VERSION = "stage_frozen_canonical_geometry_provenance_v1"

PLANNED_IMPORTS: tuple[tuple[str, int, str], ...] = (
    ("P1", 0, "import_json/stage1_prescreen_final_20260325/stage1_prescreen_manual_import_v2.json"),
    ("P1", 0, "import_json/stage1_prescreen_final_20260325/stage1_prescreen_oos_import_v2.json"),
    ("P1", 0, "import_json/stage1_prescreen_final_20260325/stage1_prescreen_oos_audit_only_import_v1.json"),
    ("P1", 0, "import_json/stage1_prescreen_final_20260325/stage1_prescreen_semi_import_v5.json"),
    ("P1", 0, "import_json/stage1_prescreen_final_20260325/stage1_prescreen_semi_audit_stress_import_v3.json"),
    ("P1", 0, "import_json/stage1_prescreen_final_20260325/stage1_prescreen_semi_audit_holdout_v2.json"),
    ("C1", 0, "import_json/calibration_c1_v3_1_formal/c1_v3_1_anchor_import_zh.json"),
    ("C1", 0, "import_json/calibration_c1_v3_1_formal/c1_v3_1_anchor_import_zh_with_gt_id2_v1.json"),
    ("C1", 0, "import_json/calibration_c1_v3_1_formal/c1_v3_1_anchor_import_foreign_https.json"),
    ("C1", 0, "import_json/calibration_c1_v3_1_formal/c1_v3_1_core_import_zh.json"),
    ("C1", 0, "import_json/calibration_c1_v3_1_formal/c1_v3_1_core_import_foreign_https.json"),
    ("C1", 0, "import_json/calibration_c1_v3_1_formal/c1_v3_1_semi_import_zh.json"),
    ("C1", 0, "import_json/calibration_c1_v3_1_formal/c1_v3_1_semi_import_foreign_https.json"),
    ("C2-B", 0, "import_json/c2b/c2b_D8_batch_a_import_zh.json"),
    ("C2-B", 0, "import_json/c2b/c2b_D8_batch_a_import_foreign_https.json"),
    ("C2-A-RP", 1, "import_json/c2a_rp/c2a_rp_block_1_import_zh.json"),
    ("C2-A-RP", 1, "import_json/c2a_rp/c2a_rp_block_1_import_foreign_https.json"),
    ("C2-A-RP", 2, "import_json/c2a_rp/c2a_rp_block_2_import_zh.json"),
    ("C2-A-RP", 2, "import_json/c2a_rp/c2a_rp_block_2_import_foreign_https.json"),
)

STAGE_ORDER = {"P1": 0, "C1": 1, "C2-B": 2, "C2-A-RP": 3, "OUT_OF_SCOPE": 9, "mixed": 10}
NEGATIVE_CODES = {"scope": {"normal"}, "difficulty": {"trivial"}, "model_issue": {"acceptable"}}


ANNOTATION_SPINE_FIELDS = [
    "schema_version", "annotation_identity", "canonical_annotation_id", "canonical_annotation_id_legacy_alias", "raw_annotation_id", "annotation_unique_id",
    "raw_stage", "stage", "block_index", "raw_project_id", "project_id", "raw_runtime_task_id", "runtime_task_id",
    "raw_task_data_task_id", "raw_task_data_planned_task_id", "planned_task_id", "base_task_id", "image_id", "building_id",
    "raw_worker_id", "worker_id", "raw_condition", "assistance_exposure", "task_lane", "scope_status", "dataset_group",
    "task_stratum", "language_group", "assignment_provenance", "canonical_selection_status",
    "historical_primary_eligibility_status", "historical_primary_eligibility_source_field",
    "historical_formal_assignment_status", "legacy_exclusion_reason", "raw_geometry_point_count", "raw_geometry_computable",
    "lead_time_seconds", "lead_time_status", "planned_import_match_status", "planned_import_source_paths_json",
    "raw_export_path", "raw_export_sha256", "canonical_reconciliation_path", "canonical_reconciliation_sha256",
]
LINEAGE_FIELDS = [
    "schema_version", "raw_annotation_version_id", "revision_group_id", "raw_stage", "stage", "block_index", "project_id",
    "runtime_task_id", "base_task_id", "raw_condition", "raw_worker_id", "worker_id", "raw_annotation_id",
    "canonical_annotation_id", "canonical_annotation_id_legacy_alias", "canonical_join_status", "selected_canonical_version", "independent_analysis_unit",
    "raw_only_reason", "version_index_within_task_worker", "previous_raw_annotation_id_chronological", "parent_annotation",
    "created_at", "updated_at", "lead_time_seconds", "result_count", "result_sha256", "source_path", "source_sha256",
]
IMAGE_FIELDS = [
    "schema_version", "image_id", "base_task_id", "building_id", "image_reference", "image_reference_sha256",
    "stage_set_json", "block_index_set_json", "raw_condition_set_json", "task_context_count", "canonical_annotation_count",
    "worker_count", "planned_import_source_paths_json", "raw_export_source_paths_json",
]
TASK_CONTEXT_FIELDS = [
    "schema_version", "task_context_id", "stage", "block_index", "raw_stage_set_json", "base_task_id", "image_id",
    "building_id", "raw_condition", "assistance_exposure", "task_lane", "scope_status_set_json", "dataset_group_set_json",
    "task_stratum_set_json", "canonical_annotation_count", "worker_count", "worker_ids_json", "raw_geometry_computable_count",
    "lead_time_available_count", "formal_active_time_available_count", "reference_measurement_available_count",
]
GEOMETRY_VARIANT_FIELDS = [
    "schema_version", "geometry_variant_id", "canonical_annotation_id", "stage", "block_index", "base_task_id",
    "raw_condition", "worker_id", "variant", "points_json", "point_count", "vertical_boundary_count", "geometry_sha256",
    "parse_status", "geometry_computable", "strict_valid", "strict_reason", "pairing_method", "seam_crossing_detected",
    "topology_valid", "repair_application_status", "repair_status", "algorithm_version", "algorithm_sha256", "source_role",
    "source_path", "source_sha256",
]
GEOMETRY_PAIRWISE_FIELDS = [
    "schema_version", "geometry_pair_id", "stage", "block_index", "base_task_id", "raw_condition", "variant",
    "left_canonical_annotation_id", "right_canonical_annotation_id", "left_worker_id", "right_worker_id", "left_point_count",
    "right_point_count", "cyclic_rmse_diagonal_normalized", "cyclic_rmse_status", "boundary_similarity",
    "wallwall_similarity", "metric_compatible", "pointwise_correspondence_compatible", "correspondence_status",
    "cyclic_correspondence_json", "alignment_direction", "alignment_rotation", "alignment_insertion_count",
    "alignment_deletion_count", "alignment_ambiguous", "pairwise_algorithm_version", "pairwise_algorithm_sha256",
]
META_LONG_FIELDS = [
    "schema_version", "meta_response_long_id", "canonical_annotation_id", "stage", "block_index", "base_task_id",
    "raw_condition", "worker_id", "field_name", "choice_index", "choice_raw", "choice_code", "response_state",
    "field_applicability", "response_timing_status", "structural_na_reason", "response_conflict", "source_path", "source_sha256",
]
META_SET_FIELDS = [
    "schema_version", "meta_response_set_id", "canonical_annotation_id", "stage", "block_index", "base_task_id",
    "raw_condition", "worker_id", "field_name", "choice_set_json", "choice_code_set_json", "response_state",
    "field_applicability", "contains_positive", "contains_explicit_negative", "response_conflict", "response_timing_status",
    "structural_na_reason", "source_path", "source_sha256",
]
PROPOSAL_FACT_FIELDS = [
    "schema_version", "proposal_id", "stage", "block_index", "base_task_id", "image_id", "building_id",
    "initialization_source_kind", "initialization_import_sha256_set_json", "initialization_prediction_sha256", "initial_geometry_hash",
    "initial_points_json", "initial_point_count", "initial_geometry_computable", "initial_geometry_consistency_status",
    "planned_trap_family_set_json", "trap_family_set_json", "reference_identity_set_json", "reference_sha256_set_json",
    "reference_type_set_json", "reference_availability_status", "response_count", "worker_count", "source_path", "source_sha256",
]
PROPOSAL_RESPONSE_FIELDS = [
    "schema_version", "proposal_response_id", "proposal_id", "canonical_annotation_id", "stage", "block_index", "base_task_id",
    "image_id", "building_id", "worker_id", "raw_condition", "initial_points_json", "final_points_json", "initial_point_count",
    "final_point_count", "initial_geometry_hash", "final_geometry_hash", "initial_to_final_rmse_diagonal_normalized",
    "topology_changed", "exact_geometry_equal", "model_issue_choice_raw", "model_issue_choice_set_json",
    "model_issue_response_status", "model_issue_timing_status", "U_initial", "U_final", "delta_U",
    "initial_structurally_valid", "final_structurally_valid", "reference_identity", "reference_sha256", "reference_type",
    "reference_availability_status", "historical_formal_assignment_status", "historical_analysis_eligibility_status",
    "source_path", "source_sha256",
]
REFERENCE_FIELDS = [
    "schema_version", "reference_measurement_id", "canonical_annotation_id", "proposal_id", "stage", "block_index",
    "base_task_id", "worker_id", "measurement_role", "metric_name", "raw_metric_value", "measurement_value",
    "measurement_status", "reference_identity", "reference_sha256", "reference_type", "reference_quality_status",
    "historical_eligibility_status", "source_path", "source_sha256",
]
ACTIVE_TIME_FIELDS = [
    "schema_version", "canonical_annotation_id", "stage", "block_index", "project_id", "runtime_task_id", "base_task_id",
    "raw_condition", "worker_id", "active_time_seconds", "active_time_formal_available", "historical_active_time_eligibility_status",
    "timing_status", "timing_rule_version", "active_time_source", "active_time_source_file", "active_time_event_count",
    "active_time_session_count", "lead_time_seconds", "lead_time_status", "lead_time_is_active_time", "event_fragment_role",
]
ACTIVE_EVENT_FIELDS = [
    "schema_version", "raw_event_id", "raw_source_collection", "raw_event_stage", "stage", "block_index", "in_formal_stage_scope",
    "source_path", "source_sha256", "source_line", "project_id", "runtime_task_id", "annotator_id", "annotation_id", "session_id",
    "timestamp", "server_received_at", "page_type", "page_gate_eligible", "page_gate_reason", "store_mismatch_present",
    "active_seconds_fragment", "active_seconds_fragment_role", "raw_event_json",
]
ACTIVE_SESSION_FIELDS = [
    "schema_version", "active_session_id", "raw_source_collections", "raw_event_stages", "stage", "block_index", "project_id",
    "runtime_task_id", "annotator_id", "session_id", "event_count", "event_fragment_sum_audit_seconds", "session_grouping",
    "primary_active_time_status",
]
COVERAGE_FIELDS = ["schema_version", "check_name", "observed", "expected", "status", "scope", "note"]
DICTIONARY_FIELDS = ["schema_version", "table_name", "field_name", "data_type", "description_zh", "missing_semantics_zh", "source_role"]
OUTPUT_MANIFEST_FIELDS = ["schema_version", "path", "size_bytes", "record_count", "sha256"]

TABLE_SCHEMAS: Mapping[str, list[str]] = {
    "annotation_spine.csv": ANNOTATION_SPINE_FIELDS,
    "annotation_version_lineage.csv": LINEAGE_FIELDS,
    "image_registry.csv": IMAGE_FIELDS,
    "task_context_master.csv": TASK_CONTEXT_FIELDS,
    "geometry_variants.csv": GEOMETRY_VARIANT_FIELDS,
    "geometry_pairwise.csv": GEOMETRY_PAIRWISE_FIELDS,
    "meta_response_long.csv": META_LONG_FIELDS,
    "meta_response_set.csv": META_SET_FIELDS,
    "proposal_fact.csv": PROPOSAL_FACT_FIELDS,
    "proposal_response.csv": PROPOSAL_RESPONSE_FIELDS,
    "reference_measurement.csv": REFERENCE_FIELDS,
    "active_time_context.csv": ACTIVE_TIME_FIELDS,
    "active_event_fact.csv": ACTIVE_EVENT_FIELDS,
    "active_session_fact.csv": ACTIVE_SESSION_FIELDS,
    "COVERAGE_AUDIT.csv": COVERAGE_FIELDS,
    "DATA_DICTIONARY.csv": DICTIONARY_FIELDS,
    "OUTPUT_MANIFEST.csv": OUTPUT_MANIFEST_FIELDS,
}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha_bytes(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool) or type(value).__name__ == "bool_":
        return str(bool(value)).lower()
    if isinstance(value, float):
        return "" if not math.isfinite(value) else format(value, ".15g")
    return value


def _write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> None:
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in fields})


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def _number(value: Any) -> float | None:
    return discovery.number(value)


def _bool_status(value: Any, *, applicable: bool = True) -> str:
    if not applicable:
        return "not_applicable"
    if value in (None, ""):
        return "not_recorded"
    return "eligible" if discovery.truth(value) else "ineligible"


def _normalise_stage(raw_stage: Any) -> tuple[str, int]:
    token = str(raw_stage or "").strip().upper().replace("_", "-")
    if token in {"C2A-RP-B1", "C2-A-RP-B1", "C2A-RP-BLOCK1", "C2-A-RP-BLOCK1"}:
        return "C2-A-RP", 1
    if token in {"C2A-RP-B2", "C2-A-RP-B2", "C2A-RP-BLOCK2", "C2-A-RP-BLOCK2"}:
        return "C2-A-RP", 2
    if token in {"C2B", "C2-B"}:
        return "C2-B", 0
    if token in {"P1", "C1"}:
        return token, 0
    if token in {"", "OUT-OF-SCOPE", "OUTSIDE", "OUT-OF-SCOPE"}:
        return "OUT_OF_SCOPE", 0
    return str(raw_stage or "mixed"), 0


def _stage_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        STAGE_ORDER.get(str(row.get("stage")), 8),
        int(row.get("block_index") or 0),
        str(row.get("base_task_id", "")),
        str(row.get("raw_condition", "")),
        str(row.get("worker_id", "")),
        str(row.get("canonical_annotation_id", "")),
    )


def _path_stem(value: Any) -> str:
    text = str(value or "").split("?", 1)[0].replace("\\", "/").rsplit("/", 1)[-1]
    return Path(text).stem


def _choice_code(value: Any) -> str:
    token = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return re.sub(r"[^0-9a-z_]+", "_", token).strip("_")[:160]


def _unique_json(values: Iterable[Any]) -> str:
    return _canonical_json(sorted({str(value) for value in values if str(value) not in {"", "None"}}))


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _load_planned_import_index() -> tuple[dict[tuple[str, int, str, str], list[dict[str, str]]], list[dict[str, Any]]]:
    index: dict[tuple[str, int, str, str], list[dict[str, str]]] = defaultdict(list)
    sources: list[dict[str, Any]] = []
    for stage, block, relative in PLANNED_IMPORTS:
        path = ROOT / relative
        if not path.is_file():
            raise FileNotFoundError(f"planned import missing: {path}")
        payload = _read_json(path)
        if not isinstance(payload, list):
            raise ValueError(f"planned import is not a task list: {path}")
        digest = discovery.sha(path)
        sources.append({
            "path": relative, "role": "planned_import_fact", "authority": "fact_truth", "sha256": digest,
            "expected_sha256": "", "binding_status": "current_file_sha_inventory", "note": f"{stage} block {block}",
        })
        for task in payload:
            data = task.get("data") or {}
            base = str(data.get("base_task_id") or data.get("image_id") or _path_stem(data.get("title") or data.get("image"))).strip()
            condition = str(data.get("condition") or "").strip().lower()
            planned = str(data.get("planned_task_id") or data.get("task_id") or "").strip()
            if not base:
                continue
            index[(stage, block, base, condition)].append({
                "planned_task_id": planned,
                "source_path": relative,
                "source_sha256": digest,
                "image_reference": str(data.get("image") or ""),
            })
    return index, sources


def _planned_match(
    index: Mapping[tuple[str, int, str, str], list[dict[str, str]]],
    *, stage: str, block: int, base: str, condition: str, raw_planned: str,
) -> tuple[str, str, str]:
    matches = list(index.get((stage, block, base, condition), []))
    status = "exact_stage_block_base_condition"
    if not matches:
        matches = [row for (s, b, image, _), rows in index.items() if (s, b, image) == (stage, block, base) for row in rows]
        status = "stage_block_base_only" if matches else "not_found"
    planned_ids = sorted({row["planned_task_id"] for row in matches if row["planned_task_id"]})
    if len(planned_ids) > 1 and raw_planned not in planned_ids:
        status = "planned_id_conflict_preserved"
    planned = raw_planned or (planned_ids[0] if len(planned_ids) == 1 else "")
    return planned, status, _unique_json(row["source_path"] for row in matches)


def _parse_raw_worker(raw_annotation_json: Any) -> str:
    payload = parse_jsonish(raw_annotation_json) or {}
    value = payload.get("completed_by", "") if isinstance(payload, dict) else ""
    if isinstance(value, dict):
        value = value.get("id", value.get("pk", ""))
    return str(value or "").strip()


def _task_lane(stage: str, condition: str, dataset_group: str, task_stratum: str) -> str:
    if condition == "oos":
        return "outside"
    if stage in {"C2-B", "C2-A-RP"} and task_stratum in {"ordinary", "stress"}:
        return task_stratum
    lower = dataset_group.lower()
    if "anchor" in lower:
        return "anchor"
    if "core" in lower:
        return "core"
    return "screening" if stage == "P1" else "primary"


def _scope_status(task_data: Mapping[str, Any], condition: str) -> str:
    scope = str(task_data.get("scope_gold") or "").strip().lower()
    if scope in {"normal", "in_scope", "in-scope"}:
        return "researcher_in_scope"
    if scope:
        return f"researcher_{_choice_code(scope)}"
    if condition == "oos":
        return "planned_oos_lane"
    return "not_adjudicated"


def _load_c1_active_time() -> tuple[dict[tuple[str, str, str], dict[str, str]], dict[str, Any]]:
    summary = _read_json(C1_ACTIVE_TIME_SUMMARY)
    actual = discovery.sha(C1_ACTIVE_TIME)
    if summary.get("schema_version") != "c1_task_worker_active_time_summary_v1" or summary.get("output_sha256") != actual:
        raise ValueError("C1 active-time freeze SHA/schema mismatch")
    rows = discovery.read_csv(C1_ACTIVE_TIME)
    lookup = {(row["project_id"], row["runtime_task_id"], discovery.worker(row["worker_id"])): row for row in rows}
    if len(rows) != 780 or len(lookup) != 780:
        raise AssertionError("C1 active-time context count/key drift")
    return lookup, summary


def _canonical_key(
    stage: str, block: int, project_id: Any, runtime_task_id: Any, worker_id: Any, annotation_id: Any,
) -> tuple[str, int, str, str, str, str]:
    return (
        stage, block, str(project_id or "").strip(), str(runtime_task_id or "").strip(),
        discovery.worker(worker_id), str(annotation_id or "").strip(),
    )


def _load_canonical_authority() -> tuple[
    dict[tuple[str, int, str, str, str, str], dict[str, str]],
    dict[tuple[str, int, str, str, str], dict[str, str]],
]:
    exact: dict[tuple[str, int, str, str, str, str], dict[str, str]] = {}
    by_task_worker: dict[tuple[str, int, str, str, str], dict[str, str]] = {}
    for stage, block, path, runtime_field, worker_field in CANONICAL_AUTHORITIES:
        source_path = path.relative_to(ROOT).as_posix()
        source_sha = discovery.sha(path)
        for row in discovery.read_csv(path):
            key = _canonical_key(
                stage, block, row.get("project_id"), row.get(runtime_field), row.get(worker_field), row.get("annotation_id"),
            )
            value = {
                "canonical_annotation_id": str(row.get("canonical_annotation_id") or ""),
                "source_path": source_path,
                "source_sha256": source_sha,
            }
            if not all(key[2:]) or not value["canonical_annotation_id"]:
                raise ValueError(f"incomplete canonical authority identity: {source_path} {key}")
            if key in exact:
                raise ValueError(f"duplicate canonical acquisition identity: {key}")
            task_worker_key = key[:-1]
            if task_worker_key in by_task_worker:
                raise ValueError(f"multiple canonical versions for task-worker identity: {task_worker_key}")
            exact[key] = value
            by_task_worker[task_worker_key] = value
    if len(exact) != 2501 or len({row["canonical_annotation_id"] for row in exact.values()}) != 2501:
        raise AssertionError("stage canonical authority count/identity drift")
    return exact, by_task_worker


def _build_bundles(
    submissions: list[dict[str, str]],
    raw_annotations: list[dict[str, Any]],
    planned_index: Mapping[tuple[str, int, str, str], list[dict[str, str]]],
    c1_time: Mapping[tuple[str, str, str], dict[str, str]],
    canonical_authority: Mapping[tuple[str, int, str, str, str, str], dict[str, str]],
) -> list[dict[str, Any]]:
    sidecars = {row["canonical_annotation_id"]: row for row in submissions}
    selected = [row for row in raw_annotations if row["canonical_join_status"] == "matched"]
    if len(sidecars) != 2501 or len(selected) != 2501:
        raise AssertionError("canonical reconciliation count drift")
    if len({row["canonical_annotation_id"] for row in selected}) != 2501:
        raise AssertionError("raw selected canonical identity is not unique")
    bundles: list[dict[str, Any]] = []
    for raw in selected:
        legacy_canonical_id = str(raw["canonical_annotation_id"])
        sidecar = sidecars.get(legacy_canonical_id)
        if sidecar is None:
            raise KeyError(f"canonical sidecar missing: {legacy_canonical_id}")
        stage, block = _normalise_stage(raw["stage"])
        task_data = parse_jsonish(raw["task_data_json"]) or {}
        condition = str(raw.get("condition") or task_data.get("condition") or sidecar.get("condition") or "unknown").strip().lower()
        base = str(raw.get("base_task_id") or task_data.get("base_task_id") or "").strip()
        image_id = str(task_data.get("image_id") or base).strip()
        building = base.split("_", 1)[0] if "_" in base else "not_identifiable"
        raw_planned = str(task_data.get("planned_task_id") or task_data.get("task_id") or raw.get("task_data_task_id") or "").strip()
        planned, planned_status, planned_sources = _planned_match(
            planned_index, stage=stage, block=block, base=base, condition=condition, raw_planned=raw_planned,
        )
        dataset_group = str(task_data.get("dataset_group") or sidecar.get("dataset_group") or "")
        task_stratum = str(task_data.get("task_stratum") or sidecar.get("task_stratum") or "").strip().lower()
        worker_id = discovery.worker(raw["worker_id"])
        authority = canonical_authority.get(_canonical_key(
            stage, block, raw["project_id"], raw["ls_runtime_task_id"], worker_id, raw["annotation_id"],
        ))
        if authority is None:
            raise KeyError(
                f"stage canonical authority missing: {stage}/{block}/{raw['project_id']}/{raw['ls_runtime_task_id']}/{worker_id}/{raw['annotation_id']}"
            )
        canonical_id = authority["canonical_annotation_id"]
        c1_row = c1_time.get((str(raw["project_id"]), str(raw["ls_runtime_task_id"]), worker_id), {})
        if stage == "P1":
            primary = _bool_status(sidecar.get("upstream_eligible_for_primary_analysis"))
            primary_source = "P1.upstream_eligible_for_primary_analysis"
            formal = "not_applicable"
        elif stage == "C1":
            primary = _bool_status(sidecar.get("c1_gt_primary_analysis_eligible"))
            primary_source = "C1.c1_gt_primary_analysis_eligible"
            formal = _bool_status(c1_row.get("formal_assignment_eligible"))
        elif stage == "C2-B":
            primary = _bool_status(sidecar.get("upstream_formal_assignment_eligible"))
            primary_source = "C2-B.upstream_formal_assignment_eligible"
            formal = _bool_status(sidecar.get("upstream_formal_assignment_eligible"))
        elif block == 1:
            primary = _bool_status(sidecar.get("upstream_formal_assignment_eligible"))
            primary_source = "C2-A-RP.B1.upstream_formal_assignment_eligible"
            formal = _bool_status(sidecar.get("upstream_formal_assignment_eligible"))
        else:
            primary = "eligible"
            primary_source = "C2-A-RP.B2.frozen_assignment_membership"
            formal = "eligible"
        results = parse_jsonish(raw["result_json"]) or []
        raw_points = [[float(x), float(y)] for x, y in extract_data(results)[0].tolist()]
        raw_worker = _parse_raw_worker(raw["raw_annotation_json"])
        lead = _number(raw.get("lead_time_seconds"))
        spine = {
            "schema_version": SCHEMA_VERSION,
            "annotation_identity": f"{stage}|{block}|{raw['project_id']}|{raw['ls_runtime_task_id']}|{worker_id}|{raw['annotation_id']}",
            "canonical_annotation_id": canonical_id,
            "canonical_annotation_id_legacy_alias": legacy_canonical_id if legacy_canonical_id != canonical_id else "",
            "raw_annotation_id": str(raw["annotation_id"]),
            "annotation_unique_id": str(raw.get("unique_id") or ""),
            "raw_stage": str(raw["stage"]), "stage": stage, "block_index": block,
            "raw_project_id": str(raw["project_id"]), "project_id": str(raw["project_id"]),
            "raw_runtime_task_id": str(raw["ls_runtime_task_id"]), "runtime_task_id": str(raw["ls_runtime_task_id"]),
            "raw_task_data_task_id": str(raw.get("task_data_task_id") or ""),
            "raw_task_data_planned_task_id": str(task_data.get("planned_task_id") or ""),
            "planned_task_id": planned, "base_task_id": base, "image_id": image_id, "building_id": building,
            "raw_worker_id": raw_worker, "worker_id": worker_id, "raw_condition": condition,
            "assistance_exposure": "model_preannotation" if condition == "semi" else "none",
            "task_lane": _task_lane(stage, condition, dataset_group, task_stratum),
            "scope_status": _scope_status(task_data, condition), "dataset_group": dataset_group,
            "task_stratum": task_stratum, "language_group": str(task_data.get("language_group") or sidecar.get("upstream_language_group") or ""),
            "assignment_provenance": str(sidecar.get("assignment_provenance") or sidecar.get("upstream_assignment_batch_id") or "not_recorded"),
            "canonical_selection_status": "selected", "historical_primary_eligibility_status": primary,
            "historical_primary_eligibility_source_field": primary_source, "historical_formal_assignment_status": formal,
            "legacy_exclusion_reason": str(sidecar.get("exclusion_reason") or ""),
            "raw_geometry_point_count": len(raw_points), "raw_geometry_computable": valid_point_ring(raw_points),
            "lead_time_seconds": lead, "lead_time_status": "available" if lead is not None else "not_evaluable",
            "planned_import_match_status": planned_status, "planned_import_source_paths_json": planned_sources,
            "raw_export_path": str(raw["source_path"]), "raw_export_sha256": str(raw["source_sha256"]),
            "canonical_reconciliation_path": authority["source_path"],
            "canonical_reconciliation_sha256": authority["source_sha256"],
        }
        bundles.append({"spine": spine, "raw": raw, "sidecar": sidecar, "task_data": task_data, "raw_points": raw_points, "c1_time": c1_row})
    bundles.sort(key=lambda item: _stage_key(item["spine"]))
    if len({item["spine"]["canonical_annotation_id"] for item in bundles}) != 2501:
        raise AssertionError("authoritative canonical identity is not unique after raw reconciliation")
    return bundles


def _build_lineage(
    raw_annotations: list[dict[str, Any]],
    canonical_by_task_worker: Mapping[tuple[str, int, str, str, str], dict[str, str]],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for raw in raw_annotations:
        grouped[(str(raw["stage"]), str(raw["project_id"]), str(raw["ls_runtime_task_id"]), discovery.worker(raw["worker_id"]))].append(raw)
    rows: list[dict[str, Any]] = []
    for key in sorted(grouped):
        group = sorted(grouped[key], key=lambda row: (str(row.get("created_at") or ""), str(row.get("updated_at") or ""), str(row["annotation_id"])))
        previous = ""
        revision_group_id = _sha_bytes("|".join(key))[:24]
        for index, raw in enumerate(group, 1):
            stage, block = _normalise_stage(raw["stage"])
            selected = raw["canonical_join_status"] == "matched"
            authority = canonical_by_task_worker.get((
                stage, block, str(raw["project_id"]), str(raw["ls_runtime_task_id"]), discovery.worker(raw["worker_id"]),
            ))
            if authority is None:
                raise KeyError(f"canonical lineage task-worker authority missing: {key}")
            canonical_id = authority["canonical_annotation_id"]
            legacy_canonical_id = str(raw.get("canonical_annotation_id") or "")
            rows.append({
                "schema_version": SCHEMA_VERSION,
                "raw_annotation_version_id": f"{raw['stage']}|{raw['project_id']}|{raw['ls_runtime_task_id']}|{raw['worker_id']}|{raw['annotation_id']}",
                "revision_group_id": revision_group_id, "raw_stage": raw["stage"], "stage": stage, "block_index": block,
                "project_id": raw["project_id"], "runtime_task_id": raw["ls_runtime_task_id"], "base_task_id": raw["base_task_id"],
                "raw_condition": raw["condition"], "raw_worker_id": _parse_raw_worker(raw["raw_annotation_json"]),
                "worker_id": discovery.worker(raw["worker_id"]), "raw_annotation_id": raw["annotation_id"],
                "canonical_annotation_id": canonical_id,
                "canonical_annotation_id_legacy_alias": legacy_canonical_id if legacy_canonical_id != canonical_id else "",
                "canonical_join_status": raw["canonical_join_status"],
                "selected_canonical_version": selected, "independent_analysis_unit": selected,
                "raw_only_reason": "superseded_or_noncanonical_raw_version" if not selected else "",
                "version_index_within_task_worker": index, "previous_raw_annotation_id_chronological": previous,
                "parent_annotation": raw.get("parent_annotation", ""), "created_at": raw.get("created_at", ""),
                "updated_at": raw.get("updated_at", ""), "lead_time_seconds": _number(raw.get("lead_time_seconds")),
                "result_count": raw.get("result_count", ""), "result_sha256": _sha_bytes(str(raw.get("result_json") or "")),
                "source_path": raw["source_path"], "source_sha256": raw["source_sha256"],
            })
            previous = str(raw["annotation_id"])
    return rows


def _active_time_row(bundle: Mapping[str, Any]) -> dict[str, Any]:
    spine, sidecar, c1 = bundle["spine"], bundle["sidecar"], bundle["c1_time"]
    stage, block = spine["stage"], int(spine["block_index"])
    if stage == "C1":
        seconds = _number(c1.get("task_worker_active_seconds"))
        eligible_value = c1.get("task_worker_time_analysis_eligible")
        status = str(c1.get("timing_status") or "not_evaluable")
        rule = str(c1.get("timing_rule_version") or "c1_task_worker_active_time_v1")
        source, source_file = "frozen_c1_task_worker_active_time", C1_ACTIVE_TIME.relative_to(ROOT).as_posix()
        event_count, session_count = c1.get("raw_event_count", ""), c1.get("session_count", "")
    elif stage == "C2-A-RP" and block == 2:
        seconds = _number(sidecar.get("active_time_seconds"))
        status = str(sidecar.get("active_time_status") or "not_evaluable")
        eligible_value = seconds is not None and status.lower() not in {"not_evaluable", "ineligible"}
        rule = str(sidecar.get("active_time_script_version") or "frozen_block2_active_time")
        source, source_file = str(sidecar.get("active_time_source_artifact") or ""), str(sidecar.get("active_time_source_artifact") or "")
        event_count, session_count = sidecar.get("active_time_event_count", ""), sidecar.get("active_time_session_count", "")
    else:
        seconds = _number(sidecar.get("upstream_active_time"))
        eligible_value = sidecar.get("upstream_primary_active_time_eligible")
        status = str(sidecar.get("upstream_active_time_match_status") or sidecar.get("upstream_timing_status") or "not_evaluable")
        rule = "frozen_stage_task_worker_active_time"
        source, source_file = str(sidecar.get("upstream_active_time_source") or ""), str(sidecar.get("upstream_active_time_source_file") or "")
        event_count, session_count = sidecar.get("upstream_active_time_event_count", ""), sidecar.get("upstream_active_time_session_count", "")
        if source == "lead_time_fallback":
            seconds = None
    eligibility = _bool_status(eligible_value)
    formal_available = seconds is not None and eligibility == "eligible"
    lead = _number(spine.get("lead_time_seconds"))
    return {
        "schema_version": SCHEMA_VERSION, "canonical_annotation_id": spine["canonical_annotation_id"], "stage": stage,
        "block_index": block, "project_id": spine["project_id"], "runtime_task_id": spine["runtime_task_id"],
        "base_task_id": spine["base_task_id"], "raw_condition": spine["raw_condition"], "worker_id": spine["worker_id"],
        "active_time_seconds": seconds, "active_time_formal_available": formal_available,
        "historical_active_time_eligibility_status": eligibility, "timing_status": status, "timing_rule_version": rule,
        "active_time_source": source, "active_time_source_file": source_file, "active_time_event_count": event_count,
        "active_time_session_count": session_count, "lead_time_seconds": lead,
        "lead_time_status": "available" if lead is not None else "not_evaluable", "lead_time_is_active_time": False,
        "event_fragment_role": "audit_only_never_backfill_active_time",
    }


def _geometry_sha(points: Any) -> str:
    return _sha_bytes(_canonical_json(points))


def _variant_row(
    spine: Mapping[str, Any], *, variant: str, points: list[list[float]], strict: Mapping[str, Any],
    parse_status: str, repair_application_status: str, repair_status: str, algorithm_version: str,
    algorithm_sha256: str, source_role: str, source_path: str, source_sha256: str,
) -> dict[str, Any]:
    count = len(points)
    return {
        "schema_version": SCHEMA_VERSION,
        "geometry_variant_id": f"{spine['canonical_annotation_id']}|{variant}",
        "canonical_annotation_id": spine["canonical_annotation_id"], "stage": spine["stage"], "block_index": spine["block_index"],
        "base_task_id": spine["base_task_id"], "raw_condition": spine["raw_condition"], "worker_id": spine["worker_id"],
        "variant": variant, "points_json": _canonical_json(points), "point_count": count,
        "vertical_boundary_count": count // 2 if count >= 4 and count % 2 == 0 else None,
        "geometry_sha256": _geometry_sha(points), "parse_status": parse_status,
        "geometry_computable": valid_point_ring(points) if variant == "raw" else bool(strict.get("valid")),
        "strict_valid": bool(strict.get("valid")), "strict_reason": str(strict.get("reason") or ""),
        "pairing_method": str(strict.get("pairing_method") or ""), "seam_crossing_detected": bool(strict.get("seam_crossing_detected")),
        "topology_valid": bool(strict.get("topology_valid")), "repair_application_status": repair_application_status,
        "repair_status": repair_status, "algorithm_version": algorithm_version, "algorithm_sha256": algorithm_sha256,
        "source_role": source_role, "source_path": source_path, "source_sha256": source_sha256,
    }


def _build_geometry(
    bundles: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    representation_sha = discovery.sha(Path(normalize_geometry.__code__.co_filename))
    pairwise_sha = discovery.sha(Path(pairwise_similarity.__code__.co_filename))
    variants: list[dict[str, Any]] = []
    calculations: dict[tuple[str, str], tuple[dict[str, Any], list[list[float]], dict[str, Any]]] = {}
    for bundle in bundles:
        spine, raw, sidecar, raw_points = bundle["spine"], bundle["raw"], bundle["sidecar"], bundle["raw_points"]
        strict_raw = normalize_geometry(raw_points)
        raw_row = _variant_row(
            spine, variant="raw", points=raw_points, strict=strict_raw,
            parse_status="parsed" if raw_points else "not_evaluable_no_corner_points",
            repair_application_status="not_applicable", repair_status="raw_preserved",
            algorithm_version=RAW_GEOMETRY_VERSION, algorithm_sha256=raw["source_sha256"], source_role="raw_label_studio_result",
            source_path=raw["source_path"], source_sha256=raw["source_sha256"],
        )
        strict_points = strict_raw.get("canonical_points") or raw_points
        strict_row = _variant_row(
            spine, variant="strict_normalized", points=strict_points, strict=strict_raw,
            parse_status="strict_valid" if strict_raw.get("valid") else "strict_not_evaluable",
            repair_application_status="not_applicable", repair_status="no_repair_attempted",
            algorithm_version=STRICT_GEOMETRY_VERSION, algorithm_sha256=representation_sha,
            source_role="derived_strict_normalization", source_path=Path(normalize_geometry.__code__.co_filename).relative_to(ROOT).as_posix(),
            source_sha256=representation_sha,
        )
        if spine["stage"] == "C1":
            repaired_result = normalize_geometry_for_c1_calculation(raw_points)
            repaired_points = repaired_result.get("canonical_points") or raw_points
            repair_application = "applied" if repaired_result.get("geometry_repair_applied") else "not_applied"
            repair_status = str(repaired_result.get("geometry_repair_status") or "not_evaluable")
            repair_version = str(repaired_result.get("geometry_repair_rule_version") or C1_ORPHAN_POINT_REPAIR_RULE_VERSION)
            repaired_source_role = "derived_c1_geometry_only_repair_variant"
            repaired_source_path = Path(normalize_geometry_for_c1_calculation.__code__.co_filename).relative_to(ROOT).as_posix()
            repaired_source_sha = representation_sha
        else:
            repaired_points = geometry_points(sidecar.get("canonical_geometry") or sidecar.get("corners_px"))
            repaired_result = normalize_geometry(repaired_points)
            repair_application = "not_asserted_historical_canonical_variant"
            repair_status = "frozen_canonical_variant_available" if repaired_points else "frozen_canonical_variant_unavailable"
            repair_version = FROZEN_CANONICAL_VARIANT_VERSION
            repaired_source_role = "frozen_stage_canonical_variant"
            repaired_source_path = CANONICAL_SPINE.relative_to(ROOT).as_posix()
            repaired_source_sha = discovery.sha(CANONICAL_SPINE)
        repaired_row = _variant_row(
            spine, variant="repaired", points=repaired_points, strict=repaired_result,
            parse_status="repaired_variant_valid" if repaired_result.get("valid") else "repaired_variant_not_evaluable",
            repair_application_status=repair_application, repair_status=repair_status, algorithm_version=repair_version,
            algorithm_sha256=representation_sha if spine["stage"] == "C1" else repaired_source_sha,
            source_role=repaired_source_role, source_path=repaired_source_path, source_sha256=repaired_source_sha,
        )
        for row, geometry, points in (
            (raw_row, strict_raw, raw_points), (strict_row, strict_raw, strict_points), (repaired_row, repaired_result, repaired_points),
        ):
            variants.append(row)
            calculations[(spine["canonical_annotation_id"], row["variant"])] = (geometry, points, row)

    pair_rows: list[dict[str, Any]] = []
    groups: dict[tuple[str, int, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in variants:
        groups[(row["stage"], int(row["block_index"]), row["base_task_id"], row["raw_condition"], row["variant"])].append(row)
    for group_key in sorted(groups, key=lambda key: (STAGE_ORDER.get(key[0], 8), key[1], key[2], key[3], key[4])):
        group = sorted(groups[group_key], key=lambda row: (row["worker_id"], row["canonical_annotation_id"]))
        for left, right in combinations(group, 2):
            left_geometry, left_points, _ = calculations[(left["canonical_annotation_id"], left["variant"])]
            right_geometry, right_points, _ = calculations[(right["canonical_annotation_id"], right["variant"])]
            metrics = pairwise_similarity(left_geometry, right_geometry)
            rmse = cyclic_rmse(left_points, right_points)
            pair_rows.append({
                "schema_version": SCHEMA_VERSION,
                "geometry_pair_id": f"{left['geometry_variant_id']}|{right['geometry_variant_id']}",
                "stage": group_key[0], "block_index": group_key[1], "base_task_id": group_key[2],
                "raw_condition": group_key[3], "variant": group_key[4],
                "left_canonical_annotation_id": left["canonical_annotation_id"], "right_canonical_annotation_id": right["canonical_annotation_id"],
                "left_worker_id": left["worker_id"], "right_worker_id": right["worker_id"],
                "left_point_count": left["point_count"], "right_point_count": right["point_count"],
                "cyclic_rmse_diagonal_normalized": rmse, "cyclic_rmse_status": "available" if rmse is not None else "not_evaluable",
                "boundary_similarity": metrics.get("boundary_similarity"), "wallwall_similarity": metrics.get("wallwall_similarity"),
                "metric_compatible": metrics.get("metric_compatible", False),
                "pointwise_correspondence_compatible": metrics.get("pointwise_correspondence_compatible", False),
                "correspondence_status": metrics.get("order_reason", "not_evaluable"),
                "cyclic_correspondence_json": _canonical_json(metrics.get("cyclic_correspondence") or []),
                "alignment_direction": metrics.get("alignment_direction", ""), "alignment_rotation": metrics.get("alignment_rotation", ""),
                "alignment_insertion_count": metrics.get("alignment_insertion_count", 0),
                "alignment_deletion_count": metrics.get("alignment_deletion_count", 0),
                "alignment_ambiguous": metrics.get("alignment_ambiguous", False),
                "pairwise_algorithm_version": "geometry_consensus_pairwise_threshold_free_current", "pairwise_algorithm_sha256": pairwise_sha,
            })
    variants.sort(key=lambda row: (*_stage_key(row), row["variant"]))
    return variants, pair_rows


def _build_meta(bundles: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    long_rows: list[dict[str, Any]] = []
    set_rows: list[dict[str, Any]] = []
    for bundle in bundles:
        spine, raw = bundle["spine"], bundle["raw"]
        grouped: dict[str, list[str]] = defaultdict(list)
        for choice in extract_choice_records(raw["result_json"]):
            field = str(choice["from_name"]).strip().lower()
            if field in {"scope", "difficulty", "model_issue"}:
                grouped[field].append(str(choice["choice_raw"]))
        for field in ("scope", "difficulty", "model_issue"):
            applicable = field != "model_issue" or spine["raw_condition"] == "semi"
            raw_choices = grouped.get(field, []) if applicable else []
            codes = [_choice_code(value) for value in raw_choices]
            negative = NEGATIVE_CODES[field]
            positive_present = any(code not in negative for code in codes)
            negative_present = any(code in negative for code in codes)
            conflict = positive_present and negative_present
            if not applicable:
                state, reason = "not_evaluable", "manual_or_nonsemi_has_no_model_proposal_issue_field"
            elif not codes:
                state, reason = "unasserted", "field_expected_but_no_choice_asserted"
            elif positive_present:
                state, reason = "positive", ""
            else:
                state, reason = "explicit_negative", ""
            timing = "not_time_locked" if field == "model_issue" else "post_task"
            set_id = f"{spine['canonical_annotation_id']}|{field}"
            set_rows.append({
                "schema_version": SCHEMA_VERSION, "meta_response_set_id": set_id,
                "canonical_annotation_id": spine["canonical_annotation_id"], "stage": spine["stage"], "block_index": spine["block_index"],
                "base_task_id": spine["base_task_id"], "raw_condition": spine["raw_condition"], "worker_id": spine["worker_id"],
                "field_name": field, "choice_set_json": _canonical_json(raw_choices), "choice_code_set_json": _canonical_json(codes),
                "response_state": state, "field_applicability": "applicable" if applicable else "structural_not_applicable",
                "contains_positive": positive_present, "contains_explicit_negative": negative_present, "response_conflict": conflict,
                "response_timing_status": timing, "structural_na_reason": reason,
                "source_path": raw["source_path"], "source_sha256": raw["source_sha256"],
            })
            choices = list(zip(raw_choices, codes)) if raw_choices else [("", "")]
            for index, (choice_raw, code) in enumerate(choices, 1):
                choice_state = state if not code else ("explicit_negative" if code in negative else "positive")
                long_rows.append({
                    "schema_version": SCHEMA_VERSION, "meta_response_long_id": f"{set_id}|{index}",
                    "canonical_annotation_id": spine["canonical_annotation_id"], "stage": spine["stage"], "block_index": spine["block_index"],
                    "base_task_id": spine["base_task_id"], "raw_condition": spine["raw_condition"], "worker_id": spine["worker_id"],
                    "field_name": field, "choice_index": index if choice_raw else "", "choice_raw": choice_raw, "choice_code": code,
                    "response_state": choice_state, "field_applicability": "applicable" if applicable else "structural_not_applicable",
                    "response_timing_status": timing, "structural_na_reason": reason, "response_conflict": conflict,
                    "source_path": raw["source_path"], "source_sha256": raw["source_sha256"],
                })
    return long_rows, set_rows


def _parse_initial_points(task_data_json: Any) -> list[list[float]]:
    payload = parse_jsonish(task_data_json) or {}
    try:
        encoded = parse_qs(urlparse(str(payload.get("vis_3d", ""))).query).get("data", [""])[0]
        pairs = json.loads(unquote(encoded))
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    points: list[list[float]] = []
    for pair in sorted(pairs, key=lambda row: float(row["x"])):
        points.extend([[float(pair["x"]), float(pair["y_ceiling"])], [float(pair["x"]), float(pair["y_floor"])]])
    return points


def _build_proposals(
    bundles: list[dict[str, Any]], meta_sets: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    review_rows = discovery.read_csv(REVIEW)
    bundle_by_id: dict[str, dict[str, Any]] = {}
    for item in bundles:
        bundle_by_id[item["spine"]["canonical_annotation_id"]] = item
        legacy_alias = item["spine"]["canonical_annotation_id_legacy_alias"]
        if legacy_alias:
            bundle_by_id[legacy_alias] = item
    model_issue = {
        row["canonical_annotation_id"]: row for row in meta_sets if row["field_name"] == "model_issue"
    }
    review_sha = discovery.sha(REVIEW)
    responses: list[dict[str, Any]] = []
    proposal_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    reference_rows: list[dict[str, Any]] = []
    for review in review_rows:
        review_canonical_id = str(review.get("canonical_annotation_id") or "")
        bundle = bundle_by_id.get(review_canonical_id)
        if bundle is None:
            raise KeyError(f"proposal response canonical identity missing: {review_canonical_id}")
        spine, raw = bundle["spine"], bundle["raw"]
        canonical_id = spine["canonical_annotation_id"]
        if spine["raw_condition"] != "semi":
            raise ValueError(f"proposal response is not Semi: {canonical_id}")
        proposal_id = str(review.get("initialization_artifact_id") or "")
        if not proposal_id:
            raise ValueError(f"proposal identity missing: {canonical_id}")
        initial_points = _parse_initial_points(raw["task_data_json"])
        final_points = bundle["raw_points"]
        issue = model_issue[canonical_id]
        reference_available = discovery.truth(review.get("reference_eligible")) and spine["base_task_id"] != BAD_GT_TASK
        response = {
            "schema_version": SCHEMA_VERSION, "proposal_response_id": f"{proposal_id}|{canonical_id}", "proposal_id": proposal_id,
            "canonical_annotation_id": canonical_id, "stage": spine["stage"], "block_index": spine["block_index"],
            "base_task_id": spine["base_task_id"], "image_id": spine["image_id"], "building_id": spine["building_id"],
            "worker_id": spine["worker_id"], "raw_condition": spine["raw_condition"],
            "initial_points_json": _canonical_json(initial_points), "final_points_json": _canonical_json(final_points),
            "initial_point_count": len(initial_points), "final_point_count": len(final_points),
            "initial_geometry_hash": str(review.get("initial_geometry_hash") or _geometry_sha(initial_points)),
            "final_geometry_hash": str(review.get("final_geometry_hash") or _geometry_sha(final_points)),
            "initial_to_final_rmse_diagonal_normalized": _number(review.get("geometry_edit_rmse_panorama_diagonal_normalized"))
                if _number(review.get("geometry_edit_rmse_panorama_diagonal_normalized")) is not None else cyclic_rmse(initial_points, final_points),
            "topology_changed": len(initial_points) != len(final_points), "exact_geometry_equal": discovery.truth(review.get("exact_geometry_equal")),
            "model_issue_choice_raw": str(review.get("model_issue_choice") or ""),
            "model_issue_choice_set_json": issue["choice_code_set_json"], "model_issue_response_status": issue["response_state"],
            "model_issue_timing_status": "not_time_locked", "U_initial": _number(review.get("U_initial")),
            "U_final": _number(review.get("U_final")), "delta_U": _number(review.get("delta_U")),
            "initial_structurally_valid": discovery.truth(review.get("initial_structurally_valid")),
            "final_structurally_valid": discovery.truth(review.get("final_structurally_valid")),
            "reference_identity": str(review.get("reference_identity") or ""), "reference_sha256": str(review.get("reference_sha256") or ""),
            "reference_type": str(review.get("reference_type") or ""),
            "reference_availability_status": "available" if reference_available else "not_evaluable",
            "historical_formal_assignment_status": _bool_status(review.get("formal_assignment_eligible"), applicable=spine["stage"] != "P1"),
            "historical_analysis_eligibility_status": _bool_status(review.get("analysis_eligible")),
            "source_path": REVIEW.relative_to(ROOT).as_posix(), "source_sha256": review_sha,
        }
        responses.append(response)
        proposal_groups[proposal_id].append({"response": response, "review": review, "initial_points": initial_points})
        for metric in ("U_initial", "U_final", "delta_U"):
            value = response[metric]
            reference_rows.append({
                "schema_version": SCHEMA_VERSION, "reference_measurement_id": f"{canonical_id}|reviewer|{metric}",
                "canonical_annotation_id": canonical_id, "proposal_id": proposal_id, "stage": spine["stage"], "block_index": spine["block_index"],
                "base_task_id": spine["base_task_id"], "worker_id": spine["worker_id"],
                "measurement_role": "proposal_initialization" if metric == "U_initial" else "worker_final" if metric == "U_final" else "initial_to_final_change",
                "metric_name": metric, "raw_metric_value": value, "measurement_value": value if reference_available else None,
                "measurement_status": "available" if value is not None and reference_available else "not_evaluable",
                "reference_identity": response["reference_identity"], "reference_sha256": response["reference_sha256"],
                "reference_type": response["reference_type"], "reference_quality_status": "available" if reference_available else "not_evaluable",
                "historical_eligibility_status": response["historical_analysis_eligibility_status"],
                "source_path": REVIEW.relative_to(ROOT).as_posix(), "source_sha256": review_sha,
            })
    proposals: list[dict[str, Any]] = []
    for proposal_id in sorted(proposal_groups):
        group = proposal_groups[proposal_id]
        first = group[0]
        response, review, initial_points = first["response"], first["review"], first["initial_points"]
        point_hashes = {_geometry_sha(item["initial_points"]) for item in group}
        prediction_hashes = {str(item["review"].get("initialization_prediction_sha256") or "") for item in group}
        prediction_hashes.discard("")
        initial_hashes = {str(item["response"]["initial_geometry_hash"] or "") for item in group}
        if len(prediction_hashes) != 1 or len(initial_hashes) != 1:
            raise ValueError(f"proposal version/geometry provenance conflict: {proposal_id}")
        reference_available = all(item["response"]["reference_availability_status"] == "available" for item in group)
        proposals.append({
            "schema_version": SCHEMA_VERSION, "proposal_id": proposal_id, "stage": response["stage"], "block_index": response["block_index"],
            "base_task_id": response["base_task_id"], "image_id": response["image_id"], "building_id": response["building_id"],
            "initialization_source_kind": str(review.get("trap_source_type") or review.get("frozen_initialization_provenance_status") or ""),
            "initialization_import_sha256_set_json": _unique_json(item["review"].get("initialization_import_sha256") for item in group),
            "initialization_prediction_sha256": next(iter(prediction_hashes)),
            "initial_geometry_hash": response["initial_geometry_hash"], "initial_points_json": _canonical_json(initial_points),
            "initial_point_count": len(initial_points), "initial_geometry_computable": valid_point_ring(initial_points),
            "initial_geometry_consistency_status": "consistent_across_responses" if len(point_hashes) == 1 else "conflict_preserved",
            "planned_trap_family_set_json": _unique_json(item["review"].get("planned_trap_family") for item in group),
            "trap_family_set_json": _unique_json(item["review"].get("trap_family") for item in group),
            "reference_identity_set_json": _unique_json(item["response"]["reference_identity"] for item in group),
            "reference_sha256_set_json": _unique_json(item["response"]["reference_sha256"] for item in group),
            "reference_type_set_json": _unique_json(item["response"]["reference_type"] for item in group),
            "reference_availability_status": "available" if reference_available else "partly_or_not_evaluable",
            "response_count": len(group), "worker_count": len({item["response"]["worker_id"] for item in group}),
            "source_path": REVIEW.relative_to(ROOT).as_posix(), "source_sha256": review_sha,
        })
    responses.sort(key=_stage_key)
    return proposals, responses, reference_rows


def _build_reference_measurements(
    bundles: list[dict[str, Any]], proposal_measurements: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = list(proposal_measurements)
    bundle_by_id: dict[str, dict[str, Any]] = {}
    bundle_by_task_worker: dict[tuple[str, int, str, str, str], dict[str, Any]] = {}
    for item in bundles:
        bundle_by_id[item["spine"]["canonical_annotation_id"]] = item
        spine = item["spine"]
        bundle_by_task_worker[(
            spine["stage"], int(spine["block_index"]), spine["project_id"], spine["runtime_task_id"], spine["worker_id"],
        )] = item
        legacy_alias = item["spine"]["canonical_annotation_id_legacy_alias"]
        if legacy_alias:
            bundle_by_id[legacy_alias] = item
    c1_source_sha = discovery.sha(CANONICAL_SPINE)
    for bundle in bundles:
        spine, sidecar = bundle["spine"], bundle["sidecar"]
        if spine["stage"] != "C1":
            continue
        value = _number(sidecar.get("c1_iou_to_gt"))
        reference_status = str(sidecar.get("c1_gt_reference_status") or "not_evaluable")
        available = value is not None and reference_status.lower() not in {"not_evaluable", "reference_unavailable", "unavailable"}
        rows.append({
            "schema_version": SCHEMA_VERSION, "reference_measurement_id": f"{spine['canonical_annotation_id']}|c1|iou_to_gt",
            "canonical_annotation_id": spine["canonical_annotation_id"], "proposal_id": "", "stage": "C1", "block_index": 0,
            "base_task_id": spine["base_task_id"], "worker_id": spine["worker_id"], "measurement_role": "worker_final",
            "metric_name": "c1_iou_to_gt", "raw_metric_value": value, "measurement_value": value if available else None,
            "measurement_status": "available" if available else "not_evaluable", "reference_identity": str(sidecar.get("c1_gt_source_artifact") or ""),
            "reference_sha256": str(sidecar.get("c1_gt_source_sha256") or ""), "reference_type": "frozen_c1_public_gt",
            "reference_quality_status": reference_status, "historical_eligibility_status": _bool_status(sidecar.get("c1_gt_primary_analysis_eligible")),
            "source_path": CANONICAL_SPINE.relative_to(ROOT).as_posix(), "source_sha256": c1_source_sha,
        })
    terminal_sha = discovery.sha(TERMINAL_REFERENCE)
    for source in discovery.read_csv(TERMINAL_REFERENCE):
        stage, block = _normalise_stage(source.get("evidence_stage"))
        source_canonical_id = str(source.get("canonical_annotation_id") or "")
        bundle = bundle_by_id.get(source_canonical_id) or bundle_by_task_worker.get((
            stage, block, str(source.get("project_id") or ""), str(source.get("runtime_task_id") or ""),
            discovery.worker(source.get("worker_id")),
        ))
        if bundle is None:
            raise KeyError(f"terminal reference canonical identity missing: {source_canonical_id}")
        canonical_id = bundle["spine"]["canonical_annotation_id"]
        base = str(source.get("base_task_id") or source.get("task_id") or bundle["spine"]["base_task_id"])
        raw_value = _number(source.get("quality"))
        bad_gt = base == BAD_GT_TASK
        available = raw_value is not None and not bad_gt
        rows.append({
            "schema_version": SCHEMA_VERSION,
            "reference_measurement_id": f"{canonical_id}|c2|quality",
            "canonical_annotation_id": canonical_id, "proposal_id": "", "stage": stage,
            "block_index": block, "base_task_id": base, "worker_id": discovery.worker(source.get("worker_id")),
            "measurement_role": "worker_final", "metric_name": "c2_reference_quality", "raw_metric_value": raw_value,
            "measurement_value": raw_value if available else None, "measurement_status": "available" if available else "not_evaluable",
            "reference_identity": "c2_reference_registry", "reference_sha256": str(source.get("reference_registry_sha256") or ""),
            "reference_type": "frozen_c2_operational_reference", "reference_quality_status": "researcher_confirmed_bad_gt" if bad_gt else "available",
            "historical_eligibility_status": str(source.get("eligibility_status") or "not_recorded"),
            "source_path": TERMINAL_REFERENCE.relative_to(ROOT).as_posix(), "source_sha256": terminal_sha,
        })
    rows.sort(key=lambda row: (*_stage_key(row), row["measurement_role"], row["metric_name"]))
    return rows


def _build_events(raw_events: list[dict[str, Any]], raw_sessions: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    events: list[dict[str, Any]] = []
    for raw in raw_events:
        stage, block = _normalise_stage(raw.get("event_stage"))
        events.append({
            "schema_version": SCHEMA_VERSION, "raw_event_id": f"{raw['source_path']}#{raw['source_line']}",
            "raw_source_collection": raw.get("source_collection", ""), "raw_event_stage": raw.get("event_stage", ""),
            "stage": stage, "block_index": block, "in_formal_stage_scope": raw.get("in_formal_stage_scope", ""),
            "source_path": raw.get("source_path", ""), "source_sha256": raw.get("source_sha256", ""), "source_line": raw.get("source_line", ""),
            "project_id": str(raw.get("project_id", "")), "runtime_task_id": str(raw.get("task_id", "")),
            "annotator_id": discovery.worker(raw.get("annotator_id", "")), "annotation_id": str(raw.get("annotation_id", "")),
            "session_id": str(raw.get("session_id", "")), "timestamp": raw.get("timestamp", ""),
            "server_received_at": raw.get("server_received_at", ""), "page_type": raw.get("page_type", ""),
            "page_gate_eligible": raw.get("page_gate_eligible", ""), "page_gate_reason": raw.get("page_gate_reason", ""),
            "store_mismatch_present": raw.get("store_mismatch_present", ""), "active_seconds_fragment": raw.get("active_seconds_fragment", ""),
            "active_seconds_fragment_role": "audit_only_never_sum_or_backfill", "raw_event_json": raw.get("raw_event_json", ""),
        })
    sessions: list[dict[str, Any]] = []
    for raw in raw_sessions:
        raw_stages = sorted(set(filter(None, str(raw.get("event_stages") or "").split(";"))))
        normalised = {_normalise_stage(value) for value in raw_stages}
        if len(normalised) == 1:
            stage, block = next(iter(normalised))
        else:
            stage, block = "mixed", 0
        sessions.append({
            "schema_version": SCHEMA_VERSION,
            "active_session_id": f"{raw.get('project_id')}|{raw.get('task_id')}|{raw.get('annotator_id')}|{raw.get('session_id')}",
            "raw_source_collections": raw.get("source_collections", ""), "raw_event_stages": raw.get("event_stages", ""),
            "stage": stage, "block_index": block, "project_id": str(raw.get("project_id", "")),
            "runtime_task_id": str(raw.get("task_id", "")), "annotator_id": discovery.worker(raw.get("annotator_id", "")),
            "session_id": str(raw.get("session_id", "")), "event_count": raw.get("event_count", ""),
            "event_fragment_sum_audit_seconds": raw.get("descriptive_fragment_seconds", ""),
            "session_grouping": raw.get("session_grouping", ""), "primary_active_time_status": raw.get("primary_active_time_status", ""),
        })
    return events, sessions


def _build_registries(
    bundles: list[dict[str, Any]], active_rows: list[dict[str, Any]], reference_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    active_by_id = {row["canonical_annotation_id"]: row for row in active_rows}
    reference_available = Counter(row["canonical_annotation_id"] for row in reference_rows if row["measurement_status"] == "available")
    task_groups: dict[tuple[str, int, str, str], list[dict[str, Any]]] = defaultdict(list)
    image_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for bundle in bundles:
        spine = bundle["spine"]
        task_groups[(spine["stage"], int(spine["block_index"]), spine["base_task_id"], spine["raw_condition"])].append(bundle)
        image_groups[spine["image_id"]].append(bundle)
    contexts: list[dict[str, Any]] = []
    for key in sorted(task_groups, key=lambda value: (STAGE_ORDER.get(value[0], 8), value[1], value[2], value[3])):
        group = task_groups[key]
        spines = [item["spine"] for item in group]
        active = [active_by_id[row["canonical_annotation_id"]] for row in spines]
        contexts.append({
            "schema_version": SCHEMA_VERSION, "task_context_id": _sha_bytes("|".join(map(str, key)))[:24],
            "stage": key[0], "block_index": key[1], "raw_stage_set_json": _unique_json(row["raw_stage"] for row in spines),
            "base_task_id": key[2], "image_id": spines[0]["image_id"], "building_id": spines[0]["building_id"],
            "raw_condition": key[3], "assistance_exposure": spines[0]["assistance_exposure"], "task_lane": spines[0]["task_lane"],
            "scope_status_set_json": _unique_json(row["scope_status"] for row in spines),
            "dataset_group_set_json": _unique_json(row["dataset_group"] for row in spines),
            "task_stratum_set_json": _unique_json(row["task_stratum"] for row in spines),
            "canonical_annotation_count": len(spines), "worker_count": len({row["worker_id"] for row in spines}),
            "worker_ids_json": _unique_json(row["worker_id"] for row in spines),
            "raw_geometry_computable_count": sum(bool(row["raw_geometry_computable"]) for row in spines),
            "lead_time_available_count": sum(row["lead_time_status"] == "available" for row in active),
            "formal_active_time_available_count": sum(bool(row["active_time_formal_available"]) for row in active),
            "reference_measurement_available_count": sum(reference_available[row["canonical_annotation_id"]] > 0 for row in spines),
        })
    images: list[dict[str, Any]] = []
    for image_id in sorted(image_groups):
        group = image_groups[image_id]
        spines = [item["spine"] for item in group]
        image_references = [extract_image_reference(item["raw"]["task_data_json"]) for item in group]
        image_reference = sorted({value for value in image_references if value})[0] if any(image_references) else ""
        context_keys = {(row["stage"], row["block_index"], row["base_task_id"], row["raw_condition"]) for row in spines}
        images.append({
            "schema_version": SCHEMA_VERSION, "image_id": image_id, "base_task_id": spines[0]["base_task_id"],
            "building_id": spines[0]["building_id"], "image_reference": image_reference,
            "image_reference_sha256": _sha_bytes(image_reference) if image_reference else "",
            "stage_set_json": _unique_json(row["stage"] for row in spines),
            "block_index_set_json": _unique_json(row["block_index"] for row in spines),
            "raw_condition_set_json": _unique_json(row["raw_condition"] for row in spines),
            "task_context_count": len(context_keys), "canonical_annotation_count": len(spines),
            "worker_count": len({row["worker_id"] for row in spines}),
            "planned_import_source_paths_json": _unique_json(
                path for row in spines for path in (parse_jsonish(row["planned_import_source_paths_json"]) or [])
            ),
            "raw_export_source_paths_json": _unique_json(row["raw_export_path"] for row in spines),
        })
    return images, contexts


def _source_row(path: Path, role: str, authority: str, *, expected: str = "", note: str = "") -> dict[str, Any]:
    actual = discovery.sha(path)
    return {
        "path": path.relative_to(ROOT).as_posix(), "role": role, "authority": authority, "sha256": actual,
        "expected_sha256": expected, "binding_status": "sha_match" if expected and actual == expected else "sha_mismatch_known_gap" if expected else "current_file_sha_inventory",
        "note": note,
    }


def _build_source_manifest(raw_sources: list[dict[str, Any]], planned_sources: list[dict[str, Any]], c1_summary: Mapping[str, Any]) -> dict[str, Any]:
    closeout = _read_json(C2A_CLOSEOUT)
    expected_precision = str(closeout.get("precision_plan_sha256") or "")
    sources = []
    for source in raw_sources:
        path = Path(source["path"])
        sources.append({
            "path": path.relative_to(ROOT).as_posix(),
            "role": "raw_label_studio_export" if path.suffix.lower() == ".json" else "raw_active_log",
            "authority": "fact_truth", "sha256": source["sha256"], "expected_sha256": "",
            "binding_status": str(source.get("validation") or "current_file_sha_inventory"), "note": str(source.get("binding") or ""),
        })
    sources.extend(planned_sources)
    sources.extend([
        *[
            _source_row(path, f"canonical_selection_authority_{stage.lower().replace('-', '_')}_b{block}", "canonical_selection_provenance")
            for stage, block, path, _runtime_field, _worker_field in CANONICAL_AUTHORITIES
        ],
        _source_row(CANONICAL_SPINE, "legacy_cross_stage_reconciliation_sidecar", "historical_provenance_only"),
        _source_row(REVIEW, "proposal_response_and_reference_provenance", "historical_provenance_only"),
        _source_row(C1_ACTIVE_TIME, "frozen_c1_task_worker_active_time", "historical_provenance_only", expected=str(c1_summary["output_sha256"])),
        _source_row(C1_ACTIVE_TIME_SUMMARY, "frozen_c1_task_worker_active_time_summary", "historical_provenance_only"),
        _source_row(TERMINAL_REFERENCE, "c2_continuous_reference_measurement", "historical_provenance_only", expected=str(closeout.get("risk_slope_evidence_sha256") or "")),
        _source_row(REFERENCE_REVIEW, "reference_quality_review", "historical_provenance_only"),
        _source_row(METHOD_CONTRACT, "method_contract_boundary", "historical_provenance_only", expected=str(closeout.get("method_contract_sha256") or "")),
        _source_row(C2B_ACCEPTANCE, "c2b_historical_evidence_acceptance", "historical_provenance_only"),
        _source_row(C2B_BOUND_CLOSEOUT, "c2b_bound_historical_closeout", "historical_provenance_only", expected=str(_read_json(C2B_ACCEPTANCE)["source_c2b"]["sha256"])),
        _source_row(C2A_CLOSEOUT, "c2a_rp_terminal_closeout", "historical_provenance_only"),
        _source_row(C2A_TERMINAL_DECLARATION, "c2a_rp_terminal_declaration", "historical_provenance_only", expected=str(closeout.get("stage_terminal_declaration_sha256") or "")),
        _source_row(C2A_PRECISION_PLAN, "legacy_precision_plan_not_consumed", "historical_provenance_only", expected=expected_precision,
                    note="known SHA mismatch; precision/risk-slope chain is not consumed as new truth"),
        _source_row(Path(normalize_geometry.__code__.co_filename), "geometry_algorithm", "code_provenance"),
        _source_row(Path(pairwise_similarity.__code__.co_filename), "pairwise_algorithm", "code_provenance"),
        _source_row(WORKBOOK_BUILDER, "optional_workbook_builder", "code_provenance"),
    ])
    deduplicated = {row["path"]: row for row in sources}
    sources = [deduplicated[path] for path in sorted(deduplicated)]
    precision = next(row for row in sources if row["path"] == C2A_PRECISION_PLAN.relative_to(ROOT).as_posix())
    return {
        "schema_version": SCHEMA_VERSION,
        "source_policy": "export_label_active_logs_import_json_fact_truth; SHA-bound derived artifacts only reconcile canonical selection, assignment, timing, and reference provenance",
        "analysis_results_are_not_raw_truth": True,
        "c2b_status": {
            "authority": C2B_ACCEPTANCE.relative_to(ROOT).as_posix(), "collection_closed": True,
            "outcome_reopening_allowed": False, "historical_closeout_candidate_only": True,
        },
        "c2a_rp_status": {
            "authority": C2A_CLOSEOUT.relative_to(ROOT).as_posix(), "stage_closed": True, "dispatch_status": "closed",
            "n_assignments": 80, "n_submissions": 80, "n_workers_target_met": 0, "n_workers_fallback": 20,
        },
        "legacy_precision_dependency_integrity": {
            "status": "known_sha_mismatch_not_consumed", "path": precision["path"],
            "expected_sha256": precision["expected_sha256"], "actual_sha256": precision["sha256"],
        },
        "bad_gt_policy": {
            "base_task_id": BAD_GT_TASK, "peer_geometry_allowed": True, "reference_quality_status": "not_evaluable",
            "historical_numeric_quality_role": "legacy_provenance_only",
        },
        "sources": sources,
    }


def _coverage(
    spine: list[dict[str, Any]], lineage: list[dict[str, Any]], images: list[dict[str, Any]], contexts: list[dict[str, Any]],
    variants: list[dict[str, Any]], proposals: list[dict[str, Any]], responses: list[dict[str, Any]], active: list[dict[str, Any]],
    events: list[dict[str, Any]], sessions: list[dict[str, Any]], meta_long: list[dict[str, Any]], references: list[dict[str, Any]],
    source_manifest: Mapping[str, Any],
) -> list[dict[str, Any]]:
    stage_counts = Counter((row["stage"], int(row["block_index"])) for row in spine)
    raw_only = sum(not row["independent_analysis_unit"] for row in lineage)
    raw_variants = [row for row in variants if row["variant"] == "raw"]
    manual_model_issue = [row for row in meta_long if row["field_name"] == "model_issue" and row["raw_condition"] != "semi"]
    bad_gt_references = [row for row in references if row["base_task_id"] == BAD_GT_TASK]
    checks = [
        ("raw_annotation_versions", len(lineage), 2513, "hard", "raw export versions"),
        ("canonical_annotations", len(spine), 2501, "hard", "selected worker-task records"),
        ("raw_only_versions", raw_only, 12, "hard", "not independent analysis units"),
        ("P1_canonical", stage_counts[("P1", 0)], 1481, "hard", "stage coverage"),
        ("C1_canonical", stage_counts[("C1", 0)], 780, "hard", "stage coverage"),
        ("C2B_canonical", stage_counts[("C2-B", 0)], 160, "hard", "stage coverage"),
        ("C2A_RP_block1_canonical", stage_counts[("C2-A-RP", 1)], 40, "hard", "stage coverage"),
        ("C2A_RP_block2_canonical", stage_counts[("C2-A-RP", 2)], 40, "hard", "stage coverage"),
        ("worker_count", len({row["worker_id"] for row in spine}), 26, "hard", "all observed workers retained"),
        ("image_count", len(images), 214, "hard", "raw base-task/image identity"),
        ("building_count", len({row["building_id"] for row in images}), 22, "hard", "image prefix building identity"),
        ("task_context_count", len(contexts), 270, "hard", "stage x block x condition x task"),
        ("proposal_count", len(proposals), 43, "hard", "unique initialization artifacts"),
        ("proposal_response_count", len(responses), 574, "hard", "canonical Semi responses"),
        ("raw_geometry_computable", sum(bool(row["geometry_computable"]) for row in raw_variants), 2438, "hard", "raw even point rings"),
        ("formal_active_time_available", sum(bool(row["active_time_formal_available"]) for row in active), 2069, "hard", "frozen task-worker active time"),
        ("lead_time_traceable", sum(row["lead_time_status"] == "available" for row in active), 2501, "hard", "kept separate from active time"),
        ("active_event_count", len(events), 34417, "hard", "raw event facts"),
        ("active_session_count", len(sessions), 3735, "hard", "raw session contexts"),
        ("canonical_id_unique", len({row["canonical_annotation_id"] for row in spine}), 2501, "hard", "primary key"),
        ("stage_block_task_worker_unique", len({(row["stage"], row["block_index"], row["runtime_task_id"], row["worker_id"]) for row in spine}), 2501, "hard", "runtime task-worker acquisition key"),
        ("P1_runtime_identity_recovered", sum(row["stage"] == "P1" and bool(row["runtime_task_id"]) for row in spine), 1481, "hard", "raw export runtime task ID"),
        ("manual_model_issue_structural_na", sum(row["response_state"] == "not_evaluable" and row["choice_code"] == "" for row in manual_model_issue), len(manual_model_issue), "hard", "Manual is not acceptable"),
        ("bad_gt_reference_values_suppressed", sum(row["measurement_status"] == "not_evaluable" and row["measurement_value"] in (None, "") for row in bad_gt_references), len(bad_gt_references), "hard", "geometry-only peer use remains allowed"),
    ]
    rows = [{
        "schema_version": SCHEMA_VERSION, "check_name": name, "observed": observed, "expected": expected,
        "status": "pass" if observed == expected else "fail", "scope": scope, "note": note,
    } for name, observed, expected, scope, note in checks]
    planned_matches = sum(row["planned_import_match_status"] != "not_found" for row in spine)
    rows.extend([
        {"schema_version": SCHEMA_VERSION, "check_name": "planned_import_identity_matches", "observed": planned_matches, "expected": len(spine),
         "status": "pass" if planned_matches == len(spine) else "audit", "scope": "provenance", "note": "unmatched rows retain raw runtime task-data identity"},
        {"schema_version": SCHEMA_VERSION, "check_name": "legacy_precision_plan_sha", "observed": source_manifest["legacy_precision_dependency_integrity"]["actual_sha256"],
         "expected": source_manifest["legacy_precision_dependency_integrity"]["expected_sha256"], "status": "known_gap", "scope": "historical_provenance_only",
         "note": "not consumed by the uncertainty substrate"},
    ])
    return rows


FIELD_DESCRIPTIONS = {
    "canonical_annotation_id": "规范选中的标注记录身份；字符串。",
    "raw_annotation_id": "Label Studio 原始 annotation ID；字符串。",
    "stage": "统一阶段：P1、C1、C2-B 或 C2-A-RP。",
    "block_index": "C2-A-RP 独立 block 编号；其他阶段为 0。",
    "raw_condition": "原始条件码，不承担 task lane 或 scope 的复合语义。",
    "assistance_exposure": "是否暴露模型预标注；与 task lane 正交。",
    "task_lane": "任务 lane，如 outside、ordinary、stress、anchor、core。",
    "scope_status": "研究者/计划层 scope 状态；不由 worker 多数票替代。",
    "active_time_seconds": "冻结 task-worker active time；缺失不补零。",
    "lead_time_seconds": "Label Studio lead time；始终与 active time 分列。",
    "response_state": "positive、explicit_negative、unasserted 或 not_evaluable。",
    "measurement_value": "仅在 reference 可用时提供的连续测量值。",
    "raw_metric_value": "历史来源中的原始连续值；reference 不可用时仅作 provenance。",
    "variant": "几何版本：raw、strict_normalized 或 repaired。",
    "geometry_computable": "该版本是否满足本表计算口径；不是历史 eligibility。",
}


def _data_dictionary() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for table, fields in TABLE_SCHEMAS.items():
        for field in fields:
            if field.endswith("_json"):
                data_type = "json_string"
            elif field.endswith("_count") or field in {"block_index", "point_count", "vertical_boundary_count", "size_bytes", "record_count"}:
                data_type = "integer_or_blank"
            elif field.startswith("is_") or field.endswith("_available") or field.endswith("_valid") or field.endswith("_compatible"):
                data_type = "boolean"
            elif any(token in field for token in ("seconds", "rmse", "similarity", "metric_value", "measurement_value", "U_initial", "U_final", "delta_U")):
                data_type = "number_or_blank"
            else:
                data_type = "string"
            rows.append({
                "schema_version": SCHEMA_VERSION, "table_name": table, "field_name": field, "data_type": data_type,
                "description_zh": FIELD_DESCRIPTIONS.get(field, f"{table} 的稳定机器字段 `{field}`。"),
                "missing_semantics_zh": "空值表示源未提供、结构不适用或不可评价；绝不自动解释为 0/false。",
                "source_role": "machine_output_schema",
            })
    return rows


def _readme(counts: Mapping[str, int], precision: Mapping[str, Any]) -> str:
    return f"""# P1–C2-A-RP 不确定性研究中性数据底座 v1

## 用途与边界

本目录是并行的 retrospective 数据底座，不修改 Paper A 方法合同、SAP、C2-B 历史接受决定、C2-A-RP closeout 或既有 v5 审计包。`export_label/`、`active_logs/`、`import_json/` 是事实真源；SHA 绑定历史工件只用于 canonical selection、assignment、active-time 与 reference provenance 对账。

全部 {counts['canonical']:,} 条 canonical worker-task 记录均保留。旧 eligibility 仅作为历史字段，不是全局过滤规则；12 条 raw-only revision 保留版本谱系，但 `independent_analysis_unit=false`。

## 固定覆盖

- raw annotation versions：{counts['raw']:,} = canonical {counts['canonical']:,} + raw-only 12
- worker：26；image：214；building：22；task context：270
- proposal：43；proposal response：574
- raw geometry 可计算：2,438；formal active time 可用：2,069；lead time 可追溯：2,501
- raw active event：34,417；session context：3,735

## 关键语义

- `raw_condition`、`assistance_exposure`、`task_lane`、`scope_status` 正交保存。
- C2-A-RP 统一为单一 stage，并以 `block_index=1/2` 区分。
- `geometry_variants.csv` 分开保存 raw、strict-normalized 与 repaired/frozen-canonical 版本；任何修复不覆盖 raw。
- `geometry_pairwise.csv` 只保存连续、无阈值指标，不生成 cluster、mode 或 entropy 标签。
- Manual 的 Model Issue 是结构性 `not_evaluable`，不是 `acceptable`；历史 Model Issue 统一标为 `not_time_locked`。
- `active_time_seconds` 与 `lead_time_seconds` 永不互填；event fragment 仅作审计。
- 坏 GT 任务 `{BAD_GT_TASK}` 仍可用于 geometry-only 同行分歧，但所有 reference quality 均为 `not_evaluable`。

## 已知完整性缺口

旧 C2-A closeout 期望 Block 2 precision plan SHA `{precision['expected_sha256']}`，当前文件 SHA 为 `{precision['actual_sha256']}`。因此旧 precision/risk-slope 链不能声称完整字节可重放；本底座明确不消费该链为新研究真值。

## 尚未冻结

本底座不冻结单一相似度阈值、cluster/mode、entropy/multimodality、worker 类型、proposal correct/wrong、Manual/Semi 因果效应或跨 stage 效应。后续研究问题与推断单位应在和导师确定方向后另行冻结。
"""


def _workbook_tables(
    coverage: list[dict[str, Any]], contexts: list[dict[str, Any]], dictionary: list[dict[str, Any]], source_manifest: Mapping[str, Any],
) -> list[tuple[str, list[dict[str, Any]]]]:
    explanation = [
        {"项目": "数据定位", "内容": "并行 retrospective 中性事实层；不重开或改写 C2-B/C2-A-RP。"},
        {"项目": "事实真源", "内容": "export_label、active_logs、import_json。"},
        {"项目": "canonical 对账", "内容": "历史 SHA 绑定工件仅用于 selection/assignment/reference provenance。"},
        {"项目": "纳入规则", "内容": "2,501 条 canonical 全部保留；旧 eligibility 仅为历史字段。"},
        {"项目": "几何边界", "内容": "raw/strict/repaired 分版；只输出无阈值连续两两指标。"},
        {"项目": "时间边界", "内容": "active time 与 lead time 分列；event fragment 仅审计。"},
        {"项目": "元标签边界", "内容": "Manual Model Issue=结构性 N/A；历史响应未在编辑前锁定。"},
        {"项目": "未冻结内容", "内容": "threshold、cluster/mode、entropy、多峰、worker 类型、proposal 正误与因果效应。"},
    ]
    coverage_zh = [{"检查项": row["check_name"], "观察值": row["observed"], "期望值": row["expected"], "状态": row["status"], "说明": row["note"]} for row in coverage]
    precision = source_manifest["legacy_precision_dependency_integrity"]
    gaps = [
        {"缺口": "旧 precision plan SHA 不一致", "影响": "旧 precision/risk-slope 链不可声称完整字节重放", "处理": "仅记录 provenance；新底座不消费"},
        {"缺口": "历史 Model Issue 未时间锁定", "影响": "不可解释为编辑前识别能力", "处理": "统一 not_time_locked"},
        {"缺口": "部分 geometry/active time 不可计算", "影响": "对应指标分母减少", "处理": "保持缺失，不补零"},
        {"缺口": "坏 GT 任务", "影响": "reference quality 不可评价", "处理": "保留 geometry-only peer disagreement"},
        {"缺口": "研究方向尚未冻结", "影响": "不能生成 cluster/mode/entropy 真值", "处理": "只输出无阈值事实与连续测量"},
        {"缺口": "precision SHA 详情", "影响": precision["actual_sha256"], "处理": f"expected={precision['expected_sha256']}"},
    ]
    context_zh = [{
        "阶段": row["stage"], "Block": row["block_index"], "图像任务": row["base_task_id"], "原始条件": row["raw_condition"],
        "辅助暴露": row["assistance_exposure"], "任务Lane": row["task_lane"], "标注数": row["canonical_annotation_count"],
        "Worker数": row["worker_count"], "几何可算数": row["raw_geometry_computable_count"], "Active time可用数": row["formal_active_time_available_count"],
    } for row in contexts]
    dictionary_zh = [{
        "机器表": row["table_name"], "英文列名": row["field_name"], "数据类型": row["data_type"],
        "中文解释": row["description_zh"], "缺失语义": row["missing_semantics_zh"],
    } for row in dictionary]
    source_zh = [{
        "路径": row["path"], "角色": row["role"], "权威层级": row["authority"], "当前SHA": row["sha256"],
        "期望SHA": row["expected_sha256"], "绑定状态": row["binding_status"],
    } for row in source_manifest["sources"]]
    return [
        ("说明与边界", explanation), ("覆盖总览", coverage_zh), ("已知缺口", gaps),
        ("任务上下文", context_zh), ("字段字典", dictionary_zh), ("来源SHA", source_zh),
    ]


def _build_workbook(
    delivery: Path, tables: list[tuple[str, list[dict[str, Any]]]], *, node_executable: str, node_modules: Path,
    preview_dir: Path,
) -> dict[str, Any]:
    if not node_executable or not Path(node_executable).is_file():
        raise FileNotFoundError("--node-executable must point to the configured bundled Node executable")
    if not node_modules.is_dir():
        raise FileNotFoundError("--node-modules must point to the configured bundled Node package directory")
    payload_dir = delivery / "_workbook_payload"
    payload_dir.mkdir()
    payload_tables = []
    for index, (name, rows) in enumerate(tables):
        columns = list(rows[0]) if rows else ["状态"]
        fields = [{
            "field": column, "meaning_zh": f"{name}中的{column}", "source_or_formula": "由同次物化的机器表/manifest生成",
            "missing_meaning": "空值表示不可评价或源未提供，不代表零",
        } for column in columns]
        payload_tables.append({
            "name": name, "sheetName": name, "tableName": f"DataTable{index + 1:03d}", "globalIndex": index,
            "spec": {"population": "审阅摘要，不复制2,501行主表", "analysis_unit": "按本sheet行定义", "filter_rule": "不因旧eligibility全局删行",
                     "grouping": "见sheet显式字段", "source": "同次uncertainty_substrate_v1物化", "fields": fields},
            "workbookColumns": columns, "omittedFields": [], "fullRowCount": len(rows), "rowsOmitted": 0, "rows": rows,
        })
    batch = {"tables": payload_tables, "xlsx_long_field_policy": "小型中文审阅工作簿；完整机器表保留在CSV"}
    batch_text = json.dumps(batch, ensure_ascii=False, separators=(",", ":")) + "\n"
    (payload_dir / "batch_001.json").write_text(batch_text, encoding="utf-8", newline="\n")
    _write_json(payload_dir / "manifest.json", {
        "format": "uncertainty_substrate_v1_compact_workbook_payload", "table_count": 6, "start_index": 0,
        "row_count": sum(len(rows) for _, rows in tables),
        "batches": [{"file": "batch_001.json", "table_count": 6, "size_bytes": len(batch_text.encode("utf-8"))}],
    })
    workbook = delivery / "不确定性数据底座审阅工作簿.xlsx"
    env = os.environ.copy()
    env["NODE_PATH"] = str(node_modules.resolve())
    result = subprocess.run(
        [node_executable, "--max-old-space-size=8192", str(WORKBOOK_BUILDER), str(payload_dir), str(workbook), str(preview_dir)],
        cwd=ROOT, env=env, check=True, capture_output=True, text=True, encoding="utf-8",
    )
    qa_path = preview_dir / "qa.json"
    qa = _read_json(qa_path)
    preview_files = sorted(preview_dir.glob("*.png"))
    if len(preview_files) != 6 or int(qa.get("tableCount", 0)) != 6:
        raise AssertionError("workbook did not render all six sheets")
    with zipfile.ZipFile(workbook) as archive:
        workbook_xml = archive.read("xl/workbook.xml").decode("utf-8")
        sheet_names = re.findall(r'<(?:\w+:)?sheet\b[^>]*\bname="([^"]+)"', workbook_xml)
        text_parts = [archive.read(name).decode("utf-8", errors="ignore") for name in archive.namelist() if name.startswith("xl/") and name.endswith(".xml")]
    error_tokens = sorted({token for token in ("#REF!", "#DIV/0!", "#VALUE!", "#NAME?", "#N/A") if any(token in part for part in text_parts)})
    if sheet_names != [name for name, _ in tables] or error_tokens:
        raise AssertionError({"sheet_names": sheet_names, "formula_error_tokens": error_tokens})
    shutil.rmtree(payload_dir)
    return {
        "status": "pass", "sheet_names": sheet_names, "preview_count": len(preview_files),
        "formula_inspection": "pass_no_formulas", "formula_error_tokens": error_tokens,
        "builder_stdout": result.stdout.strip(), "workbook_sha256": discovery.sha(workbook),
    }


def _output_manifest(delivery: Path) -> list[dict[str, Any]]:
    rows = []
    for path in sorted(item for item in delivery.rglob("*") if item.is_file() and item.name != "OUTPUT_MANIFEST.csv"):
        record_count: int | str = ""
        if path.suffix.lower() == ".csv":
            with path.open(encoding="utf-8-sig", newline="") as handle:
                record_count = max(0, sum(1 for _ in handle) - 1)
        rows.append({
            "schema_version": SCHEMA_VERSION, "path": path.relative_to(delivery).as_posix(), "size_bytes": path.stat().st_size,
            "record_count": record_count, "sha256": discovery.sha(path),
        })
    return rows


def materialize(
    output_dir: Path = DEFAULT_OUTPUT, *, build_workbook: bool = False, node_executable: str = "",
    node_modules: Path | None = None, workbook_preview_dir: Path | None = None,
) -> dict[str, Any]:
    target = output_dir.resolve()
    if target.exists():
        raise FileExistsError(f"refusing to overwrite existing uncertainty substrate freeze: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{target.name}_", dir=target.parent))
    try:
        delivery = staging / "delivery"
        delivery.mkdir()
        planned_index, planned_sources = _load_planned_import_index()
        submissions = discovery.read_csv(CANONICAL_SPINE)
        raw_annotations, raw_events, raw_sessions, _raw_ledger, raw_sources = discovery.materialize_raw(submissions)
        c1_time, c1_summary = _load_c1_active_time()
        canonical_authority, canonical_by_task_worker = _load_canonical_authority()
        bundles = _build_bundles(submissions, raw_annotations, planned_index, c1_time, canonical_authority)
        spine = [bundle["spine"] for bundle in bundles]
        lineage = _build_lineage(raw_annotations, canonical_by_task_worker)
        active = [_active_time_row(bundle) for bundle in bundles]
        variants, pairwise = _build_geometry(bundles)
        meta_long, meta_sets = _build_meta(bundles)
        proposals, responses, proposal_measurements = _build_proposals(bundles, meta_sets)
        references = _build_reference_measurements(bundles, proposal_measurements)
        events, sessions = _build_events(raw_events, raw_sessions)
        images, contexts = _build_registries(bundles, active, references)
        source_manifest = _build_source_manifest(raw_sources, planned_sources, c1_summary)
        coverage = _coverage(
            spine, lineage, images, contexts, variants, proposals, responses, active, events, sessions, meta_long, references, source_manifest,
        )
        failures = [row for row in coverage if row["status"] == "fail"]
        if failures:
            raise AssertionError({"coverage_failures": failures})
        dictionary = _data_dictionary()
        frames = {
            "annotation_spine.csv": spine, "annotation_version_lineage.csv": lineage, "image_registry.csv": images,
            "task_context_master.csv": contexts, "geometry_variants.csv": variants, "geometry_pairwise.csv": pairwise,
            "meta_response_long.csv": meta_long, "meta_response_set.csv": meta_sets, "proposal_fact.csv": proposals,
            "proposal_response.csv": responses, "reference_measurement.csv": references, "active_time_context.csv": active,
            "active_event_fact.csv": events, "active_session_fact.csv": sessions, "DATA_DICTIONARY.csv": dictionary,
            "COVERAGE_AUDIT.csv": coverage,
        }
        for name, rows in frames.items():
            _write_csv(delivery / name, rows, TABLE_SCHEMAS[name])
        _write_json(delivery / "SOURCE_MANIFEST.json", source_manifest)
        workbook_qa: dict[str, Any] = {"status": "not_requested"}
        preview_dir = workbook_preview_dir.resolve() if workbook_preview_dir else staging / "_workbook_previews"
        if build_workbook:
            workbook_qa = _build_workbook(
                delivery, _workbook_tables(coverage, contexts, dictionary, source_manifest),
                node_executable=node_executable, node_modules=node_modules or Path(""), preview_dir=preview_dir,
            )
        precision = source_manifest["legacy_precision_dependency_integrity"]
        qa_summary = {
            "schema_version": SCHEMA_VERSION, "status": "pass_with_known_gaps", "hard_check_failures": [],
            "coverage_check_count": len(coverage), "hard_check_pass_count": sum(row["status"] == "pass" for row in coverage),
            "known_gaps": [
                "legacy_c2a_precision_plan_sha_mismatch_not_consumed",
                "historical_model_issue_not_time_locked",
                "bad_gt_reference_quality_not_evaluable",
                "missing_geometry_and_active_time_remain_missing",
            ],
            "frozen_boundaries": [
                "C2-B remains closed through normative historical-evidence acceptance",
                "C2-A-RP remains closed after Block 2",
                "no threshold, cluster, mode, entropy, worker type, proposal correctness, or causal effect is frozen",
            ],
            "legacy_precision_dependency_integrity": precision, "workbook": workbook_qa,
        }
        _write_json(delivery / "QA_SUMMARY.json", qa_summary)
        counts = {"raw": len(lineage), "canonical": len(spine)}
        (delivery / "README_ZH.md").write_text(_readme(counts, precision), encoding="utf-8", newline="\n")
        _write_csv(delivery / "OUTPUT_MANIFEST.csv", _output_manifest(delivery), OUTPUT_MANIFEST_FIELDS)
        if target.exists():
            raise FileExistsError(f"refusing to overwrite concurrently created uncertainty substrate freeze: {target}")
        delivery.replace(target)
        return {
            "schema_version": SCHEMA_VERSION, "output_dir": str(target), "raw_annotation_versions": len(lineage),
            "canonical_annotations": len(spine), "image_count": len(images), "task_context_count": len(contexts),
            "proposal_count": len(proposals), "proposal_response_count": len(responses),
            "raw_geometry_computable": int(sum(row["variant"] == "raw" and bool(row["geometry_computable"]) for row in variants)),
            "formal_active_time_available": int(sum(bool(row["active_time_formal_available"]) for row in active)),
            "lead_time_traceable": int(sum(row["lead_time_status"] == "available" for row in active)),
            "workbook_status": workbook_qa["status"], "qa_status": qa_summary["status"],
        }
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--build-workbook", action="store_true")
    parser.add_argument("--node-executable", default="")
    parser.add_argument("--node-modules", type=Path)
    parser.add_argument("--workbook-preview-dir", type=Path)
    args = parser.parse_args()
    result = materialize(
        args.output_dir, build_workbook=args.build_workbook, node_executable=args.node_executable,
        node_modules=args.node_modules, workbook_preview_dir=args.workbook_preview_dir,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
