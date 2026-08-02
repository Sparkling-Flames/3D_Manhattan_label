from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from tools.thesis_main.analysis.materialize_c2a_rp_closeout import materialize
from tools.thesis_main.analysis.paper_a_contracts import METHOD_CONTRACT, load_method_contract, sha256_file


def _csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _case(
    tmp_path: Path,
    *,
    blocks: int,
    assignments: list[dict[str, str]],
    submissions: list[dict[str, str]],
    profile_status: str = "completed",
    history: list[dict[str, str]] | None = None,
    terminal_rows: list[dict[str, str]] | None = None,
) -> tuple[Path, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    plan = _csv(tmp_path / "precision_plan.csv", [
        "worker_id", "additional_blocks", "ordinary_tasks", "stress_tasks",
        "precision_target_met", "routing_eligibility", "unmet_reason",
    ], [{
        "worker_id": "w1", "additional_blocks": str(blocks), "ordinary_tasks": str(blocks),
        "stress_tasks": str(blocks), "precision_target_met": "false" if blocks else "true",
        "routing_eligibility": "uncertain_fallback_global" if blocks else "eligible",
        "unmet_reason": "target_not_met_at_frozen_cap" if blocks else "",
    }])
    assignment = _csv(tmp_path / "assignment.csv", ["worker_id", "task_id", "base_task_id", "task_stratum", "task_support_after"], assignments)
    history_path = _csv(tmp_path / "history.csv", ["worker_id", "task_id", "base_task_id"], history or [])
    submission = _csv(tmp_path / "submissions.csv", ["worker_id", "task_id"], submissions)
    profile = _csv(tmp_path / "profile.csv", ["worker_id", "profile_version", "cohort_id", "completion_status"], [{
        "worker_id": "w1", "profile_version": "p1", "cohort_id": "c1", "completion_status": profile_status,
    }])
    c2b = tmp_path / "c2b.json"
    c2b.write_text(json.dumps({
        "schema_version": "c2b_closeout_v2", "artifact_role": "C2B_BATCH_A_CLOSEOUT_FROZEN",
        "contract_role": "generated_subordinate", "formal_ready": True, "c2b_closeout_ready": True,
        "method_contract_version": load_method_contract()["contract_version"],
        "method_contract_sha256": sha256_file(METHOD_CONTRACT), "profile_version": "p1", "cohort_id": "c1",
    }), encoding="utf-8")
    terminal = None
    if terminal_rows is not None:
        terminal = _csv(tmp_path / "terminal.csv", ["worker_id", "task_id", "terminal_status", "missing_reason"], terminal_rows)
    output = tmp_path / "closeout.json"
    materialize(plan, assignment, history_path, submission, profile, c2b, output, terminal_disposition_csv=terminal)
    return output, profile


def test_zero_task_c2a_rp_closeout_is_formal(tmp_path: Path) -> None:
    output, _ = _case(tmp_path, blocks=0, assignments=[], submissions=[])
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "c2a_rp_closeout_v1"
    assert payload["artifact_role"] == "C2A_RP_CLOSEOUT_FROZEN"
    assert payload["formal_ready"] is True
    assert payload["n_workers_assigned"] == 0
    assert payload["n_assignments"] == 0
    assert payload["closure_reason"] == "all_precision_targets_met_or_unsupported_adjustments_fallback"
    assert payload["C2_A_RP_CLOSED"] is True


def test_partial_c2a_rp_missing_with_profile_terminal_status_closes(tmp_path: Path) -> None:
    output, _ = _case(
        tmp_path, blocks=1,
        assignments=[
            {"worker_id": "w1", "task_id": "o1", "base_task_id": "o1", "task_stratum": "ordinary", "task_support_after": "1"},
            {"worker_id": "w1", "task_id": "s1", "base_task_id": "s1", "task_stratum": "stress", "task_support_after": "1"},
        ],
        submissions=[{"worker_id": "w1", "task_id": "o1"}],
        profile_status="closed_partial_usable",
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["C2_A_RP_CLOSED"] is True
    assert payload["n_workers_completed"] == 0
    assert payload["n_workers_partial"] == 1
    assert payload["n_missing"] == 1


def test_c2a_rp_missing_without_terminal_disposition_fails(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="terminal disposition"):
        _case(
            tmp_path, blocks=1,
            assignments=[
                {"worker_id": "w1", "task_id": "o1", "base_task_id": "o1", "task_stratum": "ordinary", "task_support_after": "1"},
                {"worker_id": "w1", "task_id": "s1", "base_task_id": "s1", "task_stratum": "stress", "task_support_after": "1"},
            ],
            submissions=[], profile_status="in_progress",
        )


def test_c2a_rp_rejects_orphan_terminal_disposition(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown worker"):
        _case(
            tmp_path, blocks=1,
            assignments=[
                {"worker_id": "w1", "task_id": "o1", "base_task_id": "o1", "task_stratum": "ordinary", "task_support_after": "1"},
                {"worker_id": "w1", "task_id": "s1", "base_task_id": "s1", "task_stratum": "stress", "task_support_after": "1"},
            ],
            submissions=[], profile_status="in_progress",
            terminal_rows=[{"worker_id": "w2", "task_id": "", "terminal_status": "nonstarter", "missing_reason": "wrong_worker"}],
        )


def test_c2a_rp_rejects_six_tasks_and_support_over_cap(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="normative cap"):
        _case(tmp_path / "six", blocks=3, assignments=[], submissions=[])

    case = tmp_path / "support"
    case.mkdir()
    with pytest.raises(ValueError, match="support"):
        _case(
            case, blocks=1,
            assignments=[
                {"worker_id": "w1", "task_id": "new", "base_task_id": "new", "task_stratum": "ordinary", "task_support_after": "3"},
                {"worker_id": "w1", "task_id": "stress", "base_task_id": "stress", "task_stratum": "stress", "task_support_after": "1"},
            ],
            submissions=[], profile_status="closed_partial_usable",
            history=[
                {"worker_id": "w2", "task_id": "new", "base_task_id": "old-1"},
                {"worker_id": "w3", "task_id": "new", "base_task_id": "old-2"},
            ],
        )
