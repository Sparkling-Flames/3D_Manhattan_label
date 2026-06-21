import json

from tools.paper_a_manhattan import run_constrained_v0_shadow_audit as audit


def _write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _inputs(tmp_path):
    projection = _write(
        tmp_path / "projection.json",
        {
            "case_name": "shadow_fixture",
            "width": 1024,
            "height": 512,
            "camera_height": 1.6,
            "coordinate_mode_requested": "ls_percent",
            "variants": [
                {
                    "name": "original",
                    "ordered_pairs": [
                        {
                            "effective_pair_index": 1,
                            "top": {"x": 10.0, "y": 20.0},
                            "bottom": {"x": 12.0, "y": 80.0},
                        },
                        {
                            "effective_pair_index": 2,
                            "top": {"x": 30.0, "y": 20.0},
                            "bottom": {"x": 30.0, "y": 80.0},
                        },
                    ],
                }
            ],
        },
    )
    contract = _write(
        tmp_path / "contract.json",
        {
            "case_name": "shadow_fixture",
            "protected_pairs": [],
            "movable_fields_by_pair": {"1": ["x"]},
            "keep_distinct_pairs": [[1, 2]],
        },
    )
    return projection, contract


def test_shadow_audit_writes_reports_and_fails_closed_without_identity(tmp_path, monkeypatch):
    projection, contract = _inputs(tmp_path)
    monkeypatch.setattr(audit, "AUDIT_ROOT", tmp_path / "audit")
    paths = audit.run(
        tmp_path / "audit" / "missing",
        projection_path=projection,
        case_config_path=contract,
    )
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))

    assert paths["markdown"].is_file()
    assert payload["schema_version"] == "constrained_v0_column_x_shadow_audit_v1"
    assert paths["markdown"].read_text(encoding="utf-8").startswith(
        "# Constrained v0 Column-X Shadow Audit"
    )
    assert payload["candidate_count"] == 0
    assert payload["missing_required_evidence_for_column_x_alignment"] is True
    assert set(payload["unavailable_summary"]["reasons"]) >= {
        "evidence_unavailable",
        "column_identity_unavailable",
    }
    assert payload["accepted"] is False
    assert payload["downstream_recommendation"] is False


def test_shadow_audit_generates_only_shadow_candidate_with_explicit_identity(tmp_path, monkeypatch):
    projection, contract = _inputs(tmp_path)
    evidence = _write(
        tmp_path / "evidence.json",
        {
            "evidence_status": "available",
            "column_identity_status": "available",
            "visual_conflict_flags": [],
            "seam_safe": True,
        },
    )
    monkeypatch.setattr(audit, "AUDIT_ROOT", tmp_path / "audit")
    paths = audit.run(
        tmp_path / "audit" / "available",
        projection_path=projection,
        case_config_path=contract,
        evidence_path=evidence,
    )
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))

    assert payload["candidate_count"] == 1
    assert payload["legacy_m1528_active_source_unchanged"] is True
    assert all(
        row["shadow_only"]
        and row["accepted"] is False
        and row["downstream_recommendation"] is False
        for row in payload["candidate_source"]["candidate_set"]
    )


def test_height_shadow_audit_materializes_explicit_after_y(tmp_path, monkeypatch):
    projection, contract = _inputs(tmp_path)
    contract.write_text(
        json.dumps(
            {
                "case_name": "shadow_fixture",
                "protected_pairs": [],
                "movable_fields_by_pair": {"1": ["top_y"]},
                "inferred_height_target_pairs": [],
            }
        ),
        encoding="utf-8",
    )
    height_summary = _write(
        tmp_path / "height.json",
        {
            "height_target_status": "available",
            "target_height": 3.0,
            "height_outlier_pairs": [1],
            "after_y_by_pair": {"1": {"top_y": 18.0}},
            "formula_status": "explicit_after_y",
        },
    )
    monkeypatch.setattr(audit, "AUDIT_ROOT", tmp_path / "audit")
    paths = audit.run(
        tmp_path / "audit" / "height",
        projection_path=projection,
        case_config_path=contract,
        height_summary_path=height_summary,
        family="height_target_reproject",
    )
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["family"] == "height_target_reproject"
    assert payload["schema_version"] == "constrained_v0_height_target_shadow_audit_v1"
    assert paths["markdown"].read_text(encoding="utf-8").startswith(
        "# Constrained v0 Height Target Shadow Audit"
    )
    assert payload["candidate_count"] == 1
    assert payload["target_height"] == 3.0
    assert payload["formula_status"] == "explicit_after_y"
    assert payload["accepted"] is False
    assert payload["downstream_recommendation"] is False
