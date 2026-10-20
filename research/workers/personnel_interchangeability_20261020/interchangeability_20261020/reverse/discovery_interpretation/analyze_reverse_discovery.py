#!/usr/bin/env python3
"""Frozen reverse-class discovery blocks: streaming metadata, real outcomes.

Never read assessment. Do not load the much larger top-level requests array.
Every requested event is audited against frozen labels before any outcome is
summarized; missing/incomplete pools are a blocking data state, not failures.
"""
from __future__ import annotations
import argparse
from collections import Counter
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent;BASE=HERE.parent;ROOT=BASE.parents[1]
sys.path.insert(0,str(BASE))
from learn_swap_types import clean,sha,write_csv,write_json


def stream_events(path):
    """Canonical design writer places events first; decode one object at a time."""
    decoder=json.JSONDecoder()
    with gzip.open(path,"rt",encoding="utf-8") as f:
        prefix=f.read(len('{"events":['))
        assert prefix=='{"events":[',"Use canonical frozen design writer; do not scan arbitrary nested keys"
        buf="";eof=False
        while True:
            buf=buf.lstrip()
            if buf.startswith(","):buf=buf[1:].lstrip()
            if buf.startswith("]"):return
            if not buf or not eof:
                # A bounded chunk may contain many events. Only refill when
                # raw_decode signals an incomplete object below.
                pass
            try:
                if not buf:raise json.JSONDecodeError("empty",buf,0)
                event,end=decoder.raw_decode(buf)
            except json.JSONDecodeError:
                if eof:raise RuntimeError("Truncated event array")
                piece=f.read(1<<18);eof=not piece;buf+=piece
                assert len(buf)<16*(1<<20),"Unexpectedly large individual event"
                continue
            assert isinstance(event,dict)
            yield event;buf=buf[end:]


