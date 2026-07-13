import csv
from pathlib import Path

from tools.thesis_main.analysis.materialize_worker_scene_profile_candidates import materialize_worker_scene_profile_candidates


def _write(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_profile_consumes_three_state_rows_and_requires_scene_id(tmp_path: Path) -> None:
    observations = tmp_path / "worker_task_tag_observations_C1.csv"
    _write(observations, ["task_id", "base_task_id", "scene_id", "dataset_group", "condition", "worker_id", "tag_family", "tag_name", "assertion"], [
        {"task_id": "t1", "base_task_id": "s1", "scene_id": "room", "dataset_group": "Calibration_core", "condition": "manual", "worker_id": "w1", "tag_family": "difficulty", "tag_name": "occlusion", "assertion": "+"},
        {"task_id": "t2", "base_task_id": "s2", "scene_id": "", "dataset_group": "Calibration_core", "condition": "manual", "worker_id": "w1", "tag_family": "difficulty", "tag_name": "occlusion", "assertion": "+"},
    ])
    _write(tmp_path / "task_tag_three_state_summary_C1.csv", ["task_id", "tag_family", "tag_name", "task_tag_state"], [{"task_id": "t1", "tag_family": "difficulty", "tag_name": "occlusion", "task_tag_state": "convergent_positive"}])
    summary = materialize_worker_scene_profile_candidates(observations, tmp_path)
    profiles = list(csv.DictReader((tmp_path / "worker_scene_profile_candidates_C1.csv").open(encoding="utf-8")))
    assert summary["n_missing_scene_rows"] == 1
    assert profiles[0]["scene_profile_candidate"] == "insufficient_support"
    assert profiles[0]["support_status"] == "insufficient_support"
    assert profiles[0]["n_task_broad"] == "0"
    assert profiles[0]["profile_geometry_status"] == "insufficient_peer_support"
    assert profiles[0]["fallback"] == "global_reliability"
    assert profiles[0]["routing_eligible"] == "false"
