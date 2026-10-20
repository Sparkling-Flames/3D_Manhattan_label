"""Independent identity, aggregation and stratified native replay of Codex 451.

Reads the published frozen events/teams, never selects a new scientific rule.
Writes only this independent directory. Full 1353 fusion replay is not claimed.
"""
from __future__ import annotations
import os
for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_v] = "1"
import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
INPUT = ROOT / "current_main_20261020/research/workers/personnel_composition_followup_20261019"
SNAPSHOT = ROOT / "restored/work_personnel_typing_A_20261019/recovered/work_v2_20261019/fusion/INPUT_SNAPSHOT.json.gz"
sys.path.insert(0, str(ROOT / "analysis/composition"))
import fusion_runner as fr
import summarize_grid as sg
import pair_diagnostics as pdx


def read(path):
    with (gzip.open(path, "rt", encoding="utf-8-sig") if str(path).endswith(".gz") else Path(path).open(encoding="utf-8-sig")) as f:
        return json.load(f)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(pdx._clean(value), ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def equal(a, b, tolerance=1e-9):
    if a is None or (isinstance(a, float) and not np.isfinite(a)):
        return b is None or (isinstance(b, float) and not np.isfinite(b))
    if b is None or (isinstance(b, float) and not np.isfinite(b)):
        return False
    if isinstance(a, (bool, str)):
        return a == b
    return abs(float(a) - float(b)) <= tolerance


def hierarchical_mean(rows, field):
    # Explicit three-level equal weighting, independent of original pandas helper.
    pools = defaultdict(list)
    for row in rows:
        value = row.get(field)
        if value is not None and np.isfinite(float(value)):
            pools[(row["building"], row["pool_id"])].append(float(value))
    buildings = defaultdict(list)
    for (building, _), values in pools.items():
        buildings[building].append(float(np.mean(values)))
    return float(np.mean([np.mean(v) for v in buildings.values()])) if buildings else None


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--native", action="store_true"); ap.add_argument("--new-metrics", action="store_true")
    args = ap.parse_args(); started = time.monotonic()
    requests = read(INPUT / "REQUESTS.json.gz")["events"]
    teams = read(INPUT / "TEAMS.json.gz")
    original = pd.read_csv(INPUT / "EVENTS.csv.gz").set_index("event_id")
    pools = {p["pool_id"]: p for p in read(SNAPSHOT)["images"]}
    labels = sg.labels_from_files([ROOT / "analysis/reverse/worker_labels.csv.gz"])
    split = read(ROOT / "analysis/composition/SPLIT.json")
    source_paths = [INPUT/n for n in ["REQUESTS.json.gz", "TEAMS.json.gz", "EVENTS.csv.gz", "SUMMARY.csv", "PER_IMAGE.csv", "PER_BUILDING.csv", "CRITERION_COMPONENTS.csv", "REGISTRATION.json", "FIELD_CONTRACT.json"]] + [SNAPSHOT, Path(__file__), ROOT/"analysis/reverse/worker_labels.csv.gz", ROOT/"analysis/composition/summarize_grid.py"]
    source_hashes = {str(p.relative_to(ROOT)):sha(p) for p in source_paths}
    assert len(requests) == original.index.nunique() == len(original) == 451
    assert len(teams) == 1353
    assert {e["event_id"] for e in requests} == set(original.index)
    rows, mismatches, key_set, people = [], [], set(), set()
    original_cores, extra_cores = defaultdict(set), defaultdict(set)
    targets = read(INPUT/"REGISTRATION.json")["targets"]
    origin_modes = Counter(); score_status = Counter(); event_geometry_rows=[]; geometry_cache={}; previous_pid=None
    for e in requests:
        pid=e["pool_id"]; pool=pools[pid]; records={r["worker_id"]:r for r in pool["records"]}
        target=targets[e["target"]]; mapping=labels[(target["method"],"all")]
        assert e["k"]==target["k"] and e["m"]==target["m"] and pool["meta"]["layer"]=="ordinary_manual"
        assert pool["meta"]["building"] in split[e["historical_phase"]+"_buildings"]
        arms={x:set(e[x+"_workers"]) for x in "ABC"}; core=set(e["core_workers"])
        assert all(len(v)==e["k"] and len(e[x+"_workers"])==len(v) for x,v in arms.items())
        assert arms["A"]&arms["B"]==arms["A"]&arms["C"]==core and len(core)==e["k"]-e["m"]
        counts={x:Counter(mapping[w] for w in v) for x,v in arms.items()}
        assert counts["A"]==counts["B"] and counts["A"]!=counts["C"]
        for x,cls in [("A",target["outgoing"]),("B",target["outgoing"]),("C",target["incoming"])]:
            assert len(arms[x]-core)==e["m"] and {mapping[w] for w in arms[x]-core}=={cls}
        origins={x:Counter(records[w]["origin"] for w in v) for x,v in arms.items()}
        assert origins["A"]==origins["B"]==origins["C"]
        origin_modes[(e["target"],e["sample"],e.get("matching"),e.get("matched_origin"))]+=1
        row={k:e[k] for k in ("event_id","target","sample","historical_phase","pool_id","k","m")}
        row.update(image=pool["meta"]["image"],building=pool["meta"]["building"],difficulty=pool["meta"]["difficulty"],reference_id=pool["meta"]["reference_id"],core_workers="|".join(e["core_workers"]))
        ar={}
        for x,v in arms.items():
            key=fr.team_key(pid,sorted(v));assert key not in key_set
            if x+"_team_key" in e:assert key==e[x+"_team_key"]
            else:e[x+"_team_key"]=key  # Derived in memory only; extra-core requests store exact workers.
            key_set.add(key);people.update(v);t=teams[key];ar[x]=t
            assert set(t["member_workers"])==v and t["member_object_ids"]==[records[w]["object_id"] for w in sorted(v)]
            assert t["reference_id"]==pool["meta"]["reference_id"] and t["new_n"]==origins[x]["new"] and t["old_n"]==origins[x]["v1"]
            score_status[t["score_status"]]+=1;row[x+"_workers"]="|".join(e[x+"_workers"])
            for f in ("B8L2","D10","nodes","complete_evaluable","score_status","team_key","source_time_total_seconds"):
                row[x+"_"+f]=t.get(f)
        for name,x in [("within","B"),("cross","C")]:
            m=sg.pair_metrics(ar["A"],ar[x]);assert m["turnover"]==e["m"]
            fields=("turnover","abs_B8L2_change","floor_jaccard_difference","structure_bound_cyclic_deg","node_count_difference","mean_height_prism_pair_iou","joint_stable_strict","joint_stable_main","joint_stable_wide")
            for f in fields:row[name+"_"+f]=m[f]
            row[name+"_geometry_main"]=bool(m["both_complete"] and m["node_count_difference"]==0 and m["floor_jaccard_difference"] is not None and m["floor_jaccard_difference"]<=.05 and m["structure_bound_cyclic_deg"] is not None and m["structure_bound_cyclic_deg"]<=3)
            row[name+"_quality_main"]=bool(m["both_complete"] and m["abs_B8L2_change"] is not None and m["abs_B8L2_change"]<=2)
            if args.new_metrics:
                if previous_pid!=pid:geometry_cache.clear();previous_pid=pid
                z=pdx.pair_metrics(ar["A"],ar[x],cache=geometry_cache)
                event_geometry_rows.append(dict(event_id=e["event_id"],target=e["target"],sample=e["sample"],historical_phase=e["historical_phase"],pool_id=pid,building=pool["meta"]["building"],pair=name,**z))
        row["net_Q"]=(ar["C"]["B8L2"]-ar["B"]["B8L2"]) if ar["C"]["B8L2"] is not None and ar["B"]["B8L2"] is not None else None
        for f in original.columns:
            if f in row and not equal(row[f],original.loc[e["event_id"],f]):mismatches.append((e["event_id"],f,row[f],original.loc[e["event_id"],f]))
        group=e["target"],pid;c=tuple(sorted(core))
        if e["sample"]=="original_replay":original_cores[group].add(c)
        else:assert c not in extra_cores[group];extra_cores[group].add(c)
        rows.append(row)
    assert set(original_cores)==set(extra_cores)
    assert all(len(extra_cores[g])==3 and not extra_cores[g]&original_cores[g] for g in original_cores)
    assert not mismatches,mismatches[:3]
    # Check all saved per-image and per-building values, not just two headline rates.
    metrics=["net_Q","within_abs_B8L2_change","cross_abs_B8L2_change","within_floor_jaccard_difference","cross_floor_jaccard_difference"]+[f"{x}_joint_stable_{t}" for x in ("within","cross") for t in ("strict","main","wide")]
    keys=["target","sample","historical_phase"];D=pd.DataFrame(rows);aggregate=[];comparisons=[]
    for k,g in D.groupby(keys):
        group=g.to_dict("records");r=dict(zip(keys,k));values=g.net_Q.dropna()
        r.update(events=len(g),images=g.pool_id.nunique(),buildings=g.building.nunique(),scored_events=len(values),scored_images=g.loc[g.net_Q.notna(),"pool_id"].nunique(),improved_events=int((values>0).sum()),worsened_events=int((values<0).sum()),net_Q_event_p10=float(values.quantile(.1)) if len(values) else None)
        r.update({f:hierarchical_mean(group,f) for f in metrics+["within_geometry_main","cross_geometry_main","within_quality_main","cross_quality_main"]});aggregate.append(r)
    A=pd.DataFrame(aggregate)
    for filename,fields in [("SUMMARY.csv",keys),("CRITERION_COMPONENTS.csv",keys),("PER_IMAGE.csv",keys+["building","pool_id"]),("PER_BUILDING.csv",keys+["building"])]:
        saved=pd.read_csv(INPUT/filename)
        for r in saved.to_dict("records"):
            if filename in ("SUMMARY.csv","CRITERION_COMPONENTS.csv"):
                actual=next(x for x in aggregate if all(x[k]==r[k] for k in fields))
            else:
                group=[x for x in rows if all(x[k]==r[k] for k in fields)]
                actual={f:hierarchical_mean(group,f) for f in metrics}
            for f,v in r.items():
                if f not in fields:
                    assert equal(actual[f],v),(filename,fields,f,actual[f],v)
                    comparisons.append(abs(float(actual[f])-float(v)) if actual[f] is not None else 0.)
    A.to_csv(OUT/"FOLLOWUP_REAGGREGATED_SUMMARY.csv",index=False)
    if event_geometry_rows:pd.DataFrame(event_geometry_rows).to_csv(OUT/"FOLLOWUP_PARALLEL_METRICS.csv.gz",index=False,compression={"method":"gzip","mtime":0})
    # Register hash-stratified native teams before re-fusing, plus known failure status.
    chosen=[]
    for _,g in D.groupby(keys):
        chosen.append(min(g.event_id,key=lambda x:hashlib.sha256(("2026102001|"+x).encode()).hexdigest()))
    failed=D[~(D.A_complete_evaluable&D.B_complete_evaluable&D.C_complete_evaluable)]
    chosen+=sorted(set(failed.event_id)-set(chosen))[:2]
    event_lookup={e["event_id"]:e for e in requests}
    selected=[event_lookup[e] for e in chosen]
    save(OUT/"FOLLOWUP_NATIVE_SELECTION.json",dict(selection="one minimum salted event-ID hash from each of 8 target/sample/historical-phase strata, plus at most2 retained incomplete events",event_ids=chosen,teams=[{"event_id":e["event_id"],"arm":a,"pool_id":e["pool_id"],"team_key":e[a+"_team_key"],"workers":e[a+"_workers"]} for e in selected for a in "ABC"]))
    native=[]
    if args.native:
        fe=fr.init_engine(ROOT/"restored")
        with fe.cached_matching(),fe.scoring_engine(fe.ENGINE/"measurement_engine.zip",fe.ENGINE/"working_models.py") as (engine,models):
            for e in selected:
                for a in "ABC":
                    expected=teams[e[a+"_team_key"]];actual=fr.evaluate_one(pools[e["pool_id"]],e[a+"_workers"],engine,models)
                    fields=["team_key","member_workers","member_object_ids","nodes","complete_evaluable","complete_floor_evaluable","score_status"]
                    exact=all(actual[k]==expected[k] for k in fields)
                    deltas={k:(actual[k]-expected[k]) if actual[k] is not None and expected[k] is not None else None for k in ["B8L2","D10","IoU3D100"]}
                    numeric=all(equal(actual[k],expected[k]) for k in ["B8L2","D10","IoU3D100"])
                    geo=[]
                    for field in ("points","footprint"):
                        av=(actual.get("geometry") or {}).get(field);bv=(expected.get("geometry") or {}).get(field)
                        if av is None or bv is None:geo.append(dict(field=field,available=av is not None,exact=av==bv,max_abs_difference=None))
                        else:
                            aa,bb=np.asarray(av,float),np.asarray(bv,float);diff=float(np.max(np.abs(aa-bb))) if aa.shape==bb.shape else None
                            geo.append(dict(field=field,available=True,exact=av==bv,max_abs_difference=diff))
                    passed=exact and numeric and all(v["exact"] or (v["max_abs_difference"] is not None and v["max_abs_difference"]<1e-9) for v in geo)
                    native.append(dict(event_id=e["event_id"],arm=a,pool_id=e["pool_id"],team_key=expected["team_key"],score_status=expected["score_status"],metadata_exact=exact,score_deltas=deltas,geometry=geo,passed=passed))
                    assert passed,native[-1]
    result=dict(schema="independent_codex_followup_reaggregation_v1",all_passed=not mismatches and all(n["passed"] for n in native),events=len(rows),unique_actual_teams=len(key_set),images=D.image.nunique(),pools=D.pool_id.nunique(),buildings=D.building.nunique(),workers=len(people),original_events=int(D["sample"].eq("original_replay").sum()),additional_events=int(D["sample"].eq("additional_background").sum()),original_supported_target_pools=len(original_cores),all_extra_target_pools_have_3_new_distinct_cores=True,all_same_background_actual_m_source_class_invariants=True,score_status_counts=score_status,event_field_mismatches=mismatches,aggregate_cells_compared=len(comparisons),aggregate_max_abs_difference=max(comparisons),native_replay_executed=args.native,native_replay_teams=len(native),native_results=native,native_distinct_images=len({pools[n["pool_id"]]["meta"]["image"] for n in native}),native_distinct_buildings=len({pools[n["pool_id"]]["meta"]["building"] for n in native}),new_metric_pairs=len(event_geometry_rows),source_sha256=source_hashes,all_sources_unchanged=all(sha(ROOT/p)==v for p,v in source_hashes.items()),elapsed_seconds=time.monotonic()-started,interpretation="Already explored v2; additional shared backgrounds in the same previously supported images. 451 old pairs remeasured from retained geometries; only the explicitly listed native subset is independently re-fused here.")
    save(OUT/"FOLLOWUP_REAGGREGATION_AUDIT.json",result)
    print(json.dumps({k:result[k] for k in ["all_passed","events","unique_actual_teams","images","buildings","workers","aggregate_max_abs_difference","native_replay_teams","elapsed_seconds"]}))


if __name__=="__main__":main()
