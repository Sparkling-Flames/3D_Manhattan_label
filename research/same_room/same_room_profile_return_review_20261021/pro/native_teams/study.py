"""Same-room exact swaps and source/outside-history team policies.

New execution from frozen repository inputs. This is a reconstruction of study
questions, NOT recovery of the missing previous runtime or request bank.
The request bank is saved before any target team is evaluated.
"""
from __future__ import annotations
import sys as _delivery_sys
from pathlib import Path as _DeliveryPath
_delivery_root = next((p for p in _DeliveryPath(__file__).resolve().parents if (p / 'direct_io.py').is_file()))
_delivery_sys.path.insert(0, str(_delivery_root))
from direct_io import read_csv as _read_csv, open_data as _open_data, write_csv as _write_csv, write_bytes as _write_bytes, data_exists as _data_exists
import argparse, gzip, hashlib, itertools, json, math, os, sys, time
from collections import defaultdict, Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
for k in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[k] = '1'
import numpy as np
import pandas as pd
OUT = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('HOHONET_REPO', str(OUT.parents[2] / 'hohonet')))
if not _data_exists(ROOT / 'research'):
    ROOT = OUT.parents[2].parent / 'hohonet'
TAX = ROOT / 'research/workers/personnel_taxonomy_20261021'
sys.path[:0] = ['/tmp/hohonet_deps', str(TAX / 'fusion')]
import study as taxstudy
SEED = 2026102143

def read(p):
    p = Path(p)
    with _open_data(p, 'rt') if p.suffix == '.gz' else p.open() as f:
        return json.load(f)

def clean(v):
    if isinstance(v, dict):
        return {str(k): clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple, np.ndarray)):
        return [clean(x) for x in v]
    if isinstance(v, np.generic):
        return clean(v.item())
    if isinstance(v, float) and (not math.isfinite(v)):
        return None
    return v

