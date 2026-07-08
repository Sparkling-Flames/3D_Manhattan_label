from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.thesis_main.analysis.c1_live_collection_monitor import read_csv, safe, truthy, write_csv, write_json

DEFAULT_OUTPUT_DIR = Path("analysis_results/calibration_c1_closeout")
DEFAULT_QUALITY = DEFAULT_OUTPUT_DIR / "c1_quality_annotations.csv"
DEFAULT_WORKER_STATE = DEFAULT_OUTPUT_DIR / "worker_state_snapshot_C1.csv"

PROFILE_VERSION = "worker_profile_sidecar_C1_v1"
USABLE_GEOMETRY_REFERENCE = {"expert_hard_single", "expert_hard_multi", "consensus_reference", "hard_single_gt", "hard_multi_gt"}
R_U_CALIB_GROUPS = {"Calibration_anchor", "Calibration_core", "Calibration_reserve"}
R_GEOMETRY_GROUPS = {"PreScreen_manual", "Calibration_anchor", "Calibration_core", "Calibration_reserve"}
T_U_GROUPS = {"PreScreen_semi", "Calibration_semi"}
VALID_SCOPE_RESPONSES = {"correct_in_scope", "correct_oos", "scope_false_positive", "scope_false_negative"}
UNDERCOVERAGE_RESPONSES = {"partial_undercoverage", "inner_space_only", "minimal_space_bias", "full_room_compliance_failure", "overextended_adjacent_when_in_scope"}
PROCESS_SUBFAMILIES = {
    "active_time_missing_or_ineligible",
    "duplicate_same_geometry",
    "revision_time_ambiguous",
    "schema_invalid",
    "assignment_mismatch",
    "outside_manifest_submission",
}
PREDICTIVE_CHECKS = [
    ("p1_r0_vs_c1_r_u_calib", "r0_prescreen", "r_u_calib"),
    ("p1_geometry_vs_c1_geometry", "p1_geometry_profile", "r_geometry_u"),
    ("p1_scope_vs_c1_scope", "p1_scope_profile", "r_scope_u"),
    ("p1_blind_trust_vs_calibration_semi", "p1_blind_trust_flag", "T_u"),
    ("p1_undercoverage_watch_vs_c1_undercoverage", "p1_undercoverage_watch", "U_u"),
    ("p1_process_warning_vs_c1_process_reliability", "p1_process_warning", "process_reliability"),
]
FAMILIES = [
    "geometry_quality_failure",
    "scope_oos_failure",
    "semi_correction_failure",
    "undercoverage_failure",
    "process_failure",
]

EVIDENCE_FIELDS = [
    "worker_id",
    "round_id",
    "task_id",
    "base_task_id",
    "dataset_group",
    "condition",
    "stage",
    "pool",
    "task_final_scope",
    "task_oos_subtype",
    "worker_scope_response",
    "geometry_reference_status",
    "geometry_valid",
    "process_invalid",
    "quality_metric_name",
    "quality_metric_value",
    "family",
    "subfamily",
    "response_type",
    "failure_observed",
    "included_in_r_u_calib",
    "included_in_r_geometry",
    "included_in_r_scope",
    "included_in_T_u",
    "included_in_U_u",
    "included_in_process_reliability",
    "exclusion_reason",
    "active_time_source",
    "primary_active_time_eligible",
    "assignment_expected",
    "canonical_annotation_id",
    "source_manifest_version",
    "profile_rule_version",
]

MAIN_FIELDS = [
    "worker_id",
    "round_id",
    "r_u_calib",
    "r_u_calib_lcb",
    "r_u_calib_ci_low",
    "r_u_calib_ci_high",
    "r_geometry_u",
    "r_scope_u",
    "T_u",
    "U_u",
    "process_reliability",
    "profile_confidence",
    "n_calib_support",
    "n_geometry_support",
    "n_scope_support",
    "n_semi_support",
    "n_undercoverage_support",
    "n_process_support",
    "calib_support_status",
    "geometry_support_status",
    "scope_support_status",
    "semi_support_status",
    "undercoverage_support_status",
    "process_support_status",
    "profile_version",
    "profile_freeze_status",
    "notes",
]

