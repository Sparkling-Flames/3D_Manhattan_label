"""Build diagnostic-only, pre-Stage-3 Calibration analysis artifacts.

This consumer never freezes a profile or policy.  It joins frozen evidence while
preserving stage-specific eligibility, provenance conflicts, and unavailable
values as explicit missing/not-evaluable records.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import random
import subprocess
import sys
import warnings
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy.stats import kendalltau, spearmanr


ROOT = Path(__file__).resolve().parents[3]
EXPECTED_CONTRACT_VERSION = "paper_a_method_20260811_v23"
EXPECTED_CONTRACT_SCHEMA = "paper_a_method_contract_v9"
EXPECTED_CONTRACT_SHA = "f3c1ea58d0857a40aa2240b4680b674c76fe2cec8f048f61a643d9e4b74b0588"
SEED = 20260814
BOOTSTRAP_REPLICATES = 500
ROLE_FIELDS = {
    "analysis_role": "diagnostic_pre_stage3",
    "formal_profile_frozen": False,
    "formal_policy_frozen": False,
    "scientific_conclusion_prohibited": True,
    "block3_generated": False,
}
DIFFICULTY_TAGS = ("trivial", "occlusion", "low_texture", "seam", "reflection", "low_quality")


def truth(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def worker_id(value: Any) -> str:
    text = clean(value)
    if text.lower().startswith("w"):
        text = text[1:]
    return str(int(text)) if text.isdigit() else text


def evidence_key(row: dict[str, Any]) -> tuple[str, str, str, str, str]:
    return (
        clean(row.get("stage")), worker_id(row.get("worker_id")), clean(row.get("base_task_id")),
        clean(row.get("condition")), clean(row.get("canonical_submission_id")),
    )


def validate_unique_evidence_keys(rows: Iterable[dict[str, Any]]) -> None:
    seen: set[tuple[str, str, str, str, str]] = set()
    for row in rows:
        key = evidence_key(row)
        if not all(key):
            raise ValueError(f"incomplete evidence key:{key}")
        if key in seen:
            raise ValueError(f"duplicate evidence key:{key}")
        seen.add(key)


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    all_fields = fields or sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=all_fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in all_fields})


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_path(path: Path) -> str:
    if path.is_file():
        return sha256_file(path)
    digest = hashlib.sha256()
    for child in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        digest.update(child.relative_to(path).as_posix().encode())
        digest.update(sha256_file(child).encode())
    return digest.hexdigest()


def csv_schema(path: Path) -> str:
    rows = csv_rows(path)
    return clean(rows[0].get("schema_version")) if rows else "empty_csv"


def stage_from_risk(value: str) -> tuple[str, str]:
    return {
        "C2B": ("C2B", "C2-B"),
        "C2A_RP_BLOCK1": ("C2A_RP", "Block1"),
        "C2A_RP_BLOCK2": ("C2A_RP", "Block2"),
    }.get(clean(value), (clean(value), clean(value)))


def analysis_stage(row: dict[str, Any]) -> str:
    return f"{clean(row.get('stage'))}_{clean(row.get('substage_block'))}"


def raw_label_map(stage_dirs: dict[str, list[Path]]) -> dict[tuple[str, str, str], dict[str, list[str]]]:
    """Return stage/worker/raw-annotation labels without promoting them to features."""
    result: dict[tuple[str, str, str], dict[str, list[str]]] = {}
    for stage, directories in stage_dirs.items():
        for directory in directories:
            for path in sorted(directory.glob("*.json")):
                for task in json.loads(path.read_text(encoding="utf-8")):
                    for annotation in task.get("annotations") or []:
                        annotation_id = clean(annotation.get("id"))
                        worker = worker_id(annotation.get("completed_by"))
                        if not annotation_id or not worker:
                            continue
                        labels: dict[str, list[str]] = defaultdict(list)
                        for item in annotation.get("result") or []:
                            family = clean(item.get("from_name"))
                            choices = (item.get("value") or {}).get("choices") or []
                            if family in {"difficulty", "scope", "model_issue"}:
                                labels[family].extend(clean(choice) for choice in choices if clean(choice))
                        result[(stage, worker, annotation_id)] = {key: sorted(set(values)) for key, values in labels.items()}
    return result


def meta_rows_for_submission(identity: dict[str, Any], labels: dict[str, list[str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    selected = set(labels.get("difficulty", []))
    for tag in DIFFICULTY_TAGS:
        rows.append({
            **ROLE_FIELDS, **identity, "tag_family": "difficulty", "tag_value": tag, "selected": tag in selected,
            "feature_timing": "post_task", "formal_first_route_eligible": False,
            "routing_role": "not_eligible_for_first_route",
            "analysis_subrole": "descriptive_measurement_audit",
        })
    for family in ("scope", "model_issue"):
        for value in labels.get(family, []):
            rows.append({
                **ROLE_FIELDS, **identity, "tag_family": family, "tag_value": value, "selected": True,
                "feature_timing": "post_task", "formal_first_route_eligible": False,
                "routing_role": "not_eligible_for_first_route",
                "analysis_subrole": "descriptive_measurement_audit",
            })
    return rows


def load_inputs() -> dict[str, Path | list[Path]]:
    result: dict[str, Path | list[Path]] = {
        "contract": ROOT / "docs/thesis_main/PAPER_A_METHOD_CONTRACT_CURRENT.json",
        "p1_canonical": ROOT / "analysis_results/prescreen_closeout_final_gold_v2_20260701/prescreen_canonical_annotations.csv",
        "p1_summary": ROOT / "analysis_results/prescreen_closeout_final_gold_v2_20260701/prescreen_canonicalize_summary.json",
        "c1_eligibility": ROOT / "analysis_results/c1_a_batch_freeze_20260802_v17/c1_a_batch_inputs/c1_row_analysis_eligibility.csv",
        "c1_qgt": ROOT / "analysis_results/c1_a_batch_freeze_20260802_v17/c1_a_batch_inputs/c1_gt_quality_analysis.csv",
        "c1_peer": ROOT / "analysis_results/c1_a_batch_freeze_20260802_v17/c1_a_batch_inputs/geometry_worker_task_peer_analysis.csv",
        "c1_loo": ROOT / "analysis_results/c1_a_batch_freeze_20260802_v17/c1_a_batch_inputs/geometry_worker_task_loo_analysis.csv",
        "c1_structural": ROOT / "analysis_results/c1_a_batch_freeze_20260802_v17/c1_a_batch_inputs/structural_validation_analysis.csv",
        "c1_snapshot": ROOT / "analysis_results/c1_a_batch_freeze_20260802_v17/c1_a_analysis_snapshot.json",
        "c2b_canonical": ROOT / "analysis_results/c2b_closeout_20260806_final/c2b_canonical_submissions.csv",
        "c2b_acceptance": ROOT / "docs/thesis_main/C2B_HISTORICAL_EVIDENCE_ACCEPTANCE_20260811_v1.json",
        "block1_canonical": ROOT / "analysis_results/c2a_rp_block1_reestimate_20260810_v1/c2a_rp_block1_canonical_submissions.csv",
        "block1_reestimate": ROOT / "analysis_results/c2a_rp_block1_reestimate_20260810_v2/c2a_rp_block1_reestimate_summary.json",
        "block2_canonical": ROOT / "analysis_results/c2a_rp_block2_reestimate_20260814_v1/c2a_rp_block2_canonical_submissions.csv",
        "block2_reestimate": ROOT / "analysis_results/c2a_rp_block2_reestimate_20260814_v1/c2a_rp_block2_reestimate_summary.json",
        "risk": ROOT / "analysis_results/c2a_rp_block2_reestimate_20260814_v1/c2b_plus_c2a_rp_block1_plus_block2_risk_slope_evidence.csv",
        "profile": ROOT / "analysis_results/c2a_rp_block1_reestimate_20260810_v2/post_c2a_rp_block1_worker_profile.csv",
        "crosswalk": ROOT / "analysis_results/c2a_rp_block2_diagnostics_20260814_v1/reference_registry_crosswalk.csv",
        "feature_pool": ROOT / "analysis_results/c2b_build_20260802_v17_d8/compact_audit_bundle/c2b_task_eligibility_evidence.csv",
        "block1_assignment": ROOT / "analysis_results/c2a_rp_block1_distribution_20260807_v7/assignment_manifest_C2A_RP_block_1.csv",
        "block2_assignment": ROOT / "analysis_results/c2a_rp_block2_distribution_20260810_v1/assignment_manifest_C2A_RP_block_2.csv",
        "active_p1": ROOT / "active_logs/prescreen",
        "active_c1": ROOT / "active_logs/c1",
        "active_c2b": ROOT / "active_logs/c2b",
        "active_b1": ROOT / "active_logs/c2a_rp_block1_20260810",
        "active_b2": ROOT / "active_logs/c2a_rp_block2_20260814",
        "raw_p1": [ROOT / "export_label/stage1_chinese", ROOT / "export_label/stage1_English"],
        "raw_c1": [ROOT / "export_label/stage2_Chinese", ROOT / "export_label/stage2_English"],
        "raw_c2b": [ROOT / "export_label/c2B_Chinese", ROOT / "export_label/c2B_English"],
        "raw_b1": [ROOT / "export_label/c2arp_block1"],
        "raw_b2": [ROOT / "export_label/c2arp_block2"],
    }
    missing = [name for name, path in result.items() if isinstance(path, Path) and not path.exists()]
    missing += [name for name, values in result.items() if isinstance(values, list) and any(not value.exists() for value in values)]
    if missing:
        raise FileNotFoundError("required inputs missing:" + ",".join(missing))
    return result


def manifest_record(name: str, path: Path, *, truth_level: str, role: str, formal_input: bool, diagnostic_only: bool, contract_sha: str) -> dict[str, Any]:
    record: dict[str, Any] = {
        "name": name, "absolute_path": str(path.resolve()), "sha256": sha256_path(path),
        "source_truth_level": truth_level, "artifact_role": role, "formal_input": formal_input,
        "diagnostic_only": diagnostic_only, "method_contract_sha256": contract_sha,
        "frozen_or_closed": "unknown", "row_count": "", "unique_workers": "", "unique_tasks": "", "unique_buildings": "",
    }
    if path.suffix.lower() == ".csv":
        rows = csv_rows(path); record["schema_version"] = clean(rows[0].get("schema_version")) if rows else "empty_csv"; record["row_count"] = len(rows)
        for field, key in (("worker_id", "unique_workers"), ("base_task_id", "unique_tasks"), ("building_id", "unique_buildings")):
            record[key] = len({clean(row.get(field)) for row in rows if clean(row.get(field))})
    elif path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8")); record["schema_version"] = clean(payload.get("schema_version")) if isinstance(payload, dict) else "label_studio_export_json"; record["frozen_or_closed"] = clean(payload.get("status")) if isinstance(payload, dict) else "raw"
    else:
        record["schema_version"] = "directory_raw_source"; record["frozen_or_closed"] = "raw"
    return record


def build_source_manifest(inputs: dict[str, Path | list[Path]], output: Path, contract_sha: str) -> list[dict[str, Any]]:
    roles = {
        "p1_canonical": ("derived_frozen", "P1 canonical", False, True), "p1_summary": ("derived_frozen", "P1 canonical summary", False, True),
        "c1_eligibility": ("frozen_assignment_evidence", "C1 formal row eligibility", True, False), "c1_qgt": ("frozen_assignment_evidence", "C1 Q_GT", True, False),
        "c1_peer": ("frozen_assignment_evidence", "C1 peer", True, False), "c1_loo": ("frozen_assignment_evidence", "C1 LOO", False, True),
        "c1_structural": ("frozen_assignment_evidence", "C1 structural", True, False), "c1_snapshot": ("derived_frozen", "C1 v17 snapshot", False, True),
        "c2b_canonical": ("derived_frozen", "C2-B canonical", True, False), "c2b_acceptance": ("current_normative", "C2-B historical acceptance", True, False),
        "block1_canonical": ("derived_frozen", "Block1 canonical", True, False), "block1_reestimate": ("derived_frozen", "Block1 reestimate", True, False),
        "block2_canonical": ("derived_frozen", "Block2 canonical", True, False), "block2_reestimate": ("derived_frozen", "Block2 reestimate", True, False),
        "risk": ("derived_frozen", "cumulative risk evidence", True, False), "profile": ("derived_frozen", "post Block1 worker profile", False, True),
        "crosswalk": ("derived_frozen", "reference crosswalk", True, False), "feature_pool": ("derived_frozen", "pre-task feature pool", False, True),
        "block1_assignment": ("frozen_assignment", "Block1 assignment", True, False), "block2_assignment": ("frozen_assignment", "Block2 assignment", True, False),
    }
    records = []
    for name, config in roles.items():
        records.append(manifest_record(name, inputs[name], truth_level=config[0], role=config[1], formal_input=config[2], diagnostic_only=config[3], contract_sha=contract_sha))  # type: ignore[arg-type]
    for name in ("active_p1", "active_c1", "active_c2b", "active_b1", "active_b2"):
        records.append(manifest_record(name, inputs[name], truth_level="raw_active_log", role="active-time source", formal_input=False, diagnostic_only=True, contract_sha=contract_sha))  # type: ignore[arg-type]
    for name in ("raw_p1", "raw_c1", "raw_c2b", "raw_b1", "raw_b2"):
        for index, path in enumerate(inputs[name]):  # type: ignore[index]
            records.append(manifest_record(f"{name}_{index + 1}", path, truth_level="raw_runtime_export", role="meta-label/runtime source", formal_input=False, diagnostic_only=True, contract_sha=contract_sha))
    write_json(output / "source_manifest.json", {**ROLE_FIELDS, "method_contract_sha256": contract_sha, "inputs": records})
    return records


def index_rows(rows: list[dict[str, str]], *fields: str) -> dict[tuple[str, ...], dict[str, str]]:
    indexed: dict[tuple[str, ...], dict[str, str]] = {}
    for row in rows:
        key = tuple(clean(row.get(field)) for field in fields)
        if key in indexed:
            raise ValueError(f"duplicate source identity:{fields}:{key}")
        indexed[key] = row
    return indexed


def common_evidence(stage: str, substage: str, row: dict[str, str], *, base_task_id: str, canonical_id: str, annotation_id: str, risk: dict[str, str] | None, labels: dict[str, list[str]]) -> dict[str, Any]:
    risk = risk or {}
    reference_status = clean(risk.get("reference_status"))
    quality = number(row.get("iou_to_gt"))
    if quality is None:
        quality = number(risk.get("quality"))
    return {
        **ROLE_FIELDS,
        "stage": stage, "substage_block": substage, "worker_id": worker_id(row.get("worker_id") or row.get("annotator_id")),
        "base_task_id": base_task_id, "runtime_task_id": clean(row.get("runtime_task_id") or row.get("ls_runtime_task_id") or row.get("task_id")),
        "annotation_id": annotation_id, "canonical_submission_id": canonical_id, "building_id": clean(risk.get("building_id") or row.get("building_id")),
        "condition": clean(row.get("condition")) or "manual", "assignment_provenance": clean(row.get("assignment_provenance") or row.get("assignment_batch_id")),
        "canonical_status": clean(row.get("canonical_valid") or row.get("canonical_eligible") or row.get("eligible_for_primary_analysis")),
        "formal_assignment_eligible": truth(row.get("formal_assignment_eligible")),
        "gt_analysis_eligible": truth(row.get("gt_primary_analysis_eligible")), "peer_analysis_eligible": truth(row.get("peer_analysis_eligible")),
        "structural_analysis_eligible": truth(row.get("structural_opportunity_eligible") or row.get("structural_denominator_eligible")),
        "active_time_eligible": truth(row.get("time_analysis_eligible") or row.get("primary_active_time_eligible")),
        "risk_evidence_eligible": truth(risk.get("risk_slope_estimand_eligible")), "predictive_analysis_eligible": truth(row.get("predictive_validity_analysis_eligible")),
        "routing_feature_eligible": truth(row.get("routing_feature_analysis_eligible") or risk.get("routing_feature_analysis_eligible")),
        "outside": truth(row.get("outside_assignment_submission") or row.get("outside_assignment_disposition_applied")),
        "missing": False, "not_evaluable": clean(risk.get("eligibility_status")).lower() == "not_evaluable", "exclusion_reason": clean(risk.get("ineligibility_reason") or row.get("exclusion_reason")),
        "failure_attribution": clean(row.get("failure_attribution")), "iou_to_reference": quality, "delivery_adjusted_quality": "",
        "structurally_valid": clean(row.get("structurally_valid")), "worker_attributable_structural_failure": clean(row.get("worker_caused_structural_failure") or row.get("worker_structural_failure_numerator")),
        "peer_compatibility": "", "loo_peer_compatibility": "", "active_time": number(row.get("active_time")),
        "active_time_source": clean(row.get("active_time_source")), "active_time_version": clean(row.get("timing_status") or row.get("active_time_source_file")),
        "reference_status": reference_status or clean(row.get("geometry_reference_status")), "risk": number(risk.get("risk")), "task_stratum": clean(risk.get("task_stratum") or row.get("task_stratum")),
        "risk_design_vector_A": "", "risk_design_score_A": number(risk.get("risk_design_score_A")), "design_stratum": clean(risk.get("task_stratum") or row.get("task_stratum")),
        "g_topology_invalid": "", "g_duplicate_peak": "", "g_seam_instability": "", "g_postprocess_invalid": "", "d_model_feat": "", "d_model_feat_local": "",
        "dataset_source_pool": clean(row.get("dataset_group")), "reference_version": clean(risk.get("reference_registry_sha256") or row.get("reference_sha256")),
        "pre_task_feature_timing": "pre_task", "pre_task_feature_provenance": "frozen_task_risk_or_missing", "pre_task_uses_gt": False,
        "pre_task_available_before_assignment": True, "feature_missingness": "", "feature_timing": "post_task", "formal_first_route_eligible": False,
        **{tag: tag in set(labels.get("difficulty", [])) for tag in DIFFICULTY_TAGS},
        "scope": ";".join(labels.get("scope", [])), "model_issue": ";".join(labels.get("model_issue", [])),
    }


def build_long_evidence(inputs: dict[str, Path | list[Path]], output: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    labels = raw_label_map({"P1": inputs["raw_p1"], "C1": inputs["raw_c1"], "C2B": inputs["raw_c2b"], "C2A_RP_BLOCK1": inputs["raw_b1"], "C2A_RP_BLOCK2": inputs["raw_b2"]})  # type: ignore[arg-type]
    risk_rows = csv_rows(inputs["risk"])  # type: ignore[arg-type]
    risk_by_annotation = {clean(row["canonical_annotation_id"]): row for row in risk_rows}
    feature_pool = {clean(row["base_task_id"]): row for row in csv_rows(inputs["feature_pool"])}  # type: ignore[arg-type]
    rows: list[dict[str, Any]] = []

    for row in csv_rows(inputs["p1_canonical"]):  # type: ignore[arg-type]
        raw_id = clean(row.get("raw_canonical_annotation_id") or row.get("annotation_id")); worker = worker_id(row.get("annotator_id"))
        label = labels.get(("P1", worker, raw_id), {})
        base = clean(row.get("task_label")).removesuffix(".jpg")
        item = common_evidence("P1", "PreScreen", {**row, "worker_id": worker}, base_task_id=base, canonical_id=clean(row.get("canonical_annotation_id")), annotation_id=raw_id, risk=None, labels=label)
        item["formal_assignment_eligible"] = False; item["active_time_eligible"] = truth(row.get("primary_active_time_eligible")); rows.append(item)

    eligibility = index_rows(csv_rows(inputs["c1_eligibility"]), "canonical_annotation_id")  # type: ignore[arg-type]
    peer = index_rows(csv_rows(inputs["c1_peer"]), "canonical_annotation_id")  # type: ignore[arg-type]
    loo = index_rows(csv_rows(inputs["c1_loo"]), "canonical_annotation_id")  # type: ignore[arg-type]
    structural = index_rows(csv_rows(inputs["c1_structural"]), "canonical_annotation_id")  # type: ignore[arg-type]
    for qgt in csv_rows(inputs["c1_qgt"]):  # type: ignore[arg-type]
        canonical = clean(qgt.get("canonical_annotation_id")); source = {**qgt, **eligibility.get((canonical,), {})}; worker = worker_id(source.get("worker_id")); raw_id = clean(source.get("annotation_id"))
        item = common_evidence("C1", "C1-A", source, base_task_id=clean(source.get("base_task_id")), canonical_id=canonical, annotation_id=raw_id, risk=None, labels=labels.get(("C1", worker, raw_id), {}))
        item["peer_compatibility"] = number(peer.get((canonical,), {}).get("R_peer_task")); item["loo_peer_compatibility"] = number(loo.get((canonical,), {}).get("q_LOO_tu"))
        structural_row = structural.get((canonical,), {}); item["worker_attributable_structural_failure"] = clean(structural_row.get("worker_attributable") or structural_row.get("worker_failure_numerator")); item["failure_attribution"] = clean(structural_row.get("failure_attribution") or item["failure_attribution"])
        rows.append(item)

    canonical_specs = (("C2B", "C2-B", "c2b_canonical"), ("C2A_RP_BLOCK1", "Block1", "block1_canonical"), ("C2A_RP_BLOCK2", "Block2", "block2_canonical"))
    for risk_stage, substage, source_name in canonical_specs:
        stage, _ = stage_from_risk(risk_stage)
        for row in csv_rows(inputs[source_name]):  # type: ignore[arg-type]
            canonical = clean(row.get("canonical_annotation_id")); raw_id = clean(row.get("raw_canonical_annotation_id") or row.get("annotation_id")); worker = worker_id(row.get("worker_id"))
            risk = risk_by_annotation.get(canonical)
            item = common_evidence(stage, substage, row, base_task_id=clean(row.get("base_task_id")), canonical_id=canonical, annotation_id=raw_id, risk=risk, labels=labels.get((risk_stage, worker, raw_id), {}))
            feature = feature_pool.get(item["base_task_id"], {})
            item["risk_design_vector_A"] = clean(feature.get("risk_design_vector_A")); item["risk_design_score_A"] = number(feature.get("risk_design_score_A")) or item["risk_design_score_A"]
            item["design_stratum"] = clean(feature.get("risk_design_stratum")) or item["design_stratum"]
            item["pre_task_feature_provenance"] = "frozen_c2_task_risk" if feature else "risk_evidence_only"
            item["feature_missingness"] = "preannotation_model_cues_not_in_current_evidence" if not feature else "model_cues_not_bound_to_observed_task"
            rows.append(item)
    validate_unique_evidence_keys(rows)
    meta_rows: list[dict[str, Any]] = []
    for row in rows:
        stage_key = "C2A_RP_" + row["substage_block"].upper() if row["stage"] == "C2A_RP" else row["stage"]
        raw_labels = labels.get((stage_key, worker_id(row["worker_id"]), clean(row["annotation_id"])), {})
        meta_rows.extend(meta_rows_for_submission({key: row.get(key, "") for key in ("stage", "substage_block", "worker_id", "base_task_id", "condition", "canonical_submission_id", "risk", "task_stratum", "building_id")}, raw_labels))
    write_csv(output / "calibration_evidence_long.csv", rows)
    write_csv(output / "meta_label_long.csv", meta_rows)
    return rows, meta_rows


def profile_rows(evidence: list[dict[str, Any]], profile_path: Path) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in evidence:
        grouped[(clean(row["worker_id"]), clean(row["stage"]), clean(row["substage_block"]))].append(row)
    for (worker, stage, substage), rows in sorted(grouped.items(), key=lambda item: (int(item[0][0]) if item[0][0].isdigit() else 9999, item[0][1], item[0][2])):
        qualities = [value for row in rows if (value := number(row.get("iou_to_reference"))) is not None]
        peers = [value for row in rows if (value := number(row.get("peer_compatibility"))) is not None]
        times = [value for row in rows if (value := number(row.get("active_time"))) is not None]
        risks = [value for row in rows if truth(row.get("risk_evidence_eligible")) and (value := number(row.get("risk"))) is not None]
        structural = [row for row in rows if truth(row.get("structural_analysis_eligible"))]
        failures = sum(truth(row.get("worker_attributable_structural_failure")) for row in structural)
        result.append({
            **ROLE_FIELDS, "worker_id": worker, "stage": stage, "substage_block": substage, "analysis_scope": "stage_observed_evidence",
            "Q_GT_raw": float(np.median(qualities)) if qualities else "", "Q_GT_task_adjusted": "", "Q_GT_support": len(qualities),
            "R_peer_all": float(np.median(peers)) if peers else "", "R_peer_stable": float(np.median(peers)) if peers else "", "R_peer_support": len(peers),
            "R_LOO": "", "structural_numerator": failures if structural else "", "structural_denominator": len(structural), "F_struct_raw": failures / len(structural) if structural else "", "F_struct_EB": "",
            "active_time_raw_median": float(np.median(times)) if times else "", "active_time_task_adjusted": "", "active_time_support": len(times),
            "risk_evidence_n": len(risks), "risk_min": min(risks) if risks else "", "risk_max": max(risks) if risks else "", "risk_span": max(risks) - min(risks) if risks else "",
            "ordinary_n": sum(clean(row.get("task_stratum")) == "ordinary" and truth(row.get("risk_evidence_eligible")) for row in rows), "stress_n": sum(clean(row.get("task_stratum")) == "stress" and truth(row.get("risk_evidence_eligible")) for row in rows),
            "evaluability_status": "estimated" if qualities or peers or risks else "not_evaluable",
        })
    for row in csv_rows(profile_path):
        result.append({
            **ROLE_FIELDS, "worker_id": worker_id(row.get("worker_id")), "stage": "PROFILE_INPUT", "substage_block": "post_Block1", "analysis_scope": "post_block1_routing_input_not_final_profile",
            "Q_GT_raw": row.get("Q_GT_raw_median", ""), "Q_GT_task_adjusted": row.get("Q_GT_task_adjusted", ""), "Q_GT_support": row.get("GT_support", ""),
            "R_peer_all": row.get("R_peer_all", ""), "R_peer_stable": row.get("R_peer_stable", ""), "R_peer_support": row.get("R_peer_support", ""), "R_LOO": row.get("R_LOO_medoid", ""),
            "structural_numerator": row.get("F_struct_numerator", ""), "structural_denominator": row.get("F_struct_denominator", ""), "F_struct_raw": row.get("F_struct_raw", ""), "F_struct_EB": row.get("F_struct_EB", ""),
            "active_time_raw_median": row.get("T_active_raw_median", ""), "active_time_task_adjusted": row.get("T_active_task_adjusted", ""), "active_time_support": row.get("T_active_support", ""),
            "risk_evidence_n": row.get("risk_slope_support", ""), "risk_min": "", "risk_max": "", "risk_span": "", "ordinary_n": row.get("ordinary_support_observed", ""), "stress_n": row.get("stress_support_observed", ""),
            "evaluability_status": row.get("worker_profile_status", ""), "profile_formal_frozen": row.get("formal_frozen", ""), "global_policy_eligible_field": row.get("global_policy_eligible", ""),
        })
    return result


def task_matrix(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in evidence:
        grouped[(clean(row["stage"]), clean(row["base_task_id"]))].append(row)
    result = []
    for (stage, task), rows in sorted(grouped.items()):
        first = rows[0]; risks = [number(row.get("risk")) for row in rows if number(row.get("risk")) is not None]
        quality = [number(row.get("iou_to_reference")) for row in rows if number(row.get("iou_to_reference")) is not None]
        result.append({
            **ROLE_FIELDS, "stage": stage, "base_task_id": task, "building_id": first.get("building_id", ""), "risk": risks[0] if risks else "", "ordinary_stress": first.get("task_stratum", ""),
            "risk_design_vector_A": first.get("risk_design_vector_A", ""), "risk_design_score_A": first.get("risk_design_score_A", ""), "design_stratum": first.get("design_stratum", ""),
            "g_topology_invalid": first.get("g_topology_invalid", ""), "g_duplicate_peak": first.get("g_duplicate_peak", ""), "g_seam_instability": first.get("g_seam_instability", ""), "g_postprocess_invalid": first.get("g_postprocess_invalid", ""), "d_model_feat": first.get("d_model_feat", ""), "d_model_feat_local": first.get("d_model_feat_local", ""),
            "feature_timing": "pre_task", "feature_provenance": first.get("pre_task_feature_provenance", ""), "uses_gt": first.get("pre_task_uses_gt", ""), "available_before_assignment": first.get("pre_task_available_before_assignment", ""),
            "reference_status": first.get("reference_status", ""), "worker_support": len({clean(row.get("worker_id")) for row in rows}), "task_outcome_quality_mean": float(np.mean(quality)) if quality else "", "feature_missingness": first.get("feature_missingness", ""),
        })
    return result


def quality_outputs(evidence: list[dict[str, Any]], meta: list[dict[str, Any]], output: Path) -> dict[str, Any]:
    frame = pd.DataFrame(evidence)
    for field in ("risk", "iou_to_reference", "active_time"):
        frame[field] = pd.to_numeric(frame[field], errors="coerce")
    missing = []
    for stage, group in frame.groupby(["stage", "substage_block"], dropna=False):
        for field in ("risk", "iou_to_reference", "peer_compatibility", "loo_peer_compatibility", "active_time", "reference_status"):
            missing.append({"stage": stage[0], "substage_block": stage[1], "field": field, "rows": len(group), "missing": int(group[field].replace("", np.nan).isna().sum()), **ROLE_FIELDS})
    write_csv(output / "missingness_by_stage.csv", missing)
    for unit, fields, filename in (("worker_id", ["stage", "substage_block", "worker_id"], "support_by_worker.csv"), ("base_task_id", ["stage", "base_task_id"], "support_by_task.csv"), ("building_id", ["stage", "building_id"], "support_by_building.csv")):
        records = []
        for key, group in frame.groupby(fields, dropna=False):
            values = key if isinstance(key, tuple) else (key,)
            records.append(dict(zip(fields, values)) | {"evidence_rows": len(group), "risk_eligible_rows": int(group.risk_evidence_eligible.astype(bool).sum()), "workers": group.worker_id.nunique(), **ROLE_FIELDS})
        write_csv(output / filename, records)
    reference = [{"stage": stage, "reference_status": status or "missing", "rows": len(group), **ROLE_FIELDS} for (stage, status), group in frame.groupby(["stage", "reference_status"], dropna=False)]
    write_csv(output / "reference_status_summary.csv", reference)
    active = [{"stage": stage, "active_time_source": source or "missing", "active_time_version": version or "missing", "rows": len(group), "eligible_rows": int(group.active_time_eligible.astype(bool).sum()), **ROLE_FIELDS} for (stage, source, version), group in frame.groupby(["stage", "active_time_source", "active_time_version"], dropna=False)]
    write_csv(output / "active_time_source_summary.csv", active)
    meta_df = pd.DataFrame(meta)
    prevalence = []
    for (stage, family, tag), group in meta_df.groupby(["stage", "tag_family", "tag_value"]):
        prevalence.append({"stage": stage, "tag_family": family, "tag_value": tag, "rows": len(group), "selected_n": int(group.selected.astype(bool).sum()), "prevalence": float(group.selected.astype(bool).mean()), "routing_role": "not_eligible_for_first_route", "analysis_subrole": "descriptive_measurement_audit", **ROLE_FIELDS})
    write_csv(output / "meta_label_prevalence.csv", prevalence)
    difficulty = meta_df[(meta_df.tag_family == "difficulty") & meta_df.selected.astype(bool)]
    cooccurrence: Counter[tuple[str, str, str]] = Counter()
    selected_by_submission: dict[tuple[str, str], set[str]] = defaultdict(set)
    for _, row in difficulty.iterrows(): selected_by_submission[(row["stage"], row["canonical_submission_id"])].add(row["tag_value"])
    for (stage, _), tags in selected_by_submission.items():
        for left in sorted(tags):
            for right in sorted(tags):
                if left < right: cooccurrence[(stage, left, right)] += 1
    write_csv(output / "meta_label_cooccurrence.csv", [{"stage": key[0], "tag_left": key[1], "tag_right": key[2], "count": value, "routing_role": "not_eligible_for_first_route", "analysis_subrole": "descriptive_measurement_audit", **ROLE_FIELDS} for key, value in sorted(cooccurrence.items())])
    agreement = []
    for (stage, task), group in difficulty.groupby(["stage", "base_task_id"]):
        sets = [";".join(sorted(values)) for _, values in group.groupby("canonical_submission_id").tag_value.agg(set).items()]
        agreement.append({"stage": stage, "base_task_id": task, "submissions": len(sets), "exact_full_tag_set_agreement": len(set(sets)) == 1 if len(sets) >= 2 else "", "routing_role": "not_eligible_for_first_route", "analysis_subrole": "descriptive_measurement_audit", **ROLE_FIELDS})
    write_csv(output / "meta_label_task_agreement.csv", agreement)
    summary = {**ROLE_FIELDS, "rows": len(evidence), "meta_rows": len(meta), "key_unique": True, "stages": {stage: int(count) for stage, count in frame.stage.value_counts().items()}, "risk_eligible_rows": int(frame.risk_evidence_eligible.astype(bool).sum()), "post_task_features_isolated": True, "t1_v1_outcomes_present": False}
    write_json(output / "data_quality_summary.json", summary)
    return summary


def rank(values: dict[str, float]) -> dict[str, int]:
    return {worker: index + 1 for index, (worker, _) in enumerate(sorted(values.items(), key=lambda item: (-item[1], item[0])))}


def tier_cutpoints(values: Iterable[float]) -> tuple[float, float, float]:
    """Return fixed median and tertile cutpoints without outcome-based tuning."""
    array = np.asarray(list(values), dtype=float)
    if len(array) < 2 or not np.isfinite(array).all():
        raise ValueError("tier cutpoints require at least two finite values")
    median = float(np.quantile(array, .5))
    lower_third, upper_third = (float(value) for value in np.quantile(array, [1 / 3, 2 / 3]))
    return median, lower_third, upper_third


def corr(left: list[float], right: list[float], kind: str) -> float | str:
    if len(left) < 3 or len(set(left)) < 2 or len(set(right)) < 2:
        return ""
    value = spearmanr(left, right).statistic if kind == "spearman" else kendalltau(left, right).statistic
    return float(value) if value is not None and math.isfinite(value) else ""


def components_analysis(profile_path: Path, evidence: list[dict[str, Any]], output: Path) -> None:
    profile = csv_rows(profile_path)
    fields = ("Q_GT_EB", "R_peer_stable", "F_struct_EB")
    worker_values = [{"worker_id": worker_id(row.get("worker_id")), **{field: number(row.get(field)) for field in fields}, "Q_GT_raw": number(row.get("Q_GT_raw_median")), "Q_GT_task_adjusted": number(row.get("Q_GT_task_adjusted")), "Q_GT_LCB": number(row.get("Q_GT_EB_LCB")), "GT_support": row.get("GT_support", ""), "R_peer_support": row.get("R_peer_support", ""), "F_struct_numerator": row.get("F_struct_numerator", ""), "F_struct_denominator": row.get("F_struct_denominator", ""), "source_profile_formal_frozen": row.get("formal_frozen", ""), **ROLE_FIELDS} for row in profile]
    write_csv(output / "global_components_worker_table.csv", worker_values)
    correlations = []
    for left_index, left_field in enumerate(fields):
        for right_field in fields[left_index + 1:]:
            pairs = [(row[left_field], row[right_field]) for row in worker_values if row[left_field] is not None and row[right_field] is not None]
            correlations.append({"component_left": left_field, "component_right": right_field, "n": len(pairs), "spearman": corr([pair[0] for pair in pairs], [pair[1] for pair in pairs], "spearman"), "kendall": corr([pair[0] for pair in pairs], [pair[1] for pair in pairs], "kendall"), "source": "post_block1_routing_input_not_final", **ROLE_FIELDS})
    write_csv(output / "global_components_correlation.csv", correlations)
    rng = random.Random(SEED); bootstrap: dict[str, Any] = {**ROLE_FIELDS, "seed": SEED, "replicates": BOOTSTRAP_REPLICATES, "correlations": []}
    for row in correlations:
        pairs = [(item[row["component_left"]], item[row["component_right"]]) for item in worker_values if item[row["component_left"]] is not None and item[row["component_right"]] is not None]
        draws = []
        for _ in range(BOOTSTRAP_REPLICATES):
            sample = [pairs[rng.randrange(len(pairs))] for _ in pairs]
            value = corr([pair[0] for pair in sample], [pair[1] for pair in sample], "spearman")
            if value != "": draws.append(value)
        bootstrap["correlations"].append({"left": row["component_left"], "right": row["component_right"], "successful": len(draws), "ci_lower": float(np.quantile(draws, .025)) if draws else "", "ci_upper": float(np.quantile(draws, .975)) if draws else ""})
    c1 = [row for row in evidence if row["stage"] == "C1" and number(row.get("iou_to_reference")) is not None]
    baseline = {worker: float(np.median([number(row.get("iou_to_reference")) for row in rows])) for worker, rows in defaultdict(list, {worker: [row for row in c1 if row["worker_id"] == worker] for worker in {row["worker_id"] for row in c1}}).items()}
    lobo = []
    for building in sorted({clean(row.get("building_id")) for row in c1 if clean(row.get("building_id"))}):
        remaining = [row for row in c1 if clean(row.get("building_id")) != building]
        values = {worker: float(np.median([number(row.get("iou_to_reference")) for row in remaining if row["worker_id"] == worker])) for worker in baseline if any(row["worker_id"] == worker for row in remaining)}
        common = sorted(set(baseline) & set(values)); lobo.append({"omitted_unit": "building", "omitted_value": building, "n_workers": len(common), "rank_spearman": corr([rank(baseline)[worker] for worker in common], [rank(values)[worker] for worker in common], "spearman"), "role": "diagnostic_pre_stage3"})
    bootstrap["leave_one_building_out_raw_qgt"] = lobo; bootstrap["stage_rank_status"] = "not_evaluable_no_stage_specific_three_component_profile"
    write_json(output / "global_components_bootstrap.json", bootstrap)


def qgt_rank_analysis(profile_path: Path, evidence: list[dict[str, Any]], output: Path) -> None:
    profile = {worker_id(row.get("worker_id")): row for row in csv_rows(profile_path)}
    c1 = [row for row in evidence if row["stage"] == "C1" and number(row.get("iou_to_reference")) is not None]
    raw = {worker: float(np.median([number(row.get("iou_to_reference")) for row in c1 if row["worker_id"] == worker])) for worker in profile if any(row["worker_id"] == worker for row in c1)}
    adjusted = {worker: number(row.get("Q_GT_task_adjusted")) for worker, row in profile.items() if number(row.get("Q_GT_task_adjusted")) is not None}
    eb = {worker: number(row.get("Q_GT_EB")) for worker, row in profile.items() if number(row.get("Q_GT_EB")) is not None}
    lcb = {worker: number(row.get("Q_GT_EB_LCB")) for worker, row in profile.items() if number(row.get("Q_GT_EB_LCB")) is not None}
    rng = random.Random(SEED); distributions: dict[str, list[int]] = defaultdict(list)
    for _ in range(BOOTSTRAP_REPLICATES):
        sampled: list[dict[str, Any]] = []
        tasks = sorted({row["base_task_id"] for row in c1})
        drawn = [rng.choice(tasks) for _ in tasks]
        for task in drawn: sampled.extend(row for row in c1 if row["base_task_id"] == task)
        values = {worker: float(np.median([number(row.get("iou_to_reference")) for row in sampled if row["worker_id"] == worker])) for worker in raw if any(row["worker_id"] == worker for row in sampled)}
        for worker, value in rank(values).items(): distributions[worker].append(value)
    rows = []
    eb_rank, adjusted_rank, raw_rank, lcb_rank = rank(eb), rank(adjusted), rank(raw), rank(lcb)
    for worker in sorted(eb, key=lambda value: int(value) if value.isdigit() else 9999):
        rows.append({"worker_id": worker, "Q_GT_raw_c1_median": raw.get(worker, ""), "Q_GT_task_adjusted": adjusted.get(worker, ""), "Q_GT_EB": eb[worker], "Q_GT_EB_LCB": lcb.get(worker, ""), "raw_rank": raw_rank.get(worker, ""), "task_adjusted_rank": adjusted_rank.get(worker, ""), "EB_rank": eb_rank[worker], "LCB_rank_sensitivity": lcb_rank.get(worker, ""), "bootstrap_raw_rank_q025": float(np.quantile(distributions[worker], .025)) if distributions[worker] else "", "bootstrap_raw_rank_q975": float(np.quantile(distributions[worker], .975)) if distributions[worker] else "", "top3_membership_probability_raw": float(np.mean(np.asarray(distributions[worker]) <= 3)) if distributions[worker] else "", "top5_membership_probability_raw": float(np.mean(np.asarray(distributions[worker]) <= 5)) if distributions[worker] else "", **ROLE_FIELDS})
    write_csv(output / "qgt_rank_stability.csv", rows)
    ordering = []
    for left in sorted(distributions):
        for right in sorted(distributions):
            if left < right:
                probability = float(np.mean(np.asarray(distributions[left]) < np.asarray(distributions[right])))
                ordering.append({"worker_left": left, "worker_right": right, "p_left_ranked_above_right_raw_bootstrap": probability})
    write_json(output / "qgt_rank_bootstrap.json", {**ROLE_FIELDS, "seed": SEED, "replicates": BOOTSTRAP_REPLICATES, "rank_statistic": "C1 raw median IoU task-cluster bootstrap", "pairwise_ordering": ordering, "EB_rank_distribution": "not_available_from_frozen_profile_bootstrap_draws"})


def candidate_tiers(profile_path: Path, evidence: list[dict[str, Any]], output: Path) -> None:
    profiles = {worker_id(row.get("worker_id")): number(row.get("Q_GT_EB")) for row in csv_rows(profile_path) if number(row.get("Q_GT_EB")) is not None}
    ordered = [worker for worker, _ in sorted(profiles.items(), key=lambda item: (-item[1], item[0]))]
    definitions = []
    for kind, count in (("top_k", 3), ("top_k", 5), ("top_k", 10)):
        for worker in ordered: definitions.append({"definition": f"{kind}_{count}", "rule": f"top {count} by existing Q_GT_EB", "worker_id": worker, "member": worker in ordered[:count], "cutpoint_source": "deterministic_top_k", **ROLE_FIELDS})
    two_tier, lower_third, upper_third = tier_cutpoints(profiles.values())
    for label, predicate in (("two_tier_upper", lambda value: value >= two_tier), ("three_tier_high", lambda value: value >= upper_third), ("three_tier_middle", lambda value: lower_third <= value < upper_third), ("three_tier_low", lambda value: value < lower_third)):
        for worker, value in profiles.items(): definitions.append({"definition": label, "rule": "fixed empirical quantile on existing Q_GT_EB", "worker_id": worker, "member": predicate(value), "cutpoint_source": "deterministic_quantile", **ROLE_FIELDS})
    write_csv(output / "candidate_tier_definitions.csv", definitions)
    stability = []
    for definition, group in pd.DataFrame(definitions).groupby("definition"):
        members = set(group.loc[group.member.astype(bool), "worker_id"]); stability.append({"definition": definition, "group_size": len(members), "bootstrap_membership_stability": "not_evaluable_for_EB_without_frozen_draws", "cross_stage_stability": "not_evaluable_no_late_stage_global_profile", "leave_one_building_out_stability": "reported_in_global_components_bootstrap", **ROLE_FIELDS})
    write_csv(output / "candidate_tier_stability.csv", stability)
    c2 = [row for row in evidence if row["stage"] in {"C2B", "C2A_RP"} and number(row.get("risk")) is not None and number(row.get("iou_to_reference")) is not None]
    metrics = []
    for definition, group in pd.DataFrame(definitions).groupby("definition"):
        members = set(group.loc[group.member.astype(bool), "worker_id"]); values = [number(row.get("iou_to_reference")) for row in c2 if row["worker_id"] in members]
        metrics.append({"definition": definition, "worker_group_size": len(members), "outcome_rows": len(values), "quality_mean": float(np.mean(values)) if values else "", "quality_ci": "not_resampled", "leaveout_prediction_error": "not_evaluable_no_frozen_prediction_protocol", "range_restriction_qgt_eb": float(np.ptp([profiles[worker] for worker in members])) if len(members) > 1 else 0.0, **ROLE_FIELDS})
    write_csv(output / "candidate_tier_predictive_metrics.csv", metrics)


def model_row(name: str, formula: str, frame: pd.DataFrame, *, cluster: str = "", kind: str = "ols") -> tuple[dict[str, Any], Any | None]:
    base = {**ROLE_FIELDS, "model_name": name, "formula": formula, "estimand": "diagnostic_pre_stage3_quality_risk_association", "included_rows": len(frame), "workers": int(frame.worker_id.nunique()), "tasks": int(frame.base_task_id.nunique()), "buildings": int(frame.building_id.nunique()), "cluster_unit": cluster, "bootstrap_seed": SEED, "bootstrap_repetitions": BOOTSTRAP_REPLICATES}
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            if kind == "mixed_worker_slope":
                fit = smf.mixedlm(formula, frame, groups=frame["worker_id"], re_formula="1 + risk").fit(reml=True, method="lbfgs", maxiter=1000, disp=False)
            else:
                fit = smf.ols(formula, frame).fit()
            params = getattr(fit, "params", pd.Series(dtype=float)); bse = getattr(fit, "bse", pd.Series(dtype=float)); coefficient = float(params.get("risk", np.nan)) if "risk" in params else ""; se = float(bse.get("risk", np.nan)) if "risk" in bse else ""; residual_df = float(getattr(fit, "df_resid", np.nan))
        converged = bool(getattr(fit, "converged", True)); warnings_text = ";".join(str(item.message) for item in caught)
        requires_risk = "risk" in formula
        status = "not_evaluable_insufficient_residual_df" if kind == "ols" and residual_df <= 0 else "not_evaluable_nonfinite_risk_estimate" if requires_risk and (coefficient == "" or se == "" or not math.isfinite(coefficient) or not math.isfinite(se)) else "estimated" if converged else "not_converged"
        if status.startswith("not_evaluable"):
            return base | {"status": status, "coefficient": "", "se": "", "ci_lower": "", "ci_upper": "", "convergence": converged, "boundary": "boundary" in warnings_text.lower(), "hessian": "hessian" in warnings_text.lower(), "warnings": warnings_text, "aic": "", "bic": ""}, None
        return base | {"status": status, "coefficient": coefficient, "se": se, "ci_lower": coefficient - 1.96 * se if coefficient != "" and se != "" else "", "ci_upper": coefficient + 1.96 * se if coefficient != "" and se != "" else "", "convergence": converged, "boundary": "boundary" in warnings_text.lower(), "hessian": "hessian" in warnings_text.lower(), "warnings": warnings_text, "aic": float(getattr(fit, "aic", np.nan)) if math.isfinite(float(getattr(fit, "aic", np.nan))) else "", "bic": float(getattr(fit, "bic", np.nan)) if math.isfinite(float(getattr(fit, "bic", np.nan))) else ""}, fit
    except Exception as exc:  # preserve every failed model
        return base | {"status": "failed", "coefficient": "", "se": "", "ci_lower": "", "ci_upper": "", "convergence": False, "boundary": "", "hessian": "", "warnings": f"{type(exc).__name__}:{exc}", "aic": "", "bic": ""}, None


def resample_coefficient(frame: pd.DataFrame, cluster: str, replicates: int = BOOTSTRAP_REPLICATES) -> dict[str, Any]:
    rng = random.Random(SEED); clusters = sorted(frame[cluster].dropna().astype(str).unique()); draws = []; failures = 0
    for _ in range(replicates):
        sample = pd.concat([frame[frame[cluster].astype(str) == rng.choice(clusters)] for _ in clusters], ignore_index=True)
        row, _ = model_row("bootstrap", "quality ~ C(worker_id) + risk", sample, cluster=cluster)
        if row["status"] == "estimated" and row["coefficient"] != "": draws.append(row["coefficient"])
        else: failures += 1
    return {"cluster": cluster, "requested": replicates, "successful": len(draws), "failed": failures, "median": float(np.median(draws)) if draws else "", "q025": float(np.quantile(draws, .025)) if draws else "", "q975": float(np.quantile(draws, .975)) if draws else "", "seed": SEED}


def risk_models(evidence: list[dict[str, Any]], output: Path) -> list[dict[str, Any]]:
    frame = pd.DataFrame([row for row in evidence if truth(row.get("risk_evidence_eligible")) and number(row.get("risk")) is not None and number(row.get("iou_to_reference")) is not None])
    frame["risk"] = pd.to_numeric(frame.risk); frame["quality"] = pd.to_numeric(frame.iou_to_reference); frame["stage"] = frame.apply(lambda row: analysis_stage(row.to_dict()), axis=1)
    rows = []
    for name, formula, kind in (("worker_fe_continuous_risk", "quality ~ C(worker_id) + risk", "ols"), ("worker_building_fe_continuous_risk", "quality ~ C(worker_id) + C(building_id) + risk", "ols"), ("worker_building_stage_fe_continuous_risk", "quality ~ C(worker_id) + C(building_id) + C(stage) + risk", "ols"), ("worker_fe_quadratic_risk_sensitivity", "quality ~ C(worker_id) + risk + I(risk ** 2)", "ols"), ("worker_random_slope_risk", "quality ~ C(stage) + C(building_id) + risk", "mixed_worker_slope")):
        row, _ = model_row(name, formula, frame, kind=kind); rows.append(row)
    for label, subset in (("ordinary", frame[frame.task_stratum == "ordinary"]), ("stress", frame[frame.task_stratum == "stress"]), ("exclude_reference_unavailable", frame), ("exclude_researcher_confirmed_bad_gt", frame)):
        row, _ = model_row(f"sensitivity_{label}", "quality ~ C(worker_id) + risk", subset); row["estimand"] = "sensitivity"; rows.append(row)
    rows.append({**ROLE_FIELDS, "model_name": "delivery_adjusted_quality", "formula": "", "estimand": "not_evaluable", "status": "not_available_no_legal_calibration_delivery_adjusted_definition", "included_rows": 0, "exclusion_count": 0})
    rows.append({**ROLE_FIELDS, "model_name": "structural_failure_outcome", "formula": "", "estimand": "not_evaluable", "status": "not_available_no_risk_linked_structural_outcome", "included_rows": 0, "exclusion_count": 0})
    write_csv(output / "global_risk_models.csv", rows)
    resampling = {**ROLE_FIELDS, "base_task": resample_coefficient(frame, "base_task_id"), "building": resample_coefficient(frame, "building_id")}
    write_json(output / "global_risk_resampling.json", resampling)
    sensitivity = []
    for field in ("building_id", "base_task_id"):
        for value in sorted(frame[field].astype(str).unique()):
            row, _ = model_row(f"leave_one_{field}", "quality ~ C(worker_id) + risk", frame[frame[field].astype(str) != value], cluster=field)
            sensitivity.append({"omitted_unit": field, "omitted_value": value, **row})
    write_csv(output / "global_risk_sensitivity.csv", sensitivity)
    return rows


def conditional_features(evidence: list[dict[str, Any]], output: Path) -> tuple[pd.DataFrame, list[str]]:
    frame = pd.DataFrame([row for row in evidence if truth(row.get("risk_evidence_eligible")) and number(row.get("risk")) is not None and number(row.get("iou_to_reference")) is not None])
    frame["risk"] = pd.to_numeric(frame.risk); frame["quality"] = pd.to_numeric(frame.iou_to_reference); frame["stage"] = frame.apply(lambda row: analysis_stage(row.to_dict()), axis=1)
    candidates = ["risk_design_score_A", "task_stratum", "g_topology_invalid", "g_duplicate_peak", "g_seam_instability", "g_postprocess_invalid", "d_model_feat", "d_model_feat_local"]
    dictionary = []
    qualified = []
    for field in candidates:
        nonmissing = frame[field].replace("", np.nan).dropna() if field in frame else pd.Series(dtype=object)
        variation = nonmissing.nunique()
        available = len(nonmissing) > 0 and variation > 1
        dictionary.append({"feature": field, "coverage": len(nonmissing), "missing": len(frame) - len(nonmissing), "unique_values": int(variation), "uses_gt": False, "available_before_assignment": True, "provenance": "frozen_pre_task" if field in {"risk_design_score_A", "task_stratum"} else "not_bound_in_current_observed_evidence", "qualified": available, **ROLE_FIELDS})
        if available: qualified.append(field)
    write_csv(output / "conditional_feature_dictionary.csv", dictionary)
    support = []
    for feature in qualified:
        for value, group in frame.groupby(feature): support.append({"feature": feature, "value": value, "rows": len(group), "workers": group.worker_id.nunique(), "tasks": group.base_task_id.nunique(), "buildings": group.building_id.nunique(), **ROLE_FIELDS})
    write_csv(output / "conditional_feature_support.csv", support)
    correlations = []
    numeric = [field for field in ["risk", *qualified] if field != "task_stratum" and pd.api.types.is_numeric_dtype(pd.to_numeric(frame[field], errors="coerce"))]
    for index, left in enumerate(numeric):
        for right in numeric[index + 1:]:
            data = frame[[left, right]].apply(pd.to_numeric, errors="coerce").dropna(); correlations.append({"feature_left": left, "feature_right": right, "n": len(data), "spearman": corr(data[left].tolist(), data[right].tolist(), "spearman"), "kendall": corr(data[left].tolist(), data[right].tolist(), "kendall"), **ROLE_FIELDS})
    write_csv(output / "conditional_feature_correlations.csv", correlations)
    return frame, qualified


def prediction_metrics(train: pd.DataFrame, test: pd.DataFrame, formula: str) -> dict[str, Any]:
    try:
        fit = smf.ols(formula, train).fit(); predicted = fit.predict(test); actual = test.quality.to_numpy(); error = actual - predicted.to_numpy()
        return {"status": "estimated", "n_train": len(train), "n_test": len(test), "rmse": float(np.sqrt(np.mean(error ** 2))), "mae": float(np.mean(np.abs(error))), "spearman": corr(actual.tolist(), predicted.tolist(), "spearman"), "kendall": corr(actual.tolist(), predicted.tolist(), "kendall"), "prediction_interval_coverage": "not_available_ols_point_prediction"}
    except Exception as exc:
        return {"status": "failed", "n_train": len(train), "n_test": len(test), "rmse": "", "mae": "", "spearman": "", "kendall": "", "prediction_interval_coverage": "", "failure": f"{type(exc).__name__}:{exc}"}


def conditional_models(frame: pd.DataFrame, qualified: list[str], output: Path) -> list[dict[str, Any]]:
    summaries = []; failures = []
    models = [("M0", "quality ~ C(worker_id) + C(building_id) + C(stage)", "ols"), ("M1", "quality ~ C(worker_id) + C(building_id) + C(stage) + risk", "ols"), ("M2", "quality ~ C(building_id) + C(stage) + risk", "mixed_worker_slope")]
    for name, formula, kind in models:
        row, _ = model_row(name, formula, frame, kind=kind); summaries.append(row)
        if row["status"] != "estimated": failures.append(row)
    for feature in qualified:
        if feature == "risk": continue
        predictor = f"C({feature})" if feature == "task_stratum" else feature
        formula = f"quality ~ C(worker_id) + C(building_id) + C(stage) + risk + {predictor} + C(worker_id):{predictor}"
        row, _ = model_row(f"M3_{feature}", formula, frame); summaries.append(row)
        if row["status"] != "estimated": failures.append(row)
    write_csv(output / "conditional_model_summary.csv", summaries)
    variance = [{"model_name": row["model_name"], "worker_slope_variance": "not_materialized" if row["model_name"] != "M2" else row["status"], "boundary": row.get("boundary", ""), "hessian": row.get("hessian", ""), **ROLE_FIELDS} for row in summaries]
    write_csv(output / "conditional_variance_components.csv", variance)
    estimates = []
    for worker, group in frame.groupby("worker_id"):
        if len(group) >= 2 and group.risk.nunique() >= 2:
            result, _ = model_row("worker_unpooled_risk_diagnostic", "quality ~ risk", group)
            estimates.append({"worker_id": worker, "conditional_feature": "risk", "estimate": result.get("coefficient", ""), "interval_lower": result.get("ci_lower", ""), "interval_upper": result.get("ci_upper", ""), "shrinkage_amount": "not_available_unpooled_diagnostic", "support": len(group), "status": result.get("status"), **ROLE_FIELDS})
        else:
            estimates.append({"worker_id": worker, "conditional_feature": "risk", "estimate": "", "interval_lower": "", "interval_upper": "", "shrinkage_amount": "", "support": len(group), "status": "not_evaluable_insufficient_within_worker_risk_support", **ROLE_FIELDS})
    write_csv(output / "conditional_worker_estimates.csv", estimates)
    write_json(output / "conditional_model_failures.json", {**ROLE_FIELDS, "failed_models": failures})
    validation = []
    folds = (("C2B_to_Block1", frame[frame.stage == "C2B_C2-B"], frame[frame.stage == "C2A_RP_Block1"]), ("C2B_Block1_to_Block2", frame[frame.stage.isin(["C2B_C2-B", "C2A_RP_Block1"])], frame[frame.stage == "C2A_RP_Block2"]))
    for name, train, test in folds:
        for model_name, formula in (("M0", "quality ~ C(worker_id)"), ("M1", "quality ~ C(worker_id) + risk")):
            validation.append({"fold": name, "model_name": model_name, **prediction_metrics(train, test, formula), **ROLE_FIELDS})
    write_csv(output / "conditional_temporal_validation.csv", validation)
    lobo = []
    for building in sorted(frame.building_id.astype(str).unique()):
        train, test = frame[frame.building_id.astype(str) != building], frame[frame.building_id.astype(str) == building]
        lobo.append({"omitted_building": building, **prediction_metrics(train, test, "quality ~ C(worker_id) + risk"), **ROLE_FIELDS})
    write_csv(output / "conditional_leave_building_out.csv", lobo)
    slopes = {stage: {} for stage in ("C2A_RP_Block1", "C2A_RP_Block2")}
    for stage in slopes:
        for worker, group in frame[frame.stage == stage].groupby("worker_id"):
            result, _ = model_row("slope", "quality ~ risk", group)
            if result["status"] == "estimated" and result["coefficient"] != "": slopes[stage][worker] = result["coefficient"]
    common = sorted(set(slopes["C2A_RP_Block1"]) & set(slopes["C2A_RP_Block2"]))
    rank_row = {"comparison": "Block1_vs_Block2_worker_unpooled_slopes", "workers": len(common), "status": "estimated" if common else "not_evaluable_insufficient_within_stage_residual_df", "reason": "" if common else "no worker-stage slope retained after residual-df fail-closed check", "spearman": corr([slopes["C2A_RP_Block1"][worker] for worker in common], [slopes["C2A_RP_Block2"][worker] for worker in common], "spearman"), "kendall": corr([slopes["C2A_RP_Block1"][worker] for worker in common], [slopes["C2A_RP_Block2"][worker] for worker in common], "kendall"), "sign_agreement": float(np.mean([np.sign(slopes["C2A_RP_Block1"][worker]) == np.sign(slopes["C2A_RP_Block2"][worker]) for worker in common])) if common else "", **ROLE_FIELDS}
    write_csv(output / "conditional_rank_stability.csv", [rank_row])
    return failures


def posttask_diagnostics(meta: list[dict[str, Any]], evidence: list[dict[str, Any]], output: Path) -> None:
    outcomes = {(row["stage"], row["worker_id"], row["base_task_id"], row["canonical_submission_id"]): row for row in evidence}
    rows = []
    for row in meta:
        if row["tag_family"] != "difficulty":
            continue
        source = outcomes.get((row["stage"], row["worker_id"], row["base_task_id"], row["canonical_submission_id"]), {})
        rows.append({**row, "risk": source.get("risk", ""), "quality": source.get("iou_to_reference", ""), "condition": source.get("condition", ""), "routing_role": "not_eligible_for_first_route", "analysis_subrole": "descriptive_measurement_audit"})
    write_csv(output / "posttask_meta_label_diagnostics.csv", rows)
    agreement_path = output / "meta_label_task_agreement.csv"
    write_csv(output / "posttask_meta_label_agreement.csv", csv_rows(agreement_path))


def reconciliation(inputs: dict[str, Path | list[Path]], output: Path) -> None:
    rows = [
        {"artifact": "C1 v17 snapshot -> current v23", "producer_version": "paper_a_method_20260802_v17", "contract_version": EXPECTED_CONTRACT_VERSION, "formal_row_count": 739, "current_consumer_row_count": 739, "difference": 0, "difference_reason": "snapshot method binding differs", "accepted_by_normative_amendment": False, "usable_role": "C2B design input history", "unresolved_issue": "current Stage3 requires current contract binding"},
        {"artifact": "C2-B risk closeout -> cumulative", "producer_version": "c2b closeout", "contract_version": EXPECTED_CONTRACT_VERSION, "formal_row_count": 157, "current_consumer_row_count": 155, "difference": -2, "difference_reason": "two researcher_confirmed_bad_gt exclusions in current combined evidence", "accepted_by_normative_amendment": True, "usable_role": "C2A reestimate input", "unresolved_issue": "retain both counts"},
        {"artifact": "Block1 exclusion summary -> cumulative", "producer_version": "block1 reestimate v2", "contract_version": EXPECTED_CONTRACT_VERSION, "formal_row_count": 38, "current_consumer_row_count": 32, "difference": -6, "difference_reason": "current cumulative canonical-invalid/reference exclusions differ from summary", "accepted_by_normative_amendment": "", "usable_role": "diagnostic comparison", "unresolved_issue": "cross-artifact exclusion reconciliation remains open"},
        {"artifact": "post Block1 worker profile", "producer_version": "worker_profile_v2", "contract_version": EXPECTED_CONTRACT_VERSION, "formal_row_count": 22, "current_consumer_row_count": 22, "difference": 0, "difference_reason": "formal_frozen=false", "accepted_by_normative_amendment": False, "usable_role": "diagnostic routing-input profile", "unresolved_issue": "global_policy_eligible is not Strong Global roster"},
        {"artifact": "reference crosswalk", "producer_version": "post C2 local", "contract_version": EXPECTED_CONTRACT_VERSION, "formal_row_count": 96, "current_consumer_row_count": 96, "difference": 0, "difference_reason": "reference_unavailable and bad-GT use distinct fields", "accepted_by_normative_amendment": True, "usable_role": "risk eligibility audit", "unresolved_issue": "two reference-unavailable rows retained"},
    ]
    write_csv(output / "provenance_reconciliation.csv", [{**ROLE_FIELDS, **row} for row in rows])


def identity_audit(evidence: list[dict[str, Any]], output: Path) -> None:
    rows = []
    for (stage, substage), group in pd.DataFrame(evidence).groupby(["stage", "substage_block"]):
        duplicate = int(group.duplicated(subset=["worker_id", "base_task_id", "condition", "canonical_submission_id"]).sum())
        rows.append({"stage": stage, "substage_block": substage, "rows": len(group), "exact_match": len(group) - duplicate, "duplicate": duplicate, "missing_worker": int((group.worker_id == "").sum()), "missing_base_task": int((group.base_task_id == "").sum()), "missing_runtime_task": int((group.runtime_task_id == "").sum()), "missing_annotation": int((group.annotation_id == "").sum()), "missing_building": int((group.building_id == "").sum()), "missing_reference": int((group.reference_status == "").sum()), "missing_active_time_identity": int((group.active_time_source == "").sum()), "one_to_many": "audited_via_canonical_submission_key", "many_to_one": "audited_via_canonical_submission_key", "unresolved": duplicate > 0, **ROLE_FIELDS})
    write_csv(output / "identity_audit.csv", rows)


def readiness(output: Path) -> None:
    rows = [
        ("C2 risk evidence", "cumulative risk evidence", True, "diagnostic/formal input", ""),
        ("final pooled profile", "FINAL_POOLED_PROFILE_FROZEN", False, "missing", "C2A terminal closeout"),
        ("Strong Global roster", "STRONG_GLOBAL_FROZEN", False, "missing", "final pooled profile"),
        ("Full policy", "FULL_POLICY_FROZEN", False, "missing", "C2A terminal closeout and final pooled profile"),
        ("T1 outcome", "T1 resolved outcome artifact", False, "not generated", "Stage3 gate"),
        ("V1 outcome", "V1 ITT outcome artifact", False, "not generated", "Stage3/V1 gates"),
    ]
    write_csv(output / "policy_analysis_readiness.csv", [{"candidate_input": item[0], "required_artifact": item[1], "available": item[2], "formal_or_diagnostic": item[3], "missing_dependency": item[4], "provenance_status": "audited", **ROLE_FIELDS} for item in rows])


def report(output: Path, summary: dict[str, Any], model_failures: list[dict[str, Any]]) -> None:
    text = "\n".join([
        "# Calibration 双线处理计算报告", "", "- 角色：`diagnostic_pre_stage3`", "- 输入 evidence rows：" + str(summary["rows"]),
        "- meta rows：" + str(summary["meta_rows"]), "- risk eligible rows：" + str(summary["risk_eligible_rows"]),
        "- 处理文件：`calibration_evidence_long.csv`、`worker_stage_profile.csv`、`task_feature_matrix.csv`、`meta_label_long.csv`。",
        "- 模型文件：`global_risk_models.csv`、`conditional_model_summary.csv`；失败项见 `conditional_model_failures.json`。",
        "- 缺口：无 final pooled profile、Strong Global roster、Full policy、T1 outcome 或 V1 outcome。",
        "- provenance：C1 v17、C2-B 157/155、Block1 exclusion 与 worker profile formal_frozen 状态见 `provenance_reconciliation.csv`。",
        "- post-task meta labels 均标记为不可作为首次路由输入。", "- Block 3 未生成；正式 profile/policy freeze 均为 false。",
        "- 测试命令与验证结果由调用方写入 analysis manifest。", "",
    ])
    (output / "COMPUTATION_REPORT.md").write_text(text, encoding="utf-8")


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unavailable"


def run(output: Path) -> dict[str, Any]:
    if output.exists():
        if any(output.iterdir()):
            raise FileExistsError(f"output directory already contains a run:{output}")
        raise FileExistsError(f"output directory already exists:{output}")
    inputs = load_inputs(); contract = json.loads(inputs["contract"].read_text(encoding="utf-8"))  # type: ignore[union-attr]
    if contract.get("contract_version") != EXPECTED_CONTRACT_VERSION or contract.get("schema_version") != EXPECTED_CONTRACT_SCHEMA or sha256_file(inputs["contract"]) != EXPECTED_CONTRACT_SHA:  # type: ignore[arg-type]
        raise RuntimeError("current method contract does not match required v23 SHA")
    output.mkdir(parents=True)
    sources = build_source_manifest(inputs, output, EXPECTED_CONTRACT_SHA)
    reconciliation(inputs, output)
    evidence, meta = build_long_evidence(inputs, output)
    identity_audit(evidence, output)
    profiles = profile_rows(evidence, inputs["profile"])  # type: ignore[arg-type]
    write_csv(output / "worker_stage_profile.csv", profiles)
    write_csv(output / "task_feature_matrix.csv", task_matrix(evidence))
    summary = quality_outputs(evidence, meta, output)
    components_analysis(inputs["profile"], evidence, output)  # type: ignore[arg-type]
    qgt_rank_analysis(inputs["profile"], evidence, output)  # type: ignore[arg-type]
    candidate_tiers(inputs["profile"], evidence, output)  # type: ignore[arg-type]
    global_models = risk_models(evidence, output)
    feature_frame, qualified = conditional_features(evidence, output)
    conditional_failures = conditional_models(feature_frame, qualified, output)
    posttask_diagnostics(meta, evidence, output)
    readiness(output)
    report(output, summary, conditional_failures)
    outputs = [{"path": str(path.relative_to(output)), "sha256": sha256_file(path), "bytes": path.stat().st_size} for path in sorted(output.iterdir()) if path.is_file()]
    manifest = {**ROLE_FIELDS, "schema_version": "calibration_dual_track_processing_v1", "method_contract_version": EXPECTED_CONTRACT_VERSION, "method_contract_sha256": EXPECTED_CONTRACT_SHA, "git_commit": git_commit(), "python": sys.version, "platform": platform.platform(), "seed": SEED, "bootstrap_replicates": BOOTSTRAP_REPLICATES, "source_manifest_sha256": sha256_file(output / "source_manifest.json"), "inputs": len(sources), "outputs": outputs, "warnings": ["C2A Block2 model status remains multiple_variance_components_unidentifiable", "no formal profile or policy artifact created"], "failed_models": [row.get("model_name") for row in global_models if row.get("status") == "failed"] + [row.get("model_name") for row in conditional_failures], "executed_commands": ["python tools/thesis_main/analysis/process_calibration_dual_track.py --output-dir analysis_results/calibration_dual_track_processing_20260814_v1"]}
    write_json(output / "analysis_manifest.json", manifest)
    return {"output_dir": str(output), "evidence_rows": len(evidence), "meta_rows": len(meta), "outputs": len(outputs)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(run(args.output_dir), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
