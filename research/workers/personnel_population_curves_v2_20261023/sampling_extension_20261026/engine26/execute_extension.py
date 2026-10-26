"""Execute registered exact teams with the inherited, unmodified native engine.

Only scheduling, state labels and retention are added. Each task reads one pool,
commits bounded gzip parts, and writes its completion receipt last. Empty request
pools also receive receipts. Existing cache rows are never recalculated here.
"""
from __future__ import annotations
import argparse, collections, csv, gzip, hashlib, importlib.util, io, json, math, os
from pathlib import Path
import resource, sys, time
from concurrent.futures import ProcessPoolExecutor, as_completed

CURRENT_COMMIT='b9bcec809fbaec8ab055931a1abb7baa5db44dac'
FIXED_RAW={'VFuaQ6m2Qom-04','wc2JMjhGNzB-46','rPc6DW4iMge-06'}
NATIVE=None

def init_native(base):
    global NATIVE
    if NATIVE is not None:return NATIVE
    home=Path(base)/'prior_recovered/research/workers/personnel_population_curves_v2_20261023/sampling_precision_20261025/engine'
    os.environ['HOHONET_FROZEN_ENGINE_HOME']=str(home)
    os.environ['HOHONET_NATIVE_REPOSITORY']=str(home/'frozen_repo')
    for v in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'):os.environ[v]='1'
    spec=importlib.util.spec_from_file_location('inherited_native_population_runner',home/'native_population_runner.py')
    NATIVE=importlib.util.module_from_spec(spec);sys.modules[spec.name]=NATIVE;spec.loader.exec_module(NATIVE)
    return NATIVE

def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def readcsv(p):
    with gzip.open(p,'rt',encoding='utf-8-sig',newline='') as f:yield from csv.DictReader(f)
def js(p):return json.loads(Path(p).read_text())

def atomic_bytes(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_name(path.name+'.writing')
    fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o644)
    try:
        view=memoryview(data);offset=0
        while offset<len(view):
            n=os.write(fd,view[offset:offset+1024*1024])
            if not n:raise IOError('Zero-byte write')
            offset+=n
        os.fsync(fd)
    finally:os.close(fd)
    tmp.replace(path)

