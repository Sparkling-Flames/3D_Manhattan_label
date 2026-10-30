"""Resolve exact existing v2.1 teams; evaluate only missing frozen requests."""
from pathlib import Path
import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
import sys,json,gzip,hashlib,time,importlib.util,argparse,collections,multiprocessing
from concurrent.futures import ProcessPoolExecutor,as_completed
import pandas as pd
from selection_stop_prepare import STUDY,WORK,OUT,PORT,INP,REPLAY,read,digest,teamkey,native_pools,save

def iterjson(path):
    with gzip.open(path,'rt',encoding='utf-8-sig') as f:
        for line in f:
            if line.strip():yield json.loads(line)
def writejson(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+'.writing')
    with gzip.open(tmp,'wt',encoding='utf-8') as f:
        for row in rows:f.write(json.dumps(row,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n')
    tmp.replace(path)
def cache_plan():
    req=pd.read_csv(OUT/'design/ENDPOINT_REQUESTS.csv.gz');pools=native_pools();receipts=[]
    for pid,g in req.groupby('pool_id'):
        wanted=set(g.team_key);p=pools[pid];by={r['worker_id']:r for r in p['records']};found={};errors=collections.Counter()
        def accept(row,path):
            key=row.get('team_key');ws=row.get('member_workers')
            if key not in wanted or key in found:return
            if isinstance(ws,str):ws=ws.split('|')
            ids=row.get('member_object_ids');ids=ids.split('|') if isinstance(ids,str) else ids
            reason=None
            if not ws or key!=teamkey(pid,ws):reason='member_key'
            elif not set(ws)<=set(by):reason='eligibility'
            elif sorted(ids or [])!=sorted(by[w]['object_id'] for w in ws):reason='object_identity'
            elif row.get('reference_id')!=p['meta']['reference_id'] or row.get('reference_version')!=p['meta']['reference_version']:reason='reference'
            elif 'geometry' not in row:reason='no_full_geometry'
            elif row.get('pool_input_sha256',row.get('input_pool_sha256')) not in [None,digest(p,True),digest(p)]:reason='pool_hash'
            if reason:errors[reason]+=1;return
            row=dict(row,downstream_acquisition='reused_exact_current_endpoint',downstream_cache_source=str(path.relative_to(WORK)),data_release='v2.1')
            found[key]=row
        ac=WORK/'HOHONET_v21_AC_population_20261029/stage03_endpoints/pools'/pid
        for path in sorted(ac.glob('part_*.jsonl.gz')):
            for row in iterjson(path):accept(row,path)
        frozen=WORK/'repo/research/data/releases/v2.1/same_room_frozen_design/current_classes/native/pools'/(pid+'.json.gz')
        if frozen.exists():
            obj=read(frozen)
            if obj.get('pool_input_sha256') in [digest(p),digest(p,True)]:
                for row in obj['teams']:accept(row,frozen)
            else:errors['container_pool_hash']+=1
        writejson(OUT/'endpoints/reused'/f'{pid}.jsonl.gz',found.values())
        receipts.append(dict(pool_id=pid,requested=len(wanted),reused=len(found),missing=len(wanted)-len(found),rejected=dict(errors)))
    save('endpoints/CACHE_COVERAGE.json',{'unique_requests':len(req),'pools':receipts,'reused':sum(r['reused'] for r in receipts),'missing':sum(r['missing'] for r in receipts)})
    print(json.dumps({'reused':sum(r['reused'] for r in receipts),'missing':sum(r['missing'] for r in receipts)}),flush=True)

def worker(payload):
    pid,requests=payload;pools=native_pools();p=pools[pid];out=OUT/'endpoints/pools'/f'{pid}.jsonl.gz'
    if out.exists():
        old=list(iterjson(out));assert {r['team_key'] for r in old}=={r['team_key'] for r in requests};return dict(pool_id=pid,rows=len(old),resumed=True)
    rows={r['team_key']:r for r in iterjson(OUT/'endpoints/reused'/f'{pid}.jsonl.gz')};start=time.monotonic()
    os.environ['HOHONET_REPO']=str(PORT)
    path=PORT/'research/workers/personnel_v21_reselection_20261029/experiment/benchmark_engine.py'
    spec=importlib.util.spec_from_file_location('selection_frozen_engine',path);b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b);native=b.load_engine(PORT)
    with native.Engine(full_state=False) as eng:
        for r in requests:
            if r['team_key'] in rows:continue
            ws=r['member_workers'].split('|');row=b.evaluated(eng,native,p,ws)
            assert row['team_key']==r['team_key']
            row.update(downstream_acquisition='missing_exact_team_evaluated',downstream_request_uses=r['uses'],repository_commit='13a7861334749805a86dc19e9ea79fcaa71020c0')
            rows[row['team_key']]=row
    writejson(out,rows.values())
    return dict(pool_id=pid,rows=len(rows),new=sum(r['downstream_acquisition']=='missing_exact_team_evaluated' for r in rows.values()),seconds=time.monotonic()-start)

def run(jobs):
    req=pd.read_csv(OUT/'design/ENDPOINT_REQUESTS.csv.gz');results=[]
    with ProcessPoolExecutor(max_workers=jobs,mp_context=multiprocessing.get_context('spawn')) as ex:
        fs=[ex.submit(worker,(pid,g.to_dict('records'))) for pid,g in req.groupby('pool_id')]
        for f in as_completed(fs):
            r=f.result();results.append(r);save('endpoints/RUN_PROGRESS.json',results);print(json.dumps(r),flush=True)
    assert sum(r['rows'] for r in results)==len(req)
    save('endpoints/RUN_RECEIPT.json',{'rows':len(req),'pools':results,'new_natural_curves':0,'no_classification_change':True,'only_missing_teams':True})

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['plan','run']);ap.add_argument('--jobs',type=int,default=2);a=ap.parse_args()
    if a.stage=='plan':cache_plan()
    else:run(a.jobs)
