from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.thesis_main.analysis.prescreen_gold_status_audit import build_gold_status_audit, main


def _write_csv(path: Path, rows: list[dict]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return path


def _alignment_row(
    task_id: str,
    *,
    dataset_group: str = "PreScreen_manual",
    condition: str = "manual",
    scope: str = "in_scope",
    source: str = "final_gold",
    gold_status: str = "ready",
    validation_level: str = "final_gold_ref_only",
    gold_source: str = "final_gold",
    gold_task: str = "task_id:gold",
    alignment_status: str = "aligned_ready",
) -> dict:
    return {
        "task_id": task_id,
        "project_id": "1",
        "dataset_group": dataset_group,
        "condition": condition,
        "image_id": f"image_{task_id}",
        "base_image_key": f"base_{task_id}",
        "task_final_scope": scope,
        "task_scope_adjudication_source": source,
        "geometry_gold_status": gold_status,
        "geometry_gold_validation_level": validation_level,
        "geometry_gold_source": gold_source,
        "geometry_gold_task_id": gold_task,
        "geometry_alignment_status": alignment_status,
        "dry_run": "True",
        "notes": "",
    }


def _run(tmp_path: Path, rows: list[dict]):
    alignment = _write_csv(tmp_path / "alignment.csv", rows)
    return build_gold_status_audit(alignment)


def test_synthetic_source_gt_checked_is_ready_for_alignment_and_undercoverage(tmp_path: Path) -> None:
    rows, summary = _run(
        tmp_path,
        [
            _alignment_row(
                "synth",
                dataset_group="PreScreen_semi",
                condition="semi",
                source="synthetic_asset_expert_review",
                validation_level="source_gt_annotation_count_checked",
                gold_source="export_label_groudTruth",
                gold_task="2752",
            )
        ],
    )

    row = rows[0]
    assert row["gold_reference_role"] == "synthetic_source_gt_checked"
    assert row["gold_status_for_alignment"] == "ready_for_alignment"
    assert row["gold_status_for_undercoverage"] == "ready_for_undercoverage_audit"
    assert row["gold_ambiguity_flag"] is False
    assert row["manual_review_required"] is False
    assert summary["gold_ambiguity_flag_count"] == 0


def test_manual_final_gold_ref_only_requires_review(tmp_path: Path) -> None:
    rows, _summary = _run(tmp_path, [_alignment_row("manual")])

    row = rows[0]
    assert row["gold_reference_role"] == "manual_final_gold_ref"
    assert row["gold_status_for_alignment"] == "reference_only_unvalidated"
    assert row["gold_status_for_undercoverage"] == "reference_only_needs_review"
    assert row["gold_ambiguity_flag"] is True
    assert row["gold_ambiguity_reason"] == "final_gold_ref_only"
    assert row["manual_review_required"] is True


def test_oos_gold_status_is_not_applicable(tmp_path: Path) -> None:
    rows, _summary = _run(
        tmp_path,
        [
            _alignment_row(
                "oos",
                dataset_group="PreScreen_oos",
                condition="oos",
                scope="oos_geometry",
                gold_status="not_applicable",
                validation_level="not_validated",
                gold_source="",
                gold_task="",
                alignment_status="excluded_oos",
            )
        ],
    )

    row = rows[0]
    assert row["gold_reference_role"] == "oos_not_applicable"
    assert row["gold_status_for_alignment"] == "not_applicable"
    assert row["gold_status_for_undercoverage"] == "not_applicable"
    assert row["manual_review_required"] is False


def test_unresolved_or_unknown_gold_is_deferred_and_requires_review(tmp_path: Path) -> None:
    rows, _summary = _run(
        tmp_path,
        [
            _alignment_row(
                "unknown",
                scope="unknown_gold",
                gold_status="deferred",
                validation_level="not_validated",
                gold_source="",
                gold_task="",
                alignment_status="deferred",
            )
        ],
    )

    row = rows[0]
    assert row["gold_reference_role"] == "unresolved_not_applicable"
    assert row["gold_status_for_alignment"] == "deferred"
    assert row["gold_status_for_undercoverage"] == "not_ready"
    assert row["manual_review_required"] is True


def test_missing_duplicate_invalid_gold_are_not_ready(tmp_path: Path) -> None:
    rows, _summary = _run(
        tmp_path,
        [
            _alignment_row("missing", gold_status="missing", validation_level="not_validated", gold_source="", gold_task="", alignment_status="missing_gold"),
            _alignment_row("duplicate", gold_status="duplicate", validation_level="not_validated", alignment_status="duplicate_gold"),
            _alignment_row("invalid", gold_status="invalid_annotation_count", validation_level="not_validated", alignment_status="invalid_annotation_count"),
        ],
    )

    assert [row["gold_status_for_alignment"] for row in rows] == ["missing", "duplicate", "invalid"]
    assert all(row["gold_status_for_undercoverage"] == "not_ready" for row in rows)
    assert all(row["gold_ambiguity_flag"] is True for row in rows)
    assert all(row["manual_review_required"] is True for row in rows)


def test_mirror_mismatch_is_ambiguous(tmp_path: Path) -> None:
    rows, _summary = _run(tmp_path, [_alignment_row("mirror", alignment_status="mirror_gold_mismatch")])

    row = rows[0]
    assert row["gold_status_for_alignment"] == "ambiguous"
    assert row["gold_ambiguity_flag"] is True
    assert row["gold_ambiguity_reason"] == "mirror_gold_mismatch"
    assert row["manual_review_required"] is True


def test_cli_writes_only_gold_status_sidecar_outputs(tmp_path: Path) -> None:
    alignment = _write_csv(tmp_path / "alignment.csv", [_alignment_row("manual")])
    out = tmp_path / "out"

    assert main(["--alignment-csv", str(alignment), "--output-dir", str(out)]) == 0

    assert {p.name for p in out.iterdir()} == {
        "prescreen_gold_status_audit.csv",
        "prescreen_gold_status_summary.json",
    }
    assert not any(
        any(token in p.name.lower() for token in ("geometry_score", "admission", "r0", "r_u", "wmax", "w_max", "routing", "c1", "handoff", "reliability"))
        for p in out.iterdir()
    )
    rows = list(csv.DictReader((out / "prescreen_gold_status_audit.csv").open(encoding="utf-8-sig")))
    assert rows
    assert not any("score" in key.lower() for row in rows for key in row)
    summary = json.loads((out / "prescreen_gold_status_summary.json").read_text(encoding="utf-8"))
    assert summary["dry_run"] is True
    assert summary["forbidden_outputs_generated"] is False
    assert summary["forbidden_metric_field_count"] == 0
