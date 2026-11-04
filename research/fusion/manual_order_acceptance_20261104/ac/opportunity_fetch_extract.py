"""Fetch exact frozen registration rows for the already identified Q reversals.

This only reads existing source tables.  No team, geometry, or metric is created.
Large downloaded tables are disposable after the exact filtered inputs are saved.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import gzip
import hashlib
import importlib.util
import json
import urllib.request

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
OLD = ROOT / 'research/fusion/manual_order_impact_20261104/ac'
COMMIT = 'ac395e703d1fef573d1ef3e105df0286d62a0468'
REPO = 'Sparkling-Flames/3D_Manhattan_label'
spec = importlib.util.spec_from_file_location('ac_audit', ROOT / 'tools/thesis_main/analysis/audit_manual_order_ac_acceptance_20261104.py')
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)


def main():
    q = pd.read_csv(OUT / 'Q_REVERSALS.csv')
    source_index = pd.read_csv(OLD / 'SOURCE_VERSION_CHECKS.csv')
    tasks = []
    for name in ['COMPLETE_COALITIONS', 'FIXED_BLOCK_BACKGROUND_STEPS', 'SAMPLING_BATCHES', 'MEMBER_PANELS']:
        qs = q[q.analysis_table.eq(name)].drop_duplicates(a.SPECS[name])
        tasks.append((name, f'research/workers/personnel_ac_v21_20261030/stage05_sensitivity/results_v1/{name}.csv.gz', qs, a.SPECS[name]))
    name = 'EXACT_NEUTRAL_OUTSIDE_BACKGROUND_PAIRS'
    tasks.append((name, f'research/workers/personnel_ac_v21_20261030/stage05_sensitivity/exact_outside_background_v1/{name}.csv.gz',
                  q[q.family.eq('exact_background')].drop_duplicates(a.EXACT), a.EXACT))
    dest = OUT / 'inputs/opportunity'
    dest.mkdir(parents=True, exist_ok=True)
    cache = OUT / 'source_cache/opportunity_full_downloads'
    cache.mkdir(parents=True, exist_ok=True)

    def one(task):
        name, source, conditions, keys = task
        expected = source_index[source_index.source.eq(source)].iloc[0]
        full = cache / (name + '.csv.gz')
        url = f'https://raw.githubusercontent.com/{REPO}/{COMMIT}/{source}'
        if not full.exists():
            with urllib.request.urlopen(url, timeout=120) as response, full.open('wb') as stream:
                while data := response.read(1024 * 1024):
                    stream.write(data)
        sha = hashlib.sha256(full.read_bytes()).hexdigest()
        assert sha == expected.sha256, (source, sha, expected.sha256)
        selected = []
        whole_rows = 0
        # Preserve the complete original row schema, but only the exact named
        # conditions used by the Q reversal estimands, including failed rows.
        for chunk in pd.read_csv(full, chunksize=20000, low_memory=False):
            whole_rows += len(chunk)
            keep = pd.Series(False, index=chunk.index)
            for c in conditions.to_dict('records'):
                hit = pd.Series(True, index=chunk.index)
                for k in keys:
                    hit &= chunk[k].map(a.norm).eq(a.norm(c[k]))
                keep |= hit
            if keep.any(): selected.append(chunk[keep])
        frame = pd.concat(selected, ignore_index=True)
        subset = dest / (name + '.csv.gz')
        a.save(frame, subset)
        record = dict(source_repository_commit=COMMIT, source=source, url=url,
                      source_sha256=sha, source_bytes=full.stat().st_size,
                      source_rows=whole_rows, selected_conditions=len(conditions),
                      selection_keys=keys, selection_conditions=conditions[keys].to_dict('records'),
                      subset=str(subset.relative_to(ROOT)), subset_rows=len(frame),
                      subset_pools=frame.pool_id.nunique(), subset_sha256=hashlib.sha256(subset.read_bytes()).hexdigest(),
                      selection_includes_nonfinite_Q_rows=True)
        print(name, len(frame), 'rows', frame.pool_id.nunique(), 'pools', flush=True)
        return record

    with ThreadPoolExecutor(max_workers=3) as executor:
        manifests = list(executor.map(one, tasks))
    a.jsave(OUT / 'OPPORTUNITY_INPUT_MANIFEST.json', manifests)


if __name__ == '__main__':
    main()
