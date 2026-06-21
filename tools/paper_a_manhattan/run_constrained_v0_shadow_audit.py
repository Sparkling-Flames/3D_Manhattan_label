"""Materialize a read-only constrained_v0 column-x shadow audit."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from tools.paper_a_manhattan.manhattan_case_contract import build_case_contract
from tools.paper_a_manhattan.manhattan_constrained_v0_candidate_source import (
    build_column_x_alignment_shadow_source,
    build_height_target_reproject_shadow_source,
)
from tools.paper_a_manhattan.run_m1528_semantic_action_library import (
    DEFAULT_ASSERTION,
    DEFAULT_PROJECTION,
)


AUDIT_ROOT = Path("analysis_results/paper_a_manhattan/constrained_v0_shadow_audit")
DEFAULT_OUT_DIR = AUDIT_ROOT / "task218_ann3741"


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _source(path: Path) -> dict[str, str]:
    return {"path": path.as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def build_audit_payload(
    *,
    projection_path: Path = DEFAULT_PROJECTION,
    case_config_path: Path = DEFAULT_ASSERTION,
    evidence_path: Path | None = None,
    height_summary_path: Path | None = None,
    family: str = "column_x_alignment",
) -> dict[str, Any]:
    projection = _read(projection_path)
    original = next(
        (row for row in projection.get("variants", []) if row.get("name") == "original"),
        None,
    )
    if original is None or not isinstance(original.get("ordered_pairs"), list):
        raise ValueError("projection artifact must contain original ordered_pairs")
    case_config = _read(case_config_path)
    contract = (
        case_config
        if "movable_fields_by_pair" in case_config
        else build_case_contract(
            original["ordered_pairs"], case_config, original.get("metrics", {})
        )
    )
    evidence = _read(evidence_path) if evidence_path else {}
    height_summary = _read(height_summary_path) if height_summary_path else {}
    config = {
        "coordinate_mode": projection.get(
            "coordinate_mode_requested", projection.get("coordinate_mode")
        ),
        "width": projection.get("width"),
        "height": projection.get("height"),
        "camera_height": projection.get("camera_height"),
    }
    if family == "column_x_alignment":
        source = build_column_x_alignment_shadow_source(
            original["ordered_pairs"], contract, evidence, config
        )
    elif family == "height_target_reproject":
        source = build_height_target_reproject_shadow_source(
            original["ordered_pairs"], contract, height_summary, evidence, config
        )
    else:
        raise ValueError(f"unsupported shadow audit family: {family}")
    reasons = list(source.get("unavailable_summary", {}).get("reasons", []))
    reason_counts = Counter(reason.split(":", 1)[-1] for reason in reasons)
    candidates = source["candidate_set"]
    explicit_identity = (
        evidence.get("column_identity_status") is not None
        or bool(evidence.get("column_identity_by_pair"))
    )
    explicit_height_summary = (
        family == "height_target_reproject"
        and height_summary.get("height_target_source")
        in {"explicit_fixture", "explicit_manual_height_summary"}
        and height_summary.get("formula_status") == "explicit_after_y"
    )
    return {
        "schema_version": (
            "constrained_v0_column_x_shadow_audit_v1"
            if family == "column_x_alignment"
            else "constrained_v0_height_target_shadow_audit_v1"
        ),
        "case_name": projection.get("case_name") or case_config.get("case_name"),
        "family": family,
        "active_runner_role": False,
        "shadow_only": True,
        "accepted": False,
        "downstream_recommendation": False,
        "legacy_m1528_active_source_unchanged": True,
        "candidate_count": source["candidate_count"],
        "unavailable_summary": source.get("unavailable_summary", {}),
        "generated_candidate_ids": [row["candidate_id"] for row in candidates],
        "changed_pair_indices": {
            row["candidate_id"]: row["changed_pair_indices"] for row in candidates
        },
        "coordinate_changes_summary": {
            row["candidate_id"]: row["coordinate_changes"] for row in candidates
        },
        "rejection_reason_counts": dict(sorted(reason_counts.items())),
        "evidence_status": evidence.get("evidence_status", "unavailable"),
        "column_identity_status": evidence.get("column_identity_status", "unavailable"),
        "missing_required_evidence_for_column_x_alignment": (
            family == "column_x_alignment" and not explicit_identity
        ),
        "seam_guard_summary": {
            "seam_safe": bool(evidence.get("seam_safe", contract.get("seam_safe", False))),
            "seam_ambiguity": bool(evidence.get("seam_ambiguity", False)),
            "seam_ambiguous_pairs": list(evidence.get("seam_ambiguous_pairs", [])),
            "seam_margin": source["source_provenance"].get("seam_margin"),
        },
        "margin_used": source["source_provenance"].get("column_separation_margin"),
        "default_margin_used": source["source_provenance"].get("default_margin_used"),
        "min_x_residual_used": None,
        "height_target_status": height_summary.get("height_target_status", "unavailable"),
        "height_outlier_pairs": list(height_summary.get("height_outlier_pairs", [])),
        "target_height": height_summary.get(
            "dominant_height_target", height_summary.get("target_height")
        ),
        "formula_status": height_summary.get("formula_status", "unavailable"),
        "positive_shadow_fixture": explicit_height_summary,
        "explicit_height_summary": explicit_height_summary,
        "model_derived": False if explicit_height_summary else None,
        "accepted_recommendation": False,
        "final_correctness_proof": False,
        "candidate_source": source,
        "source_artifacts": {
            "projection": _source(projection_path),
            "case_config": _source(case_config_path),
            "evidence": _source(evidence_path) if evidence_path else None,
            "height_summary": _source(height_summary_path) if height_summary_path else None,
        },
    }


def render_markdown(payload: Mapping[str, Any]) -> str:
    title = (
        "Constrained v0 Column-X Shadow Audit"
        if payload["family"] == "column_x_alignment"
        else "Constrained v0 Height Target Shadow Audit"
    )
    return "\n".join(
        [
            f"# {title}",
            "",
            f"- Case: `{payload.get('case_name')}`",
            f"- Family: `{payload['family']}`",
            f"- Candidate count: `{payload['candidate_count']}`",
            f"- Evidence status: `{payload['evidence_status']}`",
            f"- Column identity status: `{payload['column_identity_status']}`",
            f"- Missing required evidence: `{payload['missing_required_evidence_for_column_x_alignment']}`",
            f"- Generated candidate ids: `{payload['generated_candidate_ids']}`",
            f"- Rejection reasons: `{payload['rejection_reason_counts']}`",
            f"- Margin used: `{payload['margin_used']}`",
            f"- Seam guard: `{payload['seam_guard_summary']}`",
            f"- Height target status: `{payload['height_target_status']}`",
            f"- Height outlier pairs: `{payload['height_outlier_pairs']}`",
            f"- Target height: `{payload['target_height']}`",
            f"- Formula status: `{payload['formula_status']}`",
            f"- Positive shadow fixture / explicit summary: `{payload['positive_shadow_fixture']}`",
            f"- Model-derived: `{payload['model_derived']}`",
            "- This is not an accepted recommendation and not a final correctness proof.",
            "- Authorization: shadow-only; accepted=false; downstream_recommendation=false.",
            "- This audit does not establish final geometric correctness.",
            "",
        ]
    )


def run(
    out_dir: Path = DEFAULT_OUT_DIR,
    **kwargs: Any,
) -> dict[str, Path]:
    root = AUDIT_ROOT.resolve()
    destination = out_dir.resolve()
    if destination != root and root not in destination.parents:
        raise ValueError(f"shadow audit output must stay under {AUDIT_ROOT.as_posix()}")
    payload = build_audit_payload(**kwargs)
    destination.mkdir(parents=True, exist_ok=True)
    json_path = destination / "constrained_v0_shadow_audit.json"
    report_path = destination / "constrained_v0_shadow_audit.md"
    with json_path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    with report_path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(render_markdown(payload))
    return {"json": json_path, "markdown": report_path}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--projection", type=Path, default=DEFAULT_PROJECTION)
    parser.add_argument("--case-config", type=Path, default=DEFAULT_ASSERTION)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--height-summary", type=Path)
    parser.add_argument(
        "--family",
        choices=("column_x_alignment", "height_target_reproject"),
        default="column_x_alignment",
    )
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    print(
        run(
            args.out_dir,
            projection_path=args.projection,
            case_config_path=args.case_config,
            evidence_path=args.evidence,
            height_summary_path=args.height_summary,
            family=args.family,
        )["json"]
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
