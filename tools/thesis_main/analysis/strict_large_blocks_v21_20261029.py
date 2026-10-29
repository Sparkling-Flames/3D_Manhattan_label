"""最终楼外分类的九/十人严格ABC补充；冻结设计后才运行原生端点。"""
from pathlib import Path
import argparse
import itertools
import gzip
import json
import math
import random
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'research/workers/personnel_v21_reselection_20261029'
OUT = ROOT / 'research/workers/strict_large_blocks_v21_20261029'
ARCHIVE = ROOT / 'research/workers/personnel_v21_reselection_20261029/independent_review/reaudit_20261029/source_archive'
SOURCE_MAP = pd.read_csv(ARCHIVE / 'SOURCE_ARCHIVE_MAP.csv')
sys.path.insert(0, str(SOURCE / 'experiment'))
from capacity_space import capacities, exact_counts
from register_adaptive import select_blocks, make_event, write_json


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(list(rows)).to_csv(path, index=False, encoding='utf-8-sig')


def write_jsonl(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.writing')
    with gzip.open(tmp, 'wt', encoding='utf-8') as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')
    tmp.replace(path)


def save_frame(path, frame):
    path = Path(path)
    tmp = path.with_name(path.name + '.writing')
    frame.to_csv(tmp, index=False, encoding='utf-8-sig', compression='gzip')
    tmp.replace(path)


def run_pool(payload):
    import run_registered as runner
    # Windows cannot fsync a read-only handle; retain atomic replacement.
    runner.write_jsonl = write_jsonl
    runner.save_frame = save_frame
    return runner.worker(payload)


def run():
    import run_registered as runner
    pools = {p['pool_id']: p for p in json.loads((OUT / 'INPUT_SNAPSHOT.json').read_text(encoding='utf-8'))['images']}
    requests = pd.read_csv(OUT / 'design/REQUESTS.csv.gz').to_dict('records')
    wanted = {r['team_key']: r for r in requests}
    cache = {pid: {} for pid in pools}
    rejected = {}
    def accept(row, source):
        key = row.get('team_key')
        if key not in wanted:
            return
        pid = wanted[key]['pool_id']
        issue = runner.fields_match(row, pools[pid], wanted[key])
        if issue:
            rejected[issue] = rejected.get(issue, 0) + 1
        elif key not in cache[pid]:
            cache[pid][key] = dict(row, cache_source=source)
    files = [p for p in (ROOT / 'research/data/releases/v2.1').rglob('*.jsonl.gz') if p.parent.name in pools or p.name == 'REUSED_ENDPOINTS.jsonl.gz']
    for p in files:
        for row in runner.iter_jsonl(p):
            accept(row, str(p.relative_to(ROOT)))
    geometry_path = source_path('stage03_completed_ABC', 'ENDPOINT_GEOMETRY.jsonl.gz')
    with gzip.open(geometry_path, 'rt', encoding='utf-8-sig') as f:
        for line in f:
            accept(json.loads(line), str(geometry_path.relative_to(ROOT)))
    write_json(OUT / 'CACHE_COVERAGE.json', dict(requests=len(requests), cache_hits=sum(map(len, cache.values())), scanned_local_files=len(files), rejected=rejected))
    print((OUT / 'CACHE_COVERAGE.json').read_text(encoding='utf-8'), flush=True)
    by = {pid: [r for r in requests if r['pool_id'] == pid] for pid in pools}
    results = []
    with ProcessPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(run_pool, (str(ROOT), pools[pid], by[pid], str(OUT / 'endpoints'), list(cache[pid].values()), 100)) for pid in pools]
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            write_json(OUT / 'RUN_PROGRESS.json', results)
            print(json.dumps(result), flush=True)
    scalars = pd.concat([pd.read_csv(p, low_memory=False) for p in (OUT / 'endpoints/scalar_shards').glob('*.csv.gz')], ignore_index=True)
    assert scalars.team_key.is_unique and set(scalars.team_key) == set(wanted)
    save_frame(OUT / 'endpoints/ENDPOINT_SCALARS.csv.gz', scalars)
    write_json(OUT / 'RUN_RECEIPT.json', dict(pools=results, total=len(scalars), new_native=sum(r['new_native'] for r in results), reused=sum(r['reused'] for r in results), complete=True))


def zip_table(stage, suffix):
    path = source_path(stage, suffix)
    return pd.read_csv(path, compression='gzip' if suffix.endswith('.gz') else None, low_memory=False)


def source_path(stage, suffix):
    rows = SOURCE_MAP[(SOURCE_MAP.source_zip_name == f'HOHONET_v21_reaudit_{stage}.zip') & SOURCE_MAP.member_path.str.endswith(suffix)]
    assert len(rows) == 1, (stage, suffix, len(rows))
    path = rows.iloc[0].repository_or_local_path
    if path.startswith('git:'):
        path = path.split(':', 2)[2]
    path = ROOT / path
    assert path.is_file(), path
    return path


