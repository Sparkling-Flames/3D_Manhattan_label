from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


DEFAULT_OUT_DIR = Path("analysis_results/experiment_visual_audit")
DEFAULT_SCOPE_MISSING_LABEL = "(missing)"
TRUE_VALUES = {"1", "true", "yes", "y", "t"}
QUALITY_METRIC_CANDIDATES = (
    "iou",
    "layout_2d_iou",
    "layout_3d_iou",
    "iou_to_consensus_loo",
)
RELIABILITY_METRIC_CANDIDATES = (
    "iou_to_consensus_loo",
    "iou_to_consensus",
    "quality",
)
ACTIVE_LOG_SIGNAL_KEYS = (
    "parse_error_count",
    "unknown_task_count",
    "unknown_annotator_count",
    "unknown_project_count",
    "unknown_session_count",
    "missing_script_version_count",
    "multi_session_pair_count",
)
FORMAL_VISUAL_FIELDS = (
    ("task_id", ("task_id",)),
    ("annotator_id", ("annotator_id",)),
    ("dataset_group", ("dataset_group",)),
    ("condition", ("condition",)),
    ("scope", ("scope",)),
    ("is_oos", ("is_oos",)),
    ("scope_filled", ("scope_filled", "scope_missing")),
    ("difficulty", ("difficulty",)),
    ("difficulty_filled", ("difficulty_filled", "difficulty_missing")),
    ("difficulty_conflict", ("difficulty_conflict",)),
    ("model_issue", ("model_issue",)),
    ("model_issue_primary", ("model_issue_primary",)),
    ("model_issue_required", ("model_issue_required",)),
    ("model_issue_missing_required", ("model_issue_missing_required",)),
    ("model_issue_conflict", ("model_issue_conflict",)),
    ("type3_flag", ("type3_flag",)),
    ("type4_flag", ("type4_flag", "scope_filled", "difficulty_filled", "difficulty_conflict", "model_issue_missing_required", "model_issue_conflict")),
    ("active_time", ("active_time",)),
    ("session_count", ("session_count", "active_time_session_count")),
    ("has_short_time_flag", ("has_short_time_flag", "active_time")),
    ("has_long_time_flag", ("has_long_time_flag", "active_time")),
    ("has_unknown_id_flag", ("has_unknown_id_flag", "project_id", "export_project_id")),
    ("project_id", ("project_id", "export_project_id")),
    ("script_version", ("script_version",)),
    ("layout_used", ("layout_used",)),
    ("layout_gate_reason", ("layout_gate_reason",)),
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build an experiment-level visualization and audit pack from a quality_report CSV."
    )
    parser.add_argument("--quality-csv", required=True, type=Path)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR, type=Path)
    parser.add_argument(
        "--tag",
        default=None,
        help="Optional output folder name. Defaults to the quality CSV stem.",
    )
    parser.add_argument(
        "--active-log-summary-json",
        default=None,
        type=Path,
        help="Optional overall summary JSON from tools/thesis_main/analysis/audit_active_log_quality.py",
    )
    parser.add_argument(
        "--active-log-per-file-csv",
        default=None,
        type=Path,
        help="Optional per-file CSV from tools/thesis_main/analysis/audit_active_log_quality.py",
    )
    return parser.parse_args(argv)


def _normalize_text(series: pd.Series, missing_label: str = DEFAULT_SCOPE_MISSING_LABEL) -> pd.Series:
    normalized = series.fillna("").astype(str).str.strip()
    return normalized.mask(normalized.eq(""), missing_label)


def _first_existing_column(df: pd.DataFrame, candidates: Iterable[str]) -> str | None:
    for column in candidates:
        if column in df.columns:
            return column
    return None


def _coerce_bool_series(df: pd.DataFrame, column: str, default: bool = False) -> pd.Series:
    if column not in df.columns:
        return pd.Series([default] * len(df), index=df.index, dtype=bool)
    raw = df[column]
    if pd.api.types.is_bool_dtype(raw):
        return raw.fillna(default).astype(bool)
    if pd.api.types.is_numeric_dtype(raw):
        return raw.fillna(int(default)).astype(int).astype(bool)
    normalized = raw.fillna("").astype(str).str.strip().str.lower()
    return normalized.isin(TRUE_VALUES)


def _choose_metric_column(df: pd.DataFrame, candidates: Iterable[str]) -> str | None:
    for column in candidates:
        if column in df.columns:
            numeric = pd.to_numeric(df[column], errors="coerce")
            if numeric.notna().any():
                return column
    return None


def _tokenize_multilabel(value: object) -> list[str]:
    if value is None:
        return []
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none"}:
        return []
    tokens: list[str] = []
    seen: set[str] = set()
    for token in text.replace(",", ";").split(";"):
        cleaned = token.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        tokens.append(cleaned)
    return tokens


def _scope_bucket_from_frame(df: pd.DataFrame) -> pd.Series:
    scope_text = _normalize_text(df.get("scope", pd.Series(index=df.index, dtype=object)))
    if "scope_filled" in df.columns:
        scope_missing = ~_coerce_bool_series(df, "scope_filled", default=False)
    else:
        scope_missing = _coerce_bool_series(df, "scope_missing")
        if "scope_missing" not in df.columns:
            scope_missing = scope_text.eq(DEFAULT_SCOPE_MISSING_LABEL)

    if "is_oos" in df.columns:
        is_oos = _coerce_bool_series(df, "is_oos")
    else:
        lower = scope_text.str.lower()
        is_oos = lower.str.startswith("oos") | lower.str.contains("out_of_scope")

    bucket = pd.Series(["in_scope"] * len(df), index=df.index, dtype=object)
    bucket = bucket.mask(is_oos, "oos")
    bucket = bucket.mask(scope_missing, "missing")
    return bucket


