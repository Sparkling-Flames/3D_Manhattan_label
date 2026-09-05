"""Materialize the historical P1/C1 uncertainty and variable-k evidence pack.

The language projects are pooled at image level.  Stage/reference regime is
retained only as provenance and sensitivity strata.  No output mutates the
normative method contract or any Label Studio source artifact.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.thesis_main.analysis.geometry_cluster_v2 import cluster_geometry_records
from tools.thesis_main.analysis.geometry_consensus.pairwise import pairwise_similarity
from tools.thesis_main.analysis.geometry_consensus.representation import normalize_geometry
from tools.thesis_main.analysis.audit_rq1_corrections_20260826 import (
    deterministic_building_bootstrap_spearman,
)
from tools.thesis_main.analysis.raw_rq1_recompute_20260826 import (
    canonicalise as canonicalise_raw_rq1,
    load_raw as load_raw_rq1,
    pairwise_task_summary as pairwise_task_summary_raw_rq1,
    task_groups as task_groups_raw_rq1,
)


ROOT = _PROJECT_ROOT
DEFAULT_OUT = ROOT / "analysis_results" / "historical_uncertainty_recompute_20260829_v1"
SEED = 20260829
K_VALUES = tuple(range(3, 14))
MINORITY_K_VALUES = (5, 8, 12, 16, 20)
CLUSTER_THRESHOLDS = (0.90, 0.925, 0.95, 0.97, 0.98)
RESOLVED_STATUSES = {"unimodal", "dominant_with_dissent"}
P1_REVISION_TASK = "564"
P1_EXCLUDED_TASK = "696"

P1_IMPORT = ROOT / "import_json" / "stage1_prescreen_final_20260325" / "stage1_prescreen_manual_import_v2.json"
P1_CLOSEOUT = ROOT / "analysis_results" / "prescreen_closeout_final_gold_v2_20260701"
C1_AUDIT = (
    ROOT
    / "analysis_results"
    / "c1_formal_audit_20260802_v16_final"
    / "c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03"
)
RAREFACTION = ROOT / "analysis_results" / "rq1_stratified_uncertainty_20260827_v1" / "dense_rarefaction_by_task_k.csv"
HIGH_DENSITY = ROOT / "analysis_results" / "rq1_raw_recompute_20260826" / "high_density_task_metrics.csv"
RAW_CANONICAL = ROOT / "analysis_results" / "rq1_raw_recompute_20260826" / "independent_canonical_records.csv"
FULL_CLUSTER_SENSITIVITY = (
    ROOT / "analysis_results" / "rq1_raw_recompute_20260826" / "high_density_cluster_threshold_sensitivity.csv"
)
METHOD_CONTRACT = ROOT / "docs" / "thesis_main" / "PAPER_A_METHOD_CONTRACT_CURRENT.json"


def truth(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "passed", "valid", "eligible"}


def text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def number(value: Any) -> float | None:
    try:
        result = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=_json_default) + "\n",
        encoding="utf-8",
    )


def _json_default(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, Path):
        return value.as_posix()
    raise TypeError(type(value).__name__)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def stable_json_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def candidate_id(row: Mapping[str, Any]) -> str:
    return text(row.get("canonical_annotation_id") or row.get("annotation_id"))


def deterministic_candidate_order(
    candidates: Sequence[Mapping[str, Any]], *, task_id: str, replicate: int, seed: int = SEED
) -> list[Mapping[str, Any]]:
    """Return one deterministic permutation; every k uses a nested prefix."""

    def rank(row: Mapping[str, Any]) -> tuple[str, str, str]:
        identifier = candidate_id(row)
        payload = f"{seed}|{task_id}|{replicate}|{identifier}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest(), identifier, text(row.get("worker_id"))

    return sorted(candidates, key=rank)


def hypergeom_probability_at_least(total: int, valid: int, sample: int, minimum: int) -> float:
    if total < 0 or valid < 0 or valid > total or sample < 0 or sample > total or minimum < 0:
        raise ValueError("invalid hypergeometric arguments")
    if minimum == 0:
        return 1.0
    if valid < minimum or sample < minimum:
        return 0.0
    denominator = math.comb(total, sample)
    probability = 0.0
    for successes in range(minimum, min(valid, sample) + 1):
        failures = sample - successes
        if failures <= total - valid:
            probability += math.comb(valid, successes) * math.comb(total - valid, failures) / denominator
    return probability


def _same_second_mode_recovered(
    full_second: set[str], sample_ids: set[str], prefix_memberships: Sequence[Sequence[str]]
) -> bool:
    """Whether the sampled members of the frozen second-ranked mode form one pure prefix cluster."""
    observed = full_second & sample_ids
    return len(observed) >= 2 and frozenset(observed) in {
        frozenset(map(str, cluster)) for cluster in prefix_memberships
    }


def _partition_matches_full_restriction(
    full_memberships: Sequence[Sequence[str]],
    sample_ids: set[str],
    prefix_memberships: Sequence[Sequence[str]],
) -> bool:
    """Compare unlabeled partitions after restricting the full partition to one sample."""
    expected = {
        frozenset(member for member in map(str, cluster) if member in sample_ids)
        for cluster in full_memberships
    } - {frozenset()}
    observed = {frozenset(map(str, cluster)) for cluster in prefix_memberships}
    return expected == observed


def leave_one_building_out_range(
    rows: Sequence[Mapping[str, Any]], *, value_field: str
) -> tuple[float | None, float | None]:
    usable = [
        row
        for row in rows
        if text(row.get("building_id")) and number(row.get(value_field)) is not None
    ]
    buildings = sorted({text(row["building_id"]) for row in usable})
    estimates = [
        mean(
            float(row[value_field])
            for row in usable
            if text(row["building_id"]) != omitted
        )
        for omitted in buildings
        if any(text(row["building_id"]) != omitted for row in usable)
    ]
    return (min(estimates), max(estimates)) if estimates else (None, None)


def building_cluster_bootstrap_ci(
    rows: Sequence[Mapping[str, Any]],
    *,
    value_field: str,
    replicates: int = 4000,
    seed: int = SEED,
) -> tuple[float | None, float | None]:
    by_building: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        value = number(row.get(value_field))
        building = text(row.get("building_id"))
        if building and value is not None:
            by_building[building].append(value)
    buildings = sorted(by_building)
    if not buildings:
        return None, None
    if len(buildings) == 1:
        estimate = float(np.mean(by_building[buildings[0]]))
        return estimate, estimate
    rng = np.random.default_rng(seed)
    draws: list[float] = []
    for _ in range(replicates):
        sampled = rng.choice(buildings, size=len(buildings), replace=True)
        values = [value for building in sampled for value in by_building[str(building)]]
        draws.append(float(np.mean(values)))
    return float(np.quantile(draws, 0.025)), float(np.quantile(draws, 0.975))


def _unique(rows: Sequence[Mapping[str, Any]], field: str, *, allow_blank: bool = False) -> str:
    values = {text(row.get(field)) for row in rows if allow_blank or text(row.get(field))}
    if len(values) != 1:
        raise AssertionError(f"{field} is not unique: {sorted(values)}")
    return next(iter(values))


def _language(project_id: str) -> str:
    if project_id in {"39", "66"}:
        return "English"
    if project_id in {"28", "69"}:
        return "Chinese"
    raise AssertionError(f"unexpected high-density project: {project_id}")


def _official_split(base_task_id: str) -> str:
    matches = [
        split
        for split in ("train", "valid", "test")
        if (ROOT / "data" / "mp3d_layout" / split / "img" / f"{base_task_id}.png").exists()
    ]
    if len(matches) != 1:
        raise AssertionError(f"official split unresolved or duplicated for {base_task_id}: {matches}")
    return "validation" if matches[0] == "valid" else matches[0]


def _p1_integrity_file(pattern: str) -> Path:
    matches = list((C1_AUDIT / "raw_snapshots" / "p1_integrity").glob(pattern))
    if len(matches) != 1:
        raise AssertionError(f"expected one P1 integrity input for {pattern}, found {len(matches)}")
    return matches[0]


def _annotation_key(row: Mapping[str, Any], *, worker_field: str = "worker_id") -> tuple[str, str, str, str]:
    return (
        text(row.get("project_id")),
        text(row.get("task_id")),
        text(row.get(worker_field)),
        text(row.get("annotation_id")),
    )


def load_inputs() -> dict[str, Any]:
    p1_import_payload = json.loads(P1_IMPORT.read_text(encoding="utf-8-sig"))
    p1_import = [dict(item.get("data") or {}) for item in p1_import_payload]
    p1_gold = read_jsonl(P1_CLOSEOUT / "final_gold_records_v2_p1_closeout_corrected.jsonl")
    p1_alignment = [
        row
        for row in read_csv(P1_CLOSEOUT / "prescreen_geometry_gold_alignment_audit.csv")
        if row.get("dataset_group") == "PreScreen_manual" and row.get("condition") == "manual"
    ]
    p1_canonical = [
        row
        for row in read_csv(P1_CLOSEOUT / "prescreen_canonical_annotations.csv")
        if row.get("dataset_group") == "PreScreen_manual" and row.get("condition") == "manual"
    ]
    p1_evidence_path = _p1_integrity_file("*_p1_task_evidence_correction_v1.csv")
    p1_scores_path = _p1_integrity_file("*_p1_geometry_task_scores_v1.csv")
    p1_evidence = [
        row
        for row in read_csv(p1_evidence_path)
        if row.get("dataset_group") == "PreScreen_manual" and row.get("condition") == "manual"
    ]
    p1_scores = [
        row
        for row in read_csv(p1_scores_path)
        if row.get("dataset_group") == "PreScreen_manual" and row.get("condition") == "manual"
    ]
    p1_corrections = json.loads(
        (P1_CLOSEOUT / "prescreen_final_gold_v2_correction_audit.json").read_text(encoding="utf-8-sig")
    )

    p1_task_ids = {text(row.get("task_id")) for row in p1_import}
    p1_bases = {text(row.get("base_task_id")) for row in p1_import}
    p1_gold = [row for row in p1_gold if text(row.get("task_id")) in p1_task_ids]
    assert len(p1_import) == len(p1_task_ids) == len(p1_bases) == len(p1_gold) == 30
    assert {text(row.get("base_task_id")) for row in p1_gold} == p1_bases
    assert len(p1_alignment) == 60 and len({row["base_image_key"] for row in p1_alignment}) == 30
    assert Counter(row["base_image_key"] for row in p1_alignment) == Counter({base: 2 for base in p1_bases})

    p1_tables = ((p1_canonical, "annotator_id"), (p1_evidence, "worker_id"), (p1_scores, "worker_id"))
    p1_key_sets = []
    for rows, worker_field in p1_tables:
        keys = {_annotation_key(row, worker_field=worker_field) for row in rows}
        assert len(rows) == len(keys) == 779
        p1_key_sets.append(keys)
    assert p1_key_sets[0] == p1_key_sets[1] == p1_key_sets[2]
    assert {row["base_task_id"] for row in p1_scores} == p1_bases

    c1_quality = [
        row
        for row in read_csv(C1_AUDIT / "c1_gt_quality_analysis.csv")
        if row.get("dataset_group") == "Calibration_anchor" and row.get("condition") == "manual"
    ]
    c1_bases = {row["base_task_id"] for row in c1_quality}
    assert len(c1_quality) == 276 and len(c1_bases) == 12
    assert len({row["canonical_annotation_id"] for row in c1_quality}) == 276
    assert sum(truth(row.get("gt_primary_analysis_eligible")) for row in c1_quality) == 263
    assert sum(truth(row.get("peer_analysis_eligible")) for row in c1_quality) == 264
    c1_references = [
        row for row in read_csv(C1_AUDIT / "c1_task_outcome_reference.csv") if row.get("base_task_id") in c1_bases
    ]
    assert len(c1_references) == 24
    assert Counter(row["base_task_id"] for row in c1_references) == Counter({base: 2 for base in c1_bases})
    assert all(
        truth(row.get("geometry_reference_ready"))
        and truth(row.get("primary_geometry_eligible"))
        and row.get("final_scope") == "in_scope"
        and not truth(row.get("submission_informed_reference_revision"))
        for row in c1_references
    )
    assert not (p1_bases & c1_bases) and len(p1_bases | c1_bases) == 42

    c1_pairwise = [
        row
        for row in read_csv(C1_AUDIT / "geometry_pairwise_similarity_C1.csv")
        if row.get("base_task_id") in c1_bases and row.get("condition") == "manual"
    ]

    high_density = read_csv(HIGH_DENSITY)
    assert len(high_density) == 42 and {row["base_task_id"] for row in high_density} == p1_bases | c1_bases
    assert sum(int(row["selected_support"]) for row in high_density) == 1055
    assert sum(int(row["strict_valid_support"]) for row in high_density) == 1013
    p1_frozen_canonical = [
        row
        for row in read_csv(RAW_CANONICAL)
        if row.get("stage") == "P1"
        and row.get("dataset_group") == "PreScreen_manual"
        and row.get("condition") == "manual"
    ]
    p1_frozen_keys = {
        (row["project_id"], row["runtime_task_id"], row["worker_id"], row["annotation_id"])
        for row in p1_frozen_canonical
    }
    assert len(p1_frozen_canonical) == len(p1_frozen_keys) == 779
    assert p1_frozen_keys == p1_key_sets[0]
    assert {_official_split(base) for base in p1_bases | c1_bases} == {"test"}

    return {
        "p1_import": p1_import,
        "p1_gold": p1_gold,
        "p1_alignment": p1_alignment,
        "p1_canonical": p1_canonical,
        "p1_evidence": p1_evidence,
        "p1_scores": p1_scores,
        "p1_corrections": p1_corrections,
        "p1_frozen_canonical": p1_frozen_canonical,
        "p1_evidence_path": p1_evidence_path,
        "p1_scores_path": p1_scores_path,
        "c1_quality": c1_quality,
        "c1_references": c1_references,
        "c1_pairwise": c1_pairwise,
        "p1_bases": p1_bases,
        "c1_bases": c1_bases,
        "high_density": high_density,
    }


def build_reference_contract(inputs: Mapping[str, Any]) -> list[dict[str, Any]]:
    p1_gold = {text(row["task_id"]): row for row in inputs["p1_gold"]}
    p1_alignment: dict[str, list[dict[str, str]]] = defaultdict(list)
    p1_scores: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in inputs["p1_alignment"]:
        p1_alignment[row["base_image_key"]].append(row)
    for row in inputs["p1_scores"]:
        p1_scores[row["base_task_id"]].append(row)
    corrections = {
        text(row.get("task_id")): text(row.get("correction_type"))
        for row in inputs["p1_corrections"].get("corrections", [])
    }
    gold_path = P1_CLOSEOUT / "final_gold_records_v2_p1_closeout_corrected.jsonl"
    gold_file_sha = sha256(gold_path)
    rows: list[dict[str, Any]] = []
    for imported in sorted(inputs["p1_import"], key=lambda row: row["base_task_id"]):
        source_task_id = text(imported["task_id"])
        base = text(imported["base_task_id"])
        gold = p1_gold[source_task_id]
        aligned = p1_alignment[base]
        scores = p1_scores[base]
        reference_status = _unique(scores, "geometry_reference_status", allow_blank=True)
        reference_identity = _unique(scores, "reference_id", allow_blank=True)
        validation_level = _unique(aligned, "geometry_gold_validation_level", allow_blank=True)
        ready = truth(gold.get("geometry_gold_ready"))
        correction = corrections.get(source_task_id, "")
        if correction == "geometry_contract":
            revision = "geometry_contract_correction_recorded"
        elif correction == "scope_contract":
            revision = "scope_contract_correction_recorded"
        else:
            revision = "no_recorded_post_closeout_correction"
        rows.append(
            {
                "base_task_id": base,
                "stage": "P1",
                "source_stage": "PreScreen",
                "stage_subset": "P1_manual",
                "condition": "manual",
                "building_id": base.split("_", 1)[0],
                "official_split": _official_split(base),
                "source_task_id": source_task_id,
                "runtime_context_count": len(aligned),
                "language_contexts": "Chinese;English",
                "source_dataset_group": text(imported.get("dataset_group")),
                "reference_regime": reference_status or "unavailable",
                "reference_record_path": gold_path.relative_to(ROOT).as_posix(),
                "reference_identity": reference_identity,
                "reference_file_sha256": gold_file_sha,
                "reference_geometry_sha256": stable_json_sha256(gold.get("canonical_corners_norm") or []),
                "reference_status": "ready" if ready else "not_ready",
                "reference_validation_level": validation_level,
                "reference_independence_status": "revision_independence_not_machine_verifiable",
                "reference_independence_basis": "user_verified_project20_export; no C1-equivalent submission-informed revision field",
                "submission_informed_reference_revision": "not_machine_materialized",
                "reference_revision_status": revision,
                "geometry_reference_ready": ready,
                "primary_geometry_eligible": ready and text(gold.get("final_scope_binary")) == "in_scope",
                "final_scope": text(gold.get("final_scope_binary")),
                "scope_subtype": text(gold.get("final_scope_alias")),
                "scope_resolution_status": text(gold.get("adjudication_status")),
                "scope_source": text(gold.get("scope_source")),
                "final_gold_source": text(gold.get("final_gold_source")),
                "export_snapshot": text(gold.get("export_snapshot")),
                "worker_scope_answer_set_version": "not_materialized",
                "analysis_stratum": "P1_sensitivity" if ready else "excluded_oos_no_geometry",
                "p1_28_sensitivity_eligible": ready and source_task_id != P1_REVISION_TASK,
                "exclusion_reason": "" if ready else "oos_insufficient_geometry_reference_not_ready",
            }
        )

    c1_by_base: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in inputs["c1_references"]:
        c1_by_base[row["base_task_id"]].append(row)
    c1_reference_path = C1_AUDIT / "c1_task_outcome_reference.csv"
    c1_file_sha = sha256(c1_reference_path)
    for base, refs in sorted(c1_by_base.items()):
        consistency_fields = (
            "task_id",
            "reference_identity",
            "reference_sha256",
            "geometry_reference_mode",
            "geometry_reference_status",
            "final_scope",
            "scope_resolution_status",
        )
        values = {field: _unique(refs, field, allow_blank=True) for field in consistency_fields}
        rows.append(
            {
                "base_task_id": base,
                "stage": "C1",
                "source_stage": "C1",
                "stage_subset": "C1_anchor",
                "condition": "manual",
                "building_id": base.split("_", 1)[0],
                "official_split": _official_split(base),
                "source_task_id": values["task_id"],
                "runtime_context_count": len(refs),
                "language_contexts": "Chinese;English",
                "source_dataset_group": "Calibration_anchor",
                "reference_regime": values["geometry_reference_mode"],
                "reference_record_path": c1_reference_path.relative_to(ROOT).as_posix(),
                "reference_identity": values["reference_identity"],
                "reference_file_sha256": c1_file_sha,
                "reference_geometry_sha256": values["reference_sha256"],
                "reference_status": values["geometry_reference_status"],
                "reference_validation_level": _unique(refs, "reference_evidence_status", allow_blank=True),
                "reference_independence_status": "documented_no_submission_informed_revision",
                "reference_independence_basis": "public_frozen_gt; per-row false; operational correction_count=0",
                "submission_informed_reference_revision": False,
                "reference_revision_status": "no_reference_amendment",
                "geometry_reference_ready": True,
                "primary_geometry_eligible": True,
                "final_scope": values["final_scope"],
                "scope_subtype": text(refs[0].get("oos_subtype")),
                "scope_resolution_status": values["scope_resolution_status"],
                "scope_source": text(refs[0].get("scope_reference_mode")),
                "final_gold_source": "public_frozen_gt",
                "export_snapshot": "",
                "worker_scope_answer_set_version": "not_materialized",
                "analysis_stratum": "C1_primary",
                "p1_28_sensitivity_eligible": "not_applicable",
                "exclusion_reason": "",
            }
        )
    rows.sort(key=lambda row: (row["stage"], row["base_task_id"]))
    assert len(rows) == 42
    assert Counter(row["stage"] for row in rows) == Counter({"P1": 30, "C1": 12})
    assert Counter(row["analysis_stratum"] for row in rows) == Counter(
        {"C1_primary": 12, "P1_sensitivity": 29, "excluded_oos_no_geometry": 1}
    )
    assert sum(bool(row["geometry_reference_ready"]) for row in rows) == 41
    assert sum(row["p1_28_sensitivity_eligible"] is True for row in rows) == 28
    return rows


def build_annotation_eligibility(
    inputs: Mapping[str, Any], reference_contract: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    contract = {row["base_task_id"]: row for row in reference_contract}
    canonical_by_key = {
        _annotation_key(row, worker_field="annotator_id"): row for row in inputs["p1_canonical"]
    }
    evidence_by_key = {_annotation_key(row): row for row in inputs["p1_evidence"]}
    frozen_by_key = {
        (row["project_id"], row["runtime_task_id"], row["worker_id"], row["annotation_id"]): row
        for row in inputs["p1_frozen_canonical"]
    }
    rows: list[dict[str, Any]] = []
    for score in sorted(inputs["p1_scores"], key=lambda row: _annotation_key(row)):
        key = _annotation_key(score)
        canonical = canonical_by_key[key]
        evidence = evidence_by_key[key]
        frozen = frozen_by_key[key]
        base = score["base_task_id"]
        ref = contract[base]
        process_analysis_eligible = truth(evidence.get("included_in_process_reliability"))
        quality_process_pass = not truth(score.get("process_failure_observed"))
        scope_eligible = ref["final_scope"] == "in_scope"
        quality_eligible = truth(score.get("included_in_p1_geometry_profile"))
        strict_geometry = normalize_geometry(
            json.loads(canonical.get("canonical_geometry") or "[]"), width=1024, height=512
        )
        rows.append(
            {
                "canonical_annotation_id": canonical["canonical_annotation_id"],
                "base_task_id": base,
                "stage": "P1",
                "stage_subset": "P1_manual",
                "project_id": score["project_id"],
                "runtime_task_id": score["task_id"],
                "worker_id": score["worker_id"],
                "annotation_id": score["annotation_id"],
                "language": _language(score["project_id"]),
                "building_id": ref["building_id"],
                "official_split": ref["official_split"],
                "condition": score["condition"],
                "independence_status": evidence["independence_status"],
                "independence_reason": evidence["independence_reason"],
                "process_analysis_eligible": process_analysis_eligible,
                "quality_process_pass": quality_process_pass,
                "scope_eligible": scope_eligible,
                "strict_geometry_valid": truth(frozen.get("strict_valid")),
                "strict_geometry_invalid_reason": frozen.get("strict_reason", ""),
                "strict_geometry_source": "frozen_dense42_recompute",
                "current_canonical_geometry_valid": bool(strict_geometry.get("valid")),
                "formal_geometry_score_gate_passed": truth(score.get("geometry_score_gate_passed")),
                "geometry_structurally_computable": truth(score.get("geometry_score_gate_passed")),
                "gt_primary_analysis_eligible": quality_eligible,
                "peer_analysis_eligible": "not_materialized",
                "geometry_score": number(score.get("geometry_score_raw")),
                "reference_regime": ref["reference_regime"],
                "exclusion_reason": score.get("exclusion_reason", ""),
                "source_contract_note": "P1 peer eligibility intentionally not inferred from quality eligibility",
            }
        )
    for item in sorted(inputs["c1_quality"], key=lambda row: row["canonical_annotation_id"]):
        base = item["base_task_id"]
        ref = contract[base]
        rows.append(
            {
                "canonical_annotation_id": item["canonical_annotation_id"],
                "base_task_id": base,
                "stage": "C1",
                "stage_subset": "C1_anchor",
                "project_id": item["project_id"],
                "runtime_task_id": item["ls_runtime_task_id"],
                "worker_id": item["worker_id"],
                "annotation_id": item["annotation_id"],
                "language": _language(item["project_id"]),
                "building_id": ref["building_id"],
                "official_split": ref["official_split"],
                "condition": item["condition"],
                "independence_status": item["independence_status"],
                "independence_reason": item.get("independence_exclusion_reason", ""),
                "process_analysis_eligible": truth(item.get("process_eligible")),
                "quality_process_pass": truth(item.get("process_eligible")),
                "scope_eligible": truth(item.get("scope_eligible")),
                "strict_geometry_valid": truth(item.get("structurally_valid")),
                "strict_geometry_invalid_reason": "" if truth(item.get("structurally_valid")) else item.get("gt_primary_analysis_exclusion_reason", ""),
                "strict_geometry_source": "c1_formal_audit",
                "current_canonical_geometry_valid": truth(item.get("geometry_structurally_computable")),
                "formal_geometry_score_gate_passed": truth(item.get("gt_score_computable")),
                "geometry_structurally_computable": truth(item.get("geometry_structurally_computable")),
                "gt_primary_analysis_eligible": truth(item.get("gt_primary_analysis_eligible")),
                "peer_analysis_eligible": truth(item.get("peer_analysis_eligible")),
                "geometry_score": number(item.get("iou_to_gt")),
                "reference_regime": ref["reference_regime"],
                "exclusion_reason": item.get("gt_primary_analysis_exclusion_reason", ""),
                "source_contract_note": "C1 formal estimand-specific eligibility copied without reinterpretation",
            }
        )
    assert len(rows) == 1055
    assert Counter(row["stage"] for row in rows) == Counter({"P1": 779, "C1": 276})
    assert Counter(row["stage"] for row in rows if row["strict_geometry_valid"] is True) == Counter(
        {"P1": 737, "C1": 276}
    )
    assert Counter(row["stage"] for row in rows if row["current_canonical_geometry_valid"] is True) == Counter(
        {"P1": 739, "C1": 276}
    )
    assert sum(row["gt_primary_analysis_eligible"] is True for row in rows) == 770
    assert Counter(row["independence_status"] for row in rows if row["stage"] == "P1") == Counter(
        {"independent": 576, "non_independent_confirmed": 88, "non_independent_suspected": 115}
    )
    return rows


def build_quality_candidates(inputs: Mapping[str, Any]) -> tuple[dict[str, list[dict[str, Any]]], dict[str, dict[tuple[str, str], dict[str, Any]]]]:
    canonical_by_key = {
        _annotation_key(row, worker_field="annotator_id"): row for row in inputs["p1_canonical"]
    }
    pools: dict[str, list[dict[str, Any]]] = defaultdict(list)
    pair_maps: dict[str, dict[tuple[str, str], dict[str, Any]]] = defaultdict(dict)
    for score in inputs["p1_scores"]:
        if not truth(score.get("included_in_p1_geometry_profile")):
            continue
        canonical = canonical_by_key[_annotation_key(score)]
        points = json.loads(canonical["canonical_geometry"])
        geometry = normalize_geometry(points, width=1024, height=512)
        if not geometry.get("valid"):
            raise AssertionError(f"P1 quality-eligible geometry failed current normalizer: {canonical['canonical_annotation_id']}")
        identifier = canonical["canonical_annotation_id"]
        geometry["candidate_id"] = identifier
        pools[score["base_task_id"]].append(
            {
                "canonical_annotation_id": identifier,
                "worker_id": score["worker_id"],
                "project_id": score["project_id"],
                "language": _language(score["project_id"]),
                "stage": "P1",
                "base_task_id": score["base_task_id"],
                "quality": float(score["geometry_score_raw"]),
                "_geometry": geometry,
            }
        )
    for task, candidates in pools.items():
        for left_index, left in enumerate(candidates):
            for right in candidates[left_index + 1 :]:
                key = tuple(sorted((candidate_id(left), candidate_id(right))))
                pair_maps[task][key] = pairwise_similarity(left["_geometry"], right["_geometry"])

    c1_pairwise: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in inputs["c1_pairwise"]:
        key = (row["base_task_id"], *sorted((row["worker_id_left"], row["worker_id_right"])))
        c1_pairwise[key] = {
            "metric_compatible": truth(row.get("metric_compatible")),
            "pointwise_correspondence_compatible": truth(row.get("pointwise_correspondence_compatible")),
            "q_boundary": number(row.get("q_boundary")),
            "q_wallwall": number(row.get("q_wallwall")),
        }
    for item in inputs["c1_quality"]:
        if not truth(item.get("gt_primary_analysis_eligible")):
            continue
        identifier = item["canonical_annotation_id"]
        frozen_sha = item.get("repaired_geometry_sha256") or item.get("raw_geometry_sha256")
        pools[item["base_task_id"]].append(
            {
                "canonical_annotation_id": identifier,
                "worker_id": item["worker_id"],
                "project_id": item["project_id"],
                "language": _language(item["project_id"]),
                "stage": "C1",
                "base_task_id": item["base_task_id"],
                "quality": float(item["iou_to_gt"]),
                "_geometry": {
                    "valid": True,
                    "candidate_id": identifier,
                    "worker_id": item["worker_id"],
                    "frozen_geometry_sha256": frozen_sha,
                },
            }
        )
    for task, candidates in pools.items():
        if candidates[0]["stage"] != "C1":
            continue
        for left_index, left in enumerate(candidates):
            for right in candidates[left_index + 1 :]:
                worker_key = (task, *sorted((left["worker_id"], right["worker_id"])))
                if worker_key not in c1_pairwise:
                    raise AssertionError(f"missing C1 pairwise metric: {worker_key}")
                pair_maps[task][tuple(sorted((candidate_id(left), candidate_id(right))))] = c1_pairwise[worker_key]

    support = Counter(len(rows) for rows in pools.values())
    assert len(pools) == 41 and min(len(rows) for rows in pools.values()) == 13
    assert support == Counter({18: 10, 22: 11, 17: 8, 19: 5, 16: 3, 13: 1, 15: 1, 20: 1, 21: 1})
    assert sum(len(rows) for rows in pools.values()) == 770
    return dict(pools), dict(pair_maps)


def _pairwise_lookup(pair_map: Mapping[tuple[str, str], Mapping[str, Any]]):
    def lookup(left: Mapping[str, Any], right: Mapping[str, Any]) -> Mapping[str, Any]:
        key = tuple(sorted((text(left.get("candidate_id")), text(right.get("candidate_id")))))
        if key not in pair_map:
            raise AssertionError(f"pairwise lookup missing {key}")
        return pair_map[key]

    return lookup


def _cluster(candidates: Sequence[Mapping[str, Any]], task: str, pair_map: Mapping[tuple[str, str], Mapping[str, Any]]) -> dict[str, Any]:
    return cluster_geometry_records(
        list(candidates),
        min_q_boundary=0.95,
        min_q_wallwall=0.95,
        base_task_id=task,
        condition="manual",
        minimum_valid_k=3,
        pairwise_fn=_pairwise_lookup(pair_map),
    )


def _selected(candidates: Sequence[Mapping[str, Any]], cluster: Mapping[str, Any]) -> Mapping[str, Any] | None:
    identifier = text(cluster.get("largest_cluster_medoid_annotation_id"))
    return next((row for row in candidates if candidate_id(row) == identifier), None)


def _compatible(
    left_id: str, right_id: str, pair_map: Mapping[tuple[str, str], Mapping[str, Any]]
) -> tuple[bool | None, float | None]:
    if not left_id or not right_id:
        return None, None
    if left_id == right_id:
        return True, 0.0
    item = pair_map.get(tuple(sorted((left_id, right_id))))
    if not item:
        return None, None
    boundary, wall = number(item.get("q_boundary")), number(item.get("q_wallwall"))
    if boundary is None or wall is None or not truth(item.get("metric_compatible")):
        return None, None
    compatible = truth(item.get("pointwise_correspondence_compatible")) and boundary >= 0.95 and wall >= 0.95
    return compatible, 1.0 - min(boundary, wall)


def replay_quality_curves(
    pools: Mapping[str, Sequence[Mapping[str, Any]]],
    pair_maps: Mapping[str, Mapping[tuple[str, str], Mapping[str, Any]]],
    *,
    replicates: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    task_k_rows: list[dict[str, Any]] = []
    transition_rows: list[dict[str, Any]] = []
    for task, candidates in sorted(pools.items()):
        stage = text(candidates[0].get("stage"))
        building = task.split("_", 1)[0]
        pair_map = pair_maps[task]
        full_cluster = _cluster(candidates, task, pair_map)
        full_status = text(full_cluster.get("task_crowd_structure_status"))
        full_resolved = full_status in RESOLVED_STATUSES
        full_selected = _selected(candidates, full_cluster) if full_resolved else None
        full_selected_id = candidate_id(full_selected or {})
        accumulators: dict[int, dict[str, list[float]]] = {
            k: defaultdict(list) for k in K_VALUES if k <= len(candidates)
        }
        transitions: dict[int, dict[str, list[float]]] = {
            k: defaultdict(list) for k in K_VALUES if k + 1 in K_VALUES and k + 1 <= len(candidates)
        }
        for replicate in range(replicates):
            order = deterministic_candidate_order(candidates, task_id=task, replicate=replicate)
            results: dict[int, dict[str, Any]] = {}
            for k in accumulators:
                sample = order[:k]
                cluster = _cluster(sample, task, pair_map)
                status = text(cluster.get("task_crowd_structure_status"))
                resolved = status in RESOLVED_STATUSES
                selected = _selected(sample, cluster) if resolved else None
                selected_id = candidate_id(selected or {})
                quality = number(selected.get("quality")) if selected else None
                compatible_full, distance_full = _compatible(selected_id, full_selected_id, pair_map)
                acc = accumulators[k]
                acc["partition_unique"].append(float(cluster.get("partition_status") == "unique"))
                acc["resolved"].append(float(resolved))
                acc["supported_multimodal"].append(float(status == "supported_multimodal"))
                acc["not_evaluable"].append(float(status == "not_evaluable"))
                acc["delivery_adjusted_quality"].append(float(quality) if quality is not None else 0.0)
                if quality is not None:
                    acc["resolved_quality"].append(float(quality))
                if full_resolved and compatible_full is not None:
                    acc["full_output_recovered"].append(float(resolved and compatible_full))
                    if resolved and distance_full is not None:
                        acc["distance_to_full_output"].append(float(distance_full))
                if full_status == "supported_multimodal":
                    acc["generic_multimodality_reproduced"].append(
                        float(status == "supported_multimodal")
                    )
                results[k] = {
                    "resolved": resolved,
                    "selected_id": selected_id,
                    "quality": quality,
                    "delivery_adjusted_quality": float(quality) if quality is not None else 0.0,
                }
            for k, values in transitions.items():
                left, right = results[k], results[k + 1]
                compatible, distance = _compatible(left["selected_id"], right["selected_id"], pair_map)
                material_change = left["resolved"] != right["resolved"]
                if left["resolved"] and right["resolved"]:
                    material_change = compatible is not True
                    if distance is not None:
                        values["output_distance"].append(distance)
                    if left["quality"] is not None and right["quality"] is not None:
                        values["resolved_pair_quality_gain"].append(right["quality"] - left["quality"])
                values["material_change"].append(float(material_change))
                values["delivery_adjusted_quality_gain"].append(
                    right["delivery_adjusted_quality"] - left["delivery_adjusted_quality"]
                )
        for k, metrics in accumulators.items():
            task_k_rows.append(
                {
                    "base_task_id": task,
                    "building_id": building,
                    "stage": stage,
                    "k_valid": k,
                    "replicates": replicates,
                    "full_quality_eligible_k": len(candidates),
                    "full_structure_status": full_status,
                    "full_resolved": full_resolved,
                    "partition_unique_rate": mean(metrics["partition_unique"]),
                    "resolved_rate": mean(metrics["resolved"]),
                    "supported_multimodal_rate": mean(metrics["supported_multimodal"]),
                    "not_evaluable_rate": mean(metrics["not_evaluable"]),
                    "resolved_only_quality": mean(metrics["resolved_quality"]) if metrics["resolved_quality"] else None,
                    "resolved_quality_replicates": len(metrics["resolved_quality"]),
                    "delivery_adjusted_quality": mean(metrics["delivery_adjusted_quality"]),
                    "full_output_recovery_rate": mean(metrics["full_output_recovered"]) if metrics["full_output_recovered"] else None,
                    "full_output_recovery_replicates": len(metrics["full_output_recovered"]),
                    "mean_distance_to_full_output": mean(metrics["distance_to_full_output"]) if metrics["distance_to_full_output"] else None,
                    "generic_multimodality_status_reproduction_rate": (
                        mean(metrics["generic_multimodality_reproduced"])
                        if metrics["generic_multimodality_reproduced"]
                        else None
                    ),
                    "generic_multimodality_status_reproduction_replicates": len(
                        metrics["generic_multimodality_reproduced"]
                    ),
                }
            )
        for k, metrics in transitions.items():
            transition_rows.append(
                {
                    "base_task_id": task,
                    "building_id": building,
                    "stage": stage,
                    "k_from": k,
                    "k_to": k + 1,
                    "replicates": replicates,
                    "material_output_change_rate": mean(metrics["material_change"]),
                    "mean_output_distance_when_both_resolved": mean(metrics["output_distance"]) if metrics["output_distance"] else None,
                    "delivery_adjusted_quality_gain": mean(metrics["delivery_adjusted_quality_gain"]),
                    "resolved_pair_quality_gain": mean(metrics["resolved_pair_quality_gain"]) if metrics["resolved_pair_quality_gain"] else None,
                    "resolved_pair_replicates": len(metrics["resolved_pair_quality_gain"]),
                }
            )
    return task_k_rows, transition_rows


def _strata_filter(name: str, rows: Sequence[Mapping[str, Any]], contract: Mapping[str, Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    if name == "C1_primary_12":
        return [row for row in rows if row["stage"] == "C1"]
    if name == "P1_sensitivity_29":
        return [row for row in rows if row["stage"] == "P1"]
    if name == "P1_excluding_revision_28":
        return [row for row in rows if row["stage"] == "P1" and contract[row["base_task_id"]]["source_task_id"] != P1_REVISION_TASK]
    if name == "pooled_image_equal_41":
        return list(rows)
    if name == "pooled_excluding_revision_40":
        return [row for row in rows if contract[row["base_task_id"]]["source_task_id"] != P1_REVISION_TASK]
    raise KeyError(name)


def _summary_row(
    rows: Sequence[Mapping[str, Any]],
    *,
    field: str,
    bootstrap_replicates: int,
    seed_offset: int,
) -> dict[str, Any]:
    values = [number(row.get(field)) for row in rows]
    values = [value for value in values if value is not None]
    lower, upper = building_cluster_bootstrap_ci(
        rows, value_field=field, replicates=bootstrap_replicates, seed=SEED + seed_offset
    )
    return {
        "estimate": mean(values) if values else None,
        "ci95_lower_building_bootstrap": lower,
        "ci95_upper_building_bootstrap": upper,
        "task_count_with_value": len(values),
    }


def summarize_quality_curves(
    task_rows: Sequence[Mapping[str, Any]],
    contract_rows: Sequence[Mapping[str, Any]],
    *,
    bootstrap_replicates: int,
) -> list[dict[str, Any]]:
    contract = {row["base_task_id"]: row for row in contract_rows}
    strata = (
        "C1_primary_12",
        "P1_sensitivity_29",
        "P1_excluding_revision_28",
        "pooled_image_equal_41",
        "pooled_excluding_revision_40",
    )
    output: list[dict[str, Any]] = []
    for stratum in strata:
        subset = _strata_filter(stratum, task_rows, contract)
        for k in K_VALUES:
            current = [row for row in subset if int(row["k_valid"]) == k]
            if not current:
                continue
            row: dict[str, Any] = {
                "analysis_stratum": stratum,
                "weighting": "task_equal; pooled rows are image-equal",
                "k_valid": k,
                "task_count": len(current),
                "building_count": len({row["building_id"] for row in current}),
                "simulation_replicates_per_task": int(current[0]["replicates"]),
                "reference_interpretation": (
                    "programmatically independent frozen public GT"
                    if stratum.startswith("C1")
                    else "P1 user-verified reference sensitivity"
                    if stratum.startswith("P1")
                    else "mixed reference regimes; sensitivity only"
                ),
            }
            for offset, field in enumerate(
                (
                    "resolved_rate",
                    "partition_unique_rate",
                    "supported_multimodal_rate",
                    "not_evaluable_rate",
                    "resolved_only_quality",
                    "delivery_adjusted_quality",
                )
            ):
                summary = _summary_row(
                    current,
                    field=field,
                    bootstrap_replicates=bootstrap_replicates,
                    seed_offset=1000 * k + 37 * offset + len(stratum),
                )
                row[field] = summary.pop("estimate")
                row.update({f"{field}_{key}": value for key, value in summary.items()})
            output.append(row)
    return output


def summarize_transitions(
    task_rows: Sequence[Mapping[str, Any]],
    contract_rows: Sequence[Mapping[str, Any]],
    *,
    bootstrap_replicates: int,
) -> list[dict[str, Any]]:
    contract = {row["base_task_id"]: row for row in contract_rows}
    output: list[dict[str, Any]] = []
    for stratum in ("C1_primary_12", "P1_sensitivity_29", "P1_excluding_revision_28", "pooled_image_equal_41"):
        subset = _strata_filter(stratum, task_rows, contract)
        for k in range(3, 13):
            current = [row for row in subset if int(row["k_from"]) == k]
            if not current:
                continue
            row: dict[str, Any] = {
                "analysis_stratum": stratum,
                "k_from": k,
                "k_to": k + 1,
                "task_count": len(current),
                "building_count": len({item["building_id"] for item in current}),
                "interpretation": "paired nested historical prefixes; one additional valid eligible annotation",
            }
            for offset, field in enumerate(
                (
                    "material_output_change_rate",
                    "delivery_adjusted_quality_gain",
                    "resolved_pair_quality_gain",
                    "mean_output_distance_when_both_resolved",
                )
            ):
                summary = _summary_row(
                    current,
                    field=field,
                    bootstrap_replicates=bootstrap_replicates,
                    seed_offset=7000 + 1000 * k + 31 * offset + len(stratum),
                )
                row[field] = summary.pop("estimate")
                row.update({f"{field}_{key}": value for key, value in summary.items()})
            output.append(row)
    return output


def summarize_reference_free(
    inputs: Mapping[str, Any],
    *,
    bootstrap_replicates: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    task_metadata = {
        row["base_task_id"]: {
            "stage": row["stage"],
            "building_id": row["base_task_id"].split("_", 1)[0],
        }
        for row in inputs["high_density"]
    }
    rare = read_csv(RAREFACTION)
    task_rows: list[dict[str, Any]] = []
    for row in rare:
        base = row["base_task_id"]
        if base not in task_metadata:
            continue
        task_rows.append(
            {
                "base_task_id": base,
                "building_id": task_metadata[base]["building_id"],
                "stage": row["stage"],
                "k_valid": int(row["k"]),
                "disagreement_recovery_abs_error_le_0_03": float(row["probability_abs_error_le_0_03"]),
                "disagreement_mean_absolute_error": float(row["mean_absolute_error"]),
                "full_cardinality_diverse": truth(row["full_cardinality_diverse"]),
                "cardinality_diversity_detection": float(row["probability_detect_cardinality_diversity"]),
                "source_replicates": int(row["replicates"]),
            }
        )
    structural_task_rows: list[dict[str, Any]] = []
    for row in inputs["high_density"]:
        total, valid = int(row["selected_support"]), int(row["strict_valid_support"])
        for k in (3, 5, 8, 10, 12, 15, 20):
            structural_task_rows.append(
                {
                    "base_task_id": row["base_task_id"],
                    "building_id": row["base_task_id"].split("_", 1)[0],
                    "stage": row["stage"],
                    "k_collected": k,
                    "probability_at_least_3_strict_valid": hypergeom_probability_at_least(total, valid, k, 3),
                    "total_canonical_support": total,
                    "strict_valid_support": valid,
                }
            )
    output: list[dict[str, Any]] = []
    for stage_label, stage in (("pooled_42", None), ("P1_stage_sensitivity", "P1"), ("C1_stage_sensitivity", "C1")):
        for k in sorted({int(row["k_valid"]) for row in task_rows}):
            current = [row for row in task_rows if int(row["k_valid"]) == k and (stage is None or row["stage"] == stage)]
            for metric in ("disagreement_recovery_abs_error_le_0_03", "disagreement_mean_absolute_error"):
                summary = _summary_row(
                    current,
                    field=metric,
                    bootstrap_replicates=bootstrap_replicates,
                    seed_offset=11000 + k + len(metric) + len(stage_label),
                )
                output.append(
                    {
                        "analysis_stratum": stage_label,
                        "metric": metric,
                        "k_type": "k_valid",
                        "k": k,
                        **summary,
                        "task_count": len(current),
                        "building_count": len({row["building_id"] for row in current}),
                        "interpretation": "finite historical strict-valid roster recovery; not external quality",
                    }
                )
            diverse = [row for row in current if row["full_cardinality_diverse"]]
            summary = _summary_row(
                diverse,
                field="cardinality_diversity_detection",
                bootstrap_replicates=bootstrap_replicates,
                seed_offset=12000 + k + len(stage_label),
            )
            output.append(
                {
                    "analysis_stratum": stage_label,
                    "metric": "cardinality_diversity_detection",
                    "k_type": "k_valid",
                    "k": k,
                    **summary,
                    "task_count": len(diverse),
                    "building_count": len({row["building_id"] for row in diverse}),
                    "interpretation": "probability of observing at least two historical vertical-boundary counts",
                }
            )
        for k in (3, 5, 8, 10, 12, 15, 20):
            current = [row for row in structural_task_rows if row["k_collected"] == k and (stage is None or row["stage"] == stage)]
            summary = _summary_row(
                current,
                field="probability_at_least_3_strict_valid",
                bootstrap_replicates=bootstrap_replicates,
                seed_offset=13000 + k + len(stage_label),
            )
            output.append(
                {
                    "analysis_stratum": stage_label,
                    "metric": "probability_at_least_3_strict_valid",
                    "k_type": "k_collected",
                    "k": k,
                    **summary,
                    "task_count": len(current),
                    "building_count": len({row["building_id"] for row in current}),
                    "interpretation": "exact hypergeometric probability from all 1055 canonical submissions",
                }
            )
    return output, structural_task_rows


def build_disagreement_distribution(
    inputs: Mapping[str, Any], *, bootstrap_replicates: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Task-equal distribution of full-roster disagreement and recovery heterogeneity."""
    high = {row["base_task_id"]: row for row in inputs["high_density"]}
    rare_by_task_k = {
        (row["base_task_id"], int(row["k"])): row
        for row in read_csv(RAREFACTION)
        if row["base_task_id"] in high
    }
    assert len({task for task, _ in rare_by_task_k}) == 42
    task_rows: list[dict[str, Any]] = []
    for task, row in sorted(high.items()):
        k12, k15 = rare_by_task_k[task, 12], rare_by_task_k[task, 15]
        selected, valid = int(row["selected_support"]), int(row["strict_valid_support"])
        task_rows.append(
            {
                "base_task_id": task,
                "building_id": task.split("_", 1)[0],
                "stage": row["stage"],
                "full_mask_distance": float(k12["full_mask_distance"]),
                "boundary_distance_mean": float(row["boundary_distance_mean"]),
                "boundary_distance_q90": float(row["boundary_distance_q90"]),
                "wall_distance_mean": float(row["wall_distance_mean"]),
                "wall_distance_q90": float(row["wall_distance_q90"]),
                "vertical_boundary_count_disagreement": float(
                    row["vertical_boundary_count_disagreement"]
                ),
                "invalid_submission_rate": (selected - valid) / selected,
                "selected_support": selected,
                "strict_valid_support": valid,
                "full_cardinality_diverse": truth(k12["full_cardinality_diverse"]),
                "recovery_rate_k12": float(k12["probability_abs_error_le_0_03"]),
                "recovery_rate_k15": float(k15["probability_abs_error_le_0_03"]),
                "recovery_gain_k12_to_k15": float(k15["probability_abs_error_le_0_03"])
                - float(k12["probability_abs_error_le_0_03"]),
                "recovery_mae_k12": float(k12["mean_absolute_error"]),
                "recovery_mae_k15": float(k15["mean_absolute_error"]),
                "recovery_mae_reduction_k12_to_k15": float(k12["mean_absolute_error"])
                - float(k15["mean_absolute_error"]),
                "cardinality_detection_k12": float(
                    k12["probability_detect_cardinality_diversity"]
                ),
                "cardinality_detection_k15": float(
                    k15["probability_detect_cardinality_diversity"]
                ),
                "cardinality_detection_gain_k12_to_k15": float(
                    k15["probability_detect_cardinality_diversity"]
                )
                - float(k12["probability_detect_cardinality_diversity"]),
                "rarefaction_replicates": int(k12["replicates"]),
            }
        )
    for rank, row in enumerate(
        sorted(task_rows, key=lambda item: (item["full_mask_distance"], item["base_task_id"])),
        start=1,
    ):
        row["mask_disagreement_rank"] = rank

    metrics = (
        "full_mask_distance",
        "boundary_distance_mean",
        "boundary_distance_q90",
        "wall_distance_mean",
        "wall_distance_q90",
        "vertical_boundary_count_disagreement",
        "invalid_submission_rate",
        "recovery_rate_k12",
        "recovery_rate_k15",
        "recovery_gain_k12_to_k15",
        "recovery_mae_k12",
        "recovery_mae_k15",
        "recovery_mae_reduction_k12_to_k15",
    )
    summary_rows: list[dict[str, Any]] = []
    for label, stage in (("pooled_42", None), ("P1_stage_sensitivity", "P1"), ("C1_stage_sensitivity", "C1")):
        current = [row for row in task_rows if stage is None or row["stage"] == stage]
        for offset, metric in enumerate(metrics):
            values = [float(row[metric]) for row in current if number(row.get(metric)) is not None]
            lower, upper = building_cluster_bootstrap_ci(
                current,
                value_field=metric,
                replicates=bootstrap_replicates,
                seed=SEED + 21000 + offset + len(label),
            )
            loo_lower, loo_upper = leave_one_building_out_range(current, value_field=metric)
            summary_rows.append(
                {
                    "analysis_stratum": label,
                    "metric": metric,
                    "task_count": len(values),
                    "building_count": len({row["building_id"] for row in current}),
                    "mean": mean(values),
                    "sd_across_tasks": float(np.std(values, ddof=1)) if len(values) > 1 else 0.0,
                    "minimum": min(values),
                    "q10": float(np.quantile(values, 0.10)),
                    "q25": float(np.quantile(values, 0.25)),
                    "median": median(values),
                    "q75": float(np.quantile(values, 0.75)),
                    "q90": float(np.quantile(values, 0.90)),
                    "maximum": max(values),
                    "mean_ci95_lower_building_bootstrap": lower,
                    "mean_ci95_upper_building_bootstrap": upper,
                    "mean_leave_one_building_out_min": loo_lower,
                    "mean_leave_one_building_out_max": loo_upper,
                    "interpretation": "task-equal distribution; channels are not merged",
                }
            )

    ecdf_rows: list[dict[str, Any]] = []
    for metric in (
        "full_mask_distance",
        "boundary_distance_mean",
        "wall_distance_mean",
        "vertical_boundary_count_disagreement",
        "invalid_submission_rate",
    ):
        values = sorted(float(row[metric]) for row in task_rows)
        for threshold in sorted(set(values)):
            ecdf_rows.append(
                {
                    "analysis_stratum": "pooled_42",
                    "metric": metric,
                    "threshold": threshold,
                    "task_equal_ecdf": sum(value <= threshold for value in values) / len(values),
                    "task_count": len(values),
                    "interpretation": "ECDF of task-level disagreement summaries; not a pair-pooled histogram",
                }
            )

    association_rows: list[dict[str, Any]] = []
    outcomes = (
        "recovery_rate_k12",
        "recovery_rate_k15",
        "recovery_gain_k12_to_k15",
        "recovery_mae_k12",
        "recovery_mae_k15",
        "recovery_mae_reduction_k12_to_k15",
    )
    for offset, outcome in enumerate(outcomes):
        rho, lower, upper = deterministic_building_bootstrap_spearman(
            task_rows, "full_mask_distance", outcome, 300 + offset
        )
        association_rows.append(
            {
                "analysis_stratum": "pooled_42",
                "predictor": "full_mask_distance",
                "outcome": outcome,
                "spearman_rho": rho,
                "ci95_lower_building_bootstrap": lower,
                "ci95_upper_building_bootstrap": upper,
                "task_count": 42,
                "building_count": 12,
                "bootstrap_replicates": 4000,
                "interpretation": (
                    "post-hoc descriptive association; predictor and outcome are derived from the same finite roster"
                ),
            }
        )
    return task_rows, summary_rows, ecdf_rows, association_rows


