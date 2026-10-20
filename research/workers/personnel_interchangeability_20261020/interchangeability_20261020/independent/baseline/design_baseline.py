"""Metadata-only, deterministic n/m/core study of two previously known directions.

This generator does not read any fusion result. All writes stay under --out.
Every feasible integer m and n is covered by at least one disjoint block draw;
a metadata-stratified allocation of second draws respects the request budget.
"""
from __future__ import annotations
import os
for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_v] = "1"
import argparse
from collections import Counter, defaultdict, deque
import gzip
import hashlib
import json
import math
from pathlib import Path
import random
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "analysis/composition"))
import fusion_runner as fr
import summarize_grid as sg

SEED = 2026102007
TARGETS = {
    "G": {"method_id": "R_geo9_source_signed_p2_K2", "outgoing": "C02", "incoming": "C01"},
    "R": {"method_id": "R_role_ward_K5", "outgoing": "C05", "incoming": "C02"},
}
SOURCES = ("new", "v1")
SNAPSHOT = ROOT / "restored/work_personnel_typing_A_20261019/recovered/work_v2_20261019/fusion/INPUT_SNAPSHOT.json.gz"
LABELS = ROOT / "analysis/reverse/worker_labels.csv.gz"
SPLIT = ROOT / "analysis/composition/SPLIT.json"
FEATURES = ROOT / "analysis/forward/results/features_train.csv.gz"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def rank(*keys):
    return hashlib.sha256(json.dumps([SEED, *keys], ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def rng(*keys):
    return random.Random(int(rank(*keys)[:16], 16))


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n")


def save_csv(path, rows):
    # Write one fully closed, verified gzip member. Streaming CSV-to-gzip writes
    # were observed truncated after process completion on the execution mount.
    raw=pd.DataFrame(rows).to_csv(index=False).encode("utf-8")
    packed=gzip.compress(raw,compresslevel=6,mtime=0) if path.suffix==".gz" else raw
    temp=path.with_name(path.name+".tmp")
    with temp.open("wb") as f:
        assert f.write(packed)==len(packed)
        f.flush();os.fsync(f.fileno())
    assert temp.read_bytes()==packed
    temp.replace(path)
    reread=path.read_bytes()
    assert reread==packed
    assert (gzip.decompress(reread) if path.suffix==".gz" else reread)==raw


def cstr(counts):
    return "|".join(f"{k}:{v}" for k, v in sorted(counts.items()))


def finite_mean(workers, features, field):
    vals = [features[w][field] for w in workers if w in features and pd.notna(features[w].get(field))]
    return sum(vals) / len(vals) if vals else None


def census(pools, maps, split):
    cells, pool_rows = [], []
    for target, rule in TARGETS.items():
        labels = maps[(rule["method_id"], "all")]
        assert len(labels) == 55
        for pool in sorted(pools.values(), key=lambda x: x["pool_id"]):
            meta = pool["meta"]
            phase = next((p for p in ("discovery", "validation") if meta["building"] in split[p + "_buildings"]), None)
            if phase is None or meta["layer"] != "ordinary_manual":
                continue
            rec = {r["worker_id"]: r for r in pool["records"] if r["worker_id"] in labels}
            assert all(r["origin"] in SOURCES for r in rec.values())
            out = {s: sorted(w for w in rec if labels[w] == rule["outgoing"] and rec[w]["origin"] == s) for s in SOURCES}
            inc = {s: sorted(w for w in rec if labels[w] == rule["incoming"] and rec[w]["origin"] == s) for s in SOURCES}
            cap = {s: min(len(out[s]) // 2, len(inc[s])) for s in SOURCES}
            max_m = sum(cap.values()); N = len(rec)
            base = dict(target=target, pool_id=pool["pool_id"], historical_phase=phase, image=meta["image"], building=meta["building"], difficulty=meta["difficulty"], eligible_n=N, inventory_pool_n=len(pool["records"]), excluded_unknown_n=len(pool["records"])-N, max_m=max_m, outgoing_new_n=len(out["new"]), outgoing_v1_n=len(out["v1"]), incoming_new_n=len(inc["new"]), incoming_v1_n=len(inc["v1"]))
            pool_rows.append(base)
            for m in range(1, max_m + 1):
                vectors = [{"new": x, "v1": m-x} for x in range(m+1) if x <= cap["new"] and m-x <= cap["v1"]]
                n0, n1 = max(2, m), N-2*m
                assert n1 >= n0 and vectors
                # Unordered A/B blocks (C is the distinct incoming class).
                possibilities = sum(math.prod(math.comb(len(out[s]), v[s]) * math.comb(len(out[s])-v[s], v[s]) * math.comb(len(inc[s]), v[s]) for s in SOURCES) // 2 for v in vectors)
                assert possibilities >= 1
                cells.append(dict(base, m=m, n_min=n0, n_max=n1, n_count=n1-n0+1, request_cost_per_draw=3*(n1-n0+1), feasible_source_vectors=vectors, block_partition_possibilities=str(possibilities), max_distinct_draws=min(2, possibilities), outgoing_by_source=out, incoming_by_source=inc))
    return cells, pool_rows


def allocate(cells, budget):
    selected = {(c["target"], c["pool_id"], c["m"]): 1 for c in cells}
    base_cost = sum(c["request_cost_per_draw"] for c in cells)
    assert base_cost <= budget, "Budget cannot cover every n,m even once"
    used = base_cost
    # Preserve both draws for the rarer R direction (only six outgoing members).
    for c in cells:
        if c["target"] == "R" and c["max_distinct_draws"] == 2:
            selected[(c["target"], c["pool_id"], c["m"])] = 2
            used += c["request_cost_per_draw"]
    assert used <= budget, "Budget too small for predeclared two-draw R priority"
    groups = defaultdict(list)
    for c in cells:
        if c["target"] == "G" and c["max_distinct_draws"] == 2:
            key = (c["m"], c["historical_phase"], c["building"], c["difficulty"])
            groups[key].append(c)
    queues = {k: deque(sorted(v, key=lambda c: rank("second", c["target"], c["pool_id"], c["m"]))) for k, v in groups.items()}
    strata = sorted(queues, key=lambda k: rank("stratum", *k))
    while any(queues.values()):
        for k in strata:
            if not queues[k]:
                continue
            c = queues[k].popleft()
            if used + c["request_cost_per_draw"] <= budget:
                selected[(c["target"], c["pool_id"], c["m"])] = 2
                used += c["request_cost_per_draw"]
    return selected, used


def build_blocks(c, draw_count, pool, labels):
    seen = set(); blocks = []
    vectors = sorted(c["feasible_source_vectors"], key=lambda v: rank("source_vector", c["target"], c["pool_id"], c["m"], v))
    eligible = sorted(r["worker_id"] for r in pool["records"] if r["worker_id"] in labels)
    for draw in range(draw_count):
        for attempt in range(10000):
            v = vectors[(draw + attempt) % len(vectors)]
            rr = rng("blocks", c["target"], c["pool_id"], c["m"], draw, attempt)
            arms = {a: [] for a in "ABC"}
            for source in SOURCES:
                both = rr.sample(c["outgoing_by_source"][source], 2*v[source])
                arms["A"] += both[:v[source]]; arms["B"] += both[v[source]:]
                arms["C"] += rr.sample(c["incoming_by_source"][source], v[source])
            arms = {a: sorted(w) for a, w in arms.items()}
            signature = (tuple(sorted((tuple(arms["A"]), tuple(arms["B"])))), tuple(arms["C"]))
            if signature not in seen:
                seen.add(signature)
                break
        else:
            raise RuntimeError("Did not obtain requested distinct block draw: " + repr(c))
        removed = set(sum(arms.values(), []))
        assert len(removed) == 3*c["m"]
        core = [w for w in eligible if w not in removed]
        rng("core_order", c["target"], c["pool_id"], c["m"], draw).shuffle(core)
        block_id = "base_" + rank("block_id", c["target"], c["pool_id"], c["m"], draw)[:20]
        blocks.append(dict(block_id=block_id, target=c["target"], pool_id=c["pool_id"], m=c["m"], draw=draw, block_source_counts=v, blocks=arms, core_order=core, n_min=c["n_min"], n_max=c["n_max"], core_order_kind="seeded_uniform_random_permutation", block_sample_attempt=attempt))
    return blocks


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", type=Path, default=Path(__file__).parent); ap.add_argument("--budget", type=int, default=100000)
    args = ap.parse_args(); out = args.out.resolve(); out.mkdir(parents=True, exist_ok=True)
    pools = {p["pool_id"]: p for p in fr.read(SNAPSHOT)["images"]}
    maps = sg.labels_from_files([LABELS]); split = fr.read(SPLIT)
    features = pd.read_csv(FEATURES).set_index("worker_id").to_dict("index")
    cells, pool_rows = census(pools, maps, split)
    selected, budget_used = allocate(cells, args.budget)
    source_paths = [SNAPSHOT, LABELS, SPLIT, FEATURES, Path(__file__), ROOT/"analysis/composition/fusion_runner.py", ROOT/"analysis/composition/summarize_grid.py", ROOT/"interchangeability_20261020/independent/pair_diagnostics.py", ROOT/"interchangeability_20261020/independent/METRIC_CONTRACT.json"]
    spec = dict(schema="known_direction_all_integer_n_m_nested_core_v1", seed=SEED, current_main_commit="445686f8f3cf6039c4ce1f60016cad1d26829044", native_science_commit="82c6164b0d4630de5316199c92aa405930973168", targets=TARGETS, domain="all/global_known55", layer="ordinary_manual", discovery_buildings=split["discovery_buildings"], assessment_buildings=split["validation_buildings"], historical_phase_names_preserved=True,
        interpretation="Previously selected G and R directions, reused and repeatedly explored v2. All these non-history buildings are assessment strata, not new external blind images or people. History10 features/labels frozen unchanged.",
        source_capacity="For each source s, outgoing A and B each require v_s, incoming C requires v_s; v_s<=min(floor(out_s/2),in_s), sum(v_s)=m. Blocks A,B,C disjoint, common core excludes all three.",
        integer_coverage="All m=1..sum(source capacities); all n=max(2,m)..N-2m. Two-person and other non-evaluable attempts retained.",
        draw_allocation="All cells one draw; R two distinct unordered(A,B),C block partitions when possible; remaining budget goes to G second draws by salted-hash round-robin strata (m,historical phase,building,difficulty). Feasible source vectors in salted-hash order, draws cycle vectors. Identity samples seeded, reject duplicate block partition. No result is read.",
        core_order="One seeded random permutation of remaining eligible members for each fixed draw. Every n uses its first n-m members. n changes membership and composition as well as vote threshold; not pure causal effect of head count.",
        team_request_budget=args.budget, allocated_request_rows=budget_used, shape_selection="Metadata only: n_min/n_max, n in {2m-1,2m,2m+1}, and event salted hash modulo 11 equals 0. Every selected event computes both A-B and A-C new metrics. Other events retain all original strict/main/wide and no-Q criteria. Adjacent n geometry diagnostics are allowed only when both endpoints are in the registered subset.",
        primary_analysis="All attempted events: within A-B versus cross A-C, and signed C-B B8L2/D10; stable flags use failures=False, continuous missing stays null. Equal weight draws within image, images within building, buildings within stratum. Every target,n,m; source-vector and historical-phase/difficulty/core-proportion conditions retained.",
        prespecified_sensitivities={"Q":"Overall utility first; then historical block Q(C)-Q(B) continuous linear adjustment plus |gap|<=2 support subset. Historical q_beta only, no target-building Q feature. This does not identify independent causal class effects when class and people confound.", "source":"A/B/C exact source-count match; separate all-new/all-v1/mixed blocks and source proportions where feasible.", "person":"Leave each actual worker out of all events containing them, and separately leave each block worker out; report remaining buildings/images/events, not a new intervention.", "core_proportions":"core incoming-class fraction bins [0,.25),[.25,.5),[.5,.75),[.75,1], plus empty core separately; total replacement fraction m/n; report support.", "threshold":"Adjacent fixed-block nested-core steps; ceil(n/2) and added-member identity/class/source recorded. Node supports are observation identities, not necessary-structure semantics.", "low_tail":"Signed C-B quality p10 and finite negative/positive counts; complete/evaluable and failure states for every arm; no zero imputation."},
        omissions=["All exact member sets are not enumerated: one or two block draws per pool,m only.", "Not all feasible source allocations are sampled if more than the allocated draws.", "No enriched core order under this request budget; random-order nested chains only.", "Unknown reverse-label workers are excluded from class experiments, not assigned a low class.", "No doorways/Semi/special pools in this known global ordinary-Manual baseline; those belong to separate condition studies."],
        source_sha256={str(p.relative_to(ROOT)): sha(p) for p in source_paths})
    save_json(out/"BASELINE_SPEC.json", spec); spec_hash = sha(out/"BASELINE_SPEC.json")
    blocks, requests, events, ledger = [], [], [], []
    for c in cells:
        target = c["target"]; rule=TARGETS[target]; pool=pools[c["pool_id"]]
        labels=maps[(rule["method_id"],"all")]; rec={r["worker_id"]:r for r in pool["records"]}
        draw_count=selected[(target,c["pool_id"],c["m"])]; bs=build_blocks(c,draw_count,pool,labels); blocks+=bs
        ledger.append({k:v for k,v in c.items() if k not in ("outgoing_by_source","incoming_by_source","feasible_source_vectors")} | dict(draws=draw_count, second_draw_status="selected" if draw_count==2 else "finite_partition_limit" if c["max_distinct_draws"]==1 else "budget_not_selected", feasible_source_vector_n=len(c["feasible_source_vectors"]), feasible_source_vectors=json.dumps(c["feasible_source_vectors"],sort_keys=True), sampled_source_vectors=json.dumps([b["block_source_counts"] for b in bs],sort_keys=True)))
        classes=sorted(set(labels.values()))
        for b in bs:
            for n in range(c["n_min"],c["n_max"]+1):
                core=b["core_order"][:n-c["m"]]; eid=b["block_id"]+f"__n{n:02d}"
                reasons=[]
                if n in (c["n_min"],c["n_max"]):reasons.append("range_endpoint")
                if n in (2*c["m"]-1,2*c["m"],2*c["m"]+1):reasons.append("n_near_2m")
                if int(rank("shape_subset",eid)[:16],16)%11==0:reasons.append("hash_1_of_11")
                cc=Counter(labels[w] for w in core); co=Counter(rec[w]["origin"] for w in core)
                added=core[-1] if core else None
                e=dict(event_id=eid, block_id=b["block_id"], target=target, method_id=rule["method_id"], domain="all", historical_phase=c["historical_phase"], pool_id=c["pool_id"], image=c["image"], building=c["building"], difficulty=c["difficulty"], k=n, m=c["m"], draw=b["draw"], eligible_n=c["eligible_n"], reference_id=pool["meta"]["reference_id"], core_n=len(core), core_counts=cstr(cc), core_outgoing_n=cc[rule["outgoing"]], core_incoming_n=cc[rule["incoming"]], core_other_n=len(core)-cc[rule["outgoing"]]-cc[rule["incoming"]], core_new_n=co["new"], core_v1_n=co["v1"], block_new_n=b["block_source_counts"]["new"], block_v1_n=b["block_source_counts"]["v1"], replace_fraction=c["m"]/n, core_incoming_fraction=cc[rule["incoming"]]/len(core) if core else None, expected_minimum_support=(n+1)//2, added_core_worker=added if n>c["n_min"] else None, added_core_class=labels[added] if added is not None and n>c["n_min"] else None, added_core_source=rec[added]["origin"] if added is not None and n>c["n_min"] else None, shape_registered=bool(reasons), shape_selection_reason="|".join(reasons), core_history_q_beta=finite_mean(core,features,"q_beta"))
                for arm in "ABC":
                    workers=sorted(core+b["blocks"][arm]); cnt=Counter(labels[w] for w in workers); counts={cl:cnt[cl] for cl in classes}; key=fr.team_key(c["pool_id"],workers)
                    e[arm+"_team_key"]=key; e[arm+"_counts"]=cstr(counts)
                    e[arm+"_block_history_q_beta"]=finite_mean(b["blocks"][arm],features,"q_beta")
                    e[arm+"_block_history_bottom_y_effect"]=finite_mean(b["blocks"][arm],features,"bottom_y_effect")
                    e[arm+"_block_history_pair_count_effect"]=finite_mean(b["blocks"][arm],features,"pair_count_effect")
                    requests.append(dict(request_id=eid+"__"+arm,event_id=eid,arm=arm,pool_id=c["pool_id"],k=n,worker_ids=workers,team_key=key,method_id=rule["method_id"],domain="all",counts=counts,phase="baseline_reused_v2"))
                events.append(e)
    assert len(requests)==budget_used and len({r["request_id"] for r in requests})==len(requests)
    assert all(sha(ROOT/p)==v for p,v in spec["source_sha256"].items())
    fr.write(out/"REQUESTS.json.gz",dict(schema=spec["schema"],spec_sha256=spec_hash,requests=requests,blocks=blocks))
    save_csv(out/"EVENT_DESIGN.csv.gz",events)
    save_csv(out/"SEARCH_LEDGER.csv",ledger)
    save_csv(out/"POOL_CAPACITY.csv",pool_rows)
    unique={r["team_key"] for r in requests}; ev=pd.DataFrame(events)
    receipt=dict(schema=spec["schema"],spec_sha256=spec_hash,request_sha256=sha(out/"REQUESTS.json.gz"),event_design_sha256=sha(out/"EVENT_DESIGN.csv.gz"),ledger_sha256=sha(out/"SEARCH_LEDGER.csv"),pool_capacity_sha256=sha(out/"POOL_CAPACITY.csv"),request_rows=len(requests),distinct_team_keys=len(unique),events=len(events),fixed_block_chains=len(blocks),pool_method_m_cells=len(cells),single_draw_cells=sum(n==1 for n in selected.values()),two_draw_cells=sum(n==2 for n in selected.values()),pools=ev.pool_id.nunique(),images=ev.image.nunique(),buildings=ev.building.nunique(),workers=len({w for r in requests for w in r["worker_ids"]}),shape_registered_events=int(ev.shape_registered.sum()),by_target={k:dict(events=len(g),pools=g.pool_id.nunique(),buildings=g.building.nunique(),min_n=int(g.k.min()),max_n=int(g.k.max()),min_m=int(g.m.min()),max_m=int(g.m.max()),shape_events=int(g.shape_registered.sum())) for k,g in ev.groupby("target")},member_reconstruction_digest=fr.digest([{k:r[k] for k in ("request_id","pool_id","k","worker_ids","counts","team_key")} for r in requests]),fusion_results_read=False)
    save_json(out/"DESIGN_FREEZE.json",receipt)
    print(json.dumps(receipt,ensure_ascii=False))


if __name__=="__main__":main()
