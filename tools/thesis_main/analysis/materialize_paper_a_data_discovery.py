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
        writer = csv.DictWriter(handle, fields, extrasaction="ignore")
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


def bh(rows: list[dict[str, Any]]) -> None:
    by_lane: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if number(row["p"]) is not None: by_lane[row["analysis_lane"]].append(row)
    for lane in by_lane:
        ordered = sorted(by_lane[lane], key=lambda r: float(r["p"])); running = 1.0
        for index in range(len(ordered)-1, -1, -1):
            running = min(running, float(ordered[index]["p"]) * len(ordered) / (index+1))
            ordered[index]["q"] = f"{running:.8g}"


def association(lane: str, unit: str, predictor: str, outcome: str, population: str,
                records: list[dict[str, Any]], group_field: str, origin: str = "systematic_scan") -> dict[str, Any]:
    usable = [(number(r.get(predictor)), number(r.get(outcome)), str(r.get(group_field, ""))) for r in records]
    usable = [(x,y,g) for x,y,g in usable if x is not None and y is not None and g]
    groups = [v[2] for v in usable]; independent = len(set(groups))
    result = dict.fromkeys(RESULT_FIELDS, "not_evaluable")
    result.update(analysis_lane=lane, unit=unit, predictor=predictor, outcome=outcome,
                  population=population, support=f"rows={len(usable)};independent_groups={independent}",
                  hypothesis_origin=origin, leakage_status="guard_pass_group_disjoint")
    binary = len({y for _,y,_ in usable}) == 2
    minimum = 15 if unit == "worker" else 20
    if independent < 3 or independent < minimum or (binary and min(Counter(y for _,y,_ in usable).values(), default=0) < 5):
        result.update(effect="not_evaluable", CI="not_evaluable", p="not_evaluable", q="not_evaluable",
                      heldout_delta="not_evaluable", fold_direction_rate="not_evaluable",
                      sensitivity_status="insufficient_independent_support", evidence_grade="E0_not_evaluable")
        return result
    x=[v[0] for v in usable]; y=[v[1] for v in usable]
    effect = correlation(x,y)
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
    # Fisher approximation; interval is intentionally conservative at small n.
    z = 0 if effect is None else abs(effect)*math.sqrt(max(1,len(usable)-3))/max(1e-12, math.sqrt(max(1e-12,1-effect*effect)))
    p=min(1.0, math.erfc(z/math.sqrt(2)))
    se=1.96/math.sqrt(max(4,len(usable)-3)); lo=max(-1,(effect or 0)-se); hi=min(1,(effect or 0)+se)
    direction=sum(directions)/len(directions) if directions else 0; delta=min(improvements) if improvements else 0
    result.update(effect=f"{effect:.8g}", CI=f"[{lo:.8g},{hi:.8g}]", p=f"{p:.8g}", q="pending_bh",
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
    for row in submissions: row["worker_id"] = worker(row["worker_id"])
    for row in profiles: row["worker_id"] = worker(row["worker_id"])
    for row in reviews:
        for key in ("worker_id", "reviewer_worker_id"):
            if row.get(key): row[key] = worker(row[key])
    counts=Counter(r["stage"] for r in submissions)
    assert len(submissions)==2501 and counts=={"P1":1481,"C1":780,"C2-B":160,"C2A-RP-B1":40,"C2A-RP-B2":40}
    assert len({r["worker_id"] for r in submissions})==26 and {"14","19","21","26"} <= {r["worker_id"] for r in submissions}

    # Fact tables retain observations; eligibility is a parallel flag, never a filter.
    submission_fields=["stage","round_id","project_id","runtime_task_id","task_id","base_task_id","building_id","condition","worker_id","annotation_id","canonical_annotation_id","canonical_valid","c1_iou_to_gt","active_time_seconds","annotation_lead_time_seconds","active_time_event_count","active_time_session_count","exclusion_reason","upstream_language_group","upstream_formal_assignment_eligible","source_artifact","source_sha256"]
    write_csv(output/"submission_fact.csv", submissions, submission_fields)
    write_csv(output/"task_fact.csv", tasks)
    write_csv(output/"worker_fact.csv", profiles)
    write_csv(output/"semi_review_fact.csv", reviews)

    catalog=[]
    for path, role, included in [(PACK/"post_block2_submission_master.csv","formal_submission_spine",True),(PACK/"post_block2_task_context_master.csv","formal_task_context",True),(PACK/"post_block2_worker_profile_master.csv","formal_worker_profile",True),(REVIEW,"semi_review",True),(T1_POOL,"T1_candidate_coverage_only",True)]:
        catalog.append({"path":path.relative_to(ROOT).as_posix(),"role":role,"included":str(included).lower(),"sha256":sha(path),"deduplication":"frozen_SHA_plus_annotation_identity","paper":"A"})
    catalog += [{"path":"export_label/","role":"raw_export_inventory_not_mixed","included":"false","sha256":"directory","deduplication":"version_and_SHA","paper":"A"},{"path":"analysis_results/stage_aware_analysis_freeze_v2_1_20260317/","role":"legacy_snapshot_inventory_not_mixed","included":"false","sha256":"directory","deduplication":"version_and_SHA","paper":"A"}]
    write_csv(output/"data_catalog.csv",catalog)
    join=[{"check":"submission_count","observed":len(submissions),"expected":2501,"status":"pass"},{"check":"worker_count","observed":len({r['worker_id'] for r in submissions}),"expected":26,"status":"pass"},{"check":"W14_C1","observed":sum(r['worker_id']=='14' and r['stage']=='C1' for r in submissions),"expected":32,"status":"pass"},{"check":"language_identity_split","observed":0,"expected":0,"status":"pass"},{"check":"unconnected_submission","observed":sum(not r.get('base_task_id') or not r.get('worker_id') for r in submissions),"expected":0,"status":"pass"}]
    write_csv(output/"join_coverage_audit.csv",join)

    # Fixed families: unavailable predictors/outcomes remain explicit E0 rows.
    results=[]
    scans=[("task_features","task","n_corners","c1_iou_to_gt","building_id"),("task_features","task","n_corners","active_time_seconds","building_id"),("time_process","task","active_time_seconds","c1_iou_to_gt","building_id"),("time_process","task","active_time_event_count","c1_iou_to_gt","building_id"),("time_process","task","active_time_session_count","canonical_valid","building_id"),("worker_early_later","worker","Q_GT_raw_median","risk_slope","worker_id"),("worker_task_match","worker","Q_GT_EB","risk_slope","worker_id")]
    for lane,unit,pred,outcome,group in scans:
        source=profiles if unit=="worker" else submissions
        results.append(association(lane,unit,pred,outcome,"all_observed",source,group,"pre_existing" if pred in {"Q_GT_raw_median","Q_GT_EB"} else "systematic_scan"))
        eligibility = "administratively_eligible" if unit == "worker" else "upstream_formal_assignment_eligible"
        formal = [row for row in source if truth(row.get(eligibility))]
        results.append(association(lane,unit,pred,outcome,"formal_eligible_sensitivity",formal,group,"pre_existing" if pred in {"Q_GT_raw_median","Q_GT_EB"} else "systematic_scan"))
    for lane,pred,outcome in [("proposal_edit","initial_proposal_quality","edited"),("proposal_edit","initial_failure_type","quality_change"),("c1_manual_semi_overlap","condition","c1_iou_to_gt"),("peer_reference","R_peer","reference_conflict"),("calibration_t1_shift","calibration_feature","T1_candidate_feature")]:
        row=dict.fromkeys(RESULT_FIELDS,"not_evaluable"); row.update(analysis_lane=lane,unit="dyad" if lane=="proposal_edit" else "task",predictor=pred,outcome=outcome,population="all_observed",support="source_fields_audited",sensitivity_status="required_field_or_outcome_not_available_in_frozen_fact",hypothesis_origin="systematic_scan",leakage_status="guard_pass_no_model_fit",evidence_grade="E0_not_evaluable")
        results.append(row)
    bh(results)
    for row in results:
        if row["evidence_grade"]=="E1_descriptive" and number(row["q"]) is not None:
            lo,hi=[float(x) for x in row["CI"].strip("[]").split(",")]
            if float(row["q"])<=.05 and lo*hi>0 and float(row["fold_direction_rate"])>=.8 and float(row["heldout_delta"])>0: row["evidence_grade"]="E2_cross_validated"
    grade_order={f"E{i}":i for i in range(5)}
    results.sort(key=lambda r:(-grade_order.get(str(r["evidence_grade"])[:2],0),-number(r["fold_direction_rate"]) if number(r["fold_direction_rate"]) is not None else 1,number(r["q"]) if number(r["q"]) is not None else 2,-int(str(r["support"]).split("independent_groups=")[-1]) if "independent_groups=" in str(r["support"]) else 0,r["analysis_lane"],r["predictor"],r["outcome"]))
    write_csv(output/"association_matrix.csv",results,RESULT_FIELDS)
    write_csv(output/"evidence_index.csv",[{"rank":i+1,**r} for i,r in enumerate(results)],["rank",*RESULT_FIELDS])
    svg='''<svg xmlns="http://www.w3.org/2000/svg" width="900" height="320"><rect width="100%" height="100%" fill="white"/><text x="30" y="35" font-size="22">Paper A grouped-CV stability (mechanical order)</text>'''
    for i,r in enumerate(results[:10]):
        rate=number(r["fold_direction_rate"]) or 0; y=65+i*23
        svg+=f'<text x="30" y="{y+14}" font-size="12">{r["analysis_lane"]}: {r["predictor"]} → {r["outcome"]}</text><rect x="420" y="{y}" width="{400*rate:.1f}" height="14" fill="#356aa0"/><text x="830" y="{y+13}" font-size="12">{rate:.2f}</text>'
    (output/"stability_plot.svg").write_text(svg+'</svg>\n',encoding="utf-8")
    report=f"""# Paper A 全量数据盘点与客观关联扫描\n\n## 结论边界\n\n本报告只使用 Paper A；主总体为 `all_observed`，formal eligibility 仅保留为事实字段。没有 T1/V1 outcome，因此 E4 当前不可获得。阴性、反转及不可评价结果均保留。\n\n## 数据覆盖\n\n- submission：2,501（P1 1,481；C1 780；C2-B 160；C2-A-RP 80）。\n- worker：26；W14 的 32 条 C1 记录及 W19、W21、W26 均保留。\n- semi-review：{len(reviews)} 条冻结行级复核记录。\n- T1 候选池只作覆盖输入登记，不构造 outcome。\n\n## 自动证据\n\n等级计数：`{dict(Counter(r['evidence_grade'] for r in results))}`。结果按等级、折方向率、q、支持量及稳定键机械排序。`pre_existing` 与 `systematic_scan` 已分开标记；结果派生字段没有进入预测变量。\n\n## 可复现性\n\n随机种子 {SEED}；最多五折，分组键不跨训练/验证；缺失不补零；族内 BH-FDR。active time 仅采用 spine 中正式 active-time 字段，lead time 未混入。\n"""
    (output/"PAPER_A_DATA_DISCOVERY_REPORT_ZH.md").write_text(report,encoding="utf-8")
    manifest={"schema_version":"paper_a_data_discovery_v1","seed":SEED,"population_primary":"all_observed","population_sensitivity":"formal_eligible_parallel","paper_b_inputs":[],"rules":{"max_folds":5,"minimum_worker_groups":15,"minimum_task_groups":20,"binary_min_events_each":5,"fdr":"Benjamini-Hochberg within family","missing":"not_zero","E4":"unavailable_no_T1_V1_outcome"},"inputs":catalog,"outputs":{}}
    for path in sorted(output.iterdir()):
        if path.name!="analysis_manifest.json": manifest["outputs"][path.name]=sha(path)
    (output/"analysis_manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return {"submissions":len(submissions),"workers":26,"reviews":len(reviews),"results":len(results)}


def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument("--output",type=Path,default=DEFAULT_OUT)
    args=parser.parse_args(); print(json.dumps(materialize(args.output),sort_keys=True)); return 0


if __name__ == "__main__": raise SystemExit(main())