def savejson(path,obj):atomic_bytes(path,json.dumps(obj,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False).encode())
def save_csv(path,rows):
    fields=sorted(set().union(*(r.keys() for r in rows)))
    s=io.StringIO(newline='');w=csv.DictWriter(s,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(rows)
    atomic_bytes(path,gzip.compress(s.getvalue().encode('utf-8-sig'),compresslevel=4,mtime=0))
    with gzip.open(path,'rt',encoding='utf-8-sig',newline='') as f:
        rd=csv.reader(f);h=next(rd);n=0
        for r in rd:
            if len(r)!=len(h):raise ValueError('CSV width mismatch')
            n+=1
    assert n==len(rows)
    return len(fields)
def save_jsonl(path,rows):
    payload=b''.join((json.dumps(r,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode() for r in rows)
    atomic_bytes(path,gzip.compress(payload,compresslevel=4,mtime=0))
    with gzip.open(path,'rt') as f:
        n=sum(1 for line in f if json.loads(line) is not None)
    assert n==len(rows)

def truth(v):return v is True or str(v).lower()=='true'
def finite(v):
    try:return v not in ('',None) and math.isfinite(float(v))
    except (ValueError,TypeError):return False

def state_fields(r,executed=True):
    """Explicit categories alongside every unchanged native status and flag."""
    k=int(r['k']);s=r.get('score_status','');q=finite(r.get('B8L2'))
    if not executed:state='not_executed'
    elif k==2 or s=='two_person_deferred':state='design_deferred_k2'
    elif q:state='scored'
    elif s=='fusion_exception':state='fusion_exception'
    elif s=='below_four':state='consensus_incomplete_below_four'
    elif s=='no_connection':state='consensus_not_connected'
    elif s in ('floor_only_reference','missing_reference'):state='reference_unavailable'
    elif s=='measurement_exception':state='measurement_exception'
    elif s in ('invalid_floor','invalid_full_geometry'):state='generated_geometry_unscorable'
    else:state='other_unscored'
    # Native "invalid_floor" is retained separately from failure to form a ring.
    return dict(endpoint_execution='executed' if executed else 'not_executed',endpoint_state=state,
        actual_consensus_failure=state in ('fusion_exception','consensus_incomplete_below_four','consensus_not_connected'),
        output_generated_unscorable=state in ('generated_geometry_unscorable','measurement_exception'),
        reference_unavailable=state=='reference_unavailable',score_available=q,
        policy_deferred=(k==2),unscored_nonpolicy=(executed and k!=2 and not q),
        status_definition_version='population_extension_20261026_v1')

def keep_full(pool,key):
    image=pool['meta'].get('image_id') or pool['meta'].get('image')
    # image and image_id have different historical formats, inspect both.
    fixed=any(any(x in str(pool['meta'].get(f,'')) for f in ('image','image_id')) for x in FIXED_RAW)
    return fixed or int(hashlib.sha256(key.encode()).hexdigest(),16)%200==0

def write_part(folder,stage,num,rows,pool_hash,request_hash,native):
    stem=f'part_{num:05d}';sc=folder/(stem+'.scalars.csv.gz');ge=folder/(stem+'.geometry_compact.jsonl.gz');raw=folder/(stem+'.full_state.jsonl.gz')
    rel=Path('new_endpoints26')/f'stage{stage}'/'parts'/rows[0]['pool_id']
    compact=[];rawrows=[]
    for line,r in enumerate(rows,1):
        r['geometry_shard']=str(rel/ge.name);r['geometry_line_1based']=line;r['geometry_state_pointer']=str(rel/ge.name)+'#L'+str(line)
        if 'full_state' in r:
            rawrows.append(dict(team_key=r['team_key'],pool_id=r['pool_id'],k=r['k'],pool_input_sha256=pool_hash,full_state=r['full_state']))
            r['full_state_pointer']=str(rel/raw.name)+'#L'+str(len(rawrows));r['full_state_retained']=True
        else:r['full_state_pointer']='';r['full_state_retained']=False
        keys=('team_key','pool_id','k','score_status','score_available','complete_evaluable','complete_floor_evaluable','reference_id','reference_version','pool_input_sha256','minimum_support','node_supports','geometry','full_state_pointer','endpoint_state','actual_consensus_failure','output_generated_unscorable')
        compact.append({k:r.get(k) for k in keys})
    cols=save_csv(sc,[native.scalar_row(r) for r in rows]);save_jsonl(ge,compact)
    if rawrows:save_jsonl(raw,rawrows)
    receipt=dict(part=num,rows=len(rows),pool_id=rows[0]['pool_id'],stage=stage,pool_input_sha256=pool_hash,request_sha256=request_hash,
        scalar_file=sc.name,scalar_sha256=sha(sc),scalar_bytes=sc.stat().st_size,scalar_columns=cols,
        geometry_file=ge.name,geometry_sha256=sha(ge),geometry_bytes=ge.stat().st_size,
        full_state_file=raw.name if rawrows else None,full_state_sha256=sha(raw) if rawrows else None,
        full_state_bytes=raw.stat().st_size if rawrows else 0,full_state_rows=len(rawrows),
        team_keys=[r['team_key'] for r in rows],score_status_counts=dict(collections.Counter(r.get('score_status') for r in rows)),
        endpoint_state_counts=dict(collections.Counter(r['endpoint_state'] for r in rows)),
        native_evaluation_seconds=sum(r['native_evaluation_wall_seconds'] for r in rows),all_tables_read_to_EOF=True)
    savejson(folder/(stem+'.receipt.json'),receipt)
    return receipt

def compute_pool(payload):
    base,pid,stage,chunk=payload;base=Path(base);native=init_native(base);pools=native.gs.pool_lookup();pool=pools[pid]
    fixed_raw_pool=any(any(x in str(pool['meta'].get(f,'')) for f in ('image','image_id')) for x in FIXED_RAW)
    effective_chunk=min(chunk,50) if fixed_raw_pool else chunk
    request=base/'design26/requests_by_pool'/f'stage{stage}'/(pid+'.csv.gz')
    requests=list(readcsv(request)) if request.exists() else [];request_hash=sha(request) if request.exists() else digest([])
    pool_hash=native.gs.digest(pool);wanted={r['team_key']:r for r in requests};assert len(wanted)==len(requests)
    folder=base/'new_endpoints26'/f'stage{stage}'/'parts'/pid;folder.mkdir(parents=True,exist_ok=True)
    saved=set();receipts=[]
    for f in sorted(folder.glob('part_*.receipt.json')):
        r=js(f);assert r['request_sha256']==request_hash and r['pool_input_sha256']==pool_hash
        for field,hfield in [('scalar_file','scalar_sha256'),('geometry_file','geometry_sha256'),('full_state_file','full_state_sha256')]:
            if r.get(field):assert sha(folder/r[field])==r[hfield]
        keys=set(r['team_keys']);assert not(keys&saved) and keys<=wanted.keys() and len(keys)==r['rows'];saved.update(keys);receipts.append(r)
    pending=[r for r in requests if r['team_key'] not in saved];initial=len(saved);t=time.monotonic()
    if not pending and (folder/'POOL_RECEIPT.json').exists():return js(folder/'POOL_RECEIPT.json')
    if pending:
        with native.FrozenNativeEngine(full_state=False) as engine:
            engine.reset_pool();rows=[];part=len(receipts)+1
            for req in pending:
                ws=req['member_workers'].split('|');assert native.gs.team_key(pid,ws)==req['team_key']
                engine.engine.full_state=keep_full(pool,req['team_key'])
                row=engine.evaluate(pool,ws)
                assert row['team_key']==req['team_key'] and row['pool_input_sha256']==pool_hash
                assert set(row['member_object_ids'])==set(req['member_object_ids'].split('|'))
                row.update(state_fields(row));row.update(repository_commit=CURRENT_COMMIT,
                    endpoint_origin='new_wholecurve_extension_native_20261026',execution_stage=stage,
                    inherited_adapter_source_commit='40d0fe62dc62f6f6c12723af10195b7abb7bc9fe',
                    native_request_sha256=request_hash)
                rows.append(row)
                if len(rows)>=effective_chunk:
                    receipts.append(write_part(folder,stage,part,rows,pool_hash,request_hash,native));part+=1;rows=[]
            if rows:receipts.append(write_part(folder,stage,part,rows,pool_hash,request_hash,native))
    states=collections.Counter();native_states=collections.Counter()
    for r in receipts:states.update(r['endpoint_state_counts']);native_states.update(r['score_status_counts'])
    total=sum(r['rows'] for r in receipts);assert total==len(requests)
    result=dict(pool_id=pid,stage=stage,requested_unique=len(requests),completed_unique=total,new_this_invocation=total-initial,
        all_cache_hit=(len(requests)==0),pool_input_sha256=pool_hash,request_sha256=request_hash,
        completed=True,parts=len(receipts),endpoint_state_counts=dict(states),score_status_counts=dict(native_states),
        native_evaluation_seconds=sum(r['native_evaluation_seconds'] for r in receipts),invocation_seconds=time.monotonic()-t,
        full_state_rows=sum(r['full_state_rows'] for r in receipts),scalar_bytes=sum(r['scalar_bytes'] for r in receipts),
        compact_geometry_bytes=sum(r['geometry_bytes'] for r in receipts),full_state_bytes=sum(r['full_state_bytes'] for r in receipts),
        max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,effective_chunk_size=effective_chunk,all_parts_read_to_EOF=True)
    savejson(folder/'POOL_RECEIPT.json',result);return result

def run(base,stage,jobs=6,chunk=250):
    from prefix_outputs import compile_pool,consolidate_stage
    start=time.monotonic();plan=list(csv.DictReader((base/'design26/POOL_SAMPLING_PLAN.csv').open(encoding='utf-8-sig')))
    plan.sort(key=lambda r:(-int(r[f'stage{stage}_new_endpoints']),r['pool_id']))
    out=base/'new_endpoints26'/f'stage{stage}';out.mkdir(parents=True,exist_ok=True)
    tasks=[(str(base.resolve()),r['pool_id'],stage,chunk) for r in plan];done=[]
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        futures={ex.submit(compute_pool,x):x[1] for x in tasks}
        for f in as_completed(futures):
            r=f.result();done.append(r)
            compile_pool(base,r['pool_id'],stage)
            print(json.dumps(dict(pool_id=r['pool_id'],done=len(done),pools=len(plan),new_unique=r['completed_unique'],seconds=round(time.monotonic()-start,1),pool_seconds=round(r['invocation_seconds'],1)),ensure_ascii=False),flush=True)
    receipt=dict(stage=stage,pools=len(done),requested_unique=sum(int(x[f'stage{stage}_new_endpoints']) for x in plan),completed_unique=sum(x['completed_unique'] for x in done),
        jobs=jobs,chunk_size=chunk,seconds=time.monotonic()-start,pool_receipts=done)
    assert receipt['requested_unique']==receipt['completed_unique'];savejson(out/'RUN_RECEIPT.json',receipt)
    consolidate_stage(base,stage)
    print(json.dumps({k:v for k,v in receipt.items() if k!='pool_receipts'},ensure_ascii=False),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--base',type=Path,required=True);ap.add_argument('--stage',type=int,choices=[1,2],required=True);ap.add_argument('--jobs',type=int,default=6);ap.add_argument('--chunk-size',type=int,default=250);a=ap.parse_args();run(a.base,a.stage,a.jobs,a.chunk_size)
