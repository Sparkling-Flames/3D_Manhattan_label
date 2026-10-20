"""Independent, all-event audit of the frozen baseline identity design."""
from collections import Counter, defaultdict
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys
import pandas as pd

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/"analysis/composition"))
import fusion_runner as fr
import summarize_grid as sg


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--folder",type=Path,default=Path(__file__).parent);a=ap.parse_args();out=a.folder
    spec=fr.read(out/"BASELINE_SPEC.json");freeze=fr.read(out/"DESIGN_FREEZE.json");payload=fr.read(out/"REQUESTS.json.gz")
    assert sha(out/"BASELINE_SPEC.json")==freeze["spec_sha256"]==payload["spec_sha256"]
    for name,key in [("REQUESTS.json.gz","request_sha256"),("EVENT_DESIGN.csv.gz","event_design_sha256"),("SEARCH_LEDGER.csv","ledger_sha256"),("POOL_CAPACITY.csv","pool_capacity_sha256")]:assert sha(out/name)==freeze[key]
    for path,expected in spec["source_sha256"].items():assert sha(ROOT/path)==expected,path
    pools={p["pool_id"]:p for p in fr.read(ROOT/"restored/work_personnel_typing_A_20261019/recovered/work_v2_20261019/fusion/INPUT_SNAPSHOT.json.gz")["images"]}
    labels=sg.labels_from_files([ROOT/"analysis/reverse/worker_labels.csv.gz"])
    events=pd.read_csv(out/"EVENT_DESIGN.csv.gz",keep_default_na=False).to_dict("records")
    req={r["request_id"]:r for r in payload["requests"]};assert len(req)==len(payload["requests"])
    blocks={b["block_id"]:b for b in payload["blocks"]};assert len(blocks)==len(payload["blocks"])
    seen=defaultdict(set);ns=defaultdict(list);used=set();people=set();observed_nm=defaultdict(set);actuals={}
    for e in events:
        pool=pools[e["pool_id"]];rec={r["worker_id"]:r for r in pool["records"]};rule=spec["targets"][e["target"]];m=e["m"];n=e["k"]
        lm=labels[(rule["method_id"],"all")];b=blocks[e["block_id"]];core=set(b["core_order"][:n-m]);eligible=set(rec)&lm.keys()
        assert pool["meta"]["layer"]=="ordinary_manual" and pool["meta"]["building"] in spec[("discovery" if e["historical_phase"]=="discovery" else "assessment")+"_buildings"]
        assert b["m"]==m and b["target"]==e["target"] and b["pool_id"]==e["pool_id"]
        assert set(b["core_order"])==eligible-set(sum(b["blocks"].values(),[])) and len(b["core_order"])==len(set(b["core_order"]))==len(eligible)-3*m
        arms={};counts={};origins={}
        for arm in "ABC":
            r=req[e["event_id"]+"__"+arm];ws=set(r["worker_ids"]);arms[arm]=ws
            assert ws==core|set(b["blocks"][arm]) and len(ws)==n==len(r["worker_ids"])
            assert r["team_key"]==e[arm+"_team_key"]==fr.team_key(e["pool_id"],sorted(ws))
            assert r["pool_id"]==e["pool_id"] and r["k"]==n and ws<=eligible
            counts[arm]=Counter(lm[w] for w in ws);origins[arm]=Counter(rec[w]["origin"] for w in ws)
            assert {k:v for k,v in r["counts"].items() if v}==counts[arm]
            assert {lm[w] for w in ws-core}=={rule["incoming"] if arm=="C" else rule["outgoing"]}
            used.add(r["request_id"]);people.update(ws);actuals[r["team_key"]]=(e["pool_id"],tuple(sorted(ws)))
        assert arms["A"]&arms["B"]==arms["A"]&arms["C"]==arms["B"]&arms["C"]==core
        assert counts["A"]==counts["B"] and counts["A"]!=counts["C"] and origins["A"]==origins["B"]==origins["C"]
        assert len(arms["A"]-arms["B"])==len(arms["A"]-arms["C"])==m
        assert e["core_n"]==n-m and e["expected_minimum_support"]==(n+1)//2
        if n>b["n_min"]:assert e["added_core_worker"]==b["core_order"][n-m-1]
        ns[e["block_id"]].append(n);observed_nm[(e["target"],e["pool_id"])].add((m,n))
    assert used==req.keys()
    for bid,b in blocks.items():
        assert sorted(ns[bid])==list(range(b["n_min"],b["n_max"]+1))
        signature=(tuple(sorted((tuple(b["blocks"]["A"]),tuple(b["blocks"]["B"])))),tuple(b["blocks"]["C"]))
        group=(b["target"],b["pool_id"],b["m"]);assert signature not in seen[group];seen[group].add(signature)
    # Enumerate capacity afresh, including the twelve R pools with no possible m.
    potential=0;empty=[]
    for target,rule in spec["targets"].items():
        lm=labels[(rule["method_id"],"all")]
        for pid,p in pools.items():
            if p["meta"]["layer"]!="ordinary_manual" or p["meta"]["building"] not in spec["discovery_buildings"]+spec["assessment_buildings"]:continue
            rr=[r for r in p["records"] if r["worker_id"] in lm];N=len(rr)
            oc=Counter(r["origin"] for r in rr if lm[r["worker_id"]]==rule["outgoing"]);ic=Counter(r["origin"] for r in rr if lm[r["worker_id"]]==rule["incoming"])
            maxm=sum(min(oc[s]//2,ic[s]) for s in set(oc)|set(ic))
            expected={(m,n) for m in range(1,maxm+1) for n in range(max(2,m),N-2*m+1)}
            assert observed_nm[(target,pid)]==expected;potential+=len(expected)
            if not expected:empty.append(dict(target=target,pool_id=pid,N=N,outgoing=dict(oc),incoming=dict(ic)))
    # Repeated exact teams are counted once; no native results are loaded here.
    prior=set();priorfiles=[]
    for path in sorted((ROOT/"analysis/composition").glob("*REQUESTS.json.gz")):
        for r in fr.read(path).get("requests",[]):prior.add(fr.team_key(r["pool_id"],r["worker_ids"]))
        priorfiles.append(dict(path=str(path.relative_to(ROOT)),sha256=sha(path)))
    fpath=ROOT/"current_main_20261020/research/workers/personnel_composition_followup_20261019/REQUESTS.json.gz"
    followup=set()
    for e in fr.read(fpath)["events"]:
        for arm in "ABC":followup.add(fr.team_key(e["pool_id"],e[arm+"_workers"]))
    unique=set(actuals)
    result=dict(schema="independent_baseline_all_event_identity_audit_v1",passed=True,request_sha256=freeze["request_sha256"],events=len(events),requests=len(req),unique_team_keys=len(unique),independent_images=len({e["image"] for e in events}),independent_buildings=len({e["building"] for e in events}),workers=len(people),all_feasible_integer_target_pool_m_n_cells=potential,all_integer_cells_covered=True,source_matched_every_event=True,all_three_pairwise_intersections_equal_core=True,all_nested_core_chains_exact=True,distinct_unordered_block_draws_every_cell=True,zero_capacity_target_pools=empty,overlap_prior_composition_unique_teams=len(unique&prior),overlap_codex_followup_unique_teams=len(unique&followup),unique_teams_novel_vs_compared_manifests=len(unique-(prior|followup)),comparison_manifest_sources=priorfiles+[dict(path=str(fpath.relative_to(ROOT)),sha256=sha(fpath))],fusion_results_read=False,limitations=["Novelty check covers the explicitly listed prior composition/followup manifests only, not every historical single-person cache.","Distinct draws share workers and images; repeated teams/events are not independent images.","All feasible n,m are covered, not all member combinations or all source vectors."])
    (out/"DESIGN_AUDIT.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:v for k,v in result.items() if k not in ("comparison_manifest_sources","zero_capacity_target_pools")},ensure_ascii=False))


if __name__=="__main__":main()
