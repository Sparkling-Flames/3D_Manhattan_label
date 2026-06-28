from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.thesis_main.analysis.prescreen_geometry_eligibility import build_geometry_eligibility, main


def _write_csv(path: Path, rows: list[dict]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return path


def _task(
    task_id: str,
    *,
    dataset_group: str,
    condition: str,
    scope: str,
    source: str = "final_gold",
    final_gold_ref: str = "task_id:gold",
    geometry_gold_status: str = "",
) -> dict:
    return {
        "task_id": task_id,
        "project_id": "1",
        "dataset_group": dataset_group,
        "condition": condition,
        "image_id": f"base_{task_id}",
        "data_title": f"base_{task_id}.jpg",
        "task_final_scope": scope,
        "task_scope_adjudication_source": source,
        "final_gold_scope": "normal" if scope == "in_scope" else scope,
        "final_gold_ref": final_gold_ref,
        "geometry_gold_status": geometry_gold_status,
        "geometry_primary_possible": str(scope == "in_scope"),
        "notes": "",
    }


def _response(
    task_id: str,
    *,
    dataset_group: str,
    condition: str,
    scope: str,
    geometry: bool = True,
    worker_scope_response: str = "correct_in_scope",
    primary_eligible: bool = True,
) -> dict:
    return {
        "annotator_id": "w1",
        "project_id": "1",
        "task_id": task_id,
        "dataset_group": dataset_group,
        "condition": condition,
        "task_final_scope": scope,
        "task_scope_adjudication_source": "final_gold",
        "geometry_valid_or_present": str(geometry),
        "worker_scope_response": worker_scope_response,
        "scope_response_primary_eligible": str(primary_eligible),
    }


def _synthetic_scope(task_id: str, *, ready: bool = True, role: str = "semi_trap_audit") -> dict:
    return {
        "runtime_task_id": task_id,
        "project_id": "1",
        "language": "zh",
        "dataset_group": "PreScreen_semi",
        "condition": "semi",
        "image_id": "source_base",
        "base_image_key": "source_base",
        "task_final_scope_after_binding": "in_scope",
        "task_scope_adjudication_source_after_binding": "synthetic_asset_expert_review",
        "geometry_gold_source_after_binding": "export_label_groudTruth" if ready else "",
        "geometry_gold_ready_after_binding": str(ready),
        "geometry_scoring_role": role,
        "manual_anchor_role": "False",
        "manual_anchor_primary_possible": "False",
    }


def _synthetic_geometry(
    task_id: str,
    *,
    base: str = "source_base",
    gold_task: str = "gt_1",
    ready: bool = True,
    status: str = "synthetic_geometry_bound_to_export_gt",
) -> dict:
    return {
        "runtime_task_id": task_id,
        "project_id": "1",
        "language": "zh",
        "base_image_key": base,
        "geometry_gold_source": "export_label_groudTruth" if ready else "",
        "geometry_gold_task_id": gold_task,
        "geometry_gold_annotation_count": "1" if ready else "",
        "geometry_gold_ready": str(ready),
        "geometry_binding_status": status,
        "task_scope_adjudication_source": "synthetic_asset_expert_review",
        "geometry_scoring_role": "semi_trap_audit" if ready else "",
        "manual_anchor_role": "False",
        "manual_anchor_primary_possible": "False",
    }


def _inputs(tmp_path: Path, tasks: list[dict], responses: list[dict], synthetic_scope: list[dict] | None = None, synthetic_geometry: list[dict] | None = None):
    scope = _write_csv(tmp_path / "scope.csv", tasks)
    response = _write_csv(tmp_path / "response.csv", responses)
    synth_scope = _write_csv(tmp_path / "synthetic_scope.csv", synthetic_scope or [_synthetic_scope("unused", ready=False)])
    synth_geom = _write_csv(tmp_path / "synthetic_geometry.csv", synthetic_geometry or [_synthetic_geometry("unused", ready=False, status="missing_export_gt")])
    return scope, response, synth_scope, synth_geom


def test_manual_in_scope_ready_gold_is_manual_primary_candidate_not_admission(tmp_path: Path) -> None:
    paths = _inputs(
        tmp_path,
        [_task("1", dataset_group="PreScreen_manual", condition="manual", scope="in_scope")],
        [_response("1", dataset_group="PreScreen_manual", condition="manual", scope="in_scope")],
    )

    task_rows, response_rows, summary = build_geometry_eligibility(*paths)

    assert task_rows[0]["geometry_gold_status"] == "ready"
    assert task_rows[0]["manual_anchor_role"] is True
    assert task_rows[0]["manual_anchor_primary_possible"] is True
    assert task_rows[0]["admission_anchor_role"] is False
    assert task_rows[0]["admission_anchor_possible"] is False
    assert task_rows[0]["dry_run"] is True
    assert response_rows[0]["geometry_evidence_role"] == "manual_prescreen_candidate"
    assert not any("score" in key.lower() for row in [*task_rows, *response_rows] for key in row)
    assert summary["forbidden_metric_field_count"] == 0


def test_response_without_geometry_is_not_manual_anchor_even_if_task_is_ready(tmp_path: Path) -> None:
    paths = _inputs(
        tmp_path,
        [_task("nogeom", dataset_group="PreScreen_manual", condition="manual", scope="in_scope")],
        [_response("nogeom", dataset_group="PreScreen_manual", condition="manual", scope="in_scope", geometry=False)],
    )

    task_rows, response_rows, _summary = build_geometry_eligibility(*paths)

    assert task_rows[0]["manual_anchor_role"] is True
    assert response_rows[0]["manual_anchor_role"] is False
    assert response_rows[0]["manual_anchor_primary_possible"] is False
    assert response_rows[0]["geometry_evidence_role"] != "manual_prescreen_candidate"


def test_response_with_scope_error_is_not_manual_anchor(tmp_path: Path) -> None:
    paths = _inputs(
        tmp_path,
        [_task("scopeerr", dataset_group="PreScreen_manual", condition="manual", scope="in_scope")],
        [
            _response(
                "scopeerr",
                dataset_group="PreScreen_manual",
                condition="manual",
                scope="in_scope",
                worker_scope_response="scope_false_positive",
            )
        ],
    )

    _task_rows, response_rows, _summary = build_geometry_eligibility(*paths)

    assert response_rows[0]["manual_anchor_role"] is False
    assert response_rows[0]["manual_anchor_primary_possible"] is False


def test_response_not_primary_eligible_is_not_manual_anchor(tmp_path: Path) -> None:
    paths = _inputs(
        tmp_path,
        [_task("ineligible", dataset_group="PreScreen_manual", condition="manual", scope="in_scope")],
        [_response("ineligible", dataset_group="PreScreen_manual", condition="manual", scope="in_scope", primary_eligible=False)],
    )

    _task_rows, response_rows, _summary = build_geometry_eligibility(*paths)

    assert response_rows[0]["manual_anchor_role"] is False
    assert response_rows[0]["manual_anchor_primary_possible"] is False


def test_response_correct_geometry_present_and_primary_eligible_is_manual_anchor(tmp_path: Path) -> None:
    paths = _inputs(
        tmp_path,
        [_task("good", dataset_group="PreScreen_manual", condition="manual", scope="in_scope")],
        [_response("good", dataset_group="PreScreen_manual", condition="manual", scope="in_scope")],
    )

    _task_rows, response_rows, _summary = build_geometry_eligibility(*paths)

    assert response_rows[0]["manual_anchor_role"] is True
    assert response_rows[0]["manual_anchor_primary_possible"] is True


def test_semi_synthetic_ready_gt_is_audit_only_not_manual_or_admission_anchor(tmp_path: Path) -> None:
    paths = _inputs(
        tmp_path,
        [_task("2", dataset_group="PreScreen_semi", condition="semi", scope="in_scope", source="synthetic_asset_expert_review")],
        [_response("2", dataset_group="PreScreen_semi", condition="semi", scope="in_scope")],
        [_synthetic_scope("2", ready=True)],
        [_synthetic_geometry("2", ready=True)],
    )

    task_rows, _response_rows, _summary = build_geometry_eligibility(*paths)

    assert task_rows[0]["geometry_gold_status"] == "ready"
    assert task_rows[0]["geometry_gold_validation_level"] == "source_gt_annotation_count_checked"
    assert task_rows[0]["geometry_evidence_role"] in {"semi_synthetic_trap_audit", "semi_aux_geometry_alignment"}
    assert task_rows[0]["geometry_scoring_role"] in {"semi_trap_audit", "semi_aux_geometry_alignment"}
    assert task_rows[0]["manual_anchor_role"] is False
    assert task_rows[0]["manual_anchor_primary_possible"] is False
    assert task_rows[0]["admission_anchor_role"] is False
    assert task_rows[0]["admission_anchor_possible"] is False


def test_semi_non_synthetic_in_scope_is_condition_diagnostic_only(tmp_path: Path) -> None:
    paths = _inputs(
        tmp_path,
        [_task("3", dataset_group="PreScreen_semi", condition="semi", scope="in_scope")],
        [_response("3", dataset_group="PreScreen_semi", condition="semi", scope="in_scope")],
    )

    task_rows, _response_rows, _summary = build_geometry_eligibility(*paths)

    assert task_rows[0]["geometry_evidence_role"] == "semi_condition_diagnostic"
    assert task_rows[0]["manual_anchor_role"] is False
    assert task_rows[0]["admission_anchor_role"] is False


def test_oos_is_excluded_from_geometry_anchors(tmp_path: Path) -> None:
    paths = _inputs(
        tmp_path,
        [_task("4", dataset_group="PreScreen_oos", condition="oos", scope="oos_geometry")],
        [_response("4", dataset_group="PreScreen_oos", condition="oos", scope="oos_geometry")],
    )

    task_rows, _response_rows, _summary = build_geometry_eligibility(*paths)

    assert task_rows[0]["geometry_gold_status"] == "not_applicable"
    assert task_rows[0]["geometry_evidence_role"] == "oos_excluded"
    assert task_rows[0]["geometry_scoring_role"] == "oos_excluded"
    assert task_rows[0]["manual_anchor_role"] is False
    assert task_rows[0]["admission_anchor_role"] is False


def test_missing_duplicate_invalid_gt_are_not_anchor_eligible(tmp_path: Path) -> None:
    tasks = [
        _task("m", dataset_group="PreScreen_manual", condition="manual", scope="in_scope", final_gold_ref="", geometry_gold_status="missing"),
        _task("d", dataset_group="PreScreen_manual", condition="manual", scope="in_scope", geometry_gold_status="duplicate"),
        _task("i", dataset_group="PreScreen_manual", condition="manual", scope="in_scope", geometry_gold_status="invalid_annotation_count"),
    ]
    paths = _inputs(
        tmp_path,
        tasks,
        [_response(row["task_id"], dataset_group="PreScreen_manual", condition="manual", scope="in_scope") for row in tasks],
    )

    task_rows, response_rows, _summary = build_geometry_eligibility(*paths)

    assert [row["geometry_gold_status"] for row in task_rows] == ["missing", "duplicate", "invalid_annotation_count"]
    assert all(row["manual_anchor_role"] is False for row in task_rows)
    assert all(row["admission_anchor_role"] is False for row in task_rows)
    assert not any("score" in key.lower() for row in [*task_rows, *response_rows] for key in row)


def test_language_mirror_runtime_rows_share_base_gold_task(tmp_path: Path) -> None:
    paths = _inputs(
        tmp_path,
        [
            _task("zh", dataset_group="PreScreen_semi", condition="semi", scope="in_scope", source="synthetic_asset_expert_review"),
            _task("en", dataset_group="PreScreen_semi", condition="semi", scope="in_scope", source="synthetic_asset_expert_review"),
        ],
        [
            _response("zh", dataset_group="PreScreen_semi", condition="semi", scope="in_scope"),
            _response("en", dataset_group="PreScreen_semi", condition="semi", scope="in_scope"),
        ],
        [_synthetic_scope("zh", ready=True), _synthetic_scope("en", ready=True)],
        [_synthetic_geometry("zh", base="same_base", gold_task="gt_same"), _synthetic_geometry("en", base="same_base", gold_task="gt_same")],
    )

    task_rows, _response_rows, summary = build_geometry_eligibility(*paths)

    assert len(task_rows) == 2
    assert summary["runtime_task_rows"] == 2
    assert summary["base_image_count"] == 1
    assert {row["geometry_gold_task_id"] for row in task_rows} == {"gt_same"}
    assert summary["mirror_alignment_mismatch_count"] == 0


def test_language_mirror_gold_task_mismatch_is_audited(tmp_path: Path) -> None:
    paths = _inputs(
        tmp_path,
        [
            _task("zh", dataset_group="PreScreen_semi", condition="semi", scope="in_scope", source="synthetic_asset_expert_review"),
            _task("en", dataset_group="PreScreen_semi", condition="semi", scope="in_scope", source="synthetic_asset_expert_review"),
        ],
        [
            _response("zh", dataset_group="PreScreen_semi", condition="semi", scope="in_scope"),
            _response("en", dataset_group="PreScreen_semi", condition="semi", scope="in_scope"),
        ],
        [_synthetic_scope("zh", ready=True), _synthetic_scope("en", ready=True)],
        [_synthetic_geometry("zh", base="same_base", gold_task="gt_zh"), _synthetic_geometry("en", base="same_base", gold_task="gt_en")],
    )

    task_rows, _response_rows, summary = build_geometry_eligibility(*paths)

    assert summary["mirror_alignment_mismatch_count"] == 1
    assert {row["geometry_alignment_status"] for row in task_rows} == {"mirror_gold_mismatch"}


def test_manual_and_synthetic_same_base_with_different_gold_do_not_trigger_mirror_mismatch(tmp_path: Path) -> None:
    manual = _task("manual", dataset_group="PreScreen_manual", condition="manual", scope="in_scope", final_gold_ref="manual_gt")
    semi = _task("semi", dataset_group="PreScreen_semi", condition="semi", scope="in_scope", source="synthetic_asset_expert_review")
    semi["image_id"] = manual["image_id"]
    paths = _inputs(
        tmp_path,
        [manual, semi],
        [
            _response("manual", dataset_group="PreScreen_manual", condition="manual", scope="in_scope"),
            _response("semi", dataset_group="PreScreen_semi", condition="semi", scope="in_scope"),
        ],
        [_synthetic_scope("semi", ready=True)],
        [_synthetic_geometry("semi", base=manual["image_id"], gold_task="synthetic_gt")],
    )

    task_rows, _response_rows, summary = build_geometry_eligibility(*paths)

    assert summary["mirror_alignment_mismatch_count"] == 0
    assert {row["geometry_alignment_status"] for row in task_rows} == {"aligned_ready"}


def test_cli_writes_only_step5_dry_run_outputs(tmp_path: Path) -> None:
    paths = _inputs(
        tmp_path,
        [_task("1", dataset_group="PreScreen_manual", condition="manual", scope="in_scope")],
        [_response("1", dataset_group="PreScreen_manual", condition="manual", scope="in_scope")],
    )
    out = tmp_path / "out"

    assert main(["--scope-adjudication-csv", str(paths[0]), "--scope-response-csv", str(paths[1]), "--synthetic-scope-csv", str(paths[2]), "--synthetic-geometry-csv", str(paths[3]), "--output-dir", str(out)]) == 0

    assert {p.name for p in out.iterdir()} == {
        "prescreen_geometry_gold_alignment_audit.csv",
        "prescreen_geometry_eligibility_audit.csv",
        "prescreen_gold_alignment_summary.json",
    }
    assert not any(any(token in p.name.lower() for token in ("admission", "r0", "r_u", "wmax", "w_max", "routing", "c1", "handoff", "geometry_score")) for p in out.iterdir())
    for path in out.glob("*.csv"):
        rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
        assert rows
        assert not any("score" in key.lower() for row in rows for key in row)
    summary = json.loads((out / "prescreen_gold_alignment_summary.json").read_text(encoding="utf-8"))
    assert summary["dry_run"] is True


# Local audit regression tests may read analysis_results in future extensions.
# Those depend on local frozen raw inputs/manifest/summary/audit CSV, not clean-clone CI.
# Step 5 should read frozen snapshot/canonical/Step 4 audit outputs, not mutable LS raw exports.
# A later preflight can check schema, key mapping, manifest sha, binding rate, and forbidden outputs.
