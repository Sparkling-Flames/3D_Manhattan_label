from __future__ import annotations

import csv
from pathlib import Path

from tools.thesis_main.analysis.materialize_c1_rehearsal_audits import materialize_three_track_worker_state


def _csv(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    fields = fields or list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_peer_five_is_formal_c2_axis_loo_missing_is_not_gate_and_w014_is_excluded(tmp_path: Path) -> None:
    global_csv, loo_csv, structural_csv, completion_csv = [tmp_path / name for name in ("global.csv", "loo.csv", "structural.csv", "completion.csv")]
    peer_csv, eligibility_csv, structural_eb_csv = [tmp_path / name for name in ("peer.csv", "eligibility.csv", "structural_eb.csv")]
    workers = ("1", "14")
    _csv(global_csv, [{"worker_id": worker, "GT_support": 5, "Q_GT_EB": .8, "task_support": 5} for worker in workers])
    _csv(loo_csv, [], ["worker_id", "base_task_id", "loo_analysis_eligible", "loo_medoid_analysis_eligible", "q_LOO_tu"])
    _csv(structural_csv, [{"worker_id": worker, "structural_opportunity_eligible": "true", "failure_attribution": "none"} for worker in workers])
    _csv(completion_csv, [{"worker_id": "1", "completion_status": "completed"}, {"worker_id": "14", "completion_status": "administrative_exclusion"}])
    _csv(structural_eb_csv, [{"worker_id": worker, "F_struct_EB": 0, "F_struct_interval_lower": 0, "F_struct_interval_upper": .1} for worker in workers])
    peer_rows = []
    eligibility_rows = []
    for worker in workers:
        for index in range(5):
            task = f"t{index}"
            peer_rows.append({"schema_version": "peer_worker_task_v2", "base_task_id": task, "condition": "manual", "dataset_group": "core", "task_crowd_structure_status": "unimodal", "worker_id": worker, "canonical_annotation_id": f"{worker}-{task}", "R_peer_task": .8, "peer_count": 4})
            eligibility_rows.append({"schema_version": "assignment_evidence_v2", "canonical_annotation_id": f"{worker}-{task}", "worker_id": worker, "base_task_id": task, "condition": "manual", "assignment_provenance": "original_assignment", "formal_assignment_eligible": True, "gt_primary_analysis_eligible": True, "peer_analysis_eligible": True, "loo_medoid_analysis_eligible": False, "strict_loo_analysis_eligible": False, "structural_opportunity_eligible": True, "time_analysis_eligible": False, "process_eligible": True, "independence_eligible": True, "scope_reference_eligible": True})
    _csv(peer_csv, peer_rows)
    _csv(eligibility_csv, eligibility_rows)
    materialize_three_track_worker_state(global_csv, loo_csv, structural_csv, completion_csv, tmp_path, eligibility_csv=eligibility_csv, peer_csv=peer_csv, structural_eb_csv=structural_eb_csv)
    with (tmp_path / "c1_three_track_worker_state.csv").open(encoding="utf-8", newline="") as stream:
        rows = {row["worker_id"]: row for row in csv.DictReader(stream)}
    assert rows["1"]["peer_task_support"] == "5"
    assert rows["1"]["R_peer_profile_status"] == "estimated"
    assert rows["1"]["LOO_medoid_status"] == "insufficient_support"
    assert rows["1"]["c2_risk_model_eligible"].lower() == "true"
    assert rows["14"]["administratively_eligible"].lower() == "false"
    assert rows["14"]["c2_risk_model_eligible"].lower() == "false"


def test_peer_four_is_descriptive_and_not_c2_eligible(tmp_path: Path) -> None:
    # The v3 contract freezes the inclusion boundary before C1 data are observed.
    from tools.thesis_main.analysis.paper_a_contracts import load_method_contract
    peer = load_method_contract()["peer"]
    assert peer["weak_descriptive_max"] == 4
    assert peer["formal_estimated_min"] == 5