def _cluster_raw_records(
    task_id: str,
    records: Sequence[Any],
    pair_lookup: Mapping[tuple[str, str], Mapping[str, Any]],
    *,
    threshold: float = 0.95,
) -> dict[str, Any]:
    converted: list[dict[str, Any]] = []
    id_by_geometry: dict[int, str] = {}
    for item in records:
        id_by_geometry[id(item.strict)] = item.canonical_id
        converted.append(
            {
                "canonical_annotation_id": item.canonical_id,
                "worker_id": item.raw.worker_id,
                "geometry": item.strict,
            }
        )

    def lookup(left: Mapping[str, Any], right: Mapping[str, Any]) -> Mapping[str, Any]:
        key = tuple(sorted((id_by_geometry[id(left)], id_by_geometry[id(right)])))
        if key not in pair_lookup:
            raise AssertionError(f"raw pairwise lookup missing: {task_id} {key}")
        return pair_lookup[key]

    return cluster_geometry_records(
        converted,
        min_q_boundary=threshold,
        min_q_wallwall=threshold,
        base_task_id=task_id,
        condition="manual",
        minimum_valid_k=3,
        pairwise_fn=lookup,
    )


def _load_full_roster_geometry() -> tuple[dict[str, list[Any]], dict[str, dict[tuple[str, str], dict[str, Any]]]]:
    canonical, _ = canonicalise_raw_rq1(load_raw_rq1())
    groups = task_groups_raw_rq1(canonical)
    pools: dict[str, list[Any]] = {}
    lookups: dict[str, dict[tuple[str, str], dict[str, Any]]] = {}
    for key, records in sorted(groups.items()):
        stage, condition, dataset_group, base = key
        selected = (
            stage == "P1" and condition == "manual" and dataset_group == "PreScreen_manual"
        ) or (
            stage == "C1" and condition == "manual" and dataset_group == "C1_anchor_all"
        )
        if not selected:
            continue
        _, lookup = pairwise_task_summary_raw_rq1(key, records)
        task_id = f"{stage}|{dataset_group}|{base}"
        pools[task_id] = [row for row in records if row.strict.get("valid")]
        lookups[task_id] = lookup
    frozen = {row["high_density_task_id"]: row for row in read_csv(HIGH_DENSITY)}
    assert len(pools) == len(lookups) == len(frozen) == 42
    assert sum(map(len, pools.values())) == 1013
    assert all(len(rows) >= max(MINORITY_K_VALUES) for rows in pools.values())
    assert {
        task: len(rows) for task, rows in pools.items()
    } == {task: int(row["strict_valid_support"]) for task, row in frozen.items()}
    return pools, lookups


