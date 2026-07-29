#!/usr/bin/env python3
"""Stage-aware analysis helper for Dev B work.

This entrypoint is intentionally conservative:
1. Use A-line registry as the runtime truth boundary.
2. Join the formal quality rerun for scene/meta/layout fields.
3. Apply a thesis-facing gate before any analysis.
4. Support a replaceable selection manifest for subset definition.
5. Treat C-line manifests as auditable membership sources, not dead inputs.

The output is still a prototype analysis pack, but it now exposes:
- Worker x scene-proxy coverage / IOU tables
- Worker profile prototype tables
- T / I / M transparency-tier metrics
- Type 4 residual process audit tables
- Input summary that records which gates and manifests were applied
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

DEFAULT_REGISTRY_PATH = Path("analysis_results/registry_20260308/merged_all_v0.csv")
DEFAULT_ANCHOR_INDEX = Path(
    "analysis_results/c_manifests_20260310/manual_anchor_bank_index_v1.csv"
)
DEFAULT_TRAP_MANIFEST = Path(
    "analysis_results/c_manifests_20260310/trap_manifest_draft_v1.csv"
)
DEFAULT_QUALITY_PATH = Path(
    "analysis_results/rerun_20260308/quality_report_formal_20260308.csv"
)
DEFAULT_META_GUARD_ACCEPTED = Path(
    "analysis_results/rerun_20260308/meta_guard_accepted.csv"
)
DEFAULT_META_GUARD_REJECTED = Path(
    "analysis_results/rerun_20260308/meta_guard_rejected.csv"
)
DEFAULT_PHASE1_ALIGNMENT_MANIFEST = Path(
    "analysis_results/phase1_progress_20260311/phase1_target_vs_realized_manifest_v1.json"
)
DEFAULT_OUTPUT_DIR = Path("analysis_results/stage_aware_analysis")

CORE_SCENE_RULE_VERSION = "scene_proxy_top4_v1"
WORKER_GROUP_RULE_VERSION = "prototype_worker_group_v1"
R_U_LCB_RULE_VERSION = "quantile10_m_tier_v1"
TYPE4_LINK_RULE_VERSION = "meta_guard_bridge_v1"
SELECTION_RULE_VERSION = "selection_manifest_resolved_v2_1"
FREEZE_VERSION = "b_formal_prep_freeze_v1_20260316"
TIM_MAPPING_RULE_VERSION = "tim_row_audit_v2_1"
TIM_MAPPING_SPEC_VERSION = "tim_mapping_spec_v2_1"

CORE_SCENE_RULE_VERSION_V2 = "scene_proxy_top4_support_v2"
WORKER_GROUP_RULE_VERSION_V2 = "stabilized_worker_group_v2"
TYPE4_LINK_RULE_VERSION_V2 = "meta_guard_system_tier_chain_v2"
ROUTE_ATTRIBUTION_RULE_VERSION = "route_attribution_minimal_v1"
ROUTE_ATTRIBUTION_RULE_VERSION_V2 = "route_attribution_replayable_v2"
FREEZE_VERSION_V2 = "b_formal_prep_freeze_v2_20260317"
FREEZE_VERSION_V2_1 = "b_formal_prep_freeze_v2_1_20260317"
TIM_MAPPING_SPEC_CANONICAL_FILE = "tim_mapping_spec_v2_1.json"
TIM_RULE_SUMMARY_CANONICAL_FILE = "tim_rule_summary_v2_1.csv"
TYPE4_EVIDENCE_CANONICAL_FILE = "type4_evidence_v2_1.csv"
CONSISTENCY_AUDIT_V2_1_FILE = "freeze_v2_1_consistency_audit.json"
STAGE1_ALIGNMENT_AUDIT_V2_1_FILE = "stage1_alignment_audit_v2_1.json"
ACTIVE_TIME_ESTIMAND_AUDIT_V2_1_FILE = "active_time_estimand_audit_v2_1.json"
SELECTION_MAIN_FACING_AUDIT_V2_1_FILE = "selection_main_facing_audit_v2_1.json"
SELECTION_PROVENANCE_AUDIT_V2_1_FILE = "selection_provenance_audit_v2_1.json"
MAIN_FACING_DATASET_GROUPS = {
    "Manual_Test",
    "SemiAuto_Test",
    "Validation_semi",
    "Gold_manual",
}

SELECTION_COLUMNS = (
    "task_id",
    "annotation_id",
    "base_task_id",
    "matched_registry_uid",
    "dataset_group",
    "annotator_id",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage-aware analysis helper")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY_PATH)
    parser.add_argument("--anchor-index", type=Path, default=DEFAULT_ANCHOR_INDEX)
    parser.add_argument("--trap-manifest", type=Path, default=DEFAULT_TRAP_MANIFEST)
    parser.add_argument(
        "--selection-manifest",
        type=Path,
        default=None,
        help="CSV/JSON manifest that defines the thesis-facing subset.",
    )
    parser.add_argument("--quality-report", type=Path, default=DEFAULT_QUALITY_PATH)
    parser.add_argument(
        "--meta-guard-accepted",
        type=Path,
        default=DEFAULT_META_GUARD_ACCEPTED,
    )
    parser.add_argument(
        "--meta-guard-rejected",
        type=Path,
        default=DEFAULT_META_GUARD_REJECTED,
    )
    parser.add_argument(
        "--phase1-alignment-manifest",
        type=Path,
        default=DEFAULT_PHASE1_ALIGNMENT_MANIFEST,
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def _load_csv(path: Path, label: str, required: bool = True) -> pd.DataFrame:
    if not path.exists():
        if required:
            raise FileNotFoundError(f"{label} not found at {path}")
        print(f"Warning: {label} not found at {path}; using empty frame.")
        return pd.DataFrame()
    print(f"Loading {label} from {path}...")
    return pd.read_csv(path)


def load_selection_manifest(path: Optional[Path]) -> pd.DataFrame:
    if path is None:
        return pd.DataFrame()
    if not path.exists():
        raise FileNotFoundError(f"Selection manifest not found at {path}")

    print(f"Loading selection manifest from {path}...")
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return pd.DataFrame(payload)
        if isinstance(payload, dict):
            for key in ("items", "rows", "data"):
                if isinstance(payload.get(key), list):
                    return pd.DataFrame(payload[key])
        raise ValueError(f"Unsupported selection manifest JSON shape: {path}")
    raise ValueError(f"Unsupported selection manifest format: {path.suffix}")


def _build_autogen_selection_manifest(raw_df: pd.DataFrame) -> pd.DataFrame:
    eligible = raw_df[raw_df["thesis_input_eligible"]].copy()
    keep_columns = [column for column in SELECTION_COLUMNS if column in eligible.columns]
    if not keep_columns:
        return pd.DataFrame(columns=SELECTION_COLUMNS)
    selection = (
        eligible[keep_columns]
        .astype(str)
        .drop_duplicates()
        .sort_values(keep_columns)
        .reset_index(drop=True)
    )
    return selection


def resolve_selection_manifest(
    raw_df: pd.DataFrame,
    selection_df: pd.DataFrame,
    selection_path: Optional[Path],
    output_dir: Path,
) -> tuple[pd.DataFrame, Path, str, bool]:
    if selection_path is not None:
        return selection_df.copy(), selection_path, "provided", True

    autogen_selection = _build_autogen_selection_manifest(raw_df)
    resolved_path = output_dir / "selection_manifest_autogen_default_gate_v1.csv"
    autogen_selection.to_csv(resolved_path, index=False)
    return autogen_selection, resolved_path, "autogen_default_gate", False


def _resolve_manifest_source_path(source_value: str, manifest_path: Path) -> Optional[Path]:
    source_text = source_value.strip().replace("\\", "/")
    if not source_text:
        return None

    candidate = Path(source_text)
    candidates: list[Path] = []
    if candidate.is_absolute():
        candidates.append(candidate)
    else:
        candidates.append(manifest_path.parent / candidate)
        candidates.append(Path.cwd() / candidate)
        if not candidate.parts or candidate.parts[0] != "analysis_results":
            candidates.append(Path.cwd() / "analysis_results" / candidate)

    for resolved in candidates:
        if resolved.exists():
            return resolved
    return None


def _build_selection_source_chain(selection_path: Path) -> tuple[list[dict[str, Any]], bool]:
    chain: list[dict[str, Any]] = []
    unresolved_source = False
    visited: set[Path] = set()
    current = selection_path
    max_depth = 6

    for _ in range(max_depth):
        resolved_current = current.resolve()
        if resolved_current in visited:
            chain.append(
                {
                    "path": str(current),
                    "loop_detected": True,
                }
            )
            break
        visited.add(resolved_current)

        entry: dict[str, Any] = {"path": str(current)}
        if not current.exists():
            entry["missing"] = True
            chain.append(entry)
            unresolved_source = True
            break

        suffix = current.suffix.lower()
        entry["format"] = suffix.lstrip(".") if suffix else "unknown"
        if suffix != ".json":
            chain.append(entry)
            break

        payload = json.loads(current.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            entry["json_shape"] = type(payload).__name__
            chain.append(entry)
            break

        for key in ("manifest_version", "selection_mode", "source", "row_count"):
            if key in payload:
                entry[key] = payload.get(key)
        chain.append(entry)

        source_value = str(payload.get("source", "")).strip()
        if not source_value:
            break

        next_path = _resolve_manifest_source_path(source_value, current)
        if next_path is None:
            unresolved_source = True
            chain.append({"unresolved_source": source_value})
            break
        current = next_path
    return chain, not unresolved_source


def write_selection_provenance_audit_v2_1(
    selection_path: Path,
    selection_mode: str,
    output_dir: Path,
) -> dict[str, Any]:
    chain: list[dict[str, Any]] = []
    chain_resolved = True
    if selection_mode == "provided":
        chain, chain_resolved = _build_selection_source_chain(selection_path)

    normalized_tokens: list[str] = []
    for item in chain:
        for key in ("path", "source", "manifest_version", "selection_mode"):
            value = item.get(key)
            if value is not None:
                normalized_tokens.append(str(value).lower())

    derived_from_autogen = any("autogen_default_gate" in token for token in normalized_tokens)
    source_independent_from_autogen = selection_mode == "provided" and not derived_from_autogen
    payload = {
        "selection_provenance_gate_version": "selection_provenance_v2_1",
        "selection_mode": selection_mode,
        "selection_manifest_path": str(selection_path),
        "source_chain_depth": len(chain),
        "source_chain_resolved_complete": chain_resolved,
        "source_chain": chain,
        "selection_derived_from_autogen_default_gate": derived_from_autogen,
        "selection_source_independent_from_autogen": source_independent_from_autogen,
    }
    if selection_mode != "provided":
        payload["selection_source_independent_from_autogen"] = False
    (output_dir / SELECTION_PROVENANCE_AUDIT_V2_1_FILE).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return payload


def write_stage1_alignment_audit_v2_1(
    phase1_alignment_manifest_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "stage1_gate_version": "stage1_protocol_alignment_v2_1",
        "source_manifest_path": str(phase1_alignment_manifest_path),
        "source_manifest_found": phase1_alignment_manifest_path.exists(),
    }
    blockers: list[str] = []
    if not phase1_alignment_manifest_path.exists():
        blockers.append("stage1_alignment_manifest_missing")
        payload.update(
            {
                "stage1_alignment_passed": False,
                "blockers": blockers,
                "manual_anchor_alignment_status": "manifest_missing",
                "prescreen_semi_alignment_status": "manifest_missing",
            }
        )
    else:
        manifest = json.loads(phase1_alignment_manifest_path.read_text(encoding="utf-8"))
        items = {
            str(item.get("item_id")): item
            for item in manifest.get("items", [])
            if isinstance(item, dict)
        }
        manual_item = items.get("stage1_prescreen_manual_expert_anchor", {})
        semi_item = items.get("stage1_prescreen_semi_total", {})
        manual_status = str(manual_item.get("status", "missing_item"))
        semi_status = str(semi_item.get("status", "missing_item"))
        manual_pass = manual_status == "aligned"
        semi_pass = semi_status == "aligned"
        if not manual_pass:
            blockers.append("stage1_manual_anchor_not_aligned")
        if not semi_pass:
            blockers.append("stage1_prescreen_semi_not_aligned")
        payload.update(
            {
                "stage1_alignment_passed": manual_pass and semi_pass,
                "blockers": blockers,
                "manual_anchor_alignment_status": manual_status,
                "manual_anchor_target": manual_item.get("thesis_target", {}),
                "manual_anchor_current_repo": manual_item.get("current_repo", {}),
                "prescreen_semi_alignment_status": semi_status,
                "prescreen_semi_target": semi_item.get("thesis_target", {}),
                "prescreen_semi_current_repo": semi_item.get("current_repo", {}),
            }
        )
    (output_dir / STAGE1_ALIGNMENT_AUDIT_V2_1_FILE).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return payload


def write_selection_main_facing_audit_v2_1(
    analysis_df: pd.DataFrame,
    selection_mode: str,
    output_dir: Path,
) -> dict[str, Any]:
    dataset_counts = (
        analysis_df["dataset_group"].fillna("").astype(str).value_counts().to_dict()
        if not analysis_df.empty
        else {}
    )
    selected_groups = set(dataset_counts.keys())
    non_main_groups = sorted(
        [group for group in selected_groups if group and group not in MAIN_FACING_DATASET_GROUPS]
    )
    main_facing_passed = selection_mode == "provided" and len(non_main_groups) == 0
    payload = {
        "selection_main_facing_gate_version": "selection_main_facing_v2_1",
        "selection_mode": selection_mode,
        "main_facing_dataset_groups": sorted(MAIN_FACING_DATASET_GROUPS),
        "selected_dataset_group_counts": dataset_counts,
        "non_main_groups_present": non_main_groups,
        "selection_main_facing_passed": main_facing_passed,
    }
    (output_dir / SELECTION_MAIN_FACING_AUDIT_V2_1_FILE).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return payload


def derive_thesis_readiness(
    selection_mode: str,
    selection_ready_flag: bool,
    stage1_alignment_audit: dict[str, Any],
    selection_main_facing_audit: dict[str, Any],
    selection_provenance_audit: Optional[dict[str, Any]] = None,
) -> tuple[bool, str, list[str]]:
    blockers: list[str] = []
    if not selection_ready_flag or selection_mode != "provided":
        blockers.append("autogen_default_gate_selection")
    if selection_mode == "provided" and not bool(
        selection_main_facing_audit.get("selection_main_facing_passed", False)
    ):
        blockers.append("selection_not_main_facing")
    source_independent_from_autogen = bool(
        (selection_provenance_audit or {}).get("selection_source_independent_from_autogen", True)
    )
    if selection_mode == "provided" and not source_independent_from_autogen:
        blockers.append("selection_not_independent_from_autogen")
    if not bool(stage1_alignment_audit.get("stage1_alignment_passed", False)):
        blockers.append("stage1_protocol_not_aligned")

    if not blockers:
        return True, "ready_for_thesis_selection", blockers
    status = "blocked_" + "_and_".join(blockers)
    return False, status, blockers


def write_active_time_estimand_audit_v2_1(
    analysis_df: pd.DataFrame,
    output_dir: Path,
) -> dict[str, Any]:
    source = analysis_df["active_time_source"].fillna("").astype(str)
    n_rows = int(len(analysis_df))
    n_log = int(source.eq("log").sum())
    n_fallback = int(source.eq("lead_time_fallback").sum())
    n_other = int(n_rows - n_log - n_fallback)
    mixed_estimand = n_log > 0 and n_fallback > 0
    primary_endpoint_ready = n_fallback == 0 and n_log > 0
    if mixed_estimand:
        status = "mixed_estimand_log_plus_fallback"
        recommendation = "log_only_primary_with_fallback_sensitivity"
    elif n_log > 0 and n_fallback == 0:
        status = "log_only_clean"
        recommendation = "log_primary_ok"
    elif n_log == 0 and n_fallback > 0:
        status = "fallback_only"
        recommendation = "not_primary_endpoint_ready"
    else:
        status = "unknown_or_empty"
        recommendation = "not_primary_endpoint_ready"

    payload = {
        "estimand_audit_version": "active_time_estimand_audit_v2_1",
        "n_rows": n_rows,
        "n_log": n_log,
        "n_lead_time_fallback": n_fallback,
        "n_other_source": n_other,
        "log_share": (n_log / n_rows) if n_rows else None,
        "lead_time_fallback_share": (n_fallback / n_rows) if n_rows else None,
        "mixed_estimand": mixed_estimand,
        "primary_endpoint_ready": primary_endpoint_ready,
        "active_time_endpoint_status": status,
        "recommended_analysis_mode": recommendation,
    }
    (output_dir / ACTIVE_TIME_ESTIMAND_AUDIT_V2_1_FILE).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return payload


def _m_tier_mask(df: pd.DataFrame) -> pd.Series:
    if "tim_m_included" in df.columns:
        return df["tim_m_included"].fillna(False).astype(bool)
    if "m_included" in df.columns:
        return df["m_included"].fillna(False).astype(bool)
    return pd.Series(False, index=df.index, dtype=bool)


def _as_string(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str)


def _to_bool_series(series: pd.Series, default: bool = False) -> pd.Series:
    if series.dtype == bool:
        return series.fillna(default)
    lowered = (
        series.fillna(str(default))
        .astype(str)
        .str.strip()
        .str.lower()
    )
    return lowered.isin({"1", "true", "yes", "y"})


def _normalize_tokens(value: Any) -> list[str]:
    if pd.isna(value):
        return []
    if isinstance(value, list):
        raw_tokens = value
    else:
        raw_tokens = str(value).split(";")
    tokens: list[str] = []
    for token in raw_tokens:
        token_str = str(token).strip()
        if token_str and token_str.lower() not in {"na", "nan", "none"}:
            tokens.append(token_str)
    return tokens


def _pick_consensus_token(
    values: Iterable[Any],
    default: str,
    demote_token: Optional[str] = None,
) -> str:
    counts: Dict[str, int] = {}
    for value in values:
        for token in _normalize_tokens(value):
            counts[token] = counts.get(token, 0) + 1
    if not counts:
        return default

    if demote_token and demote_token in counts and len(counts) > 1:
        counts = {key: val for key, val in counts.items() if key != demote_token}
        if not counts:
            return demote_token

    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return ordered[0][0]


def _scope_bucket(raw_scope: Any) -> str:
    scope = str(raw_scope).strip()
    if not scope:
        return "missing"
    if scope == "normal":
        return "in_scope"
    return "oos"


def _task_scene_consensus(quality_df: pd.DataFrame) -> pd.DataFrame:
    if quality_df.empty:
        return pd.DataFrame(columns=["task_id", "scene_proxy", "scene_scope_bucket"])

    records: list[dict[str, Any]] = []
    for task_id, group in quality_df.groupby("task_id", dropna=False):
        raw_scope = _pick_consensus_token(group.get("scope", pd.Series(dtype=object)), "missing")
        scope_bucket = _scope_bucket(raw_scope)
        if scope_bucket == "in_scope":
            difficulty_primary = _pick_consensus_token(
                group.get("difficulty", pd.Series(dtype=object)),
                default="none",
                demote_token="trivial",
            )
            issue_primary = _pick_consensus_token(
                group.get("model_issue_primary", group.get("model_issue", pd.Series(dtype=object))),
                default="acceptable",
                demote_token="acceptable",
            )
            scene_proxy = f"{difficulty_primary}|{issue_primary}"
        elif scope_bucket == "oos":
            scene_proxy = f"oos::{raw_scope}"
        else:
            scene_proxy = "missing_scope"

        records.append(
            {
                "task_id": str(task_id),
                "scene_proxy": scene_proxy,
                "scene_scope_bucket": scope_bucket,
                "scene_scope_raw": raw_scope,
                "scene_mixed_scope": bool(
                    _to_bool_series(group.get("task_scope_is_mixed", pd.Series([False]))).any()
                ),
            }
        )

    return pd.DataFrame.from_records(records)


def build_analysis_frame(registry_df: pd.DataFrame, quality_df: pd.DataFrame) -> pd.DataFrame:
    registry = registry_df.copy()
    quality = quality_df.copy()

    registry["task_id"] = _as_string(registry["task_id"])
    registry["annotation_id"] = _as_string(registry["annotation_id"])
    registry["annotator_id"] = _as_string(registry["annotator_id"])
    registry["base_task_id"] = _as_string(registry["base_task_id"])
    registry["dataset_group"] = _as_string(registry["dataset_group"])
    registry["matched_registry_uid"] = _as_string(registry["matched_registry_uid"])
    registry["task_join_status"] = _as_string(registry["task_join_status"])
    registry["active_time_source"] = _as_string(registry["active_time_source"])

    quality["task_id"] = _as_string(quality["task_id"])
    quality["annotator_id"] = _as_string(quality["annotator_id"])

    quality_columns = [
        "task_id",
        "annotator_id",
        "active_time",
        "iou",
        "layout_used",
        "layout_gate_reason",
        "scope",
        "difficulty",
        "model_issue",
        "scope_filled",
        "difficulty_filled",
        "difficulty_conflict",
        "model_issue_required",
        "model_issue_filled",
        "model_issue_conflict",
        "model_issue_missing_required",
        "model_issue_primary",
        "task_scope_majority",
        "task_scope_is_mixed",
    ]
    quality_subset = quality[[col for col in quality_columns if col in quality.columns]].copy()
    merged = registry.merge(
        quality_subset,
        on=["task_id", "annotator_id"],
        how="left",
        suffixes=("", "_quality"),
    )

    task_scene = _task_scene_consensus(quality)
    merged = merged.merge(task_scene, on="task_id", how="left")

    merged["active_time"] = pd.to_numeric(
        merged["active_time"].fillna(merged["active_time_value"]),
        errors="coerce",
    )
    merged["iou"] = pd.to_numeric(merged.get("iou"), errors="coerce")
    merged["layout_used"] = _to_bool_series(
        merged.get("layout_used", pd.Series([False] * len(merged))),
        default=False,
    )
    merged["scope"] = _as_string(
        merged.get("scope", pd.Series(index=merged.index, dtype=object)).replace("", pd.NA)
    ).where(
        _as_string(merged.get("scope", pd.Series(index=merged.index, dtype=object))) != "",
        _as_string(merged["compat_scope"]),
    )
    merged["difficulty"] = _as_string(
        merged.get("difficulty", pd.Series(index=merged.index, dtype=object))
    ).where(
        _as_string(merged.get("difficulty", pd.Series(index=merged.index, dtype=object))) != "",
        _as_string(merged["compat_difficulty"]),
    )
    merged["model_issue"] = _as_string(
        merged.get("model_issue", pd.Series(index=merged.index, dtype=object))
    ).where(
        _as_string(merged.get("model_issue", pd.Series(index=merged.index, dtype=object))) != "",
        _as_string(merged["compat_model_issue"]),
    )

    merged["scope_bucket"] = merged["scope"].map(_scope_bucket)
    merged["scope_filled"] = _to_bool_series(
        merged.get("scope_filled", pd.Series([False] * len(merged))),
        default=False,
    )
    merged["difficulty_filled"] = _to_bool_series(
        merged.get("difficulty_filled", pd.Series([False] * len(merged))),
        default=False,
    )
    merged["difficulty_conflict"] = _to_bool_series(
        merged.get("difficulty_conflict", pd.Series([False] * len(merged))),
        default=False,
    )
    merged["model_issue_conflict"] = _to_bool_series(
        merged.get("model_issue_conflict", pd.Series([False] * len(merged))),
        default=False,
    )
    merged["model_issue_missing_required"] = _to_bool_series(
        merged.get("model_issue_missing_required", pd.Series([False] * len(merged))),
        default=False,
    )
    merged["type4_flag"] = (
        ~merged["scope_filled"]
        | ~merged["difficulty_filled"]
        | merged["difficulty_conflict"]
        | merged["model_issue_conflict"]
        | merged["model_issue_missing_required"]
    )
    merged["type4_reason_codes"] = merged.apply(_collect_type4_reason_codes, axis=1)
    merged["i_included"] = merged["scope_bucket"].eq("in_scope")
    merged["m_included"] = merged["i_included"] & merged["layout_used"]
    merged["thesis_input_eligible"] = (
        merged["dataset_group"].ne("")
        & merged["task_join_status"].str.startswith("matched")
    )
    return merged


def _collect_type4_reason_codes(row: pd.Series) -> str:
    reasons: list[str] = []
    if not bool(row.get("scope_filled", False)):
        reasons.append("scope_missing")
    if not bool(row.get("difficulty_filled", False)):
        reasons.append("difficulty_missing")
    if bool(row.get("difficulty_conflict", False)):
        reasons.append("difficulty_conflict")
    if bool(row.get("model_issue_conflict", False)):
        reasons.append("model_issue_conflict")
    if bool(row.get("model_issue_missing_required", False)):
        reasons.append("model_issue_missing_required")
    return ";".join(reasons)


def apply_default_gate(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["thesis_input_eligible"]].copy()


def apply_selection_manifest(df: pd.DataFrame, selection_df: pd.DataFrame) -> pd.DataFrame:
    if selection_df.empty:
        return df.copy()

    usable_columns = [
        col for col in SELECTION_COLUMNS if col in selection_df.columns and col in df.columns
    ]
    if not usable_columns:
        raise ValueError(
            "Selection manifest does not contain any supported keys: "
            + ", ".join(SELECTION_COLUMNS)
        )

    normalized_df = df.copy()
    for column in usable_columns:
        normalized_df[column] = normalized_df[column].astype(str).str.strip()

    mask = pd.Series(False, index=normalized_df.index)
    for _, sel_row in selection_df[usable_columns].iterrows():
        row_mask = pd.Series(True, index=normalized_df.index)
        has_concrete_key = False
        for column in usable_columns:
            value = str(sel_row.get(column, "")).strip()
            if value and value.lower() not in {"nan", "none", "na"}:
                row_mask = row_mask & normalized_df[column].eq(value)
                has_concrete_key = True
        if has_concrete_key:
            mask = mask | row_mask

    return df[mask].copy()


def attach_manifest_membership(
    df: pd.DataFrame,
    anchor_df: pd.DataFrame,
    trap_df: pd.DataFrame,
) -> pd.DataFrame:
    enriched = df.copy()
    anchor_tasks = set(_as_string(anchor_df.get("base_task_id", pd.Series(dtype=object))))
    trap_tasks = set(_as_string(trap_df.get("base_task_id", pd.Series(dtype=object))))

    enriched["in_manual_anchor_bank"] = enriched["base_task_id"].isin(anchor_tasks)
    enriched["in_trap_manifest"] = enriched["base_task_id"].isin(trap_tasks)

    def classify_source_bank(row: pd.Series) -> str:
        if row["in_manual_anchor_bank"] and row["in_trap_manifest"]:
            return "anchor+trap"
        if row["in_manual_anchor_bank"]:
            return "anchor_only"
        if row["in_trap_manifest"]:
            return "trap_only"
        return "registry_only"

    enriched["source_bank_membership"] = enriched.apply(classify_source_bank, axis=1)
    return enriched


def attach_meta_guard_status(
    df: pd.DataFrame,
    accepted_df: pd.DataFrame,
    rejected_df: pd.DataFrame,
) -> pd.DataFrame:
    enriched = df.copy()
    accepted = accepted_df.copy()
    rejected = rejected_df.copy()

    for frame in (accepted, rejected):
        if frame.empty:
            continue
        for column in ("task_id", "annotation_id"):
            if column in frame.columns:
                frame[column] = _as_string(frame[column])

    accepted_pairs: set[tuple[str, str]] = set()
    if not accepted.empty and {"task_id", "annotation_id"}.issubset(accepted.columns):
        accepted_pairs = set(zip(accepted["task_id"], accepted["annotation_id"]))

    rejected_reason_map: dict[tuple[str, str], str] = {}
    if not rejected.empty and {"task_id", "annotation_id"}.issubset(rejected.columns):
        rejected_reason_map = (
            rejected.assign(
                reject_reasons=_as_string(
                    rejected.get("reject_reasons", pd.Series(index=rejected.index, dtype=object))
                )
            )
            .groupby(["task_id", "annotation_id"])["reject_reasons"]
            .agg(lambda s: ";".join(sorted({token for token in s if token})))
            .to_dict()
        )

    statuses: list[str] = []
    reasons: list[str] = []
    for row in enriched.itertuples(index=False):
        pair = (str(row.task_id), str(row.annotation_id))
        if pair in rejected_reason_map:
            statuses.append("rejected")
            reasons.append(rejected_reason_map[pair])
        elif pair in accepted_pairs:
            statuses.append("accepted")
            reasons.append("")
        else:
            statuses.append("not_seen")
            reasons.append("")

    enriched["meta_guard_status"] = statuses
    enriched["meta_guard_reject_reasons"] = reasons
    enriched["type4_source"] = enriched.apply(_compose_type4_source, axis=1)
    enriched["type4_evidence_chain"] = enriched.apply(_compose_type4_evidence_chain, axis=1)
    return enriched


def _compose_type4_source(row: pd.Series) -> str:
    if row.get("meta_guard_status") == "rejected":
        if bool(row.get("type4_flag", False)):
            return "meta_guard+system"
        return "meta_guard"
    if bool(row.get("type4_flag", False)):
        return "system"
    return "none"


def _compose_type4_evidence_chain(row: pd.Series) -> str:
    parts: list[str] = []
    if row.get("meta_guard_status") == "rejected":
        parts.append("meta_guard_rejected")
    elif row.get("meta_guard_status") == "accepted":
        parts.append("meta_guard_accepted")
    if bool(row.get("type4_flag", False)):
        parts.append("system_type4")
    if str(row.get("active_time_source", "")).strip() == "lead_time_fallback":
        parts.append("lead_time_fallback")
    return ";".join(parts) if parts else "clean"


def assign_core_scene(df: pd.DataFrame) -> pd.DataFrame:
    enriched = df.copy()
    in_scope = enriched[enriched["scope_bucket"].eq("in_scope")]
    top_scene_values = (
        in_scope.groupby("scene_proxy")["task_id"]
        .nunique()
        .sort_values(ascending=False)
    )
    top_scene_values = top_scene_values[top_scene_values >= 3].head(4).index.tolist()
    top_scene_set = set(top_scene_values)
    enriched["core_scene"] = enriched["scene_proxy"].where(
        enriched["scene_proxy"].isin(top_scene_set),
        np.where(enriched["scope_bucket"].eq("in_scope"), "other", enriched["scene_proxy"]),
    )
    enriched["core_scene_rule_version"] = CORE_SCENE_RULE_VERSION
    return enriched


def compute_worker_scene_metrics(df: pd.DataFrame) -> pd.DataFrame:
    m_mask = _m_tier_mask(df)
    records: list[dict[str, Any]] = []
    for (annotator_id, core_scene), group in df.groupby(["annotator_id", "core_scene"], dropna=False):
        group_m_mask = m_mask.loc[group.index]
        model_support = group[group_m_mask]
        model_with_iou = model_support[model_support["iou"].notna()]
        records.append(
            {
                "annotator_id": annotator_id,
                "core_scene": core_scene,
                "n_annotations": int(len(group)),
                "n_model_usable": int(len(model_support)),
                "mean_iou_m": float(model_with_iou["iou"].mean()) if not model_with_iou.empty else None,
                "mean_active_time": float(group["active_time"].mean()) if group["active_time"].notna().any() else None,
                "r_u_s": float(model_with_iou["iou"].median()) if not model_with_iou.empty else None,
                "r_u_s_lcb": float(model_with_iou["iou"].quantile(0.10)) if not model_with_iou.empty else None,
            }
        )
    if not records:
        return pd.DataFrame(
            columns=[
                "annotator_id",
                "core_scene",
                "n_annotations",
                "n_model_usable",
                "mean_iou_m",
                "mean_active_time",
                "r_u_s",
                "r_u_s_lcb",
                "core_scene_rule_version",
                "activation_status",
                "degeneration_status",
            ]
        )
    long_metrics = pd.DataFrame.from_records(records).sort_values(["annotator_id", "core_scene"])
    long_metrics["core_scene_rule_version"] = CORE_SCENE_RULE_VERSION
    long_metrics["activation_status"] = np.where(
        (long_metrics["core_scene"] != "other") & (long_metrics["n_model_usable"] >= 2),
        "activated",
        "not_activated",
    )
    long_metrics["degeneration_status"] = np.where(
        long_metrics["activation_status"].eq("activated"),
        "scene_specific",
        "fallback_global",
    )
    return long_metrics


def attach_scene_reliability_fields(
    df: pd.DataFrame,
    worker_scene_metrics: pd.DataFrame,
) -> pd.DataFrame:
    if worker_scene_metrics.empty:
        enriched = df.copy()
        for column in (
            "r_u_s",
            "r_u_s_lcb",
            "activation_status",
            "degeneration_status",
            "n_model_usable_scene",
        ):
            enriched[column] = np.nan
        return enriched

    scene_fields = worker_scene_metrics[
        [
            "annotator_id",
            "core_scene",
            "r_u_s",
            "r_u_s_lcb",
            "activation_status",
            "degeneration_status",
            "n_model_usable",
        ]
    ].rename(columns={"n_model_usable": "n_model_usable_scene"})
    return df.merge(scene_fields, on=["annotator_id", "core_scene"], how="left")


def build_core_scene_contract(df: pd.DataFrame) -> pd.DataFrame:
    contract = (
        df.groupby(["scene_proxy", "core_scene"], dropna=False)
        .agg(
            n_rows=("task_id", "count"),
            n_tasks=("task_id", "nunique"),
            n_workers=("annotator_id", "nunique"),
            in_scope_share=("scope_bucket", lambda s: s.astype(str).eq("in_scope").mean()),
        )
        .reset_index()
        .sort_values(["core_scene", "scene_proxy"])
    )
    contract["core_scene_rule_version"] = CORE_SCENE_RULE_VERSION
    contract["routing_role"] = np.where(
        contract["core_scene"].isin({"other"})
        | contract["core_scene"].astype(str).str.startswith("oos::")
        | (contract["in_scope_share"] < 1.0),
        "audit_only",
        "routing_candidate",
    )
    contract["notes"] = np.where(
        contract["routing_role"].eq("routing_candidate"),
        "scene_proxy retained in core_scene v1",
        "collapsed to audit-only or non-routing bucket",
    )

    contract["core_scene_rule_version_v2"] = CORE_SCENE_RULE_VERSION_V2
    contract["min_tasks_required_v2"] = 3
    contract["min_workers_required_v2"] = 2
    contract["strict_eligibility_v2"] = (
        contract["routing_role"].eq("routing_candidate")
        & (contract["n_tasks"] >= contract["min_tasks_required_v2"])
        & (contract["n_workers"] >= contract["min_workers_required_v2"])
    )
    contract["routing_role_v2"] = np.where(
        contract["strict_eligibility_v2"],
        "routing_candidate_strict",
        np.where(
            contract["routing_role"].eq("routing_candidate"),
            "routing_candidate_weak",
            "audit_only",
        ),
    )
    contract["strict_gate_reason_v2"] = np.where(
        contract["routing_role_v2"].eq("routing_candidate_strict"),
        "passed",
        np.where(
            contract["routing_role"].eq("audit_only"),
            "not_routing_candidate_v1",
            np.where(
                contract["n_tasks"] < contract["min_tasks_required_v2"],
                "insufficient_tasks",
                "insufficient_workers",
            ),
        ),
    )
    contract["scene_bucket_v2"] = np.where(
        contract["routing_role_v2"].eq("routing_candidate_strict"),
        "core_scene_strict",
        np.where(
            contract["routing_role_v2"].eq("routing_candidate_weak"),
            "core_scene_weak",
            np.where(
                contract["core_scene"].astype(str).str.startswith("oos::"),
                "fallback_oos",
                "fallback_other",
            ),
        ),
    )
    contract["scene_path_template_v2"] = np.where(
        contract["scene_bucket_v2"].eq("core_scene_strict"),
        "core_scene::<core_scene>",
        "fallback::<core_scene>",
    )
    return contract


def _route_risk_path(row: pd.Series) -> str:
    if row.get("meta_guard_status") == "rejected":
        return "type4_guarded"
    if bool(row.get("type4_flag", False)):
        return "type4_system"
    tier = str(row.get("tim_highest_tier", "outside_T"))
    if tier == "M":
        return "m_tier"
    if tier == "I":
        return "i_tier"
    if tier == "T":
        return "t_tier"
    return "outside_tier"


def _route_scene_path(row: pd.Series, strict_scene_set: set[str]) -> str:
    core_scene = str(row.get("core_scene", ""))
    if core_scene in strict_scene_set:
        return f"core_scene::{core_scene}"
    return f"fallback::{core_scene or 'unknown'}"


def write_route_attribution(
    df: pd.DataFrame,
    core_scene_contract: pd.DataFrame,
    output_dir: Path,
) -> None:
    if df.empty:
        return

    strict_scene_set = set(
        core_scene_contract.loc[
            core_scene_contract["routing_role_v2"].eq("routing_candidate_strict"),
            "core_scene",
        ]
        .astype(str)
        .tolist()
    )

    rank = {"M": 3, "I": 2, "T": 1, "outside_T": 0}
    candidates = df.copy()
    candidates["used_scene_specific_reliability"] = (
        candidates["activation_status"].astype(str).eq("activated")
        & candidates["r_u_s_lcb"].notna()
    )
    candidates["reliability_source"] = np.where(
        candidates["used_scene_specific_reliability"],
        "scene_specific_lcb",
        "global_reliability_lcb",
    )
    candidates["reliability_score"] = np.where(
        candidates["used_scene_specific_reliability"],
        candidates["r_u_s_lcb"],
        candidates["r_u_lcb"],
    )
    candidates["tier_rank"] = candidates["tim_highest_tier"].map(rank).fillna(0).astype(int)
    candidates["is_direct_log"] = candidates["active_time_source"].astype(str).eq("log")
    candidates["reliability_score"] = pd.to_numeric(candidates["reliability_score"], errors="coerce")
    candidates["reliability_score"] = candidates["reliability_score"].fillna(-1.0)
    candidates["scene_path"] = candidates.apply(
        lambda row: _route_scene_path(row, strict_scene_set),
        axis=1,
    )
    candidates["risk_path"] = candidates.apply(_route_risk_path, axis=1)
    candidates["route_attribution_rule_version"] = ROUTE_ATTRIBUTION_RULE_VERSION_V2
    candidates = candidates.sort_values(
        ["task_id", "reliability_score", "tier_rank", "is_direct_log", "annotator_id"],
        ascending=[True, False, False, False, True],
    ).copy()
    candidates["candidate_rank"] = candidates.groupby("task_id").cumcount() + 1
    candidates["candidate_pool_size"] = candidates.groupby("task_id")["task_id"].transform("size")
    candidates["selection_rule_trace"] = (
        "sort:reliability_score_desc>"
        "tier_rank_desc>is_direct_log_desc>annotator_id_asc"
    )

    selected = (
        candidates[candidates["candidate_rank"].eq(1)]
        .copy()
    )
    runner_up = (
        candidates[candidates["candidate_rank"].eq(2)][
            ["task_id", "annotator_id", "reliability_score", "tier_rank"]
        ]
        .rename(
            columns={
                "annotator_id": "runner_up_worker",
                "reliability_score": "runner_up_reliability_score",
                "tier_rank": "runner_up_tier_rank",
            }
        )
    )
    selected = selected.merge(runner_up, on="task_id", how="left")
    selected["winner_margin"] = selected["reliability_score"] - selected[
        "runner_up_reliability_score"
    ]
    selected["decision_reason_chain"] = selected.apply(
        lambda row: ";".join(
            [
                f"risk:{row.get('risk_path', '')}",
                f"scene:{row.get('scene_path', '')}",
                (
                    f"reliability:r_u_s_lcb={row.get('r_u_s_lcb'):.4f}"
                    if bool(row.get("used_scene_specific_reliability", False))
                    and pd.notna(row.get("r_u_s_lcb"))
                    else (
                        f"reliability:r_u_lcb={row.get('r_u_lcb'):.4f}"
                        if pd.notna(row.get("r_u_lcb"))
                        else "reliability:na"
                    )
                ),
                f"tier:{row.get('tim_highest_tier', '')}",
                f"active_time:{row.get('active_time_source', '')}",
                f"meta_guard:{row.get('meta_guard_status', '')}",
                f"rank:{int(row.get('candidate_rank', 1))}/{int(row.get('candidate_pool_size', 1))}",
                (
                    f"margin:{row.get('winner_margin'):.4f}"
                    if pd.notna(row.get("winner_margin"))
                    else "margin:na"
                ),
            ]
        ),
        axis=1,
    )
    selected["route_attribution_rule_version"] = ROUTE_ATTRIBUTION_RULE_VERSION_V2

    candidates[
        [
            "task_id",
            "annotation_id",
            "annotator_id",
            "candidate_rank",
            "candidate_pool_size",
            "reliability_source",
            "reliability_score",
            "tier_rank",
            "is_direct_log",
            "risk_path",
            "scene_path",
            "used_scene_specific_reliability",
            "selection_rule_trace",
            "route_attribution_rule_version",
        ]
    ].to_csv(output_dir / "route_candidates_v1.csv", index=False)

    selected[
        [
            "task_id",
            "risk_path",
            "scene_path",
            "used_scene_specific_reliability",
            "annotator_id",
            "candidate_pool_size",
            "candidate_rank",
            "runner_up_worker",
            "winner_margin",
            "route_attribution_rule_version",
            "decision_reason_chain",
        ]
    ].rename(columns={"annotator_id": "selected_worker"}).to_csv(
        output_dir / "route_attribution_v1.csv",
        index=False,
    )


def write_type4_evidence_v2(df: pd.DataFrame, output_dir: Path) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    evidence = df.copy()
    evidence["risk_path"] = evidence.apply(_route_risk_path, axis=1)
    evidence["evidence_layer_chain"] = evidence.apply(
        lambda row: ";".join(
            [
                layer
                for layer in [
                    "meta_guard" if str(row.get("meta_guard_status", "")).strip() else "",
                    "system_type4" if bool(row.get("type4_flag", False)) else "",
                    (
                        "instrumentation_fallback"
                        if str(row.get("active_time_source", "")) == "lead_time_fallback"
                        else "instrumentation_log"
                    ),
                    (
                        "tier_degraded"
                        if str(row.get("tim_highest_tier", "")) in {"T", "I"}
                        else "tier_model_usable"
                    ),
                ]
                if layer
            ]
        ),
        axis=1,
    )

    columns = [
        "task_id",
        "annotation_id",
        "annotator_id",
        "dataset_group",
        "meta_guard_status",
        "meta_guard_reject_reasons",
        "type4_flag",
        "type4_reason_codes",
        "type4_source",
        "type4_evidence_chain",
        "active_time_source",
        "default_gate_pass",
        "selection_pass",
        "tim_highest_tier",
        "tim_scope",
        "tim_downgrade_reason",
        "tim_reason_chain",
        "scope_bucket",
        "scene_proxy",
        "core_scene",
        "activation_status",
        "degeneration_status",
        "risk_path",
        "evidence_layer_chain",
    ]
    evidence_out = evidence[columns].copy()
    evidence_out.to_csv(output_dir / TYPE4_EVIDENCE_CANONICAL_FILE, index=False)
    # Keep legacy filename for downstream compatibility.
    evidence_out.to_csv(output_dir / "type4_evidence_v2.csv", index=False)
    return evidence_out


def write_freeze_consistency_audit_v2_1(
    row_audit_df: pd.DataFrame,
    type4_evidence_df: pd.DataFrame,
    output_dir: Path,
) -> dict[str, Any]:
    scoped_audit = row_audit_df[row_audit_df["selection_pass"]].copy()
    audit_view = scoped_audit[
        ["task_id", "annotation_id", "type4_flag", "tim_scope", "tim_highest_tier"]
    ].copy()
    evidence_view = type4_evidence_df[
        ["task_id", "annotation_id", "type4_flag", "tim_scope", "tim_highest_tier"]
    ].copy()

    merged = audit_view.merge(
        evidence_view,
        on=["task_id", "annotation_id"],
        how="outer",
        suffixes=("_audit", "_evidence"),
        indicator=True,
    )
    missing_in_evidence = int((merged["_merge"] == "left_only").sum())
    extra_in_evidence = int((merged["_merge"] == "right_only").sum())

    overlap = merged[merged["_merge"] == "both"].copy()
    scope_mismatch = overlap[overlap["tim_scope_audit"] != overlap["tim_scope_evidence"]]
    tier_mismatch = overlap[
        overlap["tim_highest_tier_audit"] != overlap["tim_highest_tier_evidence"]
    ]
    type4_mismatch = overlap[overlap["type4_flag_audit"] != overlap["type4_flag_evidence"]]

    type4_in_m_row_audit = int(
        (audit_view["type4_flag"].fillna(False) & audit_view["tim_scope"].eq("M")).sum()
    )
    type4_in_m_type4_evidence = int(
        (
            type4_evidence_df["type4_flag"].fillna(False)
            & type4_evidence_df["tim_scope"].astype(str).eq("M")
        ).sum()
    )
    consistency_gate_passed = (
        missing_in_evidence == 0
        and extra_in_evidence == 0
        and len(scope_mismatch) == 0
        and len(tier_mismatch) == 0
        and len(type4_mismatch) == 0
        and type4_in_m_row_audit == 0
        and type4_in_m_type4_evidence == 0
    )

    payload = {
        "consistency_gate_version": "type4_tim_consistency_v2_1",
        "consistency_gate_passed": consistency_gate_passed,
        "row_audit_selection_rows": int(len(audit_view)),
        "type4_evidence_rows": int(len(type4_evidence_df)),
        "missing_in_type4_evidence": missing_in_evidence,
        "extra_in_type4_evidence": extra_in_evidence,
        "scope_mismatch_rows": int(len(scope_mismatch)),
        "tier_mismatch_rows": int(len(tier_mismatch)),
        "type4_flag_mismatch_rows": int(len(type4_mismatch)),
        "type4_in_m_row_audit": type4_in_m_row_audit,
        "type4_in_m_type4_evidence": type4_in_m_type4_evidence,
        "mismatch_examples": overlap[
            (overlap["tim_scope_audit"] != overlap["tim_scope_evidence"])
            | (overlap["tim_highest_tier_audit"] != overlap["tim_highest_tier_evidence"])
            | (overlap["type4_flag_audit"] != overlap["type4_flag_evidence"])
        ]
        .head(10)
        .to_dict(orient="records"),
    }
    (output_dir / CONSISTENCY_AUDIT_V2_1_FILE).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    if not consistency_gate_passed:
        raise SystemExit(
            "freeze v2.1 consistency gate failed: TIM row audit and type4 evidence are inconsistent."
        )
    return payload


def add_row_audit_columns(df: pd.DataFrame, selection_df: pd.DataFrame) -> pd.DataFrame:
    audited = df.copy()
    audited["default_gate_pass"] = audited["thesis_input_eligible"]
    audited["default_gate_reason"] = audited.apply(_default_gate_reason, axis=1)
    if selection_df.empty:
        audited["selection_pass"] = audited["default_gate_pass"]
        audited["selection_reason"] = np.where(
            audited["default_gate_pass"],
            "selection_not_provided",
            "default_gate_blocked",
        )
        audited["selection_origin"] = np.where(
            audited["default_gate_pass"],
            "default_thesis_gate",
            "blocked_before_selection",
        )
    else:
        selected = apply_selection_manifest(audited[audited["default_gate_pass"]], selection_df)
        selected_pairs = set(zip(selected["task_id"], selected["annotation_id"]))
        audited["selection_pass"] = audited.apply(
            lambda row: (row["task_id"], row["annotation_id"]) in selected_pairs,
            axis=1,
        )
        audited["selection_reason"] = audited.apply(_selection_reason, axis=1)
        audited["selection_origin"] = np.where(
            audited["default_gate_pass"],
            "selection_manifest",
            "blocked_before_selection",
        )

    audited["tim_rule_default_gate_pass"] = audited["default_gate_pass"]
    audited["tim_rule_in_scope"] = audited["i_included"]
    audited["tim_rule_layout_usable"] = audited["m_included"]
    audited["tim_rule_type4_flag"] = audited["type4_flag"]
    audited["tim_rule_type4_excluded_from_m"] = audited["type4_flag"]
    audited["tim_rule_meta_guard_rejected"] = audited["meta_guard_status"].eq("rejected")
    audited["tim_rule_active_time_fallback"] = audited["active_time_source"].eq(
        "lead_time_fallback"
    )

    audited["tim_t_included"] = audited["default_gate_pass"]
    audited["tim_i_included"] = audited["default_gate_pass"] & audited["i_included"]
    audited["tim_m_included"] = (
        audited["default_gate_pass"] & audited["m_included"] & ~audited["type4_flag"]
    )
    audited["tim_highest_tier"] = audited.apply(_tim_highest_tier, axis=1)
    audited["tim_scope"] = audited["tim_highest_tier"]
    audited["tim_scope_rule"] = np.where(
        ~audited["tim_rule_default_gate_pass"],
        "gate_excluded",
        np.where(
            audited["tim_m_included"],
            "m_tier_layout_usable_clean",
            np.where(
                audited["tim_rule_in_scope"] & audited["tim_rule_layout_usable"] & audited["tim_rule_type4_flag"],
                "i_tier_type4_guarded",
                np.where(
                    audited["tim_rule_in_scope"],
                    "i_tier_in_scope_layout_filtered",
                    "t_tier_scope_filtered",
                ),
            ),
        ),
    )
    audited["tim_downgrade_reason"] = audited.apply(_tim_downgrade_reason, axis=1)
    audited["tim_reason_chain"] = audited.apply(_tim_reason_chain, axis=1)
    audited["tim_mapping_rule_version"] = TIM_MAPPING_RULE_VERSION
    audited["tim_mapping_spec_version"] = TIM_MAPPING_SPEC_VERSION
    return audited


def _default_gate_reason(row: pd.Series) -> str:
    reasons: list[str] = []
    if str(row.get("dataset_group", "")).strip() == "":
        reasons.append("dataset_group_blank")
    if not str(row.get("task_join_status", "")).startswith("matched"):
        reasons.append(f"join_status:{row.get('task_join_status', '')}")
    return "passed" if not reasons else ";".join(reasons)


def _selection_reason(row: pd.Series) -> str:
    if not bool(row.get("default_gate_pass", False)):
        return "default_gate_blocked"
    if bool(row.get("selection_pass", False)):
        return "selected_by_manifest"
    return "filtered_by_manifest"


def _tim_highest_tier(row: pd.Series) -> str:
    if not bool(row.get("tim_t_included", False)):
        return "outside_T"
    if bool(row.get("tim_m_included", False)):
        return "M"
    if bool(row.get("tim_i_included", False)):
        return "I"
    return "T"


def _tim_reason_chain(row: pd.Series) -> str:
    reasons: list[str] = []
    if not bool(row.get("default_gate_pass", False)):
        reasons.append(f"excluded:{row.get('default_gate_reason', '')}")
    else:
        reasons.append("passed_default_gate")
    reasons.append(f"selection:{row.get('selection_reason', '')}")
    if bool(row.get("type4_flag", False)):
        reasons.append(f"type4:{row.get('type4_reason_codes', '')}")
    if row.get("meta_guard_status") == "rejected":
        reasons.append(f"meta_guard:{row.get('meta_guard_reject_reasons', '')}")
    reasons.append(f"active_time:{row.get('active_time_source', '')}")
    if not bool(row.get("i_included", False)):
        reasons.append(f"scope:{row.get('scope_bucket', '')}")
    if bool(row.get("i_included", False)) and not bool(row.get("tim_m_included", False)):
        if bool(row.get("m_included", False)) and bool(row.get("type4_flag", False)):
            reasons.append("m_guard:type4_excluded")
        elif not bool(row.get("m_included", False)):
            reasons.append(f"layout:{row.get('layout_gate_reason', '') or 'layout_unused'}")
    return ";".join([reason for reason in reasons if reason])


def _tim_downgrade_reason(row: pd.Series) -> str:
    if not bool(row.get("default_gate_pass", False)):
        return row.get("default_gate_reason", "")
    reasons: list[str] = []
    if not bool(row.get("i_included", False)):
        reasons.append(f"scope:{row.get('scope_bucket', '')}")
    if bool(row.get("i_included", False)) and not bool(row.get("tim_m_included", False)):
        if bool(row.get("m_included", False)) and bool(row.get("type4_flag", False)):
            reasons.append("m_guard:type4_excluded")
        elif not bool(row.get("m_included", False)):
            reasons.append(f"layout:{row.get('layout_gate_reason', '') or 'layout_unused'}")
    if bool(row.get("type4_flag", False)):
        reasons.append(f"type4:{row.get('type4_reason_codes', '')}")
    if row.get("meta_guard_status") == "rejected":
        reasons.append(f"meta_guard:{row.get('meta_guard_reject_reasons', '')}")
    if str(row.get("active_time_source", "")) == "lead_time_fallback":
        reasons.append("active_time:lead_time_fallback")
    return ";".join(reasons) if reasons else "none"


def compute_worker_formal_fields(df: pd.DataFrame) -> pd.DataFrame:
    m_mask = _m_tier_mask(df)
    records: list[dict[str, Any]] = []
    for annotator_id, group in df.groupby("annotator_id", dropna=False):
        group_m_mask = m_mask.loc[group.index]
        model_support_df = group[group_m_mask].copy()
        model_df = model_support_df[model_support_df["iou"].notna()].copy()
        semi_df = group[group["dataset_group"].astype(str).str.contains("semi", case=False, na=False)]
        presemi_df = group[group["dataset_group"].eq("PreScreen_semi")]
        n_model_usable = int(len(model_support_df))
        n_prescreen_semi = int(len(presemi_df))

        r_u = float(model_df["iou"].median()) if not model_df.empty else None
        r_u_lcb = (
            float(model_df["iou"].quantile(0.10))
            if not model_df.empty
            else None
        )
        if not presemi_df.empty:
            T_u = float(
                (
                    presemi_df["model_issue_primary"]
                    .fillna("")
                    .astype(str)
                    .ne("")
                    & presemi_df["model_issue_primary"].astype(str).ne("acceptable")
                ).mean()
            )
        elif not semi_df.empty:
            T_u = float(
                (
                    semi_df["model_issue_primary"]
                    .fillna("")
                    .astype(str)
                    .ne("")
                    & semi_df["model_issue_primary"].astype(str).ne("acceptable")
                ).mean()
            )
        else:
            T_u = None

        scene_stats = (
            model_df.groupby("core_scene")["iou"]
            .agg(["median", "count"])
            .rename(columns={"median": "scene_median_iou", "count": "n_scene"})
        )
        eligible_scene_stats = scene_stats[scene_stats["n_scene"] >= 2]
        if len(eligible_scene_stats) >= 2:
            C_u = float(
                eligible_scene_stats["scene_median_iou"].max()
                - eligible_scene_stats["scene_median_iou"].min()
            )
        else:
            C_u = None
        n_scene_eligible = int(len(eligible_scene_stats))

        if r_u_lcb is None:
            worker_group = "ungrouped"
            worker_group_reason = "insufficient_model_usable"
        elif r_u_lcb < 0.55:
            worker_group = "noise"
            worker_group_reason = "noise_low_lcb"
        elif T_u is not None and T_u >= 0.50:
            worker_group = "vulnerable"
            worker_group_reason = "vuln_high_trust_risk"
        elif C_u is not None and C_u >= 0.20:
            worker_group = "vulnerable"
            worker_group_reason = "vuln_scene_gap"
        else:
            worker_group = "stable"
            worker_group_reason = "stable_default"

        if n_model_usable < 5 or r_u_lcb is None:
            worker_group_v2 = "ungrouped"
            worker_group_reason_v2 = "insufficient_model_usable_v2"
        elif r_u_lcb < 0.55:
            worker_group_v2 = "noise"
            worker_group_reason_v2 = "noise_low_lcb_v2"
        elif n_prescreen_semi >= 3 and T_u is not None and T_u >= 0.50:
            worker_group_v2 = "vulnerable"
            worker_group_reason_v2 = "vuln_high_trust_risk_v2"
        elif n_scene_eligible >= 2 and C_u is not None and C_u >= 0.20:
            worker_group_v2 = "vulnerable"
            worker_group_reason_v2 = "vuln_scene_gap_v2"
        else:
            worker_group_v2 = "stable"
            worker_group_reason_v2 = "stable_default_v2"

        worker_group_reason_chain_v2 = (
            f"n_model_usable:{n_model_usable};"
            f"n_prescreen_semi:{n_prescreen_semi};"
            f"n_scene_eligible:{n_scene_eligible};"
            f"r_u_lcb:{'na' if r_u_lcb is None else f'{r_u_lcb:.4f}'};"
            f"T_u:{'na' if T_u is None else f'{T_u:.4f}'};"
            f"C_u:{'na' if C_u is None else f'{C_u:.4f}'}"
        )

        records.append(
            {
                "annotator_id": annotator_id,
                "r_u": r_u,
                "r_u_lcb": r_u_lcb,
                "r_u_lcb_rule_version": R_U_LCB_RULE_VERSION,
                "T_u": T_u,
                "C_u": C_u,
                "n_model_usable_support": n_model_usable,
                "n_prescreen_semi_support": n_prescreen_semi,
                "n_scene_eligible_support": n_scene_eligible,
                "worker_group": worker_group,
                "worker_group_reason": worker_group_reason,
                "group_rule_version": WORKER_GROUP_RULE_VERSION,
                "worker_group_v2": worker_group_v2,
                "worker_group_reason_v2": worker_group_reason_v2,
                "worker_group_reason_chain_v2": worker_group_reason_chain_v2,
                "group_rule_version_v2": WORKER_GROUP_RULE_VERSION_V2,
            }
        )
    return pd.DataFrame.from_records(records)


def attach_worker_formal_fields(df: pd.DataFrame) -> pd.DataFrame:
    worker_fields = compute_worker_formal_fields(df)
    return df.merge(worker_fields, on="annotator_id", how="left")


def write_input_summary(
    output_dir: Path,
    raw_df: pd.DataFrame,
    gated_df: pd.DataFrame,
    analysis_df: pd.DataFrame,
    selection_df: pd.DataFrame,
    selection_path: Path,
    selection_mode: str,
    thesis_selection_ready: bool,
    thesis_readiness_status: str,
    thesis_readiness_blockers: list[str],
    stage1_alignment_audit: dict[str, Any],
    selection_main_facing_audit: dict[str, Any],
    selection_provenance_audit: dict[str, Any],
    active_time_audit: dict[str, Any],
    anchor_df: pd.DataFrame,
    trap_df: pd.DataFrame,
) -> None:
    summary = {
        "raw_rows": int(len(raw_df)),
        "rows_after_default_gate": int(len(gated_df)),
        "rows_after_selection": int(len(analysis_df)),
        "unique_tasks_after_selection": int(analysis_df["task_id"].nunique()),
        "selection_manifest_path": str(selection_path),
        "selection_manifest_rows": int(len(selection_df)),
        "selection_manifest_mode": selection_mode,
        "thesis_selection_ready": thesis_selection_ready,
        "thesis_readiness_status": thesis_readiness_status,
        "thesis_readiness_blockers": thesis_readiness_blockers,
        "selection_rule_version": SELECTION_RULE_VERSION,
        "stage1_gate_version": stage1_alignment_audit.get("stage1_gate_version"),
        "stage1_alignment_passed": stage1_alignment_audit.get("stage1_alignment_passed"),
        "stage1_alignment_file": STAGE1_ALIGNMENT_AUDIT_V2_1_FILE,
        "selection_main_facing_gate_version": selection_main_facing_audit.get(
            "selection_main_facing_gate_version"
        ),
        "selection_main_facing_passed": selection_main_facing_audit.get(
            "selection_main_facing_passed"
        ),
        "selection_main_facing_file": SELECTION_MAIN_FACING_AUDIT_V2_1_FILE,
        "selection_provenance_gate_version": selection_provenance_audit.get(
            "selection_provenance_gate_version"
        ),
        "selection_derived_from_autogen_default_gate": selection_provenance_audit.get(
            "selection_derived_from_autogen_default_gate"
        ),
        "selection_source_independent_from_autogen": selection_provenance_audit.get(
            "selection_source_independent_from_autogen"
        ),
        "selection_provenance_file": SELECTION_PROVENANCE_AUDIT_V2_1_FILE,
        "active_time_endpoint_status": active_time_audit.get("active_time_endpoint_status"),
        "active_time_primary_endpoint_ready": active_time_audit.get("primary_endpoint_ready"),
        "active_time_estimand_file": ACTIVE_TIME_ESTIMAND_AUDIT_V2_1_FILE,
        "active_time_source_counts": analysis_df["active_time_source"].value_counts().to_dict(),
        "meta_guard_status_counts": analysis_df["meta_guard_status"].value_counts().to_dict(),
        "dataset_group_counts": analysis_df["dataset_group"].value_counts().to_dict(),
        "scope_bucket_counts": analysis_df["scope_bucket"].value_counts().to_dict(),
        "core_scene_counts": analysis_df["core_scene"].value_counts().to_dict(),
        "source_bank_membership_counts": analysis_df["source_bank_membership"].value_counts().to_dict(),
        "manual_anchor_bank_rows": int(len(anchor_df)),
        "trap_manifest_rows": int(len(trap_df)),
    }
    (output_dir / "analysis_input_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def analyze_worker_scene_matrix(df: pd.DataFrame, output_dir: Path) -> pd.DataFrame:
    print("Generating worker x core-scene artifacts...")
    if df.empty:
        return pd.DataFrame()

    long_metrics = compute_worker_scene_metrics(df)
    long_metrics.to_csv(output_dir / "worker_scene_metrics_long.csv", index=False)

    coverage = df.pivot_table(
        index="annotator_id",
        columns="core_scene",
        values="task_id",
        aggfunc="count",
        fill_value=0,
    )
    coverage.to_csv(output_dir / "worker_scene_coverage_matrix.csv")

    m_mask = _m_tier_mask(df)
    matrix_iou = (
        df[m_mask & df["iou"].notna()]
        .pivot_table(
            index="annotator_id",
            columns="core_scene",
            values="iou",
            aggfunc="mean",
        )
        .sort_index(axis=1)
    )
    matrix_iou.to_csv(output_dir / "worker_scene_iou_matrix.csv")

    if not coverage.empty:
        plt.figure(figsize=(12, 7))
        sns.heatmap(coverage, cmap="Blues", cbar_kws={"label": "Count"})
        plt.title("Worker x Core-Scene Coverage")
        plt.xlabel("Core Scene")
        plt.ylabel("Annotator ID")
        plt.tight_layout()
        plt.savefig(output_dir / "worker_scene_coverage_heatmap.png")
        plt.close()

    if not matrix_iou.empty:
        plt.figure(figsize=(12, 7))
        sns.heatmap(matrix_iou, cmap="viridis", cbar_kws={"label": "Mean IOU"}, vmin=0, vmax=1)
        plt.title("Worker x Core-Scene Mean IOU")
        plt.xlabel("Core Scene")
        plt.ylabel("Annotator ID")
        plt.tight_layout()
        plt.savefig(output_dir / "worker_scene_iou_heatmap.png")
        plt.close()
    return long_metrics


def analyze_worker_profiles(df: pd.DataFrame, output_dir: Path) -> None:
    print("Generating worker profile prototype with formal fields...")
    if df.empty:
        return

    m_mask = _m_tier_mask(df)
    descriptive = (
        df.groupby("annotator_id")
        .agg(
            n_total=("task_id", "count"),
            n_in_scope=("i_included", "sum"),
            n_model_usable=("task_id", lambda s: int(m_mask.loc[s.index].sum())),
            mean_active_time=("active_time", "mean"),
            median_active_time=("active_time", "median"),
            mean_iou_m=("iou", lambda s: s[m_mask.loc[s.index]].mean()),
            fallback_active_time_share=(
                "active_time_source",
                lambda s: s.astype(str).eq("lead_time_fallback").mean(),
            ),
            type4_share=("type4_flag", "mean"),
            mixed_scope_share=("scene_mixed_scope", "mean"),
        )
        .reset_index()
        .sort_values("annotator_id")
    )
    formal = compute_worker_formal_fields(df)
    profile = descriptive.merge(formal, on="annotator_id", how="left")
    profile.to_csv(output_dir / "worker_profiles.csv", index=False)

    if profile["r_u_lcb"].notna().any():
        plt.figure(figsize=(10, 6))
        sns.scatterplot(
            data=profile,
            x="mean_active_time",
            y="r_u_lcb",
            size="n_model_usable",
            sizes=(50, 500),
            hue="worker_group",
            alpha=0.7,
        )
        for _, row in profile.iterrows():
            plt.text(
                row["mean_active_time"],
                (row["r_u_lcb"] if pd.notna(row["r_u_lcb"]) else 0) + 0.01,
                str(row["annotator_id"]),
                fontsize=9,
                ha="center",
            )
        plt.title("Worker Portrait Prototype: Active Time vs r_u_lcb")
        plt.xlabel("Mean Active Time (s)")
        plt.ylabel("r_u_lcb")
        plt.grid(True, linestyle="--", alpha=0.5)
        plt.tight_layout()
        plt.savefig(output_dir / "worker_profile_scatter.png")
        plt.close()

    profile[
        [
            "annotator_id",
            "r_u",
            "r_u_lcb",
            "T_u",
            "C_u",
            "worker_group",
            "worker_group_reason",
            "group_rule_version",
        ]
    ].to_csv(output_dir / "worker_portrait_minimal_v1.csv", index=False)
    profile[
        [
            "annotator_id",
            "r_u",
            "r_u_lcb",
            "T_u",
            "C_u",
            "n_model_usable",
            "n_prescreen_semi_support",
            "n_scene_eligible_support",
            "worker_group_v2",
            "worker_group_reason_v2",
            "worker_group_reason_chain_v2",
            "group_rule_version_v2",
        ]
    ].rename(
        columns={
            "n_prescreen_semi_support": "n_prescreen_semi",
            "n_scene_eligible_support": "n_scene_eligible",
        }
    ).to_csv(output_dir / "worker_portrait_minimal_v2.csv", index=False)


def analyze_process_evidence(df: pd.DataFrame, output_dir: Path) -> None:
    print("Generating process evidence and residual Type 4 audit...")
    if df.empty:
        return

    scope_time = (
        df.groupby(
            ["dataset_group", "scope_bucket", "active_time_source", "meta_guard_status"],
            dropna=False,
        )
        .agg(
            n_rows=("task_id", "count"),
            mean_active_time=("active_time", "mean"),
            median_active_time=("active_time", "median"),
        )
        .reset_index()
        .sort_values(["dataset_group", "scope_bucket", "active_time_source", "meta_guard_status"])
    )
    scope_time.to_csv(output_dir / "process_evidence_scope_time.csv", index=False)

    type4_audit = (
        df.groupby(["dataset_group", "meta_guard_status"], dropna=False)
        .agg(
            n_rows=("task_id", "count"),
            n_type4=("type4_flag", "sum"),
            n_scope_missing=("scope_filled", lambda s: (~s).sum()),
            n_difficulty_missing=("difficulty_filled", lambda s: (~s).sum()),
            n_difficulty_conflict=("difficulty_conflict", "sum"),
            n_model_issue_conflict=("model_issue_conflict", "sum"),
            n_model_issue_missing_required=("model_issue_missing_required", "sum"),
            n_direct_log=("active_time_source", lambda s: s.astype(str).eq("log").sum()),
            n_lead_time_fallback=(
                "active_time_source",
                lambda s: s.astype(str).eq("lead_time_fallback").sum(),
            ),
        )
        .reset_index()
        .sort_values(["dataset_group", "meta_guard_status"])
    )
    type4_audit.to_csv(output_dir / "type4_process_audit.csv", index=False)

    residual = df[
        df["type4_flag"]
        | df["meta_guard_status"].eq("rejected")
        | df["active_time_source"].eq("lead_time_fallback")
    ].copy()
    residual_columns = [
        "task_id",
        "annotation_id",
        "annotator_id",
        "dataset_group",
        "scope_bucket",
        "active_time_source",
        "type4_flag",
        "type4_reason_codes",
        "type4_source",
        "type4_evidence_chain",
        "meta_guard_status",
        "meta_guard_reject_reasons",
        "tim_highest_tier",
        "tim_reason_chain",
    ]
    residual[residual_columns].to_csv(output_dir / "type4_process_residual_rows.csv", index=False)
    residual[
        [
            "task_id",
            "annotation_id",
            "annotator_id",
            "dataset_group",
            "meta_guard_status",
            "active_time_source",
            "type4_reason_codes",
            "type4_source",
            "type4_evidence_chain",
            "tim_scope",
            "tim_downgrade_reason",
        ]
    ].to_csv(output_dir / "type4_evidence_v1.csv", index=False)

    plt.figure(figsize=(10, 6))
    plot_df = df[df["active_time"].notna()].copy()
    sns.boxplot(data=plot_df, x="scope_bucket", y="active_time", showfliers=False)
    plt.title("Active Time Distribution by Scope Bucket")
    plt.xlabel("Scope Bucket")
    plt.ylabel("Active Time (s)")
    plt.grid(True, axis="y", linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.savefig(output_dir / "process_evidence_time_by_scope.png")
    plt.close()


def analyze_tim_metrics(df: pd.DataFrame, output_dir: Path) -> None:
    print("Generating T/I/M transparency-tier metrics...")
    if df.empty:
        return

    i_mask = df["tim_i_included"] if "tim_i_included" in df.columns else df["i_included"]
    m_mask = _m_tier_mask(df)
    tiers = {
        "T_total": df,
        "I_in_scope": df[i_mask],
        "M_model_usable_clean": df[m_mask],
    }

    records: list[dict[str, Any]] = []
    for tier_name, tier_df in tiers.items():
        records.append(
            {
                "tier": tier_name,
                "n_rows": int(len(tier_df)),
                "n_tasks": int(tier_df["task_id"].nunique()),
                "n_workers": int(tier_df["annotator_id"].nunique()),
                "mean_active_time": float(tier_df["active_time"].mean())
                if tier_df["active_time"].notna().any()
                else None,
                "mean_iou": float(tier_df["iou"].mean()) if tier_df["iou"].notna().any() else None,
                "n_type4": int(tier_df["type4_flag"].sum()),
                "n_oos": int(tier_df["scope_bucket"].eq("oos").sum()),
                "n_missing_scope": int(tier_df["scope_bucket"].eq("missing").sum()),
                "n_direct_log": int(tier_df["active_time_source"].eq("log").sum()),
                "n_lead_time_fallback": int(
                    tier_df["active_time_source"].eq("lead_time_fallback").sum()
                ),
            }
        )

    pd.DataFrame.from_records(records).to_csv(output_dir / "tim_metrics.csv", index=False)


def write_tim_row_audit(df: pd.DataFrame, output_dir: Path) -> None:
    df[
        [
            "task_id",
            "annotation_id",
            "annotator_id",
            "dataset_group",
            "default_gate_pass",
            "default_gate_reason",
            "selection_pass",
            "selection_reason",
            "selection_origin",
            "tim_rule_default_gate_pass",
            "tim_rule_in_scope",
            "tim_rule_layout_usable",
            "tim_rule_type4_flag",
            "tim_rule_type4_excluded_from_m",
            "tim_rule_meta_guard_rejected",
            "tim_rule_active_time_fallback",
            "tim_t_included",
            "tim_i_included",
            "tim_m_included",
            "tim_highest_tier",
            "tim_scope",
            "tim_scope_rule",
            "tim_downgrade_reason",
            "tim_reason_chain",
            "tim_mapping_rule_version",
            "tim_mapping_spec_version",
        ]
    ].to_csv(output_dir / "tim_row_audit.csv", index=False)


def write_tim_mapping_spec(output_dir: Path) -> None:
    spec = {
        "tim_mapping_rule_version": TIM_MAPPING_RULE_VERSION,
        "tim_mapping_spec_version": TIM_MAPPING_SPEC_VERSION,
        "tier_order_high_to_low": ["M", "I", "T", "outside_T"],
        "rules": [
            {
                "id": "gate_excluded",
                "if": "default_gate_pass == False",
                "then_tier": "outside_T",
                "notes": "Rows blocked by thesis-facing default gate are outside T.",
            },
            {
                "id": "m_tier_layout_usable_clean",
                "if": "default_gate_pass == True AND m_included == True AND type4_flag == False",
                "then_tier": "M",
                "notes": "Only clean model-usable rows enter M.",
            },
            {
                "id": "i_tier_type4_guarded",
                "if": "default_gate_pass == True AND i_included == True AND m_included == True AND type4_flag == True",
                "then_tier": "I",
                "notes": "Type4 rows are explicitly excluded from M and kept in I.",
            },
            {
                "id": "i_tier_in_scope_layout_filtered",
                "if": "default_gate_pass == True AND i_included == True AND m_included == False",
                "then_tier": "I",
                "notes": "In-scope rows blocked by layout gate stay in I.",
            },
            {
                "id": "t_tier_scope_filtered",
                "if": "default_gate_pass == True AND i_included == False",
                "then_tier": "T",
                "notes": "Scope-filtered rows stay in T.",
            },
        ],
        "downgrade_reason_components": [
            "scope:*",
            "m_guard:type4_excluded",
            "layout:*",
            "type4:*",
            "meta_guard:*",
            "active_time:lead_time_fallback",
        ],
    }
    (output_dir / TIM_MAPPING_SPEC_CANONICAL_FILE).write_text(
        json.dumps(spec, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    # Keep legacy filenames for downstream compatibility while freezing v2.1 rules.
    (output_dir / "tim_mapping_spec_v2.json").write_text(
        json.dumps(spec, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (output_dir / "tim_mapping_spec_v1.json").write_text(
        json.dumps(spec, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def write_tim_rule_summary(df: pd.DataFrame, output_dir: Path) -> None:
    summary = (
        df.groupby(
            [
                "tim_scope_rule",
                "tim_highest_tier",
                "tim_rule_type4_flag",
                "tim_rule_type4_excluded_from_m",
                "tim_rule_meta_guard_rejected",
                "tim_rule_active_time_fallback",
            ],
            dropna=False,
        )
        .agg(
            n_rows=("task_id", "count"),
            n_tasks=("task_id", "nunique"),
            n_workers=("annotator_id", "nunique"),
        )
        .reset_index()
        .sort_values(["tim_scope_rule", "tim_highest_tier"])
    )
    summary.to_csv(output_dir / TIM_RULE_SUMMARY_CANONICAL_FILE, index=False)
    # Keep legacy filenames for downstream compatibility while freezing v2.1 rules.
    summary.to_csv(output_dir / "tim_rule_summary_v2.csv", index=False)
    summary.to_csv(output_dir / "tim_rule_summary_v1.csv", index=False)


def write_core_scene_contract(df: pd.DataFrame, output_dir: Path) -> None:
    contract = build_core_scene_contract(df)
    contract[
        [
            "scene_proxy",
            "core_scene",
            "n_rows",
            "n_tasks",
            "n_workers",
            "in_scope_share",
            "core_scene_rule_version",
            "routing_role",
            "notes",
        ]
    ].to_csv(output_dir / "core_scene_contract_v1.csv", index=False)
    contract[
        [
            "scene_proxy",
            "core_scene",
            "n_rows",
            "n_tasks",
            "n_workers",
            "in_scope_share",
            "core_scene_rule_version_v2",
            "min_tasks_required_v2",
            "min_workers_required_v2",
            "strict_eligibility_v2",
            "routing_role_v2",
            "strict_gate_reason_v2",
            "scene_bucket_v2",
            "scene_path_template_v2",
        ]
    ].to_csv(output_dir / "core_scene_contract_v2.csv", index=False)


def write_worker_portrait_schema(output_dir: Path) -> None:
    schema = {
        "freeze_version": FREEZE_VERSION,
        "fields": [
            {"name": "annotator_id", "type": "string", "meaning": "worker identifier"},
            {"name": "r_u", "type": "float_or_na", "meaning": "global reliability proxy on M-tier rows"},
            {
                "name": "r_u_lcb",
                "type": "float_or_na",
                "meaning": "prototype lower-bound proxy using 0.10 quantile on M-tier IOU",
            },
            {
                "name": "T_u",
                "type": "float_or_na",
                "meaning": "prototype blind-trust risk proxy from PreScreen_semi or semi rows",
            },
            {
                "name": "C_u",
                "type": "float_or_na",
                "meaning": "prototype scene-gap risk proxy across eligible core scenes",
            },
            {
                "name": "worker_group",
                "type": "string_or_na",
                "meaning": "prototype group label derived from r_u_lcb, T_u, C_u",
            },
            {
                "name": "worker_group_reason",
                "type": "string_or_na",
                "meaning": "rule code explaining worker_group assignment",
            },
            {
                "name": "group_rule_version",
                "type": "string_or_na",
                "meaning": "version of worker grouping prototype rule",
            },
        ],
    }
    (output_dir / "worker_portrait_schema_v1.json").write_text(
        json.dumps(schema, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    schema_v2 = {
        "freeze_version": FREEZE_VERSION_V2,
        "fields": [
            {"name": "annotator_id", "type": "string", "meaning": "worker identifier"},
            {"name": "r_u", "type": "float_or_na", "meaning": "global reliability proxy on M-tier rows"},
            {
                "name": "r_u_lcb",
                "type": "float_or_na",
                "meaning": "global lower-bound proxy on M-tier rows",
            },
            {"name": "T_u", "type": "float_or_na", "meaning": "PreScreen_semi trust-risk proxy"},
            {"name": "C_u", "type": "float_or_na", "meaning": "cross-scene reliability gap proxy"},
            {"name": "n_model_usable", "type": "int", "meaning": "count of M-tier rows"},
            {"name": "n_prescreen_semi", "type": "int", "meaning": "count of PreScreen_semi rows"},
            {"name": "n_scene_eligible", "type": "int", "meaning": "core scenes with >=2 M-tier rows"},
            {"name": "worker_group_v2", "type": "string", "meaning": "stabilized worker group label"},
            {"name": "worker_group_reason_v2", "type": "string", "meaning": "stabilized reason code"},
            {
                "name": "worker_group_reason_chain_v2",
                "type": "string",
                "meaning": "metric-backed decision chain for worker_group_v2",
            },
            {
                "name": "group_rule_version_v2",
                "type": "string",
                "meaning": "version of stabilized worker grouping rule",
            },
        ],
    }
    (output_dir / "worker_portrait_schema_v2.json").write_text(
        json.dumps(schema_v2, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def write_freeze_manifest(
    df: pd.DataFrame,
    output_dir: Path,
    selection_path: Path,
    selection_mode: str,
    thesis_selection_ready: bool,
    thesis_readiness_status: str,
    thesis_readiness_blockers: list[str],
    stage1_alignment_audit: dict[str, Any],
    selection_main_facing_audit: dict[str, Any],
    selection_provenance_audit: dict[str, Any],
    active_time_audit: dict[str, Any],
) -> None:
    manifest = {
        "freeze_version": FREEZE_VERSION,
        "core_scene_rule_version": CORE_SCENE_RULE_VERSION,
        "worker_group_rule_version": WORKER_GROUP_RULE_VERSION,
        "r_u_lcb_rule_version": R_U_LCB_RULE_VERSION,
        "tim_mapping_rule_version": TIM_MAPPING_RULE_VERSION,
        "type4_link_rule_version": TYPE4_LINK_RULE_VERSION,
        "selection_rule_version": SELECTION_RULE_VERSION,
        "selection_manifest_path": str(selection_path),
        "selection_manifest_mode": selection_mode,
        "thesis_selection_ready": thesis_selection_ready,
        "thesis_readiness_status": thesis_readiness_status,
        "thesis_readiness_blockers": thesis_readiness_blockers,
        "stage1_gate_version": stage1_alignment_audit.get("stage1_gate_version"),
        "stage1_alignment_passed": stage1_alignment_audit.get("stage1_alignment_passed"),
        "stage1_alignment_file": STAGE1_ALIGNMENT_AUDIT_V2_1_FILE,
        "selection_main_facing_gate_version": selection_main_facing_audit.get(
            "selection_main_facing_gate_version"
        ),
        "selection_main_facing_passed": selection_main_facing_audit.get(
            "selection_main_facing_passed"
        ),
        "selection_main_facing_file": SELECTION_MAIN_FACING_AUDIT_V2_1_FILE,
        "selection_provenance_gate_version": selection_provenance_audit.get(
            "selection_provenance_gate_version"
        ),
        "selection_derived_from_autogen_default_gate": selection_provenance_audit.get(
            "selection_derived_from_autogen_default_gate"
        ),
        "selection_source_independent_from_autogen": selection_provenance_audit.get(
            "selection_source_independent_from_autogen"
        ),
        "selection_provenance_file": SELECTION_PROVENANCE_AUDIT_V2_1_FILE,
        "active_time_endpoint_status": active_time_audit.get("active_time_endpoint_status"),
        "active_time_primary_endpoint_ready": active_time_audit.get("primary_endpoint_ready"),
        "active_time_estimand_file": ACTIVE_TIME_ESTIMAND_AUDIT_V2_1_FILE,
        "n_rows": int(len(df)),
        "n_tasks": int(df["task_id"].nunique()),
        "n_workers": int(df["annotator_id"].nunique()),
    }
    (output_dir / "formal_prep_freeze_v1_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def write_freeze_manifest_v2(
    df: pd.DataFrame,
    output_dir: Path,
    selection_path: Path,
    selection_mode: str,
    thesis_selection_ready: bool,
    thesis_readiness_status: str,
    thesis_readiness_blockers: list[str],
    stage1_alignment_audit: dict[str, Any],
    selection_main_facing_audit: dict[str, Any],
    selection_provenance_audit: dict[str, Any],
    active_time_audit: dict[str, Any],
    consistency_audit: dict[str, Any],
) -> None:
    manifest = {
        "freeze_version": FREEZE_VERSION_V2_1,
        "core_scene_rule_version_v1": CORE_SCENE_RULE_VERSION,
        "core_scene_rule_version_v2": CORE_SCENE_RULE_VERSION_V2,
        "worker_group_rule_version_v1": WORKER_GROUP_RULE_VERSION,
        "worker_group_rule_version_v2": WORKER_GROUP_RULE_VERSION_V2,
        "r_u_lcb_rule_version": R_U_LCB_RULE_VERSION,
        "tim_mapping_rule_version": TIM_MAPPING_RULE_VERSION,
        "tim_mapping_spec_version": TIM_MAPPING_SPEC_VERSION,
        "type4_link_rule_version_v1": TYPE4_LINK_RULE_VERSION,
        "type4_link_rule_version_v2": TYPE4_LINK_RULE_VERSION_V2,
        "route_attribution_rule_version_v1": ROUTE_ATTRIBUTION_RULE_VERSION,
        "route_attribution_rule_version_v2": ROUTE_ATTRIBUTION_RULE_VERSION_V2,
        "selection_rule_version": SELECTION_RULE_VERSION,
        "selection_manifest_path": str(selection_path),
        "selection_manifest_mode": selection_mode,
        "thesis_selection_ready": thesis_selection_ready,
        "thesis_readiness_status": thesis_readiness_status,
        "thesis_readiness_blockers": thesis_readiness_blockers,
        "stage1_gate_version": stage1_alignment_audit.get("stage1_gate_version"),
        "stage1_alignment_passed": stage1_alignment_audit.get("stage1_alignment_passed"),
        "stage1_alignment_file": STAGE1_ALIGNMENT_AUDIT_V2_1_FILE,
        "selection_main_facing_gate_version": selection_main_facing_audit.get(
            "selection_main_facing_gate_version"
        ),
        "selection_main_facing_passed": selection_main_facing_audit.get(
            "selection_main_facing_passed"
        ),
        "selection_main_facing_file": SELECTION_MAIN_FACING_AUDIT_V2_1_FILE,
        "selection_provenance_gate_version": selection_provenance_audit.get(
            "selection_provenance_gate_version"
        ),
        "selection_derived_from_autogen_default_gate": selection_provenance_audit.get(
            "selection_derived_from_autogen_default_gate"
        ),
        "selection_source_independent_from_autogen": selection_provenance_audit.get(
            "selection_source_independent_from_autogen"
        ),
        "selection_provenance_file": SELECTION_PROVENANCE_AUDIT_V2_1_FILE,
        "active_time_endpoint_status": active_time_audit.get("active_time_endpoint_status"),
        "active_time_primary_endpoint_ready": active_time_audit.get("primary_endpoint_ready"),
        "active_time_estimand_file": ACTIVE_TIME_ESTIMAND_AUDIT_V2_1_FILE,
        "consistency_gate_version": consistency_audit["consistency_gate_version"],
        "consistency_gate_passed": consistency_audit["consistency_gate_passed"],
        "consistency_audit_file": CONSISTENCY_AUDIT_V2_1_FILE,
        "n_rows": int(len(df)),
        "n_tasks": int(df["task_id"].nunique()),
        "n_workers": int(df["annotator_id"].nunique()),
        "artifact_naming_policy": "canonical_v2_1_with_legacy_aliases",
        "artifacts": [
            TIM_MAPPING_SPEC_CANONICAL_FILE,
            TIM_RULE_SUMMARY_CANONICAL_FILE,
            "core_scene_contract_v2.csv",
            "worker_portrait_minimal_v2.csv",
            "worker_portrait_schema_v2.json",
            TYPE4_EVIDENCE_CANONICAL_FILE,
            "route_candidates_v1.csv",
            "route_attribution_v1.csv",
            CONSISTENCY_AUDIT_V2_1_FILE,
            STAGE1_ALIGNMENT_AUDIT_V2_1_FILE,
            SELECTION_MAIN_FACING_AUDIT_V2_1_FILE,
            SELECTION_PROVENANCE_AUDIT_V2_1_FILE,
            ACTIVE_TIME_ESTIMAND_AUDIT_V2_1_FILE,
        ],
        "legacy_alias_artifacts": [
            "tim_mapping_spec_v1.json",
            "tim_mapping_spec_v2.json",
            "tim_rule_summary_v1.csv",
            "tim_rule_summary_v2.csv",
            "type4_evidence_v2.csv",
        ],
    }
    (output_dir / "formal_prep_freeze_v2_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (output_dir / "formal_prep_freeze_v2_1_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    registry_df = _load_csv(args.registry, "registry")
    anchor_df = _load_csv(args.anchor_index, "anchor index", required=False)
    trap_df = _load_csv(args.trap_manifest, "trap manifest", required=False)
    quality_df = _load_csv(args.quality_report, "quality report")
    meta_guard_accepted_df = _load_csv(
        args.meta_guard_accepted,
        "meta guard accepted",
        required=False,
    )
    meta_guard_rejected_df = _load_csv(
        args.meta_guard_rejected,
        "meta guard rejected",
        required=False,
    )
    loaded_selection_df = load_selection_manifest(args.selection_manifest)

    raw_df = build_analysis_frame(registry_df, quality_df)
    raw_df = attach_meta_guard_status(raw_df, meta_guard_accepted_df, meta_guard_rejected_df)
    raw_df = assign_core_scene(raw_df)
    selection_df, resolved_selection_path, selection_mode, thesis_selection_ready = resolve_selection_manifest(
        raw_df,
        loaded_selection_df,
        args.selection_manifest,
        args.output_dir,
    )
    stage1_alignment_audit = write_stage1_alignment_audit_v2_1(
        args.phase1_alignment_manifest,
        args.output_dir,
    )
    raw_df = add_row_audit_columns(raw_df, selection_df)

    gated_df = raw_df[raw_df["default_gate_pass"]].copy()
    analysis_df = raw_df[raw_df["selection_pass"]].copy()
    analysis_df = attach_manifest_membership(analysis_df, anchor_df, trap_df)
    analysis_df = attach_worker_formal_fields(analysis_df)

    if analysis_df.empty:
        raise SystemExit("No rows remain after gate + selection filtering.")

    selection_main_facing_audit = write_selection_main_facing_audit_v2_1(
        analysis_df,
        selection_mode,
        args.output_dir,
    )
    selection_provenance_audit = write_selection_provenance_audit_v2_1(
        resolved_selection_path,
        selection_mode,
        args.output_dir,
    )
    thesis_selection_ready, thesis_readiness_status, thesis_readiness_blockers = derive_thesis_readiness(
        selection_mode,
        thesis_selection_ready,
        stage1_alignment_audit,
        selection_main_facing_audit,
        selection_provenance_audit,
    )
    active_time_audit = write_active_time_estimand_audit_v2_1(analysis_df, args.output_dir)

    write_input_summary(
        args.output_dir,
        raw_df,
        gated_df,
        analysis_df,
        selection_df,
        resolved_selection_path,
        selection_mode,
        thesis_selection_ready,
        thesis_readiness_status,
        thesis_readiness_blockers,
        stage1_alignment_audit,
        selection_main_facing_audit,
        selection_provenance_audit,
        active_time_audit,
        anchor_df,
        trap_df,
    )
    worker_scene_metrics = analyze_worker_scene_matrix(analysis_df, args.output_dir)
    analysis_df = attach_scene_reliability_fields(analysis_df, worker_scene_metrics)
    analyze_worker_profiles(analysis_df, args.output_dir)
    analyze_process_evidence(analysis_df, args.output_dir)
    type4_evidence_df = write_type4_evidence_v2(analysis_df, args.output_dir)
    analyze_tim_metrics(analysis_df, args.output_dir)
    write_tim_row_audit(raw_df, args.output_dir)
    consistency_audit = write_freeze_consistency_audit_v2_1(
        raw_df,
        type4_evidence_df,
        args.output_dir,
    )
    write_tim_mapping_spec(args.output_dir)
    write_tim_rule_summary(raw_df, args.output_dir)
    write_core_scene_contract(analysis_df, args.output_dir)
    core_scene_contract = build_core_scene_contract(analysis_df)
    write_route_attribution(analysis_df, core_scene_contract, args.output_dir)
    write_worker_portrait_schema(args.output_dir)
    write_freeze_manifest(
        analysis_df,
        args.output_dir,
        resolved_selection_path,
        selection_mode,
        thesis_selection_ready,
        thesis_readiness_status,
        thesis_readiness_blockers,
        stage1_alignment_audit,
        selection_main_facing_audit,
        selection_provenance_audit,
        active_time_audit,
    )
    write_freeze_manifest_v2(
        analysis_df,
        args.output_dir,
        resolved_selection_path,
        selection_mode,
        thesis_selection_ready,
        thesis_readiness_status,
        thesis_readiness_blockers,
        stage1_alignment_audit,
        selection_main_facing_audit,
        selection_provenance_audit,
        active_time_audit,
        consistency_audit,
    )


if __name__ == "__main__":
    main()
