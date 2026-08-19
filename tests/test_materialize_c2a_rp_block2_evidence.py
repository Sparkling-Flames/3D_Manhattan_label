from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.thesis_main.analysis.materialize_c2a_rp_block2_evidence import bind_gt_predictions


def test_bind_gt_predictions_matches_base_task_without_changing_annotations(tmp_path: Path) -> None:
    raw = [{
        "id": 7,
        "data": {"base_task_id": "task-a", "image": "https://example/task-a.jpg"},
        "annotations": [{"id": 11, "result": [{"type": "keypointlabels"}]}],
        "predictions": [],
    }]
    gt = [{
        "data": {"base_task_id": "task-a"},
        "predictions": [{"model_version": "frozen-gt", "result": [{"type": "keypointlabels"}]}],
    }]

    bound, audit = bind_gt_predictions(raw, gt)

    assert bound[0]["annotations"] == raw[0]["annotations"]
    assert bound[0]["predictions"] == gt[0]["predictions"]
    assert audit == {"raw_tasks": 1, "gt_tasks": 1, "matched_tasks": 1, "unmatched_task_ids": []}


def test_bind_gt_predictions_fails_closed_for_missing_or_duplicate_gt() -> None:
    raw = [{"data": {"base_task_id": "task-a"}, "annotations": [], "predictions": []}]
    with pytest.raises(ValueError, match="missing GT"):
        bind_gt_predictions(raw, [])
    gt = [
        {"data": {"base_task_id": "task-a"}, "predictions": [{}]},
        {"data": {"base_task_id": "task-a"}, "predictions": [{}]},
    ]
    with pytest.raises(ValueError, match="duplicate GT"):
        bind_gt_predictions(raw, gt)
