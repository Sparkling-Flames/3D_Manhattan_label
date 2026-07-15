from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.thesis_main.analysis.c1_materialize_quality_table import materialize


def _write(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_quality_reads_fresh_canonical_choice_payload(tmp_path: Path) -> None:
    raw = tmp_path / "raw_export.json"
    raw.write_text("[]", encoding="utf-8")
    raw_sha = __import__("hashlib").sha256(raw.read_bytes()).hexdigest()
    registry = tmp_path / "c1_canonical_annotations.csv"
    _write(registry, ["canonical_annotation_id"], [{"canonical_annotation_id": "a1"}])
    sha = __import__("hashlib").sha256(registry.read_bytes()).hexdigest()
    meta = tmp_path / "c1_canonical_meta_observations.csv"
    _write(meta, ["canonical_registry_sha256", "source_artifact", "source_sha256", "source_export_sha256", "task_id", "base_task_id", "dataset_group", "worker_id", "canonical_annotation_id", "choice_map_json", "difficulty_present", "model_issue_present", "canonical_eligibility_status", "schema_interpretable", "n_corners", "geometry_hash", "assigned_expected", "independence_status", "independence_audit_identity"], [{"canonical_registry_sha256": sha, "source_artifact": str(raw), "source_sha256": raw_sha, "source_export_sha256": raw_sha, "task_id": "t", "base_task_id": "b", "dataset_group": "Calibration_anchor", "worker_id": "w", "canonical_annotation_id": "a1", "choice_map_json": json.dumps({"difficulty": ["occlusion"], "model_issue": ["acceptable"]}), "difficulty_present": "true", "model_issue_present": "true", "canonical_eligibility_status": "valid", "schema_interpretable": "true", "n_corners": "4", "geometry_hash": "g", "assigned_expected": "true", "independence_status": "independent", "independence_audit_identity": "project|task|worker|annotation"}])
    summary = materialize(registry, tmp_path, None)
    quality = list(csv.DictReader((tmp_path / "c1_quality_annotations.csv").open(encoding="utf-8")))
    assert summary["canonical_meta_fresh"] is True
    assert quality[0]["difficulty"] == "occlusion"
    assert quality[0]["model_issue"] == "acceptable"
    assert quality[0]["independence_audit_identity"] == "project|task|worker|annotation"


def test_quality_marks_missing_canonical_meta_as_blocker(tmp_path: Path) -> None:
    registry = tmp_path / "c1_canonical_annotations.csv"
    _write(registry, ["task_id"], [{"task_id": "t"}])
    assert "canonical_meta_missing_or_stale" in materialize(registry, tmp_path, None)["blockers"]


def test_quality_marks_registry_hash_mismatch_as_stale(tmp_path: Path) -> None:
    registry = tmp_path / "c1_canonical_annotations.csv"
    _write(registry, ["canonical_annotation_id"], [{"canonical_annotation_id": "a1"}])
    _write(tmp_path / "c1_canonical_meta_observations.csv", ["canonical_registry_sha256", "canonical_annotation_id"], [{"canonical_registry_sha256": "stale", "canonical_annotation_id": "a1"}])
    summary = materialize(registry, tmp_path, None)
    assert summary["canonical_meta_fresh"] is False
    assert "canonical_meta_missing_or_stale" in summary["blockers"]


def test_quality_marks_replaced_raw_export_as_stale(tmp_path: Path) -> None:
    registry = tmp_path / "c1_canonical_annotations.csv"
    _write(registry, ["canonical_annotation_id"], [{"canonical_annotation_id": "a1"}])
    raw = tmp_path / "raw.json"
    raw.write_text("original", encoding="utf-8")
    registry_sha = __import__("hashlib").sha256(registry.read_bytes()).hexdigest()
    raw_sha = __import__("hashlib").sha256(raw.read_bytes()).hexdigest()
    _write(tmp_path / "c1_canonical_meta_observations.csv", ["canonical_registry_sha256", "source_artifact", "source_sha256", "source_export_sha256", "canonical_annotation_id"], [{"canonical_registry_sha256": registry_sha, "source_artifact": str(raw), "source_sha256": raw_sha, "source_export_sha256": raw_sha, "canonical_annotation_id": "a1"}])
    raw.write_text("replaced", encoding="utf-8")
    summary = materialize(registry, tmp_path, None)
    assert summary["canonical_meta_fresh"] is False
    assert "raw_export_sha_mismatch" in summary["canonical_meta_freshness_reasons"]
