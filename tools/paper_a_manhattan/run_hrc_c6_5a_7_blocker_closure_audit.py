"""Materialize the audit-only C6.5a.7 blocker closure pack."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path("analysis_results/paper_a_manhattan")
HRC = ROOT / "hypothesis_ranking_core"
DEFAULT_OUT_DIR = HRC / "c6_5a_7_blocker_closure"
SCHEMA_VERSION = "hrc_c6_5a_7_blocker_closure_report_v1"
SIDECAR_SCHEMA = HRC / "source_artifact_readiness_audit/manual_evidence_sidecar_schema.json"
READINESS = HRC / "source_artifact_readiness_audit/hrc_source_artifact_readiness_audit.json"
MATERIALIZATION = HRC / "evidence_input_materialization/hrc_evidence_input_materialization.json"
COMPLIANCE = HRC / "scoring_compliance_audit/hrc_scoring_compliance_audit.json"
SELECTION_LEDGER = (
    HRC
    / "c6_5a_6_2_manual_selection_ledger/task238_ann2389_4543gt/"
    "hrc_c6_5a_6_2_manual_selection_ledger.json"
)
DRY_RUN_4543 = (
    HRC
    / "c6_5a_6_candidate_dry_run/task238_ann2389_4543gt/"
    "hrc_c6_5a_6_candidate_dry_run.json"
)
CANDIDATE_ADEQUACY = HRC / "candidate_adequacy_audit/hrc_candidate_adequacy_audit.json"
CORE_3741 = HRC / "task218_ann3741/hypothesis_ranking_core.json"
REVIEW_3741 = ROOT / "hypothesis_feedback_reviews/task218_ann3741_m1528_candidate_0017_review.json"
PROJECTION_2369 = ROOT / "local_3d_projection/task218_ann2369/projection_metrics.json"
CANDIDATES_2369 = (
    ROOT
    / "single_image_manual_test/latest_gt_checked/m1518_3_candidate_semantics/"
    "task218_ann2369_m1518_3_candidate_semantics_output.json"
)
PREVIEW_2369 = ROOT / "hypothesis_local_review/task218_ann2369/local_3d_review.html"
GT_CORRECTION = (
    ROOT
    / "gt_correction_audit/task238_ann2389_4543gt/"
    "hrc_gt_correction_audit_4543gt.json"
)

SAFETY_BOUNDARY = {
    "audit_only": True,
    "active_runner_changed": False,
    "ranking_key_changed": False,
    "portfolio_changed": False,
    "accepted": False,
    "downstream_recommendation": False,
    "candidate_preference_authorized": False,
    "annotation_patch_generated": False,
    "annotation_writeback": False,
}
STATUS_BOUNDARIES = {
    "c6_5b": "blocked",
    "c3_shadow_expansion": "blocked",
    "c7_optimizer": "blocked",
    "c9_learning": "blocked",
    "c10_ranker": "blocked",
}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source(path: Path) -> dict[str, Any]:
    return {"path": path.as_posix(), "sha256": _sha256(path), "exists": path.exists()}


def _unavailable_sidecar(evidence_type: str) -> dict[str, Any]:
    questions = {
        "explicit_column_identity": [
            "Which top/bottom endpoints belong to the same real vertical layout edge?",
            "Are pairs 7/8 and the seam-adjacent pair identities visually unambiguous?",
        ],
        "keep_distinct_contract": [
            "Which nearby corners represent distinct physical room corners?",
            "Must the dense pair remain distinct under any later candidate adjustment?",
        ],
    }
    return {
        "schema_version": "hrc_manual_evidence_sidecar_v1",
        "case_name": "task218_ann2369",
        "evidence_type": evidence_type,
        "reviewer": "pending_human_expert",
        "reviewed_at": None,
        "verdict": "unavailable",
        "rationale": (
            "No recorded human verdict exists. Projection, candidate, and preview "
            "artifacts are supporting material only and cannot supply the verdict."
        ),
        "required_human_confirmation": questions[evidence_type],
        "supporting_artifacts": [
            _source(PROJECTION_2369),
            _source(CANDIDATES_2369),
            _source(PREVIEW_2369),
        ],
        "supporting_artifacts_are_manual_verdict": False,
        "safety_boundary": {
            "audit_only": True,
            "active_runner_role": False,
            "accepted": False,
            "downstream_recommendation": False,
            "annotation_writeback": False,
        },
    }


def write_2369_unavailable_sidecars(out_dir: Path = DEFAULT_OUT_DIR) -> dict[str, Path]:
    schema = _load(SIDECAR_SCHEMA)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    for evidence_type in ("explicit_column_identity", "keep_distinct_contract"):
        if evidence_type not in schema["allowed_evidence_types"]:
            raise ValueError(f"unsupported manual evidence type: {evidence_type}")
        payload = _unavailable_sidecar(evidence_type)
        path = out_dir / f"manual_sidecar_{evidence_type}_task218_ann2369_unavailable.json"
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        paths[evidence_type] = path
    return paths


def _c4_gap_table() -> list[dict[str, Any]]:
    materialization = _load(MATERIALIZATION)["cases"]
    adequacy = _load(CANDIDATE_ADEQUACY)["cases"]
    core_3741 = _load(CORE_3741)
    review_3741 = _load(REVIEW_3741)
    ledger = _load(SELECTION_LEDGER)
    dry_run = _load(DRY_RUN_4543)
    candidate_specific_3741 = any(
        evidence.get("evidence_status") == "available"
        and any(
            evidence.get(field) not in (0, 0.0, None)
            for field in (
                "candidate_corner_column_delta",
                "hohonet_floor_boundary_rmse_delta",
                "hohonet_ceiling_boundary_rmse_delta",
                "seam_consistency_delta",
            )
        )
        for row in core_3741["constrained_evaluations"].values()
        for evidence in (row.get("evidence_consistency", {}),)
    )
    return [
        {
            "case_name": "task218_ann2369",
            "candidate_available": adequacy["task218_ann2369"]["candidate_count"] > 0,
            "selected_or_review_candidate": None,
            "c4_lite_available": materialization["task218_ann2369"][
                "c4_lite_diagnostics"
            ]["evidence_status"]
            == "available",
            "c4_lite_scope": "baseline_to_baseline_only",
            "candidate_specific_c4_available": False,
            "manual_visual_preference": False,
            "accepted_final_fix": False,
            "candidate_preference_authorized": False,
            "blocker_reason": "candidate-specific C4 delta and human sidecar verdicts are absent",
        },
        {
            "case_name": "task238_ann2389",
            "candidate_available": adequacy["task238_ann2389"]["candidate_count"] > 0,
            "selected_or_review_candidate": None,
            "c4_lite_available": materialization["task238_ann2389"][
                "c4_lite_diagnostics"
            ]["evidence_status"]
            == "available",
            "c4_lite_scope": "baseline_to_baseline_only",
            "candidate_specific_c4_available": False,
            "manual_visual_preference": False,
            "accepted_final_fix": False,
            "candidate_preference_authorized": False,
            "blocker_reason": "deprecated old-GT diagnostic; candidate-specific C4 evidence absent",
        },
        {
            "case_name": "task238_ann2389_4543gt",
            "candidate_available": dry_run["candidate_count"] > 0,
            "selected_or_review_candidate": ledger["selected_candidate"],
            "c4_lite_available": False,
            "c4_lite_scope": "corrected_baseline_projection_is_not_C4_evidence",
            "candidate_specific_c4_available": False,
            "manual_visual_preference": True,
            "accepted_final_fix": False,
            "candidate_preference_authorized": False,
            "blocker_reason": "selected candidate 0003 has visual preference but no candidate-specific image evidence",
        },
        {
            "case_name": "task218_ann3741",
            "candidate_available": len(core_3741["candidate_set"]) > 0,
            "selected_or_review_candidate": review_3741["expert_selected_candidate"],
            "c4_lite_available": True,
            "c4_lite_scope": "candidate_specific_projection_delta",
            "candidate_specific_c4_available": candidate_specific_3741,
            "manual_visual_preference": True,
            "accepted_final_fix": review_3741["accepted_directly"],
            "candidate_preference_authorized": False,
            "blocker_reason": "manual explicit column identity remains incomplete; selected candidate is diagnostic only",
        },
    ]


def build_payload(sidecars: dict[str, Path]) -> dict[str, Any]:
    correction = _load(GT_CORRECTION)
    ledger = _load(SELECTION_LEDGER)
    sidecar_status = {
        evidence_type: {
            **_source(path),
            "verdict": _load(path)["verdict"],
            "human_verdict_recorded": False,
        }
        for evidence_type, path in sidecars.items()
    }
    c4_table = _c4_gap_table()
    all_c4_ready = all(row["candidate_specific_c4_available"] for row in c4_table)
    all_manual_ready = all(
        row["verdict"] == "available" for row in sidecar_status.values()
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "audit_stage": "C6.5a.7",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_artifacts": {
            "readiness": _source(READINESS),
            "evidence_materialization": _source(MATERIALIZATION),
            "scoring_compliance": _source(COMPLIANCE),
            "manual_selection_ledger": _source(SELECTION_LEDGER),
            "manual_sidecar_schema": _source(SIDECAR_SCHEMA),
            "old_gt": correction["old_gt"],
            "corrected_gt": correction["corrected_gt"],
        },
        "closed_blockers": [
            "4543gt corrected projection is independent and has four pairs",
            "4543gt explicit column identity manual evidence is available",
            "4543gt keep-distinct contract is not applicable",
            "C6.5a.6.2 manual review selection is recorded without acceptance",
            "2369 missing-manual-verdict state is now explicitly materialized",
        ],
        "remaining_blockers": [
            "2369 explicit column identity human verdict unavailable",
            "2369 keep-distinct contract human verdict unavailable",
            "candidate-specific C4 evidence absent for 2369, old 2389, and selected 4543gt candidate 0003",
            "3741 explicit column identity manual evidence remains incomplete",
            "C6.5b requires explicit user approval even after evidence readiness",
        ],
        "manual_sidecar_2369": {
            "status": "unavailable_pending_human_confirmation",
            "records": sidecar_status,
            "supporting_artifacts_are_manual_verdicts": False,
        },
        "c4_evidence_gap_table": c4_table,
        "case_by_case_readiness": {
            row["case_name"]: {
                "candidate_specific_c4_ready": row[
                    "candidate_specific_c4_available"
                ],
                "candidate_preference_authorized": False,
                "accepted_final_fix": False,
                "ready_for_c6_5b": False,
            }
            for row in c4_table
        },
        "selected_candidate_status": {
            "candidate_id": ledger["selected_candidate"],
            "selected_y_step": ledger["selected_y_step"],
            "review_only": True,
            "accepted": False,
            "active_ranking_role": False,
            "portfolio_role": False,
            "downstream_recommendation": False,
        },
        "c6_5b_readiness_decision": {
            "all_candidate_specific_c4_ready": all_c4_ready,
            "all_required_manual_sidecars_ready": all_manual_ready,
            "authorized": False,
            "decision": "blocked",
            "exact_minimal_next_blocker": (
                "obtain human-expert verdicts for task218_ann2369 explicit column "
                "identity and keep-distinct contract; then materialize genuine "
                "candidate-specific C4 evidence for the intended review candidates"
            ),
            "explicit_user_approval_still_required_if_theoretically_ready": True,
        },
        "safety_boundary": SAFETY_BOUNDARY,
        "status_boundaries": STATUS_BOUNDARIES,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    rows = "\n".join(
        "| {case_name} | {candidate_available} | {selected_or_review_candidate} | "
        "{c4_lite_available} ({c4_lite_scope}) | {candidate_specific_c4_available} | "
        "{candidate_preference_authorized} | {blocker_reason} |".format(**row)
        for row in payload["c4_evidence_gap_table"]
    )
    return (
        "# HRC C6.5a.7 Blocker Closure Report\n\n"
        "- C6.5b authorized: `false`\n"
        "- Decision: `blocked`\n"
        "- Accepted/downstream/writeback: `false/false/false`\n"
        "- Candidate preference authorized: `false`\n"
        "- C3/C7/C9/C10: `blocked`\n\n"
        "## 2369 manual sidecar\n\n"
        "- Status: `unavailable_pending_human_confirmation`\n"
        "- Supporting artifacts are manual verdicts: `false`\n\n"
        "## C4 evidence gap table\n\n"
        "| case | candidate | selected/review | C4-lite | candidate-specific C4 | preference authorized | blocker |\n"
        "|---|---|---|---|---|---|---|\n"
        f"{rows}\n\n"
        "## Remaining blockers\n\n"
        + "\n".join(f"- {row}" for row in payload["remaining_blockers"])
        + "\n\n"
        "## Minimal next blocker\n\n"
        f"- {payload['c6_5b_readiness_decision']['exact_minimal_next_blocker']}\n"
    )


def run(out_dir: Path = DEFAULT_OUT_DIR) -> dict[str, Path]:
    sidecars = write_2369_unavailable_sidecars(out_dir)
    payload = build_payload(sidecars)
    json_path = out_dir / "hrc_c6_5a_7_blocker_closure_report.json"
    md_path = out_dir / "hrc_c6_5a_7_blocker_closure_report.md"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    return {"json": json_path, "markdown": md_path, **sidecars}


if __name__ == "__main__":
    print(run()["json"])
