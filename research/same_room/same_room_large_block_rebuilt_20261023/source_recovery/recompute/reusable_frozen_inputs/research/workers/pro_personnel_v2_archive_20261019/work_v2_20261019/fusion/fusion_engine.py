"""Frozen main fusion applied to explicitly saved real member subsets, data v2."""
from __future__ import annotations
from collections import Counter,defaultdict
from concurrent.futures import ProcessPoolExecutor,as_completed
from functools import lru_cache
from itertools import combinations
from pathlib import Path
import argparse,gzip,json,os,sys,time
import numpy as np
import pandas as pd
from pool_io import OUT,ROOT,SOURCE,ENGINE,COMMIT,clean,canonical,save,save_gz,csv,read,sha,digest,subset_id,team_id,number,load_pools
sys.path[:0]=[str(ROOT/'work_20261018/runtime_deps'),str(ROOT/'runtime_deps'),str(SOURCE)]
from shapely.ops import unary_union
from tools.thesis_main.analysis.consensus_delivery_20261008 import fuse,WORKING_GAP
from tools.thesis_main.analysis.wall_consensus_v1_process_20261017 import cached_matching
from tools.thesis_main.analysis.wall_consensus_population_20261014 import compact,summarize_state,transition,footprint
from tools.thesis_main.analysis.research_round_20260929 import reconstruct
from tools.thesis_main.analysis.scope_quality_scoring_20261016 import scoring_engine
from tools.thesis_main.analysis.wall_consensus_quality_20261015 import measured
from tools.thesis_main.analysis.quality_b8l2_d10_20261017 import dual_scores
from tools.thesis_main.analysis.wall_consensus_b8l2_20261016 import COMPONENTS,finite
from tools.thesis_main.analysis.paired_split_research.study import angular,cyclic

def context(pool):
    return dict(git_commit=COMMIT,input_records_hash=digest(pool['records']),reference_hash=digest(pool['reference']),
        fusion_entry='consensus_delivery_20261008.fuse',gap=WORKING_GAP,N1_applied=False,
        fusion_module_hash=sha(SOURCE/'tools/thesis_main/analysis/ring_correspondence_20261007.py'))

def structural_distance(points_a,points_b):
    out=dict(structure_bound_cyclic_deg=None,structure_available=False,structure_reason='',structure_same_pair_count=False,
        bound_cyclic_shift=None,bound_cyclic_shift_margin_deg=None)
    if points_a is None or points_b is None:out['structure_reason']='missing_connected_points';return out
    a,b=np.asarray(points_a,float),np.asarray(points_b,float)
    if len(a)!=len(b):out['structure_reason']='different_pair_count';return out
    out['structure_same_pair_count']=True
    if len(a)<6:out['structure_reason']='below_three_pairs';return out
    cost=np.maximum(angular(a[::2],b[::2]),angular(a[1::2],b[1::2]));dist,shift,margin=cyclic(cost)
    out.update(structure_bound_cyclic_deg=dist,structure_available=True,bound_cyclic_shift=shift,bound_cyclic_shift_margin_deg=margin)
    return out

def empty_summary(k):
    return dict(k=k,parity=k%2,nodes=None,below_four=None,half_vote_nodes=None,connection_available=False,order_status='fusion_exception',
        order_tied=None,geometry_status='not_evaluable',geometry_reason='fusion_exception',floor_evaluable=False,complete_floor_evaluable=False,
        complete_evaluable=False,location_unresolved=None)

def original_pairs(pool):
    rows=pool['records'];polygons=[footprint(reconstruct(r,coordinate_convention='continuous')['floor']) for r in rows]
    valid=[p for p in polygons if p is not None];union=unary_union(valid).area if valid else None;result={}
    for i,j in combinations(range(len(rows)),2):
        result[tuple(sorted((rows[i]['id'],rows[j]['id'])))]=polygons[i].symmetric_difference(polygons[j]).area if polygons[i] is not None and polygons[j] is not None else None
    return result,union,len(valid)

def compute_score(state,pool,engine,models):
    ref=pool['reference'];raw=measured(engine,state,dict(floor=ref['floor_xz_h'],points=ref['points_1024x512']))
    dual=dual_scores(raw,models) if finite(raw,COMPONENTS) else dict(B8L2=None,D10=None)
    return clean(dict(raw,B8L2=dual['B8L2'],D10=dual['D10']))

