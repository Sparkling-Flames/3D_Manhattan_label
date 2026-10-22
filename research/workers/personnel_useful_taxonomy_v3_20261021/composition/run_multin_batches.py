"""Compute only missing frozen v3 endpoints; checkpoint and export each batch."""
from __future__ import annotations
import argparse, collections, csv, gzip, hashlib, io, json, os, sys, time
from concurrent.futures import ProcessPoolExecutor,as_completed
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from multin_design import gs,OLD,CONT,ROOT,sha,write_csv
import run_endpoints as native
import pandas as pd

GEOMETRY_FIELDS=['team_key','pool_id','member_workers','k','score_status','complete_evaluable','geometry_json','node_supports','minimum_support','reference_id','reference_version']

def compact(r):
    return dict(team_key=r['team_key'],pool_id=r['pool_id'],member_workers='|'.join(r['member_workers']),k=r['k'],score_status=r.get('score_status'),complete_evaluable=r.get('complete_evaluable'),geometry_json=json.dumps(gs.clean(r.get('geometry')),separators=(',',':'),allow_nan=False),node_supports='|'.join(map(str,r.get('node_supports',[]))),minimum_support=r.get('minimum_support'),reference_id=r.get('reference_id'),reference_version=r.get('reference_version'))

def find_reused(pid,keys):
    out={}
    if not keys:return out
    paths=[OLD/'composition/runtime/endpoints'/f'{pid}.json.gz',OLD/'composition/runtime/priority_endpoints'/f'{pid}.json.gz',OLD/'composition/benchmark_endpoints'/f'{pid}.json.gz',*sorted((CONT/'next_stage/runtime').glob(f'batch_*/{pid}.json.gz')),
        *[p for p in sorted((HERE/'runtime').glob(f'*/{pid}.json.gz')) if (HERE/'batches'/p.parent.name/'COMPLETION.json').exists()]]
    for p in paths:
        if not p.exists():continue
        data=gs.read(p)
        for r in data['teams']:
            if r['team_key'] in keys and r['team_key'] not in out:out[r['team_key']]=r
        if keys<=out.keys():break
    if not keys<=out.keys():
        full,_,_=gs.existing_cache()
        for k in keys-out.keys():
            if k in full:out[k]=full[k]
    if not keys<=out.keys():raise ValueError(('cached_geometry_unavailable',pid,sorted(keys-out.keys())[:8]))
    return out

def worker(payload):
    bid,pool,req,times=payload;pid=pool['pool_id'];target=HERE/'runtime'/bid/(pid+'.json.gz')
    need={r['team_key']:r for r in req};poolhash=gs.digest(pool);rows={}
    if target.exists():
        x=gs.read(target)
        if x['pool_input_sha256']!=poolhash:raise ValueError(('changed_input',pid))
        rows={r['team_key']:r for r in x['teams']}
        if set(rows)-need.keys():raise ValueError(('unexpected_checkpoint_key',pid))
    reused=find_reused(pid,{k for k,r in need.items() if r['cached'] and k not in rows})
    fe,fr,sg,_=gs.setup_engine();cache={};diag={};started=time.monotonic();new_count=0;reused_count=0
    with fe.cached_matching(),fe.scoring_engine(fe.ENGINE/'measurement_engine.zip',fe.ENGINE/'working_models.py') as (engine,models):
        for key,request in need.items():
            if key in rows:continue
            if key in reused:
                row=dict(reused[key]);row['prior_endpoint_origin']=row.get('endpoint_origin','historical_cached');row['endpoint_origin']='reused_prior_endpoint_v3';reused_count+=1
                if 'source_time_known_n' not in row:row=native.enrich(row,pool,times,sg,diag)
            else:
                members=request['member_workers'].split('|');row=fr.evaluate_one(pool,members,engine,models,score_cache=cache)
                row=native.enrich(row,pool,times,sg,diag);new_count+=1
                row['endpoint_origin']='historical_missing_geometry_restored_v3' if request['historical_583261_set_overlap'] else 'new_endpoint_v3_member_enumeration'
            if key!=row['team_key'] or row['k']!=request['n']:raise ValueError(('identity_mismatch',key,row.get('team_key'),row.get('k')))
            row['v3_batch_id']=bid;row['historical_583261_set_overlap']=request['historical_583261_set_overlap'];row['v3_source_main']='324dba44d0a82d9d64a62965f2e549ee05165417';rows[key]=row
            if (new_count+reused_count)%500==0:gs.save(target,dict(batch_id=bid,pool_id=pid,pool_input_sha256=poolhash,fusion_gap=fe.WORKING_GAP,teams=list(rows.values())))
    gs.save(target,dict(batch_id=bid,pool_id=pid,pool_input_sha256=poolhash,fusion_gap=fe.WORKING_GAP,teams=list(rows.values())))
    return dict(pool_id=pid,requested=len(need),new_native=new_count,reused=reused_count,resumed=len(need)-new_count-reused_count,seconds=time.monotonic()-started,complete=sum(bool(r.get('complete_evaluable')) for r in rows.values()))

