from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tools.compute_dt_score import BatchAbortError, DtScoreComputer, canonical_json_hash, l2_normalize


class FakeDtScoreComputer(DtScoreComputer):
    def __init__(self, source_path: Path, embedding_map: dict[str, list[float]], *, config: dict | None = None):
        self.embedding_map = {key: l2_normalize(np.asarray(value, dtype=np.float32)) for key, value in embedding_map.items()}
        super().__init__(source_path, config=config or {"primary_k": 1, "quantile": 0.9})

    def extract_embedding(self, image_path: str) -> np.ndarray:
        return self.embedding_map[str(image_path)]


def _write_dt_summary(path: Path, refs: list[dict]) -> Path:
    payload = {
        "meta": {
            "round_id": "C1",
            "source_split": "Calibration_manual",
            "pool_size": len(refs),
            "dedup_key": "base_task_id",
            "model_version": "HoHoNet_stage1_prescreen_v5",
            "embedding_backend": "hohonet.shared_pre_head_gapw_l2",
            "distance_metric": "euclidean",
            "k": 1,
            "q": 0.9,
            "provisional_tau_d": None,
            "reference_pool_hash": canonical_json_hash(refs),
            "frozen_at": "2026-03-29T00:00:00Z",
            "selection_strategy": "lexicographical_top_n",
        },
        "reference_pool": refs,
        "loo_summary": {
            "n_ref_success": 0,
            "n_ref_fail": 0,
            "loo_score_min": None,
            "loo_score_median": None,
            "loo_score_max": None,
            "provisional_tau_d": None,
        },
        "failure_audit": {
            "extract_fail_count": 0,
            "embed_dim_error_count": 0,
            "knn_runtime_error_count": 0,
            "ref_hash_mismatch": False,
            "leakage_check_failed": False,
        },
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def test_compute_dt_score_primary_path_and_threshold_from_dt_summary(tmp_path: Path) -> None:
    dt_summary_path = _write_dt_summary(
        tmp_path / "dt_reference_summary_C1.json",
        [
            {
                "task_id": "r1",
                "base_task_id": "base_r1",
                "image_id": "ref1",
                "image_path": "ref1.jpg",
                "source_split": "Calibration_manual",
                "inclusion_rank": 1,
                "embedding_hash": "sha256:ref1",
            },
            {
                "task_id": "r2",
                "base_task_id": "base_r2",
                "image_id": "ref2",
                "image_path": "ref2.jpg",
                "source_split": "Calibration_manual",
                "inclusion_rank": 2,
                "embedding_hash": "sha256:ref2",
            },
            {
                "task_id": "r3",
                "base_task_id": "base_r3",
                "image_id": "ref3",
                "image_path": "ref3.jpg",
                "source_split": "Calibration_manual",
                "inclusion_rank": 3,
                "embedding_hash": "sha256:ref3",
            },
        ],
    )
    computer = FakeDtScoreComputer(
        dt_summary_path,
        {
            "ref1.jpg": [1.0, 0.0],
            "ref2.jpg": [0.0, 1.0],
            "ref3.jpg": [1.0, 1.0],
            "query_near.jpg": [0.9, 0.1],
            "query_far.jpg": [-1.0, 0.0],
        },
        config={"primary_k": 1, "quantile": 0.9},
    )

    scored = computer.run(
        pd.DataFrame(
            [
                {"task_id": "q1", "image_path": "query_near.jpg"},
                {"task_id": "q2", "image_path": "query_far.jpg"},
            ]
        )
    )
    by_task = scored.set_index("task_id")

    assert by_task.loc["q1", "d_t_status"] == "success"
    assert float(by_task.loc["q1", "d_t"]) < float(by_task.loc["q2", "d_t"])
    assert int(float(by_task.loc["q1", "I_t_OOD"])) == 0
    assert int(float(by_task.loc["q2", "I_t_OOD"])) == 1
    assert float(by_task.loc["q1", "tau_d"]) > 0
    summary = computer.build_dt_reference_summary()
    assert summary["meta"]["reference_pool_hash"] == canonical_json_hash(summary["reference_pool"])
    assert summary["loo_summary"]["provisional_tau_d"] == computer.tau_d


def test_compute_dt_score_rejects_blacklisted_columns_by_default(tmp_path: Path) -> None:
    dt_summary_path = _write_dt_summary(
        tmp_path / "dt_reference_summary_C1.json",
        [
            {
                "task_id": "r1",
                "base_task_id": "base_r1",
                "image_id": "ref1",
                "image_path": "ref1.jpg",
                "source_split": "Calibration_manual",
                "inclusion_rank": 1,
                "embedding_hash": "sha256:ref1",
            }
        ],
    )
    computer = FakeDtScoreComputer(
        dt_summary_path,
        {"ref1.jpg": [1.0, 0.0], "query.jpg": [1.0, 0.0]},
        config={"primary_k": 1, "quantile": 0.9},
    )

    with pytest.raises(BatchAbortError, match="leakage_check_failed"):
        computer.run(pd.DataFrame([{"task_id": "q1", "image_path": "query.jpg", "difficulty": "occlusion"}]))


def test_compute_dt_score_rejects_duplicate_base_task_id_in_dt_summary(tmp_path: Path) -> None:
    dt_summary_path = _write_dt_summary(
        tmp_path / "dt_reference_summary_C1.json",
        [
            {
                "task_id": "r1",
                "base_task_id": "dup",
                "image_id": "ref1",
                "image_path": "ref1.jpg",
                "source_split": "Calibration_manual",
                "inclusion_rank": 1,
                "embedding_hash": "sha256:ref1",
            },
            {
                "task_id": "r2",
                "base_task_id": "dup",
                "image_id": "ref2",
                "image_path": "ref2.jpg",
                "source_split": "Calibration_manual",
                "inclusion_rank": 2,
                "embedding_hash": "sha256:ref2",
            },
        ],
    )

    with pytest.raises(ValueError, match="duplicate base_task_id"):
        DtScoreComputer(dt_summary_path, config={"primary_k": 1})


def test_compute_dt_score_aborts_on_ref_hash_mismatch(tmp_path: Path) -> None:
    refs = [
        {
            "task_id": "r1",
            "base_task_id": "base_r1",
            "image_id": "ref1",
            "image_path": "ref1.jpg",
            "source_split": "Calibration_manual",
            "inclusion_rank": 1,
            "embedding_hash": "sha256:ref1",
        }
    ]
    dt_summary_path = tmp_path / "dt_reference_summary_C1.json"
    dt_summary_path.write_text(
        json.dumps(
            {
                "meta": {
                    "round_id": "C1",
                    "source_split": "Calibration_manual",
                    "pool_size": 1,
                    "dedup_key": "base_task_id",
                    "model_version": "HoHoNet_stage1_prescreen_v5",
                    "embedding_backend": "hohonet.shared_pre_head_gapw_l2",
                    "distance_metric": "euclidean",
                    "k": 1,
                    "q": 0.9,
                    "provisional_tau_d": None,
                    "reference_pool_hash": "sha256:bad",
                    "frozen_at": "2026-03-29T00:00:00Z",
                    "selection_strategy": "lexicographical_top_n",
                },
                "reference_pool": refs,
                "loo_summary": {
                    "n_ref_success": 0,
                    "n_ref_fail": 0,
                    "loo_score_min": None,
                    "loo_score_median": None,
                    "loo_score_max": None,
                    "provisional_tau_d": None,
                },
                "failure_audit": {
                    "extract_fail_count": 0,
                    "embed_dim_error_count": 0,
                    "knn_runtime_error_count": 0,
                    "ref_hash_mismatch": False,
                    "leakage_check_failed": False,
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    with pytest.raises(BatchAbortError, match="ref_hash mismatch"):
        DtScoreComputer(dt_summary_path, config={"primary_k": 1})
