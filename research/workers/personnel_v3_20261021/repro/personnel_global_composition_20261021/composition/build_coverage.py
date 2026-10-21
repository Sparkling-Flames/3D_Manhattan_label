"""Exact completion ledger over finite class-vector and member-set universes."""
from __future__ import annotations
import collections,gzip,math
from global_study import *


def execution_coverage(scalars):
    """Count deliberately registered method experiments, not post-hoc labels.

    The exhaustive near-census requests were method independent.  A method may
    describe those endpoints in UNIVERSE_FINAL_COVERAGE, but that is kept apart
    from the method's deliberately designed configurations and ABC events here.
    """
    events=pd.read_csv(OUT/'ABC_EVENTS.csv.gz',keep_default_na=False)
    configs=pd.read_csv(OUT/'CONFIG_MEMBERSHIP.csv.gz',keep_default_na=False)
    available=set(scalars.team_key)
    good=set(scalars.loc[scalars.complete_evaluable.eq(True),'team_key'])
    groups=['method_id','condition','tier','layer']
    keys=set(map(tuple,events[groups].to_numpy()))|set(map(tuple,configs[groups].to_numpy()))
    rows=[]
    for key in sorted(keys):
        e=events.loc[(events[groups]==key).all(axis=1)]
        c=configs.loc[(configs[groups]==key).all(axis=1)]
        ekeys=set(e[['team_A','team_B','team_C']].to_numpy().ravel())
        ckeys=set(c.team_key)
        designed=ekeys|ckeys
        registered_events=len(e)
        all_available=e[['team_A','team_B','team_C']].isin(available).all(axis=1)
        all_good=e[['team_A','team_B','team_C']].isin(good).all(axis=1)
        cellsets=c.groupby('cell_id').team_key.agg(set)
        rows.append(dict(zip(groups,key))|dict(
            registered_ABC_events=registered_events,
            ABC_events_all_endpoints_available=int(all_available.sum()),
            ABC_events_all_three_complete_evaluable=int(all_good.sum()),
            ABC_events_any_endpoint_not_complete_evaluable=registered_events-int(all_good.sum()),
            registered_ABC_unique_teams=len(ekeys),computed_ABC_unique_teams=len(ekeys&available),
            complete_evaluable_ABC_unique_teams=len(ekeys&good),
            registered_configuration_cells=len(cellsets),
            configuration_cells_all_registered_members_computed=sum(s<=available for s in cellsets),
            configuration_cells_all_registered_members_complete_evaluable=sum(s<=good for s in cellsets),
            registered_configuration_member_rows=len(c),
            computed_configuration_member_rows=int(c.team_key.isin(available).sum()),
            registered_configuration_unique_teams=len(ckeys),
            computed_configuration_unique_teams=len(ckeys&available),
            designed_unique_teams_union=len(designed),computed_designed_unique_teams_union=len(designed&available),
            complete_evaluable_designed_unique_teams_union=len(designed&good),
            images=len(set(e.image)|set(c.image)),buildings=len(set(e.building)|set(c.building)),
            event_images=e.image.nunique(),event_buildings=e.building.nunique(),
            n_min=int(min(e.n.min() if len(e) else math.inf,c.n.min() if len(c) else math.inf)),
            n_max=int(max(e.n.max() if len(e) else -math.inf,c.n.max() if len(c) else -math.inf)),
            event_n_min=int(e.n.min()) if len(e) else None,event_n_max=int(e.n.max()) if len(e) else None,
            m_AB_min=int(e.m_AB.min()) if len(e) else None,m_AB_max=int(e.m_AB.max()) if len(e) else None,
            m_BC_min=int(e.m_BC.min()) if len(e) else None,m_BC_max=int(e.m_BC.max()) if len(e) else None,
            primary_m_ge4_events=int((e.m_AB>=4).sum()),capacity_completion_events=int(e.registration_stage.str.startswith('capacity_completion_').sum()),
            capacity_completion_v2_events=int((e.registration_stage=='capacity_completion_v2').sum()),
            capacity_completion_v3_events=int((e.registration_stage=='capacity_completion_v3').sum()),
            method_independent_near_census_not_counted_as_designed_events=True))
    frame=pd.DataFrame(rows)
    csv(OUT/'METHOD_EXECUTION_COVERAGE.csv',frame)
    opportunities=pd.read_csv(OUT/'ABC_OPPORTUNITY_LEDGER.csv')
    maxima=opportunities.loc[opportunities.requested_by.str.contains('max_ABC_for_mode',na=False)&opportunities.changed_count_ABC_possible].copy()
    event_group=['pool_id','method_id','tier','n','event_mode']
    actual=events.groupby(event_group).m_AB.max().rename('maximum_registered_m').reset_index()
    maxima=maxima.merge(actual,on=event_group,how='left',validate='1:1')
    maxima['maximum_feasible_m_registered']=maxima.maximum_registered_m.fillna(0).eq(maxima.exact_max_m_ABC)
    maxima['coverage_reason']=np.where(maxima.maximum_feasible_m_registered,'registered',
        'theoretical_capacity_exists_but_sampled_block_or_background_had_no_alternative_Z; original_failed_draw_retained')
    csv(OUT/'MAXIMUM_TURNOVER_COVERAGE.csv',maxima)
    return frame

