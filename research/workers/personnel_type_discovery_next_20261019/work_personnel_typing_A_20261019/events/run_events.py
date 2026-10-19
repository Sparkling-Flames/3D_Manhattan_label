"""Replay exact Part A requests through the byte-identical Pro native functions.

Only output paths are redirected. Geometry, member sorting, fusion parameters,
scores, reference binding and completeness definitions remain native.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import argparse, csv, datetime, fcntl, gzip, hashlib, json, math, os, sys, time
import numpy as np

HERE=Path(__file__).resolve().parent
RECOVERED=HERE.parent/'recovered'
NATIVE=RECOVERED/'work_v2_20261019'/'fusion'
DEPS=HERE.parent/'deps'
NATIVE_OUT=HERE/'native_runs'
os.environ.setdefault('PERSONNEL_V2_REPOSITORY',str(RECOVERED/'repo_main_20261019'))
sys.path[:0]=[str(DEPS),str(NATIVE)]
import pool_io
import fusion_engine as fe
import compare_fusions as cf

# Redirect derived outputs only, without editing any original module.
fe.OUT=NATIVE_OUT
cf.OUT=NATIVE_OUT

def file_sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(2**20),b''):h.update(b)
    return h.hexdigest()

def load_design_events():
    groups=defaultdict(list)
    with gzip.open(HERE/'event_design.csv.gz','rt',encoding='utf-8-sig',newline='') as f:
        for row in csv.DictReader(f):
            row['k']=int(row['k'])
            if row['background_replicate']!='':row['background_replicate']=int(row['background_replicate'])
            row['event_selection_uses_target_geometry']=False
            row['event_selection_uses_classes']=False
            groups[row['pool_id']].append(row)
    return groups

def add_separate_endpoint_distances(out,cp):
    """Top/bottom diagnostic uses the native bound-cycle selected shift.

    The main native comparison is untouched. Missing/full-order mismatch is not
    replaced by a best 2D floor match. Units are degrees on spherical rays.
    """
    out.update(upper_bound_shift_max_deg=None,lower_bound_shift_max_deg=None,
               upper_bound_shift_mean_deg=None,lower_bound_shift_mean_deg=None)
    if not out.get('structure_available'):return
    a=cp.signature(out['team_id_a']);b=cp.signature(out['team_id_b'])
    pa,pb=np.asarray(a['points'],float),np.asarray(b['points'],float)
    top=fe.angular(pa[::2],pb[::2]);bottom=fe.angular(pa[1::2],pb[1::2])
    # Mirror paired_split_research.study.cyclic exactly: (i + shift) modulo n.
    n=len(pa)//2;ii=np.arange(n);jj=(ii+int(out['bound_cyclic_shift']))%n
    tv,bv=top[ii,jj],bottom[ii,jj]
    assert abs(float(np.maximum(tv,bv).max())-out['structure_bound_cyclic_deg'])<1e-7
    out.update(upper_bound_shift_max_deg=float(tv.max()),lower_bound_shift_max_deg=float(bv.max()),
               upper_bound_shift_mean_deg=float(tv.mean()),lower_bound_shift_mean_deg=float(bv.mean()))

def compare_pool(pool,events):
    started=time.monotonic();cp=cf.ComparisonPool(pool)
    lookup={r['worker_id']:r for r in pool['records']};rows=[]
    for event in events:
        a,b=event['request_a'],event['request_b']
        native=cp.pair(a,b)
        assert native['shared_workers']==event['k']-1 and not native['same_subset']
        assert native['member_workers_a']==event['member_workers_a'] and native['member_workers_b']==event['member_workers_b']
        row=dict(event,**{k:v for k,v in native.items() if k not in event})
        row.update(entrant_a=event['worker_a'],entrant_b=event['worker_b'],
                   comparison_family='single_replacement',data_release='v2',
                   outcome_stage='post_answer_frozen_fusion',stable_main=native['joint_stable_main'])
        for side,w in [('a',event['worker_a']),('b',event['worker_b'])]:
            rec=lookup[w];team=cp.byid[event['request_'+side]]
            row['entrant_object_id_'+side]=rec['object_id']
            row['entrant_origin_'+side]=rec['origin']
            row['entrant_point_pairs_'+side]=len(rec['points'])//2
            row['entrant_actual_B8L2_'+side]=rec.get('B8L2')
            row['entrant_actual_D10_'+side]=rec.get('D10')
            row['source_entrant_time_'+side]=rec['source_time_seconds']
            row['target_entrant_time_'+side]=rec['target_time_seconds']
            row['entrant_time_source_kind_'+side]=rec['time_source_kind']
            for field in ('nodes','geometry_status','geometry_reason','order_status','connection_available','complete_floor_evaluable',
                          'source_time_known_n','source_time_missing_n','source_time_known_sum_seconds','source_time_total_seconds',
                          'target_time_known_n','target_time_missing_n','target_time_known_sum_seconds','target_time_total_seconds',
                          'height_mean_ratio','iou_2d','IoU3D100','reference_node_shortfall','location_unresolved'):
                row[field+'_'+side]=team.get(field)
        row['entrant_same_point_count']=row['entrant_point_pairs_a']==row['entrant_point_pairs_b']
        row['entrant_point_count_information_stage']='post_answer_conditional_only'
        row['floor_change']=row['floor_jaccard_difference']
        row['abs_delta_Q']=row['abs_B8L2_change']
        row['delta_Q']=row['B8L2_change']
        add_separate_endpoint_distances(row,cp)
        rows.append(row)
    target=HERE/'comparisons'/pool['pool_id']
    n=cf.write_csv_gz(target/'events.csv.gz',rows)
    receipt=dict(pool_id=pool['pool_id'],events=n,seconds=time.monotonic()-started,
                 event_ids_sha256=pool_io.digest([r['event_id'] for r in rows]),
                 geometry_state_source=str(NATIVE_OUT.relative_to(HERE))+'/pools/'+pool['pool_id']+'/states.json.gz',
                 native_comparison_sha256=file_sha(NATIVE/'compare_fusions.py'))
    pool_io.save(target/'DONE.json',receipt)
    return receipt

def worker(pool,requests,events,do_compare):
    r=fe.run_pool(pool,requests)
    if do_compare:r['comparison']=compare_pool(pool,events)
    return r

def consolidate():
    # Native consolidation includes each registered request with all native
    # scoring/time/component fields; state caches remain per pool.
    return fe.consolidate()

def merge_events():
    files=sorted((HERE/'comparisons').glob('*/events.csv.gz'))
    fields=[]
    for p in files:
        with gzip.open(p,'rt',encoding='utf-8-sig',newline='') as f:
            fields.extend(k for k in next(csv.reader(f),[]) if k not in fields)
    target=HERE/'common_events.csv.gz';temp=target.with_suffix(target.suffix+'.tmp')
    count=0;ids=set()
    with gzip.GzipFile(filename=str(temp),mode='wb',mtime=0,compresslevel=6) as gz:
        import io
        with io.TextIOWrapper(gz,encoding='utf-8-sig',newline='') as tf:
            w=csv.DictWriter(tf,fieldnames=fields);w.writeheader()
            for p in files:
                with gzip.open(p,'rt',encoding='utf-8-sig',newline='') as f:
                    for r in csv.DictReader(f):
                        assert r['event_id'] not in ids,'duplicate event during merge'
                        ids.add(r['event_id']);w.writerow(r);count+=1
    # Full CRC/read count, then atomic publish. Keep source comparison tables.
    with gzip.open(temp,'rt',encoding='utf-8-sig',newline='') as f:
        assert sum(1 for _ in csv.DictReader(f))==count
    temp.replace(target)
    expected=pool_io.read(HERE/'DESIGN.json')['n_events']
    return dict(events=count,expected_events=expected,complete=count==expected,
                file_sha256=file_sha(target),files=len(files),fields=fields)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--stage',choices=['pilot','full','compare','merge'],default='pilot')
    ap.add_argument('--jobs',type=int,default=3)
    ap.add_argument('--pool',action='append')
    args=ap.parse_args()
    HERE.mkdir(parents=True,exist_ok=True);NATIVE_OUT.mkdir(parents=True,exist_ok=True)
    lock=(HERE/'event_writer.lock').open('a+')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:raise RuntimeError('another Part A event writer is active')
    design=pool_io.read(HERE/'DESIGN.json')
    assert file_sha(NATIVE/'INPUT_SNAPSHOT.json.gz')==design['inputs']['INPUT_SNAPSHOT.json.gz']
    source=Path(os.environ['PERSONNEL_V2_REPOSITORY'])
    for p,sha in design['method_hashes'].items():assert file_sha(source/p)==sha,p
    if args.stage=='merge':
        r=merge_events();pool_io.save(HERE/'EVENT_MERGE_RECEIPT.json',r);print(json.dumps(r));return
    request_path=HERE/('PILOT_REQUESTS_100.json.gz' if args.stage=='pilot' else 'REQUESTS.json.gz')
    payload=pool_io.read(request_path);pools=pool_io.load_pools();fe.validate_requests(payload,pools)
    bypool=defaultdict(list)
    for r in payload['requests']:
        if not args.pool or r['pool_id'] in args.pool:bypool[r['pool_id']].append(r)
    pools=[p for p in pools if p['pool_id'] in bypool]
    events=load_design_events() if args.stage in ('full','compare') else {}
    started=time.monotonic();done=[]
    if args.stage=='compare':
        with ProcessPoolExecutor(max_workers=args.jobs) as ex:
            futs={ex.submit(compare_pool,p,events[p['pool_id']]):p['pool_id'] for p in pools}
            for fut in as_completed(futs):
                r=fut.result();done.append(r)
                if len(done)%5==0:print(json.dumps(dict(comparison_pools=len(done),total=len(pools),elapsed=time.monotonic()-started)),flush=True)
    else:
        with ProcessPoolExecutor(max_workers=args.jobs) as ex:
            futs={ex.submit(worker,p,bypool[p['pool_id']],events.get(p['pool_id'],[]),args.stage=='full'):p['pool_id'] for p in pools}
            for fut in as_completed(futs):
                r=fut.result();done.append(r)
                if args.stage=='pilot' or len(done)%5==0 or len(done)==len(pools):
                    print(json.dumps(dict(stage=args.stage,completed=len(done),total=len(pools),pool_id=r['pool_id'],
                                         new_fusions=r['new_fusions'],new_scores=r['new_scores'],
                                         pool_seconds=r['total_seconds'],elapsed_seconds=time.monotonic()-started)),flush=True)
        consolidate()
    receipt=dict(stage=args.stage,jobs=args.jobs,created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                 request_file=str(request_path.relative_to(HERE)),request_file_sha256=file_sha(request_path),
                 design_sha256=file_sha(HERE/'DESIGN.json'),native_functions_unchanged=True,output_path_redirect_only=True,
                 new_fusions=sum(r.get('new_fusions',0) for r in done),new_scores=sum(r.get('new_scores',0) for r in done),
                 reused_existing_unique_states=sum(r.get('reused_unique_teams',0) for r in done),
                 request_rows_new=sum(r.get('new_request_rows',0) for r in done),
                 exception_count=sum(len(r.get('exceptions',[])) for r in done),
                 elapsed_seconds=time.monotonic()-started,by_pool=done)
    if args.stage in ('full','compare') and not args.pool:receipt['merged']=merge_events()
    name=args.stage.upper()+'_RUN_RECEIPT_'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S')+'.json'
    pool_io.save(HERE/name,receipt)
    if args.stage=='pilot':pool_io.save(HERE/'PILOT_TIMING_RECEIPT.json',receipt)
    if args.stage=='full' and not args.pool:pool_io.save(HERE/'FULL_RUN_RECEIPT.json',receipt)
    print(json.dumps({k:v for k,v in receipt.items() if k not in ('by_pool','merged')},ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':main()
