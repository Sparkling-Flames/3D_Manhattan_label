"""Register independent complete permutations, paired policies and exact margins.

This script does not read target quality when generating orders or choosing
members.  The focus list was fixed from old-sample Monte Carlo noise before
generating any new orders.  Old scalar records are inspected only for exact
endpoint reuse and binding checks after the full design is generated.
"""
from __future__ import annotations
import argparse, csv, gzip, hashlib, itertools, json, math
from pathlib import Path
import numpy as np
import pandas as pd

MASTER_SEED = 2026102501
NAMESPACE = 'population_precision_20261025'
COMMIT = '40d0fe62dc62f6f6c12723af10195b7abb7bc9fe'
POLICIES = ['structure_moreturn_first','structure_dominant_first','joint_highq_first','joint_fast_first']


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',',':')).encode()).hexdigest()


def filehash(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def seed_for(pool_id, new_index):
    raw=json.dumps([NAMESPACE, MASTER_SEED, pool_id, int(new_index)],separators=(',',':')).encode()
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], 'little')


def team_key(pool_id, workers):return pool_id+'__'+digest(sorted(workers))[:20]


def read_json(path):
    with gzip.open(path,'rt',encoding='utf-8-sig') as f:return json.load(f)


def save_csv(path, rows):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    pd.DataFrame(rows).to_csv(path,index=False,compression={'method':'gzip','mtime':0} if path.suffix=='.gz' else None)