def prepare_quality_frame(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str | None]]:
    result = df.copy()

    for column in (
        "task_id",
        "base_task_id",
        "annotation_id",
        "annotator_id",
        "dataset_group",
        "condition",
        "condition_clean",
        "project_id",
        "export_project_id",
        "script_version",
        "active_time_source",
        "active_time_match_status",
    ):
        if column in result.columns:
            result[column] = _normalize_text(result[column])

    result["scope_bucket"] = _scope_bucket_from_frame(result)
    result["in_scope_bool"] = result["scope_bucket"].eq("in_scope")
    result["layout_used_bool"] = _coerce_bool_series(result, "layout_used")
    result["type3_flag_bool"] = _coerce_bool_series(result, "type3_flag")
    result["m_included_bool"] = result["in_scope_bool"] & ~result["type3_flag_bool"]
    result["difficulty_conflict_bool"] = _coerce_bool_series(result, "difficulty_conflict")
    result["model_issue_conflict_bool"] = _coerce_bool_series(result, "model_issue_conflict")
    result["model_issue_missing_required_bool"] = _coerce_bool_series(result, "model_issue_missing_required")
    if "difficulty_filled" in result.columns:
        result["difficulty_missing_bool"] = ~_coerce_bool_series(result, "difficulty_filled", default=False)
    else:
        result["difficulty_missing_bool"] = _coerce_bool_series(result, "difficulty_missing")
    if "scope_filled" in result.columns:
        result["scope_missing_bool"] = ~_coerce_bool_series(result, "scope_filled", default=False)
    else:
        result["scope_missing_bool"] = _coerce_bool_series(result, "scope_missing")
    result["task_scope_is_mixed_bool"] = _coerce_bool_series(result, "task_scope_is_mixed")
    result["model_issue_required_bool"] = _coerce_bool_series(result, "model_issue_required")
    result["scope_filled_bool"] = ~result["scope_missing_bool"]
    result["difficulty_filled_bool"] = ~result["difficulty_missing_bool"]

    result["active_time_value"] = pd.to_numeric(result.get("active_time"), errors="coerce")
    result["boundary_rmse_value"] = pd.to_numeric(result.get("boundary_rmse_px"), errors="coerce")
    session_count_col = _first_existing_column(result, ("session_count", "active_time_session_count"))
    result["session_count_value"] = pd.to_numeric(result.get(session_count_col), errors="coerce")
    project_id_col = _first_existing_column(result, ("project_id", "export_project_id"))
    result["project_id_value"] = (
        _normalize_text(result[project_id_col])
        if project_id_col is not None
        else pd.Series([DEFAULT_SCOPE_MISSING_LABEL] * len(result), index=result.index, dtype=object)
    )
    result["script_version_value"] = (
        _normalize_text(result["script_version"])
        if "script_version" in result.columns
        else pd.Series([DEFAULT_SCOPE_MISSING_LABEL] * len(result), index=result.index, dtype=object)
    )
    result["has_short_time_flag_bool"] = (
        _coerce_bool_series(result, "has_short_time_flag")
        if "has_short_time_flag" in result.columns
        else result["active_time_value"].fillna(float("inf")).lt(1.0)
    )
    result["has_long_time_flag_bool"] = (
        _coerce_bool_series(result, "has_long_time_flag")
        if "has_long_time_flag" in result.columns
        else result["active_time_value"].fillna(-1.0).gt(3600.0)
    )
    result["has_unknown_id_flag_bool"] = (
        _coerce_bool_series(result, "has_unknown_id_flag")
        if "has_unknown_id_flag" in result.columns
        else (
            result["task_id"].fillna("").astype(str).str.strip().str.lower().isin({"", "unknown"})
            | result["annotator_id"].fillna("").astype(str).str.strip().str.lower().isin({"", "unknown"})
            | result["project_id_value"].fillna("").astype(str).str.strip().str.lower().isin({"", "unknown", DEFAULT_SCOPE_MISSING_LABEL.lower()})
        )
    )
    result["missing_script_version_bool"] = result["script_version_value"].str.lower().isin(
        {DEFAULT_SCOPE_MISSING_LABEL.lower(), "", "unknown"}
    )
    result["multi_session_bool"] = result["session_count_value"].fillna(0).gt(1)

    quality_metric = _choose_metric_column(result, QUALITY_METRIC_CANDIDATES)
    reliability_metric = _choose_metric_column(result, RELIABILITY_METRIC_CANDIDATES)

    result["metric_primary"] = (
        pd.to_numeric(result[quality_metric], errors="coerce")
        if quality_metric is not None
        else pd.Series([float("nan")] * len(result), index=result.index, dtype="float64")
    )
    result["reliability_primary"] = (
        pd.to_numeric(result[reliability_metric], errors="coerce")
        if reliability_metric is not None
        else pd.Series([float("nan")] * len(result), index=result.index, dtype="float64")
    )

    if {"pred_n_pairs", "ann_n_pairs"}.issubset(result.columns):
        result["delta_n_pairs"] = (
            pd.to_numeric(result["pred_n_pairs"], errors="coerce")
            - pd.to_numeric(result["ann_n_pairs"], errors="coerce")
        )
    else:
        result["delta_n_pairs"] = pd.Series([float("nan")] * len(result), index=result.index, dtype="float64")

    if "type4_flag" in result.columns:
        result["type4_flag_bool"] = _coerce_bool_series(result, "type4_flag")
        result["type4_from_fallback_bool"] = False
    else:
        result["type4_flag_bool"] = (
            result["scope_missing_bool"]
            | result["difficulty_missing_bool"]
            | result["difficulty_conflict_bool"]
            | result["model_issue_missing_required_bool"]
            | result["model_issue_conflict_bool"]
        )
        result["type4_from_fallback_bool"] = True

    metric_info = {
        "quality_metric_column": quality_metric,
        "reliability_metric_column": reliability_metric,
        "session_count_column": session_count_col,
        "project_id_column": project_id_col,
        "type4_source": "type4_flag" if "type4_flag" in result.columns else "derived_fallback",
    }
    return result, metric_info


