from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.thesis_main.analysis.materialize_c1_canonical_evidence_sidecars import materialize_canonical_evidence


def _write(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def test_canonical_evidence_sidecars_keep_dry_run_explicit(tmp_path: Path) -> None:
    export = tmp_path / "c1_export.json"
    _write(
        export,
        [
            {
                "id": 11,
                "project": 2,
                "data": {"task_id": "scene_1", "base_task_id": "scene_1", "dataset_group": "C1_semi", "condition": "semi"},
                "annotations": [
                    {
                        "id": 101,
                        "completed_by": {"id": 7},
                        "result": [
                            {"type": "keypointlabels", "value": {"x": 10, "y": 20}},
                            {"type": "keypointlabels", "value": {"x": 10, "y": 80}},
                            {"type": "choices", "from_name": "model_issue", "value": {"choices": ["acceptable"]}},
                        ],
                    }
                ],
                "predictions": [{"model_version": "smoke", "result": []}],
            }
        ],
    )
    canonical = tmp_path / "c1_canonical_annotations.csv"
    with canonical.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["source_export", "project_id", "ls_runtime_task_id", "worker_id", "raw_canonical_annotation_id", "canonical_annotation_id", "geometry_hash", "parse_error"])
        writer.writeheader()
        writer.writerow({"source_export": str(export), "project_id": "2", "ls_runtime_task_id": "11", "worker_id": "7", "raw_canonical_annotation_id": "101", "canonical_annotation_id": "canon", "geometry_hash": "hash", "parse_error": ""})

    summary = materialize_canonical_evidence([export], canonical, tmp_path)
    assert summary["dry_run"] is True
    assert summary["interpretation_allowed"] is False
    meta = list(csv.DictReader((tmp_path / "c1_canonical_meta_observations.csv").open(encoding="utf-8")))
    assert meta[0]["choice_map_json"]
    assert meta[0]["validity_status"] == "dry_run"
    provenance = list(csv.DictReader((tmp_path / "c1_model_artifact_provenance.csv").open(encoding="utf-8")))
    assert provenance[0]["provenance_status"] == "legacy_missing"
    assert provenance[0]["checkpoint_sha256"] == ""

