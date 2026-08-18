#!/usr/bin/env python3
"""Focused second-stage preflight for experiment re-planning.

The program discovers actual schemas from frozen repository artefacts and performs
only low-assumption descriptive calculations. It intentionally does not promote
post-task meta labels to pre-assignment predictors, and it does not claim that an
annotator-quality profile measures reviewer-role skill.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
from scipy import stats

TABLES = {
    "submission_master": "analysis_results/post_block2_analysis_pack_20260817_v4/post_block2_submission_master.csv",
    "task_context": "analysis_results/post_block2_analysis_pack_20260817_v4/post_block2_task_context_master.csv",
    "worker_profile_master": "analysis_results/post_block2_analysis_pack_20260817_v4/post_block2_worker_profile_master.csv",
    "pooled_profile": "analysis_results/final_calibration_profile_20260817_v1/pooled_worker_profile_v2.csv",
    "qgt_worker_evidence": "analysis_results/final_calibration_profile_20260817_v1/final_c1_c2_qgt_worker_evidence.csv",
    "c1_geometry_pool": "analysis_results/c1_formal_audit_20260802_v16_final/c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03/c1_geometry_pool_eligibility.csv",
    "c1_gt_quality": "analysis_results/c1_formal_audit_20260802_v16_final/c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03/c1_gt_quality_evidence.csv",
    "c1_worker_state": "analysis_results/c1_formal_audit_20260802_v16_final/c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03/c1_three_track_worker_state_formal.csv",
    "c1_structural": "analysis_results/c1_formal_audit_20260802_v16_final/c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03/structural_validation_analysis.csv",
    "c1_crowd": "analysis_results/c1_formal_audit_20260802_v16_final/c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03/c1_geometry_loo_task_crowd_structure.csv",
    "tg_task_metrics": "analysis_results/topology_sequential_preflight_20260818_v4_audit/TG_EF5_TASK_METRICS.csv",
    "tg_operating": "analysis_results/topology_sequential_preflight_20260818_v4_audit/TG_EF5_OPERATING_CHARACTERISTICS.csv",
    "reviewer_availability": "analysis_results/topology_sequential_preflight_20260818_v4_audit/REVIEWER_AVAILABILITY_SENSITIVITY.csv",
}

GROUP_TERMS = {
    "identity": ["worker", "annotator", "user", "task", "image", "building", "stage", "condition", "mode"],
    "meta": ["difficulty", "scope", "model_issue", "model issue", "occlusion", "seam", "reflection", "texture", "tag"],
    "time": ["active_time", "active time", "duration", "elapsed", "lead_time", "owner_valid"],
    "quality": ["quality", "iou", "q_gt", "qgt", "gt_", "error", "loss"],
    "structural": ["structural", "canonical_valid", "invalid", "normalization", "failure"],
    "geometry": ["geometry", "corner", "cluster", "medoid", "similarity", "topology", "point_count"],
    "profile": ["q_gt", "qgt", "r_peer", "r_loo", "f_struct", "lcb", "ucb", "support", "profile", "slope"],
}


def read_table(root: Path, rel: str) -> pd.DataFrame:
    path = root / rel
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, low_memory=False)


def match_columns(columns: Iterable[str], terms: Iterable[str]) -> list[str]:
    result = []
    for c in columns:
        lc = str(c).lower()
        if any(term in lc for term in terms):
            result.append(str(c))
    return result


def boolish(series: pd.Series) -> pd.Series:
    s = series.astype(str).str.strip().str.lower()
    return s.map({"true": True, "1": True, "yes": True, "false": False, "0": False, "no": False})


def numeric_candidates(df: pd.DataFrame, columns: list[str], min_nonempty: int = 10) -> dict[str, pd.Series]:
    out: dict[str, pd.Series] = {}
    for c in columns:
        x = pd.to_numeric(df[c], errors="coerce")
        if int(x.notna().sum()) >= min_nonempty:
            out[c] = x
    return out


def safe_spearman(x: pd.Series, y: pd.Series) -> tuple[float, float, int]:
    mask = x.notna() & y.notna()
    n = int(mask.sum())
    if n < 8 or x[mask].nunique() < 2 or y[mask].nunique() < 2:
        return np.nan, np.nan, n
    r, p = stats.spearmanr(x[mask], y[mask])
    return float(r), float(p), n


def describe_numeric(name: str, x: pd.Series, table: str) -> dict[str, Any]:
    z = pd.to_numeric(x, errors="coerce").dropna()
    if z.empty:
        return {"table": table, "column": name, "n": 0}
    return {
        "table": table,
        "column": name,
        "n": int(z.size),
        "mean": float(z.mean()),
        "sd": float(z.std(ddof=1)) if z.size > 1 else np.nan,
        "min": float(z.min()),
        "p01": float(z.quantile(.01)),
        "p05": float(z.quantile(.05)),
        "p25": float(z.quantile(.25)),
        "median": float(z.median()),
        "p75": float(z.quantile(.75)),
        "p95": float(z.quantile(.95)),
        "p99": float(z.quantile(.99)),
        "max": float(z.max()),
        "missing": int(pd.to_numeric(x, errors="coerce").isna().sum()),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path.cwd())
    ap.add_argument("--output-dir", type=Path, required=True)
    args = ap.parse_args()
    root = args.root.resolve()
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)

    tables: dict[str, pd.DataFrame] = {name: read_table(root, rel) for name, rel in TABLES.items()}

    field_map: dict[str, Any] = {}
    schema_rows: list[dict[str, Any]] = []
    value_rows: list[dict[str, Any]] = []
    numeric_rows: list[dict[str, Any]] = []

    for name, df in tables.items():
        matched = {g: match_columns(df.columns, terms) for g, terms in GROUP_TERMS.items()}
        field_map[name] = {
            "path": TABLES[name],
            "rows": int(len(df)),
            "columns": list(map(str, df.columns)),
            "matched": matched,
        }
        for c in df.columns:
            s = df[c]
            nonempty = int(s.notna().sum())
            nunique = int(s.nunique(dropna=True))
            examples = [str(v)[:180] for v in s.dropna().astype(str).drop_duplicates().head(5).tolist()]
            groups = [g for g, cols in matched.items() if c in cols]
            schema_rows.append({
                "table": name,
                "path": TABLES[name],
                "rows": len(df),
                "column": c,
                "nonempty": nonempty,
                "nunique": nunique,
                "dtype": str(s.dtype),
                "groups": "|".join(groups),
                "examples": " || ".join(examples),
            })
            if groups and 1 <= nunique <= 40:
                counts = s.fillna("__MISSING__").astype(str).value_counts(dropna=False).head(40)
                for level, count in counts.items():
                    value_rows.append({
                        "table": name,
                        "column": c,
                        "group": "|".join(groups),
                        "value": level,
                        "count": int(count),
                        "share": float(count / max(len(df), 1)),
                    })
        focus_numeric = sorted(set(sum(matched.values(), [])))
        for c, x in numeric_candidates(df, focus_numeric).items():
            numeric_rows.append(describe_numeric(c, x, name))

    pd.DataFrame(schema_rows).to_csv(out / "FOCUSED_SCHEMA.csv", index=False)
    pd.DataFrame(value_rows).to_csv(out / "FOCUSED_VALUE_COUNTS.csv", index=False)
    pd.DataFrame(numeric_rows).to_csv(out / "FOCUSED_NUMERIC_SUMMARY.csv", index=False)
    with (out / "AUTODETECTED_FIELDS.json").open("w", encoding="utf-8") as f:
        json.dump(field_map, f, ensure_ascii=False, indent=2)

    submission = tables["submission_master"].copy()
    time_quality_rows: list[dict[str, Any]] = []
    stage_time_rows: list[dict[str, Any]] = []
    if not submission.empty:
        time_cols = match_columns(submission.columns, GROUP_TERMS["time"])
        quality_cols = match_columns(submission.columns, GROUP_TERMS["quality"])
        structural_cols = match_columns(submission.columns, GROUP_TERMS["structural"])
        tnum = numeric_candidates(submission, time_cols)
        qnum = numeric_candidates(submission, quality_cols + structural_cols)
        for tc, tx in tnum.items():
            for qc, qx in qnum.items():
                r, p, n = safe_spearman(tx, qx)
                if n >= 8:
                    time_quality_rows.append({
                        "time_column": tc,
                        "outcome_column": qc,
                        "n": n,
                        "spearman_r": r,
                        "p_value_descriptive_only": p,
                    })
            grouping = [c for c in ["stage", "condition", "dataset_group"] if c in submission.columns]
            if grouping:
                tmp = submission[grouping].copy()
                tmp["time"] = tx
                for keys, grp in tmp.groupby(grouping, dropna=False):
                    if not isinstance(keys, tuple):
                        keys = (keys,)
                    z = grp["time"].dropna()
                    if z.empty:
                        continue
                    row = {g: k for g, k in zip(grouping, keys)}
                    row.update({
                        "time_column": tc,
                        "n": int(z.size),
                        "mean": float(z.mean()),
                        "median": float(z.median()),
                        "p90": float(z.quantile(.90)),
                        "p95": float(z.quantile(.95)),
                        "max": float(z.max()),
                    })
                    stage_time_rows.append(row)
    pd.DataFrame(time_quality_rows).to_csv(out / "TIME_OUTCOME_SPEARMAN.csv", index=False)
    pd.DataFrame(stage_time_rows).to_csv(out / "ACTIVE_TIME_BY_STAGE_CONDITION.csv", index=False)

    profile = tables["pooled_profile"]
    profile_summary: dict[str, Any] = {"rows": int(len(profile)), "numeric_columns": {}}
    if not profile.empty:
        pcols = match_columns(profile.columns, GROUP_TERMS["profile"])
        for c, x in numeric_candidates(profile, pcols, min_nonempty=3).items():
            d = describe_numeric(c, x, "pooled_profile")
            profile_summary["numeric_columns"][c] = d
    with (out / "PROFILE_SPREAD_SUMMARY.json").open("w", encoding="utf-8") as f:
        json.dump(profile_summary, f, ensure_ascii=False, indent=2)

    summary = {
        "status": "focused_schema_and_descriptive_preflight_complete",
        "tables": {k: {"path": TABLES[k], "rows": int(len(v)), "columns": int(len(v.columns))} for k, v in tables.items()},
        "submission_autodetected": field_map.get("submission_master", {}).get("matched", {}),
        "warnings": [
            "P-values in TIME_OUTCOME_SPEARMAN are descriptive and unadjusted; they do not establish causal or out-of-sample value.",
            "Post-task meta labels cannot be used for first assignment; any later predictive test must respect pre-peer timing and outer task/building splits.",
            "Annotator profile spread does not establish reviewer-role transfer. Reviewer efficacy requires a new randomized review-role experiment.",
        ],
    }
    with (out / "STAGE2_SUMMARY.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
