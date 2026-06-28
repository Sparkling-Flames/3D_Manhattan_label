from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.thesis_main.analysis.analyze_quality import extract_data, parse_quality_flags_v2

DEFAULT_CANONICAL = Path("analysis_results/prescreen_closeout/prescreen_canonical_annotations.csv")
DEFAULT_FINAL_GOLD = Path("analysis_results/final_gold_layer_20260325/final_gold_records_v1.jsonl")
DEFAULT_COMPLETION = Path("analysis_results/prescreen_closeout/prescreen_completion_audit.csv")
DEFAULT_UNKNOWN_GOLD_ALLOWLIST = Path("analysis_results/prescreen_closeout/prescreen_scope_unknown_gold_allowlist.csv")
DEFAULT_SYNTHETIC_BANK = Path("analysis_results/trap_collection_freeze_20260320/semi_synthetic_disjoint_candidate_bank_v2.jsonl")
DEFAULT_SYNTHETIC_EXPERT_REVIEW = Path("analysis_results/prescreen_closeout/prescreen_synthetic_expert_review.csv")
DEFAULT_EXPORT_GT = Path("export_label/groudTruth.json")
DEFAULT_RAW_INPUT_MANIFEST = Path("analysis_results/prescreen_closeout/raw_inputs/raw_input_snapshot_manifest.csv")
DEFAULT_OUTPUT_DIR = Path("analysis_results/prescreen_closeout")

TASK_FIELDS = [
    "task_id",
    "project_id",
    "dataset_group",
    "condition",
    "image_id",
    "data_title",
    "task_final_scope",
    "task_scope_adjudication_source",
    "final_gold_scope",
    "final_gold_ref",
    "worker_scope_values_seen",
    "n_worker_in_scope",
    "n_worker_oos",
    "n_worker_scope_missing",
    "mixed_scope_flag",
    "unresolved_scope_flag",
    "geometry_primary_possible",
    "notes",
]

RESPONSE_FIELDS = [
    "annotator_id",
    "language",
    "completion_status",
    "eligible_for_primary_prescreen_candidate",
    "project_id",
    "task_id",
    "dataset_group",
    "condition",
    "worker_scope_raw",
    "worker_scope_normalized",
    "task_final_scope",
    "task_scope_adjudication_source",
    "worker_scope_response",
    "geometry_valid_or_present",
    "geometry_primary_possible",
    "scope_response_primary_eligible",
    "notes",
]

UNKNOWN_GOLD_FIELDS = [
    "project_id",
    "task_id",
    "dataset_group",
    "condition",
    "image_id",
    "data_title",
    "expected_final_gold_key",
    "match_failure_reason",
    "allowlisted",
    "allowlist_reason",
]

MIXED_TASK_FIELDS = [
    "project_id",
    "task_id",
    "dataset_group",
    "condition",
    "image_id",
    "data_title",
    "task_final_scope",
    "task_scope_adjudication_source",
    "worker_scope_values_seen",
    "n_worker_in_scope",
    "n_worker_oos",
    "n_worker_scope_missing",
    "geometry_primary_possible",
]

WORKER_SCOPE_FIELDS = [
    "annotator_id",
    "language",
    "completion_status",
    "n_correct_in_scope",
    "n_correct_oos",
    "n_scope_false_positive",
    "n_scope_false_negative",
    "n_unknown_or_missing",
    "n_not_applicable_unresolved",
    "scope_accuracy_on_adjudicated_tasks",
]

SYNTHETIC_BINDING_FIELDS = [
    "runtime_task_id",
    "project_id",
    "language",
    "dataset_group",
    "condition",
    "image_id",
    "data_title",
    "base_image_key",
    "synthetic_candidate_id",
    "source_base_task_id",
    "source_title",
    "synthetic_family",
    "synthetic_source_type",
    "matched_synthetic_bank_row",
    "matched_source_final_gold_task_id",
    "matched_source_final_scope",
    "scope_binding_status",
    "scope_gold_source",
    "task_final_scope_after_binding",
    "task_scope_adjudication_source_after_binding",
    "primary_eligible_after_binding",
    "geometry_gold_source_after_binding",
    "geometry_gold_ready_after_binding",
    "geometry_scoring_deferred_after_binding",
    "geometry_scoring_role",
    "manual_anchor_role",
    "manual_anchor_primary_possible",
    "expert_realized_model_issue_primary",
    "expert_realized_model_issue_secondary",
    "trap_effective",
    "planned_realized_mismatch",
    "notes",
]

SYNTHETIC_EXPERT_REVIEW_FIELDS = [
    "runtime_task_id",
    "mirror_task_id",
    "base_image_key",
    "planned_synthetic_family",
    "expert_final_scope",
    "scope_gold_ready",
    "expert_realized_model_issue_primary",
    "expert_realized_model_issue_secondary",
    "trap_effective",
    "planned_realized_mismatch",
    "operator_validity_note",
]

SYNTHETIC_GEOMETRY_GT_FIELDS = [
    "runtime_task_id",
    "mirror_task_id",
    "project_id",
    "language",
    "base_image_key",
    "synthetic_candidate_id",
    "source_base_task_id",
    "planned_synthetic_family",
    "scope_gold_source",
    "expert_final_scope",
    "scope_gold_ready",
    "geometry_gold_source",
    "geometry_gold_task_id",
    "geometry_gold_annotation_count",
    "geometry_gold_ready",
    "geometry_binding_status",
    "task_scope_adjudication_source",
    "task_geometry_adjudication_source",
    "geometry_primary_possible",
    "geometry_scoring_deferred",
    "geometry_scoring_role",
    "manual_anchor_role",
    "manual_anchor_primary_possible",
    "notes",
]

