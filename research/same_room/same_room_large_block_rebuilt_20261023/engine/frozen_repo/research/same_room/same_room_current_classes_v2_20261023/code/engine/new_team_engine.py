"""Exact native endpoints for the current same-room study.

The wrapper imports frozen repository fusion, scores, geometry diagnostics and
record-time joins unchanged. No candidate labels or target scores enter here.
"""
from __future__ import annotations
import os
for _k in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[_k] = '1'
os.environ.setdefault('MPLCONFIGDIR', '/tmp/hohonet_mpl')
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import gzip
import hashlib
import json
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
_repo_value = os.environ.get('HOHONET_REPO')
if not _repo_value:
    raise RuntimeError('Set HOHONET_REPO to the repository checkout at commit 72a44e80c344975962e1071bd54d894dd86bb4b4; see code/engine/README.md.')
REPO = Path(_repo_value).expanduser().resolve()
if (HERE / 'deps').exists():
    sys.path.insert(0, str(HERE / 'deps'))
sys.path.insert(0, str(REPO / 'research/workers/personnel_global_composition_20261021/composition'))
import global_study as gs
import run_endpoints as native
import numpy as np
import pandas as pd


def save(path, obj):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    b = json.dumps(gs.clean(obj), ensure_ascii=False, sort_keys=True,
                   separators=(',', ':'), allow_nan=False).encode()
    if path.suffix == '.gz':
        b = gzip.compress(b, compresslevel=5, mtime=0)
    temp = path.with_name(path.name + '.tmp')
    with temp.open('wb') as f:
        f.write(b); f.flush(); os.fsync(f.fileno())
    os.replace(temp, path)


def save_csv(path, df):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    b = df.to_csv(index=False).encode('utf-8-sig')
    if path.suffix == '.gz':
        b = gzip.compress(b, compresslevel=5, mtime=0)
    temp = path.with_name(path.name + '.tmp')
    with temp.open('wb') as f:
        f.write(b); f.flush(); os.fsync(f.fileno())
    os.replace(temp, path)


def expression(geometry):
    """Existing current taxonomy expression, from frozen endpoint footprint."""
    p = np.asarray((geometry or {}).get('footprint') or [], dtype=float)
    if p.ndim != 2 or len(p) < 3 or not np.isfinite(p).all():
        return {k: None for k in ('fusion_turn_n','fusion_short_turn_edges','fusion_redundancy_n')}
    e = np.roll(p, -1, axis=0) - p
    length = np.linalg.norm(e, axis=1)
    if np.any(length < 1e-10):
        return {k: None for k in ('fusion_turn_n','fusion_short_turn_edges','fusion_redundancy_n')}
    angle = np.degrees(np.arccos(np.clip(np.sum(np.roll(e,1,axis=0)*e,axis=1)/(np.roll(length,1)*length),-1,1)))
    redundancy = angle <= 5
    short = (length/length.sum() < .04) & (angle >= 15) & (np.roll(angle,-1) >= 15)
    return dict(fusion_turn_n=int((~redundancy).sum()), fusion_short_turn_edges=int(short.sum()), fusion_redundancy_n=int(redundancy.sum()))


class Engine:
    def __init__(self, full_state=False):
        self.fe, self.fr, self.sg, self.corner_compare = gs.setup_engine()
        self.times = {r['object_id']: r for r in pd.read_csv(native.TIME_SOURCE).to_dict('records')}
        self.full_state = full_state
        self.scorecache = {}
        self.diag = {}

    def __enter__(self):
        self.match_context = self.fe.cached_matching()
        self.match_context.__enter__()
        self.score_context = self.fe.scoring_engine(self.fe.ENGINE/'measurement_engine.zip', self.fe.ENGINE/'working_models.py')
        self.engine, self.models = self.score_context.__enter__()
        return self

    def __exit__(self, *args):
        self.score_context.__exit__(*args)
        self.match_context.__exit__(*args)

    def reset_pool(self):
        self.scorecache = {}; self.diag = {}

    def evaluate(self, pool, workers):
        row = self.fr.evaluate_one(pool, sorted(workers), self.engine, self.models,
                                   score_cache=self.scorecache, full_state=self.full_state)
        row = native.enrich(row, pool, self.times, self.sg, self.diag)
        row.update(expression(row.get('geometry')))
        row.update(endpoint_origin='native_same_room_class_repetition_20261023',
                   underlying_data_version='v2', repository_commit='72a44e80c344975962e1071bd54d894dd86bb4b4')
        # Semantic alias: inherited source_time_total is activity on this image.
        row['recorded_time_eligible'] = bool(row.get('source_time_known_n') == row['k'] and
                                            (row.get('source_time_total_seconds') or 0) > 0 and
                                            row.get('time_source_kinds') and '|' not in row['time_source_kinds'])
        row['recorded_time_total_seconds'] = row.get('source_time_total_seconds') if row['recorded_time_eligible'] else None
        # Keep different logging semantics disaggregated even when their teams
        # mix old and new records. Missing observations remain missing.
        own = {r['worker_id']: r for r in pool['records']}
        by_kind = {}
        for w in workers:
            tr = self.times.get(own[w]['object_id'], {})
            kind = str(tr.get('time_source_kind', 'unknown'))
            x = tr.get('source_active_time_seconds')
            good = x is not None and not pd.isna(x) and np.isfinite(float(x))
            z = by_kind.setdefault(kind, dict(n=0, known_n=0, known_sum_seconds=0.))
            z['n'] += 1
            if good:
                z['known_n'] += 1; z['known_sum_seconds'] += float(x)
        for z in by_kind.values():
            z['total_seconds'] = z['known_sum_seconds'] if z['known_n'] == z['n'] else None
        row['record_time_by_kind_json'] = json.dumps(gs.clean(by_kind), sort_keys=True, separators=(',',':'))
        return gs.clean(row)


