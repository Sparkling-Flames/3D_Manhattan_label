"""把明确交付的已审计结果投影为展示切片；不执行研究分析或拟合。"""
from __future__ import annotations
import argparse
import base64
from collections import Counter, defaultdict
import copy
import csv
import gzip
import io
import json
from pathlib import Path
import re
import tempfile
from zipfile import ZipFile

from .build import build, validate, ROOT, MODULES

RESULTS = ROOT / "analysis_results"
REVIEWED = RESULTS / "new_manual_reviewed_20260921"
WORKER = RESULTS / "worker_cluster_sensitivity_20260921/numeric"
ROOM = RESULTS / "room_partition_comparison_20260922"
PRO = RESULTS / "cluster_validation_received_20260922/Pro原始返回.zip"
VERSION = "reviewed-20260921+audit-20260922"
RELEASE = "research-20260922"
COMPUTE = "Manual/OOS · 无辅助计算"
DESCRIBE = "全部条件 · 描述覆盖"
CLASSIFICATION = "未固定人员类别"
METHODS = {"complete": "完整链接 · 25.6px", "affinity": "直径约束＋二次亲近度 · 25.6px", "none": "描述视图（按图注明方法）"}
CASE_CODES = ["uNb9QFRL6hY-55", "uNb9QFRL6hY-29", "q9vSo1VnCiC-02", "uNb9QFRL6hY-06"]


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def rows(path):
    return list(csv.DictReader(Path(path).open(encoding="utf-8-sig", newline="")))


def archived(z, name):
    b = z.read("results/" + name)
    if name.endswith(".gz"):
        b = gzip.decompress(b)
    return list(csv.DictReader(io.StringIO(b.decode("utf-8-sig")))) if ".csv" in name else json.loads(b)


def n(value):
    return float(value) if value not in ("", None) else None


def metric(label, value, unit, definition, source, members=(), denominator=None):
    return dict(label=label, value=value, unit=unit, definition=definition, status="ready" if value is not None else "not_computed",
                denominator=denominator, source_ids=[source], member_ids=list(members))


def point(x, value, series, image="", members=(), source="pro", denominator=None, numerator=None, status=None):
    return dict(x=x, value=value, series=series, image_id=image, member_ids=list(members), source_ids=[source],
                denominator=denominator, numerator=numerator, status=status or ("ready" if value is not None else "not_computed"))


def chart(id, title, data, x, y, unit, definition, kind="scatter", x_unit="", group=False):
    return dict(id=id, title=title, kind=kind, x_label=x, x_unit=x_unit, y_label=y, unit=unit,
                definition=definition, rows=data, group_by_image=group)


def table(id, title, columns, data, source, replay=False):
    result=[]
    for row in data:
        result.append(dict(row, image_id=row.get("image_id", ""), member_ids=row.get("member_ids", []), source_ids=[source]))
    col=[dict(key=k,label=label,unit=unit) for k,label,unit in columns]
    col += [dict(key=k,label=label,unit="") for k,label in [("image_id","图片"),("member_ids","成员"),("source_ids","来源")]]
    return dict(id=id,title=title,columns=col,rows=result,replay=replay)


def module(note="", status="ready", metrics=None, charts=None, tables=None):
    return dict(status=status, note=note, metrics=metrics or [], charts=charts or [], tables=tables or [])


