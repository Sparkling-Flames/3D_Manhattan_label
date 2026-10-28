"""按实际顺序接合更新端点；保留重复团队的路径频数和旧/新增抽样层。"""
import gzip
import io
import json
import pandas as pd
from .rebuild_v21_20261028 import OUT, ROOT, read

BASE = ROOT / 'research/workers/personnel_population_curves_v2_20261023'
EXT = BASE / 'sampling_extension_20261026'
PRIOR = BASE / 'sampling_precision_20261025'
TARGET = OUT / 'natural_inputs'
METRICS = ['B8L2', 'D10', 'WQ', 'IoU3D100', 'iou_2d', 'S_bottom_deg', 'dir',
           'Hmean', 'Hcenter', 'omission', 'extension', 'boundary_loss', 'direction_loss',
           'height_loss', 'global_height_loss', 'local_height_loss', 'height_mean_ratio']
FIELDS = ['team_key', 'pool_id', 'k', 'member_workers', 'member_object_ids', 'score_status',
          'floor_turn5_n', 'floor_redundant5_n', 'floor_short_edge_03_n', 'floor_area_camera_h2',
          'height_mean_h', 'top_y_mean_px', 'bottom_y_mean_px', 'nodes', 'complete_evaluable',
          'connection_available', 'below_four', 'policy_deferred', 'geometry_status',
          'source_time_total_seconds', 'source_time_known_n'] + METRICS


def repair_new_space_deferred(frame):
    """Repair the known missing new-space flag from the saved endpoint status."""
    missing = frame.policy_deferred.isna()
    if not missing.any():
        return False
    assert missing.all() and frame.stratum.eq('new_space256').all(), 'unexpected deferred schema gap'
    deferred = frame.score_status.eq('two_person_deferred')
    assert deferred.equals(frame.k.eq(2)), 'k2 and saved deferred status disagree'
    frame['policy_deferred'] = deferred
    return True


def selected(path, ids):
    frames = []
    for d in pd.read_csv(path, compression='gzip', usecols=lambda c: c in FIELDS,
                         chunksize=50000, low_memory=False):
        frames.append(d[d.pool_id.isin(ids)])
    return pd.concat(frames, ignore_index=True)


def overlay(frame, patches):
    """An explicitly unavailable new metric replaces its old value with NA."""
    frame = frame.set_index('team_key', drop=False).copy()
    keys = frame.index.intersection(patches.index)
    for c in METRICS:
        if c not in frame:
            frame[c] = float('nan')
        frame.loc[keys, c] = pd.to_numeric(patches.loc[keys, c])
    frame.loc[keys, 'score_status'] = patches.loc[keys, 'score_status']
    frame['score_available'] = frame.B8L2.notna()
    frame['score_failure_nonpolicy'] = ~frame.score_available & frame.k.ne(2)
    frame['incomplete_nonpolicy'] = ~frame.complete_evaluable.fillna(False).astype(bool) & frame.k.ne(2)
    return frame.reset_index(drop=True)


def main():
    TARGET.mkdir(exist_ok=True)
    deps = read(OUT / 'pools/DEPENDENCIES.json')
    ids = {r['pool_id'] for r in deps if r['action'] == 'reuse_geometry_rescore'}
    pools = {r['pool_id']: r for r in read(OUT / 'pools/INPUT_SNAPSHOT.json')['images']}
    patches = {}
    for folder in ['historical_population_rescore', 'population256_rescore']:
        for path in (OUT / folder).rglob('*.jsonl.gz'):
            with gzip.open(path, 'rt', encoding='utf-8') as f:
                for line in f:
                    r = json.loads(line); m = r['result'] or {}
                    patches[r['team_key']] = dict(team_key=r['team_key'],
                        **{c: m.get(c) for c in METRICS},
                        score_status=m.get('score_status', r.get('original_score_status', r.get('original_endpoint_state'))))
    patch = pd.DataFrame(patches.values()).set_index('team_key')
    pieces = sorted((BASE / 'results').glob('ENDPOINT_SCALARS.csv.gz.part*'))
    raw = io.BytesIO(b''.join(p.read_bytes() for p in pieces))
    old = selected(raw, ids); raw.close()
    prior = pd.concat([selected(p, ids) for p in sorted(
        (PRIOR / 'new_endpoints/table_shards/NEW_ENDPOINT_SCALARS').glob('*.gz'))], ignore_index=True)
    # Final precision shards contain authoritative corrections to two endpoints.
    endpoints = pd.concat([old, prior], ignore_index=True).drop_duplicates('team_key', keep='last')
    endpoints = overlay(endpoints, patch)
    links = pd.read_csv(BASE / 'results/PREFIX_TEAM_LINKS.csv.gz', low_memory=False)
    links = links[links.pool_id.isin(ids) & links.policy.eq('natural_random')].copy()
    links['stratum'] = 'old24'
    extra = pd.read_csv(PRIOR / 'design/NEW_PREFIX_TEAM_LINKS.csv.gz', dtype={'seed': str, 'master_seed': str}, low_memory=False)
    extra = extra[extra.pool_id.isin(ids) & extra.policy.eq('natural_random')].copy()
    extra['stratum'] = extra.batch.map({'balanced_new24': 'prior_new24', 'focus_new48': 'prior_focus48'})
    assert extra.stratum.notna().all()
    links = pd.concat([links, extra], ignore_index=True)
    index = pd.read_csv(EXT / 'new_endpoints26/COMPLETE_NEW_ENDPOINT_SHARD_INDEX.csv.gz')
    counts = []
    for pid in sorted(ids):
        pool = pools[pid]; parts = [endpoints[endpoints.pool_id.eq(pid)]]
        requests = [links[links.pool_id.eq(pid)]]
        for r in index[index.pool_id.eq(pid)].itertuples():
            parts.append(overlay(selected(EXT / r.scalar_file, {pid}), patch))
        for stage in [1, 2]:
            path = EXT / f'design26/links_by_pool/stage{stage}' / (pid + '.csv.gz')
            if not path.exists():
                continue
            d = pd.read_csv(path, dtype={'seed': str, 'master_seed': str}, low_memory=False)
            d = d[d.policy.eq('natural_random')].copy()
            d['stratum'] = 'new104A' if stage == 1 else 'new104B'; requests.append(d)
        e = pd.concat(parts, ignore_index=True)
        assert e.team_key.is_unique, pid
        q = pd.concat(requests, ignore_index=True)
        assert not q.duplicated(['stratum', 'path_id', 'k']).any()
        q = q[['team_key', 'path_id', 'k', 'stratum', 'policy']].merge(
            e.drop(columns='k'), on='team_key', how='left', validate='many_to_one', indicator=True)
        assert q['_merge'].eq('both').all(), (pid, q[q['_merge'].ne('both')].team_key.tolist())
        q = q.drop(columns='_merge')
        for c, value in pool['meta'].items():
            if c in ['image', 'image_id', 'building', 'condition', 'layer', 'difficulty',
                     'pool_n', 'reference_id', 'reference_version']:
                q[c] = value
        q['pool_n'] = len(pool['records']); q['data_release'] = 'v2.1'
        q.to_csv(TARGET / (pid + '.csv.gz'), index=False, encoding='utf-8-sig')
        counts.append(dict(pool_id=pid, rows=len(q), unique_teams=q.team_key.nunique(),
                           paths=q.groupby('stratum').path_id.nunique().to_dict()))
        print('natural inputs', len(counts), '/', len(ids), flush=True)
    (TARGET / 'CHECKS.json').write_text(json.dumps(counts, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
