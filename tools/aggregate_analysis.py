"""Aggregate quality analysis results from multiple Label Studio datasets.

This tool merges outputs from analyze_quality.py (multiple CSV files) and produces:
- Consolidated CSV with dataset labels
- Per-dataset summary statistics
- Cross-dataset comparisons (Manual vs Semi, validation subsets)

Design Principles (for future plugin development):
1. Modular API: clear separation of load/merge/summarize/export
2. Configuration-driven: support external JSON config for dataset mapping
3. Extensible outputs: CSV + JSON + Markdown table formats
4. Robust error handling: graceful degradation if expected columns missing
"""

import argparse
import csv
import json
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np


# === Configuration Schema (for plugin mode) ===
DEFAULT_CONFIG = {
    "datasets": {
        "main_manual": {"display_name": "Manual_Test", "condition": "manual", "subset": "test"},
        "main_semi": {"display_name": "SemiAuto_Test", "condition": "semi", "subset": "test"},
        "calibration_manual": {"display_name": "Calibration_Manual", "condition": "manual", "subset": "calibration"},
        "validation_manual": {"display_name": "Validation_Manual", "condition": "manual", "subset": "validation"},
        "validation_semi": {"display_name": "Validation_Semi", "condition": "semi", "subset": "validation"},
    },
    "metric_columns": [
        "iou_2d", "iou_3d", "depth_rmse", "delta_1",
        "boundary_rmse", "pointwise_rmse",
        "n_corners", "scope", "difficulty", "model_issue",
        "reliability_u", "reliability_u_ci_low", "reliability_u_ci_high"
    ],
    "group_by": ["condition", "subset"],
    "output_formats": ["csv", "json", "markdown"],
}


# === Core Functions (modular for plugin API) ===

def load_csv_with_metadata(csv_path: str, dataset_key: str, config: dict) -> Tuple[List[dict], dict]:
    """Load a quality CSV and attach dataset metadata.
    
    Args:
        csv_path: path to quality_report_*.csv
        dataset_key: key in config['datasets']
        config: full config dict with dataset metadata
    
    Returns:
        (rows, metadata) where rows are dicts with added 'dataset' field
    """
    rows = []
    dataset_meta = config["datasets"].get(dataset_key, {})
    
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV not found: {csv_path}")
    
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["dataset"] = dataset_meta.get("display_name", dataset_key)
            row["condition"] = dataset_meta.get("condition", "unknown")
            row["subset"] = dataset_meta.get("subset", "unknown")
            rows.append(row)
    
    metadata = {
        "dataset_key": dataset_key,
        "display_name": dataset_meta.get("display_name", dataset_key),
        "source_file": csv_path,
        "row_count": len(rows),
    }
    return rows, metadata


def merge_csv_files(csv_paths: Dict[str, str], config: dict) -> Tuple[List[dict], List[dict]]:
    """Load and merge multiple CSV files with dataset labels.
    
    Args:
        csv_paths: {dataset_key: file_path}
        config: configuration dict
    
    Returns:
        (all_rows, metadata_list)
    """
    all_rows = []
    metadata_list = []
    
    for dataset_key, csv_path in csv_paths.items():
        try:
            rows, meta = load_csv_with_metadata(csv_path, dataset_key, config)
            all_rows.extend(rows)
            metadata_list.append(meta)
            print(f"  Loaded {meta['row_count']} rows from {dataset_key} ({meta['display_name']})")
        except Exception as e:
            print(f"  ⚠️  Error loading {dataset_key} from {csv_path}: {e}")
    
    return all_rows, metadata_list