def time_fields(selected,prefix,key):
    values=[number(r.get(key)) for r in selected];known=[v for v in values if v is not None]
    return {prefix+'_known_n':len(known),prefix+'_missing_n':len(values)-len(known),
        prefix+'_known_sum_seconds':sum(known) if known else None,prefix+'_total_seconds':sum(known) if len(known)==len(values) else None}

def validate_requests(payload,pools):
    lookup={p['pool_id']:p for p in pools};requests=payload['requests'];rids={r['request_id']:r for r in requests}
    assert len(rids)==len(requests),'duplicate_request_id'
    for r in requests:
        p=lookup[r['pool_id']];ws=r['worker_ids'];allowed={x['worker_id']:x for x in p['records']}
        assert len(set(ws))==len(ws) and set(ws)<=allowed.keys() and len(ws)==r['k'],'invalid_real_members'
        for field in ('reference_id','reference_version'):
            if field in r:assert r[field]==p['meta'][field],'request_reference_mismatch'
        if 'ordered_object_ids' in r:assert r['ordered_object_ids']==[allowed[w]['object_id'] for w in ws]
        if 'background_worker_ids' in r:
            assert set(r['background_worker_ids'])==set(ws)-{r['entrant_worker_id']} and len(r['background_worker_ids'])==len(ws)-1
    for p in payload.get('paths',[]):
        assert len(p['worker_order'])==len(p['request_ids']) and len(set(p['worker_order']))==len(p['worker_order'])
        for k,rid in enumerate(p['request_ids'],1):assert rids[rid]['worker_ids']==p['worker_order'][:k]
    return rids

