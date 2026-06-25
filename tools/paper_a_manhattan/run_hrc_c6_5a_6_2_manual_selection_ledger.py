"""Materialize the audit-only manual selection ledger for corrected GT 4543gt."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

SCHEMA_VERSION = "hrc_c6_5a_6_2_manual_selection_ledger_v1"
CASE_NAME = "task238_ann2389_4543gt"
SELECTED_CANDIDATE = "c6_5a_6_1_candidate_0003"
SOURCE = Path(
    "analysis_results/paper_a_manhattan/hypothesis_ranking_core/"
    "c6_5a_6_candidate_dry_run/task238_ann2389_4543gt/"
    "hrc_c6_5a_6_candidate_dry_run.json"
)
DEFAULT_OUT_DIR = Path(
    "analysis_results/paper_a_manhattan/hypothesis_ranking_core/"
    "c6_5a_6_2_manual_selection_ledger/task238_ann2389_4543gt"
)
STATUS_BOUNDARIES = {
    "c6_5b": "blocked",
    "c3_shadow_expansion": "blocked",
    "c7_optimizer": "blocked",
    "c9_learning": "blocked",
    "c10_ranker": "blocked",
}
SAFETY_BOUNDARY = {
    "audit_only": True,
    "accepted": False,
    "downstream_recommendation": False,
    "candidate_preference_authorized": False,
    "annotation_patch_generated": False,
    "annotation_writeback": False,
}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_payload(source_path: Path = SOURCE) -> dict[str, Any]:
    source = _load(source_path)
    candidates = {row["candidate_id"]: row for row in source["candidate_set"]}
    if source.get("case_name") != CASE_NAME or SELECTED_CANDIDATE not in candidates:
        raise ValueError("C6.5a.6.1 source case/candidate mismatch")
    selected = candidates[SELECTED_CANDIDATE]
    if selected.get("y_step") != 0.75:
        raise ValueError("selected candidate y-step must be +0.75")
    rejected_reasons = {
        "c6_5a_6_1_candidate_0001": "height L1 is higher",
        "c6_5a_6_1_candidate_0002": "acceptable but visually less preferred than +0.75",
        "c6_5a_6_1_candidate_0004": (
            "turn max is lower, but height L1 rebounds and movement is larger"
        ),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "case_name": CASE_NAME,
        "audit_stage": "C6.5a.6.2",
        "source_artifact": {
            "path": source_path.as_posix(),
            "sha256": _sha256(source_path),
            "schema_version": source["schema_version"],
        },
        "reviewer": "human_expert",
        "review_status": "completed_manual_selection_for_review_only",
        "selected_candidate": SELECTED_CANDIDATE,
        "selected_y_step": 0.75,
        "selection_basis": [
            "manual visual best among C6.5a.6.1 candidates",
            "height L1 is the lowest among C6.5a.6.1 candidates",
            "turn max is comparatively low",
            "movement is acceptable",
        ],
        "selected_diagnostics": {
            "movement": selected["diagnostics"]["movement_cost"][
                "movement_l1_normalized"
            ],
            "height_l1": selected["diagnostics"]["height_consistency"][
                "height_outlier_l1"
            ],
            "wall_max": selected["diagnostics"]["wall_residual_max"],
            "turn_max": selected["diagnostics"]["turn_residual_max"],
            "self_intersection": selected["diagnostics"]["self_intersection"],
            "pair_count": selected["pair_count"],
            "short_wall_count": selected["diagnostics"]["short_wall_count"],
        },
        "less_preferred_candidates": [
            {
                "candidate_id": candidate_id,
                "y_step": candidates[candidate_id]["y_step"],
                "reason": reason,
            }
            for candidate_id, reason in rejected_reasons.items()
        ],
        "selection_scope": "manual_audit_preference_only_not_automatic_acceptance",
        "remaining_blockers": [
            "candidate-specific C4 evidence absent",
            "2369 manual sidecar pending",
            "C6.5b remains blocked",
        ],
        "safety_boundary": SAFETY_BOUNDARY,
        "status_boundaries": STATUS_BOUNDARIES,
    }


def render_markdown(payload: Mapping[str, Any]) -> str:
    diagnostics = payload["selected_diagnostics"]
    rows = "\n".join(
        f"| {row['candidate_id']} | {row['y_step']:+.2f} | {row['reason']} |"
        for row in payload["less_preferred_candidates"]
    )
    return (
        "# C6.5a.6.2 Manual Selection Ledger\n\n"
        f"- Case: `{payload['case_name']}`\n"
        f"- Selected candidate: `{payload['selected_candidate']}`\n"
        f"- Selected y-step: `{payload['selected_y_step']:+.2f}`\n"
        "- Status: manual selected for review only\n"
        "- Accepted/downstream/preference/writeback: `false/false/false/false`\n"
        "- C6.5b/C3/C7/C9/C10: `blocked`\n\n"
        "## Selection basis\n\n"
        + "\n".join(f"- {reason}" for reason in payload["selection_basis"])
        + "\n\n"
        "## Selected diagnostics\n\n"
        f"- movement: `{diagnostics['movement']:.6f}`\n"
        f"- height L1: `{diagnostics['height_l1']:.6f}`\n"
        f"- wall max: `{diagnostics['wall_max']:.6f}`\n"
        f"- turn max: `{diagnostics['turn_max']:.6f}`\n\n"
        "## Less preferred candidates\n\n"
        "| candidate | y-step | reason |\n"
        "|---|---:|---|\n"
        f"{rows}\n\n"
        "## Remaining blockers\n\n"
        + "\n".join(f"- {blocker}" for blocker in payload["remaining_blockers"])
        + "\n"
    )


def run(out_dir: Path = DEFAULT_OUT_DIR) -> dict[str, Path]:
    payload = build_payload()
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "hrc_c6_5a_6_2_manual_selection_ledger.json"
    md_path = out_dir / "hrc_c6_5a_6_2_manual_selection_ledger.md"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    return {"json": json_path, "markdown": md_path}


if __name__ == "__main__":
    print(run()["json"])
