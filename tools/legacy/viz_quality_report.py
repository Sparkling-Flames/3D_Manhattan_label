import argparse
import os
from datetime import datetime

import numpy as np
import pandas as pd


def _safe_mkdir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _today_tag() -> str:
    return datetime.now().strftime("%Y%m%d")


def _is_empty_str_series(s: pd.Series) -> pd.Series:
    return s.isna() | (s.astype(str).str.strip() == "") | (s.astype(str).str.lower() == "nan")


def _coerce_bool(col: pd.Series) -> pd.Series:
    if col.dtype == bool:
        return col
    return col.astype(str).str.lower().map({"true": True, "false": False}).fillna(False)


def _split_multiselect(cell) -> list[str]:
    if cell is None or (isinstance(cell, float) and np.isnan(cell)):
        return []
    if isinstance(cell, list):
        return [str(x).strip() for x in cell if str(x).strip()]
    s = str(cell).strip()
    if not s or s.lower() == "nan":
        return []
    return [x.strip() for x in s.split(";") if x.strip()]


def _explode_tags(df: pd.DataFrame, col: str) -> pd.DataFrame:
    out = df.copy()
    out[col] = out[col].apply(_split_multiselect)
    out = out.explode(col)
    out[col] = out[col].fillna("(empty)")
    out.loc[out[col].astype(str).str.strip() == "", col] = "(empty)"
    return out