def connect(work, coverage=None, shared_x=None):
    """work is a disposable packaging directory; source files remain untouched."""
    with gzip.open(REVIEWED / "responses.jsonl.gz", "rt", encoding="utf-8") as f:
        records={r["canonical_annotation_id"]: r for r in map(json.loads, f)}
    accepted=[r for r in records.values() if r["calculation_included"] and r["worker_id"] not in {"W019","W026"}]
    summary=read(REVIEWED / "SUMMARY.json")
    assert len(accepted)==summary["views"]["all_accepted"]["responses"]==3019
    eligibility={r["id"]:r for r in read(REVIEWED / "eligibility.json")}
    with ZipFile(PRO) as z:
        memberships={}
        for row in archived(z,"partition_memberships.json.gz"):
            if row["variant"]=="raw" and row["method"]=="complete" and row["cut"]==25.6:
                memberships["complete",row["image_id"]]=row
        for row in archived(z,"affinity_corpus_memberships.json"):
            assert row["certified"]
            memberships["affinity",row["image_id"]]=row
        complete=[r for r in archived(z,"image_partition_sensitivity.csv.gz") if r["variant"]=="raw" and r["method"]=="complete" and float(r["cut"])==25.6]
        affinity=archived(z,"affinity_corpus.csv")
        endpoint={"complete":complete,"affinity":affinity}
        replay=[r for r in archived(z,"consensus_replay_per_image.csv") if r["variant"]=="raw" and r["method"]=="complete" and float(r["cut"])==25.6 and r["J"]=="3" and r["m"]=="2" and r["tail_fraction"]=="0.1" and r["h"]=="3"]
        prefixes=[r for r in archived(z,"consensus_replay_prefixes.csv.gz") if r["variant"]=="raw" and r["method"]=="complete" and float(r["cut"])==25.6 and int(r["order"])<3]
        orders=archived(z,"consensus_replay_orders.json")
        registry=json.loads(z.read("source/analysis_results/scene_image_exploration_20260910_v1/same_room_selection_registry_v2_20260912.json"))
    calc_ids={cid for (method,_),r in memberships.items() if method=="complete" for cid in r["ids"]}
    assert len(calc_ids)==2444 and len(complete)==len(affinity)==240
    assert all(cid in records and records[cid]["raw_condition"] in ["manual","oos"] and not records[cid]["imputed_point"] for cid in calc_ids)
    assert all(memberships["complete",iid]["ids"]==memberships["affinity",iid]["ids"] for method,iid in memberships if method=="complete")
    calc=[records[cid] for cid in sorted(calc_ids)]
    workers=sorted({r["worker_id"] for r in accepted})
    codes={r["image_id"]:r["code"] for r in eligibility.values()}
    image_ids=sorted({r["image_id"] for r in accepted},key=lambda i:codes[i])
    # Preserve manual groups only; ungrouped is not a newly inferred room.
    room_of={}
    for group in registry["groups"]:
        if group["raw_current"].get("physical_same")=="支持":
            for iid in group["image_ids"]:
                if iid in room_of and room_of[iid]!=group["review_code"]:
                    raise ValueError("overlapping manual room groups: "+iid)
                room_of[iid]=group["review_code"]
    data=dict(schema_version="research_dashboard_v1",release=RELEASE,
        versions=[dict(id=VERSION,label="终审数据 · 09-21／复核结果 · 09-22",description="3019份259图描述视图；2444份240图无辅助计算视图；不同面板单列。")],
        methods=[dict(id=k,label=v,description={"complete":"固定点数与端点对应，最大周期端点距离；簇内直径≤25.6px。", "affinity":"同距离和直径条件；最大化二次亲近度的已求解候选分区。", "none":"按原条件计数；条件图片集合可能重叠。"}[k]) for k,v in METHODS.items()],
        classifications=[dict(id=CLASSIFICATION,label=CLASSIFICATION,description="显示具体成员及移除敏感性；未认定人员质量类别，未固定AABC。")],
        sources=[dict(id=id,label=label,description=description) for id,label,description in [
            ("reviewed","终审作答","new_manual_reviewed_20260921：SUMMARY、responses、eligibility；已核实身份与有效点。"),
            ("pro","分簇与有限池重放","cluster_validation_received_20260922/Pro原始返回.zip：results；独立复核2444份点集与离散结果一致，浮点尾差记录于audit。"),
            ("worker","人员敏感性","worker_cluster_sensitivity_20260921/numeric；固定原N≥8面板，逐人移除及同图等人数对照。"),
            ("room","同房预测","room_partition_comparison_20260922；新旧分区固定目标／来源图片，按房间后建筑等权。"),
            ("screen","精选图像与人工审核","cluster_screen_20260921/data.js及cluster_screen_reviewed_20260922/逐项接收.json；目的性24图开发核查。"),
            ("room_registry","人工同房分组","same_room_selection_registry_v2_20260912；physical_same=支持，未自动推定同建筑即同房。"),
            ("coverage","资产覆盖审计","模型、GT及特征逐图关联审计；文件／特征维度与研究结论分开。")]],
        participants=[dict(id=w,label=w) for w in workers],
        images=[dict(id=i,building=i.split('_')[0],room=room_of.get(i,"未纳入人工同房组"),scene=codes[i],source_ids=["reviewed","room_registry"]) for i in image_ids],views=[],cases=[])
    by_image=defaultdict(list)
    for r in accepted:by_image[r["image_id"]].append(r)
    calc_image=defaultdict(list)
    for r in calc:calc_image[r["image_id"]].append(r)
    predictions=rows(ROOM/"paired_predictions.csv")
    room_summary=[r for r in rows(ROOM/"summary.csv") if r["same_panel_otherroom"]=="False"]
    sensitivity=[r for r in rows(WORKER/"endpoint_summary.csv") if r["method"]=="complete"]
    sensitivity_image=[r for r in rows(WORKER/"endpoint_per_image.csv") if r["method"]=="complete"]
    joint=[r for r in rows(WORKER/"joint_endpoint_summary.csv") if r["method"]=="complete"]
    transitions=read(WORKER/"replay_summary.json")
    current_replay=[r for r in transitions if r["method"]=="complete" and r["profile"]=="uncapped"]
    reviews=read(RESULTS/"cluster_screen_reviewed_20260922/逐项接收.json")
    audits=read(coverage) if coverage else None
    semi=read(Path(coverage).with_name("semi_descriptive.json")) if coverage else None
    human=read(Path(coverage).with_name("human_coverage.json")) if coverage else None
    if human:
        assert human["all_accepted"]==summary["views"]["all_accepted"]
        for condition,expected in human["conditions"].items():
            p=[r for r in accepted if r["raw_condition"]==condition]
            assert len(p)==expected["responses"] and len({r["image_id"] for r in p})==expected["images"]
    asset_ids={r["asset"]:set(r["image_ids"]) for r in audits["assets"]} if audits else {}
    reviewed_members=read(REVIEWED/"memberships.json")
    def semi_members(i,condition="semi"):
        return [records[r["id"]]["worker_id"] for r in reviewed_members if r["image_id"]==i and r["condition"]==condition and r["method"]=="complete"]
    def asset_name(s):
        for a,b in [("dinov3","DINOv3"),("da3","DA3"),("ulayout","uLayout"),("bilayout","Bi-Layout"),("hohonet","HoHoNet")]:s=s.replace(a,b)
        return s

    def members(i):return [records[cid]["worker_id"] for cid in memberships["complete",i]["ids"]]
    def modules_for(ids, method, pool, whole=False):
        selected=set(ids);persons=sorted({r["worker_id"] for r in pool});mods={key:module("此范围未计算。", "not_computed") for key in MODULES}
        mods["overview"]=module(metrics=[metric("作答",len(pool),"份","当前筛选范围的纳入作答。","reviewed"),metric("图片",len(ids),"图","按图片身份去重。","reviewed"),metric("实际人员",len(persons),"人","同一人员多份作答计一人。","reviewed",persons),metric("建筑",len({i.split('_')[0] for i in ids}),"栋","当前筛选图片的建筑。","reviewed")])
        overview=mods["overview"]
        counts=Counter((r["image_id"],r["raw_condition"]) for r in pool)
        overview["charts"].append(chart("coverage","逐图作答覆盖",[point(codes[i],v,condition,i,[r["worker_id"] for r in pool if r["image_id"]==i and r["raw_condition"]==condition],"reviewed") for (i,condition),v in counts.items()],"图片","纳入作答","份","同一人员在不同图片可多次出现；条件图集不相加。",kind="bar"))
        conditions=[]
        for condition in ["manual","oos","semi"]:
            p=[r for r in pool if r["raw_condition"]==condition]
            if p:conditions.append(dict(condition=condition,responses=len(p),images=len({r["image_id"] for r in p}),workers=len({r["worker_id"] for r in p}),buildings=len({r["building_id"] for r in p}),member_ids=sorted({r["worker_id"] for r in p})))
        overview["tables"].append(table("conditions","按条件覆盖（图片集合可重叠）",[("condition","条件",""),("responses","作答","份"),("images","图片","图"),("workers","人员","人"),("buildings","建筑","栋")],conditions,"reviewed"))
        mods["features"]=module("特征库存审计待接入；特征与不确定性关系未计算。","not_computed")
        if audits:
            items=[]
            for a in audits["assets"]:
                source=a["source"].replace(str(ROOT),"仓库").replace("\\","/")
                if re.match(r"^[A-Za-z]:/",source):source="外部Bi-Layout历史导出目录"
                items.append(dict(asset=asset_name(a["asset"]),available=a["available_images"],pool=a["pool_images"],matched=len(selected & asset_ids[a["asset"]]),scope=len(ids),validation=a["validation"],origin=source))
            columns=[("asset","资产与版本",""),("available","该版本独立图片","图"),("pool","648图池覆盖","图"),("matched","当前范围匹配","图"),("scope","当前范围分母","图"),("validation","核验范围",""),("origin","来源版本","")]
            overview["tables"].append(table("assets","GT／模型／特征资产覆盖（版本不相加）",columns,items,"coverage"))
            raw=[a for a in audits["assets"] if "本地原始特征" in a["asset"]]
            feature=module("本次仅接入资产覆盖，未接入当前版本的特征关系分析。HoHoNet与Bi每图4相位仍计1张独立图片。",
                metrics=[metric("模型特征类型",len(raw),"类","HoHoNet、Bi、DINOv3、DA3、uLayout。","coverage"),metric("当前真人图片",len(ids),"图","当前筛选，不能与648图模型池相加。","coverage"),metric("DA3同房辅助（全资产库）",audits["auxiliary_pairs"]["local_pair_files"],"对资产","全资产库独立库存，不随当前图片筛选缩减；历史相机一致性有问题，不计作可靠重建。","coverage"),metric("当前版本特征关系",None,"","本展示未接入当前分析版本的特征关系结果。","coverage")])
            feature["charts"].append(chart("features","五类特征的当前图片覆盖",[point(asset_name(a["asset"]),len(selected & asset_ids[a["asset"]]),"有资产",source="coverage",denominator=len(ids)) for a in raw],"特征来源","匹配独立图片","图","仅文件与预期键集合检查；不表示语义质量。",kind="bar"))
            feature["tables"].append(table("feature-assets","特征与模型版本",columns,[r for r in items if "GT" not in r["asset"]],"coverage"));mods["features"]=feature
        if method=="none":
            mods["annotation"]=module("描述视图不混入无辅助分簇结果。","not_applicable")
            if semi and pool and all(r["raw_condition"]=="semi" for r in pool):
                ss=[r for r in semi["per_image"] if r["image_id"] in selected]
                sm=module("Semi独立描述；完整链接25.6px；绑定可计算530份/43图。与Manual人员和人数未匹配，不是辅助效果估计。")
                sm["charts"].append(chart("semi-clusters","Semi · 人数与簇数",[point(r["N"],r["groups"],"Semi",r["image_id"],semi_members(r["image_id"]),"coverage",r["N"]) for r in ss],"可计算人数","簇数","簇","本图绑定可计算人数；描述覆盖538份含8份未绑定作答。",x_unit="人"))
                sm["tables"].append(table("semi-table","Semi逐图分簇",[("code","图片简称",""),("N","可计算人数","人"),("K","簇数","簇"),("singleton","单人簇比例","%")],[dict(code=r["code"],N=r["N"],K=r["groups"],singleton=100*r["singleton_mass"],image_id=r["image_id"],member_ids=semi_members(r["image_id"])) for r in ss],"coverage"))
                pairs=[r for r in semi["manual_semi_same_image"] if r["image_id"] in selected]
                sm["charts"].append(chart("semi-manual","同图Manual／Semi · 单人簇占比",[point(codes[r["image_id"]],100*r[c+"_singleton_mass"],c,r["image_id"],semi_members(r["image_id"],c),"coverage",r[c+"_N"]) for r in pairs for c in ["manual","semi"]],"图片","单人簇作答比例","%","同图25张；悬停显示各条件人数，人员／人数未匹配。",kind="bar"))
                mods["annotation"]=sm
            return mods
        ep=[r for r in endpoint[method] if r["image_id"] in selected]
        annotation=module("当前有效点；1024×512px；25.6px工作容差；簇编号只在当前图片和方法内有效。")
        if whole:
            panel=[r for r in ep if int(r["N"])>=8]
            annotation["metrics"]=[metric("原N≥8图片",len(panel),"图","固定高人数面板。","pro"),metric("该面板作答",sum(int(r["N"]) for r in panel),"份","图片与人员的作答记录。","pro"),metric("单人簇作答",sum(int(r["singletons"]) for r in panel),"份","当前分区中单人簇成员；非质量认定。","pro"),metric("三大支持簇覆盖≥90%",sum(r["few_J3_m2_s10"]=="True" for r in panel),"图","最多3簇，每簇≥2人，覆盖≥90%；仅完整池终点条件。","pro",denominator=len(panel))]
        annotation["charts"]=[chart("clusters","人数与簇数",[point(int(r["N"]),int(r["K"]),"当前分区",r["image_id"],members(r["image_id"])) for r in ep],"实际人数","簇数","簇","已提供的完整图分区。",x_unit="人"),chart("singleton","逐图单人簇占比",[point(int(r["N"]),100*float(r["singleton_share"]),"单人簇",r["image_id"],members(r["image_id"]),denominator=int(r["N"]),numerator=int(r["singletons"])) for r in ep],"实际人数","单人簇作答比例","%","分母为该图当前无辅助作答人数；非人员质量标签。",x_unit="人")]
        roster=[]
        for i in ids:
            m=memberships[method,i]
            for group in sorted(set(m["labels"])):
                cids=[cid for cid,g in zip(m["ids"],m["labels"]) if g==group]
                roster.append(dict(image_id=i,code=codes[i],cluster=group,size=len(cids),annotation_ids=cids,member_ids=[records[cid]["worker_id"] for cid in cids]))
        annotation["tables"].append(table("clusters","全部簇成员",[("code","图片简称",""),("cluster","簇",""),("size","支持人数","人"),("annotation_ids","作答身份","")],roster,"pro"));mods["annotation"]=annotation
        review_rows=[]
        for r in reviews:
            if r["image_id"] not in selected:continue
            m=memberships[method,r["image_id"]];g=dict(zip(m["ids"],m["labels"]))
            review_rows.append(dict(image_id=r["image_id"],code=r["code"],distance=r["fixed_max_px"],decision=r["original_decision"]["relation"],same_cluster="同簇" if g[r["ids"][0]]==g[r["ids"][1]] else "分开",annotations=r["ids"],member_ids=r["workers"]))
        if review_rows:annotation["tables"].append(table("review24","人工开发核查（目的性24图）",[("code","图片简称",""),("distance","指定对距离","px"),("decision","记录的人工判断",""),("same_cluster","当前方法分区",""),("annotations","指定作答","")],review_rows,"screen"))
        if method=="affinity":
            mods["people"]=module("二次亲近度候选目前已接入分区与簇成员；尚未接入基于该方法的人员分类、组成比较、移除敏感性或进入顺序重放。可在“标注与分簇”查看当前方法的簇成员。完整链接与历史分类结果需明确切换后查看。", "not_computed")
            mods["stability"]=module("二次亲近度候选尚未接入逐前缀重放与持续起点结果；最终分区不能替代人数过程。完整链接的已有重放结果不属于本方法。", "not_computed")
        if method=="complete":
            rep=[r for r in replay if r["image_id"] in selected]
            stable=module("固定已观察人员池，80个顺序；J=3、每簇至少2人、覆盖≥90%，尾段≥3；不是多轮修订质量上限。")
            stable["charts"].append(chart("success","有限池中持续起点的重放比例",[point(int(r["N"]),100*float(r["success_fraction"]),"80个顺序",r["image_id"],members(r["image_id"]),denominator=80) for r in rep],"已观察人数","有持续起点的顺序比例","%","份额变化≤0.1、关系变化≤0.05；候选起点从4人开始。",x_unit="人"))
            stable["tables"].append(table("replay-status","有限池逐图状态",[("code","图片简称",""),("N","观察人数","人"),("orders","顺序数","次"),("endpoint","终点覆盖条件",""),("probability","存在持续起点","%"),("onset","成功顺序中的起点中位数","人"),("state","观察状态","")],[dict(image_id=r["image_id"],code=r["code"],N=int(r["N"]),orders=80,endpoint="达到" if r["endpoint_pass"]=="True" else "未达到",probability=100*float(r["success_fraction"]),onset=n(r["observed_onset_median_success_only"]),state="有成功顺序" if float(r["success_fraction"])>0 else "观察池内未识别",member_ids=members(r["image_id"])) for r in rep],"pro"))
            if len(ids)==1:
                pref=[r for r in prefixes if r["image_id"]==ids[0]]
                for field,title,unit,mult in [("K","人数增加后的簇数","簇",1),("singleton_share","人数增加后的单人簇占比","%",100)]:
                    stable["charts"].append(chart("prefix-"+field,title,[point(int(r["k"]),mult*float(r[field]),"顺序 "+str(int(r["order"])+1),r["image_id"],[w for w in orders[int(r["order"])] if w in members(r["image_id"])][:int(r["k"])],denominator=int(r["k"])) for r in pref],"进入人数",title,unit,"展示预定编号1—3的完整重放；不按结果选择顺序。",kind="line",x_unit="人"))
            mods["stability"]=stable if rep else module("人数不足：此切片没有N≥8的重放图片。","insufficient")
            people=module("逐人移除：只比较该人出现的原N≥8图片。对照为同图逐个移除其他人的精确均值；单人簇占比不是质量认定。")
            if whole:
                for field,title,unit,mult in [("K","逐人移除后的平均簇数","簇",1),("singleton_mass","逐人移除后的单人簇比例","%",100)]:
                    values=[r for r in sensitivity if r["metric"]==field]
                    people["charts"].append(chart("remove-"+field,title,[point(r["worker"],mult*float(r[key]),label,source="worker",denominator=int(r["images"]),members=[r["worker"]]) for r in values for key,label in [("baseline","原始"),("removed","移除该人"),("control","等人数对照")]],"移除人员",title,unit,"逐图等权；各人员对应的图片面板不同。",kind="bar"))
                people["tables"].append(table("joint","联合移除W037／W034／W032（独立于逐人对照）",[("metric","指标",""),("unit","单位",""),("images","共同有效图片","图"),("baseline","原始",""),("removed","联合移除",""),("control","等大小删除子集对照","")],[dict(metric={"K":"平均簇数","singleton_mass":"单人簇占比","U8":"前8人未覆盖下一作答概率"}[r["metric"]],unit="簇" if r["metric"]=="K" else "%",images=int(r["images"]),baseline=float(r["baseline"])*(1 if r["metric"]=="K" else 100),removed=float(r["removed"])*(1 if r["metric"]=="K" else 100),control=float(r["control"])*(1 if r["metric"]=="K" else 100),member_ids=["W037","W034","W032"]) for r in joint],"worker"))
                people["tables"].append(table("worker-replay","人员移除后的持续起点（200顺序；不加簇数／单人簇限制）",[("scenario","情景",""),("images","固定图片","图"),("identified","已识别起点","图"),("possible","仅可能达到","图"),("not_reached","未达到","图")],[dict(scenario=r["scenario"],images=r["images"],identified=r["statuses"].get("identified",0),possible=r["statuses"].get("possible_only",0),not_reached=r["statuses"].get("not_reached",0)) for r in current_replay],"worker"))
            local=[r for r in sensitivity_image if r["image_id"] in selected]
            people["tables"].append(table("remove-table","逐图、逐人移除结果",[("worker","移除人员",""),("N","原人数","人"),("baseline","原簇数","簇"),("removed","移除后簇数","簇"),("control","等人数对照均值","簇")],[dict(image_id=r["image_id"],worker=r["worker"],N=int(r["N"]),baseline=n(r["baseline_K"]),removed=n(r["removed_K"]),control=n(r["control_K"]),member_ids=members(r["image_id"])) for r in local],"worker"))
            if len(ids)==1 and any(r["image_id"]==ids[0] for r in prefixes):
                order=[w for w in orders[0] if w in members(ids[0])]
                people["tables"].append(table("order","预定顺序1 · 实际进入成员",[("step","步骤","人"),("entered","进入人员","")],[dict(step=i,entered=w,image_id=ids[0],member_ids=order[:i]) for i,w in enumerate(order,1)],"pro",True))
            mods["people"]=people
        side="old" if method=="complete" else "new"
        pred=[r for r in predictions if r["image_id"] in selected]
        if pred:
            room=module("留目标图预测其分歧／支持指标；来源为同房其他图片。历史／预测身份按每次留图拆分；不是未来持续稳定人数。")
            names={"core3_mass":"三大重复支持簇覆盖","singleton_mass":"单人簇占比","pair_disagreement":"成对分歧率"}
            if whole:
                room["charts"].append(chart("mae","同房预测绝对误差",[point(("可比同房" if r["kind"]=="comparable_same" else "全部支持同房")+" · "+names[r["metric"]],100*float(r[key+"_"+side]),label,source="room",denominator=int(r["images"])) for r in room_summary for key,label in [("MAE","同房来源"),("outside_MAE","其他建筑参照"),("otherroom_MAE","同建筑其他房间参照")]],"面板与指标","建筑等权 MAE","百分点","可比同房21图/5组/5建筑；全部支持同房64图/15组/9建筑。两个面板重叠。",kind="bar"))
            for measure,label in names.items():
                p=[r for r in pred if r["metric"]==measure and r["kind"]=="comparable_same"]
                if p:room["charts"].append(chart("room-"+measure,label+" · 逐目标图",[point(r["code_old"],100*float(r[field+"_"+side]),title,r["image_id"],members(r["image_id"]),"room") for r in p for field,title in [("value","目标图观测"),("prediction","同房来源预测")]],"预测目标图片",label,"%","目标图不进入自己的来源均值。",kind="bar"))
            room["tables"].append(table("split","历史来源／预测目标拆分",[("panel","面板",""),("metric","指标",""),("target","目标图片",""),("N","目标人数","人"),("history","历史来源图片",""),("history_N","来源人数",""),("observed","目标观测","%"),("prediction","预测","%")],[dict(panel=r["kind"],metric=names[r["metric"]],target=r["code_old"],N=int(r["N_old"]),history=r["source_codes_old"],history_N=r["source_N_old"],observed=100*float(r["value_"+side]),prediction=100*float(r["prediction_"+side]),image_id=r["image_id"],member_ids=members(r["image_id"])) for r in pred],"room"));mods["rooms"]=room
        return mods

    # Default opens the complete current descriptive census; computations are explicit conditions.
    scopes=[(DESCRIBE,"none",accepted)]
    scopes += [(COMPUTE,m,calc) for m in ["complete","affinity"]]
    scopes += [(c+" · 描述覆盖","none",[r for r in accepted if r["raw_condition"]==c]) for c in ["manual","oos","semi"]]
    for condition,method,pool in scopes:
        available=sorted({r["image_id"] for r in pool},key=lambda i:codes[i])
        groups=[("","","",available)]
        for building in sorted({i.split('_')[0] for i in available}):
            ids=[i for i in available if i.startswith(building+'_')];groups.append((building,"","",ids))
            for room in sorted({room_of.get(i,"未纳入人工同房组") for i in ids}):
                subset=[i for i in ids if room_of.get(i,"未纳入人工同房组")==room]
                groups.append((building,room,"",subset))
                groups.extend((building,room,i,[i]) for i in subset)
        for building,room,image,ids in groups:
            chosen=[r for r in pool if r["image_id"] in set(ids)]
            data["views"].append(dict(id=f"v{len(data['views'])}",version=VERSION,condition=condition,method=method,classification=CLASSIFICATION,building=building,room=room,image=image,image_ids=ids,modules=modules_for(ids,method,chosen,not building)))

    studio_text=(RESULTS/"cluster_screen_20260921/data.js").read_text(encoding="utf-8")
    studio=json.JSONDecoder().raw_decode(studio_text.split("window.STUDIO_DATA=",1)[1])[0]
    photos=re.findall(r'\{const image="(data:image/[^;]+;base64,[^"]+)";window.STUDIO_IMAGES\[(\d+)\]',studio_text)
    photos={int(i):value for value,i in photos}
    selected=[]
    for index,case in enumerate(studio["cases"]):
        if case["followup"]["code"] not in CASE_CODES:continue
        iid=case["image_id"];image_data=photos[index];suffix=".png" if image_data.startswith("data:image/png") else ".jpg"
        image_name="case-"+str(index)+suffix;(work/image_name).write_bytes(base64.b64decode(image_data.split(',',1)[1]))
        for method in ["complete","affinity"]:
            m=memberships[method,iid];labels=dict(zip(m["ids"],m["labels"]));variants=[]
            for v in case["variants"]:
                cid=v["source"]["canonical_annotation_id"]
                assert cid in labels
                assert v["source"]["effective_points"]==records[cid]["effective_points_1024x512"], "stale case points: "+cid
                geom=v["geometry"]
                if not geom:raise ValueError("selected case has no precomputed bound geometry: "+cid)
                for p in geom["pairs"]:
                    a,b=map(int,p["source_pair_id"].split(':')[1].split('/'))
                    assert p["top"]==records[cid]["effective_points_1024x512"][a-1]
                    assert p["bottom"]==records[cid]["effective_points_1024x512"][b-1]
                pair_ids=[p["source_pair_id"] for p in geom["pairs"]]
                variants.append(dict(id=cid,name=f"{records[cid]['worker_id']} · 簇{labels[cid]} · {len(pair_ids)*2}端点",kind="original",pointset_version=VERSION,member_ids=[records[cid]["worker_id"]],source_ids=["reviewed","screen","pro"],cluster_ids=[str(labels[cid])],pairs=copy.deepcopy(geom["pairs"]),connections=[[p,pair_ids[(j+1)%len(pair_ids)]] for j,p in enumerate(pair_ids)],geometry=copy.deepcopy(geom),geometry_pointset_version=VERSION))
            assert {v["id"] for v in variants}==set(m["ids"])
            cid=f"{case['followup']['code']}-{method}"
            data["cases"].append(dict(id=cid,image_id=iid,version=VERSION,condition=COMPUTE,method=method,classification=CLASSIFICATION,pointset_version=VERSION,source_ids=["screen","reviewed","pro"],width=1024,height=512,variants=variants))
            selected.append(dict(case_id=cid,image=image_name))
    assert len(selected)==8
    from .history import append_history
    append_history(data)
    if shared_x is not None:
        from .shared_x import append_shared_x
        append_shared_x(data, selected, Path(shared_x))
    validate(data)
    (work/"results.json").write_text(json.dumps(data,ensure_ascii=False,allow_nan=False),encoding="utf-8")
    manifest=dict(schema_version="research_dashboard_manifest_v1",release=RELEASE,results="results.json",selected_cases=selected)
    audit=dict(release=RELEASE,source_responses=len(records),accepted_responses=len(accepted),accepted_images=len(image_ids),calculation_responses=len(calc_ids),calculation_images=len(complete),cases=CASE_CODES,full_case_variants=sum(len(c["variants"]) for c in data["cases"]),views=len(data["views"]),source_points_match=True,recomputed_research=False,coverage_source=Path(coverage).resolve().relative_to(ROOT).as_posix() if coverage else None)
    audit["historical_versions"]={v["id"]:dict(description=v["description"],views=sum(x["version"]==v["id"] for x in data["views"])) for v in data["versions"] if v["id"]!=VERSION}
    return data,manifest,audit


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--out",type=Path,default=RESULTS/"research_dashboard_20260922");p.add_argument("--coverage",type=Path);p.add_argument("--shared-x",type=Path);args=p.parse_args()
    with tempfile.TemporaryDirectory(prefix="research-dashboard-input-") as tmp:
        work=Path(tmp);data,manifest,audit=connect(work,args.coverage,args.shared_x);build(manifest,work,args.out)
    checks=[dict(view=v["id"],version=v["version"],classification=v["classification"],condition=v["condition"],method=v["method"],images=len(v["image_ids"]),modules={k:dict(status=m["status"],metrics=m["metrics"],charts=[dict(id=c["id"],title=c["title"],rows=len(c["rows"]),unit=c["unit"]) for c in m["charts"]],tables=[dict(id=t["id"],title=t["title"],rows=len(t["rows"])) for t in m["tables"]]) for k,m in v["modules"].items()}) for v in data["views"] if not v["building"]]
    with ZipFile(args.out.with_suffix(".zip"),"a") as z:
        for name,value in [("INPUT_AUDIT.json",audit),("PRESENTATION_CHECKS.json",checks)]:
            (args.out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding="utf-8")
            z.write(args.out/name,name)
    print(json.dumps(audit,ensure_ascii=False))


if __name__=="__main__":main()
