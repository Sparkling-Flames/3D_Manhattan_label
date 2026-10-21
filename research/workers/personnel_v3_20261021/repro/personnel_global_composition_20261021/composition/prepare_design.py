"""Freeze exact near-census layers, complete class vectors, matched ABC events.

Selection uses metadata, frozen target-building-excluded labels and a fixed
seed. No native endpoint score is read. Configuration counts, actual sets,
event triplets and ordered paths have separate coverage ledgers.
"""
from __future__ import annotations
import argparse,collections,itertools,math
from global_study import *

def sample_members(groups,counts,number,seed):
    possible=math.prod(math.comb(len(groups[c]),k) for c,k in counts.items());number=min(number,possible)
    if number==possible:
        choices=[list(itertools.combinations(groups[c],counts[c])) for c in sorted(groups)]
        return [tuple(sorted(itertools.chain.from_iterable(xx))) for xx in itertools.product(*choices)],possible
    random=rng(seed);chosen=set()
    while len(chosen)<number:
        chosen.add(tuple(sorted(w for c in sorted(groups) for w in random.choice(groups[c],counts[c],replace=False).tolist())))
    return sorted(chosen),possible

def select_panel(pools):
    groups=collections.defaultdict(list)
    for p in pools.values():
        if len(p['records'])>=20 and p['meta']['layer'] in ('ordinary_manual','ordinary_semi','doorway_manual'):
            groups[p['meta']['layer'],p['meta']['building']].append(p)
    rank={'困难':2,'中等':1,'简单':0};selected=[]
    for key,pp in sorted(groups.items()):
        selected.append(min(pp,key=lambda p:(-rank.get(p['meta']['difficulty'],0),digest(['panel',p['pool_id']]))))
    for p in pools.values():
        if p['meta']['image']=='jtcxE69GiFV-26' and p['meta']['layer']=='ordinary_manual' and p not in selected:selected.append(p)
    return selected

def meta(pool):return {k:pool['meta'].get(k) for k in ('pool_id','image','image_id','building','condition','layer','difficulty','reference_id','reference_version')}

def capable_extra_classes(x,cap,parent=None):
    """An extra outside worker in c can replace a Y worker in d != c.

    After reserving disjoint equal-count X/Y, residual capacity is cap-2*x.
    If n+m<U, at least one residual worker can be left outside the background.
    This is an exact count-level existence criterion, not an effect screen.
    """
    return [c for c in cap if cap[c]-2*x[c]>0 and any(x[d]>0 and d!=c and (parent is None or parent[c]==parent[d]) for d in cap)]

