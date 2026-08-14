from __future__ import annotations

import hashlib
import itertools
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "analysis_results" / "c2a_rp_block2_reestimate_20260814_v1"
OUTPUT = Path(__file__).resolve().parent
REGISTRY = ROOT / "analysis_results" / "c2a_rp_local_launch_20260807_inputs_v2"
EXPORTS = [
    ROOT / "export_label" / "c2arp_block2" / "project-84-at-2026-08-14-08-36-31615637.json",
    ROOT / "export_label" / "c2arp_block2" / "project-85-at-2026-08-14-08-36-71fffb37.json",
]
EVIDENCE_PATH = SOURCE / "c2b_plus_c2a_rp_block1_plus_block2_risk_slope_evidence.csv"
BLOCK2_PATH = SOURCE / "c2a_rp_block2_risk_slope_evidence.csv"
ACTIVE_PATH = SOURCE / "c2a_rp_block2_active_time_audit.csv"
CANONICAL_PATH = SOURCE / "c2a_rp_block2_canonical_submissions.csv"
FORMAL_SUMMARY_PATH = SOURCE / "c2a_rp_block2_reestimate_summary.json"
REFERENCE_PATH = REGISTRY / "reference_registry_post_c2_local.csv"
SCOPE_PATH = REGISTRY / "scope_registry_post_c2_local.csv"
CONFLICT_PATH = REGISTRY / "reference_conflict_review_record_post_c2_local.csv"
BOOTSTRAP_SEED = 20260814
BOOTSTRAP_REPLICATES = 1000
DIFFICULTY_TAGS = ["trivial", "occlusion", "low_texture", "seam", "reflection", "low_quality"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def truth(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def worker_id(value: object) -> str:
    text = str(value or "").strip()
    if text.lower().startswith("w"):
        text = text[1:]
    try:
        return str(int(float(text)))
    except ValueError:
        return text


def numeric_frame(frame: pd.DataFrame, fields: list[str]) -> pd.DataFrame:
    for field in fields:
        if field in frame:
            frame[field] = pd.to_numeric(frame[field], errors="coerce")
    return frame


def safe_float(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def quantile(series: pd.Series, q: float) -> float | None:
    values = pd.to_numeric(series, errors="coerce").dropna()
    return safe_float(values.quantile(q)) if len(values) else None


def summary_stats(frame: pd.DataFrame, prefix: str, field: str) -> dict[str, object]:
    values = pd.to_numeric(frame[field], errors="coerce").dropna()
    return {
        f"{prefix}_n": int(len(values)),
        f"{prefix}_mean": safe_float(values.mean()) if len(values) else None,
        f"{prefix}_median": safe_float(values.median()) if len(values) else None,
        f"{prefix}_sd": safe_float(values.std(ddof=1)) if len(values) > 1 else None,
        f"{prefix}_min": safe_float(values.min()) if len(values) else None,
        f"{prefix}_q25": quantile(values, 0.25),
        f"{prefix}_q75": quantile(values, 0.75),
        f"{prefix}_max": safe_float(values.max()) if len(values) else None,
    }


def design_matrix(frame: pd.DataFrame, *, stage: bool = False, building: bool = False) -> tuple[np.ndarray, np.ndarray]:
    local = frame.dropna(subset=["quality", "risk"]).copy()
    worker = pd.get_dummies(local["worker_id"].astype(str), prefix="worker", drop_first=False, dtype=float)
    columns = [worker.reset_index(drop=True)]
    if stage:
        columns.append(pd.get_dummies(local["evidence_stage"].astype(str), prefix="stage", drop_first=True, dtype=float).reset_index(drop=True))
    if building:
        columns.append(pd.get_dummies(local["building_id"].astype(str), prefix="building", drop_first=True, dtype=float).reset_index(drop=True))
    risk = (local["risk"].astype(float) - float(local["risk"].mean())).to_numpy().reshape(-1, 1)
    x = np.column_stack([pd.concat(columns, axis=1).to_numpy(dtype=float), risk])
    return x, local["quality"].to_numpy(dtype=float)


def ols_worker_fe(frame: pd.DataFrame, *, stage: bool = False, building: bool = False) -> dict[str, object]:
    x, y = design_matrix(frame, stage=stage, building=building)
    if len(y) <= x.shape[1] or np.ptp(x[:, -1]) <= 0:
        return {"n": int(len(y)), "status": "insufficient_rank"}
    beta, _, rank, singular = np.linalg.lstsq(x, y, rcond=None)
    residual = y - x @ beta
    dof = len(y) - rank
    mse = float(residual @ residual / dof) if dof > 0 else math.nan
    covariance = mse * np.linalg.pinv(x.T @ x)
    slope_se = math.sqrt(max(0.0, float(covariance[-1, -1]))) if math.isfinite(mse) else math.nan
    total = float(((y - y.mean()) ** 2).sum())
    return {
        "n": int(len(y)),
        "parameters": int(x.shape[1]),
        "rank": int(rank),
        "status": "estimated" if rank == x.shape[1] else "rank_deficient_pseudoinverse",
        "risk_slope": safe_float(beta[-1]),
        "risk_slope_se_classical": safe_float(slope_se),
        "residual_sd": safe_float(math.sqrt(mse)) if math.isfinite(mse) and mse >= 0 else None,
        "r_squared": safe_float(1.0 - float(residual @ residual) / total) if total > 0 else None,
        "condition_number": safe_float(singular[0] / singular[-1]) if len(singular) and singular[-1] > 0 else None,
    }


def cluster_bootstrap(frame: pd.DataFrame, cluster: str, replicates: int) -> dict[str, object]:
    rng = np.random.default_rng(BOOTSTRAP_SEED + sum(ord(char) for char in cluster))
    clusters = sorted(frame[cluster].astype(str).unique())
    grouped = {key: frame[frame[cluster].astype(str) == key] for key in clusters}
    slopes: list[float] = []
    for _ in range(replicates):
        selected = rng.choice(clusters, size=len(clusters), replace=True)
        sampled = pd.concat([grouped[key] for key in selected], ignore_index=True)
        fit = ols_worker_fe(sampled)
        slope = fit.get("risk_slope")
        if slope is not None and math.isfinite(float(slope)):
            slopes.append(float(slope))
    values = np.asarray(slopes, dtype=float)
    return {
        "diagnostic": f"{cluster}_cluster_bootstrap_worker_fe",
        "seed": BOOTSTRAP_SEED,
        "requested_replicates": replicates,
        "successful_replicates": int(len(values)),
        "risk_slope_median": safe_float(np.median(values)) if len(values) else None,
        "risk_slope_q025": safe_float(np.quantile(values, 0.025)) if len(values) else None,
        "risk_slope_q975": safe_float(np.quantile(values, 0.975)) if len(values) else None,
        "role": "diagnostic_only_not_formal_interval",
    }


def direct_slope(frame: pd.DataFrame) -> tuple[float | None, float | None]:
    local = frame.dropna(subset=["quality", "risk"])
    if len(local) < 3 or local["risk"].nunique() < 2:
        return None, None
    x = np.column_stack([np.ones(len(local)), local["risk"].to_numpy(dtype=float)])
    y = local["quality"].to_numpy(dtype=float)
    beta, _, rank, _ = np.linalg.lstsq(x, y, rcond=None)
    if rank < 2:
        return None, None
    residual = y - x @ beta
    dof = len(y) - 2
    mse = float(residual @ residual / dof) if dof > 0 else math.nan
    covariance = mse * np.linalg.pinv(x.T @ x) if math.isfinite(mse) else None
    se = math.sqrt(max(0.0, float(covariance[1, 1]))) if covariance is not None else None
    return safe_float(beta[1]), safe_float(se)


def choices(result: list[dict[str, object]], from_name: str) -> list[str]:
    selected: list[str] = []
    for item in result:
        if item.get("from_name") == from_name:
            selected.extend(str(value) for value in item.get("value", {}).get("choices", []))
    return sorted(set(selected))


def parse_meta() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for path in EXPORTS:
        tasks = json.loads(path.read_text(encoding="utf-8"))
        for task in tasks:
            for annotation in task.get("annotations", []):
                if annotation.get("was_cancelled"):
                    continue
                completed = annotation.get("completed_by")
                if isinstance(completed, dict):
                    completed = completed.get("id") or completed.get("pk")
                result = annotation.get("result", [])
                difficulty = choices(result, "difficulty")
                scope = choices(result, "scope")
                row: dict[str, object] = {
                    "source_export": path.name,
                    "project_id": str(task.get("project", "")),
                    "runtime_task_id": str(task.get("id", "")),
                    "annotation_id": str(annotation.get("id", "")),
                    "worker_id": worker_id(completed),
                    "base_task_id": str(task.get("data", {}).get("base_task_id", "")),
                    "task_stratum": str(task.get("data", {}).get("task_stratum", "")),
                    "scope_choices": ";".join(scope),
                    "difficulty_choices": ";".join(difficulty),
                }
                for tag in DIFFICULTY_TAGS:
                    row[f"tag_{tag}"] = int(tag in difficulty)
                rows.append(row)
    return pd.DataFrame(rows)


def stage_summary(evidence: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    groups: list[tuple[str, str, pd.DataFrame]] = [("CUMULATIVE", "all", evidence)]
    for stage, stage_frame in evidence.groupby("evidence_stage", dropna=False):
        groups.append((str(stage), "all", stage_frame))
        for stratum, stratum_frame in stage_frame.groupby("task_stratum", dropna=False):
            groups.append((str(stage), str(stratum), stratum_frame))
    for stage, stratum, frame in groups:
        eligible = frame[frame["eligible"]]
        row: dict[str, object] = {
            "evidence_stage": stage,
            "task_stratum": stratum,
            "rows_total": int(len(frame)),
            "rows_eligible": int(len(eligible)),
            "rows_not_evaluable": int(len(frame) - len(eligible)),
            "workers": int(frame["worker_id"].nunique()),
            "tasks_total": int(frame["base_task_id"].nunique()),
            "tasks_eligible": int(eligible["base_task_id"].nunique()),
            "buildings_total": int(frame["building_id"].nunique()),
            "buildings_eligible": int(eligible["building_id"].nunique()),
        }
        row.update(summary_stats(eligible, "risk", "risk"))
        row.update(summary_stats(eligible, "quality", "quality"))
        rows.append(row)
    return pd.DataFrame(rows)


def worker_summary(evidence: pd.DataFrame, meta: pd.DataFrame, active: pd.DataFrame) -> pd.DataFrame:
    meta_worker = meta.groupby("worker_id").agg(
        block2_meta_rows=("worker_id", "size"),
        block2_occlusion_yes=("tag_occlusion", "sum"),
        block2_scope_oos=("scope_choices", lambda values: sum("oos" in str(value) for value in values)),
    ).reset_index()
    active_worker = active.groupby("worker_id").agg(
        block2_active_n=("active_seconds", "count"),
        block2_active_median_seconds=("active_seconds", "median"),
        block2_active_max_seconds=("active_seconds", "max"),
        block2_active_flagged=("audit_flags", lambda values: sum(str(value) != "none" for value in values)),
    ).reset_index()
    rows: list[dict[str, object]] = []
    for worker, frame in evidence.groupby("worker_id"):
        eligible = frame[frame["eligible"]]
        slope, slope_se = direct_slope(eligible)
        risks = eligible["risk"].dropna()
        leverage = float(((risks - risks.mean()) ** 2).sum()) if len(risks) else math.nan
        row: dict[str, object] = {
            "worker_id": worker,
            "rows_total": int(len(frame)),
            "rows_eligible": int(len(eligible)),
            "tasks": int(eligible["base_task_id"].nunique()),
            "buildings": int(eligible["building_id"].nunique()),
            "ordinary_n": int((eligible["task_stratum"] == "ordinary").sum()),
            "stress_n": int((eligible["task_stratum"] == "stress").sum()),
            "c2b_n": int((eligible["evidence_stage"] == "C2B").sum()),
            "block1_n": int((eligible["evidence_stage"] == "C2A_RP_BLOCK1").sum()),
            "block2_n": int((eligible["evidence_stage"] == "C2A_RP_BLOCK2").sum()),
            "risk_min": safe_float(risks.min()) if len(risks) else None,
            "risk_max": safe_float(risks.max()) if len(risks) else None,
            "risk_span": safe_float(risks.max() - risks.min()) if len(risks) else None,
            "risk_sd": safe_float(risks.std(ddof=1)) if len(risks) > 1 else None,
            "risk_leverage_sum_sq": safe_float(leverage),
            "quality_mean": safe_float(eligible["quality"].mean()) if len(eligible) else None,
            "quality_median": safe_float(eligible["quality"].median()) if len(eligible) else None,
            "quality_sd": safe_float(eligible["quality"].std(ddof=1)) if len(eligible) > 1 else None,
            "direct_risk_slope_diagnostic": slope,
            "direct_risk_slope_se_diagnostic": slope_se,
        }
        rows.append(row)
    result = pd.DataFrame(rows)
    result = result.merge(meta_worker, on="worker_id", how="left").merge(active_worker, on="worker_id", how="left")
    return result.sort_values("worker_id", key=lambda series: pd.to_numeric(series, errors="coerce"))


def block_pairs(evidence: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    source = evidence[evidence["evidence_stage"].isin(["C2A_RP_BLOCK1", "C2A_RP_BLOCK2"])].copy()
    rows: list[dict[str, object]] = []
    for (block, worker), frame in source.groupby(["block_index", "worker_id"], dropna=False):
        ordinary = frame[(frame["task_stratum"] == "ordinary") & frame["eligible"]]
        stress = frame[(frame["task_stratum"] == "stress") & frame["eligible"]]
        complete = len(ordinary) == 1 and len(stress) == 1
        row: dict[str, object] = {
            "block_index": safe_float(block),
            "worker_id": worker,
            "ordinary_task": ordinary["base_task_id"].iloc[0] if len(ordinary) else None,
            "stress_task": stress["base_task_id"].iloc[0] if len(stress) else None,
            "ordinary_building": ordinary["building_id"].iloc[0] if len(ordinary) else None,
            "stress_building": stress["building_id"].iloc[0] if len(stress) else None,
            "ordinary_risk": safe_float(ordinary["risk"].iloc[0]) if len(ordinary) else None,
            "stress_risk": safe_float(stress["risk"].iloc[0]) if len(stress) else None,
            "ordinary_quality": safe_float(ordinary["quality"].iloc[0]) if len(ordinary) else None,
            "stress_quality": safe_float(stress["quality"].iloc[0]) if len(stress) else None,
            "pair_eligible": complete,
        }
        if complete:
            row["delta_risk_stress_minus_ordinary"] = row["stress_risk"] - row["ordinary_risk"]
            row["delta_quality_stress_minus_ordinary"] = row["stress_quality"] - row["ordinary_quality"]
            delta_risk = row["delta_risk_stress_minus_ordinary"]
            row["pair_slope_delta_quality_over_delta_risk"] = row["delta_quality_stress_minus_ordinary"] / delta_risk if delta_risk else None
        rows.append(row)
    pairs = pd.DataFrame(rows)
    summaries: list[dict[str, object]] = []
    for block, frame in pairs[pairs["pair_eligible"]].groupby("block_index"):
        dr = frame["delta_risk_stress_minus_ordinary"].to_numpy(dtype=float)
        dq = frame["delta_quality_stress_minus_ordinary"].to_numpy(dtype=float)
        denominator = float(dr @ dr)
        slope = float(dr @ dq / denominator) if denominator > 0 else math.nan
        rng = np.random.default_rng(BOOTSTRAP_SEED + int(block))
        boot: list[float] = []
        for _ in range(BOOTSTRAP_REPLICATES):
            indices = rng.integers(0, len(frame), size=len(frame))
            bdr, bdq = dr[indices], dq[indices]
            denom = float(bdr @ bdr)
            if denom > 0:
                boot.append(float(bdr @ bdq / denom))
        summaries.append({
            "block_index": block,
            "complete_pairs": int(len(frame)),
            "mean_delta_risk": safe_float(np.mean(dr)),
            "median_delta_risk": safe_float(np.median(dr)),
            "mean_delta_quality": safe_float(np.mean(dq)),
            "median_delta_quality": safe_float(np.median(dq)),
            "through_origin_pair_slope": safe_float(slope),
            "worker_bootstrap_q025": safe_float(np.quantile(boot, 0.025)) if boot else None,
            "worker_bootstrap_q975": safe_float(np.quantile(boot, 0.975)) if boot else None,
            "bootstrap_seed": BOOTSTRAP_SEED,
            "bootstrap_replicates": BOOTSTRAP_REPLICATES,
            "role": "diagnostic_only_not_formal_interval",
        })
    return pairs, pd.DataFrame(summaries)


def task_summary(evidence: pd.DataFrame, reference: pd.DataFrame, scope: pd.DataFrame, conflict: pd.DataFrame, meta: pd.DataFrame) -> pd.DataFrame:
    conflict_latest = conflict.sort_values("reviewed_at").drop_duplicates("base_task_id", keep="last") if len(conflict) else conflict
    meta_task = meta.groupby("base_task_id").agg(
        meta_rows=("base_task_id", "size"),
        occlusion_rate=("tag_occlusion", "mean"),
        trivial_rate=("tag_trivial", "mean"),
        worker_scope_oos_rate=("scope_choices", lambda values: np.mean(["oos" in str(value) for value in values])),
    ).reset_index()
    rows: list[dict[str, object]] = []
    for task, frame in evidence.groupby("base_task_id"):
        eligible = frame[frame["eligible"]]
        row = {
            "base_task_id": task,
            "evidence_stage": ";".join(sorted(frame["evidence_stage"].astype(str).unique())),
            "building_id": ";".join(sorted(frame["building_id"].astype(str).unique())),
            "task_stratum": ";".join(sorted(frame["task_stratum"].astype(str).unique())),
            "risk": safe_float(frame["risk"].dropna().iloc[0]) if frame["risk"].notna().any() else None,
            "rows_total": int(len(frame)),
            "rows_eligible": int(len(eligible)),
            "workers": int(frame["worker_id"].nunique()),
            "quality_mean": safe_float(eligible["quality"].mean()) if len(eligible) else None,
            "quality_median": safe_float(eligible["quality"].median()) if len(eligible) else None,
            "quality_sd": safe_float(eligible["quality"].std(ddof=1)) if len(eligible) > 1 else None,
            "quality_min": safe_float(eligible["quality"].min()) if len(eligible) else None,
            "quality_max": safe_float(eligible["quality"].max()) if len(eligible) else None,
        }
        rows.append(row)
    result = pd.DataFrame(rows)
    result = result.merge(reference[["base_task_id", "reference_status", "registry_status", "reference_normalizer_status"]], on="base_task_id", how="left")
    result = result.merge(scope[["base_task_id", "final_scope", "scope_review_level", "per_image_human_scope_review"]], on="base_task_id", how="left")
    if len(conflict_latest):
        result = result.merge(conflict_latest[["base_task_id", "review_status", "review_disposition", "issue_type"]], on="base_task_id", how="left")
    result = result.merge(meta_task, on="base_task_id", how="left")
    return result.sort_values(["evidence_stage", "building_id", "base_task_id"])


def building_summary(evidence: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for building, frame in evidence.groupby("building_id"):
        eligible = frame[frame["eligible"]]
        task_level = eligible.groupby("base_task_id", as_index=False).agg(risk=("risk", "first"), quality=("quality", "mean"))
        slope = None
        if len(task_level) >= 3 and task_level["risk"].nunique() >= 2:
            slope, _ = direct_slope(task_level.assign(worker_id="task"))
        rows.append({
            "building_id": building,
            "rows_total": int(len(frame)),
            "rows_eligible": int(len(eligible)),
            "workers": int(eligible["worker_id"].nunique()),
            "tasks": int(eligible["base_task_id"].nunique()),
            "stages": ";".join(sorted(eligible["evidence_stage"].astype(str).unique())),
            "risk_min": safe_float(task_level["risk"].min()) if len(task_level) else None,
            "risk_max": safe_float(task_level["risk"].max()) if len(task_level) else None,
            "risk_span": safe_float(task_level["risk"].max() - task_level["risk"].min()) if len(task_level) else None,
            "quality_mean": safe_float(eligible["quality"].mean()) if len(eligible) else None,
            "quality_sd": safe_float(eligible["quality"].std(ddof=1)) if len(eligible) > 1 else None,
            "task_mean_quality_vs_risk_slope_diagnostic": slope,
        })
    return pd.DataFrame(rows).sort_values("building_id")


def meta_outputs(meta: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    relation_rows: list[dict[str, object]] = []
    for stratum, frame in [("all", meta), *[(str(value), group) for value, group in meta.groupby("task_stratum")]]:
        for tag in DIFFICULTY_TAGS:
            yes = frame[frame[f"tag_{tag}"] == 1]
            no = frame[frame[f"tag_{tag}"] == 0]
            relation_rows.append({
                "task_stratum": stratum,
                "tag": tag,
                "rows": int(len(frame)),
                "yes_n": int(len(yes)),
                "yes_rate": safe_float(len(yes) / len(frame)) if len(frame) else None,
                "quality_yes_mean": safe_float(yes["quality"].mean()) if yes["quality"].notna().any() else None,
                "quality_no_mean": safe_float(no["quality"].mean()) if no["quality"].notna().any() else None,
                "risk_yes_mean": safe_float(yes["risk"].mean()) if yes["risk"].notna().any() else None,
                "risk_no_mean": safe_float(no["risk"].mean()) if no["risk"].notna().any() else None,
                "active_yes_median": safe_float(yes["active_seconds"].median()) if yes["active_seconds"].notna().any() else None,
                "active_no_median": safe_float(no["active_seconds"].median()) if no["active_seconds"].notna().any() else None,
            })
    agreement_rows: list[dict[str, object]] = []
    for task, frame in meta.groupby("base_task_id"):
        row: dict[str, object] = {
            "base_task_id": task,
            "task_stratum": frame["task_stratum"].iloc[0],
            "raters": int(len(frame)),
            "pair_count": int(len(frame) * (len(frame) - 1) / 2),
        }
        pairs = list(itertools.combinations(range(len(frame)), 2))
        for tag in DIFFICULTY_TAGS:
            values = frame[f"tag_{tag}"].to_numpy(dtype=int)
            row[f"{tag}_rate"] = safe_float(values.mean())
            row[f"{tag}_pair_agreement"] = safe_float(np.mean([values[i] == values[j] for i, j in pairs])) if pairs else None
        sets = frame["difficulty_choices"].astype(str).to_numpy()
        row["exact_set_pair_agreement"] = safe_float(np.mean([sets[i] == sets[j] for i, j in pairs])) if pairs else None
        agreement_rows.append(row)
    agreement = pd.DataFrame(agreement_rows)
    repeated = agreement[agreement["pair_count"] > 0]
    overall: list[dict[str, object]] = []
    for tag in DIFFICULTY_TAGS:
        pair_values = repeated[f"{tag}_pair_agreement"].dropna()
        overall.append({
            "metric": f"{tag}_task_equal_pair_agreement",
            "repeated_tasks": int(len(pair_values)),
            "value": safe_float(pair_values.mean()) if len(pair_values) else None,
        })
    exact = repeated["exact_set_pair_agreement"].dropna()
    overall.append({"metric": "exact_difficulty_set_task_equal_pair_agreement", "repeated_tasks": int(len(exact)), "value": safe_float(exact.mean()) if len(exact) else None})
    return pd.DataFrame(relation_rows), agreement, pd.DataFrame(overall)


def active_summary(meta: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    groups = [("all", "all", meta)]
    groups.extend(("task_stratum", str(key), frame) for key, frame in meta.groupby("task_stratum"))
    groups.extend(("audit_flags", str(key), frame) for key, frame in meta.groupby("audit_flags"))
    for dimension, level, frame in groups:
        row = {"dimension": dimension, "level": level, "rows": int(len(frame))}
        row.update(summary_stats(frame, "active_seconds", "active_seconds"))
        rows.append(row)
    return pd.DataFrame(rows)


def scope_summary(meta: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    groups = [("all", meta), *[(str(key), frame) for key, frame in meta.groupby("task_stratum")]]
    for stratum, frame in groups:
        for choice, choice_frame in frame.groupby("scope_choices", dropna=False):
            rows.append({
                "task_stratum": stratum,
                "worker_scope_choices": str(choice),
                "rows": int(len(choice_frame)),
                "row_rate": safe_float(len(choice_frame) / len(frame)) if len(frame) else None,
                "registry_in_scope_rows": int((choice_frame["final_scope"] == "in_scope").sum()),
                "worker_registry_scope_conflict_rows": int(((choice_frame["scope_choices"].str.contains("oos", na=False)) & (choice_frame["final_scope"] == "in_scope")).sum()),
                "quality_mean": safe_float(choice_frame["quality"].mean()) if choice_frame["quality"].notna().any() else None,
                "risk_mean": safe_float(choice_frame["risk"].mean()) if choice_frame["risk"].notna().any() else None,
                "active_seconds_median": safe_float(choice_frame["active_seconds"].median()) if choice_frame["active_seconds"].notna().any() else None,
            })
    return pd.DataFrame(rows)


def formal_model_diagnostics(formal_summary: dict[str, object]) -> pd.DataFrame:
    diagnostics = formal_summary["model_diagnostics"]
    attempts = diagnostics.get("optimizer_attempts", [])
    rows: list[dict[str, object]] = []
    for index, attempt in enumerate(attempts, start=1):
        rows.append({
            "formal_model_status": formal_summary["model_status"],
            "formal_worker_ci_available": formal_summary["worker_ci_reestimate_available"],
            "formal_target_ci_half_width": formal_summary["target_ci_half_width"],
            "boundary_components": ";".join(diagnostics.get("boundary_components", [])),
            "boundary_tolerance": diagnostics.get("boundary_tolerance"),
            "support_workers": diagnostics.get("support", {}).get("worker_id"),
            "support_tasks": diagnostics.get("support", {}).get("base_task_id"),
            "support_buildings": diagnostics.get("support", {}).get("building_id"),
            "optimizer_attempt": index,
            "optimizer": attempt.get("optimizer"),
            "converged": attempt.get("converged"),
            "warnings": " | ".join(attempt.get("warnings", [])),
            "role": "formal_frozen_result_reproduced_not_replaced",
        })
    return pd.DataFrame(rows)


def leave_one_out(evidence: pd.DataFrame, field: str) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for value in sorted(evidence[field].astype(str).unique()):
        fit = ols_worker_fe(evidence[evidence[field].astype(str) != value])
        rows.append({
            "omitted_field": field,
            "omitted_value": value,
            "remaining_rows": fit.get("n"),
            "risk_slope": fit.get("risk_slope"),
            "risk_slope_se_classical": fit.get("risk_slope_se_classical"),
            "status": fit.get("status"),
            "role": "diagnostic_only_not_formal_model",
        })
    return pd.DataFrame(rows)


def save(frame: pd.DataFrame, name: str) -> Path:
    path = OUTPUT / name
    frame.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def main() -> None:
    evidence = pd.read_csv(EVIDENCE_PATH, dtype=str, keep_default_na=False)
    evidence["worker_id"] = evidence["worker_id"].map(worker_id)
    evidence = numeric_frame(evidence, ["risk", "quality", "risk_design_score_A", "Q_GT_raw", "block_index"])
    evidence["eligible"] = evidence["risk_slope_estimand_eligible"].map(truth)
    evidence.loc[(evidence["evidence_stage"] == "C2A_RP_BLOCK1") & evidence["block_index"].isna(), "block_index"] = 1
    evidence.loc[(evidence["evidence_stage"] == "C2A_RP_BLOCK2") & evidence["block_index"].isna(), "block_index"] = 2
    evidence.loc[~evidence["eligible"], "quality"] = pd.to_numeric(evidence.loc[~evidence["eligible"], "quality"], errors="coerce")

    block2 = pd.read_csv(BLOCK2_PATH, dtype=str, keep_default_na=False)
    block2["worker_id"] = block2["worker_id"].map(worker_id)
    block2 = numeric_frame(block2, ["risk", "quality", "project_id", "runtime_task_id", "block_index"])
    block2["eligible"] = block2["risk_slope_estimand_eligible"].map(truth)

    active = pd.read_csv(ACTIVE_PATH, dtype=str, keep_default_na=False)
    active["worker_id"] = active["worker_id"].map(worker_id)
    active = numeric_frame(active, ["project_id", "runtime_task_id", "active_seconds", "event_count", "session_count"])
    canonical = pd.read_csv(CANONICAL_PATH, dtype=str, keep_default_na=False)
    canonical["worker_id"] = canonical["worker_id"].map(worker_id)
    canonical = numeric_frame(canonical, ["project_id", "runtime_task_id", "n_corners", "lead_time_seconds", "active_time"])

    reference = pd.read_csv(REFERENCE_PATH, dtype=str, keep_default_na=False)
    scope = pd.read_csv(SCOPE_PATH, dtype=str, keep_default_na=False)
    conflict = pd.read_csv(CONFLICT_PATH, dtype=str, keep_default_na=False)
    formal_summary = json.loads(FORMAL_SUMMARY_PATH.read_text(encoding="utf-8"))

    meta = parse_meta()
    for frame in (meta,):
        frame["project_id"] = frame["project_id"].astype(str)
        frame["runtime_task_id"] = frame["runtime_task_id"].astype(str)
    block2_join = block2.copy()
    block2_join["project_id"] = block2_join["project_id"].astype("Int64").astype(str)
    block2_join["runtime_task_id"] = block2_join["runtime_task_id"].astype("Int64").astype(str)
    meta = meta.merge(
        block2_join[["project_id", "runtime_task_id", "worker_id", "risk", "quality", "eligible", "eligibility_status", "ineligibility_reason", "building_id"]],
        on=["project_id", "runtime_task_id", "worker_id"], how="left", validate="one_to_one",
    )
    active_join = active.copy()
    active_join["project_id"] = active_join["project_id"].astype("Int64").astype(str)
    active_join["runtime_task_id"] = active_join["runtime_task_id"].astype("Int64").astype(str)
    meta = meta.merge(
        active_join[["project_id", "runtime_task_id", "worker_id", "active_seconds", "audit_flags", "script_versions", "schema_status"]],
        on=["project_id", "runtime_task_id", "worker_id"], how="left", validate="one_to_one",
    )
    canonical_join = canonical.copy()
    canonical_join["project_id"] = canonical_join["project_id"].astype("Int64").astype(str)
    canonical_join["runtime_task_id"] = canonical_join["runtime_task_id"].astype("Int64").astype(str)
    meta = meta.merge(
        canonical_join[["project_id", "runtime_task_id", "worker_id", "n_corners", "parse_error", "canonical_valid"]],
        on=["project_id", "runtime_task_id", "worker_id"], how="left", validate="one_to_one",
    )
    meta = meta.merge(reference[["base_task_id", "reference_status", "registry_status"]], on="base_task_id", how="left")
    meta = meta.merge(scope[["base_task_id", "final_scope", "scope_review_level"]], on="base_task_id", how="left")
    meta["loo_occlusion_other_rate"] = np.nan
    for task, indices in meta.groupby("base_task_id").groups.items():
        task_indices = list(indices)
        if len(task_indices) < 2:
            continue
        for index in task_indices:
            others = [other for other in task_indices if other != index]
            meta.loc[index, "loo_occlusion_other_rate"] = float(meta.loc[others, "tag_occlusion"].mean())

    stage = stage_summary(evidence)
    workers = worker_summary(evidence, meta, active)
    pairs, pair_summary = block_pairs(evidence)
    tasks = task_summary(evidence, reference, scope, conflict, meta)
    buildings = building_summary(evidence)
    meta_relation, meta_agreement, meta_agreement_summary = meta_outputs(meta)
    active_grouped = active_summary(meta)
    scope_grouped = scope_summary(meta)
    model_diagnostics = formal_model_diagnostics(formal_summary)

    sensitivity_rows: list[dict[str, object]] = []
    for name, options in [
        ("worker_fixed_effect", {}),
        ("worker_plus_stage_fixed_effect", {"stage": True}),
        ("worker_plus_building_fixed_effect", {"building": True}),
        ("worker_plus_stage_plus_building_fixed_effect", {"stage": True, "building": True}),
    ]:
        sensitivity_rows.append({"diagnostic": name, **ols_worker_fe(evidence[evidence["eligible"]], **options), "role": "diagnostic_only_not_formal_model"})
    sensitivity_rows.append(cluster_bootstrap(evidence[evidence["eligible"]], "base_task_id", BOOTSTRAP_REPLICATES))
    sensitivity_rows.append(cluster_bootstrap(evidence[evidence["eligible"]], "building_id", BOOTSTRAP_REPLICATES))
    sensitivity = pd.DataFrame(sensitivity_rows)
    leave_building = leave_one_out(evidence[evidence["eligible"]], "building_id")
    leave_task = leave_one_out(evidence[evidence["eligible"]], "base_task_id")

    source_manifest = pd.DataFrame([
        {"source": str(path.relative_to(ROOT)), "sha256": sha256(path), "role": role}
        for path, role in [
            (EVIDENCE_PATH, "cumulative_formal_risk_evidence"),
            (BLOCK2_PATH, "block2_formal_risk_evidence"),
            (ACTIVE_PATH, "block2_auxiliary_active_time"),
            (CANONICAL_PATH, "block2_canonical_submissions"),
            (FORMAL_SUMMARY_PATH, "block2_formal_summary"),
            (REFERENCE_PATH, "frozen_reference_registry"),
            (SCOPE_PATH, "frozen_scope_registry"),
            (CONFLICT_PATH, "reference_conflict_review_record"),
            *[(path, "raw_label_studio_export") for path in EXPORTS],
        ]
    ])

    source_artifact_manifest = json.loads((SOURCE / "artifact_sha256.json").read_text(encoding="utf-8"))
    sha_checks = [
        {
            "check": f"source_artifact_sha::{name}",
            "expected": expected,
            "observed": sha256(SOURCE / name),
            "passed": sha256(SOURCE / name) == expected,
        }
        for name, expected in source_artifact_manifest.items()
    ]
    evidence_reference = evidence.merge(
        reference[["base_task_id", "reference_status", "registry_status", "reference_normalizer_status"]],
        on="base_task_id",
        how="left",
    )
    reference_crosswalk = (
        evidence_reference.loc[evidence_reference["eligible"]]
        .groupby(
            [
                "evidence_stage",
                "base_task_id",
                "reference_registry_sha256",
                "reference_status",
                "registry_status",
                "reference_normalizer_status",
            ],
            dropna=False,
        )
        .agg(eligible_rows=("base_task_id", "size"), workers=("worker_id", "nunique"))
        .reset_index()
    )
    reference_crosswalk["current_registry_public_gt_as_is"] = (
        reference_crosswalk["reference_status"] == "use_existing_public_gt_as_is"
    )
    bound_reference_rows = evidence.loc[evidence["eligible"], "reference_registry_sha256"].astype(str).str.fullmatch(r"[0-9a-f]{64}").sum()
    checks = pd.DataFrame([
        {"check": "block2_rows", "expected": 40, "observed": len(block2), "passed": len(block2) == 40},
        {"check": "block2_workers", "expected": 20, "observed": block2["worker_id"].nunique(), "passed": block2["worker_id"].nunique() == 20},
        {"check": "block2_eligible_rows", "expected": 38, "observed": int(block2["eligible"].sum()), "passed": int(block2["eligible"].sum()) == 38},
        {"check": "block2_active_rows", "expected": 40, "observed": len(active), "passed": len(active) == 40},
        {"check": "block2_meta_rows", "expected": 40, "observed": len(meta), "passed": len(meta) == 40},
        {"check": "cumulative_eligible_rows", "expected": 225, "observed": int(evidence["eligible"].sum()), "passed": int(evidence["eligible"].sum()) == 225},
        {"check": "cumulative_eligible_tasks", "expected": 67, "observed": evidence.loc[evidence["eligible"], "base_task_id"].nunique(), "passed": evidence.loc[evidence["eligible"], "base_task_id"].nunique() == 67},
        {"check": "eligible_rows_with_bound_reference_registry_sha", "expected": 225, "observed": int(bound_reference_rows), "passed": int(bound_reference_rows) == 225},
        {"check": "formal_model_status", "expected": "multiple_variance_components_unidentifiable", "observed": formal_summary["model_status"], "passed": formal_summary["model_status"] == "multiple_variance_components_unidentifiable"},
        {"check": "next_block_generated", "expected": False, "observed": formal_summary["next_block_generated"], "passed": formal_summary["next_block_generated"] is False},
        *sha_checks,
    ])

    outputs = [
        save(stage, "stage_summary.csv"),
        save(workers, "worker_diagnostics.csv"),
        save(pairs, "block_pair_diagnostics.csv"),
        save(pair_summary, "block_pair_summary.csv"),
        save(tasks, "task_diagnostics.csv"),
        save(buildings, "building_diagnostics.csv"),
        save(meta, "block2_meta_rows.csv"),
        save(meta_relation, "block2_meta_relation_summary.csv"),
        save(meta_agreement, "block2_meta_task_agreement.csv"),
        save(meta_agreement_summary, "block2_meta_agreement_summary.csv"),
        save(active_grouped, "block2_active_time_summary.csv"),
        save(scope_grouped, "block2_scope_summary.csv"),
        save(model_diagnostics, "formal_model_diagnostics.csv"),
        save(sensitivity, "risk_sensitivity_summary.csv"),
        save(leave_building, "leave_one_building_out.csv"),
        save(leave_task, "leave_one_task_out.csv"),
        save(source_manifest, "source_manifest.csv"),
        save(reference_crosswalk, "reference_registry_crosswalk.csv"),
        save(checks, "checks.csv"),
        save(evidence, "source_evidence_snapshot.csv"),
    ]

    machine_summary = {
        "schema_version": "c2a_rp_block2_diagnostics_v1",
        "artifact_role": "DIAGNOSTIC_ONLY_NOT_FORMAL_C2_REESTIMATE",
        "formal_model_status_unchanged": formal_summary["model_status"],
        "formal_next_block_generated": formal_summary["next_block_generated"],
        "cumulative": {
            "rows": int(len(evidence)),
            "eligible_rows": int(evidence["eligible"].sum()),
            "workers": int(evidence["worker_id"].nunique()),
            "tasks_total": int(evidence["base_task_id"].nunique()),
            "tasks_eligible": int(evidence.loc[evidence["eligible"], "base_task_id"].nunique()),
            "buildings_total": int(evidence["building_id"].nunique()),
            "buildings_eligible": int(evidence.loc[evidence["eligible"], "building_id"].nunique()),
        },
        "block2": {
            "rows": int(len(block2)),
            "eligible_rows": int(block2["eligible"].sum()),
            "meta_rows": int(len(meta)),
            "active_time_rows": int(len(active)),
        },
        "bootstrap": {"seed": BOOTSTRAP_SEED, "replicates": BOOTSTRAP_REPLICATES},
        "reference_crosswalk": {
            "eligible_rows_current_registry_not_public_gt_as_is": int(
                reference_crosswalk.loc[~reference_crosswalk["current_registry_public_gt_as_is"], "eligible_rows"].sum()
            ),
            "tasks_current_registry_not_public_gt_as_is": int(
                reference_crosswalk.loc[~reference_crosswalk["current_registry_public_gt_as_is"], "base_task_id"].nunique()
            ),
        },
        "checks_passed": bool(checks["passed"].all()),
        "output_sha256": {path.name: sha256(path) for path in outputs},
    }
    summary_path = OUTPUT / "diagnostic_summary.json"
    summary_path.write_text(json.dumps(machine_summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")

    assert len(meta) == 40
    assert int(evidence["eligible"].sum()) == 225
    assert bool(checks["passed"].all())
    assert formal_summary["next_block_generated"] is False
    print(json.dumps({"status": "ok", "outputs": len(outputs) + 1, "summary": str(summary_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
