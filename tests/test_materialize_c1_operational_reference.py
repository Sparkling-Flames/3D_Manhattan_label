import csv
import json
from pathlib import Path

from tools.thesis_main.analysis.materialize_c1_operational_reference import materialize


def _csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_operational_reference_preserves_reviewed_and_leaves_unreviewed_pending(tmp_path: Path) -> None:
    canonical = tmp_path / "canonical.csv"
    geometry = tmp_path / "geometry.jsonl"
    inventory = tmp_path / "inventory.csv"
    gt = tmp_path / "gt.json"
    _csv(canonical, [
        {"project_id": "66", "ls_runtime_task_id": "1", "task_id": "t1", "base_task_id": "reviewed", "condition": "manual", "worker_id": "w1", "annotation_id": "a1", "canonical_annotation_id": "c1", "dataset_group": "Calibration_anchor"},
        {"project_id": "67", "ls_runtime_task_id": "2", "task_id": "t2", "base_task_id": "pending", "condition": "manual", "worker_id": "w1", "annotation_id": "a2", "canonical_annotation_id": "c2", "dataset_group": "Calibration_core"},
    ])
    points = [[100, 100], [100, 400], [700, 100], [700, 400]]
    geometry.write_text("\n".join(json.dumps({"canonical_annotation_id": key, "corners_px": points}) for key in ("c1", "c2")), encoding="utf-8")
    _csv(inventory, [
        {"base_task_id": "reviewed", "expert_review_status": "latest_human_reviewed", "expert_scope_confirmed": "inscope", "old_manual_scope_raw": ""},
        {"base_task_id": "pending", "expert_review_status": "unreviewed_pool", "expert_scope_confirmed": "", "old_manual_scope_raw": ""},
    ])
    result = [{"type": "keypointlabels", "value": {"x": x / 10.24, "y": y / 5.12}} for x, y in points]
    gt.write_text(json.dumps([{"id": "g1", "project": 70, "data": {"title": "reviewed.jpg"}, "annotations": [{"id": "ga1", "ground_truth": True, "result": result}]}]), encoding="utf-8")

    summary = materialize(canonical, geometry, inventory, gt, tmp_path)

    assert summary["n_resolved_contexts"] == 1
    assert summary["n_pending_contexts"] == 1
    assert summary["n_gt_quality_evaluable"] == 1
    assert summary["geometry_reference_ready"] is False
    assert summary["task_outcome_reference_ready"] is False
    assert summary["estimand_specific_closeout_ready"] is False
    with (tmp_path / "c1_task_outcome_reference.csv").open(encoding="utf-8") as stream:
        assert list(csv.DictReader(stream))[0]["final_scope"] == "in_scope"
    queue = list(csv.DictReader((tmp_path / "c1_scope_review_queue.csv").open(encoding="utf-8")))
    assert [row["base_task_id"] for row in queue] == ["pending"]


def test_reference_amendment_scores_with_corrected_gt_but_excludes_triggering_submission(tmp_path: Path) -> None:
    canonical, geometry, inventory, gt, amendment = [tmp_path / name for name in ("canonical.csv", "geometry.jsonl", "inventory.csv", "gt.json", "amendment.csv")]
    _csv(canonical, [
        {"project_id": "66", "ls_runtime_task_id": "1", "task_id": "t1", "base_task_id": "b1", "condition": "manual", "worker_id": "w1", "annotation_id": "a1", "canonical_annotation_id": "c1", "dataset_group": "Calibration_core"},
        {"project_id": "66", "ls_runtime_task_id": "1", "task_id": "t1", "base_task_id": "b1", "condition": "manual", "worker_id": "w2", "annotation_id": "a2", "canonical_annotation_id": "c2", "dataset_group": "Calibration_core"},
    ])
    points = [[100, 100], [100, 400], [700, 100], [700, 400]]
    geometry.write_text("\n".join(json.dumps({"canonical_annotation_id": key, "corners_px": points}) for key in ("c1", "c2")), encoding="utf-8")
    _csv(inventory, [{"base_task_id": "b1", "expert_review_status": "latest_human_reviewed", "expert_scope_confirmed": "inscope", "old_manual_scope_raw": ""}])
    gt.write_text("[]", encoding="utf-8")
    _csv(amendment, [{
        "base_task_id": "b1", "reference_status": "reference_corrected", "corrected_points_json": json.dumps(points),
        "triggering_canonical_annotation_ids_json": json.dumps(["c1"]), "reviewed_by": "expert", "reviewed_at": "2026-07-25T00:00:00Z",
    }])
    summary = materialize(canonical, geometry, inventory, gt, tmp_path / "out", reference_amendment=amendment)
    rows = {row["canonical_annotation_id"]: row for row in csv.DictReader((tmp_path / "out" / "c1_gt_quality_evidence.csv").open(encoding="utf-8"))}
    assert summary["reference_status_counts"]["reference_corrected"] == 1
    assert rows["c1"]["quality_evaluable"].lower() == "false"
    assert rows["c1"]["score_reason"] == "submission_informed_reference_revision"
    assert rows["c2"]["quality_evaluable"].lower() == "true"