ALLOWED_OOS = {"oos_geometry", "oos_open_boundary", "oos_split_level", "oos_insufficient"}
UNRESOLVED_SCOPES = {"unresolved_mixed", "unknown_gold", "audit_only", "synthetic_scope_unresolved"}
GEOMETRY_SCORE_FIELD_NAMES = {
    "geometry_score",
    "geometry_iou",
    "corner_error",
    "layout_score",
    "primary_geometry_score",
}


def _safe(value: Any) -> str:
    return str(value or "").strip()


def _load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _load_completion(path: Path | None) -> dict[str, dict[str, str]]:
    if not path or not path.exists():
        return {}
    return {row["annotator_id"]: row for row in _load_csv(path)}


def _load_final_gold(path: Path) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            for key in ("task_id", "base_task_id"):
                value = _safe(rec.get(key))
                if value:
                    index[f"{key}:{value}"] = rec
    return index


def _load_synthetic_bank(path: Path | None) -> dict[str, dict[str, Any]]:
    if not path or not path.exists():
        return {}
    out: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            cid = _safe(rec.get("candidate_id"))
            if cid:
                out[cid] = rec
    return out


def _load_synthetic_expert_review(path: Path | None) -> dict[str, dict[str, str]]:
    if not path or not path.exists():
        return {}
    out: dict[str, dict[str, str]] = {}
    for row in _load_csv(path):
        for key_name in ("runtime_task_id", "mirror_task_id"):
            task_id = _safe(row.get(key_name))
            if task_id:
                out[task_id] = row
    return out


def _load_export_gt_by_title(path: Path | None) -> dict[str, list[dict[str, Any]]]:
    if not path or not path.exists():
        return {}
    rows = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for task in rows:
        title = _safe((task.get("data") or {}).get("title"))
        if title:
            out[Path(title).stem].append(task)
    return out


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _validate_export_gt_manifest(manifest_path: Path | None, export_gt_path: Path | None) -> tuple[Path | None, dict[str, Any]]:
    if not manifest_path or not export_gt_path:
        return export_gt_path, {}
    rows = _load_csv(manifest_path)
    norm_export = _norm_manifest_path(export_gt_path)
    matches = [row for row in rows if _norm_manifest_path(_safe(row.get("source_path"))) == norm_export]
    if len(matches) != 1:
        raise ValueError(f"expected one raw input manifest row for {export_gt_path}, found {len(matches)}")
    row = matches[0]
    snapshot = _manifest_path(_safe(row.get("snapshot_path")))
    sha = _safe(row.get("sha256")).lower()
    if not snapshot.exists():
        raise ValueError(f"manifest snapshot does not exist for {export_gt_path}: {snapshot}")
    if not sha:
        raise ValueError(f"manifest sha256 missing for {export_gt_path}")
    actual = _sha256(snapshot)
    if actual.lower() != sha:
        raise ValueError(f"manifest sha256 mismatch for {export_gt_path}: {sha} != {actual}")
    evidence: dict[str, Any] = {"export_gt_snapshot_path": str(snapshot), "export_gt_sha256": actual}
    source = _manifest_path(_safe(row.get("source_path")))
    if source.exists():
        source_sha = _sha256(source)
        evidence["export_gt_source_sha256"] = source_sha
        evidence["export_gt_source_snapshot_sha256_match"] = source_sha.lower() == actual.lower()
    return snapshot, evidence


