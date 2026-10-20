"""Expand real replacement contexts using only frozen pool metadata and IDs.

One core plus every eligible entrant gives all entrant-pair comparisons without
fusing the same team twice. No target quality, geometry, worker traits or labels
are used to choose an anchor. Pair observations are not independent teams/images.
"""
from __future__ import annotations
import argparse, collections, datetime, gzip, hashlib, json, random
from pathlib import Path

NODES = [3, 4, 5, 6, 7, 9, 11, 13, 15, 17, 19, 21, 23, 25, 29, 31]
SEED = 2026102001

def read(path):
    with (gzip.open(path, 'rt') if str(path).endswith('.gz') else open(path)) as f:
        return json.load(f)

def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    path.write_bytes(gzip.compress(raw, compresslevel=6, mtime=0) if path.suffix == '.gz' else raw)

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def team_key(pid, workers):
    return pid + '__' + digest(sorted(workers))[:20]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--snapshot', type=Path, required=True)
    ap.add_argument('--split', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    snapshot = read(a.snapshot); split = read(a.split)
    history = set(split['history_buildings'])
    anchors, requests, skips = [], {}, []
    by_n = collections.Counter(); by_difficulty = collections.Counter()
    workers = set(); buildings = set(); images = set()
    for pool in sorted(snapshot['images'], key=lambda p: p['pool_id']):
        meta = pool['meta']; pid = pool['pool_id']
        if meta['building'] not in history or meta['layer'] != 'ordinary_manual':
            continue
        ws = sorted({r['worker_id'] for r in pool['records']})
        reps = 1 if meta['difficulty'] == '简单' else 2
        for n in NODES:
            if len(ws) - n + 1 < 4:
                skips.append(dict(pool_id=pid, k=n, pool_n=len(ws), reason='fewer_than_four_entrant_alternatives'))
                continue
            for rep in range(reps):
                key = [SEED, pid, n, rep]
                rng = random.Random(int(digest(key)[:16], 16))
                core = sorted(rng.sample(ws, n - 1)); entrants = sorted(set(ws) - set(core))
                aid = 'H20_' + digest(key)[:18]
                entrant_teams = {}
                for w in entrants:
                    members = sorted(core + [w]); tk = team_key(pid, members)
                    requests.setdefault(tk, dict(request_id=tk, pool_id=pid, k=n, worker_ids=members))
                    entrant_teams[w] = tk
                anchors.append(dict(anchor_id=aid, pool_id=pid, building=meta['building'], image=meta['image'],
                                    difficulty=meta['difficulty'], layer=meta['layer'], k=n, m=1,
                                    replicate=rep, core_workers=core, entrant_workers=entrants,
                                    entrant_teams=entrant_teams, pair_count=len(entrants)*(len(entrants)-1)//2))
                by_n[n] += 1; by_difficulty[meta['difficulty']] += 1
                workers.update(ws); buildings.add(meta['building']); images.add(pid)
    common = dict(schema='actual_replacement_history_expansion_v1', seed=SEED, n_nodes=NODES,
                  selection='All eligible ordinary Manual history pools; every listed n if >=4 entrants; all remaining entrant pairs within a metadata-only random core; one easy / two other cores.',
                  inputs=dict(snapshot_sha256=hashlib.sha256(a.snapshot.read_bytes()).hexdigest(),
                              split_sha256=hashlib.sha256(a.split.read_bytes()).hexdigest()),
                  excluded='No target score, annotation geometry, class, source or worker phenotype used for selection.')
    write(a.out/'history_requests.json.gz', dict(common, requests=list(requests.values())))
    write(a.out/'history_anchors.json.gz', dict(common, anchors=anchors))
    write(a.out/'history_capacity_skips.json.gz', skips)
    receipt = dict(common, registered_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   requested_team_rows=sum(len(x['entrant_workers']) for x in anchors),
                   unique_teams=len(requests), anchors=len(anchors),
                   pair_observations=sum(x['pair_count'] for x in anchors), pools=len(images),
                   buildings=len(buildings), workers=len(workers), by_n=dict(by_n),
                   by_difficulty=dict(by_difficulty), capacity_skips=len(skips),
                   coverage_limit='Listed n values and seeded cores only, not all possible teams, cores or all integer n. All pairs within those cores are enumerated.')
    write(a.out/'HISTORY_PANEL_REGISTRATION.json', receipt)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
