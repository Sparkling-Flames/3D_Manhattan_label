"""Freeze and execute the n=20 continuation in independently recoverable batches.

The source repository, reference binding, native fusion, and scoring are fixed.
Batch byte files are atomically written and structurally validated before being
announced complete. Large native checkpoints are scratch-only; portable output
contains exact requests, scalar components and compact endpoint geometry.
"""
from __future__ import annotations
import argparse, collections, csv, gzip, hashlib, json, math, os, sys, time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
STUDY = HERE.parents[1]
COMPOSITION = STUDY/'composition'
sys.path.insert(0, str(COMPOSITION))
import global_study as gs
import run_endpoints as native

DESIGN = HERE/'candidate_n20'
BATCHES = HERE/'batches'
GEOMETRY_FIELDS = ['team_key','pool_id','member_workers','k','score_status',
                   'complete_evaluable','geometry_json','node_supports',
                   'minimum_support','reference_id','reference_version']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_csv(path, expected_keys=None, expected_rows=None):
    with gzip.open(path, 'rt', encoding='utf-8-sig', newline='') as stream:
        reader = csv.reader(stream)
        fields = next(reader)
        if len(fields) != len(set(fields)):
            raise ValueError(('duplicate_header', str(path)))
        key_i = fields.index('team_key') if 'team_key' in fields else None
        keys, n = set(), 0
        for row in reader:
            if len(row) != len(fields):
                raise ValueError(('ragged_csv', str(path), n + 2, len(row), len(fields)))
            n += 1
            if key_i is not None:
                if row[key_i] in keys:
                    raise ValueError(('duplicate_team_key', str(path), row[key_i]))
                keys.add(row[key_i])
    if expected_rows is not None and n != expected_rows:
        raise ValueError(('row_count', str(path), n, expected_rows))
    if expected_keys is not None and keys != set(expected_keys):
        raise ValueError(('key_coverage', str(path), len(keys), len(expected_keys)))
    return dict(rows=n, columns=len(fields), unique_team_keys=len(keys), sha256=sha(path), bytes=Path(path).stat().st_size)


def freeze():
    req = gs.read(DESIGN/'ENDPOINT_REQUESTS.json.gz')['requests']
    original = gs.read(DESIGN/'DESIGN_CANDIDATE.json')
    full, partial, _ = gs.existing_cache()
    history = set(gzip.open(COMPOSITION/'HISTORICAL_TEAM_KEYS.txt.gz','rt').read().splitlines())
    for r in req:
        r['historical_583261_set_overlap'] = r['team_key'] in history
        r['historical_complete_geometry_available'] = r['team_key'] in full
        r['historical_scalar_available'] = r['team_key'] in partial
    needed = [r for r in req if not r['cached_previous_request'] and not r['historical_complete_geometry_available']]
    needed_keys={r['team_key'] for r in needed}
    reused = [r for r in req if r['team_key'] not in needed_keys]
    semi = sorted((r for r in needed if '__semi__' in r['pool_id']), key=lambda r:(r['pool_id'],r['team_key']))
    manual = sorted((r for r in needed if '__manual__' in r['pool_id']), key=lambda r:(r['pool_id'],r['team_key']))
    chunks = [semi] if semi else []
    chunks += [manual[i:i+25000] for i in range(0,len(manual),25000)]
    index = []
    for i, rows in enumerate(chunks,1):
        bid = f'batch_{i:03d}'
        path = BATCHES/bid/'REQUESTS.json.gz'
        gs.save(path, dict(batch_id=bid, stage='n20_all_ordinary_vectors_continuation', requests=rows))
        index.append(dict(batch_id=bid, requested=len(rows), pools=len({r['pool_id'] for r in rows}),
                          condition='semi' if all('__semi__' in r['pool_id'] for r in rows) else 'manual',
                          historical_geometry_restoration=sum(r['historical_583261_set_overlap'] for r in rows),
                          new_against_recovered_history=sum(not r['historical_583261_set_overlap'] for r in rows),
                          request_file=str(path.relative_to(HERE)), sha256=sha(path)))
    gs.save(BATCHES/'REUSED_REQUESTS.json.gz', dict(requests=reused))
    frame=gs.pd.DataFrame(index)
    gs.csv(BATCHES/'BATCH_PLAN.csv',frame)
    receipt=dict(original, status='frozen_before_new_fusion',
                 newly_required_native_endpoints=len(needed), reused_endpoints=len(reused),
                 new_against_recovered_history=sum(not r['historical_583261_set_overlap'] for r in needed),
                 historical_geometry_restorations=sum(r['historical_583261_set_overlap'] for r in needed),
                 batches=index,
                 complete_vector_scope='All ordinary pools, n=20, six predefined method-condition pairs',
                 member_sampling='Up to three fixed deterministic membersets per feasible fine/A2 vector; not an exhaustive within-vector member census',
                 scientific_continuation='Broaden original metadata-selected panel to every eligible ordinary image at n=20; compare coarse/fine and continuous QT on common endpoint populations; keep failure and source strata',
                 original_contract_unchanged=True,
                 checkpoint_interval_new_endpoints=500)
    for file in [DESIGN/'ENDPOINT_REQUESTS.json.gz',DESIGN/'CONFIG_MEMBERSHIP.csv.gz',DESIGN/'CONFIG_CELLS.csv.gz',DESIGN/'POOL_METHOD_COVERAGE.csv',HERE/'prepare_n20_design.py',Path(__file__)]:
        receipt.setdefault('input_and_code_hashes',{})[str(file.relative_to(HERE))]=sha(file)
    gs.save(HERE/'DESIGN_FREEZE.json',receipt)
    print(json.dumps(receipt,ensure_ascii=False,indent=2),flush=True)