def max_abc_capacity(cap,n,parent=None):
    U=sum(cap.values());upper=min(n,U-n-1,sum(v//2 for v in cap.values()))
    for m in range(upper,0,-1):
        if any(capable_extra_classes(x,cap,parent) for x in count_vectors({c:v//2 for c,v in cap.items()},m)):return m
    return 0

def prepare(top_deletions=2,draws=3,event_reps=1,block_vectors=4,capacity_completion=True):
    pools=pool_lookup();maps=method_maps();labels=method_rows();csv(OUT/'FROZEN_LABELS.csv',labels);panel=select_panel(pools);requests={};layers=[];configs=[];events=[];event_ledger=[];opportunities=[]
    parents={(r.method_id,r.condition,r.heldout_building,r.worker_id):r.parent_class for r in labels.itertuples() if r.tier=='fine'}
    def add(pool,ws,stage):
        ws=sorted(ws);key=team_key(pool['pool_id'],ws)
        if key not in requests:requests[key]=dict(team_key=key,pool_id=pool['pool_id'],member_workers=ws,n=len(ws),stages=[stage])
        elif stage not in requests[key]['stages']:requests[key]['stages'].append(stage)
        return key
    for pool in pools.values():
        ws=sorted(r['worker_id'] for r in pool['records']);N=len(ws)
        for n in range(max(1,N-top_deletions),N+1):
            for excluded in itertools.combinations(ws,N-n):add(pool,set(ws)-set(excluded),'complete_near_census')
            layers.append(dict(meta(pool),N=N,n=n,all_member_sets=str(math.comb(N,n)),registered_member_sets=math.comb(N,n),exhaustive_members=True,
               all_unordered_team_pairs=str(math.comb(math.comb(N,n),2)),all_ordered_length_n_sequences=str(math.perm(N,n)),addition_orders_enumerated=False))
    exact_keys=set(requests)
    save(OUT/'STAGE2_REQUESTS.json.gz',dict(stage='complete_near_census',requests=list(requests.values())))
    csv(OUT/'EXACT_LAYERS.csv',pd.DataFrame(layers))
    csv(OUT/'PANEL_POOLS.csv',pd.DataFrame([dict(meta(p),formal_pool_n=len(p['records']),selection='one largest-difficulty available image per building/layer, metadata hash tie-break; jtc-26 mechanism sentinel additionally retained') for p in panel]))
    selected_count=collections.Counter()
    for pool in panel:
        pid=pool['pool_id'];pmeta=pool['meta'];formal={r['worker_id'] for r in pool['records']}
        for (method,tier,condition,building),mapping in sorted(maps.items()):
            if (condition,building)!=(pmeta['condition'],pmeta['building']):continue
            if method in ('Rnew2','F01') and pmeta['layer']!='ordinary_manual':continue
            # Unstable no-Q candidate remains a declared negative/conditional
            # control on six metadata-selected Manual panel pools, not a main grid.
            if method=='MV_TDScopeSemi_manual_new':
                eligible=sorted([p['pool_id'] for p in panel if p['meta']['layer']=='ordinary_manual'],key=lambda p:digest(['noq_panel',p]))[:6]
                if pid not in eligible:continue
            groups=collections.defaultdict(list)
            for w in sorted(formal & mapping.keys()):groups[mapping[w]].append(w)
            cap={c:len(ws) for c,ws in groups.items()};U=sum(cap.values())
            if U<15 or len(cap)<2:continue
            common=dict(meta(pool),method_id=method,tier=tier,labelled_pool_n=U,formal_pool_n=len(formal),class_capacities=canonical_counts(cap))
            sizes=sorted({n for n in (15,20,25,30,35,40) if n<=U})
            for n in sizes:
                vectors=list(count_vectors(cap,n))
                for counts in vectors:
                    composition=canonical_counts(counts);cell_id=digest([method,tier,pid,n,composition])[:20]
                    teams,possible=sample_members(groups,counts,draws,['configuration',cell_id])
                    for rep,ws in enumerate(teams):
                        key=add(pool,ws,'complete_vectors_sampled_members')
                        configs.append(dict(common,n=n,composition=composition,cell_id=cell_id,team_key=key,replicate=rep,
                           feasible_vectors=len(vectors),registered_vectors=len(vectors),exhaustive_vectors=True,
                           possible_member_sets=str(possible),registered_member_sets=len(teams),exhaustive_members=len(teams)==possible,
                           member_variation_estimable=possible>1))
                    selected_count[method,tier]+=len(teams)
            # All m values are actual cardinalities |A\B|=|A\C|.
            # Equal-count X/Y blocks are drawn before a common core so that the
            # within-class comparator exists even with relatively large m.
            maxm=min(sum(v//2 for v in cap.values()),U-15)
            old_ms=sorted({m for m in (4,8,12,maxm) if 1<=m<=maxm})
            parent_by_c={c:parents[(method,condition,building,groups[c][0])] for c in cap} if tier=='fine' else None
            for n in sizes:
                modes=['cross_composition']+(['within_coarse_fine_change'] if tier=='fine' else [])
                max_ab=min(n,U-n,sum(v//2 for v in cap.values()))
                max_abc={mode:max_abc_capacity(cap,n,parent_by_c if mode=='within_coarse_fine_change' else None) for mode in modes}
                ms=sorted(set(old_ms)|({max_ab,*max_abc.values()} if capacity_completion else set()))
                for mode in modes:
                    for requested_m in sorted({4,8,12,max_ab,max_abc[mode]}):
                        ab_ok=requested_m>=1 and requested_m<=max_ab;abc_ok=requested_m>=1 and requested_m<=max_abc[mode]
                        opportunities.append(dict(common,n=n,event_mode=mode,m=requested_m,exact_max_m_AB=max_ab,exact_max_m_ABC=max_abc[mode],
                            equal_count_AB_possible=ab_ok,changed_count_ABC_possible=abc_ok,
                            reason='feasible' if abc_ok else ('full_team_no_replacement' if U==n else ('outside_A_has_no_extra_worker_for_changed_counts' if ab_ok and n+requested_m==U else 'class_or_parent_count_capacity')),
                            requested_by='|'.join(name for name,yes in [('standard_m',requested_m in (4,8,12)),('max_AB',requested_m==max_ab),('max_ABC_for_mode',requested_m==max_abc[mode])] if yes)))
                for m in ms:
                    if m<1 or m>n or n+m>U:continue
                    new_capacity_m=m not in old_ms
                    blockcap={c:v//2 for c,v in cap.items()};vectors=list(count_vectors(blockcap,m))
                    if not vectors:continue
                    # Actual event enumeration is intentionally finite. Exact
                    # possible matched A/B pairs can still be counted below.
                    random=rng(['events',method,tier,pid,n,m]);indices=random.choice(len(vectors),min(block_vectors,len(vectors)),replace=False).tolist()
                    possible_ab=sum(math.prod(math.comb(cap[c],x[c])*math.comb(cap[c]-x[c],x[c]) for c in cap)*math.comb(U-2*m,n-m) for x in vectors)
                    start_events=len(events);attempts=0;failures=collections.Counter()
                    for mode in modes:
                        mode_indices=list(indices)
                        capable=[i for i,x in enumerate(vectors) if n+m<U and capable_extra_classes(x,cap,parent_by_c if mode=='within_coarse_fine_change' else None)]
                        if new_capacity_m and capable and not set(mode_indices)&set(capable):mode_indices[0]=capable[int(random.integers(len(capable)))]
                        for vi in sorted(mode_indices):
                            xcounts=vectors[vi]
                            for rep in range(event_reps):
                                attempts+=1;X=[];Y=[]
                                for c in sorted(cap):
                                    drawn=random.choice(groups[c],2*xcounts[c],replace=False).tolist();X.extend(drawn[:xcounts[c]]);Y.extend(drawn[xcounts[c]:])
                                rest=sorted(formal&mapping.keys()-set(X)-set(Y))
                                if new_capacity_m and n+m<U:
                                    extras=capable_extra_classes(xcounts,cap,parent_by_c if mode=='within_coarse_fine_change' else None)
                                    reserved=[w for w in rest if mapping[w] in extras]
                                    if reserved:rest.remove(reserved[int(random.integers(len(reserved)))])
                                S=random.choice(rest,n-m,replace=False).tolist();A=set(S+X);B=set(S+Y);outside=sorted((formal&mapping.keys())-A)
                                outs=collections.Counter(mapping[w] for w in outside);zcandidates=list(count_vectors({c:outs.get(c,0) for c in cap},m))
                                zcandidates=[z for z in zcandidates if z!=xcounts]
                                if mode=='within_coarse_fine_change':
                                    parent_x=collections.Counter()
                                    for c,k in xcounts.items():parent_x[parent_by_c[c]]+=k
                                    def parent_count(z):
                                        rr=collections.Counter()
                                        for c,k in z.items():rr[parent_by_c[c]]+=k
                                        return rr
                                    zcandidates=[z for z in zcandidates if parent_count(z)==parent_x]
                                if not zcandidates:failures['no_alternative_block_counts']+=1;continue
                                # Prefer the largest feasible count-vector change;
                                # tie-break by the seeded metadata-only generator.
                                distance=lambda z:sum(abs(z[c]-xcounts[c]) for c in cap)//2
                                maxdist=max(map(distance,zcandidates));zcandidates=[z for z in zcandidates if distance(z)==maxdist]
                                z=zcandidates[int(random.integers(len(zcandidates)))];Z=[]
                                for c in sorted(cap):Z.extend(random.choice([w for w in outside if mapping[w]==c],z[c],replace=False).tolist())
                                C=set(S+Z)
                                assert A&B==A&C==set(S) and len(A-B)==len(A-C)==m
                                ca={c:sum(mapping[w]==c for w in A) for c in cap};cb={c:sum(mapping[w]==c for w in B) for c in cap};cc={c:sum(mapping[w]==c for w in C) for c in cap}
                                assert ca==cb and ca!=cc
                                keys=[add(pool,w,'capacity_completion_v2' if new_capacity_m else 'matched_ABC_large_blocks') for w in (A,B,C)]
                                event_id=digest([method,tier,mode,pid,n,m,sorted(S),sorted(X),sorted(Y),sorted(Z)])[:24]
                                events.append(dict(common,event_id=event_id,event_mode=mode,registration_stage='capacity_completion_v2' if new_capacity_m else 'initial_budget_v2',n=n,m_AB=m,m_AC=m,m_BC=len(B-C),
                                   overlap_AB=len(A&B),overlap_AC=len(A&C),overlap_BC=len(B&C),new_block_YZ_overlap=len(set(Y)&set(Z)),
                                   composition_turnover_AC=maxdist,team_A=keys[0],team_B=keys[1],team_C=keys[2],
                                   composition_A=canonical_counts(ca),composition_B=canonical_counts(cb),composition_C=canonical_counts(cc),
                                   common_background='|'.join(sorted(S)),outgoing_block_X='|'.join(sorted(X)),same_count_block_Y='|'.join(sorted(Y)),changed_count_block_Z='|'.join(sorted(Z)),
                                   ABC_sampling=f'up to {block_vectors} possible equal-count block vectors × {event_reps} member draws per n,m,mode; alternative Z maximizes feasible count change; not exhaustive event triplets'))
                    event_ledger.append(dict(common,n=n,m=m,feasible_equal_count_block_vectors=len(vectors),sampled_equal_count_block_vectors=len(indices),
                       all_possible_ordered_AB_pairs=str(possible_ab),ABC_triplets_exact_count='not_enumerated',attempts=attempts,registered_events=len(events)-start_events,
                       failed_attempts=attempts-(len(events)-start_events),failure_reasons=json.dumps(failures,sort_keys=True),exhaustive_events=False,
                       registration_stage='capacity_completion_v2' if new_capacity_m else 'initial_budget_v2',exact_max_m_AB=max_ab,exact_max_m_ABC_cross=max_abc['cross_composition'],exact_max_m_ABC_within_coarse=max_abc.get('within_coarse_fine_change')))
    csv(OUT/'CONFIG_MEMBERSHIP.csv.gz',pd.DataFrame(configs));csv(OUT/'ABC_EVENTS.csv.gz',pd.DataFrame(events));csv(OUT/'ABC_EVENT_COVERAGE.csv',pd.DataFrame(event_ledger))
    csv(OUT/'ABC_OPPORTUNITY_LEDGER.csv',pd.DataFrame(opportunities))
    save(OUT/'ENDPOINT_REQUESTS.json.gz',dict(seed=SEED,requests=list(requests.values())))
    receipt=dict(seed=SEED,pools=len(pools),panel_pools=len(panel),complete_near_census_sets=len(exact_keys),all_requested_unique_sets=len(requests),
       additional_unique_sets=len(requests)-len(exact_keys),configuration_membership_rows=len(configs),configuration_cells=len({r['cell_id'] for r in configs}),
       matched_ABC_events=len(events),member_draws_per_vector=draws,ABC_block_vectors_cap=block_vectors,ABC_member_draws_per_block=event_reps,budget_revision='DESIGN_BUDGET_V1.json; reduced before any ABC outcome inspection',all_vectors_enumerated_at_declared_panel_sizes=True,
       all_concrete_members_enumerated_only_for='All formal pools n=N-2..N and configuration cells whose possible_member_sets <= draws; every other member-space remainder is explicit.',
       all_addition_orders_enumerated=False,event_triplets_exhaustive=False,
       capacity_completion_v2=capacity_completion,capacity_amendment_scope='Per n exact AB and ABC capacity maxima; prior events preserved. Two-pool mechanism previews existed, but this correction uses only n/U/class capacities.',
       leakage_guard='All evaluated labels exclude the target building. Sampling never reads endpoint scores.',
       throughput_receipt='THROUGHPUT_RECEIPT.json',label_file_sha256=hashlib.sha256((OUT.parent/'multivariate/labels_lobo.csv.gz').read_bytes()).hexdigest())
    files=[TAX/'labels/lobo_labels.csv',OUT.parent/'multivariate/labels_lobo.csv.gz',OUT.parent/'multivariate/same_source_candidate_labels.csv',OUT/'legacy_composition_labels.csv',OUT/'FROZEN_LABELS.csv',OUT/'ENDPOINT_REQUESTS.json.gz',OUT/'ABC_EVENTS.csv.gz',OUT/'CONFIG_MEMBERSHIP.csv.gz']
    receipt['frozen_inputs_outputs_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    receipt['input_commit']='51b519f943b2dd3a4fb2f0198133ac5dd17209ab'
    receipt['legacy_label_scope']='History 10 buildings, targets only the explicitly allowed other 12 buildings; ordinary Manual only; not target-wise refitting.'
    save(OUT/'DESIGN_FREEZE.json',receipt);print(json.dumps(receipt,ensure_ascii=False),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--draws',type=int,default=3);ap.add_argument('--event-reps',type=int,default=1);ap.add_argument('--block-vectors',type=int,default=4);ap.add_argument('--initial-capacity-only',action='store_true');a=ap.parse_args();prepare(draws=a.draws,event_reps=a.event_reps,block_vectors=a.block_vectors,capacity_completion=not a.initial_capacity_only)
