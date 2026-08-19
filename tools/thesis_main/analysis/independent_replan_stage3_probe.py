#!/usr/bin/env python3
"""Probe schemas needed for the independent reviewer/profile re-plan preflight.

Append-only diagnostic.  It does not alter frozen evidence or claim reviewer
ability.  The purpose is to discover whether existing P1/C1 artefacts contain
usable semi-correction, proposal-adherence, and cross-stage fields before the
formal stage-3 calculations are specified.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

TARGET_TERMS = (
    "blind_trust",
    "semi_response_type",
    "semi_correction_failure",
    "semi_issue_recognition",
    "semi_geometry_correction",
    "successful_correction",
    "failed_correction",
    "model_issue_primary",
    "correction_reliability",
    "t_u",
)

P1_ROLLUP = Path("analysis_results/prescreen_closeout_final_gold_v2_20260701/prescreen_worker_screening_rollup.csv")
P1_R0 = Path("analysis_results/prescreen_closeout_final_gold_v2_20260701/prescreen_r0_snapshot.csv")
PROFILE = Path("analysis_results/final_calibration_profile_20260817_v1/pooled_worker_profile_v2.csv")
RUN_CONFIG = Path("analysis_results/prescreen_closeout_final_gold_v2_20260701/prescreen_closeout_run_config_final_gold_v2_20260701.json")
SEMI_REVIEW = Path("analysis_results/prescreen_closeout_final_gold_v2_20260701/raw_inputs/prescreen_semi_synthetic_trap_issue_review.csv")


def _read_header(path: Path) -> list[str]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="", errors="replace") as f:
            return list(next(csv.reader(f), []))
    except Exception:
        return []


def _count_rows(path: Path) -> int:
    try:
        with path.open("r", encoding="utf-8-sig", errors="replace") as f:
            return max(0, sum(1 for _ in f) - 1)
    except Exception:
        return -1


def _json_shape(value: Any, depth: int = 0) -> Any:
    if depth >= 3:
        return type(value).__name__
    if isinstance(value, dict):
        return {str(k): _json_shape(v, depth + 1) for k, v in list(value.items())[:30]}
    if isinstance(value, list):
        return {"type": "list", "len": len(value), "sample": _json_shape(value[0], depth + 1) if value else None}
    return type(value).__name__


def _result_signature(task: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "task_id": task.get("id"),
        "top_keys": sorted(map(str, task.keys())),
        "data": task.get("data", {}),
        "prediction_count": len(task.get("predictions") or []),
        "annotation_count": len(task.get("annotations") or []),
        "prediction_result_types": [],
        "prediction_value_keys": [],
        "annotation_result_types": [],
        "annotation_value_keys": [],
    }
    for group_name, field in (("prediction", "predictions"), ("annotation", "annotations")):
        types: set[str] = set()
        keys: set[str] = set()
        from_names: set[str] = set()
        for container in task.get(field) or []:
            for item in container.get("result") or []:
                types.add(str(item.get("type") or ""))
                from_names.add(str(item.get("from_name") or ""))
                value = item.get("value")
                if isinstance(value, dict):
                    keys.update(map(str, value.keys()))
        out[f"{group_name}_result_types"] = sorted(types)
        out[f"{group_name}_value_keys"] = sorted(keys)
        out[f"{group_name}_from_names"] = sorted(from_names)
    return out


def _safe_spearman(x: pd.Series, y: pd.Series) -> tuple[float, float, int]:
    x = pd.to_numeric(x, errors="coerce")
    y = pd.to_numeric(y, errors="coerce")
    mask = x.notna() & y.notna()
    n = int(mask.sum())
    if n < 8 or x[mask].nunique() < 2 or y[mask].nunique() < 2:
        return math.nan, math.nan, n
    r, p = stats.spearmanr(x[mask], y[mask])
    return float(r), float(p), n


def _cross_stage_probe(root: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    roll = pd.read_csv(root / P1_ROLLUP, low_memory=False)
    r0 = pd.read_csv(root / P1_R0, low_memory=False)
    prof = pd.read_csv(root / PROFILE, low_memory=False)
    roll["worker_id"] = roll["annotator_id"].astype(str)
    r0["worker_id"] = r0["worker_id"].astype(str)
    prof["worker_id"] = prof["worker_id"].astype(str)
    d = roll.merge(r0[["worker_id", "r_u_0"]], on="worker_id", how="left").merge(prof, on="worker_id", how="inner", suffixes=("_p1", "_later"))
    den = pd.to_numeric(d["n_scope_correct_in_scope"], errors="coerce") + pd.to_numeric(d["n_scope_false_positive"], errors="coerce") + pd.to_numeric(d["n_scope_false_negative"], errors="coerce")
    d["p1_scope_accuracy"] = pd.to_numeric(d["n_scope_correct_in_scope"], errors="coerce") / den.replace(0, np.nan)
    d["p1_scope_fp_rate"] = pd.to_numeric(d["n_scope_false_positive"], errors="coerce") / den.replace(0, np.nan)
    d["p1_scope_fn_rate"] = pd.to_numeric(d["n_scope_false_negative"], errors="coerce") / den.replace(0, np.nan)
    align = pd.to_numeric(d["n_alignment_available"], errors="coerce")
    d["p1_geometry_retention"] = 1.0 - (pd.to_numeric(d["n_undercoverage_high"], errors="coerce") + .5 * pd.to_numeric(d["n_undercoverage_medium"], errors="coerce")) / align.replace(0, np.nan)
    predictors = ["r_u_0", "p1_scope_accuracy", "p1_scope_fp_rate", "p1_scope_fn_rate", "p1_geometry_retention", "n_exact_copy_low_time_events", "active_time_source_coverage"]
    outcomes = [c for c in ["Q_GT_task_adjusted", "Q_GT_EB", "Q_GT_LCB", "R_peer_stable", "R_LOO_medoid", "F_struct_EB", "T_active_task_adjusted", "S_G"] if c in d.columns]
    rows: list[dict[str, Any]] = []
    for px in predictors:
        if px not in d.columns:
            continue
        for oy in outcomes:
            r, p, n = _safe_spearman(d[px], d[oy])
            rows.append({"predictor": px, "outcome": oy, "n": n, "spearman_r": r, "p_value_descriptive_only": p})
    keep = [c for c in ["worker_id"] + predictors + outcomes if c in d.columns]
    return pd.DataFrame(rows), d[keep]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path.cwd())
    ap.add_argument("--output-dir", type=Path, required=True)
    args = ap.parse_args()
    root = args.root.resolve()
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)

    header_rows: list[dict[str, Any]] = []
    for p in sorted((root / "analysis_results").rglob("*.csv")):
        if out in p.parents:
            continue
        header = _read_header(p)
        hits = [c for c in header if any(term in c.lower() for term in TARGET_TERMS)]
        if hits:
            header_rows.append({
                "path": p.relative_to(root).as_posix(),
                "rows": _count_rows(p),
                "hit_columns": "|".join(hits),
                "all_columns": "|".join(header),
            })
    pd.DataFrame(header_rows).to_csv(out / "SEMI_REVIEW_FIELD_CANDIDATES.csv", index=False)

    config = json.loads((root / RUN_CONFIG).read_text(encoding="utf-8"))
    export_paths = [Path(item["path"]) for item in config.get("inputs", {}).get("label_studio_exports", [])]
    target_ids: set[int] = set()
    if (root / SEMI_REVIEW).exists():
        sr = pd.read_csv(root / SEMI_REVIEW)
        for c in ("en_task_id", "zh_task_id"):
            target_ids.update(pd.to_numeric(sr[c], errors="coerce").dropna().astype(int).tolist())
    export_probe: dict[str, Any] = {}
    task_signatures: list[dict[str, Any]] = []
    for rel in export_paths:
        path = root / rel
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            export_probe[rel.as_posix()] = {"error": f"{type(exc).__name__}: {exc}"}
            continue
        tasks = payload if isinstance(payload, list) else payload.get("tasks", []) if isinstance(payload, dict) else []
        export_probe[rel.as_posix()] = {
            "payload_shape": _json_shape(payload),
            "task_count": len(tasks),
            "first_task_signature": _result_signature(tasks[0]) if tasks else None,
        }
        for task in tasks:
            try:
                tid = int(task.get("id"))
            except Exception:
                continue
            if tid in target_ids:
                sig = _result_signature(task)
                sig["source_export"] = rel.as_posix()
                task_signatures.append(sig)
    with (out / "P1_EXPORT_SCHEMA_PROBE.json").open("w", encoding="utf-8") as f:
        json.dump(export_probe, f, ensure_ascii=False, indent=2)
    with (out / "P1_SEMI_MIRROR_TASK_SCHEMA.json").open("w", encoding="utf-8") as f:
        json.dump(task_signatures, f, ensure_ascii=False, indent=2)

    assoc, joined = _cross_stage_probe(root)
    assoc.to_csv(out / "P1_CROSS_STAGE_ASSOCIATIONS_PROBE.csv", index=False)
    joined.to_csv(out / "P1_LATER_PROFILE_JOIN_PROBE.csv", index=False)

    summary = {
        "status": "stage3_schema_probe_complete",
        "semi_candidate_tables": len(header_rows),
        "semi_mirror_task_ids_requested": len(target_ids),
        "semi_mirror_tasks_found": len(task_signatures),
        "cross_stage_workers_joined": int(len(joined)),
        "limitations": [
            "Existing annotator-profile fields do not establish reviewer-role transfer.",
            "Cross-stage associations are worker-level descriptive probes with small n and no multiplicity correction.",
            "A formal proposal-adherence measure must use the actual reviewed synthetic issue family, not the planned operator label.",
        ],
    }
    with (out / "STAGE3_PROBE_SUMMARY.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
