"""Audit C6.5 source readiness without generating proposals, candidates, or geometry."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "hrc_source_artifact_readiness_audit_v1"
ROOT = Path("analysis_results/paper_a_manhattan")
HRC_ROOT = ROOT / "hypothesis_ranking_core"
SPEC = Path("docs/paper_a_manhattan/HRC_C6_5_GLOBAL_HYPOTHESIS_PROBE_SPEC_v1.md")
ADEQUACY = HRC_ROOT / "candidate_adequacy_audit/hrc_candidate_adequacy_audit.json"
INPUT_PACK = HRC_ROOT / "multicase_audit_input_pack/hrc_multicase_audit_input_pack_summary.json"
PLANNER = HRC_ROOT / "shadow_global_probe_planner/hrc_shadow_global_probe_planner.json"
HRC_3741 = HRC_ROOT / "task218_ann3741/hypothesis_ranking_core.json"
PROJECTION_3741 = ROOT / "local_3d_projection/task218_ann3741/projection_metrics.json"
GT75_ORDER = ROOT / "single_image_manual_test/task533_gt75/candidate_b_annotation_3425_input_verified_order.json"
HOHONET_DIR = Path("output/mp3d_layout/HOHO_layout_aug_efficienthc_Transen1_resnet34")
DEFAULT_OUT_DIR = HRC_ROOT / "source_artifact_readiness_audit"

EVIDENCE_TYPES = (
    "projection_metrics",
    "floorprint_or_depth_proxy",
    "direction_family_fit",
    "parallel_family_residual",
    "explicit_column_identity",
    "keep_distinct_contract",
    "short_wall_diagnostics",
    "height_evidence",
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
    "global_height_reproject": ("projection_metrics", "height_evidence", "case_contract"),
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


def _entry(
    status: str,
    source: Path | None = None,
    *,
    hint: str | None = None,
    missing: str | None = None,
    manual: str | None = None,
) -> dict[str, Any]:
    assert status in STATUSES
    return {
        "status": status,
        "source_artifact": source.as_posix() if source else None,
        "sha256": _sha256(source) if source else None,
        "materialization_hint": hint,
        "missing_reason": missing,
        "manual_evidence_requirement": manual,
    }


def _original_metrics(path: Path | None) -> dict[str, Any]:
    if not path:
        return {}
    variants = _load(path).get("variants") or []
    original = next((row for row in variants if row.get("name") == "original"), {})
    return original.get("metrics") or {}


def _hohonet_path(projection: Path | None, case_name: str) -> Path | None:
    if projection:
        image = ((_load(projection).get("input_provenance") or {}).get("image") or {})
        basename = image.get("source_image_basename")
    elif case_name == "gt75_task533":
        basename = (_load(GT75_ORDER).get("metadata") or {}).get("image_title")
    else:
        basename = None
    path = HOHONET_DIR / f"{Path(basename).stem}.txt" if basename else None
    return path if path and path.exists() else None


def _available(source: Path) -> dict[str, Any]:
    return _entry("available_from_existing_artifact", source)


def _materializable(source: Path, hint: str) -> dict[str, Any]:
    return _entry("materializable_from_existing_artifact", source, hint=hint)


def _manual(source: Path, requirement: str) -> dict[str, Any]:
    return _entry(
        "requires_manual_visual_evidence",
        source,
        manual=requirement,
    )


def _unavailable(reason: str) -> dict[str, Any]:
    return _entry("unavailable", missing=reason)


def _not_applicable() -> dict[str, Any]:
    return _entry("not_applicable")


def _case_matrix(
    case_name: str,
    adequacy: Mapping[str, Any],
    pack: Mapping[str, Any] | None,
) -> dict[str, Any]:
    is_3741 = case_name == "task218_ann3741"
    core = _load(HRC_3741) if is_3741 else {}
    projection_ref = None if is_3741 else ((pack or {}).get("source_artifacts") or {}).get("projection_artifact")
    projection = PROJECTION_3741 if is_3741 else Path(projection_ref["path"]) if projection_ref else None
    candidate_ref = None if is_3741 else ((pack or {}).get("source_artifacts") or {}).get("candidate_artifact")
    candidate = HRC_3741 if is_3741 else Path(candidate_ref["path"]) if candidate_ref else None
    metrics = _original_metrics(projection)
    walls = (metrics.get("floorprint") or {}).get("walls") or []
    has_direction = bool(walls) and all(wall.get("direction_deg") is not None for wall in walls)
    dense_pairs = (metrics.get("dense_pairs") or {}).get("pairs") or []
    has_dense_distinct = any(row.get("classification") == "dense_but_distinct_3d_corner" for row in dense_pairs)
    hohonet = _hohonet_path(projection, case_name)
    evaluations = list((core.get("constrained_evaluations") or {}).values())
    evaluation = evaluations[0] if evaluations else {}
    manhattan = evaluation.get("manhattan_feasibility") or {}

    source_blocked = case_name == "ordinary_compatible"
    matrix = {
        "projection_metrics": _available(projection) if projection else _unavailable("no projection metrics source artifact"),
        "floorprint_or_depth_proxy": (
            _available(projection)
            if walls
            else _unavailable("no usable floorprint/depth proxy artifact")
        ),
        "direction_family_fit": (
            _available(HRC_3741)
            if manhattan.get("direction_family_fit_status") == "available"
            else _materializable(projection, "run existing C2 evaluator over the original projection variant")
            if projection and has_direction
            else _unavailable("direction headings are unavailable")
        ),
        "parallel_family_residual": (
            _available(HRC_3741)
            if manhattan.get("parallel_family_residual_status") == "available"
            else _materializable(projection, "run existing C2 direction-family assignment over projection walls")
            if projection and has_direction
            else _unavailable("direction-family assignments cannot be formed")
        ),
        "explicit_column_identity": (
            _unavailable("ordinary-compatible source is blocked")
            if source_blocked
            else _manual(candidate, "expert must confirm pair-level column identity; C4 diagnostics are not explicit identity")
        ),
        "keep_distinct_contract": (
            _available(HRC_3741)
            if (core.get("case_contract") or {}).get("keep_distinct_pairs")
            else _materializable(projection, "materialize keep-distinct evidence from dense_but_distinct projection relations")
            if projection and has_dense_distinct
            else _manual(candidate, "expert keep-distinct assertion is required before multi-pair x/short-wall planning")
            if candidate and not source_blocked
            else _unavailable("no keep-distinct contract or evidence source")
        ),
        "short_wall_diagnostics": (
            _available(projection)
            if "short_wall_count" in ((metrics.get("floorprint") or {}).get("summary") or {})
            else _unavailable("no projection floorprint short-wall diagnostics")
        ),
        "height_evidence": (
            _available(HRC_3741)
            if evaluation.get("height_consistency")
            else _available(projection)
            if (metrics.get("heights") or {}).get("pairs")
            else _available(candidate)
            if candidate and adequacy["variable_coverage"]["top_y_change"] and not source_blocked
            else _unavailable("no height projection or candidate evidence")
        ),
        "case_contract": (
            _available(HRC_3741)
            if core.get("case_contract")
            else _materializable(projection, "run existing fail-closed build_case_contract over usable projection metrics")
            if projection and walls
            else _unavailable("case contract would fail closed without usable projection metrics")
        ),
        "constrained_evaluation": (
            _available(HRC_3741)
            if evaluations
            else _materializable(candidate, "evaluate existing candidate rows after case-contract materialization")
            if candidate and projection and adequacy["candidate_count"] > 0
            else _unavailable("candidate rows and projection/contract inputs are not jointly available")
        ),
        "rankable_by_current_HRC": (
            _available(HRC_3741)
            if adequacy["readiness"]["rankable_by_current_HRC"]
            else _materializable(candidate, "materialize case contract and constrained evaluations; do not change active runner")
            if candidate and projection and adequacy["candidate_count"] > 0
            else _unavailable("current HRC ranking inputs are incomplete")
        ),
        "source_candidate_rows": (
            _available(candidate)
            if candidate and adequacy["candidate_count"] > 0 and not source_blocked
            else _unavailable("no existing non-baseline candidate rows")
        ),
        "verified_order_record": _available(GT75_ORDER) if case_name == "gt75_task533" else _not_applicable(),
        "c4_evidence_diagnostics": (
            _available(HRC_3741)
            if (core.get("column_evidence_source_inventory") or {}).get("evidence_status") == "available"
            else _materializable(hohonet, "run existing C4-lite parser/evaluator against existing ordered pairs")
            if hohonet and candidate and not source_blocked
            else _unavailable("no usable C4-lite proposal plus ordered-pair source")
        ),
        "c5_plane_proxy_metrics": (
            _available(HRC_3741)
            if (evaluation.get("plane_proxy_metrics") or {}).get("plane_proxy_status") == "available"
            else _materializable(projection, "run existing C2/C5 evaluator over projection metrics")
            if projection and walls
            else _unavailable("projection metrics required for C5 geometry proxy")
        ),
    }
    assert set(matrix) == set(EVIDENCE_TYPES)
    return matrix


def _family_readiness(matrix: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    ready_status = {"available_from_existing_artifact"}
    result = {}
    for family, requirements in FAMILY_REQUIREMENTS.items():
        pending = [name for name in requirements if matrix[name]["status"] not in ready_status]
        result[family] = {
            "ready": not pending,
            "pending_inputs": pending,
            "execution_allowed": False,
        }
    return result


def build_audit_payload() -> dict[str, Any]:
    adequacy = _load(ADEQUACY)
    packs = _load(INPUT_PACK)["packs"]
    planner = _load(PLANNER)
    cases = {}
    for case_name, summary in adequacy["cases"].items():
        matrix = _case_matrix(case_name, summary, packs.get(case_name))
        families = _family_readiness(matrix)
        cases[case_name] = {
            "case_name": case_name,
            "candidate_input_status": summary["candidate_input_status"],
            "source_readiness": "source_blocked" if case_name == "ordinary_compatible" else "partial",
            "evidence_readiness_matrix": matrix,
            "probe_family_readiness": families,
            "ready_for_c6_5b": all(row["ready"] for row in families.values()),
            "audit_only": True,
            "accepted": False,
            "downstream_recommendation": False,
            "annotation_writeback": False,
        }

    ready_cases = [name for name, row in cases.items() if row["ready_for_c6_5b"]]
    blocked_cases = [name for name in cases if name not in ready_cases]
    by_status = {
        status: sorted(
            f"{case_name}:{evidence}"
            for case_name, case in cases.items()
            for evidence, row in case["evidence_readiness_matrix"].items()
            if row["status"] == status
        )
        for status in STATUSES
    }
    ready = len(ready_cases) == len(cases) and not by_status["requires_manual_visual_evidence"]
    assert planner["ready_for_c6_5b_proposal_manifest"] is False
    return {
        "schema_version": SCHEMA_VERSION,
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
        "cases": cases,
        "ready_for_c6_5b_proposal_manifest": ready,
        "ready_cases": ready_cases,
        "blocked_cases": blocked_cases,
        "materializable_inputs": by_status["materializable_from_existing_artifact"],
        "manual_evidence_required": by_status["requires_manual_visual_evidence"],
        "unavailable_inputs": by_status["unavailable"],
        "recommended_next_step": (
            "materialize available source artifacts"
            if by_status["materializable_from_existing_artifact"]
            else "define manual evidence sidecar schema"
            if by_status["requires_manual_visual_evidence"]
            else "remain blocked"
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
        f"- Ready for C6.5b: `{payload['ready_for_c6_5b_proposal_manifest']}`",
        f"- Ready cases: `{payload['ready_cases']}`",
        f"- Blocked cases: `{payload['blocked_cases']}`",
        f"- Recommended next step: `{payload['recommended_next_step']}`",
        "- Candidate/proposal/geometry generated: `false`",
        "",
        "## Case matrix summary",
        "",
    ]
    for name, case in payload["cases"].items():
        counts: dict[str, int] = {}
        for row in case["evidence_readiness_matrix"].values():
            counts[row["status"]] = counts.get(row["status"], 0) + 1
        lines.append(f"- `{name}`: source=`{case['source_readiness']}`; statuses={counts}")
    lines.append("")
    return "\n".join(lines)


def run(out_dir: Path = DEFAULT_OUT_DIR) -> dict[str, Path]:
    payload = build_audit_payload()
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "hrc_source_artifact_readiness_audit.json"
    md_path = out_dir / "hrc_source_artifact_readiness_audit.md"
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