def compute_summary_stats(rows: List[dict], group_by: List[str], metric_cols: List[str]) -> Dict[str, dict]:
    """Compute per-group summary statistics.
    
    Args:
        rows: merged rows with dataset/condition/subset fields
        group_by: list of columns to group by (e.g., ['condition', 'subset'])
        metric_cols: numeric columns to summarize
    
    Returns:
        {group_key: {metric: {'mean': ..., 'std': ..., 'count': ...}}}
    """
    grouped = defaultdict(lambda: defaultdict(list))
    
    for row in rows:
        # Build group key
        key_parts = [row.get(col, "unknown") for col in group_by]
        group_key = ":".join(key_parts)
        
        # Aggregate metrics
        for metric in metric_cols:
            val = row.get(metric, "")
            if val and val != "":
                try:
                    grouped[group_key][metric].append(float(val))
                except (ValueError, TypeError):
                    pass
    
    # Compute statistics
    summary = {}
    for group_key, metrics in grouped.items():
        summary[group_key] = {}
        for metric, values in metrics.items():
            if values:
                summary[group_key][metric] = {
                    "mean": float(np.mean(values)),
                    "std": float(np.std(values)),
                    "median": float(np.median(values)),
                    "count": len(values),
                }
            else:
                summary[group_key][metric] = {"mean": None, "std": None, "median": None, "count": 0}
    
    return summary


def compute_cross_dataset_comparison(summary: dict, config: dict) -> dict:
    """Compare key metrics across conditions/subsets.
    
    Args:
        summary: output from compute_summary_stats
        config: configuration with group_by fields
    
    Returns:
        {comparison_name: {metric: {group_a: ..., group_b: ..., diff: ...}}}
    """
    comparisons = {}
    
    # Example: Manual_Test vs SemiAuto_Test on test subset
    manual_test_key = "manual:test"
    semi_test_key = "semi:test"
    
    if manual_test_key in summary and semi_test_key in summary:
        test_comp = {}
        for metric in ["iou_2d", "iou_3d", "depth_rmse", "boundary_rmse"]:
            m_val = summary[manual_test_key].get(metric, {}).get("mean")
            s_val = summary[semi_test_key].get(metric, {}).get("mean")
            if m_val is not None and s_val is not None:
                test_comp[metric] = {
                    "manual": m_val,
                    "semi": s_val,
                    "diff": s_val - m_val,
                }
        comparisons["Manual_Test_vs_SemiAuto_Test"] = test_comp
    
    # Add validation comparison if available
    manual_val_key = "manual:validation"
    semi_val_key = "semi:validation"
    if manual_val_key in summary and semi_val_key in summary:
        val_comp = {}
        for metric in ["iou_2d", "iou_3d", "depth_rmse"]:
            m_val = summary[manual_val_key].get(metric, {}).get("mean")
            s_val = summary[semi_val_key].get(metric, {}).get("mean")
            if m_val is not None and s_val is not None:
                val_comp[metric] = {
                    "manual": m_val,
                    "semi": s_val,
                    "diff": s_val - m_val,
                }
        comparisons["Validation_Manual_vs_Semi"] = val_comp
    
    return comparisons


def export_merged_csv(rows: List[dict], output_path: str, column_order: Optional[List[str]] = None):
    """Write merged rows to CSV with optional column ordering."""
    if not rows:
        print(f"⚠️  No rows to export to {output_path}")
        return
    
    # Determine columns
    if column_order:
        all_cols = ["dataset", "condition", "subset"] + column_order
        # Include any extra columns not in column_order
        extra_cols = [k for k in rows[0].keys() if k not in all_cols]
        all_cols.extend(extra_cols)
    else:
        # Use natural order from first row
        all_cols = ["dataset", "condition", "subset"] + [k for k in rows[0].keys() if k not in ["dataset", "condition", "subset"]]
    
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=all_cols, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"✅ Merged CSV written to {output_path} ({len(rows)} rows)")


def export_summary_json(summary: dict, comparisons: dict, metadata: List[dict], output_path: str):
    """Export summary statistics and comparisons as JSON."""
    payload = {
        "metadata": metadata,
        "summary_by_group": summary,
        "cross_dataset_comparisons": comparisons,
        "generated_at": datetime.now().isoformat(),
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"✅ Summary JSON written to {output_path}")