def run_pool(pool,requests):
    started=time.monotonic();target=OUT/'pools'/pool['pool_id'];target.mkdir(parents=True,exist_ok=True)
    current_context=context(pool);ctxfile=target/'context.json';states={};scores={};old_results={};old_requests={}
    if ctxfile.exists():
        assert read(ctxfile)==current_context,'cache_context_changed'
        for row in read(target/'states.json.gz')['states']:states[row['subset']]=row['automatic']
        # The score cache duplicates fields in request_results and may be omitted
        # from the delivery archive. Existing request results remain unchanged;
        # a newly requested subset is remeasured from its saved exact state.
        scores=read(target/'scores.json.gz')['scores'] if (target/'scores.json.gz').exists() else {}
        old_results={r['request_id']:r for r in read(target/'request_results.json.gz')['results']}
        old_requests={r['request_id']:r for r in read(target/'requests.json.gz')['requests']}
    initial_states=set(states);by_worker={r['worker_id']:r for r in pool['records']};rawpairs,union,validpoly=original_pairs(pool)
    computed=0;new_scores=0;fusion_s=score_s=0.;exceptions=[];new_results=[]
    with cached_matching(),scoring_engine(ENGINE/'measurement_engine.zip',ENGINE/'working_models.py') as (engine,models):
        for req in requests:
            rid=req['request_id']
            if rid in old_results:
                assert req==old_requests[rid],'request_definition_changed';continue
            selected=[by_worker[w] for w in sorted(req['worker_ids'])];ids=[r['id'] for r in selected];key=subset_id(ids);tid=team_id(pool['pool_id'],ids)
            if key not in states:
                t=time.monotonic()
                try:states[key]=compact(fuse(selected,gap=WORKING_GAP)['automatic'])
                except (ValueError,ArithmeticError,RuntimeError,TypeError) as e:
                    states[key]=None;exceptions.append(dict(request_id=rid,stage='fusion',error=type(e).__name__+':'+str(e)))
                fusion_s+=time.monotonic()-t;computed+=1
            state=states[key]
            if state is None:summary=empty_summary(len(ids))
            else:
                assert {m['id'] for g in state['identity_groups'] for m in g['members']}==set(ids) and state['n']==len(ids),'actual_members_changed'
                summary=summarize_state(state)
            if key not in scores:
                t=time.monotonic()
                if state is None:scores[key]=dict(score_status='fusion_exception',B8L2=None,D10=None)
                else:
                    try:scores[key]=compute_score(state,pool,engine,models)
                    except (ValueError,ArithmeticError,RuntimeError,TypeError) as e:
                        scores[key]=dict(score_status='measurement_exception',B8L2=None,D10=None,reasons=type(e).__name__+':'+str(e))
                        exceptions.append(dict(request_id=rid,stage='measurement',error=scores[key]['reasons']))
                score_s+=time.monotonic()-t;new_scores+=1
            score=scores[key];assert (score['B8L2'] is None)==(score['D10'] is None)
            vals=[rawpairs[tuple(sorted(ij))] for ij in combinations(ids,2)];known=[v for v in vals if v is not None]
            reqmeta={k:v for k,v in req.items() if not isinstance(v,(list,dict)) and k not in ('pool_id','k')}
            if 'seed' in reqmeta:
                reqmeta['seed_decimal']=str(reqmeta['seed']);reqmeta['seed_hex']=hex(int(reqmeta['seed']))
            poolmeta={('pool_'+k if k in ('source_time_known_n','target_time_known_n') else k):v for k,v in pool['meta'].items()}
            row=dict(reqmeta,**poolmeta,data_release='v2',team_id=tid,subset=key,member_records=key,member_object_ids=key,
                member_workers='|'.join(sorted(req['worker_ids'])),ordered_workers='|'.join(req['worker_ids']),
                ordered_object_ids='|'.join(by_worker[w]['object_id'] for w in req['worker_ids']),
                **summary,**time_fields(selected,'source_time','source_time_seconds'),**time_fields(selected,'target_time','target_time_seconds'),
                member_old_n=sum(r['origin']=='v1' for r in selected),member_new_n=sum(r['origin']=='new' for r in selected),
                time_source_kinds='|'.join(sorted({r['time_source_kind'] for r in selected if r['source_time_seconds'] is not None})),
                **score,reference_pair_count=len(pool['reference']['points_1024x512'])//2,
                reference_node_shortfall=max(0,len(pool['reference']['points_1024x512'])//2-summary['nodes']) if summary['nodes'] is not None else None,
                R_valid_pairs=len(known),R_possible_pairs=len(vals),R_pool_valid_polygons=validpoly,R_normalization_union_area=union,
                R_symdiff_h2=float(np.mean(known)) if known else None,R_union_normalized=float(np.mean(known))/union if known and union else None,
                geometry_state_pointer=f'pools/{pool["pool_id"]}/states.json.gz#{tid}',quality_admitted_members=True)
            for origin in ('v1','new'):
                relevant=[r for r in selected if r['origin']==origin]
                row.update(time_fields(relevant,'source_'+origin,'source_time_seconds'))
            if state is not None:
                node_support=[x['support']/state['n'] for x in state['node_consensus']['nodes']]
                row.update(selected_node_support_mean=float(np.mean(node_support)) if node_support else None,
                    selected_node_support_min=min(node_support) if node_support else None,
                    identity_group_n=len(state['identity_groups']),nonselected_group_n=sum(not g['selected'] for g in state['identity_groups']),
                    minority_observations_n=sum(g['support'] for g in state['identity_groups'] if not g['selected']))
            new_results.append(clean(row));old_requests[rid]=req
    all_results=[*old_results.values(),*new_results]
    save_gz(target/'states.json.gz',dict(pool_id=pool['pool_id'],context=current_context,
        states=[dict(team_id=team_id(pool['pool_id'],key.split('|')),subset=key,automatic=states[key]) for key in sorted(states)]))
    save_gz(target/'scores.json.gz',dict(scores=scores));save_gz(target/'request_results.json.gz',dict(results=all_results))
    save_gz(target/'requests.json.gz',dict(requests=list(old_requests.values())));csv(target/'team_results.csv',all_results)
    save(target/'context.json',current_context)
    receipt=dict(pool_id=pool['pool_id'],requested_now=len(requests),new_request_rows=len(new_results),all_request_rows=len(all_results),
        unique_teams=len(states),new_fusions=computed,new_scores=new_scores,reused_unique_teams=len(set(states)&initial_states),
        score_available=sum(r['B8L2'] is not None for r in all_results),N2_policy_deferred=sum(r['k']==2 for r in all_results),
        other_score_missing=sum(r['k']!=2 and r['B8L2'] is None for r in all_results),
        exceptions=exceptions,fusion_seconds=fusion_s,score_seconds=score_s,total_seconds=time.monotonic()-started)
    save(target/'LAST_RUN.json',receipt)
    return receipt

def consolidate():
    rows=[];requests=[];pool_receipts=[]
    for target in sorted((OUT/'pools').glob('*')):
        if not (target/'context.json').exists():continue
        rows.extend(read(target/'request_results.json.gz')['results']);requests.extend(read(target/'requests.json.gz')['requests'])
        pool_receipts.append(read(target/'LAST_RUN.json'))
    assert len({r['request_id'] for r in rows})==len(rows)
    csv(OUT/'team_results.csv',rows);save_gz(OUT/'ALL_REQUESTS.json.gz',dict(requests=requests))
    csv(OUT/'pool_run_receipts.csv',pool_receipts)
    save(OUT/'CURRENT_COVERAGE.json',dict(request_rows=len(rows),unique_teams=len({r['team_id'] for r in rows}),
        pools=len({r['pool_id'] for r in rows}),images=len({r['image_id'] for r in rows}),buildings=len({r['building'] for r in rows}),
        quality_available=sum(r['B8L2'] is not None for r in rows),N2_policy_deferred=sum(r['k']==2 for r in rows),
        other_quality_missing=sum(r['k']!=2 and r['B8L2'] is None for r in rows),families=dict(Counter(r['request_family'] for r in rows))))
    return rows

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--requests',type=Path,default=OUT/'REQUESTS_INITIAL.json.gz')
    parser.add_argument('--jobs',type=int,default=3);parser.add_argument('--pilot',action='store_true');parser.add_argument('--pool',action='append')
    parser.add_argument('--consolidate-only',action='store_true');args=parser.parse_args()
    if args.consolidate_only:consolidate();return
    payload=read(args.requests);pools=load_pools();validate_requests(payload,pools);file_hash=sha(args.requests)
    wanted=set(args.pool) if args.pool else set(read(OUT/'DESIGN.json')['pilot_pool_ids']) if args.pilot else None
    bypool=defaultdict(list)
    for r in payload['requests']:
        if wanted is None or r['pool_id'] in wanted:bypool[r['pool_id']].append(r)
    pools=[p for p in pools if p['pool_id'] in bypool];start=time.monotonic();done=[]
    if args.jobs==1:
        for p in pools:
            row=run_pool(p,bypool[p['pool_id']]);done.append(row);print(json.dumps(row,ensure_ascii=False),flush=True)
    else:
        with ProcessPoolExecutor(max_workers=args.jobs) as executor:
            futures={executor.submit(run_pool,p,bypool[p['pool_id']]):p['pool_id'] for p in pools}
            for future in as_completed(futures):
                row=future.result();done.append(row)
                print(json.dumps(dict(completed=len(done),total=len(pools),pool_id=row['pool_id'],new_fusions=row['new_fusions'],
                    elapsed_seconds=round(time.monotonic()-start,2),pool_seconds=round(row['total_seconds'],2))),flush=True)
    assert sha(args.requests)==file_hash,'request_manifest_changed_during_execution'
    rows=consolidate();receipt=dict(request_file=str(args.requests.relative_to(OUT)) if args.requests.is_relative_to(OUT) else str(args.requests),
        request_file_sha256=file_hash,git_commit=COMMIT,jobs=args.jobs,pilot=args.pilot,pools=len(pools),
        actual_new_fusions=sum(x['new_fusions'] for x in done),actual_new_scores=sum(x['new_scores'] for x in done),
        actual_new_request_rows=sum(x['new_request_rows'] for x in done),exceptions=sum(len(x['exceptions']) for x in done),
        all_members_verified=True,no_GT_in_fusion=True,no_additional_point_preprocessing=True,N1_applied=False,
        elapsed_seconds=time.monotonic()-start,by_pool=done)
    name=('PILOT_' if args.pilot else '')+'RUN_'+file_hash[:12]+'.json';save(OUT/name,receipt)
    print(json.dumps({k:v for k,v in receipt.items() if k!='by_pool'},ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':main()
