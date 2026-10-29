"""Resume-safe official v2.1 fusion, exact-team cache reuse and complete scalars.

No research label enters the engine. Input snapshots retain target membership,
ring order, quality qualification and reference. Save every 100 new endpoints.
"""
from __future__ import annotations
import os
for v in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[v]='1'
import argparse,collections,csv,gzip,hashlib,importlib.util,json,time,sys
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
import pandas as pd
from capacity_space import read_json,read_labels,canonical_hash
from benchmark_engine import load_engine
from register_adaptive import key,members,write_json

COMMIT='519c7447278dd16c3d69f505b807fb5b53792b36'
def iter_jsonl(path):
    with gzip.open(path,'rt',encoding='utf-8-sig') as f:
        for line in f:
            if line.strip():yield json.loads(line)
def write_jsonl(path,rows):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+'.writing')
    with gzip.open(tmp,'wt',encoding='utf-8',compresslevel=4) as f:
        for r in rows:f.write(json.dumps(r,ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n')
    with tmp.open('rb') as f:os.fsync(f.fileno())
    tmp.replace(p)
def save_frame(path,frame):
    p=Path(path);tmp=p.with_name(p.name+'.writing')
    frame.to_csv(tmp,index=False,encoding='utf-8-sig',compression={'method':'gzip','mtime':0})
    with tmp.open('rb') as f:os.fsync(f.fileno())
    # Stream to EOF once before publishing a complete scalar table.
    with gzip.open(tmp,'rb') as f:
        while f.read(1024*1024):pass
    tmp.replace(p)
def fields_match(row,pool,request):
    if row.get('pool_id')!=pool['pool_id']:return 'pool_id'
    if sorted(members(row.get('member_workers')))!=sorted(members(request['member_workers'])):return 'members'
    for f in ['reference_id','reference_version']:
        if row.get(f)!=pool['meta'][f]:return f
    if 'geometry' not in row:return 'geometry_missing'
    current=row.get('data_release')=='v2.1' or row.get('underlying_data_version')=='v2.1'
    if not current:return 'not_current_v21'
    h=row.get('input_pool_sha256') or row.get('pool_input_sha256')
    if h and h!=canonical_hash(pool):return 'pool_hash'
    expected={r['worker_id']:r['object_id'] for r in pool['records']}
    if row.get('member_object_ids') and sorted(members(row['member_object_ids']))!=sorted(expected[w] for w in members(request['member_workers'])):return 'object_ids'
    return None

def worker(payload):
    repo,pool,requests,output,cache_rows,part_size=payload;native=load_engine(Path(repo));pid=pool['pool_id'];folder=Path(output)/'pools'/pid;folder.mkdir(parents=True,exist_ok=True)
    fingerprint=canonical_hash(pool);wanted={r['team_key']:r for r in requests};done={};part=0
    manifest=folder/'POOL_INPUT.json'
    if manifest.exists():assert read_json(manifest)['pool_input_sha256']==fingerprint
    else:write_json(manifest,dict(pool_id=pid,pool_input_sha256=fingerprint,reference_sha256=canonical_hash(pool['reference']),repository_commit=COMMIT))
    for p in sorted(folder.glob('part_*.jsonl.gz')):
        for r in iter_jsonl(p):
            assert r['team_key'] not in done and not fields_match(r,pool,wanted[r['team_key']])
            done[r['team_key']]=r
        part+=1
    original=len(done);buffer=[];new=0;reused=0;start=time.monotonic()
    def flush():
        nonlocal part
        if not buffer:return
        part+=1;write_jsonl(folder/f'part_{part:05d}.jsonl.gz',buffer);buffer.clear()
        write_json(folder/'PROGRESS.json',dict(pool_id=pid,requested=len(wanted),previous=original,new=new,reused=reused,done=len(done),seconds=time.monotonic()-start))
    for r in cache_rows:
        k=r['team_key']
        if k in done:continue
        assert not fields_match(r,pool,wanted[k])
        r=dict(r,input_pool_sha256=fingerprint,endpoint_reused=True);done[k]=r;buffer.append(r);reused+=1
        if len(buffer)>=part_size:flush()
    flush()
    remaining=[r for k,r in wanted.items() if k not in done]
    if remaining:
        with native.Engine(full_state=False) as engine:
            for req in remaining:
                ws=members(req['member_workers']);assert len(ws)>=3,'Actual two-person results use their separate frozen pipeline.'
                row=engine.evaluate(pool,ws);geometry=row.get('geometry')
                if geometry is not None:
                    result=engine.scorecache.get(engine.fr.digest([row['k']==2,row.get('nodes'),geometry]))
                    if result:row.update(result)
                assert row['team_key']==req['team_key'] and row['k']==int(req['n'])
                row.update(data_release='v2.1',underlying_data_version='v2.1',repository_commit=COMMIT,
                    input_pool_sha256=fingerprint,reference_sha256=canonical_hash(pool['reference']),endpoint_reused=False,
                    endpoint_origin='v21_independent_reaudit_20261029',fusion_quality_contract_unchanged=True)
                row=native.gs.clean(row);done[row['team_key']]=row;buffer.append(row);new+=1
                if len(buffer)>=part_size:flush()
            flush()
    # A scalar shard is complete and independently consumable as soon as a pool finishes.
    scalars=[]
    for r in done.values():
        scalar_input=dict(r)
        # Historical caches also store these fields as pipe-delimited strings.
        for field in ('member_workers','member_object_ids'):
            if isinstance(scalar_input[field],str):scalar_input[field]=scalar_input[field].split('|')
        scalars.append(native.native.scalar_row(scalar_input))
    sdir=Path(output)/'scalar_shards';sdir.mkdir(exist_ok=True)
    save_frame(sdir/(pid+'.csv.gz'),pd.DataFrame(scalars))
    result=dict(pool_id=pid,requested=len(wanted),previous=original,reused=reused,new_native=new,total=len(done),
        quality_available=sum(r.get('B8L2') is not None for r in done.values()),seconds=time.monotonic()-start,complete=set(done)==set(wanted))
    write_json(folder/'CHECKS.json',result);return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--repo',required=True);p.add_argument('--pools',nargs='+',required=True);p.add_argument('--requests',required=True)
    p.add_argument('--output',required=True);p.add_argument('--cache-roots',nargs='*',default=[]);p.add_argument('--cache-files',nargs='*',default=[])
    p.add_argument('--jobs',type=int,default=6);p.add_argument('--part-size',type=int,default=100);a=p.parse_args();out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
    req=read_labels(a.requests);wanted={r['team_key']:r for r in req};assert len(wanted)==len(req)
    pools={r['pool_id']:r for fn in a.pools for r in read_json(fn)['images']};by=collections.defaultdict(list)
    for r in req:
        assert r['team_key']==key(r['pool_id'],members(r['member_workers']));assert len(members(r['member_workers']))==int(r['n']);by[r['pool_id']].append(r)
    start=time.monotonic();cache=collections.defaultdict(dict);reject=collections.Counter();source_receipts=[]
    files=set(Path(x) for x in a.cache_files)
    for root in a.cache_roots:files.update(Path(root).rglob('*.jsonl.gz'))
    for path in sorted(files):
        hits=0
        for r in iter_jsonl(path):
            k=r.get('team_key')
            if k not in wanted:continue
            issue=fields_match(r,pools[wanted[k]['pool_id']],wanted[k])
            if issue:reject[issue]+=1;continue
            pid=r['pool_id']
            if k in cache[pid]:continue
            r=dict(r,cache_source=str(path.resolve()));cache[pid][k]=r;hits+=1
        if hits:source_receipts.append(dict(file=str(path.resolve()),reused_requested_teams=hits))
    write_json(out/'CACHE_COVERAGE.json',dict(requested=len(req),initial_cache_hits=sum(map(len,cache.values())),
        scanned_cache_files=len(files),sources=source_receipts,rejected=dict(reject),cache_identity='target pool + exact members/objects + current reference + v2.1 provenance; pool fingerprint where present'))
    write_json(out/'RUN_PLAN.json',dict(repository_commit=COMMIT,data_release='v2.1',requests_sha256=hashlib.sha256(Path(a.requests).read_bytes()).hexdigest(),
        request_path=str(Path(a.requests).resolve()),source_pools=a.pools,requested=len(req),pools=len(by),jobs=a.jobs,part_size=a.part_size,
        initially_missing=len(req)-sum(map(len,cache.values())),labels_do_not_enter_engine=True))
    results=[]
    with ProcessPoolExecutor(max_workers=a.jobs) as ex:
        futures=[ex.submit(worker,(a.repo,pools[pid],rows,str(out),list(cache[pid].values()),a.part_size)) for pid,rows in sorted(by.items())]
        for f in as_completed(futures):
            result=f.result();results.append(result);write_json(out/'PROGRESS.json',dict(pools=results,wall_seconds=time.monotonic()-start));print(json.dumps(result),flush=True)
    scalar=pd.concat([pd.read_csv(x,low_memory=False) for x in sorted((out/'scalar_shards').glob('*.csv.gz'))],ignore_index=True)
    assert len(scalar)==len(req) and not scalar.team_key.duplicated().any() and set(scalar.team_key)==set(wanted)
    save_frame(out/'ENDPOINT_SCALARS.csv.gz',scalar)
    write_json(out/'RUN_RECEIPT.json',dict(repository_commit=COMMIT,data_release='v2.1',requested=len(req),endpoint_rows=len(scalar),pools=len(results),
        reused=sum(r['reused'] for r in results),resumed=sum(r['previous'] for r in results),new_native=sum(r['new_native'] for r in results),
        seconds=time.monotonic()-start,jobs=a.jobs,all_complete=all(r['complete'] for r in results),full_failure_denominator_retained=True))
    print((out/'RUN_RECEIPT.json').read_text(),flush=True)

if __name__=='__main__':main()
