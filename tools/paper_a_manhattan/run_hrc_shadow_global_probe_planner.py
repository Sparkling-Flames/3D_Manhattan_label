"""Plan audit-only C6.5 global probes without generating candidates or geometry."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "hrc_shadow_global_probe_planner_v1"
FAMILIES = (
    "global_height_reproject",
    "direction_family_azimuth_snap",
    "floor_depth_balance_global",
    "multi_pair_x_alignment",
    "short_wall_preserving_floorprint_balance",
)
ROOT = Path("analysis_results/paper_a_manhattan/hypothesis_ranking_core")
SPEC = Path("docs/paper_a_manhattan/HRC_C6_5_GLOBAL_HYPOTHESIS_PROBE_SPEC_v1.md")
ADEQUACY = ROOT / "candidate_adequacy_audit/hrc_candidate_adequacy_audit.json"
INPUT_PACK = ROOT / "multicase_audit_input_pack/hrc_multicase_audit_input_pack_summary.json"
HRC_3741 = ROOT / "task218_ann3741/hypothesis_ranking_core.json"
DEFAULT_OUT_DIR = ROOT / "shadow_global_probe_planner"

FAMILY_CONTRACT = {
    "global_height_reproject": {
        "allowed_variables": ["top_y", "bottom_y"],
        "forbidden_variables": ["x", "pair_order", "topology", "corner_merge", "corner_delete"],
        "required_hard_gates": ["protected_pairs", "y_permission", "height_conflict", "projection_config"],
        "expected_c2_metrics": ["height_consistency", "pair_fold_risk"],
        "expected_c5_metrics": ["dominant_height_plane_consistency"],
    },
    "direction_family_azimuth_snap": {
        "allowed_variables": ["finite_azimuth_probe_parameter"],
        "forbidden_variables": ["annotation_coordinates", "topology", "corner_merge", "corner_delete"],
        "required_hard_gates": ["direction_heading", "self_intersection", "pair_fold", "protected_pairs"],
        "expected_c2_metrics": ["direction_family_fit", "parallel_family_residual", "unresolved_edge_count"],
        "expected_c5_metrics": ["wall_plane_orthogonal_consistency"],
    },
    "floor_depth_balance_global": {
        "allowed_variables": ["finite_floor_depth_proxy_parameter"],
        "forbidden_variables": ["topology", "pair_merge", "corner_delete", "annotation_patch"],
        "required_hard_gates": ["floorprint_metrics", "self_intersection", "pair_fold", "protected_pairs"],
        "expected_c2_metrics": ["wall_residual_max", "unresolved_edge_count"],
        "expected_c5_metrics": ["floor_polygon_plane_proxy_residual"],
    },
    "multi_pair_x_alignment": {
        "allowed_variables": ["x"],
        "forbidden_variables": ["y", "topology", "pair_identity", "pair_order", "seam_ambiguous_mutation"],
        "required_hard_gates": ["column_identity", "keep_distinct", "seam_guard", "protected_pairs"],
        "expected_c2_metrics": ["local_orthogonality", "keep_distinct_margin"],
        "expected_c5_metrics": ["wall_plane_parallel_consistency"],
    },
    "short_wall_preserving_floorprint_balance": {
        "allowed_variables": ["finite_floorprint_balance_parameter"],
        "forbidden_variables": ["short_wall_delete", "dense_corner_merge", "topology"],
        "required_hard_gates": ["short_wall_contract", "keep_distinct", "self_intersection", "pair_fold"],
        "expected_c2_metrics": ["unresolved_edge_count", "local_orthogonality"],
        "expected_c5_metrics": ["floor_polygon_plane_proxy_residual"],
    },
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact(path: Path) -> dict[str, str]:
    return {"path": path.as_posix(), "sha256": _sha256(path)}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _projection_features(pack: Mapping[str, Any]) -> dict[str, bool]:
    ref = (pack.get("source_artifacts") or {}).get("projection_artifact")
    if not ref:
        return {"floorprint": False, "height": False, "short_wall": False, "dense": False}
    payload = _load(Path(ref["path"]))
    variants = payload.get("variants") or []
    original = next((row for row in variants if row.get("name") == "original"), {})
    metrics = original.get("metrics") or {}
    floorprint = metrics.get("floorprint") or {}
    return {
        "floorprint": bool(floorprint.get("walls")),
        "height": bool((metrics.get("heights") or {}).get("pairs")),
        "short_wall": "short_wall_count" in (floorprint.get("summary") or {}),
        "dense": bool((metrics.get("dense_pairs") or {}).get("pairs")),
    }


def _case_features(
    case_name: str,
    adequacy: Mapping[str, Any],
    pack: Mapping[str, Any] | None,
) -> dict[str, bool]:
    readiness = adequacy["readiness"]
    if case_name == "task218_ann3741":
        core = _load(HRC_3741)
        evaluations = list((core.get("constrained_evaluations") or {}).values())
        evaluation = evaluations[0] if evaluations else {}
        manhattan = evaluation.get("manhattan_feasibility") or {}
        plane = evaluation.get("plane_proxy_metrics") or {}
        layout = evaluation.get("layout_plausibility") or {}
        contract = core.get("case_contract") or {}
        return {
            "height": bool(evaluation.get("height_consistency")),
            "direction": manhattan.get("direction_family_fit_status") == "available"
            and manhattan.get("parallel_family_residual_status") == "available",
            "floor_depth": bool((plane.get("floor_polygon_plane_proxy_residual") or {}).get("status") == "available"),
            "column_identity": False,
            "keep_distinct": bool(contract.get("keep_distinct_pairs")),
            "short_wall": "existing_short_wall_preserved" in layout,
            "projection": readiness["has_projection_metrics"],
        }
    projection = _projection_features(pack or {})
    return {
        "height": adequacy["variable_coverage"]["top_y_change"] or projection["height"],
        "direction": False,
        "floor_depth": projection["floorprint"],
        "column_identity": False,
        "keep_distinct": False,
        "short_wall": projection["short_wall"],
        "projection": readiness["has_projection_metrics"],
    }


def _family_missing(family: str, features: Mapping[str, bool]) -> list[str]:
    requirements = {
        "global_height_reproject": ("height",),
        "direction_family_azimuth_snap": ("direction",),
        "floor_depth_balance_global": ("floor_depth",),
        "multi_pair_x_alignment": ("column_identity", "keep_distinct", "projection"),
        "short_wall_preserving_floorprint_balance": ("short_wall", "keep_distinct", "projection"),
    }
    labels = {
        "height": "height_summary_or_height_projection_metrics",
        "direction": "direction_family_fit_and_parallel_family_residual",
        "floor_depth": "floorprint_or_depth_proxy_fields",
        "column_identity": "explicit_column_identity",
        "keep_distinct": "keep_distinct_contract_or_evidence",
        "short_wall": "short_wall_diagnostics",
        "projection": "projection_metrics",
    }
    return [labels[name] for name in requirements[family] if not features[name]]


def _case_plan(
    case_name: str,
    adequacy: Mapping[str, Any],
    pack: Mapping[str, Any] | None,
) -> dict[str, Any]:
    features = _case_features(case_name, adequacy, pack)
    applicable: list[str] = []
    blocked: list[str] = []
    plans: dict[str, Any] = {}
    for family in FAMILIES:
        missing = _family_missing(family, features)
        if missing:
            blocked.append(family)
        else:
            applicable.append(family)
        plans[family] = {
            **FAMILY_CONTRACT[family],
            "planner_status": "blocked" if missing else "applicable_or_partially_applicable",
            "blocked_reason": "missing required inputs" if missing else None,
            "missing_inputs": missing,
            "execution_allowed": False,
        }

    source_artifacts = [_artifact(SPEC), _artifact(ADEQUACY), _artifact(INPUT_PACK)]
    if case_name == "task218_ann3741":
        source_artifacts.append(_artifact(HRC_3741))
    elif pack:
        source_artifacts.extend(
            ref for ref in (pack.get("source_artifacts") or {}).values() if ref
        )
    return {
        "case_name": case_name,
        "source_artifacts": source_artifacts,
        "candidate_input_status": adequacy["candidate_input_status"],
        "readiness_from_c6_4": adequacy["readiness"],
        "applicable_probe_families": applicable,
        "blocked_probe_families": blocked,
        "probe_family_plans": plans,
        "c4_evidence_usage": "diagnostic_only",
        "planner_only": True,
        "candidate_generated": False,
        "geometry_variant_generated": False,
        "audit_only": True,
        "active_runner_role": False,
        "accepted": False,
        "downstream_recommendation": False,
        "annotation_writeback": False,
    }


def build_planner_payload() -> dict[str, Any]:
    spec_text = SPEC.read_text(encoding="utf-8")
    assert all(family in spec_text for family in FAMILIES)
    adequacy = _load(ADEQUACY)
    packs = _load(INPUT_PACK)["packs"]
    cases = {
        name: _case_plan(name, summary, packs.get(name))
        for name, summary in adequacy["cases"].items()
    }
    blocked_cases = [name for name, case in cases.items() if not case["applicable_probe_families"]]
    missing = sorted(
        {
            f"{name}:{field}"
            for name, case in cases.items()
            for plan in case["probe_family_plans"].values()
            for field in plan["missing_inputs"]
        }
    )
    ready = not blocked_cases
    return {
        "schema_version": SCHEMA_VERSION,
        "cases": cases,
        "families": list(FAMILIES),
        "planner_only": True,
        "candidate_generated": False,
        "geometry_variant_generated": False,
        "active_runner_changed": False,
        "ranking_changed": False,
        "c3_changed": False,
        "accepted": False,
        "downstream_recommendation": False,
        "annotation_writeback": False,
        "ready_for_c6_5b_proposal_manifest": ready,
        "blocked_cases": blocked_cases,
        "missing_global_probe_inputs": missing,
        "recommended_next_step": (
            "C6.5b finite shadow proposal manifest design"
            if ready
            else "collect/materialize missing source artifacts"
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
        "# HRC C6.5a Shadow Global Probe Planner",
        "",
        f"- Schema: `{payload['schema_version']}`",
        f"- Ready for C6.5b: `{payload['ready_for_c6_5b_proposal_manifest']}`",
        f"- Recommended next step: `{payload['recommended_next_step']}`",
        "- Candidate generated: `false`",
        "- Geometry variant generated: `false`",
        "",
    ]
    for name, case in payload["cases"].items():
        lines.append(
            f"- `{name}`: applicable={case['applicable_probe_families']}; blocked={case['blocked_probe_families']}"
        )
    lines.append("")
    return "\n".join(lines)


def run(out_dir: Path = DEFAULT_OUT_DIR) -> dict[str, Path]:
    payload = build_planner_payload()
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "hrc_shadow_global_probe_planner.json"
    md_path = out_dir / "hrc_shadow_global_probe_planner.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    return {"json": json_path, "markdown": md_path}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args(argv)
    print(run(args.out_dir)["json"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
