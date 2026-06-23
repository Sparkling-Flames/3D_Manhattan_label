"""Consolidate the two implemented constrained_v0 shadow-family audits."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from tools.paper_a_manhattan.run_constrained_v0_shadow_audit import (
    AUDIT_ROOT,
    DEFAULT_ASSERTION,
    DEFAULT_PROJECTION,
    build_audit_payload,
)


SCHEMA_VERSION = "constrained_v0_c3_5_consolidation_audit_v1"
DEFAULT_POSITIVE_HEIGHT_SUMMARY = (
    AUDIT_ROOT / "fixtures/height_target_positive_summary.json"
)
DEFAULT_OUT_DIR = AUDIT_ROOT / "task218_ann3741/consolidated_c3_5"
IMPLEMENTED_FAMILIES = ["column_x_alignment", "height_target_reproject"]
DEFERRED_FAMILIES = [
    "short_wall_preserving_local",
    "primary_edge_direction_family_repair",
    "floor_depth_balance",
]


def _compact(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "candidate_count": payload["candidate_count"],
        "reasons": list(payload.get("unavailable_summary", {}).get("reasons", [])),
        "generated_candidate_ids": list(payload["generated_candidate_ids"]),
        "model_derived": payload.get("model_derived"),
        "final_correctness_proof": payload["final_correctness_proof"],
        "schema_version": payload["schema_version"],
    }


def build_consolidation_payload(
    *,
    projection_path: Path = DEFAULT_PROJECTION,
    case_config_path: Path = DEFAULT_ASSERTION,
    positive_height_summary_path: Path = DEFAULT_POSITIVE_HEIGHT_SUMMARY,
) -> dict[str, Any]:
    column_real = build_audit_payload(
        projection_path=projection_path,
        case_config_path=case_config_path,
        family="column_x_alignment",
    )
    height_real = build_audit_payload(
        projection_path=projection_path,
        case_config_path=case_config_path,
        family="height_target_reproject",
    )
    height_positive = build_audit_payload(
        projection_path=projection_path,
        case_config_path=case_config_path,
        height_summary_path=positive_height_summary_path,
        family="height_target_reproject",
    )
    audits = [column_real, height_real, height_positive]
    candidates = [
        candidate
        for audit in audits
        for candidate in audit["candidate_source"]["candidate_set"]
    ]
    positive_fields = sorted(
        {
            field
            for candidate in height_positive["candidate_source"]["candidate_set"]
            for change in candidate["coordinate_changes"]
            for field in change["fields"]
        }
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "case_name": "task218_ann3741",
        "active_runner_role": False,
        "legacy_m1528_active_source_unchanged": True,
        "accepted": False,
        "downstream_recommendation": False,
        "implemented_families": list(IMPLEMENTED_FAMILIES),
        "deferred_families": list(DEFERRED_FAMILIES),
        "per_family_audit": {
            "column_x_alignment_real": _compact(column_real),
            "height_target_reproject_real": _compact(height_real),
            "height_target_reproject_positive_fixture": _compact(height_positive),
        },
        "candidate_safety_summary": {
            "generated_candidate_count": len(candidates),
            "all_shadow_only": all(row["shadow_only"] is True for row in candidates),
            "all_accepted_false": all(row["accepted"] is False for row in candidates),
            "all_downstream_recommendation_false": all(
                row["downstream_recommendation"] is False for row in candidates
            ),
            "all_active_runner_role_false": all(
                row["active_runner_role"] is False for row in candidates
            ),
            "all_annotation_writeback_false": all(
                row["annotation_writeback"] is False for row in candidates
            ),
            "positive_height_coordinate_fields": positive_fields,
            "positive_height_contains_x": any(field.endswith("_x") for field in positive_fields),
        },
        "warnings": [
            "This audit does not authorize active source replacement.",
            "This audit does not prove final geometric correctness.",
            "C6 remains not stable ranker.",
            "C7/C9/C10 remain blocked.",
        ],
        "source_artifacts": {
            "projection": projection_path.as_posix(),
            "case_config": case_config_path.as_posix(),
            "positive_height_summary": positive_height_summary_path.as_posix(),
        },
    }


def render_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Constrained v0 C3.5 Two-Family Consolidation Audit",
        "",
        f"- Case: `{payload['case_name']}`",
        f"- Implemented families: `{payload['implemented_families']}`",
        f"- Deferred families: `{payload['deferred_families']}`",
        "- Authorization: shadow-only; accepted=false; downstream_recommendation=false.",
        "",
        "## Per-family audit",
        "",
    ]
    for name, summary in payload["per_family_audit"].items():
        lines.extend(
            [
                f"- `{name}`: candidate_count=`{summary['candidate_count']}`, reasons=`{summary['reasons']}`",
            ]
        )
    lines.extend(["", "## Warnings", ""])
    lines.extend(f"- {warning}" for warning in payload["warnings"])
    lines.append("")
    return "\n".join(lines)


def run(out_dir: Path = DEFAULT_OUT_DIR, **kwargs: Any) -> dict[str, Path]:
    root = AUDIT_ROOT.resolve()
    destination = out_dir.resolve()
    if destination != root and root not in destination.parents:
        raise ValueError(f"consolidation output must stay under {AUDIT_ROOT.as_posix()}")
    payload = build_consolidation_payload(**kwargs)
    destination.mkdir(parents=True, exist_ok=True)
    json_path = destination / "constrained_v0_c3_5_consolidation_audit.json"
    markdown_path = destination / "constrained_v0_c3_5_consolidation_audit.md"
    with json_path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    with markdown_path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(render_markdown(payload))
    return {"json": json_path, "markdown": markdown_path}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--projection", type=Path, default=DEFAULT_PROJECTION)
    parser.add_argument("--case-config", type=Path, default=DEFAULT_ASSERTION)
    parser.add_argument(
        "--positive-height-summary",
        type=Path,
        default=DEFAULT_POSITIVE_HEIGHT_SUMMARY,
    )
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    print(
        run(
            args.out_dir,
            projection_path=args.projection,
            case_config_path=args.case_config,
            positive_height_summary_path=args.positive_height_summary,
        )["json"]
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
