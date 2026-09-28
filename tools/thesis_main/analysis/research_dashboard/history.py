"""历史展示适配：只读已保存数值，版本、人员池与判据显式隔离。"""
from collections import defaultdict
import csv
import gzip

from .connect_20260922 import RESULTS, MODULES, read, rows, module, metric, point, chart, table


def csv_rows(path):
    with (gzip.open(path, "rt", encoding="utf-8-sig") if path.suffix == ".gz" else path.open(encoding="utf-8-sig")) as f:
        return list(csv.DictReader(f))


def grouped(records, keys):
    result = defaultdict(list)
    for r in records:
        result[tuple(str(r[k]) for k in keys)].append(r)
    return result


BLOCKS = {"Q": "参考偏差", "T": "操作时间", "S": "scope判断", "B": "半自动行为"}
ROLES = {"quality_low": "参考偏差最低", "quality_high": "参考偏差最高", "time_low": "操作最快", "time_high": "操作最慢", "edit_low": "修改最少", "edit_high": "修改最多", "benefit_low": "净改善最低", "benefit_high": "净改善最高", "scope_reject_low": "误拒最低", "scope_reject_high": "误拒最高", "scope_accept_low": "误收最低", "scope_accept_high": "误收最高"}
PROFILES = ["无上限探针", "最多2簇／单人≤10%", "最多2簇／单人≤20%", "最多3簇／单人≤10%", "最多3簇／单人≤20%", "最多4簇／单人≤10%", "最多4簇／单人≤20%"]


