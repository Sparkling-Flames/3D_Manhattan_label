from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.thesis_main.registry.audit_c1_project_mapping import audit_project_mapping
from tools.thesis_main.registry.audit_c1_realized_vs_assigned import audit_realized_vs_assigned
from tools.thesis_main.registry.audit_p1_c1_image_overlap import audit_overlap
from tools.thesis_main.registry.build_worker_facing_c1_distribution import build_distribution
from tools.thesis_main.registry.summarize_c1_launch_readiness import summarize_launch_readiness


def _json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _csv(path: Path, rows: list[dict[str, str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


def _import_task(task_id: str, group: str) -> dict:
    return {
        "data": {
            "task_id": task_id,
            "base_task_id": task_id,
            "title": f"{task_id}.jpg",
            "image": f"https://example.test/{task_id}.jpg",
            "dataset_group": group,
        }
    }


def _calibration_manifest(path: Path) -> Path:
    return _json(
        path,
        {
            "task_sets": {
                "Calibration_anchor": [
                    {"task_id": "anchor_01", "base_task_id": "anchor_01", "image_id": "anchor_01", "dataset_group": "Calibration_anchor"}
                ],
                "Calibration_core": [
                    {"task_id": "core_01", "base_task_id": "core_01", "image_id": "core_01", "dataset_group": "Calibration_core"},
                    {"task_id": "core_02", "base_task_id": "core_02", "image_id": "core_02", "dataset_group": "Calibration_core"},
                ],
                "Calibration_reserve": [
                    {
                        "task_id": "reserve_01",
                        "base_task_id": "reserve_01",
                        "image_id": "reserve_01",
                        "dataset_group": "Calibration_reserve",
                    }
                ],
            }
        },
    )


def _assignment(path: Path, workers: tuple[str, ...] = ("w1", "w2")) -> Path:
    rows = [
        {
            "round_id": "C1",
            "worker_id": worker,
            "task_id": task,
            "base_task_id": task,
            "dataset_group": group,
            "assignment_batch": batch,
            "assignment_reason": "common_anchor" if group == "Calibration_anchor" else "balanced_core",
            "is_common_anchor": "true" if group == "Calibration_anchor" else "false",
            "expected_completion_order": str(order),
            "manifest_version": "v1",
        }
        for worker in workers
        for order, task, group, batch in [
            (1, "anchor_01", "Calibration_anchor", "anchor_all"),
            (2, "core_01", "Calibration_core", "core_all"),
            (3, "core_02", "Calibration_core", "core_all"),
        ]
    ]
    return _csv(path, rows)


def test_overlap_audit_rejects_prescreen_calibration_image_reuse(tmp_path: Path) -> None:
    p1 = _json(tmp_path / "p1.json", [_import_task("anchor_01", "PreScreen_manual")])
    calibration = _calibration_manifest(tmp_path / "calibration.json")

    summary = audit_overlap([p1], calibration)

    assert summary["passed"] is False
    assert summary["overlap_counts"]["base_task_id"] == 1
    assert "p1_calibration_overlap" in summary["blockers"]


def test_overlap_audit_uses_calibration_source_import_for_title_stem(tmp_path: Path) -> None:
    p1 = _json(
        tmp_path / "p1.json",
        [{"data": {"task_id": "p1_01", "base_task_id": "p1_base", "image_id": "p1_image", "title": "same_image.jpg", "dataset_group": "PreScreen_manual"}}],
    )
    c1_source = _json(tmp_path / "c1_source.json", [{"data": {"title": "same_image.jpg", "dataset_group": "Calibration_anchor"}}])
    calibration = _json(
        tmp_path / "calibration.json",
        {
            "task_sets": {
                "Calibration_anchor": [
                    {
                        "task_id": "anchor_01",
                        "base_task_id": "anchor_base",
                        "image_id": "anchor_image",
                        "dataset_group": "Calibration_anchor",
                        "source_import_json": str(c1_source),
                    }
                ],
                "Calibration_core": [],
                "Calibration_reserve": [],
            }
        },
    )

    summary = audit_overlap([p1], calibration)

    assert summary["passed"] is False
    assert summary["overlap_counts"]["title_stem"] == 1


def test_project_mapping_requires_exact_batch_tasks_and_blocks_reserve(tmp_path: Path) -> None:
    workers = tuple(f"w{idx:02d}" for idx in range(16))
    assignment = _assignment(tmp_path / "assignment.csv", workers)
    anchor_import = _json(tmp_path / "anchor.json", [_import_task("anchor_01", "Calibration_anchor")])
    core_import = _json(tmp_path / "core.json", [_import_task("core_01", "Calibration_core"), _import_task("reserve_01", "Calibration_reserve")])
    mapping = _csv(
        tmp_path / "mapping.csv",
        [
            {"project_name": "C1_anchor_all", "assignment_batch": "anchor_all", "import_json": str(anchor_import)},
            {"project_name": "C1_core_all", "assignment_batch": "core_all", "import_json": str(core_import)},
        ],
    )

    summary = audit_project_mapping(assignment, mapping)

    assert summary["passed"] is False
    assert "reserve_task_imported_into_c1_project" in summary["blockers"]
    assert "project_task_mismatch" in summary["blockers"]


def test_worker_facing_distribution_writes_one_csv_per_worker(tmp_path: Path) -> None:
    assignment = _assignment(tmp_path / "assignment.csv")
    mapping = _csv(
        tmp_path / "mapping.csv",
        [
            {
                "project_name": "C1_anchor_all",
                "assignment_batch": "anchor_all",
                "import_json": "anchor.json",
                "interface_language": "zh",
                "ls_endpoint": "https://label.example/ls",
                "task_url_template": "https://label.example/ls/tasks/{task_id}",
            },
            {
                "project_name": "C1_core_all",
                "assignment_batch": "core_all",
                "import_json": "core.json",
                "interface_language": "zh",
                "ls_endpoint": "https://label.example/ls",
                "task_url_template": "https://label.example/ls/tasks/{task_id}",
            },
        ],
    )
    roster = _csv(
        tmp_path / "workers.csv",
        [
            {"worker_id": "w1", "worker_display_name": "Worker 1", "platform_id": "p1", "interface_language": "zh", "admission_status": "pass"},
            {
                "worker_id": "w2",
                "worker_display_name": "Worker 2",
                "platform_id": "p2",
                "interface_language": "zh",
                "admission_status": "pass_with_watch",
            },
        ],
    )

    summary = build_distribution(assignment, tmp_path / "dist", mapping, roster)

    assert summary["passed"] is True
    assert summary["counts"]["workers"] == 2
    assert (tmp_path / "dist" / "worker_w1_C1_tasks.csv").exists()
    w2_rows = list(csv.DictReader((tmp_path / "dist" / "worker_w2_C1_tasks.csv").open(encoding="utf-8")))
    assert w2_rows[0]["watch_flag"] == "True"
    assert w2_rows[0]["task_url"] == "https://label.example/ls/tasks/anchor_01"
    index_rows = list(csv.DictReader((tmp_path / "dist" / "worker_facing_c1_distribution_index.csv").open(encoding="utf-8")))
    assert {row["project_names"] for row in index_rows} == {"C1_anchor_all|C1_core_all"}


def test_realized_vs_assigned_rejects_unassigned_submission(tmp_path: Path) -> None:
    assignment = _assignment(tmp_path / "assignment.csv")
    export = _json(
        tmp_path / "export.json",
        [
            {"data": {"task_id": "anchor_01", "dataset_group": "Calibration_anchor"}, "annotations": [{"completed_by": "w1"}]},
            {"data": {"task_id": "core_99", "dataset_group": "Calibration_core"}, "annotations": [{"completed_by": "w1"}]},
        ],
    )

    summary = audit_realized_vs_assigned(assignment, [export])

    assert summary["passed"] is False
    assert "unassigned_realized_submission" in summary["blockers"]
    assert summary["counts"]["unassigned_realized_pairs"] == 1


def test_launch_readiness_summarizes_required_audits(tmp_path: Path) -> None:
    workers = tuple(f"w{idx:02d}" for idx in range(16))
    assignment = _assignment(tmp_path / "assignment.csv", workers)
    calibration = _calibration_manifest(tmp_path / "calibration.json")
    assignment_audit = _json(tmp_path / "assignment_audit.json", {"passed": True, "counts": {"core_tasks": 2}})
    overlap_audit = _json(tmp_path / "overlap.json", {"passed": True})
    mapping_audit = _json(tmp_path / "mapping_audit.json", {"passed": True, "counts": {"projects": 2}})
    dist_index = _csv(
        tmp_path / "worker_facing_c1_distribution_index.csv",
        [
            {
                "worker_id": worker,
                "task_count": "3",
                "anchor_count": "1",
                "core_count": "2",
                "project_names": "C1_anchor_all|C1_core_all",
                "output_csv": f"{worker}.csv",
            }
            for worker in workers
        ],
    )

    summary = summarize_launch_readiness(
        assignment_manifest=assignment,
        calibration_manifest=calibration,
        assignment_audit_json=assignment_audit,
        overlap_audit_json=overlap_audit,
        project_mapping_audit_json=mapping_audit,
        distribution_index=dist_index,
        tests_status="pass",
    )

    assert summary["passed"] is True
    assert summary["counts"]["workers"] == 16
    assert summary["counts"]["anchor_tasks"] == 1
    assert summary["counts"]["core_tasks"] == 2
    assert summary["counts"]["reserve_tasks"] == 1
