from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.thesis_main.analysis.prescreen_scope_adjudication import build_scope_audits


def _choice(scope: str | None) -> list[dict]:
    if scope is None:
        return []
    return [{"type": "choices", "from_name": "scope", "value": {"choices": [scope]}}]


def _geom() -> list[dict]:
    return [{"type": "keypointlabels", "value": {"x": 10, "y": 10, "keypointlabels": ["Corner"]}}]


def _annotation(annotation_id: str, worker: str, scope: str | None, *, geometry: bool = True) -> dict:
    return {
        "id": annotation_id,
        "completed_by": {"id": worker},
        "result": (_geom() if geometry else []) + _choice(scope),
    }


def _task(ls_task_id: str, data_task_id: str, scope_gold: str, annotations: list[dict]) -> dict:
    return {
        "id": ls_task_id,
        "project": 1,
        "data": {
            "title": f"{data_task_id}.jpg",
            "dataset_group": "PreScreen_manual",
            "condition": "manual",
            "task_id": data_task_id,
            "base_task_id": f"base_{data_task_id}",
            "scope_gold": scope_gold,
        },
        "annotations": annotations,
    }


def _write_csv(path: Path, rows: list[dict]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return path


def _canonical(path: Path, export: Path, rows: list[tuple[str, str, str]]) -> Path:
    return _write_csv(
        path,
        [
            {
                "source_export": str(export),
                "project_id": "1",
                "task_id": task_id,
                "task_key": f"1:{task_id}",
                "task_label": f"{task_id}.jpg",
                "dataset_group": "PreScreen_manual",
                "condition": "manual",
                "annotator_id": worker,
                "annotation_id": ann_id,
                "raw_canonical_annotation_id": ann_id,
                "canonical_annotation_id": f"canon_{task_id}_{worker}",
                "geometry_hash": "hash",
                "n_corners": "1",
                "parse_error": "",
            }
            for task_id, worker, ann_id in rows
        ],
    )


def _completion(path: Path, workers: list[str]) -> Path:
    return _write_csv(
        path,
        [
            {
                "annotator_id": worker,
                "language": "zh",
                "completion_status": "complete",
                "eligible_for_primary_prescreen_candidate": "True",
            }
            for worker in workers
        ],
    )


def _gold(path: Path, records: list[dict]) -> Path:
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    return path


def _run(tmp_path: Path, tasks: list[dict], canonical_rows: list[tuple[str, str, str]], gold_records: list[dict]):
    export = tmp_path / "export.json"
    export.write_text(json.dumps(tasks), encoding="utf-8")
    canonical = _canonical(tmp_path / "canonical.csv", export, canonical_rows)
    completion = _completion(tmp_path / "completion.csv", sorted({worker for _task, worker, _ann in canonical_rows}))
    final_gold = _gold(tmp_path / "gold.jsonl", gold_records)
    task_rows, response_rows, summary = build_scope_audits(canonical, final_gold, completion)
    return {r["task_id"]: r for r in task_rows}, {(r["task_id"], r["annotator_id"]): r for r in response_rows}, summary


def test_scope_response_matrix_and_geometry_policy(tmp_path: Path) -> None:
    tasks = [
        _task("1", "fg_in", "normal", [_annotation("a1", "w1", "normal"), _annotation("a2", "w2", "oos_geometry")]),
        _task("2", "fg_oos", "oos_geometry", [_annotation("a3", "w1", "normal"), _annotation("a4", "w2", "oos_geometry")]),
        _task("3", "fg_missing_scope", "normal", [_annotation("a5", "w1", None)]),
    ]
    task_rows, response_rows, _summary = _run(
        tmp_path,
        tasks,
        [("1", "w1", "a1"), ("1", "w2", "a2"), ("2", "w1", "a3"), ("2", "w2", "a4"), ("3", "w1", "a5")],
        [
            {"task_id": "fg_in", "base_task_id": "base_fg_in", "final_scope_alias": "normal", "final_scope_binary": "in_scope"},
            {"task_id": "fg_oos", "base_task_id": "base_fg_oos", "final_scope_alias": "oos_geometry", "final_scope_binary": "oos"},
            {"task_id": "fg_missing_scope", "base_task_id": "base_fg_missing_scope", "final_scope_alias": "normal", "final_scope_binary": "in_scope"},
        ],
    )

    assert response_rows[("1", "w1")]["worker_scope_response"] == "correct_in_scope"
    assert response_rows[("1", "w2")]["worker_scope_response"] == "scope_false_positive"
    assert response_rows[("1", "w2")]["geometry_valid_or_present"] is True
    assert response_rows[("1", "w2")]["geometry_primary_possible"] is True
    assert response_rows[("2", "w1")]["worker_scope_response"] == "scope_false_negative"
    assert response_rows[("2", "w1")]["geometry_primary_possible"] is False
    assert response_rows[("2", "w2")]["worker_scope_response"] == "correct_oos"
    assert response_rows[("3", "w1")]["worker_scope_response"] == "unknown_or_missing"
    assert task_rows["1"]["mixed_scope_flag"] is True
    assert task_rows["1"]["task_final_scope"] == "in_scope"


def test_missing_final_gold_is_unknown_and_not_primary(tmp_path: Path) -> None:
    tasks = [_task("1", "no_gold", "", [_annotation("a1", "w1", "normal")])]
    task_rows, response_rows, _summary = _run(tmp_path, tasks, [("1", "w1", "a1")], [])

    assert task_rows["1"]["task_final_scope"] == "unknown_gold"
    assert task_rows["1"]["task_scope_adjudication_source"] == "missing_final_gold"
    assert task_rows["1"]["geometry_primary_possible"] is False
    assert response_rows[("1", "w1")]["worker_scope_response"] == "not_applicable_unresolved"
    assert response_rows[("1", "w1")]["scope_response_primary_eligible"] is False


def test_undercoverage_label_does_not_become_oos_subtype(tmp_path: Path) -> None:
    tasks = [_task("1", "under", "", [_annotation("a1", "w1", "normal")])]
    task_rows, _response_rows, _summary = _run(
        tmp_path,
        tasks,
        [("1", "w1", "a1")],
        [{"task_id": "under", "base_task_id": "base_under", "final_scope_alias": "undercoverage", "final_scope_binary": "in_scope"}],
    )

    assert task_rows["1"]["task_final_scope"] == "in_scope"
    assert not str(task_rows["1"]["task_final_scope"]).startswith("oos_")