def append_history(data):
    images = {r["id"] for r in data["images"]}
    participants = {r["id"] for r in data["participants"]}

    def catalog(key, id, label, description):
        if not any(r["id"] == id for r in data[key]):
            data[key].append(dict(id=id, label=label, description=description))

    def members(values, historical=False):
        values = values.split("|") if isinstance(values, str) else values
        prefix = historical if isinstance(historical,str) else "h0910:"
        result = [(prefix + "W" + str(w)) if historical else w for w in values]
        for w in result:
            if w not in participants:
                data["participants"].append(dict(id=w, label=w.replace("h0910:", "历史09-10 ").replace("h0904:","历史09-04 ")))
                participants.add(w)
        return result

    def add(version, condition, method, classification, mods, ids=()):
        all_ids = set(ids)
        for m in mods.values():
            for t in m["tables"] + m["charts"]:
                for r in t["rows"]:
                    if r.get("image_id"):
                        all_ids.add(r["image_id"])
        for iid in sorted(all_ids - images):
            data["images"].append(dict(id=iid, building=iid.split("_")[0], room="历史分组未接入", scene=iid, source_ids=[version]))
            images.add(iid)
        modules = {k: module("本历史切片未接入该模块；请明确切换数据版本。", "not_computed") for k in MODULES}
        modules.update(mods)
        data["views"].append(dict(id=f"v{len(data['views'])}", version=version, condition=condition, method=method, classification=classification, building="", room="", image="", image_ids=sorted(all_ids), modules=modules))

    def t(id, title, records, specs, source):
        return table(id, title, [(k,label,"旧OSPA30分数" if unit=="OSPA30" else unit) for k,label,unit in specs], records, source)

    old10 = "history-20260910"
    old21 = "history-20260921-pre-review"
    audited = "history-20260921-audited"
    for id, label, description in [
        (old10, "历史09-10 · 26人／后续20人分类", "303套Ward配置；全26人与后续20人分开，组号不能跨目标楼直接对应。历史q95／OSPA判据未在09-22新分区复验。"),
        (old21, "历史09-21 · 终审前2393份", "严格池240图2393份；旧留建筑名单及25.6px完整链接／真实代表半径。未随终审2444份或09-22新算法复算。"),
        (audited, "历史09-21 · 独立审查研究", "2444份冻结池的早期完整链接／代表半径研究；仅采用外层隔离修正预测。不是09-22亲近度候选结果。")]:
        catalog("versions", id, label, description)
        catalog("sources", id, label, {old10: "worker_four_block_exploration_20260910_v1：group_count_extension、subtype_stage_validation、readable_same39_comparison.csv。", old21: "new_manual_analysis_20260921/convergence_and_composition：RUN、subtype、composition、roster及room表。", audited: "panorama_research_received_20260921：独立审查与纳入决定、audit/independent_checks.json、outer_fold_corrected_model_predictions.csv及已复核original_package/results。"}[id])
    for id, label, desc in [("old-q95", "历史q≥0.95", "同点数硬门，q取boundary/wallwall相似度较小值；历史图结构稳定判据。"), ("old-ospa30_t6", "历史OSPA30≤6", "同点数硬门、历史OSPA30阈值6；不是最大端点25.6px。"), ("old-complete", "历史完整链接 · 25.6px", "终审前最大端点距离完整链接；不是09-22重新核验版本。"), ("old-representative", "历史真实代表半径 · 25.6px", "终审前围绕真实作答的代表半径；不是09-22直径＋亲近度方法。"), ("old-composition", "历史四人覆盖 · 原表", "固定四名独立验证者；图上与球面读数分别列出，不重算阈值。"), ("audited-probes", "历史数值探针 · 独立审查", "冻结旧端点判据；模型预测使用已修正外层留建筑结果。")]:
        catalog("methods", id, label, desc)
    catalog("classifications", "historical-unclassified", "历史汇总／非分类结果", "不将未分类当作一个已验证人群。")
    catalog("methods", "old-scene", "历史用途粗类 · 跨建筑预测", "图上25.6px／球面9°U(k)分别列出；不是持续起点，也不是四人分类比较。")

    # 全303配置保留，不按稳定性筛选；每个判据单独选择。
    p = RESULTS / "worker_four_block_exploration_20260910_v1"
    counts = rows(p / "group_count_extension/group_counts.csv")
    full = grouped(read(p / "group_count_extension/group_members.json"), ["cohort", "model", "groups"])
    repeat = grouped(rows(p / "group_count_extension/named_repeatability.csv"), ["cohort", "model", "groups"])
    availability = grouped(rows(p / "subtype_stage_validation/classification_availability.csv"), ["cohort", "model", "groups"])
    coverage = grouped(csv_rows(p / "subtype_stage_validation/named_coverage.csv.gz"), ["cohort", "model", "groups"])
    summary = grouped([r for r in rows(p / "subtype_stage_validation/named_subtype_summary.csv") if r["subset"] == "reference_allowed" and r["horizon"] in ["8", "10", "13"] and int(r["k"]) == int(r["horizon"])-5], ["cohort", "model", "groups", "config"])
    pool = {(r["image_id"], r["pool"]): members(r["worker_ids"], True) for r in csv_rows(p / "subtype_stage_validation/pool_members.csv.gz")}
    paired = grouped([r for r in csv_rows(p / "subtype_stage_validation/named_paired_curves.csv.gz") if r["reference_allowed"] == "True" and r["horizon"] in ["8", "10", "13"] and int(r["k"]) == int(r["horizon"])-5], ["cohort", "model", "groups", "config"])
    assert len(counts) == 303
    for c in counts:
        key = (c["cohort"], c["model"], c["groups"])
        label = "＋".join(BLOCKS[k] for k in c["model"]) + f" · Ward {c['groups']}组"
        class_id = f"ward-{c['model']}-{c['groups']}"
        catalog("classifications", class_id, label, "四信息块等权；全量名单仅解释候选组，评价时排除目标楼重新分类。")
        roster = [dict(group=r["group"], n=r["n"], profile=r["axis_means"], member_ids=members(r["worker_ids"], True)) for r in full[key]]
        assert sum(r["n"] for r in roster) == int(c["workers"])
        repetition = [dict(role=ROLES[r["role"]], support="主要求6份/3楼" if r["support"] == "primary_6rows_3buildings" else r["support"], attempts=int(r["attempts"]), available=int(r["available"]), both=int(r["both_at_least_2"]), overlap=float(r["jaccard_median"]) if r["jaccard_median"] else None, adjusted=float(r["adjusted_jaccard_median"]) if r["adjusted_jaccard_median"] else None) for r in repeat[key]]
        for config in ["q95", "ospa30_t6"]:
            ss = summary[key + (config,)]
            note = "历史人员池；Q为参考偏差，T为log(1+有效秒数)，S只含scope误判，B为修改与净改善。全量画像是人员效应，不是秒数或准确率。同图同人数随机对照；H=8/10/13，k=H−5，200顺序、80%明确稳定。仅可评分参考图；不同子类面板不同。未在09-22算法复验。"
            m = module(note, metrics=[metric("历史名册", 26 if c["cohort"] == "all26" else 20, "人", "人员范围独立于当前25人。", old10), metric("全量可分类", int(c["workers"]), "人", "本配置有足够训练资料的人员。", old10), metric("候选组数", int(c["groups"]), "组", "单人组保留，不等同人群类型成立。", old10)])
            m["charts"].append(chart("sizes", "全量候选组人数", [point("组"+str(r["group"]), r["n"], "人数", members=r["member_ids"], source=old10) for r in roster], "组", "人数", "人", "全量描述名单；不替代逐目标楼名单。", kind="bar"))
            for h in ["8", "10", "13"]:
                s = [r for r in ss if r["horizon"] == h]
                if s:
                    m["charts"].append(chart("stage-"+h, f"H={h} · 同图同人数明确稳定", [point(ROLES[r["role"]], 100*int(r[k])/int(r["images"]), label, source=old10, denominator=int(r["images"]), numerator=int(r[k])) for r in s for k,label in [("confirmed_images", "该子类"), ("baseline_confirmed_images", "同图随机")]], "训练特征对应的具体子类", "明确稳定图片比例", "%", "每行同图同人数；跨行图片集合可能不同。", kind="bar"))
            m["tables"] = [t("roster", "全量成员与画像（原始效应单位）", roster, [("group","组",""),("n","人数","人"),("profile","各轴人员效应均值","")], old10), t("repeat", "名单重复性 · 主要求与补充诊断分列", repetition, [("role","具名子类",""),("support","支持要求",""),("attempts","重复次数","次"),("available","可比较","次"),("both","两边均≥2人","次"),("overlap","Jaccard中位数",""),("adjusted","扣除随机重合后的中位数","")], old10)]
            m["tables"].append(t("availability", "目标图分类可用性（不把无法分类当人数不足）", [dict(image_id=r["image_id"],classification="可分类" if r["classification_available"]=="True" else "训练资料不足，未分类") for r in availability[key]], [("classification","分类状态","")], old10))
            role_coverage=grouped(coverage[key],["role"])
            m["tables"].append(t("coverage", "具名子类图内人数覆盖（含不足7人）", [dict(role=ROLES[role],images=len(rr),insufficient=sum(r["status"]=="insufficient_people" for r in rr),min_n=min(int(r["target_group_n"]) for r in rr),max_n=max(int(r["target_group_n"]) for r in rr)) for (role,),rr in role_coverage.items()], [("role","具名子类",""),("images","可分类目标图","图"),("insufficient","该类不足7人","图"),("min_n","最少可用成员","人"),("max_n","最多可用成员","人")],old10))
            m["tables"].append(t("summary", "各子类稳定状态与参考偏差", [dict(role=ROLES[r["role"]], H=int(r["horizon"]), images=int(r["images"]), buildings=int(r["buildings"]), confirmed=int(r["confirmed_images"]), unknown=int(r["undetermined_images"]), not_reached=int(r["not_reached_images"]), random=int(r["baseline_confirmed_images"]), error=float(r["reference_error"]), random_error=float(r["baseline_reference_error"])) for r in ss], [("role","子类",""),("H","观察终点","人"),("images","同图分母","图"),("buildings","建筑","栋"),("confirmed","明确稳定","图"),("unknown","未决","图"),("not_reached","该起点范围未达标","图"),("random","随机明确稳定","图"),("error","代表参考偏差","OSPA30"),("random_error","随机参考偏差","OSPA30")], old10))
            pr = [dict(image_id=r["image_id"], role=ROLES[r["role"]], H=int(r["horizon"]), k=int(r["k"]), L=100*float(r["lower"]), U=100*float(r["upper"]), random_L=100*float(r["baseline_lower"]), random_U=100*float(r["baseline_upper"]), random_pool=pool[r["image_id"],r["baseline_pool"]], member_ids=pool[r["image_id"],r["pool"]]) for r in paired[key+(config,)]]
            m["tables"].append(t("paired", "逐图具体子类与同人数对照（L/U非置信区间）", pr, [("role","子类",""),("H","无放回抽取人数","人"),("k","候选起点","人"),("L","明确稳定顺序","%"),("U","明确或可能稳定顺序","%"),("random_L","随机L","%"),("random_U","随机U","%"),("random_pool","随机抽样人员池","")], old10))
            if not ss:
                m["note"] += " 当前H及可评分参考图范围没有可展示结果，不能记为零或永不收敛。"
            add(old10, "全部26人" if c["cohort"] == "all26" else "后续20人", "old-"+config, class_id, {"people":m})

    # 粗分不是Ward Q二分，也不是09-21 Q_2；核对原生产器的标签顺序。
    coarse = rows(p / "readable_same39_comparison.csv")
    assert [int(r["confirmed"]) for r in coarse] == [17,9,18,8,8]
    assert [r["name"] for r in coarse] == ["质量偏差较低组","质量偏差较高组","较快组","较慢组","全体随机组合"]
    names = ["质量中位数·低偏差", "质量中位数·高偏差", "时间·较快", "时间·较慢", "全体随机"]
    catalog("classifications", "median-same39", "质量中位数粗分／快慢 · 共同39图", "Q中位数10/10仅作历史粗分，与Ward自动Q和09-21 Q_2不同。")
    m = module("后续20人；同39图12楼、每组8人，k=3至H=8，200顺序。粗分全量10/10、快慢8/12；只在同图面板比较。", charts=[chart("same39", "同39图 · 明确稳定／未决／未达标", [point(name,int(r[k]),label,source=old10,denominator=39,numerator=int(r[k])) for name,r in zip(names,coarse) for k,label in [("confirmed","明确稳定"),("undetermined","未决"),("not_reached","允许起点范围未达标")]], "人员组", "图片数", "图", "不是第8人已收敛，也不是未来停止保证。",kind="bar")], tables=[t("same39", "稳定与代表参考偏差分开评价", [dict(name=name,confirmed=int(r["confirmed"]),unknown=int(r["undetermined"]),not_reached=int(r["not_reached"]),error=float(r["reference_error"])) for name,r in zip(names,coarse)], [("name","人员组",""),("confirmed","明确稳定","图/39"),("unknown","未决","图/39"),("not_reached","起点范围未达标","图/39"),("error","代表参考偏差","OSPA30")],old10)])
    stability=rows(p/"stability_summary.csv")
    m["note"] += " 代表参考偏差使用旧OSPA30分数，不是像素或正确率。"
    m["tables"].append(t("coarse-members","粗分与快慢的全量历史名单",[dict(model=r["model"],group=r["label"],member_ids=members([r["worker_id"]],True)) for r in rows(p/"members.csv") if r["variant"]=="primary" and r["cohort"]=="current20" and r["panel"]=="common" and r["model"] in ["Q_median2","T"]],[("model","分类",""),("group","全量组号","")],old10))
    m["tables"].append(t("repeat-all","整套分型名单重复性（ARI，非标法稳定）",[dict(model=r["model"],support=r["half_support"],attempts=int(r["attempts"]),available=int(r["valid"]),ari=float(r["ari_median"]) if r["ari_median"] else None) for r in stability if r["variant"]=="primary" and r["cohort"]=="current20" and r["panel"]=="native"],[("model","历史分类",""),("support","支持要求",""),("attempts","尝试次数","次"),("available","可比较次数","次"),("ari","调整兰德指数中位数","")],old10))
    add(old10,"后续20人","old-q95","median-same39",{"people":m})
    multi=csv_rows(p/"subtype_stage_validation/confirmed_multi_examples.csv.gz")
    assert len({r["image_id"] for r in multi})==4
    multi_rows=[dict(image_id=r["image_id"],model=r["model"],groups=int(r["groups"]),role=ROLES[r["role"]],H=int(r["horizon"]),k=int(r["k"]),multi=int(r["stable_multi"]),single=int(r["stable_single"]),unknown=int(r["unknown"]),changing=int(r["changing"]),member_ids=pool[r["image_id"],r["pool"]]) for r in multi]
    assert all(r["multi"]+r["single"]+r["unknown"]+r["changing"]==200 for r in multi_rows)
    add(old10,"全部26人 · 稳定多簇存在性案例","old-q95","historical-unclassified",{"stability":module("旧q95判据，4张可评分参考图。多个配置/子类描述可引用同一人员池，243行不是243个独立发现。其中H=21、起点15/16是存在性例子；全表也含其他终点，不能推出任一子类普遍收敛。8人终点、起点2/3的检查无法在起点形成两个各≥2人的支持簇。",tables=[t("multi","全部已保存稳定多簇引用及具体成员",multi_rows,[("model","分类轴",""),("groups","分类组数","组"),("role","具名子类",""),("H","终点","人"),("k","起点","人"),("multi","稳定多簇","顺序/200"),("single","稳定单簇","顺序/200"),("unknown","未知","顺序/200"),("changing","变化","顺序/200")],old10)])})

    append_pre_review(data, add, catalog, members, t, old21)
    append_audited(data, add, catalog, members, t, audited)
    # 早期证据分档只展示旧名册，不接入其旧资格与独立性解释。
    v="history-20260904"
    catalog("versions",v,"历史09-04 · H/L/U证据分档","C1 Core当前20人的旧Q_GT证据分档；与Ward类别、OSPA偏差及当前资格分开。")
    catalog("sources",v,"旧Manual证据分档","worker_manual_strata_audit_20260904_v1/manual_core_full_profiles.csv、manual_worker_calculation_simple.csv；仅复用名册证据。")
    catalog("methods","old-qgt","旧Q_GT任务校正效应","Q_GT人员＋任务固定效应；建筑→任务bootstrap概率，正方向为较高参考质量证据。")
    catalog("classifications","old-hlu","H/L/U · 证据分档","P(中心化效应>0)≥0.8为H、≤0.2为L，其余U未定；U不是第三种人格。")
    p=RESULTS/"worker_manual_strata_audit_20260904_v1"
    profiles=rows(p/"manual_core_full_profiles.csv")
    stability=rows(p/"manual_worker_calculation_simple.csv")
    for (variant,), rr in grouped(profiles,["classification_variant"]).items():
        groups=grouped(rr,["evidence_stratum"])
        m=module("历史C1 Core 20人；H/L/U是参考质量证据状态，U未定而非第三类人。Q_GT方向与OSPA参考偏差不同，不作跨量纲比较。本表不改变当前资格，也不复用旧独立性解释。",charts=[chart("hlu","旧全量证据人数",[point(s.split('_')[0],len(r),"历史人数",members=members([x["worker_id"] for x in r],"h0904:"),source=v) for (s,),r in groups.items()],"证据档","人数","人","两个历史数据版本分别选择；不是人数配额。",kind="bar")])
        m["tables"]=[t("profiles","逐人历史证据与支持",[dict(effect=float(r["worker_effect_centered"]),probability=float(r["probability_effect_positive_building_bootstrap"]),stratum=r["evidence_stratum"].split('_')[0],tasks=int(r["quality_task_support"]),buildings=int(r["quality_building_support"]),member_ids=members([r["worker_id"]],"h0904:")) for r in rr],[("effect","中心化Q_GT效应","旧Q_GT"),("probability","正效应bootstrap概率","比例"),("stratum","证据档",""),("tasks","支持任务","题"),("buildings","支持建筑","栋")],v),t("stability","跨11楼折与两历史版本的证据保持",[dict(H=int(r["留一building_H次数"]),U=int(r["留一building_U次数"]),L=int(r["留一building_L次数"]),stable=r["跨11个building及两版本稳定类别"],member_ids=members([r["worker_id"]],"h0904:")) for r in stability],[("H","留楼H","次/11"),("U","留楼U","次/11"),("L","留楼L","次/11"),("stable","跨楼及两版本状态","")],v)]
        add(v,variant,"old-qgt","old-hlu",{"people":m})
    v="history-20260909-index"
    catalog("versions",v,"历史09-09 · 单维分类索引","参考偏差单维分档探索；仅登记已存在研究，不混入后续Ward四信息块结果。")
    catalog("sources",v,"单维分类原研究","worker_reference_feasibility_20260909_v1/pooled/groups/README_ZH.md；2025个人—图单元/184图/22建筑/26人。")
    catalog("classifications","old-quantile-ward","单维quantile／Ward · 2–5组","对OSPA30/60参考偏差人员效应作分位数分档或Ward分类；全26人与后续20人分别研究。")
    catalog("methods","old-worker-effect","历史参考偏差人员效应","人员分档索引；不指定标注分簇判据。")
    add(v,"旧26人／20人分别研究","old-worker-effect","old-quantile-ward",{"people":module("单维人员效应分档索引，不等同q95标注分簇，也不等同四信息块303配置。原研究比较OSPA30/60、2–5组；全量名单只作解释，验证按留建筑重新分组。本展示未迁移其完整预测表。",tables=[t("index","已有分类研究索引",[dict(scheme="quantile",axis="OSPA30/60人员效应",groups="2、3、4、5",rule="分位数分档；同值不强拆"),dict(scheme="Ward",axis="OSPA30/60人员效应",groups="2、3、4、5",rule="一维Ward；不预设人数均衡")],[("scheme","分档方法",""),("axis","训练轴",""),("groups","组数",""),("rule","定义","")],v)])})


