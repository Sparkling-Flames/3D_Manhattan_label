"""Run the frozen design with unchanged official fusion / quality functions.

The task-local wrapper updates provenance and binds record time to the current
official input snapshot. It does not change coordinates, correspondence, voting,
ordering, geometry acceptance, or scoring. It checkpoints each pool atomically.
"""
from __future__ import annotations
import os
for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import argparse, concurrent.futures, gzip, importlib.util, json, math, sys, time
from pathlib import Path
import numpy as np
import pandas as pd
from design import ROOT,OUT,COMMIT,digest,sha,csv,write_json

SCALARS=ROOT/'research/workers/personnel_v21_reselection_20261029/experiment/focused_endpoints/ENDPOINT_SCALARS.csv.gz'
MANUAL=ROOT/'research/fusion/manual_order_impact_20261104/endpoints/ENDPOINTS.jsonl.gz'
TIME=OUT/'inputs/CURRENT_TIME_INDEX.csv.gz'

def read_gz(p):
    with gzip.open(p,'rt',encoding='utf-8-sig') as f:return json.load(f)

def atomic_json(p,obj):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    b=json.dumps(obj,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
    if p.suffix=='.gz':b=gzip.compress(b,compresslevel=5,mtime=0)
    tmp=p.with_name(p.name+'.writing');tmp.write_bytes(b);tmp.replace(p)

def load_native():
    os.environ['HOHONET_REPO']=str(ROOT)
    p=ROOT/'research/same_room/same_room_current_classes_v2_20261023/code/engine/new_team_engine.py'
    spec=importlib.util.spec_from_file_location('c13_native',p);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    # Same values and logging kinds as current v2.1 pools, independently checked
    # against RAW_TARGET_RESPONSE_RECORDS before this file is consumed.
    mod.native.TIME_SOURCE=TIME
    return mod

def evaluate(engine,mod,pool,workers):
    row=engine.evaluate(pool,workers)
    geometry=row.get('geometry')
    if geometry:
        score=engine.scorecache.get(engine.fr.digest([row['k']==2,row.get('nodes'),geometry]))
        if score:row.update(score)
    state=row.pop('full_state',None)
    if state:
        row['selected_nodes']=state.get('node_consensus')
        # Failed automatic outputs remain inspectable without re-running fusion.
        if row.get('B8L2') is None:row['automatic_state']=state
    own=[r for r in pool['records'] if r['worker_id'] in workers]
    row.update(data_release='v2.1',underlying_data_version='v2.1',repository_commit=COMMIT,
               endpoint_origin='native_C13_50pct_supplement_20261104',method_identity='automatic',
               input_pool_sha256=digest(pool),input_selected_records_sha256=digest(own),reference_sha256=digest(pool['reference']),
               original_coordinates_unchanged=True,manual_order_applied=False,endpoint_reused=False,
               source_time_binding='current_frozen_v2.1_pool_records_verified_against_current_raw')
    assert len(workers)==row['k'] and row['team_key']==engine.fr.team_key(pool['pool_id'],workers)
    if row.get('minimum_support') is not None:assert row['minimum_support']==math.ceil(row['k']/2)
    if row.get('B8L2') is not None:assert math.isfinite(row['B8L2']) and row.get('D10') is not None
    if (row.get('geometry') or {}).get('points') is not None:
        pp=np.asarray(row['geometry']['points'])
        assert np.array_equal(pp[::2,0],pp[1::2,0])
    return mod.gs.clean(row)

def cache_audit():
    req=pd.read_csv(OUT/'design/REQUESTS.csv.gz');keys=set(req.team_key)
    sc=pd.read_csv(SCALARS,usecols=lambda c:c in ('team_key','pool_id','member_workers','member_object_ids','input_pool_sha256'),low_memory=False)
    hit=sc[sc.team_key.isin(keys)]
    with gzip.open(MANUAL,'rt',encoding='utf-8-sig') as f:manual=[json.loads(l) for l in f]
    mh=[r for r in manual if r['team_key'] in keys]
    # The frozen random design has no reuse hits. Do not recompute a hit silently
    # if another release is substituted later; require source/geometry recovery.
    assert len(hit)==0 and len(mh)==0
    csv(OUT/'audit/CACHE_MATCHES.csv',pd.DataFrame(columns=['team_key','source','kind']))
    receipt=dict(requests=len(req),focused_automatic_cache_rows=len(sc),focused_exact_hits=len(hit),approved_manual_cache_rows=len(manual),approved_manual_exact_hits=len(mh),
                 automatic_reuse_fraction=0,assisted_variant='Identical to automatic because no approved exact endpoint is selected; no new manual order inferred',
                 source_hashes={str(p.relative_to(ROOT)):sha(p) for p in [SCALARS,MANUAL]},request_sha256=sha(OUT/'design/REQUESTS.csv.gz'))
    write_json(OUT/'audit/CACHE_AUDIT.json',receipt);return receipt

def parity():
    mod=load_native();pools={p['pool_id']:p for p in read_gz(OUT/'inputs/SELECTED_POOLS.json.gz')['images']}
    sc=pd.read_csv(SCALARS,low_memory=False);sc=sc[sc.pool_id.isin(pools)&sc.k.ge(3)].sort_values('team_key')
    successful=sc[sc.B8L2.notna()]
    # Archived focused endpoints use other n values. Three distinct difficulty
    # strata exercise the unchanged geometry/scorer; they are not new study teams.
    picked=pd.concat([successful.groupby('difficulty',sort=True).head(1).head(3),sc[sc.B8L2.isna()].head(1)])
    assert len(picked)==4
    fields=['B8L2','D10','IoU3D100','iou_2d','S_bottom_deg','dir','Hmean','Hcenter','omission','extension','nodes','minimum_support','boundary_loss','direction_loss','height_loss']
    report=[]
    with mod.Engine(full_state=True) as eng:
        for old in picked.to_dict('records'):
            p=pools[old['pool_id']];eng.reset_pool();r=evaluate(eng,mod,p,old['member_workers'].split('|'));diff={};both=0
            for f in fields:
                a,b=old.get(f),r.get(f);a=None if pd.isna(a) else a
                assert (a is None)==(b is None),(r['team_key'],f,a,b)
                if a is not None:diff[f]=abs(float(a)-float(b));both+=1
            assert max(diff.values(),default=0)<1e-8,(r['team_key'],diff)
            assert old['score_status']==r['score_status']
            assert str(old['reference_id'])==r['reference_id'] and str(old['reference_version'])==r['reference_version']
            report.append(dict(team_key=r['team_key'],score_status=r['score_status'],numeric_fields=both,maximum_absolute_difference=max(diff.values(),default=0),differences=diff))
    receipt=dict(all_passed=True,reference_cache=str(SCALARS.relative_to(ROOT)),cache_sha256=sha(SCALARS),cases=report,
                 purpose='Runtime parity on archived exact teams; validation-only endpoints, excluded from scientific design and estimates')
    write_json(OUT/'audit/NATIVE_PARITY.json',receipt);print(json.dumps(receipt,ensure_ascii=False),flush=True)

def worker(payload):
    pool,req=payload;pid=pool['pool_id'];path=OUT/'endpoints/pools'/f'{pid}.json.gz'
    wanted={r['team_key']:r for r in req};rows={};start=time.monotonic()
    if path.exists():
        old=read_gz(path);assert old['input_pool_sha256']==digest(pool)
        rows={r['team_key']:r for r in old['teams']};assert set(rows)<=set(wanted)
    initial=len(rows);mod=load_native()
    def flush():atomic_json(path,dict(pool_id=pid,input_pool_sha256=digest(pool),teams=list(rows.values())))
    with mod.Engine(full_state=True) as eng:
        for tk,q in sorted(wanted.items()):
            if tk in rows:continue
            r=evaluate(eng,mod,pool,q['member_workers'].split('|'))
            assert r['team_key']==tk and r['reference_id']==q['reference_id'] and r['reference_version']==q['reference_version']
            assert sorted(r['member_object_ids'])==q['member_object_ids'].split('|')
            rows[tk]=r
            if (len(rows)-initial)%32==0:flush()
    flush()
    return dict(pool_id=pid,requested=len(req),computed_new=len(rows)-initial,resumed=initial,scored=sum(r.get('B8L2') is not None for r in rows.values()),
                statuses=pd.Series([r['score_status'] for r in rows.values()]).value_counts().to_dict(),seconds=time.monotonic()-start)

def export():
    mod=load_native();rows=[];geometry=[];count=0
    for p in sorted((OUT/'endpoints/pools').glob('*.json.gz')):
        for r in read_gz(p)['teams']:
            rows.append(mod.native.scalar_row(r));count+=1
            geometry.append({k:r.get(k) for k in ('team_key','pool_id','score_status','B8L2','reference_id','reference_version','input_selected_records_sha256')}|{
                'member_workers':'|'.join(r['member_workers']),'geometry_json':json.dumps(r.get('geometry'),separators=(',',':'))})
    df=pd.DataFrame(rows);csv(OUT/'endpoints/ENDPOINT_SCALARS.csv.gz',df);csv(OUT/'endpoints/ENDPOINT_GEOMETRY.csv.gz',pd.DataFrame(geometry))
    assert count==len(pd.read_csv(OUT/'design/REQUESTS.csv.gz')) and not df.team_key.duplicated().any()
    return df

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--jobs',type=int,default=4);ap.add_argument('--parity-only',action='store_true');ap.add_argument('--export-only',action='store_true');args=ap.parse_args()
    audit=cache_audit()
    if args.export_only:export();return
    parity()
    if args.parity_only:return
    request_hash=sha(OUT/'design/REQUESTS.csv.gz');req=pd.read_csv(OUT/'design/REQUESTS.csv.gz')
    pools={p['pool_id']:p for p in read_gz(OUT/'inputs/SELECTED_POOLS.json.gz')['images']}
    work=[(pools[pid],g.to_dict('records')) for pid,g in req.groupby('pool_id',sort=True)];done=[];start=time.monotonic()
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.jobs) as ex:
        futures=[ex.submit(worker,w) for w in work]
        for f in concurrent.futures.as_completed(futures):
            x=f.result();done.append(x)
            atomic_json(OUT/'endpoints/PROGRESS.json',dict(pools=len(done),requested_pools=len(work),receipts=done,wall_seconds=time.monotonic()-start))
            print(json.dumps(x,ensure_ascii=False),flush=True)
    df=export();assert sha(OUT/'design/REQUESTS.csv.gz')==request_hash
    sources=[p for p in sys.modules.values() if getattr(p,'__file__',None)]
    codehash={str(Path(p.__file__).relative_to(ROOT)):sha(p.__file__) for p in sources if Path(p.__file__).is_relative_to(ROOT) and Path(p.__file__).is_file() and str(p.__file__).endswith('.py')}
    receipt=dict(completed=True,requested=len(req),endpoint_rows=len(df),unique_endpoints=df.team_key.nunique(),selected_pools=len(work),
                 new_native_in_this_execution=sum(x['computed_new'] for x in done),resumed=sum(x['resumed'] for x in done),
                 Q_available=int(df.B8L2.notna().sum()),score_status_counts=df.score_status.value_counts().to_dict(),
                 automatic_cache_exact_hits=audit['focused_exact_hits'],approved_manual_exact_hits=audit['approved_manual_exact_hits'],
                 coordinate_edits=0,classification_refits=0,request_sha256=request_hash,source_commit=COMMIT,wall_seconds=time.monotonic()-start,
                 runtime_source_sha256=codehash,by_pool=done)
    atomic_json(OUT/'endpoints/RUN_RECEIPT.json',receipt)
    print(json.dumps({k:v for k,v in receipt.items() if k not in ('by_pool','runtime_source_sha256')},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
