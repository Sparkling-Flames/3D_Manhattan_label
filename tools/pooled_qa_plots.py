#!/usr/bin/env python3
"""Generate pooled QA plots from registry-style CSVs.

This entrypoint is intentionally for QA/audit only.
It does not replace formal analysis and it is not a paper-figure generator.

Hard constraints implemented here:
1. Generate pooled QA figures first, rather than paper main figures.
2. Every figure is stratified by `schema_version`.
3. Active-time figures are additionally split by `active_time_source`.
4. Dataset-group summaries only use rows whose `dataset_group_source` is in a
   trusted allowlist.
5. Mixed-scope tasks are emitted as explicit audit outputs.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

DEFAULT_TRUSTED_DATASET_GROUP_SOURCES = [
    "planned_registry_match",
    "export_task_data",
]

DEFAULT_MERGED_CANDIDATES = [
    Path("analysis_results/registry_20260308/merged_all_v0.csv"),
    Path("analysis_results/registry_20260308_march7_check/merged_all_v0.csv"),
]
DEFAULT_ANNOTATION_CANDIDATES = [
    Path("analysis_results/registry_20260308/annotation_registry_v1.csv"),
    Path("analysis_results/registry_20260308_march7_check/annotation_registry_v1.csv"),
]
DEFAULT_ACTIVE_TIME_CANDIDATES = [
    Path("analysis_results/registry_20260308/active_time_registry_v1.csv"),
    Path("analysis_results/registry_20260308_march7_check/active_time_registry_v1.csv"),
]
DEFAULT_REGISTRY_SUITE_SUMMARY_CANDIDATES = [
    Path("analysis_results/registry_20260308/registry_suite_summary_v1.json"),
    Path("analysis_results/registry_20260308_march7_check/registry_suite_summary_v1.json"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate pooled QA plots from registry CSVs")
    parser.add_argument("--merged-csv", type=Path, default=None, help="Path to merged_all_v0.csv")
    parser.add_argument("--annotation-registry", type=Path, default=None, help="Path to annotation_registry_v1.csv")
    parser.add_argument("--active-time-registry", type=Path, default=None, help="Path to active_time_registry_v1.csv")
    parser.add_argument(
        "--registry-suite-summary",
        type=Path,
        default=None,
        help="Optional path to registry_suite_summary_v1.json for join-status context.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("analysis_results/pooled_qa"),
        help="Output root directory",
    )
    parser.add_argument(
        "--tag",
        default=None,
        help="Optional output folder name. Defaults to the merged CSV stem.",
    )
    parser.add_argument(
        "--trusted-dataset-group-sources",
        nargs="+",
        default=DEFAULT_TRUSTED_DATASET_GROUP_SOURCES,
        help="Allowlist used before any dataset_group aggregation.",
    )
    return parser.parse_args()


def choose_existing_path(explicit_path: Path | None, candidates: list[Path]) -> Path | None:
    if explicit_path is not None:
        return explicit_path
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def read_csv_or_none(path: Path | None) -> pd.DataFrame | None:
    if path is None or not path.exists():
        return None
    return pd.read_csv(path)


def read_json_or_none(path: Path | None) -> dict | None:
    if path is None or not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def choose_join_keys(left: pd.DataFrame, right: pd.DataFrame) -> list[str]:
    candidate_sets = [
        ["task_id", "annotation_id", "annotator_id"],
        ["task_id", "annotator_id"],
        ["annotation_id"],
        ["task_id"],
    ]
    for keys in candidate_sets:
        if all(key in left.columns and key in right.columns for key in keys):
            return keys
    raise ValueError("No usable join keys were found between the selected CSV files.")


def merge_if_needed(base_df: pd.DataFrame, extra_df: pd.DataFrame | None, prefer_columns: Iterable[str]) -> pd.DataFrame:
    if extra_df is None:
        return base_df

    columns = [column for column in prefer_columns if column in extra_df.columns]
    if not columns:
        return base_df

    join_keys = choose_join_keys(base_df, extra_df)
    payload = extra_df[join_keys + [column for column in columns if column not in join_keys]].copy()
    payload = payload.drop_duplicates(subset=join_keys, keep="first")
    merged = base_df.merge(payload, on=join_keys, how="left", suffixes=("", "__extra"))

    for column in columns:
        extra_column = f"{column}__extra"
        if extra_column not in merged.columns:
            continue
        if column in merged.columns:
            merged[column] = merged[column].where(~merged[column].isna(), merged[extra_column])
        else:
            merged[column] = merged[extra_column]
        merged.drop(columns=[extra_column], inplace=True)

    return merged


def normalize_text(series: pd.Series, missing_label: str = "(missing)") -> pd.Series:
    result = series.fillna("").astype(str).str.strip()
    result = result.mask(result.eq(""), missing_label)
    return result


def prepare_frame(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()

    for column in ["task_id", "annotation_id", "annotator_id"]:
        if column in result.columns:
            result[column] = result[column].astype(str)

    if "schema_version" not in result.columns:
        result["schema_version"] = "(missing)"
    result["schema_version"] = normalize_text(result["schema_version"])

    active_time_column = None
    for candidate in ["active_time_value", "active_time"]:
        if candidate in result.columns:
            active_time_column = candidate
            break
    if active_time_column is not None:
        result["active_time_plot"] = pd.to_numeric(result[active_time_column], errors="coerce")
    else:
        result["active_time_plot"] = pd.Series([pd.NA] * len(result), index=result.index, dtype="float64")

    if "active_time_source" not in result.columns:
        result["active_time_source"] = "(missing)"
    result["active_time_source"] = normalize_text(result["active_time_source"])

    if "dataset_group" in result.columns:
        result["dataset_group"] = normalize_text(result["dataset_group"])
    if "dataset_group_source" in result.columns:
        result["dataset_group_source"] = normalize_text(result["dataset_group_source"])
    if "normalized_scope" in result.columns:
        result["normalized_scope"] = normalize_text(result["normalized_scope"])
    if "task_join_status" in result.columns:
        result["task_join_status"] = normalize_text(result["task_join_status"])
    if "is_oos" in result.columns:
        result["is_oos"] = (
            result["is_oos"]
            .astype(str)
            .str.strip()
            .str.lower()
            .map({"true": True, "false": False})
        )

    return result


def save_figure(fig: plt.Figure, output_path: Path, dpi: int = 200) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


def plot_rows_by_schema(df: pd.DataFrame) -> plt.Figure:
    counts = (
        df.groupby("schema_version", dropna=False)
        .size()
        .reset_index(name="rows")
        .sort_values(["rows", "schema_version"], ascending=[False, True])
    )
    fig, ax = plt.subplots(figsize=(8, 4))
    sns.barplot(data=counts, x="schema_version", y="rows", ax=ax)
    ax.set_title("Pooled QA rows by schema_version")
    ax.set_xlabel("schema_version")
    ax.set_ylabel("annotations (rows)")
    ax.tick_params(axis="x", rotation=20)
    fig.tight_layout()
    return fig


def plot_join_status_by_schema(df: pd.DataFrame) -> plt.Figure | None:
    if "task_join_status" not in df.columns:
        return None
    counts = (
        df.groupby(["schema_version", "task_join_status"], dropna=False)
        .size()
        .reset_index(name="rows")
    )
    if counts.empty:
        return None
    fig, ax = plt.subplots(figsize=(10, 4))
    sns.barplot(data=counts, x="schema_version", y="rows", hue="task_join_status", ax=ax)
    ax.set_title("Join status by schema_version")
    ax.set_xlabel("schema_version")
    ax.set_ylabel("annotations (rows)")
    ax.tick_params(axis="x", rotation=20)
    fig.tight_layout()
    return fig


def plot_active_time_histogram(df: pd.DataFrame) -> plt.Figure | None:
    plot_df = df.loc[df["active_time_plot"].notna() & (df["active_time_plot"] > 0)].copy()
    if plot_df.empty:
        return None

    schema_values = sorted(plot_df["schema_version"].unique().tolist())
    fig, axes = plt.subplots(
        1,
        len(schema_values),
        figsize=(6 * len(schema_values), 4),
        squeeze=False,
        sharey=True,
    )
    legend_handles = None
    legend_labels = None
    for ax, schema_value in zip(axes.flat, schema_values):
        subset = plot_df.loc[plot_df["schema_version"] == schema_value]
        sns.histplot(
            data=subset,
            x="active_time_plot",
            hue="active_time_source",
            bins=20,
            element="step",
            stat="count",
            common_norm=False,
            log_scale=True,
            ax=ax,
        )
        if legend_handles is None:
            legend_handles, legend_labels = ax.get_legend_handles_labels()
        legend = ax.get_legend()
        if legend is not None:
            legend.remove()
        ax.set_title(f"{schema_value}\n(n={len(subset)})")
        ax.set_xlabel("active time (seconds, log scale)")
        ax.set_ylabel("annotations (rows)")

    if legend_handles and legend_labels:
        fig.legend(legend_handles, legend_labels, title="active_time_source", loc="upper center", ncol=max(1, len(legend_labels)))
    fig.suptitle("Active time distribution by schema_version", y=1.08)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    return fig


def plot_active_time_box(df: pd.DataFrame) -> plt.Figure | None:
    plot_df = df.loc[df["active_time_plot"].notna() & (df["active_time_plot"] > 0)].copy()
    if plot_df.empty:
        return None

    schema_values = sorted(plot_df["schema_version"].unique().tolist())
    fig, axes = plt.subplots(
        1,
        len(schema_values),
        figsize=(6 * len(schema_values), 4.5),
        squeeze=False,
        sharey=True,
    )

    for idx, (ax, schema_value) in enumerate(zip(axes.flat, schema_values)):
        subset = plot_df.loc[plot_df["schema_version"] == schema_value]
        sns.boxplot(data=subset, x="active_time_source", y="active_time_plot", ax=ax)
        sns.stripplot(data=subset, x="active_time_source", y="active_time_plot", color="black", alpha=0.5, size=3, ax=ax)
        ax.set_yscale("log")
        ax.set_title(f"{schema_value}\n(n={len(subset)})")
        ax.set_xlabel("active_time_source")
        ax.set_ylabel("active time (seconds, log scale)" if idx == 0 else "")
        ax.tick_params(axis="x", rotation=20)

    fig.suptitle("Active time by source within each schema_version", y=1.03)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    return fig


def plot_annotator_profile(df: pd.DataFrame) -> plt.Figure | None:
    if "annotator_id" not in df.columns:
        return None
    counts = (
        df.groupby(["schema_version", "annotator_id"], dropna=False)
        .size()
        .reset_index(name="rows")
        .sort_values(["schema_version", "rows", "annotator_id"], ascending=[True, False, True])
    )
    if counts.empty:
        return None

    fig, ax = plt.subplots(figsize=(10, 4))
    sns.barplot(data=counts, x="annotator_id", y="rows", hue="schema_version", ax=ax)
    ax.set_title("Annotator profile (rows), stratified by schema_version")
    ax.set_xlabel("annotator_id")
    ax.set_ylabel("annotations (rows)")
    fig.tight_layout()
    return fig


def plot_dataset_group_source_counts(df: pd.DataFrame) -> plt.Figure | None:
    if "dataset_group_source" not in df.columns:
        return None
    counts = (
        df.groupby(["schema_version", "dataset_group_source"], dropna=False)
        .size()
        .reset_index(name="rows")
    )
    if counts.empty:
        return None

    fig, ax = plt.subplots(figsize=(10, 4))
    sns.barplot(data=counts, x="schema_version", y="rows", hue="dataset_group_source", ax=ax)
    ax.set_title("dataset_group_source by schema_version")
    ax.set_xlabel("schema_version")
    ax.set_ylabel("annotations (rows)")
    ax.tick_params(axis="x", rotation=20)
    fig.tight_layout()
    return fig


def plot_dataset_group_counts_trusted(df: pd.DataFrame, trusted_sources: list[str]) -> tuple[plt.Figure | None, pd.DataFrame]:
    required_columns = {"schema_version", "dataset_group", "dataset_group_source"}
    if not required_columns.issubset(df.columns):
        return None, pd.DataFrame()

    plot_df = df.loc[
        df["dataset_group_source"].isin(trusted_sources)
        & df["dataset_group"].notna()
        & (df["dataset_group"] != "(missing)")
    ].copy()
    if plot_df.empty:
        return None, pd.DataFrame()

    counts = (
        plot_df.groupby(["schema_version", "dataset_group", "dataset_group_source"], dropna=False)
        .size()
        .reset_index(name="rows")
        .sort_values(["schema_version", "rows", "dataset_group"], ascending=[True, False, True])
    )

    fig, ax = plt.subplots(figsize=(10, 4))
    sns.barplot(data=counts, x="dataset_group", y="rows", hue="schema_version", ax=ax)
    ax.set_title("Trusted dataset_group counts (filtered by dataset_group_source)")
    ax.set_xlabel("dataset_group")
    ax.set_ylabel("annotations (rows)")
    ax.tick_params(axis="x", rotation=25)
    fig.tight_layout()
    return fig, counts


def join_unique_values(series: pd.Series) -> str:
    values = sorted({str(value).strip() for value in series.dropna() if str(value).strip()})
    return "; ".join(values)


def build_mixed_scope_audit(df: pd.DataFrame) -> pd.DataFrame:
    required_columns = {"task_id", "schema_version", "normalized_scope", "is_oos"}
    if not required_columns.issubset(df.columns):
        return pd.DataFrame()

    audit_df = df.loc[df["task_id"].notna()].copy()
    if audit_df.empty:
        return pd.DataFrame()

    audit_df["scope_bucket"] = audit_df["is_oos"].map({True: "oos", False: "in_scope"}).fillna("unknown")

    rows: list[dict] = []
    for task_id, group in audit_df.groupby("task_id", dropna=False):
        n_annotators = int(group["annotator_id"].nunique()) if "annotator_id" in group.columns else 0
        n_scope_values = int(group["normalized_scope"].dropna().nunique())
        n_scope_buckets = int(group["scope_bucket"].dropna().nunique())
        scope_bucket_set = set(group["scope_bucket"].dropna().astype(str))
        has_in_scope = "in_scope" in scope_bucket_set
        has_oos = "oos" in scope_bucket_set
        rows.append(
            {
                "task_id": task_id,
                "schema_version": join_unique_values(group["schema_version"]),
                "n_rows": int(len(group)),
                "n_annotators": n_annotators,
                "scope_values": join_unique_values(group["normalized_scope"]),
                "n_scope_values": n_scope_values,
                "scope_buckets": join_unique_values(group["scope_bucket"]),
                "n_scope_buckets": n_scope_buckets,
                "join_statuses": join_unique_values(group["task_join_status"]) if "task_join_status" in group.columns else "",
                "has_in_scope_vote": has_in_scope,
                "has_oos_vote": has_oos,
                "is_mixed_scope": has_in_scope and has_oos,
                "is_multi_annotator": n_annotators > 1,
            }
        )

    mixed_scope_df = pd.DataFrame(rows)
    if mixed_scope_df.empty:
        return mixed_scope_df

    mixed_scope_df = mixed_scope_df.loc[mixed_scope_df["is_mixed_scope"]].copy()
    if mixed_scope_df.empty:
        return mixed_scope_df

    return mixed_scope_df.sort_values(["schema_version", "n_annotators", "task_id"], ascending=[True, False, True])


def plot_mixed_scope_counts_by_schema(mixed_scope_df: pd.DataFrame) -> plt.Figure | None:
    if mixed_scope_df.empty:
        return None

    counts = (
        mixed_scope_df.groupby("schema_version", dropna=False)
        .size()
        .reset_index(name="mixed_tasks")
        .sort_values(["mixed_tasks", "schema_version"], ascending=[False, True])
    )
    fig, ax = plt.subplots(figsize=(8, 4))
    sns.barplot(data=counts, x="schema_version", y="mixed_tasks", ax=ax)
    ax.set_title("Mixed-scope task audit by schema_version")
    ax.set_xlabel("schema_version")
    ax.set_ylabel("mixed-scope tasks (task count)")
    ax.tick_params(axis="x", rotation=20)
    fig.tight_layout()
    return fig


def dataframe_to_markdown(df: pd.DataFrame) -> str:
    if df.empty:
        return "(empty)"
    return df.to_markdown(index=False)


def determine_pack_scope(merged_csv: Path | None, df: pd.DataFrame) -> tuple[str, list[str]]:
    merged_str = str(merged_csv) if merged_csv else ""
    has_dataset_group_source = "dataset_group_source" in df.columns and df["dataset_group_source"].notna().any()
    is_march7_enriched = "march7_check" in merged_str or has_dataset_group_source
    current_scope = (
        "March 7 enriched registry 验证范围：额外验证 `dataset_group_source` 审计与 trusted `dataset_group` 汇总。"
        if is_march7_enriched
        else "主 registry 可用范围：仅完成 `schema_version` 和 `active_time_source` 分层 QA。"
    )
    scope_lines = [
        "主 registry：仅完成 `schema_version` 和 `active_time_source` 分层 QA。",
        "March 7 enriched：额外验证 `dataset_group_source` 审计与 trusted `dataset_group` 汇总。",
        f"本次输出对应：{current_scope}",
    ]
    return current_scope, scope_lines


def build_join_status_note(registry_suite_summary: dict | None) -> str:
    note = (
        "`task_join_status` 反映 planned/runtime bridge 状态，不能直接解释为标注员行为问题；"
        "`ambiguous` / `unmatched` 是为了避免静默强配而显式保留的 join 状态。"
    )
    if not registry_suite_summary:
        return note

    join_counts = registry_suite_summary.get("registry_suite", {}).get("counts_by_task_join_status")
    if join_counts:
        note += f" registry_suite_summary 当前计数：{join_counts}。"
    return note


def build_active_time_note() -> str:
    return (
        "`active_time_source=log` 表示 direct active log 命中；"
        "`lead_time_fallback` 只是回退到 Label Studio `lead_time`，不是 active log。"
    )


def main() -> int:
    args = parse_args()

    merged_csv = choose_existing_path(args.merged_csv, DEFAULT_MERGED_CANDIDATES)
    annotation_registry = choose_existing_path(args.annotation_registry, DEFAULT_ANNOTATION_CANDIDATES)
    active_time_registry = choose_existing_path(args.active_time_registry, DEFAULT_ACTIVE_TIME_CANDIDATES)
    registry_suite_summary_path = choose_existing_path(args.registry_suite_summary, DEFAULT_REGISTRY_SUITE_SUMMARY_CANDIDATES)

    base_df = read_csv_or_none(merged_csv)
    annotation_df = read_csv_or_none(annotation_registry)
    active_df = read_csv_or_none(active_time_registry)
    registry_suite_summary = read_json_or_none(registry_suite_summary_path)

    if base_df is None and annotation_df is None:
        raise FileNotFoundError("No usable input CSV was found. Provide --merged-csv or --annotation-registry.")

    df = base_df if base_df is not None else annotation_df.copy()
    if annotation_df is not None and base_df is not annotation_df:
        df = merge_if_needed(
            df,
            annotation_df,
            prefer_columns=[
                "annotation_id",
                "schema_version",
                "dataset_group",
                "dataset_group_source",
                "task_join_status",
                "normalized_scope",
                "is_oos",
            ],
        )
    df = merge_if_needed(
        df,
        active_df,
        prefer_columns=["active_time_value", "active_time_source", "lead_time_seconds"],
    )
    df = prepare_frame(df)

    run_tag = args.tag or (merged_csv.stem if merged_csv is not None else "pooled_qa")
    output_dir = args.out_dir / run_tag
    output_dir.mkdir(parents=True, exist_ok=True)

    sns.set_theme(style="whitegrid")

    pack_scope, scope_lines = determine_pack_scope(merged_csv, df)
    join_status_note = build_join_status_note(registry_suite_summary)
    active_time_note = build_active_time_note()
    mixed_scope_audit = build_mixed_scope_audit(df)

    plot_specs = [
        ("01_rows_by_schema_version.png", plot_rows_by_schema(df)),
        ("02_join_status_by_schema_version.png", plot_join_status_by_schema(df)),
        ("03_active_time_hist_by_schema_and_source.png", plot_active_time_histogram(df)),
        ("04_active_time_box_by_schema_and_source.png", plot_active_time_box(df)),
        ("05_annotator_profile_by_schema_version.png", plot_annotator_profile(df)),
        ("06_dataset_group_source_by_schema_version.png", plot_dataset_group_source_counts(df)),
    ]

    trusted_group_fig, trusted_group_counts = plot_dataset_group_counts_trusted(
        df,
        trusted_sources=args.trusted_dataset_group_sources,
    )
    plot_specs.append(("07_dataset_group_counts_trusted.png", trusted_group_fig))
    plot_specs.append(("08_mixed_scope_tasks_by_schema_version.png", plot_mixed_scope_counts_by_schema(mixed_scope_audit)))

    saved_files: list[str] = []
    skipped_files: dict[str, str] = {}
    for filename, figure in plot_specs:
        if figure is None:
            skipped_files[filename] = "missing required columns or no eligible rows"
            continue
        save_figure(figure, output_dir / filename)
        saved_files.append(filename)

    schema_counts = (
        df.groupby("schema_version", dropna=False)
        .size()
        .reset_index(name="rows")
        .sort_values(["rows", "schema_version"], ascending=[False, True])
    )
    schema_counts.to_csv(output_dir / "table_schema_version_counts.csv", index=False)

    active_time_source_counts = (
        df.groupby(["schema_version", "active_time_source"], dropna=False)
        .agg(rows=("task_id", "size"), non_null_active_time=("active_time_plot", lambda s: int(s.notna().sum())))
        .reset_index()
    )
    active_time_source_counts.to_csv(output_dir / "table_active_time_source_by_schema.csv", index=False)

    dataset_group_source_counts = pd.DataFrame()
    if "dataset_group_source" in df.columns:
        dataset_group_source_counts = (
            df.groupby(["schema_version", "dataset_group_source"], dropna=False)
            .size()
            .reset_index(name="rows")
        )
        dataset_group_source_counts.to_csv(output_dir / "table_dataset_group_source_by_schema.csv", index=False)

    if not trusted_group_counts.empty:
        trusted_group_counts.to_csv(output_dir / "table_dataset_group_counts_trusted.csv", index=False)

    if not mixed_scope_audit.empty:
        mixed_scope_audit.to_csv(output_dir / "table_mixed_scope_audit.csv", index=False)

    summary_payload = {
        "mode": "pooled_qa",
        "is_paper_figure_pack": False,
        "coverage_scope": pack_scope,
        "input_files": {
            "merged_csv": str(merged_csv) if merged_csv else None,
            "annotation_registry": str(annotation_registry) if annotation_registry else None,
            "active_time_registry": str(active_time_registry) if active_time_registry else None,
            "registry_suite_summary": str(registry_suite_summary_path) if registry_suite_summary_path else None,
        },
        "n_rows": int(len(df)),
        "n_tasks": int(df["task_id"].nunique()) if "task_id" in df.columns else None,
        "n_annotators": int(df["annotator_id"].nunique()) if "annotator_id" in df.columns else None,
        "schema_version_counts": schema_counts.to_dict(orient="records"),
        "active_time_source_by_schema": active_time_source_counts.to_dict(orient="records"),
        "dataset_group_source_by_schema": dataset_group_source_counts.to_dict(orient="records"),
        "mixed_scope_task_count": int(len(mixed_scope_audit)),
        "mixed_scope_multi_annotator_task_count": int(mixed_scope_audit.loc[mixed_scope_audit["is_multi_annotator"]].shape[0]) if not mixed_scope_audit.empty else 0,
        "trusted_dataset_group_sources": list(args.trusted_dataset_group_sources),
        "trusted_dataset_group_rows": int(trusted_group_counts["rows"].sum()) if not trusted_group_counts.empty else 0,
        "join_status_note": join_status_note,
        "active_time_note": active_time_note,
        "saved_files": saved_files,
        "skipped_files": skipped_files,
    }
    (output_dir / "summary.json").write_text(json.dumps(summary_payload, indent=2, ensure_ascii=False), encoding="utf-8")

    summary_lines = [
        "# Pooled QA Summary",
        "",
        "- This pack is for pooled QA only, not paper main figures.",
        "- It does not replace formal analysis and does not output paper main figures.",
        "- Every figure is stratified by `schema_version`.",
        "- Active-time figures are additionally split by `active_time_source`.",
        "- Dataset-group aggregation is filtered by trusted `dataset_group_source` values first.",
        "",
        "## Coverage of this pack",
    ]
    summary_lines.extend([f"- {line}" for line in scope_lines])
    summary_lines.extend([
        "",
        "## Join-status interpretation",
        f"- {join_status_note}",
        "",
        "## Active-time interpretation",
        f"- {active_time_note}",
        "",
        "## Inputs",
        f"- merged_csv: {merged_csv}",
        f"- annotation_registry: {annotation_registry}",
        f"- active_time_registry: {active_time_registry}",
        f"- registry_suite_summary: {registry_suite_summary_path}",
        "",
        "## High-level counts",
        f"- rows: {len(df)}",
        f"- tasks: {df['task_id'].nunique() if 'task_id' in df.columns else '(missing)'}",
        f"- annotators: {df['annotator_id'].nunique() if 'annotator_id' in df.columns else '(missing)'}",
        f"- mixed scope tasks: {len(mixed_scope_audit)}",
        f"- mixed scope multi-annotator tasks: {mixed_scope_audit.loc[mixed_scope_audit['is_multi_annotator']].shape[0] if not mixed_scope_audit.empty else 0}",
        "",
        "## schema_version counts",
        dataframe_to_markdown(schema_counts),
        "",
        "## active_time_source by schema_version",
        dataframe_to_markdown(active_time_source_counts),
        "",
        "## dataset_group_source by schema_version",
        dataframe_to_markdown(dataset_group_source_counts),
        "",
        "## trusted dataset_group sources",
        ", ".join(args.trusted_dataset_group_sources),
        "",
        "## Saved figures",
    ])
    summary_lines.extend([f"- {filename}" for filename in saved_files] or ["- (none)"])
    summary_lines.append("")
    summary_lines.append("## Skipped figures")
    if skipped_files:
        summary_lines.extend([f"- {filename}: {reason}" for filename, reason in skipped_files.items()])
    else:
        summary_lines.append("- (none)")
    if not trusted_group_counts.empty:
        summary_lines.extend([
            "",
            "## Trusted dataset_group counts",
            dataframe_to_markdown(trusted_group_counts),
        ])
    summary_lines.extend([
        "",
        "## Mixed scope audit",
        "- Mixed scope means the same task has both in-scope and OOS votes across annotations.",
    ])
    if mixed_scope_audit.empty:
        summary_lines.append("- (none)")
    else:
        summary_lines.extend([
            "- Audit table: table_mixed_scope_audit.csv",
            dataframe_to_markdown(mixed_scope_audit),
        ])
    (output_dir / "SUMMARY.md").write_text("\n".join(summary_lines), encoding="utf-8")

    print(f"[pooled-qa] wrote outputs to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
