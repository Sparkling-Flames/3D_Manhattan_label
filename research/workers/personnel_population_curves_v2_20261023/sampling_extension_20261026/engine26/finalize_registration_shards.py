"""Commit the frozen exact design in short, independently readable pool shards.

The first global order file passed complete EOF and count checks. All per-pool
native requests also passed. Recover only derived joins from these real files;
seeds, permutations and requested teams are unchanged. Long-open global writer
exports that failed readback are excluded from the authority.
"""
from pathlib import Path
import argparse,collections,csv,gzip,io,itertools,json,os,time
import register_extension as d
from execute_extension import atomic_bytes,save_csv,savejson,state_fields
from prefix_outputs import header,EXTRA

def run(base):
    t=time.monotonic();out=base/'design26';src=base/'repo/research/workers/personnel_population_curves_v2_20261023';snap=d.jsread(src/'inputs/INPUT_SNAPSHOT.json.gz');pools={x['pool_id']:x for x in snap['images'] if x['meta']['layer'] in ('ordinary_manual','doorway_manual')}
    orders=list(d.csvread(out/'NEW_EXACT_ORDER_DESIGN.csv.gz'));assert len(orders)==50400
    by=collections.defaultdict(list)
    for r in orders:by[r['pool_id']].append(r)
    assert set(by)==set(pools);cache={pid:{} for pid in pools};cachecounts=collections.Counter()
    oldsources=[('inherited_population_20261023',base/'inputs_cache26/ENDPOINT_SCALARS_20261023.csv.gz'),('inherited_precision_20261025',base/'inputs_cache26/precision25/NEW_ENDPOINT_SCALARS.csv.gz')]
    for origin,path in oldsources:
        for r in d.csvread(path):
            pid=r['pool_id']
            if pid in cache:
                assert r['team_key'] not in cache[pid];cache[pid][r['team_key']]=origin;cachecounts[origin]+=1
    linkcols=['pool_id','path_id','base_path_id','replicate','policy','order_kind','generation','target_capacity','paired_for_policy','target_class','method','tier','sample_kind','batch','stage','new_index','seed','master_seed','sampling_weight_new_batch','k','team_key','target_present_n','entrant_worker']
    needed_old={};plans=[];budgets=[];parts=[];counts=collections.Counter();poolplans=[]
    for pid in sorted(by):
        pool=pools[pid];own={r['worker_id']:r for r in pool['records']};N=len(own);ph=d.digest(pool);links={1:[],2:[]};wanted={};requests={}
        natural=[r for r in by[pid] if r['policy']=='natural_random'];assert len(natural)==208 and {int(r['new_index']) for r in natural}==set(range(208))
        for r in by[pid]:
            ws=r['worker_order'].split('|');assert set(ws)==set(own) and len(ws)==N and r['workers']==r['worker_order']
            i=int(r['new_index']);assert str(d.seed(pid,i))==r['seed'];stage=1 if i<104 else 2;assert stage==int(r['stage'])
            if r['policy']!='natural_random':assert i<16 and r['base_path_id'] in {x['path_id'] for x in natural}
            target=set(r.get('target_members','').split('|'))-{''}
            for k,w in enumerate(ws,1):
                selected=sorted(ws[:k]);key=d.team(pid,selected)
                link={c:r.get(c,'') for c in linkcols};link.update(k=k,team_key=key,target_present_n=sum(x in target for x in selected),entrant_worker=w);links[stage].append(link)
                if key not in wanted:wanted[key]=dict(pool['meta'],team_key=key,n=k,k=k,member_workers='|'.join(selected),member_object_ids='|'.join(own[x]['object_id'] for x in selected),pool_input_sha256=ph,requested_natural=False,requested_policy=False,requested_stage1=False,requested_stage2=False,first_required_stage=stage)
                dep=wanted[key];dep['requested_natural' if r['policy']=='natural_random' else 'requested_policy']=True;dep[f'requested_stage{stage}']=True;dep['first_required_stage']=min(stage,dep['first_required_stage'])
        for stage in (1,2):
            p=out/'requests_by_pool'/f'stage{stage}'/(pid+'.csv.gz');rr=list(d.csvread(p)) if p.exists() else [];requests[stage]={x['team_key']:x for x in rr};assert len(requests[stage])==len(rr)
            for key,r in requests[stage].items():
                dep=wanted[key];assert key not in cache[pid] and dep['first_required_stage']==stage
                for field in ('member_workers','member_object_ids','pool_input_sha256','reference_id','reference_version'):assert r[field]==str(dep[field])
            lp=out/'links_by_pool'/f'stage{stage}'/(pid+'.csv.gz');save_csv(lp,links[stage]);parts.append(dict(kind='prefix_links',pool_id=pid,stage=stage,file=str(lp.relative_to(base)),rows=len(links[stage]),sha256=d.sha(lp)))
        deps=[];oldkeys=set()
        for key,r in sorted(wanted.items()):
            origin=cache[pid].get(key)
            if origin:
                oldkeys.add(key);r.update(endpoint_source=origin,source_table='inputs_cache26/'+('ENDPOINT_SCALARS_20261023.csv.gz' if origin.endswith('20261023') else 'precision25/NEW_ENDPOINT_SCALARS.csv.gz'))
            else:
                assert key in requests[r['first_required_stage']];assert r['k'] not in (1,N-1,N) and N>10
                r.update(endpoint_source='new_native_required_20261026',source_table='new_endpoints26/stage'+str(r['first_required_stage'])+'/parts/'+pid+'/')
            deps.append(r);counts[r['endpoint_source']]+=1;counts['unique_teams']+=1
        needed_old[pid]=oldkeys
        dp=out/'dependencies_by_pool'/(pid+'.csv.gz');save_csv(dp,deps);parts.append(dict(kind='endpoint_dependencies',pool_id=pid,file=str(dp.relative_to(base)),rows=len(deps),sha256=d.sha(dp)))
        op=out/'orders_by_pool'/(pid+'.csv.gz');save_csv(op,by[pid]);parts.append(dict(kind='orders',pool_id=pid,file=str(op.relative_to(base)),rows=len(by[pid]),sha256=d.sha(op)))
        plan=dict(pool['meta'],new_natural_paths=208,new_stage_paths=104,old_balanced_paths=48,primary_total_paths=256,policy_common_pool=len(by[pid])>208,new_policy_bases=16 if len(by[pid])>208 else 0,primary_policy_total_bases=32 if len(by[pid])>208 else 0,stage1_new_endpoints=len(requests[1]),stage2_new_endpoints=len(requests[2]),pool_input_sha256=ph,all_old_cache_endpoints=len(cache[pid]));plans.append(plan)
        pr=dict(pool_id=pid,new_stage1=len(requests[1]),new_stage2=len(requests[2]),cached_unique=len(oldkeys),total_unique=len(wanted),prefix_stage1=len(links[1]),prefix_stage2=len(links[2]),pool_input_sha256=ph,exact_orders_prefixes_requests_checked=True,all_files_EOF=True)
        savejson(out/'pool_registration_receipts'/(pid+'.json'),pr);poolplans.append(pr)
        counts['prefix_rows']+=len(links[1])+len(links[2]);counts['natural_orders']+=208;counts['policy_orders']+=len(by[pid])-208
        print(json.dumps(dict(pool_id=pid,done=len(plans),pools=len(by),seconds=time.monotonic()-t)),flush=True)
    # Short complete CSV output, not a continuously open global stream.
    ss=io.StringIO(newline='');ww=csv.DictWriter(ss,fieldnames=list(plans[0]),lineterminator='\n');ww.writeheader();ww.writerows(plans);atomic_bytes(out/'POOL_SAMPLING_PLAN.csv',ss.getvalue().encode('utf-8-sig'))
    fields=header(base/'inputs_cache26/precision25/NEW_PREFIX_VALUES_COMPACT.csv.gz');fields+=[x for x in EXTRA if x not in fields]
    cachefields=[x for x in fields if x not in linkcols]+['team_key','pool_id','k'];cacheparts=[];saved=set()
    for origin,path in oldsources:
        for pid,it in itertools.groupby(d.csvread(path),key=lambda r:r['pool_id']):
            rows=[]
            for r in it:
                key=r['team_key']
                if pid in needed_old and key in needed_old[pid]:
                    assert key not in saved;saved.add(key);r.update(state_fields(r));r['endpoint_source']=origin;rows.append({k:r.get(k,'') for k in cachefields})
            if rows:
                part=1+sum(x['pool_id']==pid and x['origin']==origin for x in cacheparts)
                p=base/'inputs_cache26/needed_old_by_pool'/(pid+'__'+origin+'__part'+str(part).zfill(3)+'.csv.gz');save_csv(p,rows);cacheparts.append(dict(pool_id=pid,origin=origin,file=str(p.relative_to(base)),rows=len(rows),sha256=d.sha(p)))
    assert len(saved)==sum(map(len,needed_old.values()))
    runtime=dict(prefix_fields=fields,cache_rows=len(saved),cache_tables=cacheparts,all_CSV_read_to_EOF=True)
    savejson(out/'RUNTIME_INPUT_RECEIPT.json',runtime)
    result=dict(source_commit=d.COMMIT,namespace=d.NAMESPACE,master_seed=str(d.MASTER),data_version='human_v2',pools=len(pools),ordinary_manual=sum(p['meta']['layer']=='ordinary_manual' for p in pools.values()),doorway_manual=sum(p['meta']['layer']=='doorway_manual' for p in pools.values()),natural_per_pool=208,stage_paths=104,policy_pools=sum(len(x)>208 for x in by.values()),policy_bases=16,counts=dict(counts),stage1_new=sum(p['new_stage1'] for p in poolplans),stage2_new=sum(p['new_stage2'] for p in poolplans),parts=parts,seconds=time.monotonic()-t,all_files_EOF=True,derived_joins_rebuilt_from_actual_complete_50400_order_rows=True,failed_global_exports_not_authoritative=True)
    assert result['stage1_new']==784140 and result['stage2_new']==572517 and counts['prefix_rows']==1644576
    savejson(out/'DESIGN_RECEIPT.json',result);savejson(out/'REGISTRATION_RECEIPT.json',result);return result

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--base',type=Path,required=True);a=ap.parse_args();r=run(a.base);print(json.dumps({k:v for k,v in r.items() if k!='parts'}))