FAMILY_FIELDS = ["worker_id", "round_id", "family", "n_observed", "n_fail", "failure_rate", "support_status", "interpretation_allowed", "source_stages", "profile_version"]
SUBFAMILY_FIELDS = [
    "worker_id",
    "round_id",
    "family",
    "subfamily",
    "n_observed",
    "n_fail",
    "failure_rate",
    "task_count",
    "subfamily_global_worker_coverage",
    "support_status",
    "interpretation_allowed",
    "source_stages",
    "profile_version",
]
PREDICTIVE_FIELDS = ["worker_id", "check_name", "p1_metric_name", "p1_metric_value", "c1_metric_name", "c1_metric_value", "directionally_consistent", "support_status", "interpretation_allowed", "notes"]
P1_ALIASES = {
    "r0_prescreen": ["r0_prescreen", "r_u_0", "r_u0", "prescreen_r0"],
    "p1_geometry_profile": ["p1_geometry_profile", "geometry_profile", "r_geometry_u"],
    "p1_scope_profile": ["p1_scope_profile", "scope_profile", "r_scope_u"],
    "p1_blind_trust_flag": ["p1_blind_trust_flag", "blind_trust_flag", "blind_trust_pre_flag"],
    "p1_undercoverage_watch": ["p1_undercoverage_watch", "undercoverage_watch", "undercoverage_risk_level"],
    "p1_process_warning": ["p1_process_warning", "process_warning", "active_time_process_warning"],
}


def support_status(n: int) -> str:
    if n < 3:
        return "insufficient"
    if n < 5:
        return "weak"
    if n < 10:
        return "moderate"
    return "sufficient"


def interpretation_allowed(n: int) -> bool:
    return n >= 3


def rate(fail: int, observed: int) -> str:
    return "" if observed == 0 else f"{fail / observed:.6f}"


def score(fail: int, observed: int) -> str:
    return "" if observed == 0 else f"{1 - fail / observed:.6f}"


def norm_scope(row: dict[str, str]) -> str:
    raw = safe(row.get("task_final_scope") or row.get("final_scope") or row.get("scope")).lower()
    if raw in {"in_scope", "in-scope", "inscope"}:
        return "in_scope"
    if raw.startswith("oos"):
        return "oos"
    return "unknown"


def oos_subtype(row: dict[str, str]) -> str:
    explicit = safe(row.get("task_oos_subtype") or row.get("oos_subtype")).lower()
    if explicit:
        return explicit
    raw = safe(row.get("task_final_scope") or row.get("final_scope") or row.get("scope")).lower()
    if raw.startswith("oos"):
        return raw
    if norm_scope(row) == "oos":
        return "unknown"
    return "none"


def is_in_scope(row: dict[str, str]) -> bool:
    return norm_scope(row) == "in_scope"


def is_oos(row: dict[str, str]) -> bool:
    return norm_scope(row) == "oos"


def geometry_reference_status(row: dict[str, str]) -> str:
    return safe(row.get("geometry_reference_status") or row.get("gold_status") or "unavailable")


def geometry_valid(row: dict[str, str]) -> bool:
    if safe(row.get("geometry_valid")):
        return truthy(row.get("geometry_valid"))
    try:
        return int(float(safe(row.get("n_corners")) or 0)) >= 4 and bool(safe(row.get("geometry_hash")))
    except ValueError:
        return False


def condition(row: dict[str, str]) -> str:
    value = safe(row.get("condition")).lower()
    if value:
        return value
    group = safe(row.get("dataset_group")).lower()
    return "semi" if "semi" in group else "manual"


def stage(row: dict[str, str]) -> str:
    explicit = safe(row.get("stage") or row.get("round_id"))
    if explicit in {"P1", "C1", "C2", "C2b", "T1", "V1"}:
        return explicit
    group = safe(row.get("dataset_group"))
    if group.startswith("PreScreen_"):
        return "P1"
    if group == "C2b_diagnostic_extension":
        return "C2b"
    if group == "Calibration_reserve":
        return "C2"
    if group.startswith("Calibration_"):
        return "C1"
    return "C1"


def family_for(row: dict[str, str]) -> str:
    explicit = safe(row.get("family"))
    if explicit:
        return explicit
    sub = safe(row.get("subfamily")).lower()
    response = safe(row.get("response_type") or row.get("worker_scope_response")).lower()
    if "undercoverage" in sub or "inner_space" in sub or "minimal_space" in sub:
        return "undercoverage_failure"
    if "blind_trust" in sub or "correction" in sub or "not_fixed" in sub or condition(row) == "semi":
        return "semi_correction_failure"
    if response.startswith("scope_") or is_oos(row):
        return "scope_oos_failure"
    if process_fail(row):
        return "process_failure"
    return "geometry_quality_failure"


