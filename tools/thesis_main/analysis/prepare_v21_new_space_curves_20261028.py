"""将新空间实际256顺序接至已计算团队；补充沿用的几何描述。"""
import gzip
import importlib.util
import json
import pandas as pd
from .rebuild_v21_20261028 import ROOT, OUT, read
from .fuse_v21_new_pools_20261028 import adapter, TARGET as ENDPOINTS
from .prepare_v21_natural_inputs_20261028 import FIELDS, TARGET


def load_rows(folder, pool, prefix, fr):
    rows = {}
    for path in sorted(folder.glob('part_*.jsonl.gz')):
        with gzip.open(path, 'rt', encoding='utf-8') as f:
            for line in f:
                row = json.loads(line)
                row = prefix.geometry_enrich(row, pool, fr)
                assert row['team_key'] not in rows
                rows[row['team_key']] = row
    return rows


def main():
    pools = {p['pool_id']: p for p in read(OUT / 'pools/INPUT_SNAPSHOT.json')['images']}
    path = ROOT / 'research/workers/personnel_population_curves_v2_20261023/code/run_prefix_endpoints.py'
    spec = importlib.util.spec_from_file_location('v21_prefix_features', path)
    prefix = importlib.util.module_from_spec(spec); spec.loader.exec_module(prefix)
    native = adapter(); engine = native.Engine(full_state=False)
    checks = []
    for folder in sorted(ENDPOINTS.iterdir()):
        if not folder.is_dir() or not (folder / 'CHECKS.json').exists(): continue
        if not read(folder / 'CHECKS.json')['complete']: continue
        pid = folder.name; pool = pools[pid]
        destination = TARGET / (pid + '.csv.gz')
        if destination.exists():
            checks.append(dict(pool_id=pid, prepared=True)); continue
        rows = load_rows(folder, pool, prefix, engine.fr)
        members = {tuple(r['member_workers']): key for key, r in rows.items()}
        assert len(members) == len(rows)
        plan = read(folder / 'DESIGN.json'); links = []
        for p in plan['paths']:
            for k in range(1, len(p['workers']) + 1):
                key = members[tuple(sorted(p['workers'][:k]))]
                row = rows[key]
                record = {c: row.get(c) for c in FIELDS}
                record.update({c: v for c, v in pool['meta'].items() if c in [
                    'image', 'image_id', 'building', 'condition', 'layer', 'difficulty',
                    'pool_n', 'reference_id', 'reference_version']})
                record.update(path_id=pid + '__new256_' + str(p['path_index']),
                              path_index=p['path_index'], stratum='new_space256', policy='natural_random',
                              policy_deferred=k == 2,
                              score_available=row.get('B8L2') is not None,
                              score_failure_nonpolicy=k != 2 and row.get('B8L2') is None,
                              incomplete_nonpolicy=k != 2 and not row.get('complete_evaluable'),
                              data_release='v2.1')
                for c in ['member_workers', 'member_object_ids']:
                    record[c] = '|'.join(record[c])
                links.append(record)
        assert len(links) == 256 * len(pool['records'])
        pd.DataFrame(links).to_csv(destination, index=False, encoding='utf-8-sig')
        checks.append(dict(pool_id=pid, prepared=True, paths=256, rows=len(links), teams=len(rows)))
        print('new space curve inputs', pid, len(links), flush=True)
    (TARGET / 'NEW_SPACE_CHECKS.json').write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