def build_index(discovery,out):
    request=discovery/"reverse_requests.json.gz"
    split=json.load(open(ROOT/"analysis/composition/SPLIT.json"))
    roster=pd.read_csv(ROOT/"analysis/forward/results/features_train.csv.gz",usecols=["worker_id"]).worker_id.tolist()
    assert len(roster)<=64;bits={w:1<<i for i,w in enumerate(sorted(roster))}
    labels={};sources=[]
    for family in ["legacy","mixed"]:
        fit=BASE/(family+"_fit");m=json.load(open(fit/"METHOD_MANIFEST.json"))
        short=json.load(open(BASE/(family.upper()+"_SCREEN_SHORTLIST.json")))
        assert sha(fit/"worker_labels.csv.gz")==short["labels_sha256"]
        sources.append({"family":family,"labels_sha256":short["labels_sha256"]})
        for info in short["methods"]:
            spec=m[info["method_id"]]
            labels[spec["method_id"]]={w:c for c,ws in spec["classes"].items() for w in ws}
    rows=[];seen=set();support=Counter()
    for e in stream_events(request):
        assert e["phase"]=="discovery" and e["building"] in split["discovery_buildings"]
        assert e["event_id"] not in seen;seen.add(e["event_id"])
        mapping=labels[e["method_id"]]
        A,B,C,core=[set(e[k]) for k in ["A_workers","B_workers","C_workers","core_workers"]]
        assert len(A)==len(B)==len(C)==e["n"]
        assert A&B==A&C==core and len(A-B)==len(A-C)==e["m"]
        assert len(B-C)==e.get("B_to_C_actual_turnover",len(B-C))
        blocks=[set(e[k]) for k in ["outgoing_workers","within_incoming","cross_incoming"]]
        assert blocks==[A-core,B-core,C-core]
        assert all(w in mapping for w in set.union(*blocks)),"Unclassified worker cannot be a replaceable block member"
        for arm,workers in [("A",A),("B",B),("C",C)]:
            counts=Counter(mapping.get(w,"outside_group") for w in workers)
            if arm+"_counts" in e:assert counts==Counter(e[arm+"_counts"]),(e["event_id"],arm)
        assert Counter(mapping.get(w,"outside_group") for w in A)==Counter(mapping.get(w,"outside_group") for w in B)
        row={key:e.get(key) for key in ["event_id","phase","pool_id","building","image","method_id","domain","context_id","n","m","outgoing_class","incoming_class","pattern","direction"]}
        row["B_to_C_actual_turnover"]=len(B-C)
        row["event_definition_sha256"]=hashlib.sha256(json.dumps(e,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        for key in ["A_workers","B_workers","C_workers","core_workers","outgoing_workers","within_incoming","cross_incoming"]:
            row[key]="|".join(sorted(e[key]))
        for key,workers in [("all_worker_mask",A|B|C),("block_worker_mask",set.union(*blocks)),
            ("out_worker_mask",blocks[0]),("within_worker_mask",blocks[1]),("cross_worker_mask",blocks[2]),("core_worker_mask",core)]:
            row[key]=sum(bits[w] for w in workers)
        rows.append(row);support[e["pool_id"]]+=1
    frame=pd.DataFrame(rows);write_csv(out/"event_member_index.csv.gz",frame)
    receipt=dict(schema="reverse_discovery_streaming_member_index_v1",request_sha256=sha(request),
        indexed_events=len(frame),pool_event_counts=dict(support),buildings=sorted(frame.building.unique()),
        frozen_label_sources=sources,roster_bits={w:i for i,w in enumerate(sorted(roster))},
        member_count_core_turnover_class_count_checks=True,unclassified_replaceable_workers=0,
        parser="Read only canonical first top-level events array; never resident-load requests array",source_script_sha256=sha(Path(__file__)))
    write_json(out/"MEMBER_INDEX_RECEIPT.json",clean(receipt))
    return frame,receipt


def prepare(frame):
    for arm in "ABC":frame[arm+"_score_missing"]=frame[arm+"_B8L2"].isna()
    for kind in ["within","cross"]:
        q=frame[kind+"_B8L2_change"]
        frame[kind+"_Q_drop_gt5"]=(q< -5).astype(float).where(q.notna())
        frame[kind+"_absQ_gt5"]=frame[kind+"_bad_Q_gt5"]
    frame["net_Q_worsen_gt5"]=(frame.net_B8L2_change< -5).astype(float).where(frame.net_B8L2_change.notna())
    for kind in ["source","target"]:
        x=frame["within_"+kind+"_block_seconds"];y=frame["cross_"+kind+"_block_seconds"]
        ok=(x>0)&(y>0)&x.notna()&y.notna();frame[kind+"_time_comparable"]=ok
        frame[kind+"_block_log_ratio"]=np.log((y/x).where(ok))
    frame["within_source_seconds_per_replaced_person"]=frame.within_source_block_seconds/frame.m
    frame["cross_source_seconds_per_replaced_person"]=frame.cross_source_block_seconds/frame.m
    frame["source_seconds_change_per_replaced_person"]=frame.net_source_block_seconds/frame.m
    source_ok=frame.source_time_comparable;save=frame.cross_over_within_source_block_time<=.8
    qgood=frame.B_complete&frame.C_complete&frame.net_B8L2_change.notna()&(frame.net_B8L2_change>=-2)
    frame["source_save20"]=save.astype(float).where(source_ok)
    frame["source_save20_Q_not_worse2"]=(save&qgood).astype(float).where(source_ok)
    frame["source_save20_Q_not_worse2_same_noQ_geometry"]=(save&qgood&frame.net_geometry_noQ_main).astype(float).where(source_ok)
    # Floor and prism remain separate. The latter is a mean-height proxy.
    for kind in ["within","cross"]:
        frame[kind+"_prism_distance"]=1-frame[kind+"_mean_height_prism_pair_iou"]
    frame["excess_prism_distance"]=frame.cross_prism_distance-frame.within_prism_distance
    frame["within_any_endpoint_score_missing"]=frame.A_score_missing|frame.B_score_missing
    frame["within_endpoint_Q_mean"]=(frame.A_B8L2+frame.B_B8L2)/2
    frame["within_unordered_team_pair"]=["|".join(sorted(v)) for v in frame[["A_team_key","B_team_key"]].itertuples(index=False,name=None)]
    return frame


def within_adjust(tables,data,keys):
    """Restrict support and team-score tails to unique ACTUAL A/B teams."""
    import functools
    def people(values):return int(functools.reduce(int.__or__,map(int,values),0)).bit_count()
    per_image,per_building,aggregate=tables
    if aggregate.empty:return tables
    support=[]
    for key,g in data.groupby(keys,dropna=False):
        key=key if isinstance(key,tuple) else (key,)
        r=dict(zip(keys,key));allmask=g.core_worker_mask|g.out_worker_mask|g.within_worker_mask
        r.update(unique_teams=len(set(g.A_team_key)|set(g.B_team_key)),all_people=people(allmask),
            block_people=people(g.out_worker_mask|g.within_worker_mask))
        for metric in ["within_abs_B8L2_change","within_floor_jaccard_difference","within_prism_distance"]:
            finite=g[g[metric].notna()]
            r[metric+"_known_events"]=len(finite);r[metric+"_known_images"]=finite.pool_id.nunique()
            r[metric+"_known_buildings"]=finite.building.nunique()
        support.append(r)
    aggregate=aggregate.drop(columns=["unique_teams","all_people","block_people"])
    aggregate=aggregate.merge(pd.DataFrame(support),on=keys,validate="one_to_one")
    # Symmetric pair deduplication gives no preferred A/B orientation. Quality
    # levels and low tails therefore use each distinct endpoint team once.
    parts=[]
    for arm in "AB":
        t=data[keys+["building","pool_id",arm+"_team_key",arm+"_B8L2",arm+"_D10",arm+"_complete"]].copy()
        t=t.rename(columns={arm+"_team_key":"team_key",arm+"_B8L2":"Q",arm+"_D10":"D10",arm+"_complete":"complete"})
        parts.append(t)
    teams=pd.concat(parts,ignore_index=True).drop_duplicates(keys+["building","pool_id","team_key"])
    teams["score_available"]=teams.Q.notna()
    tq=teams.groupby(keys+["building","pool_id"],dropna=False).agg(
        within_unique_team_Q_mean=("Q","mean"),within_unique_team_Q_p10=("Q",lambda x:x.quantile(.1)),
        within_unique_team_Q_worst=("Q","min"),within_unique_team_D10_mean=("D10","mean"),
        within_unique_team_complete_fraction=("complete","mean"),within_unique_team_score_available_fraction=("score_available","mean"),
        within_unique_team_attempts=("team_key","size"),within_unique_team_scored=("Q","count")).reset_index()
    qmetrics=[c for c in tq if c.startswith("within_unique_team_") and c not in ["within_unique_team_attempts","within_unique_team_scored"]]
    bq=tq.groupby(keys+["building"],dropna=False)[qmetrics].mean().reset_index()
    aq=bq.groupby(keys,dropna=False)[qmetrics].mean().reset_index()
    per_image=per_image.merge(tq,on=keys+["building","pool_id"],validate="one_to_one")
    per_building=per_building.merge(bq,on=keys+["building"],validate="one_to_one")
    aggregate=aggregate.merge(aq,on=keys,validate="one_to_one")
    result=[]
    support_names={"events","images","buildings","unique_teams","all_people","block_people","outgoing_people",
        "within_incoming_people","n_min","n_max","m_min","m_max","replaced_fraction_min","replaced_fraction_max"}
    for table in [per_image,per_building,aggregate]:
        keep=[c for c in table if c in keys+["building","pool_id"] or c in support_names
              or (c.startswith("within_") and c!="within_Q_drop_gt5")]
        result.append(table[keep])
    return result


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--discovery",type=Path,default=ROOT/"interchangeability_20261020/discovery")
    ap.add_argument("--out",type=Path,default=HERE);ap.add_argument("--index-only",action="store_true")
    ap.add_argument("--rebuild-index",action="store_true")
    a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    path=a.out/"MEMBER_INDEX_RECEIPT.json"
    if path.exists() and not a.rebuild_index:
        index_receipt=json.load(open(path));assert index_receipt["request_sha256"]==sha(a.discovery/"reverse_requests.json.gz")
        members=pd.read_csv(a.out/"event_member_index.csv.gz")
    else:members,index_receipt=build_index(a.discovery,a.out)
    if a.index_only:return
    official=a.discovery/"reverse_metrics/SUMMARY_RECEIPT.json"
    if not official.exists():raise RuntimeError("Await root's complete reverse summary receipt; no partial-panel interpretation")
    official_receipt=json.load(open(official));assert official_receipt["request_sha256"]==index_receipt["request_sha256"]
    parts=a.discovery/"reverse_metrics/event_parts";frames=[];part_shas=[]
    for pid,n in sorted(index_receipt["pool_event_counts"].items()):
        p=parts/(pid+".csv.gz");f=pd.read_csv(p)
        expected=set(members[members.pool_id.eq(pid)].event_id)
        assert len(f)==n and set(f.event_id)==expected and not f.event_id.duplicated().any()
        assert set(f.phase)=={"discovery"}
        frames.append(f);part_shas.append({"pool_id":pid,"sha256":sha(p)})
    frame=pd.concat(frames,ignore_index=True);del frames
    mask_columns=[c for c in members if c.endswith("_mask")]
    frame=frame.merge(members[["event_id"]+mask_columns],on="event_id",validate="one_to_one")
    split=json.load(open(ROOT/"analysis/composition/SPLIT.json"))
    assert set(frame.building).issubset(split["discovery_buildings"])
    frame=prepare(frame)
    helper_path=ROOT/"interchangeability_20261020/forward/discovery_interpretation/analyze_discovery.py"
    spec=importlib.util.spec_from_file_location("frozen_shared_direction_summarizer",helper_path)
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    metrics=helper.KEY_METRICS+["within_prism_distance","cross_prism_distance","excess_prism_distance",
        "within_wall_coverage_symmetric_min_main","cross_wall_coverage_symmetric_min_main",
        "within_true_corner_F1_main","cross_true_corner_F1_main","within_true_corner_count_difference","cross_true_corner_count_difference",
        "within_different_original_nodes_shape_main_passes","cross_different_original_nodes_shape_main_passes",
        "within_endpoint_Q_mean","within_any_endpoint_score_missing"]
    # Only one level's output is resident at a time; do not accumulate all
    # per-image exact-n/m tables while native fusion occupies the same machine.
    definitions=[("method",[],False,False),("direction",["outgoing_class","incoming_class"],False,False),
        ("direction_difficulty",["outgoing_class","incoming_class","difficulty"],False,False),
        ("direction_nband",["outgoing_class","incoming_class","n_band"],False,False),
        ("direction_n_m",["outgoing_class","incoming_class","n","m"],True,False),
        ("direction_m",["outgoing_class","incoming_class","m"],True,False),
        ("direction_ratio",["outgoing_class","incoming_class","m_fraction_band"],True,False),
        ("direction_background",["outgoing_class","incoming_class","background_policy"],True,False),
        ("within_class",["outgoing_class"],False,True),
        ("within_class_difficulty",["outgoing_class","difficulty"],False,True),
        ("within_class_n_m",["outgoing_class","n","m"],False,True)]
    for name,extra,only_primary,is_within in definitions:
        pieces={level:[] for level in ["per_image","per_building","aggregate"]}
        for subset,data in helper.eligible_views(frame):
            if only_primary and subset!="primary_nge3_mge2_all":continue
            data=data.copy();data["subset"]=subset
            base=["subset","method_id","domain","context_id"]
            # A/B comparisons reused against other C teams count only once in
            # the within-class table. Signed A->B drop is not interpreted after
            # unordered-pair deduplication; symmetric measures remain valid.
            if is_within:data=data.sort_values("event_id").drop_duplicates(base+["within_unordered_team_pair"])
            tables=helper.summarize(data,base+extra,metrics=metrics,tails=not is_within and name!="direction_n_m")
            if is_within:tables=within_adjust(tables,data,base+extra)
            for level,table in zip(pieces,tables):pieces[level].append(table)
        for level,parts in pieces.items():
            write_csv(a.out/(name+"_"+level+".csv.gz"),pd.concat(parts,ignore_index=True))
        del pieces,tables,data
        print(json.dumps({"summary_level_completed":name}),flush=True)
    # Small actual-event review index with gains, losses and structural
    # counterexamples. It is discovery selection, never assessment evidence.
    primary=frame[(frame.n>=3)&(frame.m>=2)]
    cases=[];keys=["method_id","domain","context_id","outgoing_class","incoming_class"]
    for key,g in primary.groupby(keys,dropna=False):
        for field,ascending,reason in [("net_B8L2_change",False,"quality_gain"),("net_B8L2_change",True,"quality_loss"),
            ("within_floor_jaccard_difference",False,"within_class_floor_failure"),
            ("excess_floor_jaccard_difference",False,"cross_more_shape_change"),
            ("gap_geometry_shape_main",False,"new_shape_separation"),
            ("gap_geometry_shape_main",True,"new_shape_counterexample")]:
            for r in g.dropna(subset=[field]).sort_values([field,"event_id"],ascending=[ascending,True]).drop_duplicates("building").head(2).to_dict("records"):
                row={c:r[c] for c in ["event_id","pool_id","building","image","difficulty","n","m","actual_source_match","all_blocks_history_Q_close3",
                    "A_team_key","B_team_key","C_team_key","A_composition","C_composition","core_composition","A_B8L2","B_B8L2","C_B8L2",
                    "net_B8L2_change","net_D10_change","within_joint_stable_main","cross_joint_stable_main","within_geometry_noQ_main","cross_geometry_noQ_main",
                    "within_geometry_shape_main","cross_geometry_shape_main","within_floor_jaccard_difference","cross_floor_jaccard_difference",
                    "within_node_count_difference","cross_node_count_difference","net_diag_wall_coverage_05_delta","net_diag_corner_recall_05_delta",
                    "A_complete","B_complete","C_complete","cross_minus_within_history_Q"]}
                row.update(dict(zip(keys,key)),selection_reason=reason);cases.append(row)
    case=pd.DataFrame(cases).merge(members[["event_id"]+[c for c in members if c.endswith("_workers") or c in ["within_incoming","cross_incoming"]]],on="event_id",validate="many_to_one")
    write_csv(a.out/"case_search_index.csv.gz",case)
    # All attempted n remain in support, while inherited n2 deferral is explicit.
    qualification=frame.groupby(["method_id","domain","context_id","n"],dropna=False).agg(events=("event_id","size"),
        images=("pool_id","nunique"),buildings=("building","nunique"),A_score_known=("A_B8L2","count"),B_score_known=("B_B8L2","count"),C_score_known=("C_B8L2","count")).reset_index()
    qualification["eligibility"]=np.where(qualification.n==2,"inherited_two_person_deferral","eligible_n_ge3")
    write_csv(a.out/"n_qualification.csv.gz",qualification)
    write_json(a.out/"REVERSE_DISCOVERY_INTERPRETATION_RECEIPT.json",clean(dict(
        request_sha256=index_receipt["request_sha256"],member_index_sha256=sha(a.out/"event_member_index.csv.gz"),
        official_summary_sha256=sha(official),pool_part_shas=part_shas,script_sha256=sha(Path(__file__)),helper_sha256=sha(helper_path),
        methods=frame.method_id.nunique(),settings=len(frame[["method_id","domain","context_id"]].drop_duplicates()),events=len(frame),
        primary_events=len(primary),primary_images=primary.pool_id.nunique(),primary_buildings=primary.building.nunique(),
        all_unique_teams=len(set(frame.A_team_key)|set(frame.B_team_key)|set(frame.C_team_key)),
        n2_deferred_events=int(frame.n.eq(2).sum()),all_frozen_labels_unchanged=True,assessment_outputs_loaded=False,
        weighting="event means within image, image means within building, buildings equal; cell-specific finite support retained",
        within_table="unordered actual A/B pair deduplicated across incoming directions within method/context/subset; all support/worker/unique-team counts exclude C; Q mean/p10/worst uses unique A/B endpoint teams per image, then building hierarchy. No arbitrarily oriented signed A->B drop reported.",
        method_comparison="Distinct methods sampled different actual n/m/core/ABC panels; headline differences are not isolated causal algorithm improvements",
        source_context="Same-source whole-team and source-external fixed-background settings remain separate",
        tail="p10 computed within each image then same building hierarchy; attempt failures missing score remain separate, no zero fill")))


if __name__=="__main__":main()
