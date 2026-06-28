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
    export_tasks = json.loads(export.read_text(encoding="utf-8"))
    project_by_task = {str(task["id"]): str(task.get("project") or task.get("project_id") or "1") for task in export_tasks}
    return _write_csv(
        path,
        [
            {
                "source_export": str(export),
                "project_id": project_by_task.get(task_id, "1"),
                "task_id": task_id,
                "task_key": f"{project_by_task.get(task_id, '1')}:{task_id}",
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
    task_rows, response_rows, _unknown, _mixed, _worker, _synthetic, summary = build_scope_audits(canonical, final_gold, completion)
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


def test_real_unknown_gold_tasks_are_allowlisted_or_zero() -> None:
    repo = Path(__file__).resolve().parents[1]
    _task_rows, _response_rows, unknown_rows, _mixed_rows, _worker_rows, _synthetic_rows, summary = build_scope_audits(
        repo / "analysis_results/prescreen_closeout/prescreen_canonical_annotations.csv",
        repo / "analysis_results/final_gold_layer_20260325/final_gold_records_v1.jsonl",
        repo / "analysis_results/prescreen_closeout/prescreen_completion_audit.csv",
        repo / "analysis_results/prescreen_closeout/prescreen_scope_unknown_gold_allowlist.csv",
        repo / "analysis_results/trap_collection_freeze_20260320/semi_synthetic_disjoint_candidate_bank_v2.jsonl",
        repo / "analysis_results/prescreen_closeout/prescreen_synthetic_expert_review.csv",
    )

    assert summary["unknown_gold_tasks"] == 0 or all(row["allowlisted"] for row in unknown_rows)


def test_real_mixed_scope_does_not_override_final_gold_and_oos_not_geometry_primary() -> None:
    repo = Path(__file__).resolve().parents[1]
    task_rows, response_rows, _unknown_rows, mixed_rows, _worker_rows, _synthetic_rows, _summary = build_scope_audits(
        repo / "analysis_results/prescreen_closeout/prescreen_canonical_annotations.csv",
        repo / "analysis_results/final_gold_layer_20260325/final_gold_records_v1.jsonl",
        repo / "analysis_results/prescreen_closeout/prescreen_completion_audit.csv",
        repo / "analysis_results/prescreen_closeout/prescreen_scope_unknown_gold_allowlist.csv",
        repo / "analysis_results/trap_collection_freeze_20260320/semi_synthetic_disjoint_candidate_bank_v2.jsonl",
        repo / "analysis_results/prescreen_closeout/prescreen_synthetic_expert_review.csv",
    )

    task_by_id = {str(row["task_id"]): row for row in task_rows}
    assert mixed_rows
    assert all(task_by_id[str(row["task_id"])]["task_scope_adjudication_source"] != "unresolved" for row in mixed_rows)
    assert all(row["geometry_primary_possible"] is False for row in task_rows if str(row["task_final_scope"]).startswith("oos_"))
    assert all(row["geometry_primary_possible"] is False for row in response_rows if str(row["task_final_scope"]).startswith("oos_"))


def _synthetic_task(ls_task_id: str, candidate_id: str, worker_scope: str = "normal") -> dict:
    return {
        "id": ls_task_id,
        "project": 40,
        "data": {
            "title": "synthetic.jpg",
            "dataset_group": "PreScreen_semi",
            "condition": "semi",
            "task_id": f"synthetic::{candidate_id}",
            "base_task_id": "runtime_base",
            "synthetic_candidate_id": candidate_id,
            "source_type": "trap_synthetic",
            "proposal_source_kind": "frozen_synthetic_asset",
        },
        "annotations": [_annotation("a1", "w1", worker_scope)],
    }


def _synthetic_bank(path: Path, candidate_id: str, source_base_task_id: str = "source_base", family: str = "corner_drift") -> Path:
    path.write_text(
        json.dumps(
            {
                "candidate_id": candidate_id,
                "source_base_task_id": source_base_task_id,
                "source_title": f"{source_base_task_id}.jpg",
                "family": family,
                "source_type": "trap_synthetic_disjoint_source",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _synthetic_expert_review(
    path: Path,
    *,
    runtime_task_id: str,
    mirror_task_id: str = "",
    base_image_key: str = "source_base",
    planned_family: str = "over_parsing",
    realized_primary: str = "corner_duplicate",
    worker_note: str = "scope only",
) -> Path:
    return _write_csv(
        path,
        [
            {
                "runtime_task_id": runtime_task_id,
                "mirror_task_id": mirror_task_id,
                "base_image_key": base_image_key,
                "planned_synthetic_family": planned_family,
                "expert_final_scope": "in_scope",
                "scope_gold_ready": "true",
                "expert_realized_model_issue_primary": realized_primary,
                "expert_realized_model_issue_secondary": "",
                "trap_effective": "true",
                "planned_realized_mismatch": str(planned_family != realized_primary).lower(),
                "operator_validity_note": worker_note,
            }
        ],
    )


def test_synthetic_task_binds_to_source_final_gold(tmp_path: Path) -> None:
    candidate_id = "synthetic_ok"
    export = tmp_path / "export.json"
    export.write_text(json.dumps([_synthetic_task("1", candidate_id, worker_scope="oos_geometry")]), encoding="utf-8")
    canonical = _canonical(tmp_path / "canonical.csv", export, [("1", "w1", "a1")])
    completion = _completion(tmp_path / "completion.csv", ["w1"])
    final_gold = _gold(
        tmp_path / "gold.jsonl",
        [{"task_id": "source_task", "base_task_id": "source_base", "final_scope_alias": "oos_geometry", "final_scope_binary": "oos"}],
    )
    bank = _synthetic_bank(tmp_path / "bank.jsonl", candidate_id)

    task_rows, response_rows, unknown_rows, _mixed, _worker, synthetic_rows, _summary = build_scope_audits(
        canonical, final_gold, completion, None, bank
    )

    assert task_rows[0]["task_scope_adjudication_source"] == "synthetic_asset_source_gold"
    assert task_rows[0]["task_final_scope"] == "oos_geometry"
    assert task_rows[0]["geometry_primary_possible"] is False
    assert response_rows[0]["worker_scope_response"] == "correct_oos"
    assert not unknown_rows
    assert synthetic_rows[0]["scope_binding_status"] == "synthetic_bound_to_source_gold"


def test_synthetic_expert_review_binds_source_gold_missing_scope_only(tmp_path: Path) -> None:
    candidate_id = "synthetic_reviewed"
    export = tmp_path / "export.json"
    export.write_text(json.dumps([_synthetic_task("1", candidate_id, worker_scope="normal")]), encoding="utf-8")
    canonical = _canonical(tmp_path / "canonical.csv", export, [("1", "w1", "a1")])
    completion = _completion(tmp_path / "completion.csv", ["w1"])
    final_gold = _gold(tmp_path / "gold.jsonl", [])
    bank = _synthetic_bank(tmp_path / "bank.jsonl", candidate_id, family="over_parsing")
    review = _synthetic_expert_review(tmp_path / "review.csv", runtime_task_id="1")

    task_rows, response_rows, unknown_rows, _mixed, _worker, synthetic_rows, summary = build_scope_audits(
        canonical, final_gold, completion, None, bank, review
    )

    assert task_rows[0]["task_final_scope"] == "in_scope"
    assert task_rows[0]["task_scope_adjudication_source"] == "synthetic_asset_expert_review"
    assert task_rows[0]["geometry_primary_possible"] is False
    assert response_rows[0]["worker_scope_response"] == "correct_in_scope"
    assert response_rows[0]["geometry_primary_possible"] is False
    assert not unknown_rows
    assert synthetic_rows[0]["scope_binding_status"] == "synthetic_bound_by_expert_scope_review"
    assert synthetic_rows[0]["primary_eligible_after_binding"] is False
    assert synthetic_rows[0]["geometry_gold_ready_after_binding"] is False
    assert synthetic_rows[0]["planned_realized_mismatch"] == "true"
    assert summary["synthetic_scope_unresolved_task_rows"] == 0
    assert summary["synthetic_scope_bound_task_rows"] == 1


def test_synthetic_expert_realized_model_issue_does_not_override_worker_scope(tmp_path: Path) -> None:
    candidate_id = "synthetic_worker_oos"
    export = tmp_path / "export.json"
    export.write_text(json.dumps([_synthetic_task("1", candidate_id, worker_scope="oos_geometry")]), encoding="utf-8")
    canonical = _canonical(tmp_path / "canonical.csv", export, [("1", "w1", "a1")])
    completion = _completion(tmp_path / "completion.csv", ["w1"])
    final_gold = _gold(tmp_path / "gold.jsonl", [])
    bank = _synthetic_bank(tmp_path / "bank.jsonl", candidate_id, family="over_parsing")
    review = _synthetic_expert_review(tmp_path / "review.csv", runtime_task_id="1", realized_primary="corner_duplicate")

    _task_rows, response_rows, _unknown_rows, _mixed, _worker, synthetic_rows, _summary = build_scope_audits(
        canonical, final_gold, completion, None, bank, review
    )

    assert synthetic_rows[0]["expert_realized_model_issue_primary"] == "corner_duplicate"
    assert response_rows[0]["worker_scope_normalized"] == "oos"
    assert response_rows[0]["worker_scope_response"] == "scope_false_positive"


def test_synthetic_bank_matched_but_source_gold_missing_is_not_unknown_gold(tmp_path: Path) -> None:
    candidate_id = "synthetic_no_source_gold"
    export = tmp_path / "export.json"
    export.write_text(json.dumps([_synthetic_task("1", candidate_id)]), encoding="utf-8")
    canonical = _canonical(tmp_path / "canonical.csv", export, [("1", "w1", "a1")])
    completion = _completion(tmp_path / "completion.csv", ["w1"])
    final_gold = _gold(tmp_path / "gold.jsonl", [])
    bank = _synthetic_bank(tmp_path / "bank.jsonl", candidate_id)

    task_rows, _response_rows, unknown_rows, _mixed, _worker, synthetic_rows, _summary = build_scope_audits(
        canonical, final_gold, completion, None, bank
    )

    assert task_rows[0]["task_final_scope"] == "synthetic_scope_unresolved"
    assert task_rows[0]["task_scope_adjudication_source"] == "synthetic_asset_bank_no_source_gold"
    assert not unknown_rows
    assert synthetic_rows[0]["scope_binding_status"] == "synthetic_bank_matched_source_gold_missing"


def test_synthetic_bank_missing_is_not_unknown_gold(tmp_path: Path) -> None:
    export = tmp_path / "export.json"
    export.write_text(json.dumps([_synthetic_task("1", "not_in_bank")]), encoding="utf-8")
    canonical = _canonical(tmp_path / "canonical.csv", export, [("1", "w1", "a1")])
    completion = _completion(tmp_path / "completion.csv", ["w1"])
    final_gold = _gold(tmp_path / "gold.jsonl", [])

    task_rows, _response_rows, unknown_rows, _mixed, _worker, synthetic_rows, _summary = build_scope_audits(
        canonical, final_gold, completion, None, tmp_path / "missing_bank.jsonl"
    )

    assert task_rows[0]["task_final_scope"] == "synthetic_scope_unresolved"
    assert task_rows[0]["task_scope_adjudication_source"] == "synthetic_asset_unmatched"
    assert not unknown_rows
    assert synthetic_rows[0]["scope_binding_status"] == "synthetic_bank_missing"


def test_language_mirror_counts_two_runtime_rows_one_base_image(tmp_path: Path) -> None:
    candidate_id = "mirror_candidate"
    export = tmp_path / "export.json"
    tasks = [_synthetic_task("1", candidate_id), _synthetic_task("2", candidate_id)]
    tasks[0]["project"] = 29
    tasks[1]["project"] = 40
    export.write_text(json.dumps(tasks), encoding="utf-8")
    canonical = _canonical(tmp_path / "canonical.csv", export, [("1", "w1", "a1"), ("2", "w1", "a1")])
    completion = _completion(tmp_path / "completion.csv", ["w1"])
    final_gold = _gold(tmp_path / "gold.jsonl", [])
    bank = _synthetic_bank(tmp_path / "bank.jsonl", candidate_id)

    _task_rows, _response_rows, _unknown, _mixed, _worker, _synthetic, summary = build_scope_audits(canonical, final_gold, completion, None, bank)

    assert summary["synthetic_scope_unresolved_task_rows"] == 2
    assert summary["synthetic_scope_unresolved_base_image_count"] == 1


def test_language_mirror_expert_review_counts_two_runtime_rows_one_base_image(tmp_path: Path) -> None:
    candidate_id = "mirror_reviewed"
    export = tmp_path / "export.json"
    tasks = [_synthetic_task("1", candidate_id), _synthetic_task("2", candidate_id)]
    tasks[0]["project"] = 29
    tasks[1]["project"] = 40
    export.write_text(json.dumps(tasks), encoding="utf-8")
    canonical = _canonical(tmp_path / "canonical.csv", export, [("1", "w1", "a1"), ("2", "w1", "a1")])
    completion = _completion(tmp_path / "completion.csv", ["w1"])
    final_gold = _gold(tmp_path / "gold.jsonl", [])
    bank = _synthetic_bank(tmp_path / "bank.jsonl", candidate_id)
    review = _synthetic_expert_review(tmp_path / "review.csv", runtime_task_id="1", mirror_task_id="2")

    _task_rows, _response_rows, _unknown, _mixed, _worker, _synthetic, summary = build_scope_audits(
        canonical, final_gold, completion, None, bank, review
    )

    assert summary["synthetic_scope_bound_task_rows"] == 2
    assert summary["synthetic_scope_bound_base_image_count"] == 1
    assert summary["synthetic_scope_unresolved_task_rows"] == 0


def test_real_synthetic_expert_review_resolves_all_current_synthetic_scope_unresolved() -> None:
    repo = Path(__file__).resolve().parents[1]
    _task_rows, _response_rows, _unknown_rows, _mixed_rows, _worker_rows, synthetic_rows, summary = build_scope_audits(
        repo / "analysis_results/prescreen_closeout/prescreen_canonical_annotations.csv",
        repo / "analysis_results/final_gold_layer_20260325/final_gold_records_v1.jsonl",
        repo / "analysis_results/prescreen_closeout/prescreen_completion_audit.csv",
        repo / "analysis_results/prescreen_closeout/prescreen_scope_unknown_gold_allowlist.csv",
        repo / "analysis_results/trap_collection_freeze_20260320/semi_synthetic_disjoint_candidate_bank_v2.jsonl",
        repo / "analysis_results/prescreen_closeout/prescreen_synthetic_expert_review.csv",
    )

    assert summary["synthetic_scope_unresolved_task_rows"] == 0
    assert summary["synthetic_scope_bound_task_rows"] == 12
    assert summary["synthetic_scope_bound_base_image_count"] == 6
    assert summary["synthetic_bound_by_expert_scope_review_task_rows"] == 12
    assert all(row["scope_binding_status"] == "synthetic_bound_by_expert_scope_review" for row in synthetic_rows)


def test_ordinary_non_synthetic_missing_final_gold_still_unknown(tmp_path: Path) -> None:
    tasks = [_task("1", "ordinary_missing", "", [_annotation("a1", "w1", "normal")])]
    export = tmp_path / "export.json"
    export.write_text(json.dumps(tasks), encoding="utf-8")
    canonical = _canonical(tmp_path / "canonical.csv", export, [("1", "w1", "a1")])
    completion = _completion(tmp_path / "completion.csv", ["w1"])
    final_gold = _gold(tmp_path / "gold.jsonl", [])

    task_rows, _response_rows, unknown_rows, _mixed, _worker, _synthetic, summary = build_scope_audits(canonical, final_gold, completion)

    assert task_rows[0]["task_final_scope"] == "unknown_gold"
    assert len(unknown_rows) == 1
    assert summary["non_synthetic_unknown_gold_task_rows"] == 1