def build_minority_mode_replay(
    *,
    replicates: int,
    bootstrap_replicates: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Separate exact sampling visibility from recovery of the same frozen geometry mode."""
    pools, lookups = _load_full_roster_geometry()
    frozen_threshold_rows = read_csv(FULL_CLUSTER_SENSITIVITY)
    frozen_q95 = {
        row["task_id"]: row
        for row in frozen_threshold_rows
        if math.isclose(float(row["threshold"]), 0.95)
    }
    full_results: dict[str, dict[str, Any]] = {}
    full_task_rows: list[dict[str, Any]] = []
    for task_id, records in sorted(pools.items()):
        result = _cluster_raw_records(task_id, records, lookups[task_id])
        frozen = frozen_q95[task_id]
        assert result["task_crowd_structure_status"] == frozen["structure_status"]
        assert int(result["valid_k"]) == int(frozen["valid_k"])
        assert int(result["largest_cluster_support"]) == int(frozen["largest_support"])
        assert int(result["second_cluster_support"]) == int(frozen["second_support"])
        memberships = json.loads(result["cluster_membership_json"])
        threshold_rows = [row for row in frozen_threshold_rows if row["task_id"] == task_id]
        statuses = [row["structure_status"] for row in threshold_rows]
        stage, _, base = task_id.split("|", 2)
        full_results[task_id] = result
        top_support_tie = bool(
            len(memberships) > 1 and len(memberships[0]) == len(memberships[1])
        )
        second_rank_support_tie = bool(
            len(memberships) > 2 and len(memberships[1]) == len(memberships[2])
        )
        full_task_rows.append(
            {
                "task_id": task_id,
                "base_task_id": base,
                "building_id": base.split("_", 1)[0],
                "stage": stage,
                "full_valid_support": len(records),
                "threshold": 0.95,
                "partition_status": result["partition_status"],
                "structure_status": result["task_crowd_structure_status"],
                "cluster_count": result["cluster_count"],
                "largest_cluster_support": result["largest_cluster_support"],
                "second_cluster_support": result["second_cluster_support"],
                "second_cluster_share": result["second_cluster_share"],
                "top_support_tie": top_support_tie,
                "second_rank_support_tie": second_rank_support_tie,
                "second_rank_unique": not (top_support_tie or second_rank_support_tie),
                "supported_multimodal_at_threshold_count_of_5": sum(
                    status == "supported_multimodal" for status in statuses
                ),
                "same_status_at_all_5_thresholds": len(set(statuses)) == 1,
                "cluster_membership_json": result["cluster_membership_json"],
                "second_ranked_mode_member_ids_json": (
                    json.dumps(memberships[1], ensure_ascii=False, sort_keys=True)
                    if len(memberships) > 1
                    else "[]"
                ),
                "interpretation": "second-ranked mode includes deterministic ties; it is not external ground truth",
            }
        )
    assert Counter(row["structure_status"] for row in full_task_rows) == Counter(
        {
            "supported_multimodal": 21,
            "dominant_with_dissent": 14,
            "not_evaluable": 5,
            "unimodal": 2,
        }
    )

    threshold_summary: list[dict[str, Any]] = []
    for label, stage in (("pooled_42", None), ("P1_stage_sensitivity", "P1"), ("C1_stage_sensitivity", "C1")):
        for threshold in CLUSTER_THRESHOLDS:
            current = [
                row
                for row in frozen_threshold_rows
                if math.isclose(float(row["threshold"]), threshold)
                and (stage is None or row["task_id"].startswith(stage + "|"))
            ]
            counts = Counter(row["structure_status"] for row in current)
            threshold_summary.append(
                {
                    "analysis_stratum": label,
                    "threshold": threshold,
                    "task_count": len(current),
                    "unimodal_count": counts["unimodal"],
                    "dominant_with_dissent_count": counts["dominant_with_dissent"],
                    "supported_multimodal_count": counts["supported_multimodal"],
                    "not_evaluable_count": counts["not_evaluable"],
                    "supported_multimodal_rate": counts["supported_multimodal"] / len(current),
                    "not_evaluable_rate": counts["not_evaluable"] / len(current),
                    "interpretation": "threshold sensitivity only; 0.95 remains the frozen primary threshold",
                }
            )

    accumulators: dict[tuple[str, int], Counter[str]] = defaultdict(Counter)
    for task_id, records in sorted(pools.items()):
        full = full_results[task_id]
        full_memberships = json.loads(full["cluster_membership_json"])
        full_multimodal = full["task_crowd_structure_status"] == "supported_multimodal"
        full_second = set(full_memberships[1]) if full_multimodal else set()
        for replicate in range(replicates):
            order = sorted(
                records,
                key=lambda item: (
                    hashlib.sha256(
                        f"{SEED + 1}|{task_id}|{replicate}|{item.canonical_id}".encode("utf-8")
                    ).hexdigest(),
                    item.canonical_id,
                ),
            )
            for k in MINORITY_K_VALUES:
                sample = order[:k]
                sample_ids = {item.canonical_id for item in sample}
                prefix = _cluster_raw_records(task_id, sample, lookups[task_id])
                prefix_memberships = json.loads(prefix["cluster_membership_json"])
                acc = accumulators[task_id, k]
                acc["trials"] += 1
                acc["generic_multimodality"] += int(
                    prefix["task_crowd_structure_status"] == "supported_multimodal"
                )
                acc["not_evaluable"] += int(prefix["partition_status"] != "unique")
                if not full_multimodal:
                    continue
                support_visible = len(full_second & sample_ids) >= 2
                same_second = (
                    prefix["partition_status"] == "unique"
                    and _same_second_mode_recovered(
                        full_second, sample_ids, prefix_memberships
                    )
                )
                full_partition = (
                    support_visible
                    and prefix["partition_status"] == "unique"
                    and _partition_matches_full_restriction(
                        full_memberships, sample_ids, prefix_memberships
                    )
                )
                acc["any_member_visible"] += int(bool(full_second & sample_ids))
                acc["support_visible"] += int(support_visible)
                acc["same_second_mode_recovered"] += int(same_second)
                acc["full_partition_restriction_recovered"] += int(full_partition)
                acc["generic_but_not_same_second"] += int(
                    prefix["task_crowd_structure_status"] == "supported_multimodal"
                    and not same_second
                )

    full_by_task = {row["task_id"]: row for row in full_task_rows}
    task_k_rows: list[dict[str, Any]] = []
    for (task_id, k), acc in sorted(accumulators.items()):
        full = full_by_task[task_id]
        trials = int(acc["trials"])
        full_multimodal = full["structure_status"] == "supported_multimodal"
        support_visible = int(acc["support_visible"])
        total, second = int(full["full_valid_support"]), int(full["second_cluster_support"])
        task_k_rows.append(
            {
                "task_id": task_id,
                "base_task_id": full["base_task_id"],
                "building_id": full["building_id"],
                "stage": full["stage"],
                "k": k,
                "replicates": trials,
                "full_structure_status": full["structure_status"],
                "full_valid_support": total,
                "full_second_cluster_support": second,
                "full_second_cluster_share": full["second_cluster_share"],
                "full_top_support_tie": full["top_support_tie"],
                "full_second_rank_support_tie": full["second_rank_support_tie"],
                "full_second_rank_unique": full["second_rank_unique"],
                "exact_any_member_visible_probability": (
                    hypergeom_probability_at_least(total, second, k, 1)
                    if full_multimodal
                    else None
                ),
                "exact_support_visible_probability": (
                    hypergeom_probability_at_least(total, second, k, 2)
                    if full_multimodal
                    else None
                ),
                "mc_support_visible_rate": (
                    support_visible / trials if full_multimodal else None
                ),
                "same_second_mode_recovery_rate": (
                    acc["same_second_mode_recovered"] / trials if full_multimodal else None
                ),
                "same_second_mode_recovery_given_support_visible": (
                    acc["same_second_mode_recovered"] / support_visible
                    if full_multimodal and support_visible
                    else None
                ),
                "full_partition_restriction_recovery_rate": (
                    acc["full_partition_restriction_recovered"] / trials
                    if full_multimodal
                    else None
                ),
                "full_partition_restriction_recovery_given_support_visible": (
                    acc["full_partition_restriction_recovered"] / support_visible
                    if full_multimodal and support_visible
                    else None
                ),
                "generic_multimodality_status_rate": acc["generic_multimodality"] / trials,
                "generic_but_not_same_second_rate": (
                    acc["generic_but_not_same_second"] / trials if full_multimodal else None
                ),
                "generic_false_positive_rate_full_evaluable_nonmultimodal": (
                    acc["generic_multimodality"] / trials
                    if full["structure_status"] in RESOLVED_STATUSES
                    else None
                ),
                "prefix_not_evaluable_rate": acc["not_evaluable"] / trials,
                "interpretation": "finite-roster nested replay; full second-ranked mode is frozen at threshold 0.95",
            }
        )

    summary_rows: list[dict[str, Any]] = []
    multi_fields = (
        "exact_any_member_visible_probability",
        "exact_support_visible_probability",
        "mc_support_visible_rate",
        "same_second_mode_recovery_rate",
        "same_second_mode_recovery_given_support_visible",
        "full_partition_restriction_recovery_rate",
        "full_partition_restriction_recovery_given_support_visible",
        "generic_multimodality_status_rate",
        "generic_but_not_same_second_rate",
    )
    for label, stage in (("pooled_42", None), ("P1_stage_sensitivity", "P1"), ("C1_stage_sensitivity", "C1")):
        for k in MINORITY_K_VALUES:
            all_current = [
                row
                for row in task_k_rows
                if row["k"] == k and (stage is None or row["stage"] == stage)
            ]
            multi = [row for row in all_current if row["full_structure_status"] == "supported_multimodal"]
            unique_second_rank = [row for row in multi if row["full_second_rank_unique"] is True]
            nonmulti = [
                row
                for row in all_current
                if row["full_structure_status"] in RESOLVED_STATUSES
            ]
            summary: dict[str, Any] = {
                "analysis_stratum": label,
                "k": k,
                "replicates_per_task": replicates,
                "full_multimodal_task_count": len(multi),
                "full_multimodal_building_count": len({row["building_id"] for row in multi}),
                "unique_second_rank_sensitivity_task_count": len(unique_second_rank),
                "unique_second_rank_sensitivity_building_count": len(
                    {row["building_id"] for row in unique_second_rank}
                ),
                "full_evaluable_nonmultimodal_task_count": len(nonmulti),
                "full_evaluable_nonmultimodal_building_count": len(
                    {row["building_id"] for row in nonmulti}
                ),
            }
            for offset, field in enumerate(multi_fields):
                item = _summary_row(
                    multi,
                    field=field,
                    bootstrap_replicates=bootstrap_replicates,
                    seed_offset=24000 + 100 * k + offset + len(label),
                )
                summary[field] = item["estimate"]
                summary[f"{field}_ci95_lower_building_bootstrap"] = item[
                    "ci95_lower_building_bootstrap"
                ]
                summary[f"{field}_ci95_upper_building_bootstrap"] = item[
                    "ci95_upper_building_bootstrap"
                ]
            for offset, field in enumerate(
                (
                    "exact_support_visible_probability",
                    "same_second_mode_recovery_rate",
                    "same_second_mode_recovery_given_support_visible",
                    "full_partition_restriction_recovery_rate",
                )
            ):
                item = _summary_row(
                    unique_second_rank,
                    field=field,
                    bootstrap_replicates=bootstrap_replicates,
                    seed_offset=24500 + 100 * k + offset + len(label),
                )
                prefix = f"{field}_unique_second_rank_sensitivity"
                summary[prefix] = item["estimate"]
                summary[f"{prefix}_ci95_lower_building_bootstrap"] = item[
                    "ci95_lower_building_bootstrap"
                ]
                summary[f"{prefix}_ci95_upper_building_bootstrap"] = item[
                    "ci95_upper_building_bootstrap"
                ]
            fp = _summary_row(
                nonmulti,
                field="generic_false_positive_rate_full_evaluable_nonmultimodal",
                bootstrap_replicates=bootstrap_replicates,
                seed_offset=25000 + k + len(label),
            )
            summary["generic_false_positive_rate_full_evaluable_nonmultimodal"] = fp["estimate"]
            summary[
                "generic_false_positive_rate_full_evaluable_nonmultimodal_ci95_lower_building_bootstrap"
            ] = fp["ci95_lower_building_bootstrap"]
            summary[
                "generic_false_positive_rate_full_evaluable_nonmultimodal_ci95_upper_building_bootstrap"
            ] = fp["ci95_upper_building_bootstrap"]
            all_not_eval = _summary_row(
                all_current,
                field="prefix_not_evaluable_rate",
                bootstrap_replicates=bootstrap_replicates,
                seed_offset=26000 + k + len(label),
            )
            summary["prefix_not_evaluable_rate_all_tasks"] = all_not_eval["estimate"]
            summary["interpretation"] = (
                "generic status is not same-mode recovery; stage rows are sensitivity only"
            )
            summary_rows.append(summary)

    pooled_multi = [
        row
        for row in task_k_rows
        if row["full_structure_status"] == "supported_multimodal"
    ]
    mc_exact_gap = max(
        abs(float(row["mc_support_visible_rate"]) - float(row["exact_support_visible_probability"]))
        for row in pooled_multi
    )
    mc_exact_tolerance = math.sqrt(
        math.log(2 * len(pooled_multi) / 0.001) / (2 * replicates)
    )
    qa = {
        "full_task_count": len(full_task_rows),
        "full_supported_multimodal_task_count": sum(
            row["structure_status"] == "supported_multimodal" for row in full_task_rows
        ),
        "full_evaluable_nonmultimodal_task_count": sum(
            row["structure_status"] in RESOLVED_STATUSES for row in full_task_rows
        ),
        "full_not_evaluable_task_count": sum(
            row["structure_status"] == "not_evaluable" for row in full_task_rows
        ),
        "second_rank_tie_sensitive_task_count": sum(
            row["structure_status"] == "supported_multimodal"
            and not row["second_rank_unique"]
            for row in full_task_rows
        ),
        "unique_second_rank_multimodal_task_count": sum(
            row["structure_status"] == "supported_multimodal"
            and row["second_rank_unique"]
            for row in full_task_rows
        ),
        "task_k_rows": len(task_k_rows),
        "maximum_task_level_mc_minus_exact_support_visibility": mc_exact_gap,
        "simultaneous_hoeffding_tolerance_alpha_0_001": mc_exact_tolerance,
        "generic_multimodality_is_same_mode_claim": False,
    }
    assert len(task_k_rows) == 42 * len(MINORITY_K_VALUES)
    assert qa["full_supported_multimodal_task_count"] == 21
    assert qa["full_evaluable_nonmultimodal_task_count"] == 16
    assert qa["full_not_evaluable_task_count"] == 5
    assert qa["second_rank_tie_sensitive_task_count"] == 3
    assert qa["unique_second_rank_multimodal_task_count"] == 18
    assert mc_exact_gap <= mc_exact_tolerance
    return full_task_rows, task_k_rows, summary_rows, threshold_summary, qa


def build_plateau_check_summary(
    distribution_task_rows: Sequence[Mapping[str, Any]],
    transition_task_rows: Sequence[Mapping[str, Any]],
    *,
    bootstrap_replicates: int,
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    def add(
        rows: Sequence[Mapping[str, Any]],
        *,
        metric: str,
        metric_zh: str,
        field: str,
        k_from: int,
        k_to: int,
        note: str,
    ) -> None:
        usable = [row for row in rows if number(row.get(field)) is not None]
        values = [float(row[field]) for row in usable]
        lower, upper = building_cluster_bootstrap_ci(
            usable,
            value_field=field,
            replicates=bootstrap_replicates,
            seed=SEED + 28000 + len(checks),
        )
        loo_lower, loo_upper = leave_one_building_out_range(usable, value_field=field)
        checks.append(
            {
                "metric": metric,
                "metric_zh": metric_zh,
                "k_from": k_from,
                "k_to": k_to,
                "estimate": mean(values),
                "ci95_lower_building_bootstrap": lower,
                "ci95_upper_building_bootstrap": upper,
                "leave_one_building_out_min": loo_lower,
                "leave_one_building_out_max": loo_upper,
                "task_count": len(usable),
                "building_count": len({row["building_id"] for row in usable}),
                "positive_task_count": sum(value > 0 for value in values),
                "zero_task_count": sum(math.isclose(value, 0.0, abs_tol=1e-15) for value in values),
                "negative_task_count": sum(value < 0 for value in values),
                "ci_excludes_zero": bool(lower is not None and upper is not None and (lower > 0 or upper < 0)),
                "equivalence_decision": "not_tested_SESOI_not_frozen",
                "interpretation": note,
            }
        )

    add(
        distribution_task_rows,
        metric="reference_free_recovery_gain_12_to_15",
        metric_zh="无reference分歧恢复率增益",
        field="recovery_gain_k12_to_k15",
        k_from=12,
        k_to=15,
        note="positive means better recovery of the finite full-roster disagreement",
    )
    add(
        distribution_task_rows,
        metric="reference_free_mae_reduction_12_to_15",
        metric_zh="无reference恢复MAE下降",
        field="recovery_mae_reduction_k12_to_k15",
        k_from=12,
        k_to=15,
        note="positive means smaller recovery error",
    )
    add(
        [row for row in distribution_task_rows if row["full_cardinality_diverse"]],
        metric="cardinality_diversity_detection_gain_12_to_15",
        metric_zh="角点数多样性检出率增益",
        field="cardinality_detection_gain_k12_to_k15",
        k_from=12,
        k_to=15,
        note="conditional on the full roster containing more than one boundary count",
    )
    transition_12_13 = [
        row
        for row in transition_task_rows
        if int(row["k_from"]) == 12 and int(row["k_to"]) == 13
    ]
    add(
        transition_12_13,
        metric="material_output_change_rate_12_to_13",
        metric_zh="新增第13条后输出发生实质变化的概率",
        field="material_output_change_rate",
        k_from=12,
        k_to=13,
        note="not a quality gain; lower means more stable output",
    )
    add(
        transition_12_13,
        metric="delivery_adjusted_quality_gain_12_to_13",
        metric_zh="交付规则敏感质量变化",
        field="delivery_adjusted_quality_gain",
        k_from=12,
        k_to=13,
        note="non-delivery is encoded as zero and is not geometry quality",
    )
    add(
        transition_12_13,
        metric="resolved_pair_quality_gain_12_to_13",
        metric_zh="两端均可交付时的几何质量变化",
        field="resolved_pair_quality_gain",
        k_from=12,
        k_to=13,
        note="conditional on both prefixes resolving; selection-limited",
    )
    checks.append(
        {
            "metric": "reference_relative_quality_12_to_15",
            "metric_zh": "reference相对质量12到15平台",
            "k_from": 12,
            "k_to": 15,
            "estimate": None,
            "task_count": 0,
            "building_count": 0,
            "equivalence_decision": "not_identifiable_common_quality_support_ends_at_k13",
            "interpretation": "cannot claim a 12-15 quality plateau from the current reference-ready common support",
        }
    )
    return checks


def summarize_individual_quality(
    annotation_rows: Sequence[Mapping[str, Any]],
    reference_contract: Sequence[Mapping[str, Any]],
    *,
    bootstrap_replicates: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    eligible = [row for row in annotation_rows if row["gt_primary_analysis_eligible"] is True and number(row["geometry_score"]) is not None]
    task_groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in eligible:
        task_groups[row["base_task_id"]].append(row)
    by_task: list[dict[str, Any]] = []
    for task, rows in sorted(task_groups.items()):
        values = np.asarray([float(row["geometry_score"]) for row in rows], dtype=float)
        by_task.append(
            {
                "base_task_id": task,
                "building_id": rows[0]["building_id"],
                "stage": rows[0]["stage"],
                "quality_eligible_k": len(values),
                "individual_quality_mean": float(np.mean(values)),
                "individual_quality_median": float(np.median(values)),
                "individual_quality_q25": float(np.quantile(values, 0.25)),
                "individual_quality_q75": float(np.quantile(values, 0.75)),
                "individual_quality_min": float(np.min(values)),
                "individual_quality_max": float(np.max(values)),
            }
        )
    contract = {row["base_task_id"]: row for row in reference_contract}
    summary: list[dict[str, Any]] = []
    for stratum in ("C1_primary_12", "P1_sensitivity_29", "P1_excluding_revision_28", "pooled_image_equal_41"):
        current = _strata_filter(stratum, by_task, contract)
        row: dict[str, Any] = {
            "analysis_stratum": stratum,
            "task_count": len(current),
            "building_count": len({item["building_id"] for item in current}),
            "quality_eligible_annotation_count": sum(int(item["quality_eligible_k"]) for item in current),
            "aggregation": "task-equal summary of within-task individual-quality distributions",
        }
        for offset, field in enumerate(("individual_quality_mean", "individual_quality_median", "individual_quality_q25", "individual_quality_q75")):
            item = _summary_row(
                current,
                field=field,
                bootstrap_replicates=bootstrap_replicates,
                seed_offset=15000 + offset + len(stratum),
            )
            row[field] = item.pop("estimate")
            row.update({f"{field}_{key}": value for key, value in item.items()})
        summary.append(row)
    return by_task, summary


def language_sensitivity(
    annotation_rows: Sequence[Mapping[str, Any]], *, bootstrap_replicates: int
) -> list[dict[str, Any]]:
    eligible = [row for row in annotation_rows if row["gt_primary_analysis_eligible"] is True and number(row["geometry_score"]) is not None]
    grouped: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    for row in eligible:
        grouped[row["stage"], row["base_task_id"], row["language"]].append(float(row["geometry_score"]))
    task_diffs: list[dict[str, Any]] = []
    for (stage, task, language), values in sorted(grouped.items()):
        if language != "English":
            continue
        chinese = grouped.get((stage, task, "Chinese"), [])
        if not chinese:
            continue
        task_diffs.append(
            {
                "stage": stage,
                "base_task_id": task,
                "building_id": task.split("_", 1)[0],
                "english_n": len(values),
                "chinese_n": len(chinese),
                "english_task_mean_quality": mean(values),
                "chinese_task_mean_quality": mean(chinese),
                "english_minus_chinese_task_mean_quality": mean(values) - mean(chinese),
            }
        )
    output: list[dict[str, Any]] = []
    for stage in ("P1", "C1", "pooled"):
        rows = task_diffs if stage == "pooled" else [row for row in task_diffs if row["stage"] == stage]
        lower, upper = building_cluster_bootstrap_ci(
            rows,
            value_field="english_minus_chinese_task_mean_quality",
            replicates=bootstrap_replicates,
            seed=SEED + 17000 + len(stage),
        )
        output.append(
            {
                "analysis_stratum": stage,
                "task_count": len(rows),
                "building_count": len({row["building_id"] for row in rows}),
                "english_minus_chinese_task_mean_quality": mean(
                    [row["english_minus_chinese_task_mean_quality"] for row in rows]
                ),
                "ci95_lower_building_bootstrap": lower,
                "ci95_upper_building_bootstrap": upper,
                "interpretation": "project/cohort sensitivity only; not a causal language effect",
            }
        )
    return output


def build_readme(
    output_dir: Path,
    *,
    replicates: int,
    minority_replicates: int,
    bootstrap_replicates: int,
    quality_summary: Sequence[Mapping[str, Any]],
) -> None:
    pooled_k13 = next(
        row
        for row in quality_summary
        if row["analysis_stratum"] == "pooled_image_equal_41" and int(row["k_valid"]) == 13
    )
    content = f"""# 历史标注不确定性复算（讨论用）

## 口径

- 中英文项目在同一图像内合并；语言仅保留为项目/人群敏感性字段。
- 历史高密度集合为 42 图、1,055 条规范标注，42 图均来自 HoHoNet test split。
- 无 reference 曲线以 42 图为主；P1/C1 只作阶段敏感性。
- reference-relative 聚合质量曲线固定为 C1 12 图主分析、P1 29 图敏感性、P1 排除 task 564 后 28 图敏感性，以及显式图像等权的 41/40 图合并敏感性；配对边际变化曲线报告前述前三层与 41 图合并层。
- 质量聚合器不读取 reference：0.95 complete-link、唯一 partition、最大簇 medoid；supported multimodal 与 not-evaluable 均不强制交付。
- 所有 k 前缀来自同一确定性随机排列，因而 k→k+1 为配对嵌套比较。
- 置信区间按 building 聚类 bootstrap；曲线推断仍限于历史 worker roster。

## 当前可直接读出的事实

- reference-ready：41/42；C1=12，P1=29；P1 task 696 因 oos_insufficient 排除。
- 共同 reference-quality 风险集最大为 k=13；不能把图上 k=20 点写成 41 图共同实测。
- pooled 41 图在 k=13 的 GT-blind 自主交付率为 {pooled_k13['resolved_rate']:.3f}，resolved-only quality 为 {pooled_k13['resolved_only_quality']:.3f}，delivery-adjusted sensitivity 为 {pooled_k13['delivery_adjusted_quality']:.3f}。
- `delivery_adjusted_quality` 将不交付编码为 0，只是明确标注的交付敏感性，不代表真实几何 IoU 为 0。
- oracle best-of-k 未计算，也不得作为主质量曲线。
- 没有把“有害错误率”写入结果，因为实际 harm 与严重错误阈值尚未冻结。
- 成本只允许解释为“每新增一条有效 eligible 标注的边际变化”；不声称 production cost 或节省。
- `generic_multimodality_status_reproduction_rate` 只表示再次出现某种多模态；它不再被命名为“少数模式捕获”。
- 少数结构另用全 strict-valid roster 在 0.95 阈值冻结的确定性第二排序模式计算：精确抽样可见、同一模式纯恢复、完整分区限制恢复和条件恢复。3/21 个多模态任务存在第一/第二或第二/第三支持数并列，另报排除这些排序并列任务的敏感性；该模式不是外部真值。
- 42 图的整体分歧分布按任务等权汇总；mask、boundary、wall、角点数分歧和无效提交通道分别报告，不合成单一分数。
- 当前 reference 相对共同质量支持只到 k=13；没有预设 SESOI，因此不能从本包确认“12–15 人质量平台”。

## 复算参数

- prefix replay：每图 {replicates} 次。
- 同一少数结构 replay：每图 {minority_replicates} 次，k=5/8/12/16/20。
- building bootstrap：{bootstrap_replicates} 次。
- k_valid：3–13；所有 41 张 reference-ready 图共同支持。
- 固定 seed：{SEED}。

CSV 均以 UTF-8 BOM 写出，可直接用中文 Excel 打开。完整简体中文汇总见同目录工作簿。
"""
    (output_dir / "README_ZH.md").write_text(content, encoding="utf-8-sig")


def run(
    output_dir: Path = DEFAULT_OUT,
    *,
    replicates: int = 200,
    minority_replicates: int = 500,
    bootstrap_replicates: int = 4000,
) -> dict[str, Any]:
    if replicates <= 0 or minority_replicates <= 0 or bootstrap_replicates <= 0:
        raise ValueError("replicate counts must be positive")
    output_dir.mkdir(parents=True, exist_ok=True)
    inputs = load_inputs()
    reference_contract = build_reference_contract(inputs)
    annotation_rows = build_annotation_eligibility(inputs, reference_contract)
    pools, pair_maps = build_quality_candidates(inputs)
    task_k_rows, transition_task_rows = replay_quality_curves(pools, pair_maps, replicates=replicates)
    quality_summary = summarize_quality_curves(
        task_k_rows, reference_contract, bootstrap_replicates=bootstrap_replicates
    )
    transition_summary = summarize_transitions(
        transition_task_rows, reference_contract, bootstrap_replicates=bootstrap_replicates
    )
    reference_free, structural_task_rows = summarize_reference_free(
        inputs, bootstrap_replicates=bootstrap_replicates
    )
    (
        disagreement_task_rows,
        disagreement_summary,
        disagreement_ecdf,
        disagreement_associations,
    ) = build_disagreement_distribution(inputs, bootstrap_replicates=bootstrap_replicates)
    (
        full_structure_rows,
        minority_task_k_rows,
        minority_summary,
        threshold_sensitivity,
        minority_qa,
    ) = build_minority_mode_replay(
        replicates=minority_replicates,
        bootstrap_replicates=bootstrap_replicates,
    )
    plateau_checks = build_plateau_check_summary(
        disagreement_task_rows,
        transition_task_rows,
        bootstrap_replicates=bootstrap_replicates,
    )
    individual_by_task, individual_summary = summarize_individual_quality(
        annotation_rows, reference_contract, bootstrap_replicates=bootstrap_replicates
    )
    language = language_sensitivity(annotation_rows, bootstrap_replicates=bootstrap_replicates)

    outputs = {
        "image_reference_contract.csv": reference_contract,
        "annotation_eligibility.csv": annotation_rows,
        "reference_free_curves.csv": reference_free,
        "structural_valid_support_by_task_k.csv": structural_task_rows,
        "disagreement_task_distribution.csv": disagreement_task_rows,
        "disagreement_distribution_summary.csv": disagreement_summary,
        "disagreement_task_ecdf.csv": disagreement_ecdf,
        "disagreement_recovery_associations.csv": disagreement_associations,
        "full_roster_structure_tasks.csv": full_structure_rows,
        "minority_mode_replay_task_k.csv": minority_task_k_rows,
        "minority_mode_replay_summary.csv": minority_summary,
        "structure_threshold_sensitivity.csv": threshold_sensitivity,
        "plateau_check_summary.csv": plateau_checks,
        "aggregate_quality_task_k.csv": task_k_rows,
        "aggregate_quality_curves.csv": quality_summary,
        "marginal_quality_gain_task_k.csv": transition_task_rows,
        "marginal_quality_gain.csv": transition_summary,
        "individual_quality_by_task.csv": individual_by_task,
        "individual_quality_summary.csv": individual_summary,
        "language_project_sensitivity.csv": language,
    }
    for name, rows in outputs.items():
        write_csv(output_dir / name, rows)

    qa = {
        "schema_version": "historical_uncertainty_recompute_v2",
        "status": "pass",
        "assertions": {
            "image_reference_contract_rows": len(reference_contract),
            "reference_ready_images": sum(bool(row["geometry_reference_ready"]) for row in reference_contract),
            "annotation_eligibility_rows": len(annotation_rows),
            "reference_quality_eligible_annotations": sum(row["gt_primary_analysis_eligible"] is True for row in annotation_rows),
            "quality_curve_tasks": len(pools),
            "minimum_common_quality_k": min(len(rows) for rows in pools.values()),
            "historical_split_counts": dict(Counter(row["official_split"] for row in reference_contract)),
            "language_primary_strata_created": False,
            "stage_retained_as_sensitivity": True,
            "oracle_best_of_k_computed": False,
            "harmful_error_rate_computed": False,
            "full_roster_disagreement_task_count": len(disagreement_task_rows),
            "minority_replay": minority_qa,
            "same_mode_recovery_distinguished_from_generic_multimodality": True,
            "formal_12_to_15_quality_plateau_claimed": False,
        },
        "scientific_boundaries": [
            "Finite historical roster; not a new-worker population guarantee.",
            "C1 reference is primary; P1 and pooled reference results are sensitivity only.",
            "P1 historical worker scope answer-set version is not machine materialized.",
            "P1 peer_analysis_eligible is not inferred from quality eligibility.",
            "Building-clustered intervals do not repair reference non-equivalence.",
            "Full-roster difficulty and recovery are derived from the same answers; their association is descriptive, not causal.",
            "The deterministic second-ranked cluster may be support-tied with the first or third cluster and is not external ground truth.",
        ],
    }
    write_json(output_dir / "QA_SUMMARY.json", qa)
    source_paths = [
        P1_IMPORT,
        P1_CLOSEOUT / "final_gold_records_v2_p1_closeout_corrected.jsonl",
        P1_CLOSEOUT / "prescreen_geometry_gold_alignment_audit.csv",
        P1_CLOSEOUT / "prescreen_canonical_annotations.csv",
        inputs["p1_evidence_path"],
        inputs["p1_scores_path"],
        C1_AUDIT / "c1_gt_quality_analysis.csv",
        C1_AUDIT / "c1_task_outcome_reference.csv",
        C1_AUDIT / "geometry_pairwise_similarity_C1.csv",
        RAREFACTION,
        HIGH_DENSITY,
        RAW_CANONICAL,
        FULL_CLUSTER_SENSITIVITY,
        METHOD_CONTRACT,
    ]
    manifest = {
        "schema_version": "historical_uncertainty_recompute_manifest_v2",
        "output_dir": display_path(output_dir),
        "seed": SEED,
        "prefix_replicates_per_task": replicates,
        "minority_replay_replicates_per_task": minority_replicates,
        "building_bootstrap_replicates": bootstrap_replicates,
        "k_values": list(K_VALUES),
        "language_policy": "pooled_primary; project-language sensitivity only",
        "stage_policy": "not a target effect; retained for reference/protocol sensitivity",
        "split_policy": "not stratified; all historical dense42 images are test",
        "source_files": [
            {"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(path)} for path in source_paths
        ],
        "outputs": list(outputs) + ["README_ZH.md", "QA_SUMMARY.json"],
    }
    write_json(output_dir / "ANALYSIS_MANIFEST.json", manifest)
    build_readme(
        output_dir,
        replicates=replicates,
        minority_replicates=minority_replicates,
        bootstrap_replicates=bootstrap_replicates,
        quality_summary=quality_summary,
    )
    return qa


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--replicates", type=int, default=200)
    parser.add_argument("--minority-replicates", type=int, default=500)
    parser.add_argument("--bootstrap-replicates", type=int, default=4000)
    args = parser.parse_args()
    print(
        json.dumps(
            run(
                args.output_dir,
                replicates=args.replicates,
                minority_replicates=args.minority_replicates,
                bootstrap_replicates=args.bootstrap_replicates,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
