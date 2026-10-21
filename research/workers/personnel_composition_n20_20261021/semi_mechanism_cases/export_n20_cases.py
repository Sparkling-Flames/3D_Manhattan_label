#!/usr/bin/env python3
"""Explain two completed n20 matched comparisons, without changing endpoints.

These cases were selected after viewing results, one positive and one counter-
example on the same image. They do not estimate frequencies or discover labels.
Six existing sets are replayed only to recover their unretained vote ledgers;
each replay must reproduce the cached geometry exactly. No scoring is repeated.
"""
from __future__ import annotations
import collections
import hashlib
import importlib.util
import itertools
import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
CONT = HERE.parent
STUDY = CONT.parent
sys.path.insert(0, str(STUDY / "composition"))
import global_study as gs

SPECS = [
    dict(case_id="N20_SP_q9_positive_m15", event_id="927bb09d3927de85e8c3fe35",
         title="20人换15人：同构成相近，改构成后质量和形状改变",
         subtitle="q9-15 / Semi / SP粗类；两条比较均为5人共同背景＋替换15人；B到C实际换6人"),
    dict(case_id="N20_SP_q9_counterexample_m13", event_id="cae738f17a9d1a72768717fb",
         title="同图反例：20人换13人，同构成变化反而更大",
         subtitle="q9-15 / Semi / SP粗类；两条比较均为7人共同背景＋替换13人；B到C实际换6人"),
]


