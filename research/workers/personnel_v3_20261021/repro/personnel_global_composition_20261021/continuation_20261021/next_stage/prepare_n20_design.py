"""Metadata-only extension: all ordinary pools, n=20, retained fine/A2 methods.

No endpoint outcome is read. The native method labels exclude the target
building. Sampling reproduces the existing per-cell deterministic generator;
the endpoint request index is used only for exact cache deduplication.
"""
from __future__ import annotations
import collections, csv, gzip, io, itertools, json, math, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
STUDY = HERE.parents[1]
COMPOSITION = STUDY / 'composition'
sys.path.insert(0, str(COMPOSITION))
import global_study as gs
from prepare_design import sample_members, meta

METHODS = {
    ('M_structure', 'fine', 'manual'),
    ('A2_relation', 'single', 'manual'),
    ('MV_QTD_manual_new', 'fine', 'manual'),
    ('SP_scale', 'fine', 'semi'),
    ('A2_relation', 'single', 'semi'),
    ('MV_QTScopeSemi_semi_new', 'fine', 'semi'),
}
N = 20
DRAWS = 3


def atomic_frame(path, frame, key_columns=()):
    """Serialize completely, validate the full stream, then publish atomically.

    Direct path-based CSV export previously left an incomplete gzip member
    despite the producer returning. A finite-row/key check is therefore part
    of this artifact contract, not merely a ZIP CRC check.
    """
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    text=frame.to_csv(index=False,lineterminator='\n')
    raw=text.encode('utf-8-sig')
    data=gzip.compress(raw,compresslevel=5,mtime=0) if path.suffix=='.gz' else raw
    tmp=path.with_name(path.name+'.tmp')
    nbytes=tmp.write_bytes(data)
    if nbytes!=len(data):raise ValueError('short binary artifact write')
    reread=tmp.read_bytes()
    restored=gzip.decompress(reread) if path.suffix=='.gz' else reread
    if restored!=raw:raise ValueError('artifact bytes differ after write')
    reader=csv.reader(io.StringIO(restored.decode('utf-8-sig')))
    fields=next(reader);indices=[fields.index(c) for c in key_columns];keys=set();n=0
    for row in reader:
        if len(row)!=len(fields):raise ValueError(('ragged_export',str(path),n))
        if indices:
            key=tuple(row[i] for i in indices)
            if key in keys:raise ValueError(('duplicate_export_key',str(path),key))
            keys.add(key)
        n+=1
    if n!=len(frame):raise ValueError(('truncated_export',str(path),n,len(frame)))
    tmp.replace(path)


