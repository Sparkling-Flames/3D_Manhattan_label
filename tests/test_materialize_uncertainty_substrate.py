from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path

import pytest

from tools.thesis_main.analysis.full_uncertainty import materialize_uncertainty_substrate as substrate


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_uncertainty_substrate_contract_and_determinism(tmp_path: Path) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    result = substrate.materialize(first)
    substrate.materialize(second)

    deterministic = sorted(path.name for path in first.glob("*.csv")) + [
        "SOURCE_MANIFEST.json", "QA_SUMMARY.json",
    ]
    assert all((first / name).read_bytes() == (second / name).read_bytes() for name in deterministic)
    with pytest.raises(FileExistsError):
        substrate.materialize(first)

    spine = _rows(first / "annotation_spine.csv")
    lineage = _rows(first / "annotation_version_lineage.csv")
    images = _rows(first / "image_registry.csv")
    contexts = _rows(first / "task_context_master.csv")
    variants = _rows(first / "geometry_variants.csv")
    proposals = _rows(first / "proposal_fact.csv")
    responses = _rows(first / "proposal_response.csv")
    active = _rows(first / "active_time_context.csv")
    events = _rows(first / "active_event_fact.csv")
    sessions = _rows(first / "active_session_fact.csv")
    meta = _rows(first / "meta_response_set.csv")
    references = _rows(first / "reference_measurement.csv")

    assert result == {
        "schema_version": "uncertainty_substrate_v1", "output_dir": str(first.resolve()),
        "raw_annotation_versions": 2513, "canonical_annotations": 2501, "image_count": 214,
        "task_context_count": 270, "proposal_count": 43, "proposal_response_count": 574,
        "raw_geometry_computable": 2438, "formal_active_time_available": 2069,
        "lead_time_traceable": 2501, "workbook_status": "not_requested", "qa_status": "pass_with_known_gaps",
    }
    assert Counter((row["stage"], row["block_index"]) for row in spine) == {
        ("P1", "0"): 1481, ("C1", "0"): 780, ("C2-B", "0"): 160,
        ("C2-A-RP", "1"): 40, ("C2-A-RP", "2"): 40,
    }
    assert len(lineage) == 2513 and sum(row["independent_analysis_unit"] == "false" for row in lineage) == 12
    assert len({row["canonical_annotation_id"] for row in spine}) == 2501
    assert len({(row["stage"], row["block_index"], row["runtime_task_id"], row["worker_id"]) for row in spine}) == 2501
    assert all(row["runtime_task_id"] for row in spine if row["stage"] == "P1")
    assert sum(row["stage"] == "C1" and row["runtime_task_id"] != row["planned_task_id"] for row in spine) == 780
    block2 = [row for row in spine if (row["stage"], row["block_index"]) == ("C2-A-RP", "2")]
    assert len(block2) == 40
    assert all(re.fullmatch(r"[0-9a-f]{20}", row["canonical_annotation_id"]) for row in block2)
    assert all(row["canonical_annotation_id_legacy_alias"].startswith("block2-") for row in block2)

    assert len(images) == 214 and len({row["building_id"] for row in images}) == 22 and len(contexts) == 270
    assert {row["variant"] for row in variants} == {"raw", "strict_normalized", "repaired"}
    assert sum(row["variant"] == "raw" and row["geometry_computable"] == "true" for row in variants) == 2438
    pair_fields = set(_rows(first / "geometry_pairwise.csv")[0])
    assert not any(token in field for field in pair_fields for token in ("threshold", "cluster", "mode", "entropy"))

    manual_issue = [row for row in meta if row["field_name"] == "model_issue" and row["raw_condition"] != "semi"]
    assert len(manual_issue) == 1927
    assert all(row["response_state"] == "not_evaluable" and row["choice_code_set_json"] == "[]" for row in manual_issue)
    assert len(proposals) == 43 and len(responses) == 574
    assert all(row["model_issue_timing_status"] == "not_time_locked" for row in responses)
    assert all(len(json.loads(row["initialization_import_sha256_set_json"])) in {1, 2} for row in proposals)

    assert sum(row["active_time_formal_available"] == "true" for row in active) == 2069
    assert sum(row["lead_time_status"] == "available" for row in active) == 2501
    assert all(row["lead_time_is_active_time"] == "false" for row in active)
    p1_fallback = [row for row in active if row["stage"] == "P1" and row["active_time_source"] == "lead_time_fallback"]
    assert len(p1_fallback) == 353 and all(row["active_time_seconds"] == "" for row in p1_fallback)
    assert len(events) == 34417 and len(sessions) == 3735

    bad_gt = [row for row in references if row["base_task_id"] == substrate.BAD_GT_TASK]
    assert len(bad_gt) == 4
    assert all(row["measurement_status"] == "not_evaluable" and row["measurement_value"] == "" for row in bad_gt)
    manifest = json.loads((first / "SOURCE_MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["legacy_precision_dependency_integrity"]["status"] == "known_sha_mismatch_not_consumed"
    assert manifest["c2b_status"]["collection_closed"] is True
    assert manifest["c2a_rp_status"]["stage_closed"] is True
