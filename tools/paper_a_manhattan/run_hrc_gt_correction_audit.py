"""Materialize the task238/2389 corrected GT as an audit-only artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.paper_a_manhattan.run_local_3d_projection_review import (
    build_projection_variant,
)
from tools.paper_a_manhattan.run_single_image_manhattan_assist import (
    build_single_image_assist,
)


SCHEMA_VERSION = "hrc_gt_correction_audit_v1"
SOURCE_SNAPSHOT_SCHEMA_VERSION = "hrc_gt_source_snapshot_v1"
SIDECAR_SCHEMA_VERSION = "hrc_manual_evidence_sidecar_v1"
SOURCE_EXPORT = Path("export_label/groudTruth.json")
DEFAULT_OUT_DIR = Path(
    "analysis_results/paper_a_manhattan/gt_correction_audit/"
    "task238_ann2389_4543gt"
)
SOURCE_TASK_ID = 2722
CASE_TASK_ID = 238
OLD_ANNOTATION_ID = 2389
CORRECTED_ANNOTATION_ID = 4543
CORRECTED_GT_ID = "4543gt"
SAFETY_BOUNDARY = {
    "audit_only": True,
    "active_runner_role": False,
    "accepted": False,
    "downstream_recommendation": False,
    "annotation_writeback": False,
}
STATUS_BOUNDARIES = {
    "c6_5b": "blocked",
    "c3_shadow_expansion": "blocked",
    "c7_optimizer": "blocked",
    "c9_learning": "blocked",
    "c10_ranker": "blocked",
}


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.write_bytes(
        (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )


def _source_records(source_path: Path) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    tasks = _load(source_path)
    task = next((row for row in tasks if int(row.get("id", -1)) == SOURCE_TASK_ID), None)
    if task is None:
        raise ValueError(f"source task {SOURCE_TASK_ID} not found")
    annotations = {int(row["id"]): row for row in task.get("annotations", [])}
    if OLD_ANNOTATION_ID not in annotations or CORRECTED_ANNOTATION_ID not in annotations:
        raise ValueError("old or corrected GT annotation missing")
    return task, annotations[OLD_ANNOTATION_ID], annotations[CORRECTED_ANNOTATION_ID]


def _snapshot(
    task: Mapping[str, Any],
    annotation: Mapping[str, Any],
    *,
    source_path: Path,
    role: str,
) -> dict[str, Any]:
    return {
        "schema_version": SOURCE_SNAPSHOT_SCHEMA_VERSION,
        "case_name": "task238_ann2389",
        "task_id": CASE_TASK_ID,
        "source_task_id": SOURCE_TASK_ID,
        "annotation_id": int(annotation["id"]),
        "source_role": role,
        "source_export": {
            "path": source_path.as_posix(),
            "sha256": _sha256(source_path),
        },
        "image": task.get("data", {}).get("image"),
        "annotation": annotation,
    }


def _diagnostics(annotation: Mapping[str, Any]) -> dict[str, Any]:
    assist = build_single_image_assist(
        {
            "task_id": str(CASE_TASK_ID),
            "annotation_id": str(annotation["id"]),
            "width": 1024,
            "height": 512,
            "result": annotation["result"],
        }
    )
    pairs = assist["ordered_pairs"]
    for index, pair in enumerate(pairs, start=1):
        pair.setdefault("effective_pair_index", index)
        pair.setdefault("source_preview_order_index", index)
    variant = build_projection_variant(
        str(annotation["id"]),
        pairs,
        width=1024,
        height=512,
        coordinate_mode="ls_percent",
        camera_height=1.6,
    )
    projection = variant["projection"]
    metrics = variant["metrics"]
    floor = metrics["floorprint"]
    turns = metrics["corner_turns"]
    heights = metrics["heights"]
    dense = metrics["dense_pairs"]
    finite_projection = all(
        math.isfinite(float(value))
        for pair in projection["pairs"]
        for point in ("floor_3d", "ceiling_3d")
        for value in pair[point].values()
    )
    return {
        "projection_validity": {
            "valid": finite_projection and not projection["warnings"],
            "warnings": projection["warnings"],
            "coordinate_mode": projection["coordinate_mode"],
        },
        "topology": {
            "pair_count": len(pairs),
            "pair_order": [int(row["effective_pair_index"]) for row in pairs],
            "order_status": assist["preview_compatibility"]["status"],
            "order_source": "build_single_image_assist.preview_order",
            "wrap_status": "closed_cycle_included",
            "seam_status": (
                "closed_cycle_no_projection_warning"
                if not projection["warnings"]
                else "projection_warning_present"
            ),
            "self_intersection": floor["self_intersection"],
        },
        "floorprint": floor,
        "turn_residuals": turns,
        "height_consistency": heights,
        "short_wall_diagnostics": {
            "summary": floor["summary"],
            "short_walls": [row for row in floor["walls"] if row["short_wall"]],
        },
        "dense_corner_diagnostics": dense,
        "vertical_column_residuals": [
            {
                "effective_pair_index": row["effective_pair_index"],
                "top_bottom_x_residual": row["top_bottom_x_residual"],
            }
            for row in projection["pairs"]
        ],
    }


def _delta(old: Any, corrected: Any) -> float | None:
    if isinstance(old, (int, float)) and not isinstance(old, bool):
        return float(corrected) - float(old)
    return None


def _comparison(old: Mapping[str, Any], corrected: Mapping[str, Any]) -> dict[str, Any]:
    fields = {
        "pair_count": (
            old["topology"]["pair_count"],
            corrected["topology"]["pair_count"],
        ),
        "wall_residual_sum_deg": (
            old["floorprint"]["summary"]["wall_residual_sum_deg"],
            corrected["floorprint"]["summary"]["wall_residual_sum_deg"],
        ),
        "wall_residual_max_deg": (
            old["floorprint"]["summary"]["wall_residual_max_deg"],
            corrected["floorprint"]["summary"]["wall_residual_max_deg"],
        ),
        "turn_residual_sum_deg": (
            old["turn_residuals"]["summary"]["corner_residual_sum_deg"],
            corrected["turn_residuals"]["summary"]["corner_residual_sum_deg"],
        ),
        "turn_residual_max_deg": (
            old["turn_residuals"]["summary"]["corner_residual_max_deg"],
            corrected["turn_residuals"]["summary"]["corner_residual_max_deg"],
        ),
        "dominant_height": (
            old["height_consistency"]["summary"]["median_wall_height"],
            corrected["height_consistency"]["summary"]["median_wall_height"],
        ),
        "height_mad": (
            old["height_consistency"]["summary"]["height_mad"],
            corrected["height_consistency"]["summary"]["height_mad"],
        ),
        "height_residual_max": (
            old["height_consistency"]["summary"]["height_residual_max"],
            corrected["height_consistency"]["summary"]["height_residual_max"],
        ),
        "minimum_wall_length": (
            old["floorprint"]["summary"]["minimum_wall_length"],
            corrected["floorprint"]["summary"]["minimum_wall_length"],
        ),
        "short_wall_count": (
            old["floorprint"]["summary"]["short_wall_count"],
            corrected["floorprint"]["summary"]["short_wall_count"],
        ),
    }
    return {
        name: {"old": left, "corrected": right, "delta": _delta(left, right)}
        for name, (left, right) in fields.items()
    }


def _sidecar(
    evidence_type: str,
    *,
    reviewed_at: str,
    supporting_artifacts: Sequence[Mapping[str, str]],
) -> dict[str, Any]:
    rationale = (
        "Human expert confirms top/bottom belong to the same real vertical edge."
        if evidence_type == "explicit_column_identity"
        else (
            "Human expert confirms neighboring corners are distinct and the short wall "
            "is real; short_wall_exists is rationale only, not an evidence_type."
        )
    )
    return {
        "schema_version": SIDECAR_SCHEMA_VERSION,
        "case_name": "task238_ann2389",
        "corrected_gt_id": CORRECTED_GT_ID,
        "evidence_type": evidence_type,
        "reviewer": "human_expert",
        "reviewed_at": reviewed_at,
        "verdict": "available",
        "rationale": rationale,
        "short_wall_exists": True,
        "endpoint_precision_note": (
            "minor endpoint offset possible; topology/identity confirmed but not "
            "sub-pixel perfect GT"
        ),
        "supporting_artifacts": list(supporting_artifacts),
        "supporting_artifacts_are_manual_verdict": False,
        "safety_boundary": SAFETY_BOUNDARY,
    }


def run(
    out_dir: Path = DEFAULT_OUT_DIR,
    source_path: Path = SOURCE_EXPORT,
) -> dict[str, Path]:
    task, old_annotation, corrected_annotation = _source_records(source_path)
    out_dir.mkdir(parents=True, exist_ok=True)

    old_path = out_dir / "old_gt_annotation_2389_deprecated.json"
    corrected_path = out_dir / "corrected_gt_annotation_4543gt.json"
    _write_json(
        old_path,
        _snapshot(
            task,
            old_annotation,
            source_path=source_path,
            role="deprecated_superseded_source",
        ),
    )
    _write_json(
        corrected_path,
        _snapshot(
            task,
            corrected_annotation,
            source_path=source_path,
            role="corrected_gt_audit_source",
        ),
    )

    old_diagnostics = _diagnostics(old_annotation)
    corrected_diagnostics = _diagnostics(corrected_annotation)
    support = [
        {"path": corrected_path.as_posix(), "sha256": _sha256(corrected_path)},
        {
            "path": (
                "analysis_results/paper_a_manhattan/hypothesis_local_review/"
                "task238_ann2389/projection_metrics.json"
            ),
            "sha256": _sha256(
                Path(
                    "analysis_results/paper_a_manhattan/hypothesis_local_review/"
                    "task238_ann2389/projection_metrics.json"
                )
            ),
        },
    ]
    sidecar_paths = {
        evidence_type: out_dir / f"manual_sidecar_{evidence_type}_4543gt.json"
        for evidence_type in ("explicit_column_identity", "keep_distinct_contract")
    }
    for evidence_type, path in sidecar_paths.items():
        _write_json(
            path,
            _sidecar(
                evidence_type,
                reviewed_at=str(corrected_annotation["updated_at"]),
                supporting_artifacts=support,
            ),
        )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "case_name": "task238_ann2389",
        "task_id": CASE_TASK_ID,
        "source_task_id": SOURCE_TASK_ID,
        "annotation_id": OLD_ANNOTATION_ID,
        "corrected_annotation_id": CORRECTED_ANNOTATION_ID,
        "corrected_gt_id": CORRECTED_GT_ID,
        "reviewer": "human_expert",
        "reviewed_at": corrected_annotation["updated_at"],
        "correction_reason": "old GT judged inaccurate after visual review",
        "old_gt": {
            "status": "deprecated_superseded_source",
            "path": old_path.as_posix(),
            "sha256": _sha256(old_path),
        },
        "corrected_gt": {
            "status": "audit_artifact_corrected_gt_source",
            "path": corrected_path.as_posix(),
            "sha256": _sha256(corrected_path),
            "accepted_final_fix": False,
        },
        "manual_findings": {
            "explicit_column_identity": "available",
            "keep_distinct_contract": "available",
            "short_wall_exists": True,
            "endpoint_precision_note": (
                "minor endpoint offset possible; topology/identity confirmed but not "
                "sub-pixel perfect GT"
            ),
        },
        "manual_sidecars": {
            name: {
                "path": path.as_posix(),
                "sha256": _sha256(path),
                "schema_version": SIDECAR_SCHEMA_VERSION,
                "verdict": "available",
            }
            for name, path in sidecar_paths.items()
        },
        "diagnostics": {
            "old_gt": old_diagnostics,
            "corrected_gt": corrected_diagnostics,
            "old_vs_corrected": _comparison(old_diagnostics, corrected_diagnostics),
            "manual_projection_discrepancy": {
                "short_wall_exists_manual": True,
                "corrected_projection_short_wall_count": corrected_diagnostics[
                    "short_wall_diagnostics"
                ]["summary"]["short_wall_count"],
                "interpretation": (
                    "manual short-wall rationale is available, while current projection "
                    "threshold does not classify a short wall; endpoint precision remains "
                    "approximate and projection diagnostics do not replace the manual verdict"
                ),
            },
        },
        "candidate_status": {
            "candidate_specific": False,
            "candidate_count": 0,
            "candidate_preference_authorized": False,
        },
        "generated_candidate": False,
        "generated_proposal": False,
        "generated_geometry_search_result": False,
        "safety_boundary": SAFETY_BOUNDARY,
        "c6_status": "audit_blocked",
        "status_boundaries": STATUS_BOUNDARIES,
        "next_allowed_step": (
            "review corrected-GT audit and resolve remaining candidate-specific C4 and "
            "2369 manual-evidence blockers; C6.5b remains blocked"
        ),
    }
    json_path = out_dir / "hrc_gt_correction_audit_4543gt.json"
    md_path = out_dir / "hrc_gt_correction_audit_4543gt.md"
    _write_json(json_path, payload)
    comparison = payload["diagnostics"]["old_vs_corrected"]
    md_path.write_text(
        "\n".join(
            [
                "# HRC C6.5a.5 GT Correction Materialization and Diagnostic Audit",
                "",
                "- Case: `task238_ann2389`",
                "- Corrected GT: `4543gt`",
                "- Old GT: `deprecated_superseded_source`",
                "- Candidate-specific: `false`",
                "- Candidate preference authorized: `false`",
                "- Accepted/downstream/writeback: `false/false/false`",
                "- C6.5b/C3/C7/C9/C10: `blocked`",
                "",
                "## Old vs corrected",
                "",
                *[
                    f"- `{name}`: `{row['old']}` -> `{row['corrected']}`"
                    for name, row in comparison.items()
                ],
                "",
                "Manual review confirms column identity, keep-distinct topology, and a "
                "real short wall. Current projection threshold reports no short wall; "
                "this diagnostic does not replace the manual verdict.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return {
        "json": json_path,
        "markdown": md_path,
        "old_gt": old_path,
        "corrected_gt": corrected_path,
        **{f"sidecar_{name}": path for name, path in sidecar_paths.items()},
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--source", type=Path, default=SOURCE_EXPORT)
    args = parser.parse_args(argv)
    print(run(args.out_dir, args.source)["json"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