def build_tier_table(df: pd.DataFrame) -> pd.DataFrame:
    tiers = [
        ("T", df.index),
        ("I", df.index[df["in_scope_bool"]]),
        ("M", df.index[df["m_included_bool"]]),
    ]
    rows: list[dict[str, object]] = []
    for tier_name, tier_index in tiers:
        subset = df.loc[tier_index]
        rows.append(
            {
                "tier": tier_name,
                "n_rows": int(len(subset)),
                "n_tasks": int(subset["task_id"].nunique()) if "task_id" in subset.columns else 0,
                "n_annotators": int(subset["annotator_id"].nunique()) if "annotator_id" in subset.columns else 0,
            }
        )
    return pd.DataFrame(rows)


def build_scope_conflict_table(df: pd.DataFrame) -> pd.DataFrame:
    if "task_id" not in df.columns or "scope" not in df.columns:
        return pd.DataFrame(
            columns=(
                "task_id",
                "dataset_group",
                "n_rows",
                "n_annotators",
                "scope_values",
                "scope_bucket_values",
                "has_conflict",
            )
        )

    rows: list[dict[str, object]] = []
    for task_id, group in df.groupby("task_id", dropna=False):
        scope_values = sorted({value for value in _normalize_text(group["scope"]).tolist()})
        bucket_values = sorted({value for value in group["scope_bucket"].astype(str).tolist()})
        has_conflict = len(scope_values) > 1 or len(bucket_values) > 1 or bool(group["task_scope_is_mixed_bool"].any())
        if not has_conflict:
            continue
        dataset_group = ""
        for candidate in ("dataset_group", "condition_clean", "condition"):
            if candidate in group.columns:
                values = [value for value in _normalize_text(group[candidate]).tolist() if value != DEFAULT_SCOPE_MISSING_LABEL]
                if values:
                    dataset_group = values[0]
                    break
        rows.append(
            {
                "task_id": str(task_id),
                "dataset_group": dataset_group,
                "n_rows": int(len(group)),
                "n_annotators": int(group["annotator_id"].nunique()) if "annotator_id" in group.columns else 0,
                "scope_values": ";".join(scope_values),
                "scope_bucket_values": ";".join(bucket_values),
                "has_conflict": True,
            }
        )

    if not rows:
        return pd.DataFrame(
            columns=(
                "task_id",
                "dataset_group",
                "n_rows",
                "n_annotators",
                "scope_values",
                "scope_bucket_values",
                "has_conflict",
            )
        )
    return pd.DataFrame(rows).sort_values(["task_id"]).reset_index(drop=True)


def build_field_audit_table(df: pd.DataFrame, metric_info: dict[str, str | None]) -> pd.DataFrame:
    mixed_scope_tasks = build_scope_conflict_table(df)
    payload = {
        "n_rows": int(len(df)),
        "n_tasks": int(df["task_id"].nunique()) if "task_id" in df.columns else 0,
        "n_annotators": int(df["annotator_id"].nunique()) if "annotator_id" in df.columns else 0,
        "n_t_rows": int(len(df)),
        "n_i_rows": int(df["in_scope_bool"].sum()),
        "n_m_rows": int(df["m_included_bool"].sum()),
        "n_oos_rows": int((df["scope_bucket"] == "oos").sum()),
        "n_scope_missing_rows": int(df["scope_missing_bool"].sum()),
        "n_type3_rows": int(df["type3_flag_bool"].sum()),
        "n_layout_gate_fail_rows": int((~df["layout_used_bool"]).sum()),
        "n_layout_usable_rows": int(df["layout_used_bool"].sum()),
        "n_difficulty_missing_rows": int(df["difficulty_missing_bool"].sum()),
        "n_difficulty_conflict_rows": int(df["difficulty_conflict_bool"].sum()),
        "n_model_issue_required_rows": int(df["model_issue_required_bool"].sum()),
        "n_model_issue_missing_required_rows": int(df["model_issue_missing_required_bool"].sum()),
        "n_model_issue_conflict_rows": int(df["model_issue_conflict_bool"].sum()),
        "n_type4_rows": int(df["type4_flag_bool"].sum()),
        "n_active_time_missing_rows": int(df["active_time_value"].isna().sum()),
        "n_active_time_zero_rows": int((df["active_time_value"].fillna(-1) == 0).sum()),
        "n_short_time_rows": int(df["has_short_time_flag_bool"].sum()),
        "n_long_time_rows": int(df["has_long_time_flag_bool"].sum()),
        "n_unknown_id_rows": int(df["has_unknown_id_flag_bool"].sum()),
        "n_multi_session_rows": int(df["multi_session_bool"].sum()),
        "n_missing_script_version_rows": int(df["missing_script_version_bool"].sum()),
        "n_mixed_scope_tasks": int(len(mixed_scope_tasks)),
        "quality_metric_column": metric_info.get("quality_metric_column") or "",
        "reliability_metric_column": metric_info.get("reliability_metric_column") or "",
        "session_count_column": metric_info.get("session_count_column") or "",
        "project_id_column": metric_info.get("project_id_column") or "",
        "type4_source": metric_info.get("type4_source") or "",
    }
    return pd.DataFrame([payload])


