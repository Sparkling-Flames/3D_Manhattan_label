"""Read-only geometry diagnostics for each registered matched ABC event."""
from __future__ import annotations
import argparse,collections,math
from global_study import *
from run_endpoints import pool_endpoints

def compute(partial=False,events_path=None):
    events_path=Path(events_path) if events_path else OUT/'ABC_EVENTS.csv.gz'
    events=pd.read_csv(events_path,keep_default_na=False);pools=pool_lookup();fe,fr,sg,corner=setup_engine()
    historical,_,_=existing_cache();rows=[];missing=[];pair_calls=0;memo={};reused_events=0
    contract=digest({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),COMP/'summarize_grid.py',CORNER/'corner_distance.py']})
    checkpoint=OUT/'runtime/geometry_event_shards';checkpoint.mkdir(parents=True,exist_ok=True)
    for pid,g in events.groupby('pool_id',sort=True):
        teams=pool_endpoints(pid,{key:r for key,r in historical.items() if r['pool_id']==pid});signatures={}
        target=checkpoint/(pid+'.csv.gz');receipt=checkpoint/(pid+'.json')
        context=dict(events_sha256=digest(g.to_dict('records')),input_pool_sha256=digest(pools[pid]),diagnostics_contract_sha256=contract)
        pool_rows=[]
        if target.exists() and receipt.exists() and read(receipt)==context:
            pool_rows=[clean(r) for r in pd.read_csv(target,low_memory=False).to_dict('records')]
        seen={r['event_id'] for r in pool_rows};reused_events+=len(seen)
        for r in g.to_dict('records'):
            if r['event_id'] in seen:continue
            keys=[r['team_'+role] for role in 'ABC']
            if any(k not in teams for k in keys):missing.append(r['event_id']);continue
            out={k:r[k] for k in ('event_id','pool_id','image','building','condition','layer','difficulty','method_id','tier','event_mode','n','m_AB','m_AC','m_BC','composition_turnover_AC')}
            for prefix,ia,ib,expected_m in [('within_',0,1,r['m_AB']),('cross_',0,2,r['m_AC']),('net_',1,2,r['m_BC'])]:
                ka,kb=keys[ia],keys[ib];a,b=teams[ka],teams[kb];pair_key=(ka,kb)
                if pair_key not in memo:
                    for key in (ka,kb):
                        if key not in signatures:signatures[key]=sg.signature(teams[key])
                    sa,sb=signatures[ka],signatures[kb];values=sg.pair_metrics(a,b,sa,sb);c,_=corner(a,b)
                    values.update({'corner_'+k:v for k,v in c.items()})
                    if values['mean_height_prism_pair_iou'] is not None:values['mean_height_prism_pair_difference']=1-values['mean_height_prism_pair_iou']
                    pa,pb=sa['floor'],sb['floor']
                    if values['both_complete'] and pa is not None and pb is not None:
                        values['centroid_distance_h']=math.hypot(pb.centroid.x-pa.centroid.x,pb.centroid.y-pa.centroid.y)
                        values['floor_area_abs_log_ratio']=abs(math.log(pb.area/pa.area))
                    memo[pair_key]=values;pair_calls+=1
                values=memo[pair_key]
                if values['turnover']!=expected_m:raise ValueError(('actual replacement mismatch',r['event_id'],prefix,values['turnover'],expected_m))
                out.update({prefix+k:v for k,v in values.items()})
            for metric in ('abs_B8L2_change','abs_D10_change','floor_jaccard_difference','structure_bound_cyclic_deg','mean_height_prism_pair_difference','centroid_distance_h','floor_area_abs_log_ratio','node_count_difference'):
                a,b=out.get('within_'+metric),out.get('cross_'+metric)
                out['cross_minus_within_'+metric]=b-a if a is not None and b is not None else None
            pool_rows.append(clean(out))
        if pool_rows:csv(target,pd.DataFrame(pool_rows));save(receipt,context)
        rows.extend(pool_rows)
    present={r['event_id'] for r in rows}
    all_pairs={(r['team_'+a],r['team_'+b]) for r in events.to_dict('records') if r['event_id'] in present for a,b in [('A','B'),('A','C'),('B','C')]}
    csv(OUT/('ABC_GEOMETRY_PARTIAL.csv.gz' if partial else 'ABC_GEOMETRY.csv.gz'),pd.DataFrame(rows))
    save(OUT/('ABC_GEOMETRY_PARTIAL_RECEIPT.json' if partial else 'ABC_GEOMETRY_RECEIPT.json'),dict(registered_events=len(events),computed_events=len(rows),
        missing_events=len(missing),missing_event_ids=missing,unique_oriented_pairs=len(all_pairs),
        new_oriented_pair_calculations_this_invocation=pair_calls,reused_event_diagnostics=reused_events,
        event_source_sha256=hashlib.sha256(events_path.read_bytes()).hexdigest(),
        comparisons=['A-B within identical full class-count vector','A-C different vector, same shared background and actual m','B-C net contrast, own actual m explicitly retained'],
        source='Existing frozen native endpoint geometry only; no alignment, repair, rescoring or label selection.',
        failure_denominator='All registered events, including native endpoint failure. Corresponding-corner absence is separately encoded, never treated as zero distance.'))
    print(json.dumps(dict(registered_events=len(events),computed_events=len(rows),missing_events=len(missing),unique_pairs=len(all_pairs),new_pair_calculations=pair_calls,reused_events=reused_events)),flush=True)