def save(p, v):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    b = json.dumps(clean(v), ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()
    _write_bytes(p, gzip.compress(b, mtime=0) if p.suffix == '.gz' else b)

def csv(p, d):
    d = pd.DataFrame(d)
    _write_csv(d, p, index=False, compression={'method': 'gzip', 'mtime': 0} if str(p).endswith('.gz') else None)

def digest(v):
    return hashlib.sha256(json.dumps(clean(v), sort_keys=True).encode()).hexdigest()

def rng(v):
    return np.random.default_rng(int(digest([SEED, v])[:16], 16))

def teamkey(pid, ws):
    raw = json.dumps(sorted(ws), sort_keys=True, separators=(',', ':')).encode()
    return pid + '__' + hashlib.sha256(raw).hexdigest()[:20]

def mean(ws, values):
    return float(np.mean([values[w] for w in ws]))

def inputs():
    pools = read(taxstudy.FUSION / 'INPUT_SNAPSHOT.json.gz')['images']
    labs = _read_csv(TAX / 'labels/lobo_labels.csv', keep_default_na=False)
    labels = {(r.condition, r.heldout_building, r.worker_id): r._asdict() for r in labs.itertuples(index=False)}
    hist = _read_csv(ROOT / 'research/workers/personnel_profiles_composition_20261020/tables/history_lobo.csv')
    histories = {(r.target_building, r.worker_id, r.condition, r.origin, r.panel): r._asdict() for r in hist.itertuples(index=False)}
    relations = read(ROOT / 'research/same_room/relation_adoption_20261016/relations.json')
    if isinstance(relations, dict):
        relations = relations.get('relations', relations.get('pairs'))
    byimage = defaultdict(list)
    for p in pools:
        byimage[p['meta']['image_id']].append(p)
    pairs = []
    for r in relations:
        if not r.get('physical_adopted'):
            continue
        for a, b in itertools.product(byimage[r['image_a']], byimage[r['image_b']]):
            if a['meta']['condition'] != b['meta']['condition'] or a['meta']['layer'] != b['meta']['layer']:
                continue
            pairs.append((a, b, r))
    return (pools, labels, histories, pairs)

def prepare():
    pools, labels, histories, pairs = inputs()
    events = []
    policies = []
    capacity = []
    requests = {}
    case_defs = []

    def add(p, ws, kind, full=False):
        key = teamkey(p['pool_id'], ws)
        if key not in requests:
            requests[key] = dict(team_key=key, pool_id=p['pool_id'], workers=sorted(ws), k=len(ws), full_state=full, uses=[kind])
        else:
            requests[key]['full_state'] |= full
            if kind not in requests[key]['uses']:
                requests[key]['uses'].append(kind)
        return key
    for pa, pb, rel in pairs:
        ma = pa['meta']
        cond = ma['condition']
        building = ma['building']
        layer = ma['layer']
        pairid = 'PAIR_' + digest([pa['pool_id'], pb['pool_id']])[:16]
        aa = {r['worker_id']: r for r in pa['records']}
        bb = {r['worker_id']: r for r in pb['records']}
        common = sorted(aa.keys() & bb.keys())
        panel = 'doorway' if layer.startswith('doorway') else 'ordinary'
        hist = {w: histories.get((building, w, cond, aa[w]['origin'], panel), {}) for w in common}
        lab = {w: labels.get((cond, building, w), {}) for w in common}
        meta = dict(pair_id=pairid, group_ids='|'.join(rel.get('user_group_ids', [])), scope_comparable=rel.get('scope_comparable'), relation_tier=rel.get('tier'), condition=cond, building=building, layer=layer, image_a=ma['image'], image_b=pb['meta']['image'], pool_a=pa['pool_id'], pool_b=pb['pool_id'], common_workers=len(common))
        tiers = ['primary_coarse_class', 'primary_fine_class'] if cond == 'manual' else ['primary_coarse_class', 'primary_fine_class']
        for tier in tiers:
            present = sorted({lab[w].get(tier, '') for w in common} - {'', 'unassigned', 'unknown', 'insufficient_evidence'})
            for c, d in itertools.permutations(present, 2):
                if tier == 'primary_fine_class':
                    parent = {lab[w].get(tier): lab[w].get('primary_coarse_class') for w in common}
                    if parent[c] != parent[d]:
                        continue
                for m in [1, 2] if tier == 'primary_coarse_class' else [1]:
                    sizes = [3, 5, 6, 7, 9, 13] if m == 1 and tier == 'primary_coarse_class' else [5, 6, 9] if m == 2 else [5, 9]
                    byorigin = {o: ([w for w in common if lab[w].get(tier) == c and aa[w]['origin'] == o], [w for w in common if lab[w].get(tier) == d and aa[w]['origin'] == o]) for o in ['new', 'v1']}
                    origins = [o for o, (u, v) in byorigin.items() if len(u) >= 2 * m and len(v) >= m]
                    capacity.append(dict(meta, tier=tier, outgoing=c, incoming=d, m=m, feasible_block=bool(origins)))
                    if not origins:
                        continue
                    rr = rng([pairid, tier, c, d, m])
                    origin = origins[int(rr.integers(len(origins)))]
                    ca, cb = byorigin[origin]
                    z = rr.choice(sorted(ca), 2 * m, replace=False).tolist()
                    ablk = z[:m]
                    bblk = z[m:]
                    cblk = rr.choice(sorted(cb), m, replace=False).tolist()
                    reserve = rr.permutation(sorted(set(common) - set(ablk + bblk + cblk))).tolist()
                    block_designs = [('capacity_random', ablk, bblk, cblk, reserve)]
                    if m == 1 and tier == 'primary_coarse_class':
                        q = {w: hist[w].get('Q_peer', np.nan) for w in common}
                        matches = [(b, cw) for o, (u, v) in byorigin.items() for b in u for cw in v if hist[b].get('Q_supported_8images_3buildings') and hist[cw].get('Q_supported_8images_3buildings') and np.isfinite(q[b]) and np.isfinite(q[cw]) and (abs(q[b] - q[cw]) <= 3) and (sum((aa[a]['origin'] == o for a in u if a != b)) >= 1)]
                        for ix in rr.permutation(len(matches))[:3]:
                            b, cw = matches[int(ix)]
                            others = sorted((w for w in common if w != b and lab[w].get(tier) == c and (aa[w]['origin'] == aa[b]['origin'])))
                            a = others[int(rr.integers(len(others)))]
                            res = rr.permutation(sorted(set(common) - {a, b, cw})).tolist()
                            block_designs.append(('outside_Q_gap_le3', [a], [b], [cw], res))
                    for design, ablk, bblk, cblk, reserve in block_designs:
                        path = 'PATH_' + digest([pairid, tier, c, d, m, design, ablk, bblk, cblk, reserve])[:18]
                        for n in sizes if design == 'capacity_random' else [5, 9]:
                            if len(reserve) < n - m:
                                continue
                            core = reserve[:n - m]
                            for p in [pa, pb]:
                                e = dict(meta, design=design, tier=tier, outgoing_class=c, incoming_class=d, n=n, m=m, path_id=path, pool_id=p['pool_id'], image=p['meta']['image'], difficulty=p['meta']['difficulty'], reference_id=p['meta']['reference_id'], reference_version=p['meta']['reference_version'], core_workers=sorted(core), A_block=sorted(ablk), B_block=sorted(bblk), C_block=sorted(cblk))
                                for arm, bl in [('A', ablk), ('B', bblk), ('C', cblk)]:
                                    ws = sorted(core + bl)
                                    e[arm + '_workers'] = ws
                                    e[arm + '_team_key'] = add(p, ws, 'exact_swap')
                                    e[arm + '_class_counts'] = dict(Counter((lab[w].get(tier, 'unknown') for w in ws)))
                                e['block_history_Q_gap'] = mean(cblk, {w: hist[w].get('Q_peer', np.nan) for w in common}) - mean(bblk, {w: hist[w].get('Q_peer', np.nan) for w in common})
                                e['event_id'] = 'EV_' + digest(e)[:18]
                                events.append(e)
        for source, target in [(pa, pb), (pb, pa)]:
            sr = {r['worker_id']: r for r in source['records']}
            for domain in ['all', 'new', 'new_timed_history']:
                avail = [w for w in common if hist[w].get('Q_supported_8images_3buildings') and np.isfinite(hist[w].get('Q_peer', np.nan)) and (domain == 'all' or sr[w]['origin'] == 'new')]
                if domain == 'new_timed_history':
                    avail = [w for w in avail if hist[w].get('T_supported_8images_3buildings') and np.isfinite(hist[w].get('relative_time', np.nan)) and (sr[w].get('source_time_seconds') is not None) and (sr[w]['source_time_seconds'] > 0)]
                q = {w: hist[w].get('Q_peer') for w in avail}
                srcq = {w: sr[w]['B8L2'] for w in avail}
                half = {w: 0.5 * q[w] + 0.5 * srcq[w] for w in avail}

                def best(values, n):
                    return sorted(sorted(avail, key=lambda w: (-values[w], w))[:n])

                def fast(base, qual, cost):
                    current = list(base)
                    floor = mean(base, qual) - 2
                    while True:
                        candidates = []
                        for old in current:
                            for new in sorted(set(avail) - set(current)):
                                ws = sorted(set(current) - {old} | {new})
                                if mean(ws, qual) >= floor and sum((cost[w] for w in ws)) < sum((cost[w] for w in current)) - 1e-09:
                                    candidates.append((sum((cost[w] for w in ws)), -mean(ws, qual), ws))
                        if not candidates:
                            break
                        current = min(candidates)[2]
                    return current
                for n in [3, 4, 5, 6, 7, 9, 13]:
                    if len(avail) <= n:
                        continue
                    teams = {'outside_Q': best(q, n), 'source_Q': best(srcq, n), 'half_Q': best(half, n)}
                    base = teams['half_Q']
                    wanted = math.ceil(n / 2)
                    current = list(base)
                    while sum((lab[w].get('primary_coarse_class') == 'M1' for w in current)) < wanted:
                        candidates = []
                        for old in current:
                            if lab[old].get('primary_coarse_class') == 'M1':
                                continue
                            for new in sorted(set(avail) - set(current)):
                                if lab[new].get('primary_coarse_class') != 'M1':
                                    continue
                                ws = sorted(set(current) - {old} | {new})
                                if mean(ws, half) >= mean(base, half) - 2:
                                    candidates.append((-mean(ws, half), ws))
                        if not candidates:
                            break
                        current = min(candidates)[1]
                    if cond == 'manual':
                        teams['half_Q_structure'] = current
                    if domain == 'new_timed_history':
                        times = {w: sr[w]['source_time_seconds'] for w in avail}
                        ht = {w: hist[w]['relative_time'] for w in avail}
                        teams['outside_Q_outside_T_fast'] = fast(teams['outside_Q'], q, ht)
                        teams['outside_Q_source_T_fast'] = fast(teams['outside_Q'], q, times)
                    for rep in range(3):
                        teams['random_' + str(rep)] = sorted(rng([pairid, source['pool_id'], domain, n, rep]).choice(avail, n, False).tolist())
                    for policy, ws in teams.items():
                        policies.append(dict(meta, source_pool_id=source['pool_id'], source_image=source['meta']['image'], target_pool_id=target['pool_id'], target_image=target['meta']['image'], domain=domain, n=n, policy=policy, workers=ws, available_workers=len(avail), available_worker_ids=avail, team_key=add(target, ws, 'selection'), history_Q_mean=mean(ws, q), source_Q_mean=mean(ws, srcq), selected_source_activity_seconds=sum((sr[w]['source_time_seconds'] for w in ws)) if all((sr[w].get('source_time_seconds') is not None for w in ws)) else None, source_roster_activity_seconds=sum((sr[w]['source_time_seconds'] for w in avail)) if all((sr[w].get('source_time_seconds') is not None for w in avail)) else None, source_activity_known_n=sum((sr[w].get('source_time_seconds') is not None for w in avail)), class_counts=dict(Counter((lab[w].get('primary_coarse_class', 'unknown') for w in ws)))))
    cases = [('G117_repeat', ['jtcxE69GiFV-26', 'jtcxE69GiFV-28'], {'B': ['W109', 'W121', 'W132', 'W133', 'W110', 'W113'], 'C': ['W109', 'W121', 'W132', 'W133', 'W102', 'W126']}), ('G015_reversal', ['7y3sRwLe3Va-11', '7y3sRwLe3Va-19'], {'B': ['W100', 'W110', 'W128'], 'C': ['W100', 'W110', 'W122']}), ('G205_position', ['wc2JMjhGNzB-03', 'wc2JMjhGNzB-54', 'wc2JMjhGNzB-61'], {'same7': ['W012', 'W017', 'W031', 'W032', 'W130', 'W133', 'W134']})]
    for name, images, arms in cases:
        for p in pools:
            if p['meta']['image'] in images and p['meta']['layer'] == 'ordinary_manual':
                for arm, ws in arms.items():
                    if set(ws) <= {r['worker_id'] for r in p['records']}:
                        case_defs.append(dict(case_id=name, arm=arm, pool_id=p['pool_id'], image=p['meta']['image'], workers=ws, team_key=add(p, ws, 'reconstructed_case', True)))
    save(OUT / 'REQUESTS.json.gz', list(requests.values()))
    save(OUT / 'SWAP_DESIGN.json.gz', events)
    save(OUT / 'SELECTION_DESIGN.json.gz', policies)
    save(OUT / 'CASE_DEFINITIONS.json', case_defs)
    csv(OUT / 'CAPACITY.csv', capacity)
    save(OUT / 'DESIGN_RECEIPT.json', dict(provenance='本轮重建及新增；上轮请求银行未恢复', seed=SEED, main_commit='561584c8f64d5349d497ec1c6e91f1aeb4bbd7c9', label_version='personnel_taxonomy_20261021_v1; taxonomy_corrected_20261021_r1', relation_version='same_room_user_working_classification_20261016_v2', pairs=len(pairs), events=len(events), selection_rows=len(policies), teams=len(requests), swaps='same exact disjoint A/B/C blocks and nested background across both views; matched origin; quality match selected using LOBO Q only', quality_match='abs external block Q_peer gap<=3; at most three stable-seed choices per pair/direction; n5/n9', selection='shared eligible roster; outside histories min8images/3buildings; source Q known; target availability known; target scores/times unused', fast='new source activity only; greedy one-person cost-reducing swaps within 2 mean external Q_peer points; external T and source T separately', target_activity='native source_time_total_seconds is activity ON THE TARGET IMAGE; preserved name in native team, renamed in policy output', weighting='reference panels within image, repeated source/events within target image, images within building, equal buildings', validation='internal reanalysis and reconstructed experiments on current fixed dataset; not new external validation'))
    print('Prepared', len(events), 'swap view events;', len(policies), 'policy rows;', len(requests), 'unique teams', flush=True)

def run_pool(pool, requests):
    fe, fr, *_ = taxstudy.setup_engine()
    path = OUT / 'runtime' / (pool['pool_id'] + '.json.gz')
    if _data_exists(path):
        previous = read(path)
        if previous.get('request_hash') == digest(requests):
            return dict(pool_id=pool['pool_id'], teams=len(previous['teams']), cached=True)
    rows = {}
    states = {}
    t = time.monotonic()
    cache = {}
    with fe.cached_matching(), fe.scoring_engine(fe.ENGINE / 'measurement_engine.zip', fe.ENGINE / 'working_models.py') as (engine, models):
        for q in requests:
            v = fr.evaluate_one(pool, q['workers'], engine, models, cache, full_state=q['full_state'])
            if 'full_state' in v:
                states[q['team_key']] = v.pop('full_state')
            rows[q['team_key']] = v
    save(path, dict(request_hash=digest(requests), teams=rows, states=states))
    return dict(pool_id=pool['pool_id'], teams=len(rows), cached=False, seconds=time.monotonic() - t)

def run(jobs):
    pools, _, _, _ = inputs()
    ps = {p['pool_id']: p for p in pools}
    qs = read(OUT / 'REQUESTS.json.gz')
    reused = {}
    sources = {}
    for p in [TAX / 'fusion/TEAMS.json.gz', TAX / 'fusion/nested/TEAMS.json.gz', TAX / 'fusion/a2/TEAMS.json.gz']:
        if _data_exists(p):
            try:
                d = read(p)
                if isinstance(d, dict):
                    for k, v in d.items():
                        if isinstance(v, dict) and 'member_workers' in v:
                            reused[k] = v
                            sources[k] = str(p.relative_to(ROOT))
            except Exception:
                pass
    needed = defaultdict(list)
    used = {}
    for q in qs:
        k = q['team_key']
        if k in reused and (not q['full_state']) and (sorted(reused[k]['member_workers']) == q['workers']):
            used[k] = reused[k]
        else:
            needed[q['pool_id']].append(q)
    receipts = []
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        fs = {ex.submit(run_pool, ps[pid], q): pid for pid, q in needed.items()}
        for f in as_completed(fs):
            v = f.result()
            receipts.append(v)
            print(dict(v, done=len(receipts), total=len(fs)), flush=True)
    states = {}
    for pid in needed:
        d = read(OUT / 'runtime' / (pid + '.json.gz'))
        used.update(d['teams'])
        states.update(d['states'])
    save(OUT / 'TEAMS.json.gz', used)
    save(OUT / 'CASE_STATES.json.gz', states)
    save(OUT / 'RUN_RECEIPT.json', dict(teams=len(used), newly_evaluated_teams=sum((len(q) for q in needed.values())), reused_teams=len(qs) - sum((len(q) for q in needed.values())), reused_sources={k: sources[k] for k in used if k in sources and (not any((q['team_key'] == k for q in needed.get(used[k]['pool_id'], []))))}, pools=receipts))

def assemble():
    teams = read(OUT / 'TEAMS.json.gz')
    events = read(OUT / 'SWAP_DESIGN.json.gz')
    policies = read(OUT / 'SELECTION_DESIGN.json.gz')
    _, _, _, corner_compare, *_ = taxstudy.setup_engine()
    fields = ['B8L2', 'D10', 'nodes', 'omission', 'extension', 'S_bottom_deg', 'Hmean', 'dir', 'complete_evaluable', 'score_status', 'reference_nodes', 'ref_node_recall_5', 'ref_node_recall_9', 'source_time_total_seconds']
    for e in events:
        for a in 'ABC':
            for f in fields:
                e[a + '_' + f] = teams[e[a + '_team_key']].get(f)
        for f in ['B8L2', 'D10', 'nodes', 'omission', 'extension', 'ref_node_recall_5']:
            x, y = (e['B_' + f], e['C_' + f])
            e['net_' + f] = y - x if x is not None and y is not None else None
        for a in 'BC':
            x, y = (e['A_B8L2'], e[a + '_B8L2'])
            e[('within' if a == 'B' else 'cross') + '_abs_Q'] = abs(y - x) if x is not None and y is not None else None
            metrics, _ = corner_compare(teams[e['A_team_key']], teams[e[a + '_team_key']])
            arm = 'within' if a == 'B' else 'cross'
            for f in ['status', 'same_count', 'complete', 'bev_mean_h', 'bev_max_h', 'top_mean_h', 'angle_deg']:
                e[arm + '_' + f] = metrics.get(f)
    for e in policies:
        t = teams[e['team_key']]
        for f in fields:
            e[f] = t.get(f)
        e['target_activity_seconds'] = t.get('source_time_total_seconds')
        e['target_activity_known_n'] = t.get('source_time_known_n')
        e['target_member_object_ids'] = t.get('member_object_ids')
        e['reference_id'] = t.get('reference_id')
        e['reference_version'] = t.get('reference_version')
        e['pool_id'] = t['pool_id']
        e['difficulty'] = t['difficulty']

    def flat(rows):
        return [{k: json.dumps(v, ensure_ascii=False, separators=(',', ':')) if isinstance(v, (list, dict)) else v for k, v in r.items()} for r in rows]
    csv(OUT / 'SWAP_EVENTS.csv.gz', flat(events))
    csv(OUT / 'SELECTION_RESULTS.csv.gz', flat(policies))
    csv(OUT / 'CASE_TEAMS.csv', [dict(c, **{f: teams[c['team_key']].get(f) for f in fields}) for c in read(OUT / 'CASE_DEFINITIONS.json')])
    print('Assembled', len(events), len(policies))
if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('stage', choices=['prepare', 'run', 'assemble'])
    ap.add_argument('--jobs', type=int, default=4)
    a = ap.parse_args()
    {'prepare': prepare, 'run': lambda: run(a.jobs), 'assemble': assemble}[a.stage]()
