"""Audit C6.5 evidence-input readiness without generating probes or geometry."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "hrc_source_artifact_readiness_audit_v1"
ROOT = Path("analysis_results/paper_a_manhattan/hypothesis_ranking_core")
DEFAULT_OUT_DIR = ROOT / "source_artifact_readiness_audit"
DEFAULT_MANIFEST = DEFAULT_OUT_DIR / "source_artifact_manifest.json"
MANUAL_SIDECAR_SCHEMA = DEFAULT_OUT_DIR / "manual_evidence_sidecar_schema.json"
GT_CORRECTION_AUDIT = Path(
    "analysis_results/paper_a_manhattan/gt_correction_audit/"
    "task238_ann2389_4543gt/hrc_gt_correction_audit_4543gt.json"
)
CANDIDATE_DRY_RUN = Path(
    "analysis_results/paper_a_manhattan/hypothesis_ranking_core/"
    "c6_5a_6_candidate_dry_run/task238_ann2389_4543gt/"
    "hrc_c6_5a_6_candidate_dry_run.json"
)
MANUAL_SELECTION_LEDGER = ROOT / (
    "c6_5a_6_2_manual_selection_ledger/task238_ann2389_4543gt/"
    "hrc_c6_5a_6_2_manual_selection_ledger.json"
)
C6_5A_7_DIR = ROOT / "c6_5a_7_blocker_closure"
SIDECAR_2369_EXPLICIT = (
    C6_5A_7_DIR
    / "manual_sidecar_explicit_column_identity_task218_ann2369.json"
)
SIDECAR_2369_KEEP = (
    C6_5A_7_DIR
    / "manual_sidecar_keep_distinct_contract_task218_ann2369.json"
)
REFERENCE_2369_3741 = C6_5A_7_DIR / "same_image_updated_human_reference_2369_to_3741.json"

EVIDENCE_TYPES = (
    "projection_metrics",
    "floorprint_or_depth_proxy",
    "direction_family_fit",
    "parallel_family_residual",
    "explicit_column_identity",
    "keep_distinct_contract",
    "short_wall_diagnostics",
    "projection_derived_height_evidence",
    "candidate_row_height_source",
    "case_contract",
    "constrained_evaluation",
    "rankable_by_current_HRC",
    "source_candidate_rows",
    "verified_order_record",
    "c4_evidence_diagnostics",
    "c5_plane_proxy_metrics",
)
STATUSES = {
    "available_from_existing_artifact",
    "materializable_from_existing_artifact",
    "requires_manual_visual_evidence",
    "unavailable",
    "not_applicable",
}
FAMILY_REQUIREMENTS = {
    "global_height_reproject": (
        "projection_metrics",
        "projection_derived_height_evidence",
        "case_contract",
    ),
    "direction_family_azimuth_snap": (
        "projection_metrics",
        "direction_family_fit",
        "parallel_family_residual",
    ),
    "floor_depth_balance_global": ("projection_metrics", "floorprint_or_depth_proxy"),
    "multi_pair_x_alignment": (
        "projection_metrics",
        "explicit_column_identity",
        "keep_distinct_contract",
    ),
    "short_wall_preserving_floorprint_balance": (
        "projection_metrics",
        "floorprint_or_depth_proxy",
        "short_wall_diagnostics",
        "keep_distinct_contract",
    ),
}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _nested(payload: Mapping[str, Any], field: str | None) -> Any:
    value: Any = payload
    for part in (field or "").split("."):
        if part:
            value = value.get(part) if isinstance(value, Mapping) else None
    return value


def _validate_source(spec: Mapping[str, Any]) -> dict[str, Any]:
    path = Path(spec["path"])
    result = {
        "valid": False,
        "path": path.as_posix(),
        "sha256": _sha256(path) if path.exists() else None,
        "schema_version": None,
        "case_identity_valid": None,
        "required_variant": spec.get("required_variant"),
        "variant_valid": None,
        "row_count": None,
        "row_count_valid": None,
        "errors": [],
    }
    if not path.exists():
        result["errors"].append("source_artifact_missing")
        return result

    if path.suffix.lower() == ".txt":
        rows = [line.split() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        result["row_count"] = len(rows)
        result["row_count_valid"] = len(rows) >= int(spec.get("minimum_row_count", 0))
        if spec.get("expected_format") == "paired_two_column_rows":
            if len(rows) % 2 or not all(len(row) == 2 for row in rows):
                result["errors"].append("paired_two_column_rows_invalid")
        if not result["row_count_valid"]:
            result["errors"].append("row_count_below_minimum")
        result["valid"] = not result["errors"]
        return result

    payload = _load(path)
    nested_case = spec.get("required_nested_case")
    if nested_case:
        payload = payload.get(nested_case) or {}
        if not payload:
            result["errors"].append("required_nested_case_missing")

    schema_field = spec.get("schema_field")
    if schema_field:
        result["schema_version"] = _nested(payload, schema_field)
        if result["schema_version"] != spec.get("expected_schema"):
            result["errors"].append("schema_version_mismatch")

    identities = spec.get("identity_fields") or {}
    result["case_identity_valid"] = all(_nested(payload, field) == expected for field, expected in identities.items())
    if identities and not result["case_identity_valid"]:
        result["errors"].append("case_identity_mismatch")

    variant = spec.get("required_variant")
    if variant:
        variants = payload.get("variants") or []
        result["variant_valid"] = any(row.get("name") == variant for row in variants)
        if not result["variant_valid"]:
            result["errors"].append("required_variant_missing")

    true_field = spec.get("required_true_field")
    if true_field and _nested(payload, true_field) is not True:
        result["errors"].append("required_true_field_missing")

    row_field = spec.get("row_field")
    if row_field:
        rows = _nested(payload, row_field)
        result["row_count"] = len(rows) if isinstance(rows, list) else 0
        result["row_count_valid"] = result["row_count"] >= int(spec.get("minimum_row_count", 0))
        if not result["row_count_valid"]:
            result["errors"].append("row_count_below_minimum")

    result["valid"] = not result["errors"]
    return result


def _entry(
    status: str,
    validation: Mapping[str, Any] | None = None,
    *,
    hint: str | None = None,
    missing: str | None = None,
    manual: str | None = None,
    supporting: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    assert status in STATUSES
    return {
        "status": status,
        "source_artifact": validation.get("path") if validation else None,
        "sha256": validation.get("sha256") if validation else None,
        "materialization_hint": hint,
        "missing_reason": missing,
        "manual_evidence_requirement": manual,
        "manual_evidence_sidecar_schema": MANUAL_SIDECAR_SCHEMA.as_posix() if manual else None,
        "supporting_artifacts": list(supporting),
    }


def _source_entry(validation: Mapping[str, Any] | None, *, hint: str | None = None) -> dict[str, Any]:
    if not validation:
        return _entry("unavailable", missing="source artifact is not declared in manifest")
    if not validation["valid"]:
        return _entry("unavailable", validation, missing="; ".join(validation["errors"]))
    return _entry(
        "materializable_from_existing_artifact" if hint else "available_from_existing_artifact",
        validation,
        hint=hint,
    )


def _manual_entry(requirement: str, *supporting: Mapping[str, Any] | None) -> dict[str, Any]:
    refs = [
        {"path": row["path"], "sha256": row["sha256"]}
        for row in supporting
        if row and row["valid"]
    ]
    return _entry(
        "requires_manual_visual_evidence",
        manual=requirement,
        supporting=refs,
    )


def _original_metrics(projection: Mapping[str, Any] | None) -> dict[str, Any]:
    if not projection or not projection["valid"]:
        return {}
    variants = _load(Path(projection["path"])).get("variants") or []
    original = next((row for row in variants if row.get("name") == "original"), {})
    return original.get("metrics") or {}


def _case_matrix(
    case_name: str,
    sources: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    validations = {role: _validate_source(spec) for role, spec in sources.items()}
    hrc = validations.get("hrc_payload")
    projection = validations.get("projection_metrics")
    candidate = validations.get("candidate_rows")
    c4 = validations.get("c4_proposal")
    order = validations.get("verified_order_record")
    core = _load(Path(hrc["path"])) if hrc and hrc["valid"] else {}
    evaluations = list((core.get("constrained_evaluations") or {}).values())
    evaluation = evaluations[0] if evaluations else {}
    manhattan = evaluation.get("manhattan_feasibility") or {}
    metrics = _original_metrics(projection)
    floorprint = metrics.get("floorprint") or {}
    walls = floorprint.get("walls") or []
    heights = (metrics.get("heights") or {}).get("pairs") or []
    dense = (metrics.get("dense_pairs") or {}).get("pairs") or []
    has_dense_distinct = any(row.get("classification") == "dense_but_distinct_3d_corner" for row in dense)
    candidate_rows = (
        (_load(Path(candidate["path"])).get("height_reproject_candidate_rows") or [])
        if candidate and candidate["valid"]
        else []
    )

    projection_entry = _source_entry(projection)
    matrix = {
        "projection_metrics": projection_entry,
        "floorprint_or_depth_proxy": (
            _source_entry(projection) if walls else _entry("unavailable", missing="validated projection has no floorprint walls")
        ),
        "direction_family_fit": (
            _source_entry(hrc)
            if manhattan.get("direction_family_fit_status") == "available"
            else _source_entry(projection, hint="materialize audit-only C2 direction diagnostics from original projection variant")
            if walls and all(row.get("direction_deg") is not None for row in walls)
            else _entry("unavailable", missing="validated direction headings are unavailable")
        ),
        "parallel_family_residual": (
            _source_entry(hrc)
            if manhattan.get("parallel_family_residual_status") == "available"
            else _source_entry(projection, hint="materialize audit-only C2 parallel-family diagnostics")
            if walls and all(row.get("direction_deg") is not None for row in walls)
            else _entry("unavailable", missing="direction-family assignment inputs are unavailable")
        ),
        "explicit_column_identity": (
            _manual_entry(
                "manual sidecar must identify pair-level column identity; supporting artifacts are not the evidence verdict",
                candidate or hrc,
                c4,
            )
            if candidate or hrc
            else _entry("unavailable", missing="no supporting artifact for manual column identity review")
        ),
        "keep_distinct_contract": (
            _source_entry(hrc)
            if (core.get("case_contract") or {}).get("keep_distinct_pairs")
            else _source_entry(
                projection,
                hint="materialize audit-only keep-distinct input from dense_but_distinct projection relation",
            )
            if has_dense_distinct
            else _manual_entry(
                "manual sidecar must record keep-distinct verdict",
                candidate,
                projection,
            )
            if candidate
            else _entry("unavailable", missing="no keep-distinct contract or supporting artifact")
        ),
        "short_wall_diagnostics": (
            _source_entry(projection)
            if "short_wall_count" in (floorprint.get("summary") or {})
            else _entry("unavailable", missing="validated projection has no short-wall summary")
        ),
        "projection_derived_height_evidence": (
            _source_entry(hrc)
            if evaluation.get("height_consistency")
            else _source_entry(projection)
            if heights
            else _entry("unavailable", missing="no projection-derived height evidence")
        ),
        "candidate_row_height_source": (
            _source_entry(candidate)
            if candidate_rows
            else _entry("not_applicable")
            if hrc
            else _entry("unavailable", missing="no validated height candidate rows")
        ),
        "case_contract": (
            _source_entry(hrc)
            if core.get("case_contract")
            else _source_entry(
                projection,
                hint="materialize audit-only fail-closed case contract from validated projection metrics",
            )
            if walls
            else _entry("unavailable", missing="usable projection metrics are required")
        ),
        "constrained_evaluation": (
            _source_entry(hrc)
            if evaluations
            else _source_entry(
                candidate,
                hint="materialize audit-only constrained evaluations after case-contract validation",
            )
            if candidate_rows and walls
            else _entry("unavailable", missing="validated candidate rows and projection metrics are both required")
        ),
        "rankable_by_current_HRC": (
            _source_entry(hrc)
            if evaluations and core.get("case_contract")
            else _source_entry(
                candidate,
                hint="materialize audit-only HRC inputs; this does not change active runner selection",
            )
            if candidate_rows and walls
            else _entry("unavailable", missing="current HRC inputs are incomplete")
        ),
        "source_candidate_rows": (
            _source_entry(hrc)
            if (core.get("candidate_set") or [])
            else _source_entry(candidate)
            if candidate_rows
            else _entry("unavailable", missing="no validated non-baseline candidate rows")
        ),
        "verified_order_record": _source_entry(order) if order else _entry("not_applicable"),
        "c4_evidence_diagnostics": (
            _source_entry(hrc)
            if (core.get("column_evidence_source_inventory") or {}).get("evidence_status") == "available"
            else _source_entry(c4, hint="materialize audit-only C4-lite diagnostics from validated proposal rows")
            if c4
            else _entry("unavailable", missing="validated C4 proposal is unavailable")
        ),
        "c5_plane_proxy_metrics": (
            _source_entry(hrc)
            if (evaluation.get("plane_proxy_metrics") or {}).get("plane_proxy_status") == "available"
            else _source_entry(projection, hint="materialize audit-only C5 geometry proxy from projection metrics")
            if walls
            else _entry("unavailable", missing="validated projection metrics are required")
        ),
    }
    assert set(matrix) == set(EVIDENCE_TYPES)
    return matrix, validations


def _family_readiness(matrix: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    result = {}
    for family, requirements in FAMILY_REQUIREMENTS.items():
        pending = [
            name
            for name in requirements
            if matrix[name]["status"] != "available_from_existing_artifact"
        ]
        result[family] = {
            "artifact_inputs_ready": not pending,
            "pending_inputs": pending,
            "execution_allowed": False,
        }
    return result


def _corrected_gt_case(correction: Mapping[str, Any]) -> dict[str, Any]:
    projection_ref = correction["corrected_projection"]
    sidecar_ref = correction["manual_sidecars"]["explicit_column_identity"]
    projection_path = Path(projection_ref["path"])
    sidecar_path = Path(sidecar_ref["path"])
    if (
        _sha256(projection_path) != projection_ref["sha256"]
        or _sha256(sidecar_path) != sidecar_ref["sha256"]
    ):
        raise ValueError("corrected GT artifact hash drift")
    projection = _load(projection_path)
    variant = projection["variants"][0]
    projection_validation = {
        "valid": True,
        "path": projection_path.as_posix(),
        "sha256": projection_ref["sha256"],
    }
    sidecar_validation = {
        "valid": True,
        "path": sidecar_path.as_posix(),
        "sha256": sidecar_ref["sha256"],
    }
    matrix = {
        "projection_metrics": _source_entry(projection_validation),
        "floorprint_or_depth_proxy": _source_entry(projection_validation),
        "direction_family_fit": _source_entry(
            projection_validation,
            hint="materialize corrected-GT direction diagnostics",
        ),
        "parallel_family_residual": _source_entry(
            projection_validation,
            hint="materialize corrected-GT parallel-family diagnostics",
        ),
        "explicit_column_identity": _source_entry(sidecar_validation),
        "keep_distinct_contract": _entry("not_applicable"),
        "short_wall_diagnostics": _source_entry(projection_validation),
        "projection_derived_height_evidence": _source_entry(projection_validation),
        "candidate_row_height_source": _entry("not_applicable"),
        "case_contract": _source_entry(
            projection_validation,
            hint="materialize corrected-GT audit-only case contract",
        ),
        "constrained_evaluation": _entry(
            "unavailable", missing="corrected GT has no candidate-specific candidate"
        ),
        "rankable_by_current_HRC": _entry(
            "unavailable", missing="corrected GT is not candidate-specific"
        ),
        "source_candidate_rows": _entry(
            "unavailable", missing="corrected GT candidate count is zero"
        ),
        "verified_order_record": _entry("not_applicable"),
        "c4_evidence_diagnostics": _entry(
            "unavailable", missing="candidate-specific C4 evidence is absent"
        ),
        "c5_plane_proxy_metrics": _source_entry(
            projection_validation,
            hint="materialize corrected-GT C5 geometry proxy",
        ),
    }
    families = _family_readiness(matrix)
    families["short_wall_preserving_floorprint_balance"] = {
        "applicable": False,
        "artifact_inputs_ready": False,
        "pending_inputs": [],
        "not_applicable_reason": (
            "4543gt has no short wall and does not require keep-distinct preservation"
        ),
        "execution_allowed": False,
    }
    return {
        "case_name": correction["case_name"],
        "source_case_name": correction["source_case_name"],
        "corrected_gt_materialized": True,
        "corrected_gt_id": correction["corrected_gt_id"],
        "source_status": "corrected_gt_audit_source",
        "short_wall_exists": False,
        "keep_distinct_required": False,
        "manual_evidence_available_for_corrected_gt": True,
        "candidate_specific": False,
        "candidate_preference_authorized": False,
        "evidence_readiness_matrix": matrix,
        "source_validation": {
            "corrected_projection": projection_validation,
            "explicit_column_identity_sidecar": sidecar_validation,
        },
        "probe_family_readiness": families,
        "artifact_inputs_ready": False,
        "execution_allowed": False,
        "audit_only": True,
        "accepted": False,
        "downstream_recommendation": False,
        "annotation_writeback": False,
        "corrected_pair_count": len(variant["ordered_pairs"]),
    }


def build_audit_payload(manifest_path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    manifest = _load(manifest_path)
    if manifest.get("schema_version") != "hrc_source_artifact_manifest_v1":
        raise ValueError("unsupported source artifact manifest schema")

    cases = {}
    for case_name, sources in manifest["cases"].items():
        matrix, validations = _case_matrix(case_name, sources)
        families = _family_readiness(matrix)
        cases[case_name] = {
            "case_name": case_name,
            "evidence_readiness_matrix": matrix,
            "source_validation": validations,
            "probe_family_readiness": families,
            "artifact_inputs_ready": all(row["artifact_inputs_ready"] for row in families.values()),
            "execution_allowed": False,
            "audit_only": True,
            "accepted": False,
            "downstream_recommendation": False,
            "annotation_writeback": False,
        }

    correction = _load(GT_CORRECTION_AUDIT)
    if correction.get("schema_version") != "hrc_gt_correction_audit_v1":
        raise ValueError("unsupported corrected GT audit schema")
    cases["task238_ann2389"]["source_status"] = "deprecated_old_gt_diagnostic"
    cases["task238_ann2389"]["candidate_preference_authorized"] = False
    cases[correction["case_name"]] = _corrected_gt_case(correction)
    dry_run = _load(CANDIDATE_DRY_RUN)
    selection = _load(MANUAL_SELECTION_LEDGER)
    sidecar_2369 = {
        "explicit_column_identity": _load(SIDECAR_2369_EXPLICIT),
        "keep_distinct_contract": _load(SIDECAR_2369_KEEP),
    }
    if (
        dry_run.get("case_name") != "task238_ann2389_4543gt"
        or dry_run.get("candidate_count", 0) <= 0
    ):
        raise ValueError("invalid C6.5a.6.1 candidate sweep artifact")
    cases["task238_ann2389_4543gt"]["candidate_dry_run"] = {
        "generated": True,
        "path": CANDIDATE_DRY_RUN.as_posix(),
        "sha256": _sha256(CANDIDATE_DRY_RUN),
        "candidate_count": dry_run["candidate_count"],
        "candidate_preference_authorized": False,
        "execution_allowed": False,
    }
    cases["task238_ann2389_4543gt"]["manual_selection"] = {
        "selected_candidate": selection["selected_candidate"],
        "selected_y_step": selection["selected_y_step"],
        "review_only": True,
        "accepted": False,
        "candidate_preference_authorized": False,
    }
    cases["task218_ann2369"]["manual_sidecar_status"] = {
        evidence_type: {
            "path": path.as_posix(),
            "sha256": _sha256(path),
            "verdict": sidecar_2369[evidence_type]["verdict"],
            "supporting_artifacts_are_manual_verdict": False,
        }
        for evidence_type, path in {
            "explicit_column_identity": SIDECAR_2369_EXPLICIT,
            "keep_distinct_contract": SIDECAR_2369_KEEP,
        }.items()
    }
    explicit = cases["task218_ann2369"]["evidence_readiness_matrix"][
        "explicit_column_identity"
    ]
    explicit.update(
        {
            "source_artifact": SIDECAR_2369_EXPLICIT.as_posix(),
            "sha256": _sha256(SIDECAR_2369_EXPLICIT),
            "missing_reason": "pair2 unresolved due to heavy occlusion",
            "manual_evidence_requirement": "resolve pair2 column identity",
        }
    )
    cases["task218_ann2369"]["evidence_readiness_matrix"][
        "keep_distinct_contract"
    ] = _entry(
        "available_from_existing_artifact",
        {"path": SIDECAR_2369_KEEP.as_posix(), "sha256": _sha256(SIDECAR_2369_KEEP)},
    )
    cases["task218_ann2369"]["same_image_updated_human_reference"] = {
        "path": REFERENCE_2369_3741.as_posix(),
        "sha256": _sha256(REFERENCE_2369_3741),
        "reference_annotation_id": 3741,
        "verified_order": _load(REFERENCE_2369_3741)["verified_order"],
        "automatic_candidate": False,
        "accepted_final_fix": False,
    }

    artifact_inputs_ready_cases = [
        name for name, row in cases.items() if row["artifact_inputs_ready"]
    ]
    blocked_cases = [name for name in cases if name not in artifact_inputs_ready_cases]
    by_status = {
        status: sorted(
            f"{case_name}:{evidence}"
            for case_name, case in cases.items()
            for evidence, row in case["evidence_readiness_matrix"].items()
            if row["status"] == status
        )
        for status in STATUSES
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "source_manifest": {
            "path": manifest_path.as_posix(),
            "sha256": _sha256(manifest_path),
            "schema_version": manifest["schema_version"],
        },
        "manual_evidence_sidecar_schema": {
            "path": MANUAL_SIDECAR_SCHEMA.as_posix(),
            "sha256": _sha256(MANUAL_SIDECAR_SCHEMA),
            "schema_version": _load(MANUAL_SIDECAR_SCHEMA)["schema_version"],
        },
        "audit_only": True,
        "generated_candidate": False,
        "generated_proposal_manifest": False,
        "generated_geometry_variant": False,
        "active_runner_changed": False,
        "ranking_changed": False,
        "c3_changed": False,
        "accepted": False,
        "downstream_recommendation": False,
        "annotation_writeback": False,
        "corrected_gt_materialized": True,
        "corrected_gt_audit": {
            "path": GT_CORRECTION_AUDIT.as_posix(),
            "sha256": _sha256(GT_CORRECTION_AUDIT),
        },
        "c6_5a_6_candidate_dry_run": {
            "generated": True,
            "path": CANDIDATE_DRY_RUN.as_posix(),
            "sha256": _sha256(CANDIDATE_DRY_RUN),
            "candidate_count": dry_run["candidate_count"],
            "human_comparison_status": "selected_for_review_only",
            "candidate_preference_authorized": False,
        },
        "candidate_preference_authorized": {
            "task218_ann2369": False,
            "task238_ann2389": False,
            "task238_ann2389_4543gt": False,
        },
        "corrected_gt_status_summary": {
            "old_case": "task238_ann2389",
            "old_case_role": "deprecated_old_gt_diagnostic_only",
            "old_case_manual_requirements_are_corrected_gt_blockers": False,
            "corrected_case": "task238_ann2389_4543gt",
            "candidate_preference_authorized_old_case": False,
            "candidate_preference_authorized_corrected_case": False,
        },
        "c6_5a_7_blocker_closure_status": {
            "2369_explicit_column_identity": "available_with_exception_pair2",
            "2369_keep_distinct_contract": "available",
            "candidate_specific_c4_complete": False,
            "c6_5b_authorized": False,
        },
        "execution_allowed": False,
        "cases": cases,
        "artifact_inputs_ready_for_c6_5b": len(artifact_inputs_ready_cases) == len(cases),
        "artifact_inputs_ready_cases": artifact_inputs_ready_cases,
        "blocked_cases": blocked_cases,
        "materializable_inputs": by_status["materializable_from_existing_artifact"],
        "manual_evidence_required": by_status["requires_manual_visual_evidence"],
        "unavailable_inputs": by_status["unavailable"],
        "recommended_next_step": (
            "resolve task218_ann2369 pair2 column identity under occlusion; "
            "candidate-specific C4 evidence remains required"
        ),
        "status_boundaries": {
            "c3_shadow_expansion": "blocked",
            "c7_optimizer": "blocked",
            "c9_learning": "blocked",
            "c10_ranker": "blocked",
        },
    }


def render_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# HRC C6.5a.1 Source Artifact Readiness Audit",
        "",
        f"- Artifact inputs ready for C6.5b: `{payload['artifact_inputs_ready_for_c6_5b']}`",
        f"- Artifact-input-ready cases: `{payload['artifact_inputs_ready_cases']}`",
        f"- Blocked cases: `{payload['blocked_cases']}`",
        f"- Recommended next step: `{payload['recommended_next_step']}`",
        "- Execution allowed: `false`",
        "- Candidate/proposal/geometry generated: `false`",
        "",
    ]
    return "\n".join(lines)


def run(out_dir: Path = DEFAULT_OUT_DIR, manifest_path: Path = DEFAULT_MANIFEST) -> dict[str, Path]:
    payload = build_audit_payload(manifest_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "hrc_source_artifact_readiness_audit.json"
    md_path = out_dir / "hrc_source_artifact_readiness_audit.md"
    json_path.write_bytes((json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    md_path.write_bytes(render_markdown(payload).encode("utf-8"))
    return {"json": json_path, "markdown": md_path}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args(argv)
    print(run(args.out_dir, args.manifest)["json"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
