#!/usr/bin/env python3
"""Stage-aware analysis entrypoint.

This script implements the "Dev B" responsibility:
1. Ingests A-line registry (merged_all_v0.csv) as the runtime truth.
2. Ingests C-line manifest (trap_manifest, anchor_index) as the static truth.
3. Supports a replaceable "selection manifest" to override old split files.
4. Generates stage-aware analysis artifacts:
   - Worker x Scene matrix
   - Worker profiles (Quality vs Time)
   - T/I/M stratified metrics
"""

import argparse
import pandas as pd
from pathlib import Path
from typing import Optional, Dict, List, Tuple
import matplotlib.pyplot as plt
import seaborn as sns

# Default paths
DEFAULT_REGISTRY_PATH = Path("analysis_results/registry_20260308/merged_all_v0.csv")
DEFAULT_ANCHOR_INDEX = Path("analysis_results/c_manifests_20260310/manual_anchor_bank_index_v1.csv")
DEFAULT_TRAP_MANIFEST = Path("analysis_results/c_manifests_20260310/trap_manifest_draft_v1.csv")
DEFAULT_OUTPUT_DIR = Path("analysis_results/stage_aware_analysis")

def parse_args():
    parser = argparse.ArgumentParser(description="Stage-aware analysis for 3D Manhattan Label")
    
    # Input: Registry (A-line)
    parser.add_argument(
        "--registry", 
        type=Path, 
        default=DEFAULT_REGISTRY_PATH,
        help="Path to the merged registry CSV (runtime truth)"
    )
    
    # Input: Manifests (C-line)
    parser.add_argument(
        "--anchor-index",
        type=Path,
        default=DEFAULT_ANCHOR_INDEX,
        help="Path to manual anchor bank index"
    )
    parser.add_argument(
        "--trap-manifest",
        type=Path,
        default=DEFAULT_TRAP_MANIFEST,
        help="Path to trap manifest"
    )
    
    # Input: Selection Manifest (Optional override)
    parser.add_argument(
        "--selection-manifest",
        type=Path,
        default=None,
        help="Path to a selection manifest to define specific task subsets (overrides default logic)"
    )

    # Input: Quality Report (Optional, for IOU)
    parser.add_argument(
        "--quality-report",
        type=Path,
        default=Path("analysis_results/rerun_20260308/quality_report_formal_20260308.csv"),
        help="Path to the quality report CSV containing IOU data"
    )

    # Output
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory to save analysis artifacts"
    )
    
    return parser.parse_args()

def load_data(registry_path: Path, anchor_path: Path, trap_path: Path, quality_path: Optional[Path] = None) -> Dict[str, pd.DataFrame]:
    """Loads all necessary dataframes."""
    dfs = {}
    
    if registry_path.exists():
        print(f"Loading registry from {registry_path}...")
        dfs["registry"] = pd.read_csv(registry_path)
    else:
        raise FileNotFoundError(f"Registry not found at {registry_path}")
        
    if anchor_path.exists():
        print(f"Loading anchor index from {anchor_path}...")
        dfs["anchor"] = pd.read_csv(anchor_path)
    else:
        print(f"Warning: Anchor index not found at {anchor_path}, proceeding without it.")
        dfs["anchor"] = pd.DataFrame()

    if trap_path.exists():
        print(f"Loading trap manifest from {trap_path}...")
        dfs["trap"] = pd.read_csv(trap_path)
    else:
        print(f"Warning: Trap manifest not found at {trap_path}, proceeding without it.")
        dfs["trap"] = pd.DataFrame()
    
    if quality_path and quality_path.exists():
        print(f"Loading quality report from {quality_path}...")
        dfs["quality"] = pd.read_csv(quality_path)
    elif quality_path:
        print(f"Warning: Quality report not found at {quality_path}, IOU data may be missing.")
        
    return dfs

