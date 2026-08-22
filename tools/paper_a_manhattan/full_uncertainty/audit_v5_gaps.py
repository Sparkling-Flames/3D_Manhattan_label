"""Generate the small, auditable v5 uncertainty-data gap tables.

This module deliberately reads already-materialised v5 CSVs.  It does not infer
behaviour from Label Studio timestamps and does not turn lead time or event
fragments into formal active time.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Mapping

import pandas as pd
from scipy.stats import beta


ACTIVE_TIME_COMPUTABILITY_DESCRIPTIVE = "ACTIVE_TIME_COMPUTABILITY_DESCRIPTIVE.csv"
C1_ACTIVE_TIME_MISSINGNESS_AUDIT = "C1_ACTIVE_TIME_MISSINGNESS_AUDIT.csv"
EVENT_SEQUENCE_OBSERVED_FACT = "EVENT_SEQUENCE_OBSERVED_FACT.csv"
COVERAGE_GAP_COMPUTABILITY_AUDIT = "COVERAGE_GAP_COMPUTABILITY_AUDIT.csv"

_FORBIDDEN_OUTPUT_TOKENS = ("pause", "return", "revisit", "save", "submit")
_STAGE_NAMES = {"P1", "C1", "C2-B", "C2A-RP-B1", "C2A-RP-B2"}


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, encoding="utf-8-sig", low_memory=False)


def _text(value: Any) -> str:
    return "" if pd.isna(value) else str(value).strip()


def _truth(value: Any) -> bool:
    return _text(value).lower() in {"1", "true", "yes", "y", "valid", "eligible", "matched"}


def _column(frame: pd.DataFrame, name: str, default: Any = "") -> pd.Series:
    return frame[name] if name in frame else pd.Series(default, index=frame.index)


def _nonmissing(series: pd.Series) -> pd.Series:
    return series.notna() & series.astype(str).str.strip().ne("")


def _jeffreys(missing: int, n: int) -> tuple[float, float]:
    if n <= 0:
        return math.nan, math.nan
    return float(beta.ppf(0.025, missing + 0.5, n - missing + 0.5)), float(
        beta.ppf(0.975, missing + 0.5, n - missing + 0.5)
    )


def _classify_active_time(records: pd.DataFrame) -> pd.Series:
    """Classify only the frozen owner-valid lane; keep lead proxy separate."""
    if "active_time_measurement_class" in records:
        values = records["active_time_measurement_class"].fillna("").astype(str).str.strip().str.lower()
        eligible = _column(records, "active_time_formal_eligible", True).map(_truth)
        result = values.where(~values.eq("formal_frozen") | eligible, "missing")
        return result.where(result.isin({"formal_frozen", "lead_time_proxy_excluded", "missing"}), "other")
    computable = _column(records, "active_time_computable_bool", False).map(_truth)
    proxy = _column(records, "active_time_proxy_excluded", False).map(_truth)
    return pd.Series(
        ["lead_time_proxy_excluded" if p else "formal_frozen" if c else "missing" for c, p in zip(computable, proxy)],
        index=records.index,
    )


def active_time_computability_descriptive(records: pd.DataFrame) -> pd.DataFrame:
    """Return descriptive active-time counts without any proxy imputation."""
    frame = records.copy()
    frame["_lane"] = _classify_active_time(frame)
    frame["_stage"] = _column(frame, "stage").map(_text)
    frame["_condition"] = _column(frame, "condition").map(_text)
    rows: list[dict[str, Any]] = []
    group_specs = [("all", None), ("stage", "_stage"), ("condition", "_condition")]
    for grouping, key in group_specs:
        groups = [("all", frame)] if key is None else frame.groupby(key, dropna=False, sort=True)
        for value, group in groups:
            n = len(group)
            counts = group["_lane"].value_counts()
            active = int(counts.get("formal_frozen", 0))
            proxy = int(counts.get("lead_time_proxy_excluded", 0))
            missing = int(counts.get("missing", 0))
            rows.append({
                "fact": "active_time_computability",
                "grouping": grouping,
                "group_value": value,
                "n": n,
                "active_time_n": active,
                "lead_time_proxy_n": proxy,
                "missing_n": missing,
                "other_n": n - active - proxy - missing,
                "active_time_rate": active / n if n else math.nan,
                "lead_time_proxy_rate": proxy / n if n else math.nan,
                "missing_rate": missing / n if n else math.nan,
                "active_time_rule": "owner_valid_formal_frozen_only",
                "lead_time_rule": "descriptive_proxy_excluded_from_active_time",
            })
    result = pd.DataFrame(rows)
    return _safe_columns(result)


def c1_active_time_missingness_audit(records: pd.DataFrame) -> pd.DataFrame:
    """Audit C1 active-time missingness by condition, task, worker and building."""
    frame = records.copy()
    stage = _column(frame, "stage").map(_text)
    frame = frame[stage.eq("C1")].copy()
    frame["_lane"] = _classify_active_time(frame)
    frame["_condition"] = _column(frame, "condition").map(_text)
    frame["_task"] = _column(frame, "base_task_id", _column(frame, "task_id")).map(_text)
    frame["_worker"] = _column(frame, "worker_id").map(_text)
    frame["_building"] = _column(frame, "building_id").map(_text)
    rows: list[dict[str, Any]] = []
    for grouping, column in (("condition", "_condition"), ("task", "_task"), ("worker", "_worker"), ("building", "_building")):
        for value, group in frame.groupby(column, dropna=False, sort=True):
            n = len(group)
            missing = int(group["_lane"].eq("missing").sum())
            lower, upper = _jeffreys(missing, n)
            rows.append({
                "stage": "C1", "grouping": grouping, "group_value": value,
                "condition": value if grouping == "condition" else "",
                "base_task_id": value if grouping == "task" else "",
                "worker_id": value if grouping == "worker" else "",
                "building_id": value if grouping == "building" else "",
                "n": n, "missing": missing, "rate": missing / n if n else math.nan,
                "jeffreys_lower": lower, "jeffreys_upper": upper,
                "missing_definition": "active_time_measurement_class=missing; no lead-time backfill",
            })
    return _safe_columns(pd.DataFrame(rows))


def _json_value(value: Any, key: str) -> Any:
    try:
        payload = json.loads(value) if isinstance(value, str) else value
    except (TypeError, ValueError, json.JSONDecodeError):
        return ""
    return payload.get(key, "") if isinstance(payload, dict) else ""


def _script_version(row: pd.Series) -> str:
    value = _json_value(row.get("raw_event_json", ""), "script_version")
    return _text(value)


def _timestamp_ms(series: pd.Series) -> pd.Series:
    # Explicit unit=ms is part of the audit contract.  Invalid values remain missing.
    return pd.to_numeric(series, errors="coerce")


def _max_events_60s(values: list[float]) -> int:
    values = sorted(v for v in values if math.isfinite(v))
    if not values:
        return 0
    left = result = 0
    for right, value in enumerate(values):
        while value - values[left] > 60_000:
            left += 1
        result = max(result, right - left + 1)
    return result


def event_sequence_observed_fact(events: pd.DataFrame) -> pd.DataFrame:
    """Summarise observed sessions and field coverage; no behaviour is inferred."""
    frame = events.copy()
    if frame.empty:
        return _safe_columns(pd.DataFrame(columns=["fact_type", "n_events"]))
    sandbox = frame.astype(str).apply(lambda column: column.str.contains("sandbox", case=False, na=False)).any(axis=1)
    frame["_sandbox"] = sandbox
    for name in ("project_id", "task_id", "annotator_id", "session_id"):
        frame[name] = _column(frame, name).map(_text)
    frame["_ts_ms"] = _timestamp_ms(_column(frame, "timestamp"))
    frame["_server_ts"] = pd.to_datetime(_column(frame, "server_received_at"), errors="coerce", utc=True)
    frame["_stage"] = _column(frame, "event_stage").map(_text)
    frame["_formal"] = _column(frame, "in_formal_stage_scope").map(_truth)
    session_counts = frame.groupby(["project_id", "task_id", "annotator_id"], dropna=False)["session_id"].nunique()
    rows: list[dict[str, Any]] = []
    keys = ["project_id", "task_id", "annotator_id", "session_id"]
    for values, group in frame.groupby(keys, dropna=False, sort=True):
        observed = group.loc[~group["_sandbox"]]
        ts = sorted(float(x) for x in observed["_ts_ms"].dropna())
        gaps = [b - a for a, b in zip(ts, ts[1:])]
        valid_clock = observed["_ts_ms"].notna() & observed["_server_ts"].notna()
        offset = (
            observed.loc[valid_clock, "_server_ts"].astype("int64") / 1_000_000_000
            - observed.loc[valid_clock, "_ts_ms"] / 1000
        )
        rows.append({
            "fact_type": "session_sequence",
            "project_id": values[0], "task_id": values[1], "annotator_id": values[2], "session_id": values[3],
            "event_count": len(observed), "raw_event_count": len(group),
            "sandbox_event_n": int(group["_sandbox"].sum()), "timestamp_ms_n": len(ts),
            "observed_start_timestamp_ms": ts[0] if ts else math.nan,
            "observed_end_timestamp_ms": ts[-1] if ts else math.nan,
            "observed_span_seconds": (ts[-1] - ts[0]) / 1000 if len(ts) > 1 else 0.0 if ts else math.nan,
            "max_gap_seconds": max(gaps) / 1000 if gaps else 0.0,
            "gap_gt_60": any(gap > 60_000 for gap in gaps),
            "max_events_per_60_seconds": _max_events_60s(ts),
            "multi_session_fact": int(session_counts.get(values[:3], 0)) > 1,
            "formal_event_n": int(observed["_formal"].sum()),
            "outside_or_stage_mismatch_n": int((~group["_formal"]).sum()),
            "observed_outside_or_stage_mismatch_n": int((~observed["_formal"]).sum()),
            "clock_offset_median_seconds": float(offset.median()) if len(offset) else math.nan,
            "clock_offset_p95_seconds": float(offset.quantile(0.95)) if len(offset) else math.nan,
            "clock_offset_audit_only": True,
            "observed_behavior_event_fields": "",
        })
    result = pd.DataFrame(rows)
    observed_frame = frame.loc[~frame["_sandbox"]]
    total = len(observed_frame)
    coverage = []
    for field, label in (("page_gate_eligible", "gate"), ("store_mismatch_present", "store")):
        present = _nonmissing(_column(observed_frame, field)).sum()
        coverage.append({"fact_type": "field_coverage", "coverage_field": label, "field_name": field, "observed_n": int(present), "coverage_rate": present / total if total else math.nan, "description": "observed field coverage; no behaviour claim"})
    scripts = observed_frame.apply(_script_version, axis=1)
    present = scripts.ne("").sum()
    coverage.append({"fact_type": "field_coverage", "coverage_field": "script", "field_name": "script_version", "observed_n": int(present), "coverage_rate": present / total if total else math.nan, "description": "script version provenance coverage"})
    return _safe_columns(pd.concat([result, pd.DataFrame(coverage)], ignore_index=True, sort=False))


def coverage_gap_computability_audit(
    records: pd.DataFrame,
    events: pd.DataFrame,
    c1: pd.DataFrame | None = None,
    source_frames: Mapping[str, pd.DataFrame] | None = None,
) -> pd.DataFrame:
    """Report only computability supported by present fields and observed support."""
    c1 = c1 if c1 is not None else records.loc[_column(records, "stage").map(_text).eq("C1")].copy()
    frames = dict(source_frames or {})
    frames.update({"records": records, "events": events, "c1": c1})

    def support(fields: tuple[str, ...], frame_names: tuple[str, ...] = ("records",)) -> tuple[int, int, str]:
        available = [frames[name] for name in frame_names if name in frames and not frames[name].empty]
        if not available:
            return 0, 0, "absent"
        frame = available[0]
        if not set(fields).issubset(frame.columns):
            return 0, len(frame), "field_absent"
        mask = pd.Series(True, index=frame.index)
        for field in fields:
            mask &= _nonmissing(frame[field])
        return int(mask.sum()), len(frame), "observed"

    rows = []
    observed, total, status = support(("base_task_id", "geometry_computable"), ("c1",))
    rows.append({"component": "task_clustering", "computability_status": "not_evaluable_stability", "observed_n": observed, "denominator_n": total, "support": observed, "gap": "cluster stability over additional support is not observed", "description": "C1 clustering fields are descriptive; stability cannot be evaluated without repeated support trajectory"})
    observed, total, status = support(("active_time_measurement_class",), ("c1",))
    rows.append({"component": "active_time_missingness", "computability_status": "partial_descriptive", "observed_n": observed, "denominator_n": total, "support": observed, "gap": "missingness is descriptive and not imputed", "description": "owner-valid active time only; lead-time proxy remains separate"})
    required = ("version", "event", "effective", "supersedes")
    available = [name for name in required if any(name in frame.columns for frame in frames.values())]
    rows.append({"component": "reference_trajectory", "computability_status": "not_computable", "observed_n": len(available), "denominator_n": len(required), "support": 0, "gap": "missing version/event/effective/supersedes fields", "description": "reference trajectory cannot be reconstructed from current fields"})
    expert_fields = ("expert_id", "blind_review", "geometry")
    expert_present = [name for name in expert_fields if any(name in frame.columns for frame in frames.values())]
    rows.append({"component": "independent_expert_review", "computability_status": "not_computable", "observed_n": len(expert_present), "denominator_n": len(expert_fields), "support": 0, "gap": "no independent identity, blind-review, or geometry evidence", "description": "no expert table is fabricated"})
    observed, total, _ = support(("timestamp",), ("events",))
    rows.append({"component": "event_logging", "computability_status": "partial_logging", "observed_n": observed, "denominator_n": total, "support": observed, "gap": "event fields are partial; formal behaviour fields remain empty", "description": "observed event sequence and provenance only; client-server offset is audit-only"})
    return _safe_columns(pd.DataFrame(rows))


def _safe_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Keep output names neutral and prevent accidental unsupported behaviour claims."""
    bad = [column for column in frame.columns if any(token in str(column).lower() for token in _FORBIDDEN_OUTPUT_TOKENS)]
    if bad:
        raise ValueError(f"unsupported behaviour column(s): {bad}")
    return frame.reset_index(drop=True)


