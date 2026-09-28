"""Real release projection checks, without recomputing a research method."""
from pathlib import Path
from tools.thesis_main.analysis.research_dashboard.connect_20260922 import connect, RESULTS, COMPUTE, DESCRIBE


def test_shared_x_adapter_isolated_and_requires_completed_release(tmp_path, monkeypatch):
    import gzip
    import json
    import pytest
    from tools.thesis_main.analysis.research_dashboard import shared_x as adapter, history
    from tools.thesis_main.analysis.research_dashboard.build import validate
    from tools.thesis_main.analysis.research_dashboard.connect_20260922 import CLASSIFICATION
    workers=[f"p{i}" for i in range(8)]
    ids=[f"a{i}" for i in range(8)]
    manifest=dict(status="running",version="shared-test",coordinate_rule="共享x；无触发阈值",binding_scope="条件绑定不是人工核验",images=1,responses=8,all_affinity_solutions_certified=True,raw_complete_replay_reproduced=True)
    (tmp_path/"MANIFEST.json").write_text(json.dumps(manifest),encoding="utf-8")
    with pytest.raises(ValueError,match="尚未完成"):
        adapter.append_shared_x({},[],tmp_path)
    manifest["status"]="complete"
    base=dict(image_id="i",code="i",building="b",N=8)
    conditions=[dict(base,variant=v,method=m) for v in ["raw","shared_x"] for m in ["complete","affinity"]]
    files={"MANIFEST.json":manifest,"DIAGNOSTIC_CHECKS.json":{"raw_room_both_methods_reproduced":True},"views.json":{"i":dict(base,ids=ids,workers=workers)},"memberships.json":[dict(r,ids=ids,workers=workers,labels=list(range(8))) for r in conditions],"orders.json":[workers]*80,"room_summary.json":[]}
    tables={"endpoint_per_image.csv":[dict(r,K=8,counts="1;1;1;1;1;1;1;1",largest_share=.125,singleton_share=1,core3_mass=0,few_J3_m2_s10=False,objective=0) for r in conditions],
        "replay_per_image.csv":[dict(r,J=3,m=2,tail_fraction=.1,h=3,orders=80,success_orders=0,success_fraction=0,observed_onset_median_success_only="",onset_q10_success_only="",onset_q90_success_only="",endpoint_pass=False,reason_counts='{"unresolved":80}') for r in conditions],
        "replay_summary.csv":[dict(r,J=3,m=2,tail_fraction=.1,h=3,images=1,buildings=1,endpoint_pass=0,images_any_success=0,images_ge80pct_orders=0,building_equal_success=0,mean_success_fraction=0) for r in conditions],
        "room_predictions.csv":[],"room_method_comparison.csv":[],"room_error_attribution.csv":[],"dominant_tail_per_image.csv":[],"dominant_tail_summary.csv":[],"endpoint_summary.csv":[],"replay_method_comparison.csv":[],
        "point_processing.csv":[dict(id="preserved",image_id="outside-prediction-pool",worker="p0",condition="manual",prediction_included=False,status="human_preserve",pairing_source="",changed_points=0,pairs=0)]}
    tables["room_predictions.csv"]=[dict(r,kind="physical_same",metric="core3_mass",source_codes="source",source_N="8",value=.4,prediction=.3,outside_baseline=.2,otherroom_baseline="",outcome_exposed=False) for r in conditions]
    tables["replay_per_image.csv"] += [dict(r,tail_fraction=.2,success_orders=80,success_fraction=1,observed_onset_median_success_only=4,onset_q10_success_only=4,onset_q90_success_only=4) for r in list(tables["replay_per_image.csv"])]
    for r in tables["replay_per_image.csv"]:r.update(no_anchor_room=False,observation_status="ge80pct_orders" if r["success_fraction"] else "no_onset_under_rule")
    tables["replay_per_image.csv"] += [dict(r,h=5,no_anchor_room=True,observation_status="no_anchor_room") for r in tables["replay_per_image.csv"] if r["tail_fraction"]==.1]
    for r in tables["replay_summary.csv"]:r.update(no_observation_room=0,images_with_anchor_room=1)
    files["room_summary.json"]=[dict(r,metric="core3_mass",kind="physical_same",same_panel_otherroom=False,images=1,families=1,buildings=1,MAE=.1,outside_MAE=.2,samebuilding_otherroom_MAE=None,conditional_gain_interval95=[-.1,.2]) for r in conditions]
    monkeypatch.setattr(adapter,"read",lambda p:files[p.name])
    monkeypatch.setattr(adapter,"rows",lambda p:tables[p.name])
    monkeypatch.setattr(history,"csv_rows",lambda p:[])
    with gzip.open(tmp_path/"replay_prefixes.csv.gz","wt",encoding="utf-8") as f:f.write("order\n")
    points=[dict(id=cid,status="shared_x",pairing_source="conditional_unique_x_assignment",raw_effective_points=[[1,2],[3,4]],shared_x_points=[[2,2],[2,4]],pairs_zero_based=[[0,1]] if j else None) for j,cid in enumerate(ids)]
    with gzip.open(tmp_path/"pointsets.json.gz","wt",encoding="utf-8") as f:json.dump(points,f)
    data=dict(schema_version="research_dashboard_v1",release="synthetic-only",versions=[],methods=[dict(id=m,label=m,description=m) for m in ["complete","affinity"]],classifications=[dict(id=CLASSIFICATION,label=CLASSIFICATION,description=CLASSIFICATION)],sources=[dict(id="s",label="s",description="s")],participants=[dict(id=w,label=w) for w in workers],images=[dict(id="i",building="b",room="r",scene="i",source_ids=["s"])],views=[],cases=[])
    from tools.thesis_main.analysis.research_dashboard.connect_20260922 import module, MODULES
    data["versions"].append(dict(id="old",label="old",description="old"))
    old=dict(version="old",condition="old",method="complete",classification=CLASSIFICATION)
    data["views"].append(dict(old,id="v0",building="",room="",image="",image_ids=["i"],modules={k:module("old","not_computed") for k in MODULES}))
    data["cases"].append(dict(old,id="old-case",image_id="i",pointset_version="old",source_ids=["s"],width=1024,height=512,variants=[]))
    selected=[dict(case_id="old-case",image="selected.jpg")]
    adapter.append_shared_x(data,selected,tmp_path)
    validate(data)
    whole=[v for v in data["views"] if not v["building"] and v["version"]=="shared-test"]
    assert len(whole)==4 and len({(v["condition"],v["method"]) for v in whole})==4
    for v in whole:
        assert v["version"]=="shared-test" and v["modules"]["people"]["status"]=="not_computed"
        row=v["modules"]["stability"]["tables"][0]["rows"][0]
        assert row["success_fraction"]==0 and row["observed_onset_median_success_only"] is None
        assert {r["series"] for r in v["modules"]["stability"]["charts"][0]["rows"]}=={"支持覆盖≥80%","支持覆盖≥90%"}
        insufficient=next(r for r in v["modules"]["stability"]["tables"][0]["rows"] if r["h"]==5)
        assert insufficient["success_fraction"] is None and insufficient["observation_status"]=="后续观察人数不足"
        assert v["modules"]["overview"]["tables"][0]["rows"][0]["prediction_included"] is False
        assert v["modules"]["overview"]["tables"][0]["rows"][0]["audit_image"]=="outside-prediction-pool"
        assert v["modules"]["overview"]["tables"][0]["rows"][0]["image_id"]==""
        rm=v["modules"]["rooms"]
        assert rm["status"]=="ready"
        assert rm["tables"][0]["rows"][0]["conditional_gain_interval95"]==[-10,20]
        assert rm["tables"][0]["rows"][0]["samebuilding_otherroom_MAE"] is None
    new_cases=[c for c in data["cases"] if c["version"]=="shared-test"]
    assert len(new_cases)==2 and len(selected)==3
    for c in new_cases:
        assert len(c["variants"])==7  # 未绑定记录不强造角对。
        for v in c["variants"]:
            assert "geometry" not in v and v["pointset_version"]==c["pointset_version"]
            assert v["pairs"][0]["source_pair_id"]=="pair:1/2"
            assert v["pairs"][0]["top"]==([2,2] if c["pointset_version"].endswith("/shared_x") else [1,2])


