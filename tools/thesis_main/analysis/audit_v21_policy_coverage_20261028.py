"""Check frozen policy endpoint coverage without inventing missing scores."""
import gzip
import json
from pathlib import Path
import pandas as pd
from .rebuild_v21_20261028 import OUT, ROOT, read


def main():
    source = ROOT / 'research/workers/personnel_population_curves_v2_20261023/sampling_extension_20261026/analysis_policy26/results/EXACT_PAIRED_EVENTS.csv.gz'
    affected = {r['pool_id'] for r in read(OUT/'pools/DEPENDENCIES.json') if r['action'] == 'reuse_geometry_rescore'}
    needed = {'old16': set(), 'new16': set()}
    rows = {'old16': 0, 'new16': 0}
    for frame in pd.read_csv(source, usecols=['version','pool_id','k','team_key_natural','team_key_policy'], chunksize=100000):
        frame = frame[frame.pool_id.isin(affected) & frame.k.ne(2)]
        for ver, group in frame.groupby('version'):
            rows[ver] += len(group)
            needed[ver].update(group.team_key_natural)
            needed[ver].update(group.team_key_policy)
    available = set()
    roots = [OUT/'historical_population_rescore', OUT/'population256_rescore']
    for root in roots:
        for path in root.rglob('*.jsonl.gz'):
            with gzip.open(path, 'rt', encoding='utf8') as f:
                for line in f:
                    record = json.loads(line)
                    available.add(record['team_key'])
    target = OUT/'policy_frozen_design'
    target.mkdir(parents=True, exist_ok=True)
    report = {ver: {'affected_events_non_k2': rows[ver], 'required_unique_teams': len(keys), 'available_unique_teams': len(keys & available), 'missing_unique_teams': len(keys - available)} for ver, keys in needed.items()}
    for ver, keys in needed.items():
        (target/(ver+'_MISSING_TEAM_KEYS.txt')).write_text(''.join(k+'\n' for k in sorted(keys-available)), encoding='utf8')
    (target/'COVERAGE.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf8')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