def append_pre_review(data, add, catalog, members, t, version):
    p = RESULTS / "new_manual_analysis_20260921/convergence_and_composition"
    ss = rows(p / "subtype_summary.csv")
    roster = rows(p / "personnel_roster_snapshot.csv")
    submembers = {(r["config"],str(r["subtype"]),r["image_id"]):r for r in read(p/"subtype_members.json")}
    matched = csv_rows(p/"subtype_matched.csv.gz")
    comp = rows(p/"composition_common_panel.csv")
    exact = csv_rows(p/"composition_exact.csv.gz")
    configs = sorted({r["config"] for r in roster})
    for config in configs:
        classid = "old-"+config
        label = "三轴修改／参考偏差／时间" if config=="TRI_3" else "＋".join(BLOCKS[k] for k in config.split('_')[0])
        catalog("classifications",classid, config+" · "+label,"复用旧训练轴与留建筑名单；数字组号跨目标楼不自动代表固定人群。")
        for method in ["complete","representative"]:
            selected = [r for r in ss if r["config"]==config and r["method"]==method]
            summary = [dict(subtype=r["subtype"],profile=PROFILES[int(r["profile"])],images=int(r["images"]),buildings=int(r["buildings"]),H=f"{r['min_H']}–{r['max_H']}",L=100*float(r["L"]),random_L=100*float(r["random_L"]),gain=100*float(r["gain"]),low=100*float(r["interval_low"]),high=100*float(r["interval_high"])) for r in selected]
            m=module("终审前严格池240图2393份。每个具体子类实际H≥5；检查H−3至H尾段，200条同源顺序，同图同H随机对照。L是稳定顺序比例，非可靠人员比例；建筑等权区间为固定分类条件探索区间。全部7种探针保留；不是完整精确起点。")
            m["charts"]=[chart("subtype", "具体子类 · 各上限下稳定顺序比例", [point("组"+r["subtype"]+" · "+r["profile"],r[k],label,source=version,denominator=r["images"]) for r in summary for k,label in [("L","子类"),("random_L","同图同人数随机")]],"子类与上限","建筑等权稳定顺序比例","%",m["note"],kind="bar")]
            m["tables"]=[t("summary","全部上限与探索区间",summary,[("subtype","子类",""),("profile","探针上限",""),("images","图片","图"),("buildings","建筑","栋"),("H","实际H","人"),("L","子类稳定顺序","%"),("random_L","随机稳定顺序","%"),("gain","差值","百分点"),("low","区间下限","百分点"),("high","区间上限","百分点")],version)]
            pr=[]
            for r in matched:
                if r["config"]!=config or r["method"]!=method:continue
                sm=submembers[config,r["subtype"],r["image_id"]]
                assert int(r["H"])==len(sm["workers"])
                pr.append(dict(image_id=r["image_id"],code=r["code"],subtype=r["subtype"],profile=PROFILES[int(r["profile"])],H=int(r["H"]),L=100*float(r["L"]),U=100*float(r["U"]),random_L=100*float(r["random_L"]),random_U=100*float(r["random_U"]),member_ids=members(sm["workers"])))
            m["tables"].append(t("matched","逐图同人数与完整具体成员",pr,[("code","图片短名",""),("subtype","子类",""),("profile","上限",""),("H","实际H","人"),("L","子类L","%"),("U","子类U","%"),("random_L","随机L","%"),("random_U","随机U","%")],version))
            m["tables"].append(t("roster","排除目标建筑后的分类名单",[dict(building=r["heldout_building"],subtype=r["subtype"],member_ids=members([r["worker"]])) for r in roster if r["config"]==config],[("building","排除建筑",""),("subtype","该折子类","")],version))
            add(version,"严格池2393份 · 子类尾段", "old-"+method,classid,{"people":m})
        m=module("真实四人组合的局部覆盖结果，不等于全部人数／配比／顺序已重放。87725个重叠团队不是独立样本；固定4名验证者与团队不重叠。图上与球面测量分别列出。")
        m["tables"]=[t("composition","各图片全部已保存配比",[dict(image_id=r["image_id"],code=r["code"],pattern=r["pattern"],signature=r["signature"],distance=r["metric"],teams=int(r["teams"]),uncovered=100*float(r["uncovered"]),incompatible=100*float(r["incompatible"])) for r in exact if r["config"]==config],[("code","图片短名",""),("pattern","配比形状",""),("signature","具体子类计数",""),("distance","距离读数",""),("teams","重叠真实团队","个"),("uncovered","验证者未覆盖","%"),("incompatible","不兼容","%")],version),t("common","四套三分类共同56图14楼 · AABC−AAAA",[dict(distance=r["metric"],images=int(r["images"]),buildings=int(r["buildings"]),delta=100*float(r["delta"]),low=100*float(r["interval_low"]),high=100*float(r["interval_high"])) for r in comp if r["config"]==config],[("distance","距离读数",""),("images","共同图片","图"),("buildings","建筑","栋"),("delta","未覆盖差","百分点"),("low","区间下限","百分点"),("high","区间上限","百分点")],version)]
        add(version,"严格池2393份 · 四人配比", "old-composition",classid,{"people":m})
    catalog("classifications", "old-classification-overview", "人员分类对照 · 定义与子类末段稳定", "终审前Q_2、QT_2、QT_3的固定上限展示；不同面板不作排名。T/S/B沿用独立历史入口。")
    definitions = [
        dict(scheme="Q_2", definition="相对指定适用参考的偏差，数据驱动二分类；不强制均分。", evidence="09-21终审前：低参考偏差子类的末段稳定；不是09-10中位数10/10名单。"),
        dict(scheme="QT_2／QT_3", definition="参考偏差与有效操作时间联合二／三分类。", evidence="09-21终审前：组号为历史训练折标签；未核对画像不能称快且准。"),
        dict(scheme="T", definition="有效操作快慢；独立于参考偏差的行为轴。", evidence="09-10：名单重复性与稳定性分别展示；快组稳定不等于代表更接近参考。"),
        dict(scheme="S", definition="in_scope／out_of_scope判断的误接受、误拒绝；不是封闭／延伸结构型。", evidence="09-10：规则判断与可分类覆盖；不可标图仅9张，重复分型支持有限。"),
        dict(scheme="B／Q＋B", definition="半自动轮廓改动量与参考净改善；包含净改善时仍依赖参考。", evidence="09-10：行为画像、名单重复性、质量预测、子类稳定是不同检验；质量预测改善不能当收敛增益。"),
        dict(scheme="QTSB／三轴联合", definition="多信息块联合；三轴方案为修改、参考偏差与时间。", evidence="09-21终审前已有子类与四人组成结果；配比不固定AABC，具体成员另列。"),
    ]
    focus_names = {("Q_2","1"):"Q_2 · 低参考偏差类（历史1）", ("QT_2","1"):"QT_2 · 历史子类1", ("QT_3","2"):"QT_3 · 历史子类2"}
    columns = [("config","分类方案",""),("subtype","历史子类",""),("profile","探针上限",""),("images","各自图片面板","图"),("buildings","等权建筑数","栋"),("H","图内实际H","人"),("L","子类稳定顺序","%"),("random_L","同图同人数随机","%"),("gain","成对差值","百分点"),("low","探索区间下限","百分点"),("high","探索区间上限","百分点")]
    for method in ["old-complete", "old-representative"]:
        focus=[]; sensitivity=[]
        for (config, subtype), name in focus_names.items():
            source_view=next(v for v in data["views"] if v["version"]==version and v["method"]==method and v["classification"]=="old-"+config)
            saved=source_view["modules"]["people"]["tables"][0]["rows"]
            focus.append(dict(next(r for r in saved if r["subtype"]==subtype and r["profile"]==PROFILES[4]), config=config))
            if config=="Q_2":
                sensitivity=[dict(r,config=config) for r in saved if r["subtype"]==subtype and r["profile"]!=PROFILES[0]]
        note="历史09-21终审前2393份／240图；最新2444份加全局亲近度分区尚未完整复验。固定总簇数≤3、单人作答≤20%（profile=4）。按目标建筑外资料分类，名单随折变化，不强制均分。每图实际H、200条共享顺序、H−3至H末段的建筑等权稳定顺序比例；不是正确率、明确收敛图片比例或精确起点。每行仅与同图同人数随机对照比较；图、楼与H面板不同，不能直接排名。区间为固定分类条件下的探索区间，未作多配置选择校正和新人外部确认。人员分类、标注分簇、质量筛选彼此独立，分类和单人簇率不自动构成排除资格。"
        overview=module(note, charts=[chart("focus", "统一上限下的子类与同人数随机对照（不同面板）", [point(focus_names[r["config"],r["subtype"]],r[k],label,source=version) for r in focus for k,label in [("L","子类"),("random_L","同图同人数随机")]],"历史子类","建筑等权稳定顺序比例","%","分母由下表分别列出：建筑等权；每图200条顺序，图内H各异。未将图片数当作比例分母。",kind="bar")], tables=[
            t("focus","固定上限 · 各自面板与差值探索区间",focus,columns,version),
            t("q-sensitivity","Q_2低参考偏差类 · 全部六种上限敏感性",sensitivity,columns,version),
            t("definitions","分类含义与证据边界（各历史入口独立）",definitions,[("scheme","分类",""),("definition","分类依据",""),("evidence","已有检验与边界","")],version),
        ])
        for row in overview["tables"][-1]["rows"]:
            if row["scheme"] in {"T", "S", "B／Q＋B"}:
                row["source_ids"]=["history-20260910"]
        add(version,"分类对照 · 固定上限与完整敏感性",method,"old-classification-overview",{"people":overview})
    teams=csv_rows(p/"actual_teams.csv.gz")
    assert len(teams)==87725
    tr=[]
    for r in teams:
        workers=r["workers"].split('|');validation=r["validation"].split('|')
        assert len(set(workers))==4 and not set(workers)&set(validation)
        tr.append(dict(image_id=r["image_id"],team=r["team"],validation=members(validation),image_uncovered=100*float(r["image_uncovered"]),sphere_uncovered=100*float(r["sphere_uncovered"]),member_ids=members(workers)))
    add(version,"严格池2393份 · 全部具体四人团队", "old-composition","historical-unclassified",{"people":module("87725个团队覆盖89图16楼；团队互相重叠，不是独立样本。表格可按图片或人员搜索；配比标签另见各分类方案的逐楼名单。",tables=[t("teams","全部具体团队及不重叠验证者",tr,[("team","图内团队编号",""),("validation","固定验证者",""),("image_uncovered","图上未覆盖","%"),("sphere_uncovered","球面未覆盖","%")],version)])})
    # 原始逐图起点保持缺失；不以组均值起点替换每图中位起点。
    onsets=[r for r in rows(p/"image_onsets.csv") if r["pool"]=="strict"]
    splits=[r for r in csv_rows(p/"room_all_splits.csv.gz") if r["pool"]=="strict" and r["balanced"]=="True" and int(r["source_n"])>=int(r["target_n"])]
    for method in ["complete","representative"]:
        r=[dict(image_id=x["image_id"],code=x["code"],tail=int(x["tail"]),profile=PROFILES[int(x["profile"])],N=int(x["N"]),possible=int(float(x["possible_onset"])) if x["possible_onset"] else None,conservative=int(float(x["conservative_onset"])) if x["conservative_onset"] else None,state=x["status"]) for x in onsets if x["method"]==method]
        split_groups=grouped([x for x in splits if x["method"]==method],["tail","profile"])
        sr=[dict(tail=int(tail),profile=PROFILES[int(profile)],splits=len(rr),median=sum(x["median_identified_pair"]=="True" for x in rr),group_curve=sum(x["identified_pair"]=="True" for x in rr)) for (tail,profile),rr in split_groups.items()]
        assert all(x["splits"]==827 for x in sr)
        add(version,"严格池2393份 · 持续起点", "old-"+method,"historical-unclassified",{"rooms":module("同房持续起点不是端点分歧预测。近均分且来源不少于目标，共827有方向拆分（重叠、非独立样本）。逐图起点中位数与组平均曲线分别计数。空起点不是0，未识别不是永不收敛。组内最短H补充控制与全部拆分仍保留在原分析包。",tables=[t("splits","同房持续起点：可评分拆分与全部分母",sr,[("tail","后续窗口","人"),("profile","上限",""),("splits","全部拆分","个"),("median","两侧中位起点明确","个"),("group_curve","两侧组平均曲线起点明确","个")],version),t("onsets","逐图持续起点与未决状态",r,[("code","图片短名",""),("tail","后续窗口","人"),("profile","上限",""),("N","实际H","人"),("possible","可能起点","人"),("conservative","保守起点","人"),("state","原始状态","")],version)])})
    scenes=[r for r in read(p.parent/"room_scene_summary.json") if r["kind"]=="scene" and r["pool"]=="strict"]
    scene_predictions=[r for r in read(p.parent/"scene_predictions.json") if r["pool"]=="strict"]
    for r in scene_predictions:
        assert all(i.split('_')[0]!=r["building"] for i in r["source_images"])
    m=module("终审前严格2393份池；用途粗类来自人工空间台账，未知类不当相似场景。来源排除目标建筑，先房间块再建筑等权；总体基线用相同楼外信息。图上25.6px与球面9°分别列出，未按结果择优。条件区间只对固定预测重采样；U(k)不是持续起点。")
    m["charts"]=[chart("scene","跨建筑同场景预测 · 同面板参照",[point(r["metric"]+" · U("+str(r["k"])+")",100*r[key],label,source=version,denominator=r["images"]) for r in scenes if r["scope"]=="all" for key,label in [("MAE","同用途粗类"),("baseline_MAE","全部楼外图")]],"读数与人数","MAE","百分点",m["note"],kind="bar")]
    m["tables"]=[t("scene","各用途类别及总体面板（含负结果）",[dict(scene=r["scope"],distance=r["metric"],k=r["k"],images=r["images"],buildings=r["buildings"],MAE=100*r["MAE"],baseline=100*r["baseline_MAE"],gain=100*r["gain"],low=100*r["building_interval95"][0],high=100*r["building_interval95"][1]) for r in scenes],[("scene","场景类别",""),("distance","距离读数",""),("k","观察人数","人"),("images","目标图片","图"),("buildings","建筑","栋"),("MAE","同类MAE","百分点"),("baseline","总体MAE","百分点"),("gain","误差改善","百分点"),("low","区间下限","百分点"),("high","区间上限","百分点")],version),t("scene-targets","逐目标图与跨建筑来源",[dict(image_id=r["image_id"],code=r["code"],scene=r["scene"],distance=r["metric"],k=r["k"],observed=100*r["value"],prediction=100*r["prediction"],baseline=100*r["baseline"],sources=r["source_images"]) for r in scene_predictions],[("code","短名",""),("scene","场景",""),("distance","距离读数",""),("k","人数","人"),("observed","观测U(k)","%"),("prediction","预测U(k)","%"),("baseline","楼外总体预测","%"),("sources","同类来源图片","")],version)]
    add(version,"严格池2393份 · 同场景跨建筑","old-scene","historical-unclassified",{"rooms":m})