def worker(payload):
    pool, requests, output_dir = payload
    pid = pool['pool_id']; path = Path(output_dir)/'pools'/(pid+'.json.gz')
    wanted = {r['team_key']: r for r in requests}
    rows = {}
    if path.exists():
        old = gs.read(path)
        assert old['pool_input_sha256'] == gs.digest(pool)
        rows = {r['team_key']: r for r in old['teams']}
        assert set(rows) <= set(wanted)
    start = time.monotonic(); initially = len(rows)
    def flush():
        save(path, dict(pool_id=pid, pool_input_sha256=gs.digest(pool), teams=list(rows.values())))
    with Engine() as engine:
        for key, request in wanted.items():
            if key in rows:
                continue
            ws = request['member_workers'].split('|')
            row = engine.evaluate(pool, ws)
            assert key == row['team_key'] and int(request['n']) == row['k']
            rows[key] = row
            if (len(rows)-initially) % 200 == 0:
                flush()
    flush()
    return dict(pool_id=pid, requested=len(wanted), new_native=len(rows)-initially,
                resumed=initially, elapsed_seconds=time.monotonic()-start,
                finite=sum(r.get('B8L2') is not None for r in rows.values()),
                complete=sum(bool(r.get('complete_evaluable')) for r in rows.values()))


def export(output_dir):
    output_dir = Path(output_dir)
    scalar = []; geometry = []
    for p in sorted((output_dir/'pools').glob('*.json.gz')):
        for row in gs.read(p)['teams']:
            scalar.append(native.scalar_row(row))
            geometry.append(dict(team_key=row['team_key'], pool_id=row['pool_id'],
                member_workers='|'.join(row['member_workers']),
                member_object_ids='|'.join(row['member_object_ids']), k=row['k'],
                score_status=row.get('score_status'), complete_evaluable=row.get('complete_evaluable'),
                reference_id=row.get('reference_id'), reference_version=row.get('reference_version'),
                geometry_json=json.dumps(gs.clean(row.get('geometry')), separators=(',',':'), allow_nan=False),
                node_supports='|'.join(map(str,row.get('node_supports',[]))), minimum_support=row.get('minimum_support')))
    save_csv(output_dir/'ENDPOINT_SCALARS.csv.gz', pd.DataFrame(scalar))
    save_csv(output_dir/'ENDPOINT_GEOMETRY.csv.gz', pd.DataFrame(geometry))
    return len(scalar)


def run(request_path, output_dir, jobs):
    request_path=Path(request_path); output_dir=Path(output_dir); output_dir.mkdir(parents=True,exist_ok=True)
    if '.json' in request_path.name:
        obj = gs.read(request_path)
        req = pd.DataFrame(obj if isinstance(obj,list) else obj['requests'])
        if 'member_workers' not in req:
            req['member_workers'] = req['workers'].map(lambda ws:'|'.join(sorted(ws)))
    else:
        req = pd.read_csv(request_path, keep_default_na=False)
    assert not req.team_key.duplicated().any()
    pools = gs.pool_lookup(); done = []; start=time.monotonic()
    payloads = [(pools[pid], g.to_dict('records'), output_dir) for pid,g in req.groupby('pool_id',sort=True)]
    with ProcessPoolExecutor(max_workers=jobs) as executor:
        futures=[executor.submit(worker, p) for p in payloads]
        for f in as_completed(futures):
            result=f.result();done.append(result)
            save(output_dir/'PROGRESS.json', dict(pools=done,wall_seconds=time.monotonic()-start))
            print(json.dumps(result),flush=True)
    total = export(output_dir)
    assert total == len(req)
    receipt=dict(request_sha256=hashlib.sha256(request_path.read_bytes()).hexdigest(),
        requested=total,pools=len(done),new_native=sum(x['new_native'] for x in done),
        resumed=sum(x['resumed'] for x in done),wall_seconds=time.monotonic()-start,
        jobs=jobs,by_pool=done,scoring_fusion_and_eligibility_unchanged=True)
    save(output_dir/'RUN_RECEIPT.json',receipt)
    print(json.dumps(receipt),flush=True)


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--requests',required=True);p.add_argument('--output',required=True);p.add_argument('--jobs',type=int,default=4)
    a=p.parse_args();run(a.requests,a.output,a.jobs)