def subfamily_for(row: dict[str, str], family: str) -> str:
    explicit = safe(row.get("subfamily"))
    if explicit:
        return explicit
    if family == "scope_oos_failure":
        return safe(row.get("worker_scope_response")) or ("oos_case" if is_oos(row) else "scope_case")
    if family == "semi_correction_failure":
        text = safe(row.get("model_issue_primary") or row.get("model_issue"))
        return text if text and text != "acceptable" else "successful_correction"
    if family == "undercoverage_failure":
        return safe(row.get("coverage_response")) or "undercoverage_case"
    if family == "process_failure":
        return "process_integrity"
    return "normal_geometry_degraded" if geometry_valid(row) else "topology_or_pairing_failure"


def response_type(row: dict[str, str], family: str, subfamily: str) -> str:
    explicit = safe(row.get("response_type"))
    if explicit:
        return explicit
    if family == "scope_oos_failure":
        return safe(row.get("worker_scope_response")) or ("correct_oos" if is_oos(row) else "correct_in_scope")
    if family == "process_failure":
        return "process_failure" if process_fail(row) else "process_ok"
    if family == "undercoverage_failure":
        return "undercoverage_fail" if subfamily != "full_room_attempt" else "undercoverage_ok"
    if family == "semi_correction_failure":
        return "semi_fail" if subfamily not in {"successful_correction", "acceptable"} else "semi_ok"
    return "geometry_ok" if geometry_valid(row) else "geometry_fail"


def process_fail(row: dict[str, str]) -> bool:
    return (
        truthy(row.get("process_invalid"))
        or safe(row.get("subfamily")) in PROCESS_SUBFAMILIES
        or safe(row.get("response_type")) in PROCESS_SUBFAMILIES
        or truthy(row.get("outside_assignment_submission"))
        or truthy(row.get("duplicate_worker_task_submission"))
        or safe(row.get("active_time_source")) in {"missing", "mismatch"}
        or (safe(row.get("assigned_expected")) and not truthy(row.get("assigned_expected")))
    )


def is_fail(row: dict[str, str], family: str, response: str) -> bool:
    text = response.lower()
    if text.startswith("correct") or text.endswith("_ok"):
        return False
    if any(token in text for token in ("fail", "false", "invalid", "missing", "mismatch", "blind_trust", "not_fixed")):
        return True
    if family == "geometry_quality_failure":
        return not geometry_valid(row)
    if family == "process_failure":
        return process_fail(row)
    return False


def dimension_fail(evidence_row: dict[str, Any], field: str) -> bool:
    response = safe(evidence_row.get("response_type")).lower()
    if field == "included_in_r_u_calib":
        return "geometry_fail" in response or response in {"invalid", "geometry_invalid"}
    if field == "included_in_r_geometry":
        return "geometry_fail" in response or response in {"invalid", "geometry_invalid"}
    if field == "included_in_r_scope":
        scope_response = safe(evidence_row.get("worker_scope_response")).lower()
        return scope_response in {"scope_false_positive", "scope_false_negative", "unknown_or_missing"}
    if field == "included_in_T_u":
        return any(token in response for token in ("blind_trust", "failed_correction", "not_fixed", "semi_fail"))
    if field == "included_in_U_u":
        return evidence_row.get("family") == "undercoverage_failure" and safe(evidence_row.get("subfamily")) != "full_room_attempt"
    if field == "included_in_process_reliability":
        return truthy(evidence_row.get("_process_fail"))
    return truthy(evidence_row.get("_is_fail"))