def register(repo, focus_path, out, benchmark):
    src=repo/'research/workers/personnel_population_curves_v2_20261023'
    snapshot=read_json(src/'inputs/INPUT_SNAPSHOT.json.gz')
    pools={p['pool_id']:p for p in snapshot['images'] if p['meta']['layer'] in ('ordinary_manual','doorway_manual')}
    assert len(pools)==194
    focus=pd.read_csv(focus_path)
    focus=focus.set_index('pool_id')
    assert set(focus.index)==set(pools)
    old=pd.read_csv(src/'design/EXACT_ORDER_DESIGN.csv.gz',keep_default_na=False)
    op=old[(old.layer=='ordinary_manual')&(old.pool_n>=20)&old.policy.isin(POLICIES)]
    capacities=op.groupby('pool_id').policy.nunique()
    policy_pools=set(capacities[capacities==len(POLICIES)].index)
    assert len(policy_pools)==157
    role_first=op.drop_duplicates(['pool_id','policy']).set_index(['pool_id','policy'])
    for key,g in op.groupby(['pool_id','policy']):
        for col in ('target_members','target_class','method','tier'):
            assert g[col].nunique()==1,(key,col)
    orders=[];links=[];wanted={};exact=[];poolrows=[]
    poolhashes={pid:digest(pool) for pid,pool in pools.items()}
    poolworkers={pid:{r['worker_id']:r for r in pool['records']} for pid,pool in pools.items()}
    def endpoint(pool,workers,purpose):
        ws=sorted(workers);pid=pool['pool_id'];key=team_key(pid,ws)
        if key not in wanted:
            own=poolworkers[pid]
            wanted[key]=dict(pool['meta'],team_key=key,n=len(ws),k=len(ws),
                member_workers='|'.join(ws),member_object_ids='|'.join(own[w]['object_id'] for w in ws),
                pool_input_sha256=poolhashes[pid],requested_natural=False,requested_policy=False,requested_exact=False)
        wanted[key]['requested_'+purpose]=True
        return key
    def add_order(pool,row,order,target=()):
        orders.append(row);members=[];target=set(target)
        for k,worker in enumerate(order,1):
            members.append(worker);key=endpoint(pool,members,'natural' if row['policy']=='natural_random' else 'policy')
            links.append({x:row.get(x,'') for x in ('pool_id','path_id','base_path_id','replicate','policy','order_kind','generation','target_capacity','paired_for_policy','target_class','method','tier','sample_kind','batch','new_index','seed','master_seed','sampling_weight_new_batch')}
                |dict(k=k,team_key=key,target_present_n=sum(w in target for w in members),entrant_worker=worker))
    for pid,pool in sorted(pools.items()):
        meta=pool['meta'];workers=sorted(r['worker_id'] for r in pool['records']);N=len(workers)
        fr=focus.loc[pid];extra=int(fr['additional_focus_paths']);assert extra in (0,48)
        nnew=24+extra; poolhash=digest(pool)
        finalhash=hashlib.sha256((pid+'|'+'|'.join(workers)).encode()).hexdigest()[:24]
        oldnatural=old[(old.pool_id==pid)&(old.policy=='natural_random')]
        assert len(oldnatural)==24
        for ni in range(nnew):
            seed=seed_for(pid,ni);order=np.random.default_rng(seed).permutation(workers).tolist()
            base=pid+'__precision_20261025__natural_new'+str(ni).zfill(3)
            batch='balanced_new24' if ni<24 else 'focus_new48'
            row=dict(meta,path_id=base,base_path_id=base,replicate=24+ni,new_index=ni,seed=str(seed),master_seed=str(MASTER_SEED),
                policy='natural_random',workers='|'.join(order),worker_order='|'.join(order),
                order_kind='uniform_without_replacement_within_pool',generation='new_uniform_independent_20261025',
                seed_rule='sha256(JSON([namespace,master_seed,pool_id,new_index])) first8 bytes little-endian; numpy default_rng permutation',
                sample_kind='MC',batch=batch,sampling_weight_new_batch=1/(24 if ni<24 else 48),
                final_pool_hash=finalhash,final_pool_identity='same_actual_full_pool',
                eligible=True,reason='supported',target_capacity=0,paired_for_policy=(pid in policy_pools and ni<8),
                pool_input_sha256=poolhash,repository_commit=COMMIT)
            add_order(pool,row,order)
            if pid in policy_pools and ni<8:
                for policy in POLICIES:
                    rr=role_first.loc[(pid,policy)].to_dict()
                    target=set(str(rr['target_members']).split('|'))
                    assert target and target<set(workers)
                    po=[w for w in order if w in target]+[w for w in order if w not in target]
                    prow=dict(row,policy=policy,path_id=base+'__'+policy,batch='policy_new8',
                        order_kind='stable_target_class_first_from_paired_uniform_base',
                        generation='new_policy_transform_20261025',sampling_weight_new_batch=1/8,
                        target_capacity=len(target),paired_for_policy=True)
                    for col in ('heldout_building','pool_size','method','tier','target_class','selected_family','target_members',
                        'known_members','unknown_members','non_target_capacity','known_capacity','unknown_capacity',
                        'full_pool_class_vector','history_people','history_turn_center','history_short_center',
                        'history_redundancy_center','history_q_center','history_t_center'):
                        prow[col]=rr.get(col,'')
                    add_order(pool,prow,po,target)
        # The exact marginal experiment is kept apart from every random path.
        exact_ks=range(1,N+1) if N<=10 else sorted({1,N-1,N})
        for k in exact_ks:
            kind='small_pool_all_subsets' if N<=10 else ('all_singletons' if k==1 else 'all_leave_one_out' if k==N-1 else 'full_pool_singleton')
            total=math.comb(N,k)
            for ws in itertools.combinations(workers,k):
                key=endpoint(pool,ws,'exact')
                exact.append(dict(meta,team_key=key,k=k,exact_kind=kind,finite_team_space=str(total),
                    marginal_weight=1/total,member_workers='|'.join(ws),pool_input_sha256=poolhash))
        poolrows.append(dict(meta,focus_selected=extra>0,new_natural_paths=nnew,prior_natural_paths=24,
            combined_natural_paths=24+nnew,policy_common_pool=pid in policy_pools,new_paired_policy_bases=8 if pid in policy_pools else 0,
            exact_small_pool=N<=10,pool_input_sha256=poolhash,final_pool_hash=finalhash))
    # Registration persists before expensive cache reads or native calculations.
    save_csv(out/'NEW_EXACT_ORDER_DESIGN.csv.gz',orders)
    save_csv(out/'NEW_PREFIX_TEAM_LINKS.csv.gz',links)
    save_csv(out/'EXACT_MARGINAL_TEAM_DESIGN.csv.gz',exact)
    save_csv(out/'POOL_SAMPLING_PLAN.csv',poolrows)
    save_csv(out/'POLICY_COMMON_POOL_SUPPORT.csv',[r for r in poolrows if r['policy_common_pool']])
    assert len(orders)==len({r['path_id'] for r in orders})
    assert all(sorted(r['worker_order'].split('|'))==sorted(x['worker_id'] for x in pools[r['pool_id']]['records']) for r in orders)
    assert len(links)==len({(r['path_id'],r['k']) for r in links})
    # Existing data are read only AFTER the member design has been saved.
    keys=set(wanted);old_keys=set();bench_keys=set();old_seen=set()
    cachecols=['team_key','pool_id','member_workers','member_object_ids','k','reference_id','reference_version']
    for ch in pd.read_csv(src/'results/ENDPOINT_SCALARS.csv.gz',usecols=cachecols,keep_default_na=False,chunksize=40000):
        for r in ch[ch.team_key.isin(keys)].to_dict('records'):
            w=wanted[r['team_key']]; assert r['team_key'] not in old_seen;old_seen.add(r['team_key'])
            assert sorted(r['member_workers'].split('|'))==w['member_workers'].split('|')
            assert sorted(r['member_object_ids'].split('|'))==sorted(w['member_object_ids'].split('|'))
            assert int(r['k'])==w['n'] and r['pool_id']==w['pool_id']
            assert r['reference_id']==w['reference_id'] and r['reference_version']==w['reference_version']
            w['endpoint_source']='inherited_population_20261023';w['source_table']='research/workers/personnel_population_curves_v2_20261023/results/ENDPOINT_SCALARS.csv.gz'
            old_keys.add(r['team_key'])
    if benchmark.exists():
        bd=pd.read_csv(benchmark,keep_default_na=False)
        for r in bd[bd.team_key.isin(keys-old_keys)].to_dict('records'):
            w=wanted[r['team_key']]
            assert r['pool_input_sha256']==w['pool_input_sha256'] and r['member_workers']==w['member_workers']
            assert r['reference_id']==w['reference_id'] and r['reference_version']==w['reference_version']
            w['endpoint_source']='reused_new_benchmark_20261025';w['source_table']='engine/benchmark/ENDPOINT_SCALARS.csv.gz'
            bench_keys.add(r['team_key'])
    new=[]
    for key,w in wanted.items():
        if key not in old_keys|bench_keys:
            w['endpoint_source']='new_native_required_20261025';w['source_table']='new_endpoints/NEW_ENDPOINT_SCALARS.csv.gz';new.append(w)
    allrows=sorted(wanted.values(),key=lambda r:(r['pool_id'],r['team_key']))
    new.sort(key=lambda r:(r['pool_id'],r['team_key']))
    save_csv(out/'ENDPOINT_DEPENDENCIES.csv.gz',allrows)
    save_csv(out/'NEW_NATIVE_ENDPOINT_REQUESTS.csv.gz',new)
    budget=pd.DataFrame(allrows).groupby(['pool_id','image','building','layer','difficulty','pool_n','endpoint_source']).size().rename('unique_endpoints').reset_index()
    save_csv(out/'EXECUTION_BUDGET_BY_POOL.csv',budget)
    rec=dict(repository_commit=COMMIT,underlying_data='v2',namespace=NAMESPACE,master_seed=str(MASTER_SEED),
        pools=len(pools),ordinary_manual_pools=sum(p['meta']['layer']=='ordinary_manual' for p in pools.values()),
        doorway_manual_pools=sum(p['meta']['layer']=='doorway_manual' for p in pools.values()),focus_pools=sum(r['focus_selected'] for r in poolrows),
        policy_common_pools=len(policy_pools),small_pools=sum(r['exact_small_pool'] for r in poolrows),
        new_orders=len(orders),new_natural_orders=sum(r['policy']=='natural_random' for r in orders),
        new_policy_orders=sum(r['policy']!='natural_random' for r in orders),prefix_links=len(links),
        exact_marginal_links=len(exact),unique_requested_endpoints=len(wanted),inherited_endpoint_reuse=len(old_keys),
        new_benchmark_reuse=len(bench_keys),new_native_required=len(new),
        fullN_unique_teams=len(pools),fullN_new_native=sum(r['n']==r['pool_n'] for r in new),
        source_snapshot_sha256=filehash(src/'inputs/INPUT_SNAPSHOT.json.gz'),focus_preselection_sha256=filehash(focus_path),
        original_design_sha256=filehash(src/'design/EXACT_ORDER_DESIGN.csv.gz'),
        original_scalar_sha256=filehash(src/'results/ENDPOINT_SCALARS.csv.gz'),
        seed_replicate_rule='new_index=0..23 for balanced,24..71 for focus; replicate=24+new_index; policy uses new_index0..7 paired bases',
        weights='Natural new batches uniform within each pool; combine old/new paths with equal path weights, never pool-size weights. Exact margins use uniform distinct-team weight 1/C(N,k) and are not appended as random paths.',
        stopping_rule='Registered finite budget fixed before new quality outcomes. No direction/significance/smoothness stopping.',
        benchmark_note='Timing is separate; old-check recomputations are not counted as new scientific endpoints, only exact request intersections are reused.')
    (out/'DESIGN_RECEIPT.json').write_text(json.dumps(rec,ensure_ascii=False,indent=2))
    print(json.dumps(rec,ensure_ascii=False),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--focus',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--benchmark',type=Path,required=True)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True);register(a.repo,a.focus,a.out,a.benchmark)
