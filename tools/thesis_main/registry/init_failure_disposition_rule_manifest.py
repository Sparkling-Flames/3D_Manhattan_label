"""Create the C2-frozen failure disposition contract for T1 and V1."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def build_manifest(*, locked_round: str, contract_version: str) -> dict:
    if locked_round != "C2":
        raise ValueError("failure disposition must be frozen in C2")
    return {
        "meta": {
            "contract_version": contract_version,
            "locked_round": locked_round,
            "rule_version": "failure_disposition_v2",
            "external_incident_source": "active_logs/operational_incidents/",
        },
        "allowed_attributions": [
            "worker_caused_structural_failure",
            "policy_caused_failure",
            "external_system_failure",
        ],
        "external_evidence_requirements": {
            "required_fields": [
                "incident_id",
                "incident_type",
                "occurred_at",
                "recovered_at",
                "affected_project_ids",
                "affected_task_ids_or_scope_rule",
                "evidence_path",
                "evidence_sha256",
                "recorded_at",
                "recorded_before_outcome_review",
            ],
            "missing_evidence_disposition": "not_evaluable",
            "validation": [
                "incident_exists",
                "evidence_sha256_matches",
                "annotation_in_affected_scope",
                "annotation_timestamp_in_incident_window",
                "recorded_before_outcome_review_true",
            ],
        },
        "t1_rerun_rule": "rerun_or_administratively_censor_whole_pair",
        "v1_rerun_rule": "same_policy_arm_same_frozen_version_symmetric_reserved_capacity",
        "administrative_censor_rule": "exclude_from_delivery_adjusted_quality_denominator_and_report_by_condition_or_arm",
        "worker_caused_structural_failure": {
            "evidence": "validated_invalid_geometry_or_topology_attributable_to_worker_submission",
            "c1": "include_in_structural_failure_profile_not_iou",
            "t1_quality": "zero_in_assigned_condition",
            "v1": "record_worker_event; task_zero_only_if_terminal_not_delivered",
        },
        "policy_caused_failure": {
            "categories": ["candidate_exhaustion", "replacement_failure", "capacity_exhaustion"],
            "c1": "operational_audit_not_worker_capability",
            "v1_itt": "included_with_zero_when_not_delivered",
        },
        "external_system_failure": {
            "categories": ["platform_unavailable", "server_outage", "export_corruption"],
            "evidence_required": [
                "incident_id", "incident_type", "occurred_at", "recovered_at",
                "affected_project_ids", "affected_task_ids_or_scope_rule",
                "evidence_path", "evidence_sha256", "recorded_at",
                "recorded_before_outcome_review",
            ],
            "classification_timing": "before_condition_or_policy_outcome_review",
            "max_reruns": 1,
            "t1_pair_rule": "rerun_or_administratively_censor_whole_pair",
            "v1_rerun_rule": "same_policy_arm_same_frozen_version_symmetric_reserved_capacity",
            "fallback": "administrative_censor_and_report_by_condition_or_arm",
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Initialize C2-frozen failure disposition rule manifest.")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--locked-round", default="C2")
    parser.add_argument("--contract-version", default="v1")
    args = parser.parse_args(argv)
    manifest = build_manifest(locked_round=args.locked_round, contract_version=args.contract_version)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