def main():
    source = CONT / "n20_abc/results_semi/N20_ABC_ALL_COMPONENT_EVENTS.csv.gz"
    events = pd.read_csv(source, low_memory=False, keep_default_na=False)
    labels = pd.read_csv(STUDY / "composition/FROZEN_LABELS.csv", keep_default_na=False)
    pools = gs.pool_lookup()
    fe, _, _, _ = gs.setup_engine()
    cases, receipts = [], []
    with fe.cached_matching():
        for spec in SPECS:
            selected = events[events.event_id == spec["event_id"]]
            assert len(selected) == 1
            event = selected.iloc[0].to_dict()
            pool = pools[event["pool_id"]]
            byworker = {r["worker_id"]: r for r in pool["records"]}
            labs = labels[(labels.method_id == event["method_id"]) &
                          (labels.tier == event["tier"]) &
                          (labels.condition == event["condition"]) &
                          (labels.heldout_building == event["building"])]
            bylabel = dict(zip(labs.worker_id, labs.class_id))
            wanted = {event["team_" + a] for a in "ABC"}
            native, source_paths = {}, []
            paths = [STUDY / "composition/runtime/endpoints" / (pool["pool_id"] + ".json.gz")]
            paths += sorted((CONT / "next_stage/runtime").glob("*/" + pool["pool_id"] + ".json.gz"))
            for path in paths:
                if not path.exists():
                    continue
                rows = [r for r in gs.read(path)["teams"] if r["team_key"] in wanted]
                if rows:
                    source_paths.append(dict(path=str(path.relative_to(STUDY)),
                                             sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
                for r in rows:
                    if r["team_key"] in native:
                        assert gs.digest(r["geometry"]) == gs.digest(native[r["team_key"]]["geometry"])
                    native[r["team_key"]] = r
            assert set(native) == wanted
            case = dict(spec, method_id=event["method_id"], tier=event["tier"],
                        event=event, pool_id=pool["pool_id"], pool_meta=pool["meta"],
                        image_id=pool["meta"]["image_id"],
                        reference=dict(pool["reference"], reference_id=pool["meta"]["reference_id"]),
                        selection="post_result_positive_and_counterexample_on_same_image_not_frequency_estimation",
                        label_scope="frozen_target_building_excluded_SP_coarse",
                        class_names={"SP_LOW": "SP_LOW 较低推导高度", "SP_OTHER": "SP_OTHER 其余尺度表达"},
                        class_colors={"SP_LOW": "#ae5c29", "SP_OTHER": "#216f98"},
                        member_overlay_title=spec["title"] + "：全部实际成员按楼外类别叠加",
                        teams=[])
            union = set()
            for arm in "ABC":
                t = dict(native[event["team_" + arm]])
                union.update(t["member_workers"])
                assert t["k"] == 20
                assert "|".join(sorted(t["member_workers"])) == event[arm + "_member_workers"]
                state = fe.clean(fe.compact(fe.fuse([byworker[w] for w in sorted(t["member_workers"])], gap=fe.WORKING_GAP)["automatic"]))
                assert gs.digest(state["candidate"]) == gs.digest(t["geometry"])
                assert state["n"] == t["k"]
                assert state["minimum_support"] == t["minimum_support"]
                assert len(state["node_consensus"]["nodes"]) == t["nodes"]
                counts = dict(collections.Counter(bylabel[w] for w in t["member_workers"]))
                assert gs.canonical_counts(counts) == event["composition_" + arm]
                t.update(label=arm, counts=counts, full_state=state)
                case["teams"].append(t)
            case["members"] = [dict(byworker[w], class_id=bylabel[w]) for w in sorted(union)]
            # This deterministic representation is disclosed; no individual is
            # selected because their target score agrees with the group name.
            case["raw_overlay_workers"] = [w for cl in sorted(set(bylabel[w] for w in union))
                for w in sorted(w for w in union if bylabel[w] == cl)[:3]]
            out = HERE / "cases" / (spec["case_id"] + ".json.gz")
            gs.save(out, case)
            assert gs.read(out) == gs.clean(case)
            receipts.append(dict(case_id=case["case_id"], event_id=event["event_id"],
                event_table_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                pool_sha256=gs.digest(pool), native_sources=source_paths,
                new_endpoint_count=0, full_state_replays=3, score_calls=0,
                all_native_geometry_exact=True, output_sha256=hashlib.sha256(out.read_bytes()).hexdigest()))
            cases.append(case)
            print(json.dumps({"case_id":case["case_id"],"teams":[{k:t.get(k) for k in
                ["label","B8L2","D10","nodes","minimum_support","height_mean_ratio","counts"]} for t in case["teams"]]},ensure_ascii=False),flush=True)

    module_spec = importlib.util.spec_from_file_location("old_vote_transitions", STUDY / "evidence/analyze_vote_transitions.py")
    trans = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(trans)
    transitions, links, votes, metrics = [], [], [], []
    for case in cases:
        bylabel = {r["worker_id"]:r["class_id"] for r in case["members"]}
        for t in case["teams"]:
            metrics.append(dict(case_id=case["case_id"],arm=t["label"],**{k:t.get(k) for k in
                ["team_key","B8L2","D10","IoU3D100","iou_2d","S_bottom_deg","dir","Hmean","Hcenter",
                 "omission","extension","height_mean_ratio","nodes","minimum_support","ref_node_recall_9",
                 "source_time_total_seconds","source_time_known_n","target_time_total_seconds","target_time_known_n"]}))
            for g in t["full_state"]["identity_groups"]:
                votes.append(dict(case_id=case["case_id"],arm=t["label"],feature_id=g["feature_id"],
                    support=g["support"],threshold=t["minimum_support"],selected=g["selected"],
                    top_x=g["center"][0][0],top_y=g["center"][0][1],
                    bottom_x=g["center"][1][0],bottom_y=g["center"][1][1],
                    class_votes=gs.canonical_counts(collections.Counter(bylabel[m["worker"]] for m in g["members"])),
                    member_workers="|".join(sorted(m["worker"] for m in g["members"])),
                    observation_keys="|".join(f"{x[0]}:{x[1]}" for x in sorted(trans.obs(g)))))
        for a,b in itertools.combinations(case["teams"],2):
            trans.analyze_pair(case,a,b,transitions,links)
    for name,rows in [("CASE_ENDPOINT_METRICS.csv",metrics),("GROUP_CLASS_VOTES.csv",votes),
                      ("OBSERVATION_TRANSITIONS.csv",transitions),("GROUP_OVERLAP_LINKS.csv",links)]:
        path=HERE/name
        frame=pd.DataFrame(rows)
        tmp=path.with_suffix(path.suffix+".tmp")
        frame.to_csv(tmp,index=False,encoding="utf-8-sig")
        back=pd.read_csv(tmp)
        assert back.shape==frame.shape
        tmp.replace(path)
    gs.save(HERE/"CASE_EXPORT_RECEIPT.json",dict(cases=receipts,
        no_new_teams=True,total_state_replays=6,total_score_calls=0,
        node_correspondence="immutable observation record id + pair index; no cross-team node-id assumption"))


if __name__=="__main__":
    main()
