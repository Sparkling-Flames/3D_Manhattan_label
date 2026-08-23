from __future__ import annotations

from pathlib import Path

import pandas as pd

from tools.thesis_main.analysis.full_uncertainty import analyze_threshold_anchoring_worker_types_20260823 as audit


def test_validate_outputs_includes_validation_in_manifest(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(audit, "OUT", tmp_path)
    monkeypatch.setattr(audit, "git_head", lambda: "test-head")
    for name in (
        "ANALYSIS_REPORT_ZH.md",
        "THRESHOLD_SUMMARY_FORMAL22.csv",
        "PROPOSAL_CORRECTNESS_TRANSITIONS.csv",
        "WORKER_LATENT_ASSIGNMENTS_CURRENT20.csv",
        "ROBUST_OBSERVED_MULTIMODALITY_CANDIDATES.csv",
    ):
        (tmp_path / name).write_text("x\n", encoding="utf-8")

    checks = audit.validate_outputs()
    manifest = pd.read_csv(tmp_path / "OUTPUT_MANIFEST.csv", encoding="utf-8-sig")

    assert "VALIDATION.json" in set(manifest["path"])
    assert checks["output_file_count_excluding_manifest"] == len(manifest)


def test_half_features_recompute_proposal_correctness_rates() -> None:
    workers = ["1", "2"]
    selected = {name: {"t1"} for name in ("quality", "mode", "time", "proposal")}
    rows = {
        "quality_rows": pd.DataFrame([
            {"worker_id": "1", "base_task_id": "t1", "iou_to_gt": 0.8},
            {"worker_id": "2", "base_task_id": "t1", "iou_to_gt": 0.6},
        ]),
        "mode_rows": pd.DataFrame([
            {"worker_id": "1", "base_task_id": "t1", "is_largest_mode_num": 1.0, "is_supported_minority_num": 0.0, "task_centered_n_pairs": 1.0},
            {"worker_id": "2", "base_task_id": "t1", "is_largest_mode_num": 0.0, "is_supported_minority_num": 1.0, "task_centered_n_pairs": -1.0},
        ]),
        "time_rows": pd.DataFrame([
            {"worker_id": "1", "base_task_id": "t1", "time_group": "t1|semi", "log_active": 2.0},
            {"worker_id": "2", "base_task_id": "t1", "time_group": "t1|semi", "log_active": 1.0},
        ]),
        "proposal_rows": pd.DataFrame([
            {"worker_id": "1", "base_task_id": "t1", "edited": 0.0, "delta_U": -0.1, "proposal_correctness_observed_095": True, "initial_correct_095": True, "correct_proposal_degraded_095": True, "wrong_proposal_corrected_095": False, "wrong_proposal_retained_exact": False},
            {"worker_id": "2", "base_task_id": "t1", "edited": 1.0, "delta_U": 0.2, "proposal_correctness_observed_095": True, "initial_correct_095": False, "correct_proposal_degraded_095": False, "wrong_proposal_corrected_095": True, "wrong_proposal_retained_exact": False},
        ]),
    }

    result = audit.recompute_half_features(workers, rows, selected).set_index("worker_id")

    assert result.loc["1", "correct_proposal_degradation_rate_jeffreys"] == 0.75
    assert result.loc["2", "wrong_proposal_correction_rate_jeffreys"] == 0.75
    masked = audit.mask_sparse_proposal_features(result.copy())
    assert masked["correct_proposal_degradation_rate_jeffreys"].isna().all()


def test_mh_bootstrap_resamples_buildings() -> None:
    rows = []
    for building in range(3):
        for task in range(2):
            for condition, correct in (("manual", task == 0), ("semi", task == 1)):
                rows.append({
                    "building_id": f"b{building}",
                    "base_task_id": f"b{building}_t{task}",
                    "condition": condition,
                    "final_correct": correct,
                })

    lower, upper = audit.bootstrap_mh_or_by_building(pd.DataFrame(rows), "final_correct", reps=20)

    assert lower is None and upper is None  # six tasks but only three independent buildings