def worker(payload):
    batch_id, pool, req, times = payload
    pid=pool['pool_id']
    target=HERE/'runtime'/batch_id/(pid+'.json.gz')
    needed={r['team_key']:r for r in req}
    rows={}
    if target.exists():
        checkpoint=gs.read(target)
        if checkpoint['pool_input_sha256']!=gs.digest(pool):
            raise ValueError(('changed_pool_input',pid))
        rows={r['team_key']:r for r in checkpoint['teams']}
        if set(rows)-set(needed):
            raise ValueError(('checkpoint_unrequested_keys',pid))
    fe,fr,sg,_=gs.setup_engine()
    cache,diag={},{}
    new_n=0; start=time.monotonic()
    with fe.cached_matching(),fe.scoring_engine(fe.ENGINE/'measurement_engine.zip',fe.ENGINE/'working_models.py') as (engine,models):
        for key,r in needed.items():
            if key in rows:
                continue
            row=fr.evaluate_one(pool,r['member_workers'],engine,models,score_cache=cache)
            row=native.enrich(row,pool,times,sg,diag)
            row['endpoint_origin']='historical_endpoint_regenerated_for_missing_geometry' if r['historical_583261_set_overlap'] else 'new_endpoint_n20_continuation'
            row['historical_583261_set_overlap']=r['historical_583261_set_overlap']
            row['historical_complete_geometry_cache']=False
            row['historical_scalar_cache']=r['historical_scalar_available']
            row['continuation_batch']=batch_id
            if row['team_key']!=key or row['k']!=20:
                raise ValueError(('native_identity_mismatch',key))
            rows[key]=row;new_n+=1
            if new_n%500==0:
                gs.save(target,dict(batch_id=batch_id,pool_id=pid,pool_input_sha256=gs.digest(pool),fusion_gap=fe.WORKING_GAP,teams=list(rows.values())))
    gs.save(target,dict(batch_id=batch_id,pool_id=pid,pool_input_sha256=gs.digest(pool),fusion_gap=fe.WORKING_GAP,teams=list(rows.values())))
    return dict(pool_id=pid,requested=len(needed),new_native=new_n,resumed=len(needed)-new_n,seconds=time.monotonic()-start,complete=sum(bool(r.get('complete_evaluable')) for r in rows.values()))


def compact_geometry(r):
    return dict(team_key=r['team_key'],pool_id=r['pool_id'],member_workers='|'.join(r['member_workers']),
                k=r['k'],score_status=r.get('score_status'),complete_evaluable=r.get('complete_evaluable'),
                geometry_json=json.dumps(gs.clean(r.get('geometry')),ensure_ascii=False,separators=(',',':'),allow_nan=False),
                node_supports='|'.join(map(str,r.get('node_supports',[]))),minimum_support=r.get('minimum_support'),
                reference_id=r.get('reference_id'),reference_version=r.get('reference_version'))


