"""Independent delivery and saved-component audit; no official result writes."""
from pathlib import Path
import csv
import gzip
import json
import math
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
U = Path('\\\\?\\' + str(ROOT / 'unpacked'))
PREFIX = 'research/workers/personnel_exchange_discrimination_20261025/'


def main():
    files = {}
    for stage in ['01', '02A', '02B', '02C', '03', '04A1', '04A2', '04B', '04C', '05', '06B', '06A', '06C']:
        for p in (U / stage).rglob('*'):
            if not p.is_file():
                continue
            name = p.relative_to(U / stage).as_posix()
            if stage in ['06A', '06C']:
                if not name.startswith(PREFIX):
                    continue
                name = name[len(PREFIX):]
            files[name] = p
    readable = []
    for name, p in files.items():
        if not name.endswith('.gz'):
            continue
        total = 0
        with gzip.open(p, 'rb') as stream:
            while block := stream.read(1024 * 1024):
                total += len(block)
        readable.append({'file': name, 'uncompressed_bytes': total})
    print('gzip fully readable', len(readable), flush=True)
    inventory = pd.read_csv(files['final/UNIQUE_ENDPOINT_INVENTORY.csv.gz'])
    assert len(inventory) == 283211 and inventory.team_key.is_unique
    with gzip.open(files['runtime/population/inputs/INPUT_SNAPSHOT.json.gz'], 'rt', encoding='utf-8-sig') as f:
        snapshot = json.load(f)
    pools = {p['pool_id']: p for p in snapshot['images']}
    lookup = {pid: {r['worker_id']: r for r in p['records']} for pid, p in pools.items()}
    cols = ['team_key', 'pool_id', 'member_workers', 'member_object_ids', 'k', 'minimum_support',
            'B8L2', 'D10', 'IoU3D100', 'iou_3d_corner_mean', 'iou_2d', 'S_bottom_deg', 'dir', 'Hmean', 'Hcenter',
            'score_available', 'source_time_known_n', 'source_time_known_sum_seconds', 'source_time_total_seconds',
            'reference_id', 'condition']
    tables = {}
    score_checks = []
    time_count = 0
    for name in sorted(inventory.scalar_source.unique()):
        d = pd.read_csv(files[name], usecols=lambda c: c in cols)
        assert d.team_key.is_unique
        s = d[d.B8L2.notna()]
        assert s[['iou_2d', 'S_bottom_deg', 'dir', 'Hmean', 'Hcenter', 'D10']].notna().all().all()
        i = s.iou_2d.to_numpy()
        b = s.S_bottom_deg.to_numpy() ** 2 / 32
        h = (s.Hmean.to_numpy() / .8) ** 2 + (s.Hcenter.to_numpy() / .25) ** 2
        errs = {}
        for field, scale in [('B8L2', 8), ('D10', 10)]:
            direction = 1.5 * s.dir.to_numpy() ** 2 / (s.dir.to_numpy() ** 2 + scale ** 2)
            with np.errstate(divide='ignore', invalid='ignore'):
                q = np.where(i == 0, 0, 100 * i / (i + np.hypot(1 - i + i * b, i * direction) + i * h))
            errs[field] = float(np.max(np.abs(q - s[field].to_numpy())))
            assert errs[field] < 1e-8, (name, field, errs[field])
        assert np.array_equal(d.B8L2.notna(), d.score_available)
        assert d.condition.eq('manual').all()
        for row in d.itertuples(index=False):
            workers = row.member_workers.split('|')
            own = [lookup[row.pool_id][w] for w in workers]
            assert len(set(workers)) == row.k
            assert set(row.member_object_ids.split('|')) == {r['object_id'] for r in own}
            assert row.minimum_support == math.ceil(row.k / 2)
            assert row.reference_id == pools[row.pool_id]['meta']['reference_id']
            values = [float(r['source_time_seconds']) for r in own if r.get('source_time_seconds') is not None and math.isfinite(float(r['source_time_seconds']))]
            assert len(values) == row.source_time_known_n
            if values:
                assert abs(sum(values) - row.source_time_known_sum_seconds) < 1e-7
            if len(values) == row.k:
                assert abs(sum(values) - row.source_time_total_seconds) < 1e-7
                time_count += 1
            else:
                assert pd.isna(row.source_time_total_seconds)
        tables[name] = d
        score_checks.append({'file': name, 'rows': len(d), 'scored': len(s), 'failed': len(d)-len(s), 'max_abs_error': errs})
        print(score_checks[-1], flush=True)
    chosen = []
    for name, g in inventory.groupby('scalar_source'):
        d = tables[name].set_index('team_key').loc[g.team_key]
        chosen.append(d)
    unique = pd.concat(chosen)
    assert len(unique) == 283211 and unique.index.is_unique
    assert int(unique.B8L2.notna().sum()) == 279013
    assert int(unique.B8L2.isna().sum()) == 4198
    geomchecks = []
    for name, group in inventory.groupby('geometry_source'):
        with gzip.open(files[name], 'rt', encoding='utf-8-sig') as f:
            geometry = json.load(f)
        keys = {r['team_key'] for r in geometry}
        assert len(keys) == len(geometry)
        expected = set(group.team_key)
        missing = expected-keys
        bad_scored = missing & set(unique[unique.B8L2.notna()].index)
        assert not bad_scored
        geomchecks.append({'file': name, 'geometry_rows': len(geometry), 'needed_rows': len(group),
                           'absent_geometry': len(missing), 'absent_scorable_geometry': len(bad_scored)})
        print(geomchecks[-1], flush=True)
        del geometry
    result = {'zip_packages': 13, 'virtual_research_files': len(files), 'gzip_files_fully_read': readable,
              'scalar_batches': score_checks, 'geometry_batches': geomchecks, 'unique_endpoints': len(unique),
              'unique_scorable': int(unique.B8L2.notna().sum()), 'unique_unscorable': int(unique.B8L2.isna().sum()),
              'batch_rows_with_complete_source_time': time_count,
              'member_object_reference_time_and_minimum_support': 'all scalar batch rows checked against saved v2 snapshot',
              'not_done': ['all native fusion reruns', 'full scoring from original geometry', 'file hashes']}
    (ROOT/'DELIVERY_AND_SCORE_CHECK.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('DELIVERY_AND_SCORE_CHECK.json saved', flush=True)


if __name__ == '__main__':
    main()