def analyze_worker_scene_matrix(registry_df: pd.DataFrame, quality_df: Optional[pd.DataFrame], output_dir: Path):
    """Generates Worker x Scene coverage and quality matrix."""
    print("Generating Worker x Scene matrix...")
    
    df = registry_df.copy()
    rename_map = {
        "active_time_value": "active_time",
        "runtime_condition": "condition"
    }
    df.rename(columns=rename_map, inplace=True)
    
    # Try to merge IOU from quality_df if not present
    if "iou" not in df.columns and quality_df is not None:
        print("Merging IOU from quality report...")
        # Join on task_id and annotator_id
        # Quality report has task_id, annotator_id, iou
        quality_subset = quality_df[["task_id", "annotator_id", "iou"]].copy()
        
        # Ensure types match for merge keys
        df["task_id"] = df["task_id"].astype(str)
        df["annotator_id"] = df["annotator_id"].astype(str)
        quality_subset["task_id"] = quality_subset["task_id"].astype(str)
        quality_subset["annotator_id"] = quality_subset["annotator_id"].astype(str)
        
        df = pd.merge(df, quality_subset, on=["task_id", "annotator_id"], how="left")
        print(f"Merged IOU data. Non-null IOU count: {df['iou'].count()}")

    if "iou" not in df.columns:
        print("Warning: 'iou' column missing in registry. Attempting to load from quality report...")
        # Try to find quality report in the same directory as registry
        # Assuming quality report naming convention or passing it as arg would be better, 
        # but for now let's check if we can simulate or skip.
        # For this skeleton, we will skip IOU-dependent parts if missing, but we can still do coverage.
        
        # Construct coverage matrix (count) instead of IOU if IOU missing
        print("Switching to Coverage Matrix (Count) due to missing IOU.")
        matrix_coverage = df.pivot_table(index="annotator_id", columns="task_id", values="annotation_id", aggfunc="count")
        
        # Save raw matrix
        output_dir.mkdir(parents=True, exist_ok=True)
        matrix_path = output_dir / "worker_scene_coverage_matrix.csv"
        matrix_coverage.to_csv(matrix_path)
        print(f"Saved Worker x Scene Coverage matrix to {matrix_path}")
        
        # Heatmap
        try:
            plt.figure(figsize=(12, 8))
            sns.heatmap(matrix_coverage, cmap="Blues", cbar_kws={'label': 'Count'}, vmin=0, vmax=1)
            plt.title("Worker x Scene Coverage Matrix")
            plt.xlabel("Task ID")
            plt.ylabel("Annotator ID")
            plt.tight_layout()
            heatmap_path = output_dir / "worker_scene_coverage_heatmap.png"
            plt.savefig(heatmap_path)
            plt.close()
            print(f"Saved Coverage Heatmap to {heatmap_path}")
        except Exception as e:
            print(f"Warning: Could not generate heatmap: {e}")
            
        return

    # Basic pivot: Annotator vs Task (IOU)
    # We aggregate by mean if there are duplicates (though registry should be unique per task-annotator ideally)
    matrix_iou = df.pivot_table(index="annotator_id", columns="task_id", values="iou", aggfunc="mean")
    
    # Save raw matrix
    output_dir.mkdir(parents=True, exist_ok=True)
    matrix_path = output_dir / "worker_scene_iou_matrix.csv"
    matrix_iou.to_csv(matrix_path)
    print(f"Saved Worker x Scene IOU matrix to {matrix_path}")
    
    # Calculate sparsity / coverage
    n_workers, n_tasks = matrix_iou.shape
    filled = matrix_iou.notna().sum().sum()
    total_cells = n_workers * n_tasks
    sparsity = 1.0 - (filled / total_cells) if total_cells > 0 else 0.0
    print(f"Matrix stats: {n_workers} workers x {n_tasks} tasks. Sparsity: {sparsity:.2%}")

    # Generate Heatmap
    try:
        plt.figure(figsize=(12, 8))
        sns.heatmap(matrix_iou, cmap="viridis", cbar_kws={'label': 'IOU'}, vmin=0, vmax=1)
        plt.title("Worker x Scene IOU Matrix")
        plt.xlabel("Task ID")
        plt.ylabel("Annotator ID")
        plt.tight_layout()
        heatmap_path = output_dir / "worker_scene_iou_heatmap.png"
        plt.savefig(heatmap_path)
        plt.close()
        print(f"Saved Heatmap to {heatmap_path}")
    except Exception as e:
        print(f"Warning: Could not generate heatmap: {e}")

