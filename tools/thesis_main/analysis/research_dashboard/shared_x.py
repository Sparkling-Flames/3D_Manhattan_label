"""只读共享x重分析发布结果；不绑定角对、不重算坐标、分簇或预测。"""
import gzip
import json
import csv

from .connect_20260922 import read, rows, module, metric, point, chart, table, MODULES, CLASSIFICATION


def append_shared_x(data, selected, folder):
    manifest = read(folder / "MANIFEST.json")
    if manifest["status"] != "complete":
        raise ValueError("共享x结果尚未完成，禁止发布部分计算")
    if not manifest["all_affinity_solutions_certified"] or not manifest["raw_complete_replay_reproduced"]:
        raise ValueError("共享x求解或原始重放核验未通过")
    checks=read(folder / "DIAGNOSTIC_CHECKS.json")
    if not checks["raw_room_both_methods_reproduced"]:
        raise ValueError("共享x同房基线诊断未通过")
    version = manifest["version"]
    views = read(folder / "views.json")
    endpoint = rows(folder / "endpoint_per_image.csv")
    endpoint_summary = rows(folder / "endpoint_summary.csv")
    memberships = {(r["variant"], r["method"], r["image_id"]): r for r in read(folder / "memberships.json")}
    replay = rows(folder / "replay_per_image.csv")
    replay_summary = rows(folder / "replay_summary.csv")
    replay_comparison = rows(folder / "replay_method_comparison.csv")
    predictions = rows(folder / "room_predictions.csv")
    room_summary = read(folder / "room_summary.json")
    comparison = rows(folder / "room_method_comparison.csv")
    attribution = rows(folder / "room_error_attribution.csv")
    dominant = rows(folder / "dominant_tail_per_image.csv")
    dominant_summary = rows(folder / "dominant_tail_summary.csv")
    processing = rows(folder / "point_processing.csv")
    orders = read(folder / "orders.json")
    with gzip.open(folder / "replay_prefixes.csv.gz", "rt", encoding="utf-8-sig", newline="") as f:
        prefixes = [r for r in csv.DictReader(f) if int(r["order"]) < 3]
    with gzip.open(folder / "pointsets.json.gz", "rt", encoding="utf-8") as f:
        pointsets = {r["id"]: r for r in json.load(f)}
    assert len(views) == manifest["images"]
    assert sum(v["N"] for v in views.values()) == manifest["responses"]
    assert len(endpoint) == len(memberships) == 4 * len(views)
    for v in views.values():
        assert v["N"] == len(v["ids"]) == len(set(v["workers"]))
        for variant in ["raw", "shared_x"]:
            for method in ["complete", "affinity"]:
                m = memberships[variant, method, v["image_id"]]
                assert m["ids"] == v["ids"] and m["workers"] == v["workers"] and len(m["labels"]) == v["N"]
    note = manifest["coordinate_rule"] + "。" + manifest["binding_scope"] + "。人工保留与绑定未定者不强制修正；7036不在预测池。原始坐标保留。"
    data["versions"].append(dict(id=version, label="共享x重分析 · 四条件独立对照", description=note))
    data["sources"].append(dict(id=version, label="共享x重分析发布", description="shared_x_reanalysis_20260922：MANIFEST、point_processing/pointsets、endpoint/memberships、replay、room表；页面仅投影结果。"))
    def num(x):
        return None if x in ("", None) else float(x)
    def no_room(r):
        return str(r["no_anchor_room"]).lower()=="true"
    def tab(id, title, rr, specs):
        return table(id, title, specs, rr, version)
    def project(rr, specs, percentages=()):
        result=[]
        for r in rr:
            p={k:r[k] for k,_,_ in specs}
            for k in percentages:
                p[k] = None if num(r[k]) is None else 100*num(r[k])
            for k in ["observed_onset_median_success_only", "onset_q10_success_only", "onset_q90_success_only"]:
                if k in p: p[k]=num(p[k])
            for k in ["onset80_success_only", "onset90_success_only"]:
                if k in p:p[k]=num(p[k])
            if "observation_status" in p:
                p["observation_status"]={"no_anchor_room":"后续观察人数不足", "ge80pct_orders":"至少80%顺序识别起点", "some_orders_only":"仅部分顺序识别起点", "no_onset_under_rule":"观察内未识别该判据起点"}[r["observation_status"]]
                if no_room(r):p["success_fraction"]=None
            if "image_id" in r: p["image_id"]=r["image_id"]
            result.append(p)
        return result
    image_map={r["id"]:r for r in data["images"]}
    scopes=[("", "", "", list(views))]
    for building in sorted({v["building"] for v in views.values()}):
        ids=[i for i,v in views.items() if v["building"]==building]
        scopes.append((building,"","",ids))
        for room in sorted({image_map[i]["room"] for i in ids}):
            subset=[i for i in ids if image_map[i]["room"]==room]
            scopes.append((building,room,"",subset))
            scopes.extend((building,room,i,[i]) for i in subset)
    epcols=[("code","图片",""),("N","人数","人"),("K","总簇数","簇"),("counts","各簇人数","人"),("largest_share","最大簇占比","%"),("singleton_share","单人作答占比","%"),("core3_mass","三大重复支持簇覆盖","%"),("few_J3_m2_s10","J3/m2/未支持≤10%终点条件",""),("objective","亲近度目标值","")]
    repcols=[("code","图片",""),("N","观察人数","人"),("J","最多支持簇","簇"),("m","每簇至少人数","人"),("tail_fraction","未支持份额上限","比例"),("h","后续观察","人"),("orders","重放顺序","次"),("success_orders","有持续起点顺序","次"),("success_fraction","有持续起点顺序比例","%"),("observed_onset_median_success_only","成功顺序起点中位数","人"),("onset_q10_success_only","成功顺序起点Q10","人"),("onset_q90_success_only","成功顺序起点Q90","人"),("endpoint_pass","终点覆盖条件",""),("reason_counts","各状态顺序数","")]
    repcols += [("no_anchor_room","是否缺少后续观察空间",""),("observation_status","观察状态","")]
    roomcols=[("code","目标图片",""),("kind","面板",""),("metric","预测指标",""),("N","目标人数","人"),("source_codes","来源图片",""),("source_N","来源人数",""),("value","目标观测","%"),("prediction","同房预测","%"),("outside_baseline","其他建筑参照","%"),("otherroom_baseline","同楼其他房间参照","%"),("outcome_exposed","目标结果是否暴露","")]
    for variant in ["raw", "shared_x"]:
        condition = "Manual/OOS · " + ("原始有效点" if variant=="raw" else "共享x（含原样保留项）")
        for method in ["complete", "affinity"]:
            matching=lambda r:r["variant"]==variant and r["method"]==method
            ep=[r for r in endpoint if matching(r)]
            rep=[r for r in replay if matching(r)]
            pred=[r for r in predictions if matching(r)]
            for building,room,image,ids in scopes:
                pool=set(ids); members=sorted({w for i in ids for w in views[i]["workers"]})
                mods={k:module("此版本未接入该模块；旧人员分类、scope/Semi研究需明确切换历史版本，不代表共享x复验。","not_computed") for k in MODULES}
                audit=[dict({k:v for k,v in r.items() if k!="worker"},member_ids=[r["worker"]]) for r in processing if not building or r["image_id"] in pool]
                for r in audit:
                    r["audit_image"]=r["image_id"]
                    if r["image_id"] not in pool:r["image_id"]=""
                mods["overview"]=module(note,metrics=[metric("计算作答",sum(views[i]["N"] for i in ids),"份","当前预测池；不把处理审计池额外作答计入。",version),metric("计算图片",len(ids),"图","当前条件独立图片。",version),metric("实际人员",len(members),"人","当前计算池去重。",version,members)],tables=[tab("processing","点处理审计（含未进入预测池的保留项）",audit,[("id","作答身份",""),("audit_image","审计来源图片（可在预测池外）",""),("condition","原条件",""),("prediction_included","进入预测池",""),("status","处理状态",""),("pairing_source","绑定来源",""),("changed_points","变化点数","点"),("pairs","角对数","对")])])
                local=[r for r in ep if r["image_id"] in pool]
                roster=[dict(image_id=i,annotation=cid,cluster=str(lab),member_ids=[w]) for i in ids for cid,w,lab in zip(memberships[variant,method,i]["ids"],memberships[variant,method,i]["workers"],memberships[variant,method,i]["labels"])]
                mods["annotation"]=module(note+" 簇编号仅在当前图片和条件内有效。最大簇、支持覆盖与单人尾部分开呈现；未满足某覆盖判据不等于严重分歧。终点主簇优势不自动给出持续起点。新点集不提供3D。",charts=[chart("endpoint","逐图主簇、单人尾部与支持覆盖",[point(r["code"],100*float(r[k]),label,r["image_id"],views[r["image_id"]]["workers"],version,int(r["N"])) for r in local for k,label in [("largest_share","最大簇"),("singleton_share","单人作答"),("core3_mass","三大重复支持簇")]],"图片","作答占比","%","三项不是互补划分；底层表保留N与全部簇规模。",kind="bar")],tables=[tab("endpoint","逐图分区",project(local,epcols,["largest_share","singleton_share","core3_mass"]),epcols),tab("members","分簇成员与作答身份",roster,[("annotation","作答身份",""),("cluster","当前簇编号","")])])
                if not building:
                    specs=[("images","N≥8固定面板","图"),("responses","面板作答","份"),("singleton_responses","单人簇作答","份"),("forced_singleton_responses","无阈值内邻居的单人作答","份"),("near_split","阈值内但分簇不同的作答对","对"),("endpoint_few90","90%终点判据达标","图"),("mean_K","图片等权簇数","簇"),("mean_largest_share","图片等权最大簇占比","%"),("mean_singleton_share","图片等权单人尾部","%"),("mean_core3_mass","图片等权三大支持簇覆盖","%")]
                    mods["annotation"]["tables"].insert(0,tab("endpoint-summary","预计算终点汇总 · N≥8面板（不同于全部240图）",project([r for r in endpoint_summary if matching(r)],specs,[k for k,_,u in specs if u=="%"]),specs))
                rr=[r for r in rep if r["image_id"] in pool]
                if rr:
                    stable=module("固定N≥8观察池，80条共享人员顺序，k从4开始；起点与所有后续前缀比较：TV≤0.1、成员关系变化≤0.05。图并列J3/m2/后续3人的80%与90%支持覆盖；表保留全部四组支持条件和h=3/5。观察内未识别起点不等于没有主共识；终点主簇优势也不能代替持续性检验。起点分位数仅条件于成功顺序，未识别不填零；不等于质量或同房起点预测。")
                    fixed=[r for r in rr if (int(r["J"]),int(r["m"]),int(r["h"]))==(3,2,3) and float(r["tail_fraction"]) in [.1,.2]]
                    stable["charts"]=[chart("replay","80%／90%支持要求下有持续起点的顺序比例",[point(int(r["N"]),None if no_room(r) else 100*float(r["success_fraction"]),f"支持覆盖≥{100*(1-float(r['tail_fraction'])):.0f}%",r["image_id"],views[r["image_id"]]["workers"],version,int(r["orders"]),None if no_room(r) else int(r["success_orders"]),status="insufficient" if no_room(r) else "ready") for r in fixed],"观察人数","顺序比例","%",stable["note"],x_unit="人")]
                    stable["tables"]=[tab("replay","逐图全部判据与未决状态",project(rr,repcols,["success_fraction"]),repcols)]
                    if not building:
                        ss=[r for r in replay_summary if matching(r)]
                        specs=[("J","J",""),("m","m",""),("tail_fraction","未支持上限","比例"),("h","后续人数","人"),("images","图片","图"),("buildings","建筑","栋"),("endpoint_pass","终点达标图数","图"),("images_any_success","至少一条成功顺序","图"),("images_ge80pct_orders","≥80%顺序成功","图"),("building_equal_success","建筑等权顺序比例","%"),("mean_success_fraction","图片等权顺序比例","%")]
                        specs += [("no_observation_room","后续观察不足","图"),("images_with_anchor_room","有候选起点空间","图")]
                        stable["tables"].append(tab("summary","预计算总体汇总（两种权重分列）",project(ss,specs,["building_equal_success","mean_success_fraction"]),specs))
                        specs=[("comparison","明确的差值方向",""),("J","J",""),("m","m",""),("tail_fraction","未支持上限","比例"),("h","后续人数","人"),("images","固定面板","图"),("buildings","建筑","栋"),("building_equal_delta","建筑等权顺序比例差","百分点"),("conditional_low","条件区间下限","百分点"),("conditional_high","条件区间上限","百分点"),("improved_images","顺序比例增加","图"),("worsened_images","顺序比例减少","图")]
                        cr=project([r for r in replay_comparison if r["comparison"] in {"method_"+variant,"coordinates_"+method}],specs,[k for k,_,u in specs if u=="百分点"])
                        for r in cr:r["comparison"]={"method_raw":"原始点：亲近度−完整链接","method_shared_x":"共享x：亲近度−完整链接","coordinates_complete":"完整链接：共享x−原始点","coordinates_affinity":"亲近度：共享x−原始点"}[r["comparison"]]
                        stable["tables"].append(tab("replay-comparison","当前条件相关的两种变化 · 预计算成对区间",cr,specs))
                        specs=[("h","后续人数","人"),("images","总面板","图"),("dominant80_images","最大簇≥80%描述探针","图"),("dominant_but_fails90_images","最大簇≥80%但未过90%支持","图"),("endpoint_pass80","80%终点支持达标","图"),("endpoint_pass90","90%终点支持达标","图"),("images_ge80pct_orders_under80","80%支持下≥80%顺序识别起点","图"),("images_ge80pct_orders_under90","90%支持下≥80%顺序识别起点","图"),("images_passing_only_under80","仅80%支持下达到顺序要求","图"),("dominant_but_under80_orders_unresolved","主簇探针满足但顺序要求未满足","图")]
                        stable["tables"].append(tab("dominant-summary","主簇与尾部诊断（≥80%为描述探针，非最终阈值）",project([r for r in dominant_summary if matching(r)],specs),specs))
                    specs=[("code","图片",""),("N","人数","人"),("h","后续人数","人"),("counts","簇规模","人"),("largest_share","最大簇","%"),("singleton_share","单人尾部","%"),("core3_mass","重复支持覆盖","%"),("dominant80_probe","主簇≥80%探针",""),("dominant_but_fails90","主簇满足探针但未过90%支持",""),("endpoint_pass80","80%终点支持达标",""),("endpoint_pass90","90%终点支持达标",""),("success_fraction80","80%支持下顺序比例","%"),("success_fraction90","90%支持下顺序比例","%"),("onset80_success_only","80%成功顺序起点中位数","人"),("onset90_success_only","90%成功顺序起点中位数","人"),("reason_counts80","80%原因计数",""),("reason_counts90","90%原因计数","")]
                    dr=project([r for r in dominant if matching(r) and r["image_id"] in pool],specs,[k for k,_,u in specs if u=="%"])
                    for r in dr:
                        if int(r["N"])-int(r["h"])<manifest["replay"]["min_k"]:
                            r["success_fraction80"]=r["success_fraction90"]=None
                    stable["tables"].append(tab("dominant","逐图主簇／尾部与持续起点（观察不足比例留空）",dr,specs))
                    if image:
                        pp=[r for r in prefixes if matching(r) and r["image_id"]==image]
                        for field,label,mult,unit in [("K","簇数",1,"簇"),("singleton_share","单人作答占比",100,"%")]:
                            stable["charts"].append(chart("prefix-"+field,"固定编号1—3顺序 · "+label,[point(int(r["k"]),mult*float(r[field]),"顺序"+str(int(r["order"])+1),image,[w for w in orders[int(r["order"])] if w in views[image]["workers"]][:int(r["k"])],version,int(r["k"])) for r in pp],"进入人数",label,unit,"预定顺序，不按结果挑选；横轴从4人起。",kind="line",x_unit="人"))
                    mods["stability"]=stable
                else: mods["stability"]=module("此范围没有N≥8的重放图片，人数不足；不当作失败。","insufficient")
                pp=[r for r in pred if r["image_id"] in pool]
                if pp:
                    rm=module("同房留目标图预测终点分歧／支持结构，不是预测持续起点人数。目标值随坐标与分簇方法变化，MAE不是针对同一独立真值的准确率排名；固定来源图和面板比较，缺失不作零。比例以%展示，MAE与差值以百分点展示。",tables=[tab("predictions","目标／来源图片与终点预测",project(pp,roomcols,["value","prediction","outside_baseline","otherroom_baseline"]),roomcols)])
                    if not building:
                        ss=[r for r in room_summary if matching(r)]
                        specs=[("metric","指标",""),("kind","面板",""),("same_panel_otherroom","其他房间共同面板",""),("images","图片","图"),("families","房间","组"),("buildings","建筑","栋"),("MAE","同房MAE","百分点"),("outside_MAE","其他建筑MAE","百分点"),("samebuilding_otherroom_MAE","同楼其他房间MAE","百分点"),("conditional_gain_interval95","其他建筑对照改善区间","百分点")]
                        rendered=project(ss,specs,["MAE","outside_MAE","samebuilding_otherroom_MAE"])
                        for r in rendered:r["conditional_gain_interval95"]=[None if v is None else 100*v for v in r["conditional_gain_interval95"]]
                        rm["tables"].insert(0,tab("room-summary","预计算同房误差（房间后建筑等权）",rendered,specs))
                        specs=[("metric","指标",""),("kind","面板",""),("images","图片","图"),("buildings","建筑","栋"),("error_change","亲近度−完整链接MAE","百分点"),("target_contribution","目标变化数值贡献","百分点"),("source_contribution","来源预测变化数值贡献","百分点"),("conditional_delta_low","条件区间下限","百分点"),("conditional_delta_high","条件区间上限","百分点")]
                        rm["tables"].append(tab("method-change","同坐标条件下两方法误差变化（数值分解，非因果）",project([r for r in comparison if r["variant"]==variant],specs,[k for k,_,u in specs if u=="百分点"]),specs))
                    specs=[("code","目标图",""),("metric","指标",""),("kind","面板",""),("source_codes","来源图",""),("old_value","完整链接目标","%"),("new_value","亲近度目标","%"),("old_prediction","完整链接预测","%"),("new_prediction","亲近度预测","%"),("error_change","绝对误差变化","百分点"),("target_contribution","目标数值贡献","百分点"),("source_contribution","来源数值贡献","百分点")]
                    rm["tables"].append(tab("attribution","逐图完整链接→亲近度变化（当前坐标条件）",project([r for r in attribution if r["variant"]==variant and r["image_id"] in pool],specs,[k for k,_,u in specs if u in {"%","百分点"}]),specs))
                    mods["rooms"]=rm
                data["views"].append(dict(id=f"v{len(data['views'])}",version=version,condition=condition,method=method,classification=CLASSIFICATION,building=building,room=room,image=image,image_ids=ids,modules=mods))
            # Only the already selected image manifest carries point resources. Never reuse old geometry.
            old_cases=[c for c in data["cases"] if c["method"]==method and c["image_id"] in views and c["version"]!=version]
            for old in old_cases:
                iid=old["image_id"]; m=memberships[variant,method,iid]; variants=[]
                pv=version+"/"+variant
                for cid,w,lab in zip(m["ids"],m["workers"],m["labels"]):
                    p=pointsets[cid]; links=p["pairs_zero_based"]
                    if links is None: continue
                    coords=p["raw_effective_points" if variant=="raw" else "shared_x_points"]
                    pairs=[dict(source_pair_id=f"pair:{a+1}/{b+1}",display_index=j+1,top=coords[a],bottom=coords[b]) for j,(a,b) in enumerate(links)]
                    pairids=[p["source_pair_id"] for p in pairs]
                    variants.append(dict(id=cid,name=f"{w} · {p['status']} · {p['pairing_source']} · 簇{lab}",kind="original" if variant=="raw" else "perturbation",pointset_version=pv,member_ids=[w],source_ids=[version],cluster_ids=[str(lab)],pairs=pairs,connections=[[pid,pairids[(j+1)%len(pairids)]] for j,pid in enumerate(pairids)]))
                caseid=version+"-"+variant+"-"+old["id"]
                data["cases"].append(dict(id=caseid,image_id=iid,version=version,condition=condition,method=method,classification=CLASSIFICATION,pointset_version=pv,source_ids=[version],width=old["width"],height=old["height"],variants=variants))
                selected.append(dict(case_id=caseid,image=next(s["image"] for s in selected if s["case_id"]==old["id"])))
