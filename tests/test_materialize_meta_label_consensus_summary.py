from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from tools.materialize_meta_label_consensus_summary import build_summary


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "materialize_meta_label_consensus_summary.py"


def test_build_summary_demotes_default_aliases_and_uses_registry() -> None:
    quality = pd.DataFrame(
        [
            {
                "task_id": "101",
                "annotator_id": "u1",
                "dataset_group": "Calibration_manual",
                "difficulty": "trivial;occlusion",
                "model_issue_primary": "",
                "model_issue": "acceptable",
            },
            {
                "task_id": "101",
                "annotator_id": "u2",
                "dataset_group": "Calibration_manual",
                "difficulty": "occlusion",
                "model_issue_primary": "underextend",
                "model_issue": "acceptable;underextend",
            },
            {
                "task_id": "102",
                "annotator_id": "u3",
                "dataset_group": "",
                "difficulty": "",
                "model_issue_primary": "",
                "model_issue": "",
            },
        ]
    )
    registry = pd.DataFrame(
        [
            {"task_id": "101", "base_task_id": "base101", "dataset_group": "Calibration_manual"},
            {"task_id": "102", "base_task_id": "base102", "dataset_group": "Validation_semi"},
        ]
    )

    summary, audit = build_summary(quality, registry)
    by_task = summary.set_index("task_id")

    assert by_task.loc["101", "base_task_id"] == "base101"
    assert by_task.loc["101", "base_task_id_source"] == "base_task_id_registry"
    assert by_task.loc["101", "n_unique_annotators"] == 2
    assert by_task.loc["101", "n_duplicate_annotator_rows"] == 0
    assert by_task.loc["101", "n_difficulty_conflicted_annotators"] == 0
    assert by_task.loc["101", "n_model_issue_conflicted_annotators"] == 0
    assert by_task.loc["101", "difficulty_consensus"] == "occlusion"
    assert by_task.loc["101", "model_issue_consensus"] == "underextend"
    assert by_task.loc["101", "difficulty_consensus_confidence"] == 1.0
    assert by_task.loc["101", "model_issue_consensus_confidence"] == 0.5
    assert by_task.loc["101", "consensus_method"] == "majority_token_presence_demote_default_after_task_annotator_dedup"
    assert by_task.loc["101", "consensus_version"] == "v2"
    assert by_task.loc["101", "secondary_difficulty_labels"] == ""

    assert by_task.loc["102", "dataset_group"] == "Validation_semi"
    assert by_task.loc["102", "dataset_group_source"] == "dataset_group_registry"
    assert by_task.loc["102", "difficulty_consensus"] == "none"
    assert bool(by_task.loc["102", "difficulty_defaulted"]) is True
    assert by_task.loc["102", "model_issue_consensus"] == "acceptable"
    assert bool(by_task.loc["102", "model_issue_defaulted"]) is True

    assert audit["n_tasks"] == 2
    assert audit["n_tasks_difficulty_defaulted"] == 1
    assert audit["n_tasks_model_issue_defaulted"] == 1
    assert audit["n_tasks_dataset_group_conflict"] == 0
    assert audit["n_tasks_base_task_id_conflict"] == 0
    assert audit["n_tasks_duplicate_annotator_rows"] == 0
    assert audit["n_tasks_difficulty_conflicted_annotators"] == 0
    assert audit["n_tasks_model_issue_conflicted_annotators"] == 0


def test_build_summary_audits_conflicts_and_can_fail_fast() -> None:
    quality = pd.DataFrame(
        [
            {
                "task_id": "301",
                "annotator_id": "u1",
                "dataset_group": "Validation_semi",
                "base_task_id": "base301a",
                "difficulty": "occlusion",
                "model_issue": "acceptable",
            },
            {
                "task_id": "301",
                "annotator_id": "u2",
                "dataset_group": "Validation_OOD",
                "base_task_id": "base301b",
                "difficulty": "occlusion",
                "model_issue": "acceptable",
            },
        ]
    )

    summary, audit = build_summary(quality)
    by_task = summary.set_index("task_id")
    assert bool(by_task.loc["301", "dataset_group_conflict"]) is True
    assert by_task.loc["301", "dataset_group_conflict_values"] == "Validation_semi;Validation_OOD"
    assert bool(by_task.loc["301", "base_task_id_conflict"]) is True
    assert by_task.loc["301", "base_task_id_conflict_values"] == "base301a;base301b"
    assert audit["n_tasks_dataset_group_conflict"] == 1
    assert audit["n_tasks_base_task_id_conflict"] == 1

    with pytest.raises(ValueError, match="conflicts detected"):
        build_summary(quality, fail_on_conflict=True)


