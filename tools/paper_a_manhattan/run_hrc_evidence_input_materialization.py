"""Materialize audit-only HRC evidence inputs from validated existing artifacts."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.paper_a_manhattan.manhattan_case_contract import build_case_contract
from tools.paper_a_manhattan.manhattan_column_evidence import (
    compute_column_evidence,
    parse_hohonet_layout_txt,
)
from tools.paper_a_manhattan.manhattan_constrained_hypothesis_evaluator import (
    evaluate_hypothesis,
)


SCHEMA_VERSION = "hrc_evidence_input_materialization_v1"
ROOT = Path("analysis_results/paper_a_manhattan/hypothesis_ranking_core")
READINESS_DIR = ROOT / "source_artifact_readiness_audit"
DEFAULT_MANIFEST = READINESS_DIR / "source_artifact_manifest.json"
DEFAULT_READINESS = READINESS_DIR / "hrc_source_artifact_readiness_audit.json"
DEFAULT_OUT_DIR = ROOT / "evidence_input_materialization"
TARGET_CASES = ("task218_ann2369", "task238_ann2389")
TARGET_INPUTS = {
    "direction_family_fit",
    "parallel_family_residual",
    "case_contract",
    "constrained_evaluation",
    "rankable_by_current_HRC",
    "c4_evidence_diagnostics",
    "c5_plane_proxy_metrics",
}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validated_sources(
    case_name: str,
    manifest: Mapping[str, Any],
    readiness: Mapping[str, Any],
) -> dict[str, Path]:
    case_validation = readiness["cases"][case_name]["source_validation"]
    sources: dict[str, Path] = {}
    for role, spec in manifest["cases"][case_name].items():
        validation = case_validation.get(role) or {}
        path = Path(spec["path"])
        if not validation.get("valid"):
            raise ValueError(f"{case_name}:{role}:source validation failed")
        if validation.get("sha256") != _sha256(path):
            raise ValueError(f"{case_name}:{role}:source hash drift")
        sources[role] = path
    return sources


def _original_variant(path: Path) -> dict[str, Any]:
    payload = _load(path)
    rows = [row for row in payload.get("variants", []) if row.get("name") == "original"]
    if len(rows) != 1:
        raise ValueError(f"{path}: expected exactly one original variant")
    return rows[0]


def _materializable_inputs(case_name: str, readiness: Mapping[str, Any]) -> list[str]:
    matrix = readiness["cases"][case_name]["evidence_readiness_matrix"]
    return sorted(
        name
        for name in TARGET_INPUTS
        if matrix[name]["status"] == "materializable_from_existing_artifact"
    )


def _case_payload(
    case_name: str,
    manifest: Mapping[str, Any],
    readiness: Mapping[str, Any],
) -> dict[str, Any]:
    sources = _validated_sources(case_name, manifest, readiness)
    original = _original_variant(sources["projection_metrics"])
    pairs = list(original["ordered_pairs"])
    metrics = original["metrics"]
    contract = build_case_contract(pairs, projection_metrics=metrics)

    c4_source = parse_hohonet_layout_txt(
        sources["c4_proposal"],
        width=int(original["projection"]["width"]),
        height=int(original["projection"]["height"]),
    )
    c4 = compute_column_evidence(
        c4_source,
        pairs,
        pairs,
        coordinate_mode=str(original["projection"]["coordinate_mode"]),
    )
    original_with_evidence = copy.deepcopy(original)
    original_with_evidence["evidence"] = c4
    evaluation = evaluate_hypothesis(
        original_with_evidence,
        original_with_evidence,
        pairs,
        pairs,
        contract,
    )
    manhattan = evaluation["manhattan_feasibility"]
    candidate_rows = _load(sources["candidate_rows"]).get("height_reproject_candidate_rows") or []
    materialized = _materializable_inputs(case_name, readiness)

    return {
        "case_name": case_name,
        "source_artifacts": {
            role: {"path": path.as_posix(), "sha256": _sha256(path)}
            for role, path in sources.items()
        },
        "processed_materializable_inputs": materialized,
        "skipped_manual_inputs": sorted(
            name
            for name, row in readiness["cases"][case_name]["evidence_readiness_matrix"].items()
            if row["status"] == "requires_manual_visual_evidence"
        ),
        "candidate_rows_read_only": {
            "row_count": len(candidate_rows),
            "modified": False,
            "used_as_projected_candidate_variant": False,
        },
        "direction_family_fit": manhattan["direction_family_fit"],
        "parallel_family_residual": manhattan["parallel_family_residual"],
        "case_contract": contract,
        "constrained_evaluation": {
            "scope": "baseline_original_diagnostic_only",
            "baseline_original_not_candidate_evaluation": True,
            "evaluation_status": evaluation["evaluation_status"],
            "decision_class": evaluation["decision_class"],
            "feasibility": evaluation["feasibility"],
            "manhattan_feasibility": evaluation["manhattan_feasibility"],
            "height_consistency": evaluation["height_consistency"],
            "layout_plausibility": evaluation["layout_plausibility"],
            "column_evidence": evaluation["column_evidence"],
            "plane_proxy_metrics": evaluation["plane_proxy_metrics"],
        },
        "rankable_by_current_HRC_input_summary": {
            "rankable": False,
            "reason": "existing candidate rows have no validated candidate projection variants; baseline diagnostic is not rankable candidate input",
            "candidate_row_count": len(candidate_rows),
            "candidate_projection_variant_count": 0,
            "ranking_key_materialized": False,
            "portfolio_materialized": False,
        },
        "c4_lite_diagnostics": {
            **c4,
            "baseline_to_baseline_materialization": True,
            "candidate_preference_claim": False,
        },
        "c5_plane_proxy_metrics": evaluation["plane_proxy_metrics"],
        "audit_only": True,
        "execution_allowed": False,
        "accepted": False,
        "downstream_recommendation": False,
        "annotation_writeback": False,
    }


def build_payload(
    manifest_path: Path = DEFAULT_MANIFEST,
    readiness_path: Path = DEFAULT_READINESS,
) -> dict[str, Any]:
    manifest = _load(manifest_path)
    readiness = _load(readiness_path)
    if manifest.get("schema_version") != "hrc_source_artifact_manifest_v1":
        raise ValueError("unsupported source manifest schema")
    if readiness.get("schema_version") != "hrc_source_artifact_readiness_audit_v1":
        raise ValueError("unsupported readiness audit schema")
    cases = {
        case_name: _case_payload(case_name, manifest, readiness)
        for case_name in TARGET_CASES
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "source_manifest": {
            "path": manifest_path.as_posix(),
            "sha256": _sha256(manifest_path),
        },
        "source_readiness_audit": {
            "path": readiness_path.as_posix(),
            "sha256": _sha256(readiness_path),
        },
        "cases": cases,
        "processed_cases": list(TARGET_CASES),
        "processed_status": "materializable_from_existing_artifact_only",
        "manual_evidence_processed": False,
        "supporting_artifacts_used_as_manual_verdicts": False,
        "generated_candidate": False,
        "generated_proposal_manifest": False,
        "generated_geometry_variant": False,
        "active_runner_changed": False,
        "ranking_changed": False,
        "c3_changed": False,
        "audit_only": True,
        "execution_allowed": False,
        "accepted": False,
        "downstream_recommendation": False,
        "annotation_writeback": False,
        "c6_status": "audit_blocked",
        "c6_5b_authorized": False,
        "conclusion": "C6 remains audit-blocked; C6.5b is not authorized unless a later scoring/evaluator compliance audit approves the evidence/ranking contract.",
        "recommended_next_step": "audit-only scoring/evaluator compliance review of materialized evidence inputs",
        "status_boundaries": {
            "c3_shadow_expansion": "blocked",
            "c7_optimizer": "blocked",
            "c9_learning": "blocked",
            "c10_ranker": "blocked",
        },
    }


def render_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# HRC C6.5a.2 Evidence Input Materialization",
        "",
        f"- Processed cases: `{payload['processed_cases']}`",
        "- Candidate/proposal/geometry generated: `false`",
        "- Execution allowed: `false`",
        "- C6.5b authorized: `false`",
        f"- Conclusion: {payload['conclusion']}",
        "",
    ]
    for name, case in payload["cases"].items():
        lines.append(
            f"- `{name}`: inputs={case['processed_materializable_inputs']}; rankable=`{case['rankable_by_current_HRC_input_summary']['rankable']}`"
        )
    lines.append("")
    return "\n".join(lines)


def run(
    out_dir: Path = DEFAULT_OUT_DIR,
    manifest_path: Path = DEFAULT_MANIFEST,
    readiness_path: Path = DEFAULT_READINESS,
) -> dict[str, Path]:
    payload = build_payload(manifest_path, readiness_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "hrc_evidence_input_materialization.json"
    md_path = out_dir / "hrc_evidence_input_materialization.md"
    json_path.write_bytes((json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    md_path.write_bytes(render_markdown(payload).encode("utf-8"))
    return {"json": json_path, "markdown": md_path}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--readiness", type=Path, default=DEFAULT_READINESS)
    args = parser.parse_args(argv)
    print(run(args.out_dir, args.manifest, args.readiness)["json"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
