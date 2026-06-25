"""Materialize candidate-specific C4 contract records for current review cases."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.paper_a_manhattan.candidate_specific_c4_evidence_contract import (
    SCHEMA_VERSION,
    validate_candidate_specific_c4,
)

ROOT = Path("analysis_results/paper_a_manhattan")
HRC = ROOT / "hypothesis_ranking_core"
DEFAULT_OUT_DIR = HRC / "candidate_specific_c4_contract"
CORE_3741 = HRC / "task218_ann3741/hypothesis_ranking_core.json"
REVIEW_3741 = (
    ROOT / "hypothesis_feedback_reviews/task218_ann3741_m1528_candidate_0017_review.json"
)
DRY_RUN_4543 = (
    HRC
    / "c6_5a_6_candidate_dry_run/task238_ann2389_4543gt/"
    "hrc_c6_5a_6_candidate_dry_run.json"
)
SELECTION_4543 = (
    HRC
    / "c6_5a_6_2_manual_selection_ledger/task238_ann2389_4543gt/"
    "hrc_c6_5a_6_2_manual_selection_ledger.json"
)

SAFETY_BOUNDARY = {
    "audit_only": True,
    "active_runner_role": False,
    "accepted": False,
    "downstream_recommendation": False,
    "candidate_preference_authorized": False,
    "annotation_writeback": False,
}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _source(path: Path) -> dict[str, str]:
    return {
        "path": path.as_posix(),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def _record_3741() -> dict[str, Any]:
    core = _load(CORE_3741)
    review = _load(REVIEW_3741)
    candidate_id = review["expert_selected_candidate"]
    evidence = core["constrained_evaluations"][candidate_id]["evidence_consistency"]
    record = {
        "schema_version": SCHEMA_VERSION,
        "case_name": "task218_ann3741",
        "candidate_id": candidate_id,
        "baseline_only": {"available": True, "role": "reference_only"},
        "candidate_specific_projection_delta": {
            "status": "available",
            "source": _source(CORE_3741),
            "delta_fields": {
                field: evidence[field]
                for field in (
                    "candidate_corner_column_delta",
                    "hohonet_floor_boundary_rmse_delta",
                    "hohonet_ceiling_boundary_rmse_delta",
                    "seam_consistency_delta",
                )
            },
            "scope": "HoHoNet proposal/projection delta; not image-edge evidence",
        },
        "candidate_specific_image_evidence": {
            "status": "unavailable",
            "image_edge_support": evidence.get("image_edge_support_optional"),
            "candidate_image_boundary_alignment_delta": None,
            "manual_image_evidence_note": None,
            "reason": "no candidate-specific image-edge or image-boundary evidence artifact",
        },
        "manual_visual_note": {
            "status": "available",
            "source": _source(REVIEW_3741),
            "role": "diagnostic_visual_preference_not_image_evidence",
        },
        "safety_boundary": SAFETY_BOUNDARY,
    }
    record["contract_evaluation"] = validate_candidate_specific_c4(record)
    return record


def _record_4543() -> dict[str, Any]:
    dry_run = _load(DRY_RUN_4543)
    selection = _load(SELECTION_4543)
    candidate_id = selection["selected_candidate"]
    candidate = next(
        row for row in dry_run["candidate_set"] if row["candidate_id"] == candidate_id
    )
    record = {
        "schema_version": SCHEMA_VERSION,
        "case_name": "task238_ann2389_4543gt",
        "candidate_id": candidate_id,
        "baseline_only": {"available": True, "role": "corrected_gt_reference_only"},
        "candidate_specific_projection_delta": {
            "status": "available",
            "source": _source(DRY_RUN_4543),
            "coordinate_changes": candidate["coordinate_changes"],
            "scope": "candidate geometry/projection delta; not image-boundary evidence",
        },
        "candidate_specific_image_evidence": {
            "status": "unavailable",
            "image_edge_support": None,
            "candidate_image_boundary_alignment_delta": None,
            "manual_image_evidence_note": None,
            "reason": "required candidate-specific image inputs have not been materialized",
        },
        "manual_visual_note": {
            "status": "available",
            "source": _source(SELECTION_4543),
            "role": "manual_visual_preference_only_not_image_evidence",
        },
        "safety_boundary": SAFETY_BOUNDARY,
    }
    record["contract_evaluation"] = validate_candidate_specific_c4(record)
    return record


def build_payload() -> dict[str, Any]:
    records = [_record_3741(), _record_4543()]
    return {
        "schema_version": "hrc_candidate_specific_c4_contract_audit_v1",
        "contract_schema_version": SCHEMA_VERSION,
        "records": records,
        "all_records_fail_closed": all(
            row["contract_evaluation"]["fail_closed"] for row in records
        ),
        "candidate_preference_authorized": False,
        "c6_5b_authorized": False,
        "safety_boundary": SAFETY_BOUNDARY,
    }


def run(out_dir: Path = DEFAULT_OUT_DIR) -> dict[str, Path]:
    payload = build_payload()
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "hrc_candidate_specific_c4_contract_audit.json"
    md_path = out_dir / "hrc_candidate_specific_c4_contract_audit.md"
    json_path.write_bytes(
        (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )
    rows = "\n".join(
        f"| {row['case_name']} | {row['candidate_id']} | "
        f"{row['contract_evaluation']['candidate_specific_projection_delta_available']} | "
        f"{row['contract_evaluation']['candidate_specific_image_evidence_available']} | "
        f"{row['contract_evaluation']['manual_visual_note_available']} | false |"
        for row in payload["records"]
    )
    md_path.write_bytes(
        (
            "# Candidate-specific C4 Contract Audit\n\n"
            "| case | candidate | projection delta | image evidence | visual note | preference authorized |\n"
            "|---|---|---|---|---|---|\n"
            f"{rows}\n\n"
            "Both records fail closed. Projection delta and visual preference do not "
            "substitute for candidate-specific image evidence.\n"
        ).encode("utf-8")
    )
    return {"json": json_path, "markdown": md_path}


if __name__ == "__main__":
    print(run()["json"])
