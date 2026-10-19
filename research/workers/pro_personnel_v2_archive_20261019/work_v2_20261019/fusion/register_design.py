"""Freeze actual memberships before observing fusion outputs."""
from __future__ import annotations
from collections import Counter
from itertools import combinations
import math
import numpy as np
from pool_io import OUT,COMMIT,SOURCE,load_pools,save,save_gz,sha,digest

SEED=2026101901
RANDOM_K=(4,8,12,16,24,32)
REPLACEMENT_K=(8,12,16,24)
PATHS=4
RANDOM_TEAMS=12
BACKGROUNDS=2

def rng_for(*args):return np.random.default_rng(int(digest([SEED,*args])[:16],16))
def sample_subsets(workers,k,n,rng):
    total=math.comb(len(workers),k)
    if total<=n:return list(combinations(workers,k))
    values=set()
    while len(values)<n:values.add(tuple(sorted(rng.choice(workers,k,replace=False).tolist())))
    return sorted(values)
def main():
    pools=load_pools();requests=[];paths=[];backgrounds=[]
    for p in pools:
        pid=p['pool_id'];ws=sorted(r['worker_id'] for r in p['records']);n=len(ws)
        for draw in range(PATHS):
            rng=rng_for('uniform_order',pid,draw);order=rng.permutation(ws).tolist();ids=[]
            for k in range(1,n+1):
                rid=f'{pid}__prefix{draw}__k{k}';ids.append(rid)
                requests.append(dict(request_id=rid,pool_id=pid,request_family='uniform_prefix',
                    strategy='uniform_random_order',draw_id=draw,path_id=f'{pid}__path{draw}',k=k,
                    added_worker=order[k-1],worker_ids=order[:k]))
            paths.append(dict(path_id=f'{pid}__path{draw}',pool_id=pid,draw_id=draw,worker_order=order,request_ids=ids))
        for k in RANDOM_K:
            if n<k:continue
            samples=sample_subsets(ws,k,RANDOM_TEAMS,rng_for('independent_team',pid,k))
            for draw,team in enumerate(samples):
                requests.append(dict(request_id=f'{pid}__random_k{k}__draw{draw}',pool_id=pid,
                    request_family='independent_random_team',strategy='uniform_random_team',draw_id=draw,k=k,worker_ids=list(team)))
        for k in REPLACEMENT_K:
            if n<k+1:continue
            samples=sample_subsets(ws,k-1,BACKGROUNDS,rng_for('fixed_background',pid,k))
            for draw,bg in enumerate(samples):
                entrants=sorted(set(ws)-set(bg));ids=[];bid=f'{pid}__background_k{k}_{draw}'
                for entrant in entrants:
                    rid=bid+'__in_'+entrant;ids.append(rid)
                    requests.append(dict(request_id=rid,pool_id=pid,request_family='fixed_background',
                        strategy='uniform_background_all_remaining_entrants',draw_id=draw,k=k,background_id=bid,
                        entrant_worker_id=entrant,background_worker_ids=list(bg),worker_ids=[*bg,entrant]))
                backgrounds.append(dict(background_id=bid,pool_id=pid,k=k,draw_id=draw,background_worker_ids=list(bg),
                    entrants=entrants,request_ids=ids))
    assert len({r['request_id'] for r in requests})==len(requests)
    unique={(r['pool_id'],tuple(sorted(r['worker_ids']))) for r in requests}
    # Pilot choice depends only on frozen metadata and keyed random order, never team outcomes.
    pilot=[];seen_buildings=set()
    for difficulty in ('简单','中等','困难'):
        candidates=[p for p in pools if p['meta']['layer']=='ordinary_manual' and p['meta']['difficulty']==difficulty]
        candidates.sort(key=lambda p:digest([SEED,'pilot',p['pool_id']]))
        chosen=0
        for p in candidates:
            if p['meta']['building'] in seen_buildings:continue
            pilot.append(p['pool_id']);seen_buildings.add(p['meta']['building']);chosen+=1
            if chosen==3:break
    for layer in ('doorway_manual','ordinary_semi'):
        candidates=sorted((p for p in pools if p['meta']['layer']==layer),key=lambda p:digest([SEED,'pilot',p['pool_id']]))
        pilot.extend(p['pool_id'] for p in candidates[:2])
    code_paths=['tools/thesis_main/analysis/'+f for f in (
        'consensus_delivery_20261008.py','ring_correspondence_20261007.py','wall_consensus_population_20261014.py',
        'wall_consensus_quality_20261015.py','wall_consensus_v1_process_20261017.py','quality_b8l2_d10_20261017.py',
        'scope_quality_scoring_20261016.py','research_round_20260929.py','paired_split_research/study.py')]
    code_paths+=['research/statistics/b8l2_shared_v6_20261016/inputs/measurement_engine.zip',
                 'research/statistics/b8l2_shared_v6_20261016/inputs/working_models.py']
    design=dict(schema='v2_fusion_registered_design_v1',git_commit=COMMIT,seed=SEED,
        input_snapshot_sha256=sha(OUT/'INPUT_SNAPSHOT.json.gz'),seed_derivation='sha256(canonicalJSON([seed, family, pool, k/draw])) first16 hex → numpy.default_rng',
        pool_scope='All 229 same-image/condition/reference/version pools with 7302 quality-eligible independent real answers. Ordinary Manual 177 pools is primary. Doorway/Semi/special separate.',
        k_random=list(RANDOM_K),k_replacement=list(REPLACEMENT_K),uniform_full_permutations=PATHS,random_teams_per_k=RANDOM_TEAMS,
        fixed_backgrounds_per_k=BACKGROUNDS,entrants='all remaining real workers for each fixed k-1 background',
        small_pool_sampling='enumerate all subsets when number <= requested count; otherwise sample unique uniform subsets without replacement',
        n_requests=len(requests),n_unique_teams=len(unique),families=dict(Counter(r['request_family'] for r in requests)),
        n_paths=len(paths),n_backgrounds=len(backgrounds),n_all_entrant_pairs=sum(math.comb(len(b['entrants']),2) for b in backgrounds),
        pilot_pool_ids=pilot,pilot_selection='3 distinct-building ordinary pools per difficulty, keyed hash order, then 2 doorway and 2 Semi; all chosen before outcomes',
        expansion='Run this frozen design on pilot, then remaining pools if input and runtime checks pass. Outcomes cannot change seeds, categories, parameters or sample counts.',
        frozen_fusion=dict(entry='consensus_delivery_20261008.fuse',core='ring_correspondence_20261007.build',gap_per_skip_degree=7.5,
            correspondence='mean top/bottom angular distance, cyclic and reverse cuts with skip DP, one person per identity group',
            group_rule='complete linkage of allowed pairwise node matches (NOT whole-answer 9/12 degree clustering)',
            votes='MV50 inclusive: 2*support>=N',coordinates='all identity members, equal-person medians, periodic medoid anchor',
            connection='most-supported complete projected source ring; ties lexical flagged; no x-sort fallback or human partitions',
            N2='node evidence retained, source-ring sorting deferred',N1=False,source_points='frozen records final points, no extra prepare_record'),
        practical_tolerances=dict(main=dict(abs_B8L2_difference=2,floor_jaccard_difference=.05,structure_bound_cyclic_degree=3,
            required='both complete, same output node count, comparable bound cyclic ring; tolerances are an engineering diagnostic, not semantic equivalence certification'),
            sensitivity=dict(abs_B8L2_difference=[1,2,5],floor_jaccard_difference=[.02,.05,.10],structure_bound_cyclic_degree=[2,3,5])),
        failure_policy='Every requested team remains in denominator. Preserve separate failures and conditional score means; no zero-filled ability score. A separate bounded delivery utility may assign failure=0 solely for team decision sensitivity.',
        inference='image and building support; building-equal primary uncertainty. Repeated permutations/variants are not independent people; no newly blind historical holdout claim.',
        functions_and_input_hashes={p:sha(SOURCE/p) for p in code_paths})
    save(OUT/'DESIGN.json',design)
    save_gz(OUT/'REQUESTS_INITIAL.json.gz',dict(schema='v2_fusion_requests_v1',design_sha256=sha(OUT/'DESIGN.json'),
        requests=requests,paths=paths,backgrounds=backgrounds))
    save(OUT/'REGISTRATION_RECEIPT.json',dict(design_sha256=sha(OUT/'DESIGN.json'),request_sha256=sha(OUT/'REQUESTS_INITIAL.json.gz'),
        n_requests=len(requests),n_unique_teams=len(unique),output_observed_before_registration=False))
    print({k:design[k] for k in ('n_requests','n_unique_teams','families','n_paths','n_backgrounds','n_all_entrant_pairs')},flush=True)

if __name__=='__main__':main()
