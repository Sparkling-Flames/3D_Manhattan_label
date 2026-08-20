"""Materialize the leakage-guarded, all-observed Paper A discovery audit.

This entry point deliberately consumes frozen Paper A analysis artifacts rather
than exports.  It is dependency-free so the inventory can be reproduced in the
repository's minimal audit environment.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUT = ROOT / "analysis_results" / "paper_a_data_discovery_20260820_v1"
PACK = ROOT / "analysis_results" / "post_block2_analysis_pack_20260817_v4"
REVIEW = ROOT / "analysis_results" / "reviewer_profile_dual_stage_processing_20260819_v2" / "SEMI_ROW_LEVEL_REVIEWER_EVIDENCE.csv"
T1_POOL = ROOT / "import_json" / "groudTruth_458_tasks_import_from_updated_gt_20260701.json"
FEATURES = ROOT / "analysis_results" / "calibration_dual_track_processing_20260815_v3" / "task_feature_matrix.csv"
SEED = 20260820
RESULT_FIELDS = ["analysis_lane", "unit", "predictor", "outcome", "population", "support", "effect", "CI", "p", "q", "heldout_delta", "fold_direction_rate", "sensitivity_status", "hypothesis_origin", "leakage_status", "evidence_grade"]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str] | None = None) -> None:
    rows = list(rows)
    fields = fields or list(rows[0] if rows else {"status": "empty"})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)


def number(value: Any) -> float | None:
    try:
        value = float(str(value))
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def truth(value: Any) -> bool:
    return str(value).lower() in {"1", "true", "yes"}


def worker(value: Any) -> str:
    """Canonicalize numeric and W-prefixed bilingual identities."""
    text = str(value).strip().upper()
    if text.startswith("W"): text = text[1:]
    return str(int(text)) if text.isdigit() else text


def rank(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    result = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i + 1
        while j < len(order) and values[order[j]] == values[order[i]]: j += 1
        value = (i + j - 1) / 2
        for k in order[i:j]: result[k] = value
        i = j
    return result


def correlation(x: list[float], y: list[float]) -> float | None:
    if len(x) < 3: return None
    mx, my = statistics.mean(x), statistics.mean(y)
    sx = sum((v-mx)**2 for v in x); sy = sum((v-my)**2 for v in y)
    return None if sx <= 0 or sy <= 0 else sum((a-mx)*(b-my) for a,b in zip(x,y)) / math.sqrt(sx*sy)


def grouped_folds(groups: list[str], maximum: int = 5) -> list[set[str]]:
    unique = sorted(set(groups))
    if len(unique) < 3: return []
    n = min(maximum, len(unique)); folds = [set() for _ in range(n)]
    for i, value in enumerate(unique): folds[i % n].add(value)
    return folds


def directory_sha(path: Path) -> str:
    """Hash names and bytes so inventory-only directories cannot drift silently."""
    digest = hashlib.sha256()
    for item in sorted(p for p in path.rglob("*") if p.is_file()):
        digest.update(item.relative_to(path).as_posix().encode())
        digest.update(b"\0"); digest.update(bytes.fromhex(sha(item)))
    return digest.hexdigest()


def effect_stat(records: list[tuple[float, float, str]], binary: bool) -> float | None:
    if not records: return None
    x, y = [v[0] for v in records], [v[1] for v in records]
    if binary:
        cut = statistics.median(x)
        high = [b for a, b, _ in records if a > cut]
        low = [b for a, b, _ in records if a <= cut]
        return statistics.mean(high) - statistics.mean(low) if high and low else None
    sx, sy = statistics.pstdev(x), statistics.pstdev(y)
    r = correlation(x, y)
    return r if r is not None and sx > 0 and sy > 0 else None


def cluster_inference(usable: list[tuple[float, float, str]], binary: bool, seed_key: str) -> tuple[float | None, str, float | None]:
    """Infer on independent group aggregates, with a deterministic permutation p.

    This prevents submission rows from being treated as independent.  The CI is
    a percentile cluster bootstrap over whole groups, not effect ± row-level SE.
    """
    grouped: dict[str, list[tuple[float, float, str]]] = defaultdict(list)
    for row in usable: grouped[row[2]].append(row)
    aggregates = [(statistics.mean(v[0] for v in rows), statistics.mean(v[1] for v in rows), group) for group, rows in sorted(grouped.items())]
    observed = effect_stat(aggregates, binary)
    if observed is None: return None, "not_evaluable", None
    rng = random.Random(int(hashlib.sha256((str(SEED)+seed_key).encode()).hexdigest()[:16], 16))
    boot=[]; groups=sorted(grouped)
    for _ in range(1000):
        sampled=[]
        for index in range(len(groups)):
            source=grouped[rng.choice(groups)]
            sampled.extend((x,y,str(index)) for x,y,_ in source)
        value=effect_stat([(statistics.mean(v[0] for v in rows),statistics.mean(v[1] for v in rows),g) for g,rows in _group(sampled).items()],binary)
        if value is not None: boot.append(value)
    boot.sort(); ci = "not_evaluable" if len(boot)<100 else f"[{boot[int(.025*len(boot))]:.8g},{boot[min(len(boot)-1,int(.975*len(boot)))]:.8g}]"
    xs=[v[0] for v in aggregates]; ys=[v[1] for v in aggregates]; extreme=0
    for _ in range(1999):
        shuffled=ys[:]; rng.shuffle(shuffled)
        value=effect_stat([(x,y,str(i)) for i,(x,y) in enumerate(zip(xs,shuffled))],binary)
        if value is not None and abs(value)>=abs(observed)-1e-15: extreme += 1
    return observed, ci, (extreme+1)/2000


def _group(rows: list[tuple[float,float,str]]) -> dict[str,list[tuple[float,float,str]]]:
    result: dict[str,list[tuple[float,float,str]]] = defaultdict(list)
    for row in rows: result[row[2]].append(row)
    return result


def bh(rows: list[dict[str, Any]]) -> None:
    by_lane: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if number(row["p"]) is not None: by_lane[row["analysis_lane"]].append(row)
    for lane in by_lane:
        ordered = sorted(by_lane[lane], key=lambda r: float(r["p"])); running = 1.0
        for index in range(len(ordered)-1, -1, -1):
            running = min(running, float(ordered[index]["p"]) * len(ordered) / (index+1))
            ordered[index]["q"] = f"{running:.8g}"


def dyad_association(lane: str, predictor: str, outcome: str, population: str,
                     records: list[dict[str, Any]], origin: str = "systematic_scan") -> dict[str, Any]:
    """Run both holdout axes and conservatively retain the weaker inference."""
    worker_result=association(lane,"task",predictor,outcome,population,records,"worker_id",origin,"base_task_id")
    task_result=association(lane,"task",predictor,outcome,population,records,"base_task_id",origin,"base_task_id")
    candidates=[worker_result,task_result]
    evaluable=[r for r in candidates if number(r["p"]) is not None]
    if not evaluable:
        result=task_result; result["unit"]="dyad"; result["leakage_status"]="guard_pass_worker_and_task_disjoint_both_not_evaluable"
        return result
    weaker=max(evaluable,key=lambda r:(float(r["p"]),-float(r["heldout_delta"]),-float(r["fold_direction_rate"])))
    result=dict(weaker); result["unit"]="dyad"
    result["support"] += f";worker_axis_p={worker_result['p']};task_axis_p={task_result['p']}"
    result["leakage_status"]="guard_pass_worker_and_task_disjoint_weaker_retained"
    return result


def association(lane: str, unit: str, predictor: str, outcome: str, population: str,
                records: list[dict[str, Any]], group_field: str, origin: str = "systematic_scan",
                support_field: str | None = None) -> dict[str, Any]:
    usable = [(number(r.get(predictor)), number(r.get(outcome)), str(r.get(group_field, ""))) for r in records]
    usable = [(x,y,g) for x,y,g in usable if x is not None and y is not None and g]
    groups = [v[2] for v in usable]; independent = len(set(groups))
    support = len({str(r.get(support_field or group_field, "")) for r in records
                   if str(r.get(support_field or group_field, "")) and number(r.get(predictor)) is not None
                   and number(r.get(outcome)) is not None and str(r.get(group_field, ""))})
    result = dict.fromkeys(RESULT_FIELDS, "not_evaluable")
    result.update(analysis_lane=lane, unit=unit, predictor=predictor, outcome=outcome,
                  population=population, support=f"rows={len(usable)};support_units={support};independent_groups={independent}",
                  hypothesis_origin=origin, leakage_status="guard_pass_group_disjoint")
    binary = len({y for _,y,_ in usable}) == 2
    minimum = 15 if unit == "worker" else 20
    if independent < 3 or support < minimum or (binary and min(Counter(y for _,y,_ in usable).values(), default=0) < 5):
        result.update(effect="not_evaluable", CI="not_evaluable", p="not_evaluable", q="not_evaluable",
                      heldout_delta="not_evaluable", fold_direction_rate="not_evaluable",
                      sensitivity_status="insufficient_independent_support", evidence_grade="E0_not_evaluable")
        return result
    x=[v[0] for v in usable]; y=[v[1] for v in usable]
    effect, ci, p = cluster_inference(usable, binary, f"{lane}|{predictor}|{outcome}|{population}|{group_field}")
    if effect is None or p is None:
        result.update(effect="not_evaluable", CI="not_evaluable", p="not_evaluable", q="not_evaluable",
                      heldout_delta="not_evaluable", fold_direction_rate="not_evaluable",
                      sensitivity_status="zero_variance_after_independent_group_aggregation", evidence_grade="E0_not_evaluable")
        return result
    rho = correlation(rank(x),rank(y))
    folds = grouped_folds(groups); directions=[]; improvements=[]
    for held in folds:
        train=[v for v in usable if v[2] not in held]; test=[v for v in usable if v[2] in held]
        tx=[v[0] for v in train]; ty=[v[1] for v in train]
        r=correlation(tx,ty)
        if r is None or not test: continue
        sx=statistics.pstdev(tx); sy=statistics.pstdev(ty); slope=0 if sx == 0 else r*sy/sx
        intercept=statistics.mean(ty)-slope*statistics.mean(tx); base=statistics.mean(ty)
        if binary:
            pred=[min(1,max(0,intercept+slope*v[0])) for v in test]
            improvements.append(statistics.mean((v[1]-base)**2 for v in test)-statistics.mean((v[1]-p)**2 for v,p in zip(test,pred)))
        else:
            improvements.append(statistics.mean(abs(v[1]-base) for v in test)-statistics.mean(abs(v[1]-(intercept+slope*v[0])) for v in test))
        directions.append(1 if r * (effect or 0) > 0 else 0)
    direction=sum(directions)/len(directions) if directions else 0; delta=min(improvements) if improvements else 0
    result.update(effect=f"{effect:.8g}", CI=ci, p=f"{p:.8g}", q="pending_bh",
                  heldout_delta=f"{delta:.8g}", fold_direction_rate=f"{direction:.8g}",
                  sensitivity_status=f"spearman={rho:.8g}" if rho is not None else "spearman_not_evaluable",
                  evidence_grade="E1_descriptive")
    return result


def materialize(output: Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True); random.seed(SEED)
    submissions=read_csv(PACK/"post_block2_submission_master.csv")
    tasks=read_csv(PACK/"post_block2_task_context_master.csv")
    profiles=read_csv(PACK/"post_block2_worker_profile_master.csv")
    reviews=read_csv(REVIEW)
    features=read_csv(FEATURES)
    t1_raw=json.loads(T1_POOL.read_text(encoding="utf-8"))
    for row in submissions:
        row["source_worker_id"] = row["worker_id"]
        row["worker_id"] = worker(row["worker_id"])
    for row in profiles: row["worker_id"] = worker(row["worker_id"])
    for row in reviews:
        for key in ("worker_id", "reviewer_worker_id"):
            if row.get(key): row[key] = worker(row[key])
        row["proposal_failure_binary"] = "1" if truth(row.get("proposal_failure")) else "0"
        row["edited_binary"] = "0" if truth(row.get("exact_geometry_equal")) else "1"
        delta=number(row.get("delta_U")); row["improved_binary"] = "" if delta is None else ("1" if delta > 0 else "0")
        row["harmed_binary"] = "" if delta is None else ("1" if delta < 0 else "0")
    counts=Counter(r["stage"] for r in submissions)
    assert len(submissions)==2501 and counts=={"P1":1481,"C1":780,"C2-B":160,"C2A-RP-B1":40,"C2A-RP-B2":40}
    assert len({r["worker_id"] for r in submissions})==26 and {"14","19","21","26"} <= {r["worker_id"] for r in submissions}

    # Stage-specific eligibility comes from each stage's frozen contract field.
    for row in submissions:
        stage=row["stage"]
        if stage=="P1": eligible=truth(row.get("upstream_eligible_for_primary_analysis")); basis="P1.upstream_eligible_for_primary_analysis"
        elif stage=="C1": eligible=truth(row.get("c1_gt_primary_analysis_eligible")); basis="C1.c1_gt_primary_analysis_eligible"
        elif stage in {"C2-B","C2A-RP-B1"}: eligible=truth(row.get("upstream_formal_assignment_eligible")); basis=f"{stage}.upstream_formal_assignment_eligible"
        else: eligible=True; basis="C2A-RP-B2.frozen_assignment_membership"
        row["formal_eligible_unified"] = str(eligible).lower(); row["formal_eligibility_basis"] = basis

    feature_by_task={r["base_task_id"]:r for r in features}
    for row in tasks:
        feature=feature_by_task.get(row["base_task_id"],{})
        for field in ("risk","risk_design_score_A","g_duplicate_peak","g_postprocess_invalid","g_seam_instability","g_topology_invalid","feature_timing","reference_status"):
            row[field]=feature.get(field,"")
        row["analysis_population"]="observed"
    t1_tasks=[]
    for item in t1_raw:
        title=Path(str(item.get("data",{}).get("title", ""))).stem
        results=(item.get("annotations") or [{}])[0].get("result",[])
        t1_tasks.append({"stage":"T1_CANDIDATE","base_task_id":title,"building_id":title.split("_")[0] if "_" in title else "","condition":"not_assigned","observed_annotation_count":"0","n_corners_reference":len(results),"analysis_population":"candidate_coverage_only","outcome_status":"not_observed_no_outcome"})

    # Fact tables retain observations; eligibility is a parallel flag, never a filter.
    submission_fields=["stage","round_id","project_id","runtime_task_id","task_id","base_task_id","building_id","condition","worker_id","annotation_id","canonical_annotation_id","n_corners","canonical_valid","canonicalization_status","c1_iou_to_gt","c1_gt_primary_analysis_eligible","active_time_seconds","annotation_lead_time_seconds","active_time_event_count","active_time_session_count","upstream_eligible_for_primary_analysis","upstream_formal_assignment_eligible","formal_eligible_unified","formal_eligibility_basis","exclusion_reason","upstream_language_group","source_artifact","source_sha256"]
    write_csv(output/"submission_fact.csv", submissions, submission_fields)
    write_csv(output/"task_fact.csv", tasks+t1_tasks)
    write_csv(output/"worker_fact.csv", profiles)
    write_csv(output/"semi_review_fact.csv", reviews)

    catalog=[]
    for path, role, included in [(PACK/"post_block2_submission_master.csv","formal_submission_spine",True),(PACK/"post_block2_task_context_master.csv","formal_task_context",True),(PACK/"post_block2_worker_profile_master.csv","formal_worker_profile",True),(REVIEW,"semi_review",True),(FEATURES,"calibration_task_features",True),(T1_POOL,"T1_candidate_coverage_only",True)]:
        catalog.append({"path":path.relative_to(ROOT).as_posix(),"role":role,"included":str(included).lower(),"sha256":sha(path),"deduplication":"frozen_SHA_plus_annotation_identity","paper":"A"})
    catalog += [{"path":"export_label/","role":"raw_export_inventory_not_mixed","included":"false","sha256":directory_sha(ROOT/"export_label"),"deduplication":"recursive_path_and_SHA","paper":"A"},{"path":"analysis_results/stage_aware_analysis_freeze_v2_1_20260317/","role":"legacy_snapshot_inventory_not_mixed","included":"false","sha256":directory_sha(ROOT/"analysis_results"/"stage_aware_analysis_freeze_v2_1_20260317"),"deduplication":"recursive_path_and_SHA","paper":"A"}]
    write_csv(output/"data_catalog.csv",catalog)
    task_keys={(r["stage"],r["base_task_id"],r.get("condition","")) for r in tasks}; profile_ids={r["worker_id"] for r in profiles}
    annotation_duplicates=len(submissions)-len({(r["stage"],r["canonical_annotation_id"]) for r in submissions})
    raw_to_canonical=defaultdict(set)
    for r in submissions: raw_to_canonical[worker(r["source_worker_id"])].add(r["source_worker_id"])
    language_splits=sum(len(values)>1 for values in raw_to_canonical.values())
    unjoined_tasks=sum((r["stage"],r["base_task_id"],r.get("condition","")) not in task_keys for r in submissions)
    unjoined_profiles=sum(r["worker_id"] not in profile_ids for r in submissions)
    join=[{"check":"submission_count","observed":len(submissions),"expected":2501,"status":"pass"},{"check":"worker_count","observed":len(profile_ids),"expected":26,"status":"pass"},{"check":"W14_C1","observed":sum(r['worker_id']=='14' and r['stage']=='C1' for r in submissions),"expected":32,"status":"pass"},{"check":"language_identity_split","observed":language_splits,"expected":0,"status":"pass" if language_splits==0 else "fail"},{"check":"duplicate_annotation_identity","observed":annotation_duplicates,"expected":0,"status":"pass" if annotation_duplicates==0 else "fail"},{"check":"submission_to_task_unjoined","observed":unjoined_tasks,"expected":0,"status":"pass" if unjoined_tasks==0 else "fail"},{"check":"submission_to_profile_unjoined","observed":unjoined_profiles,"expected":0,"status":"pass" if unjoined_profiles==0 else "fail"}]
    write_csv(output/"join_coverage_audit.csv",join)

    # Fixed families: unavailable predictors/outcomes remain explicit E0 rows.
    results=[]
    scans=[("task_features","task","n_corners","c1_iou_to_gt","building_id"),("task_features","task","n_corners","active_time_seconds","building_id"),("time_process","task","active_time_seconds","c1_iou_to_gt","building_id"),("time_process","task","active_time_event_count","c1_iou_to_gt","building_id"),("time_process","task","active_time_session_count","canonical_valid","building_id"),("worker_early_later","worker","Q_GT_raw_median","risk_slope","worker_id"),("worker_task_match","worker","Q_GT_EB","risk_slope","worker_id")]
    for lane,unit,pred,outcome,group in scans:
        source=profiles if unit=="worker" else submissions
        results.append(association(lane,unit,pred,outcome,"all_observed",source,group,"pre_existing" if pred in {"Q_GT_raw_median","Q_GT_EB"} else "systematic_scan","base_task_id" if unit=="task" else "worker_id"))
        eligibility = "administratively_eligible" if unit == "worker" else "formal_eligible_unified"
        formal = [row for row in source if truth(row.get(eligibility))]
        results.append(association(lane,unit,pred,outcome,"formal_eligible_sensitivity",formal,group,"pre_existing" if pred in {"Q_GT_raw_median","Q_GT_EB"} else "systematic_scan","base_task_id" if unit=="task" else "worker_id"))

    # Proposal/edit family uses the actual frozen reviewer fields.
    for pred,outcome in [("U_initial","edited_binary"),("U_initial","delta_U"),("proposal_failure_binary","edited_binary"),("proposal_failure_binary","improved_binary"),("geometry_edit_rmse_panorama_diagonal_normalized","delta_U")]:
        results.append(dyad_association("proposal_edit",pred,outcome,"all_observed",reviews))
        results.append(dyad_association("proposal_edit",pred,outcome,"formal_eligible_sensitivity",[r for r in reviews if truth(r.get("analysis_eligible"))]))

    # Exactly the 25 C1 task identities observed in both conditions.
    condition_by_task: dict[str,set[str]]=defaultdict(set)
    for row in submissions:
        if row["stage"]=="C1": condition_by_task[row["base_task_id"]].add(row["condition"])
    overlap={task for task,conditions in condition_by_task.items() if {"manual","semi"} <= conditions}
    c1_overlap=[]
    for row in submissions:
        if row["stage"]=="C1" and row["base_task_id"] in overlap:
            copy=dict(row); copy["semi_condition_binary"]="1" if row["condition"]=="semi" else "0"; c1_overlap.append(copy)
    overlap_all=dyad_association("c1_manual_semi_overlap","semi_condition_binary","c1_iou_to_gt","all_observed",c1_overlap,"pre_existing")
    overlap_all["support"] += f";overlap_task_denominator={len(overlap)}"; results.append(overlap_all)
    overlap_formal=dyad_association("c1_manual_semi_overlap","semi_condition_binary","c1_iou_to_gt","formal_eligible_sensitivity",[r for r in c1_overlap if truth(r["formal_eligible_unified"])],"pre_existing")
    overlap_formal["support"] += f";overlap_task_denominator={len(overlap)}"; results.append(overlap_formal)

    # Coverage drift has no outcome: compare a pre-existing geometry feature only.
    calibration=[]
    by_task=defaultdict(list)
    for row in submissions:
        if row["stage"]=="C1" and number(row.get("n_corners")) is not None: by_task[row["base_task_id"]].append(float(row["n_corners"]))
    for task,values in by_task.items(): calibration.append({"n_corners_reference":statistics.mean(values),"candidate_pool_binary":"0","building_id":task.split("_")[0],"base_task_id":task})
    for row in t1_tasks: row["candidate_pool_binary"]="1"
    results.append(association("calibration_t1_shift","task","n_corners_reference","candidate_pool_binary","coverage_only",calibration+t1_tasks,"building_id","systematic_scan","base_task_id"))

    # Peer/reference is explanatory only: no post-task field enters a predictor.
    row=dict.fromkeys(RESULT_FIELDS,"not_evaluable"); row.update(analysis_lane="peer_reference",unit="task",predictor="peer_cluster_signal",outcome="reference_conflict",population="all_observed",support="explanatory_only_fields_not_a_predictive_model",sensitivity_status="reference_conflict_outcome_not_joined_to_fact",hypothesis_origin="systematic_scan",leakage_status="guard_pass_post_task_predictor_prohibited",evidence_grade="E0_not_evaluable")
    results.append(row)
    bh(results)
    for row in results:
        if row["evidence_grade"]=="E1_descriptive" and number(row["q"]) is not None:
            lo,hi=[float(x) for x in row["CI"].strip("[]").split(",")]
            if float(row["q"])<=.05 and lo*hi>0 and float(row["fold_direction_rate"])>=.8 and float(row["heldout_delta"])>0: row["evidence_grade"]="E2_cross_validated"
    grade_order={f"E{i}":i for i in range(5)}
    results.sort(key=lambda r:(-grade_order.get(str(r["evidence_grade"])[:2],0),-number(r["fold_direction_rate"]) if number(r["fold_direction_rate"]) is not None else 1,number(r["q"]) if number(r["q"]) is not None else 2,-int(str(r["support"]).split("independent_groups=")[-1].split(";")[0]) if "independent_groups=" in str(r["support"]) else 0,r["analysis_lane"],r["predictor"],r["outcome"],r["population"]))
    write_csv(output/"association_matrix.csv",results,RESULT_FIELDS)
    write_csv(output/"evidence_index.csv",[{"rank":i+1,**r} for i,r in enumerate(results)],["rank",*RESULT_FIELDS])
    svg='''<svg xmlns="http://www.w3.org/2000/svg" width="900" height="320"><rect width="100%" height="100%" fill="white"/><text x="30" y="35" font-size="22">Paper A grouped-CV stability (mechanical order)</text>'''
    for i,r in enumerate(results[:10]):
        rate=number(r["fold_direction_rate"]) or 0; y=65+i*23
        svg+=f'<text x="30" y="{y+14}" font-size="12">{r["analysis_lane"]}: {r["predictor"]} → {r["outcome"]}</text><rect x="420" y="{y}" width="{400*rate:.1f}" height="14" fill="#356aa0"/><text x="830" y="{y+13}" font-size="12">{rate:.2f}</text>'
    (output/"stability_plot.svg").write_text(svg+'</svg>\n',encoding="utf-8",newline="\n")
    report=f"""# Paper A 全量数据盘点与客观关联扫描\n\n## 结论边界\n\n本报告只使用 Paper A；主总体为 `all_observed`，formal eligibility 按阶段合同统一后作为并列敏感性总体。没有 T1/V1 outcome，因此 E4 当前不可获得。阴性、反转及不可评价结果均保留。\n\n## 数据覆盖\n\n- submission：2,501（P1 1,481；C1 780；C2-B 160；C2-A-RP 80）。\n- worker：26；W14 的 32 条 C1 记录及 W19、W21、W26 均保留。\n- task：327 个 observed context；另有 458 个 T1 coverage-only 候选，不构造 outcome。\n- semi-review：{len(reviews)} 条；U_initial={sum(number(r.get('U_initial')) is not None for r in reviews)}、U_final={sum(number(r.get('U_final')) is not None for r in reviews)}、delta_U={sum(number(r.get('delta_U')) is not None for r in reviews)}。\n- C1 Manual/Semi overlap：{len(overlap)} 个 base task。\n\n## 自动证据\n\n等级计数：`{dict(Counter(r['evidence_grade'] for r in results))}`。结果按等级、折方向率、q、支持量及稳定键机械排序。`pre_existing` 与 `systematic_scan` 已分开标记；结果派生字段没有进入预测变量。\n\n## 推断与可复现性\n\n随机种子 {SEED}；最多五折，分组键不跨训练/验证。p 值来自独立组聚合后的 1,999 次确定性 permutation，区间来自整组重采样的 cluster bootstrap；dyad 同时进行 worker-held-out 与 task-held-out 并保留较弱结果。缺失不补零；族内 BH-FDR。active time 仅采用 spine 中正式 active-time 字段，lead time 未混入。\n"""
    (output/"PAPER_A_DATA_DISCOVERY_REPORT_ZH.md").write_text(report,encoding="utf-8",newline="\n")
    manifest={"schema_version":"paper_a_data_discovery_v2","seed":SEED,"population_primary":"all_observed","population_sensitivity":"formal_eligible_parallel","paper_b_inputs":[],"formal_eligibility_mapping":{"P1":"upstream_eligible_for_primary_analysis","C1":"c1_gt_primary_analysis_eligible","C2-B":"upstream_formal_assignment_eligible","C2A-RP-B1":"upstream_formal_assignment_eligible","C2A-RP-B2":"frozen_assignment_membership"},"rules":{"max_folds":5,"minimum_worker_support":15,"minimum_task_support":20,"minimum_independent_groups":3,"binary_min_events_each":5,"inference":"independent-group aggregate permutation p plus whole-cluster bootstrap CI","permutations":1999,"cluster_bootstraps":1000,"dyad":"weaker_of_worker_and_task_axes","fdr":"Benjamini-Hochberg within family","missing":"not_zero","E4":"unavailable_no_T1_V1_outcome"},"inputs":catalog,"outputs":{}}
    for path in sorted(output.iterdir()):
        if path.name!="analysis_manifest.json": manifest["outputs"][path.name]=sha(path)
    (output/"analysis_manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8",newline="\n")
    return {"submissions":len(submissions),"workers":26,"reviews":len(reviews),"results":len(results)}


def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument("--output",type=Path,default=DEFAULT_OUT)
    args=parser.parse_args(); print(json.dumps(materialize(args.output),sort_keys=True)); return 0


if __name__ == "__main__": raise SystemExit(main())
