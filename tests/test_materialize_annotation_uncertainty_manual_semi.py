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


def test_v3_materialization_contract_and_determinism(tmp_path: Path) -> None:
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
    time_tasks = pd.read_csv(first / "ACTIVE_TIME_TASK_METRICS.csv")
    time_rows = pd.read_csv(first / "ACTIVE_TIME_TASK_WORKER.csv")
    quality = pd.read_csv(first / "QUALITY_AUXILIARY_SUMMARY.csv")
    quality_contexts = pd.read_csv(first / "QUALITY_DATA_MINING_CONTEXTS.csv")
    task_classification = pd.read_csv(first / "TASK_INCLUSION_CLASSIFICATION.csv")
    row_classification = pd.read_csv(first / "ROW_INCLUSION_CLASSIFICATION.csv")
    worker_coverage = pd.read_csv(first / "WORKER_COVERAGE.csv")
    exclusion_reasons = pd.read_csv(first / "EXCLUSION_REASON_AUDIT.csv")
    excluded_tasks = pd.read_csv(first / "EXCLUDED_TASK_UNCERTAINTY.csv")
    excluded_context_impact = pd.read_csv(first / "EXCLUDED_CONTEXT_IMPACT.csv")
    manual_catalog = pd.read_csv(first / "MANUAL_TASK_UNCERTAINTY_CATALOG.csv")
    population = pd.read_csv(first / "POPULATION_SENSITIVITY.csv")
    legacy = pd.read_csv(first / "LEGACY_FIXED_PARTITION_SUMMARY.csv").set_index("metric")

    assert inputs["status"].eq("pass").all()
    assert len(subsets) == 411
    assert len(tasks) == 66
    assert len(summary) == 21
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
    assert inputs.loc[inputs["role"].eq("preassignment_feature_manifest"), "path"].str.contains("c1_preannotation_task_features_manifest").all()
    assert not any("high_manual" in column for column in tasks.columns)
    assert time.loc[0, "lead_time_used"] in (False, np.bool_(False))
    assert time.loc[0, "status"] == "auxiliary_frozen_active_time"
    assert time.loc[0, "task_count"] == 22
    assert time.loc[0, "eligible_context_count"] == 184
    assert len(time_tasks) == 87 and len(time_rows) == 780
    assert time_rows["task_worker_time_analysis_eligible"].sum() == 701
    assert quality.loc[0, "status"] == "auxiliary_condition_specific_eligibility"
    assert quality.loc[0, "n_tasks"] == 22
    assert np.isclose(quality.loc[0, "mean_difference"], 0.05577422569407447)
    assert np.isclose(quality.loc[0, "building_exact_sign_flip_p"], 0.015625)
    assert len(quality_contexts) == 780
    assert len(quality_contexts[quality_contexts["worker_id"].astype(str).eq("14")]) == 32
    assert summary.loc[summary["threshold"].eq(0.95), "n_buildings"].eq(9).all()

    assert len(task_classification) == 87
    assert task_classification["has_semi_candidate"].sum() == 25
    assert task_classification["in_primary_entropy_sample"].sum() == 22
    assert task_classification["task_final_scope"].eq("oos").sum() == 8
    assert len(row_classification) == 780 and row_classification["worker_id"].nunique() == 23
    assert row_classification["secondary_uncertainty_eligible"].sum() > 0
    assert row_classification["primary_exclusion_class_definition"].eq("mutually_exclusive_analysis_priority_not_complete_reason_set").all()
    assert row_classification.loc[row_classification["worker_id"].astype(str).eq("14"), "secondary_exclusion_flags"].str.contains("worker_process:administratively_excluded_worker").all()
    assert len(worker_coverage) == 23
    assert worker_coverage["excluded_context_count"].sum() > 0
    assert excluded_tasks["base_task_id"].nunique() == 8
    assert excluded_tasks["has_semi_candidate"].sum() == 9
    assert set(excluded_tasks["threshold"]) == {0.93, 0.95, 0.97}
    assert len(manual_catalog) == 261 and manual_catalog["base_task_id"].nunique() == 87
    assert excluded_context_impact["base_task_id"].nunique() == 25
    assert (excluded_context_impact["excluded_context_added_n"] > 0).any()

    q95_population = population[
        population["threshold"].eq(0.95) & population["metric"].eq("shannon_entropy")
    ].set_index("population")
    assert set(q95_population.index) == {
        "formal_primary",
        "formal_plus_oos_tasks",
        "all_canonical_in_scope",
        "all_canonical_planned",
    }
    assert q95_population.loc["formal_primary", "n_tasks"] == 22
    assert q95_population.loc["formal_plus_oos_tasks", "n_tasks"] == 25
    assert np.isclose(q95_population.loc["formal_plus_oos_tasks", "mean_difference"], 0.02123009296316823)
    assert q95_population.loc["all_canonical_planned", "n_tasks"] == 25
    assert q95_population.loc["all_canonical_planned", "n_buildings"] == 9
    assert np.isclose(q95_population.loc["all_canonical_planned", "mean_difference"], -0.010005349170248805)
    assert q95_population.loc["formal_primary", "inference_role"] == "protocol_reference_only"
    assert q95_population.loc["all_canonical_planned", "inference_role"] == "primary_data_mining_inclusive_descriptive"
    q97_all = population[
        population["population"].eq("all_canonical_planned")
        & population["threshold"].eq(0.97)
        & population["metric"].eq("shannon_entropy")
    ].iloc[0]
    assert q97_all["n_tasks"] == 24
    w14 = worker_coverage[worker_coverage["worker_id"].astype(str).eq("14")].iloc[0]
    assert w14["all_context_count"] == 32
    assert w14["secondary_uncertainty_context_count"] == 31
    assert w14["administratively_excluded_context_count"] == 32
    reason_index = exclusion_reasons.set_index(["reason_dimension", "reason_value"])
    assert reason_index.loc[("worker_process", "administratively_excluded_worker"), "context_count"] == 32
    assert reason_index.loc[("worker_process", "outside_assignment"), "context_count"] == 9
    assert reason_index.loc[("active_time", "not_evaluable"), "context_count"] == 79
    excluded_workers = pd.read_csv(first / "EXCLUDED_WORKER_PEER_SUMMARY.csv")
    assert "14" in set(excluded_workers["excluded_worker_id"].astype(str))

    assert {
        "manual_pairwise_correspondence_disagreement",
        "manual_pairwise_metric_dissimilarity_all",
        "semi_pairwise_correspondence_disagreement",
        "semi_pairwise_metric_dissimilarity_all",
    }.issubset(tasks.columns)
    assert (subsets["pairwise_metric_eligible_count"] >= subsets["pairwise_correspondence_eligible_count"]).all()
    assert (subsets["pairwise_metric_eligible_count"] > subsets["pairwise_correspondence_eligible_count"]).any()

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
