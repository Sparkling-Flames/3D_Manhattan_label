from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.thesis_main.analysis import c1_materialize_quality_table
from tools.thesis_main.analysis import c1_materialize_worker_profile_sidecar
from tools.thesis_main.analysis import c1_materialize_worker_state
from tools.thesis_main.analysis.c1_live_collection_monitor import safe, truthy, write_json
from tools.thesis_main.analysis.materialize_worker_scene_profile_candidates import materialize_worker_scene_profile_candidates
from tools.thesis_main.analysis.routing.evidence_snapshot import materialize_evidence_snapshot
from tools.thesis_main.analysis.routing.offline_replay_v2 import offline_replay_v2
from tools.thesis_main.analysis.routing.temporal_replay import materialize_temporal_replay
from tools.thesis_main.analysis.vfinal_artifact_utils import canonical_path, sha256_file, sha256_json


REQUIRED_C1_ARTIFACTS = (
    "c1_canonical_meta_observations.csv", "c1_canonical_geometry.jsonl", "c1_model_artifact_provenance.csv", "c1_quality_annotations.csv",
    "worker_task_tag_observations_C1.csv", "task_tag_three_state_summary_C1.csv", "worker_response_style_C1.csv",
    "model_issue_harmonization_C1.csv", "geometry_pairwise_similarity_C1.csv", "geometry_worker_task_loo_C1.csv",
    "geometry_stability_C1.csv", "geometry_metric_coverage_C1.csv", "worker_scene_profile_candidates_C1.csv",
    "routing_evidence_snapshot_C1.csv", "routing_replay_scaffold_C1.csv", "routing_temporal_replay_C1.csv",
)


def _artifact_freshness(output_dir: Path, *, input_status: str) -> dict[str, Any]:
    missing, empty, stale = [], [], []
    for name in REQUIRED_C1_ARTIFACTS:
        path = output_dir / name
        if not path.exists():
            missing.append(name)
            continue
        try:
            if path.suffix == ".jsonl":
                rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
            else:
                rows = list(__import__("csv").DictReader(path.open(encoding="utf-8-sig")))
        except (OSError, UnicodeError, ValueError):
            stale.append(name)
            continue
        if not rows:
            empty.append(name)
        if any(not str(row.get("source_sha256", "")).strip() or not str(row.get("dependency_bundle_id", "")).strip() for row in rows):
            stale.append(name)
        for row in rows:
            source = canonical_path(row.get("source_artifact", ""))
            declared = str(row.get("source_sha256", ""))
            if not source.exists() or sha256_file(source) != declared:
                stale.append(name)
            try:
                dependencies = json.loads(row.get("dependency_bundle_json") or "[]")
                expected = sha256_json({"rule_version": row.get("rule_version", ""), "dependencies": sorted(dependencies, key=lambda item: item["path"])})
                dependency_paths = [item["path"] for item in dependencies]
                if len(dependency_paths) != len(set(dependency_paths)) or expected != row.get("dependency_bundle_id") or any(not Path(item["path"]).exists() or sha256_file(Path(item["path"])) != item.get("sha256") for item in dependencies):
                    stale.append(name)
            except (TypeError, ValueError, KeyError):
                stale.append(name)
    return {"fresh": not missing and not empty and not stale, "missing": missing, "empty": empty, "stale": sorted(set(stale)), "input_status": input_status}


def _snapshot_manifest_fresh(path: Path) -> bool:
    if not path.exists():
        return False
    rows = list(__import__("csv").DictReader(path.open(encoding="utf-8-sig")))
    return bool(rows) and all(item.get("snapshot_path") and Path(item["snapshot_path"]).exists() and sha256_file(Path(item["snapshot_path"])) == item.get("sha256") for item in rows)


def _formal_adjudication(path: Path | None, bundle_sha256: str) -> dict[str, Any]:
    if not path or not path.exists():
        return {"valid": False, "reason": "missing_formal_closeout_adjudication_manifest"}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"valid": False, "reason": "invalid_formal_closeout_adjudication_manifest"}
    valid = payload.get("status") == "approved" and payload.get("approved") is True and all(payload.get(field) for field in ("manifest_id", "approved_by", "approved_at")) and payload.get("input_bundle_sha256") == bundle_sha256
    return {"valid": bool(valid), "reason": "approved" if valid else "formal_closeout_adjudication_not_approved_or_stale", "sha256": sha256_file(path), "temporal_replay_not_required": bool(valid and payload.get("temporal_replay_status") == "not_required")}