def prepare():
    assert not (OUT / 'design/DESIGN.json').exists(), 'Frozen design already exists; do not overwrite.'
    pools = json.loads((ROOT / 'research/data/releases/v2.1/pools/INPUT_SNAPSHOT.json').read_text(encoding='utf-8'))['images']
    frozen = zip_table('stage03_completed_ABC', 'FROZEN_LABELS_ALL_LOBO.csv.gz')
    new = zip_table('stage01_classification', 'NEW_LABELS_ALL_LOBO.csv.gz')
    k2 = new[new.method.eq('REPRO_TARGET_DSTRUCT_K2')].copy()
    k2['method'] = 'TARGET_DSTRUCT_K2'
    old = pd.read_csv(SOURCE / 'classification/MAIN45_LABELS_ALL_LOBO.csv.gz', low_memory=False)
    labels = pd.concat([frozen, k2, old[old.method.eq('RFUSE_GEOM_K2')]], ignore_index=True)
    assert not labels.duplicated(['method', 'heldout_building', 'worker_id']).any()
    OUT.mkdir(parents=True, exist_ok=True)
    labels.to_csv(OUT / 'FROZEN_LABELS_ALL_LOBO.csv.gz', index=False)
    lookup = {(m, b): g.to_dict('records') for (m, b), g in labels.groupby(['method', 'heldout_building'])}
    methods = sorted(labels.method.unique())
    all_capacity, cells, events, requests, coverage = [], [], [], {}, []
    selected = {'TARGET_DSTRUCT_K3', 'V21_DSTRUCT_RAW3_K3', 'TARGET_DSTRUCT_K2'}
    for pool in sorted(pools, key=lambda p: p['pool_id']):
        meta = pool['meta']
        if meta['layer'] != 'ordinary_manual':
            continue
        ws = sorted(r['worker_id'] for r in pool['records'])
        for method in methods:
            groups = capacities(pool, lookup.get((method, meta['building']), []))
            for s, t in itertools.permutations([c for c in groups if c != 'unknown'], 2):
                for m in (9, 10):
                    max_n = len(ws) - 2 * m
                    feasible = len(groups[s]) >= 2*m and len(groups[t]) >= m and max_n >= m+1
                    row = dict(pool_id=pool['pool_id'], image=meta['image'], building=meta['building'], method=method, source_class=s, target_class=t, m=m, source_capacity=len(groups[s]), target_capacity=len(groups[t]), pool_n=len(ws), n_min_nonempty_D=m+1, n_max=max_n, feasible_nonempty_D=feasible, selected_family=method in selected)
                    all_capacity.append(row)
                    if not feasible or method not in selected:
                        continue
                    for n in sorted({min(m+2, max_n), max_n}):
                        cell = dict(row, n=n, selection_phase='score_blind_large_block_supplement')
                        cells.append(cell)
                        count = 256 if m == 10 else 64
                        blocks = select_blocks(cell, groups, pool['pool_id'], [], count)
                        before = len(events)
                        for bi, (x, y, z, origin, oldid) in enumerate(blocks):
                            rest = sorted(set(ws)-set(x+y+z))
                            possible = list(itertools.combinations(rest, n-m))
                            rng = random.Random(f'20261029910:{pool["pool_id"]}:{method}:{m}:{bi}:{n}')
                            backgrounds = possible if len(possible) <= 4 else rng.sample(possible, 4)
                            for j, d in enumerate(backgrounds):
                                event, teams = make_event(pool, cell, groups, x, y, z, list(d), bi, j, origin, oldid)
                                event['background_population'] = len(possible)
                                event['background_sampling'] = 'exhaustive' if len(possible) <= 4 else 'uniform_without_replacement_4'
                                events.append(event)
                                for arm, team in teams.items():
                                    key = event[arm+'_team_key']
                                    requests[key] = dict(team_key=key, pool_id=pool['pool_id'], n=n, member_workers='|'.join(team))
                        coverage.append(dict(cell, registered_events=len(events)-before, sampled_unordered_XY_blocks=len(blocks), **exact_counts(len(ws), len(groups[s]), len(groups[t]), n, m)))
    assert len({e['event_id'] for e in events}) == len(events)
    write_csv(OUT / 'ALL_DIRECTION_CAPACITY.csv', all_capacity)
    write_csv(OUT / 'design/CELLS.csv', cells)
    write_csv(OUT / 'design/EVENTS_EXACT.csv.gz', events)
    write_csv(OUT / 'design/REQUESTS.csv.gz', requests.values())
    write_csv(OUT / 'design/REGISTERED_COVERAGE.csv', coverage)
    selected_pids = {r['pool_id'] for r in requests.values()}
    write_json(OUT / 'INPUT_SNAPSHOT.json', {'images': [p for p in pools if p['pool_id'] in selected_pids]})
    write_json(OUT / 'design/DESIGN.json', dict(seed_blocks=2026102907, seed_backgrounds=20261029910, events=len(events), teams=len(requests), pools=len(selected_pids), cells=len(cells), score_blind=True, block_draws_m9=64, block_draws_m10=256, backgrounds_per_block_up_to=4, X_Y_exchange_duplicates_removed=True, X_Y_orientation='seeded draw; not ordered by score; G_A and symmetric G_S both retained', selected_families=sorted(selected), endpoints_read_before_freeze=False, existing_fusion_rules_unchanged=True))
    print((OUT / 'design/DESIGN.json').read_text(encoding='utf-8'), flush=True)