def inclusion_flags(row: dict[str, str], family: str) -> dict[str, bool]:
    cond = condition(row)
    ref = geometry_reference_status(row)
    geom_ok = geometry_valid(row)
    invalid = process_fail(row)
    process_ok = not invalid
    group = safe(row.get("dataset_group"))
    row_stage = stage(row)
    manual = cond == "manual"
    usable_ref = ref in USABLE_GEOMETRY_REFERENCE
    response = safe(row.get("response_type"))
    worker_scope = safe(row.get("worker_scope_response"))
    return {
        "included_in_r_u_calib": row_stage in {"C1", "C2"} and group in R_U_CALIB_GROUPS and truthy(row.get("used_for_r_u")) and manual and is_in_scope(row) and usable_ref and geom_ok and process_ok,
        "included_in_r_geometry": group in R_GEOMETRY_GROUPS and manual and is_in_scope(row) and usable_ref and geom_ok and process_ok,
        "included_in_r_scope": norm_scope(row) in {"in_scope", "oos"} and worker_scope in VALID_SCOPE_RESPONSES,
        "included_in_T_u": group in T_U_GROUPS and cond == "semi" and process_ok,
        "included_in_U_u": is_in_scope(row) and geom_ok and usable_ref and response in UNDERCOVERAGE_RESPONSES,
        "included_in_process_reliability": family == "process_failure" or safe(row.get("subfamily")) in PROCESS_SUBFAMILIES or invalid,
    }


