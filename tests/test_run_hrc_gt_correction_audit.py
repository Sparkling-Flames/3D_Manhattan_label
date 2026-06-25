import hashlib
import json
from pathlib import Path

from tools.paper_a_manhattan.run_hrc_gt_correction_audit import (
    CORRECTED_GT_ID,
    SCHEMA_VERSION,
    SOURCE_EXPORT,
    run,
)


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_gt_correction_materialization_preserves_boundaries(tmp_path):
    source_sha_before = _sha256(SOURCE_EXPORT)
    paths = run(tmp_path)
    assert _sha256(SOURCE_EXPORT) == source_sha_before
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["corrected_gt_id"] == CORRECTED_GT_ID
    assert payload["case_name"] == "task238_ann2389_4543gt"
    assert payload["old_gt"]["status"] == "deprecated_superseded_source"
    assert payload["corrected_gt"]["accepted_final_fix"] is False
    assert payload["old_gt"]["sha256"] == _sha256(paths["old_gt"])
    assert payload["corrected_gt"]["sha256"] == _sha256(paths["corrected_gt"])
    assert payload["old_gt"]["sha256"] != payload["corrected_gt"]["sha256"]
    assert json.loads(paths["old_gt"].read_text(encoding="utf-8"))["annotation_id"] == 2389
    assert json.loads(paths["corrected_gt"].read_text(encoding="utf-8"))[
        "annotation_id"
    ] == 4543

    assert payload["candidate_status"] == {
        "candidate_specific": False,
        "candidate_count": 0,
        "candidate_preference_authorized": False,
    }
    assert payload["safety_boundary"]["accepted"] is False
    assert payload["safety_boundary"]["downstream_recommendation"] is False
    assert payload["safety_boundary"]["annotation_writeback"] is False
    assert set(payload["status_boundaries"].values()) == {"blocked"}


def test_manual_sidecars_use_only_existing_evidence_types(tmp_path):
    paths = run(tmp_path)
    seen = set()
    for key, path in paths.items():
        if not key.startswith("sidecar_"):
            continue
        sidecar = json.loads(path.read_text(encoding="utf-8"))
        seen.add(sidecar["evidence_type"])
        assert sidecar["schema_version"] == "hrc_manual_evidence_sidecar_v1"
        assert sidecar["verdict"] == "available"
        assert sidecar["evidence_type"] == "explicit_column_identity"
        assert sidecar["short_wall_exists"] is False
        assert sidecar["keep_distinct_required"] is False
        assert sidecar["keep_distinct_contract"] == "not_applicable"
        assert sidecar["four_corner_layout_sufficient"] is True
        assert sidecar["supporting_artifacts_are_manual_verdict"] is False
        assert all(row["sha256"] for row in sidecar["supporting_artifacts"])
    assert seen == {"explicit_column_identity"}
    assert not (
        tmp_path / "manual_sidecar_keep_distinct_contract_4543gt.json"
    ).exists()


def test_old_and_corrected_diagnostics_are_compared(tmp_path):
    paths = run(tmp_path)
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    old = payload["diagnostics"]["old_gt"]
    corrected = payload["diagnostics"]["corrected_gt"]
    comparison = payload["diagnostics"]["old_vs_corrected"]

    assert old["projection_validity"]["valid"] is True
    assert corrected["projection_validity"]["valid"] is True
    assert old["topology"]["pair_count"] == 6
    assert corrected["topology"]["pair_count"] == 4
    assert comparison["pair_count"] == {"old": 6, "corrected": 4, "delta": -2.0}
    assert "floorprint" in corrected
    assert "turn_residuals" in corrected
    assert "height_consistency" in corrected
    assert "short_wall_diagnostics" in corrected
    assert "dense_corner_diagnostics" in corrected
    correction = payload["diagnostics"]["semantic_correction"]
    assert correction["short_wall_exists"] is False
    assert correction["keep_distinct_required"] is False
    assert correction["keep_distinct_contract"] == "not_applicable"
    assert correction["four_corner_layout_sufficient"] is True
    assert correction["corrected_projection_short_wall_count"] == 0

    projection = json.loads(
        paths["corrected_projection"].read_text(encoding="utf-8")
    )
    assert projection["case_name"] == "task238_ann2389_4543gt"
    assert projection["pair_count"] == 4
    assert len(projection["variants"][0]["ordered_pairs"]) == 4
    assert projection["candidate_preference_authorized"] is False