def build_audit_frames(
    records: pd.DataFrame,
    events: pd.DataFrame,
    sessions: pd.DataFrame | None = None,
    c1: pd.DataFrame | None = None,
    source_frames: Mapping[str, pd.DataFrame] | None = None,
) -> dict[str, pd.DataFrame]:
    """Pure top-level builder used by tests and the CLI."""
    # sessions is accepted for API clarity; the event keys are the session source of truth.
    del sessions
    return {
        ACTIVE_TIME_COMPUTABILITY_DESCRIPTIVE: active_time_computability_descriptive(records),
        C1_ACTIVE_TIME_MISSINGNESS_AUDIT: c1_active_time_missingness_audit(records),
        EVENT_SEQUENCE_OBSERVED_FACT: event_sequence_observed_fact(events),
        COVERAGE_GAP_COMPUTABILITY_AUDIT: coverage_gap_computability_audit(records, events, c1, source_frames),
    }


def build_frames(input_dir: Path) -> dict[str, pd.DataFrame]:
    """Load the v5 directory and return the four planned CSV-named frames."""
    records, events, sessions, c1 = load_v5_frames(Path(input_dir))
    return build_audit_frames(records, events, sessions, c1)


def load_v5_frames(input_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    records = _read_csv(input_dir / "TIME_MEASUREMENT_RECORD_AUDIT.csv")
    events = _read_csv(input_dir / "RAW_ACTIVE_EVENT_FACT.CSV")
    sessions = _read_csv(input_dir / "RAW_ACTIVE_SESSION_FACT.CSV")
    c1 = records.loc[records.get("stage", pd.Series(index=records.index)).astype(str).eq("C1")].copy()
    return records, events, sessions, c1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    frames = build_frames(args.input_dir)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in frames.items():
        frame.to_csv(args.output_dir / name, index=False, encoding="utf-8", lineterminator="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