def analyze_worker_profiles(registry_df: pd.DataFrame, quality_df: Optional[pd.DataFrame], output_dir: Path):
    """Generates Worker Profile (Active Time vs Quality)."""
    print("Generating Worker Profiles...")
    
    df = registry_df.copy()
    rename_map = {
        "active_time_value": "active_time",
        "runtime_condition": "condition"
    }
    df.rename(columns=rename_map, inplace=True)
    
    # Try to merge IOU from quality_df if not present
    if "iou" not in df.columns and quality_df is not None:
        print("Merging IOU from quality report for profiles...")
        # Join on task_id and annotator_id
        # Quality report has task_id, annotator_id, iou
        quality_subset = quality_df[["task_id", "annotator_id", "iou"]].copy()
        
        # Ensure types match for merge keys
        df["task_id"] = df["task_id"].astype(str)
        df["annotator_id"] = df["annotator_id"].astype(str)
        quality_subset["task_id"] = quality_subset["task_id"].astype(str)
        quality_subset["annotator_id"] = quality_subset["annotator_id"].astype(str)
        
        df = pd.merge(df, quality_subset, on=["task_id", "annotator_id"], how="left")

    # Check for columns
    cols = ["annotator_id", "active_time"]
    available_cols = [c for c in cols if c in df.columns]
    
    if len(available_cols) < 2:
        print(f"Warning: Missing essential columns for profile (need {cols}), found {available_cols}")
        return

    # IOU handling: if available, include quality metrics. If not, fallback to activity-only profile.
    has_iou = "iou" in df.columns
    
    agg_dict = {
        "active_time": ["mean", "std"],
        "task_id": "count" # Using task_id count as task_count
    }
    
    if has_iou:
        agg_dict["iou"] = ["mean", "std"]
    
    # Group by Annotator
    profile = df.groupby("annotator_id").agg(agg_dict).reset_index()
    
    # Flatten columns
    new_cols = ["annotator_id"]
    new_cols.append("mean_active_time")
    new_cols.append("std_active_time")
    new_cols.append("task_count")
    
    if has_iou:
        new_cols.append("mean_iou")
        new_cols.append("std_iou")
        
    profile.columns = new_cols
    
    # Save Profile Data
    profile_path = output_dir / "worker_profiles.csv"
    profile.to_csv(profile_path, index=False)
    print(f"Saved Worker Profiles to {profile_path}")
    
    # Generate Scatter Plot: Time vs Quality (if IOU exists)
    if has_iou:
        try:
            plt.figure(figsize=(10, 6))
            sns.scatterplot(
                data=profile, 
                x="mean_active_time", 
                y="mean_iou", 
                size="task_count", 
                sizes=(50, 500),
                alpha=0.7
            )
            
            # Add labels
            for i, row in profile.iterrows():
                plt.text(
                    row["mean_active_time"], 
                    row["mean_iou"] + 0.01, 
                    str(row["annotator_id"]), 
                    fontsize=9,
                    ha='center'
                )
                
            plt.title("Worker Profile: Active Time vs Mean IOU")
            plt.xlabel("Mean Active Time (s)")
            plt.ylabel("Mean IOU")
            plt.grid(True, linestyle="--", alpha=0.5)
            plt.tight_layout()
            
            plot_path = output_dir / "worker_profile_scatter.png"
            plt.savefig(plot_path)
            plt.close()
            print(f"Saved Profile Scatter Plot to {plot_path}")
        except Exception as e:
            print(f"Warning: Could not generate profile plot: {e}")
    else:
        # Plot Active Time Distribution per worker if IOU missing
        try:
            plt.figure(figsize=(10, 6))
            sns.barplot(data=profile, x="annotator_id", y="mean_active_time", palette="viridis")
            plt.title("Worker Profile: Mean Active Time")
            plt.xlabel("Annotator ID")
            plt.ylabel("Mean Active Time (s)")
            plt.grid(True, axis='y', linestyle="--", alpha=0.5)
            plt.tight_layout()
            
            plot_path = output_dir / "worker_profile_time_bar.png"
            plt.savefig(plot_path)
            plt.close()
            print(f"Saved Profile Time Bar Plot to {plot_path}")
        except Exception as e:
             print(f"Warning: Could not generate profile bar plot: {e}")


def analyze_process_evidence(registry_df: pd.DataFrame, output_dir: Path):
    """Analyzes Type 4 Process Evidence (Active Time distributions per scope)."""
    print("Generating Process Evidence Analysis...")
    
    # Check if necessary columns exist (using registry names)
    if "compat_scope" not in registry_df.columns or "active_time_value" not in registry_df.columns:
        print("Warning: Missing 'compat_scope' or 'active_time_value' columns for process evidence.")
        return

    df = registry_df.copy()
    rename_map = {
        "active_time_value": "active_time",
        "compat_scope": "scope"
    }
    df.rename(columns=rename_map, inplace=True)

    # Filter out extremely short or long times (simple outlier removal)
    df = df[(df["active_time"] > 10) & (df["active_time"] < 3600)].copy()
    
    # Active Time by Scope Boxplot
    try:
        plt.figure(figsize=(10, 6))
        sns.boxplot(data=df, x="scope", y="active_time", showfliers=False)
        plt.title("Active Time Distribution by Scope (Process Evidence)")
        plt.xlabel("Scope")
        plt.ylabel("Active Time (s)")
        plt.grid(True, axis='y', linestyle="--", alpha=0.5)
        
        plot_path = output_dir / "process_evidence_time_by_scope.png"
        plt.savefig(plot_path)
        plt.close()
        print(f"Saved Process Evidence Plot to {plot_path}")
        
        # Save summary stats
        summary = df.groupby("scope")["active_time"].describe()
        summary_path = output_dir / "process_evidence_time_stats.csv"
        summary.to_csv(summary_path)
        print(f"Saved Process Evidence Stats to {summary_path}")
        
    except Exception as e:
        print(f"Warning: Could not generate process evidence plot: {e}")