def export_batch(batch_id):
    folder=BATCHES/batch_id
    requests=gs.read(folder/'REQUESTS.json.gz')['requests']
    expected={r['team_key'] for r in requests}
    by=collections.defaultdict(set)
    for r in requests:by[r['pool_id']].add(r['team_key'])
    fields=set();states=collections.Counter();origins=collections.Counter()
    for pid,keys in sorted(by.items()):
        payload=gs.read(HERE/'runtime'/batch_id/(pid+'.json.gz'))
        rows={r['team_key']:r for r in payload['teams']}
        if set(rows)!=keys:raise ValueError(('incomplete_pool',pid,len(keys),len(rows)))
        for r in rows.values():fields.update(native.scalar_row(r))
    scalar=folder/'ENDPOINT_SCALARS.csv.gz';geometry=folder/'ENDPOINT_GEOMETRY.csv.gz'
    stmp=scalar.with_suffix('.gz.tmp');gtmp=geometry.with_suffix('.gz.tmp')
    with gzip.open(stmp,'wt',encoding='utf-8-sig',newline='',compresslevel=5) as sf, gzip.open(gtmp,'wt',encoding='utf-8-sig',newline='',compresslevel=5) as gf:
        sw=csv.DictWriter(sf,fieldnames=sorted(fields));sw.writeheader()
        gw=csv.DictWriter(gf,fieldnames=GEOMETRY_FIELDS);gw.writeheader()
        for pid,keys in sorted(by.items()):
            payload=gs.read(HERE/'runtime'/batch_id/(pid+'.json.gz'))
            for r in sorted(payload['teams'],key=lambda x:x['team_key']):
                sw.writerow(native.scalar_row(r));gw.writerow(compact_geometry(r))
                states[r.get('score_status')]+=1;origins[r.get('endpoint_origin')]+=1
    scalar_check=validate_csv(stmp,expected)
    geometry_check=validate_csv(gtmp,expected)
    stmp.replace(scalar);gtmp.replace(geometry)
    receipt=dict(batch_id=batch_id,status='complete',requested=len(expected),computed=len(expected),missing=0,
                 score_status_counts=dict(states),endpoint_origin_counts=dict(origins),
                 scalars=scalar_check,geometry=geometry_check,request_sha256=sha(folder/'REQUESTS.json.gz'),
                 original_fusion_scoring_contract=True,failures_preserved=True,
                 portable_files=['REQUESTS.json.gz','ENDPOINT_SCALARS.csv.gz','ENDPOINT_GEOMETRY.csv.gz','COMPLETION.json'],
                 large_runtime_checkpoints_excluded=True)
    gs.save(folder/'COMPLETION.json',receipt)
    print(json.dumps(receipt,ensure_ascii=False),flush=True)


def run(batch_id,jobs):
    folder=BATCHES/batch_id
    requests=gs.read(folder/'REQUESTS.json.gz')['requests']
    pools=gs.pool_lookup()
    times={r['object_id']:r for r in gs.pd.read_csv(native.TIME_SOURCE).to_dict('records')}
    by=collections.defaultdict(list)
    for r in requests:by[r['pool_id']].append(r)
    started=time.monotonic();progress=[]
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        futures={ex.submit(worker,(batch_id,pools[pid],req,times)):pid for pid,req in sorted(by.items())}
        for f in as_completed(futures):
            result=f.result();progress.append(result)
            gs.save(folder/'POOL_PROGRESS.json',dict(batch_id=batch_id,pools=progress,elapsed_seconds=time.monotonic()-started))
            print(json.dumps(result,ensure_ascii=False),flush=True)
    export_batch(batch_id)
    gs.save(folder/'EXECUTION.json',dict(batch_id=batch_id,jobs=jobs,seconds=time.monotonic()-started,pools=progress,
             new_native=sum(x['new_native'] for x in progress),resumed=sum(x['resumed'] for x in progress)))


def export_reused():
    requests=gs.read(BATCHES/'REUSED_REQUESTS.json.gz')['requests']
    keys={r['team_key'] for r in requests}
    # This file is an explicit view of the existing frozen data, not new fusion.
    d=gs.pd.read_csv(COMPOSITION/'TEAMS_SCALARS.csv.gz',low_memory=False)
    d=d[d.team_key.isin(keys)]
    if set(d.team_key)!=keys:
        raise ValueError('Some reuse is outside the previous scalar file; add explicit old-cache enrichment before exporting.')
    out=BATCHES/'REUSED_ENDPOINT_SCALARS.csv.gz';tmp=out.with_suffix('.gz.tmp')
    d.to_csv(tmp,index=False,encoding='utf-8-sig',compression={'method':'gzip','mtime':0})
    check=validate_csv(tmp,keys);tmp.replace(out)
    by=collections.defaultdict(set)
    for r in requests:by[r['pool_id']].add(r['team_key'])
    gout=BATCHES/'REUSED_ENDPOINT_GEOMETRY.csv.gz';gtmp=gout.with_suffix('.gz.tmp')
    with gzip.open(gtmp,'wt',encoding='utf-8-sig',newline='',compresslevel=5) as stream:
        writer=csv.DictWriter(stream,fieldnames=GEOMETRY_FIELDS);writer.writeheader()
        for pid,needed in sorted(by.items()):
            available=native.pool_endpoints(pid)
            if needed-available.keys():raise ValueError(('missing_reused_geometry',pid))
            for key in sorted(needed):writer.writerow(compact_geometry(available[key]))
    gcheck=validate_csv(gtmp,keys);gtmp.replace(gout)
    gs.save(BATCHES/'REUSED_RECEIPT.json',dict(scalars=check,geometry=gcheck,new_fusion_calls=0,source_sha256=sha(COMPOSITION/'TEAMS_SCALARS.csv.gz')))
    print(json.dumps(dict(reused=len(keys),file=str(out),new_fusion_calls=0)),flush=True)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('command',choices=['freeze','run','export','reuse'])
    ap.add_argument('--batch',default='batch_001');ap.add_argument('--jobs',type=int,default=6)
    a=ap.parse_args()
    {'freeze':freeze,'run':lambda:run(a.batch,a.jobs),'export':lambda:export_batch(a.batch),'reuse':export_reused}[a.command]()
