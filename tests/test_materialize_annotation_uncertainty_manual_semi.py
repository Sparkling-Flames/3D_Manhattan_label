from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

from tools.thesis_main.analysis.materialize_annotation_uncertainty_manual_semi import (
    BAD_TASK_ID,
    CORRECTED_TASK_ID,
    materialize,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_v2_materialization_contract_and_determinism(tmp_path: Path) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    materialize(first, bootstrap_replicates=200)
    materialize(second, bootstrap_replicates=200)

    first_hashes = {path.name: _sha(path) for path in first.iterdir() if path.is_file()}
    second_hashes = {path.name: _sha(path) for path in second.iterdir() if path.is_file()}
    assert first_hashes == second_hashes

    inputs = pd.read_csv(first / "INPUT_MANIFEST.csv")
    subsets = pd.read_csv(first / "TASK_SUBSET_RECLUSTERING.csv")
    tasks = pd.read_csv(first / "TASK_METRICS.csv")
    summary = pd.read_csv(first / "THRESHOLD_ROBUSTNESS.csv")
    assignment = pd.read_csv(first / "ASSIGNMENT_TASK_AUDIT.csv")
    initialization = pd.read_csv(first / "SEMI_INITIALIZATION_AUDIT.csv")
    difficulty = pd.read_csv(first / "DIFFICULTY_PROXY_COVERAGE.csv")
    time = pd.read_csv(first / "FROZEN_TIME_AUXILIARY.csv")
    quality = pd.read_csv(first / "QUALITY_AUXILIARY_SUMMARY.csv")
    legacy = pd.read_csv(first / "LEGACY_FIXED_PARTITION_SUMMARY.csv").set_index("metric")

    assert inputs["status"].eq("pass").all()
    assert len(subsets) == 411
    assert len(tasks) == 66
    assert len(summary) == 18
    assert set(summary["threshold"]) == {0.93, 0.95, 0.97}
    assert tasks["base_task_id"].nunique() == 22
    assert tasks["building_id"].nunique() == 9
    q95 = tasks[tasks["threshold"].eq(0.95)]
    assert (q95["common_k"] if "common_k" in q95 else q95["manual_subset_count"].map(lambda count: 3 if count == 10 else 4)).value_counts().to_dict() == {4: 21, 3: 1}
    assert CORRECTED_TASK_ID in set(tasks["base_task_id"])
    assert BAD_TASK_ID not in set(tasks["base_task_id"])
    assert assignment["realized_overlap_count"].sum() == 0
    assert assignment["planned_overlap_count"].sum() == 0
    assert len(initialization) == 22 and initialization["status"].eq("pass").all()
    assert difficulty["confirmatory_status"].eq("not_evaluable").all()
    assert difficulty["frozen_preassignment_n_ready"].eq(0).all()
    assert not any("high_manual" in column for column in tasks.columns)
    assert time.loc[0, "lead_time_used"] in (False, np.bool_(False))
    assert time.loc[0, "status"] == "not_evaluable"
    assert quality.loc[0, "status"] == "not_evaluable_no_semi_gt_primary_rows"
    assert summary.loc[summary["threshold"].eq(0.95), "n_buildings"].eq(9).all()

    expected = {
        "shannon_entropy": (0.0328664399, 0.8003501892089844),
        "gini_simpson": (0.0208333333, 0.7943534851074219),
        "largest_mode_share": (-0.0068181818, 0.9446487426757812),
        "supported_multimodality": (-0.0363636364, 0.5),
        "mode_count": (0.0727272727, 0.80247),
    }
    for metric, (mean, p_value) in expected.items():
        assert np.isclose(legacy.loc[metric, "mean_difference"], mean, atol=1e-10)
        assert np.isclose(legacy.loc[metric, "task_exact_sign_flip_p"], p_value, atol=5e-6)

    all_text = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in first.iterdir() if path.suffix in {".csv", ".json", ".md"})
    assert BAD_TASK_ID not in all_text
    assert "high_manual_ambiguity" not in all_text
    assert "未检出总体不确定性降低" in (first / "ANNOTATION_UNCERTAINTY_MANUAL_SEMI_REPORT_ZH.md").read_text(encoding="utf-8")
