"""Write the read-only M15.25 expert visual verdict sidecar for task218_ann3741."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


SCHEMA_VERSION = "m15_25_visual_verdict_pack_v1"
CASE_NAME = "task218_ann3741"
DEFAULT_CANDIDATE_SEARCH = Path(
    "analysis_results/paper_a_manhattan/local_candidate_search/"
    "task218_ann3741/candidate_search.json"
)
DEFAULT_PROJECTION_METRICS = Path(
    "analysis_results/paper_a_manhattan/local_3d_projection/"
    "task218_ann3741/projection_metrics.json"
)
DEFAULT_PROJECTION_REPORT = Path(
    "analysis_results/paper_a_manhattan/local_3d_projection/"
    "task218_ann3741/projection_review_report.md"
)
DEFAULT_EXPERT_ASSERTION = Path(
    "analysis_results/paper_a_manhattan/local_candidate_search/"
    "task218_ann3741/expert_assertion.json"
)
DEFAULT_OUT_DIR = Path(
    "analysis_results/paper_a_manhattan/visual_verdict/task218_ann3741"
)
SAFETY_BOUNDARY = {
    "expert_side": True,
    "offline_local_only": True,
    "dry_run_only": True,
    "annotation_write_allowed": False,
    "annotation_patch_generated": False,
    "automatic_apply": False,
    "worker_facing": False,
    "routing_input": False,
    "formal_artifact": False,
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _source_artifact(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise FileNotFoundError(path)
    return {"path": path.as_posix(), "sha256": _sha256(path)}


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def build_visual_verdict(
    *,
    candidate_search: Path = DEFAULT_CANDIDATE_SEARCH,
    projection_metrics: Path = DEFAULT_PROJECTION_METRICS,
    projection_review_report: Path = DEFAULT_PROJECTION_REPORT,
    expert_assertion: Path | None = DEFAULT_EXPERT_ASSERTION,
) -> dict[str, Any]:
    candidate_payload = _read_json(candidate_search)
    _read_json(projection_metrics)
    projection_review_report.read_text(encoding="utf-8")
    candidate_ids = {
        str(row.get("candidate_id"))
        for row in candidate_payload.get("candidates", [])
        if isinstance(row, Mapping)
    }
    required = {f"candidate_{index}" for index in range(1, 6)}
    missing = sorted(required - candidate_ids)
    if missing:
        raise ValueError(f"candidate search is missing reviewed candidates: {missing}")

    sources: dict[str, Any] = {
        "candidate_search": _source_artifact(candidate_search),
        "projection_metrics": _source_artifact(projection_metrics),
        "projection_review_report": _source_artifact(projection_review_report),
        "expert_assertion": None,
    }
    if expert_assertion is not None and expert_assertion.is_file():
        _read_json(expert_assertion)
        sources["expert_assertion"] = _source_artifact(expert_assertion)

    per_candidate = {
        "candidate_1": {
            "verdict": "partial_diagnostic_only",
            "sufficient": False,
            "reason": "Insufficient; y-height and local wall-surface problems remain.",
        },
        "candidate_2": {
            "verdict": "largest_visible_perturbation_but_still_inadequate",
            "sufficient": False,
            "direct_fix": False,
            "reason": "Largest visible change, but it does not solve the root geometry.",
        },
        "candidate_3": {
            "verdict": "partial_diagnostic_only",
            "sufficient": False,
            "reason": "Insufficient; no root wall-surface or y-height resolution.",
        },
        "candidate_4": {
            "verdict": "partial_diagnostic_only",
            "sufficient": False,
            "reason": "Insufficient; no root wall-surface or y-height resolution.",
        },
        "candidate_5": {
            "verdict": "local_x_alignment_only",
            "sufficient": False,
            "direct_fix": False,
            "reason": "Improves local 5-6 residual but does not resolve primary edge 6-7.",
        },
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "case_name": CASE_NAME,
        "source_artifacts": sources,
        "review_context": {
            "workbench_version": "m15.23.4",
            "review_type": "expert_side_local_visual_review",
            "reviewer_input_mode": "manual_visual_verdict",
            "reviewed_candidate_ids": sorted(per_candidate),
        },
        "overall_verdict": {
            "direct_fix_available": False,
            "all_candidates_direct_ls_trial_allowed": False,
            "best_visual_candidate": "candidate_2",
            "best_visual_candidate_reason": (
                "candidate_2 has the largest visible perturbation, but remains partial "
                "and does not solve the root geometry."
            ),
            "recommended_action": "no_direct_apply_continue_algorithmic_probe",
        },
        "manual_findings": {
            "significant_geometry_change_observed": False,
            "candidate_2_largest_but_inadequate": True,
            "y_height_unresolved_pairs": [1, 2, 5, 6, 7, 8],
            "unresolved_wall_surface_footprint_regions": ["2-3", "5-6-7-8"],
            "primary_unresolved_edge": "6-7",
            "candidate_5_scope": "local_x_alignment_only",
            "visualization_clarity_is_root_cause": False,
        },
        "per_candidate_visual_verdict": per_candidate,
        "algorithm_gap": {
            "current_coverage": "local_x_y_perturbation_and_limited_joint_search",
            "missing_geometry_model": "local_wall_surface_y_height_footprint_consistency",
            "future_candidate_requirement": (
                "primary_edge_constrained_and_wall_surface_aware"
            ),
        },
        "next_step_recommendation": {
            "first": "m15_23_5_multi_candidate_compare_grid",
            "later": "m15_26_primary_edge_constrained_wall_surface_probe",
            "sequence_constraint": "archive_visual_verdict_before_m15_26",
        },
        "safety_boundary": dict(SAFETY_BOUNDARY),
    }


def render_markdown(payload: Mapping[str, Any]) -> str:
    findings = payload["manual_findings"]
    sources = payload["source_artifacts"]
    lines = [
        f"# M15.25 Visual Verdict Pack — {payload['case_name']}",
        "",
        "**No direct candidate fix is available.**",
        "",
        "## Expert verdict",
        "",
        "- candidate_2 is the largest perturbation but still inadequate; it remains a partial diagnostic, not a direct fix.",
        f"- Y-height inconsistency remains unresolved for pairs `{findings['y_height_unresolved_pairs']}`.",
        "- Wall-surface / footprint problems remain around `2-3` and `5-6-7-8`.",
        "- Primary edge `6-7` remains unresolved.",
        "- candidate_5 is local x alignment only; it does not resolve `6-7`.",
        "- No candidate may be applied directly in Label Studio.",
        "",
        "## Per-candidate visual verdict",
        "",
    ]
    for candidate_id, row in payload["per_candidate_visual_verdict"].items():
        lines.append(f"- **{candidate_id}:** `{row['verdict']}` — {row['reason']}")
    lines.extend(
        [
            "",
            "## Algorithm gap",
            "",
            "The current candidate families cover local x/y perturbations and limited joint search, but do not model the wall-surface, y-height, and footprint consistency needed for this case.",
            "",
            "## Recommended sequence",
            "",
            "1. Build `m15_23_5_multi_candidate_compare_grid` for clearer cross-candidate visual comparison.",
            "2. After this verdict is archived, consider `m15_26_primary_edge_constrained_wall_surface_probe`.",
            "",
            "## Source artifacts",
            "",
        ]
    )
    for name, source in sources.items():
        if source is None:
            lines.append(f"- {name}: `not available`")
        else:
            lines.append(f"- {name}: `{source['path']}` — `{source['sha256']}`")
    lines.extend(
        [
            "",
            "## Safety boundary",
            "",
            "Expert-side, offline, dry-run sidecar only. It produces no annotation patch, Label Studio writeback, routing input, worker-facing output, or formal artifact.",
            "",
        ]
    )
    return "\n".join(lines)


def run(
    out_dir: Path = DEFAULT_OUT_DIR,
    *,
    candidate_search: Path = DEFAULT_CANDIDATE_SEARCH,
    projection_metrics: Path = DEFAULT_PROJECTION_METRICS,
    projection_review_report: Path = DEFAULT_PROJECTION_REPORT,
    expert_assertion: Path | None = DEFAULT_EXPERT_ASSERTION,
) -> dict[str, Path]:
    payload = build_visual_verdict(
        candidate_search=candidate_search,
        projection_metrics=projection_metrics,
        projection_review_report=projection_review_report,
        expert_assertion=expert_assertion,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "visual_verdict.json"
    report_path = out_dir / "visual_verdict.md"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    report_path.write_text(render_markdown(payload), encoding="utf-8")
    return {"json": json_path, "report": report_path}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-search", type=Path, default=DEFAULT_CANDIDATE_SEARCH)
    parser.add_argument("--projection-metrics", type=Path, default=DEFAULT_PROJECTION_METRICS)
    parser.add_argument(
        "--projection-review-report", type=Path, default=DEFAULT_PROJECTION_REPORT
    )
    parser.add_argument("--expert-assertion", type=Path, default=DEFAULT_EXPERT_ASSERTION)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    paths = run(
        args.out_dir,
        candidate_search=args.candidate_search,
        projection_metrics=args.projection_metrics,
        projection_review_report=args.projection_review_report,
        expert_assertion=args.expert_assertion,
    )
    for kind, path in paths.items():
        print(f"{kind}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
