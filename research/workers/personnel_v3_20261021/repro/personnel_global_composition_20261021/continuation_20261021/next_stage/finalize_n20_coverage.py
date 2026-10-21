"""Close only fully completed n=20 batches and update the exact global ledger.

No fusion is run and no outcome is used for endpoint selection. Prior files
remain unchanged; this publishes a new-stage coverage ledger.
"""
from __future__ import annotations
import collections, csv, gzip, hashlib, json, sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
STUDY=HERE.parents[1]
OUT=HERE/'coverage'
sys.path.insert(0,str(HERE));sys.path.insert(0,str(STUDY/'composition'))
import global_study as gs
from prepare_n20_design import atomic_frame, METHODS
from run_n20_batches import validate_csv


def verify_frozen_inputs(design):
    input_checks={
        str(STUDY/'composition/FROZEN_LABELS.csv'):design['frozen_labels_sha256'],
        str(STUDY/'composition/ENDPOINT_REQUESTS.json.gz'):design['existing_request_sha256'],
        **{str(HERE/k):v for k,v in design['input_and_code_hashes'].items() if k.startswith('candidate_n20/')},
    }
    for name,expected_hash in input_checks.items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=expected_hash:
            raise ValueError(('frozen_input_changed',name))
    return input_checks


def main():
    design=gs.read(HERE/'DESIGN_FREEZE.json')
    input_checks=verify_frozen_inputs(design)
    target=gs.read(HERE/'candidate_n20/ENDPOINT_REQUESTS.json.gz')['requests']
    required={r['team_key'] for r in target}
    observed=set();states=collections.Counter();new_states=collections.Counter();sources=[]
    paths=[HERE/'batches/REUSED_ENDPOINT_SCALARS.csv.gz']+[HERE/'batches'/r['batch_id']/'ENDPOINT_SCALARS.csv.gz' for r in design['batches']]
    for path in paths:
        expected={r['team_key'] for r in gs.read(path.parent/('REUSED_REQUESTS.json.gz' if path.name.startswith('REUSED') else 'REQUESTS.json.gz'))['requests']}
        check=validate_csv(path,expected)
        if observed & expected:raise ValueError('Endpoint is repeated in multiple batches')
        observed |= expected
        data=gs.pd.read_csv(path,usecols=['team_key','score_status','complete_evaluable'])
        states.update(data.score_status)
        if not path.name.startswith('REUSED'):new_states.update(data.score_status)
        sources.append(dict(path=str(path.relative_to(HERE)),**check))
        gpath=path.with_name(path.name.replace('SCALARS','GEOMETRY'))
        validate_csv(gpath,expected)
    if observed!=required:raise ValueError(('incomplete_continuation',len(observed),len(required)))
    memberships=gs.pd.read_csv(HERE/'candidate_n20/CONFIG_MEMBERSHIP.csv.gz')
    if memberships.team_key.nunique()!=len(required) or set(memberships.team_key)!=required:
        raise ValueError('Configuration references do not cover exactly the frozen requests')
    if len(memberships)!=design['member_references'] or memberships.cell_id.nunique()!=design['cells']:
        raise ValueError('Configuration row/cell counts differ from freeze')
    poolmeth=gs.pd.read_csv(HERE/'candidate_n20/POOL_METHOD_COVERAGE.csv')
    aggregate=poolmeth.groupby(['method_id','tier','condition'],as_index=False).agg(
        pools=('pool_id','nunique'),images=('image_id','nunique'),buildings=('building','nunique'),
        all_class_vectors=('all_class_vectors','sum'),prior_touched_vectors=('prior_touched_vectors','sum'),
        new_vectors=('new_vectors','sum'),member_references=('member_references','sum'),
        member_references_cached=('member_references_cached','sum'),new_member_references=('new_member_references','sum'))
    aggregate['computed_class_vectors']=aggregate.all_class_vectors
    aggregate['missing_class_vectors']=0
    atomic_frame(OUT/'N20_METHOD_COMPLETION.csv',aggregate,('method_id','tier','condition'))
    # The old global ledger counts actual registered/computed sets under every
    # eligible method, even when a set was generated under another method.
    # Apply exactly that convention to the enlarged union, without changing
    # the predefined scientific scope of the current six-method comparison.
    oldreq=gs.read(STUDY/'composition/ENDPOINT_REQUESTS.json.gz')['requests']
    allreq={r['team_key']:r for r in oldreq}
    allreq.update({r['team_key']:r for r in target})
    by=collections.defaultdict(list)
    for r in allreq.values():
        if len(r['member_workers'])==20:by[r['pool_id']].append(r)
    universe=gs.pd.read_csv(STUDY/'composition/UNIVERSE_FINAL_COVERAGE.csv.gz',dtype=str)
    old_total_vectors=sum(map(int,universe.computed_class_vectors))
    maps=gs.method_maps();updated_rows=0
    for i,r in universe.iterrows():
        if int(r['n'])!=20 or r['pool_id'] not in by:continue
        mapping=maps[(r.method_id,r.tier,r.condition,r.building)]
        cap={c:int(n) for c,n in (x.split(':') for x in r.class_capacities.split('|'))}
        compositions=set();nsets=0
        for q in by[r.pool_id]:
            if not set(q['member_workers'])<=mapping.keys():continue
            counts=collections.Counter(mapping[w] for w in q['member_workers'])
            compositions.add(gs.canonical_counts({c:counts.get(c,0) for c in cap}));nsets+=1
        nvec=len(compositions);allvec=int(r.all_feasible_class_vectors);allsets=int(r.all_actual_member_sets)
        if nvec<int(r.computed_class_vectors) or nsets<int(r.computed_actual_member_sets):
            raise ValueError(('coverage_regression',r.pool_id,r.method_id,r.tier))
        if nvec>allvec or nsets>allsets:raise ValueError('Coverage exceeds finite universe')
        for prefix in ('registered','computed'):
            universe.at[i,prefix+'_class_vectors']=str(nvec)
            universe.at[i,prefix+'_actual_member_sets']=str(nsets)
            universe.at[i,'exhaustive_vectors_'+prefix]=str(nvec==allvec)
            universe.at[i,'exhaustive_members_'+prefix]=str(nsets==allsets)
        universe.at[i,'remaining_unregistered_class_vectors']=str(allvec-nvec)
        universe.at[i,'remaining_uncomputed_class_vectors']=str(allvec-nvec)
        universe.at[i,'remaining_unregistered_actual_member_sets']=str(allsets-nsets)
        universe.at[i,'remaining_uncomputed_actual_member_sets']=str(allsets-nsets)
        updated_rows+=1
    primary=universe[(universe.n=='20')&universe.layer.isin(['ordinary_manual','ordinary_semi'])]
    mask=primary.apply(lambda r:(r.method_id,r.tier,r.condition) in METHODS,axis=1)
    if any(primary[mask].remaining_uncomputed_class_vectors.astype(int)!=0):
        raise ValueError('Selected n=20 vector space is not complete')
    outfile=OUT/'UNIVERSE_FINAL_COVERAGE_AFTER_N20.csv.gz'
    atomic_frame(outfile,universe,('pool_id','method_id','tier','n'))
    totalvec=sum(map(int,universe.computed_class_vectors))
    history=set(gzip.open(STUDY/'composition/HISTORICAL_TEAM_KEYS.txt.gz','rt').read().splitlines())
    prior_completion=gs.read(STUDY/'composition/ENDPOINT_COMPLETION.json')
    combined_states=collections.Counter(prior_completion['score_status_counts'])+new_states
    if sum(combined_states.values())!=len(allreq):raise ValueError('Combined failure denominator differs from endpoint union')
    receipt=dict(status='complete',frozen_requested=len(required),computed_unique=len(observed),missing=0,
        all_requested_class_vectors=design['cells'],computed_class_vectors=design['cells'],
        configuration_member_references=len(memberships),score_status_counts=dict(states),
        continuation_new_unique_sets=design['newly_required_native_endpoints'],previous_reused_unique_sets=design['reused_endpoints'],
        previous_stage_unique_sets=len(oldreq),combined_distinct_endpoint_sets=len(allreq),
        combined_new_sets_against_recovered_history=len(set(allreq)-history),
        combined_historical_geometry_restorations=len(set(allreq)&history),
        continuation_new_score_status_counts=dict(new_states),combined_score_status_counts=dict(combined_states),
        global_method_vector_universe=sum(map(int,universe.all_feasible_class_vectors)),
        old_global_computed_vectors=old_total_vectors,new_global_computed_vectors=totalvec,
        newly_touched_vectors_all_eligible_methods=totalvec-old_total_vectors,
        remaining_global_uncomputed_vectors=sum(map(int,universe.remaining_uncomputed_class_vectors)),
        updated_global_rows=updated_rows,source_files=sources,
        frozen_input_hashes_verified=input_checks,
        concrete_members_exhaustive=False,all_orders_exhaustive=False,
        only_member_exhaustive_cells=design['only_member_exhaustive_cells'],singleton_cells=design['singleton_cells'],
        failed_endpoints_retained=True,old_stage_files_unchanged=True)
    gs.save(OUT/'N20_COMPLETION.json',receipt)
    print(json.dumps(receipt,ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':main()