def _expand_sidecar_dependencies(paths: list[Path]) -> list[Path]:
    """Flatten the dependencies actually declared by every generated sidecar."""
    expanded = list(paths)
    for path in paths:
        if not path.exists() or path.suffix not in {".csv", ".jsonl"}:
            continue
        try:
            rows = ([json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.suffix == ".jsonl" else list(__import__("csv").DictReader(path.open(encoding="utf-8-sig"))))
            for row in rows:
                expanded.extend(Path(item["path"]) for item in json.loads(row.get("dependency_bundle_json") or "[]"))
        except (OSError, UnicodeError, ValueError, KeyError, TypeError):
            continue
    unique: dict[str, Path] = {}
    for path in expanded:
        resolved = canonical_path(path)
        unique[str(resolved)] = resolved
    return list(unique.values())


def _blockers(summary: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if summary["quality_table_blockers"]:
        blockers.append("quality_table_blockers")
    if summary["dt_backflow"]:
        blockers.append("dt_backflow")
    if not summary["profile_sidecar_generated"]:
        blockers.append("profile_sidecar_missing")
    if summary["profile_freeze_status"] != "C1_provisional":
        blockers.append("profile_freeze_status_not_C1_provisional")
    if not summary["artifacts_fresh"]:
        blockers.append("closeout_artifacts_missing_or_stale")
    if not summary["formal_inputs_present"]:
        blockers.append("formal_c1_annotation_data_missing")
    if not summary["artifacts_fresh"]:
        blockers.append("artifact_freshness_blocked")
    if not summary.get("formal_adjudication", {}).get("valid"):
        blockers.append("formal_closeout_adjudication_missing_invalid_or_stale")
    if not summary["formal_closeout_ready"]:
        blockers.append("thesis_facing_closeout_blocked_pending_formal_closeout")
    if not summary["c2_decision_chain_ready"]:
        blockers.append("c2_decision_chain_blocked_pending_formal_closeout")
    return blockers


def build_gate_summary(
    quality_table_summary: dict[str, Any],
    worker_state_summary: dict[str, Any],
    c2_gap_summary: dict[str, Any],
    c2_draft_summary: dict[str, Any],
    worker_profile_sidecar_summary: dict[str, Any],
    profile_summary_path: Path,
    vfinal_sidecar_summaries: dict[str, Any] | None = None,
    artifact_bundle: dict[str, Any] | None = None,
    *,
    input_status: str = "dry_run",
    artifact_freshness: dict[str, Any] | None = None,
    canonicalization_summary: dict[str, Any] | None = None,
    adjudication: dict[str, Any] | None = None,
    snapshot_manifest_fresh: bool = False,
) -> dict[str, Any]:
    profile_generated = profile_summary_path.exists() and bool(worker_profile_sidecar_summary)
    summary = {
        "quality_table_summary": quality_table_summary,
        "worker_state_summary": worker_state_summary,
        "c2_gap_summary": c2_gap_summary,
        "c2_draft_summary": c2_draft_summary,
        "worker_profile_sidecar_summary": worker_profile_sidecar_summary,
        "quality_table_blockers": list(quality_table_summary.get("blockers") or []),
        "r_u_estimated": truthy(quality_table_summary.get("r_u_estimated")) or truthy(worker_state_summary.get("r_u_estimated")) or truthy(worker_profile_sidecar_summary.get("r_u_calib_estimated")),
        "dt_backflow": truthy(quality_table_summary.get("dt_backflow")),
        "worker_state_provisional": truthy(worker_state_summary.get("provisional")),
        "c2_direct_assignment": truthy(c2_gap_summary.get("direct_assignment")),
        "reserve_only": truthy(c2_draft_summary.get("reserve_only")),
        "reserve_capacity_shortfall_count": int(c2_draft_summary.get("reserve_capacity_shortfall_count") or 0),
        "profile_sidecar_generated": profile_generated,
        "profile_freeze_status": safe(worker_profile_sidecar_summary.get("profile_freeze_status")),
        "p1_descriptive_directional_check_status": safe(worker_profile_sidecar_summary.get("p1_descriptive_directional_check_status")) or "not_evaluable",
        "formal_predictive_validity_status": safe(worker_profile_sidecar_summary.get("formal_predictive_validity_status")) or "not_run_blocked",
        "p1_informed_diagnostic_profile_status": safe(worker_profile_sidecar_summary.get("p1_informed_diagnostic_profile_status")) or "incomplete",
        "full_profile_ready": truthy(worker_profile_sidecar_summary.get("full_profile_ready")),
        "full_diagnostic_profile_ready": truthy(worker_profile_sidecar_summary.get("full_diagnostic_profile_ready")),
        "p1_bundle_structurally_complete": truthy(worker_profile_sidecar_summary.get("p1_bundle_structurally_complete")),
        "pending_adjudication_count": int(worker_profile_sidecar_summary.get("pending_adjudication_count") or 0),
        "structural_contract_valid": bool(quality_table_summary.get("canonical_meta_fresh")) and not quality_table_summary.get("blockers"),
        "formal_inputs_present": input_status == "formal" and bool(quality_table_summary.get("canonical_meta_fresh")),
        "artifacts_fresh": bool((artifact_freshness or {}).get("fresh")),
        "artifact_freshness": artifact_freshness or {},
        "dry_run_contract_exercised": input_status != "formal",
        "raw_pipeline_ready": bool(quality_table_summary.get("canonical_meta_fresh")) and not quality_table_summary.get("blockers") and input_status == "formal",
        "provisional_sidecar_ready": False,
        "formal_closeout_ready": False,
        "thesis_facing_closeout_ready": False,
        "c2_decision_chain_ready": False,
        "r_u_freeze": False,
        "c2_freeze": False,
        "formal_routing_conclusion_allowed": False,
        "passed": False,
        "blocked_for_launch": True,
        "blockers": [],
        "warnings": list(worker_profile_sidecar_summary.get("warnings") or []),
        "passed_semantics": "provisional_pipeline_only_formal_closeout_and_c2_decisions_blocked",
        "vfinal_sidecars": vfinal_sidecar_summaries or {},
        "analysis_contract_ready": False,
        "formal_c1_annotation_data_present": input_status == "formal" and bool(quality_table_summary.get("canonical_meta_fresh")),
        "dry_run_is_formal_data": input_status == "formal",
        "closeout_input_bundle": artifact_bundle or {},
        "canonicalization_summary": canonicalization_summary or {},
        "formal_adjudication": adjudication or {},
        "raw_snapshot_manifest_fresh": snapshot_manifest_fresh,
    }
    canonical = canonicalization_summary or {}
    temporal_status = safe((vfinal_sidecar_summaries or {}).get("routing_temporal_replay", {}).get("status"))
    summary["formal_closeout_ready"] = bool(
        input_status == "formal" and canonical.get("structural_integrity_passed") is True and canonical.get("collection_completeness_passed") is True
        and snapshot_manifest_fresh and not quality_table_summary.get("blockers") and int(quality_table_summary.get("n_quality_rows") or 0) > 0
        and int(quality_table_summary.get("independence_not_evaluable_count") or 0) == 0 and summary["artifacts_fresh"]
        and summary["pending_adjudication_count"] == 0 and temporal_status in {"candidate_only", "not_required_by_adjudication"}
        and summary["r_u_estimated"] and summary["full_profile_ready"] and bool((adjudication or {}).get("valid"))
    )
    summary["thesis_facing_closeout_ready"] = summary["formal_closeout_ready"]
    summary["c2_decision_chain_ready"] = summary["formal_closeout_ready"] and not summary["dt_backflow"]
    summary["r_u_freeze"] = summary["formal_closeout_ready"] and truthy(worker_state_summary.get("r_u_freeze"))
    summary["c2_freeze"] = summary["c2_decision_chain_ready"] and truthy(c2_draft_summary.get("c2_freeze"))
    summary["formal_routing_conclusion_allowed"] = summary["c2_freeze"]
    summary["passed"] = summary["formal_closeout_ready"]
    summary["analysis_contract_ready"] = summary["formal_closeout_ready"]
    summary["passed_semantics"] = "formal_closeout_ready" if summary["formal_closeout_ready"] else ("non_formal_dry_run" if input_status != "formal" else "formal_closeout_blocked")
    summary["blockers"] = _blockers(summary)
    summary["blocked_for_launch"] = bool(summary["blockers"])
    return summary


def write_markdown(path: Path, summary: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# C1 Closeout Dryrun Gate Summary",
        "",
        f"- passed: {str(summary['passed']).lower()}",
        f"- blocked_for_launch: {str(summary['blocked_for_launch']).lower()}",
        f"- passed_semantics: {summary['passed_semantics']}",
        f"- p1_descriptive_directional_check_status: {summary['p1_descriptive_directional_check_status']}",
        f"- formal_predictive_validity_status: {summary['formal_predictive_validity_status']}",
        "",
        "## Gate Flags",
        f"- quality_table_blockers: {', '.join(summary['quality_table_blockers']) if summary['quality_table_blockers'] else 'none'}",
        f"- r_u_estimated: {str(summary['r_u_estimated']).lower()}",
        f"- dt_backflow: {str(summary['dt_backflow']).lower()}",
        f"- worker_state_provisional: {str(summary['worker_state_provisional']).lower()}",
        f"- c2_direct_assignment: {str(summary['c2_direct_assignment']).lower()}",
        f"- reserve_only: {str(summary['reserve_only']).lower()}",
        f"- reserve_capacity_shortfall_count: {summary['reserve_capacity_shortfall_count']}",
        f"- profile_sidecar_generated: {str(summary['profile_sidecar_generated']).lower()}",
        f"- profile_freeze_status: {summary['profile_freeze_status']}",
        f"- structural_contract_valid: {str(summary['structural_contract_valid']).lower()}",
        f"- formal_inputs_present: {str(summary['formal_inputs_present']).lower()}",
        f"- artifacts_fresh: {str(summary['artifacts_fresh']).lower()}",
        f"- dry_run_contract_exercised: {str(summary['dry_run_contract_exercised']).lower()}",
        f"- formal_closeout_ready: {str(summary['formal_closeout_ready']).lower()}",
        f"- thesis_facing_closeout_ready: {str(summary['thesis_facing_closeout_ready']).lower()}",
        f"- c2_decision_chain_ready: {str(summary['c2_decision_chain_ready']).lower()}",
        f"- r_u_freeze: {str(summary['r_u_freeze']).lower()}",
        f"- c2_freeze: {str(summary['c2_freeze']).lower()}",
        f"- formal_routing_conclusion_allowed: {str(summary['formal_routing_conclusion_allowed']).lower()}",
        "",
        "## Blockers",
        *(f"- {item}" for item in summary["blockers"]),
        "" if summary["blockers"] else "- none",
        "",
        "## Warnings",
        *(f"- {item}" for item in summary["warnings"]),
        "" if summary["warnings"] else "- none",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def materialize(
    canonical_csv: Path,
    assignment_manifest: Path,
    reserve_pool_csv: Path,
    output_dir: Path,
    c2_output_dir: Path,
    candidate_inventory_csv: Path,
    min_r_u_tasks: int,
    min_scene_support: int,
    min_calib: int,
    epsilon_r: float,
    tasks_per_fill: int,
    p1_artifacts: list[Path] | None = None,
    p1_task_evidence_csv: Path | None = None,
    p1_worker_status_csv: Path | None = None,
    p1_geometry_task_scores: Path | None = None,
    p1_worker_geometry_profile: Path | None = None,
    input_status: str = "dry_run",
    independence_audit_csv: Path | None = None,
    retrospective_provenance_amendment_csv: Path | None = None,
    temporal_event_csv: Path | None = None,
    temporal_policy_manifest: Path | None = None,
    formal_closeout_adjudication_manifest: Path | None = None,
) -> dict[str, Any]:
    quality_summary = c1_materialize_quality_table.materialize(canonical_csv, output_dir, candidate_inventory_csv, input_status=input_status)
    quality_csv = output_dir / "c1_quality_annotations.csv"
    worker_summary = c1_materialize_worker_state.materialize(quality_csv, [assignment_manifest], output_dir, min_r_u_tasks)
    worker_state_csv = output_dir / "worker_state_snapshot_C1.csv"
    # C2 gap and assignment materialization are deliberately blocked until formal closeout.
    gap_summary = {"materialization_blocked": True, "direct_assignment": False}
    c2_summary = {"materialization_blocked": True, "reserve_only": False, "reserve_capacity_shortfall_count": 0}
    profile_summary = c1_materialize_worker_profile_sidecar.materialize(
        quality_csv,
        worker_state_csv,
        output_dir,
        p1_artifacts,
        p1_task_evidence_csv,
        p1_worker_status_csv,
        p1_geometry_task_scores,
        p1_worker_geometry_profile,
    )
    scene_summary = materialize_worker_scene_profile_candidates(
        output_dir / "worker_task_tag_observations_C1.csv",
        output_dir,
        geometry_loo_csv=output_dir / "geometry_worker_task_loo_C1.csv",
        input_status=input_status,
        min_task_support=min_scene_support,
    )
    routing_snapshot_summary = materialize_evidence_snapshot(
        quality_csv, output_dir / "routing_evidence_snapshot_C1.csv", input_status=input_status,
    )
    scaffold_summary = offline_replay_v2(
        output_dir / "routing_evidence_snapshot_C1.csv",
        output_dir / "routing_replay_scaffold_C1.csv", input_status=input_status,
    )
    temporal_summary = materialize_temporal_replay(
        temporal_event_csv or output_dir / "routing_arrival_events_C1.csv",
        output_dir / "routing_temporal_replay_C1.csv",
        policy_manifest=temporal_policy_manifest, canonical_csv=canonical_csv, quality_csv=quality_csv, input_status=input_status,
    )
    artifact_freshness = _artifact_freshness(output_dir, input_status=input_status)
    canonicalization_summary_path = output_dir / "c1_canonicalization_summary.json"
    canonicalization_summary = json.loads(canonicalization_summary_path.read_text(encoding="utf-8")) if canonicalization_summary_path.exists() else {}
    raw_snapshot_manifest = Path(canonicalization_summary.get("raw_input_manifest") or output_dir / "raw_inputs" / "raw_input_snapshot_manifest.csv")
    if independence_audit_csv and canonicalization_summary.get("independence_audit_source_sha256") and sha256_file(independence_audit_csv) != canonicalization_summary.get("independence_audit_source_sha256"):
        artifact_freshness["fresh"] = False; artifact_freshness.setdefault("stale", []).append("independence_audit_binding")
    if retrospective_provenance_amendment_csv and canonicalization_summary.get("retrospective_amendment_source_sha256") and sha256_file(retrospective_provenance_amendment_csv) != canonicalization_summary.get("retrospective_amendment_source_sha256"):
        artifact_freshness["fresh"] = False; artifact_freshness.setdefault("stale", []).append("retrospective_amendment_binding")
    vfinal_sidecars = {
        "worker_scene_profile_candidates": scene_summary,
        "routing_evidence_snapshot": routing_snapshot_summary,
        "routing_replay_scaffold": scaffold_summary,
        "routing_temporal_replay": temporal_summary,
        "geometry_sidecars_present": (output_dir / "geometry_worker_task_loo_C1.csv").exists(),
        "formal_c1_annotation_data_present": input_status == "formal" and bool(quality_summary.get("canonical_meta_fresh")),
    }
    profile_summary_path = output_dir / "worker_profile_sidecar_C1.summary.json"
    bundle_paths = [canonical_csv, assignment_manifest, reserve_pool_csv, candidate_inventory_csv, raw_snapshot_manifest, Path("tools/label_studio/label_studio_c1_xml_freeze_manifest_v1.json"), output_dir / "c1_export_merge_manifest.csv", output_dir / "c1_runtime_task_mapping.csv", *[output_dir / name for name in REQUIRED_C1_ARTIFACTS], Path("docs/thesis_main/meta_label_three_state_rule_manifest_v1.json"), Path("docs/thesis_main/model_issue_harmonization_rule_manifest_v1.json"), Path("docs/thesis_main/geometry_loo_candidate_rule_manifest_v1.json"), Path("docs/thesis_main/sequential_routing_candidate_rule_manifest_v1.json"), *([independence_audit_csv] if independence_audit_csv else []), *([retrospective_provenance_amendment_csv] if retrospective_provenance_amendment_csv else []), *([temporal_event_csv] if temporal_event_csv else []), *([temporal_policy_manifest] if temporal_policy_manifest else [])]
    bundle_paths = _expand_sidecar_dependencies(bundle_paths)
    artifact_bundle = {"bundle_version": "c1_closeout_input_bundle_v1", "artifacts": [{"path": str(path), "exists": path.exists(), "sha256": sha256_file(path) if path.exists() else ""} for path in bundle_paths]}
    artifact_bundle["bundle_sha256"] = __import__("hashlib").sha256(json.dumps(artifact_bundle["artifacts"], sort_keys=True).encode("utf-8")).hexdigest()
    adjudication = _formal_adjudication(formal_closeout_adjudication_manifest, artifact_bundle["bundle_sha256"])
    if adjudication.get("temporal_replay_not_required"):
        vfinal_sidecars["routing_temporal_replay"]["status"] = "not_required_by_adjudication"
        artifact_freshness["empty"] = [name for name in artifact_freshness.get("empty", []) if name != "routing_temporal_replay_C1.csv"]
        artifact_freshness["stale"] = [name for name in artifact_freshness.get("stale", []) if name != "routing_temporal_replay_C1.csv"]
        artifact_freshness["fresh"] = not artifact_freshness.get("missing") and not artifact_freshness.get("empty") and not artifact_freshness.get("stale")
    gate_summary = build_gate_summary(quality_summary, worker_summary, gap_summary, c2_summary, profile_summary, profile_summary_path, vfinal_sidecars, artifact_bundle, input_status=input_status, artifact_freshness=artifact_freshness, canonicalization_summary=canonicalization_summary, adjudication=adjudication, snapshot_manifest_fresh=_snapshot_manifest_fresh(raw_snapshot_manifest))
    gate_summary["closeout_input_bundle"] = artifact_bundle
    (output_dir / "c1_closeout_input_bundle.json").write_text(json.dumps(artifact_bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    write_json(output_dir / "c1_closeout_dryrun_gate_summary.json", gate_summary)
    write_markdown(output_dir / "c1_closeout_dryrun_gate_summary.md", gate_summary)
    return gate_summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run C1 closeout dryrun materialization chain without official launch approval.")
    parser.add_argument("--canonical-csv", type=Path, required=True)
    parser.add_argument("--assignment-manifest", type=Path, required=True)
    parser.add_argument("--reserve-pool-csv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--c2-output-dir", type=Path, required=True)
    parser.add_argument("--candidate-inventory-csv", type=Path, required=True)
    parser.add_argument("--min-r-u-tasks", type=int, required=True)
    parser.add_argument("--min-scene-support", type=int, required=True)
    parser.add_argument("--min-calib", type=int, required=True)
    parser.add_argument("--epsilon-r", type=float, required=True)
    parser.add_argument("--tasks-per-fill", type=int, required=True)
    parser.add_argument("--p1-artifact", type=Path, action="append", default=[])
    parser.add_argument("--p1-task-evidence-csv", type=Path)
    parser.add_argument("--p1-worker-status-csv", type=Path)
    parser.add_argument("--p1-geometry-task-scores", type=Path)
    parser.add_argument("--p1-worker-geometry-profile", type=Path)
    parser.add_argument("--input-status", choices=("dry_run", "formal"), default="dry_run")
    parser.add_argument("--independence-audit-csv", type=Path)
    parser.add_argument("--retrospective-provenance-amendment-csv", type=Path)
    parser.add_argument("--temporal-event-csv", type=Path)
    parser.add_argument("--temporal-policy-manifest", type=Path)
    parser.add_argument("--formal-closeout-adjudication-manifest", type=Path)
    args = parser.parse_args(argv)
    summary = materialize(
        args.canonical_csv,
        args.assignment_manifest,
        args.reserve_pool_csv,
        args.output_dir,
        args.c2_output_dir,
        args.candidate_inventory_csv,
        args.min_r_u_tasks,
        args.min_scene_support,
        args.min_calib,
        args.epsilon_r,
        args.tasks_per_fill,
        args.p1_artifact,
        args.p1_task_evidence_csv,
        args.p1_worker_status_csv,
        args.p1_geometry_task_scores,
        args.p1_worker_geometry_profile,
        args.input_status,
        args.independence_audit_csv,
        args.retrospective_provenance_amendment_csv,
        args.temporal_event_csv,
        args.temporal_policy_manifest,
        args.formal_closeout_adjudication_manifest,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
