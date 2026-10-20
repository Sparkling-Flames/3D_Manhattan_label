#!/usr/bin/env python3
"""Frozen assessment new-only K2: fixed ABC blocks, all integer nested cores.

The block draw is made once per pool/direction/m/replicate, before any n is
chosen. Each arm then receives the same prefix of one fixed random core order.
No target annotation geometry, quality, timings, fusion or assessment outcome
enters the generator. Two block draws are sampled; concrete blocks and core
orders are not exhaustively enumerated.
"""
from __future__ import annotations
import argparse
import collections
import datetime
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import random

from design_blocks import labels_from, counts, applicable, allowed_workers, select_blocks
from design_history_panel import read, digest, team_key

BASE=Path(__file__).resolve().parents[1]
ROOT=BASE.parent
SNAPSHOT=ROOT/"restored/work_personnel_typing_A_20261019/recovered/work_v2_20261019/fusion/INPUT_SNAPSHOT.json.gz"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_atomic(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    raw=json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    packed=gzip.compress(raw,compresslevel=6,mtime=0) if path.suffix==".gz" else raw
    if path.suffix==".gz":assert gzip.decompress(packed)==raw
    tmp=path.with_name(path.name+".tmp")
    with tmp.open("wb") as f:f.write(packed);f.flush();os.fsync(f.fileno())
    tmp.replace(path)
    if path.suffix==".gz":assert gzip.decompress(path.read_bytes())==raw


def metadata_pools(snapshot,buildings):
    # Strip individual scores/geometries immediately. Only IDs, eligibility
    # metadata and recorded source origin are available to the design below.
    payload=read(snapshot)
    pools=[{"pool_id":p["pool_id"],"meta":p["meta"],
            "records":[{"worker_id":r["worker_id"],"origin":r["origin"]} for r in p["records"]]}
           for p in payload["images"] if p["meta"]["building"] in buildings]
    del payload
    return sorted(pools,key=lambda p:p["pool_id"])


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--snapshot",type=Path,default=SNAPSHOT)
    ap.add_argument("--split",type=Path,default=ROOT/"analysis/composition/SPLIT.json")
    ap.add_argument("--labels",type=Path,default=BASE/"reverse/mixed_fit/worker_labels.csv.gz")
    ap.add_argument("--spec",type=Path,default=BASE/"assessment/NESTED_NEW2_SPEC.json")
    ap.add_argument("--freeze",type=Path,default=BASE/"assessment/ASSESSMENT_FREEZE.json")
    ap.add_argument("--out",type=Path,default=BASE/"assessment/nested_new2_requests.json.gz")
    args=ap.parse_args()
    spec,freeze,split=read(args.spec),read(args.freeze),read(args.split)
    assert spec["phase"]=="assessment" and spec["seed"]==2026102023
    assert sha(args.spec)==freeze["file_sha256"]["assessment/NESTED_NEW2_SPEC.json"]
    assert sha(args.labels)==freeze["file_sha256"]["reverse/mixed_fit/worker_labels.csv.gz"]
    registration=read(BASE/"REGISTRATION.json")
    assert sha(args.snapshot)==registration["snapshot_sha256"]
    assert set(freeze["assessment_buildings"])==set(split["validation_buildings"])
    maps=labels_from([args.labels])
    pools=metadata_pools(args.snapshot,set(freeze["assessment_buildings"]))
    requests={};events=[];paths=[];ledger=[];seen_event_ids=set()
    for method in spec["methods"]:
        mid,domain=method["method_id"],method["domain"]
        mapping=maps[mid,domain]
        assert domain=="ordinary_new" and method["allowed_origins"]==["new"]
        assert set(mapping.values())=={"C01","C02"}
        assert method["m_values"]==[2,5] and method["replicates"]==2
        assert method["matching_policies"]==["source_matched"]
        for pool in pools:
            if not applicable(pool,method):continue
            meta=pool["meta"];pid=pool["pool_id"]
            ws=allowed_workers(pool,method);origins={r["worker_id"]:r["origin"] for r in pool["records"]}
            assert len(ws)==len(set(ws)) and all(origins[w]=="new" for w in ws)
            groups={cl:sorted(w for w in ws if mapping.get(w)==cl) for cl in sorted(set(mapping.values()))}
            for outgoing,incoming in method["directions"]:
                for m in method["m_values"]:
                    reasons=[];n_min=max(3,m);n_max=len(ws)-2*m
                    if len(groups[outgoing])<2*m:reasons.append("fewer_than_2m_outgoing_class")
                    if len(groups[incoming])<m:reasons.append("fewer_than_m_incoming_class")
                    if n_max<n_min:reasons.append("no_common_core_capacity_for_any_nge3")
                    feasible_n=list(range(n_min,n_max+1)) if not reasons else []
                    row=dict(pool_id=pid,image_id=meta["image_id"],image=meta["image"],building=meta["building"],
                        difficulty=meta["difficulty"],reference_id=meta["reference_id"],method_id=mid,domain=domain,
                        outgoing_class=outgoing,incoming_class=incoming,m=m,available_new_n=len(ws),
                        outgoing_available_n=len(groups[outgoing]),incoming_available_n=len(groups[incoming]),
                        class_capacities={cl:len(g) for cl,g in groups.items()},
                        required_outgoing_n=2*m,required_incoming_n=m,n13_required_total_new_n=13+2*m,
                        feasible_n=feasible_n,n13_feasible=13 in feasible_n,
                        status="feasible" if feasible_n else "capacity_infeasible",capacity_reasons=reasons,
                        requested_replicates=method["replicates"],accepted_paths=0,accepted_events=0,
                        block_draws_are_exhaustive=False,integer_n_expansion_is_exhaustive_given_each_fixed_path=True)
                    if not feasible_n:
                        ledger.append(row);continue
                    row["unordered_AB_block_patterns_possible"]=(math.comb(len(groups[outgoing]),m)*
                        math.comb(len(groups[outgoing])-m,m)//2*math.comb(len(groups[incoming]),m))
                    seen_blocks=set()
                    for rep in range(method["replicates"]):
                        key=[spec["seed"],spec["phase"],mid,domain,method["context_id"],pid,outgoing,incoming,m,rep]
                        rng=random.Random(int(digest(key)[:16],16))
                        # Two different physical block triples when possible;
                        # A/B orientation alone does not make a second draw.
                        for attempt in range(128):
                            blocks,reason=select_blocks(groups,origins,outgoing,incoming,m,"source_matched",rng)
                            assert reason is None
                            signature=(tuple(sorted([tuple(blocks[0]),tuple(blocks[1])])),tuple(blocks[2]))
                            if signature not in seen_blocks:break
                        else:raise AssertionError("Two registered distinct block draws could not be generated")
                        seen_blocks.add(signature)
                        reserved=set(sum(blocks,[]))
                        assert len(reserved)==3*m
                        core_order=sorted(set(ws)-reserved);rng.shuffle(core_order)
                        path_id="N20_"+digest(key)[:22]
                        path=dict(path_id=path_id,phase=spec["phase"],method_id=mid,domain=domain,
                            context_id=method["context_id"],pool_id=pid,image_id=meta["image_id"],image=meta["image"],
                            building=meta["building"],difficulty=meta["difficulty"],reference_id=meta["reference_id"],
                            outgoing_class=outgoing,incoming_class=incoming,m=m,replicate=rep,
                            outgoing_workers=blocks[0],within_incoming=blocks[1],cross_incoming=blocks[2],
                            core_order=core_order,feasible_n=feasible_n,event_ids=[],seed_key=key,
                            block_redraws_for_physical_uniqueness=attempt)
                        previous=None
                        for n in feasible_n:
                            prefix=core_order[:n-m];core=sorted(prefix)
                            assert len(core)==n-m
                            arms=[sorted(core+b) for b in blocks]
                            ca,cb,cc=[counts(a,mapping) for a in arms]
                            assert ca==cb and ca!=cc
                            assert all(len(set(a))==len(a)==n for a in arms)
                            A,B,C=map(set,arms)
                            assert A&B==A&C==B&C==set(core)
                            assert len(A-B)==len(A-C)==len(B-C)==m
                            if previous is not None:
                                assert n==previous[0]+1
                                assert all(set(a)-set(p)=={core_order[n-m-1]} and not set(p)-set(a) for a,p in zip(arms,previous[1]))
                            event_id="I20_"+digest([path_id,n])[:22]
                            assert event_id not in seen_event_ids;seen_event_ids.add(event_id)
                            e=dict(event_id=event_id,path_id=path_id,phase=spec["phase"],method_id=mid,domain=domain,
                                family=method["family"],context_id=method["context_id"],pool_id=pid,
                                building=meta["building"],image=meta["image"],image_id=meta["image_id"],
                                difficulty=meta["difficulty"],layer=meta["layer"],condition=meta["condition"],
                                reference_id=meta["reference_id"],reference_version=meta.get("reference_version"),
                                n=n,k=n,m=m,outgoing_class=outgoing,incoming_class=incoming,
                                background_policy="nested_random_prefix",matching="source_matched",actual_source_match=True,
                                core_workers=core,outgoing_workers=blocks[0],within_incoming=blocks[1],cross_incoming=blocks[2],
                                A_counts=ca,B_counts=cb,C_counts=cc,core_counts=counts(core,mapping),
                                changed_category_slots=m,pattern="single_class_block",
                                outside_background_n=sum(w not in mapping for w in core),complete_turnover=m==n,
                                direction=outgoing+">"+incoming,allowed_origins=["new"],excluded_workers=[],
                                available_population_n=len(ws),replicate=rep,B_to_C_actual_turnover=m,
                                core_prefix_n=len(core),path_step=n-n_min,
                                added_core_worker=core_order[n-m-1] if previous is not None else None,
                                primary_role="large_block_primary" if n==13 and m==5 else "dilution_control" if n==13 and m==2 else "frozen_integer_n_curve")
                            for arm,workers in zip("ABC",arms):
                                tk=team_key(pid,workers);e[arm+"_workers"]=workers;e[arm+"_team_key"]=tk
                                request=dict(request_id=tk,pool_id=pid,k=n,worker_ids=workers,
                                    reference_id=meta["reference_id"],reference_version=meta.get("reference_version"))
                                if tk in requests:assert requests[tk]==request
                                requests.setdefault(tk,request)
                            events.append(e);path["event_ids"].append(event_id);previous=(n,arms)
                        paths.append(path)
                    row["accepted_paths"]=method["replicates"];row["accepted_events"]=method["replicates"]*len(feasible_n)
                    ledger.append(row)
    common=dict(schema="interchangeability_nested_new2_requests_v1",spec=spec,
        input_sha256={str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p):sha(p) for p in [args.snapshot,args.split,args.labels,args.spec,args.freeze,Path(__file__)]},
        design="Draw fixed disjoint A/B outgoing-class blocks and C incoming-class block once; add identical prefixes of one fixed shuffled eligible-new core order for every capacity-feasible integer n>=3.",
        events_per_pool_field="Generic inherited field is inactive for the explicitly registered all-feasible-integer nested design; two full paths per direction/m/pool.")
    payload=dict(common,events=events,requests=list(requests.values()),paths=paths,ledger=ledger)
    write_atomic(args.out,payload)
    rec=dict(common,registered_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        request_sha256=sha(args.out),events=len(events),requested_team_rows=3*len(events),unique_teams=len(requests),
        pools=len({e["pool_id"] for e in events}),true_images=len({e["image_id"] for e in events}),
        buildings=len({e["building"] for e in events}),workers=len({w for e in events for arm in "ABC" for w in e[arm+"_workers"]}),
        fixed_paths=len(paths),capacity_cells=len(ledger),infeasible_capacity_cells=sum(r["status"]!="feasible" for r in ledger),
        n_nodes=sorted({e["n"] for e in events}),m_nodes=sorted({e["m"] for e in events}),
        n13_capacity=[dict(outgoing_class=out,incoming_class=inc,m=m,
            eligible_pool_cells=sum(r["outgoing_class"]==out and r["incoming_class"]==inc and r["m"]==m for r in ledger),
            feasible_pools=sum(r["outgoing_class"]==out and r["incoming_class"]==inc and r["m"]==m and r["n13_feasible"] for r in ledger),
            feasible_true_images=len({r["image_id"] for r in ledger if r["outgoing_class"]==out and r["incoming_class"]==inc and r["m"]==m and r["n13_feasible"]}),
            feasible_buildings=len({r["building"] for r in ledger if r["outgoing_class"]==out and r["incoming_class"]==inc and r["m"]==m and r["n13_feasible"]}),
            events=sum(e["outgoing_class"]==out and e["incoming_class"]==inc and e["m"]==m and e["n"]==13 for e in events))
            for out,inc in spec["methods"][0]["directions"] for m in spec["methods"][0]["m_values"]],
        invariants=dict(fixed_blocks_across_n=True,identical_core_prefix_each_arm=True,single_same_core_worker_added_each_step=True,
            actual_member_counts_and_turnover=True,source_new_only=True,frozen_label_composition=True,missing_capacity_not_modified=True),
        coverage_limit="All pool/direction/m capacity cells and all integer n for 2 fixed paths per feasible cell; not all blocks, core permutations or concrete teams.",
        assessment_outcomes_used_for_design=False)
    write_atomic(args.out.parent/"NESTED_NEW2_DESIGN_RECEIPT.json",rec)
    write_atomic(args.out.parent/"NESTED_NEW2_PATHS.json.gz",dict(input_request_sha256=sha(args.out),paths=paths))
    write_atomic(args.out.parent/"NESTED_NEW2_CAPACITY.json",dict(input_request_sha256=sha(args.out),ledger=ledger))
    print(json.dumps({k:rec[k] for k in ["events","unique_teams","pools","true_images","buildings","fixed_paths","n_nodes","m_nodes","n13_capacity"]},ensure_ascii=False),flush=True)


if __name__=="__main__":main()