def build_delta_pairs_table(df: pd.DataFrame) -> pd.DataFrame:
    if df["delta_n_pairs"].notna().sum() == 0:
        return pd.DataFrame(
            columns=(
                "delta_bin",
                "n_rows",
                "n_tasks",
                "median_metric_primary",
                "median_boundary_rmse_px",
                "median_active_time",
            )
        )

    subset = df.loc[df["delta_n_pairs"].notna()].copy()
    if (subset["scope_bucket"] == "in_scope").any():
        subset = subset.loc[subset["scope_bucket"] == "in_scope"].copy()

    def _bin_value(value: float) -> str:
        integer = int(round(value))
        if integer <= -2:
            return "<=-2"
        if integer >= 3:
            return ">=3"
        return str(integer)

    subset["delta_bin"] = subset["delta_n_pairs"].map(_bin_value)
    order = ["<=-2", "-1", "0", "1", "2", ">=3"]
    grouped = (
        subset.groupby("delta_bin", dropna=False)
        .agg(
            n_rows=("task_id", "size"),
            n_tasks=("task_id", "nunique"),
            median_metric_primary=("metric_primary", "median"),
            median_boundary_rmse_px=("boundary_rmse_value", "median"),
            median_active_time=("active_time_value", "median"),
        )
        .reset_index()
    )
    grouped["delta_bin"] = pd.Categorical(grouped["delta_bin"], categories=order, ordered=True)
    grouped = grouped.sort_values("delta_bin").reset_index(drop=True)
    grouped["delta_bin"] = grouped["delta_bin"].astype(str)
    return grouped


def build_tag_summary(df: pd.DataFrame, column: str, default_alias: str | None = None) -> pd.DataFrame:
    if column not in df.columns:
        return pd.DataFrame(
            columns=(
                "tag",
                "is_default_alias",
                "n_rows",
                "n_tasks",
                "median_active_time",
                "median_metric_primary",
                "median_reliability_primary",
            )
        )

    subset = df.copy()
    if (subset["scope_bucket"] == "in_scope").any():
        subset = subset.loc[subset["scope_bucket"] == "in_scope"].copy()

    rows: list[dict[str, object]] = []
    for _, row in subset.iterrows():
        tokens = _tokenize_multilabel(row.get(column))
        if not tokens:
            continue
        for token in tokens:
            rows.append(
                {
                    "task_id": row.get("task_id", ""),
                    "tag": token,
                    "active_time_value": row.get("active_time_value"),
                    "metric_primary": row.get("metric_primary"),
                    "reliability_primary": row.get("reliability_primary"),
                }
            )

    if not rows:
        return pd.DataFrame(
            columns=(
                "tag",
                "is_default_alias",
                "n_rows",
                "n_tasks",
                "median_active_time",
                "median_metric_primary",
                "median_reliability_primary",
            )
        )

    token_df = pd.DataFrame(rows)
    grouped = (
        token_df.groupby("tag", dropna=False)
        .agg(
            n_rows=("task_id", "size"),
            n_tasks=("task_id", "nunique"),
            median_active_time=("active_time_value", "median"),
            median_metric_primary=("metric_primary", "median"),
            median_reliability_primary=("reliability_primary", "median"),
        )
        .reset_index()
        .sort_values(["n_rows", "tag"], ascending=[False, True])
        .reset_index(drop=True)
    )
    grouped.insert(1, "is_default_alias", grouped["tag"].eq(default_alias) if default_alias else False)
    return grouped


