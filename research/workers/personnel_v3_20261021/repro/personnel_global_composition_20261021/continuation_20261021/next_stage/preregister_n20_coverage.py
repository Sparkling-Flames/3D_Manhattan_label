"""Exact metadata-only coverage implied by the frozen n=20 requests.

This is registration coverage, never a declaration that pending endpoints
have been computed. The completed ledger is published by finalize_n20_coverage.
"""
from __future__ import annotations
import collections,gzip,sys,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
STUDY=HERE.parents[1]
OUT=HERE/'coverage'
sys.path[:0]=[str(HERE),str(STUDY/'composition')]
import global_study as gs
from prepare_n20_design import atomic_frame


def main():
    oldreq=gs.read(STUDY/'composition/ENDPOINT_REQUESTS.json.gz')['requests']
    target=gs.read(HERE/'candidate_n20/ENDPOINT_REQUESTS.json.gz')['requests']
    allreq={r['team_key']:r for r in oldreq};allreq.update({r['team_key']:r for r in target})
    by=collections.defaultdict(list)
    for r in allreq.values():
        if len(r['member_workers'])==20:by[r['pool_id']].append(r)
    universe=gs.pd.read_csv(STUDY/'composition/UNIVERSE_FINAL_COVERAGE.csv.gz',dtype=str)
    maps=gs.method_maps();rows=[]
    for _,r in universe[universe.n=='20'].iterrows():
        mapping=maps[(r.method_id,r.tier,r.condition,r.building)]
        cap={c:int(n) for c,n in (x.split(':') for x in r.class_capacities.split('|'))}
        compositions=set();nsets=0
        for q in by[r.pool_id]:
            if not set(q['member_workers'])<=mapping.keys():continue
            counts=collections.Counter(mapping[w] for w in q['member_workers'])
            compositions.add(gs.canonical_counts({c:counts.get(c,0) for c in cap}));nsets+=1
        previous=int(r.computed_class_vectors);allvec=int(r.all_feasible_class_vectors)
        if len(compositions)<previous or len(compositions)>allvec:raise ValueError('Invalid vector extension')
        rows.append(dict(pool_id=r.pool_id,method_id=r.method_id,tier=r.tier,condition=r.condition,
             image=r.image,building=r.building,layer=r.layer,n=20,
             all_feasible_class_vectors=allvec,previous_computed_class_vectors=previous,
             frozen_requested_class_vectors=len(compositions),additional_requested_class_vectors=len(compositions)-previous,
             previous_computed_actual_member_sets=int(r.computed_actual_member_sets),
             frozen_requested_actual_member_sets=nsets,
             remaining_unrequested_class_vectors=allvec-len(compositions),
             full_vector_coverage_registered=len(compositions)==allvec))
    frame=gs.pd.DataFrame(rows)
    atomic_frame(OUT/'N20_REGISTERED_GLOBAL_COVERAGE.csv',frame,('pool_id','method_id','tier'))
    old_vectors=sum(map(int,universe.computed_class_vectors));added=sum(frame.additional_requested_class_vectors)
    total=sum(map(int,universe.all_feasible_class_vectors))
    history=set(gzip.open(STUDY/'composition/HISTORICAL_TEAM_KEYS.txt.gz','rt').read().splitlines())
    receipt=dict(status='registered_metadata_only_computation_pending',
       old_endpoint_sets=len(oldreq),combined_requested_endpoint_sets=len(allreq),
       new_actual_member_sets=len(allreq)-len(oldreq),
       combined_new_against_recovered_history=len(set(allreq)-history),
       historical_geometry_restorations=len(set(allreq)&history),
       all_method_all_n_class_vector_universe=total,previous_computed_vectors=old_vectors,
       additional_requested_vectors_all_eligible_methods=int(added),
       frozen_registered_vectors_all_methods=old_vectors+int(added),
       remaining_unregistered_vectors=total-old_vectors-int(added),
       selected_six_method_n20_vectors=48321,selected_newly_touched_n20_vectors=42168,
       source_selection_uses_outcomes=False,counts_are_not_completed_endpoint_claims=True)
    gs.save(OUT/'REGISTERED_COVERAGE_RECEIPT.json',receipt)
    print(json.dumps(receipt,ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':main()
