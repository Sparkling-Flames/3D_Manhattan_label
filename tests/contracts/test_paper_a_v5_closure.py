from __future__ import annotations

import pandas as pd
import pytest

from tools.thesis_main.analysis.c1_task_adjusted_quality import assess_stage_effect_identifiability
from tools.thesis_main.analysis.paper_a_contracts import validate_record
from tools.thesis_main.analysis.materialize_c1_rehearsal_audits import _materialize_enrollment_registry


def test_policy_candidate_requires_frozen_global_rank() -> None:
    row = {
        "schema_version": "policy_candidate_v2", "worker_id": "w1", "S_G": .7,
        "global_policy_eligible": True, "R_peer_stable": None,
        "R_peer_profile_status": "not_evaluable", "R_LOO_medoid": None,
        "LOO_medoid_status": "not_evaluable", "profile_version": "p",
    }
    with pytest.raises(ValueError, match="global_rank_S_G"):
        validate_record("policy_candidate_v2", row)
    validate_record("policy_candidate_v2", {**row, "global_rank_S_G": 1})


def test_stage_effect_requires_cross_stage_anchor() -> None:
    no_anchor = pd.DataFrame({"base_task_id": ["c1-task", "c2-task"], "stage": ["C1", "C2"]})
    assert assess_stage_effect_identifiability(no_anchor)["status"] == "not_identifiable"
    anchored = pd.DataFrame({"base_task_id": ["anchor", "anchor"], "stage": ["C1", "C2"]})
    assert assess_stage_effect_identifiability(anchored)["status"] == "identifiable"


def test_rehearsal_keeps_registered_in_progress_worker_provisional(tmp_path) -> None:
    completion = [{"worker_id": "late", "completion_status": "in_progress"}]
    registry, summary, _ = _materialize_enrollment_registry(None, completion, tmp_path, formal=False)
    assert registry["late"]["enrollment_batch"] == "original"
    assert summary["status"] == "provisional"
    assert summary["all_registered_workers_terminal"] is False
    registry_csv = tmp_path / "calibration_enrollment_registry.csv"
    registry_csv.write_text(
        "worker_id,enrollment_batch,rolling_activated,admission_status,terminal_status,enrolled_at\n"
        "late,late_entry,true,admitted,in_progress,2026-07-30T00:00:00Z\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="invalid enrollment registry status"):
        _materialize_enrollment_registry(registry_csv, completion, tmp_path, formal=True)
