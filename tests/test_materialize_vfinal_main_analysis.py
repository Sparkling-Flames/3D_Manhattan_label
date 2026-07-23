import csv
import hashlib
import json
import sys
from pathlib import Path

import pytest

from tools.thesis_main.analysis.materialize_vfinal_main_analysis import (
    analyze_t1,
    analyze_v1,
    main,
    verify_formal_inputs,
)


def _t1(pair="p1", disposition="included", source="p1", risk="ordinary"):
    base = {
        "analysis_unit_pair_id": pair,
        "pair_analysis_disposition": disposition,
        "source_pair_id": source,
        "risk_assist": risk,
        "image_id": "img1",
        "quality_evaluable": "true" if disposition == "included" else "false",
    }
    return [
        {**base, "worker_id": f"{pair}-m", "condition": "manual", "delivery_adjusted_quality": "0", "structurally_valid": "false",
         "iou_to_gt": "0", "row_failure_attribution": "worker_caused_structural_failure",
         "active_time_seconds": "12", "active_time_integrity_status": "exact_annotation_valid"},
        {**base, "worker_id": f"{pair}-s", "condition": "semi", "delivery_adjusted_quality": "0.8", "structurally_valid": "true",
         "iou_to_gt": "0.8", "row_failure_attribution": "none",
         "active_time_seconds": "8", "active_time_integrity_status": "exact_annotation_valid"},
    ]


def _v1(task, arm="strong_global", risk="ordinary", status="resolved", quality="0.8", **extra):
    return {
        "task_id": task, "original_task_id": task, "resolved_task_id": task,
        "policy_arm": arm, "risk_route": risk, "analysis_disposition": "included",
        "itt_included": "true", "policy_failure": "false", "policy_terminal_status": status,
        "delivery_adjusted_quality": quality, "iou_to_gt": quality,
        "k_used": "2", "active_time_seconds": "10", "completion_time_seconds": "20",
        **extra,
    }


def test_t1_keeps_worker_failure_zero_and_excludes_external_censor():
    rows = _t1()
    rows += _t1("p2", "administrative_censor", risk="stress_assist")
    pairs, summary, audit = analyze_t1(rows)
    assert pairs[0]["delivery_adjusted_quality_diff_semi_minus_manual"] == 0.8
    assert pairs[0]["structurally_valid_diff_semi_minus_manual"] == 1.0
    assert pairs[0]["valid_only_iou_diff_semi_minus_manual"] == ""
    assert len(summary) == 1
    assert audit["pair_disposition_counts"] == {"administrative_censor": 1, "included": 1}
    assert audit["active_time_pair_coverage"] == 1.0


def test_t1_requires_exactly_one_manual_and_one_semi():
    rows = _t1()
    rows[1]["condition"] = "manual"
    with pytest.raises(ValueError, match="exactly one Manual and one Semi"):
        analyze_t1(rows)


def test_v1_policy_failure_stays_in_itt_at_zero_and_resolved_only_is_separate():
    rows = [
        _v1("g1"),
        _v1("g2", status="unresolved", quality="0", policy_failure="true", iou_to_gt=""),
        _v1("g3", risk="stress_route", quality="0.6"),
        _v1("f1", arm="full_integrated", risk="stress_route", quality="0.9"),
    ]
    tasks, summary, standardized, audit = analyze_v1(rows)
    g = next(row for row in summary if row["policy_arm"] == "strong_global")
    assert g["n_itt"] == 2
    assert g["delivery_adjusted_quality_mean"] == 0.4
    assert g["resolved_only_quality_mean"] == 0.8
    assert g["policy_failure_rate"] == 0.5
    assert len(tasks) == 4
    assert any(row["standardization"] == "design_50_50" for row in standardized)
    assert audit["n_administrative_censor"] == 0


def test_v1_administrative_censor_not_in_quality_denominator():
    censored = _v1("g2", quality="")
    censored.update(analysis_disposition="administrative_censor", itt_included="false", iou_to_gt="")
    _, summary, _, audit = analyze_v1([_v1("g1"), censored])
    assert summary[0]["n_itt"] == 1
    assert summary[0]["delivery_adjusted_quality_mean"] == 0.8
    assert audit["n_administrative_censor"] == 1


def test_v1_design_production_and_scenario_standardization():
    rows = [
        _v1("g1", quality="1"),
        _v1("g2", risk="stress_route", quality="0"),
        _v1("f1", arm="full_integrated", quality="0.6"),
        _v1("f2", arm="full_integrated", risk="stress_route", quality="0.2"),
    ]
    weights = [
        {"risk_route": "ordinary", "weight": "0.8", "source_sha256": "a" * 64},
        {"risk_route": "stress_route", "weight": "0.2", "source_sha256": "a" * 64},
    ]
    _, _, standardized, _ = analyze_v1(rows, weights)
    design = next(r for r in standardized if r["policy_arm"] == "strong_global" and r["standardization"] == "design_50_50")
    production = next(r for r in standardized if r["policy_arm"] == "strong_global" and r["standardization"] == "production")
    assert design["delivery_adjusted_quality_mean"] == 0.5
    assert production["delivery_adjusted_quality_mean"] == 0.8

    _, _, scenarios, _ = analyze_v1(rows)
    assert {r["standardization"] for r in scenarios} >= {
        "scenario_80_20", "scenario_60_40", "scenario_50_50", "scenario_30_70"
    }


def test_formal_manifest_and_input_hashes_fail_closed_when_stale(tmp_path: Path):
    source = tmp_path / "resolved.csv"
    source.write_text("x\n1\n", encoding="utf-8")
    freeze = tmp_path / "freeze.json"
    rule = tmp_path / "rule.json"
    freeze.write_text(json.dumps({"status": "frozen"}), encoding="utf-8")
    rule.write_text(json.dumps({"status": "frozen"}), encoding="utf-8")
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    verified = verify_formal_inputs(
        source, freeze, rule,
        input_sha256=digest(source),
        freeze_manifest_sha256=digest(freeze),
        rule_manifest_sha256=digest(rule),
    )
    assert verified["input_sha256"] == digest(source)
    with pytest.raises(ValueError, match="input SHA256 mismatch"):
        verify_formal_inputs(
            source, freeze, rule,
            input_sha256="0" * 64,
            freeze_manifest_sha256=digest(freeze),
            rule_manifest_sha256=digest(rule),
        )


def test_dryrun_prints_audit_without_writing_output(tmp_path: Path, monkeypatch, capsys):
    source = tmp_path / "resolved.csv"
    rows = _t1() + _t1("p2")
    with source.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    output = tmp_path / "must_not_exist"
    monkeypatch.setattr(sys, "argv", [
        "materialize_vfinal_main_analysis.py", "--stage", "T1",
        "--resolved-input-csv", str(source), "--output-dir", str(output),
        "--input-status", "dryrun",
    ])
    main()
    assert json.loads(capsys.readouterr().out)["input_status"] == "dryrun"
    assert not output.exists()