def main():
    start = time.monotonic()
    pools = gs.pool_lookup()
    maps = gs.method_maps()
    old = {r['team_key']: r for r in gs.read(COMPOSITION / 'ENDPOINT_REQUESTS.json.gz')['requests']}
    requests, memberships, cells, totals = {}, [], [], []
    old_by = collections.defaultdict(list)
    for row in old.values():
        if len(row['member_workers']) == N:
            old_by[row['pool_id']].append(row)
    for pool in sorted(pools.values(), key=lambda p: p['pool_id']):
        if pool['meta']['layer'] not in ('ordinary_manual', 'ordinary_semi'):
            continue
        pid = pool['pool_id']
        formal = {r['worker_id'] for r in pool['records']}
        for (method, tier, condition, building), mapping in sorted(maps.items()):
            if (method, tier, condition) not in METHODS:
                continue
            if (condition, building) != (pool['meta']['condition'], pool['meta']['building']):
                continue
            groups = collections.defaultdict(list)
            for w in sorted(formal & mapping.keys()):
                groups[mapping[w]].append(w)
            capacities = {c: len(ws) for c, ws in groups.items()}
            U = sum(capacities.values())
            if U < N:
                continue
            common = dict(meta(pool), method_id=method, tier=tier, n=N,
                          formal_pool_n=len(formal), labelled_pool_n=U,
                          class_capacities=gs.canonical_counts(capacities))
            old_compositions = collections.Counter()
            for old_row in old_by[pid]:
                ws = old_row['member_workers']
                if set(ws) <= mapping.keys():
                    counts = {c: sum(mapping[w] == c for w in ws) for c in capacities}
                    old_compositions[gs.canonical_counts(counts)] += 1
            vectors = list(gs.count_vectors(capacities, N))
            n_reused, n_members, new_cells = 0, 0, 0
            for counts in vectors:
                composition = gs.canonical_counts(counts)
                cell_id = gs.digest([method, tier, pid, N, composition])[:20]
                teams, possible = sample_members(groups, counts, DRAWS, ['configuration', cell_id])
                reused = 0
                for replicate, ws in enumerate(teams):
                    key = gs.team_key(pid, ws)
                    is_old = key in old
                    reused += is_old
                    if key not in requests:
                        requests[key] = dict(team_key=key, pool_id=pid, member_workers=list(ws),
                                             n=N, stages=['n20_all_ordinary_vectors_continuation'],
                                             cached_previous_request=is_old)
                    memberships.append(dict(common, cell_id=cell_id, composition=composition,
                                            team_key=key, replicate=replicate,
                                            possible_member_sets=str(possible),
                                            registered_member_sets=len(teams),
                                            exhaustive_vectors=True,
                                            exhaustive_members=len(teams) == possible,
                                            member_variation_estimable=possible > 1,
                                            cached_previous_request=is_old))
                cells.append(dict(common, cell_id=cell_id, composition=composition,
                                  possible_member_sets=str(possible), sampled_member_sets=len(teams),
                                  sampled_sets_cached=reused, prior_any_member_sets=old_compositions[composition],
                                  prior_cell_touched=old_compositions[composition] > 0,
                                  exhaustive_members=len(teams) == possible,
                                  singleton=possible == 1))
                n_members += len(teams)
                n_reused += reused
                new_cells += old_compositions[composition] == 0
            totals.append(dict(common, all_class_vectors=len(vectors),
                               prior_touched_vectors=len(vectors)-new_cells,
                               new_vectors=new_cells, member_references=n_members,
                               member_references_cached=n_reused,
                               new_member_references=n_members-n_reused))
    out = HERE / 'candidate_n20'
    atomic_frame(out / 'CONFIG_MEMBERSHIP.csv.gz', gs.pd.DataFrame(memberships), ('cell_id','team_key'))
    atomic_frame(out / 'CONFIG_CELLS.csv.gz', gs.pd.DataFrame(cells), ('cell_id',))
    atomic_frame(out / 'POOL_METHOD_COVERAGE.csv', gs.pd.DataFrame(totals), ('method_id','tier','pool_id'))
    all_req = sorted(requests.values(), key=lambda r: (r['pool_id'], r['team_key']))
    gs.save(out / 'ENDPOINT_REQUESTS.json.gz', dict(requests=all_req, seed=gs.SEED))
    receipt = dict(
        selection='All ordinary eligible pools at n=20; predefined retained fine/A2 families; no score access',
        method_conditions=sorted(METHODS),
        cells=len(cells),
        prior_touched_cells=sum(x['prior_cell_touched'] for x in cells),
        missing_prior_cells=sum(not x['prior_cell_touched'] for x in cells),
        member_references=len(memberships),
        unique_requested_sets=len(requests),
        prior_requested_sets=sum(r['cached_previous_request'] for r in all_req),
        missing_prior_requested_sets=sum(not r['cached_previous_request'] for r in all_req),
        pools=len({r['pool_id'] for r in all_req}),
        images=len({r['image_id'] for r in cells}),
        buildings=len({r['building'] for r in cells}),
        vector_scope_complete=True, member_scope_complete=False,
        only_member_exhaustive_cells=sum(x['exhaustive_members'] for x in cells),
        singleton_cells=sum(x['singleton'] for x in cells),
        all_addition_orders_enumerated=False,
        parent_coarse_vectors_covered_by_fine_vectors=True,
        existing_request_sha256=gs.hashlib.sha256((COMPOSITION/'ENDPOINT_REQUESTS.json.gz').read_bytes()).hexdigest(),
        frozen_labels_sha256=gs.hashlib.sha256((COMPOSITION/'FROZEN_LABELS.csv').read_bytes()).hexdigest(),
        fusion_calls=0, elapsed_seconds=time.monotonic()-start,
        status='candidate metadata design only; no new outcomes computed')
    gs.save(out / 'DESIGN_CANDIDATE.json', receipt)
    print(json.dumps(receipt, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    main()