def analyze():
    import run_registered as runner
    sys.path.insert(0, str(SOURCE / 'analysis'))
    from measure_registered_events import measure
    pools = {p['pool_id']: p for p in json.loads((OUT / 'INPUT_SNAPSHOT.json').read_text(encoding='utf-8'))['images']}
    events = pd.read_csv(OUT / 'design/EVENTS_EXACT.csv.gz')
    shards = OUT / 'results/metric_shards'
    shards.mkdir(parents=True, exist_ok=True)
    all_tables = []
    for pid, group in events.groupby('pool_id'):
        dest = shards / (pid + '.csv.gz')
        if dest.exists():
            all_tables.append(pd.read_csv(dest, low_memory=False))
            continue
        receipt = OUT / 'endpoints/pools' / pid / 'CHECKS.json'
        if not receipt.exists():
            continue
        rows = {r['team_key']: r for path in (receipt.parent).glob('part_*.jsonl.gz') for r in runner.iter_jsonl(path)}
        table = measure(group.reset_index(drop=True), rows, pools[pid])
        # The archived measure function calls missing Q "failed"; expose that
        # as Q_missing and retain native failure/status separately here.
        table = table.rename(columns={a+'_failed': a+'_Q_missing' for a in 'ABC'})
        for arm in 'ABC':
            for field in ['score_status', 'complete_evaluable', 'reasons', 'failure_reason']:
                table[arm+'_'+field] = table[arm+'_team_key'].map(lambda key: json.dumps(rows[key].get(field), ensure_ascii=False) if isinstance(rows[key].get(field), (dict, list)) else rows[key].get(field))
        table['G_A'] = table.B8L2_AC_gap
        table['G_S'] = table.B8L2_gap
        table['G_A_swapped'] = table.B8L2_CB.abs().where(table.ABC_scored)-table.B8L2_within
        assert ((table.G_A+table.G_A_swapped)/2-table.G_S).dropna().abs().max() < 1e-9
        save_frame(dest, table)
        all_tables.append(table)
        print('Measured ' + pid, flush=True)
    if not all_tables:
        return
    result = pd.concat(all_tables, ignore_index=True)
    save_frame(OUT / 'results/EVENT_METRICS.csv.gz', result)
    keys = ['method', 'image', 'building', 'pool_id', 'source_class', 'target_class', 'n', 'm']
    metrics = ['G_A', 'G_S', 'G_A_swapped', 'B8L2_within', 'B8L2_AC_absolute', 'B8L2_CA', 'B8L2_CB', 'D10_CA', 'D10_CB', 'D10_AC_gap', 'D10_gap', 'IoU3D100_CA', 'IoU3D100_CB', 'fusion_turn_n_CA', 'fusion_turn_n_CB', 'geometry_area_h2_CA', 'height_mean_h_CA', 'geometry_pair_angle_AB', 'geometry_pair_angle_AC', 'geometry_pair_angle_BC', 'geometry_bev_distance_AB', 'geometry_bev_distance_AC', 'geometry_bev_distance_BC', 'record_time_CA_pct_source_matched', 'record_time_CB_pct_source_matched']
    metrics = [c for c in metrics if c in result]
    blocks = result.groupby(keys + ['block_id'], dropna=False)[metrics].mean().reset_index()
    image = blocks.groupby(keys, dropna=False)[metrics].mean().reset_index()
    counts = result.groupby(keys, dropna=False).agg(events=('event_id', 'size'), blocks=('block_id', 'nunique'), ABC_Q_events=('ABC_scored', 'sum')).reset_index()
    image = image.merge(counts, on=keys, validate='one_to_one')
    image.to_csv(OUT / 'results/IMAGE_CONDITION_RESULTS.csv', index=False)
    old = zip_table('stage02_comparison', 'COMBINED_UNION_EVENTS_WITH_ROLES.csv.gz')
    rolekeys = ['method', 'building', 'source_class', 'target_class']
    rolecols = [c for c in old if c in ['axis', 'rank_direction', 'role_direction'] or c.endswith('_axis_rank')]
    roles = old[rolekeys + rolecols].drop_duplicates()
    assert not roles.duplicated(rolekeys).any()
    image.merge(roles, on=rolekeys, how='left', validate='many_to_one').to_csv(OUT / 'results/IMAGE_RESULTS_WITH_HISTORICAL_ROLES.csv', index=False)
    prior = old[old.m.isin([7, 8]) & old.pool_id.isin(image.pool_id) & old.method.isin(image.method)].copy()
    prior['G_A'] = prior.B8L2_CA.abs()-prior.B8L2_BA.abs()
    prior['G_S'] = (prior.B8L2_CA.abs()+prior.B8L2_CB.abs())/2-prior.B8L2_BA.abs()
    # Match image and fold-class direction, never label this an identical path.
    prior = prior.merge(image[rolekeys + ['pool_id']].drop_duplicates(), on=rolekeys + ['pool_id'], how='inner', validate='many_to_one')
    pkeys = rolekeys + ['pool_id', 'image', 'n', 'm']
    pb = prior.groupby(pkeys + ['block_id'], dropna=False)[['G_A', 'G_S', 'B8L2_CA', 'B8L2_CB']].mean().reset_index()
    pb.groupby(pkeys, dropna=False)[['G_A', 'G_S', 'B8L2_CA', 'B8L2_CB']].mean().reset_index().to_csv(OUT / 'results/PRIOR_M7_M8_SAME_IMAGE_DIRECTION.csv', index=False)
    freq = []
    for key, group in result.groupby(keys, dropna=False):
        unique = group.drop_duplicates('block_id')
        for block in ['X', 'Y', 'Z']:
            counts = unique[block].str.split('|').explode().value_counts()
            for worker, count in counts.items():
                freq.append(dict(zip(keys, key), block=block, worker_id=worker, appearances=int(count), blocks=len(unique), fraction=count/len(unique)))
    pd.DataFrame(freq).to_csv(OUT / 'results/MEMBER_BLOCK_COVERAGE.csv', index=False)
    half = result.copy()
    half['sample_half'] = half.block_replicate.ge(half.m.map({9: 32, 10: 128})).astype(int) + 1
    hb = half.groupby(keys + ['sample_half', 'block_id'], dropna=False)[['G_A', 'G_S']].mean().reset_index()
    hb.groupby(keys + ['sample_half'], dropna=False)[['G_A', 'G_S']].mean().reset_index().to_csv(OUT / 'results/BLOCK_SAMPLE_HALVES.csv', index=False)
    if (OUT / 'endpoints/ENDPOINT_SCALARS.csv.gz').exists():
        ep = pd.read_csv(OUT / 'endpoints/ENDPOINT_SCALARS.csv.gz', low_memory=False)
        ep.groupby(['score_status', 'geometry_status', 'geometry_reason', 'connection_available'], dropna=False).size().rename('endpoints').reset_index().to_csv(OUT / 'results/ENDPOINT_STATUS_COUNTS.csv', index=False)
        threshold = result[['method', 'image', 'n', 'm', 'A_minimum_support']].drop_duplicates()
        threshold['D_n'] = threshold.n-threshold.m
        threshold['block_can_pass_alone'] = threshold.m.ge(threshold.A_minimum_support)
        threshold['D_can_pass_alone'] = threshold.D_n.ge(threshold.A_minimum_support)
        threshold.to_csv(OUT / 'results/MV50_CAPACITY.csv', index=False)
    long = []
    for key, group in result.groupby(keys, dropna=False):
        for metric in metrics:
            byblock = group.groupby('block_id')[metric].mean()
            long.append(dict(zip(keys, key), metric=metric, mean=byblock.mean(), valid_events=int(group[metric].notna().sum()), registered_events=len(group), valid_blocks=int(byblock.notna().sum()), registered_blocks=len(byblock), positive_blocks=int(byblock.gt(1e-9).sum()), negative_blocks=int(byblock.lt(-1e-9).sum())))
    pd.DataFrame(long).to_csv(OUT / 'results/IMAGE_METRIC_SUPPORT.csv', index=False)
    write_json(OUT / 'results/CHECKS.json', dict(measured_events=len(result), registered_events=len(events), complete=len(result)==len(events), symmetric_equals_mean_two_A_orientations=True, weights='equal backgrounds within block, then equal blocks within pool/image; n and m kept separate', missing_Q_not_zero=True))



if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['prepare', 'run', 'analyze'])
    args = parser.parse_args()
    {'prepare': prepare, 'run': run, 'analyze': analyze}[args.stage]()