def append_audited(data, add, catalog, members, t, version):
    p=RESULTS/"panorama_research_received_20260921"
    audit=read(p/"audit/independent_checks.json")
    predictions=rows(p/"audit/outer_fold_corrected_model_predictions.csv")
    names={"N_only":"仅人数N","N_plus_roster":"N＋人员配比","N_plus_model_counts":"N＋模型角数","N_plus_model_counts_gaps":"N＋模型角数及差异","N_plus_model_and_roster":"N＋模型特征＋人员配比"}
    f=module("历史探索，使用已修正外层留建筑预测：同一外层折的训练图与测试图人员画像均排除目标建筑。三个目标分别保留；冻结Ridge参数与面板。未重建神经推理，未核清预训练暴露；不是当前亲近度算法结果。U(k)是有限池未覆盖，不是持续稳定起点。")
    for outcome in ["U5","U8","pair_disagreement"]:
        s=[r for r in audit["corrected_model_summary"] if r["outcome"]==outcome]
        f["charts"].append(chart(outcome,outcome+" · 修正外层隔离后的预测误差",[point(names[r["config"]],100*r["corrected_MAE"],"建筑等权MAE",source=version,denominator=r["images"]) for r in s],"输入特征","建筑等权MAE","百分点",f["note"],kind="bar"))
    f["tables"]=[t("predictions","全部修正逐图预测（不使用原错误版本）",[dict(image_id=r["image_id"],building=r["building"],outcome=r["outcome"],config=names[r["config"]],value=100*float(r["value"]),prediction=100*float(r["prediction"]),error=100*float(r["absolute_error"])) for r in predictions],[("building","建筑",""),("outcome","预测目标",""),("config","特征方案",""),("value","观测","%"),("prediction","修正预测","%"),("error","绝对误差","百分点")],version)]
    f["tables"].append(t("intervals","固定模型与面板条件下的探索区间",[dict(outcome=r["outcome"],config=names[r["config"]],images=r["images"],buildings=r["buildings"],gain=100*r["conditional_gain"]["mean"],low=100*r["conditional_gain"]["interval95"][0],high=100*r["conditional_gain"]["interval95"][1]) for r in audit["corrected_model_summary"]],[("outcome","目标",""),("config","方案",""),("images","图片","图"),("buildings","建筑","栋"),("gain","相对仅人数的MAE改善","百分点"),("low","区间下限","百分点"),("high","区间上限","百分点")],version))
    results=p/"original_package/results"
    comp=read(results/"composition_summary.json")
    examples=rows(results/"same_composition_member_examples.csv")
    people=module("同配比换真人的波动：严格成对分歧目标、可变化图片面板、有限组合抽样。不同人数与分类分开；同配比内部方差占比的均值／中位数不是因果贡献。连续画像预测的是相对同图均值的偏离，不是正确率或新人预测。")
    people["charts"]=[chart("within","同配比内部波动占比",[point(r["config"]+" · "+str(r["n"])+"人",100*r["mean_within_fraction"],"可变化图等权均值",source=version,denominator=r["variable_images"]) for r in comp],"分类与人数","同配比内方差占总方差","%",people["note"],kind="bar")]
    people["tables"]=[t("composition","组成与具体成员的波动分解",[dict(config=r["config"],n=r["n"],images=r["images"],variable=r["variable_images"],buildings=r["buildings"],mean=100*r["mean_within_fraction"],median=100*r["median_within_fraction"]) for r in comp],[("config","分类",""),("n","人数","人"),("images","总图片","图"),("variable","可变化图片","图"),("buildings","总面板建筑","栋"),("mean","内部方差占比均值","%"),("median","内部方差占比中位数","%")],version),t("members","同配比不同真人的已保存例子（非全部组合）",[dict(image_id=r["image_id"],code=r["code"],config=r["config"],n=int(r["n"]),composition=r["composition"],teams=int(r["teams_in_composition"]),minimum=100*float(r["minimum"]),maximum=100*float(r["maximum"]),lower=members(r["lower_team"].split(';')),upper=members(r["upper_team"].split(';'))) for r in examples],[("code","图片短名",""),("config","分类",""),("n","人数","人"),("composition","同一配比",""),("teams","该配比团队数","个"),("minimum","最小成对分歧","%"),("maximum","最大成对分歧","%"),("lower","最小值成员",""),("upper","最大值成员","")],version)]
    wp=read(results/"worker_prediction_summary.json")
    people["tables"].append(t("continuous","连续画像与离散分类 · 全部已保存模型",[dict(outcome=r["outcome"],model=r["model"],images=r["images"],buildings=r["buildings"],responses=r["responses"],gain=100*r["relative_MSE_gain"],low=r["absolute_gain_interval95"][0],high=r["absolute_gain_interval95"][1],unclassified=r["unclassified_rows"]) for r in wp],[("outcome","预测偏离目标",""),("model","模型",""),("images","图片","图"),("buildings","建筑","栋"),("responses","作答","份"),("gain","MSE相对改善","%"),("low","MSE绝对改善下限","比例平方"),("high","MSE绝对改善上限","比例平方"),("unclassified","未分类记录","份")],version))
    onset=read(results/"same_room_onset_transfer_summary.json")
    room=module("持续起点需要来源与目标均明确；条件MAE只针对可评分子集，不是整体成功率。未决、仅一边明确及观察不足保留。端点分歧/覆盖预测与持续起点不同。",tables=[t("onset","同房持续起点可评价范围",[dict(method=r["method"],tail=r["tail"],scope=r["scope"],targets=r["all_eligible_targets"],buildings=r["all_buildings"],scorable=r["scorable_targets"],scorable_buildings=r["scorable_buildings"],states=r["statuses"],MAE=r["conditional_MAE"]) for r in onset],[("method","历史分簇",""),("tail","后续观察","人"),("scope","房间面板",""),("targets","全部目标","图"),("buildings","全部建筑","栋"),("scorable","双方明确目标","图"),("scorable_buildings","可评建筑","栋"),("states","完整状态计数",""),("MAE","可评子集人数MAE","人")],version)])
    local=read(results/"geometry_summary.json")
    annotation=module("3D数值反事实代理：相机高度归一化；顶点深度借配对地板推算，并非独立量测。原始投影与拟合分开；拟合成功不等于标注正确，不据此指定2D距离权重。",metrics=[metric("3D代理作答",local["responses"],"份","绑定端点数值研究，不是新的作答。",version),metric("绑定角对",local["bound_pairs"],"对","几何代理输入。",version),metric("拟合成功",local["fit_panel"]["statuses"]["ok"],"份","46份目的性数值拟合中的成功数；非正确率。",version,denominator=46),metric("拟合阻止",local["fit_panel"]["statuses"]["blocked"],"份","阻止原因保留。",version,denominator=46)],tables=[t("geometry","3D代理边界与阻止原因",[dict(scope="顶／底x不完全相同",count=local["top_bottom_x_not_identical"]),dict(scope=local["fit_panel"]["blocked_reasons"],count=7)],[("scope","状态／原因",""),("count","数量","")],version)])
    measurement=read(results/"measurement_summary.json")
    far=sum(measurement["bottleneck_role"].values())
    annotation["tables"].insert(0,t("local","局部与整图读数 · 作答对加权（非算法错误率）",[dict(measure="点数不同",count=measurement["diagnostic_case_counts"]["count_gate"],denominator=measurement["n_pairs"]),dict(measure="同点数远距中仅一个角对超阈值",count=measurement["far_same_count_single_corner"],denominator=far),dict(measure="局部平均U8≤0.2且整图U8≥0.5的同点数子池",count=measurement["local_at8"]["locally_mean_le02_joint_ge05"],denominator=measurement["local_at8"]["pools"])],[("measure","现象",""),("count","计数","对／子池"),("denominator","对应分母","对／子池")],version))
    add(version,"冻结2444份 · 已审查历史探针","audited-probes","historical-unclassified",{"people":people,"features":f,"rooms":room,"annotation":annotation})
