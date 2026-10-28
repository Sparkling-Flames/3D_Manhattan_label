"""仅恢复缺失几何的受影响配比端点；逐队核对冻结几何摘要。"""
import gzip
import json
import math
import copy
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
import pandas as pd
from .rebuild_v21_20261028 import OUT, ROOT, read
from .fuse_v21_new_pools_20261028 import adapter

SOURCE = ROOT / 'research/workers/personnel_mixture_comparison_20261022/configurations'
TARGET = OUT / 'composition_rescore'


def process(payload):
    pool, teams, target = payload
    folder = Path(target) / pool['pool_id']; folder.mkdir(exist_ok=True)
    done = set(); part = 0
    for path in sorted(folder.glob('part_*.jsonl.gz')):
        with gzip.open(path, 'rt', encoding='utf-8') as f:
            for line in f:
                r = json.loads(line); assert r['team_key'] not in done; done.add(r['team_key'])
        part += 1
    assert done <= {r['team_key'] for r in teams}
    native = adapter(); buffer = []; n = 0
    def flush():
        nonlocal part
        if not buffer: return
        part += 1; path = folder / f'part_{part:05d}.jsonl.gz'; temp = path.with_suffix('.writing')
        with gzip.open(temp, 'wt', encoding='utf-8') as f:
            for row in buffer: f.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')
        temp.replace(path); buffer.clear()
    with native.Engine(full_state=False) as engine:
        for old in teams:
            if old['team_key'] in done: continue
            row = engine.evaluate(pool, old['member_workers'].split('|'))
            assert row['team_key'] == old['team_key']
            if old.get('member_set_key'):
                assert set(row['member_workers']) == set(old['member_set_key'].split('|'))
                row['member_set_key'] = old['member_set_key']
            if old.get('member_object_ids'):
                assert set(row['member_object_ids']) == set(old['member_object_ids'].split('|'))
            # Changed references cannot change deterministic fusion geometry.
            for field in ['nodes', 'fusion_turn_n', 'geometry_area_h2', 'height_mean_h', 'bottom_y_mean_px', 'top_y_mean_px']:
                a, b = old.get(field), row.get(field)
                if pd.notna(a):
                    assert b is not None and math.isclose(a, b, abs_tol=1e-8, rel_tol=1e-9), (old['team_key'], field, a, b)
            geometry = row.get('geometry')
            if geometry is not None:
                result = engine.scorecache.get(engine.fr.digest([row['k'] == 2, row.get('nodes'), geometry]))
                if result: row.update(result)
            row.update(data_release='v2.1', underlying_data_version='v2.1',
                       geometry_recovery=old.get('geometry_recovery','missing_saved_batch_replayed_exact_members'),
                       frozen_geometry_summary_verified=any(pd.notna(old.get(f)) for f in ['nodes','geometry_area_h2','height_mean_h']))
            buffer.append(native.gs.clean(row)); n += 1
            if len(buffer) >= 50: flush()
            if n % 500 == 0: print(pool['pool_id'], len(done) + n, '/', len(teams), flush=True)
        flush()
    result = dict(pool_id=pool['pool_id'], requested=len(teams), previous=len(done),
                  computed=n, complete=len(done) + n == len(teams))
    (folder / 'CHECKS.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result


def main():
    TARGET.mkdir(exist_ok=True)
    pools = {p['pool_id']: p for p in read(OUT / 'pools/INPUT_SNAPSHOT.json')['images']}
    ids = {r['pool_id'] for r in read(OUT / 'pools/DEPENDENCIES.json') if r['action'] == 'reuse_geometry_rescore'}
    members = pd.read_csv(SOURCE / 'TEAM_MEMBERS.csv.gz')
    members = members[members.pool_id.isin(ids)]
    scalar = pd.concat([pd.read_csv(SOURCE / f'ENDPOINT_OUTCOMES_{c}.csv.gz') for c in ['manual', 'semi']])
    joined = members[['team_key', 'member_workers']].merge(scalar, on='team_key', validate='one_to_one')
    assert len(joined) == len(members)
    parity_path = TARGET / 'ENGINE_PARITY.json'
    if not parity_path.exists():
        refs = {r['target_id']: r for r in read(ROOT / 'research/quality/quality_workers_v2_20261019/reference_catalog.json')}
        native = adapter(); parity = []
        for old in joined.groupby('pool_id').head(1).to_dict('records'):
            pool = copy.deepcopy(pools[old['pool_id']]); pool['reference'] = refs[pool['meta']['reference_id']]
            with native.Engine(full_state=False) as engine:
                row = engine.evaluate(pool, old['member_workers'].split('|'))
            difference = abs(old['B8L2'] - row['B8L2']) if pd.notna(old['B8L2']) and row.get('B8L2') is not None else None
            assert difference is not None and difference < 1e-8
            assert old['nodes'] == row['nodes']
            parity.append(dict(pool_id=old['pool_id'], team_key=old['team_key'],
                               difference=difference, nodes_equal=True))
        parity_path.write_text(json.dumps(parity, indent=2), encoding='utf-8')
    parity = read(parity_path)
    assert {r['pool_id'] for r in parity} == set(joined.pool_id)
    assert all(r['nodes_equal'] and r['difference'] < 1e-8 for r in parity)
    # The coverage check was performed on every saved population score key.
    known = {}
    wanted = set(joined.team_key)
    for f in (OUT / 'historical_population_rescore').glob('*.jsonl.gz'):
        with gzip.open(f, 'rt', encoding='utf-8') as stream:
            for line in stream:
                r = json.loads(line)
                if r['team_key'] in wanted: known[r['team_key']] = r
    reused_path = TARGET / 'REUSED_ENDPOINTS.jsonl.gz'
    if not reused_path.exists():
        geometry = {}
        sources = {r['geometry_source'] for r in known.values()}
        for source in sources:
            by_index = {r['geometry_index']: key for key, r in known.items() if r['geometry_source'] == source}
            with gzip.open(ROOT / source, 'rt', encoding='utf-8') as f:
                rows = (json.loads(line) for line in f) if source.endswith('.jsonl.gz') else iter(json.load(f))
                for i, r in enumerate(rows):
                    if i in by_index:
                        assert r['team_key'] == by_index[i]
                        geometry[r['team_key']] = r.get('geometry')
        native = adapter(); reused = []
        with native.Engine(full_state=False) as engine:
            for old in joined[joined.team_key.isin(known)].to_dict('records'):
                update = known[old['team_key']]; pool = pools[old['pool_id']]
                old.update(update['result'] or {})
                old.update(geometry=geometry[old['team_key']], member_workers=old['member_workers'].split('|'),
                           reference_id=pool['meta']['reference_id'], reference_version=pool['meta']['reference_version'])
                if (old['geometry'] or {}).get('points'):
                    old.update(engine.fr.reference_structure(old['geometry']['points'], pool['reference']['points_1024x512']))
                old = native.native.enrich(old, pool, engine.times, engine.sg, {})
                old.update(data_release='v2.1', geometry_recovery='saved_population_geometry_reused')
                reused.append(native.gs.clean(old))
        with gzip.open(reused_path, 'wt', encoding='utf-8') as f:
            for row in reused: f.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')
    joined = joined[~joined.team_key.isin(known)]
    (TARGET / 'REQUESTS.csv.gz').parent.mkdir(exist_ok=True)
    joined[['team_key', 'pool_id', 'member_workers', 'k']].to_csv(TARGET / 'REQUESTS.csv.gz', index=False, encoding='utf-8-sig')
    with ProcessPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(process, [(pools[pid], g.to_dict('records'), str(TARGET)) for pid, g in joined.groupby('pool_id')]))
    (TARGET / 'CHECKS.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
