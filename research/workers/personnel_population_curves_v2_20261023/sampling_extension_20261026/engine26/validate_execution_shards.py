"""Read actual scalar/geometry gzip contents and compare exact registered keys.

Use after extracting a delivery ZIP as well as before packaging. Validation is
per pool, so complete logical tables do not require a long-open global export.
"""
from pathlib import Path
import argparse,collections,csv,gzip,json,time
from execute_extension import readcsv,sha,savejson,save_csv

def readjsonl(p):
    with gzip.open(p,'rt',encoding='utf-8-sig') as f:
        for line in f:yield json.loads(line)

def validate(base,stages=(1,2),allow_partial=False):
    t=time.monotonic();plan=list(csv.DictReader((base/'design26/POOL_SAMPLING_PLAN.csv').open(encoding='utf-8-sig')))
    pools=[];parts=[];states=collections.Counter();fail=[]
    for stage in stages:
        for p in plan:
            pid=p['pool_id'];folder=base/'new_endpoints26'/f'stage{stage}'/'parts'/pid;done=folder/'POOL_RECEIPT.json'
            if not done.exists():
                if allow_partial:continue
                raise FileNotFoundError(done)
            request=base/'design26/requests_by_pool'/f'stage{stage}'/(pid+'.csv.gz');wanted={r['team_key']:r for r in readcsv(request)} if request.exists() else {}
            observed=set();pool_states=collections.Counter();nparts=0
            for rp in sorted(folder.glob('part_*.receipt.json')):
                r=json.loads(rp.read_text());sp=folder/r['scalar_file'];gp=folder/r['geometry_file'];assert sha(sp)==r['scalar_sha256'] and sha(gp)==r['geometry_sha256']
                scalars=list(readcsv(sp));geos=list(readjsonl(gp));assert len(scalars)==len(geos)==r['rows'];assert [x['team_key'] for x in scalars]==r['team_keys']==[x['team_key'] for x in geos]
                for s,g in zip(scalars,geos):
                    key=s['team_key'];assert key not in observed;observed.add(key);q=wanted[key]
                    for field in ('pool_id','member_workers','member_object_ids','reference_id','reference_version','pool_input_sha256'):assert s[field]==q[field],(key,field)
                    assert s['pool_id']==g['pool_id'] and int(s['k'])==int(q['k'])==int(g['k'])
                    assert s['score_status']==g['score_status'];assert s['endpoint_state']==g['endpoint_state'];pool_states[s['endpoint_state']]+=1
                raw_count=0
                if r.get('full_state_file'):
                    raw=folder/r['full_state_file'];assert sha(raw)==r['full_state_sha256']
                    for x in readjsonl(raw):assert x['team_key'] in observed;raw_count+=1
                assert raw_count==r['full_state_rows'];nparts+=1
                parts.append(dict(stage=stage,pool_id=pid,rows=r['rows'],scalar_file=str(sp.relative_to(base)),scalar_sha256=r['scalar_sha256'],geometry_file=str(gp.relative_to(base)),geometry_sha256=r['geometry_sha256'],full_state_rows=raw_count,full_state_file=str((folder/r['full_state_file']).relative_to(base)) if raw_count else '',all_contents_read_to_EOF=True))
            assert observed==wanted.keys();receipt=json.loads(done.read_text());assert receipt['completed_unique']==len(observed)==int(p[f'stage{stage}_new_endpoints'])
            prefix=base/'new_endpoints26'/f'stage{stage}'/'prefix_values'/(pid+'.csv.gz');prefix_keys=set();prefix_count=0
            if prefix.exists():
                for r in readcsv(prefix):
                    key=(r['path_id'],int(r['k']));assert key not in prefix_keys;prefix_keys.add(key);prefix_count+=1
                expected={(r['path_id'],int(r['k'])) for r in readcsv(base/'design26/links_by_pool'/f'stage{stage}'/(pid+'.csv.gz'))};assert prefix_keys==expected
            elif not allow_partial:raise FileNotFoundError(prefix)
            pools.append(dict(stage=stage,pool_id=pid,unique_endpoints=len(observed),native_parts=nparts,prefix_rows=prefix_count,endpoint_state_counts=dict(pool_states)));states.update(pool_states)
    out=base/'new_endpoints26';result=dict(stages=list(stages),allow_partial=allow_partial,pool_stages=len(pools),unique_new_endpoints=sum(r['unique_endpoints'] for r in pools),prefix_rows=sum(r['prefix_rows'] for r in pools),native_part_count=len(parts),endpoint_state_counts=dict(states),pool_receipts=pools,seconds=time.monotonic()-t,all_tables_read_to_EOF=True,all_exact_request_scalar_geometry_keys_joined=True)
    tag='PARTIAL' if allow_partial else 'COMPLETE';savejson(out/(tag+'_EXECUTION_VALIDATION.json'),result)
    if parts:save_csv(out/(tag+'_NEW_ENDPOINT_SHARD_INDEX.csv.gz'),parts)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--stage',type=int,action='append',choices=[1,2]);p.add_argument('--allow-partial',action='store_true');a=p.parse_args();r=validate(a.base,a.stage or (1,2),a.allow_partial);print(json.dumps({k:v for k,v in r.items() if k!='pool_receipts'}))
