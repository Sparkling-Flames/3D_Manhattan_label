"""Run the reviewed materializer with bounded deterministic resampling.

The runner also applies two final review corrections without changing raw data:
- explicit `normal`, `trivial` and `low_quality` choices remain in their
  respective Scope/Difficulty groups rather than an undifferentiated catch-all;
- non-worker rows are removed from the excluded-worker peer-evidence export.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

from tools.paper_a_manhattan.full_uncertainty import full_uncertainty_reviewed as reviewed
from tools.paper_a_manhattan.full_uncertainty import materialize_full_uncertainty_data_mining_v2 as materializer


_ORIGINAL_CHOICE_GROUP = reviewed.choice_group
_ORIGINAL_VIEWPOINTS = materializer.reviewed_worker_viewpoints
_ORIGINAL_TIME_ANALYSIS = materializer.time_analysis


def _reviewed_choice_group(from_name: str, choice: str) -> tuple[str, str, str]:
    source = str(from_name or "").strip().lower().replace("-", "_")
    token = str(choice or "").strip().lower().replace("-", "_")
    if source == "scope":
        if token == "normal":
            return "scope", "in_scope", "范围内/正常"
        if token == "oos_geometry":
            return "scope", "oos_geometry", "范围外：几何假设不适用"
        if token == "oos_insufficient":
            return "scope", "oos_insufficient_evidence", "几何证据不足"
    if source == "difficulty":
        if token == "trivial":
            return "difficulty", "trivial", "无显著难点"
        if token == "low_quality":
            return "difficulty", "low_image_quality", "低图像质量"
    return _ORIGINAL_CHOICE_GROUP(from_name, choice)


def _clean_viewpoints():
    memberships, workers, pairs, tests, excluded = _ORIGINAL_VIEWPOINTS()
    if not excluded.empty and "worker_id" in excluded:
        worker = excluded["worker_id"].astype(str).str.strip()
        excluded = excluded[excluded["worker_id"].notna() & worker.ne("") & worker.ne("nan")].reset_index(drop=True)
    return memberships, workers, pairs, tests, excluded


def _clean_time_analysis(unified):
    time_frame, summary, paired, relation, outliers_models = _ORIGINAL_TIME_ANALYSIS(unified)
    if not outliers_models.empty and {"time_metric", "term"}.issubset(outliers_models.columns):
        term = outliers_models["term"].astype(str)
        unsupported_interaction = (
            outliers_models["time_metric"].eq("model")
            & term.str.contains(r"C\(stage\)\[T\.(C2-A-RP-B1|C2-A-RP-B2|C2-B)\]:C\(condition\)\[T\.semi\]", regex=True, na=False)
        )
        outliers_models = outliers_models[~unsupported_interaction].reset_index(drop=True)
    return time_frame, summary, paired, relation, outliers_models


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=materializer.DEFAULT_OUT)
    args = parser.parse_args()

    reviewed.choice_group = _reviewed_choice_group
    reviewed.worker_viewpoint_stability.__kwdefaults__["permutations"] = 2000
    reviewed._permutation_variance.__kwdefaults__["permutations"] = 2000
    reviewed._split_half_reliability.__kwdefaults__["repetitions"] = 1000
    materializer.reviewed_worker_viewpoints = _clean_viewpoints
    materializer.time_analysis = _clean_time_analysis

    materializer.materialize(args.output_dir.resolve())


if __name__ == "__main__":
    main()
