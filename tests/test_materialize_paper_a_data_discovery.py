import csv
import json
from pathlib import Path

import pytest

from tools.thesis_main.analysis.materialize_paper_a_data_discovery import (
    RESULT_FIELDS,
    cluster_inference,
    materialize,
)


def rows(path: Path):
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


@pytest.fixture(scope="module")
def output(tmp_path_factory):
    out = tmp_path_factory.mktemp("paper_a_discovery")
    summary = materialize(out)
    return out, summary


def test_complete_identity_and_join_inventory(output):
    out, summary = output
    assert summary == {"submissions": 2501, "workers": 26, "reviews": 574, "results": 28}
    submissions = rows(out / "submission_fact.csv")
    assert len({row["worker_id"] for row in submissions}) == 26
    assert sum(row["worker_id"] == "14" and row["stage"] == "C1" for row in submissions) == 32
    assert {"19", "21", "26"} <= {row["worker_id"] for row in submissions}
    assert {"n_corners", "formal_eligible_unified", "formal_eligibility_basis"} <= set(submissions[0])
    audits = {row["check"]: row for row in rows(out / "join_coverage_audit.csv")}
    for check in ("language_identity_split", "duplicate_annotation_identity", "submission_to_task_unjoined", "submission_to_profile_unjoined"):
        assert audits[check]["observed"] == "0"
        assert audits[check]["status"] == "pass"


def test_stage_specific_formal_sensitivity_is_populated(output):
    out, _ = output
    submissions = rows(out / "submission_fact.csv")
    expected = {"P1": 1481, "C1": 627, "C2-B": 160, "C2A-RP-B1": 40, "C2A-RP-B2": 40}
    observed = {stage: sum(row["stage"] == stage and row["formal_eligible_unified"] == "true" for row in submissions) for stage in expected}
    assert observed == expected
    evidence = rows(out / "association_matrix.csv")
    sensitivity = [row for row in evidence if row["population"] == "formal_eligible_sensitivity"]
    assert sensitivity
    assert any("rows=0" not in row["support"] for row in sensitivity)


def test_existing_proposal_overlap_and_t1_fields_are_analyzed(output):
    out, _ = output
    reviews = rows(out / "semi_review_fact.csv")
    assert sum(bool(row["U_initial"]) for row in reviews) == 557
    assert sum(bool(row["U_final"]) for row in reviews) == 558
    assert sum(bool(row["delta_U"]) for row in reviews) == 555
    tasks = rows(out / "task_fact.csv")
    assert sum(row["stage"] == "T1_CANDIDATE" for row in tasks) == 458
    evidence = rows(out / "association_matrix.csv")
    assert list(evidence[0]) == RESULT_FIELDS
    assert any(row["analysis_lane"] == "proposal_edit" and row["predictor"] == "U_initial" and row["evidence_grade"] != "E0_not_evaluable" for row in evidence)
    overlap = [row for row in evidence if row["analysis_lane"] == "c1_manual_semi_overlap" and row["population"] == "all_observed"]
    assert len(overlap) == 1 and "overlap_task_denominator=25" in overlap[0]["support"]
    assert any(row["analysis_lane"] == "calibration_t1_shift" and "rows=545" in row["support"] for row in evidence)


def test_cluster_inference_and_manifest_are_reproducible(output, tmp_path):
    out, _ = output
    sample = [(float(i), float(i % 3), f"g{i % 6}") for i in range(60)]
    assert cluster_inference(sample, False, "test") == cluster_inference(sample * 2, False, "test")
    manifest = json.loads((out / "analysis_manifest.json").read_text())
    assert manifest["paper_b_inputs"] == []
    assert manifest["rules"]["inference"].startswith("independent-group")
    assert all(item["sha256"] != "directory" for item in manifest["inputs"])
    second = tmp_path / "second"
    materialize(second)
    second_manifest = json.loads((second / "analysis_manifest.json").read_text())
    assert manifest["outputs"] == second_manifest["outputs"]