def test_c1_qgt_uses_uniquely_repaired_orphan_point_geometry(tmp_path: Path) -> None:
    canonical, geometry, inventory, gt = [tmp_path / name for name in ("canonical.csv", "geometry.jsonl", "inventory.csv", "gt.json")]
    _csv(canonical, [{"project_id": "66", "ls_runtime_task_id": "1", "task_id": "t1", "base_task_id": "b1", "condition": "manual", "worker_id": "w1", "annotation_id": "a1", "canonical_annotation_id": "c1", "dataset_group": "Calibration_core"}])
    points = [[100, 100], [100, 400], [700, 100], [700, 400]]
    geometry.write_text(json.dumps({"canonical_annotation_id": "c1", "corners_px": [*points, [900, 250]]}), encoding="utf-8")
    _csv(inventory, [{"base_task_id": "b1", "expert_review_status": "latest_human_reviewed", "expert_scope_confirmed": "inscope", "old_manual_scope_raw": ""}])
    result = [{"type": "keypointlabels", "value": {"x": x / 10.24, "y": y / 5.12}} for x, y in points]
    gt.write_text(json.dumps([{"id": "g1", "project": 70, "data": {"title": "b1.jpg"}, "annotations": [{"id": "ga1", "ground_truth": True, "result": result}]}]), encoding="utf-8")

    materialize(canonical, geometry, inventory, gt, tmp_path / "out")
    row = next(csv.DictReader((tmp_path / "out" / "c1_gt_quality_evidence.csv").open(encoding="utf-8")))

    assert row["quality_evaluable"].lower() == "true"
    assert float(row["iou_to_gt"]) > .99
    assert row["geometry_repair_applied"] == "True"


def test_scope_adjudication_must_bind_the_generated_base_task_queue(tmp_path: Path) -> None:
    canonical, geometry, inventory, gt = [tmp_path / name for name in ("canonical.csv", "geometry.jsonl", "inventory.csv", "gt.json")]
    _csv(canonical, [{"project_id": "66", "ls_runtime_task_id": "1", "task_id": "t1", "base_task_id": "b1", "condition": "manual", "worker_id": "w1", "annotation_id": "a1", "canonical_annotation_id": "c1", "dataset_group": "Calibration_core"}])
    points = [[100, 100], [100, 400], [700, 100], [700, 400]]
    geometry.write_text(json.dumps({"canonical_annotation_id": "c1", "corners_px": points}), encoding="utf-8")
    _csv(inventory, [{"base_task_id": "b1", "expert_review_status": "unreviewed_pool", "expert_scope_confirmed": "", "old_manual_scope_raw": ""}])
    gt.write_text("[]", encoding="utf-8")
    materialize(canonical, geometry, inventory, gt, tmp_path / "audit")
    initial = list(csv.DictReader((tmp_path / "audit" / "c1_scope_initial_review_template.csv").open(encoding="utf-8")))
    assert initial == [{field: "b1" if field == "base_task_id" else "" for field in (
        "base_task_id", "initial_researcher_scope", "initial_reviewed_by", "initial_reviewed_at",
        "initial_protocol_version", "initial_review_source_sha256", "initial_notes",
    )}]
    template = next(csv.DictReader((tmp_path / "audit" / "c1_scope_adjudication_template.csv").open(encoding="utf-8")))
    decision = tmp_path / "scope.csv"
    _csv(decision, [{**template, "final_scope": "oos", "oos_subtype": "unsupported", "reviewed_by": "expert", "reviewed_at": "2026-07-25T00:00:00Z", "source_queue_sha256": "stale"}])
    summary = materialize(canonical, geometry, inventory, gt, tmp_path / "formal", scope_adjudication_csv=decision)
    assert summary["invalid_or_stale_scope_adjudication_count"] == 1
    assert summary["n_pending_contexts"] == 1


