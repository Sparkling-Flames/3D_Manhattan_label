"""Save quality report figures to disk (batch mode).

This script uses viz_quality_utils.py to generate and save all standard figures
from a quality_report CSV. Designed for:
- Batch figure generation for documentation/reports
- Reproducible figure sets with consistent styling
- Integration with automated analysis pipelines
"""

import argparse
import os
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import seaborn as sns

from viz_quality_utils import (
    load_quality_report,
    filter_in_scope,
    filter_layout_used,
    plot_scope_distribution,
    plot_layout_gate_reasons,
    plot_metric_distribution,
    plot_metric_vs_time,
    plot_metric_by_annotator,
    plot_time_by_annotator,
    plot_task_annotator_heatmap,
    plot_mixed_scope_tasks,
    build_summary_stats,
)


def save_fig(fig, path: str, dpi: int = 200):
    """Save figure and close."""
    if fig is None:
        return
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"  ✅ {Path(path).name}")


def main():
    parser = argparse.ArgumentParser(description="Generate and save quality report figures")
    parser.add_argument("csv", help="Path to quality_report_*.csv")
    parser.add_argument("--out-dir", default="analysis_results/figures", help="Output directory")
    parser.add_argument("--tag", default=None, help="Optional run tag (folder name suffix)")
    parser.add_argument("--metric", default="iou", help="Primary metric for plots")
    parser.add_argument("--only-in-scope", action="store_true", help="Filter to in-scope rows")
    parser.add_argument("--only-layout-used", action="store_true", help="Filter to layout_used==True")
    parser.add_argument("--dpi", type=int, default=200, help="Figure DPI")
    args = parser.parse_args()
    
    # Set seaborn style
    sns.set_theme(style="whitegrid")
    
    # Load data
    print(f"Loading {args.csv}...")
    df = load_quality_report(args.csv)
    print(f"  Loaded {len(df)} rows, {df['task_id'].nunique()} tasks")
    
    # Apply filters
    if args.only_in_scope:
        df = filter_in_scope(df)
        print(f"  Filtered to in-scope: {len(df)} rows")
    
    if args.only_layout_used:
        df = filter_layout_used(df)
        print(f"  Filtered to layout_used: {len(df)} rows")
    
    # Prepare output directory
    run_tag = args.tag or datetime.now().strftime("%Y%m%d")
    out_dir = Path(args.out_dir) / run_tag
    out_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\nGenerating figures in {out_dir}...")
    
    # Generate all standard plots
    save_fig(plot_scope_distribution(df), out_dir / "01_rows_by_scope.png", args.dpi)
    save_fig(plot_layout_gate_reasons(df), out_dir / "02_layout_gate_reason.png", args.dpi)
    save_fig(plot_metric_distribution(df, args.metric), out_dir / f"03_{args.metric}_hist_by_scope.png", args.dpi)
    save_fig(plot_metric_vs_time(df, args.metric), out_dir / f"04_{args.metric}_vs_time.png", args.dpi)
    save_fig(plot_metric_by_annotator(df, args.metric), out_dir / f"05_{args.metric}_by_annotator.png", args.dpi)
    save_fig(plot_time_by_annotator(df), out_dir / "06_time_by_annotator.png", args.dpi)
    save_fig(plot_task_annotator_heatmap(df, args.metric), out_dir / f"07_heatmap_task_annotator_{args.metric}.png", args.dpi)
    save_fig(plot_mixed_scope_tasks(df), out_dir / "08_mixed_scope_tasks.png", args.dpi)
    
    # Save summary stats
    stats = build_summary_stats(df)
    summary_lines = ["# Quality Report Summary\n"]
    summary_lines.append(f"- rows: {stats['n_rows']}")
    summary_lines.append(f"- tasks: {stats['n_tasks']}")
    summary_lines.append(f"- annotators: {', '.join(stats['n_annotators'])}\n")
    summary_lines.append("## Multi-annotator coverage")
    for n, count in stats["annotators_per_task"].items():
        summary_lines.append(f"- {n} annotator(s) per task: {count} tasks\n")
    
    if "layout_used_rate" in stats:
        summary_lines.append("## Layout gating")
        summary_lines.append(f"- layout_used rate: {stats['layout_used_rate']:.4f}")
        if stats.get("layout_gate_reasons"):
            summary_lines.append("- layout_gate_reason counts:")
            for reason, cnt in stats["layout_gate_reasons"].items():
                summary_lines.append(f"  - {reason}: {cnt}")
    
    if "scope_empty_count" in stats:
        summary_lines.append("\n## Scope hygiene")
        summary_lines.append(f"- scope empty rows: {stats['scope_empty_count']}/{stats['n_rows']}")
        summary_lines.append("- scope distribution:")
        for scope, cnt in stats["scope_distribution"].items():
            summary_lines.append(f"  - {scope}: {cnt}")
    
    if "mixed_scope_tasks" in stats:
        summary_lines.append("\n## Mixed-scope tasks")
        mixed_str = ", ".join(map(str, stats["mixed_scope_tasks"])) if stats["mixed_scope_tasks"] else "(none)"
        summary_lines.append(f"- task_ids: {mixed_str}")
    
    (out_dir / "SUMMARY.md").write_text("\n".join(summary_lines), encoding="utf-8")
    print(f"  ✅ SUMMARY.md")
    
    # Save edge-case tables
    cols = ["task_id", "annotator_id", "active_time", args.metric, "boundary_rmse_px", 
            "layout_used", "layout_gate_reason", "scope", "difficulty", "model_issue"]
    cols = [c for c in cols if c in df.columns]
    
    df.sort_values(args.metric).head(20).to_csv(out_dir / f"table_low_{args.metric}.csv", index=False, columns=cols)
    print(f"  ✅ table_low_{args.metric}.csv")
    
    if "boundary_rmse_px" in df.columns:
        df.sort_values("boundary_rmse_px", ascending=False).head(20).to_csv(out_dir / "table_high_boundary_rmse.csv", index=False, columns=cols)
        print(f"  ✅ table_high_boundary_rmse.csv")
    
    if "active_time" in df.columns:
        df.sort_values("active_time", ascending=False).head(20).to_csv(out_dir / "table_high_time.csv", index=False, columns=cols)
        print(f"  ✅ table_high_time.csv")
    
    print(f"\n🎉 Done! Figures saved to {out_dir}")


if __name__ == "__main__":
    main()
