"""Historical-Q composition study on frozen HOHONET v2 inputs.

The module creates exact requests before reading team outcomes. It calls the
repository's unchanged fusion/scoring functions. All output paths are explicit;
no repository inputs or qualification flags are modified.
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time

for _key in ('OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS'):
    os.environ[_key] = '1'

import numpy as np
import pandas as pd

SEED = 2026102039
FUSION_REL = 'research/workers/pro_personnel_v2_archive_20261019/work_v2_20261019/fusion'
COMPOSITION_REL = 'research/workers/personnel_interchangeability_20261020/analysis/composition'
CORE_REL = 'research/workers/personnel_interchangeability_20261020/interchangeability_20261020/core_replay'


def read(path):
    p = Path(path)
    return json.loads(gzip.decompress(p.read_bytes()) if p.suffix == '.gz' else p.read_bytes())


def clean(v):
    if isinstance(v, dict):
        return {str(k): clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple, np.ndarray)):
        return [clean(x) for x in v]
    if isinstance(v, np.generic):
        return clean(v.item())
    if isinstance(v, float) and not math.isfinite(v):
        return None
    return v


def save(path, value):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(clean(value), ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()
    p.write_bytes(gzip.compress(raw, compresslevel=5, mtime=0) if p.suffix == '.gz' else raw)


def digest(v):
    return hashlib.sha256(json.dumps(v, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def tkey(pid, workers):
    return pid + '__' + digest(sorted(workers))[:20]


def rng(*v):
    return np.random.default_rng(int(digest([SEED, *v])[:16], 16))


def write_csv(path, frame):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding='utf-8',
                 compression={'method': 'gzip', 'mtime': 0} if str(path).endswith('.gz') else None)


def prepare(args):
    pools = read(args.repo / FUSION_REL / 'INPUT_SNAPSHOT.json.gz')['images']
    features = pd.read_csv(args.features)
    fs = features[(features.panel == 'ordinary') & features.Q_supported_8images_3buildings]
    feature_lookup = {(r.target_building, r.condition, r.worker_id): r for r in fs.itertuples()}
    split = read(args.repo / COMPOSITION_REL / 'SPLIT.json')
    phases = {b: phase for phase in ('history', 'discovery', 'validation')
              for b in split[phase + '_buildings']}

    # One image per building x difficulty, selected using identifiers only.
    # Every ordinary Semi, doorway and special pool receives the broad grid.
    groups = collections.defaultdict(list)
    full = set()
    for p in pools:
        m = p['meta']
        if m['layer'] == 'ordinary_manual':
            groups[m['building'], m['difficulty']].append(p)
        else:
            full.add(p['pool_id'])
    for ps in groups.values():
        ps.sort(key=lambda p: digest([SEED, 'metadata_grid', p['pool_id']]))
        full.update(p['pool_id'] for p in ps[:1])

    requests = {}
    events = []
    inventory = []
    selections = []

    def request(p, ws):
        ws = sorted(ws)
        key = tkey(p['pool_id'], ws)
        if key not in requests:
            requests[key] = dict(request_id=key, pool_id=p['pool_id'], worker_ids=ws, k=len(ws))
        return key

    def event(p, family, ws, **kw):
        m = p['meta']
        e = dict(event_id=f'Q{len(events):07d}', family=family, pool_id=p['pool_id'],
                 image=m['image'], image_id=m['image_id'], building=m['building'],
                 condition=m['condition'], layer=m['layer'], difficulty=m['difficulty'],
                 phase=phases[m['building']], historical_profile_panel='ordinary',
                 team_key=request(p, ws), n=len(ws), **kw)
        events.append(e)
        return e

    for p in pools:
        m = p['meta']
        by = {r['worker_id']: r for r in p['records']}
        h, low = [], []
        for w in by:
            f = feature_lookup.get((m['building'], m['condition'], w))
            if f is not None and math.isfinite(f.Q_peer):
                (h if f.Q_peer >= 0 else low).append(w)
                selections.append(dict(pool_id=p['pool_id'], image=m['image'], worker_id=w,
                    target_building=m['building'], condition=m['condition'], origin=by[w]['origin'],
                    Q_group='H' if f.Q_peer >= 0 else 'L', historical_Q_peer=f.Q_peer,
                    historical_Q_mean=f.Q_mean, historical_Q_q10=f.Q_q10,
                    n_quality_images=f.n_quality_images, n_quality_buildings=f.n_quality_buildings,
                    historical_profile_panel='ordinary'))
        h.sort(); low.sort()
        inventory.append(dict(m, H_n=len(h), L_n=len(low), unknown_n=len(by)-len(h)-len(low),
            broad_grid=p['pool_id'] in full,
            pure_n7_available=min(len(h), len(low)) >= 7,
            source='unchanged frozen quality-and-vote-eligible pool'))
        if len(h) + len(low) < 3:
            continue

        ns = list(range(3, 10)) + [11, 13] if p['pool_id'] in full else [7]
        for n in ns:
            if len(h) + len(low) < n:
                continue
            lo, hi = max(0, n-len(low)), min(n, len(h))
            hs = list(range(lo, hi+1)) if n <= 9 else sorted({x for x in [lo, hi, 0, 1, n//4, n//2, n-2, n-1, n] if lo <= x <= hi})
            for rep in range(args.replicates):
                prng = rng('grid', p['pool_id'], n, rep)
                hp, lp = list(prng.permutation(h)), list(prng.permutation(low))
                for nh in hs:
                    event(p, 'grid', hp[:nh] + lp[:n-nh], H=nh, L=n-nh,
                          replicate=rep, source_policy='all_supported', pure_comparison_available=lo == 0 and hi == n)
                ws = list(prng.choice(h + low, n, replace=False))
                nh = len(set(ws) & set(h))
                event(p, 'random', ws, H=nh, L=n-nh, replicate=rep,
                      source_policy='all_supported', pure_comparison_available=lo == 0 and hi == n)

        # Same-origin sensitivity at the common n=7; source semantics do not mix.
        hn = [w for w in h if by[w]['origin'] == 'new']
        ln = [w for w in low if by[w]['origin'] == 'new']
        n = 7
        if len(hn) + len(ln) >= n:
            lo, hi = max(0, n-len(ln)), min(n, len(hn))
            for rep in range(2):
                prng = rng('new_grid', p['pool_id'], rep)
                hp, lp = list(prng.permutation(hn)), list(prng.permutation(ln))
                for nh in range(lo, hi+1):
                    event(p, 'grid', hp[:nh]+lp[:n-nh], H=nh, L=n-nh, replicate=rep,
                          source_policy='new_only', pure_comparison_available=lo == 0 and hi == n)

        if p['pool_id'] not in full:
            continue
        # A fixed core is expanded along both incoming quality groups. The
        # baseline core and exact prefix members stay fixed through each path.
        for core_group, base, other in [('H', h, low)]:
            for core_n in [3, 5]:
                if len(base) < core_n:
                    continue
                for rep in range(2):
                    prng = rng('growth', p['pool_id'], core_group, core_n, rep)
                    bp, op = list(prng.permutation(base)), list(prng.permutation(other))
                    core = bp[:core_n]
                    for incoming, stream in [(core_group, bp[core_n:]), ('L' if core_group == 'H' else 'H', op)]:
                        path_id = f'{p["pool_id"]}__{core_group}{core_n}_add{incoming}_{rep}'
                        for add in range(min(10, len(stream))+1):
                            ws = core + stream[:add]
                            nh = len(set(ws) & set(h))
                            event(p, 'growth', ws, H=nh, L=len(ws)-nh, replicate=rep,
                                  source_policy='all_supported', path_id=path_id, core_group=core_group,
                                  core_n=core_n, core_workers=core, incoming_group=incoming, added_n=add,
                                  added_workers=stream[:add])

        # Matched-background ABC substitutions: A/B replace a block by the same
        # historical Q group; A/C replace exactly the same number by the other.
        # These comparisons have identical origin counts (all-new) in every arm.
        for n, block in [(7, 2), (13, 5)]:
            for outgoing, source, incoming, replacement in [('L', ln, 'H', hn), ('H', hn, 'L', ln)]:
                if len(source) < 2*block or len(replacement) < block or len(hn)+len(ln) < n+2*block:
                    continue
                for rep in range(2):
                    prng = rng('block', p['pool_id'], n, block, outgoing, rep)
                    sp, ip = list(prng.permutation(source)), list(prng.permutation(replacement))
                    a, b, c = sp[:block], sp[block:2*block], ip[:block]
                    remaining = sorted(set(hn+ln)-set(a+b+c))
                    core = list(prng.choice(remaining, n-block, replace=False))
                    eid = f'{p["pool_id"]}__block{n}_{block}_{outgoing}_{rep}'
                    for arm, part in [('A', a), ('B', b), ('C', c)]:
                        ws = core + part; nh = len(set(ws)&set(h))
                        event(p, 'block', ws, H=nh, L=n-nh, replicate=rep,
                              source_policy='new_only', block_event_id=eid, arm=arm, m=block,
                              direction=outgoing+'>'+incoming, core_workers=core, block_workers=part)

    out = args.out
    write_csv(out/'pool_inventory.csv', pd.DataFrame(inventory))
    write_csv(out/'historical_selections.csv.gz', pd.DataFrame(selections))
    save(out/'requests.json.gz', dict(schema='historical_Q_composition_v1', requests=list(requests.values()), events=events))
    registration = dict(seed=SEED, design_created_before_team_results=True,
        feature_file=str(args.features), historical_feature='LOO same-task peer Q residual, ordinary condition-specific history outside target building',
        H_rule='Q_peer>=0', L_rule='Q_peer<0', support='at least 8 quality images and 3 buildings outside target building',
        condition_separation='manual and semi separately; ordinary history applied to doorway/special targets only as labelled conditional transfer',
        broad_grid='one image identifier per building x ordinary-manual difficulty by fixed hash; all Semi/doorway/special pools',
        common_grid='n7 for every capacity-supported pool', grid_members='four independent permutations; changing H by m replaces exactly m workers with common background',
        source_sensitivity='new-only n7 grid and exact new-only ABC block comparisons',
        growth='H cores of 3 and 5; append each group along two fixed orders, 0..10 additions, no target quality selection',
        error_policy='do not impute failures or missing scores; preserve all requested members',
        interpretation='retrospective internal LOBO policy evaluation; these images and workers were studied before; no external blind claim',
        total_requests=len(requests), event_rows=len(events), attempted_pools=len({r['pool_id'] for r in requests.values()}),
        source_quality_pools=len(pools), broad_pools=len(full), source_true_images=len({p['meta']['image_id'] for p in pools}),
        family_counts=dict(collections.Counter(e['family'] for e in events)),
        layers=dict(collections.Counter(p['meta']['layer'] for p in pools)), replicates=args.replicates)
    save(out/'REGISTRATION.json', registration)
    print(json.dumps(registration, ensure_ascii=False, indent=2), flush=True)


def init_engine(repo):
    repo = Path(repo).resolve()
    os.environ['PERSONNEL_V2_REPOSITORY'] = str(repo)
    sys.path[:0] = [str(repo), str(repo/FUSION_REL), str(repo/COMPOSITION_REL)]
    import fusion_engine as fe
    import fusion_runner as fr
    import geometry_diagnostics as gd
    fr.FE = fe
    return fe, fr, gd


def reusable_rows(repo, wanted):
    found = {}
    paths = [(CORE_REL+'/EXPECTED_FINAL_FIELDS.json.gz', 'prior_core_final_fields'),
             ('research/workers/personnel_composition_followup_20261019/TEAMS.json.gz', 'prior_followup_geometry')]
    for rel, origin in paths:
        rows = read(repo/rel)
        for row in (rows.values() if isinstance(rows, dict) else rows):
            key = row['team_key']
            if key in wanted:
                found[key] = dict(row, result_origin=origin, result_source=rel)
    return found


def compute_pool(repo, pool, requests, reused, out):
    fe, fr, gd = init_engine(repo)
    started = time.monotonic()
    target = Path(out)/'native_final'/f'{pool["pool_id"]}.json.gz'
    prior = read(target) if target.exists() else dict(teams=[])
    rows = {r['team_key']: r for r in prior['teams']}
    cached = len(rows)
    wanted = {r['request_id']:r['worker_ids'] for r in requests}
    n_reused = n_new = 0
    score_cache = {}
    with fe.cached_matching(), fe.scoring_engine(fe.ENGINE/'measurement_engine.zip',fe.ENGINE/'working_models.py') as (scorer, models):
        for key, ws in wanted.items():
            if key in rows:
                continue
            if key in reused:
                row = dict(pool['meta'], **{k:v for k,v in reused[key].items() if k not in pool['meta']})
                n_reused += 1
            else:
                row = fr.evaluate_one(pool, ws, scorer, models, score_cache)
                row['result_origin'] = 'new_native_fusion'
                n_new += 1
            # These automatic node/edge measures are explicitly reference-relative
            # diagnostics, not a semantic necessary-wall annotation.
            nr = len(pool['reference']['points_1024x512'])//2
            if row.get('nodes') is not None and row.get('ref_node_recall_9') is not None:
                matched = row['ref_node_recall_9']*nr
                row['ref_node_precision_9'] = matched/row['nodes'] if row['nodes'] else None
                row['ref_unmatched_candidate_nodes_9'] = row['nodes']-matched
            else:
                row['ref_node_precision_9'] = row['ref_unmatched_candidate_nodes_9'] = None
            geo = row.get('geometry')
            if geo and geo.get('footprint'):
                diag = gd.diagnose(geo['footprint'], pool['reference']['floor_xz_h'])
                row.update({k:diag.get(k) for k in ['diag_status','diag_wall_coverage_05','diag_corner_recall_05','diag_reference_corner_n','diag_candidate_corner_n','diag_matched_corner_n']})
                row['diag_corner_precision_05'] = diag.get('diag_matched_corner_n')/diag['diag_candidate_corner_n'] if diag.get('diag_candidate_corner_n') else None
            rows[key] = row
    save(target, dict(pool_id=pool['pool_id'], teams=list(rows.values())))
    return dict(pool_id=pool['pool_id'], wanted=len(wanted), cached=cached, reused_prior=n_reused,
                new_native=n_new, finite_scores=sum(rows[k].get('B8L2') is not None for k in wanted),
                seconds=time.monotonic()-started)


def run(args):
    payload = read(args.out/'requests.json.gz')
    reqs = payload['requests']
    if args.pool:
        reqs = [r for r in reqs if r['pool_id'] in args.pool]
    by = collections.defaultdict(list)
    for r in reqs:
        by[r['pool_id']].append(r)
    pools = {p['pool_id']:p for p in read(args.repo/FUSION_REL/'INPUT_SNAPSHOT.json.gz')['images']}
    reused = reusable_rows(args.repo, {r['request_id'] for r in reqs})
    save(args.out/'REUSE_PRE_RUN.json', dict(matching_prior_teams=len(reused), requested=len(reqs), prior_sources=dict(collections.Counter(r['result_origin'] for r in reused.values()))))
    start = time.monotonic(); receipts = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.jobs) as ex:
        futures = {ex.submit(compute_pool,args.repo,pools[pid],rs,
                   {r['request_id']:reused[r['request_id']] for r in rs if r['request_id'] in reused},args.out):pid for pid,rs in by.items()}
        for f in concurrent.futures.as_completed(futures):
            receipt = f.result(); receipts.append(receipt)
            print(json.dumps(dict(receipt,done=len(receipts),pools=len(by),elapsed=round(time.monotonic()-start,1))), flush=True)
    save(args.out/'RUN_RECEIPT.json', dict(seconds=time.monotonic()-start,jobs=args.jobs,requested=len(reqs),
        actual_new_native=sum(r['new_native'] for r in receipts),reused_prior=sum(r['reused_prior'] for r in receipts),
        resumed_cached=sum(r['cached'] for r in receipts),by_pool=receipts))


def parser():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('command', choices=['prepare','run'])
    ap.add_argument('--repo', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--features', type=Path)
    ap.add_argument('--replicates', type=int, default=4)
    ap.add_argument('--jobs', type=int, default=2)
    ap.add_argument('--pool', action='append')
    return ap


if __name__ == '__main__':
    args = parser().parse_args()
    args.repo = args.repo.resolve(); args.out = args.out.resolve()
    {'prepare':prepare, 'run':run}[args.command](args)