def analyze_stratified_metrics(registry_df: pd.DataFrame, quality_df: Optional[pd.DataFrame], output_dir: Path):
    """Generates T/I/M Stratified Metrics."""
    print("Generating T/I/M Stratified Analysis...")
    
    df = registry_df.copy()
    rename_map = {
        "active_time_value": "active_time",
        "runtime_condition": "condition",
        "dataset_group": "group"
    }
    df.rename(columns=rename_map, inplace=True)

    # Merge IOU
    if "iou" not in df.columns and quality_df is not None:
        quality_subset = quality_df[["task_id", "annotator_id", "iou"]].copy()
        df["task_id"] = df["task_id"].astype(str)
        df["annotator_id"] = df["annotator_id"].astype(str)
        quality_subset["task_id"] = quality_subset["task_id"].astype(str)
        quality_subset["annotator_id"] = quality_subset["annotator_id"].astype(str)
        df = pd.merge(df, quality_subset, on=["task_id", "annotator_id"], how="left")

    # Define Stratification Logic (Mapping group/condition to T/I/M)
    # T (Test): dataset_group contains 'Test' or 'test'
    # I (Internal/Calibration): dataset_group contains 'Calibration' or 'calibration'
    # M (Main/Validation): dataset_group contains 'Validation' or 'validation'
    # This is a heuristic mapping based on common naming conventions.
    
    def classify_strata(row):
        group = str(row.get("group", "")).lower()
        if "test" in group:
            return "Test (RQ1)"
        elif "calibration" in group:
            return "Internal (RQ2)"
        elif "validation" in group:
            return "Main (RQ3)"
        else:
            return "Other"

    df["strata"] = df.apply(classify_strata, axis=1)
    
    # Calculate Metrics per Strata
    metrics = {
        "task_id": "count",
        "active_time": "mean"
    }
    # Note: agg function can accept list of strings for multiple aggregations
    if "iou" in df.columns:
        # Use type: ignore to bypass linter error for valid pandas agg syntax
        metrics["iou"] = ["mean", "std"] # type: ignore
        
    stratified = df.groupby("strata").agg(metrics).reset_index()
    
    # Flatten columns
    new_cols = ["strata", "count", "mean_active_time"]
    if "iou" in df.columns:
        new_cols.extend(["mean_iou", "std_iou"])
    stratified.columns = new_cols
    
    # Save Stratified Data
    stratified_path = output_dir / "stratified_metrics.csv"
    stratified.to_csv(stratified_path, index=False)
    print(f"Saved Stratified Metrics to {stratified_path}")
    
    # Visualization
    if "iou" in df.columns:
        try:
            plt.figure(figsize=(8, 6))
            sns.barplot(data=df, x="strata", y="iou", errorbar="sd", palette="Set2")
            plt.title("IOU Performance by Strata (T/I/M)")
            plt.ylabel("IOU")
            plt.grid(True, axis='y', linestyle="--", alpha=0.5)
            
            plot_path = output_dir / "stratified_iou_bar.png"
            plt.savefig(plot_path)
            plt.close()
            print(f"Saved Stratified IOU Plot to {plot_path}")
        except Exception as e:
            print(f"Warning: Could not generate stratified plot: {e}")


def main():
    args = parse_args()
    
    # Ensure output directory exists
    args.output_dir.mkdir(parents=True, exist_ok=True)

    try:
        dfs = load_data(args.registry, args.anchor_index, args.trap_manifest, args.quality_report)
        
        # 1. Worker x Scene Matrix
        if "registry" in dfs and not dfs["registry"].empty:
            quality_df = dfs.get("quality")
            analyze_worker_scene_matrix(dfs["registry"], quality_df, args.output_dir)
            analyze_worker_profiles(dfs["registry"], quality_df, args.output_dir)
            analyze_process_evidence(dfs["registry"], args.output_dir)
            analyze_stratified_metrics(dfs["registry"], quality_df, args.output_dir)
        else:
            print("Registry is empty or not loaded.")
        
        # Future steps:
        # 2. Worker Profiles
        # 3. T/I/M Stratification
        
    except Exception as e:
        print(f"Error during analysis: {e}")
        # import traceback
        # traceback.print_exc()
        exit(1)

if __name__ == "__main__":
    main()
