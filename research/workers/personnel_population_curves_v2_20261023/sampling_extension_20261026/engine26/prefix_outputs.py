"""Bounded-memory cache projection and exact prefix/endpoint joining.

All repeated prefix requests remain rows. Endpoint reuse never collapses their
sampling multiplicity. The native scalar files remain the full metric authority.
"""
from pathlib import Path
import argparse,collections,csv,gzip,itertools,json,time
from register_extension import Writer,csvread,sha
from execute_extension import state_fields,savejson

EXTRA=['stage','natural_base_path_id','complete_floor_evaluable','floor_evaluable',
       'endpoint_execution','endpoint_state','actual_consensus_failure','output_generated_unscorable',
       'reference_unavailable','unscored_nonpolicy','status_definition_version','execution_stage',
       'full_state_pointer','full_state_retained','native_evaluation_wall_seconds']

def header(p):
    with gzip.open(p,'rt',encoding='utf-8-sig',newline='') as f:return next(csv.reader(f))

def prepare(base):
    """Prepare from the authoritative exact order/request pool shards.

    Reuse a fully validated completed receipt when present. The former global
    streaming exports are intentionally never referenced by this entry point.
    """
    base=Path(base);path=base/'design26/RUNTIME_INPUT_RECEIPT.json'
    if path.exists():
        r=json.loads(path.read_text());ok=True
        for item in r['cache_tables']:
            p=Path(item['file']);p=p if p.is_absolute() else base/p
            if not p.exists() or sha(p)!=item['sha256']:ok=False;break
        if ok:return r
    from finalize_registration_shards import run
    run(base)
    return json.loads(path.read_text())

def compile_pool(base,pid,stage):
    base=Path(base);receipt=json.loads((base/'design26/RUNTIME_INPUT_RECEIPT.json').read_text());fields=receipt['prefix_fields'];values={}
    cachepaths=[base/x['file'] for x in receipt['cache_tables'] if x.get('pool_id')==pid or Path(x['file']).name.startswith(pid+'__')]
    for cache in sorted(cachepaths):
        for r in csvread(cache):
            assert r['team_key'] not in values
            values[r['team_key']]=r
    for s in range(1,stage+1):
        folder=base/'new_endpoints26'/f'stage{s}'/'parts'/pid
        assert (folder/'POOL_RECEIPT.json').exists(),'Pool native output not committed'
        for file in sorted(folder.glob('part_*.scalars.csv.gz')):
            for r in csvread(file):
                key=r['team_key'];assert key not in values
                r['endpoint_source']=f'new_native_stage{s}_20261026';values[key]=r
    target=base/'new_endpoints26'/f'stage{stage}'/'prefix_values'/(pid+'.csv.gz');rows=[];keys=set();statuses=collections.Counter();policies=collections.Counter()
    for link in csvread(base/'design26/links_by_pool'/f'stage{stage}'/(pid+'.csv.gz')):
        key=link['team_key'];r=dict(values[key]);assert int(float(r['k']))==int(link['k']) and r['pool_id']==pid
        r.update(link);r['natural_base_path_id']=r['base_path_id'];r.update(state_fields(r));rows.append({k:r.get(k,'') for k in fields})
        keys.add(key);statuses[r['endpoint_state']]+=1;policies[r['policy']]+=1
    from execute_extension import save_csv
    cols=save_csv(target,rows)
    result=dict(file=str(target),rows=len(rows),columns=cols,sha256=sha(target),complete_EOF=True,pool_id=pid,stage=stage,unique_teams=len(keys),endpoint_state_counts=dict(statuses),policy_prefix_counts=dict(policies))
    savejson(target.with_suffix('').with_suffix('.receipt.json'),result);return result

def consolidate_stage(base,stage):
    receipt=json.loads((base/'design26/RUNTIME_INPUT_RECEIPT.json').read_text());fields=receipt['prefix_fields'];folder=base/'new_endpoints26'/f'stage{stage}'
    plan=list(csv.DictReader((base/'design26/POOL_SAMPLING_PLAN.csv').open(encoding='utf-8-sig')));pools=[]
    for r in sorted(plan,key=lambda x:x['pool_id']):
        pid=r['pool_id'];p=folder/'prefix_values'/(pid+'.csv.gz')
        if not p.exists():compile_pool(base,pid,stage)
        assert set(header(p))==set(fields)
        n=0
        for row in csvread(p):n+=1
        pools.append(dict(pool_id=pid,rows=n,file=str(p.relative_to(base)),sha256=sha(p)))
    result=dict(stage=stage,pools=pools,rows=sum(x['rows'] for x in pools),columns=sorted(fields),
        storage='Complete logical table partitioned by pool; all actual CSV gzip read to EOF',all_CSV_read_to_EOF=True)
    savejson(folder/'PREFIX_COMPILE_RECEIPT.json',result);return result

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--base',type=Path,required=True);a.add_argument('--prepare',action='store_true');a.add_argument('--stage',type=int,choices=[1,2]);args=a.parse_args()
    if args.prepare:r=prepare(args.base)
    else:r=consolidate_stage(args.base,args.stage)
    print(json.dumps({k:v for k,v in r.items() if k not in ('cache_tables','link_tables','pools')}))
