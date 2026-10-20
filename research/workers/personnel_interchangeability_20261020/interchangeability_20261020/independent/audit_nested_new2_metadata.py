"""Independent all-event identity and all-pool capacity check; no outcomes."""
from pathlib import Path
import collections,hashlib,json,sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'interchangeability_20261020/code'))
from design_history_panel import read,write,team_key
from design_blocks import labels_from,counts

def main():
    base=ROOT/'interchangeability_20261020';path=base/'assessment/nested_new2_requests.json.gz'
    d=read(path); split=read(ROOT/'analysis/composition/SPLIT.json');bs=set(split['validation_buildings'])
    snap=read(ROOT/'restored/work_personnel_typing_A_20261019/recovered/work_v2_20261019/fusion/INPUT_SNAPSHOT.json.gz')
    pools={p['pool_id']:p for p in snap['images'] if p['meta']['building'] in bs and p['meta']['layer']=='ordinary_manual'}
    method=d['spec']['methods'][0]; mapping=labels_from([base/'reverse/mixed_fit/worker_labels.csv.gz'])[method['method_id'],method['domain']]
    ev={e['event_id']:e for e in d['events']};req={q['request_id']:q for q in d['requests']};steps=0;physical=collections.defaultdict(set)
    for p in d['paths']:
        expected=list(range(max(3,p['m']),len([r for r in pools[p['pool_id']]['records'] if r['origin']=='new'])-2*p['m']+1));assert expected==p['feasible_n']
        group=sorted([ev[x] for x in p['event_ids']],key=lambda e:e['n']);assert [e['n'] for e in group]==expected
        order=p['core_order'];old=None
        physical[p['pool_id'],p['outgoing_class'],p['incoming_class'],p['m']].add((tuple(sorted([tuple(sorted(p['outgoing_workers'])),tuple(sorted(p['within_incoming']))])),tuple(sorted(p['cross_incoming']))))
        origins={r['worker_id']:r['origin'] for r in pools[p['pool_id']]['records']}
        for e in group:
            for k in ['outgoing_workers','within_incoming','cross_incoming']:assert e[k]==p[k]
            n,m=e['n'],e['m'];assert set(e['core_workers'])==set(order[:n-m])
            aa,bb,cc=[set(e[k]) for k in ['outgoing_workers','within_incoming','cross_incoming']];core=set(e['core_workers'])
            assert not(aa&bb or aa&cc or bb&cc or core&(aa|bb|cc))
            assert all(mapping[w]==e['outgoing_class'] for w in aa|bb) and all(mapping[w]==e['incoming_class'] for w in cc)
            for arm,block in zip('ABC',[aa,bb,cc]):
                ws=set(e[arm+'_workers']);assert ws==core|block and len(ws)==n and all(origins[w]=='new' for w in ws)
                assert counts(ws,mapping)==e[arm+'_counts']
                tk=team_key(e['pool_id'],list(ws));assert tk==e[arm+'_team_key'];q=req[tk]
                assert q['k']==n and set(q['worker_ids'])==ws and q['reference_id']==e['reference_id']==pools[e['pool_id']]['meta']['reference_id']
                if old is not None:
                    assert ws-set(old[arm+'_workers'])=={e['added_core_worker']}=={order[n-m-1]}
                    assert not(set(old[arm+'_workers'])-ws)
            if old is not None:steps+=1
            old=e
    assert all(len(x)==2 for x in physical.values())
    led={(r['pool_id'],r['outgoing_class'],r['incoming_class'],r['m']):r for r in d['ledger']}
    expectedcells=[];n13=[]
    for pid,p in pools.items():
        ws=[r['worker_id'] for r in p['records'] if r['origin']=='new'];cap=collections.Counter(mapping[w] for w in ws if w in mapping)
        for outgoing,incoming in method['directions']:
            for m in [2,5]:
                cell=(pid,outgoing,incoming,m);expectedcells.append(cell);row=led[cell]
                feasible=(cap[outgoing]>=2*m and cap[incoming]>=m and len(ws)-2*m>=max(3,m))
                ns=list(range(max(3,m),len(ws)-2*m+1)) if feasible else []
                assert row['feasible_n']==ns and row['available_new_n']==len(ws)
                assert row['outgoing_available_n']==cap[outgoing] and row['incoming_available_n']==cap[incoming]
                assert row['n13_feasible']==(len(ws)>=13+2*m and cap[outgoing]>=2*m and cap[incoming]>=m)
                assert row['accepted_paths']==2*int(feasible) and row['accepted_events']==2*len(ns)
                if row['n13_feasible']:n13.append(dict(pool_id=pid,image=p['meta']['image'],building=p['meta']['building'],outgoing=outgoing,incoming=incoming,m=m))
    assert set(expectedcells)==set(led)
    report=dict(schema='independent_nested_new2_metadata_audit_v1',request_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),events=len(ev),unique_teams=len(req),paths=len(d['paths']),adjacent_three_arm_steps=steps,adjacent_arm_steps=steps*3,enumerated_ordinary_assessment_pools=len(pools),capacity_cells=len(led),accepted_pools=len({e['pool_id'] for e in ev.values()}),true_images=len({e['image'] for e in ev.values()}),buildings=len({e['building'] for e in ev.values()}),all_identity_source_reference_count_core_prefix_invariants=True,all_integer_n_given_path_verified=True,all_45_pool_n13_capacity_cells_verified=True,two_physically_distinct_block_draws_per_feasible_cell=True,read_any_native_or_metric_outputs=False,n13_support=[dict(direction=outgoing+'>'+incoming,m=m,pools=len({r['pool_id'] for r in n13 if r['outgoing']==outgoing and r['incoming']==incoming and r['m']==m}),buildings=len({r['building'] for r in n13 if r['outgoing']==outgoing and r['incoming']==incoming and r['m']==m})) for outgoing,incoming in method['directions'] for m in [2,5]],limitations='Only two sampled physical block triples/core orders per feasible capacity cell. All integer n on each path are enumerated, not all team combinations. Increasing n adds a real member and changes composition/threshold jointly; no pure sample-size causal interpretation.')
    write(base/'independent/NESTED_NEW2_METADATA_AUDIT.json',report);print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':main()