def test_scope_workflow_uses_group_direction_and_allows_terminal_unresolved(tmp_path: Path) -> None:
    canonical, geometry, inventory, gt = [tmp_path / name for name in ("canonical.csv", "geometry.jsonl", "inventory.csv", "gt.json")]
    points = [[100, 100], [100, 400], [700, 100], [700, 400]]
    canonical_rows = []
    meta_rows = []
    independence_rows = []
    def add(base: str, worker: str, response: str, *, outside: str = "false", independent: str = "independent") -> None:
        annotation = f"{base}-{worker}"
        canonical_rows.append({
            "project_id": "66", "ls_runtime_task_id": annotation, "task_id": annotation,
            "base_task_id": base, "condition": "manual", "worker_id": worker,
            "annotation_id": annotation, "canonical_annotation_id": annotation,
            "dataset_group": "Calibration_core", "assignment_provenance": "original_assignment",
            "outside_assignment_submission": outside, "duplicate_review_status": "not_required",
        })
        meta_rows.append({"canonical_annotation_id": annotation, "worker_id": worker, "schema_interpretable": "true", "choice_map_json": json.dumps({"scope": [response]})})
        independence_rows.append({"canonical_annotation_id": annotation, "independence_status": independent})
    for worker, response in (("w1", "normal"), ("w2", "normal"), ("w3", "normal"), ("w4", "oos_open_boundary"), ("W014", "oos_open_boundary"), ("w5", "oos_open_boundary"), ("w6", "oos_open_boundary")):
        add("b1", worker, response, outside="true" if worker == "w5" else "false", independent="not_independent" if worker == "w6" else "independent")
    for worker, response in (("w7", "normal"), ("w8", "normal"), ("w9", "oos_open_boundary"), ("w10", "oos_open_boundary")):
        add("b2", worker, response)
    add("b3", "w11", "normal")
    _csv(canonical, canonical_rows)
    meta = tmp_path / "meta.csv"; _csv(meta, meta_rows)
    independence = tmp_path / "independence.csv"; _csv(independence, independence_rows)
    geometry.write_text("\n".join(json.dumps({"canonical_annotation_id": row["canonical_annotation_id"], "corners_px": points}) for row in canonical_rows), encoding="utf-8")
    _csv(inventory, [
        {"base_task_id": "b1", "expert_review_status": "unreviewed_pool", "expert_scope_confirmed": ""},
        {"base_task_id": "b2", "expert_review_status": "unreviewed_pool", "expert_scope_confirmed": ""},
        {"base_task_id": "b3", "expert_review_status": "latest_human_reviewed", "expert_scope_confirmed": "oos_prior_review"},
    ])
    result = [{"type": "keypointlabels", "value": {"x": x / 10.24, "y": y / 5.12}} for x, y in points]
    gt.write_text(json.dumps([{"id": "g1", "project": 66, "data": {"title": "b1.jpg"}, "annotations": [{"id": "ga1", "ground_truth": True, "result": result}]}]), encoding="utf-8")
    initial = tmp_path / "initial.csv"
    _csv(initial, [
        {"base_task_id": "b1", "initial_researcher_scope": "in_scope", "initial_reviewed_by": "researcher", "initial_reviewed_at": "2026-08-01T00:00:00Z", "initial_protocol_version": "scope-v1", "initial_review_source_sha256": "a" * 64, "initial_notes": ""},
        {"base_task_id": "b2", "initial_researcher_scope": "oos", "initial_reviewed_by": "researcher", "initial_reviewed_at": "2026-08-01T00:00:00Z", "initial_protocol_version": "scope-v1", "initial_review_source_sha256": "b" * 64, "initial_notes": ""},
    ])
    out = tmp_path / "candidate"
    materialize(canonical, geometry, inventory, gt, out, scope_initial_review_csv=initial, scope_meta_csv=meta, scope_independence_csv=independence)
    consensus = {row["base_task_id"]: row for row in csv.DictReader((out / "c1_scope_consensus_audit.csv").open(encoding="utf-8"))}
    assert set(consensus) == {"b1", "b2"}
    assert (consensus["b1"]["n_worker_in_scope"], consensus["b1"]["n_worker_oos"], consensus["b1"]["worker_scope_direction"]) == ("3", "2", "in_scope")
    assert consensus["b2"]["worker_scope_direction"] == "no_consensus"
    assert [row["base_task_id"] for row in csv.DictReader((out / "c1_scope_secondary_review_queue.csv").open(encoding="utf-8"))] == ["b2"]
    decisions = list(csv.DictReader((out / "c1_scope_adjudication_template.csv").open(encoding="utf-8")))
    for row in decisions:
        if row["base_task_id"] == "b2":
            row.update({"secondary_scope": "unresolved", "task_final_scope": "unresolved", "reviewed_by": "researcher", "reviewed_at": "2026-08-01T01:00:00Z"})
    decision_path = tmp_path / "final.csv"; _csv(decision_path, decisions)
    summary = materialize(canonical, geometry, inventory, gt, tmp_path / "formal", scope_adjudication_csv=decision_path, scope_initial_review_csv=initial, scope_meta_csv=meta, scope_independence_csv=independence, formal=True)
    assert summary["formal_ready"] is True
    outcomes = {row["base_task_id"]: row for row in csv.DictReader((tmp_path / "formal" / "c1_task_outcome_reference.csv").open(encoding="utf-8"))}
    dispositions = {row["base_task_id"]: row for row in csv.DictReader((tmp_path / "formal" / "c1_task_scope_final_disposition.csv").open(encoding="utf-8"))}
    assert dispositions["b1"]["scope_resolution_status"] == "resolved"
    assert dispositions["b1"]["final_scope_source"] == "worker_researcher_concordant"
    assert outcomes["b1"]["reviewed_by"] == "researcher"
    assert outcomes["b1"]["reviewed_at"] == "2026-08-01T00:00:00Z"
    assert outcomes["b3"]["final_scope"] == "oos"
    assert outcomes["b2"]["scope_resolution_status"] == "terminal_unresolved"
    assert dispositions["b2"]["scope_resolution_status"] == "terminal_unresolved"
    assert dispositions["b3"]["final_scope_source"] == "inventory_latest_human_reviewed"
    assert dispositions["b2"]["final_scope_source"] == "secondary_review_unresolved"
    quality = {row["worker_id"]: row for row in csv.DictReader((tmp_path / "formal" / "c1_gt_quality_evidence.csv").open(encoding="utf-8"))}
    assert quality["w4"]["gt_primary_analysis_eligible"] == "True"


