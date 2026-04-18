from pathlib import Path

from tools.build_mp3d_txt_smoke_test import build_smoke_test_payload


def test_build_mp3d_txt_smoke_test_payload_excludes_prescreen_and_has_scope():
    repo_root = Path(__file__).resolve().parents[1]
    payload = build_smoke_test_payload(repo_root=repo_root, sample_count=5, random_seed=20260328)

    tasks = payload["tasks"]
    summary = payload["summary"]
    sampled_ids = summary["sampled_base_task_ids"]

    assert len(tasks) == 5
    assert len(sampled_ids) == 5
    assert len(set(sampled_ids)) == 5
    assert summary["dataset_group"] == "MP3D_TXT_SMOKE"

    registry_csv = repo_root / "analysis_results" / "truth_layer_extraction_20260324" / "trap_task_registry_v1.csv"
    registry_text = registry_csv.read_text(encoding="utf-8-sig")
    for base_task_id in sampled_ids:
        assert base_task_id not in registry_text

    for task in tasks:
        assert task["data"]["dataset_group"] == "MP3D_TXT_SMOKE"
        assert task["data"]["prediction_source"] == "model_output_txt"
        assert task["data"]["gold_source"] == "mp3d_label_cor_txt"
        assert len(task["predictions"]) == 1
        assert len(task["annotations"]) == 1

        ann_results = task["annotations"][0]["result"]
        pred_results = task["predictions"][0]["result"]

        assert any(item["type"] == "choices" and item["from_name"] == "scope" for item in ann_results)
        assert any(item["type"] == "keypointlabels" for item in ann_results)
        assert any(item["type"] == "polygonlabels" for item in ann_results)
        assert not any(item["type"] == "choices" for item in pred_results)