def build():
    pools=pool_lookup();maps=method_maps();labels=method_rows();requests=read(OUT/'ENDPOINT_REQUESTS.json.gz')['requests']
    scalar_frame=pd.read_csv(OUT/'TEAMS_SCALARS.csv.gz',usecols=['team_key','complete_evaluable']) if (OUT/'TEAMS_SCALARS.csv.gz').exists() else pd.DataFrame(columns=['team_key','complete_evaluable'])
    complete=set(scalar_frame.team_key)
    prior,scalar,_=existing_cache();history=set(gzip.open(OUT/'HISTORICAL_TEAM_KEYS.txt.gz','rt').read().splitlines())
    required={r['team_key'] for r in requests};old=history|prior.keys()|scalar.keys();by=collections.defaultdict(list)
    workers=sorted(set(r['worker_id'] for p in pools.values() for r in p['records']));bits={w:1<<i for i,w in enumerate(workers)}
    for r in requests:by[r['pool_id']].append((r['team_key'],len(r['member_workers']),sum(bits[w] for w in r['member_workers'])))
    rows=[]
    for pool in pools.values():
        meta=pool['meta'];pid=pool['pool_id'];formal={r['worker_id'] for r in pool['records']}
        for (method,tier,cond,bld),mapping in sorted(maps.items()):
            if (cond,bld)!=(meta['condition'],meta['building']):continue
            if method in ('Rnew2','F01') and meta['layer']!='ordinary_manual':continue
            ws=formal&mapping.keys();U=len(ws);classes=sorted({mapping[w] for w in ws});classbits={c:sum(bits[w] for w in ws if mapping[w]==c) for c in classes};allow=sum(bits[w] for w in ws)
            cap={c:mask.bit_count() for c,mask in classbits.items()};coefficients=vector_coefficients(cap.values());rr=collections.defaultdict(collections.Counter);cc=collections.defaultdict(collections.Counter)
            for key,n,mask in by[pid]:
                if mask & ~allow:continue
                vector=tuple((mask&classbits[c]).bit_count() for c in classes);rr[n][vector]+=1
                if key in complete:cc[n][vector]+=1
            for n in range(1,U+1):
                possible=math.comb(U,n);registered=sum(rr[n].values());done=sum(cc[n].values())
                assert registered<=possible and done<=registered and len(rr[n])<=coefficients[n]
                rows.append(dict(pool_id=pid,image=meta['image'],condition=cond,layer=meta['layer'],building=bld,difficulty=meta['difficulty'],method_id=method,tier=tier,
                    formal_pool_n=len(formal),labelled_pool_n=U,unknown_workers_n=len(formal)-U,class_capacities=canonical_counts(cap),n=n,
                    all_feasible_class_vectors=coefficients[n],registered_class_vectors=len(rr[n]),computed_class_vectors=len(cc[n]),
                    remaining_unregistered_class_vectors=coefficients[n]-len(rr[n]),remaining_uncomputed_class_vectors=coefficients[n]-len(cc[n]),
                    all_actual_member_sets=str(possible),registered_actual_member_sets=registered,computed_actual_member_sets=done,
                    remaining_unregistered_actual_member_sets=str(possible-registered),remaining_uncomputed_actual_member_sets=str(possible-done),
                    exhaustive_vectors_registered=len(rr[n])==coefficients[n],exhaustive_vectors_computed=len(cc[n])==coefficients[n],
                    exhaustive_members_registered=registered==possible,exhaustive_members_computed=done==possible,
                    full_labelled_pool_singleton=n==U,member_variation_estimable=possible>1,
                    full_addition_orders=str(math.factorial(U)),ordered_prefixes_length_n=str(math.perm(U,n)),ordered_paths_enumerated=False))
    frame=pd.DataFrame(rows);csv(OUT/'UNIVERSE_FINAL_COVERAGE.csv.gz',frame)
    order_path=OUT.parent/'analysis/LAST_TWO_PATH_RECEIPT.json'
    order_receipt=read(order_path) if order_path.exists() else None
    receipt=dict(requested_unique=len(required),computed_unique=len(required&complete),missing_registered_endpoints=len(required-complete),
        historical_583261_overlap=len(required&history),available_complete_geometry_overlap=len(required&prior.keys()),available_scalar_overlap=len(required&scalar.keys()),
        union_prior_registered_sets_overlap=len(required&old),new_actual_member_sets_against_recovered_prior_indexes=len(required-old),
        universe_method_pool_size_rows=len(frame),all_feasible_class_vectors_across_method_populations=int(frame.all_feasible_class_vectors.sum()),
        registered_vectors_across_method_populations=int(frame.registered_class_vectors.sum()),computed_vectors_across_method_populations=int(frame.computed_class_vectors.sum()),
        scope='Class methods have different eligible populations. Their vector totals are ledger cells, not independent images or endpoint sets. Prior-index overlap includes the recovered 583261 study and materialized other-stage caches; unavailable unindexed historical caches are not silently presumed covered.',
        near_census='Every formal-pool actual member set at n=N-2,N-1,N; this does not enumerate all pair comparisons or all earlier order prefixes.',
        all_omitted_member_spaces_exact=True,all_full_addition_orders_enumerated=False,
        exact_last_two_suffix_process=order_receipt,
        exact_last_two_suffix_scope='Formal N-2 -> N-1 -> N pools; does not imply all full orders or every smaller method-labelled population has been separately ordered.')
    save(OUT/'COMPLETION_COVERAGE_RECEIPT.json',receipt)
    # Add pure-block and full hierarchy descriptors without changing frozen
    # event identities, member sets, outcomes or the registered event table.
    descriptors=[]
    for r in pd.read_csv(OUT/'ABC_EVENTS.csv.gz',keep_default_na=False).to_dict('records'):
        mapping=maps[r['method_id'],r['tier'],r['condition'],r['building']];out=dict(event_id=r['event_id'])
        blocks={k:r[col].split('|') if r[col] else [] for k,col in [('X','outgoing_block_X'),('Y','same_count_block_Y'),('Z','changed_count_block_Z')]}
        counts={k:collections.Counter(mapping[w] for w in ws) for k,ws in blocks.items()}
        for k,c in counts.items():out['block_'+k+'_counts']=canonical_counts(c);out['block_'+k+'_pure_class']=next(iter(c)) if len(c)==1 else None
        out['pure_class_block_swap']=len(counts['X'])==len(counts['Z'])==1 and counts['X']!=counts['Z'];out['same_block_counts_XY']=counts['X']==counts['Y']
        out['class_count_turnover_XZ']=sum(abs(counts['X'][c]-counts['Z'][c]) for c in counts['X'].keys()|counts['Z'].keys())//2
        descriptors.append(out)
    csv(OUT/'ABC_BLOCK_DESCRIPTORS.csv.gz',pd.DataFrame(descriptors))
    execution_coverage(scalar_frame)
    save(OUT/'REQUEST_CACHE_OVERLAP.json',dict(
        request_scope='final_design_after_capacity_completion_v2',
        request_file='ENDPOINT_REQUESTS.json.gz',
        request_sha256=hashlib.sha256((OUT/'ENDPOINT_REQUESTS.json.gz').read_bytes()).hexdigest(),
        total_requested_unique=len(required),
        recovered_history_unique=len(history),historical_583261_overlap=len(required&history),
        materialized_full_geometry_unique=len(prior),materialized_full_geometry_overlap=len(required&prior.keys()),
        materialized_scalar_unique=len(scalar),materialized_scalar_overlap=len(required&scalar.keys()),
        new_against_union_prior_indexes=len(required-old),
        historical_endpoint_regeneration='Historical set overlap does not imply recoverable native geometry. Missing geometry was regenerated under the frozen contract and retained as historical_overlap, not counted as a new independent member-set experiment.'))
    print(json.dumps(receipt,ensure_ascii=False),flush=True)

if __name__=='__main__':build()
