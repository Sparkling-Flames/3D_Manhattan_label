import csv
from pathlib import Path

from tools.thesis_main.analysis.materialize_worker_scene_profile_candidates import materialize_worker_scene_profile_candidates


def test_worker_scene_candidates_are_not_primary_profile(tmp_path: Path) -> None:
    quality = tmp_path / "quality.csv"
    fields = ["task_id", "base_task_id", "dataset_group", "scene_label", "condition", "worker_id", "difficulty", "model_issue"]
    with quality.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows([
            {"task_id": "t1", "base_task_id": "s1", "dataset_group": "Calibration_core", "scene_label": "room", "condition": "manual", "worker_id": "w1", "difficulty": "occlusion", "model_issue": "acceptable"},
            {"task_id": "t2", "base_task_id": "s1", "dataset_group": "Calibration_core", "scene_label": "room", "condition": "manual", "worker_id": "w1", "difficulty": "trivial", "model_issue": "acceptable"},
        ])
    summary = materialize_worker_scene_profile_candidates(quality, tmp_path)
    assert summary["dry_run"] is True
    profiles = list(csv.DictReader((tmp_path / "worker_scene_profile_candidates_C1.csv").open(encoding="utf-8")))
    assert profiles
    assert all(row["scene_profile_primary"] == "false" for row in profiles)
    assert all(row["routing_eligible"] == "false" for row in profiles)