def test_pending_scope_workflow_never_falls_back_to_inventory(tmp_path: Path) -> None:
    canonical, geometry, inventory, gt, initial, meta = [tmp_path / name for name in ("canonical.csv", "geometry.jsonl", "inventory.csv", "gt.json", "initial.csv", "meta.csv")]
    points = [[100, 100], [100, 400], [700, 100], [700, 400]]
    _csv(canonical, [{"project_id": "67", "ls_runtime_task_id": "1", "task_id": "t1", "base_task_id": "b1", "condition": "manual", "planned_project_name": "C1_core_all", "worker_id": "w1", "annotation_id": "a1", "canonical_annotation_id": "c1", "dataset_group": "Calibration_core"}])
    geometry.write_text(json.dumps({"canonical_annotation_id": "c1", "corners_px": points}), encoding="utf-8")
    _csv(inventory, [{"base_task_id": "b1", "expert_review_status": "latest_human_reviewed", "expert_scope_confirmed": "oos"}])
    _csv(initial, [{"base_task_id": "b1", "initial_researcher_scope": "in_scope", "initial_reviewed_by": "researcher", "initial_reviewed_at": "2026-08-01T00:00:00Z", "initial_protocol_version": "scope-v1", "initial_review_source_sha256": "a" * 64, "initial_notes": ""}])
    _csv(meta, [{"canonical_annotation_id": "c1", "worker_id": "w1", "schema_interpretable": "true", "choice_map_json": json.dumps({"scope": ["oos_open_boundary"]})}])
    gt.write_text("[]", encoding="utf-8")

    summary = materialize(canonical, geometry, inventory, gt, tmp_path / "out", scope_initial_review_csv=initial, scope_meta_csv=meta)
    outcome = next(csv.DictReader((tmp_path / "out" / "c1_task_outcome_reference.csv").open(encoding="utf-8")))

    assert summary["n_pending_contexts"] == 1
    assert outcome["final_scope"] == ""
    assert outcome["scope_resolution_status"] == "pending"