def test_reviewed_release_projection(tmp_path, monkeypatch):
    from tools.label_studio.panorama_studio import geometry
    monkeypatch.setattr(geometry, "analyze", lambda *a, **kw: (_ for _ in ()).throw(AssertionError("must not recompute")))
    data, manifest, audit = connect(tmp_path, RESULTS / "presentation_inventory_20260922/asset_coverage.json")
    whole = {(v["condition"], v["method"]): v for v in data["views"] if not v["building"]}
    desc = whole[DESCRIBE, "none"]
    assert [m["value"] for m in desc["modules"]["overview"]["metrics"]] == [3019, 259, 25, 22]
    assert audit["calculation_responses"] == 2444 and audit["source_points_match"]
    baseline, candidate = [whole[COMPUTE, method] for method in ["complete", "affinity"]]
    assert [m["value"] for m in baseline["modules"]["annotation"]["metrics"]] == [110, 1940, 515, 27]
    assert [m["value"] for m in candidate["modules"]["annotation"]["metrics"]] == [110, 1940, 537, 23]
    assert candidate["modules"]["stability"]["status"] == "not_computed"
    assert candidate["modules"]["people"]["status"] == "not_computed"
    assert "二次亲近度" in candidate["modules"]["people"]["note"]
    assert not candidate["modules"]["people"]["charts"]
    semi = whole["semi · 描述覆盖", "none"]
    assert len(semi["image_ids"]) == 43
    semi_rows = semi["modules"]["annotation"]["tables"][0]["rows"]
    assert sum(r["N"] for r in semi_rows) == 530
    assert semi["modules"]["stability"]["status"] == "not_computed"
    assert len(manifest["selected_cases"]) == 8 and len(data["cases"]) == 8
    assert sum(len(c["variants"]) for c in data["cases"]) == 166
    assert all(len(v["pairs"]) >= 3 for c in data["cases"] for v in c["variants"])
    assets = desc["modules"]["overview"]["tables"][1]["rows"]
    by_name = {r["asset"]: r for r in assets}
    assert by_name["Bi-Layout_历史清单ok"]["matched"] == 257
    assert by_name["DINOv3_本地原始特征"]["matched"] == 259
    assert by_name["DINOv3_本地原始特征"]["available"] == 648
    assert desc["modules"]["features"]["metrics"][-1]["value"] is None
    assert desc["modules"]["features"]["metrics"][2]["label"] == "DA3同房辅助（全资产库）"
    assert "未接入当前版本" in desc["modules"]["features"]["note"]
    room_chart = next(c for c in candidate["modules"]["rooms"]["charts"] if c["id"] == "mae")
    row = next(r for r in room_chart["rows"] if r["x"] == "可比同房 · 三大重复支持簇覆盖" and r["series"] == "同房来源")
    assert abs(row["value"]-7.593512767425806) < 1e-10 and row["denominator"] == 21
    historical = [v for v in data["views"] if v["version"] == "history-20260910"]
    assert len({(v["condition"], v["classification"]) for v in historical if v["classification"].startswith("ward-")}) == 303
    q = next(v for v in data["views"] if v["version"] == "history-20260921-pre-review" and v["classification"] == "old-Q_2" and v["method"] == "old-complete")
    values = q["modules"]["people"]["tables"][0]["rows"]
    low = next(r for r in values if r["subtype"] == "1" and r["profile"] == "最多3簇／单人≤20%")
    assert low["images"] == 34 and low["buildings"] == 10
    assert abs(low["L"] - 38.682142857142854) < 1e-10
    overviews = [v for v in data["views"] if v["classification"] == "old-classification-overview"]
    assert {v["method"] for v in overviews} == {"old-complete", "old-representative"}
    for v in overviews:
        overview = v["modules"]["people"]
        assert "2444" in overview["note"] and "未完整复验" in overview["note"]
        selected = next(t for t in overview["tables"] if t["id"] == "focus")["rows"]
        assert [(r["config"], r["images"], r["buildings"], r["H"]) for r in selected] == [("Q_2",34,10,"5–13"),("QT_2",63,15,"5–15"),("QT_3",54,14,"5–9")]
        for r in selected:
            original = next(x for x in data["views"] if x["classification"] == "old-"+r["config"] and x["method"] == v["method"])
            source_row = next(x for x in original["modules"]["people"]["tables"][0]["rows"] if x["subtype"] == r["subtype"] and x["profile"] == r["profile"])
            assert all(r[k] == source_row[k] for k in ["L","random_L","gain","low","high"])
        sensitivity = next(t for t in overview["tables"] if t["id"] == "q-sensitivity")["rows"]
        assert len(sensitivity) == 6 and all(r["gain"] > 0 for r in sensitivity)
    feature = next(v for v in data["views"] if v["version"] == "history-20260921-audited")
    u8 = next(c for c in feature["modules"]["features"]["charts"] if c["id"] == "U8")
    assert abs(next(r for r in u8["rows"] if r["x"] == "仅人数N")["value"] - 20.797953069168232) < 1e-10
    assert all(r["denominator"] == 64 for r in u8["rows"])
    assert all(v["version"] != "history-20260910" for v in data["cases"])
    old_room = next(v for v in data["views"] if v["version"] == "history-20260921-pre-review" and v["condition"].endswith("持续起点") and v["method"] == "old-complete")
    splits = old_room["modules"]["rooms"]["tables"][0]["rows"]
    assert all(r["splits"] == 827 for r in splits)
    assert all(r["median"] == 0 for r in splits if r["tail"] == 5)
    scene = next(v for v in data["views"] if v["method"] == "old-scene")
    scene_rows = scene["modules"]["rooms"]["charts"][0]["rows"]
    assert abs(next(r for r in scene_rows if r["x"] == "image · U(8)" and r["series"] == "同用途粗类")["value"]-24.250014750969337) < 1e-10
    multi = next(v for v in data["views"] if v["version"] == "history-20260910" and "稳定多簇" in v["condition"])
    assert len(multi["image_ids"]) == 4
    teams = next(v for v in data["views"] if v["condition"].endswith("全部具体四人团队"))
    team_rows = teams["modules"]["people"]["tables"][0]["rows"]
    assert len(team_rows) == 87725
    assert all(len(r["member_ids"]) == 4 and not set(r["member_ids"]) & set(r["validation"]) for r in team_rows)
    from tools.thesis_main.analysis.research_dashboard.shared_x import append_shared_x
    from tools.thesis_main.analysis.research_dashboard.build import validate
    old_count=len(data["views"])
    append_shared_x(data,manifest["selected_cases"],RESULTS/"shared_x_reanalysis_20260922")
    validate(data)
    added=data["views"][old_count:]
    whole=[v for v in added if not v["building"]]
    assert len(whole)==4 and len(data["cases"])==24
    expected={(False,"complete"):(515,14,25),(False,"affinity"):(537,16,31),(True,"complete"):(509,12,21),(True,"affinity"):(524,19,31)}
    for v in whole:
        singleton,n90,n80=expected["共享x" in v["condition"],v["method"]]
        ep=v["modules"]["annotation"]["tables"][0]["rows"][0]
        assert int(ep["singleton_responses"])==singleton and int(ep["images"])==110
        summary=next(t for t in v["modules"]["stability"]["tables"] if t["id"]=="summary")["rows"]
        for tail,expected_count in [(.1,n90),(.2,n80)]:
            r=next(r for r in summary if int(r["J"])==3 and int(r["m"])==2 and int(r["h"])==3 and float(r["tail_fraction"])==tail)
            assert int(r["images_ge80pct_orders"])==expected_count
        assert all(int(r["no_observation_room"])==18 for r in summary if int(r["h"])==5)
        assert v["modules"]["people"]["status"]=="not_computed"
    assert all("geometry" not in v for c in data["cases"][8:] for v in c["variants"])