def test_build_summary_tracks_duplicate_annotator_rows() -> None:
    quality = pd.DataFrame(
        [
            {
                "task_id": "302",
                "annotator_id": "u1",
                "dataset_group": "Validation_semi",
                "base_task_id": "base302",
                "difficulty": "occlusion",
                "model_issue": "acceptable",
            },
            {
                "task_id": "302",
                "annotator_id": "u1",
                "dataset_group": "Validation_semi",
                "base_task_id": "base302",
                "difficulty": "occlusion",
                "model_issue": "acceptable",
            },
        ]
    )

    summary, audit = build_summary(quality)
    by_task = summary.set_index("task_id")
    assert by_task.loc["302", "n_unique_annotators"] == 1
    assert by_task.loc["302", "n_duplicate_annotator_rows"] == 1
    assert audit["n_tasks_duplicate_annotator_rows"] == 1
    assert by_task.loc["302", "difficulty_consensus"] == "occlusion"
    assert by_task.loc["302", "difficulty_consensus_confidence"] == 1.0


def test_build_summary_dedups_by_annotator_and_excludes_conflicted_vote_unit() -> None:
    quality = pd.DataFrame(
        [
            {
                "task_id": "303",
                "annotator_id": "u1",
                "dataset_group": "Validation_semi",
                "base_task_id": "base303",
                "difficulty": "occlusion",
                "model_issue": "acceptable",
            },
            {
                "task_id": "303",
                "annotator_id": "u1",
                "dataset_group": "Validation_semi",
                "base_task_id": "base303",
                "difficulty": "reflection",
                "model_issue": "acceptable",
            },
            {
                "task_id": "303",
                "annotator_id": "u2",
                "dataset_group": "Validation_semi",
                "base_task_id": "base303",
                "difficulty": "reflection",
                "model_issue": "acceptable",
            },
        ]
    )

    summary, audit = build_summary(quality)
    by_task = summary.set_index("task_id")
    assert by_task.loc["303", "n_unique_annotators"] == 2
    assert by_task.loc["303", "n_duplicate_annotator_rows"] == 1
    assert by_task.loc["303", "n_difficulty_conflicted_annotators"] == 1
    assert by_task.loc["303", "difficulty_consensus"] == "reflection"
    assert by_task.loc["303", "difficulty_consensus_confidence"] == 1.0
    assert audit["n_tasks_difficulty_conflicted_annotators"] == 1


def test_cli_materializes_summary_and_audit(tmp_path: Path) -> None:
    quality_csv = tmp_path / "quality.csv"
    registry_csv = tmp_path / "registry.csv"
    output_csv = tmp_path / "meta_label_consensus_summary_v1.csv"
    audit_json = tmp_path / "meta_label_consensus_summary_v1.audit.json"

    pd.DataFrame(
        [
            {
                "task_id": "201",
                "annotator_id": "u1",
                "dataset_group": "Validation_semi",
                "difficulty": "reflection;occlusion",
                "model_issue_primary": "corner_drift",
                "model_issue": "corner_drift",
            },
            {
                "task_id": "201",
                "annotator_id": "u2",
                "dataset_group": "Validation_semi",
                "difficulty": "occlusion",
                "model_issue_primary": "acceptable",
                "model_issue": "acceptable",
            },
        ]
    ).to_csv(quality_csv, index=False)

    pd.DataFrame(
        [{"task_id": "201", "base_task_id": "base201", "dataset_group": "Validation_semi"}]
    ).to_csv(registry_csv, index=False)

    subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--quality-csv",
            str(quality_csv),
            "--registry-csv",
            str(registry_csv),
            "--output-csv",
            str(output_csv),
            "--output-audit-json",
            str(audit_json),
        ],
        check=True,
    )

    out_df = pd.read_csv(output_csv, dtype=str).fillna("")
    out = out_df.set_index("task_id")
    assert out.loc["201", "base_task_id"] == "base201"
    assert out.loc["201", "difficulty_consensus"] == "occlusion"
    assert out.loc["201", "model_issue_consensus"] == "corner_drift"

    audit = json.loads(audit_json.read_text(encoding="utf-8"))
    assert audit["n_tasks"] == 1


def test_cli_fail_on_conflict_exits_nonzero(tmp_path: Path) -> None:
    quality_csv = tmp_path / "quality.csv"
    output_csv = tmp_path / "meta_label_consensus_summary_v1.csv"

    pd.DataFrame(
        [
            {
                "task_id": "401",
                "annotator_id": "u1",
                "dataset_group": "Validation_semi",
                "base_task_id": "base401a",
                "difficulty": "occlusion",
                "model_issue": "acceptable",
            },
            {
                "task_id": "401",
                "annotator_id": "u2",
                "dataset_group": "Validation_OOD",
                "base_task_id": "base401b",
                "difficulty": "occlusion",
                "model_issue": "acceptable",
            },
        ]
    ).to_csv(quality_csv, index=False)

    with pytest.raises(subprocess.CalledProcessError):
        subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--quality-csv",
                str(quality_csv),
                "--output-csv",
                str(output_csv),
                "--fail-on-conflict",
            ],
            check=True,
        )