def test_scope_workflow_rejects_direct_scope_edit(tmp_path: Path) -> None:
    canonical, geometry, inventory, gt, initial, meta = [tmp_path / name for name in ("canonical.csv", "geometry.jsonl", "inventory.csv", "gt.json", "initial.csv", "meta.csv")]
    points = [[100, 100], [100, 400], [700, 100], [700, 400]]
    _csv(canonical, [{"project_id": "67", "ls_runtime_task_id": str(index), "task_id": "t1", "base_task_id": "b1", "condition": "manual", "planned_project_name": "C1_core_all", "worker_id": f"w{index}", "annotation_id": f"a{index}", "canonical_annotation_id": f"c{index}", "dataset_group": "Calibration_core", "assignment_provenance": "original_assignment", "outside_assignment_submission": "false", "duplicate_review_status": "not_required"} for index in range(1, 4)])
    geometry.write_text("\n".join(json.dumps({"canonical_annotation_id": f"c{index}", "corners_px": points}) for index in range(1, 4)), encoding="utf-8")
    _csv(inventory, [{"base_task_id": "b1", "expert_review_status": "latest_human_reviewed", "expert_scope_confirmed": "oos"}])
    _csv(initial, [{"base_task_id": "b1", "initial_researcher_scope": "in_scope", "initial_reviewed_by": "researcher", "initial_reviewed_at": "2026-08-01T00:00:00Z", "initial_protocol_version": "scope-v1", "initial_review_source_sha256": "a" * 64, "initial_notes": ""}])
    _csv(meta, [{"canonical_annotation_id": f"c{index}", "worker_id": f"w{index}", "schema_interpretable": "true", "choice_map_json": json.dumps({"scope": ["normal"]})} for index in range(1, 4)])
    gt.write_text("[]", encoding="utf-8")
    audit = tmp_path / "audit"
    materialize(canonical, geometry, inventory, gt, audit, scope_initial_review_csv=initial, scope_meta_csv=meta)
    decision = next(csv.DictReader((audit / "c1_scope_adjudication_template.csv").open(encoding="utf-8")))
    decision["task_final_scope"] = "oos"
    decision_path = tmp_path / "edited.csv"; _csv(decision_path, [decision])

    summary = materialize(canonical, geometry, inventory, gt, tmp_path / "out", scope_initial_review_csv=initial, scope_meta_csv=meta, scope_adjudication_csv=decision_path)
    outcome = next(csv.DictReader((tmp_path / "out" / "c1_task_outcome_reference.csv").open(encoding="utf-8")))

    assert summary["invalid_or_stale_scope_adjudication_count"] == 1
    assert outcome["final_scope"] == "in_scope"


