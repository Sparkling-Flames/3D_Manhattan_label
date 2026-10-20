#!/usr/bin/env python3
"""Create readable class names and audit exact frozen-label reconstruction.

This script only writes explanation/audit files. Frozen worker_labels and
method_manifest are read-only. It does not fit fusion outcomes.
"""
from __future__ import annotations

import argparse
import gzip
import itertools
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from audit_and_features import BASE, clean, js, load_module, sha
from build_candidates import define_candidates

CN = {
    "q_beta":"同任务相对Q", "q_residual_p10":"相对Q低尾", "q_residual_sd":"相对Q波动",
    "t_source_origin_effect":"来源内相对时间", "t_log_residual_tail":"时间长尾",
    "pair_count_effect":"相对点数", "bottom_y_effect":"底部ERP纵坐标",
    "top_y_effect":"顶部ERP纵坐标", "height_log_effect":"参考高度比",
    "hard_minus_easy":"困难相对容易适应", "medium_minus_easy":"中等相对容易适应",
    "semi_new_edit_effect":"新Semi修改倾向", "semi_old_edit_effect":"旧Semi修改倾向",
    "semi_new_error_nonedit_effect":"新报告错误后未改倾向", "scope_out_effect":"范围外回答倾向",
}


def cn(col):
    if col in CN:
        return CN[col]
    for old, name in [("time_effect","本条件相对时间"),("q_effect","本条件相对最终Q"),
                      ("q_abs_p10","本条件最终Q低尾"),("pair_effect","本条件相对点数"),
                      ("bottom_y_effect","本条件底部ERP纵坐标"),("height_log_effect","本条件参考高度比")]:
        if col.endswith(old):return name
    return col


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--dir",type=Path,default=Path(__file__).resolve().parent)
    ap.add_argument("--repo",type=Path,default=BASE/"repo")
    ap.add_argument("--skip-rebuild",action="store_true")
    args=ap.parse_args()
    out=args.dir
    f=pd.read_csv(out/"features_train.csv.gz").set_index("worker_id",drop=False)
    fixed=pd.read_csv(out/"worker_labels.csv.gz")
    man=json.loads((out/"method_manifest.json").read_text())
    shortlist=json.loads((out/"SHORTLIST.json").read_text())["items"]
    selected={r["method_id"] for r in shortlist}
    original_sha={p.name:sha(p) for p in [out/"worker_labels.csv.gz",out/"method_manifest.json"]}
    checks={}
    assert not fixed.duplicated(["method_id","domain","worker_id"]).any()
    assert fixed.groupby(["method_id","domain"]).size().eq(60).all()
    for mid,m in man["methods"].items():
        a=fixed[fixed.method_id.eq(mid)]
        mp={w:cl for cl,v in m["classes"].items() for w in v["workers"]}
        assert dict(zip(a.loc[a.known,"worker_id"],a.loc[a.known,"class_id"]))==mp,mid
        assert set(mp).issubset(m["eligible_workers"]),mid
        assert set(a.loc[~a.known,"class_id"]) <= {"unknown"},mid
    checks["manifest_long_labels_match_all_methods"]=True
    if not args.skip_rebuild:
        regen=define_candidates(f.reset_index(drop=True))
        rebuilt=pd.DataFrame(regen.rows)
        cols=["worker_id","method_id","domain","class_id","known","origin","eligible_population","reason","train_key"]
        sort=["method_id","domain","worker_id"]
        a=fixed.sort_values(sort)[cols].reset_index(drop=True)
        b=rebuilt.sort_values(sort)[cols].reset_index(drop=True)
        assert a.equals(b)
        checks["all_definitions_reconstructed_exactly"]=True
        checks["reconstructed_methods"]=len(regen.methods)
        checks["reconstructed_label_rows"]=len(a)
    # Verify field-removal experiments retain exactly the same people.
    for k in [2,3]:
        group=[m for m in man["methods"].values() if (m.get("ablation") or {}).get("family")==f"newCommon_K{k}"]
        assert len(group)==8
        assert len({tuple(m["known_workers"]) for m in group})==1
        assert len(group[0]["known_workers"])==26
    checks["seven_group_ablations_common_26_workers"]=True
    explain=[]
    for mid,m in man["methods"].items():
        if not m["known_workers"]:continue
        group=f.loc[m["known_workers"]]
        fields=m["required_fields"]
        center=group[fields].median()
        scale=group[fields].quantile(.75)-group[fields].quantile(.25)
        scale=scale.where(scale.gt(1e-9),group[fields].std()).fillna(1).replace(0,1)
        for cl,info in m["classes"].items():
            g=f.loc[info["workers"]]
            means=g[fields].mean()
            relative=((means-center)/scale).dropna()
            # Names describe historically distinctive axes only. Exact raw
            # thresholds/centroids remain in the original frozen manifest.
            distinctive=relative.abs().sort_values(ascending=False).index.tolist()[:3]
            descriptors=[]
            for col in distinctive:
                if "time_effect" in col or col=="t_source_origin_effect":
                    word="相对更快" if relative[col]<0 else "相对更慢"
                    descriptors.append(word+"（来源内）")
                else:
                    descriptors.append(cn(col)+( "偏低" if relative[col]<0 else "偏高"))
            if m["family"]=="rule" and len(fields)==1 and "cuts" in m["parameters"]:
                # Ordinal middle groups should be called middle, not "faster"
                # merely because a skewed group's mean falls below its median.
                rank=sorted(m["classes"]).index(cl)
                count=len(m["classes"])
                if count==2:word=["较低组","较高组"][rank]
                elif count==3:word=["较低组","居中组","较高组"][rank]
                else:word=f"第{rank+1}/{count}分位组"
                if fields[0]=="t_source_origin_effect" or fields[0].endswith("time_effect"):
                    if count==2:word=["相对较快组","相对较慢组"][rank]
                    elif count==3:word=["相对较快组","时间居中组","相对较慢组"][rank]
                    descriptors=[word+"（来源内相对时间）"]
                else:descriptors=[cn(fields[0])+"："+word]
            timecol={"semi_new":"cond_semi_new_time_effect","semi_v1":"cond_semi_v1_time_effect",
                     "doorway_manual":"cond_doorway_time_effect"}.get(m["pool_filter"],"t_source_origin_effect")
            row=dict(method_id=mid,domain=m["domain"],pool_filter=m["pool_filter"],class_id=cl,
                shortlist=mid in selected,class_name_zh="；".join(descriptors),
                name_basis="relative to this method's historical known people; descriptive, not an official grade",
                people=len(g),new_people=int(g.person_origin.eq("new").sum()),old_people=int(g.person_origin.eq("v1").sum()),
                exact_members="|".join(info["workers"]),q_beta_mean=g.q_beta.mean(),q_abs_mean=g.q_abs_mean.mean(),
                q_abs_p10_mean=g.q_abs_p10.mean(),pair_effect_mean=g.pair_count_effect.mean(),
                bottom_y_effect_mean=g.bottom_y_effect.mean(),height_log_effect_mean=g.height_log_effect.mean(),
                time_feature=timecol,eligible_definition=m["eligible_definition"],
                threshold_or_fit=json.dumps(m["parameters"],ensure_ascii=False,separators=(",",":")),
                min_history_core_tasks=int(g.core_tasks.min()),min_history_core_buildings=int(g.core_buildings.min()))
            for origin in ["new","v1"]:
                s=g[g.person_origin.eq(origin)][timecol].dropna()
                row[origin+"_time_supported_people"]=len(s)
                row[origin+"_time_log_effect_mean"]=s.mean() if len(s) else None
                row[origin+"_time_multiplier"]=np.exp(s.mean()) if len(s) else None
            for col in ["t_records","t_buildings","hard_tasks","hard_buildings",
                        "semi_new_error_nonedit_records","semi_new_error_nonedit_buildings",
                        "semi_new_edit_records","semi_old_edit_records","scope_records","scope_varying_tasks"]:
                row["member_min_"+col]=g[col].min()
                row["member_max_"+col]=g[col].max()
            explain.append(row)
    explanations=pd.DataFrame(explain)
    explanations.to_csv(out/"CLASS_EXPLANATIONS_ZH.csv.gz",index=False)
    explanations[explanations.shortlist].to_csv(out/"SHORTLIST_CLASSES_ZH.csv",index=False)
    # Exact sparse opportunity accounting, including historical inventory people
    # outside the formal 60. Such people are not silently included in labels.
    records=json.load(gzip.open(args.repo/"research/statistics/v2_evidence_audit_20261019/records.json.gz","rt"))["records"]
    hist=set(man["history_buildings"])
    old=[]
    for r in records:
        se=r.get("semi_evidence") or {}
        if r["building_id"] in hist and se.get("confirmed_error_opportunity") and se.get("known_error_unchanged") is not None:
            old.append(dict(worker_id=r["worker_id"],image_id=r["image_id"],building_id=r["building_id"],unchanged=bool(se["known_error_unchanged"])))
    op=pd.DataFrame(old)
    supported=op[op.worker_id.isin(f.index)]
    old_summary={"all_inventory_history_opportunities":len(op),"all_inventory_workers":op.worker_id.nunique(),
        "all_inventory_images":op.image_id.nunique(),"all_inventory_buildings":op.building_id.nunique(),
        "formal60_history_opportunities":len(supported),"formal60_workers_with_opportunity":supported.worker_id.nunique(),
        "formal60_max_per_person_records":supported.groupby("worker_id").size().max(),
        "formal60_unchanged_count":int(supported.unchanged.sum()),
        "outside_formal60_workers":sorted(set(op.worker_id)-set(f.index)),
        "support_gate":{"records":3,"buildings":2},"supported_workers":0,
        "reason":"Each observed formal-profile person has only one recorded error opportunity in one building; this is insufficient opportunity, not zero blindness or confirmed correction."}
    pd.DataFrame(old).to_csv(out/"old_confirmed_error_history_opportunities.csv",index=False)
    checks["old_confirmed_error_failure"]=old_summary
    assert original_sha=={p.name:sha(p) for p in [out/"worker_labels.csv.gz",out/"method_manifest.json"]}
    checks["frozen_files_unchanged"]=original_sha
    js(out/"LABEL_VERIFICATION.json",dict(utc=datetime.now(timezone.utc).isoformat(),checks=checks))
    lines=["# 正向细类：冻结标签、解释与直接替换入口", "",
        "本轮所有标签只用旧 SPLIT 的 10 栋历史建筑；188 个定义中 184 个产生至少两类。36 个优先方法按字段覆盖和历史成员容量选出，尚未据目标融合效果筛选。",
        "", "## 高Q身份边界", "",
        "高Q23指历史相对Q β≥0（新15、旧8）；高三分位18人是其子集。多出的5人是 W029、W110、W114、W125、W131。两种口径的所有候选使用不同ID，不能混称同一高Q类。",
        "", "## 分类与解释如何读取", "",
        "- `worker_labels.csv.gz` 和 `method_manifest.json` 是不可改的冻结标签及规则。每个人的 known/unknown、eligible_population 和原因均保留。",
        "- `SHORTLIST_CLASSES_ZH.csv` 是36优先方法的逐类中文轴解释、精确成员、来源、阈值/拟合参数和时间倍数；`CLASS_EXPLANATIONS_ZH.csv.gz` 包含全部候选。类名只描述本方法内历史差异，不代表正式人员级别。",
        "- `pool_filter=ordinary_manual/doorway_manual/semi_new/semi_v1` 指定任务；domain=hard 另限制既有困难协议。Semi主实验整队同来源，不能混入另一批人员解释成功。",
        "- 高Q/行为细类之外的真实人员可在A/B/C中作为完全相同的固定 `outside_group` 背景；他们没有因此获得该细类标签。",
        "- `capacity_directed_cells.csv.gz` 是实际池成员上 n/m/有向类对的容量，不是已观察到的融合成功。三人小类无法提供 m=2 的同类换出块，不能用单人稳定冒充整类可互换。",
        "", "## 时间、条件与机会", "",
        "继承全域T按同图片/条件/来源/时间证据类型拟合 log秒数的任务与人员效应。exp(人员效应)是相对同来源任务的倍数；更小表示相对更快。新旧批有不同时间证据语义，因此分来源列出倍数，不能直接用两个倍数宣称跨批绝对时间差。时间长尾单独保留。",
        "",
        "历史新批2379份，6.622–1500.270秒；旧批431份，2–2334秒。旧批有5份短于5秒、4份长于1800秒；原资格只要求秒数为正，本轮未按结果临时剪尾。独立来源内OLS与继承T最大差小于4e−14。门洞/新Semi/旧Semi另拟合自己的合格本条件时间，其支持为27/27/19人，对应最终Q支持为35/27/24人。",
        "",
        "原特征的156列已重算逐列一致；新增172列记录自己的任务/几何/时间/机会。新旧Semi编辑、错误未改和scope不合为纠错分。scope只有回答倾向；其自身Semi条件用原门槛拟合无人合格，因此另列失败。Semi中实际可测试的是跨历史任务形成的scope人员倾向，而不是虚构本条件裁定专家。",
        "",
        f"旧确认错误非编辑：历史库存{len(op)}条、{op.worker_id.nunique()}人、{op.image_id.nunique()}图、{op.building_id.nunique()}楼；正式60人中只有{len(supported)}条机会、{supported.worker_id.nunique()}人，每人仅1条。原门槛为3次机会且跨2楼，无人合格。4次未修改也不能自动推出总体盲信水平；修改不等于确认纠正。",
        "", "## 消融与复核", "",
        "七个字段组为 Q、T、困难适应、几何、Semi编辑、新报告错误后未改、scope。Full及逐一去掉字段组，固定共同的26名新批人员；K2/K3各8种真实分型。不能把删除变量后扩大人员覆盖当成增量。",
        "",
        "`LABEL_VERIFICATION.json` 记录188个候选、11280行标签按代码从历史特征精确重建，全部known/unknown与规则映射一致；不会修改冻结标签。历史删楼是训练敏感性，不能代替未见图片、未见人员或外部盲测。",
        "", "## 复现", "",
        "```text", "python interchangeability_20261020/forward/audit_and_features.py",
        "python interchangeability_20261020/forward/build_candidates.py",
        "python interchangeability_20261020/forward/explain_and_verify.py", "```", "",
        "默认从已归档前轮分析及科学冻结repo读取；可用--repo/--prior/--split/--out指定恢复目录。全程不读取新的类别块输出，不修改旧analysis或冻结参考。"]
    (out/"README_ZH.md").write_text("\n".join(lines)+"\n")
    print(json.dumps(clean({"checks":checks,"class_explanation_rows":len(explanations),
                            "shortlist_class_rows":int(explanations.shortlist.sum())}),ensure_ascii=False))


if __name__=="__main__":
    main()