def _manifest_path(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else _PROJECT_ROOT / p


def _norm_manifest_path(path: str | Path) -> str:
    return str(_manifest_path(path)).replace("/", "\\").lower()


def _synthetic_geometry_gt_rows(
    synthetic_rows: list[dict[str, Any]],
    synthetic_expert_review: dict[str, dict[str, str]],
    export_gt_by_title: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in synthetic_rows:
        base_key = _safe(row.get("source_base_task_id") or row.get("base_image_key"))
        matches = export_gt_by_title.get(base_key, [])
        ann_count = len(matches[0].get("annotations") or []) if len(matches) == 1 else ""
        ready = len(matches) == 1 and ann_count == 1
        if not matches:
            status = "missing_export_gt"
        elif len(matches) > 1:
            status = "duplicate_export_gt"
        elif ann_count != 1:
            status = "invalid_annotation_count"
        else:
            status = "synthetic_geometry_bound_to_export_gt"
        review = synthetic_expert_review.get(_safe(row.get("runtime_task_id")), {})
        runtime_task_id = _safe(row.get("runtime_task_id"))
        mirror_task_id = _safe(review.get("mirror_task_id"))
        if runtime_task_id == mirror_task_id:
            mirror_task_id = _safe(review.get("runtime_task_id"))
        out.append(
            {
                "runtime_task_id": runtime_task_id,
                "mirror_task_id": mirror_task_id,
                "project_id": row.get("project_id", ""),
                "language": row.get("language", ""),
                "base_image_key": base_key,
                "synthetic_candidate_id": row.get("synthetic_candidate_id", ""),
                "source_base_task_id": row.get("source_base_task_id", ""),
                "planned_synthetic_family": row.get("synthetic_family", ""),
                "scope_gold_source": row.get("scope_gold_source", ""),
                "expert_final_scope": _safe(review.get("expert_final_scope")) or row.get("task_final_scope_after_binding", ""),
                "scope_gold_ready": _safe(review.get("scope_gold_ready")),
                "geometry_gold_source": "export_label_groudTruth" if ready else "",
                "geometry_gold_task_id": matches[0].get("id", "") if len(matches) == 1 else "",
                "geometry_gold_annotation_count": ann_count,
                "geometry_gold_ready": ready,
                "geometry_binding_status": status,
                "task_scope_adjudication_source": row.get("task_scope_adjudication_source_after_binding", ""),
                "task_geometry_adjudication_source": "export_label_groudTruth" if ready else "",
                "geometry_primary_possible": False,
                "geometry_scoring_deferred": ready,
                "geometry_scoring_role": "semi_trap_audit" if ready else "",
                "manual_anchor_role": False,
                "manual_anchor_primary_possible": False,
                "notes": "geometry GT bound; primary geometry scoring deferred to Step 5" if ready else "geometry GT not uniquely ready",
            }
        )
    return out


def _load_unknown_gold_allowlist(path: Path | None) -> dict[tuple[str, str], str]:
    if not path or not path.exists():
        return {}
    rows = _load_csv(path)
    return {
        (_safe(row.get("project_id")), _safe(row.get("task_id"))): _safe(row.get("reason") or row.get("allowlist_reason"))
        for row in rows
        if _safe(row.get("project_id")) and _safe(row.get("task_id"))
    }


def _normalize_task_scope(alias: str, binary: str = "") -> str:
    text = _safe(alias).lower()
    binary = _safe(binary).lower()
    if "undercoverage" in text or "minimal" in text or "minimal-space" in text:
        return "in_scope"
    if text in {"normal", "in_scope", "inscope", "in-scope"} or binary == "in_scope":
        return "in_scope"
    if text in ALLOWED_OOS:
        return text
    if binary == "oos":
        return "oos_geometry"
    if text == "audit_only":
        return "audit_only"
    return "unknown_gold"


def _is_oos_scope(scope: str) -> bool:
    return scope in ALLOWED_OOS


def _geometry_possible(scope: str) -> bool:
    return scope == "in_scope"


def _load_export_details(canonical_rows: list[dict[str, str]]) -> tuple[dict[tuple[str, str, str], dict[str, Any]], dict[tuple[str, str, str, str], dict[str, Any]]]:
    task_index: dict[tuple[str, str, str], dict[str, Any]] = {}
    ann_index: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for export_path_text in sorted({_safe(row.get("source_export")) for row in canonical_rows if _safe(row.get("source_export"))}):
        export_path = Path(export_path_text)
        with export_path.open("r", encoding="utf-8") as f:
            tasks = json.load(f)
        for task in tasks:
            project_id = _safe(task.get("project") or task.get("project_id"))
            task_id = _safe(task.get("id") or task.get("task_id"))
            key = (export_path_text, project_id, task_id)
            task_index[key] = task
            for idx, ann in enumerate(task.get("annotations") or [], start=1):
                ann_id = _safe(ann.get("id")) or f"annotation_index_{idx}"
                ann_index[(export_path_text, project_id, task_id, ann_id)] = ann
    return task_index, ann_index


def _task_data(task: dict[str, Any] | None) -> dict[str, Any]:
    data = (task or {}).get("data")
    return data if isinstance(data, dict) else {}


def _final_gold_for(data: dict[str, Any], final_gold: dict[str, dict[str, Any]]) -> tuple[dict[str, Any] | None, str]:
    for key_name in ("task_id", "base_task_id"):
        value = _safe(data.get(key_name))
        if value:
            rec = final_gold.get(f"{key_name}:{value}")
            if rec:
                return rec, f"{key_name}:{value}"
    return None, ""


def _expected_gold_key(data: dict[str, Any]) -> str:
    keys = []
    for key_name in ("task_id", "base_task_id"):
        value = _safe(data.get(key_name))
        if value:
            keys.append(f"{key_name}:{value}")
    return ";".join(keys)


def _synthetic_candidate_id(data: dict[str, Any]) -> str:
    explicit = _safe(data.get("synthetic_candidate_id"))
    if explicit:
        return explicit
    task_id = _safe(data.get("task_id"))
    if task_id.startswith("synthetic::"):
        return task_id.split("synthetic::", 1)[1]
    return ""


def _is_synthetic_trap(data: dict[str, Any]) -> bool:
    if _safe(data.get("dataset_group")).lower() != "prescreen_semi":
        return False
    if _synthetic_candidate_id(data):
        return True
    return (
        _safe(data.get("source_type")).lower() == "trap_synthetic"
        or _safe(data.get("proposal_source_kind")).lower() == "frozen_synthetic_asset"
    )


def _language_from_project(project_id: str) -> str:
    if project_id in {"28", "29", "30"}:
        return "zh"
    if project_id in {"39", "40", "41"}:
        return "en"
    return ""


def _synthetic_scope_binding(
    *,
    project_id: str,
    runtime_task_id: str,
    data: dict[str, Any],
    synthetic_bank: dict[str, dict[str, Any]],
    synthetic_expert_review: dict[str, dict[str, str]],
    final_gold_index: dict[str, dict[str, Any]],
) -> tuple[str, str, str, str, str, dict[str, Any] | None]:
    if not _is_synthetic_trap(data):
        return "", "", "", "", "", None
    candidate_id = _synthetic_candidate_id(data)
    bank_row = synthetic_bank.get(candidate_id)
    base_image_key = _safe(data.get("base_task_id"))
    if not bank_row:
        audit = _synthetic_audit_row(
            project_id=project_id,
            runtime_task_id=runtime_task_id,
            data=data,
            candidate_id=candidate_id,
            bank_row=None,
            source_gold=None,
            status="synthetic_bank_missing",
            final_scope="synthetic_scope_unresolved",
            source="synthetic_asset_unmatched",
            notes="synthetic candidate missing from bank",
        )
        return "synthetic_scope_unresolved", "synthetic_asset_unmatched", "", "", "synthetic candidate missing from bank", audit
    source_base_task_id = _safe(bank_row.get("source_base_task_id"))
    source_gold = final_gold_index.get(f"base_task_id:{source_base_task_id}") if source_base_task_id else None
    expert_review = synthetic_expert_review.get(runtime_task_id)
    if source_gold:
        raw_scope = _safe(source_gold.get("final_scope_alias") or source_gold.get("final_scope_binary"))
        final_scope = _normalize_task_scope(raw_scope, _safe(source_gold.get("final_scope_binary")))
        audit = _synthetic_audit_row(
            project_id=project_id,
            runtime_task_id=runtime_task_id,
            data=data,
            candidate_id=candidate_id,
            bank_row=bank_row,
            source_gold=source_gold,
            status="synthetic_bound_to_source_gold",
            final_scope=final_scope,
            source="synthetic_asset_source_gold",
            notes="synthetic source bound to final_gold by source_base_task_id",
        )
        return final_scope, "synthetic_asset_source_gold", raw_scope, f"base_task_id:{source_base_task_id}", "", audit
    if expert_review and _safe(expert_review.get("scope_gold_ready")).lower() == "true":
        raw_scope = _safe(expert_review.get("expert_final_scope"))
        final_scope = _normalize_task_scope(raw_scope)
        audit = _synthetic_audit_row(
            project_id=project_id,
            runtime_task_id=runtime_task_id,
            data=data,
            candidate_id=candidate_id,
            bank_row=bank_row,
            source_gold=None,
            status="synthetic_bound_by_expert_scope_review",
            final_scope=final_scope,
            source="synthetic_asset_expert_review",
            notes=_safe(expert_review.get("operator_validity_note")),
            expert_review=expert_review,
        )
        return (
            final_scope,
            "synthetic_asset_expert_review",
            raw_scope,
            f"synthetic_expert_review:{runtime_task_id}",
            "synthetic expert review resolves scope; source geometry GT is bound in synthetic geometry audit; primary geometry scoring deferred to Step 5",
            audit,
        )
    audit = _synthetic_audit_row(
        project_id=project_id,
        runtime_task_id=runtime_task_id,
        data=data,
        candidate_id=candidate_id,
        bank_row=bank_row,
        source_gold=None,
        status="synthetic_bank_matched_source_gold_missing",
        final_scope="synthetic_scope_unresolved",
        source="synthetic_asset_bank_no_source_gold",
        notes="synthetic bank matched but source_base_task_id has no final_gold record",
    )
    return (
        "synthetic_scope_unresolved",
        "synthetic_asset_bank_no_source_gold",
        "",
        f"base_task_id:{source_base_task_id}",
        "synthetic bank matched but source final_gold missing",
        audit,
    )


def _synthetic_audit_row(
    *,
    project_id: str,
    runtime_task_id: str,
    data: dict[str, Any],
    candidate_id: str,
    bank_row: dict[str, Any] | None,
    source_gold: dict[str, Any] | None,
    status: str,
    final_scope: str,
    source: str,
    notes: str,
    expert_review: dict[str, str] | None = None,
) -> dict[str, Any]:
    source_base_task_id = _safe((bank_row or {}).get("source_base_task_id"))
    source_scope = _safe((source_gold or {}).get("final_scope_alias") or (source_gold or {}).get("final_scope_binary"))
    return {
        "runtime_task_id": runtime_task_id,
        "project_id": project_id,
        "language": _language_from_project(project_id),
        "dataset_group": _safe(data.get("dataset_group")),
        "condition": _safe(data.get("condition")),
        "image_id": _safe(data.get("base_task_id")),
        "data_title": _safe(data.get("title")),
        "base_image_key": source_base_task_id or _safe(data.get("base_task_id")),
        "synthetic_candidate_id": candidate_id,
        "source_base_task_id": source_base_task_id,
        "source_title": _safe((bank_row or {}).get("source_title")),
        "synthetic_family": _safe((bank_row or {}).get("family") or data.get("trap_family")),
        "synthetic_source_type": _safe(data.get("source_type") or (bank_row or {}).get("source_type") or "trap_synthetic"),
        "matched_synthetic_bank_row": bool(bank_row),
        "matched_source_final_gold_task_id": _safe((source_gold or {}).get("task_id")),
        "matched_source_final_scope": source_scope,
        "scope_binding_status": status,
        "task_final_scope_after_binding": final_scope,
        "task_scope_adjudication_source_after_binding": source,
        "scope_gold_source": "prescreen_synthetic_expert_review" if source == "synthetic_asset_expert_review" else source,
        "primary_eligible_after_binding": _geometry_possible(final_scope) and source != "synthetic_asset_expert_review",
        "geometry_gold_source_after_binding": "",
        "geometry_gold_ready_after_binding": source != "synthetic_asset_expert_review" and _geometry_possible(final_scope),
        "geometry_scoring_deferred_after_binding": False,
        "geometry_scoring_role": "semi_trap_audit" if source == "synthetic_asset_expert_review" else "",
        "manual_anchor_role": False,
        "manual_anchor_primary_possible": False,
        "expert_realized_model_issue_primary": _safe((expert_review or {}).get("expert_realized_model_issue_primary")),
        "expert_realized_model_issue_secondary": _safe((expert_review or {}).get("expert_realized_model_issue_secondary")),
        "trap_effective": _safe((expert_review or {}).get("trap_effective")),
        "planned_realized_mismatch": _safe((expert_review or {}).get("planned_realized_mismatch")),
        "notes": notes,
    }


def _task_scope(data: dict[str, Any], final_gold_index: dict[str, dict[str, Any]]) -> tuple[str, str, str, str, str]:
    rec, ref = _final_gold_for(data, final_gold_index)
    if rec:
        raw = _safe(rec.get("final_scope_alias") or rec.get("final_scope_binary"))
        return _normalize_task_scope(raw, _safe(rec.get("final_scope_binary"))), "final_gold", raw, ref, ""
    data_scope = _safe(data.get("scope_gold") or data.get("scope_target"))
    if data_scope:
        return _normalize_task_scope(data_scope), "expert_review", data_scope, "task_data_scope", "fallback_to_task_data_scope_contract"
    return "unknown_gold", "missing_final_gold", "", "", "missing final_gold/task scope contract"


def _worker_scope(annotation: dict[str, Any] | None) -> tuple[str, str, bool]:
    if not annotation:
        return "", "missing", False
    corners, _poly, choice_map, quality = extract_data(annotation.get("result", []))
    flags = parse_quality_flags_v2(choice_map, quality_all=quality, mode="v2")
    raw = ";".join(choice_map.get("scope", []))
    geometry_present = bool(len(corners) > 0)
    if flags.get("scope_missing") or flags.get("is_oos") is None:
        return raw, "missing", geometry_present
    if flags.get("is_oos") is True:
        return raw, "oos", geometry_present
    return raw, "in_scope", geometry_present


def _scope_response(task_scope: str, worker_scope: str) -> str:
    if task_scope in UNRESOLVED_SCOPES or task_scope == "unknown_gold":
        return "not_applicable_unresolved"
    if worker_scope == "missing":
        return "unknown_or_missing"
    if task_scope == "in_scope" and worker_scope == "in_scope":
        return "correct_in_scope"
    if task_scope == "in_scope" and worker_scope == "oos":
        return "scope_false_positive"
    if _is_oos_scope(task_scope) and worker_scope == "oos":
        return "correct_oos"
    if _is_oos_scope(task_scope) and worker_scope == "in_scope":
        return "scope_false_negative"
    return "unknown_or_missing"


def _geometry_score_fields_present(row_groups: list[list[dict[str, Any]]]) -> bool:
    for rows in row_groups:
        for row in rows:
            for key in row:
                key_lower = str(key).lower()
                if key_lower in GEOMETRY_SCORE_FIELD_NAMES:
                    return True
                if key_lower.endswith("_score") and any(token in key_lower for token in ("geometry", "layout", "corner")):
                    return True
    return False


def build_scope_audits(
    canonical_csv: Path,
    final_gold_jsonl: Path,
    completion_csv: Path | None = None,
    unknown_gold_allowlist_csv: Path | None = None,
    synthetic_bank_jsonl: Path | None = None,
    synthetic_expert_review_csv: Path | None = None,
    export_gt_json: Path | None = None,
    raw_input_manifest_csv: Path | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    canonical_rows = _load_csv(canonical_csv)
    completion = _load_completion(completion_csv)
    final_gold_index = _load_final_gold(final_gold_jsonl)
    unknown_gold_allowlist = _load_unknown_gold_allowlist(unknown_gold_allowlist_csv)
    synthetic_bank = _load_synthetic_bank(synthetic_bank_jsonl)
    synthetic_expert_review = _load_synthetic_expert_review(synthetic_expert_review_csv)
    export_gt_binding_path, export_gt_evidence = _validate_export_gt_manifest(raw_input_manifest_csv, export_gt_json)
    export_gt_by_title = _load_export_gt_by_title(export_gt_binding_path)
    task_index, ann_index = _load_export_details(canonical_rows)

    task_groups: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    parsed_rows: list[dict[str, Any]] = []
    for row in canonical_rows:
        key = (_safe(row.get("source_export")), _safe(row.get("project_id")), _safe(row.get("task_id")))
        task_groups[key].append(row)
        ann = ann_index.get((key[0], key[1], key[2], _safe(row.get("raw_canonical_annotation_id") or row.get("annotation_id"))))
        raw_scope, worker_scope, geometry_present = _worker_scope(ann)
        parsed = dict(row)
        parsed.update({"worker_scope_raw": raw_scope, "worker_scope_normalized": worker_scope, "geometry_valid_or_present": geometry_present})
        parsed_rows.append(parsed)

    by_row_key = {
        (_safe(r.get("source_export")), _safe(r.get("project_id")), _safe(r.get("task_id")), _safe(r.get("canonical_annotation_id"))): r
        for r in parsed_rows
    }

    task_rows: list[dict[str, Any]] = []
    unknown_gold_rows: list[dict[str, Any]] = []
    synthetic_audit_rows: list[dict[str, Any]] = []
    task_scope_map: dict[tuple[str, str, str], dict[str, Any]] = {}
    for key, rows in sorted(task_groups.items()):
        task = task_index.get(key)
        data = _task_data(task)
        task_scope, source, gold_scope, gold_ref, note, synthetic_audit = _synthetic_scope_binding(
            project_id=key[1],
            runtime_task_id=key[2],
            data=data,
            synthetic_bank=synthetic_bank,
            synthetic_expert_review=synthetic_expert_review,
            final_gold_index=final_gold_index,
        )
        if synthetic_audit:
            synthetic_audit_rows.append(synthetic_audit)
        if not source:
            task_scope, source, gold_scope, gold_ref, note = _task_scope(data, final_gold_index)
        scopes = []
        n_in = n_oos = n_missing = 0
        for row in rows:
            parsed = by_row_key[(key[0], key[1], key[2], _safe(row.get("canonical_annotation_id")))]
            scope = parsed["worker_scope_normalized"]
            scopes.append(scope)
            if scope == "in_scope":
                n_in += 1
            elif scope == "oos":
                n_oos += 1
            else:
                n_missing += 1
        mixed = n_in > 0 and n_oos > 0
        unresolved = task_scope in UNRESOLVED_SCOPES or task_scope == "unknown_gold"
        geometry_primary_possible = _geometry_possible(task_scope) and source != "synthetic_asset_expert_review"
        task_row = {
            "task_id": key[2],
            "project_id": key[1],
            "dataset_group": rows[0].get("dataset_group", ""),
            "condition": rows[0].get("condition", ""),
            "image_id": _safe(data.get("base_task_id") or Path(_safe(data.get("title"))).stem),
            "data_title": _safe(data.get("title") or rows[0].get("task_label")),
            "task_final_scope": task_scope,
            "task_scope_adjudication_source": source,
            "final_gold_scope": gold_scope,
            "final_gold_ref": gold_ref,
            "worker_scope_values_seen": ";".join(f"{k}:{v}" for k, v in sorted(Counter(scopes).items())),
            "n_worker_in_scope": n_in,
            "n_worker_oos": n_oos,
            "n_worker_scope_missing": n_missing,
            "mixed_scope_flag": mixed,
            "unresolved_scope_flag": unresolved,
            "geometry_primary_possible": geometry_primary_possible,
            "notes": note,
        }
        task_rows.append(task_row)
        task_scope_map[key] = task_row
        if task_scope == "unknown_gold":
            expected_key = _expected_gold_key(data)
            allowlist_reason = unknown_gold_allowlist.get((key[1], key[2]), "")
            unknown_gold_rows.append(
                {
                    "project_id": key[1],
                    "task_id": key[2],
                    "dataset_group": rows[0].get("dataset_group", ""),
                    "condition": rows[0].get("condition", ""),
                    "image_id": task_row["image_id"],
                    "data_title": task_row["data_title"],
                    "expected_final_gold_key": expected_key,
                    "match_failure_reason": note or "no final_gold match for expected keys",
                    "allowlisted": bool(allowlist_reason),
                    "allowlist_reason": allowlist_reason,
                }
            )

    response_rows: list[dict[str, Any]] = []
    for row in parsed_rows:
        key = (_safe(row.get("source_export")), _safe(row.get("project_id")), _safe(row.get("task_id")))
        task_row = task_scope_map[key]
        comp = completion.get(_safe(row.get("annotator_id")), {})
        response = _scope_response(str(task_row["task_final_scope"]), str(row["worker_scope_normalized"]))
        primary_eligible = (
            response not in {"unknown_or_missing", "not_applicable_unresolved"}
            and str(comp.get("eligible_for_primary_prescreen_candidate", "True")).lower() == "true"
        )
        response_rows.append(
            {
                "annotator_id": row.get("annotator_id", ""),
                "language": comp.get("language", ""),
                "completion_status": comp.get("completion_status", ""),
                "eligible_for_primary_prescreen_candidate": comp.get("eligible_for_primary_prescreen_candidate", ""),
                "project_id": row.get("project_id", ""),
                "task_id": row.get("task_id", ""),
                "dataset_group": row.get("dataset_group", ""),
                "condition": row.get("condition", ""),
                "worker_scope_raw": row["worker_scope_raw"],
                "worker_scope_normalized": row["worker_scope_normalized"],
                "task_final_scope": task_row["task_final_scope"],
                "task_scope_adjudication_source": task_row["task_scope_adjudication_source"],
                "worker_scope_response": response,
                "geometry_valid_or_present": row["geometry_valid_or_present"],
                "geometry_primary_possible": task_row["geometry_primary_possible"],
                "scope_response_primary_eligible": primary_eligible,
                "notes": "dry_run_partial_snapshot",
            }
        )

    mixed_task_rows = [
        {field: row.get(field, "") for field in MIXED_TASK_FIELDS}
        for row in task_rows
        if bool(row.get("mixed_scope_flag"))
    ]
    worker_rows = _worker_scope_summary(response_rows)
    runtime_task_rows = len(task_rows)
    base_image_count = len({_safe(row.get("image_id")) for row in task_rows if _safe(row.get("image_id"))})
    unknown_gold_base_images = {_safe(row.get("image_id")) for row in unknown_gold_rows if _safe(row.get("image_id"))}
    synthetic_bound_rows = [
        r
        for r in synthetic_audit_rows
        if r["scope_binding_status"] in {"synthetic_bound_to_source_gold", "synthetic_bound_by_expert_scope_review"}
    ]
    synthetic_expert_bound_rows = [r for r in synthetic_audit_rows if r["scope_binding_status"] == "synthetic_bound_by_expert_scope_review"]
    synthetic_unresolved_rows = [
        r
        for r in synthetic_audit_rows
        if r["scope_binding_status"] not in {"synthetic_bound_to_source_gold", "synthetic_bound_by_expert_scope_review"}
    ]
    synthetic_geometry_rows = _synthetic_geometry_gt_rows(synthetic_audit_rows, synthetic_expert_review, export_gt_by_title)
    synthetic_geometry_bound_rows = [r for r in synthetic_geometry_rows if r["geometry_binding_status"] == "synthetic_geometry_bound_to_export_gt"]
    synthetic_geometry_unbound_rows = [r for r in synthetic_geometry_rows if r["geometry_binding_status"] != "synthetic_geometry_bound_to_export_gt"]
    synthetic_geometry_scoring_deferred_rows = [r for r in synthetic_geometry_bound_rows if not bool(r["geometry_primary_possible"])]
    geometry_ready_by_runtime = {str(r["runtime_task_id"]): bool(r["geometry_gold_ready"]) for r in synthetic_geometry_rows}
    geometry_source_by_runtime = {str(r["runtime_task_id"]): str(r["geometry_gold_source"]) for r in synthetic_geometry_rows}
    geometry_deferred_by_runtime = {str(r["runtime_task_id"]): bool(r["geometry_scoring_deferred"]) for r in synthetic_geometry_rows}
    for row in synthetic_audit_rows:
        runtime_task_id = str(row.get("runtime_task_id", ""))
        if runtime_task_id in geometry_ready_by_runtime:
            row["geometry_gold_ready_after_binding"] = geometry_ready_by_runtime[runtime_task_id]
            row["geometry_gold_source_after_binding"] = geometry_source_by_runtime[runtime_task_id]
            row["geometry_scoring_deferred_after_binding"] = geometry_deferred_by_runtime[runtime_task_id]
            if geometry_deferred_by_runtime[runtime_task_id]:
                row["geometry_scoring_role"] = "semi_trap_audit"
    summary = {
        "dry_run": True,
        "data_complete": False,
        "n_tasks": len(task_rows),
        "n_responses": len(response_rows),
        "n_unknown_gold_audit_rows": len(unknown_gold_rows),
        "n_unknown_gold_allowlisted": sum(bool(r["allowlisted"]) for r in unknown_gold_rows),
        "n_mixed_task_audit_rows": len(mixed_task_rows),
        "n_worker_scope_summary_rows": len(worker_rows),
        "unknown_gold_task_rows_total": len(unknown_gold_rows),
        "unknown_gold_base_image_count": len(unknown_gold_base_images),
        "non_synthetic_unknown_gold_task_rows": len(unknown_gold_rows),
        "non_synthetic_unknown_gold_base_image_count": len(unknown_gold_base_images),
        "synthetic_scope_bound_task_rows": len(synthetic_bound_rows),
        "synthetic_scope_bound_base_image_count": len({_safe(r.get("base_image_key")) for r in synthetic_bound_rows if _safe(r.get("base_image_key"))}),
        "synthetic_bound_by_expert_scope_review_task_rows": len(synthetic_expert_bound_rows),
        "synthetic_bound_by_expert_scope_review_base_image_count": len(
            {_safe(r.get("base_image_key")) for r in synthetic_expert_bound_rows if _safe(r.get("base_image_key"))}
        ),
        "synthetic_scope_unresolved_task_rows": len(synthetic_unresolved_rows),
        "synthetic_scope_unresolved_base_image_count": len({_safe(r.get("base_image_key")) for r in synthetic_unresolved_rows if _safe(r.get("base_image_key"))}),
        "synthetic_geometry_gt_bound_task_rows": len(synthetic_geometry_bound_rows),
        "synthetic_geometry_gt_bound_base_image_count": len(
            {_safe(r.get("base_image_key")) for r in synthetic_geometry_bound_rows if _safe(r.get("base_image_key"))}
        ),
        "synthetic_geometry_gt_unbound_task_rows": len(synthetic_geometry_unbound_rows),
        "synthetic_geometry_gt_unbound_base_image_count": len(
            {_safe(r.get("base_image_key")) for r in synthetic_geometry_unbound_rows if _safe(r.get("base_image_key"))}
        ),
        "synthetic_geometry_gt_source": "export_label_groudTruth",
        "synthetic_geometry_primary_possible_task_rows": sum(bool(r["geometry_primary_possible"]) for r in synthetic_geometry_rows),
        "synthetic_geometry_scoring_deferred_task_rows": len(synthetic_geometry_scoring_deferred_rows),
        "geometry_score_fields_present": _geometry_score_fields_present([task_rows, response_rows, synthetic_audit_rows, synthetic_geometry_rows]),
        "_synthetic_geometry_gt_rows": synthetic_geometry_rows,
        **export_gt_evidence,
        "runtime_task_rows": runtime_task_rows,
        "base_image_count": base_image_count,
        "language_mirror_note": "Chinese/English Label Studio mirrors count as separate runtime task rows; base_image_count deduplicates by base/source image key.",
        "task_final_scope_counts": dict(Counter(str(r["task_final_scope"]) for r in task_rows)),
        "worker_scope_response_counts": dict(Counter(str(r["worker_scope_response"]) for r in response_rows)),
        "unknown_gold_tasks": sum(r["task_final_scope"] == "unknown_gold" for r in task_rows),
        "unresolved_mixed_tasks": sum(r["task_final_scope"] == "unresolved_mixed" for r in task_rows),
        "missing_worker_scope_rows": sum(r["worker_scope_normalized"] == "missing" for r in response_rows),
        "mixed_scope_tasks": sum(bool(r["mixed_scope_flag"]) for r in task_rows),
    }
    return task_rows, response_rows, unknown_gold_rows, mixed_task_rows, worker_rows, synthetic_audit_rows, summary


def _worker_scope_summary(response_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in response_rows:
        grouped[_safe(row.get("annotator_id"))].append(row)
    out: list[dict[str, Any]] = []
    for annotator_id, rows in sorted(grouped.items(), key=lambda item: int(item[0]) if item[0].isdigit() else item[0]):
        counts = Counter(str(row.get("worker_scope_response")) for row in rows)
        correct = counts["correct_in_scope"] + counts["correct_oos"]
        adjudicated = correct + counts["scope_false_positive"] + counts["scope_false_negative"]
        out.append(
            {
                "annotator_id": annotator_id,
                "language": rows[0].get("language", ""),
                "completion_status": rows[0].get("completion_status", ""),
                "n_correct_in_scope": counts["correct_in_scope"],
                "n_correct_oos": counts["correct_oos"],
                "n_scope_false_positive": counts["scope_false_positive"],
                "n_scope_false_negative": counts["scope_false_negative"],
                "n_unknown_or_missing": counts["unknown_or_missing"],
                "n_not_applicable_unresolved": counts["not_applicable_unresolved"],
                "scope_accuracy_on_adjudicated_tasks": round(correct / adjudicated, 6) if adjudicated else "",
            }
        )
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--canonical-csv", default=str(DEFAULT_CANONICAL))
    parser.add_argument("--final-gold-jsonl", default=str(DEFAULT_FINAL_GOLD))
    parser.add_argument("--completion-csv", default=str(DEFAULT_COMPLETION))
    parser.add_argument("--unknown-gold-allowlist-csv", default=str(DEFAULT_UNKNOWN_GOLD_ALLOWLIST))
    parser.add_argument("--synthetic-bank-jsonl", default=str(DEFAULT_SYNTHETIC_BANK))
    parser.add_argument("--synthetic-expert-review-csv", default=str(DEFAULT_SYNTHETIC_EXPERT_REVIEW))
    parser.add_argument("--export-gt-json", default=str(DEFAULT_EXPORT_GT))
    parser.add_argument("--raw-input-manifest-csv", default=str(DEFAULT_RAW_INPUT_MANIFEST))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args(argv)

    out_dir = Path(args.output_dir)
    task_rows, response_rows, unknown_gold_rows, mixed_task_rows, worker_rows, synthetic_audit_rows, summary = build_scope_audits(
        Path(args.canonical_csv),
        Path(args.final_gold_jsonl),
        Path(args.completion_csv) if args.completion_csv else None,
        Path(args.unknown_gold_allowlist_csv) if args.unknown_gold_allowlist_csv else None,
        Path(args.synthetic_bank_jsonl) if args.synthetic_bank_jsonl else None,
        Path(args.synthetic_expert_review_csv) if args.synthetic_expert_review_csv else None,
        Path(args.export_gt_json) if args.export_gt_json else None,
        Path(args.raw_input_manifest_csv) if args.raw_input_manifest_csv else None,
    )
    synthetic_geometry_rows = summary.pop("_synthetic_geometry_gt_rows", [])
    task_path = out_dir / "prescreen_scope_adjudication.csv"
    response_path = out_dir / "prescreen_scope_response_audit.csv"
    unknown_gold_path = out_dir / "prescreen_scope_unknown_gold_audit.csv"
    mixed_task_path = out_dir / "prescreen_scope_mixed_task_audit.csv"
    worker_scope_path = out_dir / "prescreen_worker_scope_summary.csv"
    synthetic_binding_path = out_dir / "prescreen_synthetic_scope_binding_audit.csv"
    synthetic_geometry_path = out_dir / "prescreen_synthetic_geometry_gt_binding_audit.csv"
    summary_path = out_dir / "prescreen_scope_summary.json"
    _write_csv(task_path, TASK_FIELDS, task_rows)
    _write_csv(response_path, RESPONSE_FIELDS, response_rows)
    _write_csv(unknown_gold_path, UNKNOWN_GOLD_FIELDS, unknown_gold_rows)
    _write_csv(mixed_task_path, MIXED_TASK_FIELDS, mixed_task_rows)
    _write_csv(worker_scope_path, WORKER_SCOPE_FIELDS, worker_rows)
    _write_csv(synthetic_binding_path, SYNTHETIC_BINDING_FIELDS, synthetic_audit_rows)
    _write_csv(synthetic_geometry_path, SYNTHETIC_GEOMETRY_GT_FIELDS, synthetic_geometry_rows)
    summary.update(
        {
            "scope_adjudication_csv": str(task_path),
            "scope_response_audit_csv": str(response_path),
            "scope_unknown_gold_audit_csv": str(unknown_gold_path),
            "scope_mixed_task_audit_csv": str(mixed_task_path),
            "worker_scope_summary_csv": str(worker_scope_path),
            "synthetic_scope_binding_audit_csv": str(synthetic_binding_path),
            "synthetic_geometry_gt_binding_audit_csv": str(synthetic_geometry_path),
        }
    )
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
