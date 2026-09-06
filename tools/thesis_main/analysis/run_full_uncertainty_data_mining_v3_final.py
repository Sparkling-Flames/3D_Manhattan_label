"""Final reviewed runner for the comprehensive v3 analysis.

This wrapper corrects the model-issue denominator: only choices emitted by the
``model_issue`` control can count as an explicit proposal problem.  Difficulty,
scope and other tags are never recoded as model problems merely because they are
not ``acceptable``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from tools.thesis_main.analysis import materialize_full_uncertainty_data_mining_v3 as base


def fixed_aggregate_worker_tags(meta_long: pd.DataFrame) -> pd.DataFrame:
    if meta_long.empty:
        return pd.DataFrame(columns=["stage", "condition", "base_task_id", "worker_id"])
    frame = meta_long.copy()
    frame["stage"] = frame["stage"].map(base.normalise_stage)
    frame["condition"] = frame["condition"].map(base.normalise_condition)
    frame["worker_id"] = frame["worker_id"].map(base.worker_id)
    frame["choice_code"] = frame["choice_code"].map(base.clean)
    frame["meta_group"] = frame["meta_group"].map(base.clean)
    frame["is_explicit_model_problem"] = frame["meta_group"].eq("model_issue") & ~frame["choice_code"].isin({"", "acceptable"})
    grouped = frame.groupby(["stage", "condition", "base_task_id", "worker_id"], dropna=False).agg(
        tag_codes=("choice_code", lambda values: ";".join(sorted(set(filter(None, map(base.clean, values)))))),
        tag_labels_zh=("choice_label_zh", lambda values: ";".join(sorted(set(filter(None, map(base.clean, values)))))),
        acceptable_tag=("choice_code", lambda values: any(base.clean(value) == "acceptable" for value in values)),
        trivial_tag=("choice_code", lambda values: any(base.clean(value) == "trivial" for value in values)),
        in_scope_tag=("choice_code", lambda values: any(base.clean(value) == "in_scope" for value in values)),
        model_issue_tag=("meta_group", lambda values: any(base.clean(value) == "model_issue" for value in values)),
        explicit_model_problem_tag=("is_explicit_model_problem", "max"),
    ).reset_index()
    return grouped


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def finalise_package(out: Path, validation: dict) -> None:
    package = out / "Paper_A_完整数据整理报告与全部分析结果_20260821_v3.zip"
    if package.exists():
        package.unlink()
    manifest = base.output_manifest(out)
    base.write_csv(out / "OUTPUT_MANIFEST.csv", manifest)
    base.create_zip(out, package, exclude={package})
    with zipfile.ZipFile(package, "r") as archive:
        assert archive.testzip() is None
        names = set(archive.namelist())
        required = {
            "FULL_UNCERTAINTY_DATA_REPORT_ZH_V3.md",
            "Paper_A_完整数据整理与不确定性分析报告_20260821_v3.docx",
            "Paper_A_完整数据整理与分析工作簿_20260821_v3.xlsx",
            "SEMI_25_CONVERGENCE_EXPANSION_ALL_IMAGES.csv",
            "CROWD_GT_101_GEOMETRIC_CAUSE_AUDIT.csv",
            "DUAL_ANNOTATOR_GEOMETRY_SENSITIVITY_ALL.csv",
            "TAG_BEHAVIOR_ALL_CASES.csv",
            "ALL_RECORDS_WITH_ORTHOGONAL_FLAGS.csv",
            "ALL_IMAGE_INSTANCE_INDEX.csv",
        }
        missing = sorted(required - names)
        assert not missing, missing
    (out / "V3_PACKAGE_SHA256.txt").write_text(sha256(package) + "  " + package.name + "\n", encoding="utf-8")
    validation["v3_package_zip_size_bytes"] = package.stat().st_size
    validation["v3_package_sha256"] = sha256(package)
    validation["final_runner"] = "run_full_uncertainty_data_mining_v3_final.py"
    base.write_json(out / "VALIDATION_SUMMARY.json", validation)
    base.write_csv(out / "OUTPUT_MANIFEST.csv", base.output_manifest(out))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=base.DEFAULT_OUTPUT)
    args = parser.parse_args()
    base.aggregate_worker_tags = fixed_aggregate_worker_tags
    validation = base.materialize(args.output_dir.resolve())
    assert validation["paired_manual_semi_task_count"] == 25, validation
    assert validation["crowd_gt_task_condition_count"] == 101, validation
    assert validation["dual_annotator_task_count"] == 54, validation
    finalise_package(args.output_dir.resolve(), validation)
    print(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
