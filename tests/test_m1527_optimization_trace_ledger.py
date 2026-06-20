import json

import pytest

from tools.paper_a_manhattan.run_m1527_optimization_trace_ledger import (
    SCHEMA_VERSION,
    record_manual_review,
    seed_ledger,
)


def test_trace_ledger_seed_and_atomic_manual_review(tmp_path):
    path = tmp_path / "optimization_trace_ledger.json"
    seed_ledger(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == SCHEMA_VERSION
    assert list(payload["optimization_path"]) == ["m15_22", "m15_26", "m15_27_1"]
    assert payload["manual_visual_review"]["status"] == "pending"
    assert all(not row["automatic_fix_claimed"] for row in payload["optimization_path"].values())
    assert not path.with_suffix(".json.tmp").exists()

    record_manual_review(
        path,
        comparative_verdict="m15_27_better",
        selected_candidate_id="m1527_candidate_0094",
        manual_ls_trial_recommended=True,
        notes="visual comparison recorded",
        reviewer="expert",
        reviewed_at="2026-06-20T12:00:00+00:00",
    )
    reviewed = json.loads(path.read_text(encoding="utf-8"))["manual_visual_review"]
    assert reviewed == {
        "status": "reviewed",
        "comparative_verdict": "m15_27_better",
        "selected_candidate_id": "m1527_candidate_0094",
        "manual_ls_trial_recommended": True,
        "notes": "visual comparison recorded",
        "reviewer": "expert",
        "reviewed_at": "2026-06-20T12:00:00+00:00",
    }
    assert not path.with_suffix(".json.tmp").exists()

    with pytest.raises(ValueError, match="unknown candidate"):
        record_manual_review(
            path,
            comparative_verdict="inconclusive",
            selected_candidate_id="not_a_candidate",
            manual_ls_trial_recommended=False,
            notes="",
        )
    with pytest.raises(FileExistsError):
        seed_ledger(path)