def build_evidence_rows(quality_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    out = []
    for row in quality_rows:
        worker = safe(row.get("worker_id"))
        if not worker:
            continue
        family = family_for(row)
        subfamily = subfamily_for(row, family)
        response = response_type(row, family, subfamily)
        flags = inclusion_flags(row, family)
        exclusion = []
        if condition(row) == "semi" and (flags["included_in_r_u_calib"] or flags["included_in_r_geometry"]):
            exclusion.append("semi_must_not_enter_manual_reliability")
        if not flags["included_in_r_u_calib"]:
            exclusion.append("not_in_r_u_calib")
        if not flags["included_in_r_geometry"]:
            exclusion.append("not_in_r_geometry")
        out.append(
            {
                "worker_id": worker,
                "round_id": safe(row.get("round_id")) or "C1",
                "task_id": safe(row.get("task_id")),
                "base_task_id": safe(row.get("base_task_id")),
                "dataset_group": safe(row.get("dataset_group")),
                "condition": condition(row),
                "stage": stage(row),
                "pool": safe(row.get("pool")) or safe(row.get("dataset_group")),
                "task_final_scope": norm_scope(row) or "unknown",
                "task_oos_subtype": oos_subtype(row),
                "worker_scope_response": safe(row.get("worker_scope_response")),
                "geometry_reference_status": geometry_reference_status(row),
                "geometry_valid": geometry_valid(row),
                "process_invalid": process_fail(row),
                "quality_metric_name": safe(row.get("quality_metric_name")),
                "quality_metric_value": safe(row.get("quality_metric_value")),
                "family": family,
                "subfamily": subfamily,
                "response_type": response,
                "failure_observed": is_fail(row, family, response),
                **flags,
                "exclusion_reason": ";".join(exclusion),
                "active_time_source": safe(row.get("active_time_source")),
                "primary_active_time_eligible": truthy(row.get("primary_active_time_eligible")),
                "assignment_expected": truthy(row.get("assigned_expected", True)),
                "canonical_annotation_id": safe(row.get("canonical_annotation_id")),
                "source_manifest_version": safe(row.get("source_manifest_version") or row.get("manifest_version")),
                "profile_rule_version": PROFILE_VERSION,
                "_is_fail": is_fail(row, family, response),
                "_process_fail": process_fail(row),
            }
        )
    return out


def _worker_state_lookup(path: Path) -> dict[str, dict[str, str]]:
    return {safe(row.get("worker_id")): row for row in read_csv(path)}


def build_main_matrix(evidence_rows: list[dict[str, Any]], worker_state_rows: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    workers = sorted({row["worker_id"] for row in evidence_rows} | set(worker_state_rows))
    rows = []
    for worker in workers:
        group = [row for row in evidence_rows if row["worker_id"] == worker]
        fail_by_flag: dict[str, tuple[int, int]] = {}
        for field in (
            "included_in_r_u_calib",
            "included_in_r_geometry",
            "included_in_r_scope",
            "included_in_T_u",
            "included_in_U_u",
            "included_in_process_reliability",
        ):
            observed = [row for row in group if truthy(row.get(field))]
            fail_by_flag[field] = (sum(dimension_fail(row, field) for row in observed), len(observed))
        state = worker_state_rows.get(worker, {})
        n_calib = fail_by_flag["included_in_r_u_calib"][1]
        n_geom = fail_by_flag["included_in_r_geometry"][1]
        n_scope = fail_by_flag["included_in_r_scope"][1]
        n_semi = fail_by_flag["included_in_T_u"][1]
        n_under = fail_by_flag["included_in_U_u"][1]
        n_proc = fail_by_flag["included_in_process_reliability"][1]
        statuses = [support_status(n) for n in (n_calib, n_geom, n_scope, n_semi, n_under, n_proc)]
        confidence = "sufficient" if all(s in {"moderate", "sufficient"} for s in statuses[:3]) else min(statuses, key=["insufficient", "weak", "moderate", "sufficient"].index)
        rows.append(
            {
                "worker_id": worker,
                "round_id": "C1",
                "r_u_calib": safe(state.get("r_u_hat")),
                "r_u_calib_lcb": safe(state.get("r_u_ci_low")),
                "r_u_calib_ci_low": safe(state.get("r_u_ci_low")),
                "r_u_calib_ci_high": safe(state.get("r_u_ci_high")),
                "r_geometry_u": score(*fail_by_flag["included_in_r_geometry"]),
                "r_scope_u": score(*fail_by_flag["included_in_r_scope"]),
                "T_u": rate(*fail_by_flag["included_in_T_u"]),
                "U_u": rate(*fail_by_flag["included_in_U_u"]),
                "process_reliability": score(*fail_by_flag["included_in_process_reliability"]),
                "profile_confidence": confidence,
                "n_calib_support": n_calib,
                "n_geometry_support": n_geom,
                "n_scope_support": n_scope,
                "n_semi_support": n_semi,
                "n_undercoverage_support": n_under,
                "n_process_support": n_proc,
                "calib_support_status": support_status(n_calib),
                "geometry_support_status": support_status(n_geom),
                "scope_support_status": support_status(n_scope),
                "semi_support_status": support_status(n_semi),
                "undercoverage_support_status": support_status(n_under),
                "process_support_status": support_status(n_proc),
                "profile_version": PROFILE_VERSION,
                "profile_freeze_status": "C1_provisional",
                "notes": "sidecar_only_no_prescreen_writeback",
            }
        )
    return rows


def aggregate_family(evidence_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in evidence_rows:
        grouped[(row["worker_id"], row["family"])].append(row)
    workers = sorted({row["worker_id"] for row in evidence_rows})
    out = []
    for worker in workers:
        for family in FAMILIES:
            group = grouped.get((worker, family), [])
            observed = len(group)
            fails = sum(truthy(row.get("_is_fail")) for row in group)
            stages = ";".join(sorted({safe(row.get("stage")) for row in group if safe(row.get("stage"))}))
            out.append(
                {
                    "worker_id": worker,
                    "round_id": "C1",
                    "family": family,
                    "n_observed": observed,
                    "n_fail": fails,
                    "failure_rate": rate(fails, observed),
                    "support_status": support_status(observed),
                    "interpretation_allowed": interpretation_allowed(observed),
                    "source_stages": stages,
                    "profile_version": PROFILE_VERSION,
                }
            )
    return out


def aggregate_subfamily(evidence_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    coverage = Counter((row["family"], row["subfamily"], row["worker_id"]) for row in evidence_rows)
    global_worker_coverage = Counter((family, subfamily) for family, subfamily, _worker in coverage)
    for row in evidence_rows:
        grouped[(row["worker_id"], row["family"], row["subfamily"])].append(row)
    out = []
    for (worker, family, subfamily), group in sorted(grouped.items()):
        observed = len(group)
        fails = sum(truthy(row.get("_is_fail")) for row in group)
        task_count = len({safe(row.get("task_id")) for row in group if safe(row.get("task_id"))})
        stages = ";".join(sorted({safe(row.get("stage")) for row in group if safe(row.get("stage"))}))
        cover = global_worker_coverage[(family, subfamily)]
        out.append(
            {
                "worker_id": worker,
                "round_id": "C1",
                "family": family,
                "subfamily": subfamily,
                "n_observed": observed,
                "n_fail": fails,
                "failure_rate": rate(fails, observed),
                "task_count": task_count,
                "subfamily_global_worker_coverage": cover,
                "support_status": support_status(observed),
                "interpretation_allowed": observed >= 8 and task_count >= 4 and cover >= 6,
                "source_stages": stages,
                "profile_version": PROFILE_VERSION,
            }
        )
    return out


def _simple_json_rows(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if isinstance(data, dict):
        for value in data.values():
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
        return [data]
    return []


def load_p1_artifacts(paths: list[Path] | None) -> tuple[dict[str, dict[str, str]], list[str]]:
    lookup: dict[str, dict[str, str]] = defaultdict(dict)
    for path in paths or []:
        if not path.exists():
            continue
        if path.suffix.lower() == ".csv":
            rows = read_csv(path)
        elif path.suffix.lower() == ".jsonl":
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        elif path.suffix.lower() == ".json":
            rows = _simple_json_rows(json.loads(path.read_text(encoding="utf-8")))
        else:
            continue
        for row in rows:
            worker = safe(row.get("worker_id") or row.get("annotator_id"))
            if not worker:
                continue
            for key, value in row.items():
                value_s = safe(value)
                if value_s and not lookup[worker].get(key):
                    lookup[worker][key] = value_s
            for metric, aliases in P1_ALIASES.items():
                if lookup[worker].get(metric):
                    continue
                for alias in aliases:
                    value = safe(row.get(alias))
                    if value:
                        lookup[worker][metric] = value
                        break
    return dict(lookup), [str(path) for path in paths or []]


def _numeric(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _risk_bool(value: str) -> bool | None:
    text = safe(value).lower()
    if not text:
        return None
    if text in {"1", "true", "yes", "y", "high", "medium", "watch", "flag", "flagged", "risk", "warning"}:
        return True
    if text in {"0", "false", "no", "n", "low", "none", "clear", "ok"}:
        return False
    number = _numeric(text)
    if number is not None:
        return number >= 0.5
    return None


def directionally_consistent(p1_metric: str, p1_value: str, c1_value: str) -> str:
    if not safe(p1_value) or not safe(c1_value):
        return ""
    c1_num = _numeric(c1_value)
    if c1_num is None:
        return ""
    if p1_metric in {"p1_blind_trust_flag", "p1_undercoverage_watch", "p1_process_warning"}:
        p1_risk = _risk_bool(p1_value)
        if p1_risk is None:
            return ""
        if p1_metric == "p1_process_warning":
            return str(p1_risk == (c1_num < 0.5)).lower()
        return str(p1_risk == (c1_num >= 0.5)).lower()
    p1_num = _numeric(p1_value)
    if p1_num is None:
        return ""
    return str((p1_num >= 0.5) == (c1_num >= 0.5)).lower()


def build_predictive_rows(main_rows: list[dict[str, Any]], p1_lookup: dict[str, dict[str, str]] | None = None) -> list[dict[str, Any]]:
    rows = []
    p1_lookup = p1_lookup or {}
    for row in main_rows:
        p1 = p1_lookup.get(row["worker_id"], {})
        for check_name, p1_metric, c1_metric in PREDICTIVE_CHECKS:
            p1_value = safe(p1.get(p1_metric))
            c1_value = safe(row.get(c1_metric))
            consistency = directionally_consistent(p1_metric, p1_value, c1_value)
            evaluable = bool(p1_value and c1_value and consistency)
            rows.append(
                {
                    "worker_id": row["worker_id"],
                    "check_name": check_name,
                    "p1_metric_name": p1_metric,
                    "p1_metric_value": p1_value,
                    "c1_metric_name": c1_metric,
                    "c1_metric_value": c1_value,
                    "directionally_consistent": consistency,
                    "support_status": "weak_descriptive" if evaluable else "not_evaluable",
                    "interpretation_allowed": False,
                    "notes": "p1_artifact_read_only;prescreen_chain_not_touched" if evaluable else "p1_or_c1_metric_missing;prescreen_chain_not_touched",
                }
            )
    return rows


def write_predictive_report(path: Path, predictive_rows: list[dict[str, Any]]) -> None:
    evaluable = [row for row in predictive_rows if row["support_status"] != "not_evaluable"]
    consistent = sum(row["directionally_consistent"] == "true" for row in evaluable)
    inconsistent = sum(row["directionally_consistent"] == "false" for row in evaluable)
    status = "evaluable" if evaluable else "not_evaluable"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "# P1-to-C1 Predictive Validity Report",
                "",
                f"Status: {status}.",
                "",
                "P1 artifacts are read-only inputs. The completed PreScreen chain is not rewritten or re-materialized.",
                "",
                f"Check rows: {len(predictive_rows)}",
                f"Evaluable descriptive rows: {len(evaluable)}",
                f"Directionally consistent rows: {consistent}",
                f"Directionally inconsistent rows: {inconsistent}",
                "",
            ]
        ),
        encoding="utf-8",
    )


def materialize(quality_csv: Path, worker_state_csv: Path, output_dir: Path, p1_artifacts: list[Path] | None = None) -> dict[str, Any]:
    evidence = build_evidence_rows(read_csv(quality_csv))
    public_evidence = [{k: v for k, v in row.items() if not k.startswith("_")} for row in evidence]
    main = build_main_matrix(evidence, _worker_state_lookup(worker_state_csv))
    family = aggregate_family(evidence)
    subfamily = aggregate_subfamily(evidence)
    p1_lookup, input_p1_artifacts = load_p1_artifacts(p1_artifacts)
    predictive = build_predictive_rows(main, p1_lookup)
    predictive_evaluable = any(row["support_status"] != "not_evaluable" for row in predictive)

    evidence_csv = output_dir / "worker_task_evidence_table_C1.csv"
    main_csv = output_dir / "worker_profile_main_matrix_C1.csv"
    family_csv = output_dir / "worker_failure_family_response_C1.csv"
    subfamily_csv = output_dir / "worker_subfamily_response_C1.csv"
    predictive_csv = output_dir / "p1_to_c1_predictive_validity.csv"
    predictive_report = output_dir / "p1_to_c1_predictive_validity_report.md"
    summary_json = output_dir / "worker_profile_sidecar_C1.summary.json"
    write_csv(evidence_csv, public_evidence, EVIDENCE_FIELDS)
    write_csv(main_csv, main, MAIN_FIELDS)
    write_csv(family_csv, family, FAMILY_FIELDS)
    write_csv(subfamily_csv, subfamily, SUBFAMILY_FIELDS)
    write_csv(predictive_csv, predictive, PREDICTIVE_FIELDS)
    write_predictive_report(predictive_report, predictive)
    summary = {
        "profile_version": PROFILE_VERSION,
        "input_quality_csv": str(quality_csv),
        "input_worker_state_csv": str(worker_state_csv),
        "input_p1_artifacts": input_p1_artifacts,
        "output_worker_task_evidence_table": str(evidence_csv),
        "output_worker_profile_main_matrix": str(main_csv),
        "output_worker_failure_family_response": str(family_csv),
        "output_worker_subfamily_response": str(subfamily_csv),
        "output_p1_to_c1_predictive_validity": str(predictive_csv),
        "output_p1_to_c1_predictive_validity_report": str(predictive_report),
        "n_workers": len(main),
        "n_evidence_rows": len(public_evidence),
        "n_profile_rows": len(main),
        "n_family_rows": len(family),
        "n_subfamily_rows": len(subfamily),
        "n_insufficient_family_cells": sum(row["support_status"] == "insufficient" for row in family),
        "n_insufficient_subfamily_cells": sum(row["support_status"] == "insufficient" for row in subfamily),
        "r_u_calib_estimated": any(safe(row.get("r_u_calib")) for row in main),
        "r_geometry_u_estimated": any(safe(row.get("r_geometry_u")) for row in main),
        "p1_predictive_validity_status": "evaluable" if predictive_evaluable else "not_evaluable",
        "profile_freeze_status": "C1_provisional",
        "blockers": [],
        "warnings": [] if predictive_evaluable else ["p1_predictive_validity_not_evaluable_without_p1_artifacts" if not input_p1_artifacts else "p1_predictive_validity_not_evaluable_without_matching_p1_c1_metrics"],
    }
    write_json(summary_json, summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize C1 worker-profile sidecar artifacts.")
    parser.add_argument("--quality-csv", type=Path, default=DEFAULT_QUALITY)
    parser.add_argument("--worker-state-csv", type=Path, default=DEFAULT_WORKER_STATE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--p1-artifact", type=Path, action="append", default=[])
    args = parser.parse_args(argv)
    print(json.dumps(materialize(args.quality_csv, args.worker_state_csv, args.output_dir, args.p1_artifact), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
