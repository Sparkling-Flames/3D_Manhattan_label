"""Summarize closed native artifacts without treating requests as completions.

This is an execution ledger, not a statistical result. Counts of unique teams,
sampled prefix occurrences and independent random orders remain separate.
Part receipts are committed only after scalar/geometry gzip EOF validation.
Full relational validation is performed by validate_execution_shards.py.
"""
from pathlib import Path
import argparse, collections, csv, datetime, json
from execute_extension import save_csv, savejson


def run(base, require_complete=False):
    base=Path(base)
    reg=json.loads((base/'design26/REGISTRATION_RECEIPT.json').read_text())
    with (base/'design26/POOL_SAMPLING_PLAN.csv').open(encoding='utf-8-sig') as f:
        plan=list(csv.DictReader(f))
    poolrows=[]; staterows=[]; stages=[]
    for stage in (1,2):
        out=base/'new_endpoints26'/f'stage{stage}'
        total=collections.Counter(); unique_states=collections.Counter()
        occurrence_states=collections.Counter();policy_occurrences=collections.Counter()
        for p in plan:
            pid=p['pool_id'];folder=out/'parts'/pid
            end=folder/'POOL_RECEIPT.json'
            done=json.loads(end.read_text()) if end.exists() else None
            parts=[json.loads(x.read_text()) for x in sorted(folder.glob('part_*.receipt.json'))]
            pref=out/'prefix_values'/(pid+'.receipt.json')
            prefix=json.loads(pref.read_text()) if pref.exists() else None
            closed=sum(x['rows'] for x in parts);requested=int(p[f'stage{stage}_new_endpoints'])
            if done:
                assert done['completed_unique']==closed==requested
            if require_complete:
                assert done is not None and done['completed'] and prefix is not None,pid
            for x in parts:unique_states.update(x['endpoint_state_counts'])
            if prefix:
                occurrence_states.update(prefix['endpoint_state_counts'])
                policy_occurrences.update(prefix['policy_prefix_counts'])
            row={k:p[k] for k in ('pool_id','image','image_id','building','condition','layer','difficulty','pool_n','reference_id','reference_version','pool_input_sha256')}
            row.update(stage=stage,requested_new_unique=requested,closed_new_unique=closed,
                remaining_new_unique=requested-closed,pool_native_complete=done is not None,
                prefix_complete=prefix is not None,closed_parts=len(parts),
                prefix_occurrences=prefix['rows'] if prefix else 0,
                native_evaluation_seconds=sum(x['native_evaluation_seconds'] for x in parts),
                scalar_bytes=sum(x['scalar_bytes'] for x in parts),
                compact_geometry_bytes=sum(x['geometry_bytes'] for x in parts),
                full_state_bytes=sum(x['full_state_bytes'] for x in parts),
                full_state_rows=sum(x['full_state_rows'] for x in parts),
                max_worker_rss_kib=done['max_rss_kib'] if done else None,
                completion_receipt=str(end.relative_to(base)) if done else '')
            poolrows.append(row)
            for k in ('requested_new_unique','closed_new_unique','remaining_new_unique','closed_parts',
                      'prefix_occurrences','native_evaluation_seconds','scalar_bytes','compact_geometry_bytes',
                      'full_state_bytes','full_state_rows'):
                total[k]+=row[k]
            total['complete_pool_count']+=int(done is not None)
            total['complete_prefix_pool_count']+=int(prefix is not None)
        for unit,count in (('unique_new_endpoint',unique_states),('sampled_prefix_occurrence',occurrence_states)):
            for state,n in sorted(count.items()):
                staterows.append(dict(stage=stage,counting_unit=unit,endpoint_state=state,count=n))
        rr=out/'RUN_RECEIPT.json'
        stage_result=dict(stage=stage,**total,endpoint_state_counts=dict(unique_states),
            prefix_state_counts=dict(occurrence_states),policy_prefix_counts=dict(policy_occurrences),
            native_stage_wall_seconds=json.loads(rr.read_text())['seconds'] if rr.exists() else None)
        stages.append(stage_result)
    complete=all(s['complete_pool_count']==len(plan) and s['complete_prefix_pool_count']==len(plan)
                 and s['remaining_new_unique']==0 for s in stages)
    if require_complete:assert complete
    completed=sum(s['closed_new_unique'] for s in stages)
    if complete:
        assert completed==reg['counts']['new_native_required_20261026']
        assert sum(s['prefix_occurrences'] for s in stages)==reg['counts']['prefix_rows']
    result=dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        complete=complete,repository_commit='b9bcec809fbaec8ab055931a1abb7baa5db44dac',
        registration_counts=reg['counts'],pool_count=len(plan),
        ordinary_manual_pools=reg['ordinary_manual'],doorway_manual_pools=reg['doorway_manual'],
        independent_new_natural_orders=reg['counts']['natural_orders'],
        derived_new_policy_orders=reg['counts']['policy_orders'],
        new_natural_orders_per_pool=reg['natural_per_pool'],
        new_policy_random_bases_per_eligible_pool=16,
        completed_new_unique_endpoints=completed,
        reused_unique_endpoints=reg['counts']['inherited_population_20261023']+reg['counts']['inherited_precision_20261025'],
        stages=stages,
        interpretation={
            'policy_orders':'Four target-first permutations of each of 16 paired random bases; not 64 independent natural draws.',
            'native_evaluation_seconds':'Sum of per-team elapsed evaluation seconds across workers; not experiment wall time.',
            'max_worker_rss_kib':'Process high-water mark, not a sum or an exact per-pool allocation.',
            'prefix_occurrences':'Repeated exact teams retain their multiplicity in the random-order sample.',
            'complete':'All registered new teams and per-pool prefix outputs closed; scientific precision is assessed separately.',
            'geometry_retention':'Compact final geometry for every new team; full identity state only prespecified three pools plus hash 1/200.',
            'status_denominators':'Unique-endpoint counts describe computation; prefix occurrence counts describe sampled paths. Statistical rates use the relevant natural/policy support, not this combined ledger.'})
    dest=base/'new_endpoints26'
    tag='FINAL' if complete else 'PARTIAL'
    save_csv(dest/(tag+'_POOL_EXECUTION_LEDGER.csv.gz'),poolrows)
    save_csv(dest/(tag+'_EXECUTION_STATUS_COUNTS.csv.gz'),staterows)
    savejson(dest/(tag+'_EXECUTION_LEDGER.json'),result)
    return result


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--base',type=Path,required=True)
    ap.add_argument('--require-complete',action='store_true');args=ap.parse_args()
    r=run(args.base,args.require_complete)
    print(json.dumps({k:v for k,v in r.items() if k not in ('stages','interpretation')}))
