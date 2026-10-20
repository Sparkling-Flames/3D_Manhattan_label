"""Freeze a metadata-only subset of nested steps for identity-vote diagnostics."""
from collections import defaultdict
import hashlib,json
from pathlib import Path
import pandas as pd
import design_baseline as d


def main():
    out=Path(__file__).parent;E=pd.read_csv(out/"EVENT_DESIGN.csv.gz")
    B=d.fr.read(out/"REQUESTS.json.gz")["blocks"];lookup={b["block_id"]:b for b in B}
    # One hash-ranked block chain per target/building/m/difficulty. No outcome,
    # reference geometry, current annotation clustering or fitted score is read.
    first=E.groupby("block_id",sort=False).first().reset_index();chosen=[]
    for keys,g in first.groupby(["target","building","m","difficulty"]):
        bid=min(g.block_id,key=lambda x:d.rank("mechanism_chain",x));b=lookup[bid]
        possible=list(range(b["n_min"],b["n_max"]))
        starts=[n for n in (2*b["m"]-1,2*b["m"]) if n in possible]
        if not starts:
            for parity in (0,1):
                xs=[n for n in possible if n%2==parity]
                if xs:starts.append(xs[0])
        for n in sorted(set(starts)):
            chosen.append(dict(block_id=bid,target=keys[0],building=keys[1],m=int(keys[2]),difficulty=keys[3],pool_id=b["pool_id"],n_before=n,n_after=n+1,event_before=bid+f"__n{n:02d}",event_after=bid+f"__n{n+1:02d}",added_worker=b["core_order"][n+1-b["m"]-1]))
    spec=dict(schema="known_baseline_nested_vote_metadata_subset_v1",seed=d.SEED,baseline_request_sha256=d.sha(out/"REQUESTS.json.gz"),selector_sha256=d.sha(Path(__file__)),selection="One minimum salted-hash block chain per target/building/m/difficulty. Adjacent n=2m-1→2m and 2m→2m+1 when feasible; if neither, first available increase and nonincrease of ceil(n/2). Three arms at each step. Chosen solely from block identities/ranges/difficulty; no native result read.",no_results_read=True,steps=chosen,selected_step_n=len(chosen),unique_chains=len({x["block_id"] for x in chosen}),unique_endpoint_events=len({x[k] for x in chosen for k in ("event_before","event_after")}),supplementary_geometry="Run frozen geometry_metrics on these registered adjacent endpoint pairs; no legacy same-k stability criterion is defined across n.",mechanism_limits="Membership/class proportions also change at every step. Only unchanged old-observation partitions allow the selected/unselected vote bookkeeping interpretation; no assertion of semantic necessity. Every stored native transition field kept.")
    d.save_json(out/"MECHANISM_SPEC.json",spec)
    print(json.dumps({k:v for k,v in spec.items() if k not in ("steps",)},ensure_ascii=False))


if __name__=="__main__":main()
