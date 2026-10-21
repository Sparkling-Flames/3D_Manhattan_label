#!/usr/bin/env python3
"""Read-only integration of distinct frozen personnel methods and coverage.

Writes only this directory. It does not refit, relabel, alter qualification,
execute fusion or replace a historical experiment's original label snapshot.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
ROOT = HERE.parents[3]
TAX = ROOT / "research/workers/personnel_taxonomy_20261021"
MAIN = "51b519f943b2dd3a4fb2f0198133ac5dd17209ab"
INPUTS = {}
UNKNOWN = {"", "unknown", "unassigned", "insufficient_evidence"}
NEW_METHODS = ["MV_QTD_manual", "MV_QTD_manual_new", "MV_QTScopeSemi_semi_new", "MV_TDScopeSemi_manual_new"]
DOMAIN_ORDER = ["Q", "T", "D", "scope", "Semi"]
RECORD_INDEX = ROOT / "research/workers/personnel_profiles_composition_20261020/source/tables/profiles/record_index.csv.gz"


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def source(path): return str(path.relative_to(ROOT))
def readcsv(path, **kwargs):
    INPUTS[source(path)] = sha(path)
    return pd.read_csv(path, **kwargs)
def readjson(path):
    INPUTS[source(path)] = sha(path)
    return json.loads(path.read_text())
def clean(value):
    if isinstance(value, dict): return {str(k): clean(v) for k,v in value.items()}
    if isinstance(value, (list,tuple)): return [clean(v) for v in value]
    if isinstance(value, np.generic): value=value.item()
    if value is None or isinstance(value,float) and not math.isfinite(value): return None
    return value
def js(value): return json.dumps(clean(value),ensure_ascii=False,separators=(",",":"),allow_nan=False)
def dump(name,value): (HERE/name).write_text(json.dumps(clean(value),ensure_ascii=False,indent=2,allow_nan=False)+"\n")
def csv(name,frame): frame.to_csv(HERE/name,index=False,encoding="utf-8-sig")
def text(x): return "" if pd.isna(x) else str(x)
def known(x): return text(x).strip() not in UNKNOWN
def domains(x):
    parts=text(x).replace("Scope","scope").replace("|","+").split("+")
    return "+".join(d for d in DOMAIN_ORDER if d in parts)


def base_row(method, condition, worker, origins, inventory):
    inv=inventory.get((worker,condition),{})
    return dict(method_id=method,condition=condition,worker_id=worker,origin=origins[worker],
        method_condition_key=f"{method}::{condition}",label_snapshot_id="",fit_scope="",heldout_building="",
        classification_form="hierarchy",known=False,coarse_class="unknown",coarse_name_zh="证据不足或适用域外",
        fine_class="unknown",fine_name_zh="证据不足或适用域外",fine_status="unknown",missing_reason="",
        research_role="",domains="",population="",support_json="{}",label_source="",label_source_sha256="",
        source_method_id="",source_label_input_commit="",integration_main=MAIN,
        target_use="display_only_use_validation_index_for_target",validation_index="integration/VALIDATION_LABEL_INDEX.csv",
        formal_eligibility_policy="标签不授予组队或质量评分资格；逐图逐作答沿用冻结资格",
        nonOOS_records=inv.get("nonOOS_records",0),ordinary_pool_eligible_records=inv.get("ordinary_pool_eligible_records",0),
        ordinary_quality_eligible_records=inv.get("ordinary_quality_eligible_records",0),doorway_inventory_records=inv.get("doorway_inventory_records",0),
        historical_worker_exclusion_records=inv.get("historical_worker_exclusion_records",0),
        time_source_kind=inv.get("time_source_kind",""),time_unit="seconds",Semi_cross_condition_auxiliary=False,
        namespace_note="class_id只在method_id、condition、label_snapshot_id和层级内解释")


def labels_and_registry():
    readable_path=STUDY/"multivariate/personnel_labels_readable.csv"
    readable=readcsv(readable_path)
    roster=readable[["worker_id","origin"]].dropna().drop_duplicates().sort_values("worker_id")
    assert len(roster)==62 and roster.worker_id.is_unique
    workers=list(roster.worker_id);origins=dict(zip(roster.worker_id,roster.origin))
    inv=readcsv(STUDY/"multivariate/worker_condition_inventory.csv")
    inventory={(r["worker_id"],r["condition"]):r for r in inv.to_dict("records")}
    rows=[];registry=[]
    for condition, primary in [("manual","M_structure"),("semi","SP_scale")]:
        path=TAX/"labels"/f"{condition}_labels.csv"
        table=readcsv(path,keep_default_na=False)
        assert set(table.worker_id)==set(workers)
        for method in [primary,"A2_relation"]:
            for r in table.to_dict("records"):
                row=base_row(method,condition,r["worker_id"],origins,inventory)
                row.update(label_snapshot_id="taxonomy_20261021_all_data",fit_scope="all_data_descriptive",heldout_building="ALL",
                    label_source=source(path),label_source_sha256=sha(path),source_label_input_commit=r["input_commit"],
                    population="该条件普通非OOS库存；支持和正式资格分别判断",
                    domains="structure" if method=="M_structure" else "position+scale" if method=="SP_scale" else "raw_geometry_relation")
                if method==primary:
                    row.update(known=known(r["primary_coarse_class"]),coarse_class=r["primary_coarse_class"],
                        coarse_name_zh=r["primary_coarse_name_zh"],fine_class=r["primary_fine_class"],
                        fine_name_zh=r["primary_fine_name_zh"],fine_status=r["primary_fine_status"],missing_reason=r["missing_reason"],
                        research_role=r["primary_coarse_status"],source_method_id=r["primary_method"],
                        support_json=js({k:r[k] for k in ["n_images","n_buildings","n_quality_usable","n_independent_vote_eligible","n_records","primary_coarse_lobo_support","primary_coarse_lobo_agreement","primary_fine_lobo_support","primary_fine_lobo_agreement","position_n_train_images","position_n_train_buildings"]}))
                else:
                    row.update(classification_form="flat",known=known(r["geometry_relation_class"]),coarse_class=r["geometry_relation_class"],
                        coarse_name_zh="几何关系类"+r["geometry_relation_class"] if known(r["geometry_relation_class"]) else "证据不足",
                        fine_class="",fine_name_zh="",fine_status="not_defined_flat_partition",missing_reason=r["geometry_missing_reason"],
                        research_role=r["geometry_relation_status"],source_method_id="A2_samecount_source_residual",
                        support_json=js({k:r[k] for k in ["geometry_n_train_images","geometry_n_train_buildings"]}))
                if not row["known"] and not row["missing_reason"]: row["missing_reason"]="source_label_unassigned_reason_not_recorded"
                rows.append(row)
            registry.append(dict(method_id=method,condition=condition,stage="personnel_taxonomy_20261021",classification_form="flat" if method=="A2_relation" else "hierarchy",
                domains=rows[-1]["domains"],fit_scope="all_data_descriptive+leave_building_out",source_method_id=rows[-1]["source_method_id"],
                method_note="A2与M/SP独立；Manual/Semi类别编号互不等同" if method=="A2_relation" else "以原方法层级为准，普通图发现；门洞单列"))
    support_fields=[c for c in readable.columns if c.endswith(("_tasks","_buildings","_records","_supported")) or c in ["support","Q_supported","T_supported","D_supported","Semi_supported","scope_supported","semi_evidence_tier"]]
    for r in readable.to_dict("records"):
        row=base_row(r["method_id"],r["condition"],r["worker_id"],origins,inventory)
        row.update(label_snapshot_id="global_composition_20261021_all_data",fit_scope="all_data_exploratory",heldout_building="ALL",
            known=bool(r["known"]),coarse_class=r["coarse_class"],coarse_name_zh=r["coarse_name_zh"],fine_class=r["fine_class"],fine_name_zh=r["fine_name_zh"],
            fine_status="unsplit_parent" if r["known"] and r["coarse_class"]==r["fine_class"] else "working_subtype" if r["known"] else "unknown",
            missing_reason=text(r["missing_reason"]),research_role=r["research_role"],domains=domains(r["domains"]),
            population="new_source_only" if r["method_id"].endswith("_new") else "all_sources_with_QTD_support",
            support_json=js({k:r[k] for k in support_fields}),label_source=source(readable_path),label_source_sha256=sha(readable_path),
            source_method_id=r["method_id"],time_source_kind=text(r["time_source_kind"]),
            Semi_cross_condition_auxiliary=r["method_id"]=="MV_TDScopeSemi_manual_new")
        if not row["known"] and not row["missing_reason"]: row["missing_reason"]="source_label_unknown_reason_not_recorded"
        rows.append(row)
    for method in NEW_METHODS:
        part=readable[readable.method_id.eq(method)]
        method_note=part.research_role.iloc[0]
        if method=="MV_QTScopeSemi_semi_new":
            method_note += "; Semi细层为描述性/探索用途；22个排除楼折仅11楼有该新批条件记录可删，不作为稳定身份或跨楼Q预测工具"
        registry.append(dict(method_id=method,condition=part.condition.iloc[0],stage="personnel_global_composition_20261021",classification_form="hierarchy",
            domains=domains(part.domains.iloc[0]),fit_scope="all_data_exploratory+leave_building_out",source_method_id=method,
            method_note=method_note))
    legacy_path=ROOT/"research/workers/personnel_interchangeability_followup_20261020/audit_learning/RESEARCH_WORKING_LABELS_60.csv"
    legacy=readcsv(legacy_path,keep_default_na=False).set_index("worker_id")
    receipt=readjson(STUDY/"composition/LEGACY_LABEL_ADAPTER_RECEIPT.json")
    for method in ["Rnew2","F01"]:
        field="Rnew2_geometry_quality_class" if method=="Rnew2" else "F01_efficiency_class"
        source_method="R_directswap_geometry_partition_b2_K2__ordinary_new__mixed_history_v1" if method=="Rnew2" else "F20_highQ23_T_qK2"
        for worker in workers:
            row=base_row(method,"manual",worker,origins,inventory)
            rr=legacy.loc[worker].to_dict() if worker in legacy.index else None
            cl=rr[field] if rr else "unknown";assigned=bool(rr[method+"_known"]) if rr else False
            reason="" if assigned else rr[method+"_reason"] if rr else "not_in_frozen_60_person_history_inventory"
            row.update(label_snapshot_id="interchangeability_history10_d199d7b13dccfe7e",fit_scope="frozen_history10_target12",heldout_building="",
                classification_form="flat",known=assigned,coarse_class=cl,
                coarse_name_zh=("来源内相对快" if cl=="C01" else "来源内相对慢") if method=="F01" and assigned else "冻结历史关系类"+cl if assigned else "证据不足或适用域外",
                fine_class="",fine_name_zh="",fine_status="not_defined_flat_partition",missing_reason=reason,
                research_role="旧条件工作分类；仅限原12目标建筑及普通Manual；不是全数据重拟合",
                domains="actual_replacement_geometry" if method=="Rnew2" else "T;Q_population_gate",
                population="new35" if method=="Rnew2" else "history_highQ23",
                support_json=js({"source_reason":rr[method+"_reason"] if rr else reason,"history_buildings":receipt["training_buildings"],"allowed_target_buildings":receipt["allowed_target_buildings"],"known_people":receipt["method_people"][method]}),
                label_source=source(legacy_path),label_source_sha256=sha(legacy_path),source_method_id=source_method,
                target_use="frozen_history_label_only_on_original_target12_ordinary_manual")
            rows.append(row)
        registry.append(dict(method_id=method,condition="manual",stage="personnel_interchangeability_20261020+followup",classification_form="flat",
            domains=rows[-1]["domains"],fit_scope="frozen_history10_target12",source_method_id=source_method,
            method_note="没有另造ALL全数据标签；10楼删除敏感性不等于22楼外标签"))
    labels=pd.DataFrame(rows).sort_values(["condition","method_id","worker_id"])
    assert len(labels)==620
    assert not labels.duplicated(["method_id","condition","label_snapshot_id","worker_id"]).any()
    assert labels.groupby(["method_id","condition"]).size().eq(62).all()
    assert labels.loc[~labels.known,"missing_reason"].ne("").all()
    csv("PERSONNEL_LABELS_LONG.csv",labels)
    for c in ["manual","semi"]: csv(c.upper()+"_LABELS_LONG.csv",labels[labels.condition.eq(c)])
    csv("WORKER_ROSTER.csv",roster)
    reg=pd.DataFrame(registry).sort_values(["condition","method_id"])
    counts=labels.groupby(["method_id","condition"]).agg(roster_people=("worker_id","size"),known_people=("known","sum")).reset_index()
    reg=reg.merge(counts,validate="one_to_one");csv("METHOD_REGISTRY.csv",reg)
    members=[]
    for (m,c,snap,fit),g in labels[labels.known].groupby(["method_id","condition","label_snapshot_id","fit_scope"]):
        for tier in ["coarse","fine"]:
            for cl,h in g[g[tier+"_class"].ne("")].groupby(tier+"_class"):
                members.append(dict(method_id=m,condition=c,label_snapshot_id=snap,fit_scope=fit,tier="single" if m=="A2_relation" else tier,class_id=cl,
                    name_zh=h[tier+"_name_zh"].iloc[0],people=len(h),members="|".join(sorted(h.worker_id)),
                    source_counts=js(h.origin.value_counts().to_dict())))
    csv("CLASS_MEMBERS.csv",pd.DataFrame(members))
    return labels,reg,workers,receipt


def validation_index(workers, legacy_receipt):
    rows=[]
    record_index=readcsv(RECORD_INDEX,keep_default_na=False)
    new_records=record_index[record_index.origin.eq("new")]
    new_opportunity=new_records.groupby(["condition","building_id"]).size().to_dict()
    path=TAX/"labels/lobo_labels.csv";d=readcsv(path,keep_default_na=False)
    observed_semi=set(d[d.condition.eq("semi")].heldout_building)
    for (condition,building),g in d.groupby(["condition","heldout_building"]):
        for method,field in [("M_structure" if condition=="manual" else "SP_scale","primary_coarse_class"),("A2_relation","geometry_relation_class")]:
            rows.append(dict(method_id=method,condition=condition,heldout_building=building,fit_scope="leave_building_out",label_snapshot_id="taxonomy_20261021_lobo",
                source_path=source(path),source_sha256=sha(path),source_filter=js({"condition":condition,"heldout_building":building}),
                worker_field="worker_id",coarse_field=field,fine_field="primary_fine_class" if method!="A2_relation" else "",
                source_rows=len(g),known_people=int(g[field].map(known).sum()),roster_people=62,
                implicit_missing_workers="|".join(sorted(set(workers)-set(g.worker_id))),target_condition_observed=True,
                use_rule="exact_condition_and_heldout_building; source class IDs unchanged",
                note="原A2专项历史实验须另用route_a原始fold class_id；本索引为taxonomy展示/本轮组成标签" if method=="A2_relation" else "SP_LOW为粗类，SP_L为该粗类下的细类；按tier保留，不互换字段" if method=="SP_scale" else ""))
    for filename in ["labels_lobo.csv.gz","labels_lobo_new_source_sensitivity.csv.gz"]:
        path=STUDY/"multivariate"/filename;d=readcsv(path,keep_default_na=False)
        for (method,condition,building),g in d.groupby(["method_id","condition","heldout_building"]):
            rows.append(dict(method_id=method,condition=condition,heldout_building=building,fit_scope="leave_building_out",label_snapshot_id="global_composition_20261021_lobo",
                source_path=source(path),source_sha256=sha(path),source_filter=js({"method_id":method,"condition":condition,"heldout_building":building}),
                worker_field="worker_id",coarse_field="coarse_class",fine_field="fine_class",source_rows=len(g),known_people=int(g.known.sum()),roster_people=62,
                implicit_missing_workers="|".join(sorted(set(workers)-set(g.worker_id))),target_condition_observed=condition=="manual" or building in observed_semi,
                target_method_population_observed=(condition,building) in new_opportunity if method.endswith("_new") else True,
                target_method_population_scope="new_source_only" if method.endswith("_new") else "all_sources",
                target_method_population_records=int(new_opportunity.get((condition,building),0)) if method.endswith("_new") else int(((record_index.condition==condition)&(record_index.building_id==building)).sum()),
                use_rule="exact_method_condition_and_heldout_building; missing row remains unknown",
                note="target_condition_observed为全来源条件库存；target_method_population_observed另限定方法来源人群。新批Semi22折只有11楼有该条件新批记录可删；空机会折不构成独立验证；W022无Semi原答"))
    path=STUDY/"composition/legacy_composition_labels.csv";d=readcsv(path,keep_default_na=False)
    for (method,condition,building),g in d.groupby(["method_id","condition","heldout_building"]):
        rows.append(dict(method_id=method,condition=condition,heldout_building=building,fit_scope="frozen_history10_target12",label_snapshot_id="interchangeability_history10_d199d7b13dccfe7e",
            source_path=source(path),source_sha256=sha(path),source_filter=js({"method_id":method,"condition":condition,"heldout_building":building}),
            worker_field="worker_id",coarse_field="class_id",fine_field="",source_rows=len(g),known_people=len(g),roster_people=62,
            implicit_missing_workers="|".join(sorted(set(workers)-set(g.worker_id))),target_condition_observed=True,
            use_rule="only_original_target12_ordinary_manual; no refit in target fold",
            note="original_phase="+g.original_target_phase.iloc[0]+"; reused explored checks, not fresh blind test"))
    index=pd.DataFrame(rows).sort_values(["condition","method_id","heldout_building"])
    assert not index.duplicated(["method_id","condition","heldout_building","label_snapshot_id"]).any()
    csv("VALIDATION_LABEL_INDEX.csv",index)
    # The actual experiment snapshot, not a recomputed method_rows(), owns event counts.
    path=STUDY/"composition/FROZEN_LABELS.csv";d=readcsv(path,keep_default_na=False)
    binding=[]
    for (m,t,c),g in d.groupby(["method_id","tier","condition"]):
        binding.append(dict(method_id=m,tier=t,condition=c,source_path=source(path),source_sha256=sha(path),
            source_rows=len(g),buildings=g.heldout_building.nunique(),class_ids="|".join(sorted(g.class_id.unique())),
            exact_join_keys="method_id|tier|condition|heldout_building|worker_id",known_rows_only=True,
            note="该快照决定本轮事件构成；不能以全数据标签或重新生成标签改写原事件"))
    csv("EXPERIMENT_LABEL_BINDINGS.csv",pd.DataFrame(binding))
    csv("LABEL_NAMESPACE_NOTES.csv",pd.DataFrame([
        dict(method_id="SP_scale",condition="semi",tier="coarse_vs_fine",all_data_value="SP_LOW",validation_value="SP_LOW",fine_value="SP_L",
            rule="最终标签及组合快照均为粗层SP_LOW、细层SP_L；SP_OTHER下为SP_A/SP_T。不把粗/细同一角色混成同一字段"),
        dict(method_id="A2_relation",condition="manual|semi",tier="single",all_data_value="A01|A02|A03",validation_value="source_fold_namespace",fine_value="",
            rule="Manual/Semi独立；原route_a专项实验保留raw fold class_id，aligned_class_id为展示；不视作M/SP的子类"),
        dict(method_id="Rnew2|F01",condition="manual",tier="coarse",all_data_value="not_refitted",validation_value="C01|C02",fine_value="",
            rule="同名C01/C02分属不同方法；旧10楼历史冻结仅用于原12目标楼，不构造全22楼验证标签"),
    ]))
    return index


def lobo_active_opportunity():
    """Summarize existing labels only: no fitting and no new evaluation."""
    records=readcsv(RECORD_INDEX,keep_default_na=False)
    counts=records[records.origin.eq("new") & records.condition.eq("semi")].groupby("building_id").size()
    path=STUDY/"multivariate/candidate_lobo_stability.csv"
    d=readcsv(path,keep_default_na=False)
    d=d[d.method_id.eq("MV_QTScopeSemi_semi_new")].copy()
    d["condition"]="semi"
    d["population"]="new_source_only"
    d["target_population_records"]=d.heldout_building.map(counts).fillna(0).astype(int)
    d["active_input_opportunity"]=d.target_population_records.gt(0)
    d["source_stability_path"]=source(path)
    d["source_record_index_path"]=source(RECORD_INDEX)
    d["analysis_status"]="reaggregation_of_existing_stability_no_refitting"
    d=d.sort_values(["level","heldout_building"])
    assert len(d)==44 and d.groupby("level").size().eq(22).all()
    assert d.groupby("level").active_input_opportunity.sum().eq(11).all()
    csv("LOBO_STABILITY_ACTIVE_OPPORTUNITY.csv",d)
    summaries=[]
    for level,g in d.groupby("level"):
        for group,mask in [("all22",pd.Series(True,index=g.index)),("active11",g.active_input_opportunity),("inactive11",~g.active_input_opportunity)]:
            q=g[mask]
            summaries.append(dict(method_id="MV_QTScopeSemi_semi_new",condition="semi",population="new_source_only",level=level,opportunity_group=group,
                buildings=len(q),ARI_mean=float(q.ARI_full_vs_lobo.mean()),ARI_min=float(q.ARI_full_vs_lobo.min()),
                building_ids="|".join(sorted(q.heldout_building))))
    dump("LOBO_STABILITY_ACTIVE_RECEIPT.json",dict(source_stability_path=source(path),source_stability_sha256=sha(path),
        source_record_index_path=source(RECORD_INDEX),source_record_index_sha256=sha(RECORD_INDEX),
        active_records=int(counts.sum()),active_buildings=sorted(counts.index),summary=summaries,
        rule="Active means this held-out building has original new-batch Semi records. Empty folds delete no records for this method population and all have ARI=1. Original 22-fold summaries retain their identity.",
        no_refitting=True,no_new_fusion=True,labels_and_members_unchanged=True))
    return summaries


def domain_coverage(labels, composition_summary):
    old=readcsv(STUDY/"coverage/DOMAIN_SUBSET_COVERAGE.csv",keep_default_na=False)
    ledger=readcsv(STUDY/"coverage/METHOD_DOMAIN_LEDGER.csv",keep_default_na=False)
    new=readcsv(STUDY/"multivariate/domain_subset_26_coverage.csv",keep_default_na=False)
    screen=readcsv(STUDY/"multivariate/domain_subset_screen_labels.csv.gz",keep_default_na=False)
    old["domain_subset"]=old.subset_id.map(domains)
    ledger["normalized_pure"]=ledger.pure_fitted_subset.map(domains)
    ledger["normalized_conditioned"]=ledger.pure_conditioned_subset.map(domains)
    def condition_role(c):
        if c in ["semi_new","semi_v1"]: return "semi"
        if c=="ordinary_manual" or c.startswith("ordinary Manual"): return "manual"
        return "shared_or_other_domain_not_independent_condition"
    ledger["condition_role"]=ledger.condition.map(condition_role)
    actual=readcsv(composition_summary) if composition_summary else None
    if actual is not None:
        required={"method_id","condition","tier","layer","registered_ABC_events","ABC_events_all_endpoints_available","ABC_events_all_three_complete_evaluable","registered_configuration_cells"}
        assert required.issubset(actual.columns)
        assert not actual.duplicated(["method_id","condition","tier","layer"]).any()
        actual_index=actual.copy()
        actual_index["source_path"]=source(composition_summary)
        actual_index["source_sha256"]=sha(composition_summary)
        actual_index["count_rule"]="method/tier/layer registrations; do not sum team counts as a unique-set union; independent near-census endpoints are excluded from designed events"
        actual_index["capacity_note"]=np.where(actual_index.method_id.eq("F01"),"0 ABC events; 6 configuration cells/14 member sets computed; no feasible registered large-block ABC under current population capacity","")
        csv("METHOD_EXECUTION_INDEX.csv",actual_index)
    out=[]
    for r in new.to_dict("records"):
        sub=domains(r["domain_subset"]);condition=r["condition"]
        oldrow=old[old.domain_subset.eq(sub)].iloc[0]
        exact=ledger[ledger.condition_role.eq(condition)]
        shared=ledger[ledger.condition_role.eq("shared_or_other_domain_not_independent_condition")]
        ep=exact[exact.normalized_pure.eq(sub)];ec=exact[exact.normalized_conditioned.eq(sub)]
        sp=shared[shared.normalized_pure.eq(sub)]
        candidates=labels[labels.method_id.isin(NEW_METHODS)&labels.condition.eq(condition)&labels.domains.eq(sub)]
        mids=sorted(candidates.method_id.unique())
        sl=screen[screen.condition.eq(condition)&screen.domain_subset.map(domains).eq(sub)]
        row=dict(condition=condition,domain_subset=sub,domain_count=int(r["domain_count"]),
            legacy_all_conditions_pure_definitions=oldrow.pure_fitted_candidate_definitions,
            legacy_all_conditions_conditioned_definitions=oldrow.pure_population_conditioned_definitions,
            legacy_all_conditions_pure_actual_methods=oldrow.pure_fitted_actual_team_methods,
            legacy_all_conditions_conditioned_actual_methods=oldrow.pure_conditioned_actual_team_methods,
            legacy_exact_condition_pure_definitions=len(ep),legacy_exact_condition_conditioned_definitions=len(ec),
            legacy_exact_condition_pure_actual_methods=int(ep.actual_team_result_stages.ne("").sum()),
            legacy_exact_condition_conditioned_actual_methods=int(ec.actual_team_result_stages.ne("").sum()),
            legacy_shared_other_domain_pure_definitions=len(sp),
            legacy_exact_method_ids="|".join(ep.method_id),legacy_conditioned_method_ids="|".join(ec.method_id),
            legacy_shared_method_ids="|".join(sp.method_id),
            legacy_condition_note="all/easy/hard等原登记不自动视作独立Manual或Semi分类；全阶段总数仅历史引用，不能跨条件相加",
            legacy_independent_check_scope=oldrow.independent_check_scope,
            current_screen_status=r["status"],current_screen_supported_workers=r["supported_workers"],
            current_screen_labels_rows=len(sl),current_screen_folds=sl.heldout_building.nunique(),
            current_screen_class_sizes=r["class_sizes"],current_screen_source_AMI=r["source_AMI"],current_screen_lobo_ARI_median=r["lobo_ARI_median"],
            current_frozen_method_count=len(mids),current_frozen_methods="|".join(mids),
            current_frozen_known_people=js(candidates.groupby("method_id").known.sum().to_dict()),
            current_composition_status="frozen_methods_registered_final_counts_pending" if mids else "screen_only_no_selected_composition_method",
            current_actual_event_count=None,current_available_event_count=None,current_complete_event_count=None,
            current_complete_evaluable_event_count=None,current_any_non_evaluable_event_count=None,
            current_registered_configuration_cells=None,current_computed_configuration_cells=None,
            current_m_ge4_event_count=None,current_by_layer_counts_json="",current_method_team_counts_json="",
            current_actual_methods="",current_composition_count_source="",
            scope_alignment="old Scope and current scope share response-tendency domain only; feature gates, training pools and numerical values are not interchangeable; old QTDS S=structure",
            Semi_interpretation="old confirmed initialization/error vs new reported edit/error opportunities remain separate; Manual Semi domain is cross-condition auxiliary",
            not_full_enumeration="screen labels/frozen methods do not establish full count-vector, member-set or order coverage")
        if actual is not None and mids:
            a=actual[actual.method_id.isin(mids)&actual.condition.eq(condition)]
            row["current_actual_methods"]="|".join(sorted(a.method_id.unique()))
            row["current_composition_status"]="actual_method_summary_attached" if len(a) else "no_actual_summary_rows_for_registered_methods"
            row["current_composition_count_source"]=source(composition_summary)
            row["current_method_team_counts_json"]=js(a.to_dict("records"))
            # Numbers are method/tier/layer incidences, not a deduplicated union of sets.
            metrics={"current_actual_event_count":"registered_ABC_events",
                "current_available_event_count":"ABC_events_all_endpoints_available",
                "current_complete_event_count":"ABC_events_all_three_complete_evaluable",
                "current_complete_evaluable_event_count":"ABC_events_all_three_complete_evaluable",
                "current_any_non_evaluable_event_count":"ABC_events_any_endpoint_not_complete_evaluable",
                "current_registered_configuration_cells":"registered_configuration_cells",
                "current_computed_configuration_cells":"configuration_cells_all_registered_members_computed",
                "current_m_ge4_event_count":"primary_m_ge4_events"}
            for target,field in metrics.items():row[target]=int(a[field].sum())
            by_layer=a.groupby("layer")[list(dict.fromkeys(metrics.values()))].sum().reset_index()
            row["current_by_layer_counts_json"]=js(by_layer.to_dict("records"))
        out.append(row)
    frame=pd.DataFrame(out).sort_values(["condition","domain_count","domain_subset"])
    assert len(frame)==52 and frame.groupby("condition").size().eq(26).all()
    assert frame[frame.condition.eq("manual")].current_screen_status.eq("screened").sum()==26
    assert frame[frame.condition.eq("semi")].current_screen_status.eq("screened").sum()==11
    csv("DOMAIN_SUBSET_COVERAGE_26x2.csv",frame)
    return frame


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--composition-summary",type=Path)
    args=parser.parse_args();HERE.mkdir(exist_ok=True)
    if args.composition_summary is not None:args.composition_summary=args.composition_summary.resolve()
    labels,registry,workers,legacy=labels_and_registry()
    index=validation_index(workers,legacy)
    active_stability=lobo_active_opportunity()
    coverage=domain_coverage(labels,args.composition_summary)
    # All sources must still match after writing; no label mutation is allowed.
    assert all(sha(ROOT/p)==digest for p,digest in INPUTS.items())
    outputs=[p for p in HERE.glob("*.csv")]+[p for p in [HERE/"README_ZH.md",HERE/"FIELD_SCHEMA.json"] if p.exists()]
    dump("INTEGRATION_RECEIPT.json",dict(schema="personnel_method_integration_20261021_v1",input_main=MAIN,
        total_people=62,method_ids=9,method_condition_pairs=len(registry),long_rows=len(labels),
        all_data_rows=int(labels.fit_scope.str.startswith("all_data").sum()),frozen_history_rows=int(labels.fit_scope.eq("frozen_history10_target12").sum()),
        manual_rows=int(labels.condition.eq("manual").sum()),semi_rows=int(labels.condition.eq("semi").sum()),
        validation_index_rows=len(index),domain_coverage_rows=len(coverage),source_sha256=INPUTS,
        semi_active_lobo_stability=active_stability,
        output_sha256={p.name:sha(p) for p in outputs},script_sha256=sha(Path(__file__)),source_labels_unchanged=True,no_refitting_or_fusion=True,
        composition_counts_status="attached_external_summary" if args.composition_summary else "pending_final_completion_not_silently_zero"))
    print(json.dumps(dict(rows=len(labels),methods=len(registry),validation_folds=len(index),domain_rows=len(coverage),
        known=labels.groupby(["method_id","condition"]).known.sum().to_dict().__str__()),ensure_ascii=False))


if __name__=="__main__":main()
