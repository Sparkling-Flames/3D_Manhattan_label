import json
from pathlib import Path

from tools.paper_a_manhattan.run_hrc_c6_5a_6_2_manual_selection_ledger import (
    SELECTED_CANDIDATE,
    build_payload,
    run,
)


def test_manual_selection_ledger_records_existing_review_only_selection():
    payload = build_payload()
    source = json.loads(
        Path(payload["source_artifact"]["path"]).read_text(encoding="utf-8")
    )
    assert SELECTED_CANDIDATE in {
        row["candidate_id"] for row in source["candidate_set"]
    }
    assert payload["selected_candidate"] == SELECTED_CANDIDATE
    assert payload["selected_y_step"] == 0.75
    assert payload["selection_scope"] == (
        "manual_audit_preference_only_not_automatic_acceptance"
    )
    assert payload["safety_boundary"] == {
        "audit_only": True,
        "accepted": False,
        "downstream_recommendation": False,
        "candidate_preference_authorized": False,
        "annotation_patch_generated": False,
        "annotation_writeback": False,
    }
    assert set(payload["status_boundaries"].values()) == {"blocked"}
    assert payload["remaining_blockers"] == [
        "candidate-specific C4 evidence absent",
        "2369 manual sidecar pending",
        "C6.5b remains blocked",
    ]


def test_manual_selection_ledger_writes_json_and_summary(tmp_path):
    paths = run(tmp_path)
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    summary = paths["markdown"].read_text(encoding="utf-8")
    assert payload["selected_candidate"] == SELECTED_CANDIDATE
    assert "manual selected for review only" in summary
    assert "C6.5b/C3/C7/C9/C10: `blocked`" in summary