def export_case(event_id,case_id,full_state=False):
    events=pd.read_csv(OUT/'ABC_EVENTS.csv.gz',keep_default_na=False);found=events[events.event_id==event_id]
    if len(found)!=1:raise ValueError('event identity is not unique')
    event=found.iloc[0].to_dict();pool=pool_lookup()[event['pool_id']];pid=pool['pool_id'];historical,_,_=existing_cache()
    teams=pool_endpoints(pid,{k:r for k,r in historical.items() if r['pool_id']==pid});mapping=method_maps()[event['method_id'],event['tier'],event['condition'],event['building']]
    selected=[dict(teams[event['team_'+x]],label=x) for x in 'ABC'];members=sorted(set.union(*(set(r['member_workers']) for r in selected)))
    by={r['worker_id']:r for r in pool['records']}
    member_rows=[dict(by[w],class_id=mapping[w],footprint=by[w].get('footprint')) for w in members]
    for i,t in enumerate(selected):
        t['counts']={c:sum(mapping[w]==c for w in t['member_workers']) for c in sorted(set(mapping.values()))}
    if full_state:
        fe,fr,sg,_=setup_engine();cache={}
        with fe.cached_matching(),fe.scoring_engine(fe.ENGINE/'measurement_engine.zip',fe.ENGINE/'working_models.py') as (engine,models):
            for t in selected:
                got=fr.evaluate_one(pool,t['member_workers'],engine,models,cache,full_state=True)
                for score in ('B8L2','D10'):
                    a,b=t.get(score),got.get(score)
                    if not ((a is None and b is None) or a is not None and b is not None and math.isclose(a,b,abs_tol=1e-7,rel_tol=1e-10)):raise ValueError('selected-case replay mismatch')
                t['full_state']=got['full_state']
    case=dict(case_id=case_id,title=f"{event['image']} · {event['method_id']} {event['tier']} · n={event['n']}, m={event['m_AB']}",
       subtitle='A/B保持完整类别构成，A/C改变构成；两比较共用同一背景且替换人数相同。B/C净差按自身实际替换人数解释。',
       pool_id=pid,image_id=pool['meta']['image_id'],image=pool['meta']['image'],building=pool['meta']['building'],
       reference=dict(pool['reference'],reference_id=pool['meta']['reference_id'],reference_version=pool['meta']['reference_version']),
       event=event,teams=selected,members=member_rows,label_scope='target_building_excluded',full_state_replayed=full_state)
    target=OUT/'cases'/(case_id+'.json');save(target,case);print(str(target),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--partial',action='store_true');p.add_argument('--events',type=Path);p.add_argument('--event-id');p.add_argument('--case-id');p.add_argument('--full-state',action='store_true');a=p.parse_args()
    if a.event_id:export_case(a.event_id,a.case_id or a.event_id,a.full_state)
    else:compute(a.partial,a.events)
