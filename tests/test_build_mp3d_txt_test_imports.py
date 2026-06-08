from pathlib import Path

from tools.thesis_main.data_prep.build_mp3d_txt_smoke_test import build_smoke_test_payload
from tools.thesis_main.data_prep.build_mp3d_txt_test_imports import _build_manual_task, _build_semi_task


def test_build_mp3d_txt_test_imports_manual_has_no_predictions_and_semi_has_predictions():
    repo_root = Path(__file__).resolve().parents[1]
    payload = build_smoke_test_payload(repo_root=repo_root, sample_count=3, random_seed=20260328)
    candidates = payload["selected_candidates"]

    manual_tasks = [_build_manual_task(repo_root, c, "https://example.com/img", "https://example.com") for c in candidates]
    semi_tasks = [_build_semi_task(repo_root, c, "https://example.com/img", "https://example.com") for c in candidates]

    assert len(manual_tasks) == 3
    assert len(semi_tasks) == 3

    for task in manual_tasks:
        assert "predictions" not in task
        assert task["data"]["condition"] == "manual"
        assert task["data"]["dataset_group"] == "MP3D_TXT_SMOKE_manual"
        assert task["data"]["pseudo_gold_source"] == "mp3d_label_cor_txt"

    for task in semi_tasks:
        assert "predictions" in task
        assert len(task["predictions"]) == 1
        assert task["data"]["condition"] == "semi"
        assert task["data"]["dataset_group"] == "MP3D_TXT_SMOKE_semi"
        assert task["data"]["proposal_source_kind"] == "model_output_txt"