def build_anomaly_audit_table(df: pd.DataFrame, scope_conflict_tasks: set[str]) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    metric_threshold = (
        float(df["metric_primary"].dropna().quantile(0.10))
        if df["metric_primary"].notna().any()
        else None
    )
    active_time_threshold = (
        float(df["active_time_value"].dropna().quantile(0.90))
        if df["active_time_value"].notna().any()
        else None
    )

    rows: list[dict[str, object]] = []
    for _, row in df.iterrows():
        reasons: list[str] = []
        task_id = str(row.get("task_id", ""))
        metric_value = row.get("metric_primary")
        active_time_value = row.get("active_time_value")

        if metric_threshold is not None and pd.notna(metric_value) and float(metric_value) <= metric_threshold:
            reasons.append("low_metric_q10")
        if active_time_threshold is not None and pd.notna(active_time_value) and float(active_time_value) >= active_time_threshold:
            reasons.append("high_active_time_q90")
        if not bool(row.get("layout_used_bool", False)):
            reasons.append("layout_gate_failure")
        if bool(row.get("type4_flag_bool", False)):
            reasons.append("type4_flag")
        if bool(row.get("type3_flag_bool", False)):
            reasons.append("type3_flag")
        if task_id in scope_conflict_tasks:
            reasons.append("mixed_scope_task")

        if not reasons:
            continue

        rows.append(
            {
                "task_id": task_id,
                "annotator_id": str(row.get("annotator_id", "")),
                "scope_bucket": str(row.get("scope_bucket", "")),
                "layout_used": bool(row.get("layout_used_bool", False)),
                "layout_gate_reason": str(row.get("layout_gate_reason", "")),
                "metric_primary": metric_value,
                "active_time": active_time_value,
                "difficulty": str(row.get("difficulty", "")),
                "model_issue": str(row.get("model_issue", "")),
                "anomaly_reasons": ";".join(reasons),
                "n_anomaly_reasons": len(reasons),
            }
        )

    if not rows:
        return pd.DataFrame(
            columns=(
                "task_id",
                "annotator_id",
                "scope_bucket",
                "layout_used",
                "layout_gate_reason",
                "metric_primary",
                "active_time",
                "difficulty",
                "model_issue",
                "anomaly_reasons",
                "n_anomaly_reasons",
            )
        )

    return (
        pd.DataFrame(rows)
        .sort_values(["n_anomaly_reasons", "metric_primary", "active_time"], ascending=[False, True, False])
        .reset_index(drop=True)
    )


def load_active_log_summary(path: Path | None) -> dict[str, object]:
    if path is None or not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def build_active_log_summary_table(summary: dict[str, object]) -> pd.DataFrame:
    if not summary:
        return pd.DataFrame(columns=("signal", "count", "rate"))
    rows: list[dict[str, object]] = []
    for key in ACTIVE_LOG_SIGNAL_KEYS:
        count = int(summary.get(key, 0) or 0)
        rate_key = key.replace("_count", "_rate")
        rows.append(
            {
                "signal": key,
                "count": count,
                "rate": float(summary.get(rate_key, 0.0) or 0.0),
            }
        )
    return pd.DataFrame(rows)


