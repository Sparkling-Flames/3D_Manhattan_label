#!/usr/bin/env python3
"""Independent stage-3 preflight for reviewer-role transfer and portrait redesign.

This is an append-only development audit.  It independently re-analyses the
existing P1/C1 Semi proposal-response evidence with two-way worker/task fixed
effects, compares the resulting behavioral dimensions with the frozen three-axis
worker profile, evaluates fixed-feature-set LOOCV, audits language-mirror
identity, and computes reviewer-study sample-size scenarios.

It deliberately does *not* infer peer-review efficacy from model-proposal
handling.  No worker ranking, reviewer tier, dispatch rule, or Main launch is
authorized by this script.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from statsmodels.stats.power import NormalIndPower
from statsmodels.stats.proportion import proportion_effectsize

SEED = 20260819
BOOTSTRAP_DRAWS = 500
RULE_VERSION = "independent_replan_stage3_v1"
FLAGS = {
    "development_only": True,
    "scientific_conclusion_prohibited": True,
    "formal_reviewer_profile_frozen": False,
    "reviewer_policy_frozen": False,
    "main_launch_authorized": False,
}

REVIEW_DIR = Path("analysis_results/reviewer_profile_dual_stage_processing_20260819_v2")
ROW_EVIDENCE = REVIEW_DIR / "SEMI_ROW_LEVEL_REVIEWER_EVIDENCE.csv"
P1_PROFILE = REVIEW_DIR / "P1_REVIEWER_PROFILE.csv"
C1_PROFILE = REVIEW_DIR / "C1_REVIEWER_VALIDATION_PROFILE.csv"
READINESS = REVIEW_DIR / "REVIEWER_PROFILE_READINESS.csv"
OLD_PROFILE = Path("analysis_results/final_calibration_profile_20260817_v1/pooled_worker_profile_v2.csv")
AVAILABILITY = Path("analysis_results/topology_sequential_preflight_20260818_v4_audit/REVIEWER_AVAILABILITY_SENSITIVITY.csv")

OUTCOMES = {
    "delta_u": "delta_U",
    "proposal_accepted_unchanged": "proposal_accepted_unchanged_eps_0",
    "issue_edit_concordance": "issue_geometry_edit_concordant_eps_0",
    "harmful_correction": "harmful_correction_eps_0",
}

P1_FEATURES = [
    "trap_delta_u_mean",
    "strict_blind_trust_rate",
    "detection_youden_index",
    "control_harmful_edit_rate",
]
OLD_FEATURES = ["Q_GT_task_adjusted", "R_peer_stable", "F_struct_EB"]

FIXED_MAPPINGS = [
    ("quality_gain", "trap_delta_u_mean", "delta_u"),
    ("acceptance_low_edit_tendency", "strict_blind_trust_rate", "proposal_accepted_unchanged"),
    ("issue_edit_discrimination", "detection_youden_index", "issue_edit_concordance"),
    ("harmful_intervention_tendency", "control_harmful_edit_rate", "harmful_correction"),
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def truth(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def numeric(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.astype(float)
    mapped = series.map(lambda x: 1.0 if truth(x) else 0.0 if str(x).strip().lower() in {"0", "false", "no", "n"} else np.nan)
    raw = pd.to_numeric(series, errors="coerce")
    return raw.where(raw.notna(), mapped)


def safe_spearman(x: Iterable[Any], y: Iterable[Any]) -> tuple[float | None, float | None, int]:
    a = pd.to_numeric(pd.Series(list(x)), errors="coerce")
    b = pd.to_numeric(pd.Series(list(y)), errors="coerce")
    mask = a.notna() & b.notna()
    n = int(mask.sum())
    if n < 5 or a[mask].nunique() < 2 or b[mask].nunique() < 2:
        return None, None, n
    rho, p = stats.spearmanr(a[mask], b[mask])
    return float(rho), float(p), n


def connected_worker_task_graph(df: pd.DataFrame) -> dict[str, Any]:
    adjacency: dict[str, set[str]] = defaultdict(set)
    for row in df[["worker_id", "base_task_id"]].dropna().itertuples(index=False):
        w, t = f"w:{row.worker_id}", f"t:{row.base_task_id}"
        adjacency[w].add(t)
        adjacency[t].add(w)
    components: list[set[str]] = []
    unseen = set(adjacency)
    while unseen:
        start = next(iter(unseen))
        seen = {start}
        queue = deque([start])
        while queue:
            node = queue.popleft()
            for nxt in adjacency[node]:
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)
        components.append(seen)
        unseen -= seen
    components.sort(key=len, reverse=True)
    return {
        "component_count": len(components),
        "largest_component_nodes": len(components[0]) if components else 0,
        "workers": int(df["worker_id"].nunique()),
        "tasks": int(df["base_task_id"].nunique()),
        "rows": int(len(df)),
        "connected": len(components) == 1,
        "component_sizes": [len(c) for c in components],
    }


def fit_two_way_effects(df: pd.DataFrame, outcome: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    work = df[["worker_id", "base_task_id", outcome]].copy()
    work[outcome] = numeric(work[outcome])
    work = work.dropna()
    work["worker_id"] = work["worker_id"].astype(str)
    work["base_task_id"] = work["base_task_id"].astype(str)
    support = work.groupby("worker_id")[outcome].size().rename("support")
    graph = connected_worker_task_graph(work)
    formula = f"{outcome} ~ C(worker_id) + C(base_task_id)"
    model = smf.ols(formula, data=work).fit()
    workers = sorted(work["worker_id"].unique())
    tasks = sorted(work["base_task_id"].unique())
    grid = pd.DataFrame([(w, t) for w in workers for t in tasks], columns=["worker_id", "base_task_id"])
    grid["prediction"] = model.predict(grid)
    effects = grid.groupby("worker_id", as_index=False)["prediction"].mean().rename(columns={"prediction": f"fe_{outcome}"})
    effects[f"fe_{outcome}"] -= effects[f"fe_{outcome}"].mean()
    effects = effects.merge(support.reset_index(), on="worker_id", how="left")
    diagnostics = {
        "outcome": outcome,
        "formula": formula,
        "rows": int(len(work)),
        "workers": int(len(workers)),
        "tasks": int(len(tasks)),
        "rank": int(model.model.rank),
        "design_columns": int(model.model.exog.shape[1]),
        "condition_number": float(model.condition_number),
        "r_squared": float(model.rsquared),
        "graph": graph,
        "binary_linear_probability_model": bool(set(work[outcome].unique()).issubset({0.0, 1.0})),
        "interpretation": "standardized worker effect under common observed task mix; descriptive only",
    }
    return effects, diagnostics


def bootstrap_mapping(
    c1: pd.DataFrame,
    p1: pd.DataFrame,
    outcome: str,
    p1_feature: str,
    *,
    draws: int = BOOTSTRAP_DRAWS,
    seed: int = SEED,
) -> tuple[float | None, float | None, int]:
    rng = random.Random(seed)
    tasks = sorted(c1["base_task_id"].dropna().astype(str).unique())
    values: list[float] = []
    for draw in range(draws):
        sampled = [rng.choice(tasks) for _ in tasks]
        pieces = []
        for j, task in enumerate(sampled):
            part = c1[c1["base_task_id"].astype(str) == task].copy()
            part["base_task_id"] = f"{task}__boot{j}"
            pieces.append(part)
        boot = pd.concat(pieces, ignore_index=True)
        try:
            effects, _ = fit_two_way_effects(boot, outcome)
        except Exception:
            continue
        merged = p1[["worker_id", p1_feature]].merge(effects[["worker_id", f"fe_{outcome}"]], on="worker_id", how="inner").dropna()
        if len(merged) < 8:
            continue
        sampled_workers = merged.sample(n=len(merged), replace=True, random_state=seed + draw)
        rho, _, n = safe_spearman(sampled_workers[p1_feature], sampled_workers[f"fe_{outcome}"])
        if rho is not None and n >= 8:
            values.append(rho)
    if not values:
        return None, None, 0
    return float(np.quantile(values, .025)), float(np.quantile(values, .975)), len(values)


def loocv_ridge(df: pd.DataFrame, outcome: str, features: list[str]) -> dict[str, Any]:
    cols = ["worker_id", outcome] + features
    data = df[cols].copy()
    for c in [outcome] + features:
        data[c] = pd.to_numeric(data[c], errors="coerce")
    data = data.dropna().reset_index(drop=True)
    if len(data) < max(10, len(features) + 4):
        return {"n": int(len(data)), "status": "insufficient"}
    observed: list[float] = []
    predicted: list[float] = []
    baseline: list[float] = []
    for i in range(len(data)):
        train = data.drop(index=i)
        test = data.iloc[[i]]
        scaler = StandardScaler().fit(train[features])
        x_train = scaler.transform(train[features])
        x_test = scaler.transform(test[features])
        model = Ridge(alpha=1.0).fit(x_train, train[outcome])
        predicted.append(float(model.predict(x_test)[0]))
        baseline.append(float(train[outcome].mean()))
        observed.append(float(test[outcome].iloc[0]))
    obs = np.asarray(observed)
    pred = np.asarray(predicted)
    base = np.asarray(baseline)
    rho, p, _ = safe_spearman(obs, pred)
    return {
        "n": int(len(data)),
        "status": "descriptive_loocv",
        "features": "|".join(features),
        "ridge_alpha": 1.0,
        "rmse": float(np.sqrt(np.mean((obs - pred) ** 2))),
        "mae": float(np.mean(np.abs(obs - pred))),
        "baseline_rmse": float(np.sqrt(np.mean((obs - base) ** 2))),
        "baseline_mae": float(np.mean(np.abs(obs - base))),
        "spearman": rho,
        "spearman_p_descriptive": p,
    }


def wilson_half_width(n: int, p: float, z: float = 1.959963984540054) -> float:
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return float(half)


def language_audit(rows: pd.DataFrame) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for stage in sorted(rows["stage"].dropna().unique()):
        x = rows[rows["stage"] == stage].copy()
        by_language = {}
        for lang, g in x.groupby("language_cohort"):
            by_language[str(lang)] = {
                "rows": int(len(g)),
                "workers": int(g["worker_id"].nunique()),
                "tasks": int(g["base_task_id"].nunique()),
                "worker_ids": sorted(g["worker_id"].astype(str).unique()),
            }
        task_hashes = x.groupby(["base_task_id", "language_cohort"])["initial_geometry_hash"].agg(lambda s: sorted(set(s.dropna().astype(str)))).reset_index()
        pivot = task_hashes.pivot(index="base_task_id", columns="language_cohort", values="initial_geometry_hash")
        languages = sorted(x["language_cohort"].dropna().astype(str).unique())
        paired = 0
        exact = 0
        if len(languages) == 2 and all(lang in pivot.columns for lang in languages):
            complete = pivot.dropna(subset=languages)
            paired = int(len(complete))
            exact = int(sum(complete[languages[0]].map(tuple) == complete[languages[1]].map(tuple)))
        worker_sets = [set(x[x["language_cohort"].astype(str) == lang]["worker_id"].astype(str)) for lang in languages]
        output[str(stage)] = {
            "by_language": by_language,
            "languages": languages,
            "paired_task_count": paired,
            "exact_initial_geometry_task_count": exact,
            "exact_initial_geometry_rate": exact / paired if paired else None,
            "worker_pool_overlap": len(set.intersection(*worker_sets)) if worker_sets else 0,
            "interpretation": "task/proposal mirror identity can be checked; language effect is not identifiable because worker cohorts are not randomized across language",
        }
    return output


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: "" if v is None else v for k, v in row.items()})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path.cwd())
    ap.add_argument("--output-dir", type=Path, required=True)
    args = ap.parse_args()
    root = args.root.resolve()
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)

    paths = {
        "row_evidence": root / ROW_EVIDENCE,
        "p1_profile": root / P1_PROFILE,
        "c1_profile": root / C1_PROFILE,
        "readiness": root / READINESS,
        "old_profile": root / OLD_PROFILE,
        "availability": root / AVAILABILITY,
        "script": Path(__file__).resolve(),
    }
    required = ["row_evidence", "p1_profile", "c1_profile", "readiness", "old_profile"]
    missing = [name for name in required if not paths[name].exists()]
    if missing:
        raise FileNotFoundError(f"missing stage3 inputs: {missing}")

    rows = pd.read_csv(paths["row_evidence"], low_memory=False)
    rows["worker_id"] = rows["worker_id"].astype(str)
    c1 = rows[(rows["stage"] == "C1") & rows["analysis_eligible"].map(truth) & rows["c1_eligible_worker"].map(truth)].copy()
    p1_all = pd.read_csv(paths["p1_profile"], low_memory=False)
    p1 = p1_all[(p1_all["epsilon"] == 0.0) & (p1_all["analysis_cohort"] == "c1_eligible23_primary")].copy()
    p1["worker_id"] = p1["worker_id"].astype(str)
    old = pd.read_csv(paths["old_profile"], low_memory=False)
    old["worker_id"] = old["worker_id"].astype(str)

    effects_tables: list[pd.DataFrame] = []
    diagnostics: list[dict[str, Any]] = []
    associations: list[dict[str, Any]] = []
    for label, column in OUTCOMES.items():
        c1[column] = numeric(c1[column])
        effects, diag = fit_two_way_effects(c1, column)
        effects = effects.rename(columns={f"fe_{column}": f"fe_{label}", "support": f"support_{label}"})
        effects_tables.append(effects)
        diagnostics.append({**diag, "label": label})
    worker_effects = effects_tables[0]
    for table in effects_tables[1:]:
        worker_effects = worker_effects.merge(table, on="worker_id", how="outer")
    worker_effects.to_csv(out / "C1_TWO_WAY_FE_WORKER_EFFECTS.csv", index=False)

    for mapping_id, p1_feature, outcome_label in FIXED_MAPPINGS:
        fe_col = f"fe_{outcome_label}"
        merged = p1[["worker_id", p1_feature]].merge(worker_effects[["worker_id", fe_col]], on="worker_id", how="inner")
        rho, pval, n = safe_spearman(merged[p1_feature], merged[fe_col])
        ci_low, ci_high, valid = bootstrap_mapping(c1, p1, OUTCOMES[outcome_label], p1_feature, seed=SEED + len(associations))
        associations.append({
            "mapping_id": mapping_id,
            "p1_feature": p1_feature,
            "c1_fe_outcome": fe_col,
            "n_workers": n,
            "spearman": rho,
            "p_value_descriptive_only": pval,
            "nested_task_worker_bootstrap_ci_low": ci_low,
            "nested_task_worker_bootstrap_ci_high": ci_high,
            "valid_bootstrap_draws": valid,
            "construct_claim": "behavioral continuity only; not peer-review efficacy",
            **FLAGS,
        })
    write_csv(out / "P1_TO_C1_TWO_WAY_FE_VALIDATION.csv", associations)

    profile = old.merge(p1[["worker_id"] + P1_FEATURES], on="worker_id", how="inner").merge(worker_effects, on="worker_id", how="inner")
    profile.to_csv(out / "WORKER_PROFILE_REDESIGN_JOIN.csv", index=False)

    corr_cols = [c for c in OLD_FEATURES + P1_FEATURES + [f"fe_{x}" for x in OUTCOMES] if c in profile.columns]
    corr_rows: list[dict[str, Any]] = []
    for i, left in enumerate(corr_cols):
        for right in corr_cols[i + 1:]:
            rho, pval, n = safe_spearman(profile[left], profile[right])
            corr_rows.append({"left": left, "right": right, "n": n, "spearman": rho, "p_value_descriptive_only": pval, **FLAGS})
    write_csv(out / "PROFILE_REDUNDANCY_SPEARMAN.csv", corr_rows)

    loocv_rows: list[dict[str, Any]] = []
    for outcome_label in OUTCOMES:
        outcome = f"fe_{outcome_label}"
        for set_name, features in (
            ("intercept_only", []),
            ("old_three_axes", OLD_FEATURES),
            ("p1_proposal_response", P1_FEATURES),
            ("combined", OLD_FEATURES + P1_FEATURES),
        ):
            if not features:
                data = profile[["worker_id", outcome]].dropna().copy()
                obs = data[outcome].to_numpy(float)
                preds = np.array([(obs.sum() - obs[i]) / (len(obs) - 1) for i in range(len(obs))]) if len(obs) > 1 else np.array([])
                result = {
                    "n": int(len(obs)), "status": "descriptive_loocv", "features": "",
                    "rmse": float(np.sqrt(np.mean((obs - preds) ** 2))) if len(preds) else None,
                    "mae": float(np.mean(np.abs(obs - preds))) if len(preds) else None,
                    "baseline_rmse": None, "baseline_mae": None, "spearman": None, "spearman_p_descriptive": None,
                }
            else:
                result = loocv_ridge(profile, outcome, features)
            loocv_rows.append({"outcome": outcome_label, "feature_set": set_name, **result, "interpretation": "construct redundancy and future-study planning only; not prospective C1 validation", **FLAGS})
    write_csv(out / "PROFILE_INCREMENTAL_LOOCV.csv", loocv_rows)

    language = language_audit(rows)
    (out / "LANGUAGE_MIRROR_AUDIT.json").write_text(json.dumps(language, ensure_ascii=False, indent=2), encoding="utf-8")

    identifiability = {
        "actual_peer_layout_review_observed": False,
        "reviewer_first_committed_independent_judgment_observed": False,
        "anonymous_peer_candidates_observed": False,
        "majority_support_hidden_or_randomized_observed": False,
        "approve_reject_reannotate_action_observed": False,
        "expert_adjudicated_reviewer_success_observed": False,
        "reviewer_selection_randomized": False,
        "extra_independent_annotation_counterfactual_observed": False,
        "existing_estimand": "response to a single model initialization in P1/C1 Semi tasks",
        "identifiable_from_existing_data": [
            "proposal acceptance/low-edit tendency",
            "issue-report/edit concordance",
            "quality change after editing",
            "harmful intervention on control or proposal tasks",
        ],
        "not_identifiable_from_existing_data": [
            "peer-review efficacy",
            "ability to choose among multiple human layouts",
            "resistance to crowd-majority conformity",
            "benefit of profile-qualified reviewer selection",
            "review versus sixth independent annotation",
            "scope/portal adjudication after candidate exposure",
        ],
        "decision": "existing data support a proposal-response profile hypothesis, not a reviewer role claim",
        **FLAGS,
    }
    if paths["availability"].exists():
        identifiability["reviewer_availability_source"] = str(AVAILABILITY)
        identifiability["availability_only_not_efficacy"] = True
    (out / "REVIEWER_ROLE_IDENTIFIABILITY.json").write_text(json.dumps(identifiability, ensure_ascii=False, indent=2), encoding="utf-8")

    sample_rows: list[dict[str, Any]] = []
    for n in [6, 12, 18, 25, 40, 60, 100]:
        for p in [0.5, 0.75, 0.9]:
            sample_rows.append({"scenario_type": "per_worker_wilson_precision", "n": n, "assumed_rate": p, "wilson_95_half_width": wilson_half_width(n, p), "notes": "single binary profile component; ignores task clustering"})
    power_solver = NormalIndPower()
    for p0 in [0.55, 0.65, 0.75]:
        for delta in [0.10, 0.15, 0.20]:
            p1_rate = min(0.99, p0 + delta)
            effect = abs(proportion_effectsize(p1_rate, p0))
            for target_power in [0.80, 0.90]:
                raw_n = float(power_solver.solve_power(effect_size=effect, alpha=0.05, power=target_power, ratio=1.0, alternative="two-sided"))
                for deff in [1.0, 1.2, 1.5]:
                    n_arm = int(math.ceil(raw_n * deff))
                    sample_rows.append({
                        "scenario_type": "two_arm_binary_reviewer_trial",
                        "baseline_rate": p0, "target_rate": p1_rate, "absolute_delta": delta,
                        "target_power": target_power, "design_effect": deff,
                        "n_per_arm": n_arm, "flagged_tasks_total_two_arm": 2 * n_arm,
                        "base_tasks_needed_at_reach5_0_3684": int(math.ceil(2 * n_arm / 0.3684)),
                        "notes": "conservative independent-proportion approximation; paired same-task design may require fewer tasks depending on discordance",
                    })
    for flagged_target in [30, 60, 90, 120, 180]:
        for flagged_rate in [0.20, 0.3684, 0.50]:
            sample_rows.append({
                "scenario_type": "flagged_task_yield",
                "flagged_task_target": flagged_target,
                "assumed_flagged_rate": flagged_rate,
                "base_tasks_needed": int(math.ceil(flagged_target / flagged_rate)),
                "notes": "natural reach-k5/flag rate must be estimated prospectively; enriched counterexample sampling changes target population",
            })
    for total_actions in [60, 120, 180, 300]:
        for pool_size in [4, 6, 8, 10]:
            sample_rows.append({
                "scenario_type": "reviewer_workload",
                "total_review_actions": total_actions,
                "reviewer_pool_size": pool_size,
                "mean_actions_per_reviewer": total_actions / pool_size,
                "notes": "balance target; actual assignment must respect task exposure and independence",
            })
    write_csv(out / "REVIEWER_STUDY_SAMPLE_SIZE_SCENARIOS.csv", sample_rows)

    summary = {
        "rule_version": RULE_VERSION,
        "input_denominators": {
            "c1_row_evidence": int(len(c1)),
            "c1_workers": int(c1["worker_id"].nunique()),
            "c1_tasks": int(c1["base_task_id"].nunique()),
            "p1_primary_workers": int(p1["worker_id"].nunique()),
            "profile_join_workers": int(len(profile)),
        },
        "two_way_fe_diagnostics": diagnostics,
        "fixed_mapping_results": associations,
        "language_mirror": language,
        "independent_decisions": {
            "prescreen_has_incremental_research_value": "yes_for_proposal_response_hypotheses",
            "semi_is_equivalent_to_peer_review": "no",
            "semi_can_motivate_role_transfer_test": "yes",
            "existing_three_axis_profile_should_be_discarded": "no",
            "existing_three_axis_profile_should_be_sufficient_alone": "no",
            "recommended_portrait_redesign": "modular: competence + scope/topology + proposal-response; never one scalar",
            "profile_selected_reviewer_ready_for_main": "no",
            "reviewer_role_randomized_study_needed": "yes",
        },
        "critical_limitations": [
            "Model-initialization response and peer-layout adjudication are different roles and information conditions.",
            "C1 two-way fixed effects remain development estimates from a sparse observational worker-task graph.",
            "P1 issue-family support is only 2-5 tasks per worker-family cell and cannot support fine-grained individual family tiers.",
            "Old three-axis fields are partly estimated from C1 and therefore their comparison with C1 Semi behavior is construct-redundancy analysis, not prospective prediction.",
            "Language cohorts use mirrored task/proposal content but disjoint worker cohorts, so language effects are confounded with worker composition.",
        ],
        **FLAGS,
    }
    (out / "STAGE3_INDEPENDENT_PREFLIGHT_SUMMARY.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    report = f"""# 独立 reviewer / worker-profile Stage-3 preflight\n\n## 结论\n\n现有数据支持一个可复现的 **proposal-response behavior** 构念，但不支持把它直接解释为 peer reviewer ability。Prescreen 与 C1 的单模型 proposal 任务显示，接受/少编辑、issue–edit discrimination、以及有害干预倾向具有跨阶段连续性；真正的质量改进连续性仍不稳定。\n\n因此，现有三轴画像不应删除，而应从单一总分改造成三个模块：\n\n1. independent annotation competence：Q_GT / R_peer / F_struct；\n2. scope–topology reasoning：范围、portal、overextension/undercoverage；\n3. proposal-response behavior：acceptance inertia、issue discrimination、correction utility、harmful intervention。\n\n第三模块只能产生 reviewer-candidate hypothesis，不能授权 reviewer selection。同行复核必须通过新的 blinded role-transfer randomized experiment 识别。\n\n## 推荐新实验\n\n对达到冻结 disagreement/cap 条件的任务随机：\n\n- A：第六名工人独立完整重标；\n- B：普通 qualified reviewer；\n- C：profile-qualified reviewer。\n\n所有 reviewer 先只看 panorama 并提交独立 scope/topology 判断，再查看匿名随机排序的候选布局；隐藏 worker identity、profile、support count 和 majority。随后允许 approve one、reject all 或 reannotate。\n\n该试验同时区分 review mode 与 profile qualification；若只比较 profile reviewer 与普通 reviewer，无法判断 review 本身是否优于新增独立标注。\n\n## 状态\n\n- existing-data reviewer efficacy: NOT IDENTIFIABLE\n- proposal-response portrait hypothesis: DEVELOPMENT SUPPORTED\n- profile-qualified reviewer in Main: NO-GO\n- randomized role-transfer study: CONDITIONAL GO\n\n所有输出均为 development-only，禁止用于 reviewer 排名、tier、dispatch 或 Main launch。\n"""
    (out / "STAGE3_INDEPENDENT_PREFLIGHT_REPORT.md").write_text(report, encoding="utf-8")

    output_files = [
        "C1_TWO_WAY_FE_WORKER_EFFECTS.csv",
        "P1_TO_C1_TWO_WAY_FE_VALIDATION.csv",
        "WORKER_PROFILE_REDESIGN_JOIN.csv",
        "PROFILE_REDUNDANCY_SPEARMAN.csv",
        "PROFILE_INCREMENTAL_LOOCV.csv",
        "LANGUAGE_MIRROR_AUDIT.json",
        "REVIEWER_ROLE_IDENTIFIABILITY.json",
        "REVIEWER_STUDY_SAMPLE_SIZE_SCENARIOS.csv",
        "STAGE3_INDEPENDENT_PREFLIGHT_SUMMARY.json",
        "STAGE3_INDEPENDENT_PREFLIGHT_REPORT.md",
    ]
    manifest = {
        "rule_version": RULE_VERSION,
        "seed": SEED,
        "bootstrap_draws": BOOTSTRAP_DRAWS,
        "inputs": {name: {"path": str(path.relative_to(root)) if path.is_relative_to(root) else str(path), "sha256": sha256(path)} for name, path in paths.items() if path.exists()},
        "outputs": {name: sha256(out / name) for name in output_files},
        **FLAGS,
    }
    (out / "STAGE3_INDEPENDENT_PREFLIGHT_MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