def test_partial_scope_adjudication_applies_valid_terminal_rows_without_freezing(tmp_path: Path) -> None:
    canonical, geometry, inventory, gt, initial, meta = [tmp_path / name for name in ("canonical.csv", "geometry.jsonl", "inventory.csv", "gt.json", "initial.csv", "meta.csv")]
    points = [[100, 100], [100, 400], [700, 100], [700, 400]]
    rows, meta_rows = [], []
    for base, response in (("b1", "oos_open_boundary"), ("b2", "oos_open_boundary")):
        for index in range(1, 4):
            identity = f"{base}-{index}"
            rows.append({"project_id": "67", "ls_runtime_task_id": identity, "task_id": identity, "base_task_id": base, "condition": "manual", "planned_project_name": "C1_core_all", "worker_id": f"{base}w{index}", "annotation_id": identity, "canonical_annotation_id": identity, "dataset_group": "Calibration_core", "assignment_provenance": "original_assignment", "outside_assignment_submission": "false", "duplicate_review_status": "not_required"})
            meta_rows.append({"canonical_annotation_id": identity, "worker_id": f"{base}w{index}", "schema_interpretable": "true", "choice_map_json": json.dumps({"scope": [response]})})
    _csv(canonical, rows); _csv(meta, meta_rows)
    geometry.write_text("\n".join(json.dumps({"canonical_annotation_id": row["canonical_annotation_id"], "corners_px": points}) for row in rows), encoding="utf-8")
    _csv(inventory, [{"base_task_id": base, "expert_review_status": "latest_human_reviewed", "expert_scope_confirmed": "in_scope"} for base in ("b1", "b2")])
    _csv(initial, [{"base_task_id": base, "initial_researcher_scope": "in_scope", "initial_reviewed_by": "researcher", "initial_reviewed_at": "2026-08-01T00:00:00Z", "initial_protocol_version": "scope-v1", "initial_review_source_sha256": base * 64, "initial_notes": ""} for base in ("b1", "b2")])
    gt.write_text("[]", encoding="utf-8")
    audit = tmp_path / "audit"
    materialize(canonical, geometry, inventory, gt, audit, scope_initial_review_csv=initial, scope_meta_csv=meta)
    decisions = list(csv.DictReader((audit / "c1_scope_adjudication_template.csv").open(encoding="utf-8")))
    decisions[0].update({"secondary_scope": "oos", "task_final_scope": "oos", "reviewed_by": "researcher", "reviewed_at": "2026-08-01T01:00:00Z"})
    decision_path = tmp_path / "partial.csv"; _csv(decision_path, decisions)

    summary = materialize(canonical, geometry, inventory, gt, tmp_path / "out", scope_initial_review_csv=initial, scope_meta_csv=meta, scope_adjudication_csv=decision_path)
    outcomes = {row["base_task_id"]: row for row in csv.DictReader((tmp_path / "out" / "c1_task_outcome_reference.csv").open(encoding="utf-8"))}

    assert summary["scope_disposition_frozen"] is False
    assert outcomes["b1"]["final_scope"] == "oos"
    assert outcomes["b2"]["final_scope"] == ""


