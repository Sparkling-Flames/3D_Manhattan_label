"""Quality report visualization utilities for Jupyter notebook and scripted use.

This module provides reusable functions for analyzing and visualizing HoHoNet 
quality reports. It's designed for interactive exploration in Jupyter notebooks
while also supporting batch figure generation via save_quality_figures.py.

Design Principles:
- Functions return matplotlib/seaborn figure objects (not saved directly)
- DataFrame transformations are separate from plotting
- Compatible with aggregate_analysis.py outputs
- Extensible for custom plots
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple


def load_quality_report(csv_path: str) -> pd.DataFrame:
    """Load and normalize a quality_report CSV.
    
    Args:
        csv_path: Path to quality_report_*.csv
    
    Returns:
        DataFrame with normalized dtypes (task_id/annotator_id as str, booleans coerced)
    """
    df = pd.read_csv(csv_path)
    
    # Normalize string IDs
    for c in ["task_id", "annotator_id"]:
        if c in df.columns:
            df[c] = df[c].astype(str)
    
    # Normalize boolean columns
    bool_cols = ["layout_used", "task_scope_is_mixed", "pairing_warning", 
                 "pointwise_rmse_used", "has_manual_poly"]
    for c in bool_cols:
        if c in df.columns:
            df[c] = df[c].astype(str).str.lower().map({"true": True, "false": False}).fillna(False)
    
    # Normalize scope (empty -> '(empty)')
    if "scope" not in df.columns:
        df["scope"] = "(missing)"
    df["scope"] = df["scope"].fillna("").astype(str)
    df.loc[df["scope"].str.strip() == "", "scope"] = "(empty)"
    
    return df


def compute_task_summary(df: pd.DataFrame, metric_cols: Optional[List[str]] = None) -> pd.DataFrame:
    """Aggregate per-task statistics from multi-annotator rows.
    
    Args:
        df: quality_report DataFrame (long format: one row per annotator)
        metric_cols: Columns to aggregate (default: iou, boundary_rmse_px, active_time)
    
    Returns:
        DataFrame with one row per task_id, columns like:
        - n_annotators
        - {metric}_median, {metric}_iqr, {metric}_min, {metric}_max
        - scope_majority, is_mixed_scope
    """
    if metric_cols is None:
        metric_cols = ["iou", "boundary_rmse_px", "active_time"]
    
    agg_funcs = {}
    agg_funcs["annotator_id"] = "nunique"
    
    for m in metric_cols:
        if m in df.columns:
            agg_funcs[m] = ["median", lambda x: x.quantile(0.75) - x.quantile(0.25), "min", "max"]
    
    summary = df.groupby("task_id").agg(agg_funcs).reset_index()
    
    # Flatten multi-level columns
    summary.columns = ["_".join(c).rstrip("_") if isinstance(c, tuple) else c for c in summary.columns]
    summary.rename(columns={"annotator_id_nunique": "n_annotators"}, inplace=True)
    
    # Compute scope majority and mixed flag
    scope_mode = df.groupby("task_id")["scope"].apply(lambda x: x.mode()[0] if len(x.mode()) > 0 else "(unknown)")
    scope_nunique = df.groupby("task_id")["scope"].nunique()
    
    summary["scope_majority"] = summary["task_id"].map(scope_mode)
    summary["is_mixed_scope"] = summary["task_id"].map(scope_nunique > 1)
    
    return summary


def compute_disagreement_table(df: pd.DataFrame, metric: str = "iou") -> pd.DataFrame:
    """Find tasks with highest variance in a metric across annotators.
    
    Args:
        df: quality_report DataFrame
        metric: Column to compute variance on
    
    Returns:
        DataFrame sorted by variance (highest disagreement first)
    """
    if metric not in df.columns:
        raise ValueError(f"Metric column not found: {metric}")
    
    var = df.groupby("task_id")[metric].var().sort_values(ascending=False)
    mean = df.groupby("task_id")[metric].mean()
    n = df.groupby("task_id")[metric].count()
    
    result = pd.DataFrame({
        "task_id": var.index,
        f"{metric}_variance": var.values,
        f"{metric}_mean": mean.loc[var.index].values,
        "n_annotators": n.loc[var.index].values,
    }).reset_index(drop=True)
    
    return result


def filter_in_scope(df: pd.DataFrame) -> pd.DataFrame:
    """Filter to in-scope rows only (scope not starting with 'oos')."""
    return df[~df["scope"].str.lower().str.startswith("oos")].copy()


def filter_layout_used(df: pd.DataFrame) -> pd.DataFrame:
    """Filter to rows where layout_used == True."""
    if "layout_used" not in df.columns:
        raise ValueError("layout_used column not found")
    return df[df["layout_used"] == True].copy()


def build_summary_stats(df: pd.DataFrame) -> Dict:
    """Compute summary statistics for display in notebook."""
    stats = {
        "n_rows": len(df),
        "n_tasks": int(df["task_id"].nunique()),
        "n_annotators": sorted(df["annotator_id"].astype(str).unique().tolist()),
        "annotators_per_task": df.groupby("task_id")["annotator_id"].nunique().value_counts().sort_index().to_dict(),
    }
    
    if "layout_used" in df.columns:
        stats["layout_used_rate"] = float(df["layout_used"].mean())
        stats["layout_gate_reasons"] = df.loc[~df["layout_used"], "layout_gate_reason"].value_counts().to_dict()
    
    if "scope" in df.columns:
        stats["scope_empty_count"] = int((df["scope"] == "(empty)").sum())
        stats["scope_distribution"] = df["scope"].value_counts().head(10).to_dict()
    
    if "task_scope_is_mixed" in df.columns:
        stats["mixed_scope_tasks"] = sorted(df.loc[df["task_scope_is_mixed"], "task_id"].unique().tolist())
    
    return stats


# === Plotting functions (return figure objects) ===

def plot_scope_distribution(df: pd.DataFrame, figsize=(10, 4)):
    """Bar chart of scope counts."""
    import matplotlib.pyplot as plt
    import seaborn as sns
    
    fig, ax = plt.subplots(figsize=figsize)
    order = df["scope"].value_counts().index.tolist()
    sns.countplot(data=df, x="scope", order=order, ax=ax)
    ax.set_xticklabels(ax.get_xticklabels(), rotation=30, ha="right")
    ax.set_title("Rows by scope")
    plt.tight_layout()
    return fig


def plot_layout_gate_reasons(df: pd.DataFrame, figsize=(10, 4)):
    """Bar chart of layout_gate_reason for layout_used=False rows."""
    import matplotlib.pyplot as plt
    import seaborn as sns
    
    if "layout_used" not in df.columns:
        raise ValueError("layout_used column not found")
    
    gate_df = df.loc[~df["layout_used"], "layout_gate_reason"].fillna("(empty)")
    if len(gate_df) == 0:
        return None
    
    fig, ax = plt.subplots(figsize=figsize)
    vc = gate_df.value_counts()
    sns.barplot(x=vc.index, y=vc.values, ax=ax)
    ax.set_xticklabels(ax.get_xticklabels(), rotation=30, ha="right")
    ax.set_title("layout_gate_reason (layout_used = false)")
    ax.set_ylabel("rows")
    plt.tight_layout()
    return fig


def plot_metric_distribution(df: pd.DataFrame, metric: str, hue: str = "scope", bins: int = 25, figsize=(10, 4)):
    """Histogram of metric distribution by hue."""
    import matplotlib.pyplot as plt
    import seaborn as sns
    
    if metric not in df.columns:
        raise ValueError(f"Metric column not found: {metric}")
    
    fig, ax = plt.subplots(figsize=figsize)
    sns.histplot(data=df, x=metric, hue=hue, bins=bins, element="step", stat="density", common_norm=False, ax=ax)
    ax.set_title(f"Distribution of {metric} by {hue}")
    plt.tight_layout()
    return fig


def plot_metric_vs_time(df: pd.DataFrame, metric: str, hue: str = "scope", style: str = "annotator_id", figsize=(7, 5)):
    """Scatter plot of metric vs active_time."""
    import matplotlib.pyplot as plt
    import seaborn as sns
    
    if metric not in df.columns or "active_time" not in df.columns:
        raise ValueError("Required columns not found")
    
    fig, ax = plt.subplots(figsize=figsize)
    sns.scatterplot(data=df, x="active_time", y=metric, hue=hue, style=style, alpha=0.85, ax=ax)
    ax.set_xscale("log")
    ax.set_title(f"{metric} vs active_time (log-x)")
    plt.tight_layout()
    return fig


def plot_metric_by_annotator(df: pd.DataFrame, metric: str, figsize=(10, 4)):
    """Boxplot of metric by annotator with strip overlay."""
    import matplotlib.pyplot as plt
    import seaborn as sns
    
    if metric not in df.columns or "annotator_id" not in df.columns:
        raise ValueError("Required columns not found")
    
    fig, ax = plt.subplots(figsize=figsize)
    sns.boxplot(data=df, x="annotator_id", y=metric, ax=ax)
    sns.stripplot(data=df, x="annotator_id", y=metric, color="black", size=2.5, alpha=0.5, ax=ax)
    ax.set_title(f"{metric} by annotator")
    plt.tight_layout()
    return fig


def plot_time_by_annotator(df: pd.DataFrame, figsize=(10, 4)):
    """Boxplot of active_time by annotator (log-y)."""
    import matplotlib.pyplot as plt
    import seaborn as sns
    
    if "active_time" not in df.columns or "annotator_id" not in df.columns:
        raise ValueError("Required columns not found")
    
    fig, ax = plt.subplots(figsize=figsize)
    sns.boxplot(data=df, x="annotator_id", y="active_time", ax=ax)
    sns.stripplot(data=df, x="annotator_id", y="active_time", color="black", size=2.5, alpha=0.5, ax=ax)
    ax.set_yscale("log")
    ax.set_title("active_time by annotator (log-y)")
    plt.tight_layout()
    return fig


def plot_task_annotator_heatmap(df: pd.DataFrame, metric: str, figsize=(10, 8), max_tasks: int = 60):
    """Heatmap of task x annotator values."""
    import matplotlib.pyplot as plt
    import seaborn as sns
    
    if not {"task_id", "annotator_id", metric}.issubset(df.columns):
        raise ValueError("Required columns not found")
    
    pv = df.pivot_table(index="task_id", columns="annotator_id", values=metric, aggfunc="mean")
    
    if pv.shape[0] > max_tasks:
        print(f"⚠️  Too many tasks ({pv.shape[0]}), showing top {max_tasks} by row variance")
        row_var = pv.var(axis=1).sort_values(ascending=False)
        pv = pv.loc[row_var.head(max_tasks).index]
    
    fig, ax = plt.subplots(figsize=(figsize[0], max(4, 0.25 * pv.shape[0])))
    sns.heatmap(pv, annot=False, cmap="viridis", vmin=0.0, vmax=1.0, ax=ax)
    ax.set_title(f"Task x Annotator heatmap ({metric})")
    plt.tight_layout()
    return fig


def plot_mixed_scope_tasks(df: pd.DataFrame, figsize=(8, 3)):
    """Bar chart of mixed-scope task counts."""
    import matplotlib.pyplot as plt
    import seaborn as sns
    
    if "task_scope_is_mixed" not in df.columns:
        raise ValueError("task_scope_is_mixed column not found")
    
    mixed = df[df["task_scope_is_mixed"]].copy()
    if len(mixed) == 0:
        return None
    
    fig, ax = plt.subplots(figsize=figsize)
    vc = mixed["task_id"].value_counts()
    sns.barplot(x=vc.index, y=vc.values, ax=ax)
    ax.set_title("Mixed-scope tasks (row counts)")
    ax.set_xlabel("task_id")
    ax.set_ylabel("rows")
    plt.tight_layout()
    return fig
