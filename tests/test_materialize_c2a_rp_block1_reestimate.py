import csv
import json
import math
from pathlib import Path

import pytest

import tools.thesis_main.analysis.materialize_c2a_rp_closeout as c2a_closeout
from tools.thesis_main.analysis.build_c2_assignment_manifest_from_c1_gaps import _resolve_fitted_worker_slope_distribution
from tools.thesis_main.analysis.materialize_c2a_rp_block1_reestimate import materialize


def _csv(path: Path, rows: list[dict[str, object]]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_uniform_reference_exclusion_and_unified_width(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bad = "bad"
    common = {"building_id": "b", "risk": "1", "quality": ".8", "task_stratum": "ordinary"}
    c2b = _csv(tmp_path / "c2b.csv", [
        {**common, "evidence_stage": "C2B", "worker_id": "1", "base_task_id": bad, "risk_slope_estimand_eligible": "True"},
        {**common, "evidence_stage": "C2B", "worker_id": "1", "base_task_id": "ok1", "risk_slope_estimand_eligible": "True"},
    ])
    block1 = _csv(tmp_path / "block1.csv", [
        {**common, "evidence_stage": "C2A_RP_BLOCK1", "worker_id": "1", "base_task_id": bad, "risk_slope_estimand_eligible": "False"},
    ])
    profile = _csv(tmp_path / "profile.csv", [{"worker_id": "1", "support": "2"}])
    threshold = tmp_path / "threshold.json"
    threshold.write_text(json.dumps({"thresholds": {"risk_slope_ci_half_width": .1}, "derivation": {"formula_ids": {"risk_slope_ci_half_width": "normal_95_max_unified_slope_sd"}}}), encoding="utf-8")
    closeout = tmp_path / "closeout.json"
    closeout.write_text('{"candidate_only":true}', encoding="utf-8")
    review = tmp_path / "review.json"
    review.write_text(json.dumps({"tasks": [{"base_task_id": bad,
        "decision": "reference_unavailable_for_geometry_estimand", "reviewed_by": "researcher",
        "reviewed_at": None, "review_basis": "direct panorama and reference review",
        "worker_outcomes_used": False,
        "worker_disagreement_used": False}]}), encoding="utf-8")

    def fake_fit(records):
        assert [row["base_task_id"] for row in records] == ["ok1"]
        return {"status": "estimated", "group_slope_mean": -.03, "group_slope_se": .03,
                "between_worker_slope_sd": .04, "slope_model_form": "crossed_random_worker_slope",
                "worker_slopes": {"1": -.02}, "worker_slope_ses": {"1": .01}}

    result = materialize(tmp_path / "out", c2b_evidence=c2b, block1_evidence=block1,
                         base_profile=profile, threshold_path=threshold, c2b_closeout=closeout,
                         reference_review=review, excluded_task_ids={bad}, fit_model=fake_fit)
    assert result["formal_ready"] is True
    assert result["eligible_model_rows"] == 1
    expected = 1.96 * math.sqrt(.03 ** 2 + .01 ** 2)
    assert result["workers"]["1"]["unified_ci_half_width"] == pytest.approx(expected)
    monkeypatch.setattr(c2a_closeout, "_fit_crossed_model", fake_fit)
    closeout = c2a_closeout._actual_worker_slope([{"worker_id": "1", "base_task_id": "ok1"}])
    assert closeout["1"]["ci_half_width"] == pytest.approx(expected)
    evidence = list(csv.DictReader((tmp_path / "out/c2b_plus_c2a_rp_block1_risk_slope_evidence.csv").open(encoding="utf-8")))
    assert all(row["risk_slope_estimand_eligible"] == "False" for row in evidence if row["base_task_id"] == bad)
    assert result["input_sha256"] and result["output_sha256"]


def test_common_slope_uses_group_se_only() -> None:
    model = {"group_slope_mean": -.03, "group_slope_se": .02, "between_worker_slope_sd": 0,
             "slope_model_form": "crossed_common_worker_slope", "worker_slopes": {"1": -.03},
             "worker_slope_ses": {"1": .02}}
    distribution = _resolve_fitted_worker_slope_distribution(model, "1", 4)
    assert distribution["total_sd"] == pytest.approx(.02)
    assert distribution["source"] == "common_group_posterior"