def build_active_time_row_audit_table(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(
            columns=("signal", "count", "rate")
        )
    n_rows = max(len(df), 1)
    rows = [
        {"signal": "short_time_rows", "count": int(df["has_short_time_flag_bool"].sum()), "rate": float(df["has_short_time_flag_bool"].mean())},
        {"signal": "long_time_rows", "count": int(df["has_long_time_flag_bool"].sum()), "rate": float(df["has_long_time_flag_bool"].mean())},
        {"signal": "unknown_id_rows", "count": int(df["has_unknown_id_flag_bool"].sum()), "rate": float(df["has_unknown_id_flag_bool"].mean())},
        {"signal": "multi_session_rows", "count": int(df["multi_session_bool"].sum()), "rate": float(df["multi_session_bool"].mean())},
        {"signal": "missing_script_version_rows", "count": int(df["missing_script_version_bool"].sum()), "rate": float(df["missing_script_version_bool"].mean())},
        {"signal": "active_time_missing_rows", "count": int(df["active_time_value"].isna().sum()), "rate": float(df["active_time_value"].isna().sum() / n_rows)},
    ]
    return pd.DataFrame(rows)


def build_active_time_by_annotator_table(df: pd.DataFrame) -> pd.DataFrame:
    if "annotator_id" not in df.columns or df.empty:
        return pd.DataFrame(
            columns=(
                "annotator_id",
                "n_rows",
                "total_time",
                "mean_time",
                "median_time",
                "p95_time",
                "p99_time",
                "multi_session_rows",
                "unknown_id_rows",
            )
        )
    subset = df.loc[df["active_time_value"].notna()].copy()
    if subset.empty:
        return pd.DataFrame(
            columns=(
                "annotator_id",
                "n_rows",
                "total_time",
                "mean_time",
                "median_time",
                "p95_time",
                "p99_time",
                "multi_session_rows",
                "unknown_id_rows",
            )
        )
    grouped = (
        subset.groupby("annotator_id", dropna=False)
        .agg(
            n_rows=("task_id", "size"),
            total_time=("active_time_value", "sum"),
            mean_time=("active_time_value", "mean"),
            median_time=("active_time_value", "median"),
            p95_time=("active_time_value", lambda s: float(s.quantile(0.95))),
            p99_time=("active_time_value", lambda s: float(s.quantile(0.99))),
            multi_session_rows=("multi_session_bool", "sum"),
            unknown_id_rows=("has_unknown_id_flag_bool", "sum"),
        )
        .reset_index()
        .sort_values(["total_time", "annotator_id"], ascending=[False, True])
        .reset_index(drop=True)
    )
    return grouped


def build_active_time_source_table(df: pd.DataFrame) -> pd.DataFrame:
    source_col = _first_existing_column(df, ("active_time_source",))
    match_col = _first_existing_column(df, ("active_time_match_status",))
    if source_col is None and match_col is None:
        return pd.DataFrame(columns=("active_time_source", "active_time_match_status", "n_rows"))
    source_series = (
        _normalize_text(df[source_col])
        if source_col is not None
        else pd.Series([DEFAULT_SCOPE_MISSING_LABEL] * len(df), index=df.index, dtype=object)
    )
    match_series = (
        _normalize_text(df[match_col])
        if match_col is not None
        else pd.Series([DEFAULT_SCOPE_MISSING_LABEL] * len(df), index=df.index, dtype=object)
    )
    grouped = (
        pd.DataFrame(
            {
                "active_time_source": source_series,
                "active_time_match_status": match_series,
            }
        )
        .groupby(["active_time_source", "active_time_match_status"], dropna=False)
        .size()
        .reset_index(name="n_rows")
        .sort_values(["n_rows", "active_time_source", "active_time_match_status"], ascending=[False, True, True])
        .reset_index(drop=True)
    )
    return grouped


def build_schema_alignment_table(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for formal_field, candidates in FORMAL_VISUAL_FIELDS:
        source_column = _first_existing_column(df, candidates)
        if source_column is None:
            rows.append(
                {
                    "formal_field": formal_field,
                    "status": "missing",
                    "source_column": "",
                    "note": "not found in quality_report",
                }
            )
            continue
        status = "aligned" if source_column == formal_field else "compat_fallback"
        rows.append(
            {
                "formal_field": formal_field,
                "status": status,
                "source_column": source_column,
                "note": "" if status == "aligned" else "uses explicit compatibility bridge",
            }
        )
    return pd.DataFrame(rows)


def save_table(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8")


def save_json(payload: dict[str, object], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def save_fig(fig: plt.Figure | None, path: Path, dpi: int = 180) -> bool:
    if fig is None:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return True


def plot_tier_funnel(tier_df: pd.DataFrame) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(6, 4))
    sns.barplot(data=tier_df, x="tier", y="n_rows", ax=ax, palette="Blues_d")
    for index, row in tier_df.iterrows():
        ax.text(index, row["n_rows"], f"{int(row['n_rows'])}", ha="center", va="bottom")
    ax.set_title("T/I/M row counts")
    ax.set_xlabel("tier")
    ax.set_ylabel("rows")
    fig.tight_layout()
    return fig


def plot_scope_distribution(df: pd.DataFrame) -> plt.Figure:
    counts = (
        df.groupby("scope_bucket", dropna=False)
        .size()
        .reset_index(name="n_rows")
        .sort_values(["n_rows", "scope_bucket"], ascending=[False, True])
    )
    fig, ax = plt.subplots(figsize=(7, 4))
    sns.barplot(data=counts, x="scope_bucket", y="n_rows", ax=ax, palette="muted")
    ax.set_title("Scope bucket distribution")
    ax.set_xlabel("scope_bucket")
    ax.set_ylabel("rows")
    fig.tight_layout()
    return fig


def plot_layout_gate_reasons(df: pd.DataFrame) -> plt.Figure | None:
    subset = df.loc[~df["layout_used_bool"]].copy()
    if subset.empty:
        return None
    reasons = _normalize_text(subset.get("layout_gate_reason", pd.Series(index=subset.index, dtype=object)))
    counts = reasons.value_counts(dropna=False).rename_axis("layout_gate_reason").reset_index(name="n_rows")
    fig, ax = plt.subplots(figsize=(9, 4.5))
    sns.barplot(data=counts, x="layout_gate_reason", y="n_rows", ax=ax, palette="crest")
    ax.set_title("Layout gate failures")
    ax.set_xlabel("layout_gate_reason")
    ax.set_ylabel("rows")
    ax.tick_params(axis="x", rotation=20)
    fig.tight_layout()
    return fig


def plot_active_time_vs_metric(df: pd.DataFrame) -> plt.Figure | None:
    subset = df.loc[df["active_time_value"].notna() & df["metric_primary"].notna()].copy()
    if subset.empty:
        return None
    subset = subset.loc[subset["active_time_value"] > 0].copy()
    if subset.empty:
        return None
    fig, ax = plt.subplots(figsize=(7, 5))
    sns.scatterplot(
        data=subset,
        x="active_time_value",
        y="metric_primary",
        hue="scope_bucket",
        style="layout_used_bool",
        alpha=0.8,
        ax=ax,
    )
    ax.set_xscale("log")
    ax.set_title("Active time vs primary quality metric")
    ax.set_xlabel("active_time (seconds, log scale)")
    ax.set_ylabel("metric_primary")
    fig.tight_layout()
    return fig


def plot_active_time_by_scope(df: pd.DataFrame) -> plt.Figure | None:
    subset = df.loc[df["active_time_value"].notna() & (df["active_time_value"] > 0)].copy()
    if subset.empty:
        return None
    fig, ax = plt.subplots(figsize=(7, 4.5))
    sns.boxplot(data=subset, x="scope_bucket", y="active_time_value", showfliers=False, ax=ax)
    sns.stripplot(data=subset, x="scope_bucket", y="active_time_value", color="black", alpha=0.45, size=3, ax=ax)
    ax.set_yscale("log")
    ax.set_title("Active time by scope bucket")
    ax.set_xlabel("scope_bucket")
    ax.set_ylabel("active_time (seconds, log scale)")
    fig.tight_layout()
    return fig


def plot_delta_pairs(delta_df: pd.DataFrame) -> plt.Figure | None:
    if delta_df.empty:
        return None
    fig, ax = plt.subplots(figsize=(7, 4))
    sns.barplot(data=delta_df, x="delta_bin", y="n_rows", ax=ax, palette="rocket")
    ax.set_title("Delta n_pairs distribution")
    ax.set_xlabel("pred_n_pairs - ann_n_pairs")
    ax.set_ylabel("rows")
    fig.tight_layout()
    return fig


def plot_tag_counts(tag_df: pd.DataFrame, title: str, *, drop_default_alias: bool = True) -> plt.Figure | None:
    if tag_df.empty:
        return None
    plot_df = tag_df.copy()
    if drop_default_alias and "is_default_alias" in plot_df.columns:
        filtered = plot_df.loc[~plot_df["is_default_alias"]].copy()
        if not filtered.empty:
            plot_df = filtered
    plot_df = plot_df.head(8)
    if plot_df.empty:
        return None
    fig, ax = plt.subplots(figsize=(8, 4.5))
    sns.barplot(data=plot_df, x="tag", y="n_rows", ax=ax, palette="mako")
    ax.set_title(title)
    ax.set_xlabel("tag")
    ax.set_ylabel("rows")
    ax.tick_params(axis="x", rotation=20)
    fig.tight_layout()
    return fig


def plot_active_log_quality(summary_df: pd.DataFrame) -> plt.Figure | None:
    if summary_df.empty:
        return None
    fig, ax = plt.subplots(figsize=(9, 4.5))
    sns.barplot(data=summary_df, x="signal", y="count", ax=ax, palette="flare")
    ax.set_title("Active-log quality signals")
    ax.set_xlabel("signal")
    ax.set_ylabel("count")
    ax.tick_params(axis="x", rotation=25)
    fig.tight_layout()
    return fig


def write_summary_markdown(
    path: Path,
    tier_df: pd.DataFrame,
    field_audit_df: pd.DataFrame,
    schema_alignment_df: pd.DataFrame,
    difficulty_df: pd.DataFrame,
    model_issue_df: pd.DataFrame,
    scope_conflict_df: pd.DataFrame,
    active_time_row_audit_df: pd.DataFrame,
    active_log_df: pd.DataFrame,
) -> None:
    row = field_audit_df.iloc[0].to_dict() if not field_audit_df.empty else {}
    lines = [
        "# Experiment Visual Audit",
        "",
        "## Core counts",
        "- tier definition: T = all rows; I = in-scope rows; M = in-scope and type3_flag = False",
    ]
    for _, tier_row in tier_df.iterrows():
        lines.append(f"- tier {tier_row['tier']}: {int(tier_row['n_rows'])} rows, {int(tier_row['n_tasks'])} tasks")

    if row:
        lines.extend(
            [
                "",
                "## Field audit",
                f"- mixed scope tasks: {int(row['n_mixed_scope_tasks'])}",
                f"- type3 rows: {int(row['n_type3_rows'])}",
                f"- layout gate fail rows: {int(row['n_layout_gate_fail_rows'])}",
                f"- type4 rows: {int(row['n_type4_rows'])}",
                f"- active_time missing rows: {int(row['n_active_time_missing_rows'])}",
            ]
        )

    if not schema_alignment_df.empty:
        missing_count = int(schema_alignment_df["status"].eq("missing").sum())
        compat_count = int(schema_alignment_df["status"].eq("compat_fallback").sum())
        lines.extend(
            [
                "",
                "## Schema alignment",
                f"- missing formal fields: {missing_count}",
                f"- compatibility fallback fields: {compat_count}",
            ]
        )

    if not difficulty_df.empty:
        lines.extend(["", "## Top difficulty tags"])
        for _, tag_row in difficulty_df.head(5).iterrows():
            lines.append(f"- {tag_row['tag']}: {int(tag_row['n_rows'])} rows")

    if not model_issue_df.empty:
        lines.extend(["", "## Top model_issue tags"])
        for _, tag_row in model_issue_df.head(5).iterrows():
            lines.append(f"- {tag_row['tag']}: {int(tag_row['n_rows'])} rows")

    lines.extend(["", "## Scope conflicts", f"- conflict tasks: {len(scope_conflict_df)}"])

    if not active_time_row_audit_df.empty:
        lines.extend(["", "## Active-time row audit"])
        for _, signal_row in active_time_row_audit_df.iterrows():
            lines.append(
                f"- {signal_row['signal']}: {int(signal_row['count'])} (rate={float(signal_row['rate']):.4f})"
            )

    if not active_log_df.empty:
        lines.extend(["", "## Active-log quality"])
        for _, signal_row in active_log_df.iterrows():
            lines.append(
                f"- {signal_row['signal']}: {int(signal_row['count'])} (rate={float(signal_row['rate']):.4f})"
            )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    sns.set_theme(style="whitegrid")

    if not args.quality_csv.exists():
        raise FileNotFoundError(f"quality csv not found: {args.quality_csv}")

    quality_df = pd.read_csv(args.quality_csv)
    prepared_df, metric_info = prepare_quality_frame(quality_df)

    tag = args.tag or args.quality_csv.stem
    out_dir = args.out_dir / tag
    out_dir.mkdir(parents=True, exist_ok=True)

    tier_df = build_tier_table(prepared_df)
    field_audit_df = build_field_audit_table(prepared_df, metric_info)
    schema_alignment_df = build_schema_alignment_table(quality_df)
    delta_pairs_df = build_delta_pairs_table(prepared_df)
    difficulty_df = build_tag_summary(prepared_df, "difficulty", default_alias="trivial")
    model_issue_df = build_tag_summary(prepared_df, "model_issue", default_alias="acceptable")
    scope_conflict_df = build_scope_conflict_table(prepared_df)
    scope_conflict_tasks = set(
        scope_conflict_df.get("task_id", pd.Series(dtype=str)).astype(str).tolist()
    )
    anomaly_df = build_anomaly_audit_table(prepared_df, scope_conflict_tasks)

    active_log_summary = load_active_log_summary(args.active_log_summary_json)
    active_log_summary_df = build_active_log_summary_table(active_log_summary)
    active_time_row_audit_df = build_active_time_row_audit_table(prepared_df)
    active_time_by_annotator_df = build_active_time_by_annotator_table(prepared_df)
    active_time_source_df = build_active_time_source_table(prepared_df)
    active_log_per_file_df = (
        pd.read_csv(args.active_log_per_file_csv)
        if args.active_log_per_file_csv is not None and args.active_log_per_file_csv.exists()
        else pd.DataFrame()
    )

    tables_written = {
        "table_tier_counts": out_dir / "table_tier_counts.csv",
        "table_field_audit": out_dir / "table_field_audit.csv",
        "table_schema_alignment": out_dir / "table_schema_alignment.csv",
        "table_a_delta_n_pairs": out_dir / "table_a_delta_n_pairs.csv",
        "table_b1_difficulty": out_dir / "table_b1_difficulty.csv",
        "table_b2_model_issue": out_dir / "table_b2_model_issue.csv",
        "table_b2_scope_conflict": out_dir / "table_b2_scope_conflict.csv",
        "table_a1_anomaly_audit": out_dir / "table_a1_anomaly_audit.csv",
        "table_active_time_row_audit": out_dir / "table_active_time_row_audit.csv",
        "table_active_time_by_annotator": out_dir / "table_active_time_by_annotator.csv",
        "table_active_time_source": out_dir / "table_active_time_source.csv",
        "table_active_log_summary": out_dir / "table_active_log_summary.csv",
        "table_active_log_per_file": out_dir / "table_active_log_per_file.csv",
    }

    save_table(tier_df, tables_written["table_tier_counts"])
    save_table(field_audit_df, tables_written["table_field_audit"])
    save_table(schema_alignment_df, tables_written["table_schema_alignment"])
    save_table(delta_pairs_df, tables_written["table_a_delta_n_pairs"])
    save_table(difficulty_df, tables_written["table_b1_difficulty"])
    save_table(model_issue_df, tables_written["table_b2_model_issue"])
    save_table(scope_conflict_df, tables_written["table_b2_scope_conflict"])
    save_table(anomaly_df, tables_written["table_a1_anomaly_audit"])
    save_table(active_time_row_audit_df, tables_written["table_active_time_row_audit"])
    save_table(active_time_by_annotator_df, tables_written["table_active_time_by_annotator"])
    save_table(active_time_source_df, tables_written["table_active_time_source"])
    save_table(active_log_summary_df, tables_written["table_active_log_summary"])
    save_table(active_log_per_file_df, tables_written["table_active_log_per_file"])

    active_log_plot_df = active_log_summary_df if not active_log_summary_df.empty else active_time_row_audit_df

    figures = {
        "01_tier_funnel": plot_tier_funnel(tier_df),
        "02_scope_distribution": plot_scope_distribution(prepared_df),
        "03_layout_gate_reasons": plot_layout_gate_reasons(prepared_df),
        "04_active_time_vs_quality": plot_active_time_vs_metric(prepared_df),
        "05_active_time_by_scope": plot_active_time_by_scope(prepared_df),
        "06_delta_n_pairs": plot_delta_pairs(delta_pairs_df),
        "07_difficulty_tags": plot_tag_counts(difficulty_df, "Difficulty tag counts", drop_default_alias=True),
        "08_model_issue_tags": plot_tag_counts(model_issue_df, "Model issue tag counts", drop_default_alias=True),
        "09_active_log_quality": plot_active_log_quality(active_log_plot_df),
    }

    figure_paths: dict[str, str] = {}
    for name, fig in figures.items():
        output_path = out_dir / f"{name}.png"
        if save_fig(fig, output_path):
            figure_paths[name] = str(output_path)

    write_summary_markdown(
        out_dir / "SUMMARY.md",
        tier_df,
        field_audit_df,
        schema_alignment_df,
        difficulty_df,
        model_issue_df,
        scope_conflict_df,
        active_time_row_audit_df,
        active_log_summary_df,
    )

    summary_payload = {
        "quality_csv": str(args.quality_csv),
        "output_dir": str(out_dir),
        "n_rows": int(len(prepared_df)),
        "n_tasks": int(prepared_df["task_id"].nunique()) if "task_id" in prepared_df.columns else 0,
        "quality_metric_column": metric_info.get("quality_metric_column"),
        "reliability_metric_column": metric_info.get("reliability_metric_column"),
        "session_count_column": metric_info.get("session_count_column"),
        "project_id_column": metric_info.get("project_id_column"),
        "type4_source": metric_info.get("type4_source"),
        "tier_counts": tier_df.to_dict(orient="records"),
        "field_audit": field_audit_df.iloc[0].to_dict() if not field_audit_df.empty else {},
        "schema_alignment": schema_alignment_df.to_dict(orient="records"),
        "active_log_summary_path": str(args.active_log_summary_json) if args.active_log_summary_json else "",
        "active_log_per_file_path": str(args.active_log_per_file_csv) if args.active_log_per_file_csv else "",
        "generated_tables": {key: str(value) for key, value in tables_written.items()},
        "generated_figures": figure_paths,
    }
    save_json(summary_payload, out_dir / "summary.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