def test_initial_scope_review_uses_all_formal_c1_core_mapping_not_inventory_status(tmp_path: Path) -> None:
    canonical, geometry, inventory, gt, initial = [tmp_path / name for name in ("canonical.csv", "geometry.jsonl", "inventory.csv", "gt.json", "initial.csv")]
    _csv(canonical, [
        {"project_id": "67", "ls_runtime_task_id": "1", "task_id": "b67", "base_task_id": "b67", "condition": "manual", "worker_id": "w1", "annotation_id": "a67", "canonical_annotation_id": "c67", "dataset_group": "Calibration_core", "planned_project_name": "C1_core_all", "planned_inner_id": "67"},
        {"project_id": "67", "ls_runtime_task_id": "2", "task_id": "b68", "base_task_id": "b68", "condition": "manual", "worker_id": "w1", "annotation_id": "a68", "canonical_annotation_id": "c68", "dataset_group": "Calibration_core", "planned_project_name": "C1_core_all", "planned_inner_id": "68"},
    ])
    geometry.write_text("", encoding="utf-8")
    _csv(inventory, [
        {"base_task_id": "b67", "expert_review_status": "unreviewed_pool", "expert_scope_confirmed": ""},
        {"base_task_id": "b68", "expert_review_status": "unreviewed_pool", "expert_scope_confirmed": ""},
    ])
    gt.write_text("[]", encoding="utf-8")
    _csv(initial, [
        {"base_task_id": "b67", "initial_researcher_scope": "in_scope", "initial_reviewed_by": "researcher", "initial_reviewed_at": "2026-08-01T00:00:00Z", "initial_protocol_version": "scope-v1", "initial_review_source_sha256": "a" * 64, "initial_notes": ""},
        {"base_task_id": "b68", "initial_researcher_scope": "oos", "initial_reviewed_by": "researcher", "initial_reviewed_at": "2026-08-01T00:00:00Z", "initial_protocol_version": "scope-v1", "initial_review_source_sha256": "b" * 64, "initial_notes": ""},
    ])

    materialize(canonical, geometry, inventory, gt, tmp_path / "out", scope_initial_review_csv=initial)

    consensus = list(csv.DictReader((tmp_path / "out" / "c1_scope_consensus_audit.csv").open(encoding="utf-8")))
    assert [row["base_task_id"] for row in consensus] == ["b67", "b68"]


def test_scope_consensus_excludes_c1_semi_votes_for_overlapping_core_image(tmp_path: Path) -> None:
    canonical, geometry, inventory, gt, initial, meta = [
        tmp_path / name for name in ("canonical.csv", "geometry.jsonl", "inventory.csv", "gt.json", "initial.csv", "meta.csv")
    ]
    rows, meta_rows = [], []
    for condition, project, response in (
        ("manual", "C1_core_all", "normal"),
        ("semi", "C1_semi", "oos_split_level"),
    ):
        for worker in ("1", "2", "3"):
            annotation = f"{condition}-{worker}"
            rows.append({
                "project_id": "67", "ls_runtime_task_id": annotation, "task_id": "b19", "base_task_id": "b19",
                "condition": condition, "planned_project_name": project, "worker_id": worker,
                "annotation_id": annotation, "canonical_annotation_id": annotation, "dataset_group": "Calibration_core",
                "assignment_provenance": "original_assignment", "outside_assignment_submission": "false",
                "duplicate_review_status": "not_required",
            })
            meta_rows.append({
                "canonical_annotation_id": annotation, "worker_id": worker, "schema_interpretable": "true",
                "choice_map_json": json.dumps({"scope": [response]}),
            })
    _csv(canonical, rows)
    _csv(meta, meta_rows)
    geometry.write_text("", encoding="utf-8")
    _csv(inventory, [{"base_task_id": "b19", "expert_review_status": "unreviewed_pool", "expert_scope_confirmed": ""}])
    gt.write_text("[]", encoding="utf-8")
    _csv(initial, [{
        "base_task_id": "b19", "initial_researcher_scope": "in_scope", "initial_reviewed_by": "researcher",
        "initial_reviewed_at": "2026-08-01T00:00:00Z", "initial_protocol_version": "scope-v1",
        "initial_review_source_sha256": "a" * 64, "initial_notes": "",
    }])

    materialize(canonical, geometry, inventory, gt, tmp_path / "out", scope_initial_review_csv=initial, scope_meta_csv=meta)

    consensus = next(csv.DictReader((tmp_path / "out" / "c1_scope_consensus_audit.csv").open(encoding="utf-8")))
    assert (consensus["n_worker_in_scope"], consensus["n_worker_oos"], consensus["worker_scope_direction"]) == ("3", "0", "in_scope")
