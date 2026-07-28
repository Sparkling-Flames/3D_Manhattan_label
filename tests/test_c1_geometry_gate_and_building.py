import csv
import json

import pytest

from tools.thesis_main.analysis.c1_c2_mainline import materialize_task_building_binding
from tools.thesis_main.analysis.geometry_consensus.materialize import materialize_geometry_consensus
from tools.thesis_main.analysis.materialize_c1_rehearsal_audits import (
    materialize_effective_task_support,
    materialize_geometry_pool_eligibility,
)


def _csv(path, rows):
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader(); writer.writerows(rows)


def test_effective_support_counts_unique_final_workers_without_expanding_target(tmp_path):
    assignment = tmp_path / "manual_assignment.csv"
    _csv(assignment, [{"worker_id": f"w{i}", "task_id": "t", "base_task_id": "b", "dataset_group": "core"} for i in range(1, 6)])
    canonical = tmp_path / "canonical.csv"
    _csv(canonical, [
        {"canonical_annotation_id": f"a{i}", "worker_id": worker, "base_task_id": "b", "condition": "manual"}
        for i, worker in enumerate(("w1", "w2", "w3", "w4", "w34", "w34"), 1)
    ])
    gate = tmp_path / "gate.csv"
    _csv(gate, [{"canonical_annotation_id": f"a{i}", "geometry_pool_eligible": "true"} for i in range(1, 7)])
    summary = materialize_effective_task_support([assignment], canonical, gate, tmp_path)
    row = next(csv.DictReader((tmp_path / "c1_task_support_deficit.csv").open(encoding="utf-8")))
    assert summary["n_complete"] == 1
    assert row["target_support"] == "5" and row["realized_support"] == "5" and row["support_deficit"] == "0"


def test_geometry_pool_excluded_row_cannot_be_peer_reference(tmp_path):
    canonical = tmp_path / "canonical.csv"
    base = {"project_id": "p", "ls_runtime_task_id": "t", "task_id": "T", "base_task_id": "b", "condition": "manual", "assigned_expected": "true", "outside_assignment_submission": "false", "duplicate_worker_task_submission": "false"}
    _csv(canonical, [{**base, "canonical_annotation_id": "ok", "annotation_id": "1", "worker_id": "w1"}, {**base, "canonical_annotation_id": "excluded", "annotation_id": "2", "worker_id": "w14"}])
    version = tmp_path / "version.csv"; _csv(version, [{"annotation_id": "1", "version_disposition": "selected_canonical"}, {"annotation_id": "2", "version_disposition": "selected_canonical"}])
    structural = tmp_path / "struct.csv"; _csv(structural, [{"canonical_annotation_id": value, "structural_validation_status": "passed"} for value in ("ok", "excluded")])
    reference = tmp_path / "ref.csv"; _csv(reference, [{**base, "final_scope": "in_scope"}])
    independence = tmp_path / "ind.csv"; _csv(independence, [{"canonical_annotation_id": value, "independence_status": "independent"} for value in ("ok", "excluded")])
    outside = tmp_path / "outside.csv"; _csv(outside, [{"canonical_annotation_id": value, "process_eligible_override": "false"} for value in ("ok", "excluded")])
    completion = tmp_path / "completion.csv"; _csv(completion, [{"worker_id": "w1", "completion_status": "completed"}, {"worker_id": "w14", "completion_status": "administrative_exclusion"}])
    summary = materialize_geometry_pool_eligibility(canonical, version, structural, reference, tmp_path, independence_csv=independence, outside_disposition_csv=outside, completion_csv=completion)
    assert summary["n_eligible"] == 1 and summary["n_excluded"] == 1


def test_formal_building_binding_and_candidate_geometry_manifest_fail_closed(tmp_path):
    canonical = tmp_path / "canonical.csv"; _csv(canonical, [{"base_task_id": "b"}])
    registry = tmp_path / "registry.csv"; _csv(registry, [{"base_task_id": "b", "building_id": "B1", "registry_status": "approved", "reviewed_by": "r", "reviewed_at": "t"}])
    assert materialize_task_building_binding(canonical, registry, tmp_path, formal=True)["n_approved"] == 1
    _csv(registry, [{"base_task_id": "b", "building_id": "", "registry_status": "unresolved"}])
    with pytest.raises(ValueError): materialize_task_building_binding(canonical, registry, tmp_path, formal=True)
    geometry = tmp_path / "geometry.jsonl"; geometry.write_text("", encoding="utf-8")
    manifest = tmp_path / "rules.json"; manifest.write_text(json.dumps({"status": "candidate", "interpretation_allowed": False, "thresholds": {"boundary_grid": 16, "similarity_cutoff": .8, "tied_medoid_iou_range_cutoff": .1, "minimum_valid_k": 3}}), encoding="utf-8")
    with pytest.raises(ValueError): materialize_geometry_consensus(geometry, tmp_path, input_status="formal", rule_manifest=manifest)