def export_summary_markdown(summary: dict, comparisons: dict, output_path: str):
    """Export summary as Markdown table for easy reading."""
    lines = ["# Quality Analysis Summary", "", "## Per-Dataset Statistics", ""]
    
    # Summary table
    lines.append("| Group | Metric | Mean | Std | Median | Count |")
    lines.append("|-------|--------|------|-----|--------|-------|")
    for group_key, metrics in summary.items():
        for metric, stats in metrics.items():
            if stats["count"] > 0:
                lines.append(
                    f"| {group_key} | {metric} | {stats['mean']:.4f} | {stats['std']:.4f} | "
                    f"{stats['median']:.4f} | {stats['count']} |"
                )
    
    lines.extend(["", "## Cross-Dataset Comparisons", ""])
    
    for comp_name, comp_data in comparisons.items():
        lines.append(f"### {comp_name}")
        lines.append("")
        lines.append("| Metric | Manual | Semi | Diff (Semi - Manual) |")
        lines.append("|--------|--------|------|----------------------|")
        for metric, vals in comp_data.items():
            lines.append(
                f"| {metric} | {vals['manual']:.4f} | {vals['semi']:.4f} | {vals['diff']:.4f} |"
            )
        lines.append("")
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"✅ Summary Markdown written to {output_path}")


# === CLI Entry Point ===

def main():
    parser = argparse.ArgumentParser(
        description="Aggregate quality analysis results from multiple Label Studio datasets"
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to JSON config file (optional; defaults to built-in schema)",
    )
    parser.add_argument(
        "--csv",
        type=str,
        nargs="+",
        required=True,
        help="Paths to quality_report CSV files (in order: main_manual main_semi calib_manual val_manual val_semi). "
             "Use dataset_key:path format for explicit mapping, e.g., main_manual:path/to/manual.csv",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="analysis_results",
        help="Directory to save aggregated outputs",
    )
    parser.add_argument(
        "--output-prefix",
        type=str,
        default="aggregate",
        help="Prefix for output filenames",
    )
    parser.add_argument(
        "--formats",
        nargs="+",
        choices=["csv", "json", "markdown"],
        default=["csv", "json", "markdown"],
        help="Output formats to generate",
    )
    
    args = parser.parse_args()
    
    # Load or use default config
    if args.config and os.path.exists(args.config):
        with open(args.config, "r", encoding="utf-8") as f:
            config = json.load(f)
        print(f"Loaded config from {args.config}")
    else:
        config = DEFAULT_CONFIG
        print("Using default configuration")
    
    # Parse CSV paths
    csv_paths = {}
    dataset_keys = list(config["datasets"].keys())
    
    for i, csv_arg in enumerate(args.csv):
        if ":" in csv_arg:
            # Explicit mapping: dataset_key:path
            key, path = csv_arg.split(":", 1)
            csv_paths[key] = path
        else:
            # Positional mapping
            if i < len(dataset_keys):
                csv_paths[dataset_keys[i]] = csv_arg
            else:
                print(f"⚠️  Ignoring extra CSV argument: {csv_arg}")
    
    print(f"\nMerging {len(csv_paths)} CSV files...")
    
    # Load and merge
    all_rows, metadata_list = merge_csv_files(csv_paths, config)
    
    if not all_rows:
        print("❌ No data loaded. Exiting.")
        return
    
    print(f"\n✅ Total rows merged: {len(all_rows)}")
    
    # Compute summaries
    print("\nComputing summary statistics...")
    summary = compute_summary_stats(
        all_rows,
        group_by=config.get("group_by", ["condition", "subset"]),
        metric_cols=config.get("metric_columns", []),
    )
    
    print("\nComputing cross-dataset comparisons...")
    comparisons = compute_cross_dataset_comparison(summary, config)
    
    # Prepare output directory
    os.makedirs(args.output_dir, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    base_name = f"{args.output_prefix}_{date_str}"
    
    # Export in requested formats
    if "csv" in args.formats:
        csv_out = os.path.join(args.output_dir, f"{base_name}.csv")
        export_merged_csv(all_rows, csv_out, column_order=config.get("metric_columns"))
    
    if "json" in args.formats:
        json_out = os.path.join(args.output_dir, f"{base_name}_summary.json")
        export_summary_json(summary, comparisons, metadata_list, json_out)
    
    if "markdown" in args.formats:
        md_out = os.path.join(args.output_dir, f"{base_name}_summary.md")
        export_summary_markdown(summary, comparisons, md_out)
    
    print("\n🎉 Aggregation complete!")


if __name__ == "__main__":
    main()
