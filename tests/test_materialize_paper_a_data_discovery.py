import csv
import json
from pathlib import Path

from tools.thesis_main.analysis.materialize_paper_a_data_discovery import RESULT_FIELDS, materialize


def rows(path: Path):
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_materializes_complete_paper_a_inventory_deterministically(tmp_path):
    out = tmp_path / "first"
    summary = materialize(out)
    assert summary["submissions"] == 2501
    submissions = rows(out / "submission_fact.csv")
    assert len({row["worker_id"] for row in submissions}) == 26
    assert sum(row["worker_id"] == "14" and row["stage"] == "C1" for row in submissions) == 32
    assert {"19", "21", "26"} <= {row["worker_id"] for row in submissions}
    manifest = json.loads((out / "analysis_manifest.json").read_text())
    assert manifest["paper_b_inputs"] == []
    assert all("paper_b" not in item["path"].lower() for item in manifest["inputs"])
    evidence = rows(out / "association_matrix.csv")
    assert list(evidence[0]) == RESULT_FIELDS
    assert {"all_observed", "formal_eligible_sensitivity"} <= {row["population"] for row in evidence}
    assert {row["evidence_grade"] for row in evidence} <= {"E0_not_evaluable", "E1_descriptive", "E2_cross_validated", "E3_cross_context_consistent", "E4_prospective_confirmed"}
    second = tmp_path / "second"
    materialize(second)
    first_manifest = json.loads((out / "analysis_manifest.json").read_text())
    second_manifest = json.loads((second / "analysis_manifest.json").read_text())
    assert first_manifest["outputs"] == second_manifest["outputs"]
