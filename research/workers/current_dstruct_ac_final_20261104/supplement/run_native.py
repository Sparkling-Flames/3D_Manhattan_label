"""Evaluate only the frozen AC coverage requests with unchanged native code.

Cache identity is checked before evaluation. A nonzero exact cache hit stops
this wrapper so that the saved endpoint can be recovered and reused explicitly.
All native full states are retained for later vote/correspondence diagnostics.
"""
from __future__ import annotations
import os
for _name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[_name]='1'
import argparse, concurrent.futures, gzip, importlib.util, json, math, sys, time
from pathlib import Path
import numpy as np
import pandas as pd
from design import ROOT,OUT,COMMIT,digest,sha,csv,write_json

TIME=OUT/'inputs/CURRENT_TIME_INDEX.csv.gz'
FOCUSED=ROOT/'research/workers/personnel_v21_reselection_20261029/experiment/focused_endpoints/ENDPOINT_SCALARS.csv.gz'
MANUAL=ROOT/'research/fusion/manual_order_impact_20261104/endpoints/ENDPOINTS.jsonl.gz'

def read_gz(path):
    with gzip.open(path,'rt',encoding='utf-8-sig') as f:return json.load(f)
def atomic(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    b=json.dumps(obj,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
    if path.suffix=='.gz':b=gzip.compress(b,compresslevel=5,mtime=0)
    tmp=path.with_name(path.name+'.writing');tmp.write_bytes(b);tmp.replace(path)
def load_native():
    os.environ['HOHONET_REPO']=str(ROOT)
    p=ROOT/'research/same_room/same_room_current_classes_v2_20261023/code/engine/new_team_engine.py'
    sp=importlib.util.spec_from_file_location('ac_gap_native',p);mod=importlib.util.module_from_spec(sp);sp.loader.exec_module(mod)
    mod.native.TIME_SOURCE=TIME
    return mod
def evaluate(engine,mod,pool,workers):
    row=engine.evaluate(pool,workers)
    geometry=row.get('geometry')
    if geometry:
        score=engine.scorecache.get(engine.fr.digest([row['k']==2,row.get('nodes'),geometry]))
        if score:row.update(score)
    own=[r for r in pool['records'] if r['worker_id'] in workers]
    row.update(data_release='v2.1',underlying_data_version='v2.1',repository_commit=COMMIT,
               endpoint_origin='current_DSTRUCT_AC_capacity_gap_20261104',method_identity='automatic',
               input_pool_sha256=digest(pool),input_selected_records_sha256=digest(own),reference_sha256=digest(pool['reference']),
               original_coordinates_unchanged=True,manual_order_applied=False,endpoint_reused=False,
               source_time_binding='current_frozen_v2.1_pool_records')
    assert len(workers)==row['k'] and row['team_key']==engine.fr.team_key(pool['pool_id'],workers)
    if row.get('minimum_support') is not None:assert row['minimum_support']==math.ceil(row['k']/2)
    if row.get('B8L2') is not None:assert math.isfinite(row['B8L2']) and row.get('D10') is not None
    if (row.get('geometry') or {}).get('points') is not None:
        pp=np.asarray(row['geometry']['points']);assert np.array_equal(pp[::2,0],pp[1::2,0])
    return mod.gs.clean(row)

def cache_audit():
    req=pd.read_csv(OUT/'REQUESTS.csv.gz');keys=set(req.team_key);pids=set(req.pool_id)
    base=ROOT/'research/workers/personnel_v21_reselection_20261029'
    paths=[ROOT/'research/workers/personnel_ac_v21_20261030/stage01_registered/TEAM_REQUESTS.csv.gz',FOCUSED,
           ROOT/'research/workers/mixture_patterns_and_c13_half_20261104/c13_half/design/REQUESTS.csv.gz',
           base/'additional_delivery/packages/05A/experiment/global_screen_design/REQUESTS.csv.gz']
    paths += [base/'experiment'/name/'REQUESTS.csv.gz' for name in ['refinement_baseline_design','direct_AC_design','refinement_AC_design','refinement_m_design','member_sensitivity_design','fixed_A_m_design']]
    natural_manifest=json.loads((ROOT/'research/workers/mixture_patterns_and_c13_half_20261104/curves/NATURAL_SOURCE_MANIFEST.json').read_text())
    natural_by_pool={Path(r['path']).name.removesuffix('.csv.gz'):ROOT/r['path'] for r in natural_manifest}
    paths += [natural_by_pool[p] for p in sorted(pids)]
    records=[];hits=[]
    for path in paths:
        df=pd.read_csv(path,usecols=['team_key'])
        h=sorted(set(df.team_key)&keys)
        records.append(dict(source=str(path.relative_to(ROOT)),rows=len(df),unique_keys=df.team_key.nunique(),exact_requested_hits=len(h),sha256=sha(path)))
        hits.extend(dict(team_key=k,source=str(path.relative_to(ROOT))) for k in h)
    with gzip.open(MANUAL,'rt',encoding='utf-8-sig') as f:man=[json.loads(l) for l in f]
    mh=[r['team_key'] for r in man if r['team_key'] in keys]
    records.append(dict(source=str(MANUAL.relative_to(ROOT)),rows=len(man),unique_keys=len({r['team_key'] for r in man}),exact_requested_hits=len(mh),sha256=sha(MANUAL)))
    hits.extend(dict(team_key=k,source=str(MANUAL.relative_to(ROOT))) for k in mh)
    csv(OUT/'audit/CACHE_SOURCES.csv',pd.DataFrame(records));csv(OUT/'audit/CACHE_MATCHES.csv',pd.DataFrame(hits,columns=['team_key','source']))
    receipt=dict(requests=len(req),sources_checked=len(records),source_key_rows=sum(r['rows'] for r in records),
                 exact_requested_teams_found=len({r['team_key'] for r in hits}),approved_manual_exact_hits=len(mh),
                 request_sha256=sha(OUT/'REQUESTS.csv.gz'),reuse_policy='Exact hits require recovery of saved endpoint, input and reference identity; do not silently recompute or swap the request')
    write_json(OUT/'audit/CACHE_AUDIT.json',receipt)
    if hits:raise RuntimeError('Exact saved endpoints exist: recover and reuse these before evaluation; see CACHE_MATCHES.csv')
    return receipt

def parity():
    mod=load_native();pools={p['pool_id']:p for p in read_gz(OUT/'inputs/SELECTED_POOLS.json.gz')['images']}
    sc=pd.read_csv(FOCUSED,low_memory=False);sc=sc[sc.pool_id.isin(pools)&sc.k.ge(3)].sort_values('team_key')
    good=sc[sc.B8L2.notna()]
    picked=good.groupby('difficulty',sort=True).head(1)
    if len(picked)<3:picked=pd.concat([picked,good[~good.team_key.isin(picked.team_key)].head(3-len(picked))])
    picked=pd.concat([picked,sc[sc.B8L2.isna()].head(1)])
    assert len(picked)>=3
    fields=['B8L2','D10','IoU3D100','iou_2d','S_bottom_deg','dir','Hmean','Hcenter','omission','extension','nodes','minimum_support','boundary_loss','direction_loss','height_loss']
    checked=[]
    with mod.Engine(full_state=True) as eng:
        for old in picked.to_dict('records'):
            p=pools[old['pool_id']];eng.reset_pool();r=evaluate(eng,mod,p,old['member_workers'].split('|'));diff={}
            for field in fields:
                a,b=old.get(field),r.get(field);a=None if pd.isna(a) else a
                assert (a is None)==(b is None),(r['team_key'],field,a,b)
                if a is not None:diff[field]=abs(float(a)-float(b))
            assert max(diff.values(),default=0)<1e-8,(r['team_key'],diff)
            assert old['score_status']==r['score_status']
            assert str(old['reference_id'])==r['reference_id'] and str(old['reference_version'])==r['reference_version']
            checked.append(dict(team_key=r['team_key'],score_status=r['score_status'],numeric_fields=len(diff),maximum_absolute_difference=max(diff.values(),default=0),differences=diff))
    receipt=dict(all_passed=True,source=str(FOCUSED.relative_to(ROOT)),cases=checked,
                 scientific_sample=False,purpose='Runtime parity only; validation teams do not enter AC estimates')
    write_json(OUT/'audit/NATIVE_PARITY.json',receipt)
    return receipt

def worker(payload):
    pool,requests=payload;pid=pool['pool_id'];path=OUT/'endpoints/pools'/f'{pid}.json.gz'
    wanted={r['team_key']:r for r in requests};rows={};start=time.monotonic()
    if path.exists():
        previous=read_gz(path);assert previous['input_pool_sha256']==digest(pool)
        rows={r['team_key']:r for r in previous['teams']};assert set(rows)<=set(wanted)
    resumed=len(rows);mod=load_native()
    with mod.Engine(full_state=True) as eng:
        for k,rr in sorted(wanted.items()):
            if k in rows:continue
            rows[k]=evaluate(eng,mod,pool,rr['member_workers'].split('|'))
    atomic(path,dict(pool_id=pid,input_pool_sha256=digest(pool),request_sha256=sha(OUT/'REQUESTS.csv.gz'),teams=[rows[k] for k in sorted(rows)]))
    return dict(pool_id=pid,requested=len(wanted),resumed=resumed,computed_new=len(rows)-resumed,
                Q_available=sum(r.get('B8L2') is not None for r in rows.values()),
                statuses=pd.Series([r['score_status'] for r in rows.values()]).value_counts().to_dict(),seconds=time.monotonic()-start)

def export():
    mod=load_native();rows=[];geos=[]
    for p in sorted((OUT/'endpoints/pools').glob('*.json.gz')):
        for r in read_gz(p)['teams']:
            rows.append(mod.native.scalar_row(r))
            geos.append({k:r.get(k) for k in ('team_key','pool_id','score_status','B8L2','reference_id','reference_version','input_selected_records_sha256')}|{
                'member_workers':'|'.join(r['member_workers']),'geometry_json':json.dumps(r.get('geometry'),separators=(',',':'))})
    df=pd.DataFrame(rows);csv(OUT/'endpoints/ENDPOINT_SCALARS.csv.gz',df);csv(OUT/'endpoints/ENDPOINT_GEOMETRY.csv.gz',pd.DataFrame(geos))
    assert len(df)==len(pd.read_csv(OUT/'REQUESTS.csv.gz')) and not df.team_key.duplicated().any()
    return df

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--jobs',type=int,default=4);ap.add_argument('--cache-only',action='store_true');ap.add_argument('--parity-only',action='store_true');ap.add_argument('--export-only',action='store_true');args=ap.parse_args()
    audit=cache_audit()
    print(json.dumps(audit,ensure_ascii=False),flush=True)
    if args.cache_only:return
    if args.export_only:export();return
    pt=parity();print(json.dumps(pt,ensure_ascii=False),flush=True)
    if args.parity_only:return
    request_sha=sha(OUT/'REQUESTS.csv.gz');req=pd.read_csv(OUT/'REQUESTS.csv.gz')
    pools={p['pool_id']:p for p in read_gz(OUT/'inputs/SELECTED_POOLS.json.gz')['images']}
    work=[(pools[pid],g.to_dict('records')) for pid,g in req.groupby('pool_id',sort=True)];done=[];start=time.monotonic()
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.jobs) as ex:
        futures=[ex.submit(worker,w) for w in work]
        for f in concurrent.futures.as_completed(futures):
            r=f.result();done.append(r);atomic(OUT/'endpoints/PROGRESS.json',dict(completed_pools=len(done),requested_pools=len(work),receipts=done,wall_seconds=time.monotonic()-start))
            print(json.dumps(r,ensure_ascii=False),flush=True)
    df=export();assert sha(OUT/'REQUESTS.csv.gz')==request_sha
    modules=[p for p in sys.modules.values() if getattr(p,'__file__',None)]
    codehash={str(Path(p.__file__).relative_to(ROOT)):sha(p.__file__) for p in modules if Path(p.__file__).is_relative_to(ROOT) and Path(p.__file__).is_file() and str(p.__file__).endswith('.py')}
    receipt=dict(completed=True,requests=len(req),unique_teams=df.team_key.nunique(),pools=len(work),new_native_in_this_execution=sum(r['computed_new'] for r in done),resumed=sum(r['resumed'] for r in done),
                 Q_available=int(df.B8L2.notna().sum()),score_status_counts=df.score_status.value_counts().to_dict(),source_commit=COMMIT,
                 exact_saved_endpoint_hits=audit['exact_requested_teams_found'],approved_manual_hits=audit['approved_manual_exact_hits'],
                 coordinate_edits=0,classification_refits=0,new_manual_orders=0,request_sha256=request_sha,wall_seconds=time.monotonic()-start,
                 runtime_source_sha256=codehash,by_pool=done)
    atomic(OUT/'endpoints/RUN_RECEIPT.json',receipt)
    print(json.dumps({k:v for k,v in receipt.items() if k not in ('runtime_source_sha256','by_pool')},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