def validate(path,keys):
    seen=set();count=0
    with gzip.open(path,'rt',encoding='utf-8-sig',newline='') as f:
        r=csv.reader(f);head=next(r);i=head.index('team_key');width=len(head)
        if width!=len(set(head)):raise ValueError('duplicate fields')
        for row in r:
            if len(row)!=width or row[i] in seen:raise ValueError(('bad_csv',path,count))
            seen.add(row[i]);count+=1
    if seen!=set(keys):raise ValueError(('key_coverage',path,len(seen),len(keys)))
    return dict(rows=count,columns=width,bytes=Path(path).stat().st_size,sha256=sha(path))

def export(bid):
    folder=HERE/'batches'/bid;d=pd.read_csv(folder/'REQUESTS.csv.gz',keep_default_na=False);needed=set(d.team_key);fields=set();states=collections.Counter();origins=collections.Counter()
    for pid,g in d.groupby('pool_id'):
        x=gs.read(HERE/'runtime'/bid/(pid+'.json.gz'));rows={r['team_key']:r for r in x['teams']}
        if set(rows)!=set(g.team_key):raise ValueError(('incomplete_batch',bid,pid))
        for r in rows.values():fields.update(native.scalar_row(r).keys())
    sp=folder/'ENDPOINT_SCALARS.csv.gz';gp=folder/'ENDPOINT_GEOMETRY.csv.gz';st=sp.with_name(sp.name+'.tmp');gt=gp.with_name(gp.name+'.tmp')
    # Complete compression before opening the publication file. Long-lived
    # compressed streams in this execution environment twice lost their tail
    # after close; the exact EOF/key-set gate caught both unpublished exports.
    # Bounded batches fit in memory, so one fsynced byte write avoids that path.
    with io.StringIO(newline='') as sf,io.StringIO(newline='') as gf:
        sw=csv.DictWriter(sf,fieldnames=sorted(fields));sw.writeheader();gw=csv.DictWriter(gf,fieldnames=GEOMETRY_FIELDS);gw.writeheader()
        for pid in sorted(d.pool_id.unique()):
            for r in sorted(gs.read(HERE/'runtime'/bid/(pid+'.json.gz'))['teams'],key=lambda r:r['team_key']):
                sw.writerow(native.scalar_row(r));gw.writerow(compact(r));states[r.get('score_status')]+=1;origins[r.get('endpoint_origin')]+=1
        for dest,buf in [(st,sf),(gt,gf)]:
            packed=gzip.compress(buf.getvalue().encode('utf-8-sig'),compresslevel=5,mtime=0)
            with open(dest,'wb') as target:
                target.write(packed);target.flush();os.fsync(target.fileno())
    sr=validate(st,needed);gr=validate(gt,needed);st.replace(sp);gt.replace(gp)
    receipt=dict(batch_id=bid,status='complete',requested=len(needed),exported=len(needed),missing=0,states=dict(states),origins=dict(origins),scalars=sr,geometry=gr,requests_sha256=sha(folder/'REQUESTS.csv.gz'),failures_retained=True,exact_membership_retained=True,unchanged_native_fusion_scoring=True)
    gs.save(folder/'COMPLETION.json',receipt);print(json.dumps(receipt,ensure_ascii=False),flush=True)
    return receipt

def run(bid,jobs,pilot=False):
    folder=HERE/'batches'/bid;d=pd.read_csv(folder/'REQUESTS.csv.gz',keep_default_na=False);pools=gs.pool_lookup()
    times={r['object_id']:r for r in pd.read_csv(native.TIME_SOURCE).to_dict('records')}
    start=time.monotonic();progress=[]
    if pilot:
        first=d.pool_id.iloc[0];sample=d[d.pool_id.eq(first)].head(128)
        got=worker((bid,pools[first],sample.to_dict('records'),times));gs.save(HERE/'PILOT_THROUGHPUT.json',dict(got,wall_seconds=time.monotonic()-start,new_per_second=got['new_native']/got['seconds'],pilot_is_subset_of_registered_requests=True));print(json.dumps(got),flush=True);return
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        futures={ex.submit(worker,(bid,pools[pid],g.to_dict('records'),times)):pid for pid,g in d.groupby('pool_id',sort=True)}
        for f in as_completed(futures):
            got=f.result();progress.append(got);gs.save(folder/'POOL_PROGRESS.json',dict(batch_id=bid,pools=progress,elapsed=time.monotonic()-start));print(json.dumps(got),flush=True)
    export(bid);gs.save(folder/'EXECUTION.json',dict(batch_id=bid,jobs=jobs,seconds=time.monotonic()-start,new_native=sum(r['new_native'] for r in progress),reused=sum(r['reused'] for r in progress),resumed=sum(r['resumed'] for r in progress),pools=progress))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['run','export']);p.add_argument('--batch',default='batch_001');p.add_argument('--jobs',type=int,default=4);p.add_argument('--pilot',action='store_true');a=p.parse_args()
    run(a.batch,a.jobs,a.pilot) if a.action=='run' else export(a.batch)