def _write_text(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def build_summary(df: pd.DataFrame) -> str:
    rows = len(df)
    tasks = int(df["task_id"].nunique())
    annotators = sorted(df["annotator_id"].astype(str).unique().tolist())

    per_task_n = df.groupby("task_id")["annotator_id"].nunique()
    n_dist = per_task_n.value_counts().sort_index()

    layout_used = _coerce_bool(df.get("layout_used", pd.Series([False] * rows)))

    scope = df.get("scope", pd.Series([""] * rows)).fillna("")
    scope_str = scope.astype(str)
    scope_empty = int(
        (
            _is_empty_str_series(scope_str)
            | (scope_str.str.strip() == "(empty)")
            | (scope_str.str.strip() == "(missing)")
        ).sum()
    )

    gate_reason = df.get("layout_gate_reason", pd.Series([""] * rows)).fillna("(empty)")
    gate_reason_empty = gate_reason.astype(str).replace({"": "(empty)", "nan": "(empty)", "None": "(empty)"})

    mixed_tasks = sorted(
        df.loc[_coerce_bool(df.get("task_scope_is_mixed", pd.Series([False] * rows))), "task_id"]
        .unique()
        .tolist()
    )

    lines = []
    lines.append("# Quality Report Summary\n")
    lines.append(f"- rows: {rows}")
    lines.append(f"- tasks: {tasks}")
    lines.append(f"- annotators: {', '.join(annotators)}")
    lines.append("\n## Multi-annotator coverage")
    for k, v in n_dist.items():
        lines.append(f"- {int(k)} annotator(s) per task: {int(v)} tasks")

    lines.append("\n## Layout gating")
    lines.append(f"- layout_used true: {int(layout_used.sum())} / {rows}")
    if "layout_gate_reason" in df.columns:
        vc = gate_reason_empty.value_counts()
        lines.append("- gate reasons:")
        for k, v in vc.items():
            lines.append(f"  - {k}: {int(v)}")

    lines.append("\n## Scope")
    lines.append(f"- scope empty: {scope_empty} / {rows}")
    if "scope" in df.columns:
        vc = scope_str.replace({"": "(empty)", "nan": "(empty)", "None": "(empty)"}).value_counts()
        lines.append("- scope distribution:")
        for k, v in vc.items():
            lines.append(f"  - {k}: {int(v)}")

    if mixed_tasks:
        lines.append("\n## Mixed-scope tasks")
        lines.append(f"- task_ids: {', '.join(map(str, mixed_tasks[:50]))}{' ...' if len(mixed_tasks) > 50 else ''}")

    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Legacy: visualize quality report CSV.")
    parser.add_argument("csv", help="Path to quality_report_*.csv")
    parser.add_argument("--out", default=None, help="Output directory")
    parser.add_argument(
        "--metric",
        default="layout_2d_iou",
        help="Metric column for heatmap / tables (default: layout_2d_iou)",
    )
    args = parser.parse_args(argv)

    csv_path = args.csv
    metric_col = args.metric
    df = pd.read_csv(csv_path)

    out_dir = args.out
    if out_dir is None:
        base = os.path.splitext(os.path.basename(csv_path))[0]
        out_dir = os.path.join(os.path.dirname(csv_path), f"{base}_viz_{_today_tag()}")
    _safe_mkdir(out_dir)

    # Lazy import for environments without plotting deps.
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import seaborn as sns

        # 01 scope distribution
        if "scope" in df.columns:
            df2 = _explode_tags(df, "scope")
            plt.figure(figsize=(10, 4))
            vc = df2["scope"].value_counts().sort_values(ascending=False)
            sns.barplot(x=vc.index, y=vc.values)
            plt.xticks(rotation=30, ha="right")
            plt.title("scope distribution")
            plt.tight_layout()
            plt.savefig(os.path.join(out_dir, "01_scope_distribution.png"), dpi=200)
            plt.close()

        # 02 layout gate reasons
        if "layout_gate_reason" in df.columns:
            plt.figure(figsize=(10, 4))
            vc = df["layout_gate_reason"].fillna("(empty)").astype(str)
            vc = vc.replace({"": "(empty)", "nan": "(empty)", "None": "(empty)"}).value_counts()
            sns.barplot(x=vc.index, y=vc.values)
            plt.xticks(rotation=30, ha="right")
            plt.title("layout_gate_reason")
            plt.tight_layout()
            plt.savefig(os.path.join(out_dir, "02_layout_gate_reason.png"), dpi=200)
            plt.close()

        # 03 metric distribution
        if metric_col in df.columns:
            plt.figure(figsize=(8, 3))
            sns.histplot(df[metric_col].dropna(), bins=30)
            plt.title(f"{metric_col} distribution")
            plt.tight_layout()
            plt.savefig(os.path.join(out_dir, f"03_metric_hist_{metric_col}.png"), dpi=200)
            plt.close()

        # 04 metric vs time
        if metric_col in df.columns and "active_time" in df.columns:
            plt.figure(figsize=(6, 4))
            sns.scatterplot(data=df, x="active_time", y=metric_col, hue="annotator_id", alpha=0.7)
            plt.xscale("log")
            plt.title(f"{metric_col} vs active_time (log-x)")
            plt.tight_layout()
            plt.savefig(os.path.join(out_dir, f"04_metric_vs_time_{metric_col}.png"), dpi=200)
            plt.close()

        # 05 metric by annotator
        if metric_col in df.columns and "annotator_id" in df.columns:
            plt.figure(figsize=(10, 4))
            sns.boxplot(data=df, x="annotator_id", y=metric_col)
            sns.stripplot(data=df, x="annotator_id", y=metric_col, color="black", size=2.5, alpha=0.5)
            plt.title(f"{metric_col} by annotator")
            plt.tight_layout()
            plt.savefig(os.path.join(out_dir, f"05_metric_by_annotator_{metric_col}.png"), dpi=200)
            plt.close()

        # 06 time by annotator
        if "active_time" in df.columns and "annotator_id" in df.columns:
            plt.figure(figsize=(10, 4))
            sns.boxplot(data=df, x="annotator_id", y="active_time")
            sns.stripplot(data=df, x="annotator_id", y="active_time", color="black", size=2.5, alpha=0.5)
            plt.yscale("log")
            plt.title("active_time by annotator (log-y)")
            plt.tight_layout()
            plt.savefig(os.path.join(out_dir, "06_time_by_annotator.png"), dpi=200)
            plt.close()

        # 07 task x annotator heatmap
        if {"task_id", "annotator_id", metric_col}.issubset(df.columns):
            pv = df.pivot_table(index="task_id", columns="annotator_id", values=metric_col, aggfunc="mean")
            if pv.shape[0] <= 60:
                plt.figure(figsize=(10, max(4, 0.25 * pv.shape[0])))
                sns.heatmap(pv, annot=False, cmap="viridis", vmin=0.0, vmax=1.0)
                plt.title(f"Task x Annotator heatmap ({metric_col})")
                plt.tight_layout()
                plt.savefig(os.path.join(out_dir, f"07_heatmap_task_annotator_{metric_col}.png"), dpi=200)
                plt.close()

        # 08 mixed scope tasks bar
        if "task_scope_is_mixed" in df.columns:
            mixed = df[df["task_scope_is_mixed"].astype(bool)].copy()
            if len(mixed) > 0:
                plt.figure(figsize=(8, 3))
                vc = mixed["task_id"].value_counts()
                sns.barplot(x=vc.index, y=vc.values)
                plt.title("Mixed-scope tasks (row counts)")
                plt.xlabel("task_id")
                plt.ylabel("rows")
                plt.tight_layout()
                plt.savefig(os.path.join(out_dir, "08_mixed_scope_tasks.png"), dpi=200)
                plt.close()

    except Exception as e:
        _write_text(os.path.join(out_dir, "PLOT_ERROR.txt"), f"Plotting failed: {e}\n")

    # Write summary + edge-case tables
    summary_md = build_summary(df)
    _write_text(os.path.join(out_dir, "SUMMARY.md"), summary_md)

    cols = [
        "task_id",
        "annotator_id",
        "active_time",
        metric_col,
        "boundary_rmse_px",
        "layout_used",
        "layout_gate_reason",
        "scope",
        "difficulty",
        "model_issue",
    ]
    cols = [c for c in cols if c in df.columns]

    # lowest metric
    if metric_col in df.columns:
        low = df.sort_values(metric_col, ascending=True).head(20)
        low.to_csv(os.path.join(out_dir, f"table_low_{metric_col}.csv"), index=False, columns=cols)

    # highest boundary rmse
    if "boundary_rmse_px" in df.columns:
        hi_b = df.sort_values("boundary_rmse_px", ascending=False).head(20)
        hi_b.to_csv(os.path.join(out_dir, "table_high_boundary_rmse.csv"), index=False, columns=cols)

    # highest time
    if "active_time" in df.columns:
        hi_t = df.sort_values("active_time", ascending=False).head(20)
        hi_t.to_csv(os.path.join(out_dir, "table_high_time.csv"), index=False, columns=cols)

    print(f"Saved figures and tables to: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
